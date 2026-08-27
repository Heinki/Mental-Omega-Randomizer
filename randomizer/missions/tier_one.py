"""Tier-one starter selection and mission-local access rules."""

from .access import (
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
    access_catalog,
    _alternative_prerequisite_rules,
    _build_access_rule,
    _chaos_prerequisite_rules,
    _mission_production_buildings,
    _native_access_prerequisites,
    _player_family,
    _special_factory_alternatives,
    all_section_value_maps,
    chaos_cameo_priority_rules,
    chaos_category_owner_ids,
    chaos_production_alternatives,
    country_family,
    map_house_records,
    merged_production_owners,
    player_controlled_houses,
    player_house_from_map,
    production_owner_countries,
    safe_build_countries,
)

def tier_one_unit_ids(families):
    """Return the five abstract combat roles for variant selection."""
    requested = {str(family or '').lower() for family in families}
    if not requested:
        return ()
    return tuple(TIER_ONE_ROLE_MARKERS[role] for role in TIER_ONE_ROLE_UNITS)

def tier_one_role_label(unit_or_marker):
    role = TIER_ONE_ROLE_BY_MARKER.get(str(unit_or_marker or '').upper())
    if not role:
        return ''
    if role == 'ground_vehicle':
        return 'Ground Tank'
    if role == 'anti_air_vehicle':
        return 'Anti-Air Tank'
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

def select_tier_one_unit_variants(
    rng,
    starting_unit_ids,
    *,
    families,
    allowed_roles=None,
    excluded_unit_ids=(),
):
    """Resolve each saved role marker to one concrete seeded unit identity."""
    available_families = tuple(dict.fromkeys(
        str(family or '').lower()
        for family in families
        if str(family or '').lower() in {
            *STANDARD_TIER_ONE_FAMILIES,
            'foehn',
        }
    ))
    allowed = (
        set(TIER_ONE_ROLE_UNITS)
        if allowed_roles is None
        else {str(role) for role in allowed_roles}
    )
    excluded = {
        str(unit_id or '').upper()
        for unit_id in excluded_unit_ids
        if unit_id
    }
    selected = []
    for value in starting_unit_ids or ():
        unit_id = str(value or '').upper()
        role = TIER_ONE_ROLE_BY_MARKER.get(unit_id)
        if not role:
            if unit_id and unit_id not in excluded and unit_id not in selected:
                selected.append(unit_id)
            continue
        if role not in allowed:
            continue
        candidates = tuple(dict.fromkeys(
            entry[0]
            for family in available_families
            for entry in _tier_one_variant_entries(role, family)
            if entry[0] not in excluded
        ))
        if candidates:
            selected.append(rng.choice(candidates))
    return tuple(selected)

def select_tier_one_defense_variants(
    rng,
    starting_defense_ids,
    *,
    families,
    excluded_unit_ids=(),
):
    """Resolve the defense marker to one seeded identity for each role."""
    available_families = tuple(dict.fromkeys(
        str(family or '').lower()
        for family in families
        if str(family or '').lower() in TIER_ONE_DEFENSE_UNITS
    ))
    excluded = {
        str(unit_id or '').upper()
        for unit_id in excluded_unit_ids
        if unit_id
    }
    selected = []
    for value in starting_defense_ids or ():
        unit_id = str(value or '').upper()
        if unit_id != TIER_ONE_DEFENSE_MARKER:
            if unit_id and unit_id not in excluded and unit_id not in selected:
                selected.append(unit_id)
            continue
        for role in TIER_ONE_DEFENSE_ROLES:
            candidates = tuple(dict.fromkeys(
                TIER_ONE_DEFENSE_ROLE_UNITS[role][family]
                for family in available_families
                if (
                    family in TIER_ONE_DEFENSE_ROLE_UNITS[role]
                    and TIER_ONE_DEFENSE_ROLE_UNITS[role][family]
                    not in excluded
                )
            ))
            if candidates:
                selected.append(rng.choice(candidates))
    return tuple(dict.fromkeys(selected))

def expanded_tier_one_unit_ids(
    starting_unit_ids,
    *,
    families=None,
    include_foehn=False,
):
    """Expand saved role markers into eligible concrete unit identities."""
    available_families = [
        str(family or '').lower()
        for family in (
            STANDARD_TIER_ONE_FAMILIES if families is None else families
        )
        if str(family or '').lower() in STANDARD_TIER_ONE_FAMILIES
    ]
    if include_foehn:
        available_families.append('foehn')
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
            for family in available_families
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
    """Assign every faction once on ground, plus one seeded aircraft."""
    families = list(STANDARD_TIER_ONE_FAMILIES) + ['foehn']
    rng.shuffle(families)
    units = [
        _random_tier_one_variant(rng, role, family)
        for role, family in zip(TIER_ONE_GROUND_ROLES, families)
    ]
    aircraft_family = rng.choice(STANDARD_TIER_ONE_FAMILIES)
    units.append(_random_tier_one_variant(
        rng, 'basic_aircraft', aircraft_family
    ))
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

def standard_tier_one_unit_markers(starting_unit_ids):
    """Normalize legacy concrete Standard starters back to abstract roles."""
    selected_ids = {
        str(unit_id or '').upper()
        for unit_id in (starting_unit_ids or ())
        if unit_id
    }
    selected_roles = _selected_tier_one_roles(selected_ids)
    return tuple(
        TIER_ONE_ROLE_MARKERS[role]
        for role in TIER_ONE_ROLE_UNITS
        if role in selected_roles
    )

def concrete_tier_one_starter_ids(starting_unit_ids):
    """Keep recognized concrete/marker identities across all five roles."""
    allowed_ids = {
        TIER_ONE_ROLE_MARKERS[role]
        for role in TIER_ONE_ROLE_UNITS
    }
    allowed_ids.update(
        entry[0]
        for role in TIER_ONE_ROLE_UNITS
        for family in STANDARD_TIER_ONE_FAMILIES + ('foehn',)
        for entry in _tier_one_variant_entries(role, family)
    )
    return tuple(dict.fromkeys(
        unit_id
        for value in (starting_unit_ids or ())
        if (unit_id := str(value or '').upper()) in allowed_ids
    ))

def standard_tier_one_defense_markers(starting_defense_ids):
    """Normalize legacy concrete Standard defenses to the shared marker."""
    selected_ids = {
        str(unit_id or '').upper()
        for unit_id in (starting_defense_ids or ())
        if unit_id
    }
    known_ids = {
        unit_id
        for family_ids in TIER_ONE_DEFENSE_UNITS.values()
        for unit_id in family_ids
    }
    return (
        (TIER_ONE_DEFENSE_MARKER,)
        if TIER_ONE_DEFENSE_MARKER in selected_ids
        or selected_ids.intersection(known_ids)
        else ()
    )

def _standard_tier_one_entry(role, family, player_countries):
    configured = TIER_ONE_SUBFACTION_UNITS.get(role, {})
    by_lower = {country.lower(): entry for country, entry in configured.items()}
    for country in player_countries:
        entry = by_lower.get(str(country).lower())
        if entry and country_family({'country': country}) == family:
            return entry
    return TIER_ONE_ROLE_UNITS[role][family]

def _preferred_standard_starter_family(
    lines, records, production_categories, allowed
):
    """Choose one usable family, preferring complete ground production."""
    player_family = _player_family(lines, records)
    ranked = []
    for index, family in enumerate(STANDARD_TIER_ONE_FAMILIES):
        if family not in allowed:
            continue
        categories = {
            category
            for candidate_family, category in production_categories
            if candidate_family == family
        }
        score = (
            2
            if 'base' in categories
            else int('infantry' in categories) + int('vehicles' in categories)
        )
        if score:
            ranked.append((score, family == player_family, -index, family))
    return max(ranked, default=(0, False, 0, ''))[-1]

def _tier_one_airfield_rules(
    base_families,
    aircraft_families,
    _owners,
    _required_houses,
    chaos_mode=False,
    chaos_alternatives=None,
):
    """Unlock required AircraftType factories behind matching faction tech."""
    base_families = {
        family for family in base_families if family in CHAOS_PRIMARY_PRODUCTION
    }
    if not base_families and not chaos_mode:
        return {}

    if chaos_mode:
        # Chaos shares unlocked production buildings across factions. Any
        # Construction Yard may build the selected aircraft's airfield.
        conyards = (
            chaos_alternatives or CHAOS_PRODUCTION_ALTERNATIVES
        )['base']
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
    include_capturable_production=False,
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
        map_chaos_alternatives = chaos_production_alternatives(
            lines,
            house_records=records,
            additional_production_houses=additional_production_houses,
        )
        construction_yards = map_chaos_alternatives['base']
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
                include_capturable=include_capturable_production,
            )
            if building_id in PRODUCTION_LOOKUP
        }
        base_families = {
            family for family, category in production_categories
            if category == 'base'
        }
        if not base_families and allow_player_family_fallback:
            # Many ordinary campaign base missions spawn or transfer the MCV
            # only after scripted opening events. If no physical family exists,
            # prepare the current house family behind its exact Yard.
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
        starter_family = _preferred_standard_starter_family(
            lines,
            records,
            {(family, 'base') for family in base_families},
            allowed_families,
        )
        base_families = {starter_family} if starter_family else set()
        # Standard resolves the abstract starter roles for one matching
        # mission family. Sibling faction defenses are never injected.
        eligible_families = tuple(
            family
            for family in STANDARD_TIER_ONE_FAMILIES
            if family in allowed_families
            and (
                (marker_selected and family in base_families)
                or (
                    not marker_selected
                    and any(
                        unit_id in selected_ids
                        for unit_id in TIER_ONE_DEFENSE_UNITS.get(family, ())
                    )
                )
            )
        )

    catalog_by_id = {
        tech_id: (tech_level, family, category, prerequisite, native_owners)
        for tech_id, tech_level, family, category, prerequisite, native_owners
        in access_catalog()
        if tech_id in {
            starter_id
            for family_ids in TIER_ONE_DEFENSE_UNITS.values()
            for starter_id in family_ids
        }
        and category == 'base'
    }
    selected_roles = {
        role
        for role, family_units in TIER_ONE_DEFENSE_ROLE_UNITS.items()
        if marker_selected or selected_ids.intersection(family_units.values())
    }
    for family in eligible_families:
        family_tech_ids = (
            TIER_ONE_DEFENSE_UNITS.get(family, ())
            if chaos_mode
            else tuple(
                TIER_ONE_DEFENSE_ROLE_UNITS[role][family]
                for role in TIER_ONE_DEFENSE_ROLES
                if role in selected_roles
            )
        )
        for tech_id in family_tech_ids:
            if tech_id in excluded_ids:
                continue
            if chaos_mode and not marker_selected and tech_id not in selected_ids:
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
                    prerequisite_alternatives=(
                        construction_yards or (prerequisite,)
                    ),
                )
            else:
                rules[tech_id] = _build_access_rule(
                    lines,
                    sections,
                    player_countries,
                    tech_level,
                    native_owners,
                    prerequisite_alternatives=(prerequisite,),
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
    include_capturable_production=False,
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
        include_capturable=include_capturable_production,
    ):
        production = PRODUCTION_LOOKUP.get(building_id)
        if production:
            production_categories.add(production)
    base_families = {
        family for family, category in production_categories if category == 'base'
    }
    selected_roles = _selected_tier_one_roles(selected_ids)

    if chaos_mode:
        map_chaos_alternatives = chaos_production_alternatives(
            lines,
            house_records=records,
            additional_production_houses=additional_production_houses,
        )
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
                        production_alternatives=map_chaos_alternatives,
                    ))
                    rules[tech_id] = values
        rules.update(_tier_one_airfield_rules(
            base_families,
            selected_aircraft_families,
            owners,
            required_houses,
            chaos_mode=True,
            chaos_alternatives=map_chaos_alternatives,
        ))
        return rules

    allowed_families = {
        str(family or '').lower()
        for family in standard_families
        if str(family or '').lower() in STANDARD_TIER_ONE_FAMILIES
    }
    if not production_categories and allow_player_family_fallback:
        # Ordinary campaign maps can transfer/spawn the player's MCV only
        # after their opening script. Use the house family only when the source
        # map exposes no physical or scripted production family at all.
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
    starter_family = _preferred_standard_starter_family(
        lines,
        records,
        production_categories,
        allowed_families,
    )
    allowed_families = {starter_family} if starter_family else set()
    production_categories = {
        (family, category)
        for family, category in production_categories
        if family == starter_family
    }
    base_families = {
        family for family, category in production_categories
        if category == 'base'
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
    if starter_family:
        # One known family is enough to prepare the complete four-role set.
        # Exact Barracks/War Factory prerequisites keep a missing category
        # dormant until the mission script creates or transfers that factory.
        available_categories.add((starter_family, 'infantry'))
        available_categories.add((starter_family, 'vehicles'))
        available_categories.add((starter_family, 'air'))

    marker_roles = {
        TIER_ONE_ROLE_BY_MARKER[unit_id]
        for unit_id in selected_ids
        if unit_id in TIER_ONE_ROLE_BY_MARKER
    }
    selected_aircraft_families = set()
    for role in TIER_ONE_ROLE_UNITS:
        entries = []
        if role in marker_roles:
            entries.extend(
                (family, *_standard_tier_one_entry(
                    role, family, player_countries
                ))
                for family in STANDARD_TIER_ONE_FAMILIES
            )
        else:
            entries.extend(
                (family, tech_id, category)
                for family in STANDARD_TIER_ONE_FAMILIES
                for tech_id, category in _tier_one_variant_entries(role, family)
                if tech_id in selected_ids
            )
        for family, tech_id, category in dict.fromkeys(entries):
            if family not in allowed_families:
                continue
            if tech_id in excluded_ids:
                continue
            if (family, category) not in available_categories:
                continue
            if category == 'air':
                selected_aircraft_families.add(family)
            prerequisite = CHAOS_PRIMARY_PRODUCTION[family][category]
            values = {
                'TechLevel': '1',
                'Owner': owners,
                'RequiredHouses': required_houses,
                'ForbiddenHouses': 'none',
            }
            values.update(_alternative_prerequisite_rules((prerequisite,)))
            rules[tech_id] = values
    rules.update(_tier_one_airfield_rules(
        base_families.intersection(allowed_families),
        selected_aircraft_families,
        owners,
        required_houses,
    ))
    return rules

def chaos_earned_access_rules(
    lines,
    earned_rewards,
    additional_build_houses=(),
    excluded_special_infantry_factories=(),
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
    player_family = _player_family(lines, records)
    earned_access_ids = set()
    earned_tech_levels = {}
    for reward in earned_rewards:
        if reward.get('kind') in {'buff', 'superweapon'}:
            continue
        for tech_id, values in reward.get('rules', {}).items():
            tech_level = next(
                (str(value) for key, value in values.items() if key.lower() == 'techlevel'),
                '',
            )
            if tech_level:
                earned_access_ids.add(tech_id.upper())
                earned_tech_levels[tech_id.upper()] = tech_level

    # Chaos keeps exact unlocked identities, then exposes each from every
    # compatible factory category. Standard role/faction translation must not
    # filter this path; Foehn access works in non-Foehn campaigns.
    entries_by_tech = {}
    for entry in access_catalog():
        tech_id = entry[0]
        if tech_id in earned_access_ids:
            entries_by_tech.setdefault(tech_id, []).append(entry)
    special_alternatives = {
        category: _special_factory_alternatives(
            lines,
            category,
            sections,
            excluded_infantry_factory_ids=(
                excluded_special_infantry_factories
            ),
        )
        for category in ('base', 'infantry', 'vehicles', 'air', 'naval')
    }
    map_chaos_alternatives = chaos_production_alternatives(
        lines,
        house_records=records,
    )
    for tech_id, entries in entries_by_tech.items():
        tech_level = earned_tech_levels.get(tech_id, entries[0][1])
        categories = {entry[3] for entry in entries}
        native_owner_values = [entry[5] for entry in entries]
        native_owner_values.extend(chaos_category_owner_ids(categories))
        native_owners = merged_production_owners(*native_owner_values)
        alternatives = []
        for _tech_id, _level, _family, category, prerequisite, _owners in entries:
            alternatives.extend(map_chaos_alternatives.get(category, ()))
            alternatives.extend(special_alternatives.get(category, ()))
            if not map_chaos_alternatives.get(category):
                alternatives.extend(_native_access_prerequisites(
                    tech_id, prerequisite
                ))
        rules[tech_id] = _build_access_rule(
            lines,
            sections,
            player_countries,
            tech_level,
            native_owners,
            prerequisite_alternatives=alternatives,
        )
    for section, values in chaos_cameo_priority_rules(player_family).items():
        rules.setdefault(section, {}).update(values)
    return rules
