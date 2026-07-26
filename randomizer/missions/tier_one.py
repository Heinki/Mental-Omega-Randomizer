"""Tier-one starter selection and mission-local access rules."""

from .access import (
    ACCESS_CATALOG,
    CHAOS_PRIMARY_PRODUCTION,
    CHAOS_PRODUCTION_ALTERNATIVES,
    PRODUCTION_LOOKUP,
    STANDARD_TIER_ONE_FAMILIES,
    TIER_ONE_AIRFIELDS,
    TIER_ONE_DEFENSE_MARKER,
    TIER_ONE_DEFENSE_ROLES,
    TIER_ONE_DEFENSE_ROLE_UNITS,
    TIER_ONE_DEFENSE_UNITS,
    TIER_ONE_GROUND_ROLES,
    TIER_ONE_ROLE_BY_MARKER,
    TIER_ONE_ROLE_MARKERS,
    TIER_ONE_ROLE_UNITS,
    TIER_ONE_SUBFACTION_UNITS,
    _alternative_prerequisite_rules,
    _build_access_rule,
    _chaos_prerequisite_rules,
    _mission_production_buildings,
    _player_family,
    _special_factory_alternatives,
    all_section_value_maps,
    chaos_cameo_priority_rules,
    country_family,
    map_house_records,
    player_controlled_houses,
    player_house_from_map,
    production_owner_countries,
    safe_build_countries,
)

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

def tier_one_defense_ids(families):
    """Return the abstract starter-defense marker for eligible seed pools."""
    requested = {str(family or '').lower() for family in families}
    return (TIER_ONE_DEFENSE_MARKER,) if requested else ()

def expanded_tier_one_defense_ids(
    starting_defense_ids,
    include_foehn=False,
    families=None,
):
    """Expand the saved defense marker to concrete construction identities."""
    available_families = [
        str(family or '').lower()
        for family in (
            STANDARD_TIER_ONE_FAMILIES if families is None else families
        )
        if str(family or '').lower() in STANDARD_TIER_ONE_FAMILIES
    ]
    if include_foehn:
        available_families.append('foehn')
    available_ids = {
        unit_id
        for family in available_families
        for unit_id in TIER_ONE_DEFENSE_UNITS.get(family, ())
    }
    expanded = set()
    for value in starting_defense_ids or ():
        unit_id = str(value or '').upper()
        if unit_id == TIER_ONE_DEFENSE_MARKER:
            expanded.update(available_ids)
        elif unit_id in available_ids:
            expanded.add(unit_id)
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

def random_chaos_tier_one_defense_ids(rng):
    """Select one ground and one anti-air defense from distinct factions."""
    families = list(STANDARD_TIER_ONE_FAMILIES) + ['foehn']
    rng.shuffle(families)
    return tuple(
        TIER_ONE_DEFENSE_ROLE_UNITS[role][family]
        for role, family in zip(TIER_ONE_DEFENSE_ROLES, families)
    )

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
        # Foreign Chaos aircraft already accept any matching AircraftType
        # factory. Unlock the player's native airfield, never the aircraft's
        # foreign airfield (for example YAAIRF in an Allied base).
        conyards = ()
        airfield_families = set(base_families) if aircraft_families else set()
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

def starting_tier_one_defense_rules(
    lines,
    starting_defense_ids,
    chaos_mode=False,
    standard_families=STANDARD_TIER_ONE_FAMILIES,
    additional_build_houses=(),
    additional_production_houses=(),
    excluded_unit_ids=(),
    allow_player_family_fallback=False,
):
    """Make basic ground/anti-air defenses available behind matching yards."""
    selected_ids = {
        str(unit_id or '').upper()
        for unit_id in (starting_defense_ids or ())
        if unit_id
    }
    if not selected_ids:
        return {}
    excluded_ids = {
        str(unit_id or '').upper()
        for unit_id in (excluded_unit_ids or ())
        if unit_id
    }
    marker_selected = TIER_ONE_DEFENSE_MARKER in selected_ids

    sections = all_section_value_maps(lines)
    records = map_house_records(lines, sections=sections)
    player_countries = safe_build_countries(lines, records, additional_build_houses)
    rules = {}

    if chaos_mode:
        eligible_families = tuple(TIER_ONE_DEFENSE_UNITS)
    else:
        allowed_families = {
            str(family or '').lower()
            for family in standard_families
            if str(family or '').lower() in STANDARD_TIER_ONE_FAMILIES
        }
        production_categories = {
            PRODUCTION_LOOKUP[building_id]
            for building_id in _mission_production_buildings(
                lines,
                records,
                additional_production_houses,
            )
            if building_id in PRODUCTION_LOOKUP
        }
        base_families = {
            family for family, category in production_categories
            if category == 'base'
        }
        if not base_families and allow_player_family_fallback:
            # Many ordinary campaign base missions spawn or transfer the MCV
            # only after scripted opening events. Their source map therefore
            # has no physical Construction Yard to detect at launch. Falling
            # back to the current player house family exposes the matching
            # defense behind that family's yard without granting another
            # faction's structures.
            player_families = {
                country_family(records.get(house, {}))
                for house in player_controlled_houses(lines, records=records)
            }
            base_families.update(player_families.intersection(allowed_families))
            if not base_families:
                base_families.update(
                    family
                    for family, _category in production_categories
                    if family in allowed_families
                )
        eligible_families = tuple(
            family
            for family in STANDARD_TIER_ONE_FAMILIES
            if family in allowed_families and family in base_families
        )

    catalog_by_id = {
        tech_id: (tech_level, family, category, prerequisite, native_owners)
        for tech_id, tech_level, family, category, prerequisite, native_owners
        in ACCESS_CATALOG
        if tech_id in {
            starter_id
            for family_ids in TIER_ONE_DEFENSE_UNITS.values()
            for starter_id in family_ids
        }
        and category == 'base'
    }
    for family in eligible_families:
        for tech_id in TIER_ONE_DEFENSE_UNITS.get(family, ()):
            if tech_id in excluded_ids:
                continue
            if not marker_selected and tech_id not in selected_ids:
                continue
            catalog_entry = catalog_by_id.get(tech_id)
            if not catalog_entry:
                continue
            tech_level, _native_family, _category, prerequisite, native_owners = (
                catalog_entry
            )
            if chaos_mode:
                rules[tech_id] = _build_access_rule(
                    lines,
                    sections,
                    player_countries,
                    tech_level,
                    native_owners,
                    prerequisite_alternatives=CHAOS_PRODUCTION_ALTERNATIVES['base'],
                )
            else:
                rules[tech_id] = _build_access_rule(
                    lines,
                    sections,
                    player_countries,
                    tech_level,
                    native_owners,
                    prerequisite_override=prerequisite,
                )
    return rules

def starting_tier_one_rules(
    lines,
    starting_unit_ids,
    chaos_mode=False,
    standard_families=STANDARD_TIER_ONE_FAMILIES,
    additional_build_houses=(),
    additional_production_houses=(),
    excluded_unit_ids=(),
    allow_player_family_fallback=False,
):
    """Make the seed's guaranteed Tier 1 combat roles immediately buildable."""
    selected_ids = {
        str(unit_id or '').upper()
        for unit_id in (starting_unit_ids or ())
        if unit_id
    }
    if not selected_ids:
        return {}
    excluded_ids = {
        str(unit_id or '').upper()
        for unit_id in (excluded_unit_ids or ())
        if unit_id
    }

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
                    if tech_id in excluded_ids:
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
    if not production_categories and allow_player_family_fallback:
        # Ordinary campaign maps can transfer/spawn the player's MCV only
        # after their opening script. Resolve the future native production
        # family from the human house without granting a foreign factory.
        player_families = {
            country_family(records.get(house, {}))
            for house in player_controlled_houses(lines, records=records)
        }
        for family in player_families.intersection(allowed_families):
            production_categories.update({
                (family, 'base'),
                (family, 'infantry'),
                (family, 'vehicles'),
                (family, 'air'),
            })
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
            if tech_id in excluded_ids:
                continue
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
            productions = [
                PRODUCTION_LOOKUP[prerequisite]
                for prerequisite in prerequisites
                if prerequisite in PRODUCTION_LOOKUP
            ]
            if not tech_level or not productions:
                continue
            categories = list(dict.fromkeys(category for _, category in productions))
            rules[tech_id.upper()] = {
                'TechLevel': tech_level,
                'Owner': owners,
                'RequiredHouses': required_houses,
                'ForbiddenHouses': 'none',
            }
            alternatives = []
            for category in categories:
                alternatives.extend(CHAOS_PRODUCTION_ALTERNATIVES.get(category, ()))
                alternatives.extend(special_alternatives[category])
            if not alternatives:
                alternatives.extend(prerequisites)
            rules[tech_id.upper()].update(
                _alternative_prerequisite_rules(alternatives)
            )
    for section, values in chaos_cameo_priority_rules(player_family).items():
        rules.setdefault(section, {}).update(values)
    return rules
