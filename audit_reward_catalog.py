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
from randomizer_rewards import (
    ALWAYS_AVAILABLE_TECH_IDS,
    ALWAYS_AVAILABLE_UNIT_IDS,
    BUFF_TARGETS,
    FACTION_DEFENSE_ROSTERS,
    FACTION_UNIT_ROSTERS,
    REWARD_POOL,
    TRAINABLE_DEFENSE_IDS,
    UNIT_BUFF_REWARDS,
    unit_display_label,
)


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

    buff_reward_units = {
        reward.get('unit', '').upper()
        for reward in UNIT_BUFF_REWARDS
        if reward.get('unit')
    }
    for faction, categories in FACTION_UNIT_ROSTERS.items():
        roster = {
            unit_id.upper(): label
            for units in categories.values()
            for unit_id, label in units.items()
        }
        missing_targets = sorted(set(roster) - buff_tags)
        if missing_targets:
            failures.append(f'{faction} roster missing buff targets: ' + ', '.join(missing_targets))
        missing_rewards = sorted(set(roster) - buff_reward_units)
        if missing_rewards:
            failures.append(f'{faction} roster missing generated buff rewards: ' + ', '.join(missing_rewards))
        for tag, expected in sorted(roster.items()):
            actual = unit_display_label(tag)
            if actual != expected:
                failures.append(f'{tag}: expected label "{expected}", got "{actual}"')
        print(f'{faction} buff coverage: {len(set(roster) & buff_reward_units)}/{len(roster)}')

        expected_access = set(roster) - {tag.upper() for tag in ALWAYS_AVAILABLE_UNIT_IDS}
        missing_access = sorted(expected_access - reward_tags)
        if missing_access:
            failures.append(f'{faction} roster missing access rewards: ' + ', '.join(missing_access))
        print(f'{faction} access coverage: {len(expected_access & reward_tags)}/{len(expected_access)}')

        defenses = {tag.upper(): label for tag, label in FACTION_DEFENSE_ROSTERS[faction].items()}
        missing_defense_access = sorted(set(defenses) - reward_tags)
        missing_defense_buffs = sorted(set(defenses) - buff_reward_units)
        if missing_defense_access:
            failures.append(f'{faction} defenses missing access rewards: ' + ', '.join(missing_defense_access))
        if missing_defense_buffs:
            failures.append(f'{faction} defenses missing buff rewards: ' + ', '.join(missing_defense_buffs))
        print(
            f'{faction} defense access/buff coverage: '
            f'{len(set(defenses) & reward_tags)}/{len(defenses)}, '
            f'{len(set(defenses) & buff_reward_units)}/{len(defenses)}'
        )

    defense_veteran_ids = {
        reward.get('unit', '').upper()
        for reward in UNIT_BUFF_REWARDS
        if reward.get('buff_type') == 'veteran'
        and BUFF_TARGETS.get(reward.get('unit'), {}).get('category') == 'defenses'
    }
    unexpected_defense_veterans = sorted(defense_veteran_ids - TRAINABLE_DEFENSE_IDS)
    missing_defense_veterans = sorted(TRAINABLE_DEFENSE_IDS - defense_veteran_ids)
    if unexpected_defense_veterans:
        failures.append(
            'Non-trainable defenses have veteran rewards: '
            + ', '.join(unexpected_defense_veterans)
        )
    if missing_defense_veterans:
        failures.append(
            'Trainable defenses are missing veteran rewards: '
            + ', '.join(missing_defense_veterans)
        )
    print(
        f'Trainable defense veteran coverage: '
        f'{len(TRAINABLE_DEFENSE_IDS & defense_veteran_ids)}/{len(TRAINABLE_DEFENSE_IDS)}'
    )

    essential_access = sorted({tag.upper() for tag in ALWAYS_AVAILABLE_TECH_IDS} & reward_tags)
    if essential_access:
        failures.append('Always-available essentials incorrectly have access rewards: ' + ', '.join(essential_access))
    essential_locks = sorted({tag.upper() for tag in ALWAYS_AVAILABLE_TECH_IDS} & controlled)
    if essential_locks:
        failures.append('Always-available essentials are controlled/locked: ' + ', '.join(essential_locks))

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
