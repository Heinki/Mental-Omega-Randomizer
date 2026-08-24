"""Typed adapter for editable Shop Mode balance configuration."""

from randomizer.config.static import load_static_config

from .model import (
    MissionEconomyClass,
    MissionRewardDefinition,
    ModifierDefinition,
    PermanentUpgradeDefinition,
    ShopModeConfig,
    StageWeightProfile,
)


def load_shop_mode_config() -> ShopModeConfig:
    sections = load_static_config('shop_mode.json')
    settings = sections['settings']
    mission_rewards = {
        MissionEconomyClass(class_id): MissionRewardDefinition(
            class_id=MissionEconomyClass(class_id),
            display_name=str(definition['display_name']),
            difficulty=int(definition['difficulty']),
            run_coins=int(definition['run_coins']),
            meta_coins=int(definition['meta_coins']),
        )
        for class_id, definition in sections['mission_rewards'].items()
    }
    stage_weights = tuple(
        StageWeightProfile(
            through_percent=int(profile['through_percent']),
            weights={
                MissionEconomyClass(class_id): int(weight)
                for class_id, weight in profile['weights'].items()
            },
        )
        for profile in sections['stage_class_weights']
    )
    upgrades = {
        upgrade_id: PermanentUpgradeDefinition(
            id=upgrade_id,
            display_name=str(definition['display_name']),
            max_level=int(definition['max_level']),
            prices=tuple(int(price) for price in definition['prices']),
            effects={
                str(effect): int(value)
                for effect, value in definition['effects'].items()
            },
        )
        for upgrade_id, definition in sections['permanent_upgrades'].items()
    }
    modifiers = {
        modifier_id: ModifierDefinition(
            id=modifier_id,
            display_name=str(definition['display_name']),
            description=str(definition['description']),
            effects={
                str(effect): int(value)
                for effect, value in definition['effects'].items()
            },
        )
        for modifier_id, definition in sections['modifiers'].items()
    }
    return ShopModeConfig(
        run_length=int(settings['run_length']),
        mission_offer_count=int(settings['mission_offer_count']),
        unit_inventory_size=int(settings['unit_inventory_size']),
        max_selected_permanent_units=int(
            settings['max_selected_permanent_units']
        ),
        starting_run_coins=int(settings['starting_run_coins']),
        maximum_starting_ore=int(settings['maximum_starting_ore']),
        minimum_shop_price=int(settings['minimum_shop_price']),
        reroll_policy=str(settings['reroll_policy']),
        archipelago_purchase_locations=int(
            settings['archipelago_purchase_locations']
        ),
        archipelago_purchase_meta_coin_cost=int(
            settings['archipelago_purchase_meta_coin_cost']
        ),
        archipelago_mission_victories_are_locations=bool(
            settings['archipelago_mission_victories_are_locations']
        ),
        mission_rewards=mission_rewards,
        stage_class_weights=stage_weights,
        run_unit_prices={
            str(tier): int(price)
            for tier, price in sections['run_unit_prices'].items()
        },
        run_buff_prices={
            str(tier): int(price)
            for tier, price in sections['run_buff_prices'].items()
        },
        permanent_unit_prices={
            str(tier): int(price)
            for tier, price in sections['permanent_unit_prices'].items()
        },
        permanent_buff_prices={
            str(tier): int(price)
            for tier, price in sections['permanent_buff_prices'].items()
        },
        permanent_upgrades=upgrades,
        modifiers=modifiers,
    )


SHOP_CONFIG = load_shop_mode_config()
