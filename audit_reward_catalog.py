"""Audit randomizer unit tags against local Mental Omega map/INI sources.

This is a developer helper. It does not launch the game or modify files.
Run from the game folder with:

    python RandomizerLauncher\audit_reward_catalog.py
"""

from pathlib import Path
import sys

APP_DIR = Path(__file__).resolve().parent
GAME_ROOT = APP_DIR.parent
sys.path.insert(0, str(APP_DIR))

from randomizer_map import EXTRA_TECH_LOCKS, controlled_tech_ids
from randomizer_rewards import BUFF_TARGETS, REWARD_POOL, unit_display_label


EXPECTED_LABELS = {
    'ADOG': 'Attack Dog',
    'AHMV': 'Humvee',
    'AMEDIC': 'Field Medic',
    'CLEG': 'Cryo Legionnaire',
    'DBOAT': 'Sea Scorpion',
    'DOG': 'Soviet Attack Dog',
    'E1': 'GI',
    'E2': 'Conscript',
    'ENGINEER': 'Engineer',
    'FLAKT': 'Flak Trooper',
    'FV': 'IFV',
    'GGI': 'Guardian GI',
    'HTK': 'Flak Track',
    'HTNK': 'Heavy Tank',
    'JUMPJET': 'Rocketeer',
    'SAPC': 'Soviet Transport',
    'SHK': 'Tesla Trooper',
    'SQD': 'Giant Squid',
    'SUB': 'Typhoon Sub',
    'TTNK': 'Tesla Tank',
}


def read_text(path):
    return path.read_text(encoding='utf-8', errors='ignore')


def ini_sections(text):
    current = None
    values = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(';'):
            continue
        if line.startswith('[') and ']' in line:
            current = line[1:line.index(']')].upper()
            values.setdefault(current, {})
            continue
        if current and '=' in line:
            key, value = line.split('=', 1)
            values[current][key.strip()] = value.strip()
    return values


def no_bases_start_sections():
    path = GAME_ROOT / 'INI' / 'Map Code' / 'No Bases.ini'
    if not path.exists():
        return set(), f'Missing {path}'
    sections = ini_sections(read_text(path))
    return {
        section
        for section, values in sections.items()
        if values.get('AllowedToStartInMultiplayer', '').lower() == 'yes'
    }, None


def source_files():
    roots = [
        GAME_ROOT / 'INI',
        GAME_ROOT / 'MapsMO',
        APP_DIR / 'extracted_maps',
        APP_DIR / 'generated_maps',
    ]
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob('*'):
            if path.suffix.lower() in {'.ini', '.map'}:
                yield path


def section_presence(tags):
    presence = {tag: [] for tag in tags}
    for path in source_files():
        text = read_text(path).upper()
        for tag in tags:
            if f'[{tag}]' in text:
                presence[tag].append(path.relative_to(GAME_ROOT))
    return presence


def reward_rule_tags():
    tags = set()
    for reward in REWARD_POOL:
        for section in reward.get('rules', {}):
            tags.add(section.upper())
    return tags


def main():
    failures = []
    controlled = set(controlled_tech_ids())
    reward_tags = reward_rule_tags()
    buff_tags = {tag.upper() for tag in BUFF_TARGETS if tag != 'MOR_BUILDINGS'}
    guarded = controlled | {tag.upper() for tag in EXTRA_TECH_LOCKS}

    print('Reward rule tags:', ', '.join(sorted(reward_tags)))
    print('Buff target tags:', ', '.join(sorted(buff_tags)))

    for tag, expected in sorted(EXPECTED_LABELS.items()):
        actual = unit_display_label(tag)
        if actual != expected:
            failures.append(f'{tag}: expected label "{expected}", got "{actual}"')

    start_sections, error = no_bases_start_sections()
    if error:
        failures.append(error)
    else:
        unguarded = sorted(start_sections - guarded)
        if unguarded:
            failures.append(
                'No Bases start/build sections are not controlled or extra-locked: '
                + ', '.join(unguarded)
            )

    missing_buff_rules = sorted(buff_tags - controlled - {'MOR_BUILDINGS'})
    if missing_buff_rules:
        failures.append(
            'Buff targets without matching controlled tech IDs: '
            + ', '.join(missing_buff_rules)
        )

    presence = section_presence(reward_tags | buff_tags)
    missing_sections = sorted(tag for tag, paths in presence.items() if not paths)
    if missing_sections:
        print('No local map-code/generated section found for:', ', '.join(missing_sections))

    if failures:
        print('\nAUDIT FAILED')
        for failure in failures:
            print('-', failure)
        raise SystemExit(1)

    print('\nAudit OK')
    print(f'No Bases guarded sections: {len(start_sections & guarded)}/{len(start_sections)}')


if __name__ == '__main__':
    main()
