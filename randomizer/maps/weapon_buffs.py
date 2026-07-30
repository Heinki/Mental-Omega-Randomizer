"""Player weapon clones, native variants, and veterancy rules."""

from ._shared import (
    BUFF_TARGETS,
    MAX_COUNTRY_VETERAN_VALUE_LENGTH,
    SHARED_WEAPON_USER_IDS,
    WEAPON_STAT_BUFF_TYPES,
    all_section_value_maps,
    build_unit_usage_index,
    comma_items,
    house_category_suffix,
    map_house_records,
    parse_action_groups,
    player_controlled_houses,
    player_house_from_map,
    resolve_configured_helper_houses,
    section_lines,
    section_value_map_preserve,
    stacking_multiplier,
    unique_in_order,
    unit_usage_houses,
)
from .buff_values import (
    _active_direct_buff_counts,
    apply_unit_buff_value,
    apply_weapon_buff_value,
)
from .clone_references import (
    _standalone_clone_values_from_maps,
    _target_with_effective_unit_stats,
)
from .base import (
    _value_case_insensitive,
    merge_unique_csv_bounded,
    parse_float,
)

def unit_weapon_buff_rules(
    lines,
    rewards,
    configured_helper_houses=(),
    require_unlocked_access=True,
    additional_unlocked_tech_ids=None,
    share_basic_equivalent_buffs=False,
    unit_specific_mode=False,
    clone_handled=None,
    excluded_unit_ids=(),
    excluded_player_houses=(),
):
    """Apply direct buffs only when their global type is safe for friendly houses.

    TechnoType and WeaponType values are global in the engine. Player and
    explicitly configured helper houses participate; any buff whose affected
    unit type or shared weapon is also used by an enemy is skipped.
    """
    records = map_house_records(lines)
    player_house = player_house_from_map(lines, records=records)
    if not player_house:
        return ({}, [], [])

    excluded_house_names = {
        str(house or '').lower() for house in excluded_player_houses
    }
    player_houses = [
        house
        for house in (
            player_controlled_houses(lines, records=records) or [player_house]
        )
        if house.lower() not in excluded_house_names
    ]
    helper_houses, _ = resolve_configured_helper_houses(
        records,
        configured_helper_houses,
        player_houses,
    )
    allowed_names = []
    for house in unique_in_order(player_houses + helper_houses):
        record = records.get(house, {})
        if not record:
            record = records.get(house + ' House', {})
        allowed_names.append(house)
        allowed_names.append(house.replace(' House', ''))
        if not house.lower().endswith(' house'):
            allowed_names.append(house + ' House')
        if record.get('country'):
            allowed_names.append(record['country'])
    allowed_houses = {name.lower() for name in allowed_names if name}
    usage_index = build_unit_usage_index(lines)

    counts_by_unit = _active_direct_buff_counts(
        rewards,
        require_unlocked_access=require_unlocked_access,
        additional_unlocked_tech_ids=additional_unlocked_tech_ids,
        share_basic_equivalent_buffs=share_basic_equivalent_buffs,
        unit_specific_mode=unit_specific_mode,
    )
    for unit_id in {
        str(unit_id or '').upper() for unit_id in excluded_unit_ids
    }:
        counts_by_unit.pop(unit_id, None)
    clone_handled = {
        str(unit_id).upper(): values
        for unit_id, values in (clone_handled or {}).items()
    }

    rule_sections = {}
    applied_units = []
    skipped_units = []
    for unit_id, counts in counts_by_unit.items():
        handled = clone_handled.get(unit_id.upper(), {})
        handled_unit_types = set(handled.get('unit_buff_types', ()))
        handled_weapon_ids = {
            str(weapon).upper() for weapon in handled.get('weapon_ids', ())
        }
        target = BUFF_TARGETS.get(unit_id, {})
        unsafe_unit_houses = sorted({
            house
            for house in unit_usage_houses(lines, unit_id, usage_index)
            if house.lower() not in allowed_houses
        })

        applied = False
        direct_types = (
            set(counts) - WEAPON_STAT_BUFF_TYPES - handled_unit_types
        )
        if unsafe_unit_houses and direct_types:
            skipped_units.append(
                f'{target.get("label", unit_id)} ({", ".join(unsafe_unit_houses)})'
            )
        elif direct_types:
            unit_values = rule_sections.setdefault(unit_id, {})
            effective_target = target
            if 'passenger_capacity' in direct_types:
                # Native mission transports can deliberately override their
                # installed cargo/capture capacity. Add earned slots to that
                # authored value instead of replacing it from the installed
                # reward snapshot (ASOMNIA's Chrono Prison uses 24).
                authored_passengers = _value_case_insensitive(
                    section_value_map_preserve(lines, unit_id),
                    'Passengers',
                )
                if authored_passengers is not None:
                    try:
                        effective_target = dict(target)
                        effective_target['passengers'] = int(
                            float(str(authored_passengers).strip())
                        )
                    except (TypeError, ValueError):
                        effective_target = target
            for buff_type in (
                'health', 'armor', 'sight', 'ammo', 'passenger_capacity',
                'open_topped', 'self_healing', 'cloak', 'sensors', 'cost',
                'speed',
            ):
                if buff_type in direct_types and apply_unit_buff_value(
                    unit_values,
                    effective_target,
                    buff_type,
                    counts[buff_type],
                ):
                    applied = True
            if not unit_values:
                rule_sections.pop(unit_id, None)

        weapon_buff_types = WEAPON_STAT_BUFF_TYPES.intersection(counts)
        if weapon_buff_types:
            for weapon, base_stats in target.get('weapons', {}).items():
                if weapon.upper() in handled_weapon_ids:
                    continue
                weapon_users = SHARED_WEAPON_USER_IDS.get(weapon.upper(), {unit_id})
                unsafe_weapon_houses = sorted({
                    house
                    for weapon_user in weapon_users
                    for house in unit_usage_houses(lines, weapon_user, usage_index)
                    if house.lower() not in allowed_houses
                })
                if unsafe_weapon_houses:
                    skipped_units.append(
                        f'{target.get("label", unit_id)} / {weapon} '
                        f'({", ".join(unsafe_weapon_houses)})'
                    )
                    continue
                weapon_values = {}
                for buff_type in ('damage', 'range', 'reload'):
                    if buff_type in weapon_buff_types:
                        applied = (
                            apply_weapon_buff_value(
                                weapon_values,
                                base_stats,
                                buff_type,
                                counts[buff_type],
                            )
                            or applied
                        )
                if not weapon_values:
                    continue
                rule_sections.setdefault(weapon, {}).update(weapon_values)
        if 'damage' in weapon_buff_types and target.get('special_damage_fields'):
            if unsafe_unit_houses:
                skipped_units.append(
                    f'{target.get("label", unit_id)} / spawned missile damage '
                    f'({", ".join(unsafe_unit_houses)})'
                )
            else:
                multiplier = stacking_multiplier('damage', counts['damage'])
                general_values = rule_sections.setdefault('General', {})
                for field, base_damage in target['special_damage_fields'].items():
                    general_values[field] = str(
                        max(base_damage + 1, int(round(base_damage * multiplier)))
                    )
                applied = True
        if applied:
            applied_units.append(target.get('label', unit_id))

    return (
        rule_sections,
        unique_in_order(applied_units),
        unique_in_order(skipped_units),
    )

def native_variant_unit_buff_rules(
    rewards,
    installed_sections,
    native_map_sections,
    source_unit_id,
    native_unit_ids,
    require_unlocked_access=True,
    additional_unlocked_tech_ids=None,
    share_basic_equivalent_buffs=False,
    unit_specific_mode=False,
):
    """Apply one earned unit's buffs to native scripted mission variants.

    Some campaign heroes convert through several exact TechnoType IDs and use
    native-type existence events. Cloning those IDs breaks the conversion and
    loss chain. This keeps every authored identity, applies direct stats from
    each mission base, and buffs each variant's map-local primary weapon.
    """
    source_unit_id = str(source_unit_id or '').upper()
    target = BUFF_TARGETS.get(source_unit_id, {})
    if not target:
        return {}, []
    installed_sections = installed_sections or {}
    native_map_sections = native_map_sections or {}
    counts = _active_direct_buff_counts(
        rewards,
        require_unlocked_access=require_unlocked_access,
        additional_unlocked_tech_ids=additional_unlocked_tech_ids,
        share_basic_equivalent_buffs=share_basic_equivalent_buffs,
        unit_specific_mode=unit_specific_mode,
    ).get(source_unit_id, {})
    # These identities are mission-spawned/scripted by definition. Cloaking
    # them can make player-controlled heroes invisible and unselectable when
    # no other friendly unit reveals their cell. A separately buildable player
    # clone, when present, remains eligible for the earned cloak reward.
    counts = {
        buff_type: count
        for buff_type, count in counts.items()
        if buff_type != 'cloak'
    }
    if not counts:
        return {}, []

    installed_by_lower = {
        str(section).lower(): section for section in (installed_sections or {})
    }
    native_by_lower = {
        str(section).lower(): section for section in (native_map_sections or {})
    }
    rule_sections = {}
    applied_ids = []
    weapon_ids = []
    missing = object()

    for native_unit_id in unique_in_order(
        str(item or '').upper() for item in native_unit_ids if item
    ):
        installed_name = installed_by_lower.get(native_unit_id.lower())
        native_name = native_by_lower.get(native_unit_id.lower())
        base_values = _standalone_clone_values_from_maps(
            installed_sections.get(installed_name, {}) if installed_name else {},
            native_map_sections.get(native_name, {}) if native_name else {},
        )
        if not base_values:
            continue
        effective_target = _target_with_effective_unit_stats(target, base_values)
        updated_values = dict(base_values)
        applied = False
        for buff_type in (
            'health', 'armor', 'sight', 'ammo', 'passenger_capacity',
            'open_topped', 'self_healing', 'cloak', 'sensors', 'production',
            'cost', 'speed',
        ):
            if buff_type in counts:
                applied = (
                    apply_unit_buff_value(
                        updated_values,
                        effective_target,
                        buff_type,
                        counts[buff_type],
                    )
                    or applied
                )
        if applied:
            changed_values = {}
            for key, value in updated_values.items():
                original = _value_case_insensitive(base_values, key, missing)
                if original is missing or str(original) != str(value):
                    changed_values[key] = value
            if changed_values:
                rule_sections[native_unit_id] = changed_values
                applied_ids.append(native_unit_id)

        for key, weapon_id in base_values.items():
            if str(key).lower() not in {'primary', 'eliteprimary'}:
                continue
            weapon_id = str(weapon_id or '').strip()
            if weapon_id and weapon_id.lower() not in {'none', '<none>'}:
                weapon_ids.append(weapon_id)

    weapon_buff_types = WEAPON_STAT_BUFF_TYPES.intersection(counts)
    for weapon_id in unique_in_order(weapon_ids):
        installed_name = installed_by_lower.get(weapon_id.lower())
        native_name = native_by_lower.get(weapon_id.lower())
        base_values = _standalone_clone_values_from_maps(
            installed_sections.get(installed_name, {}) if installed_name else {},
            native_map_sections.get(native_name, {}) if native_name else {},
        )
        if not base_values:
            continue
        base_stats = {
            'damage': parse_float(
                _value_case_insensitive(base_values, 'Damage', 0), 0
            ),
            'range': parse_float(
                _value_case_insensitive(base_values, 'Range', 0), 0
            ),
            'rof': parse_float(
                _value_case_insensitive(base_values, 'ROF', 0), 0
            ),
        }
        weapon_values = {}
        for buff_type in ('damage', 'range', 'reload'):
            if buff_type in weapon_buff_types:
                apply_weapon_buff_value(
                    weapon_values,
                    base_stats,
                    buff_type,
                    counts[buff_type],
                )
        if weapon_values:
            rule_sections.setdefault(weapon_id, {}).update(weapon_values)

    return rule_sections, applied_ids

def native_variant_veterancy_rules(
    lines,
    source_unit_id,
    native_unit_ids,
    source_clone_id='',
):
    """Extend an earned native-unit veterancy entry to scripted variants.

    Country Veteran* lists are the engine mechanism that promotes freshly
    created units.  Mission variants such as AHAMARTIA's ATANY keep exact
    identities for loss and respawn triggers, so they cannot inherit a cloned
    TANY identity. Only extend a list that already contains the earned source
    or its isolated player clone; this preserves the normal country-safety
    decision made earlier. Clone rewriting runs before this pass and normally
    substitutes the source ID, so checking only the native source skips variants.
    """
    source_unit_id = str(source_unit_id or '').upper()
    target = BUFF_TARGETS.get(source_unit_id, {})
    category = target.get('category')
    if category not in {'infantry', 'units', 'aircraft', 'defenses'}:
        return {}, []
    suffix = (
        'Buildings'
        if category == 'defenses'
        else house_category_suffix(target)
    )
    field = f'Veteran{suffix}'
    variants = unique_in_order(
        str(unit_id or '').upper() for unit_id in native_unit_ids if unit_id
    )
    if not variants:
        return {}, []
    earned_ids = {
        unit_id
        for unit_id in (
            source_unit_id,
            str(source_clone_id or '').upper(),
        )
        if unit_id
    }

    records = map_house_records(lines)
    player_houses = player_controlled_houses(lines, records=records)
    countries = unique_in_order(
        str(records.get(house, {}).get('country') or house.replace(' House', ''))
        for house in player_houses
        if house
    )
    rules = {}
    applied = []
    for country in countries:
        current = str(
            _value_case_insensitive(
                section_value_map_preserve(lines, country), field, ''
            )
            or ''
        )
        current_ids = {item.upper() for item in comma_items(current)}
        if earned_ids.isdisjoint(current_ids):
            continue
        updated = merge_unique_csv_bounded(
            current,
            variants,
            MAX_COUNTRY_VETERAN_VALUE_LENGTH,
        )
        if updated == current:
            continue
        rules.setdefault(country, {})[field] = updated
        applied.extend(
            unit_id for unit_id in variants if unit_id not in current_ids
        )
    return rules, unique_in_order(applied)

def scripted_reinforcement_veterancy_rules(
    lines,
    veteran_unit_ids,
    configured_helper_houses=(),
    excluded_player_houses=(),
):
    """Promote eligible player reinforcement teams without widening rewards.

    Actions 7, 80, and 107 force every created member to the TeamType's
    VeteranLevel, overriding Country Veteran* lists. Set VeteranLevel=2 only
    when every TaskForce member has earned veterancy; mixed teams containing
    any unearned or nontrainable identity remain authored.
    """
    veteran_unit_ids = {
        str(unit_id or '').upper()
        for unit_id in veteran_unit_ids
        if unit_id
    }
    if not veteran_unit_ids:
        return {}, []

    sections = all_section_value_maps(lines)
    sections_by_lower = {
        str(section).lower(): values for section, values in sections.items()
    }
    records = map_house_records(lines, sections=sections)
    excluded = {
        str(house or '').lower() for house in excluded_player_houses
    }
    player_houses = [
        house
        for house in player_controlled_houses(lines, records=records)
        if house.lower() not in excluded
    ]
    helper_houses, _ = resolve_configured_helper_houses(
        records,
        configured_helper_houses,
        player_houses,
    )
    allowed_owners = set()
    for house in unique_in_order(player_houses + helper_houses):
        record = records.get(house, {})
        country = str(record.get('country') or house.replace(' House', ''))
        allowed_owners.update({
            house.lower(),
            house.replace(' House', '').lower(),
            country.lower(),
        })

    known_teams = {
        str(team_id).lower()
        for team_id in sections_by_lower.get('teamtypes', {}).values()
        if team_id
    }
    reinforcement_teams = set()
    for line in section_lines(lines, 'Actions'):
        if '=' not in line:
            continue
        _, groups = parse_action_groups(line.split('=', 1)[1])
        for group in groups:
            if group[0] not in {'7', '80', '107'}:
                continue
            reinforcement_teams.update(
                str(parameter).lower()
                for parameter in group[1:]
                if str(parameter).lower() in known_teams
            )

    rules = {}
    promoted = []
    for team_id in sorted(reinforcement_teams):
        team_values = sections_by_lower.get(team_id, {})
        if str(team_values.get('house', '')).lower() not in allowed_owners:
            continue
        taskforce_id = str(team_values.get('taskforce', '')).lower()
        members = [
            tokens[1].upper()
            for key, value in sections_by_lower.get(taskforce_id, {}).items()
            if str(key).isdigit()
            for tokens in ([item.strip() for item in str(value).split(',')],)
            if len(tokens) >= 2 and tokens[1]
        ]
        if not members or any(
            member not in veteran_unit_ids for member in members
        ):
            continue
        try:
            current_level = int(team_values.get('veteranlevel', 1))
        except (TypeError, ValueError):
            current_level = 1
        if current_level >= 2:
            continue
        rules[team_id] = {'VeteranLevel': '2'}
        promoted.append(team_id)
    return rules, promoted
