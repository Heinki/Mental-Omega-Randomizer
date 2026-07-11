"""Mission-local access translation for mixed campaign production.

The randomizer locks unit access globally, but campaign maps sometimes hand
the player another faction's production during the mission. Selected-faction
campaigns translate earned roles to that production; All Campaigns retains a
small unconditional safety net.
"""

from randomizer_map import (
    country_family,
    map_house_records,
    player_controlled_houses,
    player_house_from_map,
    section_lines,
)
from randomizer_rewards import (
    ALWAYS_AVAILABLE_TECH_IDS,
    REWARD_POOL,
    unit_role_equivalents,
)


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
        'infantry': {'FOERAX', 'FABARR'},
        'vehicles': {'FAWEAP'},
        'naval': {'FAYARD'},
    },
}

# Physical factories used as the shared Chaos sidebar for each player faction.
# Some names in PRODUCTION_BUILDINGS (such as YURRAX and FOERAX) are generic
# prerequisite aliases, so keep the actual buildable structure explicit here.
CHAOS_PRIMARY_PRODUCTION = {
    'allies': {
        'base': 'GACNST',
        'infantry': 'GAPILE',
        'vehicles': 'GAWEAP',
        'air': 'GAAIRC',
        'naval': 'GAYARD',
    },
    'soviets': {
        'base': 'NACNST',
        'infantry': 'NAHAND',
        'vehicles': 'NAWEAP',
        'naval': 'NAYARD',
    },
    'epsilon': {
        'base': 'YACNST',
        'infantry': 'YABRCK',
        'vehicles': 'YAWEAP',
        'naval': 'YAYARD',
    },
    'foehn': {
        'base': 'FACNST',
        'infantry': 'FABARR',
        'vehicles': 'FAWEAP',
        'naval': 'FAYARD',
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


def _access_catalog():
    """Index access rewards by their target faction production category."""
    catalog = []
    seen = set()
    for reward in REWARD_POOL:
        if reward.get('kind') in {'buff', 'superweapon'}:
            continue
        for tech_id, values in reward.get('rules', {}).items():
            tech_id = tech_id.upper()
            tech_level = next(
                (str(value) for key, value in values.items() if key.lower() == 'techlevel'),
                '',
            )
            prerequisite = next(
                (str(value).upper() for key, value in values.items() if key.lower() == 'prerequisiteoverride'),
                '',
            )
            production = PRODUCTION_LOOKUP.get(prerequisite)
            if not tech_level or not production:
                continue
            family, category = production
            key = (tech_id, family, category)
            if key in seen:
                continue
            seen.add(key)
            catalog.append((tech_id, tech_level, family, category))
    return catalog


ACCESS_CATALOG = _access_catalog()


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
        return {'allies', 'soviets'}
    if player_family in PRODUCTION_BUILDINGS:
        return set(PRODUCTION_BUILDINGS) - {player_family, 'foehn'}
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


def mission_basic_unit_rules(lines, earned_access_ids=None, use_equivalent_access=False):
    """Return off-faction access needed by mixed mission production.

    All-Campaign seeds retain the unconditional basic safety net. A selected
    faction instead translates earned access into role-equivalent units for
    the off-faction production actually present in the map.
    """
    house_records = map_house_records(lines)
    unlocks = []
    production_categories = set()
    earned_access_ids = {str(unit_id).upper() for unit_id in (earned_access_ids or [])}

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
        production_categories.add((family, category))
        if not use_equivalent_access:
            unlocks.extend(_unlocks_for_category(family, category))

    if use_equivalent_access:
        expanded_categories = set(production_categories)
        for family, category in production_categories:
            if category == 'base':
                expanded_categories.add((family, 'infantry'))
                expanded_categories.add((family, 'vehicles'))

        # Engineers and similar economy essentials remain available because
        # their selected-faction counterparts are always available. All other
        # translated access requires an earned role peer.
        available_access = earned_access_ids | {
            tech_id.upper() for tech_id in ALWAYS_AVAILABLE_TECH_IDS
        }
        for tech_id, tech_level, family, category in ACCESS_CATALOG:
            if (family, category) not in expanded_categories:
                continue
            if unit_role_equivalents(tech_id).intersection(available_access):
                unlocks.append((tech_id, tech_level))

        # Engineers are not access rewards, so add the matching off-faction
        # engineer when a base or barracks is present.
        for family, category in expanded_categories:
            if category not in {'base', 'infantry'}:
                continue
            unlocks.extend(
                (tech_id, level)
                for tech_id, level in BASIC_INFANTRY_UNLOCKS.get(family, [])
                if tech_id in ALWAYS_AVAILABLE_TECH_IDS
            )

    rules = {}
    for tech_id, tech_level in _unique_unlocks(unlocks):
        rules[tech_id] = {'TechLevel': tech_level}
    return rules


def chaos_earned_access_rules(lines, earned_rewards):
    """Adapt every earned access item to player-controlled production."""
    player_houses = set(player_controlled_houses(lines))
    if not player_houses:
        player_house = player_house_from_map(lines)
        if player_house:
            player_houses.add(player_house)
    if not player_houses:
        return {}

    records = map_house_records(lines)
    player_countries = []
    for house in player_houses:
        country = records.get(house, {}).get('country') or house.replace(' House', '')
        if country and country not in player_countries:
            player_countries.append(country)
    if not player_countries:
        return {}

    production_by_category = {}
    for line in section_lines(lines, 'Structures'):
        owner, building_id = _structure_owner_and_type(line)
        if owner not in player_houses:
            continue
        production = PRODUCTION_LOOKUP.get(building_id)
        if not production:
            continue
        _, category = production
        production_by_category.setdefault(category, []).append(building_id)

    if not production_by_category:
        production_by_category = {}

    rules = {}
    owners = ','.join(player_countries + ['MORPLAYER'])
    player_family = _player_family(lines, records)
    primary_production = CHAOS_PRIMARY_PRODUCTION.get(player_family, {})
    base_buildings = production_by_category.get('base', [])
    base_prerequisite = primary_production.get('base')
    if not base_prerequisite and base_buildings:
        base_prerequisite = base_buildings[0]

    # Chaos makes every faction's production structures available from the
    # player's Construction Yard. This covers aircraft/naval factories that a
    # mission does not place initially and keeps the actual factory type valid
    # for the engine instead of pretending a War Factory can build AircraftTypes.
    if base_prerequisite:
        for categories in PRODUCTION_BUILDINGS.values():
            for category, building_ids in categories.items():
                if category == 'base':
                    continue
                for building_id in sorted(building_ids):
                    rules[building_id] = {
                        'TechLevel': '1',
                        'Owner': owners,
                        'RequiredHouses': owners,
                        'ForbiddenHouses': 'none',
                        'PrerequisiteOverride': base_prerequisite,
                    }

    for reward in earned_rewards:
        if reward.get('kind') in {'buff', 'superweapon'}:
            continue
        for tech_id, values in reward.get('rules', {}).items():
            tech_level = next(
                (str(value) for key, value in values.items() if key.lower() == 'techlevel'),
                '',
            )
            prerequisite = next(
                (str(value).upper() for key, value in values.items() if key.lower() == 'prerequisiteoverride'),
                '',
            )
            production = PRODUCTION_LOOKUP.get(prerequisite)
            if not tech_level or not production:
                continue
            _, category = production
            # Route foreign unlocks through the current player's own sidebar.
            # A campaign may not place the factory at map start, so relying on
            # Structures alone leaves (for example) Soviet infantry tied to
            # NAHAND even after the player later builds an Allied GAPILE.
            chosen_prerequisite = primary_production.get(category)
            if not chosen_prerequisite:
                available_buildings = production_by_category.get(category, [])
                chosen_prerequisite = available_buildings[0] if available_buildings else prerequisite
            rules[tech_id.upper()] = {
                'TechLevel': tech_level,
                'Owner': owners,
                'RequiredHouses': owners,
                'ForbiddenHouses': 'none',
                'PrerequisiteOverride': chosen_prerequisite,
            }
    return rules


def summarize_basic_unit_rules(rules):
    if not rules:
        return ''
    ordered = [tech_id for tech_id in TECH_ORDER if tech_id in rules]
    ordered.extend(sorted(tech_id for tech_id in rules if tech_id not in TECH_ORDER))
    return ', '.join(ordered)
