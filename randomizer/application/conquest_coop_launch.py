"""All-peer native launch agreement and durable coalition result consensus."""

from copy import deepcopy
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid

from randomizer.core.paths import GAME_ROOT, DEBUG_LOG
from randomizer.core.storage import atomic_write_json, read_json_object
from randomizer.conquest.transport_lobby import pack, unpack, installation_details
from randomizer.conquest.engine import render, install, verify_prepared
from randomizer.conquest.persistence import validate, commit_attempt, mark_launched, finish_attempt
from randomizer.conquest.players import roster
from randomizer.conquest.network import validate_endpoints
from randomizer.conquest.results import ResultWatch, recover, native_game_running
from randomizer.maps.assets import claim_runtime_asset_lease


class ConquestCoopLaunchController:
    def _cq_endpoints(self, state):
        by_name = {p['name']: p for p in self._cq_lobby.players}
        endpoints = [dict(name=p['name'], address=by_name[p['name']]['ip'], port=by_name[p['name']]['port'])
                     for p in roster(state)]
        validate_endpoints(state, endpoints)
        return endpoints

    def _cq_native_slot(self):
        return next(i for i, p in enumerate(roster(self.conquest_state)) if p['id'] == self.conquest_local_actor())

    def _cq_prepare_files(self, state, token, speed, endpoints, slot):
        command = self.build_command()
        if native_game_running(GAME_ROOT, any_installation=True):
            raise ValueError('Close the running game before joining this battle.')
        claim_runtime_asset_lease()
        self._conquest_runtime_owned = True
        self.cleanup_generated_root_maps()
        self.disable_generated_rules_for_client()
        claim_runtime_asset_lease()
        prepared = render(GAME_ROOT, state, token, game_speed=speed, coop_slot=slot, endpoints=endpoints)
        prepared['runtime_hash'] = installation_details(GAME_ROOT)[0]
        return prepared, command, dict(map_hash=hashlib.sha256(prepared['map']).hexdigest(),
                                      spawn_hash=hashlib.sha256(prepared['spawn']).hexdigest())

    def begin_conquest_coop_battle(self):
        lobby = self._cq_lobby
        if not self.conquest_coop_ready() or lobby.role != 'host' or self.conquest_busy():
            raise ValueError('Wait for every player before launching.')
        state = deepcopy(self.conquest_state)
        self._cq_validate_roster(state)
        token = uuid.uuid4().hex
        endpoints = self._cq_endpoints(state)
        speed = self.get_selected_game_speed_value()
        pending = dict(token=token, lobby=lobby, deadline=time.monotonic() + 180,
                       worker=True, cancelled=False, ready=set(), endpoints=endpoints)
        self._cq_pending = pending
        self._cq_reports = {}
        self._cq_reported = None
        self._conquest_preparing = True
        self.refresh_conquest('Preparing this encounter for every commander…')

        def work():
            prepared, command, hashes = self._cq_prepare_files(state, token, speed, endpoints, 0)
            committed, _ = self.conquest_repository.update(state['id'], state['revision'],
                lambda s: commit_attempt(s, state['pending']['id'], token, **hashes))
            install(GAME_ROOT, prepared)
            return committed, command, hashes, prepared['runtime_hash']

        def done(result):
            pending['worker'] = False
            self.conquest_state, pending['command'], pending['hashes'], pending['runtime_hash'] = result
            if pending['cancelled'] or self._cq_lobby is not lobby or not lobby.connected:
                return self._cq_finish_cancelled()
            self.publish_conquest()
            lobby.send(dict(type='cq_prepare', token=token, payload=pack(json.dumps(dict(
                state=self.conquest_state, endpoints=endpoints, speed=speed,
                runtime_hash=pending['runtime_hash'],
                map_hash=pending['hashes']['map_hash'])).encode())))
            self._cq_status.set('Waiting for every player to verify the identical battle map…')
            self.refresh_conquest()

        self.run_in_background('Preparing cooperative Conquest…', 'Freezing personal armies and the shared native map.',
                               work, done, self._cq_preparation_failed)

    def prepare_conquest_coop_guest(self, lobby, message):
        if self.conquest_busy() or self._cq_pending:
            raise ValueError('A battle is already running or being prepared.')
        payload = json.loads(unpack(message['payload']))
        state = validate(payload['state'])
        self._cq_validate_roster(state)
        token = message['token']
        attempt = state['pending']['attempt'] if state['pending'] else None
        if (not attempt or token != attempt['id'] or attempt['status'] != 'prepared' or
            payload['map_hash'] != attempt['map_hash'] or not self.conquest_state or
            state != self.conquest_state or payload['endpoints'] != self._cq_endpoints(state)):
            raise ValueError('Preparation differs from the authenticated campaign or network roster.')
        pending = dict(token=token, lobby=lobby, worker=True, cancelled=False,
                       deadline=time.monotonic() + 180, endpoints=payload['endpoints'])
        self._cq_pending = pending
        self._conquest_preparing = True
        self._cq_reported = None
        slot = self._cq_native_slot()
        self.refresh_conquest('Your teammate started this encounter. Preparing your personal army…')

        def work():
            prepared, command, hashes = self._cq_prepare_files(state, token, payload['speed'], payload['endpoints'], slot)
            if prepared['runtime_hash'] != payload.get('runtime_hash'):
                raise ValueError('Native game files differ between players. Update every installation to the same version, then retry.')
            if hashes['map_hash'] != payload['map_hash']:
                raise ValueError('Conquest battle map differs between players.')
            install(GAME_ROOT, prepared)
            return command, hashes

        def done(result):
            pending['worker'] = False
            pending['command'], pending['hashes'] = result
            if pending['cancelled'] or self._cq_lobby is not lobby or not lobby.connected:
                return self._cq_finish_cancelled()
            pending['ready'] = True
            lobby.send(dict(type='cq_ready', token=token, map_hash=pending['hashes']['map_hash']))
            self._cq_status.set('Battle verified. Waiting for all players…')
            self.refresh_conquest()

        self.run_in_background('Joining cooperative Conquest…', 'Validating personal loadouts and the shared map.',
                               work, done, self._cq_preparation_failed)

    def conquest_coop_guest_ready(self, lobby, slot, message):
        pending = self._cq_pending
        if (not pending or pending.get('worker') or slot == 0 or message.get('token') != pending['token'] or
            message.get('map_hash') != pending['hashes']['map_hash']):
            raise ValueError('Invalid or stale Conquest readiness.')
        pending['ready'].add(slot)
        if pending['ready'] != set(range(1, lobby.count)):
            return
        self._cq_verify_start(pending)
        self._conquest_change(lambda state: mark_launched(state, pending['token']))
        lobby.send(dict(type='cq_start', token=pending['token'], map_hash=pending['hashes']['map_hash']))
        self._cq_start_process(pending)

    def start_conquest_coop_guest(self, lobby, message):
        pending = self._cq_pending
        if (not pending or pending.get('ready') is not True or message.get('token') != pending['token'] or
            message.get('map_hash') != pending['hashes']['map_hash'] or
            self.conquest_state['pending']['attempt']['status'] != 'launched'):
            raise ValueError('Invalid Conquest start agreement.')
        self._cq_verify_start(pending)
        self._cq_start_process(pending)

    def _cq_verify_start(self, pending):
        if pending['cancelled'] or self._cq_lobby is not pending['lobby'] or not pending['lobby'].connected:
            raise ValueError('Conquest lobby disconnected before launch.')
        if self._cq_endpoints(self.conquest_state) != pending['endpoints']:
            raise ValueError('Conquest peer endpoints changed during preparation.')
        verify_prepared(GAME_ROOT, pending['hashes'])
        if native_game_running(GAME_ROOT, any_installation=True):
            raise ValueError('Another game started during preparation.')

    def _cq_start_process(self, pending):
        token, command = pending['token'], pending['command']
        watch = ResultWatch(DEBUG_LOG, token, self.conquest_state['pending'])
        options = {}
        if sys.platform == 'win32':
            from .launch_controller import windows_syringe_command_line
            options['executable'] = command[0]
            command = windows_syringe_command_line(command)
        else:
            environment = os.environ.copy()
            environment['WINEDLLOVERRIDES'] = ';'.join(filter(None, (environment.get('WINEDLLOVERRIDES', ''), 'ddraw=n,b')))
            options.update(env=environment, start_new_session=True)
        self.active_game_process = subprocess.Popen(command, cwd=GAME_ROOT, **options)
        self._conquest_attempt_id = token
        self._conquest_watch = watch
        self._cq_pending = None
        self._conquest_preparing = False
        self._cq_status.set('Battle running. Every commander uses their own upgrades.')
        self.refresh_conquest()
        self.after(500, self._poll_conquest)

    def _cq_preparation_failed(self, exc, detail):
        if self._cq_pending:
            self._cq_pending['worker'] = False
        self.append_log(detail, error=True)
        self.disconnect_conquest_coop(reason='Preparation stopped: ' + str(exc) + ' Reconnect all players to recover.')
        self._cq_finish_cancelled()

    def _cq_finish_cancelled(self):
        self._cq_pending = None
        self._conquest_preparing = False
        self._release_conquest_runtime()
        # A committed attempt remains durable until all peers report whether
        # they launched. Never silently re-enable autobattle after a partial go.
        self.conquest_state = self.conquest_repository.load()
        self.refresh_conquest()
        if getattr(self, '_close_after_game', False):
            self.close_launcher()

    def _cq_receipt_path(self):
        return self.conquest_repository.path.with_suffix('.receipt.json')

    def _cq_store_result(self, outcome):
        state = self.conquest_state
        attempt = state['pending']['attempt']
        player = next(p for p in roster(state) if p['id'] == self.conquest_local_actor())
        report = dict(type='cq_result', token=attempt['id'], campaign=state['id'],
                      map_hash=attempt['map_hash'], name=player['name'], outcome=outcome)
        atomic_write_json(self._cq_receipt_path(), report, durable=True)
        return report

    def _cq_send_result(self, report):
        lobby = self._cq_lobby
        if not self.conquest_coop_ready():
            return
        if lobby.role == 'host':
            self.accept_conquest_coop_result(lobby.slot, report)
        else:
            lobby.send(report)
        self._cq_reported = report['token']

    def _poll_conquest_coop(self):
        process, watch = self.active_game_process, self._conquest_watch
        try:
            running = process.poll() is None or native_game_running(GAME_ROOT)
            outcome = watch.poll(final=not running)
            if running:
                self.after(500, self._poll_conquest)
                return
            if not outcome:
                outcome = recover(DEBUG_LOG, self._conquest_attempt_id, self.conquest_state['pending'])
            report = self._cq_store_result(outcome)
            self._cq_resume_attempt = report['token']
            self.active_game_process = None
            self._conquest_watch = None
            self._conquest_error = ''
            self._release_conquest_runtime()
            self._cq_status.set('Battle closed. Waiting for every player’s result; reconnect if disconnected.')
            self._cq_send_result(report)
            self.refresh_conquest()
            if getattr(self, '_close_after_game', False):
                self.close_launcher()
        except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
            self._conquest_error = str(exc)
            self.refresh_conquest()
            if self._conquest_watch:
                self.after(1000, self._poll_conquest)
            else:
                self.disconnect_conquest_coop(reason='Battle receipt saved. Reconnect to synchronize: ' + str(exc))
                if getattr(self, '_close_after_game', False):
                    self.close_launcher()

    def _cq_recover_local_result(self):
        state = self.conquest_state
        if not state or not state.get('coop') or not state['pending'] or not state['pending']['attempt']:
            return
        attempt = state['pending']['attempt']
        if (self.conquest_busy() or self._cq_pending or self._cq_reported == attempt['id'] or
            getattr(self, '_cq_resume_attempt', None) != attempt['id']):
            return
        if time.monotonic() < getattr(self, '_cq_next_recovery', 0):
            return
        self._cq_next_recovery = time.monotonic() + 3
        if native_game_running(GAME_ROOT):
            self._cq_status.set('Close the previous native battle before recovering this campaign.')
            return
        saved = read_json_object(self._cq_receipt_path()) if self._cq_receipt_path().is_file() else {}
        name = next(p['name'] for p in roster(state) if p['id'] == self.conquest_local_actor())
        if (saved.get('token') == attempt['id'] and saved.get('map_hash') == attempt['map_hash'] and
            saved.get('campaign') == state['id'] and saved.get('name') == name and
            saved.get('outcome') in (None, 'victory', 'defeat')):
            report = saved
        else:
            report = self._cq_store_result(recover(DEBUG_LOG, attempt['id'], state['pending']))
        self._cq_send_result(report)

    def accept_conquest_coop_result(self, slot, report):
        state, lobby = self.conquest_state, self._cq_lobby
        battle = state['pending'] if state else None
        attempt = battle['attempt'] if battle else None
        if not attempt:
            return  # Retransmission of an already finalized result.
        if (report.get('token') != attempt['id'] or report.get('campaign') != state['id'] or
            report.get('map_hash') != attempt['map_hash'] or report.get('outcome') not in (None, 'victory', 'defeat') or
            report.get('name') != lobby.players[slot]['name']):
            raise ValueError('Cooperative result differs from the committed battle or authenticated player.')
        name = report['name']
        if name in self._cq_reports and self._cq_reports[name] != report['outcome']:
            raise ValueError('Player sent conflicting battle outcomes. Reconnect to recover from native logs.')
        self._cq_reports[name] = report['outcome']
        required = {p['name'] for p in roster(state)}
        if set(self._cq_reports) != required:
            self._cq_status.set('Waiting for battle results: ' + ', '.join(sorted(required - self._cq_reports.keys())))
            return
        outcomes = set(self._cq_reports.values())
        outcome = next(iter(outcomes)) if len(outcomes) == 1 and None not in outcomes else None
        receipts = dict(self._cq_reports)
        def commit(current):
            finish_attempt(current, attempt['id'], outcome)
            current['attempts'][-1]['players'] = receipts
        self._conquest_change(commit)
        self._cq_status.set('All players agreed; battle saved.' if outcome else
                            'Results missing or disagree. Same encounter remains pending for retry or autobattle.')
        self.refresh_conquest()
