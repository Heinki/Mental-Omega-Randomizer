"""Readable mission production-access diagnostics.

This module audits the completed generated map.  It does not participate in
access planning or mutate game rules; support logs must describe the rules the
engine will receive, not create a second access policy.
"""

from collections import defaultdict

from randomizer.core.collections import comma_items, unique_in_order
from randomizer.maps.houses import (
    country_family,
    map_house_records,
    player_controlled_houses,
    player_house_from_map,
)
from randomizer.maps.ini import all_section_value_maps, parse_action_groups, section_lines
from randomizer.missions.access import PRODUCTION_LOOKUP, mission_production_buildings
from randomizer.rewards.catalogue import (
    BUFF_TARGETS,
    canonical_rewards,
    reward_display_name,
    unit_display_label,
    unit_role_equivalents,
)
from randomizer.rewards.rules import tech_ids_for_rewards


_FAMILY_LABELS = {
    'allies': 'Allied',
    'soviets': 'Soviet',
    'epsilon': 'Epsilon',
    'foehn': 'Foehn',
}

_PLAYER_FACTION_LABELS = {
    'allies': 'Allies',
    'soviets': 'Soviets',
    'epsilon': 'Epsilon',
    'foehn': 'Foehn',
}

_FACTORY_CATEGORY_LABELS = {
    'base': 'Construction Yard',
    'infantry': 'Barracks',
    'vehicles': 'War Factory',
    'air': 'Airfield',
    'naval': 'Naval Yard',
}


def _lower_values(values):
    return {
        str(key).strip().lower(): str(value).strip()
        for key, value in (values or {}).items()
        if value is not None
    }


def _section_lookup(sections):
    return {str(name).upper(): values for name, values in sections.items()}


def _effective_values(type_id, final_sections, installed_sections):
    type_id = str(type_id or '').upper()
    values = _lower_values(installed_sections.get(type_id, {}))
    values.update(_lower_values(final_sections.get(type_id, {})))
    return values


def _positive_production_entry(
    values,
    player_aliases,
    *,
    ignore_factory_owner_filters=False,
):
    """Return whether final rules expose a potential human production entry."""
    try:
        tech_level = int(float(values.get('techlevel', '-1')))
    except (TypeError, ValueError):
        return False
    if tech_level < 0 or tech_level > 10:
        return False
    try:
        if int(float(values.get('buildlimit', '1'))) == 0:
            return False
    except (TypeError, ValueError):
        pass
    if values.get('unbuildable', '').lower() == 'yes':
        return False

    def identities(key):
        return {
            item.lower()
            for item in comma_items(values.get(key, ''))
            if item.lower() not in {'none', '<none>'}
        }

    owners = identities('owner')
    required = identities('requiredhouses')
    forbidden = identities('forbiddenhouses')
    factory_owners = identities('factoryowners')
    factory_forbidden = identities('factoryowners.forbidden')
    negative = identities('prerequisite.negative')
    if owners and owners.isdisjoint(player_aliases):
        return False
    if required and required.isdisjoint(player_aliases):
        return False
    if forbidden.intersection(player_aliases):
        return False
    if not ignore_factory_owner_filters:
        if factory_owners and factory_owners.isdisjoint(player_aliases):
            return False
        if factory_forbidden.intersection(player_aliases):
            return False
    if 'morporiginalgate' in negative:
        return False
    return True


def _prerequisite_paths(values):
    paths = []
    primary = tuple(
        item.upper()
        for item in comma_items(values.get('prerequisite', ''))
        if item.upper() not in {'NONE', '<NONE>'}
    )
    if primary:
        paths.append(primary)
    numbered = []
    for key, value in values.items():
        if not key.startswith('prerequisite.list') or key == 'prerequisite.lists':
            continue
        suffix = key.removeprefix('prerequisite.list')
        if not suffix.isdigit() or int(suffix) == 0:
            continue
        path = tuple(
            item.upper()
            for item in comma_items(value)
            if item.upper() not in {'NONE', '<NONE>'}
        )
        if path:
            numbered.append((int(suffix), path))
    paths.extend(path for _index, path in sorted(numbered))
    paths.extend(
        (item.upper(),)
        for item in comma_items(values.get('prerequisiteoverride', ''))
        if item.upper() not in {'NONE', '<NONE>'}
    )
    return list(dict.fromkeys(paths))


def _factory_source_id(factory_id, clone_source_by_id):
    return clone_source_by_id.get(str(factory_id).upper(), str(factory_id).upper())


def _factory_info(factory_id, clone_source_by_id):
    source_id = _factory_source_id(factory_id, clone_source_by_id)
    match = PRODUCTION_LOOKUP.get(source_id)
    if not match:
        return '', '', source_id
    return match[0], match[1], source_id


def _factory_label(factory_id, clone_source_by_id):
    family, category, source_id = _factory_info(
        factory_id, clone_source_by_id
    )
    if family and category:
        return (
            f'{_FAMILY_LABELS.get(family, family.title())} '
            f'{_FACTORY_CATEGORY_LABELS.get(category, category.title())} '
            f'({factory_id})'
        )
    return f'{source_id} ({factory_id})' if source_id != factory_id else factory_id


def _production_factory_ids(final_sections, installed_sections):
    result = set(PRODUCTION_LOOKUP)
    for section_id in set(installed_sections) | set(final_sections):
        values = _effective_values(section_id, final_sections, installed_sections)
        factory = values.get('factory', '').lower()
        if factory in {
            'infantrytype', 'unittype', 'aircrafttype', 'buildingtype',
        } and not (
            values.get('invisibleingame', '').lower() == 'yes'
            or values.get('insignificant', '').lower() == 'yes'
            or values.get('buildlimit', '') == '0'
        ):
            result.add(str(section_id).upper())
    return result


def _factory_routes(values, factory_ids, clone_source_by_id):
    routes = []
    for path in _prerequisite_paths(values):
        factories = [
            item for item in path
            if item in factory_ids
            or _factory_source_id(item, clone_source_by_id) in factory_ids
        ]
        if not factories:
            continue
        ancillary = [item for item in path if item not in factories]
        labels = [_factory_label(item, clone_source_by_id) for item in factories]
        labels.extend(ancillary)
        routes.append(' + '.join(labels))
    return tuple(unique_in_order(routes)) or ('No factory prerequisite',)


def _structure_owner_and_type(line):
    if '=' not in line:
        return '', ''
    parts = [part.strip() for part in line.split('=', 1)[1].split(',')]
    if len(parts) < 2:
        return '', ''
    return parts[0], parts[1].upper()


def _player_identity(lines, records):
    player_house = player_house_from_map(lines, records=records)
    player_record = records.get(player_house, {})
    player_country = str(
        player_record.get('country')
        or player_house.removesuffix(' House')
        or 'Unknown'
    )
    aliases = {'morplayer'}
    for house in player_controlled_houses(lines, records=records) or [player_house]:
        record = records.get(house, {})
        for value in (
            house,
            str(house).removesuffix(' House'),
            record.get('country', ''),
            record.get('parent_country', ''),
        ):
            if str(value or '').strip():
                aliases.add(str(value).strip().lower())
    return player_house or 'Unknown', player_country, player_record, aliases


def _owned_and_potential_factories(
    lines,
    records,
    player_aliases,
    final_sections,
    installed_sections,
    factory_ids,
    clone_source_by_id,
):
    owned = []
    capturable = []
    scripted = []
    for line in section_lines(lines, 'Structures'):
        owner, building_id = _structure_owner_and_type(line)
        source_id = _factory_source_id(building_id, clone_source_by_id)
        if source_id not in factory_ids and building_id not in factory_ids:
            continue
        owner_record = records.get(owner, {})
        owner_aliases = {
            str(owner).lower(),
            str(owner).removesuffix(' House').lower(),
            str(owner_record.get('country') or '').lower(),
        }
        if owner_aliases.intersection(player_aliases):
            owned.append(building_id)
            continue
        values = _effective_values(
            building_id, final_sections, installed_sections
        )
        if values.get('capturable', '').lower() != 'no':
            capturable.append(building_id)

    # Script-created factories are not owned at map start, but matter when a
    # captured-tech report must explain a later sidebar entry.
    for line in section_lines(lines, 'Actions'):
        if '=' not in line:
            continue
        _count, groups = parse_action_groups(line.split('=', 1)[1])
        for group in groups:
            if len(group) < 3 or group[0] != '125':
                continue
            building_id = group[2].strip().upper()
            source_id = _factory_source_id(building_id, clone_source_by_id)
            if source_id in factory_ids or building_id in factory_ids:
                scripted.append(building_id)
    owned = tuple(unique_in_order(owned))
    owned_set = set(owned)
    return (
        owned,
        tuple(
            item for item in unique_in_order(capturable)
            if item not in owned_set
        ),
        tuple(
            item for item in unique_in_order(scripted)
            if item not in owned_set
        ),
    )


def _reward_unlock_entries(rewards):
    entries = []
    for reward in canonical_rewards(rewards or ()):
        tech_ids = sorted(tech_ids_for_rewards([reward]))
        if not tech_ids:
            continue
        entries.append(
            f'{reward_display_name(reward)} '
            f'({", ".join(tech_ids)})'
        )
    return tuple(unique_in_order(entries))


def _faction_label(source_id, routes, clone_source_by_id):
    factions = BUFF_TARGETS.get(source_id, {}).get('factions') or ()
    if factions:
        return '/'.join(str(faction) for faction in factions)
    for route in routes:
        for factory_id in PRODUCTION_LOOKUP:
            if f'({factory_id})' not in route:
                continue
            family, _category, _source = _factory_info(
                factory_id, clone_source_by_id
            )
            if family:
                return _FAMILY_LABELS.get(family, family.title())
    return 'Unknown'


def _factory_ids_in_routes(routes, factory_ids):
    found = []
    for route in routes:
        for factory_id in factory_ids:
            if route == factory_id or f'({factory_id})' in route:
                found.append(factory_id)
    return tuple(unique_in_order(found))


def _routes_reachable(
    routes,
    factory_ids,
    clone_source_by_id,
    reachable_production,
    owned_factories,
    potential_factories,
):
    if routes == ('No factory prerequisite',):
        return True
    direct_ids = (
        set(owned_factories)
        | set(potential_factories)
        | set(reachable_production)
    )
    reachable_categories = {
        (family, category)
        for factory_id in direct_ids
        for family, category, _source_id in (
            _factory_info(factory_id, clone_source_by_id),
        )
        if family and category
    }
    for factory_id in _factory_ids_in_routes(routes, factory_ids):
        family, category, source_id = _factory_info(
            factory_id, clone_source_by_id
        )
        if (
            factory_id in direct_ids
            or source_id in direct_ids
            or (family, category) in reachable_categories
            or (family, 'base') in reachable_categories
        ):
            return True
    return False


def _captured_route_possible(
    routes,
    factory_ids,
    clone_source_by_id,
    captured_factories,
    potential_factories,
):
    route_factory_ids = _factory_ids_in_routes(routes, factory_ids)
    for route_id in route_factory_ids:
        route_family, route_category, route_source = _factory_info(
            route_id, clone_source_by_id
        )
        for candidate in list(captured_factories) + list(potential_factories):
            family, category, source_id = _factory_info(
                candidate, clone_source_by_id
            )
            if not family or family != route_family:
                continue
            if (
                source_id == route_source
                or category == route_category
            ):
                return True
    return False


def build_unit_access_report(
    lines,
    installed_rule_sections,
    mission,
    state,
    *,
    reward_mode,
    progression_mode,
    campaign_filter,
    starting_rewards=(),
    progression_rewards=(),
    active_rewards=(),
    mission_specific_ids=(),
    delayed_mission_unlock_ids=(),
    starting_faction_tech_ids=(),
    expected_buildable_source_ids=(),
    controlled_source_ids=(),
    clone_handled=None,
    similar_tech_enabled=False,
    similar_tech_reason='',
    randomize_unit_access=True,
):
    """Return one complete, line-oriented final-map production report."""
    clone_handled = clone_handled or {}
    final_sections = _section_lookup(all_section_value_maps(lines))
    installed_sections = _section_lookup(installed_rule_sections)
    records = map_house_records(lines)
    player_house, player_country, player_record, player_aliases = (
        _player_identity(lines, records)
    )
    player_family = country_family(player_record)
    player_faction = _PLAYER_FACTION_LABELS.get(
        player_family,
        str(mission.get('side') or 'Unknown'),
    )

    clone_id_by_source = {
        str(source_id).upper(): str(details.get('clone_id') or '').upper()
        for source_id, details in clone_handled.items()
        if str(details.get('clone_id') or '').strip()
    }
    clone_source_by_id = {
        clone_id: source_id for source_id, clone_id in clone_id_by_source.items()
    }
    factory_ids = _production_factory_ids(final_sections, installed_sections)
    (
        owned_factories,
        capturable_factories,
        scripted_factories,
    ) = _owned_and_potential_factories(
        lines,
        records,
        player_aliases,
        final_sections,
        installed_sections,
        factory_ids,
        clone_source_by_id,
    )
    reachable_production = tuple(
        factory_id
        for factory_id in mission_production_buildings(
            lines,
            house_records=records,
            include_capturable=True,
        )
        if (
            factory_id in factory_ids
            or _factory_source_id(
                factory_id, clone_source_by_id
            ) in factory_ids
        )
    )
    potential_factories = tuple(unique_in_order(
        list(capturable_factories)
        + list(scripted_factories)
        + [
            factory_id
            for factory_id in reachable_production
            if factory_id not in owned_factories
        ]
    ))
    captured_factories = []
    for factory_id in owned_factories:
        family, _category, _source = _factory_info(
            factory_id, clone_source_by_id
        )
        if family and player_family and family != player_family:
            captured_factories.append(factory_id)

    starting_ids = set(tech_ids_for_rewards(starting_rewards))
    progression_ids = set(tech_ids_for_rewards(progression_rewards))
    active_ids = set(tech_ids_for_rewards(active_rewards))
    mission_ids = {str(item).upper() for item in mission_specific_ids}
    delayed_ids = {
        str(item).upper() for item in delayed_mission_unlock_ids
    }
    starting_tech_ids = {
        str(item).upper() for item in starting_faction_tech_ids
    }
    expected_ids = {
        str(item).upper() for item in expected_buildable_source_ids
    }
    controlled_ids = {str(item).upper() for item in controlled_source_ids}

    def access_sources(source_id, routes):
        sources = []
        if source_id in starting_ids:
            sources.append('Starting unlock')
        if source_id in progression_ids:
            sources.append('Progression unlock')
        if source_id in mission_ids:
            sources.append('Mission required')
        if source_id in starting_tech_ids or (
            not randomize_unit_access and source_id in active_ids
        ):
            sources.append('Starting faction tech')
        if reward_mode == 'Randomizer Arsenal' and source_id in active_ids:
            sources.append('Mission arsenal')
        if reward_mode == 'Chaos' and source_id in active_ids:
            sources.append('Chaos mode')
        route_factory_ids = _factory_ids_in_routes(routes, factory_ids)
        for factory_id in route_factory_ids:
            if factory_id not in captured_factories:
                continue
            sources.append(
                'Captured '
                + _factory_label(factory_id, clone_source_by_id).rsplit(
                    f' ({factory_id})', 1
                )[0]
            )
        route_family_categories = {
            (family, category)
            for factory_id in route_factory_ids
            for family, category, _source in (
                _factory_info(factory_id, clone_source_by_id),
            )
            if family and family != player_family
        }
        for family, category in sorted(route_family_categories):
            candidates = []
            for factory_id in (
                list(captured_factories) + list(capturable_factories)
            ):
                candidate_family, candidate_category, candidate_source = (
                    _factory_info(factory_id, clone_source_by_id)
                )
                if candidate_family != family:
                    continue
                route_sources = {
                    _factory_source_id(route_id, clone_source_by_id)
                    for route_id in route_factory_ids
                }
                priority = (
                    0 if candidate_source in route_sources else
                    1 if candidate_category == category else
                    2 if candidate_category == 'base' else
                    3
                )
                if priority < 3:
                    candidates.append((priority, factory_id))
            if not candidates:
                scripted_candidates = []
                for factory_id in (
                    list(scripted_factories) + list(potential_factories)
                ):
                    candidate_family, candidate_category, candidate_source = (
                        _factory_info(factory_id, clone_source_by_id)
                    )
                    if candidate_family != family:
                        continue
                    route_sources = {
                        _factory_source_id(route_id, clone_source_by_id)
                        for route_id in route_factory_ids
                    }
                    priority = (
                        0 if candidate_source in route_sources else
                        1 if candidate_category == category else
                        2 if candidate_category == 'base' else
                        3
                    )
                    if priority < 3:
                        scripted_candidates.append((priority, factory_id))
                if not scripted_candidates:
                    continue
                _priority, enabler = min(scripted_candidates)
                enabler_text = _factory_label(
                    enabler, clone_source_by_id
                ).rsplit(f' ({enabler})', 1)[0]
                sources.append('Scripted/planned ' + enabler_text + ' required')
                continue
            _priority, enabler = min(candidates)
            enabler_text = _factory_label(
                enabler, clone_source_by_id
            ).rsplit(f' ({enabler})', 1)[0]
            captured_text = 'Captured ' + enabler_text
            if enabler not in captured_factories:
                captured_text += ' required'
            sources.append(captured_text)
        return tuple(unique_in_order(sources))

    entries = []
    entry_by_source = {}
    unauthorized = []
    duplicates = []

    for source_id in sorted(expected_ids):
        clone_id = clone_id_by_source.get(source_id, '')
        entry_id = clone_id or source_id
        values = _effective_values(
            entry_id, final_sections, installed_sections
        )
        delayed = source_id in delayed_ids
        if not delayed and not _positive_production_entry(values, player_aliases):
            # An expected foreign identity can remain dormant because its
            # physical factory is unavailable. It is not a final production
            # entry for this mission and should not clutter the report.
            continue
        routes = _factory_routes(values, factory_ids, clone_source_by_id)
        if not _routes_reachable(
            routes,
            factory_ids,
            clone_source_by_id,
            reachable_production,
            owned_factories,
            potential_factories,
        ):
            continue
        sources = access_sources(source_id, routes)
        entry = {
            'source_id': source_id,
            'entry_id': entry_id,
            'display': unit_display_label(source_id),
            'identity': f'clone of {source_id}' if clone_id else 'original',
            'faction': _faction_label(source_id, routes, clone_source_by_id),
            'routes': routes,
            'sources': sources,
            'delayed': delayed,
        }
        entries.append(entry)
        entry_by_source[source_id] = entry
        if not sources:
            unauthorized.append(entry)

        if clone_id:
            native_values = _effective_values(
                source_id, final_sections, installed_sections
            )
            native_routes = _factory_routes(
                native_values, factory_ids, clone_source_by_id
            )
            native_buildable = _positive_production_entry(
                native_values, player_aliases
            )
            if (
                not native_buildable
                and _positive_production_entry(
                    native_values,
                    player_aliases,
                    ignore_factory_owner_filters=True,
                )
                and _captured_route_possible(
                    native_routes,
                    factory_ids,
                    clone_source_by_id,
                    captured_factories,
                    capturable_factories,
                )
            ):
                native_buildable = True
            if (
                _positive_production_entry(values, player_aliases)
                and native_buildable
            ):
                duplicates.append(entry)

    # Generated support/reference/payload clones must stay locked. If one is
    # positive despite not belonging to the authorized buildable set, expose
    # it even when no normal reward entry points at it.
    for source_id, clone_id in sorted(clone_id_by_source.items()):
        if source_id in expected_ids:
            continue
        values = _effective_values(clone_id, final_sections, installed_sections)
        if not _positive_production_entry(values, player_aliases):
            continue
        routes = _factory_routes(values, factory_ids, clone_source_by_id)
        if not _routes_reachable(
            routes,
            factory_ids,
            clone_source_by_id,
            reachable_production,
            owned_factories,
            potential_factories,
        ):
            continue
        entry = {
            'source_id': source_id,
            'entry_id': clone_id,
            'display': unit_display_label(source_id),
            'identity': f'clone of {source_id}',
            'faction': _faction_label(source_id, routes, clone_source_by_id),
            'routes': routes,
            'sources': (),
            'delayed': False,
        }
        entries.append(entry)
        unauthorized.append(entry)

    # Audit controlled originals that escaped isolation without receiving any
    # authorized mission/reward source.
    for source_id in sorted(controlled_ids - expected_ids):
        if source_id not in final_sections:
            continue
        values = _effective_values(source_id, final_sections, installed_sections)
        if not _positive_production_entry(values, player_aliases):
            continue
        routes = _factory_routes(values, factory_ids, clone_source_by_id)
        if not _routes_reachable(
            routes,
            factory_ids,
            clone_source_by_id,
            reachable_production,
            owned_factories,
            potential_factories,
        ):
            continue
        entry = {
            'source_id': source_id,
            'entry_id': source_id,
            'display': unit_display_label(source_id),
            'identity': 'original',
            'faction': _faction_label(source_id, routes, clone_source_by_id),
            'routes': routes,
            'sources': (),
            'delayed': False,
        }
        entries.append(entry)
        unauthorized.append(entry)

    code = str(mission.get('code') or 'UNKNOWN')
    scenario = str(mission.get('scenario') or 'unknown map')
    title = str(mission.get('title') or code)
    campaign_label = (
        'All Campaigns'
        if campaign_filter == 'All Campaigns'
        else f'Single Campaign ({campaign_filter})'
    )
    progression_label = (
        'Grid'
        if progression_mode == 'Grid Mode'
        else str(progression_mode or 'Standard')
    )
    modes = unique_in_order([reward_mode or 'Standard', campaign_label, progression_label])
    starting_entries = _reward_unlock_entries(starting_rewards)
    progression_entries = _reward_unlock_entries(progression_rewards)
    mission_entries = [
        f'{unit_display_label(unit_id)} ({unit_id})'
        + (' [delayed mission unlock]' if unit_id in delayed_ids else '')
        for unit_id in sorted(mission_ids)
    ]

    lines_out = [
        f'=== UNIT ACCESS REPORT | {code} | {title} | {scenario} ===',
        'Current mode: ' + ' | '.join(modes),
        f'Player faction/house: {player_faction} | {player_house} | {player_country}',
        'Starting Unlocks: '
        + (', '.join(starting_entries) if starting_entries else 'None'),
        'Progression Unlocks: '
        + (', '.join(progression_entries) if progression_entries else 'None'),
        'Mission-specific unlocks: '
        + (', '.join(mission_entries) if mission_entries else 'None'),
        'Similar/equivalent-tech option: '
        + ('Enabled' if similar_tech_enabled else 'Disabled')
        + (f' ({similar_tech_reason})' if similar_tech_reason else '')
        + '; equivalent sharing affects buffs only unless an explicit access source is listed.',
        'Production buildings currently owned (map start): '
        + (
            ', '.join(
                _factory_label(item, clone_source_by_id)
                for item in owned_factories
            )
            if owned_factories else 'None'
        ),
        'Captured enemy tech/buildings currently owned (map start): '
        + (
            ', '.join(
                _factory_label(item, clone_source_by_id)
                for item in captured_factories
            )
            if captured_factories else 'None'
        ),
        'Capturable/scripted/planned production buildings: '
        + (
            ', '.join(
                _factory_label(item, clone_source_by_id)
                for item in potential_factories
            )
            if potential_factories else 'None'
        ),
        f'Final buildable unit list: {len(entries)} production entry/entries '
        '(availability depends on listed factory prerequisites).',
    ]

    grouped = defaultdict(list)
    for entry in entries:
        grouped[entry['routes']].append(entry)
    for routes in sorted(grouped, key=lambda value: tuple(item.lower() for item in value)):
        lines_out.append('Production building: ' + ' OR '.join(routes))
        for entry in sorted(
            grouped[routes],
            key=lambda item: (item['display'].lower(), item['entry_id']),
        ):
            source_text = '; '.join(entry['sources']) or 'NONE'
            if entry['delayed']:
                source_text += '; delayed mission unlock'
            lines_out.append(
                '  - '
                f'{entry["display"]} | ID={entry["entry_id"]} | '
                f'{entry["identity"]} | faction={entry["faction"]} | '
                f'factory={" OR ".join(entry["routes"])} | '
                f'access={source_text}'
            )

    explicit_access_ids = starting_ids | progression_ids | mission_ids | starting_tech_ids
    equivalent_lines = []
    for original_id in sorted(explicit_access_ids):
        for equivalent_id in sorted(unit_role_equivalents(original_id)):
            if equivalent_id == original_id or equivalent_id in explicit_access_ids:
                continue
            entry = entry_by_source.get(equivalent_id)
            if not entry:
                continue
            enabling_factories = [
                _factory_label(factory_id, clone_source_by_id)
                for factory_id in _factory_ids_in_routes(
                    entry['routes'], factory_ids
                )
                if factory_id in captured_factories
            ]
            why = (
                'Chaos mode'
                if reward_mode == 'Chaos'
                else 'Single Campaign similar tech'
            )
            equivalent_lines.append(
                f'  - original={unit_display_label(original_id)} ({original_id}) | '
                f'equivalent={entry["display"]} ({entry["entry_id"]}) | '
                f'why={why} | enabled by='
                + (', '.join(enabling_factories) if enabling_factories else entry['faction'])
            )
    lines_out.append('Equivalent/similar production access:')
    lines_out.extend(
        equivalent_lines
        or ['  - None; every listed production entry has exact or mission-specific access.']
    )

    for entry in unauthorized:
        lines_out.append(
            'WARNING: Unauthorized production access | '
            f'{entry["display"]} | ID={entry["entry_id"]} | '
            f'factory={" OR ".join(entry["routes"])}'
        )
    for entry in duplicates:
        lines_out.append(
            'WARNING: Duplicate production entry | '
            f'{entry["display"]} | original={entry["source_id"]} | '
            f'clone={entry["entry_id"]} | '
            f'factory={" OR ".join(entry["routes"])}'
        )
    lines_out.append(f'=== END UNIT ACCESS REPORT | {code} ===')
    return lines_out
