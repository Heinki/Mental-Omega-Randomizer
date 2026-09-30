"""Check private Shop clones and unchanged shared Grid clones."""

from dataclasses import replace
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from randomizer.coop.catalogue import discover_coop_missions
from randomizer.coop.direct import _spawn_data
from randomizer.coop.prototype import (
    SIDE_COUNTRIES, build_manifest, build_shop_manifest, install,
    rebuild_from_manifest, remove, shop_unit_loadout,
)
from randomizer.core.paths import GAME_ROOT
from randomizer.maps.ini import section_value_map_preserve
from randomizer.rewards.catalogue import REWARD_POOL
from randomizer.shop.modifiers import stage_production_restrictions
from randomizer.shop.model import BuffPurchase, PurchaseRecord, RunStatus, ShopRun


def section(data, name):
    return section_value_map_preserve(data.decode('latin-1').splitlines(), name)


def main():
    health_reward = next(
        item['name'] for item in REWARD_POOL
        if item.get('unit') == 'FV' and item.get('buff_type') == 'health'
    )
    damage_reward = next(
        item['name'] for item in REWARD_POOL
        if item.get('unit') == 'FV' and item.get('buff_type') == 'damage'
    )
    host_run = ShopRun(
        run_id='host', seed='COOP-SHOP-TEST', status=RunStatus.ACTIVE,
        stage=1, run_length=10, run_coins=0, starting_unit_ids=('FV',),
        run_buffs=(BuffPurchase(health_reward, 2),),
    )
    guest_run = ShopRun(
        run_id='guest', seed='COOP-SHOP-TEST', status=RunStatus.ACTIVE,
        stage=1, run_length=10, run_coins=0, starting_unit_ids=('HTNK',),
        run_purchases=(PurchaseRecord('Stryker IFV Access'),),
        run_buffs=(BuffPurchase(damage_reward),),
    )
    host = shop_unit_loadout(host_run)
    guest = shop_unit_loadout(guest_run)
    assert host == {'access_ids': ['FV'], 'buff_counts': {'FV': {'health': 2}}}
    assert guest['access_ids'] == ['FV', 'HTNK']
    assert guest['buff_counts'] == {'FV': {'damage': 1}}
    restricted_run = replace(host_run, modifiers=('you_shall_not_build',))
    assert shop_unit_loadout(restricted_run)['production_restrictions'] == sorted(
        stage_production_restrictions(restricted_run)
    )

    missions = discover_coop_missions(GAME_ROOT)
    assert len(missions) == 36
    for mission in missions:
        manifest, data = build_shop_manifest(
            GAME_ROOT, 'COOP-SHOP-TEST', mission['coop_name'], host, guest,
        )
        assert manifest['schema'] == 5
        assert manifest['player_country'] != manifest['guest_country']
        assert rebuild_from_manifest(GAME_ROOT, manifest) == data
        host_clone = section(data, 'MORHFV')
        guest_clone = section(data, 'MORGFV')
        guest_tank = section(data, 'MORGHTNK')
        assert host_clone['Owner'] == manifest['player_country']
        assert host_clone['RequiredHouses'] == manifest['player_country']
        assert guest_clone['Owner'] == manifest['guest_country']
        assert guest_clone['RequiredHouses'] == manifest['guest_country']
        assert guest_tank['Owner'] == manifest['guest_country']
        assert int(host_clone['Strength']) > int(guest_clone['Strength'])
        assert host_clone['Primary'] != guest_clone['Primary']
        assert not section(data, 'MORHHTNK')
        vehicles = set(section(data, 'VehicleTypes').values())
        assert {'MORHFV', 'MORGFV', 'MORGHTNK'} <= vehicles
        weapons = set(section(data, 'WeaponTypes').values())
        assert guest_clone['Primary'] in weapons
        host_spawn = _spawn_data(
            GAME_ROOT, manifest, role='host', name='Host', peer_name='Guest',
            peer_ip='127.0.0.1', local_port=1234, peer_port=1235,
            game_id=42, difficulty='normal', map_data=data,
        )
        guest_spawn = _spawn_data(
            GAME_ROOT, manifest, role='guest', name='Guest', peer_name='Host',
            peer_ip='127.0.0.1', local_port=1235, peer_port=1234,
            game_id=42, difficulty='normal', map_data=data,
        )
        host_index = SIDE_COUNTRIES.index(manifest['player_country'])
        guest_index = SIDE_COUNTRIES.index(manifest['guest_country'])
        assert section(host_spawn, 'Settings')['Side'] == str(host_index)
        assert section(host_spawn, 'Other1')['Side'] == str(guest_index)
        assert section(guest_spawn, 'Settings')['Side'] == str(guest_index)
        assert section(guest_spawn, 'Other1')['Side'] == str(host_index)

    restricted_host = {**host, 'production_restrictions': ['vehicles']}
    restricted_manifest, restricted_map = build_shop_manifest(
        GAME_ROOT, 'COOP-SHOP-TEST', 'coop_sthunder', restricted_host, guest,
    )
    assert section(restricted_map, 'MORHFV')['TechLevel'] == '-1'
    assert section(restricted_map, 'MORGFV')['TechLevel'] == '1'
    assert restricted_manifest['player_loadouts']['host'] == restricted_host
    assert rebuild_from_manifest(GAME_ROOT, restricted_manifest) == restricted_map
    restricted_guest = {**guest, 'production_restrictions': ['vehicles']}
    guest_manifest, guest_map = build_shop_manifest(
        GAME_ROOT, 'COOP-SHOP-TEST', 'coop_sthunder', host, restricted_guest,
    )
    assert section(guest_map, 'MORHFV')['TechLevel'] == '1'
    assert section(guest_map, 'MORGFV')['TechLevel'] == '-1'
    assert section(guest_map, 'MORGHTNK')['TechLevel'] == '-1'
    assert rebuild_from_manifest(GAME_ROOT, guest_manifest) == guest_map
    for invalid in (['vehicles', 'vehicles'], ['unknown'], [42]):
        try:
            build_shop_manifest(
                GAME_ROOT, 'COOP-SHOP-TEST', 'coop_sthunder',
                {**host, 'production_restrictions': invalid}, guest,
            )
        except ValueError:
            pass
        else:
            raise AssertionError(f'Invalid production restrictions accepted: {invalid}')

    shared = {
        'seed': 'COOP-SHARED-TEST', 'progression_mode': 'Grid Mode',
        'reward_mode': 'Chaos', 'coop_mode': True, 'starting_rewards': [],
        'mission_order': ['COOP_STHUNDER'], 'mission_checks': {},
    }
    grid_manifest, grid_map = build_manifest(
        GAME_ROOT, shared, 'coop_sthunder', unit_id='FV', allow_test_unit=True,
    )
    assert grid_manifest['schema'] == 4
    assert section(grid_map, 'MORPFV')['Owner'] == grid_manifest['player_country']
    assert not section(grid_map, 'MORHFV')
    assert not section(grid_map, 'MORGFV')
    with TemporaryDirectory() as temporary:
        private = Path(temporary)
        (private / 'INI').mkdir()
        (private / 'MapsMO' / 'Cooperative').mkdir(parents=True)
        original_catalogue = (GAME_ROOT / 'INI' / 'MentalOmegaMaps.ini').read_bytes()
        (private / 'INI' / 'MentalOmegaMaps.ini').write_bytes(original_catalogue)
        source = GAME_ROOT / 'MapsMO' / 'Cooperative' / 'coop_sthunder.map'
        shutil.copy2(source, private / 'MapsMO' / 'Cooperative' / source.name)
        manifest, data = build_shop_manifest(
            private, 'COOP-SHOP-TEST', 'coop_sthunder', host, guest,
        )
        later_manifest, later_data = build_shop_manifest(
            private, 'COOP-SHOP-TEST', 'coop_sthunder', host, guest,
            stage=2,
        )
        assert later_manifest['shop_stage'] == 2
        assert later_manifest['map_file'] != manifest['map_file']
        assert later_data == data
        destination = install(private, manifest, data)
        assert destination.read_bytes() == data
        assert manifest['map_key'] in (
            private / 'INI' / 'MentalOmegaMaps.ini'
        ).read_text(encoding='latin-1')
        install(private, manifest, data)
        remove(private, manifest)
        assert not destination.exists()
        assert (private / 'INI' / 'MentalOmegaMaps.ini').read_bytes() == original_catalogue
        try:
            rebuild_from_manifest(private, {**manifest, 'guest_country': 'UnitedStates'})
        except ValueError:
            pass
        else:
            raise AssertionError('Modified guest country was accepted.')
    print('Shop private clones and sides on 36 maps; reversible install; Grid shared clone unchanged')


if __name__ == '__main__':
    main()
