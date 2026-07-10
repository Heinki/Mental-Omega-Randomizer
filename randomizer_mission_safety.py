"""Mission-local safety unlocks for campaign production.

The randomizer locks unit access globally, but campaign maps sometimes hand
the player another faction's production during the mission. This module keeps
those maps playable by deriving a small basic-unit safety net from the map's
placed production structures.
"""

from randomizer_map import country_family, map_house_records, player_house_from_map, section_lines


BASIC_INFANTRY_UNLOCKS = {
    'allies': [('ENGINEER', '1'), ('E1', '1'), ('GGI', '1')],
    'soviets': [('ENGINEER', '1'), ('E2', '1'), ('FLAKT', '1')],
    'epsilon': [('ENGINEER', '1'), ('INIT', '1')],
    'foehn': [('ENGINEER', '1'), ('KNIGHT', '1')],
}

BASIC_VEHICLE_UNLOCKS = {
    'allies': [('AHMV', '2'), ('FV', '2')],
    'soviets': [('HTNK', '2'), ('HTK', '2')],
    'epsilon': [('LTNK', '2'), ('YTNK', '2')],
    'foehn': [('JACKAL', '2'), ('CYCL', '2')],
}

BASIC_AIR_UNLOCKS = {
    'allies': [('JUMPJET', '1')],
}

BASIC_NAVAL_UNLOCKS = {
    'allies': [('LCRF', '2'), ('DEST', '3'), ('DLPH', '3')],
    'soviets': [('SAPC', '2'), ('SUB', '3'), ('DBOAT', '3')],
}

PRODUCTION_BUILDINGS = {
    'allies': {
        'base': {'GACNST'},
        'infantry': {'GAPILE'},
        'vehicles': {'GAWEAP'},
        'air': {'GAAIRC'},
        'naval': {'GAYARD'},
    },
    'soviets': {
        'base': {'NACNST'},
        'infantry': {'NAHAND'},
        'vehicles': {'NAWEAP'},
        'naval': {'NAYARD'},
    },
    'epsilon': {
        'base': {'YACNST'},
        'infantry': {'YURRAX', 'YABRCK'},
        'vehicles': {'YAWEAP'},
        'naval': {'YAYARD'},
    },
    'foehn': {
        'base': {'FACNST'},
        'infantry': {'FOERAX'},
        'vehicles': {'FAWEAP'},
        'naval': {'FAYARD'},
    },
}

TECH_ORDER = [
    'ENGINEER',
    'E1',
    'GGI',
    'JUMPJET',
    'AHMV',
    'FV',
    'LCRF',
    'DEST',
    'DLPH',
    'E2',
    'FLAKT',
    'HTNK',
    'HTK',
    'SAPC',
    'SUB',
    'DBOAT',
    'INIT',
    'LTNK',
    'YTNK',
    'KNIGHT',
    'JACKAL',
    'CYCL',
]


def _building_variants(building_id):
    variants = {building_id}
    variants.add(building_id + 'B')
    variants.add(building_id + 'C')
    variants.add(building_id + 'AI')
    variants.add(building_id + '_D')
    return variants


def _production_lookup():
    lookup = {}
    for family, categories in PRODUCTION_BUILDINGS.items():
        for category, building_ids in categories.items():
            for building_id in building_ids:
                for variant in _building_variants(building_id):
                    lookup[variant] = (family, category)
    return lookup


PRODUCTION_LOOKUP = _production_lookup()


def _structure_owner_and_type(line):
    if '=' not in line:
        return None, None
    _, value = line.split('=', 1)
    parts = [part.strip() for part in value.split(',')]
    if len(parts) < 2:
        return None, None
    return parts[0], parts[1].upper()


def _structure_family(owner, building_family, house_records):
    record = house_records.get(owner or '')
    owner_family = country_family(record) if record else ''
    return owner_family or building_family


def _player_family(lines, house_records):
    player_house = player_house_from_map(lines)
    if not player_house:
        return ''
    return country_family(house_records.get(player_house, {}))


def _allowed_safety_families(player_family):
    if player_family == 'foehn':
        return {'allies', 'soviets', 'foehn'}
    if player_family in PRODUCTION_BUILDINGS:
        return set(PRODUCTION_BUILDINGS) - {player_family}
    return set()


def _unlocks_for_category(family, category):
    if category == 'base':
        return (
            BASIC_INFANTRY_UNLOCKS.get(family, [])
            + BASIC_VEHICLE_UNLOCKS.get(family, [])
        )
    if category == 'infantry':
        return BASIC_INFANTRY_UNLOCKS.get(family, [])
    if category == 'vehicles':
        return BASIC_VEHICLE_UNLOCKS.get(family, [])
    if category == 'air':
        return BASIC_AIR_UNLOCKS.get(family, [])
    if category == 'naval':
        return BASIC_NAVAL_UNLOCKS.get(family, [])
    return []


def _unique_unlocks(unlocks):
    seen = set()
    result = []
    for tech_id, tech_level in unlocks:
        key = tech_id.upper()
        if key in seen:
            continue
        seen.add(key)
        result.append((key, tech_level))
    return result


def mission_basic_unit_rules(lines):
    """Return off-faction TechLevel overrides needed by mission production."""
    house_records = map_house_records(lines)
    unlocks = []

    player_family = _player_family(lines, house_records)
    allowed_families = _allowed_safety_families(player_family)

    for line in section_lines(lines, 'Structures'):
        owner, building_id = _structure_owner_and_type(line)
        building_match = PRODUCTION_LOOKUP.get(building_id)
        if not building_match:
            continue

        building_family, category = building_match
        family = _structure_family(owner, building_family, house_records)
        if family not in allowed_families:
            continue
        unlocks.extend(_unlocks_for_category(family, category))

    rules = {}
    for tech_id, tech_level in _unique_unlocks(unlocks):
        rules[tech_id] = {'TechLevel': tech_level}
    return rules


def summarize_basic_unit_rules(rules):
    if not rules:
        return ''
    ordered = [tech_id for tech_id in TECH_ORDER if tech_id in rules]
    ordered.extend(sorted(tech_id for tech_id in rules if tech_id not in TECH_ORDER))
    return ', '.join(ordered)
