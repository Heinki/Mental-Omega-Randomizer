"""Low-level TechnoType and WeaponType buff calculations."""

from math import isfinite

from ._shared import (
    BUFF_EFFECTS,
    BUFF_TARGETS,
    CLONE_REQUIRED_BUFF_TYPES,
    MANDATORY_EXCLUDED_BUFF_TYPE_IDS,
    RANDOMIZER_TYPE_LIST_KEY_START,
    WEAPON_STAT_BUFF_TYPES,
    all_section_value_maps,
    buff_stack_limit,
    buffs_with_unlocked_access,
    capped_movement_speed,
    expand_equivalent_role_buffs,
    linked_buff_variant_ids,
    map_house_records,
    player_controlled_houses,
    player_house_from_map,
    resolve_configured_helper_houses,
    section_value_map_preserve,
    stacking_amount,
    stacking_multiplier,
    unique_in_order,
)
from .base import (
    _next_reserved_type_key,
    format_multiplier,
    parse_float,
)
from randomizer.config.tuning import (
    stacked_cost,
    stacked_self_heal_amount,
    stacked_weapon_damage,
    stacked_weapon_rof,
)


MIN_SAFE_TECHNO_STRENGTH = 2


def parsed_safe_strength(value):
    """Return an engine-usable TechnoType Strength or ``None``.

    A Strength of zero is the engine/default failure state and is displayed as
    a one-hitpoint object.  One is technically parseable but is never a sane
    player-unit baseline.  Reject both instead of hiding a bad load behind a
    later ``max(1, ...)`` calculation.
    """
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if not isfinite(number):
        return None
    strength = int(round(number))
    return strength if strength >= MIN_SAFE_TECHNO_STRENGTH else None


def strength_from_values(values):
    """Read Strength case-insensitively from one INI value mapping."""
    for key, value in (values or {}).items():
        if str(key).lower() == 'strength':
            return parsed_safe_strength(value)
    return None


def set_safe_strength(values, strength):
    """Write one canonical Strength key and remove casing duplicates."""
    raw_strength = strength
    strength = parsed_safe_strength(raw_strength)
    if strength is None:
        raise ValueError(f'Unsafe TechnoType Strength: {raw_strength!r}')
    for key in list(values):
        if str(key).lower() == 'strength':
            values.pop(key, None)
    values['Strength'] = str(strength)
    return strength


def resolved_safe_strength(target, *value_sources):
    """Resolve health from live/template mappings, then curated metadata."""
    for values in value_sources:
        strength = strength_from_values(values)
        if strength is not None:
            return strength
    strength = parsed_safe_strength((target or {}).get('strength'))
    if strength is None:
        raise ValueError(
            'No safe TechnoType Strength in effective values or buff target.'
        )
    return strength


def normalize_unit_strength(values, target, *fallback_value_sources):
    """Repair a missing/invalid live Strength from reviewed fallbacks."""
    current = strength_from_values(values)
    strength = (
        current
        if current is not None
        else resolved_safe_strength(target, *fallback_value_sources)
    )
    set_safe_strength(values, strength)
    return strength


def veteran_armor_safety_rules(lines, installed_sections):
    """Repair map VeteranArmor values that can collapse promoted health."""
    map_general = section_value_map_preserve(lines, 'General')
    map_value = next(
        (
            value for key, value in map_general.items()
            if str(key).lower() == 'veteranarmor'
        ),
        None,
    )
    if map_value is None:
        return {}
    try:
        map_multiplier = float(str(map_value).strip())
    except (TypeError, ValueError):
        map_multiplier = 0.0
    if isfinite(map_multiplier) and map_multiplier >= 1.0:
        return {}

    installed_general = next(
        (
            values for section, values in (installed_sections or {}).items()
            if str(section).lower() == 'general'
        ),
        {},
    )
    installed_value = next(
        (
            value for key, value in installed_general.items()
            if str(key).lower() == 'veteranarmor'
        ),
        1.0,
    )
    try:
        installed_multiplier = float(str(installed_value).strip())
    except (TypeError, ValueError):
        installed_multiplier = 1.0
    if not isfinite(installed_multiplier) or installed_multiplier < 1.0:
        installed_multiplier = 1.0
    return {
        'General': {
            'VeteranArmor': format_multiplier(installed_multiplier),
        },
    }

def apply_unit_buff_value(values, target, buff_type, count):
    if buff_type == 'health':
        multiplier = stacking_multiplier('health', count)
        base_strength = resolved_safe_strength(target)
        set_safe_strength(values, int(round(base_strength * multiplier)))
    elif buff_type == 'sight':
        values['Sight'] = str(int(round(
            target['sight'] + stacking_amount('sight', count)
        )))
    elif buff_type == 'ammo':
        values['Ammo'] = str(int(round(
            target['ammo'] + stacking_amount('ammo', count)
        )))
    elif buff_type == 'storage':
        values['Storage'] = str(int(round(
            target['storage'] + stacking_amount('storage', count)
        )))
    elif buff_type == 'income':
        values['ProduceCashAmount'] = str(int(round(
            target['produce_cash_amount'] + stacking_amount('income', count)
        )))
    elif buff_type == 'passenger_capacity':
        if int(target.get('passengers', 0)) < 1:
            return False
        values['Passengers'] = str(int(target['passengers']) + int(count))
    elif buff_type == 'open_topped':
        if int(target.get('passengers', 0)) < 1:
            return False
        values['OpenTopped'] = 'yes'
    elif buff_type == 'self_healing':
        values['SelfHealing'] = 'yes'
        # Ares defaults to one hitpoint per RepairRate tick. Give every stack
        # another configured fraction of effective maximum strength.
        current_strength = resolved_safe_strength(target, values)
        values['SelfHealing.Amount'] = str(
            stacked_self_heal_amount(current_strength, count)
        )
    elif buff_type == 'cloak':
        values['Cloakable'] = 'yes'
        values['Cloakable.Stages'] = '1'
        values['CloakingSpeed'] = '1'
        values['CloakSound'] = 'none'
    elif buff_type == 'sensors':
        values['Sensors'] = 'yes'
        values['SensorsSight'] = str(int(round(
            target.get('sight', 5) + float(BUFF_EFFECTS['sensor_sight_bonus'])
        )))
    elif buff_type == 'cost':
        values['Cost'] = str(stacked_cost(target['cost'], count))
    elif buff_type == 'production':
        multiplier = stacking_multiplier('production', count)
        existing_key = next(
            (
                key
                for key in values
                if str(key).lower() == 'buildtimemultiplier'
            ),
            'BuildTimeMultiplier',
        )
        base = parse_float(values.get(existing_key), 1.0)
        values[existing_key] = format_multiplier(base * multiplier)
    elif buff_type == 'speed':
        values['Speed'] = str(capped_movement_speed(target, count))
    elif buff_type == 'armor':
        multiplier = stacking_multiplier('armor', count)
        current_strength = resolved_safe_strength(target, values)
        set_safe_strength(values, int(round(current_strength / multiplier)))
    else:
        return False
    return True

def apply_weapon_buff_value(values, base_stats, buff_type, count):
    if buff_type == 'damage' and base_stats.get('damage', 0) > 0:
        base_damage = int(round(base_stats['damage']))
        values['Damage'] = str(stacked_weapon_damage(base_damage, count))
    elif buff_type == 'range' and base_stats.get('range', 0) > 0:
        values['Range'] = format_multiplier(
            base_stats['range'] + stacking_amount('range', count)
        )
    elif buff_type == 'reload' and base_stats.get('rof', 0) > 1:
        values['ROF'] = str(stacked_weapon_rof(base_stats['rof'], count))
    else:
        return False
    return True

def _active_direct_buff_counts(
    rewards,
    require_unlocked_access=True,
    additional_unlocked_tech_ids=None,
    share_basic_equivalent_buffs=False,
    unit_specific_mode=False,
    include_house_scoped_fallback=False,
    house_scoped_only=False,
    global_production_unit_ids=None,
):
    """Group applicable direct TechnoType/WeaponType buffs by source unit."""
    grouped_counts = {}
    active_rewards = buffs_with_unlocked_access(
        rewards,
        require_unlocked_access=require_unlocked_access,
        additional_unlocked_tech_ids=additional_unlocked_tech_ids,
        share_basic_equivalent_buffs=share_basic_equivalent_buffs,
    )
    role_rewards = expand_equivalent_role_buffs(
        active_rewards,
        enabled=share_basic_equivalent_buffs,
    )
    global_production_count = 0
    global_production_limit = None
    identity_rewards = []
    for reward in role_rewards:
        identity_rewards.append(reward)
        if reward.get('kind') != 'buff':
            continue
        source_id = str(reward.get('unit') or '').upper()
        for variant_id in sorted(linked_buff_variant_ids(source_id) - {source_id}):
            variant_target = BUFF_TARGETS.get(variant_id, {})
            if (
                variant_target.get('linked_buff_weapon_only')
                and reward.get('buff_type') not in WEAPON_STAT_BUFF_TYPES
            ):
                continue
            variant_reward = dict(reward)
            variant_reward['unit'] = variant_id
            identity_rewards.append(variant_reward)
    for reward in identity_rewards:
        if reward.get('kind') != 'buff':
            continue
        buff_type = reward.get('buff_type')
        unit_id = str(reward.get('unit') or '').upper()
        target = BUFF_TARGETS.get(unit_id, {})
        if not unit_id or not target:
            continue
        if buff_type == 'production' and target.get('global_production'):
            global_production_count += 1
            global_production_limit = buff_stack_limit(reward)
            if global_production_limit is not None:
                global_production_count = min(
                    global_production_count,
                    global_production_limit,
                )
            continue
        if unit_id in MANDATORY_EXCLUDED_BUFF_TYPE_IDS.get(
            buff_type, frozenset()
        ):
            # Defense in depth for old saves and externally supplied runtime
            # rewards. Catalogue/UI exclusion is not the only safety boundary.
            continue
        if house_scoped_only and buff_type not in {
            'production', 'cost', 'speed', 'armor',
        }:
            continue
        # Production is always written to the exact owned TechnoType clone;
        # CountryType BuildTime*Mult is not reliable in campaign play. Cost
        # and armor are also clone-required so unit rewards never expand into
        # category-wide effects. Chaos keeps speed clone-local as before.
        direct_chaos_types = {'production'}
        if unit_specific_mode:
            direct_chaos_types.update({'cost', 'speed', 'armor'})
        if reward.get('force_direct_unit_buff'):
            direct_chaos_types.update(
                {'production', 'cost', 'speed', 'armor'}
            )
        if include_house_scoped_fallback:
            direct_chaos_types.update(
                {'production', 'cost', 'speed', 'armor'}
            )
        if buff_type not in CLONE_REQUIRED_BUFF_TYPES and buff_type not in direct_chaos_types:
            continue
        if (
            buff_type in WEAPON_STAT_BUFF_TYPES
            and not target.get('weapons')
            and not target.get('runtime_transform')
            and not (buff_type == 'damage' and target.get('special_damage_fields'))
        ):
            continue
        required_field = {
            'health': 'strength',
            'sight': 'sight',
            'ammo': 'ammo',
            'storage': 'storage',
            'income': 'produce_cash_amount',
            'passenger_capacity': 'passengers',
            'open_topped': 'passengers',
            'cost': 'cost',
            'speed': 'speed',
            'armor': 'strength',
            'build_limit': 'build_limit',
            'building_limit': 'build_limit',
        }.get(buff_type)
        if required_field and required_field not in target:
            continue
        key = (unit_id, buff_type)
        grouped_counts[key] = grouped_counts.get(key, 0) + 1
        limit = buff_stack_limit(reward)
        if limit is not None:
            grouped_counts[key] = min(grouped_counts[key], limit)

    if global_production_count:
        for unit_id in {
            str(item).upper()
            for item in (global_production_unit_ids or ())
        }:
            target = BUFF_TARGETS.get(unit_id, {})
            if target.get('category') not in {
                'infantry', 'units', 'aircraft', 'defenses',
                'special_buildings',
            }:
                continue
            key = (unit_id, 'production')
            grouped_counts[key] = (
                grouped_counts.get(key, 0) + global_production_count
            )
            if global_production_limit is not None:
                grouped_counts[key] = min(
                    grouped_counts[key],
                    global_production_limit,
                )

    counts_by_unit = {}
    for (unit_id, buff_type), count in grouped_counts.items():
        counts_by_unit.setdefault(unit_id, {})[buff_type] = count

    return counts_by_unit

def _allowed_buff_house_names(
    lines,
    configured_helper_houses=(),
    excluded_player_houses=(),
):
    records = map_house_records(lines)
    player_house = player_house_from_map(lines, records=records)
    if not player_house:
        return records, set()
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
        allowed_names.extend((
            house,
            house.replace(' House', ''),
            house + ' House' if not house.lower().endswith(' house') else house,
            record.get('country'),
        ))
    return records, {name.lower() for name in allowed_names if name}

def _register_map_type(
    section_rules,
    lines,
    installed_sections,
    list_section,
    type_id,
    map_entries=None,
):
    installed_entries = installed_sections.get(list_section, {})
    if map_entries is None:
        map_entries = section_value_map_preserve(lines, list_section)
    pending_entries = section_rules.setdefault(list_section, {})
    registered = {
        str(value).lower()
        for value in list(installed_entries.values())
        + list(map_entries.values())
        + list(pending_entries.values())
    }
    if type_id.lower() in registered:
        return
    keys = {str(key).lower() for key in map_entries}
    keys.update(str(key).lower() for key in pending_entries)
    key, _ = _next_reserved_type_key(keys, RANDOMIZER_TYPE_LIST_KEY_START)
    pending_entries[key] = type_id


def reconcile_generated_techno_registrations(
    lines,
    installed_sections,
    expected_by_list,
):
    """Repair generated TechnoTypes lost to pending registry-key collisions.

    Several map-rule builders allocate reserved numeric keys independently
    before their batches are merged.  Two batches can therefore both choose
    the same key; a normal mapping update retains only the later value.  The
    generated TechnoType section still exists, but the engine does not load it
    as that category and can instantiate it with the one-HP default state.

    Reconcile once against the completed map.  This also serves as a launch
    invariant: every intended generated TechnoType must have both a definition
    and a category-list registration.
    """
    repair_rules = {}
    repaired = []
    missing_definitions = []
    map_sections = {
        str(section).lower(): values
        for section, values in all_section_value_maps(lines).items()
    }
    for list_section, type_ids in expected_by_list.items():
        map_entries = map_sections.get(list_section.lower(), {})
        for type_id in unique_in_order(
            str(value or '').strip() for value in type_ids
        ):
            if not type_id:
                continue
            if not (
                map_sections.get(type_id.lower())
                or installed_sections.get(type_id, {})
            ):
                missing_definitions.append(type_id)
                continue
            before = {
                str(value).lower()
                for value in list(
                    installed_sections.get(list_section, {}).values()
                )
                + list(
                    map_entries.values()
                )
                + list(repair_rules.get(list_section, {}).values())
            }
            _register_map_type(
                repair_rules,
                lines,
                installed_sections,
                list_section,
                type_id,
                map_entries=map_entries,
            )
            if type_id.lower() not in before:
                repaired.append(type_id)
    if missing_definitions:
        raise ValueError(
            'Generated TechnoType definition missing before registry '
            'reconciliation: ' + ', '.join(unique_in_order(missing_definitions))
        )
    return repair_rules, unique_in_order(repaired)
