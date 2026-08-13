"""Launcher adapter for the isolated Archipelago session worker."""

from copy import deepcopy
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

from .archipelago_yaml_controller import ArchipelagoYamlController

from ._dependencies import (
    REWARD_BY_NAME,
    canonical_reward,
    log_event,
    logging,
    reward_display_name,
    save_config,
    threading,
)


class ArchipelagoController(ArchipelagoYamlController):
    def gameplay_settings_locked(self):
        return bool(getattr(self, '_archipelago_gameplay_locked', False))

    @staticmethod
    def _widget_descendants(root):
        result = []
        pending = list(root.winfo_children())
        while pending:
            widget = pending.pop()
            result.append(widget)
            pending.extend(widget.winfo_children())
        return result

    def initialize_archipelago_control_registry(self):
        """Maintain the complete set of gameplay-affecting UI controls."""
        excluded = set(self._widget_descendants(self.appearance_frame))
        excluded.add(self.appearance_frame)
        candidates = [
            *self._widget_descendants(self.settings_frame),
            *self._widget_descendants(self.advanced_tab),
            self.archipelago_save_yaml_button,
        ]
        stateful = []
        interactive_classes = {
            'TButton', 'TCheckbutton', 'TRadiobutton', 'TEntry',
            'TSpinbox', 'TCombobox', 'TScale', 'Treeview',
        }
        for widget in candidates:
            if widget in excluded or widget in stateful:
                continue
            if str(widget.winfo_class()) not in interactive_classes:
                continue
            try:
                widget.cget('state')
            except Exception:
                continue
            stateful.append(widget)
        self._archipelago_gameplay_widgets = tuple(stateful)
        self._archipelago_connection_widgets = (
            self.archipelago_server_entry,
            self.archipelago_port_entry,
            self.archipelago_slot_entry,
            self.archipelago_password_entry,
        )

    def _enforce_archipelago_control_lock(self):
        if not self.gameplay_settings_locked():
            return
        for widget in self._archipelago_gameplay_widgets:
            try:
                widget.configure(state='disabled')
            except Exception:
                pass

    def set_archipelago_controls_locked(self, locked):
        locked = bool(locked)
        if locked == self.gameplay_settings_locked():
            if locked:
                self._enforce_archipelago_control_lock()
            return
        widgets = (
            *self._archipelago_gameplay_widgets,
            *self._archipelago_connection_widgets,
        )
        if locked:
            saved = {}
            for widget in widgets:
                try:
                    saved[widget] = str(widget.cget('state'))
                    widget.configure(state='disabled')
                except Exception:
                    continue
            self._archipelago_locked_widget_states = saved
            self._archipelago_gameplay_locked = True
            return
        self._archipelago_gameplay_locked = False
        saved = self._archipelago_locked_widget_states
        self._archipelago_locked_widget_states = {}
        for widget, state in saved.items():
            try:
                widget.configure(state=state)
            except Exception:
                continue
        self.refresh_setting_states()

    def _configured_archipelago_state(self):
        if not self.state:
            return None
        ap_state = self.state.get('archipelago')
        if (
            not isinstance(ap_state, dict)
            or not ap_state.get('manifest_checksum')
            or not isinstance(ap_state.get('run_manifest'), dict)
        ):
            return None
        return ap_state

    def _active_archipelago_state(self):
        ap_state = self._configured_archipelago_state()
        if ap_state is None or not ap_state.get('enabled'):
            return None
        return ap_state

    def archipelago_run_staged(self):
        ap_state = self._configured_archipelago_state()
        return ap_state is not None and not ap_state.get('enabled')

    def archipelago_run_active(self):
        return self._active_archipelago_state() is not None

    @staticmethod
    def _standalone_archipelago_config(current, saved):
        """Restore gameplay settings while retaining connection identity."""
        restored = deepcopy(saved)
        restored_ap = restored.setdefault('archipelago', {})
        current_ap = current.get('archipelago', {})
        for key in ('server', 'port', 'slot_name', 'client_uuid'):
            if key in current_ap:
                restored_ap[key] = deepcopy(current_ap[key])
        restored_ap['enabled'] = False
        return restored

    def _capture_archipelago_standalone_context(self):
        """Freeze the local run and launcher settings before AP takes over."""
        if self.archipelago_run_active():
            return
        self.save_current_launcher_config()
        self._archipelago_standalone_state = (
            self._current_standalone_state_snapshot()
        )
        self._archipelago_standalone_config = deepcopy(self.config)

    def restore_archipelago_context_on_startup(self, loaded_state):
        """Recover standalone context after a launcher exit during AP play."""
        if not isinstance(loaded_state, dict):
            return loaded_state, False
        ap_state = loaded_state.get('archipelago')
        if not isinstance(ap_state, dict) or not ap_state.get('enabled'):
            return loaded_state, False
        standalone_state = ap_state.get('standalone_state')
        standalone_config = ap_state.get('standalone_config')
        if not isinstance(standalone_state, dict) or not standalone_config:
            return loaded_state, False

        self._archipelago_cached_state = deepcopy(loaded_state)
        self._archipelago_standalone_state = deepcopy(standalone_state)
        self._archipelago_standalone_config = self._standalone_archipelago_config(
            self.config, standalone_config
        )
        self.config = deepcopy(self._archipelago_standalone_config)
        save_config(self.config)
        self.dark_mode_var.set(bool(self.config.get('dark_mode', False)))
        self.hide_reward_details_var.set(bool(
            self.config.get('hide_reward_details', False)
        ))
        self.hide_locked_grid_missions_var.set(bool(
            self.config.get('hide_locked_grid_missions', False)
        ))
        log_event(
            'archipelago_standalone_context_restored_on_startup',
            seed=standalone_state.get('seed', ''),
        )
        return deepcopy(standalone_state), True

    def _restore_archipelago_standalone_context(self, refresh=True):
        """Switch from server-owned AP state back to the saved local run."""
        active_state = self._active_archipelago_state()
        if active_state is None:
            self._archipelago_session_validated = False
            return False

        standalone_state = self._archipelago_standalone_state
        standalone_config = self._archipelago_standalone_config
        if not isinstance(standalone_state, dict):
            standalone_state = active_state.get('standalone_state')
        if not isinstance(standalone_config, dict):
            standalone_config = active_state.get('standalone_config')
        if not isinstance(standalone_state, dict) or not standalone_config:
            log_event(
                'archipelago_standalone_context_missing',
                level=logging.ERROR,
            )
            return False

        self._archipelago_cached_state = deepcopy(self.state)
        restored_config = self._standalone_archipelago_config(
            self.config, standalone_config
        )
        self.state = deepcopy(standalone_state)
        self._archipelago_standalone_state = deepcopy(self.state)
        self._archipelago_standalone_config = deepcopy(restored_config)
        self._archipelago_session_validated = False
        self._archipelago_slot_data = {}
        self._archipelago_item_names = {}
        self._archipelago_players = {}
        self._archipelago_location_info = {}
        self._archipelago_server_checked_locations = set()
        self._archipelago_displayed_receipts = set()
        self.apply_portable_settings(restored_config)
        self.save_state()
        if refresh:
            self._refresh_archipelago_server_views()
            if self._configured_archipelago_state() is not None:
                self.refresh_archipelago_yaml_status()
            else:
                self.archipelago_yaml_status_var.set(
                    'Save a Player YAML from the current Settings-page values.'
                )
        log_event(
            'archipelago_standalone_context_restored',
            seed=self.state.get('seed', ''),
        )
        return True

    def reset_archipelago_after_new_seed(self):
        """Return UI/config identity to standalone after state replacement."""
        self.config.setdefault('archipelago', {})['enabled'] = False
        self._archipelago_yaml_text = ''
        self._archipelago_session_validated = False
        self._archipelago_slot_data = {}
        self._archipelago_item_names = {}
        self._archipelago_players = {}
        self._archipelago_location_info = {}
        self._archipelago_server_checked_locations = set()
        self._archipelago_displayed_receipts = set()
        self._archipelago_standalone_state = None
        self._archipelago_standalone_config = None
        self._archipelago_cached_state = None
        self._set_archipelago_chat_enabled(False)
        self.archipelago_status_var.set('Disconnected')
        self.archipelago_yaml_status_var.set(
            'Save a Player YAML from the current Settings-page values.'
        )
        self.archipelago_status_label.configure(
            style='Archipelago.Disconnected.TLabel'
        )

    def _promote_archipelago_run(self):
        ap_state = self._configured_archipelago_state()
        if ap_state is None:
            raise ValueError('No staged Archipelago run is available.')
        ap_state['activation'] = 'active'
        ap_state['enabled'] = True
        self.config.setdefault('archipelago', {})['enabled'] = True
        self.state['earned_rewards'] = self.earned_rewards_from_checks()
        self.save_state()
        save_config(self.config)
        self.refresh_archipelago_yaml_status()
        self.update_header_summary()
        self.refresh_progress_view()

    def _archipelago_endpoint(self):
        server = self.archipelago_server_var.get().strip()
        if not server:
            raise ValueError('Archipelago server is required.')
        try:
            port = int(self.archipelago_port_var.get())
        except (TypeError, ValueError) as exc:
            raise ValueError('Archipelago port must be a number.') from exc
        if not 1 <= port <= 65535:
            raise ValueError('Archipelago port must be between 1 and 65535.')

        if '://' not in server:
            scheme = (
                'wss'
                if server.rstrip('.').casefold() == 'archipelago.gg'
                else 'ws'
            )
            return f'{scheme}://{server}:{port}'
        parsed = urlsplit(server)
        if parsed.scheme not in {'ws', 'wss'} or not parsed.hostname:
            raise ValueError('Archipelago server must use ws:// or wss://.')
        host = f'[{parsed.hostname}]' if ':' in parsed.hostname else parsed.hostname
        netloc = f'{host}:{parsed.port or port}'
        scheme = (
            'wss'
            if parsed.hostname.rstrip('.').casefold() == 'archipelago.gg'
            else parsed.scheme
        )
        return urlunsplit((scheme, netloc, parsed.path or '/', '', ''))

    def _set_archipelago_chat_enabled(self, enabled):
        state = 'normal' if enabled else 'disabled'
        for widget_name in (
            'archipelago_chat_entry',
            'archipelago_chat_button',
        ):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                widget.configure(state=state)

    def send_archipelago_chat(self, _event=None):
        text = self.archipelago_chat_var.get().strip()
        if not text:
            return 'break'
        session = getattr(self, '_archipelago_session', None)
        if (
            session is None
            or not self._archipelago_session_validated
            or not session.send_chat(text)
        ):
            self.archipelago_status_var.set(
                'Chat unavailable — connect to Archipelago first'
            )
            self._set_archipelago_chat_enabled(False)
            return 'break'
        self.archipelago_chat_var.set('')
        return 'break'

    def _archipelago_saved_checkpoint(self, endpoint, slot_name):
        ap_state = self.state.get('archipelago', {}) if self.state else {}
        cached_state = getattr(self, '_archipelago_cached_state', None)
        cached_ap = (
            cached_state.get('archipelago', {})
            if isinstance(cached_state, dict) else {}
        )
        if not isinstance(ap_state, dict) or not ap_state.get('enabled'):
            ap_state = cached_ap
        if not isinstance(ap_state, dict) or not ap_state.get('enabled'):
            return None
        if ap_state.get('server') != endpoint or ap_state.get('slot_name') != slot_name:
            return None
        checkpoint = ap_state.get('checkpoint')
        return checkpoint if isinstance(checkpoint, dict) else None

    def connect_archipelago(self):
        session = getattr(self, '_archipelago_session', None)
        if session is not None and session.running:
            return
        try:
            if getattr(self, 'busy_depth', 0):
                raise ValueError('Wait for the current launcher task to finish.')
            from Archipelago.client import ArchipelagoSession, SessionConfig

            endpoint = self._archipelago_endpoint()
            slot_name = self.archipelago_slot_var.get().strip()
            config = SessionConfig(
                server=endpoint,
                slot_name=slot_name,
                password=self.archipelago_password_var.get(),
                client_uuid=self.archipelago_client_uuid,
            )
            checkpoint = self._archipelago_saved_checkpoint(
                config.normalized().server,
                slot_name,
            )
            session = ArchipelagoSession(
                config,
                event_callback=lambda event: self.ui_queue.put(
                    ('archipelago', event)
                ),
                checkpoint=checkpoint,
            )
        except Exception as exc:
            self._archipelago_connection_error = str(exc)
            self.archipelago_status_var.set(f'Connection failed — {exc}')
            self.append_archipelago_history(f'Connection setup failed: {exc}')
            log_event(
                'archipelago_connection_setup_failed',
                level=logging.ERROR,
                error=str(exc),
            )
            return

        self._capture_archipelago_standalone_context()

        ap_config = self.config.setdefault('archipelago', {})
        ap_config['server'] = self.archipelago_server_var.get().strip()
        ap_config['port'] = int(self.archipelago_port_var.get())
        ap_config['slot_name'] = slot_name
        ap_config['client_uuid'] = self.archipelago_client_uuid
        save_config(self.config)

        self._archipelago_session = session
        self._archipelago_connection_error = ''
        self._archipelago_session_validated = False
        self._archipelago_displayed_receipts = set()
        self._set_archipelago_chat_enabled(False)
        self.archipelago_connect_button.configure(state='disabled')
        self.archipelago_disconnect_button.configure(state='normal')
        self.set_archipelago_controls_locked(True)
        self.append_archipelago_history(f'Connecting to {session.config.server}…')
        session.start()

    def disconnect_archipelago(self):
        session = getattr(self, '_archipelago_session', None)
        if session is None:
            return
        self.archipelago_status_var.set('Disconnecting')
        self.archipelago_status_label.configure(
            style='Archipelago.Waiting.TLabel'
        )
        self.archipelago_disconnect_button.configure(state='disabled')
        self._set_archipelago_chat_enabled(False)

        def stop_worker():
            session.stop(timeout=5.0)

        threading.Thread(
            target=stop_worker,
            name='MentalOmegaArchipelagoStop',
            daemon=True,
        ).start()

    def shutdown_archipelago(self):
        session = getattr(self, '_archipelago_session', None)
        if session is not None:
            session.stop(timeout=2.5)
        self._restore_archipelago_standalone_context(refresh=False)

    def handle_archipelago_event(self, event):
        if event.kind == 'status':
            state = str(event.payload.get('state', 'disconnected'))
            if state == 'disconnected':
                self._restore_archipelago_standalone_context()
                self._archipelago_session = None
            if state == 'connected' and not self._archipelago_session_validated:
                label = 'Authenticating Archipelago slot'
            elif state == 'connected':
                label = 'Connected — AP rewards active'
            elif state == 'reconnecting':
                label = 'Reconnecting — AP run active'
            elif state == 'connecting':
                label = (
                    'Connecting — AP run active'
                    if self.archipelago_run_active()
                    else 'Connecting — standalone rewards active'
                )
            elif state == 'disconnected':
                connection_error = getattr(
                    self, '_archipelago_connection_error', ''
                )
                if connection_error:
                    label = f'Connection failed — {connection_error}'
                else:
                    label = (
                        'Disconnected — AP run active'
                        if self.archipelago_run_active()
                        else 'Disconnected — standalone rewards active'
                        if self.archipelago_run_staged()
                        else 'Disconnected'
                    )
            else:
                label = state.title()
            self.archipelago_status_var.set(label)
            status_style = {
                'connected': 'Archipelago.Connected.TLabel',
                'connecting': 'Archipelago.Waiting.TLabel',
                'reconnecting': 'Archipelago.Waiting.TLabel',
            }.get(state, 'Archipelago.Disconnected.TLabel')
            self.archipelago_status_label.configure(style=status_style)
            connected_or_waiting = state in {
                'connecting', 'reconnecting', 'connected'
            }
            self.set_archipelago_controls_locked(connected_or_waiting)
            self.archipelago_connect_button.configure(
                state='disabled' if connected_or_waiting else 'normal'
            )
            self.archipelago_disconnect_button.configure(
                state='normal' if connected_or_waiting else 'disabled'
            )
            self._set_archipelago_chat_enabled(
                state == 'connected'
                and self._archipelago_session_validated
            )
            if state != getattr(self, '_archipelago_last_status', None):
                self.append_archipelago_history(label)
                self._archipelago_last_status = state
            return
        if event.kind == 'connected':
            result = event.payload
            self._archipelago_connection_error = ''
            try:
                item_names = self._validate_archipelago_item_mapping(
                    result.slot_data
                )
                from Archipelago.catalogue_contract import (
                    runtime_catalogue_checksum,
                )
                expected_checksum = runtime_catalogue_checksum()
                if result.slot_data.get('catalogue_checksum') != expected_checksum:
                    raise ValueError(
                        'reward/mission catalogue checksum does not match '
                        'this launcher installation'
                    )
                slot_manifest = result.slot_data.get('run_manifest')
                self._validate_archipelago_server_state(result.slot_data)
            except ValueError as exc:
                self.append_archipelago_history(
                    f'Connected slot item catalogue is incompatible: {exc}'
                )
                self.disconnect_archipelago()
                return
            self.append_archipelago_history(
                f'Authenticated: seed {result.seed_name}, '
                f'team {result.team + 1}, slot {result.slot}.'
            )
            active_session = getattr(self, '_archipelago_session', None)
            if active_session is None:
                self.append_archipelago_history(
                    'Connected session disappeared before validation completed.'
                )
                return
            self._archipelago_session_validated = True
            self._load_archipelago_server_state(
                result,
                item_names,
                active_session,
            )
            self._apply_manifest_launcher_settings(slot_manifest)
            self._synchronize_archipelago_progression_ui(slot_manifest)
            self._promote_archipelago_run()
            self._set_archipelago_chat_enabled(True)
            self.archipelago_status_var.set(
                'Connected — AP rewards active'
            )
            self.reconcile_archipelago_checks()
            self._refresh_archipelago_server_views()
            return
        if event.kind == 'checkpoint':
            self._persist_archipelago_checkpoint(event.payload)
            return
        if event.kind == 'received_items':
            applied_indexes = self.apply_archipelago_received_items(
                event.payload
            )
            if applied_indexes:
                self._refresh_archipelago_server_views()
            return
        if event.kind == 'received_metadata':
            if self._merge_archipelago_received_metadata(event.payload):
                self.save_state()
                self._refresh_archipelago_server_views()
            return
        if event.kind == 'location_info':
            if self._store_archipelago_location_info(event.payload):
                self.save_state()
                self.refresh_progress_view()
            return
        if event.kind == 'locations_checked':
            incoming = {
                int(value) for value in (event.payload or ())
            }
            changed = self._apply_archipelago_server_locations(incoming)
            locations = ', '.join(str(value) for value in event.payload)
            self.append_archipelago_history(
                f'Server synchronized checked locations: {locations}.'
            )
            if changed:
                self.save_state()
                self._refresh_archipelago_server_views()
            return
        if event.kind == 'desynchronized':
            self.append_archipelago_history(
                'Item index mismatch detected; requested full synchronization.'
            )
            return
        if event.kind == 'message' and event.payload:
            self.append_archipelago_server_message(event.payload)
            return
        if event.kind == 'error':
            message = str(event.payload.get('message', 'Unknown network error.'))
            self._archipelago_connection_error = message
            self.archipelago_status_var.set(f'Connection failed — {message}')
            self.append_archipelago_history(f'Network error: {message}')
            log_event(
                'archipelago_client_error',
                level=(
                    logging.ERROR
                    if event.payload.get('fatal') else logging.WARNING
                ),
                error=message,
                fatal=bool(event.payload.get('fatal')),
            )

    def _persist_archipelago_checkpoint(self, checkpoint):
        ap_state = self._active_archipelago_state()
        if ap_state is None:
            return
        if not getattr(self, '_archipelago_session_validated', False):
            return
        session = getattr(self, '_archipelago_session', None)
        if session is None:
            return
        ap_state['server'] = session.config.server
        ap_state['slot_name'] = session.config.slot_name
        ap_state['checkpoint'] = checkpoint
        self.save_state()

    @staticmethod
    def _validate_archipelago_item_mapping(slot_data):
        values = slot_data.get('items', {})
        if not isinstance(values, dict) or not values:
            raise ValueError('slot data has no item mapping')
        item_names = {}
        try:
            for item_id, reward_name in values.items():
                item_id = int(item_id)
                reward_name = str(reward_name).strip()
                if item_id <= 0 or not reward_name or item_id in item_names:
                    raise ValueError
                item_names[item_id] = reward_name
        except (TypeError, ValueError) as exc:
            raise ValueError('slot data item mapping is invalid') from exc
        unknown = sorted({
            reward_name
            for reward_name in item_names.values()
            if reward_name not in REWARD_BY_NAME
        })
        if unknown:
            preview = ', '.join(unknown[:3])
            if len(unknown) > 3:
                preview += f', +{len(unknown) - 3} more'
            raise ValueError(f'unknown Randomizer reward(s): {preview}')
        return item_names

    @staticmethod
    def _validate_archipelago_server_state(slot_data):
        manifest = slot_data.get('run_manifest')
        snapshot = (
            manifest.get('state_snapshot')
            if isinstance(manifest, dict) else None
        )
        if not isinstance(snapshot, dict):
            raise ValueError('server manifest has no state snapshot')
        mission_order = slot_data.get('mission_order')
        if (
            snapshot.get('seed') != slot_data.get('randomizer_seed')
            or snapshot.get('mission_order') != mission_order
            or snapshot.get('progression_mode')
            != slot_data.get('progression_mode')
            or not isinstance(snapshot.get('mission_checks'), dict)
        ):
            raise ValueError('server state snapshot identity is invalid')
        for code, mapped_checks in slot_data.get('locations', {}).items():
            checks = snapshot['mission_checks'].get(code)
            if not isinstance(checks, list):
                raise ValueError(f'server state has no checks for {code}')
            check_ids = {
                str(check.get('id'))
                for check in checks
                if isinstance(check, dict) and check.get('id')
            }
            if not set(mapped_checks).issubset(check_ids):
                raise ValueError(f'server state misses active checks for {code}')
        return snapshot

    def _load_archipelago_server_state(
        self, result, item_names, active_session
    ):
        """Replace local run fields with signed server state after validation."""
        snapshot = self._validate_archipelago_server_state(result.slot_data)
        slot_manifest = result.slot_data['run_manifest']
        cached_state = getattr(self, '_archipelago_cached_state', None)
        cached_ap = (
            cached_state.get('archipelago', {})
            if isinstance(cached_state, dict) else {}
        )
        previous_ap = deepcopy(
            cached_ap
            if isinstance(cached_ap, dict)
            and cached_ap.get('manifest_checksum')
            == slot_manifest.get('manifest_checksum')
            else self._configured_archipelago_state() or {}
        )
        if (
            previous_ap.get('manifest_checksum')
            != slot_manifest.get('manifest_checksum')
        ):
            previous_ap = {}
        previous_ap.update({
            'activation': 'active',
            'enabled': True,
            'slot_data': deepcopy(result.slot_data),
            'run_manifest': deepcopy(slot_manifest),
            'manifest_checksum': slot_manifest['manifest_checksum'],
            'server': result.endpoint,
            'slot_name': active_session.config.slot_name,
            'team': int(result.team),
            'slot': int(result.slot),
            'checkpoint': active_session.checkpoint(),
            'players': deepcopy(result.slot_info),
        })
        if isinstance(self._archipelago_standalone_state, dict) and isinstance(
            self._archipelago_standalone_config, dict
        ) and self._archipelago_standalone_config:
            previous_ap['standalone_state'] = deepcopy(
                self._archipelago_standalone_state
            )
            previous_ap['standalone_config'] = deepcopy(
                self._archipelago_standalone_config
            )
        previous_ap.setdefault('location_info', {})
        self.state = deepcopy(snapshot)
        self.state['archipelago'] = previous_ap
        self._archipelago_slot_data = deepcopy(result.slot_data)
        self._archipelago_item_names = dict(item_names)
        self._archipelago_players = {
            int(slot): deepcopy(info)
            for slot, info in result.slot_info.items()
        }
        self._archipelago_location_info = {
            int(location): deepcopy(info)
            for location, info in previous_ap.get('location_info', {}).items()
            if isinstance(info, dict)
        }
        self._archipelago_server_checked_locations = set()
        self._apply_archipelago_server_locations(
            result.checked_locations,
            replace=True,
        )
        self.state['earned_rewards'] = self.earned_rewards_from_checks()
        return previous_ap

    def _apply_archipelago_server_locations(self, location_ids, replace=False):
        """Project server-checked locations into mission/Grid completion state."""
        slot_data = getattr(self, '_archipelago_slot_data', {})
        mappings = slot_data.get('locations', {})
        allowed = {
            int(value)
            for mission in mappings.values()
            if isinstance(mission, dict)
            for values in mission.values()
            if isinstance(values, list)
            for value in values
        }
        incoming = {
            int(value)
            for value in (location_ids or ())
            if int(value) in allowed
        }
        previous = set(getattr(
            self, '_archipelago_server_checked_locations', set()
        ))
        checked = incoming if replace else previous | incoming
        self._archipelago_server_checked_locations = checked
        mission_checks = self.state.get('mission_checks', {})
        changed = checked != previous
        completed = []
        started = []
        for code in self.state.get('mission_order', []):
            checks = mission_checks.get(code, [])
            mapped_checks = mappings.get(code, {})
            mission_started = False
            mission_complete = False
            for check in checks:
                if not isinstance(check, dict):
                    continue
                check_id = str(check.get('id', ''))
                mapped = {
                    int(value)
                    for value in mapped_checks.get(check_id, [])
                }
                unlocked = bool(mapped and mapped.issubset(checked))
                before = bool(check.get('unlocked'))
                check.pop('released', None)
                if unlocked:
                    check['unlocked'] = True
                    mission_started = True
                    if check_id == 'victory':
                        mission_complete = True
                else:
                    check.pop('unlocked', None)
                changed = changed or before != unlocked
            if mission_started and not mission_complete:
                started.append(code)
            if mission_complete:
                completed.append(code)
        if self.state.get('completed_missions') != completed:
            self.state['completed_missions'] = completed
            changed = True
        if self.state.get('started_missions') != started:
            self.state['started_missions'] = started
            changed = True
        self.state['earned_rewards'] = self.earned_rewards_from_checks()
        if self.state.get('progression_mode') == 'Grid Mode':
            from randomizer.progression.grid import refresh_states
            refresh_states(
                self.state.get('grid', {}),
                completed,
                unlock_all_after_goal=False,
            )
        return changed

    def _refresh_archipelago_server_views(self):
        """Invalidate every view fed by AP seed, progress, or received items."""
        self.__dict__.pop('_unlock_dashboard_sources_cache', None)
        self.__dict__.pop('_canonical_earned_rewards_cache', None)
        self.unlock_dashboard_signature = None
        self.grid_render_signature = None
        self.update_header_summary()
        self.redraw_mission_tree()
        self.refresh_progress_view()

    @staticmethod
    def _archipelago_receipt_value(receipt, key, default=None):
        if isinstance(receipt, dict):
            return receipt.get(key, default)
        return getattr(receipt, key, default)

    @staticmethod
    def _archipelago_metadata_fields(value):
        fields = {}
        for key in (
            'item_name', 'from_player', 'from_game', 'recipient_player',
            'recipient_game', 'location_name',
        ):
            text = str(value.get(key) or '').strip()
            if text:
                fields[key] = text
        return fields

    def _merge_archipelago_received_metadata(self, values):
        ap_state = self._active_archipelago_state()
        if ap_state is None or not isinstance(values, (list, tuple)):
            return False
        incoming = {}
        for value in values:
            if not isinstance(value, dict):
                continue
            try:
                incoming[int(value['index'])] = self._archipelago_metadata_fields(
                    value
                )
            except (KeyError, TypeError, ValueError):
                continue
        changed = False
        for record in ap_state.get('received_rewards', []):
            if not isinstance(record, dict):
                continue
            metadata = incoming.get(int(record.get('index', -1)))
            if not metadata:
                continue
            for key, value in metadata.items():
                if record.get(key) != value:
                    record[key] = value
                    changed = True
        return changed

    def _store_archipelago_location_info(self, values):
        ap_state = self._active_archipelago_state()
        if ap_state is None or not isinstance(values, (list, tuple)):
            return False
        saved = ap_state.setdefault('location_info', {})
        changed = False
        for value in values:
            if not isinstance(value, dict):
                continue
            try:
                record = {
                    key: int(value[key])
                    for key in ('item', 'location', 'player', 'flags')
                }
            except (KeyError, TypeError, ValueError):
                continue
            record.update(self._archipelago_metadata_fields(value))
            location = record['location']
            if location <= 0:
                continue
            if self._archipelago_location_info.get(location) != record:
                self._archipelago_location_info[location] = record
                saved[str(location)] = deepcopy(record)
                changed = True
        return changed

    def archipelago_check_item_details(self, code, check_id):
        """Return server-scouted placements for one AP check."""
        ap_state = self._active_archipelago_state()
        if ap_state is None:
            return None
        if not self._archipelago_location_info:
            for location, value in ap_state.get('location_info', {}).items():
                if not isinstance(value, dict):
                    continue
                try:
                    self._archipelago_location_info[int(location)] = deepcopy(
                        value
                    )
                except (TypeError, ValueError):
                    continue
        return tuple(
            deepcopy(self._archipelago_location_info.get(location))
            for location in self._archipelago_location_ids(code, check_id)
            if isinstance(self._archipelago_location_info.get(location), dict)
        )

    def archipelago_reward_assignment_source_items(self):
        """Return known future MO rewards placed at this slot's locations."""
        ap_state = self._active_archipelago_state()
        if ap_state is None:
            return None
        current_slot = int(ap_state.get('slot') or 0)
        if current_slot <= 0:
            return ()
        mission_lookup = self.mission_lookup()
        playable = {
            code
            for code in self.unlocked_mission_codes()
            if not self.is_mission_complete(code)
        }
        checked = set(getattr(
            self, '_archipelago_server_checked_locations', set()
        ))
        items = []
        seen_locations = set()
        for code in self.state.get('mission_order', []):
            title = mission_lookup.get(code, {}).get('title', code)
            for check in self.mission_checks(code):
                check_id = str(check.get('id', ''))
                check_name = str(check.get('name') or 'Check')
                for location in self._archipelago_location_ids(code, check_id):
                    if location in seen_locations:
                        continue
                    record = self._archipelago_location_info.get(location)
                    if (
                        not isinstance(record, dict)
                        or int(record.get('player') or 0) != current_slot
                    ):
                        continue
                    reward_name = self._archipelago_reward_name(
                        int(record.get('item') or 0)
                    )
                    if reward_name not in REWARD_BY_NAME:
                        continue
                    seen_locations.add(location)
                    items.append((
                        f'{title} â€” {check_name}',
                        canonical_reward({'name': reward_name}),
                        bool(code in playable and location not in checked),
                    ))
        return tuple(items)

    def _archipelago_reward_name(self, item_id):
        item_names = getattr(self, '_archipelago_item_names', {})
        if not item_names:
            slot_data = getattr(self, '_archipelago_slot_data', {})
            if not slot_data:
                ap_state = self._active_archipelago_state() or {}
                saved = ap_state.get('slot_data')
                slot_data = saved if isinstance(saved, dict) else {}
            try:
                item_names = self._validate_archipelago_item_mapping(slot_data)
            except ValueError:
                return ''
            self._archipelago_item_names = item_names
        return str(item_names.get(int(item_id), ''))

    def _archipelago_reward_records(self):
        ap_state = self._active_archipelago_state()
        if ap_state is None:
            return None
        values = ap_state.get('received_rewards', [])
        if not isinstance(values, list):
            return ()
        records = []
        seen = set()
        for value in values:
            if not isinstance(value, dict):
                continue
            try:
                index = int(value['index'])
            except (KeyError, TypeError, ValueError):
                continue
            reward_name = str(value.get('reward_name', ''))
            if index < 0 or index in seen or reward_name not in REWARD_BY_NAME:
                continue
            seen.add(index)
            records.append(value)
        return tuple(sorted(records, key=lambda value: int(value['index'])))

    def archipelago_reward_history(self):
        """Return AP-mode earned rewards, or None for standalone mode."""
        records = self._archipelago_reward_records()
        if records is None:
            return None
        return tuple(
            canonical_reward({'name': record['reward_name']})
            for record in records
        )

    def archipelago_reward_source_items(self):
        """Return source labels and canonical rewards for Unlocks UI."""
        records = self._archipelago_reward_records()
        if records is None:
            return None
        return tuple(
            (
                self._archipelago_received_source_label(record),
                canonical_reward({'name': record['reward_name']}),
            )
            for record in records
        )

    @staticmethod
    def _archipelago_received_source_label(record):
        player = str(record.get('from_player') or '').strip()
        if not player:
            player = f'Player {int(record.get("player", 0))}'
        game = str(record.get('from_game') or '').strip() or 'game unavailable'
        location = str(record.get('location_name') or '').strip()
        if not location:
            raw_location = int(record.get('location', 0))
            location = (
                'Precollected / starting inventory'
                if raw_location == 0
                else f'location #{raw_location}'
            )
        return f'Found by {player} ({game}) at {location}'

    def apply_archipelago_received_items(self, receipts):
        """Persist and acknowledge one network item batch with two saves."""
        receipts = tuple(receipts or ())
        if not receipts:
            return ()
        ap_state = self._active_archipelago_state()
        session = getattr(self, '_archipelago_session', None)
        if (
            ap_state is None
            or session is None
            or not getattr(self, '_archipelago_session_validated', False)
        ):
            return ()
        raw_history = ap_state.get('received_rewards', [])
        existing_records = list(self._archipelago_reward_records() or ())
        if not isinstance(raw_history, list) or len(existing_records) != len(
            raw_history
        ):
            self.append_archipelago_history(
                'Received reward history is invalid; item left pending.'
            )
            log_event(
                'archipelago_reward_history_invalid',
                level=logging.ERROR,
                received_count=len(receipts),
            )
            return ()

        records_by_index = {
            int(record['index']): record for record in existing_records
        }
        incoming_by_index = {}
        new_records = []
        metadata_updated = False
        for receipt in receipts:
            item_id = int(self._archipelago_receipt_value(receipt, 'item', 0))
            index = int(self._archipelago_receipt_value(receipt, 'index', -1))
            reward_name = self._archipelago_reward_name(item_id)
            if not reward_name or reward_name not in REWARD_BY_NAME:
                self.append_archipelago_history(
                    f'Item #{index} cannot be applied: unknown '
                    f'Mental Omega item ID {item_id}.'
                )
                log_event(
                    'archipelago_reward_apply_failed',
                    level=logging.ERROR,
                    index=index,
                    item_id=item_id,
                    error='unknown item ID',
                )
                return ()
            record = {
                'index': index,
                'item_id': item_id,
                'reward_name': reward_name,
                'location': int(self._archipelago_receipt_value(
                    receipt, 'location', 0
                )),
                'player': int(self._archipelago_receipt_value(
                    receipt, 'player', 0
                )),
                'flags': int(self._archipelago_receipt_value(
                    receipt, 'flags', 0
                )),
            }
            if isinstance(receipt, dict):
                record.update(self._archipelago_metadata_fields(receipt))
            record['received_at'] = datetime.now().astimezone().isoformat(
                timespec='seconds'
            )
            previous_incoming = incoming_by_index.get(index)
            existing = records_by_index.get(index)
            identity_keys = (
                'index', 'item_id', 'reward_name', 'location', 'player', 'flags'
            )
            identity = tuple(record[key] for key in identity_keys)
            if (
                previous_incoming is not None
                and tuple(previous_incoming[key] for key in identity_keys)
                != identity
            ) or (
                existing is not None
                and tuple(existing.get(key) for key in identity_keys) != identity
            ):
                self.append_archipelago_history(
                    f'Item #{index} conflicts with saved reward history.'
                )
                log_event(
                    'archipelago_reward_identity_conflict',
                    level=logging.ERROR,
                    index=index,
                )
                return ()
            incoming_by_index[index] = record
            if existing is None and previous_incoming is None:
                new_records.append(record)
            elif existing is not None:
                for key, value in self._archipelago_metadata_fields(record).items():
                    if not existing.get(key):
                        existing[key] = value
                        metadata_updated = True

        acknowledge_indexes = sorted(incoming_by_index)
        if not new_records:
            try:
                changed = session.acknowledge_received(acknowledge_indexes)
                if changed or metadata_updated:
                    ap_state['checkpoint'] = session.checkpoint()
                    self.save_state()
                if changed:
                    self.append_archipelago_history(
                        'Recovered acknowledgment for '
                        f'{len(acknowledge_indexes)} Archipelago item(s).'
                    )
            except Exception as exc:
                self.append_archipelago_history(
                    f'Item acknowledgment failed: {exc}'
                )
            return ()

        previous_history = ap_state.get('received_rewards', [])
        previous_checkpoint = ap_state.get('checkpoint')
        previous_earned = self.state.get('earned_rewards', [])
        ap_state['received_rewards'] = sorted(
            [*existing_records, *new_records],
            key=lambda value: int(value['index']),
        )
        ap_state['checkpoint'] = session.checkpoint()
        self.state['earned_rewards'] = self.earned_rewards_from_checks()
        try:
            self.save_state()
        except Exception as exc:
            ap_state['received_rewards'] = previous_history
            ap_state['checkpoint'] = previous_checkpoint
            self.state['earned_rewards'] = previous_earned
            self.append_archipelago_history(
                f'Archipelago item batch save failed: {exc}'
            )
            log_event(
                'archipelago_reward_apply_failed',
                level=logging.ERROR,
                received_count=len(receipts),
                new_count=len(new_records),
                error=str(exc),
            )
            return ()

        try:
            session.acknowledge_received(acknowledge_indexes)
            ap_state['checkpoint'] = session.checkpoint()
            self.save_state()
        except Exception as exc:
            self.append_archipelago_history(
                f'{len(new_records)} item(s) applied; acknowledgment save '
                f'will recover later: {exc}'
            )
            log_event(
                'archipelago_reward_acknowledge_deferred',
                level=logging.WARNING,
                first_index=min(acknowledge_indexes),
                last_index=max(acknowledge_indexes),
                count=len(acknowledge_indexes),
                error=str(exc),
            )

        if any(
            canonical_reward({'name': record['reward_name']}).get(
                'enemy_reward'
            )
            for record in new_records
        ):
            self._enemy_buffs_view_dirty = True
        if len(new_records) == 1:
            record = new_records[0]
            reward = canonical_reward({'name': record['reward_name']})
            message = (
                f'Applied {reward_display_name(reward)}. '
                f'{self._archipelago_received_source_label(record)}.'
            )
        else:
            message = (
                f'Applied {len(new_records)} Archipelago items '
                f'(#{new_records[0]["index"]}-#{new_records[-1]["index"]}).'
            )
        self.append_archipelago_history(message)
        log_event(
            'archipelago_reward_batch_applied',
            count=len(new_records),
            first_index=new_records[0]['index'],
            last_index=new_records[-1]['index'],
        )
        return tuple(record['index'] for record in new_records)

    def apply_archipelago_received_item(self, receipt):
        """Compatibility wrapper for focused single-item callers."""
        return bool(self.apply_archipelago_received_items((receipt,)))

    def _archipelago_location_ids(self, code, check_id):
        ap_state = self._active_archipelago_state()
        if ap_state is None:
            return ()
        slot_data = getattr(self, '_archipelago_slot_data', {})
        if not slot_data:
            saved = ap_state.get('slot_data')
            slot_data = saved if isinstance(saved, dict) else {}
        missions = slot_data.get('locations', {})
        mission = missions.get(str(code).upper(), {}) if isinstance(missions, dict) else {}
        values = mission.get(str(check_id), []) if isinstance(mission, dict) else []
        if not isinstance(values, list):
            return ()
        try:
            location_ids = tuple(sorted({int(value) for value in values}))
        except (TypeError, ValueError):
            return ()
        return tuple(value for value in location_ids if value > 0)

    def archipelago_check_location_count(self, code, check_id):
        if self._active_archipelago_state() is None:
            return None
        return len(self._archipelago_location_ids(code, check_id))

    def archipelago_mission_location_counts(self, code):
        if self._active_archipelago_state() is None:
            return None
        checks = self.state.get('mission_checks', {}).get(code, [])
        done = 0
        total = 0
        for check in checks:
            if not isinstance(check, dict):
                continue
            count = len(
                self._archipelago_location_ids(code, check.get('id', ''))
            )
            total += count
            if check.get('unlocked'):
                done += count
        return done, total

    def _report_archipelago_check_locations(
        self,
        code,
        check_id,
        label,
        event_stem,
    ):
        location_ids = self._archipelago_location_ids(code, check_id)
        if not location_ids:
            return ()
        ap_state = self._active_archipelago_state()
        if ap_state is None:
            return ()
        try:
            session = getattr(self, '_archipelago_session', None)
            if (
                session is not None
                and getattr(self, '_archipelago_session_validated', False)
            ):
                added = session.report_locations(location_ids)
                checkpoint = session.checkpoint()
            else:
                checkpoint = dict(ap_state.get('checkpoint') or {})
                checkpoint['format'] = 2
                checkpoint.setdefault('pending_locations', [])
                completed = {
                    int(value)
                    for value in checkpoint.get('completed_locations', [])
                }
                added = tuple(
                    value for value in location_ids if value not in completed
                )
                completed.update(added)
                checkpoint['completed_locations'] = sorted(completed)
                pending = {
                    int(value)
                    for value in checkpoint.get('pending_locations', [])
                }
                pending.update(added)
                checkpoint['pending_locations'] = sorted(pending)
            if not added:
                return ()
            ap_state['checkpoint'] = checkpoint
            self.save_state()
            self.append_archipelago_history(
                f'Sent {label} {str(code).upper()} {check_id}: '
                + ', '.join(str(value) for value in added)
            )
            log_event(
                f'archipelago_{event_stem}_reported',
                code=str(code).upper(),
                check_id=str(check_id),
                locations=list(added),
            )
            return tuple(added)
        except Exception as exc:
            self.append_archipelago_history(
                f'{label.title()} synchronization failed for '
                f'{code} {check_id}: {exc}'
            )
            log_event(
                f'archipelago_{event_stem}_report_failed',
                level=logging.ERROR,
                code=str(code).upper(),
                check_id=str(check_id),
                error=str(exc),
            )
            return ()

    def report_archipelago_objective_check(self, code, check_id):
        """Persist and queue one successful non-victory Randomizer check."""
        if str(check_id) == 'victory':
            return ()
        return self._report_archipelago_check_locations(
            code,
            check_id,
            'objective check',
            'objective',
        )

    def report_archipelago_goal_if_complete(self):
        """Persist and send CLIENT_GOAL when existing run logic is complete."""
        ap_state = self._active_archipelago_state()
        if ap_state is None:
            return False
        try:
            if not self.is_run_complete():
                return False
            session = getattr(self, '_archipelago_session', None)
            if (
                session is not None
                and getattr(self, '_archipelago_session_validated', False)
            ):
                changed = session.mark_goal_complete()
                checkpoint = session.checkpoint()
            else:
                checkpoint = dict(ap_state.get('checkpoint') or {})
                checkpoint['format'] = 2
                changed = not bool(checkpoint.get('goal_complete', False))
                checkpoint['goal_complete'] = True
            checkpoint_changed = ap_state.get('checkpoint') != checkpoint
            ap_state['checkpoint'] = checkpoint
            if changed or checkpoint_changed:
                self.save_state()
            if changed:
                self.append_archipelago_history(
                    'Sent Archipelago goal completion.'
                )
                log_event(
                    'archipelago_goal_reported',
                    seed=self.state.get('seed', ''),
                    progression_mode=self.active_progression_mode(),
                )
            return bool(changed)
        except Exception as exc:
            self.append_archipelago_history(
                f'Goal synchronization failed: {exc}'
            )
            log_event(
                'archipelago_goal_report_failed',
                level=logging.ERROR,
                error=str(exc),
            )
            return False

    def report_archipelago_mission_completion(self, code):
        """Report missed objectives, mission reward slots, then run goal."""
        if self._active_archipelago_state() is None:
            return ()
        added = []
        mission_checks = self.state.get('mission_checks', {})
        checks = (
            mission_checks.get(code, [])
            if isinstance(mission_checks, dict)
            else []
        )
        for check in checks:
            if not isinstance(check, dict) or not check.get('unlocked'):
                continue
            check_id = str(check.get('id', ''))
            if check_id and check_id != 'victory':
                added.extend(
                    self.report_archipelago_objective_check(code, check_id)
                )
        added.extend(
            self._report_archipelago_check_locations(
                code,
                'victory',
                'mission completion',
                'mission_completion',
            )
        )
        self.report_archipelago_goal_if_complete()
        return tuple(added)

    def reconcile_archipelago_checks(self):
        """Resend every unlocked check and completed goal after recovery."""
        if self._active_archipelago_state() is None:
            return ()
        added = []
        mission_checks = self.state.get('mission_checks', {})
        if not isinstance(mission_checks, dict):
            return ()
        for code, checks in mission_checks.items():
            if not isinstance(checks, list):
                continue
            for check in checks:
                if not isinstance(check, dict) or not check.get('unlocked'):
                    continue
                check_id = str(check.get('id', ''))
                if not check_id:
                    continue
                if check_id == 'victory':
                    added.extend(
                        self._report_archipelago_check_locations(
                            code,
                            check_id,
                            'mission completion',
                            'mission_completion',
                        )
                    )
                else:
                    added.extend(
                        self.report_archipelago_objective_check(code, check_id)
                    )
        self.report_archipelago_goal_if_complete()
        if added:
            self.append_archipelago_history(
                f'Reconciled {len(added)} Archipelago location(s).'
            )
        return tuple(added)

    def reconcile_archipelago_objective_checks(self):
        """Compatibility alias for Phase 5 callers."""
        return self.reconcile_archipelago_checks()

    def append_archipelago_history(self, message):
        """Record internal synchronization detail without polluting AP chat."""
        log_event('archipelago_internal', detail=str(message).rstrip())

    def configure_archipelago_message_tags(self):
        widget = getattr(self, 'archipelago_history_text', None)
        if widget is None:
            return
        dark = bool(self.dark_mode_var.get())
        normal = self.ui_palette()['foreground']
        colors = {
            'ap_text': normal,
            'ap_game': '#70c7ff' if dark else '#176a9c',
            'ap_location': '#6ee7a8' if dark else '#087a48',
            'ap_item_progression': '#c3afff' if dark else '#6548b8',
            'ap_item_useful': '#9fb6ff' if dark else '#315fa8',
            'ap_item_filler': '#68dce8' if dark else '#087a86',
            'ap_item_trap': '#ff8a80' if dark else '#b3261e',
        }
        for tag, foreground in colors.items():
            widget.tag_configure(tag, foreground=foreground)

    def _archipelago_player_tag(self, slot):
        dark_colors = (
            '#ee66ee', '#ffd166', '#66ccff', '#ff8a80',
            '#7fe39c', '#c9a7ff', '#ffad66', '#78e6d0',
        )
        light_colors = (
            '#9c168f', '#8a5a00', '#176a9c', '#b3261e',
            '#087a48', '#6548b8', '#a64b00', '#08766c',
        )
        try:
            slot = int(slot)
        except (TypeError, ValueError):
            slot = 0
        colors = dark_colors if self.dark_mode_var.get() else light_colors
        tag = f'ap_player_{slot % len(colors)}'
        self.archipelago_history_text.tag_configure(
            tag, foreground=colors[slot % len(colors)]
        )
        return tag

    def _archipelago_message_tag(self, segment):
        role = str(segment.get('role') or 'text')
        if role == 'player':
            return self._archipelago_player_tag(segment.get('slot', 0))
        if role == 'game':
            return 'ap_game'
        if role == 'location':
            return 'ap_location'
        if role == 'item':
            flags = int(segment.get('flags') or 0)
            return (
                'ap_item_progression' if flags & 1
                else 'ap_item_useful' if flags & 2
                else 'ap_item_trap' if flags & 4
                else 'ap_item_filler'
            )
        server_color = str(segment.get('color') or '').casefold()
        server_colors = {
            'red': '#ff7b72' if self.dark_mode_var.get() else '#b3261e',
            'green': '#6ee7a8' if self.dark_mode_var.get() else '#087a48',
            'blue': '#70c7ff' if self.dark_mode_var.get() else '#176a9c',
            'cyan': '#68dce8' if self.dark_mode_var.get() else '#087a86',
            'magenta': '#ee66ee' if self.dark_mode_var.get() else '#9c168f',
            'yellow': '#ffd166' if self.dark_mode_var.get() else '#8a5a00',
            'plum': '#c3afff' if self.dark_mode_var.get() else '#6548b8',
            'salmon': '#ff8a80' if self.dark_mode_var.get() else '#b3261e',
            'slateblue': '#9fb6ff' if self.dark_mode_var.get() else '#315fa8',
        }
        if server_color in server_colors:
            tag = f'ap_server_{server_color}'
            self.archipelago_history_text.tag_configure(
                tag, foreground=server_colors[server_color]
            )
            return tag
        return 'ap_text'

    def append_archipelago_server_message(self, message):
        """Render one clean AP chat/activity line with semantic colors."""
        widget = getattr(self, 'archipelago_history_text', None)
        if widget is None:
            return
        segments = (
            message
            if isinstance(message, (list, tuple))
            else ({'text': str(message), 'role': 'text'},)
        )
        cleaned = []
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            text = ''.join(
                ' ' if character in '\r\n\t' else character
                for character in str(segment.get('text', ''))
                if ord(character) >= 32 or character in '\r\n\t'
            )
            if text:
                cleaned.append((text, self._archipelago_message_tag(segment)))
        if not cleaned:
            return
        widget.configure(state='normal')
        for text, tag in cleaned:
            widget.insert('end', text, tag)
        widget.insert('end', '\n', 'ap_text')
        widget.see('end')
        widget.configure(state='disabled')
