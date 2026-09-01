"""Apply earned power buffs to isolated map-local superweapon clones."""

from copy import deepcopy

from randomizer.rewards.catalogue import REWARD_POOL, canonical_rewards
from randomizer.rewards.power_buff_definitions import (
    POWER_BUFF_CONFIG,
    power_buff_stack_limit,
)


def building_bound_power_launch_rewards(rewards, owned_clone_ids):
    """Bind access-granted building powers to their isolated player clone."""
    canonical = canonical_rewards(rewards)
    bindings = {}
    for reward in canonical:
        power_id = str(reward.get('building_superweapon') or '').upper()
        if not power_id:
            continue
        for source_id in reward.get('rules', {}):
            clone_id = owned_clone_ids.get(str(source_id).upper())
            if clone_id:
                bindings.setdefault(power_id, []).append(clone_id)
    if not bindings:
        return list(rewards)

    power_rewards = {
        str(reward.get('superweapon') or '').upper(): reward
        for reward in REWARD_POOL
        if reward.get('kind') == 'superweapon'
        and reward.get('superweapon')
    }
    missing = sorted(set(bindings) - set(power_rewards))
    if missing:
        raise ValueError(
            'Special-building power has no matching unlock reward: '
            + ', '.join(missing)
        )

    output = []
    explicit_power_ids = {
        str(reward.get('superweapon') or '').upper()
        for reward in canonical
        if reward.get('kind') == 'superweapon'
    }
    for reward in canonical:
        power_id = str(reward.get('superweapon') or '').upper()
        if power_id not in bindings:
            output.append(reward)
            continue
        attached = deepcopy(reward)
        attached['superweapon_primary_buildings'] = list(dict.fromkeys(
            bindings[power_id]
        ))
        attached['superweapon_grant_action'] = True
        attached['_runtime_canonical'] = True
        output.append(attached)
    for power_id, building_ids in bindings.items():
        if power_id in explicit_power_ids:
            continue
        attached = deepcopy(power_rewards[power_id])
        attached['superweapon_primary_buildings'] = list(dict.fromkeys(
            building_ids
        ))
        attached['_runtime_canonical'] = True
        output.append(attached)
    return output


def equivalent_payload_unit_buff_rewards(
    rewards,
    unlocked_power_ids,
    available_unit_ids,
    player_faction,
):
    """Copy one faction hero's earned combat buffs to Libra Clones.

    The runtime copies retain only buff type/count semantics. LIBRC keeps its
    own identity, base stats, weapons, art, voices, armor, and behavior.
    """
    canonical = canonical_rewards(rewards)
    unlocked_powers = {
        str(power_id).upper() for power_id in (unlocked_power_ids or ())
    }
    available_units = {
        str(unit_id).upper() for unit_id in (available_unit_ids or ())
    }
    additions = []
    configurations = POWER_BUFF_CONFIG['payload'].get(
        'equivalent_hero_buff_sources', {}
    )
    for power_id, config in configurations.items():
        if str(power_id).upper() not in unlocked_powers:
            continue
        preferred = str(config.get('preferred_source') or '').upper()
        faction_source = str(
            (config.get('sources_by_faction') or {}).get(player_faction, '')
        ).upper()
        source_unit = (
            preferred
            if preferred and preferred in available_units
            else faction_source
        )
        if not source_unit:
            continue
        payload_unit = str(config.get('payload_unit') or '').upper()
        if not payload_unit:
            continue
        for reward in canonical:
            if (
                reward.get('kind') != 'buff'
                or str(reward.get('unit') or '').upper() != source_unit
            ):
                continue
            equivalent = dict(reward)
            equivalent['unit'] = payload_unit
            equivalent['force_direct_unit_buff'] = True
            equivalent['_runtime_canonical'] = True
            additions.append(equivalent)
    return list(rewards) + additions


def _value(values, key, default=None):
    lowered = str(key).lower()
    return next(
        (value for name, value in values.items() if str(name).lower() == lowered),
        default,
    )


def _format_number(value):
    return f'{float(value):.3f}'.rstrip('0').rstrip('.')


def _source_values(reward, installed_sections):
    values = dict(installed_sections.get(reward['superweapon'], {}))
    values.update(reward.get('superweapon_rules') or {})
    return values


def _scaled_integer(baseline, factor, count):
    baseline = int(baseline)
    scaled = int(round(baseline * (float(factor) ** count)))
    if factor >= 1:
        return max(baseline + 1, scaled)
    return min(baseline - 1, scaled)


def _expanded_range(baseline, count):
    parts = [part.strip() for part in str(baseline).split(',')]
    if len(parts) == 2:
        increase = (
            int(POWER_BUFF_CONFIG['area']['rectangle_amount_per_stack'])
            * count
        )
        return ','.join(str(max(1, int(part) + increase)) for part in parts)
    increase = float(POWER_BUFF_CONFIG['area']['amount_per_stack']) * count
    return _format_number(float(parts[0]) + increase)


def _ensure_auxiliary_clone(reward, source, reference_key=None):
    clones = deepcopy(reward.get('superweapon_auxiliary_clones') or {})
    spec = deepcopy(clones.get(source) or {})
    spec.setdefault('values', {})
    references = list(spec.get('reference_keys') or ())
    if reference_key and reference_key not in references:
        references.append(reference_key)
    if str(reference_key or '').lower() == 'sw.warhead':
        # Ares does not allocate a WarheadType merely because a map contains
        # its section. The private type must be present in [Warheads] before
        # the cloned superweapon's SW.Warhead reference is parsed.
        spec.setdefault('list', 'Warheads')
    if references:
        spec['reference_keys'] = references
    clones[source] = spec
    reward['superweapon_auxiliary_clones'] = clones
    return spec


def _ensure_techno_clone(reward, source):
    clones = deepcopy(reward.get('superweapon_techno_clones') or {})
    spec = deepcopy(clones.get(source) or {})
    spec.setdefault('values', {})
    clones[source] = spec
    reward['superweapon_techno_clones'] = clones
    return spec


def _ensure_global_rules(reward, section):
    sections = deepcopy(reward.get('superweapon_global_rules') or {})
    values = deepcopy(sections.get(section) or {})
    sections[section] = values
    reward['superweapon_global_rules'] = sections
    return values


def _apply_scalar_rule(rules, spec, count, factor):
    rules[spec['field']] = str(
        _scaled_integer(spec['baseline'], factor, count)
    )


def _apply_area(reward, installed_sections, count):
    power_id = reward['superweapon']
    area = POWER_BUFF_CONFIG['area']
    direct = area['direct_fields'].get(power_id)
    if direct:
        reward.setdefault('superweapon_rules', {})[direct['field']] = (
            _expanded_range(direct['baseline'], count)
        )
    warhead = area['warhead_fields'].get(power_id)
    if not warhead:
        return
    source = warhead['source']
    source_values = installed_sections.get(source, {})
    baseline = _value(source_values, warhead['field'])
    if baseline is None:
        return
    if warhead.get('clone_group') == 'techno':
        spec = _ensure_techno_clone(
            reward, warhead.get('clone_key') or source
        )
    else:
        spec = _ensure_auxiliary_clone(
            reward, source, warhead.get('reference_key')
        )
    spec['values'][warhead['field']] = _expanded_range(baseline, count)


def _apply_damage(reward, installed_sections, count):
    power_id = reward['superweapon']
    damage = POWER_BUFF_CONFIG['damage']
    factor = float(damage['factor_per_stack'])
    direct = damage['direct_fields'].get(power_id)
    if direct:
        _apply_scalar_rule(
            reward.setdefault('superweapon_rules', {}),
            direct,
            count,
            factor,
        )
    techno = damage.get('techno_fields', {}).get(power_id)
    if not techno:
        return
    source = techno['source']
    baseline = techno.get('baseline')
    if baseline is None:
        baseline = _value(
            installed_sections.get(source, {}), techno['field']
        )
    if baseline is None:
        return
    spec = _ensure_techno_clone(
        reward, techno.get('clone_key') or source
    )
    spec['values'][techno['field']] = str(
        _scaled_integer(baseline, factor, count)
    )


def _apply_health(reward, installed_sections, count):
    health = POWER_BUFF_CONFIG['health']
    field_spec = health['techno_fields'].get(reward['superweapon'])
    if not field_spec:
        return
    source = field_spec['source']
    baseline = field_spec.get('baseline')
    if baseline is None:
        baseline = _value(
            installed_sections.get(source, {}), field_spec['field']
        )
    if baseline is None:
        return
    spec = _ensure_techno_clone(
        reward, field_spec.get('clone_key') or source
    )
    spec['values'][field_spec['field']] = str(_scaled_integer(
        baseline,
        float(health['factor_per_stack']),
        count,
    ))


def _apply_duration(reward, installed_sections, count):
    power_id = reward['superweapon']
    duration = POWER_BUFF_CONFIG['duration']
    factor = float(duration['factor_per_stack'])
    direct = duration['direct_fields'].get(power_id)
    if direct:
        _apply_scalar_rule(
            reward.setdefault('superweapon_rules', {}),
            direct,
            count,
            factor,
        )
    warhead = duration['warhead_fields'].get(power_id)
    if not warhead:
        return
    source = warhead['source']
    source_values = installed_sections.get(source, {})
    if warhead.get('clone_group') == 'techno':
        spec = _ensure_techno_clone(reward, source)
    else:
        spec = _ensure_auxiliary_clone(reward, source, 'SW.Warhead')
    for field in warhead['fields']:
        baseline = _value(source_values, field)
        if baseline is None:
            continue
        spec['values'][field] = str(
            _scaled_integer(baseline, factor, count)
        )


def _apply_draining_techno_lifetime(
    reward,
    installed_sections,
    health_count,
    duration_count,
):
    field_spec = POWER_BUFF_CONFIG['duration'].get(
        'draining_techno_fields', {}
    ).get(reward['superweapon'])
    if not field_spec or not (health_count or duration_count):
        return
    source_values = installed_sections.get(field_spec['source'], {})
    baseline_strength = _value(source_values, field_spec['strength_field'])
    if baseline_strength is None:
        return
    techno_spec = _ensure_techno_clone(
        reward, field_spec.get('clone_key') or field_spec['source']
    )
    effective_strength = techno_spec['values'].get(
        field_spec['strength_field'], baseline_strength
    )
    techno_spec['values']['Armor'] = field_spec['armor']

    duration_factor = (
        float(POWER_BUFF_CONFIG['duration']['factor_per_stack'])
        ** duration_count
    )
    strength_factor = float(effective_strength) / float(baseline_strength)
    self_damage_percent = (
        float(field_spec['base_verses_percent'])
        * strength_factor
        / duration_factor
    )
    _ensure_global_rules(reward, 'ArmorTypes')[field_spec['armor']] = (
        field_spec['armor_parent']
    )
    _ensure_global_rules(
        reward, field_spec['damage_warhead']
    )[f'Versus.{field_spec["armor"]}'] = (
        f'{_format_number(self_damage_percent)}%'
    )


def _apply_effect(reward, count):
    effect = POWER_BUFF_CONFIG['effect']
    field_spec = effect['multiplier_fields'].get(reward['superweapon'])
    if not field_spec:
        return
    baseline = float(field_spec['baseline'])
    scaled_delta = abs(1.0 - baseline) * (
        float(effect['factor_per_stack']) ** count
    )
    if field_spec['mode'] == 'reduction':
        value = max(0.1, 1.0 - scaled_delta)
    else:
        value = 1.0 + scaled_delta
    spec = _ensure_auxiliary_clone(
        reward,
        field_spec['source'],
        field_spec.get('reference_key'),
    )
    spec['values'][field_spec['field']] = _format_number(value)


def _vehicle_armor_rules(installed_sections, source_values, verses):
    values = [
        item.strip()
        for item in str(_value(source_values, 'Verses', '')).split(',')
    ]
    if len(values) != 11:
        return {}
    for index in (3, 4, 5):
        values[index] = verses
    rules = {'Verses': ','.join(values)}
    seen = set()
    for vehicle_id in installed_sections.get('VehicleTypes', {}).values():
        vehicle_values = installed_sections.get(str(vehicle_id).strip(), {})
        explicitly_unselectable = (
            str(_value(vehicle_values, 'Selectable', '')).lower() == 'no'
        )
        implementation_helper = (
            str(_value(vehicle_values, 'Insignificant', '')).lower() == 'yes'
            and str(_value(vehicle_values, 'DontScore', '')).lower() == 'yes'
        )
        if explicitly_unselectable or implementation_helper:
            continue
        armor = str(_value(vehicle_values, 'Armor', '')).strip()
        lowered = armor.lower()
        if (
            not armor
            or lowered in {'light', 'medium', 'heavy'}
            or lowered in seen
        ):
            continue
        seen.add(lowered)
        rules[f'Versus.{armor}'] = verses
    return rules


def _apply_targeting(reward, installed_sections):
    field_spec = POWER_BUFF_CONFIG['targeting'][
        'vehicle_armor_fields'
    ].get(reward['superweapon'])
    if not field_spec:
        return
    source_values = installed_sections.get(field_spec['source'], {})
    rules = _vehicle_armor_rules(
        installed_sections, source_values, field_spec['verses']
    )
    if not rules:
        return
    spec = _ensure_techno_clone(
        reward, field_spec.get('clone_key') or field_spec['source']
    )
    spec['values'].update(rules)
    if field_spec.get('clear_designators'):
        reward.setdefault('superweapon_rules', {})['SW.Designators'] = ''


def _apply_vision(reward, installed_sections, count):
    power_id = reward['superweapon']
    vision = POWER_BUFF_CONFIG['vision']
    field_spec = vision['power_fields'].get(power_id)
    if not field_spec:
        return
    source = field_spec['source']
    source_values = installed_sections.get(source, {})
    baseline = _value(source_values, field_spec['field'])
    if baseline is None:
        return
    spec = _ensure_techno_clone(reward, source)
    spec.update({
        'source': source,
        'clone': field_spec['clone'],
        'list': field_spec['list'],
        'reference_keys': ('SpyPlane.Type',),
    })
    amount = int(vision['amount_per_stack']) * count
    spec['values'][field_spec['field']] = str(int(baseline) + amount)


def _apply_payload(reward, source_values, count):
    power_id = reward['superweapon']
    payload = POWER_BUFF_CONFIG['payload']
    rules = reward.setdefault('superweapon_rules', {})
    internal = payload.get('internal_unit_delivery_fields', {}).get(power_id)
    if internal:
        delivered = [
            item.strip()
            for item in str(internal['baseline']).split(',')
            if item.strip()
        ]
        if delivered:
            sections = deepcopy(
                reward.get('superweapon_rule_sections') or {}
            )
            values = deepcopy(sections.get(internal['section']) or {})
            values[internal['field']] = ','.join(
                delivered
                + [delivered[index % len(delivered)] for index in range(count)]
            )
            sections[internal['section']] = values
            reward['superweapon_rule_sections'] = sections
        return
    if power_id in payload['unit_delivery_power_ids']:
        delivered = [
            item.strip()
            for item in str(_value(source_values, 'Deliver.Types', '')).split(',')
            if item.strip()
        ]
        if delivered:
            rules['Deliver.Types'] = ','.join(
                delivered
                + [delivered[index % len(delivered)] for index in range(count)]
            )
        return
    if power_id in payload['paradrop_power_ids']:
        types = [
            item.strip()
            for item in str(_value(source_values, 'ParaDrop.Types', '')).split(',')
            if item.strip()
        ]
        numbers = [
            max(0, int(item.strip()))
            for item in str(_value(source_values, 'ParaDrop.Num', '')).split(',')
            if item.strip()
        ]
        if types and len(types) == len(numbers):
            if power_id in payload.get('paradrop_all_type_increases', ()):
                numbers = [number + count for number in numbers]
            else:
                for index in range(count):
                    numbers[index % len(numbers)] += 1
            # Ares requires both lists when overriding a paradrop payload.
            rules['ParaDrop.Types'] = ','.join(types)
            rules['ParaDrop.Num'] = ','.join(str(number) for number in numbers)
        return
    if power_id in payload.get('drop_pod_power_ids', ()):
        minimum = int(_value(source_values, 'DropPod.Minimum', 0) or 0)
        maximum = int(_value(source_values, 'DropPod.Maximum', minimum) or minimum)
        if minimum > 0 and maximum >= minimum:
            rules['DropPod.Minimum'] = str(minimum + count)
            rules['DropPod.Maximum'] = str(maximum + count)
        types = [
            item.strip()
            for item in str(_value(source_values, 'DropPod.Types', '')).split(',')
            if item.strip()
        ]
        additions = list(
            payload.get('drop_pod_type_weight_additions', {}).get(power_id, ())
        )
        if types and additions:
            # Ares selects each DropPod.Types entry with equal probability.
            # Add both configured non-baseline roles per stack so larger Moon
            # drops scale as a mixed force instead of chiefly adding DESORs.
            rules['DropPod.Types'] = ','.join(types + additions * count)
        return
    if power_id in payload['spy_plane_power_ids']:
        baseline = int(_value(source_values, 'SpyPlane.Count', 1) or 1)
        rules['SpyPlane.Count'] = str(baseline + count)


def apply_power_buffs_to_unlock_rewards(rewards, installed_sections):
    """Return real power unlocks with any earned buffs folded into them.

    Buff rewards are stored independently. They never enter grant/clone output
    and therefore cannot create a power without its actual unlock reward.
    """
    canonical = canonical_rewards(rewards)
    counts = {}
    for reward in canonical:
        buff_type = reward.get('power_buff_type')
        power_id = str(reward.get('superweapon') or '')
        if reward.get('kind') == 'buff' and buff_type and power_id:
            key = (power_id.upper(), str(buff_type))
            limit = power_buff_stack_limit(reward)
            next_count = counts.get(key, 0) + 1
            counts[key] = min(next_count, limit) if limit is not None else next_count

    output = []
    for original in canonical:
        if original.get('kind') != 'superweapon':
            continue
        reward = deepcopy(original)
        # Runtime copy already came through canonical_rewards. Preserve folded
        # clone overrides if downstream helpers canonicalize again.
        reward['_runtime_canonical'] = True
        power_id = str(reward.get('superweapon') or '')
        source_values = _source_values(reward, installed_sections)
        recharge_count = counts.get((power_id.upper(), 'recharge'), 0)
        if recharge_count:
            config = POWER_BUFF_CONFIG['recharge']
            baseline = float(_value(source_values, 'RechargeTime', 0) or 0)
            if baseline > 0:
                value = (
                    baseline
                    * float(config['factor_per_stack']) ** recharge_count
                )
                reward.setdefault('superweapon_rules', {})[
                    'RechargeTime'
                ] = _format_number(value)

        cost_count = counts.get((power_id.upper(), 'cost'), 0)
        if cost_count:
            config = POWER_BUFF_CONFIG['cost']
            baseline = int(_value(source_values, 'Money.Amount', 0) or 0)
            if baseline < 0:
                value = max(
                    int(config['minimum_absolute']),
                    int(round(
                        abs(baseline)
                        * float(config['factor_per_stack']) ** cost_count
                    )),
                )
                reward.setdefault('superweapon_rules', {})[
                    'Money.Amount'
                ] = str(-value)

        area_count = counts.get((power_id.upper(), 'area'), 0)
        if area_count:
            _apply_area(reward, installed_sections, area_count)

        damage_count = counts.get((power_id.upper(), 'damage'), 0)
        if damage_count:
            _apply_damage(reward, installed_sections, damage_count)

        health_count = counts.get((power_id.upper(), 'health'), 0)
        if health_count:
            _apply_health(reward, installed_sections, health_count)

        duration_count = counts.get((power_id.upper(), 'duration'), 0)
        if duration_count:
            _apply_duration(reward, installed_sections, duration_count)
        _apply_draining_techno_lifetime(
            reward,
            installed_sections,
            health_count,
            duration_count,
        )

        effect_count = counts.get((power_id.upper(), 'effect'), 0)
        if effect_count:
            _apply_effect(reward, effect_count)

        targeting_count = counts.get((power_id.upper(), 'targeting'), 0)
        if targeting_count:
            _apply_targeting(reward, installed_sections)

        vision_count = counts.get((power_id.upper(), 'vision'), 0)
        if vision_count:
            _apply_vision(reward, installed_sections, vision_count)

        payload_count = counts.get((power_id.upper(), 'payload'), 0)
        if payload_count:
            _apply_payload(reward, source_values, payload_count)
        output.append(reward)
    return output
