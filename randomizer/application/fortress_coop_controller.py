"""Two/three-player Fortress lobby, reusing the authenticated ZeroTier channel."""

import queue
import json
import time
import zlib
from tkinter import messagebox

from randomizer.coop import feature
from randomizer.coop.privacy import redact_connection_details
from randomizer.core.paths import GAME_ROOT
from randomizer.final_fortress.coop_ui import connection_dialog, refresh_connection_dialog
from randomizer.final_fortress.lobby import FortressHost, FortressLobby

from .fortress_coop_launch import FortressCoopLaunchController


class FortressCoopController(FortressCoopLaunchController):
    def on_fortress_coop_mode_changed(self):
        process = getattr(self, 'active_game_process', None)
        if (self._fortress_lobbies or self._final_fortress_preparing
                or (process is not None and process.poll() is None)):
            self.final_fortress_coop_var.set(bool(self._fortress_lobbies))
        elif not feature.COOP_FEATURE_ENABLED:
            self.final_fortress_coop_var.set(False)
        self.refresh_final_fortress()

    def refresh_fortress_settings_controls(self):
        """Present Fortress's own lobby choices without changing campaign settings."""
        if not hasattr(self, 'final_fortress_coop_var'):
            return
        fortress = self.final_fortress_mode_selected()
        sessions = getattr(self, '_fortress_lobbies', {})
        process = getattr(self, 'active_game_process', None)
        locked = (bool(sessions) or self._final_fortress_preparing
                  or (process is not None and process.poll() is None))
        enabled = bool(self.final_fortress_coop_var.get())
        for prefix in ('', 'shop_'):
            fields = getattr(self, prefix + 'fortress_player_count_fields', ())
            for field in fields:
                field.grid() if fortress else field.grid_remove()
            toggle = getattr(self, prefix + 'coop_mode_check', None)
            if toggle is not None:
                if getattr(toggle, '_fortress_settings_mode', None) != fortress:
                    toggle.configure(
                        variable=self.final_fortress_coop_var if fortress else self.coop_mode_var,
                        command=self.on_fortress_coop_mode_changed if fortress else self.on_coop_checkbox_changed)
                    toggle._fortress_settings_mode = fortress
                if fortress:
                    toggle.configure(state='disabled' if locked or not feature.COOP_FEATURE_ENABLED else 'normal')
            tooltip = getattr(self, prefix + 'coop_mode_tooltip', None)
            if tooltip is not None:
                tooltip.text = ('Off: solo Fortress. On: two or three humans over ZeroTier.' if fortress
                                else 'Off: solo campaign missions. On: two-player co-op missions.')
            include = getattr(self, prefix + 'include_challenge_missions_check', None)
            if include is not None:
                include.configure(variable=self._fortress_challenge_maps_var if fortress
                                  else self.include_challenge_missions_var)
            if not fortress:
                continue
            if include is not None:
                include.configure(text='Include challenge maps (unavailable in Final Fortress)', state='disabled')
                include.grid()
            for field in getattr(self, prefix + 'challenge_fields', ()):
                field.grid_remove()
            for suffix in ('challenge_local_frame', 'challenge_availability_label'):
                widget = getattr(self, prefix + suffix, None)
                if widget is not None:
                    widget.grid_remove()
            combo = getattr(self, prefix + 'fortress_player_count_combo', None)
            if combo is not None:
                combo.configure(state='readonly' if enabled and not locked and feature.COOP_FEATURE_ENABLED
                                else 'disabled')
            button = getattr(self, prefix + 'coop_connection_button', None)
            if button is not None:
                button.configure(state='normal' if feature.COOP_FEATURE_ENABLED else 'disabled')
                button.grid() if enabled or sessions else button.grid_remove()
        frame = getattr(self, 'coop_controls_frame', None)
        if frame is not None:
            frame.configure(text='Final Fortress co-op' if fortress else 'Co-op & Challenges')

    def open_coop_dialog(self):
        if self.final_fortress_mode_selected():
            return self.open_fortress_coop_dialog()
        return super().open_coop_dialog()

    def open_fortress_coop_dialog(self):
        if feature.COOP_FEATURE_ENABLED:
            connection_dialog(self)

    def fortress_coop_guest(self):
        return bool(getattr(self, '_fortress_lobbies', None)
                    and self._fortress_role == 'guest')

    def game_speed_controls_locked(self):
        return (getattr(self, '_final_fortress_preparing', False)
                or self.fortress_coop_guest() or super().game_speed_controls_locked())

    def close_launcher(self):
        process = getattr(self, 'active_game_process', None)
        if (not getattr(self, '_final_fortress_preparing', False)
                and not (process is not None and process.poll() is None)):
            self.disconnect_fortress_coop()
        return super().close_launcher()

    def _fortress_safe_message(self, value):
        private = [getattr(self, name).get() for name in (
            '_fortress_coop_address_var', '_fortress_coop_host_code', '_fortress_coop_guest_code')
                   if hasattr(self, name)]
        for lobby in getattr(self, '_fortress_lobbies', {}).values():
            private.extend((lobby.address, lobby.pairing_code))
        return redact_connection_details(value, *private)

    def connect_fortress_coop(self):
        if not feature.COOP_FEATURE_ENABLED or getattr(self, '_fortress_lobbies', None):
            return
        process = getattr(self, 'active_game_process', None)
        if (getattr(self, '_coop_lobby', None) or getattr(self, '_coop_busy', False)
                or self._final_fortress_preparing or self._final_fortress_watch is not None
                or (process is not None and process.poll() is None)):
            messagebox.showwarning('Fortress co-op', 'Close the current game or other co-op lobby first.', parent=self)
            return
        role = 'host' if self._fortress_coop_role_var.get() == 'Host' else 'guest'
        sessions = {}
        try:
            name = self._fortress_coop_name_var.get().strip()
            count = int(self._fortress_coop_count_var.get()) if role == 'host' else None
            if role == 'host' and count not in (2, 3):
                raise ValueError('Choose two or three human players.')
            slots = range(1, count) if role == 'host' else (0,)
            code = (self._fortress_coop_host_code if role == 'host'
                    else self._fortress_coop_guest_code).get().strip()
            for slot in slots:
                sessions[slot] = FortressLobby(
                    GAME_ROOT, role, name, address=self._fortress_coop_address_var.get().strip(),
                    pairing_code=code)
        except (ValueError, OSError) as exc:
            messagebox.showerror('Fortress co-op', self._fortress_safe_message(exc), parent=self)
            return
        self._fortress_lobbies = sessions
        self.final_fortress_coop_var.set(True)
        self._fortress_role = role
        self._fortress_humans = count if role == 'host' else None
        self._fortress_local_slot = 0 if role == 'host' else None
        self._fortress_pending = None
        self._fortress_worker_active = False
        self._fortress_roster = []
        self._fortress_peer_runs = {}
        generation = self._fortress_lobby_generation = object()
        self.fortress_coop_status_var.set('Waiting for all Fortress players…')
        self._fortress_host = FortressHost(sessions) if role == 'host' else None
        if self._fortress_host is not None:
            self._fortress_host.start()
        else:
            sessions[0].start()
        self.refresh_final_fortress()
        self.refresh_game_speed_controls()
        self.after(100, lambda: self._poll_fortress_lobby(generation))

    def disconnect_fortress_coop(self):
        process = getattr(self, 'active_game_process', None)
        if (getattr(self, '_final_fortress_preparing', False)
                or (process is not None and process.poll() is None)):
            return
        host = getattr(self, '_fortress_host', None)
        if host is not None:
            host.close()
            self._fortress_host = None
        for lobby in getattr(self, '_fortress_lobbies', {}).values():
            lobby.close()
        self._fortress_lobbies = {}
        if hasattr(self, 'final_fortress_coop_var'):
            self.final_fortress_coop_var.set(False)
        self._fortress_pending = None
        if hasattr(self, 'fortress_coop_status_var'):
            self.fortress_coop_status_var.set('Disconnected')
        if hasattr(self, 'final_fortress_launch_button'):
            self.refresh_final_fortress()
            self.refresh_game_speed_controls()

    def fortress_coop_ready(self):
        sessions = getattr(self, '_fortress_lobbies', {})
        if not sessions or self._fortress_role != 'host' or not all(l.connected for l in sessions.values()):
            return False
        names = [next(iter(sessions.values())).name, *[sessions[i].peer for i in sorted(sessions)]]
        installations = [json.dumps(lobby.peer_installation, sort_keys=True) for lobby in sessions.values()]
        return (len(names) == len({name.casefold() for name in names})
                and len(installations) == len(set(installations))
                and not getattr(self, '_fortress_peer_runs', {}))

    def refresh_fortress_coop_controls(self):
        self.refresh_fortress_settings_controls()
        sessions = getattr(self, '_fortress_lobbies', {})
        process = getattr(self, 'active_game_process', None)
        busy = self._final_fortress_preparing or (process is not None and process.poll() is None)
        dialog = getattr(self, '_fortress_coop_dialog', None)
        if dialog is not None and dialog.winfo_exists():
            refresh_connection_dialog(self, connected=bool(sessions), busy=busy)
        if not hasattr(self, 'final_fortress_launch_button'):
            return
        guest = self.fortress_coop_guest()
        self.final_fortress_launch_button.configure(
            text='Waiting for host' if guest else 'Launch co-op Fortress' if sessions
            else 'Connect Fortress co-op…' if self.final_fortress_coop_var.get() else 'Launch Final Fortress')
        if self.final_fortress_coop_var.get() and not sessions and not busy and feature.COOP_FEATURE_ENABLED:
            self.final_fortress_launch_button.configure(state='normal')
            self.final_fortress_status_var.set('Choose 2 or 3 human players in Settings, then connect the Fortress lobby.')
        if sessions and (guest or not self.fortress_coop_ready()):
            self.final_fortress_launch_button.configure(state='disabled')
        if guest and not busy:
            self.final_fortress_status_var.set(
                'Waiting for the host. Host perks are shared; your Defensive Points and purchases remain personal.')
        for widget in getattr(self, 'final_fortress_setup_combos', ()):
            widget.configure(state='disabled' if busy or guest else 'readonly')
        if sessions:
            self.final_fortress_setup_combos[0].configure(state='disabled')
        widget = getattr(self, 'final_fortress_mental_ai_boost_check', None)
        if widget is not None:
            widget.configure(state='disabled' if busy or guest else 'normal')
        if hasattr(self, 'final_fortress_profile_combo') and sessions:
            self.final_fortress_profile_combo.configure(state='disabled')

    def _publish_fortress_roster(self):
        if self._fortress_role != 'host':
            return
        sessions = self._fortress_lobbies
        names = [next(iter(sessions.values())).name,
                 *[sessions[i].peer if sessions[i].connected else '(waiting)' for i in sorted(sessions)]]
        state = self.final_fortress_state
        preferences = state['preferences']
        setup = (f'{self.final_fortress_config["map"]["display_name"]}, '
                 f'{preferences["player_country"] or "Choose faction"}, {preferences["difficulty"]}, '
                 f'x{preferences["wave_multiplier"]}; host perks shared')
        status = ' / '.join(names) + ' — ' + setup
        if len({name.casefold() for name in names if name != '(waiting)'}) != len(
                [name for name in names if name != '(waiting)']):
            status = 'Duplicate player names. Disconnect and choose distinct names.'
        installations = [json.dumps(lobby.peer_installation, sort_keys=True)
                         for lobby in sessions.values() if lobby.connected]
        if len(installations) != len(set(installations)):
            status = 'Each Fortress player needs a separate game installation. Disconnect before reconnecting.'
        self.fortress_coop_status_var.set(status)
        for slot, lobby in sessions.items():
            if lobby.connected:
                lobby.send({'type': 'fortress_roster', 'players': names, 'slot': slot, 'setup': setup,
                            'map_id': self.final_fortress_config['map']['id']})

    def _poll_fortress_lobby(self, generation):
        sessions = getattr(self, '_fortress_lobbies', {})
        if not sessions or generation is not self._fortress_lobby_generation:
            return
        for slot, lobby in list(sessions.items()):
            for _ in range(24):
                try:
                    kind, value = lobby.events.get_nowait()
                except queue.Empty:
                    break
                try:
                    if kind == 'connected':
                        self.append_log(f'Fortress player {slot + 1} connected: {lobby.peer}.'
                                        if self._fortress_role == 'host'
                                        else f'Fortress host connected: {lobby.peer}.')
                        self._publish_fortress_roster()
                        self.refresh_final_fortress()
                    elif kind == 'message':
                        local_slot = self._fortress_local_slot if self._fortress_role == 'guest' else slot
                        self._handle_fortress_message(local_slot, lobby, value)
                    elif kind in ('error', 'disconnected'):
                        detail = self._fortress_safe_message(value)
                        self.fortress_coop_status_var.set('Fortress connection ended. Disconnect before reconnecting. ' + detail)
                        if getattr(self, '_fortress_pending', None):
                            self._abort_fortress_coop('A Fortress player disconnected.')
                        self.refresh_final_fortress()
                    elif kind in ('listening', 'status'):
                        self.append_log('Fortress network: ' + self._fortress_safe_message(value))
                except (ValueError, OSError, RuntimeError, KeyError, TypeError, zlib.error) as exc:
                    self._abort_fortress_coop(str(exc))
        pending = getattr(self, '_fortress_pending', None)
        if pending and time.monotonic() > pending['deadline'] and not pending.get('cancelled'):
            self._abort_fortress_coop('Fortress preparation timed out. Reconnect all players and try again.')
        self.refresh_fortress_coop_controls()
        self.after(150, lambda: self._poll_fortress_lobby(generation))
