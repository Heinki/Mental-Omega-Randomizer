"""Generate the static player-owned TechnoType roster.

Infantry definitions come from the mapper-reviewed InfantryList.txt. Remaining
rewardable units come from the installed Mental Omega 3.3.6 rules registry.
Generated files are committed runtime data; generation is a maintenance step,
never part of mission launch.
"""

from __future__ import annotations

import argparse
import re
from collections import OrderedDict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INFANTRY = ROOT / 'InfantryList.txt'
DEFAULT_RULES = ROOT.parent / 'RandomizerLauncherData' / 'cameo_cache' / 'rulesmo.ini'
DEFAULT_OUTPUT_DIR = ROOT / 'configs'
TYPE_LISTS = OrderedDict((
    ('infantry', 'InfantryTypes'),
    ('units', 'VehicleTypes'),
    ('aircraft', 'AircraftTypes'),
    ('defenses', 'BuildingTypes'),
    ('special_buildings', 'BuildingTypes'),
))
OUTPUT_GROUPS = OrderedDict((
    ('infantry', ('RandomizerInfantry.ini', 300000)),
    ('heroes', ('RandomizerHeroes.ini', 310000)),
    ('vehicles', ('RandomizerVehicles.ini', 320000)),
    ('ships', ('RandomizerShips.ini', 330000)),
    ('aircraft', ('RandomizerAircraft.ini', 340000)),
    ('buildings', ('RandomizerDefensesAndSpecialBuildings.ini', 350000)),
))
IMAGE_OVERRIDES = {
    # Mapper source calls the Mortar Quad art MORTAR, but installed artmo.ini
    # defines its cameo and sequence under [MOTOR].
    'MOTOR': 'MOTOR',
}


def read_sections(path: Path) -> OrderedDict[str, OrderedDict[str, str]]:
    sections: OrderedDict[str, OrderedDict[str, str]] = OrderedDict()
    current = None
    for raw_line in path.read_text(encoding='utf-8-sig', errors='strict').splitlines():
        stripped = raw_line.strip()
        match = re.fullmatch(r'\[([^]]+)\]', stripped)
        if match:
            current = match.group(1).strip()
            sections[current] = OrderedDict()
            continue
        if current is None or not stripped or stripped.startswith(';') or '=' not in raw_line:
            continue
        key, value = raw_line.split('=', 1)
        sections[current][key.strip()] = value.strip()
    return sections


def case_name(sections, requested):
    requested = requested.lower()
    return next((name for name in sections if name.lower() == requested), None)


def infantry_sources(sections):
    registry_name = case_name(sections, 'InfantryTypes')
    if not registry_name:
        raise ValueError('InfantryList.txt has no [InfantryTypes] section.')
    source_to_section = {}
    for clone_id in sections[registry_name].values():
        clone_id = clone_id.split(';', 1)[0].strip()
        if not clone_id.upper().startswith('MOR'):
            continue
        source_id = 'E1' if clone_id.upper() == 'MORE1' else clone_id[3:].upper()
        section_name = case_name(sections, clone_id)
        if not section_name:
            # Mapper scratch lists may reserve a future registry ID before its
            # definition exists. Required reward targets are checked below.
            continue
        source_to_section[source_id] = section_name
    return source_to_section


def render_section(name, values):
    lines = [f'[{name}]']
    for key, value in values.items():
        if key.lower() == '$inherits':
            continue
        lines.append(f'{key}={value}')
    return lines


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--infantry', type=Path, default=DEFAULT_INFANTRY)
    parser.add_argument('--rules', type=Path, default=DEFAULT_RULES)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    # Import after resolving project root so direct script execution works.
    import sys
    sys.path.insert(0, str(ROOT))
    from randomizer.rewards.catalogue import (
        BUFF_TARGETS,
        LIMITED_HERO_UNIT_IDS,
        NAVAL_UNIT_IDS,
    )

    infantry_sections = read_sections(args.infantry)
    installed_sections = read_sections(args.rules)
    reviewed_infantry = infantry_sources(infantry_sections)

    target_ids_by_list = OrderedDict(
        (list_name, []) for list_name in dict.fromkeys(TYPE_LISTS.values())
    )
    target_categories = {}
    for source_id, target in BUFF_TARGETS.items():
        category = target.get('category')
        list_name = TYPE_LISTS.get(category)
        if not list_name:
            continue
        target_ids_by_list[list_name].append(source_id.upper())
        target_categories[source_id.upper()] = category

    # Preserve mapper-reviewed extra infantry for later catalogue expansion.
    for source_id in reviewed_infantry:
        if source_id not in target_ids_by_list['InfantryTypes']:
            target_ids_by_list['InfantryTypes'].append(source_id)
            target_categories[source_id] = 'infantry-extra'

    definitions = OrderedDict()
    missing = []
    for list_name, source_ids in target_ids_by_list.items():
        for source_id in source_ids:
            if source_id in definitions:
                continue
            if source_id in reviewed_infantry:
                source_values = infantry_sections[reviewed_infantry[source_id]]
            else:
                source_name = case_name(installed_sections, source_id)
                if not source_name:
                    missing.append(source_id)
                    continue
                source_values = installed_sections[source_name]
            values = OrderedDict(source_values)
            if source_id in IMAGE_OVERRIDES:
                for key in list(values):
                    if key.lower() == 'image':
                        del values[key]
                values['Image'] = IMAGE_OVERRIDES[source_id]
            elif not any(key.lower() == 'image' and value for key, value in values.items()):
                values['Image'] = source_id
            definitions[source_id] = values

    if missing:
        raise ValueError('Installed rules missing target section(s): ' + ', '.join(missing))

    grouped_ids = OrderedDict((group, []) for group in OUTPUT_GROUPS)
    for source_id in definitions:
        category = target_categories[source_id]
        if source_id in LIMITED_HERO_UNIT_IDS or category == 'infantry-extra':
            group = 'heroes'
        elif category == 'infantry':
            group = 'infantry'
        elif category == 'units' and source_id in NAVAL_UNIT_IDS:
            group = 'ships'
        elif category == 'units':
            group = 'vehicles'
        elif category == 'aircraft':
            group = 'aircraft'
        else:
            group = 'buildings'
        grouped_ids[group].append(source_id)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for group, source_ids in grouped_ids.items():
        filename, next_key = OUTPUT_GROUPS[group]
        output_path = args.output_dir / filename
        lines = [
            f'; Mental Omega Randomizer owned {group}',
            '; Generated by tools/generate_randomizer_units.py.',
            '; Runtime changes MORP* sections only. Native IDs remain AI/script types.',
            '',
        ]
        registry_groups = OrderedDict()
        for source_id in source_ids:
            list_name = TYPE_LISTS[target_categories[source_id].split('-', 1)[0]]
            registry_groups.setdefault(list_name, []).append(source_id)
        for list_name, registry_ids in registry_groups.items():
            lines.append(f'[{list_name}]')
            for source_id in registry_ids:
                lines.append(f'{next_key}=MORP{source_id}')
                next_key += 1
            lines.append('')
        for source_id in source_ids:
            lines.extend(render_section(f'MORP{source_id}', definitions[source_id]))
            lines.append('')
        output_path.write_text('\n'.join(lines), encoding='utf-8', newline='\n')
        print(
            f'Wrote {output_path}: {len(source_ids)} TechnoTypes, '
            f'{len(source_ids)} registry entries.'
        )


if __name__ == '__main__':
    main()
