"""Exercise launcher YAML, AP 0.6.7 generation, handshake, and Shop controls.

Run with Archipelago's Python environment and --archipelago-root pointing to
its source checkout. --apworld optionally verifies the distributable archive.
Only world auto-discovery is bypassed; AP options, regions, state and item fill
use the real Archipelago implementation. Co-op uses an isolated loopback AP
protocol server. No game, save, or existing server is modified.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from itertools import product
import importlib
import json
import queue
from pathlib import Path
import sys
import threading
import time
from types import ModuleType, SimpleNamespace
import unittest

parser = argparse.ArgumentParser()
parser.add_argument('--archipelago-root', type=Path, required=True)
parser.add_argument('--apworld', type=Path)
args = parser.parse_args()
ROOT = Path(__file__).resolve().parents[1]
# A staged test script can target a repository without installing it.
if ROOT == Path('/'):
    ROOT = Path.cwd()
sys.path[:0] = [str(ROOT), str(args.archipelago_root)]
worlds = ModuleType('worlds')
worlds.__path__ = [str(args.archipelago_root / 'worlds')]
sys.modules['worlds'] = worlds
module = next(p.name for p in (ROOT / 'Archipelago/APWorld').iterdir()
              if (p / 'world.py').is_file())
sys.path.insert(0, str(args.apworld or ROOT / 'Archipelago/APWorld'))
world_module = importlib.import_module(module + '.world')
contract = importlib.import_module(module + '.manifest')
data = importlib.import_module(module + '.data')
from BaseClasses import CollectionState, MultiWorld
from Fill import distribute_items_restrictive
from worlds.AutoWorld import World
import yaml
from Archipelago.catalogue_contract import build_catalogue_projection
from Archipelago.run_manifest import gameplay_config_snapshot
from Archipelago.yaml_config import parse_player_yaml, serialize_player_yaml
from Archipelago.client.handshake import ArchipelagoProtocolError, validate_slot_data
from Archipelago.client.session import _scout_location_ids
from randomizer.application.archipelago_controller import ArchipelagoController
from randomizer.application.shop_archipelago_controller import ShopArchipelagoController
from randomizer.application.shop_controller import ShopController
from randomizer.shop.model import RunStatus

WorldType = next(value for value in vars(world_module).values()
                 if isinstance(value, type) and issubclass(value, World)
                 and value is not World)


def signed(manifest):
    manifest['manifest_checksum'] = contract.manifest_checksum(manifest)
    return manifest


def fixture(mode):
    return {'progression_mode': mode}


def make_world(settings, ap_seed=12345):
    text = serialize_player_yaml(settings, "Regression's Slot")
    parsed = parse_player_yaml(text)
    assert parsed['run_manifest'] is None
    document = yaml.safe_load(text)[WorldType.game]
    expected_settings = gameplay_config_snapshot(settings)
    expected_settings.pop('seed', None)
    assert document['launcher_settings'] == expected_settings
    assert set(document) == {'launcher_settings'}
    mw = MultiWorld(1)
    mw.set_seed(ap_seed)
    mw.player_name = {1: 'Regression'}
    mw.game[1] = WorldType.game
    world = WorldType(mw, 1)
    mw.worlds[1] = world
    options_type = WorldType.options_dataclass
    world.options = options_type(**{
        name: option.from_any(document.get(name, option.default))
        for name, option in options_type.type_hints.items()
    })
    mw.state = CollectionState(mw)
    world.generate_early()
    world.create_regions()
    world.create_items()
    world.set_rules()
    return world


def make_option_world(values, ap_seed=54321):
    mw = MultiWorld(1)
    mw.set_seed(ap_seed)
    mw.player_name = {1: 'Regression'}
    mw.game[1] = WorldType.game
    world = WorldType(mw, 1)
    mw.worlds[1] = world
    options_type = WorldType.options_dataclass
    world.options = options_type(**{
        name: option.from_any(values.get(name, option.default))
        for name, option in options_type.type_hints.items()
    })
    world.generate_early()
    return world


class Widget:
    def __init__(self, children=()):
        self.children = list(children)
        self.state = 'normal'

    def configure(self, **values):
        self.__dict__.update(values)

    def cget(self, key):
        return getattr(self, key)

    def winfo_children(self):
        return self.children

    def winfo_class(self):
        return 'TButton'


def coop_session_roundtrip(slot):
    """Exercise the real client, item replay, check acknowledgments and goal."""
    from websockets.sync.server import serve
    from websockets.exceptions import ConnectionClosed
    from Archipelago.client import ArchipelagoSession, SessionConfig
    from randomizer.coop.archipelago import shared_run_state, received_rewards
    from randomizer.rewards.catalogue import REWARD_BY_NAME

    item_id = next(int(identifier) for identifier, name in slot['items'].items()
                   if name in REWARD_BY_NAME and not REWARD_BY_NAME[name].get('enemy_reward'))
    location = _scout_location_ids(slot)[0]
    events = queue.Queue()
    checked = threading.Event()
    goal = threading.Event()
    failures = []

    def handler(connection):
        try:
            connection.send(json.dumps([{
                'cmd': 'RoomInfo', 'seed_name': 'COOP-AP-INTEGRATION',
                'games': ['Mental Omega'],
            }]))
            for message in connection:
                for packet in json.loads(message):
                    if packet['cmd'] == 'Connect':
                        assert packet['items_handling'] == 7
                        connection.send(json.dumps([{
                            'cmd': 'Connected', 'team': 0, 'slot': 1,
                            'checked_locations': [], 'missing_locations': [location],
                            'slot_data': slot, 'slot_info': {},
                        }, {
                            'cmd': 'ReceivedItems', 'index': 0,
                            'items': [{'item': item_id, 'location': location, 'player': 1, 'flags': 1}],
                        }, {
                            'cmd': 'ReceivedItems', 'index': 0,
                            'items': [{'item': item_id, 'location': location, 'player': 1, 'flags': 1}],
                        }]))
                    elif packet['cmd'] == 'LocationChecks':
                        assert packet['locations'] == [location]
                        connection.send(json.dumps([{
                            'cmd': 'RoomUpdate', 'checked_locations': [location],
                        }]))
                        checked.set()
                    elif packet['cmd'] == 'StatusUpdate' and packet['status'] == 30:
                        goal.set()
        except ConnectionClosed:
            pass
        except Exception as exc:
            failures.append(exc)

    with serve(handler, '127.0.0.1', 0) as server:
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        session = ArchipelagoSession(
            SessionConfig(server=f'127.0.0.1:{server.socket.getsockname()[1]}', slot_name='Shared Coop'),
            event_callback=events.put,
        )
        controller = ArchipelagoController()
        controller.state = deepcopy(slot['run_manifest']['state_snapshot'])
        controller.state['archipelago'] = {
            'enabled': True, 'activation': 'active', 'received_rewards': [],
            'manifest_checksum': slot['manifest_checksum'],
            'run_manifest': controller._archipelago_manifest_identity(slot['run_manifest']),
            'slot_data': controller._archipelago_slot_identity(slot),
            'slot': 1, 'team': 0,
        }
        controller._archipelago_slot_data = slot
        controller._archipelago_item_names = controller._validate_archipelago_item_mapping(slot)
        controller._archipelago_session = session
        controller._archipelago_session_validated = True
        controller.save_state = lambda: None
        controller.append_archipelago_history = lambda message: None
        controller.earned_rewards_from_checks = lambda: list(controller.archipelago_reward_history())
        controller.is_run_complete = lambda: True
        controller.active_progression_mode = lambda: controller.state['progression_mode']
        try:
            session.start()
            deadline = time.monotonic() + 10
            while not controller.state['archipelago']['received_rewards']:
                event = events.get(timeout=max(0.01, deadline - time.monotonic()))
                if event.kind == 'error':
                    raise AssertionError(event.payload)
                if event.kind == 'received_items':
                    controller.apply_archipelago_received_items(event.payload)
                if time.monotonic() >= deadline:
                    raise AssertionError('Co-op AP item delivery timed out.')
            records = controller.state['archipelago']['received_rewards']
            assert len(records) == 1
            assert not controller.apply_archipelago_received_items(({
                'index': 0, 'item': item_id, 'location': location, 'player': 1, 'flags': 1,
            },))
            assert len(received_rewards(shared_run_state(controller.state, slot))) == 1
            group = {'code': '__COOP__', 'check_id': 'victory', 'event_stem': 'victory',
                     'locations': (location,)}
            assert controller._report_archipelago_location_groups((group,)) == (location,)
            assert not controller._report_archipelago_location_groups((group,))
            assert checked.wait(5)
            controller.report_archipelago_goal_if_complete()
            assert goal.wait(5)
            assert session.checkpoint()['goal_complete']
            guest = ArchipelagoController()
            guest.state = shared_run_state(controller.state, slot)
            assert not guest._report_archipelago_location_groups((group,))
            assert not guest.report_archipelago_goal_if_complete()
            assert not failures, failures
        finally:
            session.stop()
            server.shutdown()
            worker.join(3)


class IntegrationTests(unittest.TestCase):
    def test_clean_build_mission_snapshot(self):
        from Archipelago.mission_catalogue import generation_missions

        missions = generation_missions(ROOT / 'missing-game' / 'INI' / 'BattleClient.ini')
        coops = generation_missions(ROOT / 'missing-game' / 'INI' / 'BattleClient.ini', coop=True)
        self.assertEqual({mission['code'] for mission in missions + coops}, set(data.MISSION_DATA))
        self.assertEqual(len(missions), 97)
        self.assertEqual(len(coops), 36)

    def test_mission_goal_bounds_and_maximum_run(self):
        option = WorldType.options_dataclass.type_hints['mission_goal']
        self.assertEqual(option.range_start, 1)
        self.assertEqual(option.range_end, sum(not code.startswith('COOP_') for code in data.MISSION_DATA))
        self.assertEqual(option.from_any(15).value, 15)
        self.assertEqual(option.from_any(97).value, 97)
        with self.assertRaises(Exception):
            option.from_any(0)
        with self.assertRaises(Exception):
            option.from_any(98)
        world = make_option_world({'mission_goal': 97})
        self.assertEqual(len(world.run_manifest['mission_order']), 97)

    def test_option_creator_fields_generate_a_run(self):
        from Options import (
            Choice, FreeText, NamedRange, OptionCounter, OptionList, OptionSet,
            Range, TextChoice, Toggle, Visibility,
        )

        supported = (
            NamedRange, Range, Toggle, TextChoice, Choice, FreeText,
            OptionSet, OptionList, OptionCounter,
        )
        visible = {
            name: option for name, option in WorldType.options_dataclass.type_hints.items()
            if option.visibility & (Visibility.simple_ui | Visibility.complex_ui)
        }
        self.assertTrue(visible)
        self.assertTrue(all(issubclass(option, supported) for option in visible.values()))
        world = make_option_world({
            'campaign': 'allies',
            'mission_goal': 5,
            'progression_mode': 'grid_mode',
            'difficulty': 'mental',
            'start_with_tier_one_units': True,
        })
        settings = world.run_manifest['frozen_settings']['launcher']
        self.assertEqual(settings['campaign_filter'], 'Allies')
        self.assertEqual(settings['mission_goal'], 5)
        self.assertEqual(settings['progression_mode'], 'Grid Mode')
        self.assertEqual(settings['difficulty'], 'Mental')
        self.assertTrue(settings['generation']['start_with_tier_one_units'])

    def test_generation_and_handshake(self):
        for mode, coop in product(('Classic', 'Mission List', 'Grid Mode', 'Shop Mode'), (False, True)):
            with self.subTest(mode=mode, coop=coop):
                world = make_world(dict(fixture(mode), coop_mode=coop))
                mw = world.multiworld
                self.assertEqual(len(mw.itempool), len(mw.get_unfilled_locations()))
                distribute_items_restrictive(mw)
                self.assertFalse(mw.get_unfilled_locations())
                self.assertTrue(mw.can_beat_game())
                slot = validate_slot_data(json.loads(json.dumps(world.fill_slot_data())))
                ArchipelagoController._validate_archipelago_item_mapping(slot)
                ArchipelagoController._validate_archipelago_server_state(slot)
                self.assertEqual(slot['run_manifest']['state_snapshot']['coop_mode'], coop)
                self.assertTrue(all(code.startswith('COOP_') == coop for code in slot['mission_order']))
                if mode == 'Shop Mode':
                    self.assertTrue(set(slot['shop']['purchase_locations']).issubset(
                        _scout_location_ids(slot)))
                    self.assertEqual(slot['slot_data_version'], 7)
                    self.assertEqual(len(slot['shop']['item_locations']), 120)
                    self.assertEqual(slot['shop']['items_per_victory'], 12)
                    self.assertEqual(sum(
                        slot['run_manifest']['item_pool'].values()
                    ), 120)
                    self.assertEqual(len(slot['shop']['stage_victories']),
                                     slot['shop']['run_length'])
                if coop:
                    coop_session_roundtrip(slot)

    def test_yaml_preserves_types(self):
        values = {'seed': '2026-09-07', 'progression_mode': 'Shop Mode',
                  'generation': {'off': 'Off', 'on': 'on', 'number': '00123',
                                 'null': None, 'float': 1.25, 'empty': {},
                                 'list': ['a,b', 'null', True, 3, 1.5]}}
        text = serialize_player_yaml(values, 'Type Test')
        expected = gameplay_config_snapshot(values)
        expected.pop('seed')
        parsed = parse_player_yaml(text)
        self.assertEqual(parsed['launcher_settings'], expected)
        self.assertIsNone(parsed['run_manifest'])
        self.assertEqual(yaml.safe_load(text)[WorldType.game]['launcher_settings'], expected)
        make_world(values)

    def test_player_yaml_is_reusable_across_archipelago_seeds(self):
        settings = fixture('Grid Mode')
        first = make_world(settings, ap_seed=12345).run_manifest
        repeat = make_world(settings, ap_seed=12345).run_manifest
        second = make_world(settings, ap_seed=54321).run_manifest
        self.assertEqual(first, repeat)
        self.assertNotEqual(first['randomizer_seed'], second['randomizer_seed'])
        self.assertNotEqual(first['grid'], second['grid'])
        for generated in (first, second):
            self.assertEqual(
                generated['state_snapshot']['seed'],
                generated['randomizer_seed'],
            )
            self.assertEqual(
                generated['frozen_settings']['launcher']['seed'],
                generated['randomizer_seed'],
            )
            self.assertEqual(
                generated['manifest_checksum'],
                contract.manifest_checksum(generated),
            )

    def test_release_labels_do_not_break_contract(self):
        for mode in ('Mission List', 'Shop Mode'):
            validate_slot_data(make_world(fixture(mode)).fill_slot_data())

    def test_catalogue_release_metadata_and_legacy_checksums(self):
        from Archipelago.catalogue_contract import (
            projection_checksum, runtime_catalogue_is_compatible,
        )
        projection = build_catalogue_projection()
        if 'world_version' in projection and 'randomizer_version' in projection:
            changed = {**projection, 'world_version': '99.0',
                       'randomizer_version': '99.0'}
            self.assertEqual(projection_checksum(projection), projection_checksum(changed))
        manifest = make_world(fixture('Shop Mode')).run_manifest
        for checksum in getattr(data, 'COMPATIBLE_CATALOGUE_CHECKSUMS', ()):
            manifest = deepcopy(manifest)
            manifest['catalogue_checksum'] = checksum
            signed(manifest)
            self.assertEqual(contract.parse_manifest(manifest)['catalogue_checksum'], checksum)
            self.assertTrue(runtime_catalogue_is_compatible(checksum))

    def test_legacy_defaults_preserve_checksum(self):
        for mode in ('Mission List', 'Shop Mode'):
            manifest = make_world(fixture(mode)).run_manifest
            manifest.pop('progression', None)
            manifest.pop('starting_items', None)
            manifest.pop('local_placements', None)
            if mode == 'Shop Mode':
                manifest['shop'].pop('received_unit_loadout', None)
            else:
                manifest.pop('shop', None)
            signed(manifest)
            original = deepcopy(manifest)
            parsed = contract.parse_manifest(manifest)
            if mode == 'Shop Mode':
                self.assertEqual(parsed['shop'].get('received_unit_loadout', 'manual'), 'manual')
            world = make_world(fixture(mode))
            legacy_options = world.options
            legacy_options.generated_world.value = {}
            legacy_options.run_manifest.value = json.dumps(manifest)
            legacy_options.launcher_settings.value = {}
            world.generate_early()
            self.assertNotEqual(
                world.run_manifest['randomizer_seed'],
                original['randomizer_seed'],
            )

    def test_corruption_and_incompatibility_still_rejected(self):
        manifest = make_world(fixture('Shop Mode')).run_manifest
        for field, value, resign in (
            ('randomizer_seed', 'tampered', False),
            ('schema_version', 999, True),
            ('catalogue_checksum', '0' * 64, True),
            ('randomizer_version', '', True),
        ):
            with self.subTest(field=field):
                changed = deepcopy(manifest)
                changed[field] = value
                if resign:
                    signed(changed)
                with self.assertRaises(contract.ManifestError):
                    contract.parse_manifest(changed)
        slot = make_world(fixture('Shop Mode')).fill_slot_data()
        slot['run_manifest'] = deepcopy(slot['run_manifest'])
        slot['run_manifest']['schema_version'] = 999
        signed(slot['run_manifest'])
        slot['manifest_checksum'] = slot['run_manifest']['manifest_checksum']
        with self.assertRaises(ArchipelagoProtocolError):
            validate_slot_data(slot)
        slot = make_world(fixture('Shop Mode')).fill_slot_data()
        slot['run_manifest'] = deepcopy(slot['run_manifest'])
        slot['run_manifest']['randomizer_seed'] = 'tampered'
        with self.assertRaises(ArchipelagoProtocolError):
            validate_slot_data(slot)

    def test_shop_controls_during_connection_and_restart(self):
        class Controller(ShopController, ArchipelagoController):
            pass
        controller = Controller()
        controller._archipelago_gameplay_locked = True
        controller.shop_run = None
        for name in ('shop_progression_mode_combo', 'shop_seed_entry',
                     'shop_setup_start_button', 'shop_faction_pool_combo',
                     'shop_discount_specialization_combo', 'shop_difficulty_combo',
                     'shop_coop_mode_check', 'shop_coop_player_count_combo'):
            setattr(controller, name, Widget())
        controller.appearance_frame = Widget()
        controller.settings_frame = Widget([controller.shop_setup_start_button,
                                             controller.shop_seed_entry])
        controller.advanced_tab = Widget()
        for name in ('archipelago_save_yaml_button', 'archipelago_server_entry',
                     'archipelago_port_entry', 'archipelago_slot_entry',
                     'archipelago_password_entry'):
            setattr(controller, name, Widget())
        controller.initialize_archipelago_control_registry()
        self.assertNotIn(controller.shop_setup_start_button,
                         controller._archipelago_gameplay_widgets)
        for validated, status, expected in (
            (False, None, 'disabled'), (True, None, 'normal'),
            (True, RunStatus.ACTIVE, 'disabled'),
            (True, RunStatus.FAILED, 'normal'),
            (True, RunStatus.COMPLETED, 'normal'),
        ):
            with self.subTest(validated=validated, status=status):
                controller.shop_archipelago_game_active = lambda: validated
                controller.shop_run = SimpleNamespace(status=status) if status else None
                controller._enforce_archipelago_control_lock()
                self.assertEqual(controller.shop_setup_start_button.state, expected)
                self.assertEqual(controller.shop_seed_entry.state, 'disabled')

    def test_shop_stage_markers_and_purchase_locations(self):
        slot = validate_slot_data(make_world(fixture('Shop Mode')).fill_slot_data())
        class Controller(ShopArchipelagoController, ArchipelagoController):
            pass
        controller = Controller()
        controller.archipelago_shop_slot_settings = lambda: slot['shop']
        controller._cache_archipelago_location_mappings(slot)
        for location in slot['shop']['purchase_locations']:
            self.assertIn(location, controller._archipelago_allowed_locations)
        for entry in slot['shop']['stage_victories']:
            group = controller._archipelago_shop_stage_group(entry['stage'])
            self.assertIn(entry['logic_location'], group['locations'])
            self.assertIn(entry['logic_location'], controller._archipelago_allowed_locations)
            if entry['location'] is not None:
                self.assertIn(entry['location'], group['locations'])
        acknowledged = []
        controller._archipelago_slot_data = slot
        controller._archipelago_session_validated = True
        ap_state = {'received_rewards': []}
        controller._active_archipelago_state = lambda: ap_state
        controller._archipelago_session = SimpleNamespace(
            acknowledge_received=lambda indexes: acknowledged.extend(indexes) or True,
            checkpoint=lambda: {'format': 2},
        )
        controller.save_state = lambda: None
        controller.append_archipelago_history = lambda message: self.fail(message)
        receipts = [{'index': index, 'item': entry['logic_item']}
                    for index, entry in enumerate(slot['shop']['stage_victories'])]
        self.assertEqual(controller.apply_archipelago_received_items(receipts), ())
        self.assertEqual(acknowledged, list(range(len(receipts))))
        self.assertEqual(ap_state['received_rewards'], [])

    def test_shop_goal_belongs_to_current_slot(self):
        controller = ShopArchipelagoController()
        controller.archipelago_progression_mode = lambda: 'Shop Mode'
        controller.archipelago_shop_context = lambda: ('current-room', ())
        for identity, status, expected in (
            ('', RunStatus.COMPLETED, False),
            ('other-room', RunStatus.COMPLETED, False),
            ('current-room', RunStatus.ACTIVE, False),
            ('current-room', RunStatus.COMPLETED, True),
        ):
            controller.shop_repository = SimpleNamespace(load_run=lambda:
                SimpleNamespace(ap_identity=identity, status=status))
            self.assertEqual(controller.is_run_complete(), expected)


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]], verbosity=2)
