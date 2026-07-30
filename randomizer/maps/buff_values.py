"""Low-level TechnoType and WeaponType buff calculations."""

from ._shared import (
    BUFF_EFFECTS,
    BUFF_TARGETS,
    CLONE_REQUIRED_BUFF_TYPES,
    MANDATORY_EXCLUDED_BUFF_TYPE_IDS,
    RANDOMIZER_TYPE_LIST_KEY_START,
    WEAPON_STAT_BUFF_TYPES,
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

def apply_unit_buff_value(values, target, buff_type, count):
    if buff_type == 'health':
        multiplier = stacking_multiplier('health', count)
        values['Strength'] = str(max(1, int(round(target['strength'] * multiplier))))
    elif buff_type == 'sight':
        values['Sight'] = str(int(round(
            target['sight'] + stacking_amount('sight', count)
        )))
    elif buff_type == 'ammo':
        values['Ammo'] = str(int(round(
            target['ammo'] + stacking_amount('ammo', count)
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
        current_strength = int(values.get('Strength', target['strength']))
        heal_fraction = min(
            float(BUFF_EFFECTS['maximum_self_heal_fraction']),
            float(BUFF_EFFECTS['defense_self_heal_fraction']) * count,
        )
        values['SelfHealing.Amount'] = str(
            max(1, int(round(
                current_strength
                * heal_fraction
            )))
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
        multiplier = stacking_multiplier('cost', count)
        values['Cost'] = str(max(0, int(round(target['cost'] * multiplier))))
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
        current_strength = int(values.get('Strength', target['strength']))
        values['Strength'] = str(max(1, int(round(current_strength / multiplier))))
    else:
        return False
    return True

def apply_weapon_buff_value(values, base_stats, buff_type, count):
    if buff_type == 'damage' and base_stats.get('damage', 0) > 0:
        multiplier = stacking_multiplier('damage', count)
        base_damage = int(round(base_stats['damage']))
        values['Damage'] = str(max(base_damage + 1, int(round(base_damage * multiplier))))
    elif buff_type == 'range' and base_stats.get('range', 0) > 0:
        values['Range'] = format_multiplier(
            base_stats['range'] + stacking_amount('range', count)
        )
    elif buff_type == 'reload' and base_stats.get('rof', 0) > 1:
        multiplier = stacking_multiplier('reload', count)
        values['ROF'] = str(max(1, int(round(base_stats['rof'] * multiplier))))
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
    identity_rewards = []
    for reward in role_rewards:
        identity_rewards.append(reward)
        if reward.get('kind') != 'buff':
            continue
        source_id = str(reward.get('unit') or '').upper()
        for variant_id in sorted(linked_buff_variant_ids(source_id) - {source_id}):
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
        direct_chaos_types = (
            {'production', 'cost', 'speed', 'armor'}
            if unit_specific_mode
            else set()
        )
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
            and not (buff_type == 'damage' and target.get('special_damage_fields'))
        ):
            continue
        required_field = {
            'health': 'strength',
            'sight': 'sight',
            'ammo': 'ammo',
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

def _register_map_type(section_rules, lines, installed_sections, list_section, type_id):
    installed_entries = installed_sections.get(list_section, {})
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
