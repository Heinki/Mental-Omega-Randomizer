"""Exercise launcher YAML, AP 0.6.7 generation, handshake, and Shop controls.

Run with Archipelago's Python environment and --archipelago-root pointing to
its source checkout. --apworld optionally verifies the distributable archive.
Only world auto-discovery is bypassed; AP options, regions, state and item fill
use the real Archipelago implementation. No game, save, or server is modified.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys
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
from Archipelago.run_manifest import build_run_manifest
from Archipelago.yaml_config import parse_player_yaml, serialize_player_yaml
from Archipelago.client.handshake import ArchipelagoProtocolError, validate_slot_data
from Archipelago.client.session import _scout_location_ids
from randomizer.application.archipelago_controller import ArchipelagoController
from randomizer.application.shop_archipelago_controller import ShopArchipelagoController
from randomizer.application.shop_controller import ShopController
from randomizer.shop.model import RunStatus
from randomizer.rewards.catalogue import REWARD_POOL

WorldType = next(value for value in vars(world_module).values()
                 if isinstance(value, type) and issubclass(value, World)
                 and value is not World)
MISSIONS = build_catalogue_projection()['missions']
REWARD = next(r for r in REWARD_POOL if r.get('kind') == 'buff')


def signed(manifest):
    manifest['manifest_checksum'] = contract.manifest_checksum(manifest)
    return manifest


def fixture(mode):
    missions = MISSIONS[:16] if mode == 'Grid Mode' else MISSIONS
    codes = [m['code'] for m in missions]
    state = {
        'seed': 'AP-REGRESSION', 'campaign_filter': 'All Campaigns',
        'progression_mode': mode, 'mission_order': codes,
        'mission_goal': len(codes), 'starting_unlocked_missions': 3,
        'reward_mode': 'Standard',
        'mission_checks': {m['code']: [
            {'id': check['id'], 'rewards': [REWARD]}
            for check in m['checks']
        ] for m in missions},
    }
    if mode == 'Grid Mode':
        state['grid'] = {
            'nodes': {code: {'x': i % 4, 'y': i // 4}
                      for i, code in enumerate(codes)},
            'final_mission': codes[-1], 'two_start_positions': False,
        }
    return build_run_manifest(state)


def make_world(manifest, ap_seed=12345):
    text = serialize_player_yaml(manifest, "Regression's Slot")
    parsed = parse_player_yaml(text)
    assert parsed['run_manifest']['randomizer_seed'] == 'random'
    assert 'launcher' not in parsed['run_manifest']['frozen_settings']
    assert parsed['run_manifest']['frozen_settings']['launcher_checksum']
    document = yaml.safe_load(text)[WorldType.game]
    expected_settings = deepcopy(manifest['frozen_settings']['launcher'])
    expected_settings.pop('seed', None)
    assert document['launcher_settings'] == expected_settings
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


class IntegrationTests(unittest.TestCase):
    def test_generation_and_handshake(self):
        for mode in ('Classic', 'Mission List', 'Grid Mode', 'Shop Mode'):
            with self.subTest(mode=mode):
                world = make_world(fixture(mode))
                mw = world.multiworld
                self.assertEqual(len(mw.itempool), len(mw.get_unfilled_locations()))
                distribute_items_restrictive(mw)
                self.assertFalse(mw.get_unfilled_locations())
                self.assertTrue(mw.can_beat_game())
                slot = validate_slot_data(json.loads(json.dumps(world.fill_slot_data())))
                ArchipelagoController._validate_archipelago_item_mapping(slot)
                ArchipelagoController._validate_archipelago_server_state(slot)
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

    def test_yaml_preserves_types(self):
        manifest = fixture('Shop Mode')
        values = {'seed': '2026-09-07', 'progression_mode': 'Shop Mode',
                  'generation': {'off': 'Off', 'on': 'on', 'number': '00123',
                                 'null': None, 'float': 1.25, 'empty': {},
                                 'list': ['a,b', 'null', True, 3, 1.5]}}
        manifest['frozen_settings']['launcher'] = values
        signed(manifest)
        text = serialize_player_yaml(manifest, 'Type Test')
        expected = deepcopy(values)
        expected.pop('seed')
        parsed = parse_player_yaml(text)
        self.assertEqual(parsed['launcher_settings'], expected)
        self.assertEqual(parsed['run_manifest']['randomizer_seed'], 'random')
        self.assertNotIn('launcher', parsed['run_manifest']['frozen_settings'])
        self.assertEqual(yaml.safe_load(text)[WorldType.game]['launcher_settings'], expected)
        make_world(manifest)

    def test_player_yaml_is_reusable_across_archipelago_seeds(self):
        manifest = fixture('Grid Mode')
        first = make_world(manifest, ap_seed=12345).run_manifest
        second = make_world(manifest, ap_seed=54321).run_manifest
        self.assertNotEqual(first['randomizer_seed'], manifest['randomizer_seed'])
        self.assertNotEqual(first['randomizer_seed'], second['randomizer_seed'])
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
            manifest = fixture(mode)
            manifest['randomizer_version'] = '0.0-compatible-release'
            signed(manifest)
            validate_slot_data(make_world(manifest).fill_slot_data())

    def test_catalogue_release_metadata_and_legacy_checksums(self):
        from Archipelago.catalogue_contract import (
            projection_checksum, runtime_catalogue_is_compatible,
        )
        projection = build_catalogue_projection()
        if 'world_version' in projection and 'randomizer_version' in projection:
            changed = {**projection, 'world_version': '99.0',
                       'randomizer_version': '99.0'}
            self.assertEqual(projection_checksum(projection), projection_checksum(changed))
        for checksum in getattr(data, 'COMPATIBLE_CATALOGUE_CHECKSUMS', ()):
            manifest = fixture('Shop Mode')
            manifest['catalogue_checksum'] = checksum
            signed(manifest)
            slot = validate_slot_data(make_world(manifest).fill_slot_data())
            self.assertEqual(slot['catalogue_checksum'], checksum)
            self.assertTrue(runtime_catalogue_is_compatible(checksum))

    def test_legacy_defaults_preserve_checksum(self):
        for mode in ('Mission List', 'Shop Mode'):
            manifest = fixture(mode)
            manifest.pop('progression', None)
            manifest.pop('starting_items', None)
            manifest.pop('local_placements', None)
            if mode == 'Shop Mode':
                manifest['shop'].pop('received_unit_loadout', None)
            else:
                manifest.pop('shop', None)
            signed(manifest)
            original = deepcopy(manifest)
            world = make_world(manifest)
            self.assertNotEqual(
                world.run_manifest['randomizer_seed'],
                original['randomizer_seed'],
            )
            slot = validate_slot_data(world.fill_slot_data())
            if mode == 'Shop Mode':
                self.assertEqual(slot['shop']['received_unit_loadout'], 'manual')
            legacy_options = world.options
            legacy_options.generated_world.value = {}
            legacy_options.run_manifest.value = json.dumps(manifest)
            legacy_options.launcher_settings.value = deepcopy(
                manifest['frozen_settings']['launcher']
            )
            world.generate_early()
            self.assertNotEqual(
                world.run_manifest['randomizer_seed'],
                original['randomizer_seed'],
            )

    def test_corruption_and_incompatibility_still_rejected(self):
        manifest = fixture('Shop Mode')
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
        slot = make_world(manifest).fill_slot_data()
        slot['run_manifest'] = deepcopy(slot['run_manifest'])
        slot['run_manifest']['schema_version'] = 999
        signed(slot['run_manifest'])
        slot['manifest_checksum'] = slot['run_manifest']['manifest_checksum']
        with self.assertRaises(ArchipelagoProtocolError):
            validate_slot_data(slot)
        slot = make_world(manifest).fill_slot_data()
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
                     'shop_starting_buff_draft_combo',
                     'shop_discount_specialization_combo', 'shop_difficulty_combo'):
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
