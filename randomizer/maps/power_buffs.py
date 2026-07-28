"""Apply earned power buffs to isolated map-local superweapon clones."""

from copy import deepcopy

from randomizer.rewards.catalogue import canonical_rewards
from randomizer.rewards.power_buff_definitions import (
    POWER_BUFF_CONFIG,
)


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
    if references:
        spec['reference_keys'] = references
    clones[source] = spec
    reward['superweapon_auxiliary_clones'] = clones
    return spec


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
    spec = _ensure_auxiliary_clone(
        reward, source, warhead.get('reference_key')
    )
    spec['values'][warhead['field']] = _expanded_range(baseline, count)


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
    spec = _ensure_auxiliary_clone(reward, source, 'SW.Warhead')
    for field in warhead['fields']:
        baseline = _value(source_values, field)
        if baseline is None:
            continue
        spec['values'][field] = str(
            _scaled_integer(baseline, factor, count)
        )


def _apply_payload(reward, source_values, count):
    power_id = reward['superweapon']
    payload = POWER_BUFF_CONFIG['payload']
    rules = reward.setdefault('superweapon_rules', {})
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
            for index in range(count):
                numbers[index % len(numbers)] += 1
            # Ares requires both lists when overriding a paradrop payload.
            rules['ParaDrop.Types'] = ','.join(types)
            rules['ParaDrop.Num'] = ','.join(str(number) for number in numbers)
        return
    if power_id in payload['spy_plane_power_ids']:
        baseline = int(_value(source_values, 'SpyPlane.Count', 1) or 1)
        rules['SpyPlane.Count'] = str(baseline + count)


def apply_power_buffs_to_unlock_rewards(rewards, installed_sections):
    """Fold earned buffs into copied power rewards before clone generation."""
    canonical = canonical_rewards(rewards)
    counts = {}
    for reward in canonical:
        buff_type = reward.get('power_buff_type')
        power_id = str(reward.get('superweapon') or '')
        if reward.get('kind') == 'buff' and buff_type and power_id:
            key = (power_id.upper(), str(buff_type))
            counts[key] = counts.get(key, 0) + 1

    output = []
    for original in canonical:
        if original.get('kind') != 'superweapon':
            output.append(original)
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
            config = POWER_BUFF_CONFIG['damage']
            spec = config['direct_fields'].get(power_id)
            if spec:
                _apply_scalar_rule(
                    reward.setdefault('superweapon_rules', {}),
                    spec,
                    damage_count,
                    float(config['factor_per_stack']),
                )

        duration_count = counts.get((power_id.upper(), 'duration'), 0)
        if duration_count:
            _apply_duration(reward, installed_sections, duration_count)

        payload_count = counts.get((power_id.upper(), 'payload'), 0)
        if payload_count:
            _apply_payload(reward, source_values, payload_count)
        output.append(reward)
    return output
