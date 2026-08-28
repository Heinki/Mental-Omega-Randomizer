"""Pure aggregation of configured Shop Mode modifier effects."""

from fractions import Fraction
from hashlib import sha256

from .config import SHOP_CONFIG
from .model import ShopModeConfig


def modifier_effects(modifier_ids, config: ShopModeConfig = SHOP_CONFIG):
    """Combine selected modifier fields in stable input order.

    Percent effects multiply. Flat effects add. Unknown IDs fail instead of
    silently changing a saved run's balance.
    """
    effects = {
        'starting_run_coins_flat': 0,
        'run_reward_percent': Fraction(1, 1),
        'run_reward_flat': 0,
        'meta_reward_percent': Fraction(1, 1),
        'meta_reward_flat': 0,
        'shop_price_percent': Fraction(1, 1),
        'shop_price_flat': 0,
        'hidden_offer_count': 0,
        'player_damage_percent': Fraction(1, 1),
        'player_armor_percent': Fraction(1, 1),
        'production_time_percent': Fraction(1, 1),
        'combat_production_time_percent': Fraction(1, 1),
        'player_cost_percent': Fraction(1, 1),
        'support_recharge_percent': Fraction(1, 1),
        'unit_inventory_flat': 0,
        'power_inventory_flat': 0,
        'starter_veteran': 0,
        'starter_unit_count_flat': 0,
        'disable_rerolls': 0,
        'disable_assists': 0,
        'disable_revivals': 0,
        'mission_starting_credits_flat': 0,
        'mission_offer_count_flat': 0,
        'liquidate_ore_after_victory': 0,
        'challenge_meta_reward_percent': Fraction(1, 1),
        'normal_run_reward_percent': Fraction(1, 1),
    }
    seen = set()
    for modifier_id in modifier_ids or ():
        modifier_id = str(modifier_id)
        if modifier_id in seen:
            continue
        seen.add(modifier_id)
        definition = config.modifiers.get(modifier_id)
        if definition is None:
            raise ValueError(f'Unknown Shop Mode modifier: {modifier_id!r}')
        for key, value in definition.effects.items():
            if key.endswith('_percent'):
                effects[key] *= Fraction(int(value), 100)
            else:
                effects[key] += int(value)
    return effects


def modifier_difficulty(modifier_ids):
    """Return one visible difficulty point per distinct modifier."""
    return len(tuple(dict.fromkeys(str(item) for item in modifier_ids or ())))


def modifier_mission_offer_count(
    modifier_ids, config: ShopModeConfig = SHOP_CONFIG
):
    effects = modifier_effects(modifier_ids, config)
    return max(
        1,
        min(
            config.mission_offer_count,
            config.mission_offer_count + effects['mission_offer_count_flat'],
        ),
    )


def hidden_offer_codes(run, config: ShopModeConfig = SHOP_CONFIG):
    """Choose reward-hidden offers without consuming gameplay RNG."""
    count = max(0, int(modifier_effects(
        run.modifiers, config
    )['hidden_offer_count']))
    offers = tuple(run.mission_offers)
    if not count or not offers:
        return ()
    ranked = sorted(
        offers,
        key=lambda offer: sha256(
            f'{run.seed}:{run.stage}:{run.rerolls_used}:'
            f'{offer.mission_code}:blind-choice'.encode('utf-8')
        ).digest(),
    )
    return tuple(offer.mission_code for offer in ranked[:count])
