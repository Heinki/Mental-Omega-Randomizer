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
from randomizer.coop.shop_stage import apply_stage_snapshot, stage_snapshot
from randomizer.shop.config import SHOP_CONFIG
from randomizer.shop.model import (
    BuffPurchase, MissionEconomyClass, MissionOffer, PurchaseRecord,
    RunStatus, ShopProfile, ShopRun,
)
from randomizer.shop.service import ShopProgressionService
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
    _handle_coop_message = CoopController._handle_coop_message
    _poll_coop_game = CoopController._poll_coop_game

    def __init__(self, role, profile, run, mission_pool):
        self.shop_repository = Repository(profile, run)
        self.shop_service = ShopProgressionService(self.shop_repository)
        self.shop_profile = profile
        self.shop_run = run
        self.shop_config = SHOP_CONFIG
        self._shop_launch_run = run
        self._shop_launch_mission_pool = tuple(mission_pool)
        self._coop_active_game_token = 'private-game-token-1234567890123456'
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

    def show_shop_failure_result(self, *_args):
        pass

    def refresh_shop_mode(self):
        pass

    def _set_shop_message(self, message, *, error=False):
        self.messages.append((str(message), error))

    def append_log(self, message, error=False):
        self.messages.append((str(message), error))

    def coop_publish_shop_stage(self):
        self.published += 1

    def _scan_coop_victory(self):
        pass

    def is_mission_complete(self, _code):
        return False

    def finish_progression_launch_context(self):
        self._shop_launch_run = None


def check_case(host_revivals):
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
    with TemporaryDirectory() as temporary:
        prior_log = coop_controller.DEBUG_LOG
        coop_controller.DEBUG_LOG = Path(temporary) / 'debug.log'
        coop_controller.DEBUG_LOG.write_text('Game finished without win marker\n')
        try:
            host._poll_coop_game()
        finally:
            coop_controller.DEBUG_LOG = prior_log
    assert host.shop_repository.commits == 1
    message = host._coop_lobby.sent[0]
    assert message['type'] == 'shop_failure'
    assert message['revived'] is bool(host_revivals)
    guest._shop_launch_run = None  # Guest game may close before host game.
    guest._handle_coop_message(guest._coop_lobby, message)
    assert guest.shop_repository.commits == 1
    assert guest._shop_launch_run is None
    assert guest.shop_repository.run.status == host.shop_repository.run.status
    assert guest.shop_repository.run.run_coins == 37
    assert guest.shop_repository.run.run_purchases == base_run_purchases
    assert guest.shop_repository.run.run_buffs == base_run_buffs
    assert guest.shop_repository.profile.meta_coins == 29
    guest._handle_coop_message(guest._coop_lobby, message)
    assert guest.shop_repository.commits == 1
    wrong = dict(message, session_token='stale-game-token')
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
        synced = apply_stage_snapshot(
            guest.shop_repository.run, stage_snapshot(host.shop_repository.run),
            {mission['code']: mission for mission in missions},
        )
        assert synced.mission_offers == host.shop_repository.run.mission_offers
        assert synced.run_coins == 37
    else:
        assert host.published == 0
        assert guest.shop_repository.run.failed_stage == 1


base_run_purchases = (PurchaseRecord('Stryker IFV Access'),)
base_run_buffs = (BuffPurchase('Stryker IFV Armor Plating I'),)


if __name__ == '__main__':
    check_case(0)
    check_case(1)
    print('Co-op Shop failure, private profile, host revival, deduplication: passed')
