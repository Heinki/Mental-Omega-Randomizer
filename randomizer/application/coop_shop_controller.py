"""Host mission control and personal-economy synchronization for co-op Shop."""

from randomizer.coop.shop_stage import apply_stage_snapshot, stage_digest, stage_snapshot
from randomizer.shop.model import RunStatus


class CoopShopSetupRequired(ValueError):
    """A paired guest must prepare its own Shop run before stage sync."""

    def __init__(self, snapshot):
        seed = snapshot.get('seed') if isinstance(snapshot, dict) else None
        stage = snapshot.get('stage') if isinstance(snapshot, dict) else None
        if (not isinstance(seed, str) or not seed or len(seed) > 128
                or type(stage) is not int or stage < 1):
            raise ValueError('Invalid host Shop stage snapshot.')
        self.seed = seed
        super().__init__(
            f'Host is playing Shop Mode. Host seed: {seed}; stage: {stage}.\n\n'
            'Select Shop Mode, enable co-op, and start your own Shop run with '
            'the same seed before joining. Both runs must have the same stage '
            'and completed missions. Your profile and purchases stay separate.'
        )


class CoopShopController:
    def suggest_coop_shop_mission(self, index):
        lobby = getattr(self, '_coop_lobby', None)
        run = self.shop_repository.load_run()
        if (not lobby or not lobby.connected or run is None
                or run.status is not RunStatus.ACTIVE or run.mission_committed
                or self.shop_launch_active() or getattr(self, '_coop_busy', False)):
            return
        try:
            code = self.shop_mission_cards[int(index)]['code']
            if code not in {offer.mission_code for offer in run.mission_offers}:
                return
            lobby.send({'type': 'shop_suggest', 'code': code,
                        'digest': self._coop_shop_stage_digest})
            self._set_shop_message(f'Suggested {code} to the host.')
        except (OSError, IndexError, ValueError) as exc:
            self._set_shop_message(exc, error=True)

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
            self._record_coop_log('Co-op Shop stage sync failed: ' + str(exc), error=True)

    def receive_coop_shop_message(self, lobby, message):
        kind = message['type']
        if lobby.role == 'guest':
            if kind == 'shop_stage':
                if not self.coop_mode_var.get():
                    raise ValueError('Enable co-op before joining a Shop host.')
                run = self.shop_repository.load_run()
                snapshot = message.get('data')
                if (not self.shop_mode_selected() or run is None
                        or run.status is not RunStatus.ACTIVE):
                    raise CoopShopSetupRequired(snapshot)
                updated = apply_stage_snapshot(run, snapshot, self.mission_lookup())
                if updated != run:
                    self.shop_repository.save_run(updated)
                self.shop_run = updated
                self._coop_shop_stage_digest = stage_digest(snapshot)
                self.refresh_shop_mode()
                lobby.send({'type': 'shop_ready', 'digest': stage_digest(snapshot)})
                self._record_coop_log(f'Host Shop stage {updated.stage} synced.')
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
                    return True
                if (run is None or run.status is not RunStatus.ACTIVE
                        or run.seed != message.get('seed') or run.stage != stage
                        or not run.mission_committed
                        or run.selected_mission_code != code):
                    raise ValueError('Host Shop victory differs from guest committed stage.')
                self._shop_launch_run = run
                self._shop_launch_mission_pool = tuple(self._shop_run_mission_pool(run))
                if not self.unlock_mission_check(code, 'victory', 'Co-op host victory'):
                    raise ValueError('Guest Shop victory could not be recorded.')
                self._record_coop_log(f'Co-op Shop victory synced for {code}.')
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
                    return True
                if (run.status is RunStatus.ACTIVE and not run.mission_committed
                        and run.emergency_revivals_used > 0):
                    return True
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
                self._record_coop_log(f'Co-op Shop failure synced for {code}.')
                process = getattr(self, 'active_game_process', None)
                if process is None or process.poll() is not None:
                    self.finish_progression_launch_context()
            else:
                return False
            return True
        if kind == 'shop_ready':
            if (self.shop_mode_selected() and self.coop_mode_var.get()
                    and getattr(self, '_coop_shop_stage_digest', '')
                    and message.get('digest') == self._coop_shop_stage_digest):
                self._coop_shop_ready = True
                self._record_coop_log('Guest Shop stage ready.')
                self.refresh_shop_mode()
            else:
                # An acknowledgement can cross a reroll/selection already
                # published by the host. Only the current digest grants ready.
                self._record_coop_log('Ignored acknowledgement for an older Shop stage.')
            return True
        if kind == 'shop_suggest':
            run = self.shop_repository.load_run()
            code = message.get('code')
            if (self.shop_mode_selected() and run is not None
                    and run.status is RunStatus.ACTIVE and not run.mission_committed
                    and message.get('digest') == getattr(self, '_coop_shop_stage_digest', '')
                    and code in {offer.mission_code for offer in run.mission_offers}):
                mission = self.mission_lookup().get(code, {})
                self._set_shop_message(f'{lobby.peer} suggests {mission.get("title", code)}.')
                self._record_coop_log(f'{lobby.peer} suggests Shop mission {code}.')
            return True
        return False
