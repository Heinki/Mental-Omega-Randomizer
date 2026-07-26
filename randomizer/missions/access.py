"""Mission-local access translation for mixed campaign production.

The randomizer locks unit access globally, but campaign maps sometimes hand
the player another faction's production during the mission. Selected-faction
campaigns translate earned roles to that production; All Campaigns preserves
exact per-faction unlocks.
"""

from randomizer.core.collections import comma_items, unique_in_order

from randomizer.maps.rules import safe_engineer_identity_values
from randomizer.maps.houses import (
    country_family,
    map_house_records,
    player_controlled_houses,
    player_house_from_map,
    production_owner_countries,
    resolve_configured_helper_houses,
)
from randomizer.maps.ownership import (
    build_unit_usage_index,
    player_transfer_houses,
    unit_usage_houses,
    unsafe_country_houses,
)
from randomizer.maps.ini import all_section_value_maps, section_lines
from randomizer.rewards.catalogue import (
    BUFF_TARGETS,
    REWARD_POOL,
    unit_role_equivalents,
)
from randomizer.config.static import load_static_config


_FACTION_CONFIG = load_static_config('factions.json')
_TIER_ONE_CONFIG = load_static_config('tier_one.json')


ENGINEER_BY_FAMILY = dict(_FACTION_CONFIG['engineer_by_family'])
ENGINEER_INSTALLED_FORBIDDEN_HOUSES = dict(_FACTION_CONFIG['engineer_installed_forbidden_houses'])
CONYARD_BY_MCV = dict(_FACTION_CONFIG['conyard_by_mcv'])
STALINS_FIST_FACTORY = str(_FACTION_CONFIG['stalins_fist_factory'])
STALINS_FIST_PLACEMENT_IDS = set(_FACTION_CONFIG['stalins_fist_placement_ids'])
STALINS_FIST_TASKFORCE_IDS = set(_FACTION_CONFIG['stalins_fist_taskforce_ids'])
STALINS_FIST_FAMILIES = set(_FACTION_CONFIG['stalins_fist_families'])

# Five guaranteed combat roles for the optional seed-start roster. Standard
# translates each role to the physical production families present in a map.
# Chaos assigns every faction once across the four ground roles, then selects
# one true AircraftType from the three factions that own an airfield.
TIER_ONE_ROLE_UNITS = {
    role: {family: tuple(values) for family, values in families.items()}
    for role, families in _TIER_ONE_CONFIG['role_units'].items()
}
TIER_ONE_ROLE_MARKERS = dict(_TIER_ONE_CONFIG['role_markers'])
TIER_ONE_ROLE_BY_MARKER = {
    marker.upper(): role for role, marker in TIER_ONE_ROLE_MARKERS.items()
}
TIER_ONE_DEFENSE_MARKER = str(_TIER_ONE_CONFIG['defense_marker']).upper()
TIER_ONE_DEFENSE_ROLE_UNITS = {
    role: {
        family: str(unit_id).upper()
        for family, unit_id in families.items()
    }
    for role, families in _TIER_ONE_CONFIG['defense_role_units'].items()
}
TIER_ONE_DEFENSE_ROLES = tuple(_TIER_ONE_CONFIG['defense_roles'])
TIER_ONE_DEFENSE_UNITS = {
    family: tuple(str(unit_id).upper() for unit_id in unit_ids)
    for family, unit_ids in _TIER_ONE_CONFIG['defense_units'].items()
}
TIER_ONE_SUBFACTION_UNITS = {
    role: {country: tuple(values) for country, values in countries.items()}
    for role, countries in _TIER_ONE_CONFIG['subfaction_units'].items()
}
TIER_ONE_GROUND_ROLES = tuple(_TIER_ONE_CONFIG['ground_roles'])

STANDARD_TIER_ONE_FAMILIES = tuple(_TIER_ONE_CONFIG['standard_families'])

TIER_ONE_AIRFIELDS = dict(_TIER_ONE_CONFIG['airfields'])

AMPHIBIOUS_TRANSPORTS = {
    family: tuple(values)
    for family, values in _FACTION_CONFIG['amphibious_transports'].items()
}

PRODUCTION_BUILDINGS = {
    family: {category: set(ids) for category, ids in categories.items()}
    for family, categories in _FACTION_CONFIG['production_buildings'].items()
}
for family, categories in _TIER_ONE_CONFIG['production_aliases'].items():
    for category, aliases in categories.items():
        PRODUCTION_BUILDINGS.setdefault(family, {}).setdefault(category, set()).update(
            str(alias).upper() for alias in aliases
        )

# Physical factories used as the shared Chaos sidebar for each player faction.
# Some names in PRODUCTION_BUILDINGS (such as YURRAX and FOERAX) are generic
# prerequisite aliases, so keep the actual buildable structure explicit here.
CHAOS_PRIMARY_PRODUCTION = {
    family: dict(categories)
    for family, categories in _FACTION_CONFIG['chaos_primary_production'].items()
}

CHAOS_PRODUCTION_ALTERNATIVES = {
    category: tuple(
        categories[category]
        for categories in CHAOS_PRIMARY_PRODUCTION.values()
        if categories.get(category)
    )
    for category in ('base', 'infantry', 'vehicles', 'air', 'naval')
}

TECH_ORDER = list(_FACTION_CONFIG['tech_order'])


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
ACCESS_PREREQUISITES = {}


def _access_catalog():
    """Index access rewards by their target faction production category."""
    catalog = []
    seen = set()
    ACCESS_PREREQUISITES.clear()
    for reward in REWARD_POOL:
        if reward.get('kind') in {'buff', 'superweapon'}:
            continue
        for tech_id, values in reward.get('rules', {}).items():
            tech_id = tech_id.upper()
            tech_level = next(
                (str(value) for key, value in values.items() if key.lower() == 'techlevel'),
                '',
            )
            prerequisite_override = next(
                (
                    str(value).upper()
                    for key, value in values.items()
                    if key.lower() == 'prerequisiteoverride'
                ),
                '',
            )
            prerequisites = []
            if prerequisite_override and prerequisite_override != 'NONE':
                prerequisites.append(prerequisite_override)
            prerequisites.extend(
                str(value).upper()
                for key, value in values.items()
                if key.lower().startswith('prerequisite.list')
                and key.lower() != 'prerequisite.lists'
            )
            prerequisites = list(dict.fromkeys(prerequisites))
            if not tech_level or not prerequisites:
                continue
            ACCESS_PREREQUISITES[tech_id] = tuple(prerequisites)
            owner = next(
                (str(value) for key, value in values.items() if key.lower() == 'owner'),
                '',
            )
            for prerequisite in prerequisites:
                production = PRODUCTION_LOOKUP.get(prerequisite)
                if not production:
                    continue
                family, category = production
                key = (tech_id, family, category)
                if key in seen:
                    continue
                seen.add(key)
                catalog.append((tech_id, tech_level, family, category, prerequisite, owner))
    return catalog


ACCESS_CATALOG = _access_catalog()


def _native_access_prerequisites(tech_id, fallback):
    return ACCESS_PREREQUISITES.get(str(tech_id).upper(), (fallback,))


def _structure_owner_and_type(line):
    if '=' not in line:
        return None, None
    _, value = line.split('=', 1)
    parts = [part.strip() for part in value.split(',')]
    if len(parts) < 2:
        return None, None
    return parts[0], parts[1].upper()


def _mission_production_buildings(
    lines,
    house_records,
    additional_production_houses=(),
):
    """Yield production the player owns, receives, or captures by policy."""
    eligible_houses = set()
    configured_sources, _ = resolve_configured_helper_houses(
        house_records,
        additional_production_houses,
        (),
    )
    for house in (
        player_controlled_houses(lines, records=house_records)
        + player_transfer_houses(lines, records=house_records)
        + list(configured_sources)
    ):
        record = house_records.get(house, {})
        eligible_houses.update({
            house.lower(),
            house.replace(' House', '').lower(),
            str(record.get('country') or '').lower(),
        })
    eligible_houses.discard('')

    # Base-build missions often begin with an MCV rather than a deployed
    # Construction Yard. Player/scripted TaskForce ownership proves that this
    # production family can become available later in the mission.
    usage_index = build_unit_usage_index(lines)
    for mcv_id, conyard_id in CONYARD_BY_MCV.items():
        usage_aliases = set()
        for house in unit_usage_houses(lines, mcv_id, usage_index):
            record = house_records.get(house, {})
            usage_aliases.update({
                str(house).lower(),
                str(house).replace(' House', '').lower(),
                str(record.get('country') or '').lower(),
            })
        usage_aliases.discard('')
        if usage_aliases.intersection(eligible_houses):
            yield conyard_id

    for line in section_lines(lines, 'Structures'):
        owner, building_id = _structure_owner_and_type(line)
        if building_id and str(owner or '').lower() in eligible_houses:
            yield building_id

    # Several campaign missions, notably Epsilon 07, define the base the
    # player later operates only as numbered build nodes in a House section.
    # Those factories never appear in [Structures] in the source map.
    for house in house_records:
        record = house_records.get(house, {})
        aliases = {
            house.lower(),
            house.replace(' House', '').lower(),
            str(record.get('country') or '').lower(),
        }
        if not aliases.intersection(eligible_houses):
            continue
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


def _merged_items(*groups):
    return unique_in_order(item for group in groups for item in group)


def safe_build_countries(lines, house_records=None, additional_houses=()):
    """Return player countries plus safely isolated helper countries.

    The engine gates production by Country/HouseType, not by a campaign's
    runtime House instance. Player countries must remain present or earned
    access disappears. A helper country is added only when no denied active
    house shares it.
    """
    house_records = house_records or map_house_records(lines)
    player_houses = player_controlled_houses(lines, records=house_records)
    if not player_houses:
        player_house = player_house_from_map(lines, records=house_records)
        if player_house:
            player_houses = [player_house]
    helper_houses, _ = resolve_configured_helper_houses(
        house_records,
        additional_houses,
        player_houses,
    )
    allowed_houses = _merged_items(player_houses, helper_houses)
    usage_index = build_unit_usage_index(lines)
    countries = [
        house_records.get(house, {}).get('country') or house.replace(' House', '')
        for house in player_houses
    ]
    for house in helper_houses:
        country = house_records.get(house, {}).get('country') or house.replace(' House', '')
        if country and not unsafe_country_houses(
            lines,
            country,
            allowed_houses,
            records=house_records,
            usage_index=usage_index,
        ):
            countries.append(country)
    return _merged_items(countries, ['MORPLAYER'])


def _allowed_safety_families(player_family):
    if player_family == 'foehn':
        return {'allies', 'soviets'}
    if player_family in PRODUCTION_BUILDINGS:
        return set(PRODUCTION_BUILDINGS) - {player_family, 'foehn'}
    return set()


def _special_infantry_factories(sections):
    """Return map-local infantry factories outside known faction barracks."""
    return tuple(
        section.upper()
        for section, values in sections.items()
        if values.get('factory', '').lower() == 'infantrytype'
        and section.upper() not in PRODUCTION_LOOKUP
    )


def _map_provides_stalins_fist(lines, sections):
    for section in ('Units', 'Structures'):
        for line in section_lines(lines, section):
            if '=' not in line:
                continue
            parts = [part.strip().upper() for part in line.split('=', 1)[1].split(',')]
            if len(parts) >= 2 and parts[1] in STALINS_FIST_PLACEMENT_IDS:
                return True

    by_lower = {name.lower(): values for name, values in sections.items()}
    for taskforce_id in by_lower.get('taskforces', {}).values():
        for key, value in by_lower.get(taskforce_id.lower(), {}).items():
            if not key.isdigit():
                continue
            parts = [part.strip().upper() for part in value.split(',')]
            if len(parts) >= 2 and parts[1] in STALINS_FIST_TASKFORCE_IDS:
                return True
    return False


def _special_factory_alternatives(lines, category, sections=None):
    sections = sections if sections is not None else all_section_value_maps(lines)
    alternatives = []
    if category == 'vehicles' and _map_provides_stalins_fist(lines, sections):
        alternatives.append(STALINS_FIST_FACTORY)
    if category == 'infantry':
        alternatives.extend(_special_infantry_factories(sections))
    return tuple(alternatives)


def single_engineer_rules(
    lines,
    chaos_mode=False,
    additional_build_houses=(),
    additional_production_houses=(),
):
    """Prepare every faction Engineer behind its matching barracks."""
    sections = all_section_value_maps(lines)
    records = map_house_records(lines, sections=sections)
    special_barracks = list(_special_infantry_factories(sections))
    player_family = _player_family(lines, records)
    # Standard campaigns contain only the three original factions. Chaos also
    # installs Foehn's Engineer. A foreign Engineer remains
    # unavailable until the player captures or constructs that faction's
    # barracks, then appears without mission-specific capture allowlists.
    active_families = [
        family
        for family in ENGINEER_BY_FAMILY
        if chaos_mode or family != 'foehn'
    ]

    player_countries = safe_build_countries(
        lines,
        records,
        additional_build_houses,
    )
    player_owners = production_owner_countries(
        lines, player_countries, sections=sections
    )
    engineer_country_universe = _merged_items(*(
        comma_items(forbidden)
        for forbidden in ENGINEER_INSTALLED_FORBIDDEN_HOUSES.values()
    ))
    rules = {}
    for family in active_families:
        engineer_id = ENGINEER_BY_FAMILY.get(family)
        production = CHAOS_PRIMARY_PRODUCTION.get(family, {})
        native_barracks = production.get('infantry')
        if not engineer_id or not native_barracks:
            continue
        prerequisites = [native_barracks]
        # Map-local generic infantry factories serve the player's native
        # Engineer. Foreign captured barracks retain their own Engineer.
        if family == player_family:
            prerequisites.extend(special_barracks)
        forbidden_native_owners = {
            item.lower()
            for item in comma_items(
                ENGINEER_INSTALLED_FORBIDDEN_HOUSES[engineer_id]
            )
        }
        native_owners = [
            country
            for country in engineer_country_universe
            if country.lower() not in forbidden_native_owners
        ]
        rule = {
            'TechLevel': '1',
            'BuildLimit': None,
            'Owner': ','.join(_merged_items(
                native_owners, player_owners
            )),
            'RequiredHouses': ','.join(_merged_items(
                native_owners, player_countries
            )),
            'ForbiddenHouses': 'none',
        }
        # Every fallback must remain a normal Engineer. Some maps or stale
        # installed caches redefine one as a 1-health Chrono infantry.
        rule.update(safe_engineer_identity_values(
            BUFF_TARGETS[engineer_id], remove_unsafe=True
        ))
        rule.update(_alternative_prerequisite_rules(prerequisites))
        rules[engineer_id] = rule

    return rules


def _build_access_rule(
    lines,
    sections,
    player_build_countries,
    tech_level,
    native_owners,
    prerequisite_alternatives=(),
    prerequisite_override=None,
):
    """Build common ownership and prerequisite fields for earned access."""
    owners = _merged_items(
        comma_items(native_owners),
        production_owner_countries(
            lines, player_build_countries, sections=sections
        ),
    )
    required_houses = _merged_items(
        comma_items(native_owners), player_build_countries
    )
    rule = {
        'TechLevel': tech_level,
        'Owner': ','.join(owners),
        'RequiredHouses': ','.join(required_houses),
        'ForbiddenHouses': 'none',
    }
    if prerequisite_override is not None:
        rule['PrerequisiteOverride'] = prerequisite_override
    if prerequisite_alternatives:
        rule.update(_alternative_prerequisite_rules(prerequisite_alternatives))
    return rule


def mission_basic_unit_rules(
    lines,
    earned_access_ids=None,
    translate_equivalents=False,
    additional_build_houses=(),
    additional_production_houses=(),
):
    """Return off-faction access needed by mixed mission production.

    All-Campaign seeds preserve exact earned unit IDs for each physical
    production family. A selected single-faction campaign translates earned
    access into role-equivalent units for foreign production. Exactly one
    faction-appropriate Engineer remains a base-operation essential.
    """
    sections = all_section_value_maps(lines)
    house_records = map_house_records(lines, sections=sections)
    unlocks = []
    production_categories = set()
    earned_access_ids = {str(unit_id).upper() for unit_id in (earned_access_ids or [])}

    player_family = _player_family(lines, house_records)
    allowed_families = _allowed_safety_families(player_family)

    production_buildings = list(_mission_production_buildings(
        lines,
        house_records,
        additional_production_houses,
    ))
    # Any placed foreign factory can become player-owned through an Engineer.
    # Its prerequisite keeps access dormant until capture. All Campaigns
    # exposes only exact earned IDs; selected single campaigns translate an
    # earned role to that factory family's equivalent below.
    production_buildings.extend(
        building_id
        for line in section_lines(lines, 'Structures')
        for _owner, building_id in [_structure_owner_and_type(line)]
        if building_id
    )

    for building_id in _merged_items(production_buildings):
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

    expanded_categories = set(production_categories)
    for family, category in production_categories:
        if category == 'base':
            expanded_categories.update(
                (family, production_category)
                for production_category in PRODUCTION_BUILDINGS[family]
                if production_category != 'base'
            )

    available_access = earned_access_ids
    player_build_countries = safe_build_countries(
        lines,
        house_records,
        additional_build_houses,
    )

    # Special map-local barracks intentionally share every exact unlocked
    # infantry type, regardless of faction. Keep each unit's native barracks as
    # an alternative so this map rule never removes ordinary production.
    special_barracks = _special_infantry_factories(sections)
    if special_barracks:
        for tech_id, tech_level, _family, category, prerequisite, native_owners in ACCESS_CATALOG:
            if category != 'infantry' or tech_id not in available_access:
                continue
            access_rule = _build_access_rule(
                lines,
                sections,
                player_build_countries,
                tech_level,
                native_owners,
                prerequisite_alternatives=(
                    *_native_access_prerequisites(tech_id, prerequisite),
                    *special_barracks,
                ),
            )
            unlocks.append((tech_id, tech_level, access_rule))

    # Stalin's Fist is physically Soviet but serves the current Soviet or
    # Epsilon mission faction. Standard exposes only exact unlocked vehicles
    # from that corresponding family.
    if (
        player_family in STALINS_FIST_FAMILIES
        and _map_provides_stalins_fist(lines, sections)
    ):
        for tech_id, tech_level, family, category, prerequisite, native_owners in ACCESS_CATALOG:
            if (
                family != player_family
                or category != 'vehicles'
                or tech_id not in available_access
            ):
                continue
            access_rule = _build_access_rule(
                lines,
                sections,
                player_build_countries,
                tech_level,
                native_owners,
                prerequisite_alternatives=(
                    *_native_access_prerequisites(tech_id, prerequisite),
                    STALINS_FIST_FACTORY,
                ),
            )
            unlocks.append((tech_id, tech_level, access_rule))

    for tech_id, tech_level, family, category, prerequisite, native_owners in ACCESS_CATALOG:
        if (family, category) not in expanded_categories:
            continue
        has_access = (
            bool(unit_role_equivalents(tech_id).intersection(available_access))
            if translate_equivalents
            else tech_id in available_access
        )
        if not has_access:
            continue
        access_rule = _build_access_rule(
            lines,
            sections,
            player_build_countries,
            tech_level,
            native_owners,
            prerequisite_alternatives=_native_access_prerequisites(
                tech_id, prerequisite
            ),
        )
        unlocks.append((tech_id, tech_level, access_rule))

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
    for section, values in single_engineer_rules(
        lines,
        additional_build_houses=additional_build_houses,
        additional_production_houses=additional_production_houses,
    ).items():
        rules[section] = values
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
        if target.get('category') == 'special_buildings':
            rules[tech_id] = {
                'CameoPriority': str(target.get('cameo_priority', -1000))
            }
            continue
        factions = target.get('factions') or []
        if len(factions) != 1:
            continue
        faction = str(factions[0]).lower()
        if faction in priorities:
            rules[tech_id] = {'CameoPriority': str(priorities[faction])}

    return rules


def _alternative_prerequisite_rules(alternatives):
    alternatives = _merged_items(alternatives)
    if not alternatives:
        return {}
    if len(alternatives) == 1:
        # Standard captured-factory access must remain gated by that exact
        # faction building. A concrete override also survives player-clone
        # generation; `none` plus List0 was stripped from cloned units and
        # could expose Allied peers before an Allied factory was captured.
        return {'PrerequisiteOverride': alternatives[0]}

    rules = {
        'PrerequisiteOverride': 'none',
        'Prerequisite.List0': alternatives[0],
        'Prerequisite.Lists': str(len(alternatives)),
    }
    for index, building_id in enumerate(alternatives[1:], start=1):
        rules[f'Prerequisite.List{index}'] = building_id
    return rules


def _chaos_prerequisite_rules(category, fallback, extra_alternatives=()):
    """Allow an earned item from the matching factory of any faction."""
    alternatives = list(CHAOS_PRODUCTION_ALTERNATIVES.get(category, ()))
    if not alternatives and fallback:
        alternatives = [fallback]
    alternatives.extend(extra_alternatives)
    return _alternative_prerequisite_rules(alternatives)


def always_available_transport_rules(
    lines,
    chaos_mode=False,
    additional_build_houses=(),
    additional_production_houses=(),
):
    """Make relevant amphibious transports immediately buildable."""
    sections = all_section_value_maps(lines)
    records = map_house_records(lines, sections=sections)
    player_countries = safe_build_countries(
        lines, records, additional_build_houses
    )
    owners = ','.join(
        production_owner_countries(lines, player_countries, sections=sections)
    )
    required_houses = ','.join(player_countries)
    allowed_families = set(AMPHIBIOUS_TRANSPORTS) if chaos_mode else {
        _player_family(lines, records)
    }
    rules = {}
    for family, (tech_id, prerequisite) in AMPHIBIOUS_TRANSPORTS.items():
        if family not in allowed_families:
            continue
        values = {
            'TechLevel': '1',
            'Owner': owners,
            'RequiredHouses': required_houses,
            'ForbiddenHouses': 'none',
        }
        if chaos_mode:
            values.update(_chaos_prerequisite_rules('naval', prerequisite))
        else:
            values['PrerequisiteOverride'] = prerequisite
        rules[tech_id] = values
    return rules


def summarize_basic_unit_rules(rules):
    if not rules:
        return ''
    ordered = [tech_id for tech_id in TECH_ORDER if tech_id in rules]
    ordered.extend(sorted(tech_id for tech_id in rules if tech_id not in TECH_ORDER))
    return ', '.join(ordered)
