"""Frozen Fortress launch agreement; each machine validates its own map and rewards."""

from copy import deepcopy
import re
import secrets
import time
from tkinter import messagebox

from randomizer.coop.lobby import decode_state, encode_state
from randomizer.core.game_shutdown import GameShutdownWatch
from randomizer.core.paths import DEBUG_LOG, GAME_ROOT
from randomizer.final_fortress.coop import result_identity, validate_endpoints
from randomizer.final_fortress.engine import prepare_game
from randomizer.final_fortress.persistence import FinalFortressPersistenceError
from randomizer.final_fortress.results import FinalFortressResultWatch
from randomizer.ui.cameos import installed_rules_registry


class FortressCoopLaunchController:
    def launch_fortress_coop(self):
        self.refresh_final_fortress()
        process = getattr(self, 'active_game_process', None)
        if (not self.fortress_coop_ready() or self._final_fortress_preparing
                or self._final_fortress_watch is not None or self._final_fortress_launch_blockers
                or getattr(self, '_coop_lobby', None) or getattr(self, '_coop_busy', False)
                or (process is not None and process.poll() is None)):
            return
        sessions = dict(self._fortress_lobbies)
        first = next(iter(sessions.values()))
        players = [first.name, *[sessions[i].peer for i in sorted(sessions)]]
        endpoints = [{'name': players[0], 'address': first.ipv4_pair()[0], 'port': 1234},
                     *[{'name': sessions[i].peer, 'address': sessions[i].ipv4_pair()[1],
                        'port': 1234 + i} for i in sorted(sessions)]]
        preferences = dict(self.final_fortress_state['preferences'])
        preferences['player_color'] = self.selected_fortress_color()
        repository = self.final_fortress_repository
        config = deepcopy(self.final_fortress_config)
        from randomizer.final_fortress.economy import selected_fundraising_rank
        fundraising_ranks = [selected_fundraising_rank(self.final_fortress_state),
                             *[self._fortress_fundraising_ranks[i] for i in sorted(sessions)]]
        speed = self.get_selected_game_speed_value()
        pending = self._new_fortress_preparation(secrets.token_hex(24), sessions)
        pending['endpoints'] = endpoints
        pending['speed'] = speed

        def prepare():
            _, rules = installed_rules_registry(synchronous=True)
            self.begin_direct_game_preparation()
            self._finish_previous_fortress_run(repository)
            state, run_id = repository.begin_run(
                config, difficulty=preferences['difficulty'], seed='FF-' + secrets.token_hex(8),
                player_country=preferences['player_country'],
                player_color=preferences['player_color'],
                wave_multiplier=preferences['wave_multiplier'],
                mental_ai_boost=preferences['mental_ai_boost'], coop_players=players,
                fundraising_ranks=fundraising_ranks)
            pending['run_id'] = run_id
            run = state['run']
            digest = prepare_game(GAME_ROOT, run, rules, game_speed=speed,
                                  coop_slot=0, endpoints=endpoints)
            return run, digest, self.build_command()

        def prepared(result):
            self._fortress_worker_active = False
            if pending.get('cancelled'):
                return self._abort_fortress_coop(pending['cancelled'])
            run, digest, command = result
            if not all(lobby.connected for lobby in sessions.values()):
                raise ConnectionError('A Fortress player disconnected during preparation.')
            pending.update(run=run, digest=digest, command=command, ready=set())
            payload = encode_state({'coop_mode': True, 'run': run, 'endpoints': endpoints,
                                    'game_speed': speed, 'map_sha256': digest})
            for lobby in sessions.values():
                lobby.send({'type': 'fortress_prepare', 'token': pending['token'], 'payload': payload})
            self.fortress_coop_status_var.set('Host map ready. Waiting for every guest to validate it…')

        self._run_fortress_preparation(prepare, prepared)

    @staticmethod
    def _finish_previous_fortress_run(repository):
        repository.recover_finished_run(DEBUG_LOG)
        previous = repository.load()['run']
        if previous is not None and previous['status'] == 'active':
            repository.record_event(previous['id'], 'abandoned')

    def _new_fortress_preparation(self, token, sessions):
        pending = {'token': token, 'sessions': sessions, 'deadline': time.monotonic() + 180}
        self._fortress_pending = pending
        self._final_fortress_preparing = True
        self.refresh_final_fortress()
        self.refresh_game_speed_controls()
        return pending

    def _run_fortress_preparation(self, prepare, prepared):
        self._fortress_worker_active = True
        def failed(exc, detail):
            self._fortress_worker_active = False
            self.append_log(self._fortress_safe_message(detail), error=True)
            self._abort_fortress_coop(str(exc))
        self.run_in_background('Preparing Fortress co-op…',
                               'Validating the shared run and preparing identical survival maps.',
                               prepare, prepared, failed)

    def _handle_fortress_message(self, slot, lobby, message):
        kind = message.get('type')
        if kind == 'fortress_fundraising':
            from randomizer.final_fortress.economy import validate_fundraising_ranks
            if self._fortress_role != 'host' or slot not in self._fortress_lobbies:
                raise ValueError('Only a connected guest may advertise a Fundraising rank.')
            rank = message.get('rank')
            validate_fundraising_ranks([rank], 1)
            self._fortress_fundraising_ranks[slot] = rank
            self.refresh_final_fortress()
            return
        if kind == 'fortress_idle' and self._fortress_role == 'host':
            if getattr(self, '_fortress_peer_runs', {}).get(slot) == message.get('run_id'):
                del self._fortress_peer_runs[slot]
                if not self._fortress_peer_runs:
                    self._publish_fortress_roster()
                self.refresh_final_fortress()
            return
        if kind == 'fortress_roster':
            if self._fortress_role != 'guest':
                raise ValueError('Only the host may publish a Fortress roster.')
            players = message.get('players')
            assigned_slot = message.get('slot')
            if (not isinstance(players, list) or not 2 <= len(players) <= 3
                    or not all(isinstance(name, str) for name in players)
                    or type(assigned_slot) is not int or not 0 < assigned_slot < len(players)
                    or (slot is not None and assigned_slot != slot)
                    or players[assigned_slot] != lobby.name or players[0] != lobby.peer):
                raise ValueError('The host Fortress roster does not include this player.')
            self._fortress_local_slot = assigned_slot
            self._fortress_lobbies = {assigned_slot: lobby}
            self._fortress_roster = players
            map_id = message.get('map_id')
            if map_id is not None:
                from randomizer.final_fortress.maps import select_map
                select_map(self.final_fortress_map_catalogue, map_id)
            self._fortress_host_map_id = map_id
            self._fortress_coop_count_var.set(str(len(players)))
            self.fortress_coop_status_var.set(' / '.join(players) + ' — ' + str(message.get('setup', '')))
            self.refresh_final_fortress()
            return
        if kind == 'fortress_prepare':
            try:
                return self._prepare_fortress_guest(slot, lobby, message)
            except (ValueError, OSError, RuntimeError, KeyError, TypeError):
                if not getattr(self, '_fortress_pending', None):
                    lobby.send({'type': 'fortress_abort', 'token': message.get('token')})
                raise
        pending = getattr(self, '_fortress_pending', None)
        if not pending or message.get('token') != pending['token']:
            return
        if kind == 'fortress_abort':
            self._abort_fortress_coop('A peer cancelled Fortress preparation.', notify=False)
        elif kind == 'fortress_ready' and self._fortress_role == 'host':
            if (pending.get('cancelled') or 'digest' not in pending
                    or message.get('run_id') != pending['run']['id']
                    or message.get('map_sha256') != pending['digest']):
                raise ValueError('Fortress maps differ between players. Use matching builds and game files.')
            pending['ready'].add(slot)
            if pending['ready'] == set(pending['sessions']):
                for peer in pending['sessions'].values():
                    peer.send({'type': 'fortress_start', 'token': pending['token'],
                               'run_id': pending['run']['id'], 'map_sha256': pending['digest']})
                self._spawn_fortress_coop_game(pending)
        elif kind == 'fortress_start' and self._fortress_role == 'guest':
            if (pending.get('cancelled') or not pending.get('ready')
                    or message.get('run_id') != pending['run']['id']
                    or message.get('map_sha256') != pending['digest']):
                raise ValueError('Fortress start arrived before the local map was ready.')
            self._spawn_fortress_coop_game(pending)

    def _prepare_fortress_guest(self, slot, lobby, message):
        process = getattr(self, 'active_game_process', None)
        if (self._fortress_role != 'guest' or type(slot) is not int or slot not in (1, 2)
                or self._final_fortress_preparing
                or self._final_fortress_watch is not None
                or (process is not None and process.poll() is None)):
            raise ValueError('Cannot replace an active Fortress game.')
        token = message.get('token')
        if not isinstance(token, str) or not re.fullmatch('[0-9a-f]{48}', token):
            raise ValueError('Invalid Fortress launch identity.')
        payload = decode_state(message['payload'])
        run = payload['run']
        if not isinstance(run, dict) or not isinstance(run.get('plan'), dict):
            raise ValueError('Invalid Fortress run snapshot.')
        plan = run['plan']
        players = plan.get('coop_players', [])
        if (players != self._fortress_roster or slot >= len(players)
                or players[slot] != lobby.name or players[0] != lobby.peer):
            raise ValueError('Fortress launch differs from the connected roster.')
        from randomizer.final_fortress.economy import selected_fundraising_rank, validate_fundraising_ranks
        personal = plan.get('fundraising_ranks')
        validate_fundraising_ranks(personal, len(players))
        if personal[slot] != selected_fundraising_rank(self.final_fortress_state):
            raise ValueError('Your Fundraising selection changed. Ask the host to launch again.')
        validate_endpoints(plan, payload['endpoints'])
        if (payload['endpoints'][0]['address'] != lobby.ipv4_pair()[1]
                or payload['endpoints'][slot]['address'] != lobby.ipv4_pair()[0]):
            raise ValueError('Fortress endpoints differ from the authenticated network connection.')
        repository = self.final_fortress_repository
        pending = self._new_fortress_preparation(token, {slot: lobby})

        def prepare():
            _, rules = installed_rules_registry(synchronous=True)
            self.begin_direct_game_preparation()
            self._finish_previous_fortress_run(repository)
            state = repository.join_coop_run(run, lobby.name)
            pending['run_id'] = run['id']
            digest = prepare_game(GAME_ROOT, state['run'], rules, game_speed=payload['game_speed'],
                                  coop_slot=slot, endpoints=payload['endpoints'])
            if digest != payload['map_sha256']:
                raise ValueError('Fortress maps differ. Update all launchers and use matching game files.')
            return state['run'], digest, self.build_command()

        def prepared(result):
            self._fortress_worker_active = False
            if pending.get('cancelled'):
                return self._abort_fortress_coop(pending['cancelled'])
            current_run, digest, command = result
            pending.update(run=current_run, digest=digest, command=command, ready=True)
            lobby.send({'type': 'fortress_ready', 'token': token,
                        'run_id': current_run['id'], 'map_sha256': digest})
            self.fortress_coop_status_var.set('Map verified. Waiting for the host to start everyone…')

        self._run_fortress_preparation(prepare, prepared)

    def _spawn_fortress_coop_game(self, pending):
        if pending is not self._fortress_pending or pending.get('cancelled'):
            raise ValueError('Fortress preparation was cancelled.')
        if not all(lobby.connected for lobby in pending['sessions'].values()):
            raise ConnectionError('A Fortress player disconnected before launch.')
        run = pending['run']
        name, transfers, slot = result_identity(run)
        watch = FinalFortressResultWatch(DEBUG_LOG, run['id'], run['plan'], player_name=name,
                                         initial_transfers=transfers, coop_slot=slot)
        shutdown = GameShutdownWatch(DEBUG_LOG)
        try:
            process, _ = self.spawn_game_process(pending['command'])
        except Exception:
            shutdown.close()
            raise
        shutdown.bind(process)
        self.active_game_process = process
        self._final_fortress_watch = watch
        self._final_fortress_shutdown = shutdown
        self._final_fortress_logged_waves = 0
        self._final_fortress_recorded_events = set()
        self._final_fortress_recorded_kills = None
        self._final_fortress_preparing = False
        self._fortress_last_run = run['id']
        if self._fortress_role == 'host':
            self._fortress_peer_runs = {slot: run['id'] for slot in pending['sessions']}
        self._fortress_pending = None
        self.append_log(f'Fortress co-op started for {name}: run {run["id"]}; map {pending["digest"]}.')
        self.fortress_coop_status_var.set('Fortress co-op running. Defensive Points save to your own profile.')
        self.refresh_game_speed_controls()
        self.refresh_final_fortress()
        self.after(500, self._poll_final_fortress_game)

    def fortress_coop_game_finished(self, run_id):
        if not getattr(self, '_fortress_lobbies', None) or run_id != getattr(self, '_fortress_last_run', None):
            return
        if self._fortress_role == 'guest':
            for lobby in self._fortress_lobbies.values():
                if lobby.connected:
                    try:
                        lobby.send({'type': 'fortress_idle', 'run_id': run_id})
                    except OSError:
                        self.fortress_coop_status_var.set('Game ended. Reconnect the Fortress lobby before another run.')
                        return
            self.fortress_coop_status_var.set('Game ended. Your Defensive Points are saved; waiting for the host.')
        elif self._fortress_peer_runs:
            self.fortress_coop_status_var.set('Game ended. Waiting for other players to finish before the next run.')
        else:
            try:
                self._publish_fortress_roster()
            except OSError:
                self.fortress_coop_status_var.set('Game ended. Reconnect the Fortress lobby before another run.')

    def _abort_fortress_coop(self, reason, *, notify=True):
        reason = self._fortress_safe_message(reason)
        pending = getattr(self, '_fortress_pending', None)
        if pending and not pending.get('cancelled'):
            pending['cancelled'] = reason
            if notify:
                for lobby in pending['sessions'].values():
                    if lobby.connected:
                        try:
                            lobby.send({'type': 'fortress_abort', 'token': pending['token']})
                        except OSError:
                            pass
        if getattr(self, '_fortress_worker_active', False):
            return
        if pending:
            run_id = pending.get('run_id')
            if run_id:
                try:
                    self.final_fortress_repository.record_event(run_id, 'abandoned')
                except (ValueError, FinalFortressPersistenceError) as exc:
                    self.append_log(str(exc), error=True)
            self.disable_generated_rules_for_client()
        self._fortress_pending = None
        self._final_fortress_preparing = False
        self.fortress_coop_status_var.set('Fortress co-op stopped: ' + reason)
        self.append_log('Fortress co-op: ' + reason, error=True)
        self.refresh_final_fortress()
        self.refresh_game_speed_controls()
        if getattr(self, '_close_after_game', False):
            self.close_launcher()
        elif pending:
            messagebox.showerror('Fortress co-op', reason, parent=self)
