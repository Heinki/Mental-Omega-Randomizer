"""Launcher adapter for the isolated Archipelago session worker."""

from copy import deepcopy
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
            self.archipelago_generate_yaml_button,
            self.archipelago_load_yaml_button,
        ]
        stateful = []
        for widget in candidates:
            if widget in excluded or widget in stateful:
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

    def reset_archipelago_after_new_seed(self):
        """Return UI/config identity to standalone after state replacement."""
        self.config.setdefault('archipelago', {})['enabled'] = False
        self._archipelago_yaml_text = ''
        self._archipelago_session_validated = False
        self._archipelago_slot_data = {}
        self._archipelago_item_names = {}
        self._archipelago_displayed_receipts = set()
        self._set_archipelago_chat_enabled(False)
        self.archipelago_status_var.set('Disconnected')
        self.archipelago_yaml_status_var.set(
            'Generate or load a player YAML for the active run.'
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
            self.append_archipelago_history(
                'Chat unavailable until Archipelago connection is validated.'
            )
            self._set_archipelago_chat_enabled(False)
            return 'break'
        self.archipelago_chat_var.set('')
        self.append_archipelago_history(
            f'Queued as {session.config.slot_name}: {text}'
        )
        return 'break'

    def _archipelago_saved_checkpoint(self, endpoint, slot_name):
        ap_state = self.state.get('archipelago', {}) if self.state else {}
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
            self._validated_active_archipelago_manifest()
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
            self.archipelago_status_var.set('Disconnected')
            self.append_archipelago_history(f'Connection setup failed: {exc}')
            log_event(
                'archipelago_connection_setup_failed',
                level=logging.ERROR,
                error=str(exc),
            )
            return

        ap_config = self.config.setdefault('archipelago', {})
        ap_config['server'] = self.archipelago_server_var.get().strip()
        ap_config['port'] = int(self.archipelago_port_var.get())
        ap_config['slot_name'] = slot_name
        ap_config['client_uuid'] = self.archipelago_client_uuid
        save_config(self.config)

        self._archipelago_session = session
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

    def handle_archipelago_event(self, event):
        if event.kind == 'status':
            state = str(event.payload.get('state', 'disconnected'))
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
                local_manifest = self._validated_active_archipelago_manifest()
                slot_manifest = result.slot_data.get('run_manifest')
                from Archipelago.run_manifest import (
                    validate_run_manifest_for_state,
                )
                validate_run_manifest_for_state(self.state, slot_manifest)
                if (
                    slot_manifest.get('manifest_checksum')
                    != local_manifest.get('manifest_checksum')
                ):
                    raise ValueError(
                        'server run manifest does not match the active YAML'
                    )
            except ValueError as exc:
                self.append_archipelago_history(
                    f'Connected slot item catalogue is incompatible: {exc}'
                )
                self.disconnect_archipelago()
                return
            self._archipelago_slot_data = dict(result.slot_data)
            self._archipelago_item_names = item_names
            self.append_archipelago_history(
                f'Authenticated: seed {result.seed_name}, '
                f'team {result.team + 1}, slot {result.slot}.'
            )
            ap_state = self._configured_archipelago_state()
            if ap_state is not None:
                state_seed = str(self.state.get('seed', ''))
                slot_seed = str(result.slot_data.get('randomizer_seed', ''))
                if state_seed and slot_seed != state_seed:
                    self.append_archipelago_history(
                        'Connected slot does not match the active Randomizer '
                        f'seed ({slot_seed!r} != {state_seed!r}). Disconnecting.'
                    )
                    self.disconnect_archipelago()
                    return
                ap_state['slot_data'] = dict(result.slot_data)
                ap_state['run_manifest'] = deepcopy(slot_manifest)
                ap_state['manifest_checksum'] = slot_manifest[
                    'manifest_checksum'
                ]
                self._apply_manifest_launcher_settings(slot_manifest)
                ap_state['server'] = result.endpoint
                active_session = getattr(self, '_archipelago_session', None)
                if active_session is None:
                    self.append_archipelago_history(
                        'Connected session disappeared before validation completed.'
                    )
                    return
                ap_state['slot_name'] = active_session.config.slot_name
                ap_state['checkpoint'] = active_session.checkpoint()
                self._archipelago_session_validated = True
                self._synchronize_archipelago_progression_ui(slot_manifest)
                self._promote_archipelago_run()
                self._set_archipelago_chat_enabled(True)
                self.archipelago_status_var.set(
                    'Connected — AP rewards active'
                )
                self.reconcile_archipelago_checks()
            return
        if event.kind == 'checkpoint':
            self._persist_archipelago_checkpoint(event.payload)
            return
        if event.kind == 'received_items':
            applied_indexes = self.apply_archipelago_received_items(
                event.payload
            )
            if applied_indexes:
                self.refresh_progress_view()
            return
        if event.kind == 'locations_checked':
            locations = ', '.join(str(value) for value in event.payload)
            self.append_archipelago_history(
                f'Server synchronized checked locations: {locations}.'
            )
            return
        if event.kind == 'desynchronized':
            self.append_archipelago_history(
                'Item index mismatch detected; requested full synchronization.'
            )
            return
        if event.kind == 'message' and event.payload:
            self.append_archipelago_history(str(event.payload))
            return
        if event.kind == 'error':
            message = str(event.payload.get('message', 'Unknown network error.'))
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
                'Archipelago item '
                f'#{int(record["index"])} from slot '
                f'{int(record.get("player", 0))}',
                canonical_reward({'name': record['reward_name']}),
            )
            for record in records
        )

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
        for receipt in receipts:
            reward_name = self._archipelago_reward_name(receipt.item)
            if not reward_name or reward_name not in REWARD_BY_NAME:
                self.append_archipelago_history(
                    f'Item #{receipt.index} cannot be applied: unknown '
                    f'Mental Omega item ID {receipt.item}.'
                )
                log_event(
                    'archipelago_reward_apply_failed',
                    level=logging.ERROR,
                    index=int(receipt.index),
                    item_id=int(receipt.item),
                    error='unknown item ID',
                )
                return ()
            record = {
                'index': int(receipt.index),
                'item_id': int(receipt.item),
                'reward_name': reward_name,
                'location': int(receipt.location),
                'player': int(receipt.player),
                'flags': int(receipt.flags),
            }
            index = record['index']
            previous_incoming = incoming_by_index.get(index)
            existing = records_by_index.get(index)
            if (
                previous_incoming is not None
                and previous_incoming != record
            ) or (existing is not None and existing != record):
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

        acknowledge_indexes = sorted(incoming_by_index)
        if not new_records:
            try:
                changed = session.acknowledge_received(acknowledge_indexes)
                if changed:
                    ap_state['checkpoint'] = session.checkpoint()
                    self.save_state()
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
                f'Applied item #{record["index"]}: '
                f'{reward_display_name(reward)} from slot {record["player"]}.'
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
                checkpoint.setdefault('format', 1)
                completed = {
                    int(value)
                    for value in checkpoint.get('completed_locations', [])
                }
                added = tuple(
                    value for value in location_ids if value not in completed
                )
                completed.update(added)
                checkpoint['completed_locations'] = sorted(completed)
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
                checkpoint.setdefault('format', 1)
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
        widget = getattr(self, 'archipelago_history_text', None)
        if widget is None:
            return
        widget.configure(state='normal')
        widget.insert('end', str(message).rstrip() + '\n')
        widget.see('end')
        widget.configure(state='disabled')
