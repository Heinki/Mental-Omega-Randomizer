"""Typed access to editable reward, clone, and assistance tuning."""

from randomizer_static_config import load_static_config


_CONFIG = load_static_config('rewards/tuning.json')

BUFF_EFFECTS = _CONFIG['buff_effects']
CLONE_POLICY = _CONFIG['clone_policy']
MISSION_ASSISTANCE = _CONFIG['mission_assistance']
REWARD_PLANNING = _CONFIG['reward_planning']


def stacking_multiplier(effect, count):
    """Return one configured bounded exponential multiplier."""
    values = BUFF_EFFECTS[effect]
    multiplier = float(values['factor_per_stack']) ** max(0, int(count))
    if 'minimum_multiplier' in values:
        multiplier = max(float(values['minimum_multiplier']), multiplier)
    if 'maximum_multiplier' in values:
        multiplier = min(float(values['maximum_multiplier']), multiplier)
    return multiplier


def stacking_amount(effect, count):
    """Return one configured bounded additive amount."""
    values = BUFF_EFFECTS[effect]
    amount = float(values['amount_per_stack']) * max(0, int(count))
    return min(float(values['maximum_amount']), amount)
