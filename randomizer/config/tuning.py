"""Typed access to editable reward, clone, and assistance tuning."""

from randomizer.config.static import load_static_config


_CONFIG = load_static_config('rewards/tuning.json')

BUFF_EFFECTS = _CONFIG['buff_effects']
CLONE_POLICY = _CONFIG['clone_policy']
MISSION_ASSISTANCE = _CONFIG['mission_assistance']
REWARD_PLANNING = _CONFIG['reward_planning']


def stacking_multiplier(effect, count):
    """Return one configured unbounded exponential multiplier."""
    values = BUFF_EFFECTS[effect]
    return float(values['factor_per_stack']) ** max(0, int(count))


def stacking_amount(effect, count):
    """Return one configured unbounded additive amount."""
    values = BUFF_EFFECTS[effect]
    return float(values['amount_per_stack']) * max(0, int(count))
