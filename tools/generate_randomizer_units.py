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
FALLBACK_REVIEWED_INFANTRY = ROOT / 'configs' / 'RandomizerHeroes.ini'
DEFAULT_RULES = ROOT.parent / 'RandomizerLauncherData' / 'cameo_cache' / 'rulesmo.ini'
DEFAULT_OUTPUT_DIR = ROOT / 'configs'
SUPPLEMENTAL_SOURCE_FILES = (
    ROOT.parent / 'MapsMO' / 'Challenge' / 'c_revolution.map',
)
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
# Append newly reviewed map-only identities instead of renumbering every
# committed registry entry that already follows them in BUFF_TARGETS order.
STABLE_APPEND_IDS = frozenset({'MAMM', 'PANTHER'})
IMAGE_OVERRIDES = {
    # Mapper source calls the Mortar Quad art MORTAR, but installed artmo.ini
    # defines its cameo and sequence under [MOTOR].
    'MOTOR': 'MOTOR',
}
SPECIAL_TEMPLATE_SOURCES = {
    # Campaign/map-only variants receive independent reward identities while
    # retaining the complete installed source definition underneath.
    'GHTNKP': 'GHTNK',
    'PROMEP': 'PROME',
    'ITNK': 'RACC',
    'JACKALP': 'JACKAL',
    'DIVERP': 'DIVER',
    'TARCHIAP': 'TARCHIA',
    'ROACHP': 'ROACH',
    'NAPSIS': 'YAPSIS',
    'NACLONS': 'NACLON',
    'LUNRE': 'LUNR',
}
TEMPLATE_VALUE_OVERRIDES = {
    # Iron Guard is an auto-firing EMPulse cannon. Cloaking the building can
    # prevent its self-targeted field weapon from firing reliably.
    'NAIRDM': {
        'Prerequisite': '',
        'Cloakable.Allowed': 'no',
    },
    'BORIS': {
        'BuildLimit': '1',
    },
    'PERUN': {
        # Campaign source is intentionally impractical to produce. Portable
        # reward must use normal construction timing.
        'BuildTimeMultiplier': '1',
    },
    'RHAD': {
        'BuildLimit': '1',
    },
    'GHTNKP': {
        'Name': 'Gharial Prototype',
        'Image': 'GHTNK2',
        'IFVMode': '3',
        'Primary': 'GharialBetaCannon',
        'Weapon1': 'GharialBetaCannon',
        'ElitePrimary': 'GharialBetaCannon',
        'EliteWeapon1': 'GharialBetaCannon',
        'InitialPayload.Nums': '0',
    },
    'PROMEP': {
        'Name': 'Mastodon Prototype',
        'Image': 'PROME2',
        'Speed': '4',
        'IFVMode': '11',
        'Weapon1': 'PrometheusBetaCharge',
        'Weapon2': 'PrometheusBetaCharge',
        'Weapon3': 'PrometheusBetaBlast',
        'Weapon4': 'PrometheusBetaBlast',
        'Weapon5': 'PrometheusBetaCharge2',
        'Weapon6': 'PrometheusBetaCharge2',
        'EliteWeapon1': 'PrometheusBetaCharge',
        'EliteWeapon2': 'PrometheusBetaCharge',
        'EliteWeapon3': 'PrometheusBetaBlast',
        'EliteWeapon4': 'PrometheusBetaBlast',
        'EliteWeapon5': 'PrometheusBetaCharge2',
        'EliteWeapon6': 'PrometheusBetaCharge2',
        'VoiceSelect': 'MastodonBetaSelect',
        'VoiceAttackCommand': 'MastodonBetaAttackCommand',
        'VoiceFeedback': 'none',
        'SelfHealing.Amount': '2',
        'DamageParticleSystems': 'SparkSys,SmallGreySSys',
    },
    'ITNK': {
        'ROT': '6',
        'Image': 'ITNK',
        'Name': 'Infector Tank',
        'UIName': 'NAME:ITNK',
        'Sight': '8',
        'Speed': '6',
        'Strength': '320',
        'MoveSound': 'GharialMoveStart',
        'CrushSound': 'TankCrush',
        'VoiceSelect': 'RaccoonSelect2',
        'InhibitorRange': '0',
        'AttachEffect.Delay': '-1',
        'AttachEffect.Animation': 'DUMMY',
    },
    'JACKALP': {
        'Name': 'Jackal Racer Prototype',
        # JACKALA is a native-map appearance swap whose visible turret still
        # depends on the original JACKAL identity. Standalone reward clones
        # need the complete JACKAL voxel/turret pair.
        'Image': 'JACKAL',
    },
    'DIVERP': {
        'Name': 'Diverbee Prototype',
        'Image': 'ADIVER',
        'Cost': '800',
        'Soylent': '400',
        'Explosion': 'DIVERKILL2',
        'AttachEffect.Animation': 'none',
    },
    'TARCHIAP': {
        'Name': 'Tarchia Prototype',
        'Image': 'ATARCHIA',
        'Speed': '6',
        'IFVMode': '3',
        'Weapon5': 'TarchiaCannonOld',
        'Weapon6': 'TarchiaCannonOld',
        'EliteWeapon5': 'TarchiaCannonOld',
        'EliteWeapon6': 'TarchiaCannonOld',
        'Explodes': 'no',
        'DeathWeapon': 'none',
    },
    'ROACHP': {
        'Name': 'Bison Prototype',
        'Image': 'ROACH2',
        'Speed': '5',
        'Strength': '700',
        'Explodes': 'yes',
        'DeathWeapon': 'MantisDeathWeapon',
        'DamageParticleSystems': 'SparkSys,SmallGreySSys',
    },
    'NAPSIS': {
        'Name': 'Psychic Sensor',
        'UIName': 'NAME:NAPSIS',
        'Image': 'NAPSIS',
        'Cost': '800',
        'Power': '-50',
        'Radar': 'no',
        'Spyable': 'no',
        'SuperWeapon': 'none',
        'SuperWeapon2': 'none',
        'HasRadialIndicator': 'true',
        'PsychicDetectionRadius': '10',
        'ConcentricRadialIndicator': 'true',
    },
    'NACLONS': {
        'Name': 'Soviet Cloning Vats',
        'UIName': 'NAME:NACLON',
        'Image': 'NACLON',
    },
    'LUNRE': {
        'Name': 'Cosmonaut',
        'Image': 'LUNR',
    },
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
        if clone_id.upper() == 'MORE1':
            source_id = 'E1'
        elif clone_id.upper().startswith('MORP'):
            source_id = clone_id[4:].upper()
        else:
            source_id = clone_id[3:].upper()
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
    parser.add_argument(
        '--group',
        action='append',
        choices=tuple(OUTPUT_GROUPS),
        help='Generate only this output group. May be repeated.',
    )
    args = parser.parse_args()

    # Import after resolving project root so direct script execution works.
    import sys
    sys.path.insert(0, str(ROOT))
    from randomizer.rewards.catalogue import (
        BUFF_TARGETS,
        LIMITED_HERO_UNIT_IDS,
        NAVAL_UNIT_IDS,
        SPECIAL_REWARD_UNIT_IDS,
    )

    selected_groups = set(args.group or OUTPUT_GROUPS)
    needs_reviewed_infantry = bool(selected_groups.intersection({'infantry', 'heroes'}))
    reviewed_infantry_path = args.infantry
    if needs_reviewed_infantry and not reviewed_infantry_path.is_file():
        reviewed_infantry_path = FALLBACK_REVIEWED_INFANTRY
    if needs_reviewed_infantry and not reviewed_infantry_path.is_file():
        raise FileNotFoundError(
            'Reviewed infantry source is required for selected groups: '
            f'{args.infantry} or {FALLBACK_REVIEWED_INFANTRY}'
        )
    infantry_sections = (
        read_sections(reviewed_infantry_path)
        if reviewed_infantry_path.is_file()
        else OrderedDict()
    )
    installed_sections = read_sections(args.rules)
    supplemental_sections = OrderedDict()
    for source_path in SUPPLEMENTAL_SOURCE_FILES:
        if source_path.is_file():
            supplemental_sections.update(read_sections(source_path))
    reviewed_infantry = (
        infantry_sources(infantry_sections) if infantry_sections else {}
    )

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
                template_source = SPECIAL_TEMPLATE_SOURCES.get(source_id, source_id)
                source_sections = installed_sections
                source_name = case_name(source_sections, template_source)
                if not source_name:
                    source_sections = supplemental_sections
                    source_name = case_name(source_sections, template_source)
                if not source_name:
                    missing.append(source_id)
                    continue
                source_values = source_sections[source_name]
            values = OrderedDict(source_values)
            if source_id in IMAGE_OVERRIDES:
                for key in list(values):
                    if key.lower() == 'image':
                        del values[key]
                values['Image'] = IMAGE_OVERRIDES[source_id]
            elif not any(key.lower() == 'image' and value for key, value in values.items()):
                values['Image'] = source_id
            values.update(TEMPLATE_VALUE_OVERRIDES.get(source_id, {}))
            definitions[source_id] = values

    if missing:
        raise ValueError('Installed rules missing target section(s): ' + ', '.join(missing))

    grouped_ids = OrderedDict((group, []) for group in OUTPUT_GROUPS)
    for source_id in definitions:
        category = target_categories[source_id]
        if (
            source_id in LIMITED_HERO_UNIT_IDS
            or (
                source_id in SPECIAL_REWARD_UNIT_IDS
                and category == 'infantry'
            )
            or category == 'infantry-extra'
        ):
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
    for group, source_ids in grouped_ids.items():
        grouped_ids[group] = [
            source_id for source_id in source_ids
            if source_id not in STABLE_APPEND_IDS
        ] + [
            source_id for source_id in source_ids
            if source_id in STABLE_APPEND_IDS
        ]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for group, source_ids in grouped_ids.items():
        if group not in selected_groups:
            continue
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
