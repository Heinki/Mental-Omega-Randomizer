"""Co-op settings, shared Grid lobby, suggestions, and direct game launch."""

import copy
import queue
import threading
import traceback
import tkinter as tk
from tkinter import messagebox, ttk

from randomizer.config.player import save_config
from randomizer.coop.direct import host_session, join_session
from randomizer.coop.lobby import LOBBY_PORT, Lobby, decode_state, encode_state
from randomizer.coop.prototype import available_units, build_manifest
from randomizer.core.paths import GAME_ROOT
from randomizer.rewards.arsenal import ARSENAL_MODE


class CoopController:
    def refresh_coop_controls(self):
        if not hasattr(self, 'coop_connection_button'):
            return
        enabled = self.coop_mode_var.get()
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
        for button in (self.coop_connection_button, self.compact_coop_button):
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

    def on_coop_mode_changed(self):
        process = getattr(self, 'active_game_process', None)
        if (self.gameplay_settings_locked() or getattr(self, '_coop_lobby', None)
                or (process is not None and process.poll() is None)):
            self.coop_mode_var.set(bool(self.config.get('coop_mode', False)))
            return
        enabled = bool(self.coop_mode_var.get())
        if enabled and self.progression_mode_var.get() == 'Shop Mode':
            self.progression_mode_var.set('Grid Mode')
            self.on_progression_mode_changed()
        self.progression_mode_combo.configure(values=(
            ('Classic', 'Mission List', 'Grid Mode') if enabled else
            ('Classic', 'Mission List', 'Grid Mode', 'Shop Mode')
        ))
        self.config['coop_mode'] = enabled
        self.config['progression_mode'] = self.progression_mode_var.get()
        self.refresh_coop_controls()
        self.config['campaign_filter'] = self.campaign_var.get()
        save_config(self.config)
        self.state = self.load_state()
        self.migrate_state()
        if self.state:
            self.progression_mode_var.set(self.state.get('progression_mode', 'Grid Mode'))
            self.reward_mode_var.set(self.state.get('reward_mode', self.reward_mode_var.get()))
            self.campaign_var.set(self.state.get('campaign_filter', self.campaign_var.get()))
            self.mission_goal_var.set(self.state.get('mission_goal', self.mission_goal_var.get()))
            self.rewards_per_check_var.set(self.state.get(
                'rewards_per_check', self.rewards_per_check_var.get()
            ))
        self.apply_missions(self.load_missions())
        self.grid_render_signature = None
        self.redraw_progression_views()
        self.update_header_summary()
        self.refresh_progress_view()
        self.refresh_setting_states()
        self.append_log('Co-op map pool selected.' if enabled else 'Campaign map pool selected.')

    def open_coop_dialog(self):
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
        address = tk.StringVar(value='127.0.0.1')
        port = tk.StringVar(value=str(LOBBY_PORT))
        status = tk.StringVar(value='Host generates co-op seed. Guest joins to see same Grid.')
        modes = ttk.Frame(frame)
        modes.grid(row=0, column=0, columnspan=2, sticky='w')

        def choose_role(selected):
            if name.get() in ('CoopHost', 'CoopGuest'):
                name.set('CoopHost' if selected == 'host' else 'CoopGuest')

        ttk.Radiobutton(modes, text='Host', variable=role, value='host',
                        command=lambda: choose_role('host')).pack(side='left')
        ttk.Radiobutton(modes, text='Join', variable=role, value='guest',
                        command=lambda: choose_role('guest')).pack(side='left', padx=(12, 0))
        for row, label, variable in ((1, 'Player name', name),
                                     (2, 'Host IP / ZeroTier IP', address),
                                     (3, 'Lobby TCP port', port)):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky='w', pady=3)
            ttk.Entry(frame, textvariable=variable, width=28).grid(
                row=row, column=1, sticky='ew', padx=(12, 0), pady=3)
        ttk.Label(frame, textvariable=status, wraplength=410).grid(
            row=4, column=0, columnspan=2, sticky='w', pady=(8, 6))
        ttk.Label(frame, justify='left', wraplength=410,
                  text=('Internet: join same ZeroTier network; authorize both devices. '
                        'Guest enters host ZeroTier IP. Allow TCP lobby port and next '
                        'port, plus UDP 1234, through firewalls. Use separate game folders. '
                        'Direct public IP needs router forwarding to host.')).grid(
                            row=5, column=0, columnspan=2, sticky='w')
        buttons = ttk.Frame(frame)
        buttons.grid(row=6, column=0, columnspan=2, sticky='e', pady=(12, 0))
        ttk.Button(buttons, text='Close', command=dialog.destroy).pack(side='right')
        ttk.Button(buttons, text='Disconnect', command=self.disconnect_coop).pack(
            side='right', padx=(0, 8))
        start = ttk.Button(buttons, text='Connect', command=lambda: self._connect_coop(
            role.get(), name.get(), address.get(), port.get()))
        start.pack(side='right', padx=(0, 8))
        self._coop_dialog = dialog
        self._coop_status_var = status
        self._coop_start_button = start
        lobby = getattr(self, '_coop_lobby', None)
        if lobby:
            start.configure(state='disabled')
            status.set(f'Connected to {lobby.peer}.' if lobby.connected else 'Waiting for peer…')
        dialog.focus_set()

    def _connect_coop(self, role, name, address, port_text):
        if getattr(self, '_coop_lobby', None):
            return
        if self.active_game_process is not None and self.active_game_process.poll() is None:
            messagebox.showwarning('Co-op', 'Close current game first.')
            return
        if role == 'host' and not self.state.get('coop_mode'):
            messagebox.showwarning('Co-op', 'Generate or load a co-op seed first.')
            return
        try:
            port = int(port_text)
            if not 1024 <= port <= 65534:
                raise ValueError('Lobby port must be 1024–65534.')
            if role == 'guest' and not address.strip():
                raise ValueError('Enter host IP address.')
            lobby = Lobby(GAME_ROOT, role, name.strip(), address=address.strip(), port=port)
        except (ValueError, OSError) as exc:
            messagebox.showerror('Co-op', str(exc))
            return
        self._coop_lobby = lobby
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
        if not (lobby and lobby.connected and lobby.role == 'host'
                and self.state.get('coop_mode')):
            return
        try:
            lobby.send({'type': 'state', 'data': encode_state(self.state)})
            self.coop_broadcast_selection()
        except (OSError, ValueError) as exc:
            self.append_log('Co-op state sync failed: ' + str(exc), error=True)

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
            if kind == 'state':
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
                if code not in self.state.get('mission_order', []):
                    raise ValueError('Host selected map outside shared run.')
                self._start_coop_game('guest', code)
        elif kind == 'suggest':
            code = message.get('code')
            mission = self.mission_lookup().get(code)
            if mission and code in self.state.get('mission_order', []):
                self.append_log(f'{lobby.peer} suggests {mission["title"]} ({code}).')
                if getattr(self, '_coop_dialog', None) and self._coop_dialog.winfo_exists():
                    self._coop_status_var.set(f'{lobby.peer} suggests {mission["title"]}. Select it in Grid to play.')

    def request_coop_launch(self):
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

    def _start_coop_game(self, role, code):
        lobby = getattr(self, '_coop_lobby', None)
        if getattr(self, '_coop_busy', False) or not lobby or not lobby.connected:
            return
        if self.active_game_process is not None and self.active_game_process.poll() is None:
            messagebox.showwarning('Co-op', 'Close current game first.')
            return
        self._coop_busy = True
        self._coop_queue = queue.Queue()
        mission = self.mission_lookup().get(code)
        state_snapshot = copy.deepcopy(self.state)
        difficulty = {'Casual': 'easy', 'Normal': 'normal',
                      'Mental': 'hard'}.get(self.difficulty_var.get(), 'normal')
        self.append_log(f'Preparing co-op map {code} as {role}.')
        if getattr(self, '_coop_dialog', None) and self._coop_dialog.winfo_exists():
            self._coop_status_var.set('Preparing map and connecting game…')

        def worker():
            try:
                if role == 'host':
                    if not mission:
                        raise ValueError('Selected co-op map is missing.')
                    source_mission = code if state_snapshot.get('reward_mode') == ARSENAL_MODE else ''
                    available = available_units(state_snapshot, source_mission)
                    manifest, _ = build_manifest(
                        GAME_ROOT, state_snapshot, mission['coop_name'],
                        source_mission=source_mission,
                        unit_id='' if available else 'FV', allow_test_unit=True,
                    )
                    lobby.send({'type': 'launch', 'code': code})
                    result = host_session(
                        GAME_ROOT, manifest, name=lobby.name,
                        control_port=lobby.port + 1,
                        difficulty=difficulty,
                    )
                else:
                    same_machine = lobby.address.lower() in ('127.0.0.1', 'localhost')
                    result = join_session(
                        GAME_ROOT, lobby.address, name=lobby.name,
                        control_port=lobby.port + 1,
                        game_port=1235 if same_machine else 1234,
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
            self.append_log('Co-op game launch failed: ' + str(exc), error=True)
            messagebox.showerror('Co-op', str(exc))
            return
        self.active_game_process = process
        self.append_log(f'Co-op game started as {result["role"]}.')
        if getattr(self, '_coop_dialog', None) and self._coop_dialog.winfo_exists():
            self._coop_status_var.set('Game running. Lobby stays connected.')
        self.after(1000, self._poll_coop_game)

    def _poll_coop_game(self):
        process = self.active_game_process
        if process is not None and process.poll() is None:
            self.after(1000, self._poll_coop_game)
            return
        self.active_game_process = None
        self._coop_busy = False
        self.append_log('Co-op game process exited.')
        if getattr(self, '_coop_dialog', None) and self._coop_dialog.winfo_exists():
            self._coop_status_var.set('Game ended. Host may select another map.')
        if getattr(self, '_close_after_game', False):
            self.disconnect_coop()
            self.shutdown_archipelago()
            self.destroy()
