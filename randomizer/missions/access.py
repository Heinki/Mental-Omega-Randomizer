"""Mode-specific access rules for campaign production.

Standard keeps each faction behind its physical production. Chaos instead
shares unlocked units across every compatible production building category.
Keep those policies separate: Standard capture translation must never become
the filter for Chaos access.
"""

from functools import lru_cache

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
from randomizer.maps.ini import (
    all_section_value_maps,
    parse_action_groups,
    section_lines,
)
from randomizer.rewards.catalogue import (
    BUFF_TARGETS,
    FACTION_DEFENSE_ROSTERS,
    FACTION_UNIT_ROSTERS,
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

MINERS = {
    family: tuple(values)
    for family, values in _FACTION_CONFIG['miners'].items()
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
    # Import at call time. During the maps/rewards import cycle the facade
    # temporarily exposes an empty placeholder which is later replaced, so a
    # module-level imported reference can remain permanently stale.
    from randomizer.rewards.catalogue import REWARD_POOL

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
            prerequisites = []
            for key, value in values.items():
                lowered = key.lower()
                if not (
                    lowered in {'prerequisite', 'prerequisiteoverride'}
                    or (
                        lowered.startswith('prerequisite.list')
                        and lowered != 'prerequisite.lists'
                    )
                ):
                    continue
                prerequisites.extend(
                    item.upper()
                    for item in comma_items(value)
                    if item.strip().upper() not in {'NONE', '<NONE>'}
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


ACCESS_CATALOG = []


def access_catalog():
    """Return the access index after reward-module initialization completes.

    ``missions.access`` participates in the maps/rewards import cycle. Building
    this index eagerly can observe the public reward facade before
    ``REWARD_POOL`` is populated and permanently freeze an empty catalogue.
    Launch-time access resolution is safely past that cycle, so populate once
    on first real use.
    """
    if not ACCESS_CATALOG:
        ACCESS_CATALOG.extend(_access_catalog())
    return ACCESS_CATALOG


def _native_access_prerequisites(tech_id, fallback):
    access_catalog()
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
    include_capturable=False,
):
    """Yield current, transferred, configured, or potentially captured production."""
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
        mcv_houses = unit_usage_houses(lines, mcv_id, usage_index)
        usage_aliases = set()
        for house in mcv_houses:
            record = house_records.get(house, {})
            usage_aliases.update({
                str(house).lower(),
                str(house).replace(' House', '').lower(),
                str(record.get('country') or '').lower(),
            })
        usage_aliases.discard('')
        if (
            usage_aliases.intersection(eligible_houses)
            or (include_capturable and mcv_houses)
        ):
            yield conyard_id

    for line in section_lines(lines, 'Structures'):
        owner, building_id = _structure_owner_and_type(line)
        if building_id and (
            str(owner or '').lower() in eligible_houses
            or (
                include_capturable
                and building_id in PRODUCTION_LOOKUP
            )
        ):
            yield building_id

    if include_capturable:
        # Action 125 creates a BuildingType at a waypoint. Campaign openings
        # and capture objectives can therefore provide a factory that has no
        # source-map [Structures] entry. Preparing its matching T1 rules is
        # safe: the exact building prerequisite stays unsatisfied until the
        # player actually receives or captures that structure.
        for line in section_lines(lines, 'Actions'):
            if '=' not in line:
                continue
            _, value = line.split('=', 1)
            _, groups = parse_action_groups(value)
            for group in groups:
                if len(group) < 3 or group[0] != '125':
                    continue
                building_id = group[2].strip().upper()
                if building_id in PRODUCTION_LOOKUP:
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


def mission_production_families(
    lines,
    house_records=None,
    additional_production_houses=(),
    include_capturable=True,
):
    """Return faction families backed by physical or scripted production."""
    records = house_records or map_house_records(lines)
    return {
        family
        for building_id in _mission_production_buildings(
            lines,
            records,
            additional_production_houses,
            include_capturable=include_capturable,
        )
        for production in (PRODUCTION_LOOKUP.get(building_id),)
        if production
        for family in (production[0],)
    }


def mission_production_buildings(
    lines,
    house_records=None,
    additional_production_houses=(),
    include_capturable=True,
):
    """Return exact physical/scripted production types relevant to a mission."""
    records = house_records or map_house_records(lines)
    return tuple(unique_in_order(_mission_production_buildings(
        lines,
        records,
        additional_production_houses,
        include_capturable=include_capturable,
    )))


def chaos_production_alternatives(
    lines,
    house_records=None,
    additional_production_houses=(),
):
    """Return shared Chaos factories plus exact compatible map variants.

    Installed AI factory variants such as GAPILEB and GAWEAPB are distinct
    prerequisite identities even though they share the normal building image
    and production category.  Keep the four primary faction factories, then
    add every compatible physical or scripted type detected on this map so a
    captured variant exposes the same Chaos roster.
    """
    records = house_records or map_house_records(lines)
    alternatives = {
        category: list(building_ids)
        for category, building_ids in CHAOS_PRODUCTION_ALTERNATIVES.items()
    }
    for building_id in _mission_production_buildings(
        lines,
        records,
        additional_production_houses,
        include_capturable=True,
    ):
        production = PRODUCTION_LOOKUP.get(building_id)
        if not production:
            continue
        _family, category = production
        alternatives.setdefault(category, []).append(building_id)
    return {
        category: tuple(unique_in_order(building_ids))
        for category, building_ids in alternatives.items()
    }


def _player_family(lines, house_records):
    player_house = player_house_from_map(lines)
    if not player_house:
        return ''
    return country_family(house_records.get(player_house, {}))


def _merged_items(*groups):
    return unique_in_order(item for group in groups for item in group)


def merged_production_owners(*owner_values):
    """Merge comma-separated Owner values without changing their order."""
    return ','.join(unique_in_order(
        owner
        for value in owner_values
        for owner in comma_items(value)
    ))


@lru_cache(maxsize=None)
def _chaos_category_owner_ids(category_key):
    categories = set(category_key)
    return tuple(unique_in_order(
        owner
        for _tech_id, _level, _family, category, _prerequisite, owners
        in access_catalog()
        if category in categories
        for owner in comma_items(owners)
    ))


def chaos_category_owner_ids(categories):
    """Return native countries behind each shared Chaos production category.

    Captured factories check both their prerequisite identity and whether
    their native Owner list overlaps the produced TechnoType's Owner list.
    Derive the country roster from existing access data instead of maintaining
    a second faction-country mapping.
    """
    category_key = tuple(sorted({
        str(category) for category in categories if category
    }))
    return _chaos_category_owner_ids(category_key)


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
    if player_family in PRODUCTION_BUILDINGS:
        # Role translation applies to the current production family too. An
        # Allied role reward used on a Soviet-start mission must resolve to the
        # Soviet peer behind NAHAND/NAWEAP, just as a later captured Allied,
        # Epsilon, or Foehn factory resolves to its own peer.
        return set(PRODUCTION_BUILDINGS)
    return set()


def _special_infantry_factories(sections, excluded_factory_ids=()):
    """Return map-local infantry factories outside known faction barracks."""
    excluded = {
        str(factory_id).strip().upper()
        for factory_id in excluded_factory_ids
        if str(factory_id).strip()
    }
    return tuple(
        section.upper()
        for section, values in sections.items()
        if values.get('factory', '').lower() == 'infantrytype'
        and section.upper() not in PRODUCTION_LOOKUP
        and section.upper() not in excluded
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


def _special_factory_alternatives(
    lines,
    category,
    sections=None,
    excluded_infantry_factory_ids=(),
):
    sections = sections if sections is not None else all_section_value_maps(lines)
    alternatives = []
    if category == 'vehicles' and _map_provides_stalins_fist(lines, sections):
        alternatives.append(STALINS_FIST_FACTORY)
    if category == 'infantry':
        alternatives.extend(_special_infantry_factories(
            sections,
            excluded_infantry_factory_ids,
        ))
    return tuple(alternatives)


def single_engineer_rules(
    lines,
    chaos_mode=False,
    additional_build_houses=(),
    excluded_special_infantry_factories=(),
):
    """Prepare exactly one faction-appropriate Engineer."""
    sections = all_section_value_maps(lines)
    records = map_house_records(lines, sections=sections)
    special_barracks = list(_special_infantry_factories(
        sections,
        excluded_special_infantry_factories,
    ))
    player_family = _player_family(lines, records)
    # Engineers are a base-operation essential, not captured-tech rewards.
    # Installing one clone per physically reachable faction made every Chaos
    # barracks expose four Engineer cameos. It also let a mission-granted
    # allied barracks look like captured technology when its authored initial
    # owner differed from the player House. Prefer the player's own family;
    # only fall back when that family has no usable Engineer definition.
    available_families = (
        set(ENGINEER_BY_FAMILY)
        if chaos_mode
        else mission_production_families(
            lines,
            house_records=records,
            include_capturable=True,
        )
    )
    chaos_alternatives = (
        chaos_production_alternatives(lines, house_records=records)
        if chaos_mode else {}
    )
    ordered_families = unique_in_order((
        player_family,
        *ENGINEER_BY_FAMILY,
    ))
    active_families = next((
        [family]
        for family in ordered_families
        if family in available_families and ENGINEER_BY_FAMILY.get(family)
    ), [])

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
        if chaos_mode:
            rule.update(_chaos_prerequisite_rules(
                'infantry',
                native_barracks,
                special_barracks,
                production_alternatives=chaos_alternatives,
            ))
        else:
            rule.update(_standard_prerequisite_rules(
                native_barracks,
                special_barracks if family == player_family else (),
            ))
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
    excluded_special_infantry_factories=(),
):
    """Resolve earned identities against physically available production.

    Exact access stays exact unless a caller explicitly requests legacy role
    translation. Foreign identities remain dormant until their Barracks, War
    Factory, airfield, or naval factory is owned. Exactly one
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
        include_capturable=True,
    ))
    # Any placed factory can become player-owned through an Engineer. Its exact
    # prerequisite keeps foreign access dormant until capture, while the
    # starting faction's matching factory activates its own equivalent.
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

    # A map-local generic Barracks follows the current Standard player family.
    # It may expose an exact unlocked infantry identity, but must not expose
    # unrelated faction rewards before foreign production capture.
    special_barracks = _special_infantry_factories(
        sections,
        excluded_special_infantry_factories,
    )
    if special_barracks:
        for tech_id, tech_level, family, category, prerequisite, native_owners in access_catalog():
            has_access = (
                bool(unit_role_equivalents(tech_id).intersection(available_access))
                if translate_equivalents
                else tech_id in available_access
            )
            if (
                category != 'infantry'
                or family != player_family
                or not has_access
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
        for tech_id, tech_level, family, category, prerequisite, native_owners in access_catalog():
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

    for tech_id, tech_level, family, category, prerequisite, native_owners in access_catalog():
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
        chaos_mode=False,
        additional_build_houses=additional_build_houses,
        excluded_special_infantry_factories=(
            excluded_special_infantry_factories
        ),
    ).items():
        rules[section] = values
    return rules


def chaos_cameo_priority_rules(player_family):
    """Keep Chaos sidebars in stable faction and roster order."""
    faction_order = ['allies', 'soviets', 'epsilon', 'foehn']
    player_family = str(player_family or '').lower()
    if player_family in faction_order:
        faction_order.remove(player_family)
        faction_order.insert(0, player_family)
    faction_priorities = {
        faction: (len(faction_order) - index) * 1_000
        for index, faction in enumerate(faction_order)
    }

    # Equal faction-wide priorities only formed broad blocks. Map-local clone
    # registrations follow earned reward/buff order, so ties made every launch
    # shuffle units inside those blocks. Rank each production tab by committed
    # roster order; reviewed extras naturally remain where that roster places
    # them. Large faction bands keep all ranks from crossing into another side.
    ordered_ids = {}
    for faction, categories in FACTION_UNIT_ROSTERS.items():
        faction_key = str(faction).lower()
        ordered_ids[(faction_key, 'infantry')] = list(
            categories.get('infantry', {})
        )
        ordered_ids[(faction_key, 'units')] = [
            *categories.get('units', {}),
            *categories.get('aircraft', {}),
        ]
        ordered_ids[(faction_key, 'buildings')] = list(
            FACTION_DEFENSE_ROSTERS.get(faction, {})
        )
    ranks = {
        (faction, sidebar, str(unit_id).upper()): rank
        for (faction, sidebar), unit_ids in ordered_ids.items()
        for rank, unit_id in enumerate(unit_ids)
    }
    next_rank = {
        key: len(unit_ids) for key, unit_ids in ordered_ids.items()
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
        category = str(target.get('category') or '').lower()
        sidebar = {
            'infantry': 'infantry',
            'units': 'units',
            'aircraft': 'units',
            'defenses': 'buildings',
        }.get(category)
        if faction not in faction_priorities or not sidebar:
            continue
        rank_key = (faction, sidebar, str(tech_id).upper())
        rank = ranks.get(rank_key)
        if rank is None:
            group_key = (faction, sidebar)
            rank = next_rank.get(group_key, 0)
            next_rank[group_key] = rank + 1
        rules[tech_id] = {
            'CameoPriority': str(faction_priorities[faction] - rank)
        }

    return rules


def _alternative_prerequisite_rules(alternatives):
    alternatives = _merged_items(alternatives)
    if not alternatives:
        return {}
    if len(alternatives) == 1:
        # This is the complete exact gate, not an escape hatch from another
        # prerequisite. Keep it on the normal field so map-local clones cannot
        # inherit or trigger broad PrerequisiteOverride behavior.
        return {
            'Prerequisite': alternatives[0],
            'PrerequisiteOverride': None,
            'Prerequisite.List0': None,
            'Prerequisite.Lists': None,
        }

    # Ares counts only the extra, 1-based lists. The normal Prerequisite is
    # the first path; List1..ListN are the alternatives. Using List0..ListN
    # with Lists=len(alternatives) created one missing, therefore empty, list.
    # An empty list is always satisfied and broke physical-factory gating.
    rules = {
        'Prerequisite': alternatives[0],
        'PrerequisiteOverride': None,
        'Prerequisite.List0': None,
        'Prerequisite.Lists': str(len(alternatives) - 1),
    }
    for index, building_id in enumerate(alternatives[1:], start=1):
        rules[f'Prerequisite.List{index}'] = building_id
    return rules


def _chaos_prerequisite_rules(
    category,
    fallback,
    extra_alternatives=(),
    production_alternatives=None,
):
    """Allow a Chaos item from every compatible faction factory."""
    production_alternatives = (
        CHAOS_PRODUCTION_ALTERNATIVES
        if production_alternatives is None
        else production_alternatives
    )
    alternatives = list(production_alternatives.get(category, ()))
    if not alternatives and fallback:
        alternatives.append(fallback)
    alternatives.extend(extra_alternatives)
    return _alternative_prerequisite_rules(alternatives)


def _standard_prerequisite_rules(fallback, extra_alternatives=()):
    """Keep Standard access behind its exact faction production."""
    alternatives = [fallback] if fallback else []
    alternatives.extend(extra_alternatives)
    return _alternative_prerequisite_rules(alternatives)


def always_available_transport_rules(
    lines,
    chaos_mode=False,
    additional_build_houses=(),
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
    allowed_families = (
        set(AMPHIBIOUS_TRANSPORTS)
        if chaos_mode
        else mission_production_families(
            lines,
            house_records=records,
            include_capturable=True,
        )
    )
    chaos_alternatives = (
        chaos_production_alternatives(lines, house_records=records)
        if chaos_mode else {}
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
            values.update(_chaos_prerequisite_rules(
                'naval',
                prerequisite,
                production_alternatives=chaos_alternatives,
            ))
        else:
            values.update(_standard_prerequisite_rules(prerequisite))
        rules[tech_id] = values
    return rules


def always_available_miner_rules(lines, additional_build_houses=()):
    """Prepare one player-owned clone for every faction miner.

    Original refinery identities remain in use, but their ``FreeUnit`` field
    is retargeted to the matching player clone at final map generation.  The
    native miner can therefore be hidden with the same production gate as every
    other cloned unit without suppressing the refinery spawn or exposing two
    equivalent factory cameos.
    """
    sections = all_section_value_maps(lines)
    records = map_house_records(lines, sections=sections)
    player_countries = safe_build_countries(
        lines, records, additional_build_houses
    )
    owners = ','.join(
        production_owner_countries(lines, player_countries, sections=sections)
    )
    required_houses = ','.join(player_countries)
    rules = {}
    for family, (tech_id, factory_id, refinery_id) in MINERS.items():
        rules[tech_id] = {
            'TechLevel': '1',
            'Owner': owners,
            'RequiredHouses': required_houses,
            'ForbiddenHouses': 'none',
            'FactoryOwners': None,
            'FactoryOwners.Forbidden': None,
            # PrerequisiteOverride is satisfied by *any one* listed building.
            # A normal prerequisite list requires both exact faction
            # buildings, so foreign miners appear only after both structures
            # are captured (or constructed).
            'Prerequisite': f'{factory_id},{refinery_id}',
            'PrerequisiteOverride': None,
            'Prerequisite.Lists': None,
            'Prerequisite.List0': None,
            'Prerequisite.StolenTechs': None,
        }
    return rules


def original_mcv_access_rules(
    lines,
    mcv_ids,
    additional_build_houses=(),
):
    """Expose configured native MCVs for the exact mission player only."""
    sections = all_section_value_maps(lines)
    records = map_house_records(lines, sections=sections)
    player_countries = safe_build_countries(
        lines, records, additional_build_houses
    )
    owners = ','.join(
        production_owner_countries(lines, player_countries, sections=sections)
    )
    required_houses = ','.join(player_countries)
    return {
        str(mcv_id).upper(): {
            'TechLevel': '1',
            'Owner': owners,
            'RequiredHouses': required_houses,
            'ForbiddenHouses': 'none',
            'FactoryOwners': None,
            'FactoryOwners.Forbidden': None,
        }
        for mcv_id in unique_in_order(
            str(value).strip().upper() for value in (mcv_ids or ())
        )
        if mcv_id
    }


def summarize_basic_unit_rules(rules):
    if not rules:
        return ''
    ordered = [tech_id for tech_id in TECH_ORDER if tech_id in rules]
    ordered.extend(sorted(tech_id for tech_id in rules if tech_id not in TECH_ORDER))
    return ', '.join(ordered)
