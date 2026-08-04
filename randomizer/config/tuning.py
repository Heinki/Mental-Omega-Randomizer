"""Typed access to editable reward, clone, and assistance tuning."""

from functools import lru_cache

from randomizer.config.static import load_static_config


_CONFIG = load_static_config('rewards/tuning.json')

BUFF_EFFECTS = _CONFIG['buff_effects']
CLONE_POLICY = _CONFIG['clone_policy']
MISSION_ASSISTANCE = _CONFIG['mission_assistance']
REWARD_PLANNING = _CONFIG['reward_planning']


def mission_assistance_stack_count(count):
    """Clamp retry assistance to its configured mission-only stack cap."""
    try:
        count = max(0, int(count))
    except (TypeError, ValueError):
        return 0
    stack_limit = max(1, int(MISSION_ASSISTANCE.get('stack_limit', 10)))
    return min(count, stack_limit)


def stacking_multiplier(effect, count):
    """Return one configured exponential multiplier within its exact cap."""
    values = BUFF_EFFECTS[effect]
    count = max(0, int(count))
    requested_count = count
    stack_limit = values.get('stack_limit')
    if stack_limit is not None:
        count = min(count, int(stack_limit))
    multiplier = float(values['factor_per_stack']) ** count
    minimum = values.get('minimum_multiplier')
    maximum = values.get('maximum_multiplier')
    if stack_limit is not None and requested_count >= int(stack_limit):
        if minimum is not None:
            multiplier = float(minimum)
        elif maximum is not None:
            multiplier = float(maximum)
    if minimum is not None:
        multiplier = max(float(minimum), multiplier)
    if maximum is not None:
        multiplier = min(float(maximum), multiplier)
    return multiplier


def stacking_amount(effect, count):
    """Return one configured additive amount within its exact cap."""
    values = BUFF_EFFECTS[effect]
    count = max(0, int(count))
    requested_count = count
    stack_limit = values.get('stack_limit')
    if stack_limit is not None:
        count = min(count, int(stack_limit))
    amount = float(values['amount_per_stack']) * count
    maximum = values.get('maximum_amount')
    if (
        maximum is not None
        and stack_limit is not None
        and requested_count >= int(stack_limit)
    ):
        amount = float(maximum)
    if maximum is not None:
        amount = min(float(maximum), amount)
    return amount


def stacked_cost(base_cost, count):
    """Return the configured rounded cost for a cumulative stack count."""
    base_cost = max(0, int(round(float(base_cost))))
    count = max(0, int(count))
    return max(0, int(round(
        base_cost * stacking_multiplier('cost', count)
    )))


def stacked_weapon_damage(base_damage, count):
    """Return capped damage with at least one point gained per useful stack."""
    base_damage = max(1, int(round(float(base_damage))))
    count = max(0, int(count))
    if count == 0:
        return base_damage
    maximum = int(round(
        base_damage
        * float(BUFF_EFFECTS['damage'].get('maximum_multiplier', 1.0))
    ))
    multiplied = int(round(
        base_damage * stacking_multiplier('damage', count)
    ))
    return min(maximum, max(base_damage + 1, multiplied))


def stacked_weapon_rof(base_rof, count):
    """Return ROF delay with at least one tick removed per useful stack."""
    base_rof = max(1, int(round(float(base_rof))))
    count = max(0, int(count))
    rounded = max(1, int(round(
        base_rof * stacking_multiplier('reload', count)
    )))
    if count > 0 and base_rof > 1:
        return min(rounded, base_rof - 1)
    return rounded


def stacked_self_heal_amount(base_strength, count):
    """Return healing where every accepted stack adds at least one hitpoint."""
    base_strength = max(1, int(round(float(base_strength))))
    count = max(0, int(count))
    maximum = max(1, int(round(
        base_strength * float(BUFF_EFFECTS['maximum_self_heal_fraction'])
    )))
    fraction = min(
        float(BUFF_EFFECTS['maximum_self_heal_fraction']),
        float(BUFF_EFFECTS['defense_self_heal_fraction']) * count,
    )
    return min(maximum, max(1, int(round(base_strength * fraction))))


@lru_cache(maxsize=None)
def stacking_stack_limit(effect):
    """Return first stack reaching an effect cap, or ``None`` if unbounded."""
    values = BUFF_EFFECTS[effect]
    configured_limit = values.get('stack_limit')
    if configured_limit is not None:
        return max(1, int(configured_limit))
    if (
        'minimum_multiplier' not in values
        and 'maximum_multiplier' not in values
        and 'maximum_amount' not in values
    ):
        return None
    calculator = (
        stacking_amount
        if 'amount_per_stack' in values
        else stacking_multiplier
    )
    for count in range(1, 10001):
        if calculator(effect, count) == calculator(effect, count + 1):
            return count
    raise ValueError(f'Buff effect {effect!r} does not reach its configured cap')
