"""Authoritative Conquest turns over the existing paired ZeroTier transport."""

import json
import queue
import secrets
import time
import uuid
import tkinter as tk
from tkinter import ttk, messagebox

from randomizer.core.paths import APP_DIR, GAME_ROOT
from randomizer.conquest.transport_lobby import unpack
from randomizer.conquest.transport_interfaces import zerotier_ipv4_addresses
from randomizer.conquest.catalogue import FACTIONS
from randomizer.conquest.feature import enabled as conquest_enabled
from randomizer.conquest.network import ConquestLobby, authorize_action, decision_actor
from randomizer.conquest.players import roster, label
from randomizer.conquest.persistence import Repository, validate
from randomizer.ui.viewport import ScrollableViewport, fit_dialog
from .conquest_coop_launch import ConquestCoopLaunchController


class ConquestCoopController(ConquestCoopLaunchController):
    def initialize_conquest_coop(self):
        self._cq_lobby = None
        self._cq_pending = None
        self._cq_request = None
        self._cq_hello = {}
        self._cq_reports = {}
        self._cq_reported = None
        self._cq_identity = None
        self._cq_role = tk.StringVar(value='Host')
        self._cq_name = tk.StringVar(value=self.config.get('player_name', 'Commander')[:15])
        self._cq_address = tk.StringVar()
        self._cq_pairing = tk.StringVar(value=secrets.token_hex(12))
        self._cq_count = tk.StringVar(value='2')
        self._cq_status = tk.StringVar(value='Solo campaign · Connect through ZeroTier for 2–4 players.')
        self._cq_shared = tk.BooleanVar(value=False)

    def conquest_local_actor(self):
        state = self.conquest_state
        if not state or not state.get('coop'):
            return 'player'
        name = self._cq_identity or self._cq_name.get()
        return next((p['id'] for p in roster(state) if p['name'] == name), 'player')

    def conquest_cooperative(self):
        return bool(self._cq_lobby or self.conquest_state and self.conquest_state.get('coop'))

    def conquest_coop_ready(self):
        lobby = self._cq_lobby
        return bool(lobby and lobby.connected and
                    (lobby.role == 'guest' or len(self._cq_hello) == lobby.count))

    def conquest_orders_locked(self):
        return bool(self._cq_request or self._cq_pending or
                    self.conquest_cooperative() and not self.conquest_coop_ready())

    def conquest_can_create(self):
        if not conquest_enabled():
            return False
        if not self.conquest_cooperative():
            return True
        return bool(self.conquest_coop_ready() and self._cq_lobby.role == 'host' and
                    not (self.conquest_state and self.conquest_state['pending'] and self.conquest_state['pending']['attempt']))

    def conquest_can_advance(self):
        return not self.conquest_cooperative() or bool(self.conquest_coop_ready() and self._cq_lobby.role == 'host')

    def _cq_actor(self, slot):
        lobby = self._cq_lobby
        if type(slot) is not int or not 0 <= slot < lobby.count:
            raise ValueError('Invalid authenticated player slot.')
        name = lobby.players[slot]['name']
        return next((p['id'] for p in roster(self.conquest_state) if p['name'] == name), None)

    def _cq_validate_roster(self, state):
        lobby = self._cq_lobby
        players = roster(state)
        if (not state.get('coop') or len(players) != lobby.count or
            players[0]['name'] != lobby.players[0]['name'] or
            {p['name'] for p in players} != {p['name'] for p in lobby.players}):
            raise ValueError('Resume with the original host and player names. Join order may differ.')

    def cooperative_new_settings(self, settings):
        if not self.conquest_cooperative():
            return settings
        if not self.conquest_can_create():
            raise ValueError('Only the connected host can create a campaign after every player joins.')
        lobby = self._cq_lobby
        settings['coop_players'] = [dict(id='player' if i == 0 else f'player{i+1}', name=p['name'],
            country=self._cq_hello[i]['country']) for i, p in enumerate(lobby.players)]
        settings['shared_nodes'] = self._cq_shared.get()
        return settings

    def publish_conquest(self):
        lobby = self._cq_lobby
        if lobby and lobby.role == 'host' and self.conquest_coop_ready() and self.conquest_state:
            self._cq_validate_roster(self.conquest_state)
            lobby.send_snapshot(self.conquest_state)

    def _cq_session_ready(self):
        if self.conquest_state:
            try:
                self._cq_validate_roster(self.conquest_state)
            except ValueError:
                if self.conquest_state['pending'] and self.conquest_state['pending']['attempt']:
                    raise ValueError('Reconnect the original host and players to recover the unfinished battle before replacing this campaign.')
                # Keep the previous save on disk until the host explicitly
                # confirms replacement through New campaign.
                self.conquest_state = None
                self._cq_resume_attempt = None
        if self.conquest_state:
            self.publish_conquest()
        else:
            self._cq_status.set('All players connected. Host can create a campaign; replacing an existing save requires confirmation.')
        self.refresh_conquest()

    def _coop_safe_message(self, value):
        from randomizer.coop.privacy import redact_connection_details
        private = [getattr(self, name).get() for name in ('_cq_address', '_cq_pairing') if hasattr(self, name)]
        lobby = getattr(self, '_cq_lobby', None)
        if lobby:
            private.extend((lobby.address, lobby.pairing_code))
            private.extend(p['ip'] for p in lobby.players)
        return redact_connection_details(super()._coop_safe_message(value), *private)

    def open_conquest_coop(self):
        if not conquest_enabled():
            return
        existing = getattr(self, '_cq_window', None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            return
        window = self._cq_window = tk.Toplevel(self)
        window.title('Conquest · ZeroTier co-op')
        window.transient(self)
        viewport = ScrollableViewport(window, padding=16)
        viewport.pack(fill='both', expand=True)
        frame = viewport.content
        frame.columnconfigure(1, weight=1)
        fields = [('Role', self._cq_role, ('Host', 'Join')),
                  ('Human players', self._cq_count, ('2', '3', '4')),
                  ('Your name', self._cq_name, None),
                  ('Host ZeroTier IPv4 (Join)', self._cq_address, None),
                  ('Pairing code', self._cq_pairing, None)]
        for row, (title, variable, choices) in enumerate(fields):
            ttk.Label(frame, text=title).grid(row=row, column=0, sticky='w', padx=(0, 12), pady=5)
            widget = (ttk.Combobox(frame, textvariable=variable, values=choices, state='readonly')
                      if choices else ttk.Entry(frame, textvariable=variable, width=32))
            widget.grid(row=row, column=1, sticky='ew', pady=5)
        ttk.Label(frame, text='Choose your faction in New campaign before connecting. Use the same player count and pairing code on every PC. Reconnecting preserves personal ownership by player name. The original host keeps the authoritative save.', wraplength=460).grid(row=5, column=0, columnspan=2, sticky='ew', pady=8)
        ttk.Checkbutton(frame, text='New campaign: share territory stat bonuses only', variable=self._cq_shared).grid(row=6, column=0, columnspan=2, sticky='w')
        ttk.Label(frame, textvariable=self._cq_status, wraplength=460).grid(row=7, column=0, columnspan=2, sticky='ew', pady=8)
        ttk.Button(frame, text='Connect', command=self.connect_conquest_coop).grid(row=8, column=0, sticky='ew')
        ttk.Button(frame, text='Disconnect', command=self.disconnect_conquest_coop).grid(row=8, column=1, sticky='ew')
        def copy_code():
            self.clipboard_clear()
            self.clipboard_append(self._cq_pairing.get())
        ttk.Button(frame, text='Copy pairing code', command=copy_code).grid(row=9, column=0, sticky='ew', pady=8)
        ttk.Button(frame, text='Return to solo campaign', command=self.leave_conquest_coop).grid(row=9, column=1, sticky='ew', pady=8)
        ttk.Button(frame, text='Connection log', command=self._show_coop_log).grid(row=10, column=0, sticky='w')
        viewport.bind_controls()
        fit_dialog(window, frame)

    def connect_conquest_coop(self):
        if not conquest_enabled() or self._cq_lobby or self.conquest_busy() or self.busy_depth:
            return
        try:
            if self.gameplay_settings_locked() or getattr(self, '_coop_lobby', None) or getattr(self, '_fortress_lobby', None):
                raise ValueError('Disconnect the other multiplayer session first.')
            host = self._cq_role.get() == 'Host'
            addresses = zerotier_ipv4_addresses() if host else ()
            lobby = ConquestLobby(GAME_ROOT, 'host' if host else 'guest', self._cq_name.get(),
                int(self._cq_count.get()), address=self._cq_address.get(), pairing_code=self._cq_pairing.get())
            repository = Repository(APP_DIR / ('conquest_coop_state.json' if host else 'conquest_coop_guest.json'))
            state = repository.load()
            self.conquest_repository, self.conquest_state = repository, state if host else None
            self._cq_lobby = lobby
            self._cq_identity = lobby.name
            self._cq_hello, self._cq_reports = {}, {}
            self._cq_request = self._cq_reported = None
            self._cq_initial_sync = not host
            self._cq_resume_attempt = (state['pending']['attempt']['id'] if host and state and state['pending'] and state['pending']['attempt'] else None)
            self._conquest_error = ''
            lobby.start()
            self._cq_status.set('Connecting…' + (' Host ZeroTier IPv4: ' + ', '.join(addresses) if host else ''))
            self.refresh_conquest()
            self.after(100, lambda: self._poll_conquest_lobby(lobby))
        except (ValueError, RuntimeError, OSError) as exc:
            messagebox.showerror('Conquest co-op', str(exc), parent=self)

    def disconnect_conquest_coop(self, *, reason='Disconnected. Campaign paused until all players reconnect.'):
        lobby = self._cq_lobby
        if lobby:
            lobby.close()
        self._cq_lobby = None
        self._cq_request = None
        self._cq_status.set(reason)
        if self._cq_pending:
            self._cq_pending['cancelled'] = True
            if not self._cq_pending.get('worker'):
                self._cq_pending = None
                self._conquest_preparing = False
                self._release_conquest_runtime()
        self.refresh_conquest(reason)

    def leave_conquest_coop(self):
        if self.conquest_busy() or self._cq_pending:
            return
        self.disconnect_conquest_coop()
        self.conquest_repository = Repository()
        self.conquest_state = None
        self._cq_identity = None
        self._cq_status.set('Solo campaign')
        self.reload_conquest()

    def coop_conquest_action(self, action, values):
        if not self.conquest_coop_ready() or self.conquest_busy() or self._cq_request or self._conquest_error:
            return
        lobby = self._cq_lobby
        try:
            if not self.conquest_state:
                raise ValueError('Wait for the host to create or resume the campaign.')
            if lobby.role == 'host':
                self._cq_execute(lobby.slot, action, values)
            else:
                token = uuid.uuid4().hex
                self._cq_request = dict(token=token, deadline=time.monotonic() + 20)
                lobby.send(dict(type='cq_action', token=token, campaign=self.conquest_state['id'],
                    revision=self.conquest_state['revision'], action=action, values=values))
            self.refresh_conquest()
        except (ValueError, RuntimeError, OSError) as exc:
            self._cq_request = None
            self.refresh_conquest(str(exc))
            messagebox.showerror('Conquest co-op', str(exc), parent=self)

    def _cq_execute(self, slot, action, values):
        if self.conquest_busy() or self._cq_pending or self._conquest_error:
            raise ValueError('Wait for the current battle or preparation to finish.')
        if not self.conquest_coop_ready():
            raise ValueError('Wait for every commander to reconnect.')
        actor = self._cq_actor(slot)
        message = None
        if action == 'launch':
            authorize_action(self.conquest_state, actor, action, values)
            self.begin_conquest_coop_battle()
        else:
            result = self._conquest_change(lambda state: authorize_action(state, actor, action, values))
            message = result if isinstance(result, str) else None
        self.refresh_conquest(message)
        return message

    def _poll_conquest_lobby(self, lobby):
        if self._cq_lobby is not lobby:
            return
        try:
            for _ in range(40):
                try:
                    kind, value = lobby.events.get_nowait()
                except queue.Empty:
                    break
                if kind == 'connected':
                    country = self.conquest_view.settings['player_country'].get()
                    self._cq_hello[lobby.slot] = dict(country=country)
                    self._cq_status.set('Connected: ' + ', '.join(p['name'] for p in lobby.players))
                    if lobby.role == 'guest':
                        lobby.send(dict(type='cq_hello', country=country))
                    elif self.conquest_coop_ready():
                        self._cq_session_ready()
                elif kind == 'message':
                    self._handle_conquest_message(lobby, *value)
                elif kind == 'status':
                    self._cq_status.set(self._coop_safe_message(value))
                    self._record_coop_log('Conquest: ' + value)
                elif kind == 'error':
                    raise ValueError(self._coop_safe_message(value))
            if lobby.closed.is_set():
                raise ValueError('Conquest connection closed. Reconnect every player to resume.')
            if self._cq_pending and time.monotonic() > self._cq_pending['deadline']:
                raise ValueError('Conquest battle preparation timed out. Reconnect to recover.')
            if self._cq_request and time.monotonic() > self._cq_request['deadline']:
                raise ValueError('Host did not acknowledge the order. Reconnect to synchronize the saved result.')
            if self.conquest_coop_ready():
                self._cq_recover_local_result()
        except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
            self._record_coop_log('Conquest: ' + str(exc), error=True)
            self.disconnect_conquest_coop(reason=str(exc))
            return
        if self._cq_lobby is lobby:
            self.after(200, lambda: self._poll_conquest_lobby(lobby))

    def _handle_conquest_message(self, lobby, slot, message):
        kind = message.get('type')
        if kind == 'cq_hello' and lobby.role == 'host':
            if message.get('country') not in FACTIONS or slot == 0:
                raise ValueError('Invalid Conquest faction declaration.')
            self._cq_hello[slot] = dict(country=message['country'])
            if self.conquest_coop_ready():
                self._cq_session_ready()
        elif kind == 'state' and lobby.role == 'guest':
            state = validate(json.loads(unpack(message['snapshot'])))
            self._cq_validate_roster(state)
            if self._conquest_watch and (state['id'] != self.conquest_state['id'] or
                not state['pending'] or state['pending']['id'] != self.conquest_state['pending']['id']):
                raise ValueError('Host replaced an active battle unexpectedly.')
            if self._cq_initial_sync:
                self._cq_resume_attempt = state['pending']['attempt']['id'] if state['pending'] and state['pending']['attempt'] else None
                self._cq_initial_sync = False
            self.conquest_state = self.conquest_repository.mirror(state)
            self._conquest_error = ''
            self._cq_status.set('Synchronized · ' + label(state, decision_actor(state)) + ' controls this turn/encounter.')
            self.refresh_conquest()
        elif kind == 'cq_action' and lobby.role == 'host':
            token = message.get('token')
            if not isinstance(token, str) or len(token) != 32:
                raise ValueError('Invalid campaign order identity.')
            try:
                if (not self.conquest_state or message.get('campaign') != self.conquest_state['id'] or
                    type(message.get('revision')) is not int or message['revision'] != self.conquest_state['revision']):
                    raise ValueError('Campaign changed. Review the synchronized map and try again.')
                result = self._cq_execute(slot, message.get('action'), message.get('values'))
                lobby.send(dict(type='cq_ack', token=token, message=result), slot)
            except (ValueError, RuntimeError, OSError) as exc:
                self.publish_conquest()
                lobby.send(dict(type='cq_ack', token=token, error=str(exc)), slot)
        elif kind == 'cq_ack' and lobby.role == 'guest':
            if self._cq_request and message.get('token') == self._cq_request['token']:
                self._cq_request = None
                self.refresh_conquest(message.get('error') or message.get('message') or 'Order saved by host.')
        elif kind == 'cq_prepare' and lobby.role == 'guest':
            self.prepare_conquest_coop_guest(lobby, message)
        elif kind == 'cq_ready' and lobby.role == 'host':
            self.conquest_coop_guest_ready(lobby, slot, message)
        elif kind == 'cq_start' and lobby.role == 'guest':
            self.start_conquest_coop_guest(lobby, message)
        elif kind == 'cq_result' and lobby.role == 'host':
            self.accept_conquest_coop_result(slot, message)
        else:
            raise ValueError('Unexpected Conquest protocol message.')
