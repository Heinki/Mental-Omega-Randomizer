"""Archipelago player-YAML export and active-run identity."""

from copy import deepcopy
from pathlib import Path

from ._dependencies import filedialog, log_event, save_config, time


class ArchipelagoYamlController:
    _ARCHIPELAGO_PROGRESSION_MODES = {
        'Classic', 'Mission List', 'Grid Mode'
    }

    @staticmethod
    def _archipelago_manifest_identity(manifest):
        """Persist only identity; full generated data lives in YAML/server."""
        keys = (
            'schema_version', 'randomizer_version', 'randomizer_seed',
            'catalogue_checksum', 'manifest_checksum', 'campaign_filter',
            'progression_mode', 'mission_goal', 'mission_order', 'goal',
        )
        return {
            key: deepcopy(manifest[key])
            for key in keys
            if key in manifest
        }

    def archipelago_progression_mode(self):
        """Return signed AP mode only after this run becomes active."""
        ap_state = self._active_archipelago_state()
        if ap_state is None:
            return None
        for source in (
            ap_state.get('slot_data'),
            ap_state.get('run_manifest'),
        ):
            if not isinstance(source, dict):
                continue
            mode = str(source.get('progression_mode') or '')
            if mode in self._ARCHIPELAGO_PROGRESSION_MODES:
                return mode
        return None

    def _synchronize_archipelago_progression_ui(self, manifest):
        """Apply signed mode and rebuild mission presentation immediately."""
        started = time.perf_counter()
        previous_seed = str(self.state.get('seed') or '')
        previous_mode = str(self.state.get('progression_mode') or '')
        previous_nodes = len((self.state.get('grid') or {}).get('nodes', {}))
        mode = str(manifest.get('progression_mode') or '')
        if mode not in self._ARCHIPELAGO_PROGRESSION_MODES:
            raise ValueError(f'unsupported progression mode {mode!r}')
        self.state['progression_mode'] = mode
        self.progression_mode_var.set(mode)
        self.grid_render_signature = None
        self.redraw_mission_tree()
        log_event(
            'archipelago_progression_ui_synchronized',
            previous_seed=previous_seed,
            active_seed=self.state.get('seed', ''),
            previous_mode=previous_mode,
            active_mode=mode,
            previous_grid_nodes=previous_nodes,
            active_grid_nodes=len(
                (self.state.get('grid') or {}).get('nodes', {})
            ),
            manifest_checksum=manifest.get('manifest_checksum', ''),
            elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
        )

    def refresh_archipelago_yaml_status(self):
        ap_state = self._configured_archipelago_state()
        if ap_state is None or not ap_state.get('manifest_checksum'):
            return
        manifest = ap_state.get('run_manifest') or {}
        checksum = str(ap_state['manifest_checksum'])
        seed = str(manifest.get('randomizer_seed') or '')
        slot = ap_state.get('slot_name', 'Commander')
        mode = str(
            (ap_state.get('slot_data') or {}).get('progression_mode')
            or manifest.get('progression_mode', '')
        )
        if ap_state.get('enabled'):
            status = (
                f'Active AP run: {seed} | {mode} | '
                f'{checksum[:12]}… | slot {slot}'
            )
            if self.archipelago_status_var.get().startswith('Disconnected'):
                self.archipelago_status_var.set(
                    'Disconnected — AP run active'
                )
        else:
            status = (
                f'Player YAML saved: {seed} | {mode} | '
                f'{checksum[:12]}… | slot {slot}. '
                'Connect to load the generated run from the server.'
            )
            if self.archipelago_status_var.get().startswith('Disconnected'):
                self.archipelago_status_var.set(
                    'Disconnected — Player YAML ready'
                )
        self.archipelago_yaml_status_var.set(status)

    def _apply_manifest_launcher_settings(self, manifest):
        frozen = manifest.get('frozen_settings', {})
        snapshot = frozen.get('launcher', {}) if isinstance(frozen, dict) else {}
        if not isinstance(snapshot, dict) or not snapshot:
            return
        self._apply_archipelago_launcher_settings(snapshot)

    def _apply_archipelago_launcher_settings(self, snapshot):
        merged = deepcopy(self.config)
        saved_archipelago = deepcopy(merged.get('archipelago', {}))
        for key, value in snapshot.items():
            merged[key] = deepcopy(value)
        merged['archipelago'] = saved_archipelago
        self.apply_portable_settings(merged)

    def _current_standalone_state_snapshot(self):
        """Return local progress without embedding AP runtime state."""
        existing_ap = self._configured_archipelago_state() or {}
        saved_state = existing_ap.get('standalone_state')
        if isinstance(saved_state, dict) and not saved_state:
            # Saving AP YAML with no existing local seed temporarily presents
            # the generated run. Disconnect must return to the original empty
            # standalone state, not that generated AP preview.
            return {}
        standalone_state = deepcopy(self.state)
        standalone_state.pop('archipelago', None)
        return standalone_state

    def _stage_archipelago_manifest(
        self, manifest, slot_name, yaml_text, generated_state
    ):
        """Remember exported identity; server state remains authoritative."""
        standalone_state = self._current_standalone_state_snapshot()
        standalone_config = deepcopy(self.config)
        if not self.state:
            self.state = deepcopy(generated_state)
        self.state['archipelago'] = {
            'activation': 'staged',
            'enabled': False,
            'manifest_checksum': manifest['manifest_checksum'],
            'run_manifest': self._archipelago_manifest_identity(manifest),
            'slot_name': slot_name,
            'standalone_state': standalone_state,
            'standalone_config': standalone_config,
        }
        self._archipelago_standalone_state = deepcopy(standalone_state)
        self._archipelago_standalone_config = deepcopy(standalone_config)
        self.archipelago_slot_var.set(slot_name)
        ap_config = self.config.setdefault('archipelago', {})
        ap_config['enabled'] = False
        ap_config['slot_name'] = slot_name
        self._archipelago_yaml_text = yaml_text
        self.save_state()
        save_config(self.config)
        self.refresh_archipelago_yaml_status()
        log_event(
            'archipelago_player_yaml_staged',
            randomizer_seed=manifest.get('randomizer_seed', ''),
            progression_mode=manifest.get('progression_mode', ''),
            manifest_checksum=manifest.get('manifest_checksum', ''),
            missions=len(manifest.get('mission_order', ())),
            yaml_bytes=len(yaml_text.encode('utf-8')),
        )

    def save_archipelago_yaml(self):
        """Export one AP player file from the exact visible launcher controls."""
        if self.gameplay_settings_locked():
            return
        slot_name = self.archipelago_slot_var.get().strip() or 'Commander'
        options = self.seed_generation_options_from_settings()
        if options is None:
            return

        self.config.setdefault('archipelago', {})['slot_name'] = slot_name
        self.save_current_launcher_config()
        launcher_config = deepcopy(self.config)
        path = filedialog.asksaveasfilename(
            parent=self,
            title='Save Archipelago Player YAML',
            defaultextension='.yaml',
            initialfile=f'{slot_name}.yaml',
            filetypes=(
                ('Archipelago player YAML', '*.yaml'),
                ('All files', '*.*'),
            ),
        )
        if not path:
            self.clear_seed_generation_overrides()
            return

        self.run_in_background(
            'Saving Archipelago Player YAML...',
            'Building the AP run from the current launcher settings.',
            lambda: self.build_seed_generation(options),
            lambda result: self._finish_archipelago_yaml_save(
                result, Path(path), slot_name, launcher_config
            ),
            self._handle_archipelago_yaml_save_error,
        )

    def _finish_archipelago_yaml_save(
        self, result, path, slot_name, launcher_config
    ):
        try:
            from Archipelago.run_manifest import build_run_manifest
            from Archipelago.yaml_config import serialize_player_yaml
            from randomizer.core.storage import atomic_write_text

            manifest = build_run_manifest(result['state'], launcher_config)
            yaml_text = serialize_player_yaml(manifest, slot_name)
            atomic_write_text(path, yaml_text)
            self._stage_archipelago_manifest(
                manifest, slot_name, yaml_text, result['state']
            )
        finally:
            self.clear_seed_generation_overrides()
        self.append_archipelago_history(f'Saved Player YAML: {path}')

    def _handle_archipelago_yaml_save_error(self, exc, detail):
        self.clear_seed_generation_overrides()
        self.append_archipelago_history(f'Player YAML save failed: {exc}')
        self.handle_seed_generation_error(exc, detail)
