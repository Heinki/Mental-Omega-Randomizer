"""Check deterministic two-copy co-op export and reversible LAN registration."""

from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from randomizer.coop.prototype import (
    _map_config, build_manifest, install, rebuild_from_manifest, remove,
)
from randomizer.core.paths import GAME_ROOT
from randomizer.maps.ini import section_value_map
from randomizer.rewards.catalogue import REWARD_POOL


def _private_copy(destination, source):
    (destination / 'INI').mkdir(parents=True)
    (destination / 'MapsMO' / 'Cooperative').mkdir(parents=True)
    shutil.copy2(
        GAME_ROOT / 'INI' / 'MentalOmegaMaps.ini',
        destination / 'INI' / 'MentalOmegaMaps.ini',
    )
    shutil.copy2(
        source,
        destination / 'MapsMO' / 'Cooperative' / source.name,
    )


def main():
    base = {
        'seed': 'COOP-CHECK',
        'starting_rewards': [
            {'name': 'Stryker IFV Access'},
            {'name': 'Rhino Heavy Tank Access'},
            next(reward for reward in REWARD_POOL
                 if reward.get('unit') == 'FV' and reward.get('buff_type') == 'health'),
            next(reward for reward in REWARD_POOL
                 if reward.get('unit') == 'FV' and reward.get('buff_type') == 'damage'),
            next(reward for reward in REWARD_POOL
                 if reward.get('unit') == 'HTNK' and reward.get('buff_type') == 'speed'),
        ],
        'mission_order': ['CHECK'],
        'mission_checks': {},
    }
    cases = (
        ({**base, 'progression_mode': 'Classic', 'reward_mode': 'Standard'}, {}),
        ({**base, 'progression_mode': 'Grid Mode', 'reward_mode': 'Chaos'}, {}),
        ({
            **base,
            'progression_mode': 'Grid Mode',
            'reward_mode': 'Randomizer Arsenal',
            'mission_arsenals': {'CHECK': {
                'units': [{
                    'unit_id': 'FV', 'tech_ids': ['FV'],
                    'reward_name': 'Stryker IFV Access', 'tech_level': 1,
                }],
                'powers': [],
            }},
        }, {'source_mission': 'CHECK'}),
    )
    source, *_ = _map_config(GAME_ROOT, 'coop_sthunder')
    original = (GAME_ROOT / 'INI' / 'MentalOmegaMaps.ini').read_bytes()
    for state, kwargs in cases:
        manifest, data = build_manifest(
            GAME_ROOT, state, 'coop_sthunder', unit_id='FV', **kwargs
        )
        with TemporaryDirectory() as first, TemporaryDirectory() as second:
            for temp in (first, second):
                private = Path(temp)
                _private_copy(private, source)
                assert rebuild_from_manifest(private, manifest) == data
                installed = install(private, manifest, data)
                assert installed.read_bytes() == data
                assert manifest['map_key'] in (
                    private / 'INI' / 'MentalOmegaMaps.ini'
                ).read_text(encoding='latin-1')
                sections = data.decode('latin-1').splitlines()
                clone = section_value_map(sections, 'MORPFV')
                assert clone['requiredhouses'] == manifest['player_country']
                assert int(clone['strength']) > 275
                assert clone['primary'].startswith('MORCW')
                assert manifest['buff_counts']['FV']['health'] == 1
                if state['reward_mode'] != 'Randomizer Arsenal':
                    assert manifest['access_ids'] == ['FV', 'HTNK']
                    assert int(section_value_map(sections, 'MORPHTNK')['speed']) > 5
                install(private, manifest, data)
                remove(private, manifest)
                assert not installed.exists()
                assert (private / 'INI' / 'MentalOmegaMaps.ini').read_bytes() == original
            tampered = dict(manifest, map_file='../other.map')
            try:
                rebuild_from_manifest(Path(first), tampered)
            except ValueError:
                pass
            else:
                raise AssertionError('Manifest destination tampering was accepted.')
    try:
        build_manifest(
            GAME_ROOT, {**base, 'progression_mode': 'Shop Mode'},
            'coop_sthunder', unit_id='FV',
        )
    except ValueError:
        pass
    else:
        raise AssertionError('Shop Mode was accepted by the co-op prototype.')
    print('Co-op prototype: Classic, Grid, Arsenal; two identical maps per case; reversible install')


if __name__ == '__main__':
    main()
