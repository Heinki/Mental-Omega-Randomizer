"""Archipelago player-YAML lifecycle for the launcher UI."""

from copy import deepcopy
from pathlib import Path

from ._dependencies import filedialog, messagebox, save_config


class ArchipelagoYamlController:
    _ARCHIPELAGO_PROGRESSION_MODES = {
        'Classic', 'Mission List', 'Grid Mode'
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
        mode = str(manifest.get('progression_mode') or '')
        if mode not in self._ARCHIPELAGO_PROGRESSION_MODES:
            raise ValueError(f'unsupported progression mode {mode!r}')
        self.state['progression_mode'] = mode
        self.progression_mode_var.set(mode)
        self.grid_render_signature = None
        self.redraw_mission_tree()

    def _validated_active_archipelago_manifest(self, require_state=True):
        ap_state = self._configured_archipelago_state()
        if ap_state is None:
            raise ValueError(
                'Generate or load an Archipelago YAML for the active run first.'
            )
        manifest = ap_state.get('run_manifest')
        from Archipelago.run_manifest import (
            validate_run_manifest_checksum,
            validate_run_manifest_for_state,
        )
        if require_state:
            validate_run_manifest_for_state(self.state, manifest)
        else:
            validate_run_manifest_checksum(manifest)
        if ap_state.get('manifest_checksum') != manifest.get('manifest_checksum'):
            raise ValueError('Saved Archipelago manifest identity is inconsistent.')
        return manifest

    def refresh_archipelago_yaml_status(self):
        ap_state = self._configured_archipelago_state()
        if ap_state is None or not ap_state.get('manifest_checksum'):
            return
        checksum = str(ap_state['manifest_checksum'])
        seed = self.state.get('seed', '')
        slot = ap_state.get('slot_name', 'Commander')
        mode = str(
            (ap_state.get('slot_data') or {}).get('progression_mode')
            or (ap_state.get('run_manifest') or {}).get(
                'progression_mode', ''
            )
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
                f'AP YAML ready: {seed} | {mode} | '
                f'{checksum[:12]}… | slot {slot}. '
                'Standalone rewards stay active until connection validates.'
            )
            if self.archipelago_status_var.get().startswith('Disconnected'):
                self.archipelago_status_var.set(
                    'Disconnected — standalone rewards active'
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

    def _activate_archipelago_manifest(self, manifest, slot_name, yaml_text):
        from Archipelago.run_manifest import validate_run_manifest_for_state
        validate_run_manifest_for_state(self.state, manifest)
        checksum = manifest['manifest_checksum']
        previous = self.state.get('archipelago')
        same_run = (
            isinstance(previous, dict)
            and previous.get('manifest_checksum') == checksum
        )
        keep_active = bool(same_run and previous.get('enabled'))
        ap_state = {
            'activation': 'active' if keep_active else 'staged',
            'enabled': keep_active,
            'manifest_checksum': checksum,
            'run_manifest': deepcopy(manifest),
            'slot_name': slot_name,
        }
        if same_run:
            for key in (
                'server', 'checkpoint', 'received_rewards', 'slot_data'
            ):
                if key in previous:
                    ap_state[key] = deepcopy(previous[key])
        self.state['archipelago'] = ap_state
        self.archipelago_slot_var.set(slot_name)
        ap_config = self.config.setdefault('archipelago', {})
        ap_config['enabled'] = keep_active
        ap_config['slot_name'] = slot_name
        self._archipelago_yaml_text = yaml_text
        self._apply_manifest_launcher_settings(manifest)
        self.state['earned_rewards'] = self.earned_rewards_from_checks()
        self.save_state()
        save_config(self.config)
        self.refresh_archipelago_yaml_status()
        self.update_header_summary()
        self.redraw_mission_tree()
        self.refresh_progress_view()

    def generate_archipelago_yaml(self):
        if self.gameplay_settings_locked():
            return None
        if not self.state:
            self.append_archipelago_history(
                'Generate a Randomizer seed before generating player YAML.'
            )
            return None
        try:
            from Archipelago.run_manifest import build_run_manifest
            from Archipelago.yaml_config import serialize_player_yaml
            self.save_current_launcher_config()
            manifest = build_run_manifest(self.state, self.config)
            slot_name = self.archipelago_slot_var.get().strip() or 'Commander'
            yaml_text = serialize_player_yaml(manifest, slot_name)
            self._activate_archipelago_manifest(
                manifest, slot_name, yaml_text
            )
        except Exception as exc:
            self.append_archipelago_history(f'YAML generation failed: {exc}')
            return None
        self.append_archipelago_history(
            'Generated Archipelago YAML. Standalone rewards remain active '
            'until the server connection validates.'
            if not self.archipelago_run_active()
            else 'Regenerated YAML for the active Archipelago run.'
        )
        return yaml_text

    def save_archipelago_yaml(self):
        yaml_text = self._archipelago_yaml_text
        if not yaml_text:
            try:
                from Archipelago.yaml_config import serialize_player_yaml
                manifest = self._validated_active_archipelago_manifest()
                slot_name = self.archipelago_slot_var.get().strip() or 'Commander'
                yaml_text = serialize_player_yaml(manifest, slot_name)
                self._archipelago_yaml_text = yaml_text
            except Exception:
                yaml_text = ''
        if not yaml_text:
            yaml_text = self.generate_archipelago_yaml()
        if not yaml_text:
            return
        path = filedialog.asksaveasfilename(
            parent=self,
            title='Save Archipelago Player YAML',
            defaultextension='.yaml',
            initialfile=(
                f'{self.archipelago_slot_var.get().strip() or "Commander"}.yaml'
            ),
            filetypes=(
                ('Archipelago player YAML', '*.yaml'),
                ('All files', '*.*'),
            ),
        )
        if not path:
            return
        try:
            from randomizer.core.storage import atomic_write_text
            atomic_write_text(Path(path), yaml_text)
        except Exception as exc:
            self.append_archipelago_history(f'YAML save failed: {exc}')
            return
        self.append_archipelago_history(f'Saved Archipelago YAML: {path}')

    def load_archipelago_yaml(self):
        if self.gameplay_settings_locked():
            return
        path = filedialog.askopenfilename(
            parent=self,
            title='Load Archipelago Player YAML',
            filetypes=(
                ('Archipelago player YAML', '*.yaml *.yml'),
                ('All files', '*.*'),
            ),
        )
        if not path:
            return
        try:
            from Archipelago.yaml_config import parse_player_yaml
            yaml_text = Path(path).read_text(encoding='utf-8-sig')
            document = parse_player_yaml(yaml_text)
            manifest = document['run_manifest']
            frozen = manifest.get('frozen_settings', {})
            expected_settings = (
                frozen.get('launcher') if isinstance(frozen, dict) else None
            )
            edited_settings = document['launcher_settings']
            if not isinstance(expected_settings, dict) or not expected_settings:
                raise ValueError('Run manifest has no launcher settings.')
            if edited_settings != expected_settings:
                self._import_edited_archipelago_settings(
                    edited_settings, document['name']
                )
                return
            self._activate_archipelago_manifest(
                manifest, document['name'], yaml_text
            )
        except Exception as exc:
            self.append_archipelago_history(f'YAML load failed: {exc}')
            return
        self.append_archipelago_history(f'Loaded Archipelago YAML: {path}')

    def _import_edited_archipelago_settings(self, settings, slot_name):
        self._apply_archipelago_launcher_settings(settings)
        self.archipelago_slot_var.set(slot_name)
        self.config.setdefault('archipelago', {})['slot_name'] = slot_name
        save_config(self.config)
        self._archipelago_yaml_text = ''
        self.archipelago_yaml_status_var.set(
            'Edited YAML settings loaded. Generate New Seed, then '
            'Generate YAML again.'
        )
        self.append_archipelago_history(
            'Imported edited YAML settings for the next seed. '
            'Generate New Seed, then regenerate/save the player YAML '
            'before Archipelago generation.'
        )
        self.workspace_tabs.select(self.settings_tab)
        messagebox.showinfo(
            'Archipelago Settings Imported',
            'The readable YAML settings were changed and are now '
            'loaded into the launcher.\n\nGenerate New Seed, then '
            'return to Archipelago and Generate/Save YAML again.',
            parent=self,
        )
