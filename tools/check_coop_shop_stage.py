"""Check host Shop stage sync without touching guest economy or purchases."""

from dataclasses import replace
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from randomizer.coop.catalogue import discover_coop_missions
from randomizer.coop.shop_stage import apply_stage_snapshot, stage_digest, stage_snapshot
from randomizer.application.coop_controller import CoopController
from randomizer.application.shop_controller import ShopController
from randomizer.core.paths import GAME_ROOT
from randomizer.shop.model import (
    BuffPurchase, MissionEconomyClass, MissionOffer, PurchaseRecord,
    RunStatus, ShopRun,
)


def rejected(run, snapshot, missions):
    try:
        apply_stage_snapshot(run, snapshot, missions)
    except ValueError:
        return
    raise AssertionError('Invalid Shop stage was accepted.')


def main():
    missions = {item['code']: item for item in discover_coop_missions(GAME_ROOT)}
    codes = sorted(missions)[:4]
    offers = tuple(MissionOffer(code, MissionEconomyClass.ACT_1) for code in codes[:3])
    host = ShopRun(
        run_id='host', seed='STAGE-TEST', status=RunStatus.ACTIVE,
        stage=1, run_length=10, run_coins=100, mission_offers=offers,
        starting_unit_ids=('FV',),
    )
    guest = ShopRun(
        run_id='guest', seed='STAGE-TEST', status=RunStatus.ACTIVE,
        stage=1, run_length=10, run_coins=37,
        mission_offers=tuple(reversed(offers)),
        starting_unit_ids=('HTNK',),
        run_purchases=(PurchaseRecord('Stryker IFV Access'),),
        run_buffs=(BuffPurchase('Stryker IFV Armor Plating I'),),
    )
    snapshot = stage_snapshot(host)
    assert len(stage_digest(snapshot)) == 64
    synced = apply_stage_snapshot(guest, snapshot, missions)
    assert synced.mission_offers == host.mission_offers
    assert synced.run_coins == 37
    assert synced.run_purchases == guest.run_purchases
    assert synced.run_buffs == guest.run_buffs
    assert synced.starting_unit_ids == guest.starting_unit_ids
    assert synced.run_id == 'guest'
    controller_receive_case(guest, snapshot, missions)

    rerolled = replace(
        host, mission_offers=(offers[0], offers[1],
                              MissionOffer(codes[3], MissionEconomyClass.ACT_1)),
        rerolls_used=1,
    )
    synced = apply_stage_snapshot(synced, stage_snapshot(rerolled), missions)
    assert synced.rerolls_used == 1
    selected = replace(rerolled, selected_mission_code=codes[1])
    synced = apply_stage_snapshot(synced, stage_snapshot(selected), missions)
    assert synced.selected_mission_code == codes[1]
    assisted = replace(selected, assisted_mission_code=codes[1],
                       difficulty_assists_used=1)
    synced = apply_stage_snapshot(synced, stage_snapshot(assisted), missions)
    assert synced.assisted_mission_code == codes[1]
    assert synced.difficulty_assists_used == 1
    committed = replace(assisted, mission_committed=True)
    synced = apply_stage_snapshot(synced, stage_snapshot(committed), missions)
    assert synced.mission_committed
    assert apply_stage_snapshot(synced, stage_snapshot(committed), missions) == synced

    changed = dict(stage_snapshot(committed), selected_mission_code=codes[0])
    rejected(synced, changed, missions)
    changed = dict(stage_snapshot(committed), mission_committed=False)
    rejected(synced, changed, missions)
    changed = dict(stage_snapshot(committed), seed='OTHER')
    rejected(synced, changed, missions)
    changed = dict(stage_snapshot(committed), stage=True)
    rejected(synced, changed, missions)
    changed = dict(stage_snapshot(committed), rerolls_used=2)
    rejected(synced, changed, missions)
    changed = dict(stage_snapshot(committed), offers=[
        {'mission_code': 'NOT_COOP', 'class': 'act_1'},
    ])
    rejected(synced, changed, missions)
    controller_flow(host, codes[0])
    print('Shop offers, reroll, selection, commitment, guest economy isolation: passed')


def controller_flow(run, code):
    class Repository:
        current = run

        def load(self):
            return None, self.current

        def load_run(self):
            return self.current

    class Service:
        def __init__(self, repository):
            self.repository = repository

        def select_mission(self, selected):
            self.repository.current = replace(
                self.repository.current, selected_mission_code=selected,
            )
            return self.repository.current

        def commit_mission(self, selected):
            assert self.repository.current.selected_mission_code == selected
            self.repository.current = replace(
                self.repository.current, mission_committed=True,
            )
            return self.repository.current

    class Controller:
        def __init__(self):
            self.shop_repository = Repository()
            self.shop_service = Service(self.shop_repository)
            self.shop_mission_cards = [{'code': code}]
            self._coop_lobby = type('Lobby', (), {'connected': True})()
            self._coop_shop_ready = False
            self._shop_launch_run = None
            self._coop_busy = False
            self.active_game_process = None
            self.published = 0
            self.launched = []
            self.messages = []

        def coop_guest_connected(self):
            return False

        def coop_publish_shop_stage(self):
            self.published += 1
            self._coop_shop_ready = False

        def _set_shop_message(self, message, *, error=False):
            self.messages.append((str(message), error))

        def refresh_shop_mode(self):
            pass

        def shop_launch_active(self):
            return self._shop_launch_run is not None

        def _shop_mission(self, selected):
            return {'coop_name': selected.lower()}

        def _shop_run_mission_pool(self, current):
            return ()

        def _start_coop_game(self, role, selected):
            self.launched.append((role, selected))

    controller = Controller()
    ShopController._advance_coop_shop_mission(controller, 0)
    assert controller.shop_repository.current.selected_mission_code == code
    assert controller.published == 1
    ShopController._advance_coop_shop_mission(controller, 0)
    assert not controller.shop_repository.current.mission_committed
    controller._coop_shop_ready = True
    ShopController._advance_coop_shop_mission(controller, 0)
    assert controller.shop_repository.current.mission_committed
    assert controller.published == 2
    controller._coop_shop_ready = True
    ShopController._advance_coop_shop_mission(controller, 0)
    assert controller.launched == [('host', code)]


def controller_receive_case(run, snapshot, missions):
    class Repository:
        current = run

        def load_run(self):
            return self.current

        def save_run(self, updated):
            self.current = updated

    class Fake:
        def __init__(self):
            self.coop_mode_var = type('Variable', (), {'get': lambda _self: True})()
            self.shop_repository = Repository()
            self.messages = []
            self._coop_shop_stage_digest = stage_digest(snapshot)
            self._coop_shop_ready = False

        def shop_mode_selected(self):
            return True

        def mission_lookup(self):
            return missions

        def refresh_shop_mode(self):
            pass

        def append_log(self, message):
            self.messages.append(message)

        _record_coop_log = append_log

    guest = Fake()
    guest_lobby = type('Lobby', (), {
        'role': 'guest', 'sent': [],
        'send': lambda self, message: self.sent.append(message),
    })()
    CoopController._handle_coop_message(
        guest, guest_lobby, {'type': 'shop_stage', 'data': snapshot},
    )
    assert guest_lobby.sent == [
        {'type': 'shop_ready', 'digest': stage_digest(snapshot)}
    ]
    assert guest.shop_repository.current.run_coins == run.run_coins
    host = Fake()
    host_lobby = type('Lobby', (), {'role': 'host'})()
    CoopController._handle_coop_message(host, host_lobby, guest_lobby.sent[0])
    assert host._coop_shop_ready


if __name__ == '__main__':
    main()
