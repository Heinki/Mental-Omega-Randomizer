"""Focused schema validation for editable Shop Mode balance data."""


def _is_nonempty_string(value):
    return isinstance(value, str) and bool(value)


def validate_shop_mode_config(sections, path, invalid):
    mission_classes = {'act_1', 'act_2', 'operation', 'finale'}
    tiers = {'tier_1', 'tier_2', 'tier_3'}
    settings = sections['settings']
    integer_settings = {
        'run_length': (1, 100),
        'mission_offer_count': (1, 10),
        'unit_inventory_size': (1, 100),
        'power_inventory_size': (1, 100),
        'max_selected_permanent_units': (0, 100),
        'starting_run_coins': (0, 1000000),
        'maximum_starting_ore': (1, 1000000),
        'minimum_shop_price': (1, 1000000),
        'archipelago_purchase_locations': (0, 25),
        'archipelago_purchase_meta_coin_cost': (1, 1000000),
    }
    for key, (minimum, maximum) in integer_settings.items():
        value = settings.get(key)
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or not minimum <= value <= maximum
        ):
            invalid(f'Invalid Shop Mode setting {key!r}', path)
    if settings.get('reroll_policy') != 'per_run':
        invalid('Shop Mode reroll_policy must be "per_run"', path)
    if not isinstance(
        settings.get('archipelago_mission_victories_are_locations'), bool
    ):
        invalid(
            'Shop Mode archipelago_mission_victories_are_locations must be '
            'a boolean',
            path,
        )
    excluded_reward_ids = settings.get('excluded_reward_ids')
    if (
        not isinstance(excluded_reward_ids, list)
        or any(not _is_nonempty_string(item) for item in excluded_reward_ids)
        or len(excluded_reward_ids) != len(set(excluded_reward_ids))
    ):
        invalid('Invalid Shop Mode excluded_reward_ids', path)

    rewards = sections['mission_rewards']
    if set(rewards) != mission_classes:
        invalid('Shop Mode mission reward classes are incomplete', path)
    difficulties = []
    for class_id, definition in rewards.items():
        if not isinstance(definition, dict):
            invalid(f'Invalid Shop Mode mission reward {class_id!r}', path)
        if not _is_nonempty_string(definition.get('display_name')):
            invalid(
                f'Invalid Shop Mode mission reward field '
                f'{class_id}.display_name',
                path,
            )
        for key in ('difficulty', 'run_coins', 'meta_coins'):
            value = definition.get(key)
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < (1 if key == 'difficulty' else 0)
            ):
                invalid(
                    f'Invalid Shop Mode mission reward field {class_id}.{key}',
                    path,
                )
        difficulties.append(definition['difficulty'])
    if len(set(difficulties)) != len(mission_classes):
        invalid('Shop Mode mission difficulties must be unique', path)
    ordered_rewards = sorted(
        rewards.values(), key=lambda definition: definition['difficulty']
    )
    if any(
        harder['meta_coins'] <= easier['meta_coins']
        for easier, harder in zip(ordered_rewards, ordered_rewards[1:])
    ):
        invalid(
            'Shop Mode Gem rewards must increase with difficulty',
            path,
        )

    profiles = sections['stage_class_weights']
    if not profiles:
        invalid('Shop Mode stage class weights cannot be empty', path)
    previous_percent = 0
    for profile in profiles:
        if not isinstance(profile, dict):
            invalid('Invalid Shop Mode stage weight profile', path)
        through_percent = profile.get('through_percent')
        weights = profile.get('weights')
        if (
            not isinstance(through_percent, int)
            or isinstance(through_percent, bool)
            or not previous_percent < through_percent <= 100
            or not isinstance(weights, dict)
            or set(weights) != mission_classes
            or any(
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
                for value in weights.values()
            )
            or not any(weights.values())
        ):
            invalid('Invalid Shop Mode stage weight profile', path)
        previous_percent = through_percent
    if previous_percent != 100:
        invalid('Shop Mode stage weights must cover 100 percent', path)

    for section_name in (
        'run_unit_prices',
        'run_buff_prices',
        'permanent_unit_prices',
        'permanent_buff_prices',
    ):
        prices = sections[section_name]
        if (
            set(prices) != tiers
            or any(
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 1
                for value in prices.values()
            )
            or not prices['tier_1'] < prices['tier_2'] < prices['tier_3']
        ):
            invalid(f'Invalid Shop Mode {section_name}', path)

    required_upgrades = {
        'mission_reroll': ('rerolls_per_level',),
        'mission_difficulty_assist': ('assists_per_level',),
        'victory_run_coin_bonus': ('run_coins_per_level',),
        'starting_capital': ('run_coins_per_level',),
        'mission_starting_credits': ('credits_per_level',),
        'shop_discount': ('ore_per_level',),
        'extra_shop_stock': ('units_per_level', 'powers_per_level'),
        'expanded_loadout': ('slots_per_level',),
        'emergency_revival': ('revivals_per_run',),
        'free_buff_token': ('tokens_per_level',),
        'challenge_hunter': (
            'run_coins_per_level', 'meta_coins_every_levels'
        ),
        'recovery_salvage': ('ore_per_level', 'maximum_saved_ore'),
        'starting_buff_draft': ('buffs_per_level',),
        'discount_specialization': ('ore_per_level',),
        'permanent_challenge_slots': ('slots_per_level',),
        'coupon_book': ('ore_per_level',),
        'stock_lock': ('locks_per_stage',),
        'veteran_academy': ('veteran_loadout',),
        'gem_dividend': ('ore_per_gem', 'maximum_gems_per_level'),
        'premium_supplier': ('minimum_stage', 'guaranteed_offers'),
    }
    upgrades = sections['permanent_upgrades']
    if not set(required_upgrades).issubset(upgrades):
        invalid('Shop Mode permanent upgrades are incomplete', path)
    for upgrade_id, definition in upgrades.items():
        if not _is_nonempty_string(upgrade_id) or not isinstance(definition, dict):
            invalid(f'Invalid Shop Mode upgrade {upgrade_id!r}', path)
        maximum = definition.get('max_level')
        prices = definition.get('prices')
        effects = definition.get('effects')
        if (
            not _is_nonempty_string(definition.get('display_name'))
            or not isinstance(maximum, int)
            or isinstance(maximum, bool)
            or maximum < 1
            or not isinstance(prices, list)
            or len(prices) != maximum
            or any(
                not isinstance(price, int)
                or isinstance(price, bool)
                or price < 1
                for price in prices
            )
            or not isinstance(effects, dict)
            or not isinstance(definition.get('purchasable', True), bool)
        ):
            invalid(f'Invalid Shop Mode upgrade {upgrade_id!r}', path)
        for effect_key in required_upgrades.get(upgrade_id, ()):
            if (
                not isinstance(effects.get(effect_key), int)
                or isinstance(effects.get(effect_key), bool)
                or effects[effect_key] < 1
            ):
                invalid(
                    f'Invalid Shop Mode upgrade effect '
                    f'{upgrade_id}.{effect_key}',
                    path,
                )

    mission_effects = sections['mission_effects']
    if not mission_effects:
        invalid('Shop Mode mission_effects cannot be empty', path)
    for effect_id, definition in mission_effects.items():
        player_rewards = (
            definition.get('player_reward_ids')
            if isinstance(definition, dict) else None
        )
        enemy_reward = (
            definition.get('enemy_reward_id', '')
            if isinstance(definition, dict) else ''
        )
        exclusive_rewards = (
            definition.get('exclusive_reward_ids', [])
            if isinstance(definition, dict) else None
        )
        if (
            not _is_nonempty_string(effect_id)
            or not isinstance(definition, dict)
            or not _is_nonempty_string(definition.get('title'))
            or not _is_nonempty_string(definition.get('description'))
            or not isinstance(definition.get('bonus_run_coins'), int)
            or isinstance(definition.get('bonus_run_coins'), bool)
            or definition['bonus_run_coins'] < 0
            or not isinstance(definition.get('bonus_meta_coins'), int)
            or isinstance(definition.get('bonus_meta_coins'), bool)
            or definition['bonus_meta_coins'] < 0
            or player_rewards is not None and (
                not isinstance(player_rewards, list)
                or not player_rewards
                or any(not _is_nonempty_string(item) for item in player_rewards)
            )
            or enemy_reward and not _is_nonempty_string(enemy_reward)
            or bool(player_rewards) == bool(enemy_reward)
            or not isinstance(exclusive_rewards, list)
            or any(not _is_nonempty_string(item) for item in exclusive_rewards)
            or len(exclusive_rewards) != len(set(exclusive_rewards))
            or exclusive_rewards and not player_rewards
            or not isinstance(definition.get('buffs_allied_helpers', False), bool)
        ):
            invalid(f'Invalid Shop Mode mission effect {effect_id!r}', path)

    allowed_modifier_effects = {
        'starting_run_coins_flat',
        'run_reward_percent',
        'run_reward_flat',
        'meta_reward_percent',
        'meta_reward_flat',
        'shop_price_percent',
        'shop_price_flat',
        'hidden_offer_count',
        'player_damage_percent',
        'player_armor_percent',
        'production_time_percent',
        'combat_production_time_percent',
        'player_cost_percent',
        'support_recharge_percent',
        'unit_inventory_flat',
        'power_inventory_flat',
        'starter_veteran',
        'starter_unit_count_flat',
        'disable_rerolls',
        'disable_assists',
        'disable_revivals',
        'mission_starting_credits_flat',
        'mission_offer_count_flat',
        'liquidate_ore_after_victory',
        'challenge_meta_reward_percent',
        'normal_run_reward_percent',
    }
    percent_flat_pairs = {
        'run_reward_percent': 'run_reward_flat',
        'meta_reward_percent': 'meta_reward_flat',
        'shop_price_percent': 'shop_price_flat',
    }
    for modifier_id, definition in sections['modifiers'].items():
        effects = definition.get('effects') if isinstance(definition, dict) else None
        has_benefit = bool(isinstance(effects, dict) and (
            effects.get('starting_run_coins_flat', 0) > 0
            or effects.get('run_reward_flat', 0) > 0
            or effects.get('meta_reward_flat', 0) > 0
            or effects.get('run_reward_percent', 100) > 100
            or effects.get('meta_reward_percent', 100) > 100
            or effects.get('shop_price_percent', 100) < 100
            or effects.get('shop_price_flat', 0) < 0
            or effects.get('player_damage_percent', 100) > 100
            or effects.get('production_time_percent', 100) < 100
            or effects.get('unit_inventory_flat', 0) > 0
            or effects.get('power_inventory_flat', 0) > 0
            or effects.get('starter_veteran', 0) > 0
            or effects.get('support_recharge_percent', 100) < 100
            or effects.get('challenge_meta_reward_percent', 100) > 100
        ))
        has_penalty = bool(isinstance(effects, dict) and (
            effects.get('starting_run_coins_flat', 0) < 0
            or effects.get('run_reward_flat', 0) < 0
            or effects.get('meta_reward_flat', 0) < 0
            or effects.get('run_reward_percent', 100) < 100
            or effects.get('meta_reward_percent', 100) < 100
            or effects.get('shop_price_percent', 100) > 100
            or effects.get('shop_price_flat', 0) > 0
            or effects.get('hidden_offer_count', 0) > 0
            or effects.get('player_armor_percent', 100) < 100
            or effects.get('player_cost_percent', 100) > 100
            or effects.get('combat_production_time_percent', 100) > 100
            or effects.get('starter_unit_count_flat', 0) < 0
            or effects.get('disable_rerolls', 0) > 0
            or effects.get('disable_assists', 0) > 0
            or effects.get('disable_revivals', 0) > 0
            or effects.get('mission_starting_credits_flat', 0) < 0
            or effects.get('mission_offer_count_flat', 0) < 0
            or effects.get('liquidate_ore_after_victory', 0) > 0
            or effects.get('normal_run_reward_percent', 100) < 100
        ))
        mixes_percent_and_flat = bool(isinstance(effects, dict) and any(
            effects.get(percent_key, 100) != 100
            and effects.get(flat_key, 0) != 0
            for percent_key, flat_key in percent_flat_pairs.items()
        ))
        if (
            not _is_nonempty_string(modifier_id)
            or not isinstance(definition, dict)
            or not _is_nonempty_string(definition.get('display_name'))
            or not _is_nonempty_string(definition.get('description'))
            or not isinstance(effects, dict)
            or not effects
            or not set(effects).issubset(allowed_modifier_effects)
            or any(
                not isinstance(value, int) or isinstance(value, bool)
                for value in effects.values()
            )
            or any(
                key.endswith('_percent') and value < 0
                for key, value in effects.items()
            )
            or not 0 <= effects.get('hidden_offer_count', 0) <= settings.get(
                'mission_offer_count', 0
            )
            or not has_benefit
            or not has_penalty
            or mixes_percent_and_flat
        ):
            invalid(f'Invalid Shop Mode modifier {modifier_id!r}', path)
