"""Check co-op map reward isolation before a two-computer playtest."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from randomizer.coop.catalogue import discover_coop_missions
from randomizer.coop.prototype import (
    build_manifest, build_shop_manifest, rebuild_from_manifest,
    shop_unit_loadout,
)
from randomizer.core.paths import GAME_ROOT
from randomizer.maps.ini import section_value_map_preserve
from randomizer.rewards.catalogue import REWARD_POOL
from randomizer.shop.model import (
    MissionEconomyClass, MissionOffer, PurchaseRecord, RunStatus,
    ShopProfile, ShopRun,
)


def section(data, name):
    return section_value_map_preserve(data.decode('latin-1').splitlines(), name)


def reward(name):
    return next(item for item in REWARD_POOL if item['name'] == name)


def main():
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
