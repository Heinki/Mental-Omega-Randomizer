"""Typed adapter for editable Shop Mode balance configuration."""

from randomizer.config.static import load_static_config

from .model import (
    MissionEconomyClass,
    MissionRewardDefinition,
    ModifierDefinition,
    PermanentUpgradeDefinition,
    ShopModeConfig,
    ShopPowerPriceDefinition,
    ShopTargetPriceDefinition,
    StageDifficultyProfile,
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
    stage_difficulty_weights = tuple(
        StageDifficultyProfile(
            through_percent=int(profile['through_percent']),
            weights={
                str(difficulty): int(weight)
                for difficulty, weight in profile['weights'].items()
            },
        )
        for profile in sections['stage_difficulty_weights']
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
            purchasable=bool(definition.get('purchasable', True)),
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
        power_inventory_size=int(settings['power_inventory_size']),
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
        excluded_reward_ids=tuple(
            str(reward_id) for reward_id in settings['excluded_reward_ids']
        ),
        mission_rewards=mission_rewards,
        stage_class_weights=stage_weights,
        stage_difficulty_weights=stage_difficulty_weights,
        power_target_prices={
            str(target_id): ShopPowerPriceDefinition(
                run_access=definition['run_access'],
                run_buff=definition['run_buff'],
            )
            for target_id, definition
            in sections['power_target_prices'].items()
        },
        unit_target_prices={
            str(target_id): ShopTargetPriceDefinition(
                run_access=definition['run_access'],
                run_buff=definition['run_buff'],
                permanent_access=definition['permanent_access'],
                permanent_buff=definition['permanent_buff'],
            )
            for target_id, definition in sections['unit_target_prices'].items()
        },
        permanent_upgrades=upgrades,
        modifiers=modifiers,
    )


SHOP_CONFIG = load_shop_mode_config()
