"""Pure Shop Mode reward and price calculations."""

from .config import SHOP_CONFIG
from .model import CurrencyReward, MissionEconomyClass, ShopModeConfig
from .modifiers import modifier_effects


def _bounded_upgrade_level(config, upgrade_id, level):
    definition = config.permanent_upgrades[upgrade_id]
    try:
        level = int(level)
    except (TypeError, ValueError):
        level = 0
    return max(0, min(definition.max_level, level))


def mission_reward(
    mission_class,
    *,
    victory_coin_bonus_level=0,
    modifiers=(),
    successful=True,
    config: ShopModeConfig = SHOP_CONFIG,
):
    """Return configured victory currency; failures always return zero."""
    if not successful:
        return CurrencyReward()
    try:
        class_id = MissionEconomyClass(mission_class)
    except ValueError as exc:
        raise ValueError(
            f'Unknown Shop Mode mission class: {mission_class!r}'
        ) from exc
    definition = config.mission_rewards[class_id]
    effects = modifier_effects(modifiers, config)
    base_run_coins = max(
        0, int(definition.run_coins * effects['run_reward_percent'])
    )
    meta_coins = max(
        0, int(definition.meta_coins * effects['meta_reward_percent'])
    )
    level = _bounded_upgrade_level(
        config, 'victory_run_coin_bonus', victory_coin_bonus_level
    )
    per_level = config.permanent_upgrades[
        'victory_run_coin_bonus'
    ].effects['run_coins_per_level']
    victory_bonus = level * int(per_level)
    return CurrencyReward(
        run_coins=base_run_coins + victory_bonus,
        meta_coins=meta_coins,
        base_run_coins=base_run_coins,
        victory_bonus_run_coins=victory_bonus,
    )


def starting_run_coins(
    *,
    starting_capital_level=0,
    modifiers=(),
    config: ShopModeConfig = SHOP_CONFIG,
):
    level = _bounded_upgrade_level(
        config, 'starting_capital', starting_capital_level
    )
    per_level = config.permanent_upgrades['starting_capital'].effects[
        'run_coins_per_level'
    ]
    effects = modifier_effects(modifiers, config)
    return min(
        config.maximum_starting_ore,
        max(
            0,
            config.starting_run_coins
            + level * int(per_level)
            + effects['starting_run_coins_flat'],
        ),
    )


def discounted_shop_price(
    base_price,
    *,
    shop_discount_level=0,
    modifiers=(),
    config: ShopModeConfig = SHOP_CONFIG,
):
    try:
        base_price = int(base_price)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'Invalid Shop Mode base price: {base_price!r}') from exc
    if base_price < 0:
        raise ValueError(f'Invalid Shop Mode base price: {base_price!r}')
    effects = modifier_effects(modifiers, config)
    modified = (
        int(base_price * effects['shop_price_percent'])
        + effects['shop_price_flat']
    )
    level = _bounded_upgrade_level(
        config, 'shop_discount', shop_discount_level
    )
    percent_per_level = config.permanent_upgrades['shop_discount'].effects[
        'percent_per_level'
    ]
    discounted = modified * max(0, 100 - level * percent_per_level) // 100
    return max(config.minimum_shop_price, discounted)


def run_unit_price(
    tier,
    *,
    shop_discount_level=0,
    modifiers=(),
    config: ShopModeConfig = SHOP_CONFIG,
):
    try:
        base_price = config.run_unit_prices[str(tier)]
    except KeyError as exc:
        raise ValueError(f'Unknown Shop Mode unit tier: {tier!r}') from exc
    return discounted_shop_price(
        base_price,
        shop_discount_level=shop_discount_level,
        modifiers=modifiers,
        config=config,
    )


def run_buff_price(
    tier,
    *,
    shop_discount_level=0,
    modifiers=(),
    config: ShopModeConfig = SHOP_CONFIG,
):
    try:
        base_price = config.run_buff_prices[str(tier)]
    except KeyError as exc:
        raise ValueError(f'Unknown Shop Mode buff tier: {tier!r}') from exc
    return discounted_shop_price(
        base_price,
        shop_discount_level=shop_discount_level,
        modifiers=modifiers,
        config=config,
    )


def permanent_unit_price(tier, *, config: ShopModeConfig = SHOP_CONFIG):
    try:
        return int(config.permanent_unit_prices[str(tier)])
    except KeyError as exc:
        raise ValueError(f'Unknown Shop Mode unit tier: {tier!r}') from exc


def permanent_buff_price(tier, *, config: ShopModeConfig = SHOP_CONFIG):
    try:
        return int(config.permanent_buff_prices[str(tier)])
    except KeyError as exc:
        raise ValueError(f'Unknown Shop Mode buff tier: {tier!r}') from exc


def permanent_upgrade_price(
    upgrade_id,
    next_level,
    *,
    config: ShopModeConfig = SHOP_CONFIG,
):
    definition = config.permanent_upgrades.get(str(upgrade_id))
    if definition is None:
        raise ValueError(f'Unknown Shop Mode permanent upgrade: {upgrade_id!r}')
    try:
        next_level = int(next_level)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'Invalid Shop Mode upgrade level: {next_level!r}') from exc
    if not 1 <= next_level <= definition.max_level:
        raise ValueError(
            f'Shop Mode upgrade {upgrade_id!r} has no level {next_level}'
        )
    return definition.prices[next_level - 1]
