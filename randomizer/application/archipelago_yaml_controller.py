"""Archipelago player-YAML export and active-run identity."""

from copy import deepcopy
from pathlib import Path

from ._dependencies import filedialog, log_event, time


class ArchipelagoYamlController:
    _ARCHIPELAGO_PROGRESSION_MODES = {
        'Classic', 'Mission List', 'Grid Mode', 'Shop Mode'
    }

    @staticmethod
    def _archipelago_manifest_identity(manifest):
        """Persist only identity; full generated data comes from the server."""
        keys = (
            'schema_version', 'randomizer_version', 'randomizer_seed',
            'catalogue_checksum', 'manifest_checksum', 'campaign_filter',
            'progression_mode', 'mission_goal', 'mission_order', 'goal', 'shop',
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
                f'Reusable Player YAML saved: {mode} | '
                f'{checksum[:12]}… | slot {slot}. '
                'Each generated AP room gets a fresh Randomizer seed.'
                if seed == 'random'
                else (
                    f'Player YAML saved: {seed} | {mode} | '
                    f'{checksum[:12]}… | slot {slot}. '
                    'Connect to load the generated run from the server.'
                )
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

    def save_archipelago_yaml(self):
        """Export one AP player file from the exact visible launcher controls."""
        if self.gameplay_settings_locked():
            return
        slot_name = self.archipelago_slot_var.get().strip() or 'Commander'
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
            return

        try:
            from Archipelago.yaml_config import serialize_player_yaml
            from randomizer.core.storage import atomic_write_text

            yaml_text = serialize_player_yaml(launcher_config, slot_name)
            atomic_write_text(Path(path), yaml_text)
            self._archipelago_yaml_text = yaml_text
            self.archipelago_yaml_status_var.set(
                f'Player YAML saved: {slot_name}. '
                'Archipelago generates a fresh run for every new seed.'
            )
            self.append_archipelago_history(f'Saved Player YAML: {path}')
        except Exception as exc:
            self.append_archipelago_history(f'Player YAML save failed: {exc}')
            self.handle_seed_generation_error(exc, str(exc))
