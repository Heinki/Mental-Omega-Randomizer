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
        'normal_run_reward_flat': 0,
        'exclude_tier_3_offers': 0,
        'exclude_special_offers': 0,
        'exclude_power_offers': 0,
        'cross_faction_power_offers': 0,
        'enemy_armor_stacks': 0,
        'force_hardest_difficulty': 0,
        'force_enemy_challenge': 0,
        'rotate_shop_faction': 0,
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


SHOP_FACTION_ROTATION = ('Allies', 'Soviets', 'Epsilon', 'Foehn')


def modifier_shop_faction(modifier_ids, stage, default='All Campaigns'):
    """Return stage-local stock faction for Faction Roulette."""
    effects = modifier_effects(modifier_ids)
    if not effects['rotate_shop_faction']:
        return str(default or 'All Campaigns')
    return SHOP_FACTION_ROTATION[
        (max(1, int(stage)) - 1) % len(SHOP_FACTION_ROTATION)
    ]


def modifier_allows_faction_pool(modifier_ids, faction_filter):
    """Faction Roulette requires the unrestricted four-faction pool."""
    return not (
        modifier_effects(modifier_ids)['rotate_shop_faction']
        and str(faction_filter) != 'All Campaigns'
    )


def modifier_allows_shop_offer(entry, reward, modifier_ids):
    """Apply run-wide access-offer exclusions."""
    effects = modifier_effects(modifier_ids)
    reward_type = getattr(entry.reward_type, 'value', entry.reward_type)
    if reward_type == 'power_access':
        return not effects['exclude_power_offers']
    if reward_type != 'unit_access':
        return True
    if effects['exclude_tier_3_offers'] and entry.tier == 'tier_3':
        return False
    if effects['exclude_special_offers'] and reward.get('special_reward'):
        return False
    return True


def modifier_allows_loadout_entry(entry, reward, modifier_ids):
    """Apply access restrictions to permanent starting-loadout entries."""
    effects = modifier_effects(modifier_ids)
    reward_type = getattr(entry.reward_type, 'value', entry.reward_type)
    return not (
        reward_type == 'unit_access'
        and effects['exclude_tier_3_offers']
        and entry.tier == 'tier_3'
    )


def modifier_forces_hardest_difficulty(modifier_ids):
    return bool(modifier_effects(modifier_ids)['force_hardest_difficulty'])


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
