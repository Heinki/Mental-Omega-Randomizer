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
)
from randomizer_ini import section_lines
from randomizer_rewards import (
    ALWAYS_AVAILABLE_TECH_IDS,
    BUFF_TARGETS,
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

# Four guaranteed combat roles for the optional seed-start roster. Standard
# translates each role to the physical production families present in a map.
# Chaos assigns every faction once across the four roles.
TIER_ONE_ROLE_UNITS = {
    'ground_infantry': {
        'allies': ('E1', 'infantry'),
        'soviets': ('E2', 'infantry'),
        'epsilon': ('INIT', 'infantry'),
        'foehn': ('KNIGHT', 'infantry'),
    },
    'anti_air_infantry': {
        'allies': ('GGI', 'infantry'),
        'soviets': ('FLAKT', 'infantry'),
        'epsilon': ('HARP', 'infantry'),
        'foehn': ('COVE', 'infantry'),
    },
    'ground_vehicle': {
        'allies': ('ETNK', 'vehicles'),
        'soviets': ('HTNK', 'vehicles'),
        'epsilon': ('LTNK', 'vehicles'),
        'foehn': ('DRACO', 'vehicles'),
    },
    'anti_air_vehicle': {
        'allies': ('AHMV', 'vehicles'),
        'soviets': ('HTK', 'vehicles'),
        'epsilon': ('YTNK', 'vehicles'),
        'foehn': ('JACKAL', 'vehicles'),
    },
}

STANDARD_TIER_ONE_FAMILIES = ('allies', 'soviets', 'epsilon')

BASIC_AIR_UNLOCKS = {
    'allies': [('JUMPJET', '1')],
}

BASIC_NAVAL_UNLOCKS = {
    'allies': [('LCRF', '2'), ('DEST', '3'), ('DLPH', '3')],
    'soviets': [('SAPC', '2'), ('SUB', '3'), ('DBOAT', '3')],
}

AMPHIBIOUS_TRANSPORTS = {
    'allies': ('LCRF', 'GAYARD'),
    'soviets': ('SAPC', 'NAYARD'),
    'epsilon': ('YHVR', 'YAYARD'),
    'foehn': ('SEAT', 'FAYARD'),
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
        'air': {'NAAIR'},
        'naval': {'NAYARD'},
    },
    'epsilon': {
        'base': {'YACNST'},
        'infantry': {'YURRAX', 'YABRCK'},
        'vehicles': {'YAWEAP'},
        'air': {'YAAIRF'},
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
        'air': 'NAAIR',
        'naval': 'NAYARD',
    },
    'epsilon': {
        'base': 'YACNST',
        'infantry': 'YABRCK',
        'vehicles': 'YAWEAP',
        'air': 'YAAIRF',
        'naval': 'YAYARD',
    },
    'foehn': {
        'base': 'FACNST',
        'infantry': 'FABARR',
        'vehicles': 'FAWEAP',
        'air': 'FAWEAP',
        'naval': 'FAYARD',
    },
}

CHAOS_PRODUCTION_ALTERNATIVES = {
    category: tuple(
        categories[category]
        for categories in CHAOS_PRIMARY_PRODUCTION.values()
        if categories.get(category)
    )
    for category in ('base', 'infantry', 'vehicles', 'air', 'naval')
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
    'YHVR',
    'INIT',
    'LTNK',
    'YTNK',
    'KNIGHT',
    'JACKAL',
    'CYCL',
    'SEAT',
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
            owner = next(
                (str(value) for key, value in values.items() if key.lower() == 'owner'),
                '',
            )
            key = (tech_id, family, category)
            if key in seen:
                continue
            seen.add(key)
            catalog.append((tech_id, tech_level, family, category, prerequisite, owner))
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


def _mission_production_buildings(lines, house_records):
    """Yield physical production types placed or planned by the mission."""
    for line in section_lines(lines, 'Structures'):
        _owner, building_id = _structure_owner_and_type(line)
        if building_id:
            yield building_id

    # Several campaign missions, notably Epsilon 07, define the base the
    # player later operates only as numbered build nodes in a House section.
    # Those factories never appear in [Structures] in the source map.
    for house in house_records:
        for line in section_lines(lines, house):
            if '=' not in line:
                continue
            key, value = line.split('=', 1)
            if not key.strip().isdigit():
                continue
            building_id = value.split(',', 1)[0].strip().upper()
            if building_id:
                yield building_id


def _player_family(lines, house_records):
    player_house = player_house_from_map(lines)
    if not player_house:
        return ''
    return country_family(house_records.get(player_house, {}))


def _comma_items(value):
    return [item.strip() for item in str(value or '').split(',') if item.strip()]


def _merged_items(*groups):
    result = []
    seen = set()
    for group in groups:
        for item in group:
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
    return result


def _player_build_countries(lines, house_records):
    countries = []
    for house in player_controlled_houses(lines):
        country = house_records.get(house, {}).get('country') or house.replace(' House', '')
        if country:
            countries.append(country)
    return _merged_items(countries, ['MORPLAYER'])


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

    for building_id in _mission_production_buildings(lines, house_records):
        building_match = PRODUCTION_LOOKUP.get(building_id)
        if not building_match:
            continue

        building_family, category = building_match
        # Production is determined by the physical factory type. Its starting
        # owner can be an enemy or neutral house before a scripted handover or
        # capture, and using that owner's country misclassifies Soviet/Allied
        # factories in mixed campaign missions.
        family = building_family
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
        player_build_countries = _player_build_countries(lines, house_records)
        for tech_id, tech_level, family, category, prerequisite, native_owners in ACCESS_CATALOG:
            if (family, category) not in expanded_categories:
                continue
            if unit_role_equivalents(tech_id).intersection(available_access):
                owners = _merged_items(_comma_items(native_owners), player_build_countries)
                access_rule = {
                    'TechLevel': tech_level,
                    'Owner': ','.join(owners),
                    'RequiredHouses': ','.join(owners),
                    'ForbiddenHouses': 'none',
                    'PrerequisiteOverride': prerequisite,
                }
                unlocks.append((tech_id, tech_level, access_rule))

        # Engineers are not access rewards, so add the matching off-faction
        # engineer when a base or barracks is present.
        for family, category in expanded_categories:
            if category not in {'base', 'infantry'}:
                continue
            unlocks.extend(
                (tech_id, level, None)
                for tech_id, level in BASIC_INFANTRY_UNLOCKS.get(family, [])
                if tech_id in ALWAYS_AVAILABLE_TECH_IDS
            )

    rules = {}
    seen = set()
    for unlock in unlocks:
        tech_id, tech_level = unlock[:2]
        tech_id = tech_id.upper()
        if tech_id in seen:
            continue
        seen.add(tech_id)
        rule = unlock[2] if len(unlock) > 2 else None
        rules[tech_id] = dict(rule or {'TechLevel': tech_level})
    return rules


def chaos_cameo_priority_rules(player_family):
    """Keep each faction contiguous on Chaos production sidebars."""
    faction_order = ['allies', 'soviets', 'epsilon', 'foehn']
    player_family = str(player_family or '').lower()
    if player_family in faction_order:
        faction_order.remove(player_family)
        faction_order.insert(0, player_family)
    priorities = {
        faction: (len(faction_order) - index) * 100
        for index, faction in enumerate(faction_order)
    }

    rules = {}
    for tech_id, target in BUFF_TARGETS.items():
        factions = target.get('factions') or []
        if len(factions) != 1:
            continue
        faction = str(factions[0]).lower()
        if faction in priorities:
            rules[tech_id] = {'CameoPriority': str(priorities[faction])}

    return rules


def _chaos_prerequisite_rules(category, fallback):
    """Allow an earned item from the matching factory of any faction."""
    alternatives = list(CHAOS_PRODUCTION_ALTERNATIVES.get(category, ()))
    if not alternatives and fallback:
        alternatives = [fallback]
    if not alternatives:
        return {}

    rules = {
        # Reset campaign/global overrides so Ares' independent prerequisite
        # lists below decide availability.
        'PrerequisiteOverride': 'none',
        'Prerequisite.List0': alternatives[0],
        'Prerequisite.Lists': str(max(0, len(alternatives) - 1)),
    }
    for index, building_id in enumerate(alternatives[1:], start=1):
        rules[f'Prerequisite.List{index}'] = building_id
    return rules


def always_available_transport_rules(lines, chaos_mode=False):
    """Make every faction's amphibious transport immediately buildable."""
    records = map_house_records(lines)
    owners = ','.join(_player_build_countries(lines, records))
    rules = {}
    for _family, (tech_id, prerequisite) in AMPHIBIOUS_TRANSPORTS.items():
        values = {
            'TechLevel': '1',
            'Owner': owners,
            'RequiredHouses': owners,
            'ForbiddenHouses': 'none',
        }
        if chaos_mode:
            values.update(_chaos_prerequisite_rules('naval', prerequisite))
        else:
            values['PrerequisiteOverride'] = prerequisite
        rules[tech_id] = values
    return rules


def tier_one_unit_ids(families):
    """Return all four starter roles for each requested faction family."""
    requested = {str(family or '').lower() for family in families}
    return tuple(
        role_units[family][0]
        for role_units in TIER_ONE_ROLE_UNITS.values()
        for family in STANDARD_TIER_ONE_FAMILIES + ('foehn',)
        if family in requested
    )


def random_chaos_tier_one_unit_ids(rng):
    """Assign every faction once across ground/AA infantry and vehicles."""
    families = list(STANDARD_TIER_ONE_FAMILIES) + ['foehn']
    rng.shuffle(families)
    return tuple(
        role_units[family][0]
        for role_units, family in zip(TIER_ONE_ROLE_UNITS.values(), families)
    )


def starting_tier_one_rules(
    lines,
    starting_unit_ids,
    chaos_mode=False,
    standard_families=STANDARD_TIER_ONE_FAMILIES,
):
    """Make the seed's guaranteed Tier 1 combat roles immediately buildable."""
    selected_ids = {
        str(unit_id or '').upper()
        for unit_id in (starting_unit_ids or ())
        if unit_id
    }
    if not selected_ids:
        return {}

    records = map_house_records(lines)
    player_countries = _player_build_countries(lines, records)
    owners = ','.join(player_countries)
    rules = {}

    if chaos_mode:
        for role_units in TIER_ONE_ROLE_UNITS.values():
            for family, (tech_id, category) in role_units.items():
                if tech_id not in selected_ids:
                    continue
                values = {
                    'TechLevel': '1',
                    'Owner': owners,
                    'RequiredHouses': owners,
                    'ForbiddenHouses': 'none',
                }
                fallback = CHAOS_PRIMARY_PRODUCTION[family][category]
                values.update(_chaos_prerequisite_rules(category, fallback))
                rules[tech_id] = values
        return rules

    allowed_families = {
        str(family or '').lower()
        for family in standard_families
        if str(family or '').lower() in STANDARD_TIER_ONE_FAMILIES
    }
    selected_roles = {
        role
        for role, role_units in TIER_ONE_ROLE_UNITS.items()
        if selected_ids.intersection(tech_id for tech_id, _category in role_units.values())
    }
    available_categories = set()
    for building_id in _mission_production_buildings(lines, records):
        production = PRODUCTION_LOOKUP.get(building_id)
        if not production:
            continue
        family, category = production
        if family not in allowed_families:
            continue
        available_categories.add((family, category))
        if category == 'base':
            available_categories.add((family, 'infantry'))
            available_categories.add((family, 'vehicles'))

    for role in selected_roles:
        role_units = TIER_ONE_ROLE_UNITS[role]
        for family in STANDARD_TIER_ONE_FAMILIES:
            if family not in allowed_families:
                continue
            tech_id, category = role_units[family]
            if (family, category) not in available_categories:
                continue
            prerequisite = CHAOS_PRIMARY_PRODUCTION[family][category]
            rules[tech_id] = {
                'TechLevel': '1',
                'Owner': owners,
                'RequiredHouses': owners,
                'ForbiddenHouses': 'none',
                'PrerequisiteOverride': prerequisite,
            }
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

    rules = {}
    owners = ','.join(player_countries + ['MORPLAYER'])
    player_family = _player_family(lines, records)

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
            rules[tech_id.upper()] = {
                'TechLevel': tech_level,
                'Owner': owners,
                'RequiredHouses': owners,
                'ForbiddenHouses': 'none',
            }
            rules[tech_id.upper()].update(
                _chaos_prerequisite_rules(category, prerequisite)
            )
    for section, values in chaos_cameo_priority_rules(player_family).items():
        rules.setdefault(section, {}).update(values)
    return rules


def summarize_basic_unit_rules(rules):
    if not rules:
        return ''
    ordered = [tech_id for tech_id in TECH_ORDER if tech_id in rules]
    ordered.extend(sorted(tech_id for tech_id in rules if tech_id not in TECH_ORDER))
    return ', '.join(ordered)
