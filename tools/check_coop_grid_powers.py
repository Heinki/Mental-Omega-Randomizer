"""Verify earned Grid powers reach both native human slots on every co-op map."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from randomizer.coop.catalogue import discover_coop_missions
from randomizer.coop.direct import MODES, _mode_map, _spawn_data
from randomizer.coop.prototype import build_manifest, rebuild_from_manifest
from randomizer.core.paths import GAME_ROOT
from randomizer.maps.ini import section_value_map_preserve
from randomizer.rewards.catalogue import REWARD_POOL


def section(data, name):
    return section_value_map_preserve(data.decode('latin-1').splitlines(), name)


def grants_by_slot(data):
    """Follow native action-14 tags from neutral providers to Player @ A/B."""
    triggers = section(data, 'Triggers')
    actions = section(data, 'Actions')
    tags = section(data, 'Tags')
    grants = {}
    for trigger, value in triggers.items():
        if 'MOR Shared Grid Powers P' not in value:
            continue
        tokens = actions[trigger].split(',')
        assert tokens[:3] == ['1', '14', '0']
        house = int(tokens[3])
        assert house in (4475, 4476)
        assert house not in grants
        grants[house] = []
        for value in section(data, 'Structures').values():
            building = value.split(',')
            tag = tags.get(building[6], '').split(',')
            if tag[-1] != trigger:
                continue
            assert building[0] == 'Neutral'
            rules = section(data, building[1])
            assert rules['KeepAlive'] == 'no'
            assert rules['IsPassable'] == 'yes'
            assert rules['TechLevel'] == '-1'
            power = rules.get('SuperWeapon')
            if power:
                grants[house].append(power)
    assert set(grants) == {4475, 4476}
    assert sorted(grants[4475]) == sorted(grants[4476])
    assert len(grants[4475]) == len(set(grants[4475]))
    return grants


def grid_state(rewards):
    return {
        'seed': 'SHARED-GRID-POWERS', 'progression_mode': 'Grid Mode',
        'coop_mode': True, 'reward_mode': 'Chaos',
        'starting_rewards': [{'name': 'Stryker IFV Access'}],
        'mission_order': ['COOP_STHUNDER'],
        'mission_checks': {'COOP_STHUNDER': [{
            'id': 'victory', 'unlocked': True, 'rewards': rewards,
        }, {
            'id': 'locked', 'unlocked': False,
            'rewards': [{'name': 'Lightning Storm Power'}],
        }]},
    }


def main():
    state = grid_state([{'name': 'Chronolift Power'}, {'name': 'Time Freeze Power'}])
    missions = discover_coop_missions(GAME_ROOT)
    for mission in missions:
        manifest, data = build_manifest(GAME_ROOT, state, mission['coop_name'])
        assert section(data, 'General')['Behind'] == 'none'
        assert manifest['power_reward_ids'] == ['Chronolift Power', 'Time Freeze Power']
        grants = grants_by_slot(data)
        for powers in grants.values():
            assert any('Chronolift' in power for power in powers)
            assert any('TimeFreeze' in power for power in powers)
            assert not any('Lightning' in power for power in powers)
            for power in powers:
                rules = section(data, power)
                assert rules['SW.RequiredHouses'] == manifest['player_country']
                assert rules['SW.AllowAI'] == 'no'
        assert rebuild_from_manifest(GAME_ROOT, manifest) == data
        for difficulty in MODES:
            assert section(_mode_map(GAME_ROOT, manifest, difficulty), 'General')['Behind'] == 'none'
        for role in ('host', 'guest'):
            spawn = _spawn_data(
                GAME_ROOT, manifest, role=role, name=role, peer_name='other',
                peer_ip='127.0.0.1', local_port=1234, peer_port=1235,
                game_id=42, difficulty='normal', map_data=data,
            )
            assert section(spawn, 'Settings')['Side'] == section(spawn, 'Other1')['Side']

    powers = [reward for reward in REWARD_POOL if reward.get('kind') == 'superweapon']
    manifest, data = build_manifest(GAME_ROOT, grid_state(powers), 'coop_sthunder')
    grants = grants_by_slot(data)
    registered = set(section(data, 'SuperWeaponTypes').values())
    for power in grants[4475]:
        assert power in registered
    assert len(grants[4475]) >= len(powers)
    assert rebuild_from_manifest(GAME_ROOT, manifest) == data
    print(f'Shared Chronolift/Time Freeze on {len(missions)} maps; '
          f'all {len(powers)} earned powers, equal grants, AI exclusion, '
          'map parity, no Behind marker in any difficulty: passed')


if __name__ == '__main__':
    main()
