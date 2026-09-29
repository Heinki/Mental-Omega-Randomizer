"""Co-op settings, shared Grid lobby, suggestions, and direct game launch."""

import copy
import ipaddress
import os
import queue
import secrets
import threading
import traceback
import tkinter as tk
from tkinter import messagebox, ttk

from randomizer.config.player import save_config
from randomizer.coop.direct import host_session, join_session
from randomizer.coop.lobby import LOBBY_PORT, Lobby, decode_state, encode_state
from randomizer.coop.prototype import available_units, build_manifest, shop_unit_loadout
from randomizer.coop.shop_stage import (
    apply_stage_snapshot, recovery_result_message, stage_digest, stage_snapshot,
)
from randomizer.coop.victory import victory_marker_name
from randomizer.core.paths import DEBUG_LOG, GAME_ROOT
from randomizer.rewards.arsenal import ARSENAL_MODE
from randomizer.shop.model import RunStatus


class CoopController:
    def refresh_coop_controls(self):
        if not hasattr(self, 'coop_connection_button'):
            return
        available = self.coop_feature_enabled_var.get()
        for widget in (self.coop_mode_check, self.coop_connection_button,
                       self.compact_coop_button, self.shop_coop_row):
            if available:
                widget.grid()
            else:
                widget.grid_remove()
        enabled = available and self.coop_mode_var.get()
        guest = self.coop_guest_connected()
        self.campaign_combo.configure(values=(
            ('All Campaigns', 'Allies', 'Soviets', 'Epsilon') if enabled else
            ('All Campaigns', 'Allies', 'Soviets', 'Epsilon', 'Foehn')
        ))
        if enabled and self.campaign_var.get() == 'Foehn':
            self.campaign_var.set('All Campaigns')
        self.rewards_per_check_label.configure(
            text='Rewards per mission' if enabled else 'Rewards per objective'
        )
        for button in (self.coop_connection_button, self.compact_coop_button,
                       self.shop_coop_connection_button):
            button.configure(state='normal' if enabled else 'disabled')
        for button in (self.launch_selected_button, self.compact_launch_button):
            button.configure(text='Suggest Mission' if guest else 'Launch Selected Mission')
        for button in (self.debug_complete_button, self.compact_complete_button):
            button.configure(text='Record Co-op Victory' if enabled else 'Mark Mission Complete')
        self.sync_debug_completion_controls()

    def active_mission_exclusions(self):
        return (self.excluded_coop_mission_codes if self.coop_mode_var.get()
                else self.excluded_mission_codes)

    def coop_guest_connected(self):
        lobby = getattr(self, '_coop_lobby', None)
        return bool(lobby and lobby.connected and lobby.role == 'guest')

    def on_coop_feature_enabled_changed(self):
        enabled = bool(self.coop_feature_enabled_var.get())
        if not enabled and self.coop_mode_var.get():
            self.coop_mode_var.set(False)
            self.on_coop_mode_changed()
            if self.coop_mode_var.get():
                self.coop_feature_enabled_var.set(True)
                self.refresh_coop_controls()
                return
        self.config['coop_feature_enabled'] = enabled
        save_config(self.config)
        self.refresh_coop_controls()
        self.refresh_shop_settings_controls()
        self.update_header_summary()

    def on_coop_mode_changed(self):
        if self.coop_mode_var.get() and not self.coop_feature_enabled_var.get():
            self.coop_mode_var.set(False)
            return
        process = getattr(self, 'active_game_process', None)
        if (self.gameplay_settings_locked() or getattr(self, '_coop_lobby', None)
                or (process is not None and process.poll() is None)):
            self.coop_mode_var.set(bool(self.config.get('coop_mode', False)))
            return
        enabled = bool(self.coop_mode_var.get())
        if self.shop_mode_selected():
            run = self.shop_repository.load_run()
            if run is not None and run.status is RunStatus.ACTIVE:
                co_op_run = bool(run.eligible_mission_codes) and all(
                    str(code).startswith('COOP_') for code in run.eligible_mission_codes
                )
                if co_op_run != enabled:
                    self.coop_mode_var.set(bool(self.config.get('coop_mode', False)))
                    messagebox.showwarning(
                        'Co-op Shop',
                        'Finish the active Shop run before switching its mission pool.',
                        parent=self,
                    )
                    return
        self.config['coop_mode'] = enabled
        self.config['progression_mode'] = self.progression_mode_var.get()
        self.refresh_coop_controls()
        self.config['campaign_filter'] = self.campaign_var.get()
        save_config(self.config)
        self.state = self.load_state()
        self.migrate_state()
        if self.state and not self.shop_mode_selected():
            self.progression_mode_var.set(self.state.get('progression_mode', 'Grid Mode'))
            self.reward_mode_var.set(self.state.get('reward_mode', self.reward_mode_var.get()))
            self.campaign_var.set(self.state.get('campaign_filter', self.campaign_var.get()))
            self.mission_goal_var.set(self.state.get('mission_goal', self.mission_goal_var.get()))
            self.rewards_per_check_var.set(self.state.get(
                'rewards_per_check', self.rewards_per_check_var.get()
            ))
        self.apply_missions(self.load_missions())
        if self.shop_mode_selected():
            self.sync_shop_workspace()
            self.refresh_shop_mode()
        self.grid_render_signature = None
        self.redraw_progression_views()
        self.update_header_summary()
        self.refresh_progress_view()
        self.refresh_setting_states()
        self.append_log('Co-op map pool selected.' if enabled else 'Campaign map pool selected.')

    def open_coop_dialog(self):
        if not self.coop_feature_enabled_var.get():
            messagebox.showinfo('Co-op', 'Enable experimental co-op in Advanced first.')
            return
        if not self.coop_mode_var.get():
            messagebox.showinfo('Co-op', 'Check Co-op mode in Settings first.')
            return
        old = getattr(self, '_coop_dialog', None)
        if old is not None and old.winfo_exists():
            old.lift()
            return
        dialog = tk.Toplevel(self)
        dialog.title('Co-op connection')
        dialog.transient(self)
        dialog.resizable(False, False)
        frame = ttk.Frame(dialog, padding=16)
        frame.grid(sticky='nsew')
        frame.columnconfigure(1, weight=1)
        role = tk.StringVar(value='host')
        name = tk.StringVar(value='CoopHost')
        address = tk.StringVar(value=self.config.get('coop_last_host', '127.0.0.1'))
        port = tk.StringVar(value=str(LOBBY_PORT))
        network_mode = tk.StringVar(value=self.config.get('coop_network_mode', 'local'))
        pairing_code = tk.StringVar()
        status = tk.StringVar(value=(
            'Both players start Shop runs with the same seed and stage. Host controls missions.'
            if self.shop_mode_selected() else
            'Host generates co-op seed. Guest joins to see same Grid.'
        ))
        guide = tk.StringVar()
        modes = ttk.Frame(frame)
        modes.grid(row=0, column=0, columnspan=2, sticky='w')

        def choose_role(selected):
            if name.get() in ('CoopHost', 'CoopGuest'):
                name.set('CoopHost' if selected == 'host' else 'CoopGuest')

        ttk.Radiobutton(modes, text='Host', variable=role, value='host',
                        command=lambda: choose_role('host')).pack(side='left')
        ttk.Radiobutton(modes, text='Join', variable=role, value='guest',
                        command=lambda: choose_role('guest')).pack(side='left', padx=(12, 0))
        network = ttk.Frame(frame)
        network.grid(row=1, column=0, columnspan=2, sticky='w', pady=(8, 4))
        for value, label in (('local', 'LAN / same PC'),
                             ('zerotier', 'ZeroTier'), ('direct', 'Public IP')):
            ttk.Radiobutton(network, text=label, variable=network_mode,
                            value=value).pack(side='left', padx=(0, 10))
        for row, label, variable in ((2, 'Player name', name),
                                     (3, 'Host IP', address),
                                     (4, 'Lobby TCP port', port),
                                     (5, 'Pairing code', pairing_code)):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky='w', pady=3)
            ttk.Entry(frame, textvariable=variable, width=28).grid(
                row=row, column=1, sticky='ew', padx=(12, 0), pady=3)
        ttk.Label(frame, textvariable=status, wraplength=410).grid(
            row=6, column=0, columnspan=2, sticky='w', pady=(8, 6))
        ttk.Label(frame, textvariable=guide, justify='left', wraplength=410).grid(
            row=7, column=0, columnspan=2, sticky='w')

        def update_guide(*_):
            mode = network_mode.get()
            if mode == 'direct' and role.get() == 'host' and not pairing_code.get():
                pairing_code.set(secrets.token_urlsafe(18))
            guide.set({
                'local': ('LAN: guest enters host LAN IPv4. Same PC: use 127.0.0.1 '
                          'with separate game folders. Allow TCP lobby/next port and UDP 1234.'),
                'zerotier': ('Join and authorize both devices on same ZeroTier network. '
                             'Guest enters host managed IPv4. Allow TCP lobby/next port '
                             'and UDP 1234 in both firewalls. No router forwarding needed.'),
                'direct': ('Share pairing code privately. Guest enters host public IPv4. '
                           'Forward TCP lobby/next port to host; forward UDP 1234 to each '
                           'player on each router. Allow ports in firewalls. Needs public '
                           'IPv4. Control data is unencrypted.'),
            }.get(mode, 'Select a connection method.'))

        network_mode.trace_add('write', update_guide)
        role.trace_add('write', update_guide)
        update_guide()
        buttons = ttk.Frame(frame)
        buttons.grid(row=8, column=0, columnspan=2, sticky='e', pady=(12, 0))
        ttk.Button(buttons, text='Close', command=dialog.destroy).pack(side='right')
        ttk.Button(buttons, text='Disconnect', command=self.disconnect_coop).pack(
            side='right', padx=(0, 8))
        start = ttk.Button(buttons, text='Connect', command=lambda: self._connect_coop(
            role.get(), name.get(), address.get(), port.get(),
            network_mode.get(), pairing_code.get()))
        start.pack(side='right', padx=(0, 8))
        self._coop_dialog = dialog
        self._coop_status_var = status
        self._coop_start_button = start
        lobby = getattr(self, '_coop_lobby', None)
        if lobby:
            start.configure(state='disabled')
            status.set(f'Connected to {lobby.peer}.' if lobby.connected else 'Waiting for peer…')
        dialog.focus_set()

    def _connect_coop(self, role, name, address, port_text,
                      network_mode='local', pairing_code=''):
        if not self.coop_feature_enabled_var.get():
            return
        if getattr(self, '_coop_lobby', None):
            return
        if self.active_game_process is not None and self.active_game_process.poll() is None:
            messagebox.showwarning('Co-op', 'Close current game first.')
            return
        if self.shop_mode_selected():
            run = self.shop_repository.load_run()
            if run is None:
                messagebox.showwarning('Co-op', 'Start a Shop run first.')
                return
            if run.status is not RunStatus.ACTIVE:
                try:
                    recoverable = role == 'host' and recovery_result_message(run) is not None
                except ValueError as exc:
                    messagebox.showwarning('Co-op', str(exc))
                    return
                if not recoverable:
                    messagebox.showwarning(
                        'Co-op', 'A finished Shop run can reconnect only as host to sync its result.'
                    )
                    return
            if (not run.eligible_mission_codes or any(
                    not str(code).startswith('COOP_')
                    for code in run.eligible_mission_codes)):
                messagebox.showwarning('Co-op', 'Start a Shop run from the co-op map pool.')
                return
        elif role == 'host' and not self.state.get('coop_mode'):
            messagebox.showwarning('Co-op', 'Generate or load a co-op seed first.')
            return
        try:
            pairing_code = pairing_code.strip()
            port = int(port_text)
            if not 1024 <= port <= 65534:
                raise ValueError('Lobby port must be 1024–65534.')
            if role == 'guest' and not address.strip():
                raise ValueError('Enter host IP address.')
            if network_mode not in ('local', 'zerotier', 'direct'):
                raise ValueError('Select a co-op connection method.')
            if network_mode == 'direct':
                if len(pairing_code) < 16 or len(pairing_code) > 128:
                    raise ValueError('Public IP pairing code must be 16–128 characters.')
                if role == 'guest':
                    host_ip = ipaddress.ip_address(address.strip())
                    if host_ip.version != 4 or not host_ip.is_global:
                        raise ValueError('Enter host public IPv4 address.')
            lobby = Lobby(GAME_ROOT, role, name.strip(), address=address.strip(),
                          port=port, pairing_code=pairing_code)
        except (ValueError, OSError) as exc:
            messagebox.showerror('Co-op', str(exc))
            return
        self.config['coop_network_mode'] = network_mode
        if role == 'guest':
            self.config['coop_last_host'] = address.strip()
        save_config(self.config)
        self._coop_lobby = lobby
        self._coop_shop_ready = False
        self._coop_shop_stage_digest = ''
        self._coop_start_button.configure(state='disabled')
        self._coop_status_var.set('Waiting for guest…' if role == 'host' else 'Connecting…')
        lobby.start()
        self.after(100, self._poll_coop_lobby)

    def disconnect_coop(self):
        lobby = getattr(self, '_coop_lobby', None)
        if not lobby:
            return
        was_guest = lobby.role == 'guest'
        lobby.close()
        self._coop_lobby = None
        self._coop_shop_ready = False
        self._coop_shop_stage_digest = ''
        if was_guest:
            self.state = self.load_state()
            self.migrate_state()
            self.grid_render_signature = None
            self.redraw_progression_views()
            self.refresh_progress_view()
        if getattr(self, '_coop_dialog', None) and self._coop_dialog.winfo_exists():
            self._coop_start_button.configure(state='normal')
            self._coop_status_var.set('Disconnected.')
        self.append_log('Co-op lobby disconnected.')
        self.refresh_coop_controls()

    def _poll_coop_lobby(self):
        lobby = getattr(self, '_coop_lobby', None)
        if not lobby:
            return
        try:
            while True:
                event = lobby.events.get_nowait()
                if event[0] == 'listening':
                    self.append_log(f'Co-op lobby listening on TCP {event[1]}.')
                elif event[0] == 'connected':
                    self.append_log(f'Co-op lobby connected to {event[1]}.')
                    self.refresh_coop_controls()
                    if getattr(self, '_coop_dialog', None) and self._coop_dialog.winfo_exists():
                        self._coop_status_var.set(f'Connected to {event[1]}. Host selects and launches.')
                    if lobby.role == 'host':
                        self.coop_publish_state()
                elif event[0] == 'message':
                    self._handle_coop_message(lobby, event[1])
                elif event[0] == 'error':
                    self.append_log('Co-op lobby: ' + event[1], error=True)
                elif event[0] == 'disconnected':
                    self.disconnect_coop()
                    return
        except queue.Empty:
            pass
        except Exception as exc:
            self.append_log('Co-op lobby message failed: ' + str(exc), error=True)
            self.disconnect_coop()
            return
        self.after(100, self._poll_coop_lobby)

    def coop_publish_state(self):
        lobby = getattr(self, '_coop_lobby', None)
        if not (lobby and lobby.connected and lobby.role == 'host'):
            return
        if self.shop_mode_selected() and self.coop_mode_var.get():
            try:
                run = self.shop_repository.load_run()
                result = recovery_result_message(run)
                if result:
                    lobby.send(result)
                if run is not None and run.status is RunStatus.ACTIVE:
                    self.coop_publish_shop_stage()
            except (OSError, ValueError) as exc:
                self.append_log('Co-op Shop recovery sync failed: ' + str(exc), error=True)
            return
        if not self.state.get('coop_mode'):
            return
        try:
            lobby.send({'type': 'state', 'data': encode_state(self.state)})
            self.coop_broadcast_selection()
        except (OSError, ValueError) as exc:
            self.append_log('Co-op state sync failed: ' + str(exc), error=True)

    def coop_publish_shop_stage(self):
        lobby = getattr(self, '_coop_lobby', None)
        if not (lobby and lobby.connected and lobby.role == 'host'
                and self.coop_mode_var.get() and self.shop_mode_selected()):
            return
        try:
            snapshot = stage_snapshot(self.shop_repository.load_run())
            self._coop_shop_stage_digest = stage_digest(snapshot)
            self._coop_shop_ready = False
            lobby.send({'type': 'shop_stage', 'data': snapshot})
        except (OSError, ValueError) as exc:
            self.append_log('Co-op Shop stage sync failed: ' + str(exc), error=True)

    def coop_broadcast_selection(self):
        lobby = getattr(self, '_coop_lobby', None)
        mission = self.selected_mission()
        if lobby and lobby.connected and lobby.role == 'host' and mission:
            try:
                lobby.send({'type': 'select', 'code': mission['code']})
            except OSError as exc:
                self.append_log('Co-op selection sync failed: ' + str(exc), error=True)

    def coop_selection_changed(self):
        if getattr(self, '_coop_applying_selection', False):
            return
        lobby = getattr(self, '_coop_lobby', None)
        mission = self.selected_mission()
        if not (lobby and lobby.connected and mission and self.state.get('coop_mode')):
            return
        if lobby.role == 'host':
            self.coop_broadcast_selection()
        else:
            try:
                lobby.send({'type': 'suggest', 'code': mission['code']})
                self.append_log(f'Suggested {mission["title"]} to host.')
            except OSError as exc:
                self.append_log('Co-op suggestion failed: ' + str(exc), error=True)

    def _handle_coop_message(self, lobby, message):
        kind = message['type']
        if lobby.role == 'guest':
            if kind == 'shop_stage':
                if not (self.coop_mode_var.get() and self.shop_mode_selected()):
                    raise ValueError('Host Shop stage reached a non-Shop guest.')
                run = self.shop_repository.load_run()
                snapshot = message.get('data')
                updated = apply_stage_snapshot(run, snapshot, self.mission_lookup())
                if updated != run:
                    self.shop_repository.save_run(updated)
                self.shop_run = updated
                self.refresh_shop_mode()
                lobby.send({'type': 'shop_ready', 'digest': stage_digest(snapshot)})
                self.append_log(f'Host Shop stage {updated.stage} synced.')
            elif kind == 'shop_victory':
                if not (self.coop_mode_var.get() and self.shop_mode_selected()):
                    raise ValueError('Host Shop victory reached a non-Shop guest.')
                run = self.shop_repository.load_run()
                code = message.get('code')
                stage = message.get('stage')
                if type(stage) is not int:
                    raise ValueError('Host Shop victory has invalid stage.')
                if (run is not None and run.seed == message.get('seed')
                        and code in run.completed_missions
                        and (run.stage > stage or run.status is RunStatus.COMPLETED)):
                    return
                if (run is None or run.status is not RunStatus.ACTIVE
                        or run.seed != message.get('seed') or run.stage != stage
                        or not run.mission_committed
                        or run.selected_mission_code != code):
                    raise ValueError('Host Shop victory differs from guest committed stage.')
                self._shop_launch_run = run
                self._shop_launch_mission_pool = tuple(self._shop_run_mission_pool(run))
                if not self.unlock_mission_check(code, 'victory', 'Co-op host victory'):
                    raise ValueError('Guest Shop victory could not be recorded.')
                self.append_log(f'Co-op Shop victory synced for {code}.')
                process = getattr(self, 'active_game_process', None)
                if process is None or process.poll() is not None:
                    self.finish_progression_launch_context()
            elif kind == 'shop_failure':
                if not (self.coop_mode_var.get() and self.shop_mode_selected()):
                    raise ValueError('Host Shop failure reached a non-Shop guest.')
                run = self.shop_repository.load_run()
                code = message.get('code')
                stage = message.get('stage')
                token = message.get('session_token')
                recovery = message.get('recovery') is True
                if (type(stage) is not int or not isinstance(code, str)
                        or not code.startswith('COOP_')
                        or type(message.get('revived')) is not bool
                        or message.get('recovery') not in (None, True)
                        or (not recovery and (
                            not isinstance(token, str) or len(token) < 24
                            or token != getattr(self, '_coop_active_game_token', None)
                        ))):
                    raise ValueError('Host Shop failure has invalid game identity.')
                if (run is None or run.seed != message.get('seed')
                        or run.stage != stage):
                    raise ValueError('Host Shop failure differs from guest run.')
                if (run.status is RunStatus.FAILED
                        and run.failed_stage == stage
                        and run.failed_mission_code == code):
                    return
                if (run.status is RunStatus.ACTIVE and not run.mission_committed
                        and run.emergency_revivals_used > 0):
                    return
                if (run.status is not RunStatus.ACTIVE or not run.mission_committed
                        or run.selected_mission_code != code):
                    raise ValueError('Host Shop failure differs from guest committed stage.')
                self.shop_profile, run = self.shop_repository.load()
                self._shop_launch_run = run
                self._shop_launch_mission_pool = tuple(self._shop_run_mission_pool(run))
                self._coop_host_revival = message['revived']
                try:
                    recorded = self.record_failed_mission_attempt(
                        code, 'Co-op host failure'
                    )
                finally:
                    self._coop_host_revival = None
                if not recorded:
                    raise ValueError('Guest Shop failure could not be recorded.')
                self.append_log(f'Co-op Shop failure synced for {code}.')
                process = getattr(self, 'active_game_process', None)
                if process is None or process.poll() is not None:
                    self.finish_progression_launch_context()
            elif kind == 'state':
                state = decode_state(message.get('data', ''))
                codes = state.get('mission_order', [])
                available = {mission['code'] for mission in self.missions}
                if not isinstance(codes, list) or not codes or not all(
                        code in available for code in codes):
                    raise ValueError('Host co-op maps differ from installed catalogue.')
                self.state = state
                self.grid_render_signature = None
                self._coop_applying_selection = True
                try:
                    self.redraw_mission_tree()
                    self.redraw_progression_views()
                    self.refresh_progress_view()
                finally:
                    self._coop_applying_selection = False
                self.update_header_summary()
                self.append_log(f'Host Grid synced: {len(codes)} maps, seed {state["seed"]}.')
            elif kind == 'select':
                code = message.get('code')
                index = next((i for i, mission in enumerate(self.missions)
                              if mission['code'] == code), None)
                if index is not None:
                    self._coop_applying_selection = True
                    try:
                        if self.active_progression_mode() == 'Grid Mode':
                            self.select_grid_mission(index)
                        else:
                            self.selected_index.set(index)
                            self.refresh_progress_view(refresh_unlocks=False)
                    finally:
                        self._coop_applying_selection = False
            elif kind == 'launch':
                code = message.get('code')
                if self.shop_mode_selected() and self.coop_mode_var.get():
                    run = self.shop_repository.load_run()
                    if (run is None or run.status is not RunStatus.ACTIVE
                            or not run.mission_committed
                            or run.selected_mission_code != code):
                        raise ValueError('Host Shop launch differs from guest committed mission.')
                    self._shop_launch_run = run
                    self._shop_launch_victory_key = None
                    self._shop_launch_mission_pool = tuple(self._shop_run_mission_pool(run))
                elif code not in self.state.get('mission_order', []):
                    raise ValueError('Host selected map outside shared run.')
                session_token = message.get('session_token')
                if not isinstance(session_token, str) or len(session_token) < 24:
                    raise ValueError('Host sent invalid co-op game token.')
                self._start_coop_game('guest', code, session_token=session_token)
        elif kind == 'shop_ready':
            if (self.shop_mode_selected() and self.coop_mode_var.get()
                    and getattr(self, '_coop_shop_stage_digest', '')
                    and message.get('digest') == self._coop_shop_stage_digest):
                self._coop_shop_ready = True
                self.append_log('Guest Shop stage ready.')
                self.refresh_shop_mode()
            else:
                raise ValueError('Guest acknowledged a different Shop stage.')
        elif kind == 'suggest':
            code = message.get('code')
            mission = self.mission_lookup().get(code)
            if mission and code in self.state.get('mission_order', []):
                self.append_log(f'{lobby.peer} suggests {mission["title"]} ({code}).')
                if getattr(self, '_coop_dialog', None) and self._coop_dialog.winfo_exists():
                    self._coop_status_var.set(f'{lobby.peer} suggests {mission["title"]}. Select it in Grid to play.')

    def request_coop_launch(self):
        if not self.coop_feature_enabled_var.get():
            messagebox.showwarning('Co-op', 'Enable experimental co-op in Advanced first.')
            return
        lobby = getattr(self, '_coop_lobby', None)
        mission = self.selected_mission()
        if not self.state.get('coop_mode') or mission is None:
            messagebox.showwarning('Co-op', 'Generate a co-op seed and select a map first.')
            return
        if mission['code'] not in set(self.unlocked_mission_codes()) | set(
                self.state.get('completed_missions', [])):
            messagebox.showwarning('Co-op', 'Selected co-op map is locked.')
            return
        if not lobby or not lobby.connected:
            messagebox.showwarning('Co-op', 'Connect both launchers first.')
            return
        if lobby.role == 'guest':
            self.coop_selection_changed()
        else:
            self._start_coop_game('host', mission['code'])

    def _start_coop_game(self, role, code, *, session_token=''):
        if not self.coop_feature_enabled_var.get():
            return
        lobby = getattr(self, '_coop_lobby', None)
        if getattr(self, '_coop_busy', False) or not lobby or not lobby.connected:
            return
        if self.active_game_process is not None and self.active_game_process.poll() is None:
            messagebox.showwarning('Co-op', 'Close current game first.')
            return
        self._coop_busy = True
        if role == 'host':
            session_token = secrets.token_urlsafe(24)
        self._coop_queue = queue.Queue()
        self._coop_active_game_code = code
        self._coop_active_game_role = role
        self._coop_active_game_token = session_token
        mission = self.mission_lookup().get(code)
        state_snapshot = copy.deepcopy(self.state)
        shop_run = (self.shop_repository.load_run()
                    if self.shop_mode_selected() and self.coop_mode_var.get()
                    else None)
        difficulty = {'Casual': 'easy', 'Normal': 'normal',
                      'Mental': 'hard'}.get(self.difficulty_var.get(), 'normal')
        if shop_run is not None:
            level = self.shop_mission_difficulty_value(shop_run, code)
            if shop_run.assisted_mission_code == code:
                level = max(0, level - 1)
            difficulty = ('easy', 'normal', 'hard')[min(2, max(0, level))]
        self.append_log(f'Preparing co-op map {code} as {role}.')
        if getattr(self, '_coop_dialog', None) and self._coop_dialog.winfo_exists():
            self._coop_status_var.set('Preparing map and connecting game…')

        def worker():
            try:
                if role == 'host':
                    if not mission:
                        raise ValueError('Selected co-op map is missing.')
                    if shop_run is not None:
                        if (shop_run.status is not RunStatus.ACTIVE
                                or not shop_run.mission_committed
                                or shop_run.selected_mission_code != code):
                            raise ValueError('Host Shop mission is not committed.')
                        manifest = None
                        shop_setup = {
                            'seed': shop_run.seed, 'stage': shop_run.stage,
                            'coop_name': mission['coop_name'],
                            'loadout': shop_unit_loadout(shop_run),
                        }
                    else:
                        source_mission = code if state_snapshot.get('reward_mode') == ARSENAL_MODE else ''
                        available = available_units(state_snapshot, source_mission)
                        manifest, _ = build_manifest(
                            GAME_ROOT, state_snapshot, mission['coop_name'],
                            source_mission=source_mission,
                            unit_id='' if available else 'FV', allow_test_unit=True,
                        )
                        shop_setup = None
                    lobby.send({'type': 'launch', 'code': code,
                                'session_token': session_token})
                    result = host_session(
                        GAME_ROOT, manifest, name=lobby.name,
                        control_port=lobby.port + 1,
                        difficulty=difficulty,
                        session_token=session_token,
                        shop_setup=shop_setup,
                    )
                else:
                    same_machine = lobby.address.lower() in ('127.0.0.1', 'localhost')
                    shop_setup = ({
                        'seed': shop_run.seed, 'stage': shop_run.stage,
                        'loadout': shop_unit_loadout(shop_run),
                    } if shop_run is not None else None)
                    result = join_session(
                        GAME_ROOT, lobby.address, name=lobby.name,
                        control_port=lobby.port + 1,
                        game_port=1235 if same_machine else 1234,
                        session_token=session_token,
                        shop_setup=shop_setup,
                    )
                self._coop_queue.put(('ready', result))
            except Exception as exc:
                self._coop_queue.put(('error', str(exc), traceback.format_exc()))

        threading.Thread(target=worker, name='CoopGame', daemon=True).start()
        self.after(100, self._poll_coop_session)

    def _poll_coop_session(self):
        try:
            event = self._coop_queue.get_nowait()
        except queue.Empty:
            if getattr(self, '_coop_busy', False):
                self.after(100, self._poll_coop_session)
            return
        if event[0] == 'error':
            self._coop_busy = False
            if self.shop_mode_selected():
                self.finish_progression_launch_context()
            self.append_log('Co-op game failed: ' + event[1], error=True)
            self.append_log(event[2], error=True)
            if getattr(self, '_coop_dialog', None) and self._coop_dialog.winfo_exists():
                self._coop_status_var.set('Game connection failed: ' + event[1])
            messagebox.showerror('Co-op', event[1])
            return
        result = event[1]
        self.append_log(f'Co-op paired with {result["peer"]}; game ID {result["game_id"]}; '
                        f'map {result["map_sha256"]}.')
        try:
            process, _ = self.spawn_game_process(self.build_command())
        except Exception as exc:
            self._coop_busy = False
            if self.shop_mode_selected():
                self.finish_progression_launch_context()
            self.append_log('Co-op game launch failed: ' + str(exc), error=True)
            messagebox.showerror('Co-op', str(exc))
            return
        self.active_game_process = process
        if result['role'] == 'host':
            try:
                with DEBUG_LOG.open('rb') as handle:
                    log_stat = os.fstat(handle.fileno())
                    handle.seek(max(0, log_stat.st_size - 64))
                    log_anchor = handle.read(64)
            except OSError:
                log_stat = None
                log_anchor = b''
            self._coop_victory_watch = {
                'code': self._coop_active_game_code,
                'marker': victory_marker_name(self._coop_active_game_code.lower()),
                'offset': log_stat.st_size if log_stat else 0,
                'file_id': (log_stat.st_dev, log_stat.st_ino) if log_stat else None,
                'anchor': log_anchor,
                'detected': False,
            }
        else:
            self._coop_victory_watch = None
        self.append_log(f'Co-op game started as {result["role"]}.')
        if getattr(self, '_coop_dialog', None) and self._coop_dialog.winfo_exists():
            self._coop_status_var.set('Game running. Lobby stays connected.')
        self.after(1000, self._poll_coop_game)

    def _poll_coop_game(self):
        self._scan_coop_victory()
        process = self.active_game_process
        if process is not None and process.poll() is None:
            self.after(1000, self._poll_coop_game)
            return
        self.active_game_process = None
        self._coop_busy = False
        self.append_log('Co-op game process exited.')
        watch = getattr(self, '_coop_victory_watch', None)
        if watch and not watch['detected'] and not self.is_mission_complete(watch['code']):
            if (self.shop_mode_selected() and self.coop_mode_var.get()
                    and getattr(self, '_coop_active_game_role', '') == 'host'
                    and DEBUG_LOG.exists() and not watch.get('log_error')):
                if self.record_failed_mission_attempt(
                        watch['code'], 'Co-op game closed without victory'):
                    self.append_log('Co-op Shop attempt recorded as failed for both players.')
            else:
                self.append_log('No co-op victory marker detected. Host can record a won mission manually.')
        self._coop_victory_watch = None
        if self.shop_mode_selected() and self.coop_mode_var.get():
            self.finish_progression_launch_context()
        if getattr(self, '_coop_dialog', None) and self._coop_dialog.winfo_exists():
            self._coop_status_var.set('Game ended. Host may select another map.')
        if getattr(self, '_close_after_game', False):
            self.disconnect_coop()
            self.shutdown_archipelago()
            self.destroy()

    def _scan_coop_victory(self):
        watch = getattr(self, '_coop_victory_watch', None)
        if not watch or watch['detected'] or not DEBUG_LOG.exists():
            return
        try:
            with DEBUG_LOG.open('rb') as handle:
                log_stat = os.fstat(handle.fileno())
                file_id = (log_stat.st_dev, log_stat.st_ino)
                offset = watch['offset']
                if log_stat.st_size < offset or watch.get('file_id') != file_id:
                    offset = 0
                elif offset and watch.get('anchor') is not None:
                    anchor_start = max(0, offset - 64)
                    handle.seek(anchor_start)
                    if handle.read(offset - anchor_start) != watch['anchor']:
                        offset = 0
                handle.seek(offset)
                data = handle.read()
                watch['offset'] = handle.tell()
                anchor_start = max(0, watch['offset'] - 64)
                handle.seek(anchor_start)
                watch['anchor'] = handle.read(watch['offset'] - anchor_start)
                watch['file_id'] = file_id
        except OSError as exc:
            watch['log_error'] = True
            self.append_log('Co-op victory log read failed: ' + str(exc), error=True)
            return
        if not any(watch['marker'] in line for line in data.decode(
                'utf-8', errors='ignore').splitlines()):
            return
        watch['detected'] = True
        code = watch['code']
        if self.is_mission_complete(code):
            return
        self.append_log(f'Co-op victory marker detected for {code}.')
        self.unlock_mission_check(code, 'victory', 'Co-op in-game victory')
