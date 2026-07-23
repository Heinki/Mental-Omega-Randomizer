"""Mission-local access translation for mixed campaign production.

The randomizer locks unit access globally, but campaign maps sometimes hand
the player another faction's production during the mission. Selected-faction
campaigns translate earned roles to that production; All Campaigns preserves
exact per-faction unlocks.
"""

from randomizer_map import (
    build_unit_usage_index,
    country_family,
    map_house_records,
    player_controlled_houses,
    player_house_from_map,
    player_transfer_houses,
    production_owner_countries,
    resolve_configured_helper_houses,
    unit_usage_houses,
    unsafe_country_houses,
)
from randomizer_ini import all_section_value_maps, section_lines
from randomizer_rewards import (
    BUFF_TARGETS,
    ENGINEER_UNIT_IDS,
    REWARD_POOL,
    unit_role_equivalents,
)
from randomizer_static_config import load_static_config


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
    """Prepare one installed Engineer cameo for any barracks the player gains."""
    sections = all_section_value_maps(lines)
    records = map_house_records(lines, sections=sections)
    production_families = []
    for building_id in _mission_production_buildings(
        lines,
        records,
        additional_production_houses,
    ):
        production = PRODUCTION_LOOKUP.get(building_id)
        if not production or production[1] not in {'base', 'infantry'}:
            continue
        family = production[0]
        if family not in production_families:
            production_families.append(family)

    special_barracks = list(_special_infantry_factories(sections))
    player_family = _player_family(lines, records)
    if chaos_mode:
        selected_family = (
            production_families[0]
            if production_families
            else player_family
        )
    else:
        selected_family = (
            player_family
            if player_family in production_families
            else (
                production_families[0]
                if production_families
                else player_family
            )
        )
    selected_id = ENGINEER_BY_FAMILY.get(selected_family)
    if not selected_id:
        return {}

    player_countries = safe_build_countries(
        lines,
        records,
        additional_build_houses,
    )
    owners = ','.join(
        production_owner_countries(lines, player_countries, sections=sections)
    )
    required_houses = ','.join(player_countries)
    prerequisites = _merged_items(
        (
            CHAOS_PRIMARY_PRODUCTION[family]['infantry']
            for family in production_families
            if family in CHAOS_PRIMARY_PRODUCTION
        ),
        special_barracks,
    )
    selected_rule = {
        'TechLevel': '1',
        'BuildLimit': None,
        'Owner': owners,
        'RequiredHouses': required_houses,
        'ForbiddenHouses': 'none',
    }
    selected_rule.update(
        _alternative_prerequisite_rules(prerequisites or ('BARRACKS',))
    )

    rules = {selected_id: selected_rule}
    section_by_upper = {
        str(section).upper(): values for section, values in sections.items()
    }
    for engineer_id in sorted(ENGINEER_UNIT_IDS - {selected_id}):
        # Hide redundant cameos from every player-controlled country without
        # BuildLimit=0, which could block an AI/scripted Engineer request.
        # Retain effective installed/map enemy exclusions on the original.
        map_values = section_by_upper.get(engineer_id, {})
        forbidden_value = (
            map_values.get('forbiddenhouses')
            if 'forbiddenhouses' in map_values
            else ENGINEER_INSTALLED_FORBIDDEN_HOUSES[engineer_id]
        )
        native_forbidden = [
            item
            for item in _comma_items(forbidden_value)
            if item.lower() not in {'none', '<none>'}
        ]
        rules[engineer_id] = {
            'ForbiddenHouses': ','.join(
                _merged_items(native_forbidden, player_countries)
            )
        }
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
        _comma_items(native_owners),
        production_owner_countries(
            lines, player_build_countries, sections=sections
        ),
    )
    required_houses = _merged_items(
        _comma_items(native_owners), player_build_countries
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

    for building_id in _mission_production_buildings(
        lines,
        house_records,
        additional_production_houses,
    ):
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
                prerequisite_alternatives=(prerequisite, *special_barracks),
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
                prerequisite_alternatives=(prerequisite, STALINS_FIST_FACTORY),
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
            prerequisite_override=prerequisite,
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

    rules = {
        'PrerequisiteOverride': 'none',
        'Prerequisite.List0': alternatives[0],
        'Prerequisite.Lists': str(max(0, len(alternatives) - 1)),
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
    if not chaos_mode:
        allowed_families.update(
            family
            for building_id in _mission_production_buildings(
                lines,
                records,
                additional_production_houses,
            )
            for family, category in [PRODUCTION_LOOKUP.get(building_id, ('', ''))]
            if family and category in {'base', 'naval'}
        )
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


def tier_one_unit_ids(families):
    """Return abstract Standard starter roles; launch maps resolve subfactions."""
    requested = {str(family or '').lower() for family in families}
    if not requested:
        return ()
    return tuple(TIER_ONE_ROLE_MARKERS[role] for role in TIER_ONE_ROLE_UNITS)


def tier_one_role_label(unit_or_marker):
    role = TIER_ONE_ROLE_BY_MARKER.get(str(unit_or_marker or '').upper())
    if not role:
        return ''
    return role.replace('_', ' ').title().replace('Anti Air', 'Anti-Air')


def _tier_one_variant_entries(role, family=None):
    entries = []
    default = TIER_ONE_ROLE_UNITS.get(role, {}).get(family) if family else None
    if default:
        entries.append(default)
    for country, entry in TIER_ONE_SUBFACTION_UNITS.get(role, {}).items():
        if family and country_family({'country': country}) != family:
            continue
        if entry not in entries:
            entries.append(entry)
    return entries


def expanded_tier_one_unit_ids(starting_unit_ids):
    """Expand Standard role markers without granting Chaos-only Foehn units."""
    expanded = set()
    for value in starting_unit_ids or ():
        unit_id = str(value or '').upper()
        role = TIER_ONE_ROLE_BY_MARKER.get(unit_id)
        if not role:
            if unit_id:
                expanded.add(unit_id)
            continue
        expanded.update(
            entry[0]
            for family in STANDARD_TIER_ONE_FAMILIES
            for entry in _tier_one_variant_entries(role, family)
        )
    return expanded


def _random_tier_one_variant(rng, role, family):
    variants = _tier_one_variant_entries(role, family)
    if not variants:
        return TIER_ONE_ROLE_UNITS[role][family][0]
    if len(variants) == 1:
        return variants[0][0]
    return rng.choice(variants)[0]


def random_chaos_tier_one_unit_ids(rng):
    """Assign every faction once on ground, plus one seeded basic aircraft."""
    families = list(STANDARD_TIER_ONE_FAMILIES) + ['foehn']
    rng.shuffle(families)
    units = [
        _random_tier_one_variant(rng, role, family)
        for role, family in zip(TIER_ONE_GROUND_ROLES, families)
    ]
    aircraft_family = rng.choice(STANDARD_TIER_ONE_FAMILIES)
    units.append(_random_tier_one_variant(rng, 'basic_aircraft', aircraft_family))
    return tuple(units)


def _selected_tier_one_roles(selected_ids):
    roles = {
        TIER_ONE_ROLE_BY_MARKER[unit_id]
        for unit_id in selected_ids
        if unit_id in TIER_ONE_ROLE_BY_MARKER
    }
    for role in TIER_ONE_ROLE_UNITS:
        variant_ids = {
            entry[0]
            for family in STANDARD_TIER_ONE_FAMILIES + ('foehn',)
            for entry in _tier_one_variant_entries(role, family)
        }
        if selected_ids.intersection(variant_ids):
            roles.add(role)
    return roles


def _standard_tier_one_entry(role, family, player_countries):
    configured = TIER_ONE_SUBFACTION_UNITS.get(role, {})
    by_lower = {country.lower(): entry for country, entry in configured.items()}
    for country in player_countries:
        entry = by_lower.get(str(country).lower())
        if entry and country_family({'country': country}) == family:
            return entry
    return TIER_ONE_ROLE_UNITS[role][family]


def _tier_one_airfield_rules(
    base_families,
    aircraft_families,
    owners,
    required_houses,
    chaos_mode=False,
):
    """Unlock required AircraftType factories only when base building exists."""
    base_families = {
        family for family in base_families if family in CHAOS_PRIMARY_PRODUCTION
    }
    if not base_families:
        return {}

    if chaos_mode:
        # Chaos aircraft may belong to another faction. Any detected MCV/
        # Construction Yard can therefore place the selected native airfield.
        conyards = tuple(
            CHAOS_PRIMARY_PRODUCTION[family]['base']
            for family in sorted(base_families)
        )
        airfield_families = set(aircraft_families)
    else:
        conyards = ()
        airfield_families = set(base_families).intersection(aircraft_families)

    rules = {}
    for family in sorted(airfield_families):
        airfield = TIER_ONE_AIRFIELDS.get(family)
        if not airfield:
            continue
        prerequisites = conyards or (CHAOS_PRIMARY_PRODUCTION[family]['base'],)
        values = {
            'TechLevel': '1',
            'BuildLimit': None,
            'Owner': owners,
            'RequiredHouses': required_houses,
            'ForbiddenHouses': 'none',
        }
        values.update(_alternative_prerequisite_rules(prerequisites))
        rules[airfield] = values
    return rules


def starting_tier_one_rules(
    lines,
    starting_unit_ids,
    chaos_mode=False,
    standard_families=STANDARD_TIER_ONE_FAMILIES,
    additional_build_houses=(),
    additional_production_houses=(),
):
    """Make the seed's guaranteed Tier 1 combat roles immediately buildable."""
    selected_ids = {
        str(unit_id or '').upper()
        for unit_id in (starting_unit_ids or ())
        if unit_id
    }
    if not selected_ids:
        return {}

    sections = all_section_value_maps(lines)
    records = map_house_records(lines, sections=sections)
    player_countries = safe_build_countries(lines, records, additional_build_houses)
    owners = ','.join(
        production_owner_countries(lines, player_countries, sections=sections)
    )
    required_houses = ','.join(player_countries)
    rules = {}

    production_categories = set()
    for building_id in _mission_production_buildings(
        lines,
        records,
        additional_production_houses,
    ):
        production = PRODUCTION_LOOKUP.get(building_id)
        if production:
            production_categories.add(production)
    base_families = {
        family for family, category in production_categories if category == 'base'
    }
    selected_roles = _selected_tier_one_roles(selected_ids)

    if chaos_mode:
        selected_aircraft_families = set()
        for role in TIER_ONE_ROLE_UNITS:
            if role not in selected_roles:
                continue
            for family in STANDARD_TIER_ONE_FAMILIES + ('foehn',):
                for tech_id, category in _tier_one_variant_entries(role, family):
                    if tech_id not in selected_ids:
                        continue
                    if category == 'air':
                        selected_aircraft_families.add(family)
                    values = {
                        'TechLevel': '1',
                        'Owner': owners,
                        'RequiredHouses': required_houses,
                        'ForbiddenHouses': 'none',
                    }
                    fallback = CHAOS_PRIMARY_PRODUCTION[family][category]
                    values.update(_chaos_prerequisite_rules(
                        category,
                        fallback,
                        _special_factory_alternatives(lines, category, sections),
                    ))
                    rules[tech_id] = values
        rules.update(_tier_one_airfield_rules(
            base_families,
            selected_aircraft_families,
            owners,
            required_houses,
            chaos_mode=True,
        ))
        return rules

    allowed_families = {
        str(family or '').lower()
        for family in standard_families
        if str(family or '').lower() in STANDARD_TIER_ONE_FAMILIES
    }
    available_categories = set()
    for family, category in production_categories:
        if family not in allowed_families:
            continue
        available_categories.add((family, category))
        if category == 'base':
            available_categories.add((family, 'infantry'))
            available_categories.add((family, 'vehicles'))
            available_categories.add((family, 'air'))

    for role in TIER_ONE_ROLE_UNITS:
        if role not in selected_roles:
            continue
        for family in STANDARD_TIER_ONE_FAMILIES:
            if family not in allowed_families:
                continue
            tech_id, category = _standard_tier_one_entry(
                role, family, player_countries
            )
            if (family, category) not in available_categories:
                continue
            prerequisite = CHAOS_PRIMARY_PRODUCTION[family][category]
            rules[tech_id] = {
                'TechLevel': '1',
                'Owner': owners,
                'RequiredHouses': required_houses,
                'ForbiddenHouses': 'none',
                'PrerequisiteOverride': prerequisite,
            }
    rules.update(_tier_one_airfield_rules(
        base_families.intersection(allowed_families),
        (
            TIER_ONE_ROLE_UNITS['basic_aircraft']
            if 'basic_aircraft' in selected_roles
            else ()
        ),
        owners,
        required_houses,
    ))
    return rules


def chaos_earned_access_rules(
    lines,
    earned_rewards,
    additional_build_houses=(),
    additional_production_houses=(),
):
    """Adapt every earned access item to player-controlled production."""
    player_houses = set(player_controlled_houses(lines))
    if not player_houses:
        player_house = player_house_from_map(lines)
        if player_house:
            player_houses.add(player_house)
    if not player_houses:
        return {}

    sections = all_section_value_maps(lines)
    records = map_house_records(lines, sections=sections)
    player_countries = safe_build_countries(lines, records, additional_build_houses)

    rules = {}
    owners = ','.join(
        production_owner_countries(lines, player_countries, sections=sections)
    )
    required_houses = ','.join(player_countries)
    player_family = _player_family(lines, records)
    special_alternatives = {
        category: _special_factory_alternatives(lines, category, sections)
        for category in ('base', 'infantry', 'vehicles', 'air', 'naval')
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
            rules[tech_id.upper()] = {
                'TechLevel': tech_level,
                'Owner': owners,
                'RequiredHouses': required_houses,
                'ForbiddenHouses': 'none',
            }
            rules[tech_id.upper()].update(
                _chaos_prerequisite_rules(
                    category,
                    prerequisite,
                    special_alternatives[category],
                )
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
