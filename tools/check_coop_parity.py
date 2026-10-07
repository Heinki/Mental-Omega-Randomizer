"""Check co-op map reward isolation before a two-computer playtest."""

from pathlib import Path
from dataclasses import replace
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from randomizer.coop.catalogue import discover_coop_missions
from randomizer.coop.archipelago import shared_run_state, shared_shop_inventory
from randomizer.coop.lobby import encode_state, decode_state
from randomizer.coop.prototype import (
    build_manifest, build_shop_manifest, rebuild_from_manifest,
    shop_unit_loadout,
)
from randomizer.core.paths import GAME_ROOT
from randomizer.maps.ini import section_value_map_preserve
from randomizer.maps.ini import all_section_value_maps_preserve, parse_action_groups
from randomizer.maps.production import PLAYER_ORIGINAL_PRODUCTION_GATE_ID
from randomizer.missions.catalogue import filter_missions_by_build_settings
from randomizer.missions.access import TIER_ONE_ROLE_MARKERS, TIER_ONE_DEFENSE_MARKER
from randomizer.rewards.catalogue import REWARD_POOL, REWARD_BY_BUFF_KEY
from randomizer.shop.model import (
    MissionEconomyClass, MissionOffer, PurchaseRecord, RunStatus,
    ShopProfile, ShopRun,
)


def section(data, name):
    return section_value_map_preserve(data.decode('latin-1').splitlines(), name)


def reward(name):
    return next(item for item in REWARD_POOL if item['name'] == name)


def check_standard_access():
    missions = discover_coop_missions(GAME_ROOT)
    classifications = {
        kind: {item['code'] for item in missions if item['build_classification'] == kind}
        for kind in ('base_build', 'true_no_build', 'no_build_production')
    }
    assert {kind: len(codes) for kind, codes in classifications.items()} == {
        'base_build': 23, 'true_no_build': 10, 'no_build_production': 3,
    }
    assert classifications['no_build_production'] == {
        'COOP_ABALANCE', 'COOP_ABUGGY', 'COOP_AMONSTER',
    }
    build_only = filter_missions_by_build_settings(missions, False, False)
    assert {item['code'] for item in build_only} == classifications['base_build']
    for true_no_build in (False, True):
        for limited_production in (False, True):
            selected = filter_missions_by_build_settings(
                missions, true_no_build, limited_production,
            )
            expected = (classifications['base_build']
                        | (classifications['true_no_build'] if true_no_build else set())
                        | (classifications['no_build_production'] if limited_production else set()))
            assert {item['code'] for item in selected} == expected
    state = {
        'seed': 'COOP-STANDARD-LOCKS', 'progression_mode': 'Grid Mode',
        'reward_mode': 'Standard', 'starting_rewards': [
            reward('Terror Drone Access'), reward('Stryker IFV Access'),
            reward('Super Thor Gunship Access'),
        ],
    }
    for mission in missions:
        manifest, data = build_manifest(GAME_ROOT, state, mission['coop_name'])
        assert section(data, 'MORPDRON')['Prerequisite'] == 'NAWEAP'
        assert section(data, 'MORPFV')['Prerequisite'] == 'GAWEAP'
        assert section(data, 'MORPSTHOR')['Prerequisite'] == 'GAWEAP'
        assert not section(data, 'MORPGGI')
        for source in ('DRON', 'FV', 'HTNK', 'E1', 'GGI', 'ENFO', 'HCRUIS'):
            assert PLAYER_ORIGINAL_PRODUCTION_GATE_ID in section(
                data, source,
            )['Prerequisite.Negative'].split(',')
        structures = section(data, 'Structures')
        tags = section(data, 'Tags')
        actions = section(data, 'Actions')
        slots = []
        for value in structures.values():
            tokens = value.split(',')
            if tokens[1] != PLAYER_ORIGINAL_PRODUCTION_GATE_ID:
                continue
            assert tokens[0] == 'Neutral'
            trigger = tags[tokens[6]].split(',')[-1]
            slots.append(actions[trigger].split(',')[3])
        assert sorted(slots) == ['4475', '4476']
        carrier = section(data, 'MORPSTHOR')
        payloads = carrier['InitialPayload.Types'].split(',')
        assert carrier['InitialPayload.Nums'] == '5,5,1'
        assert carrier['Passengers.Allowed'].split(',') == payloads
        assert carrier['OpenTopped'] == 'yes'
        assert len(set(payloads)) == 3
        for payload in payloads:
            values = section(data, payload)
            assert values['TechLevel'] == '-1'
            assert values['RequiredHouses'] == manifest['player_country']
            assert not values.get('Prerequisite.Negative')
            assert not values.get('BuildLimit')
            assert values['Primary']
            assert payload in (
                list(section(data, 'InfantryTypes').values())
                + list(section(data, 'VehicleTypes').values())
            )
        original = all_section_value_maps_preserve(
            (GAME_ROOT / 'MapsMO' / 'Cooperative' / mission['scenario'])
            .read_bytes().decode('latin-1').splitlines()
        )
        for name in ('Units', 'Infantry', 'TeamTypes', 'TaskForces', 'ScriptTypes', 'AITriggerTypes'):
            generated = section(data, name)
            assert all(generated.get(key) == value
                       for key, value in original.get(name, {}).items()), (mission['code'], name)
            if name in {'TeamTypes', 'TaskForces', 'ScriptTypes'}:
                for reference in original.get(name, {}).values():
                    assert section(data, reference) == original[reference]
        for value in actions.values():
            _count, groups = parse_action_groups(value)
            assert len(value.encode('utf-8')) <= 511
            assert all(len(group) == 8 for group in groups)
        assert rebuild_from_manifest(GAME_ROOT, manifest) == data
    chaos, chaos_data = build_manifest(
        GAME_ROOT, dict(state, reward_mode='Chaos'), 'coop_sthunder',
    )
    standard, _ = build_manifest(GAME_ROOT, state, 'coop_sthunder')
    assert chaos['map_file'] != standard['map_file']
    assert section(chaos_data, 'MORPFV')['Prerequisite'] == 'NAWEAP'
    tampered = dict(standard, reward_mode='Chaos')
    try:
        rebuild_from_manifest(GAME_ROOT, tampered)
    except ValueError:
        pass
    else:
        raise AssertionError('Reward mode tampering reused the Standard manifest.')
    starters = dict(state, starting_rewards=[], starting_unit_ids=[
        TIER_ONE_ROLE_MARKERS['ground_vehicle'],
    ], starting_defense_ids=[TIER_ONE_DEFENSE_MARKER])
    starter_manifest, starter_map = build_manifest(GAME_ROOT, starters, 'coop_sthunder')
    assert not starter_manifest['test_override']
    assert 'FV' not in starter_manifest['access_ids']
    assert section(starter_map, 'MORPHTNK')['Prerequisite'] == 'NAWEAP'
    assert starter_manifest['building_ids']
    empty, empty_map = build_manifest(
        GAME_ROOT, dict(state, starting_rewards=[]), 'coop_apanzer',
    )
    assert not empty['unit_id'] and not empty['access_ids'] and not empty['test_override']
    assert not section(empty_map, 'MORPFV')
    assert rebuild_from_manifest(GAME_ROOT, empty) == empty_map
    thor_loadout = {
        'access_ids': ['STHOR'], 'buff_counts': {},
        'production_restrictions': ['vehicles'],
    }
    private, private_map = build_shop_manifest(
        GAME_ROOT, 'COOP-PRIVATE-PAYLOADS', 'coop_sthunder',
        thor_loadout, dict(thor_loadout, production_restrictions=[]),
    )
    host_payloads = section(private_map, 'MORHSTHOR')['InitialPayload.Types'].split(',')
    guest_payloads = section(private_map, 'MORGSTHOR')['InitialPayload.Types'].split(',')
    assert set(host_payloads).isdisjoint(guest_payloads)
    assert section(private_map, 'MORHSTHOR')['TechLevel'] == '-1'
    assert section(private_map, 'MORGSTHOR')['TechLevel'] == '1'
    for payloads, country in (
        (host_payloads, private['player_country']),
        (guest_payloads, private['guest_country']),
    ):
        for payload in payloads:
            values = section(private_map, payload)
            assert values['TechLevel'] == '-1'
            assert values['RequiredHouses'] == country
            assert not values.get('BuildLimit')
            assert not any(key.lower().startswith('prerequisite') and value
                           for key, value in values.items())
    assert rebuild_from_manifest(GAME_ROOT, private) == private_map
    print('Co-op classifications, Standard/Chaos locks, starter access, payloads, native scripts: passed', flush=True)


def check_archipelago_inventory():
    health = REWARD_BY_BUFF_KEY[('FV', 'health')]['name']
    records = [
        {'index': index, 'reward_name': name}
        for index, name in enumerate((
            'Stryker IFV Access', health, health, 'Terror Drone Access',
            'Lightning Storm Power', 'AI Infantry Armor',
        ))
    ]
    state = {
        'seed': 'COOP-AP-REWARDS', 'coop_mode': True,
        'reward_mode': 'Standard', 'progression_mode': 'Grid Mode',
        'starting_rewards': [reward('Super Thor Gunship Access')],
        'mission_order': ['COOP_STHUNDER'],
        'mission_checks': {'COOP_STHUNDER': [{
            'id': 'victory', 'unlocked': True,
            'rewards': [reward('Rhino Heavy Tank Access')],
        }]},
        'reward_settings': {'enemy_scaling': {'maximum_total_buffs': 1}},
        'archipelago': {
            'enabled': True, 'activation': 'active', 'received_rewards': records + [records[1]],
            'manifest_checksum': 'c' * 64, 'run_manifest': {'progression_mode': 'Grid Mode'},
            'slot_data': {}, 'team': 0, 'slot': 1, 'server': 'private-server',
            'standalone_config': {'archipelago': {'password': 'private-password'}},
            'checkpoint': {'seed_name': 'Coop Room', 'client_uuid': 'private-uuid'},
        },
    }
    shared = decode_state(encode_state(shared_run_state(state)))
    assert shared['archipelago']['checkpoint'] == {'seed_name': 'Coop Room'}
    assert 'server' not in shared['archipelago']
    assert 'standalone_config' not in shared['archipelago']
    for mission in discover_coop_missions(GAME_ROOT):
        manifest, data = build_manifest(GAME_ROOT, state, mission['coop_name'])
        assert manifest['access_ids'] == ['DRON', 'FV']
        assert manifest['buff_counts']['FV']['health'] == 2
        assert manifest['power_reward_ids'] == ['Lightning Storm Power']
        assert manifest['enemy_reward_ids'] == ['AI Infantry Armor']
        peer_manifest, peer_data = build_manifest(GAME_ROOT, shared, mission['coop_name'])
        assert peer_manifest == manifest and peer_data == data
        assert rebuild_from_manifest(GAME_ROOT, manifest) == data
    guest = ShopRun(
        run_id='private-guest', seed=state['seed'], status=RunStatus.ACTIVE,
        stage=1, run_length=10, run_coins=37, starting_unit_ids=('HTNK',),
        eligible_mission_codes=('COOP_STHUNDER',),
        run_purchases=(PurchaseRecord('Super Thor Gunship Access'),),
    )
    bound = shared_shop_inventory(guest, shared)
    assert bound.ap_identity
    assert bound.run_coins == guest.run_coins and bound.run_purchases == guest.run_purchases
    assert bound.starting_unit_ids == guest.starting_unit_ids
    assert shared_shop_inventory(bound, shared) == bound
    loadout = shop_unit_loadout(bound, state=shared)
    assert {'DRON', 'FV', 'HTNK', 'STHOR'} <= set(loadout['access_ids'])
    assert loadout['buff_counts']['FV']['health'] == 2
    assert loadout['enemy_reward_ids'] == ['AI Infantry Armor']
    shop_manifest, shop_map = build_shop_manifest(
        GAME_ROOT, state['seed'], 'coop_sthunder', loadout, loadout,
    )
    assert shop_manifest['enemy_reward_ids'] == ['AI Infantry Armor']
    assert rebuild_from_manifest(GAME_ROOT, shop_manifest) == shop_map
    assert shared_shop_inventory(replace(guest, seed='OTHER'), shared) == replace(guest, seed='OTHER')
    print('AP shared ledger, replay, received-only access/buffs/powers/traps on 36 maps, Shop private economy: passed', flush=True)


def main():
    check_standard_access()
    check_archipelago_inventory()
    state = {
        'seed': 'COOP-PARITY-GRID', 'progression_mode': 'Grid Mode',
        'reward_mode': 'Chaos', 'coop_mode': True,
        'starting_rewards': [
            reward('Soviet Cloning Vats Access'),
            reward('Lightning Storm Power'),
        ],
        'mission_order': ['COOP_STHUNDER'],
        'mission_checks': {
            'COOP_STHUNDER': [{'id': 'victory', 'unlocked': True}],
        },
        'reward_settings': {'enemy_scaling': {'maximum_total_buffs': 1}},
        'enemy_reward_plan': [{
            'mission': 'COOP_STHUNDER', 'check_id': 'victory',
            'reward': reward('AI Infantry Armor'),
        }],
    }
    grid_manifest, grid_map = build_manifest(
        GAME_ROOT, state, 'coop_sthunder', unit_id='FV', allow_test_unit=True,
    )
    assert grid_manifest['building_ids'] == ['NACLONS']
    assert grid_manifest['power_reward_ids'] == ['Lightning Storm Power']
    assert grid_manifest['enemy_reward_ids'] == ['AI Infantry Armor']
    assert section(grid_map, 'MORPNACLONS')['RequiredHouses'] == 'USSR'
    assert 'MORPNACLONS' in section(grid_map, 'BuildingTypes').values()
    assert section(grid_map, 'Europeans')['ArmorInfantryMult'] != (
        section((GAME_ROOT / 'MapsMO' / 'Cooperative' / 'coop_sthunder.map').read_bytes(),
                'Europeans').get('ArmorInfantryMult')
    )
    assert rebuild_from_manifest(GAME_ROOT, grid_manifest) == grid_map

    host = {
        'access_ids': ['FV'], 'buff_counts': {},
        'building_ids': ['NACLONS'],
        'power_reward_ids': ['Lightning Storm Power'],
        'starting_credit_bonus': 2000,
        'production_restrictions': ['vehicles'],
        'enemy_reward_ids': ['AI Infantry Armor', 'AI T1 Unit Health'],
    }
    guest = {
        'access_ids': ['HTNK'], 'buff_counts': {},
        'power_reward_ids': ['Lightning Storm Power'],
        'starting_credit_bonus': -3000,
    }
    manifest, data = build_shop_manifest(
        GAME_ROOT, 'COOP-PARITY-SHOP', 'coop_sthunder', host, guest,
    )
    assert section(data, 'MORHFV')['TechLevel'] == '-1'
    assert section(data, 'MORGHTNK')['TechLevel'] == '1'
    assert section(data, 'MORHNACLONS')['RequiredHouses'] == 'USSR'
    assert not section(data, 'MORGNACLONS')
    assert 'USSR' in section(data, 'NAWEAP')['ForbiddenHouses']
    assert 'Latin' not in section(data, 'NAWEAP')['ForbiddenHouses']
    assert section(data, 'MORHCASH')['ProduceCashStartup'] == '2000'
    assert section(data, 'MORGCASH')['ProduceCashStartup'] == '-3000'
    actions = section(data, 'Actions').values()
    assert any('MORHCASH' in value for value in actions)
    assert any('MORGCASH' in value for value in actions)
    powers = [
        section(data, power_id)
        for power_id in section(data, 'SuperWeaponTypes').values()
    ]
    assert any(item.get('SW.RequiredHouses') == 'USSR' for item in powers)
    assert any(item.get('SW.RequiredHouses') == 'Latin' for item in powers)
    assert section(data, 'Europeans')['ArmorInfantryMult']
    assert rebuild_from_manifest(GAME_ROOT, manifest) == data

    hostile = dict(host, enemy_reward_ids=[
        'AI Allied Lightning Storm', 'AI T1 Unit Health',
    ])
    _, hostile_map = build_shop_manifest(
        GAME_ROOT, 'COOP-PARITY-AI', 'coop_sthunder', hostile, guest,
    )
    assert section(hostile_map, 'E1')['Strength'] != section(
        (GAME_ROOT / 'MapsMO' / 'Cooperative' / 'coop_sthunder.map').read_bytes(),
        'E1',
    ).get('Strength')
    assert section(hostile_map, 'LightningStormSpecial')['SW.AllowAI'] == 'yes'
    assert any(',34,' in value for value in section(hostile_map, 'Actions').values())

    run = ShopRun(
        run_id='host', seed='COOP-PARITY-SHOP', status=RunStatus.ACTIVE,
        stage=1, run_length=10, run_coins=0, starting_unit_ids=('FV',),
        run_purchases=(PurchaseRecord('Soviet Cloning Vats Access'),
                       PurchaseRecord('Lightning Storm Power')),
        modifiers=('veteran_economy',),
        mission_offers=(MissionOffer('COOP_STHUNDER', MissionEconomyClass.ACT_1),),
        selected_mission_code='COOP_STHUNDER',
    )
    profile = ShopProfile(permanent_upgrades={'mission_starting_credits': 2})
    loadout = shop_unit_loadout(run, profile)
    assert loadout['building_ids'] == ['NACLONS']
    assert loadout['power_reward_ids'] == ['Lightning Storm Power']
    assert loadout['starting_credit_bonus'] == 4000

    for mission in discover_coop_missions(GAME_ROOT):
        _, per_map = build_shop_manifest(
            GAME_ROOT, 'COOP-PARITY-SHOP', mission['coop_name'], host, guest,
        )
        assert section(per_map, 'MORHCASH')['ProduceCashStartup'] == '2000'
        assert section(per_map, 'MORGCASH')['ProduceCashStartup'] == '-3000'
    print('Co-op Grid/Shop buildings, powers, private credits, enemy buffs/powers, factory bans: passed')


if __name__ == '__main__':
    main()
