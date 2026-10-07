"""Exercise private Shop failure settlement and host-controlled revival."""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from randomizer.application import coop_controller
from randomizer.application.coop_controller import CoopController
from randomizer.application.shop_controller import ShopController
from randomizer.coop.catalogue import discover_coop_missions
from randomizer.coop.shop_stage import (
    apply_stage_snapshot, recovery_result_message, stage_snapshot,
)
from randomizer.shop.config import SHOP_CONFIG
from randomizer.shop.model import (
    BuffPurchase, MissionEconomyClass, MissionOffer, PurchaseRecord,
    RunStatus, ShopProfile, ShopRun,
)
from randomizer.shop.persistence import ShopPersistencePaths, ShopRepository
from randomizer.shop.service import ShopProgressionService
from randomizer.shop.state import normalize_shop_run
from randomizer.core.paths import GAME_ROOT


class Repository:
    def __init__(self, profile, run):
        self.profile = profile
        self.run = run
        self.commits = 0

    def load(self):
        return self.profile, self.run

    def load_run(self):
        return self.run

    def save_run(self, run):
        self.run = run

    def commit(self, profile, run, _transaction):
        self.profile, self.run = profile, run
        self.commits += 1


class Lobby:
    def __init__(self, role):
        self.role = role
        self.connected = True
        self.sent = []

    def send(self, message):
        self.sent.append(message)


class Harness:
    record_failed_mission_attempt = ShopController.record_failed_mission_attempt
    unlock_mission_check = ShopController.unlock_mission_check
    _handle_coop_message = CoopController._handle_coop_message
    _poll_coop_game = CoopController._poll_coop_game
    coop_publish_state = CoopController.coop_publish_state

    def __init__(self, role, profile, run, mission_pool):
        self.shop_repository = Repository(profile, run)
        self.shop_service = ShopProgressionService(self.shop_repository)
        self.shop_profile = profile
        self.shop_run = run
        self.shop_config = SHOP_CONFIG
        self._shop_launch_run = run
        self._shop_launch_mission_pool = tuple(mission_pool)
        self._coop_active_game_token = 'private-game-token-1234567890123456'
        self._coop_active_game_role = role
        self._coop_lobby = Lobby(role)
        self.coop_mode_var = type('Var', (), {'get': lambda _self: True})()
        self.messages = []
        self.published = 0

    def shop_mode_selected(self):
        return True

    def shop_launch_active(self):
        return self._shop_launch_run is not None

    def _shop_run_mission_pool(self, _run):
        return self._shop_launch_mission_pool

    def mission_lookup(self):
        return {mission['code']: mission
                for mission in self._shop_launch_mission_pool}

    def show_shop_failure_result(self, *_args):
        pass

    def show_shop_victory_result(self, *_args):
        pass

    def record_archipelago_shop_victory(self, *_args):
        pass

    def refresh_shop_mode(self):
        pass

    def _set_shop_message(self, message, *, error=False):
        self.messages.append((str(message), error))

    def append_log(self, message, error=False):
        self.messages.append((str(message), error))

    _record_coop_log = append_log

    def coop_publish_shop_stage(self):
        self.published += 1
        self._coop_lobby.send({
            'type': 'shop_stage',
            'data': stage_snapshot(self.shop_repository.run),
        })

    def _scan_coop_victory(self):
        pass

    def is_mission_complete(self, _code):
        return False

    def finish_progression_launch_context(self):
        self._shop_launch_run = None


def check_case(host_revivals, *, disconnected=False):
    missions = discover_coop_missions(GAME_ROOT)
    codes = [mission['code'] for mission in missions[:4]]
    offers = tuple(MissionOffer(code, MissionEconomyClass.ACT_1)
                   for code in codes[:3])
    base = dict(
        seed='COOP-FAILURE-CHECK', status=RunStatus.ACTIVE,
        stage=1, run_length=10, mission_offers=offers,
        selected_mission_code=codes[0], mission_committed=True,
        eligible_mission_codes=tuple(codes),
    )
    host = Harness(
        'host', ShopProfile(permanent_upgrades={
            'emergency_revival': host_revivals,
        }), ShopRun(run_id='host', run_coins=100, **base), missions,
    )
    guest = Harness(
        'guest', ShopProfile(meta_coins=29), ShopRun(
            run_id='guest', run_coins=37,
            run_purchases=base_run_purchases,
            run_buffs=base_run_buffs,
            **base,
        ), missions,
    )
    host._coop_victory_watch = {'code': codes[0], 'detected': False}
    host.active_game_process = type('Exited', (), {'poll': lambda _self: 0})()
    if disconnected:
        host._coop_lobby = None
    with TemporaryDirectory() as temporary:
        prior_log = coop_controller.DEBUG_LOG
        coop_controller.DEBUG_LOG = Path(temporary) / 'debug.log'
        coop_controller.DEBUG_LOG.write_text('Game finished without win marker\n')
        try:
            host._poll_coop_game()
        finally:
            coop_controller.DEBUG_LOG = prior_log
    assert host.shop_repository.commits == 1
    reloaded = normalize_shop_run(host.shop_repository.run.to_dict())
    assert reloaded.coop_last_result == host.shop_repository.run.coop_last_result
    if disconnected:
        assert host.published == 0
        host._coop_lobby = Lobby('host')
        host.coop_publish_state()
    message = host._coop_lobby.sent[0]
    assert message['type'] == 'shop_failure'
    assert message['revived'] is bool(host_revivals)
    assert bool(message.get('recovery')) is disconnected
    guest._shop_launch_run = None  # Guest game may close before host game.
    guest._handle_coop_message(guest._coop_lobby, message)
    assert guest.shop_repository.commits == 1
    assert guest._shop_launch_run is None
    if host_revivals:
        assert host._coop_lobby.sent[1]['type'] == 'shop_stage'
        guest._handle_coop_message(
            guest._coop_lobby, host._coop_lobby.sent[1]
        )
    assert guest.shop_repository.run.status == host.shop_repository.run.status
    assert guest.shop_repository.run.run_coins == 37
    assert guest.shop_repository.run.run_purchases == base_run_purchases
    assert guest.shop_repository.run.run_buffs == base_run_buffs
    assert guest.shop_repository.profile.meta_coins == 29
    guest._handle_coop_message(guest._coop_lobby, message)
    assert guest.shop_repository.commits == 1
    wrong = dict(message, session_token='stale-game-token', recovery=None)
    try:
        guest._handle_coop_message(guest._coop_lobby, wrong)
    except ValueError:
        pass
    else:
        raise AssertionError('Stale Shop failure was accepted.')
    if host_revivals:
        assert host.published == 1
        assert guest.shop_repository.run.emergency_revivals_used == 1
        assert not guest.shop_repository.run.mission_committed
        assert guest.shop_repository.run.mission_offers == (
            host.shop_repository.run.mission_offers
        )
        synced = apply_stage_snapshot(
            guest.shop_repository.run, stage_snapshot(host.shop_repository.run),
            {mission['code']: mission for mission in missions},
        )
        assert synced.mission_offers == host.shop_repository.run.mission_offers
        assert synced.run_coins == 37
    else:
        assert host.published == 0
        assert guest.shop_repository.run.failed_stage == 1


def check_victory_recovery():
    missions = discover_coop_missions(GAME_ROOT)
    code = missions[0]['code']
    base = dict(
        seed='COOP-VICTORY-RECOVERY', status=RunStatus.ACTIVE,
        stage=1, run_length=1, run_coins=55,
        mission_offers=(MissionOffer(code, MissionEconomyClass.ACT_1),),
        selected_mission_code=code, mission_committed=True,
        eligible_mission_codes=(code,),
    )
    host = Harness('host', ShopProfile(meta_coins=7),
                   ShopRun(run_id='host-win', **base), missions)
    guest = Harness('guest', ShopProfile(meta_coins=29),
                    ShopRun(run_id='guest-win', **base), missions)
    host_result = host.shop_service.record_victory(
        code, record_coop_result=True,
    )
    assert host_result.changed
    saved_host_run = normalize_shop_run(host.shop_repository.run.to_dict())
    message = recovery_result_message(saved_host_run)
    assert message == {'type': 'shop_victory', 'seed': base['seed'],
                       'stage': 1, 'code': code}
    host.coop_publish_state()
    assert host._coop_lobby.sent == [message]
    guest._shop_launch_run = None
    guest._handle_coop_message(guest._coop_lobby, message)
    assert guest.shop_repository.run.status is RunStatus.COMPLETED
    assert guest.shop_repository.run.run_id == 'guest-win'
    assert guest.shop_repository.commits == 1
    assert guest._shop_launch_run is None
    guest._handle_coop_message(guest._coop_lobby, message)
    assert guest.shop_repository.commits == 1
    with TemporaryDirectory() as temporary:
        folder = Path(temporary)
        paths = ShopPersistencePaths(
            profile=folder / 'profile.json', run=folder / 'run.json',
            transaction=folder / 'transaction.json',
            backup_dir=folder / 'backups',
        )
        stored = ShopRepository(paths)
        stored.save_profile(ShopProfile(meta_coins=7))
        stored.save_run(ShopRun(run_id='durable-host', **base))
        ShopProgressionService(stored).record_victory(
            code, record_coop_result=True,
        )
        saved_profile, saved_run = ShopRepository(paths).load()
        assert saved_profile.meta_coins > 7
        assert recovery_result_message(saved_run) == message
        assert not paths.transaction.exists()


base_run_purchases = (PurchaseRecord('Stryker IFV Access'),)
base_run_buffs = (BuffPurchase('Stryker IFV Armor Plating I'),)


if __name__ == '__main__':
    check_case(0)
    check_case(1)
    check_case(0, disconnected=True)
    check_case(1, disconnected=True)
    check_victory_recovery()
    print('Co-op Shop failure, revival, victory recovery, deduplication: passed')
