"""Focused executable contracts for Shop Mode domain and persistence."""

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from randomizer.config.schema import StaticConfigError, validate_sections
from randomizer.config.static import load_static_config
from randomizer.core.storage import atomic_write_json, atomic_write_text
from randomizer.missions.tier_one import (
    _tier_one_airfield_rules,
    tier_one_defense_ids,
    tier_one_unit_ids,
)
from randomizer.maps.shop_modifiers import apply_shop_clone_modifiers
from randomizer.rewards.catalogue import REWARD_BY_NAME
from randomizer.rewards.rules import tech_ids_for_rewards
from randomizer.ui.cameos import (
    ARCHIPELAGO_CAMEO_PATH,
    ensure_superweapon_cameos,
    ensure_unit_cameos,
)

from .catalogue import canonical_reward_for_id, shop_catalogue
from .active import (
    active_shop_power_ids,
    active_shop_rewards,
    active_shop_starter_defense_ids,
    active_shop_starter_unit_ids,
    active_shop_tech_ids,
)
from .archipelago import (
    ap_unit_entitlement_ids,
    archipelago_shop_identity,
    shop_reward_ids_from_ap_ledger,
)
from .archipelago_purchases import (
    archipelago_purchase_placement_text,
    archipelago_purchase_records,
)
from .config import SHOP_CONFIG
from .economy import (
    discounted_shop_price,
    mission_reward,
    permanent_buff_price,
    permanent_unit_price,
    run_buff_price,
    run_reward_price,
    starting_run_coins,
)
from .meta import (
    purchase_permanent_buff,
    purchase_permanent_unit,
    purchase_permanent_upgrade,
    validate_starting_loadout,
)
from .inventory import (
    guarantee_premium_offer,
    preserve_locked_offer,
    rotating_power_inventory,
    rotating_unit_inventory,
)
from .missions import (
    classify_mission,
    generate_mission_offers,
    mission_classes_for_stage,
)
from .mission_modifiers import (
    MISSION_MODIFIERS,
    mission_modifier_for_offer,
    mission_modifier_for_run_offer,
)
from .modifiers import (
    hidden_offer_codes,
    modifier_difficulty,
    modifier_effects,
    modifier_mission_offer_count,
)
from .model import (
    SHOP_ACCESS_REWARD_MODE,
    BuffPurchase,
    MissionEconomyClass,
    MissionOffer,
    PurchaseRecord,
    PurchaseResult,
    RunStatus,
    ShopProfile,
    ShopCatalogueEntry,
    ShopRewardType,
    ShopRun,
)
from .purchases import apply_validated_run_purchase, validate_run_purchase
from .persistence import (
    ShopPersistenceError,
    ShopPersistencePaths,
    ShopRepository,
)
from .service import ShopProgressionService
from .state import ShopStateError, normalize_shop_profile, normalize_shop_run
from .summary import reward_breakdown_lines, run_summary_lines
from .transitions import (
    abandon_run,
    apply_mission_difficulty_assist,
    apply_mission_failure,
    apply_mission_victory,
    commit_selected_mission,
    merge_archipelago_entitlements,
    reroll_missions,
    select_mission,
    start_new_run,
)


def _reward(reward_id):
    reward = canonical_reward_for_id(reward_id)
    if reward.get('name') != reward_id:
        raise AssertionError(f'Missing self-check reward {reward_id!r}')
    return reward


def _requested_upgrade_modifier_checks():
    required_upgrades = {
        'coupon_book', 'stock_lock', 'veteran_academy',
        'gem_dividend', 'premium_supplier',
    }
    required_modifiers = {
        'glass_cannon', 'overclocked_factories', 'black_market',
        'elite_force', 'no_safety_net', 'support_doctrine',
        'war_economy', 'narrow_intelligence', 'liquid_assets',
        'treasure_hunter',
    }
    all_modifier_ids = tuple(SHOP_CONFIG.modifiers)
    effects = modifier_effects(all_modifier_ids)

    tier_one = ShopCatalogueEntry(
        'Test Tier One Access', ShopRewardType.UNIT_ACCESS,
        'TESTONE', 'tier_1', None, ('Allies',),
    )
    tier_two = ShopCatalogueEntry(
        'Test Tier Two Access', ShopRewardType.UNIT_ACCESS,
        'TESTTWO', 'tier_2', None, ('Allies',),
    )
    other = ShopCatalogueEntry(
        'Test Other Access', ShopRewardType.UNIT_ACCESS,
        'TESTOTHER', 'tier_1', None, ('Allies',),
    )
    locked = preserve_locked_offer((tier_one, other), tier_two)
    premium = guarantee_premium_offer(
        (tier_one, other),
        (tier_one, tier_two, other),
        run_seed='SELF-CHECK',
        stage=3,
        minimum_stage=3,
    )

    profile = ShopProfile(
        permanent_upgrades={'gem_dividend': 3},
    )
    final_offer = MissionOffer('FINALE', MissionEconomyClass.FINALE)
    final_run = ShopRun(
        run_id='dividend',
        seed='DIVIDEND',
        status=RunStatus.ACTIVE,
        stage=SHOP_CONFIG.run_length,
        run_length=SHOP_CONFIG.run_length,
        run_coins=20,
        mission_offers=(final_offer,),
        selected_mission_code='FINALE',
        mission_committed=True,
    )
    dividend = apply_mission_victory(profile, final_run, 'FINALE')

    liquid_offer = MissionOffer('NEXT', MissionEconomyClass.ACT_1)
    liquid_run = replace(
        final_run,
        run_id='liquid',
        stage=1,
        run_coins=99,
        modifiers=('liquid_assets',),
        mission_offers=(MissionOffer('NOW', MissionEconomyClass.ACT_1),),
        selected_mission_code='NOW',
    )
    liquid = apply_mission_victory(
        ShopProfile(), liquid_run, 'NOW', next_offers=(liquid_offer,)
    )
    liquid_reward = mission_reward(
        MissionEconomyClass.ACT_1, modifiers=('liquid_assets',)
    )

    rules = {
        'CLONE': {
            'Strength': '111',
            'Cost': '100',
            'BuildTimeMultiplier': '1',
        },
        'WEAPON': {'Damage': '115'},
    }
    report = apply_shop_clone_modifiers(
        rules,
        {'E1': {'clone_id': 'CLONE', 'weapon_clone_ids': {'M60': 'WEAPON'}}},
        {
            'shop_player_damage_percent': 1.25,
            'shop_player_armor_percent': 0.8,
            'shop_production_time_percent': 0.75,
            'shop_combat_production_time_percent': 1.2,
            'shop_player_cost_percent': 1.2,
            'shop_modifier_armor_seed_stacks': {'E1': 0},
            'shop_modifier_damage_seed_stacks': {'E1': 0},
        },
    )
    challenge = SimpleNamespace(
        challenge=True,
        bonus_run_coins=0,
        bonus_meta_coins=0,
    )
    challenge_reward = mission_reward(
        MissionEconomyClass.ACT_1,
        modifiers=('treasure_hunter',),
        mission_modifier=challenge,
    )
    normal_reward = mission_reward(
        MissionEconomyClass.ACT_1,
        modifiers=('treasure_hunter',),
    )
    base_reward = SHOP_CONFIG.mission_rewards[MissionEconomyClass.ACT_1]

    return {
        'requested_permanent_upgrades_valid': required_upgrades.issubset(
            SHOP_CONFIG.permanent_upgrades
        ),
        'requested_modifiers_valid': required_modifiers.issubset(
            SHOP_CONFIG.modifiers
        ),
        'modifier_composition_valid': bool(
            modifier_difficulty(all_modifier_ids) == len(all_modifier_ids)
            and float(
                effects['production_time_percent'] * effects[
                    'combat_production_time_percent'
                ]
            ) == 0.9
            and effects['disable_rerolls']
            and effects['disable_assists']
            and effects['disable_revivals']
            and modifier_mission_offer_count(('narrow_intelligence',)) == 2
        ),
        'stock_upgrade_effects_valid': bool(
            tier_two in locked
            and tier_two in premium
            and len(locked) == 2
            and len(premium) == 2
        ),
        'gem_dividend_valid': bool(
            dividend.reward.gem_dividend_meta_coins == 3
            and dividend.profile.meta_coins == dividend.reward.meta_coins
        ),
        'liquid_assets_valid': bool(
            liquid.run.run_coins == liquid_reward.run_coins
        ),
        'treasure_hunter_valid': bool(
            challenge_reward.meta_coins == base_reward.meta_coins * 2
            and normal_reward.base_run_coins
            == int(base_reward.run_coins * 0.75)
        ),
        'shop_clone_modifiers_valid': bool(
            rules['CLONE']['Strength'] == '80'
            and rules['CLONE']['Cost'] == '120'
            and rules['CLONE']['BuildTimeMultiplier'] == '0.9'
            and rules['WEAPON']['Damage'] == '125'
            and all(report.values())
        ),
    }


def _permanent_feature_checks(mission_pool):
    catalogue = shop_catalogue()
    unit_entries = tuple(
        item for item in catalogue
        if item.reward_type is ShopRewardType.UNIT_ACCESS
    )
    buff_entry = next(
        item for item in catalogue
        if item.reward_type is ShopRewardType.UNIT_BUFF
    )
    power_entries = tuple(
        item for item in catalogue
        if item.reward_type is ShopRewardType.POWER_ACCESS
    )
    power_rewards = tuple(
        canonical_reward_for_id(item.reward_id) for item in power_entries
    )
    power_ids = {
        str(
            reward.get('cameo_superweapon') or reward.get('superweapon') or ''
        ).upper()
        for reward in power_rewards
        if reward.get('cameo_superweapon') or reward.get('superweapon')
    }
    sidebar_overrides = {
        str(
            reward.get('cameo_superweapon') or reward.get('superweapon')
        ).upper(): str(
            (reward.get('superweapon_rules') or {}).get('SidebarPCX')
        )
        for reward in power_rewards
        if (reward.get('superweapon_rules') or {}).get('SidebarPCX')
    }
    power_cameos = ensure_superweapon_cameos(power_ids, sidebar_overrides)
    offers = generate_mission_offers(
        mission_pool, run_seed='SHOP-PERMANENT-FEATURES', stage=1
    )
    upgrade_levels = {
        'extra_shop_stock': 2,
        'expanded_loadout': 1,
        'emergency_revival': 1,
        'free_buff_token': 1,
        'challenge_hunter': 5,
        'recovery_salvage': 5,
        'starting_buff_draft': 1,
        'discount_specialization': 5,
        'permanent_challenge_slots': 1,
    }
    profile = ShopProfile(
        meta_coins=1000,
        permanent_upgrades=upgrade_levels,
        salvaged_run_coins=7,
    )
    run = ShopRun(
        run_id='permanent-features',
        seed='SHOP-PERMANENT-FEATURES',
        status=RunStatus.ACTIVE,
        stage=1,
        run_length=SHOP_CONFIG.run_length,
        run_coins=20,
        mission_offers=offers,
        starting_draft_buffs=(BuffPurchase(buff_entry.reward_id, 1),),
        reward_settings={'shop_discount_specialization': 'Units'},
    )
    early_forced = mission_modifier_for_run_offer(
        run, offers[0], challenge_slots=1
    )
    late_run = replace(run, stage=6)
    forced = mission_modifier_for_run_offer(
        late_run, offers[0], challenge_slots=1
    )
    challenge_reward = mission_reward(
        offers[0].economy_class,
        mission_modifier=forced,
        challenge_hunter_level=5,
    )
    normal_price = run_reward_price(unit_entries[0])
    specialized_price = run_reward_price(
        unit_entries[0], specialization='Units', specialization_level=5
    )
    globally_discounted = all(
        run_reward_price(entry, specialization_level=5)
        < run_reward_price(entry)
        and run_reward_price(
            entry, specialization='Units', specialization_level=5
        ) == run_reward_price(
            entry, specialization='Powers', specialization_level=5
        )
        for entry in (unit_entries[0], buff_entry, power_entries[0])
    )
    stock = rotating_unit_inventory(
        unit_entries,
        run_seed=run.seed,
        stage=run.stage,
        offer_count=SHOP_CONFIG.unit_inventory_size + 2,
    )
    marker_run = replace(
        run,
        starting_unit_ids=tier_one_unit_ids(
            ('allies', 'soviets', 'epsilon')
        ),
        starting_defense_ids=tier_one_defense_ids(
            ('allies', 'soviets', 'epsilon')
        ),
        reward_settings={'shop_faction_filter': 'All Campaigns'},
    )
    concrete_starters = active_shop_starter_unit_ids(marker_run)
    concrete_defenses = active_shop_starter_defense_ids(marker_run)
    starter_cameos = ensure_unit_cameos(
        (*concrete_starters, *concrete_defenses)
    )
    committed = commit_selected_mission(run, offers[0].mission_code)
    revived = apply_mission_failure(
        committed,
        offers[0].mission_code,
        profile=profile,
        maximum_emergency_revivals=1,
        revival_offers=offers[1:] + offers[:1],
    )
    failed = apply_mission_failure(
        replace(committed, emergency_revivals_used=1),
        offers[0].mission_code,
        profile=profile,
        maximum_emergency_revivals=1,
        salvage_run_coins=25,
        maximum_salvaged_run_coins=25,
    )
    free_validation = validate_run_purchase(
        canonical_reward_for_id(buff_entry.reward_id),
        price=0,
        run_coins=run.run_coins,
        active_tech_ids=(buff_entry.target_id,),
    )
    token_run = apply_validated_run_purchase(
        run,
        canonical_reward_for_id(buff_entry.reward_id),
        free_validation,
        consume_free_buff_token=True,
    )
    loadout_entries = unit_entries[:6]
    expanded = validate_starting_loadout(
        starter_tech_ids=(),
        selected_reward_ids=(item.reward_id for item in loadout_entries),
        entitled_reward_ids=(item.reward_id for item in loadout_entries),
        maximum_extra_units=6,
    )
    started = start_new_run(
        profile,
        run_id='salvage-start',
        seed='SALVAGE-START',
        mission_offers=offers,
    )
    retired_draft_purchase = purchase_permanent_upgrade(
        ShopProfile(meta_coins=1000), 'starting_buff_draft'
    )
    required = set(upgrade_levels)
    return {
        'permanent_features_config_valid': required.issubset(
            SHOP_CONFIG.permanent_upgrades
        ),
        'permanent_feature_persistence_valid': bool(
            normalize_shop_profile(profile.to_dict()) == profile
            and normalize_shop_run(run.to_dict()) == run
        ),
        'extra_shop_stock_valid': len(stock) == SHOP_CONFIG.unit_inventory_size + 2,
        'shop_power_cameos_valid': bool(
            power_ids and set(power_cameos) == power_ids
        ),
        'starter_loadout_display_valid': bool(
            len(concrete_starters) == 5
            and len(set(concrete_starters)) == 5
            and len(concrete_defenses) == 2
            and concrete_starters == active_shop_starter_unit_ids(marker_run)
            and concrete_defenses == active_shop_starter_defense_ids(marker_run)
            and set(concrete_starters).union(concrete_defenses).issubset(
                active_shop_tech_ids(marker_run)
            )
            and set(starter_cameos)
            == set(concrete_starters).union(concrete_defenses)
            and not any(
                item.startswith('T1_')
                for item in (*concrete_starters, *concrete_defenses)
            )
        ),
        'expanded_loadout_valid': expanded.allowed and expanded.extra_slots_used == 6,
        'emergency_revival_valid': bool(
            revived.revived
            and revived.run.status is RunStatus.ACTIVE
            and revived.run.emergency_revivals_used == 1
            and not revived.run.mission_committed
        ),
        'free_buff_token_valid': bool(
            free_validation.allowed
            and token_run.run_coins == run.run_coins
            and token_run.free_buff_tokens_used == 1
        ),
        'challenge_hunter_valid': bool(
            forced is not None
            and forced.challenge
            and challenge_reward.challenge_hunter_run_coins == 5
            and challenge_reward.challenge_hunter_meta_coins == 2
        ),
        'recovery_salvage_valid': bool(
            not failed.revived
            and failed.profile is not None
            and failed.profile.salvaged_run_coins == 20
            and started.run.run_coins == SHOP_CONFIG.starting_run_coins + 7
            and started.profile.salvaged_run_coins == 0
        ),
        'starting_buff_draft_retirement_valid': bool(
            not SHOP_CONFIG.permanent_upgrades[
                'starting_buff_draft'
            ].purchasable
            and not retired_draft_purchase.validation.allowed
            and retired_draft_purchase.profile.meta_coins == 1000
            and run.starting_draft_buffs
            and canonical_reward_for_id(buff_entry.reward_id)
            in active_shop_rewards(run)
            and not started.run.starting_draft_buffs
        ),
        'discount_specialization_valid': bool(
            specialized_price < normal_price and globally_discounted
        ),
        'permanent_challenge_slots_valid': bool(
            early_forced
            and not early_forced.challenge
            and forced
            and forced.challenge
        ),
    }


def _phase_two_checks(mission_pool):
    offers = generate_mission_offers(
        mission_pool, run_seed='SHOP-PERSISTENCE-CHECK', stage=1
    )
    profile = ShopProfile(
        meta_coins=20,
        permanent_unit_unlocks=('GI Access',),
        permanent_upgrades={'victory_run_coin_bonus': 3},
    )
    started = start_new_run(
        profile,
        run_id='shop-persistence-run',
        seed='SHOP-PERSISTENCE-CHECK',
        mission_offers=offers,
        permanent_entitlement_ids=profile.permanent_unit_unlocks,
    )
    selected_code = offers[0].mission_code
    selected = select_mission(started.run, selected_code)
    reroll_offer = generate_mission_offers(
        mission_pool,
        run_seed='SHOP-PERSISTENCE-CHECK',
        stage=1,
        reroll_count=1,
        previous_offer_codes=(offer.mission_code for offer in offers),
    )
    rerolled_run = reroll_missions(
        started.run, reroll_offer, maximum_rerolls=1
    )
    standalone_ui_transitions_valid = bool(
        selected.selected_mission_code == selected_code
        and not selected.mission_committed
        and rerolled_run.rerolls_used == 1
        and not rerolled_run.selected_mission_code
    )
    committed = commit_selected_mission(started.run, selected_code)
    next_offers = generate_mission_offers(
        mission_pool,
        run_seed='SHOP-PERSISTENCE-CHECK',
        stage=2,
        completed_codes=(selected_code,),
    )
    victory = apply_mission_victory(
        started.profile,
        committed,
        selected_code,
        next_offers=next_offers,
    )
    duplicate = apply_mission_victory(
        victory.profile, victory.run, selected_code
    )
    victory_idempotency_valid = bool(
        victory.changed
        and not duplicate.changed
        and duplicate.profile == victory.profile
        and duplicate.run == victory.run
        and victory.run.stage == 2
        and victory.run.rewarded_victories == (victory.victory_key,)
    )

    failed_source = replace(
        committed,
        run_coins=99,
        run_purchases=(PurchaseRecord('GI Access'),),
        ap_entitlements_snapshot=('Guardian GI Access',),
    )
    failure = apply_mission_failure(failed_source, selected_code)
    repeated_failure = apply_mission_failure(failure.run, selected_code)
    failure_valid = bool(
        failure.changed
        and failure.run.status is RunStatus.FAILED
        and failure.run.failed_stage == 1
        and not repeated_failure.changed
    )
    abandoned = abandon_run(started.run)
    abandon_valid = bool(
        abandoned.changed
        and abandoned.run.status is RunStatus.FAILED
        and abandoned.run.failed_mission_code == 'GAVE_UP'
        and abandoned.run.failed_stage == started.run.stage
        and not abandoned.run.mission_offers
        and not abandoned.run.mission_committed
    )

    finale_offer = MissionOffer(
        'SC_FIN_1', MissionEconomyClass.FINALE
    )
    completion_source = ShopRun(
        run_id='shop-completion-run',
        seed='SHOP-COMPLETION-CHECK',
        status=RunStatus.ACTIVE,
        stage=SHOP_CONFIG.run_length,
        run_length=SHOP_CONFIG.run_length,
        run_coins=0,
        mission_offers=(finale_offer,),
        selected_mission_code=finale_offer.mission_code,
        mission_committed=True,
    )
    completion = apply_mission_victory(
        ShopProfile(), completion_source, finale_offer.mission_code
    )
    repeated_completion = apply_mission_victory(
        completion.profile, completion.run, finale_offer.mission_code
    )
    completion_valid = bool(
        completion.changed
        and completion.run.status is RunStatus.COMPLETED
        and completion.run.stage == SHOP_CONFIG.run_length
        and not completion.run.mission_offers
        and completion.profile.lifetime_runs_completed == 1
        and not repeated_completion.changed
        and repeated_completion.profile.lifetime_runs_completed == 1
    )

    legacy_profile = profile.to_dict()
    legacy_profile['meta_coins'] = 137
    for field in ('permanent_buffs', 'salvaged_run_coins', 'archipelago_profiles'):
        legacy_profile.pop(field, None)
    legacy_run = failed_source.to_dict()
    legacy_run['reward_mode'] = 'Standard'
    legacy_run['run_coins'] = 83
    for field in (
        'difficulty_assists_used', 'assisted_mission_code',
        'permanent_buffs_snapshot', 'starting_draft_buffs',
        'free_buff_tokens_used', 'emergency_revivals_used',
    ):
        legacy_run.pop(field, None)
    upgraded_profile = normalize_shop_profile(legacy_profile)
    upgraded_run = normalize_shop_run(legacy_run)
    upgrade_currency_compatibility_valid = bool(
        upgraded_profile.meta_coins == 137
        and upgraded_run.run_coins == 83
        and upgraded_run.reward_mode == 'Standard'
        and upgraded_run.run_purchases == failed_source.run_purchases
    )

    with TemporaryDirectory(prefix='mo-shop-self-check-') as temporary:
        root = Path(temporary)
        paths = ShopPersistencePaths(
            profile=root / 'shop_profile.json',
            run=root / 'shop_run.json',
            transaction=root / 'shop_transaction.json',
            backup_dir=root / 'backups',
        )
        repository = ShopRepository(paths)
        missing_profile, missing_run = repository.load()
        repository.commit(
            started.profile, started.run, started.transaction_id
        )
        repository.save_run(committed)
        reopened_profile, reopened_run = ShopRepository(paths).load()

        repository.prepare_commit(
            victory.profile, victory.run, victory.victory_key
        )
        atomic_write_json(
            paths.profile, victory.profile.to_dict(), indent=None
        )
        recovered_profile, recovered_run = ShopRepository(paths).load()
        replayed = ShopProgressionService(
            ShopRepository(paths)
        ).record_victory(selected_code)

        repository.commit(
            started.profile,
            failure.run,
            'shop-persistence-run:failure-test',
        )
        restarted = ShopProgressionService(repository).start_run(
            run_id='shop-persistence-run-2',
            seed='SHOP-PERSISTENCE-CHECK-2',
            mission_offers=offers,
            permanent_entitlement_ids=(
                started.profile.permanent_unit_unlocks
            ),
        )
        restart_valid = bool(
            restarted.run.run_coins == SHOP_CONFIG.starting_run_coins
            and not restarted.run.run_purchases
            and not restarted.run.run_buffs
            and restarted.profile.meta_coins == started.profile.meta_coins
            and restarted.profile.permanent_unit_unlocks
            == started.profile.permanent_unit_unlocks
            and restarted.profile.lifetime_runs_started
            == started.profile.lifetime_runs_started + 1
        )

        service_reset_profile, service_reset_run = ShopProgressionService(
            repository
        ).reset_profile()
        service_reset_valid = bool(
            service_reset_profile == ShopProfile()
            and service_reset_run is None
            and not paths.run.exists()
        )
        repository.commit(
            restarted.profile,
            restarted.run,
            'shop-persistence-run:restore-before-reset',
        )
        repository.prepare_commit(
            ShopProfile(), None, 'shop-persistence-run:reset-recovery'
        )
        atomic_write_json(paths.profile, ShopProfile().to_dict(), indent=None)
        recovered_reset_profile, recovered_reset_run = ShopRepository(
            paths
        ).load()
        reset_recovery_valid = bool(
            recovered_reset_profile == ShopProfile()
            and recovered_reset_run is None
            and not paths.run.exists()
            and not paths.transaction.exists()
        )

        atomic_write_text(paths.profile, '{')
        try:
            repository.load_profile()
            corrupt_state_rejected = False
        except ShopPersistenceError:
            corrupt_state_rejected = any(paths.backup_dir.iterdir())

        persistence_valid = bool(
            missing_profile == ShopProfile()
            and missing_run is None
            and reopened_profile == started.profile
            and reopened_run == committed
            and recovered_profile == victory.profile
            and recovered_run == victory.run
            and not paths.transaction.exists()
            and not replayed.changed
            and replayed.profile == victory.profile
            and replayed.run == victory.run
            and restart_valid
            and service_reset_valid
            and reset_recovery_valid
            and corrupt_state_rejected
        )

    return {
        'standalone_ui_transitions_valid': standalone_ui_transitions_valid,
        'victory_idempotency_valid': victory_idempotency_valid,
        'failure_transition_valid': failure_valid,
        'abandon_transition_valid': abandon_valid,
        'completion_transition_valid': completion_valid,
        'persistence_recovery_valid': persistence_valid,
        'upgrade_currency_compatibility_valid': (
            upgrade_currency_compatibility_valid
        ),
    }


def _phase_four_checks():
    classes = tuple(MissionEconomyClass)
    mission_pool = [
        {
            'code': f'SC_RUN_{index:02d}',
            'reward_class': classes[index % len(classes)].value,
        }
        for index in range(16)
    ]
    with TemporaryDirectory(prefix='mo-shop-run-self-check-') as temporary:
        root = Path(temporary)
        repository = ShopRepository(ShopPersistencePaths(
            profile=root / 'shop_profile.json',
            run=root / 'shop_run.json',
            transaction=root / 'shop_transaction.json',
            backup_dir=root / 'backups',
        ))
        service = ShopProgressionService(repository)
        offers = generate_mission_offers(
            mission_pool, run_seed='SHOP-FULL-RUN', stage=1
        )
        service.start_run(
            run_id='shop-full-run',
            seed='SHOP-FULL-RUN',
            mission_offers=offers,
            campaign_filter='All Campaigns',
            reward_mode='Standard',
            reward_settings={'randomize_unit_access': True},
            eligible_mission_codes=(
                mission['code'] for mission in mission_pool
            ),
            starting_unit_ids=('MOR_T1_INFANTRY',),
            starting_defense_ids=('MOR_T1_DEFENSES',),
        )
        total_meta_coins = 0
        all_stages_had_three_offers = True
        for expected_stage in range(1, SHOP_CONFIG.run_length + 1):
            profile, run = repository.load()
            all_stages_had_three_offers &= len(run.mission_offers) == 3
            code = run.mission_offers[0].mission_code
            selected = service.select_mission(code)
            committed = service.commit_mission(code)
            assert selected.selected_mission_code == code
            assert not selected.mission_committed
            assert committed.mission_committed
            next_offers = ()
            if expected_stage < SHOP_CONFIG.run_length:
                next_offers = generate_mission_offers(
                    mission_pool,
                    run_seed=run.seed,
                    stage=expected_stage + 1,
                    completed_codes=run.completed_missions + (code,),
                )
            transition = service.record_victory(
                code, next_offers=next_offers
            )
            assert transition.changed
            total_meta_coins += transition.reward.meta_coins
        final_profile, final_run = repository.load()

    unit_reward_ids = [
        entry.reward_id for entry in shop_catalogue()
        if entry.reward_type is ShopRewardType.UNIT_ACCESS
    ][:2]
    buff_reward_id = next(
        entry.reward_id for entry in shop_catalogue()
        if entry.reward_type is ShopRewardType.UNIT_BUFF
    )
    stacked = replace(
        final_run,
        selected_permanent_units=(unit_reward_ids[0],),
        run_purchases=(PurchaseRecord(unit_reward_ids[1]),),
        run_buffs=(BuffPurchase(buff_reward_id, 2),),
    )
    reward_names = [reward.get('name') for reward in active_shop_rewards(stacked)]
    return {
        'full_standalone_run_valid': bool(
            all_stages_had_three_offers
            and final_run.status is RunStatus.COMPLETED
            and len(final_run.completed_missions) == SHOP_CONFIG.run_length
            and len(set(final_run.completed_missions)) == SHOP_CONFIG.run_length
            and final_profile.meta_coins == total_meta_coins
            and final_profile.lifetime_runs_completed == 1
        ),
        'active_shop_reward_payload_valid': bool(
            reward_names.count(unit_reward_ids[0]) == 1
            and reward_names.count(unit_reward_ids[1]) == 1
            and reward_names.count(buff_reward_id) == 2
        ),
    }


def _phase_five_checks():
    catalogue = shop_catalogue()
    selection_pool = [
        entry.reward_id for entry in catalogue
        if entry.reward_type is ShopRewardType.UNIT_ACCESS
    ][:8]
    unit_ids = selection_pool[:2]
    buff_id = next(
        entry.reward_id for entry in catalogue
        if entry.reward_type is ShopRewardType.UNIT_BUFF
    )
    records = (
        {'index': 0, 'reward_name': unit_ids[0]},
        {'index': 1, 'reward_name': unit_ids[1]},
        {'index': 2, 'reward_name': buff_id},
        {'index': 2, 'reward_name': buff_id},
        {'index': 3, 'reward_name': buff_id},
    )
    ap_reward_ids = shop_reward_ids_from_ap_ledger(records)
    ap_state = {
        'manifest_checksum': 'phase-five-manifest',
        'checkpoint': {'seed_name': 'Phase Five Room'},
        'team': 0,
        'slot': 3,
    }
    ap_identity = archipelago_shop_identity(ap_state)
    other_identity = archipelago_shop_identity({**ap_state, 'slot': 4})
    offers = (
        MissionOffer('SC_AP_1', MissionEconomyClass.ACT_1),
    )
    all_units_started = start_new_run(
        ShopProfile(),
        run_id='shop-ap-all-units-run-1',
        seed='SHOP-AP-ALL-UNITS',
        mission_offers=offers,
        ap_entitlement_ids=selection_pool,
        ap_identity=ap_identity,
        maximum_extra_units=3,
    )
    started = start_new_run(
        ShopProfile(),
        run_id='shop-ap-run-1',
        seed='SHOP-AP-RUN-1',
        mission_offers=offers,
        selected_reward_ids=(unit_ids[0],),
        ap_entitlement_ids=ap_reward_ids,
        ap_identity=ap_identity,
    )
    active_names = [
        reward.get('name') for reward in active_shop_rewards(started.run)
    ]
    replayed = merge_archipelago_entitlements(
        started.run, ap_identity, ap_reward_ids
    )
    expanded = merge_archipelago_entitlements(
        started.run, ap_identity, (*ap_reward_ids, buff_id)
    )
    wrong_slot = merge_archipelago_entitlements(
        started.run, other_identity, (*ap_reward_ids, buff_id)
    )
    failed = apply_mission_failure(
        replace(
            started.run,
            selected_mission_code=offers[0].mission_code,
            mission_committed=True,
        ),
        offers[0].mission_code,
    )
    restarted = start_new_run(
        started.profile,
        run_id='shop-ap-run-2',
        seed='SHOP-AP-RUN-2',
        mission_offers=offers,
        selected_reward_ids=(unit_ids[1],),
        ap_entitlement_ids=ap_reward_ids,
        ap_identity=ap_identity,
    )
    restored = normalize_shop_run(restarted.run.to_dict())
    restarted_names = [
        reward.get('name') for reward in active_shop_rewards(restarted.run)
    ]
    with TemporaryDirectory(prefix='mo-shop-ap-self-check-') as temporary:
        root = Path(temporary)
        repository = ShopRepository(ShopPersistencePaths(
            profile=root / 'shop_profile.json',
            run=root / 'shop_run.json',
            transaction=root / 'shop_transaction.json',
            backup_dir=root / 'backups',
        ))
        repository.commit(
            started.profile, started.run, started.transaction_id
        )
        service = ShopProgressionService(repository)
        synced = service.sync_archipelago_entitlements(
            ap_identity, (*ap_reward_ids, buff_id)
        )
        replayed_sync = service.sync_archipelago_entitlements(
            ap_identity, (*ap_reward_ids, buff_id)
        )
        persisted_sync = ShopRepository(repository.paths).load_run()
    return {
        'archipelago_ledger_replay_valid': bool(
            ap_reward_ids == (
                unit_ids[0], unit_ids[1], buff_id, buff_id
            )
            and replayed == started.run
            and expanded.ap_entitlements_snapshot.count(buff_id) == 3
            and wrong_slot == started.run
        ),
        'archipelago_loadout_merge_valid': bool(
            ap_identity
            and ap_identity != other_identity
            and not archipelago_shop_identity({
                **ap_state, 'slot': 'invalid'
            })
            and ap_unit_entitlement_ids(ap_reward_ids) == tuple(unit_ids)
            and active_names.count(unit_ids[0]) == 1
            and active_names.count(unit_ids[1]) == 1
            and active_names.count(buff_id) == 2
        ),
        'archipelago_all_units_loadout_valid': bool(
            not all_units_started.run.selected_permanent_units
            and set(selection_pool) == {
                reward.get('name')
                for reward in active_shop_rewards(all_units_started.run)
            }
            and all_units_started.run.run_coins
            == SHOP_CONFIG.starting_run_coins
        ),
        'archipelago_failure_restart_valid': bool(
            failed.run.status is RunStatus.FAILED
            and restarted.run.ap_identity == ap_identity
            and restarted.run.ap_entitlements_snapshot == ap_reward_ids
            and restarted.run.run_coins == SHOP_CONFIG.starting_run_coins
            and restarted.profile.meta_coins == started.profile.meta_coins
            and restarted_names.count(unit_ids[1]) == 1
            and restarted_names.count(unit_ids[0]) == 1
            and restarted_names.count(buff_id) == 2
            and not restarted.profile.permanent_unit_unlocks
            and not restarted.profile.archipelago_profiles
            and restored == restarted.run
        ),
        'archipelago_snapshot_persistence_valid': bool(
            synced.ap_entitlements_snapshot.count(buff_id) == 3
            and replayed_sync == synced
            and persisted_sync == synced
        ),
    }


def _phase_six_checks():
    identity = 'ap-v1:shop-purchase-self-check'
    other_identity = 'ap-v1:other-shop-slot'
    with TemporaryDirectory(prefix='mo-shop-ap-purchase-check-') as temporary:
        root = Path(temporary)
        paths = ShopPersistencePaths(
            profile=root / 'shop_profile.json',
            run=root / 'shop_run.json',
            transaction=root / 'shop_transaction.json',
            backup_dir=root / 'backups',
        )
        repository = ShopRepository(paths)
        repository.save_profile(ShopProfile(meta_coins=12))
        service = ShopProgressionService(repository)
        first = service.purchase_archipelago_location(
            identity,
            101,
            cost=5,
            connected=True,
            available_location_ids=(101, 102),
        )
        repeated = service.purchase_archipelago_location(
            identity,
            101,
            cost=5,
            connected=True,
            available_location_ids=(101, 102),
        )
        reopened = ShopProgressionService(ShopRepository(paths))
        pending = reopened.pending_archipelago_purchase_ids(identity)
        pending_profile = reopened.repository.load_profile()
        reconciled = reopened.reconcile_archipelago_purchases(identity, (101,))
        records = archipelago_purchase_records(reconciled, identity)
        insufficient = reopened.purchase_archipelago_location(
            identity,
            102,
            cost=8,
            connected=True,
            available_location_ids=(101, 102),
        )
        disconnected = reopened.purchase_archipelago_location(
            identity,
            102,
            cost=1,
            connected=False,
            available_location_ids=(101, 102),
        )
        final_profile = reopened.repository.load_profile()
    malformed = final_profile.to_dict()
    malformed['archipelago_profiles'][identity][
        'shop_purchase_transactions'
    ]['101']['status'] = 'charged-again'
    try:
        normalize_shop_profile(malformed)
        malformed_rejected = False
    except ShopStateError:
        malformed_rejected = True
    return {
        'archipelago_purchase_transaction_valid': bool(
            first.result is PurchaseResult.OK
            and repeated.result is PurchaseResult.AP_LOCATION_ALREADY_CHECKED
            and pending == (101,)
            and pending_profile.meta_coins == 7
            and records['101'] == {'cost': 5, 'status': 'checked'}
            and not archipelago_purchase_records(reconciled, other_identity)
            and insufficient.result is PurchaseResult.INSUFFICIENT_CURRENCY
            and disconnected.result is PurchaseResult.AP_NOT_CONNECTED
            and final_profile.meta_coins == 7
            and malformed_rejected
        ),
    }


def _phase_seven_checks():
    offers = (
        MissionOffer('SC_POLISH_1', MissionEconomyClass.ACT_1),
        MissionOffer('SC_POLISH_2', MissionEconomyClass.OPERATION),
        MissionOffer('SC_POLISH_3', MissionEconomyClass.FINALE),
    )
    run = ShopRun(
        run_id='shop-polish-run',
        seed='SHOP-POLISH',
        status=RunStatus.ACTIVE,
        stage=4,
        run_length=SHOP_CONFIG.run_length,
        run_coins=100,
        mission_offers=offers,
        modifiers=('greedy', 'veteran_economy', 'blind_choice'),
    )
    hidden = hidden_offer_codes(run)
    adjusted = mission_reward(
        MissionEconomyClass.FINALE,
        modifiers=run.modifiers,
    )
    poor_logistics_reward = mission_reward(
        MissionEconomyClass.ACT_1,
        modifiers=('poor_logistics',),
    )
    generous_reward = mission_reward(
        MissionEconomyClass.OPERATION,
        modifiers=('generous_command',),
    )
    breakdown = reward_breakdown_lines(
        MissionEconomyClass.FINALE,
        victory_coin_bonus_level=2,
        modifiers=run.modifiers,
    )

    catalogue = shop_catalogue()
    power_buffs_by_target = {
        entry.target_id: entry
        for entry in catalogue
        if entry.reward_type is ShopRewardType.POWER_BUFF
    }
    power_access = next(
        entry for entry in catalogue
        if entry.reward_type is ShopRewardType.POWER_ACCESS
        and entry.target_id in power_buffs_by_target
    )
    power_buff = power_buffs_by_target[power_access.target_id]
    access_reward = canonical_reward_for_id(power_access.reward_id)
    access_validation = validate_run_purchase(
        access_reward,
        price=3,
        run_coins=run.run_coins,
    )
    with_power = apply_validated_run_purchase(
        run, access_reward, access_validation
    )
    buff_reward = canonical_reward_for_id(power_buff.reward_id)
    buff_validation = validate_run_purchase(
        buff_reward,
        price=2,
        run_coins=with_power.run_coins,
        active_power_ids=active_shop_power_ids(with_power),
    )
    with_buff = apply_validated_run_purchase(
        with_power, buff_reward, buff_validation
    )

    completed = replace(
        with_buff,
        status=RunStatus.COMPLETED,
        stage=with_buff.run_length,
        mission_offers=(),
        completed_missions=tuple(
            f'SC_DONE_{index}' for index in range(1, 11)
        ),
    )
    failed = replace(
        with_buff,
        status=RunStatus.FAILED,
        failed_mission_code='SC_FAILED',
        failed_stage=4,
    )
    completion_summary = run_summary_lines(ShopProfile(meta_coins=42), completed)
    failure_summary = run_summary_lines(ShopProfile(meta_coins=42), failed)
    restored = normalize_shop_run(run.to_dict())
    return {
        'modifier_polish_valid': bool(
            len(hidden) == 1
            and hidden == hidden_offer_codes(run)
            and hidden[0] in {offer.mission_code for offer in offers}
            and adjusted.run_coins == 14
            and adjusted.meta_coins == 5
            and poor_logistics_reward.run_coins == 7
            and starting_run_coins(modifiers=('poor_logistics',)) == 5
            and discounted_shop_price(
                5, modifiers=('poor_logistics',)
            ) == 7
            and generous_reward.meta_coins == 2
            and 'meta_reward_flat' not in SHOP_CONFIG.modifiers[
                'generous_command'
            ].effects
            and any('Permanent Victory Bonus: +2' in line for line in breakdown)
            and any('Total: +16 Ore' in line for line in breakdown)
            and 'Persistent Gems: 42' in completion_summary
            and restored == run
        ),
        'power_shop_purchase_valid': bool(
            access_validation.result is PurchaseResult.OK
            and power_access.target_id in active_shop_power_ids(with_power)
            and buff_validation.result is PurchaseResult.OK
            and with_buff.run_buffs == (BuffPurchase(power_buff.reward_id, 1),)
            and with_buff.run_coins == 95
        ),
        'run_summary_valid': bool(
            completion_summary[0] == 'RUN VICTORY'
            and 'Missions won: 10 / 10' in completion_summary
            and failure_summary[0] == 'RUN OVER'
            and any('Failed at stage 4' in line for line in failure_summary)
        ),
    }


def validate_shop_domain():
    malformed_config = load_static_config('shop_mode.json')
    malformed_config['settings']['run_length'] = 0
    try:
        validate_sections('shop_mode.json', malformed_config, 'shop-self-check')
        config_validation_valid = False
    except StaticConfigError:
        config_validation_valid = True
    flat_meta_config = load_static_config('shop_mode.json')
    flat_meta_config['mission_rewards']['act_2']['meta_coins'] = 1
    try:
        validate_sections('shop_mode.json', flat_meta_config, 'shop-self-check')
        config_validation_valid = False
    except StaticConfigError:
        pass
    hidden_offer_config = load_static_config('shop_mode.json')
    hidden_offer_config['modifiers']['blind_choice']['effects'][
        'hidden_offer_count'
    ] = -1
    try:
        validate_sections(
            'shop_mode.json', hidden_offer_config, 'shop-self-check'
        )
        config_validation_valid = False
    except StaticConfigError:
        pass
    mixed_modifier_config = load_static_config('shop_mode.json')
    mixed_modifier_config['modifiers']['greedy']['effects'][
        'meta_reward_flat'
    ] = 1
    try:
        validate_sections(
            'shop_mode.json', mixed_modifier_config, 'shop-self-check'
        )
        config_validation_valid = False
    except StaticConfigError:
        pass

    act_one = mission_reward(MissionEconomyClass.ACT_1)
    operation = mission_reward(
        MissionEconomyClass.OPERATION, victory_coin_bonus_level=3
    )
    capped_bonus = mission_reward(
        MissionEconomyClass.OPERATION, victory_coin_bonus_level=999
    )
    failed = mission_reward(MissionEconomyClass.FINALE, successful=False)
    meta_rewards_by_difficulty = [
        mission_reward(class_id).meta_coins
        for class_id in (
            MissionEconomyClass.ACT_1,
            MissionEconomyClass.ACT_2,
            MissionEconomyClass.OPERATION,
            MissionEconomyClass.FINALE,
        )
    ]
    starting_credit_upgrade = SHOP_CONFIG.permanent_upgrades[
        'mission_starting_credits'
    ]
    starting_credit_reward = canonical_reward_for_id(
        'Starting Credits +1,000'
    )
    economy_valid = bool(
        (act_one.run_coins, act_one.meta_coins) == (3, 1)
        and operation.run_coins == 10
        and operation.meta_coins == 3
        and operation.victory_bonus_run_coins == 3
        and capped_bonus.victory_bonus_run_coins == 5
        and run_buff_price('tier_1') == 2
        and (failed.run_coins, failed.meta_coins) == (0, 0)
        and meta_rewards_by_difficulty == [1, 2, 3, 4]
        and discounted_shop_price(0, shop_discount_level=999) == 1
        and permanent_unit_price('tier_1')
        < permanent_unit_price('tier_2')
        < permanent_unit_price('tier_3')
        and permanent_buff_price('tier_1')
        < permanent_buff_price('tier_2')
        < permanent_buff_price('tier_3')
        and starting_run_coins(starting_capital_level=999) == 50
        and starting_credit_upgrade.max_level == 20
        and starting_credit_upgrade.effects['credits_per_level'] == 1000
        and starting_credit_upgrade.max_level
        * starting_credit_upgrade.effects['credits_per_level'] == 20000
        and starting_credit_reward.get('credits_per_stack') == 1000
        and starting_credit_reward.get('maximum_credits') == 20000
    )

    catalogue = shop_catalogue()
    access_entries = [
        entry for entry in catalogue
        if entry.reward_type is ShopRewardType.UNIT_ACCESS
    ]
    buff_entries = [
        entry for entry in catalogue
        if entry.reward_type is ShopRewardType.UNIT_BUFF
        and entry.stack_limit is not None
    ]
    power_entries = [
        entry for entry in catalogue
        if entry.reward_type is ShopRewardType.POWER_ACCESS
    ]
    gi_access = _reward('GI Access')
    gi_buff_entry = next(entry for entry in buff_entries if entry.target_id == 'E1')
    gi_buff = _reward(gi_buff_entry.reward_id)
    blocked_buff = validate_run_purchase(
        gi_buff,
        price=1,
        run_coins=10,
        active_tech_ids=(),
    )
    allowed_buff = validate_run_purchase(
        gi_buff,
        price=1,
        run_coins=10,
        active_tech_ids=('E1',),
    )
    capped_buff = validate_run_purchase(
        gi_buff,
        price=1,
        run_coins=10,
        active_tech_ids=('E1',),
        current_stacks=gi_buff_entry.stack_limit,
    )
    committed_purchase = validate_run_purchase(
        gi_access,
        price=1,
        run_coins=10,
        mission_committed=True,
    )
    purchase_rules_valid = bool(
        access_entries
        and buff_entries
        and power_entries
        and blocked_buff.result is PurchaseResult.REQUIRES_UNIT_ACCESS
        and allowed_buff.result is PurchaseResult.OK
        and capped_buff.result is PurchaseResult.MAX_STACKS
        and committed_purchase.result
        is PurchaseResult.PURCHASE_LOCKED_DURING_MISSION
        and not tech_ids_for_rewards([gi_buff])
    )

    profile = ShopProfile(meta_coins=100)
    first_purchase = purchase_permanent_unit(profile, gi_access, price=10)
    repeated_purchase = purchase_permanent_unit(
        first_purchase.profile, gi_access, price=10
    )
    permanent_buff_purchase = purchase_permanent_buff(
        first_purchase.profile, gi_buff, price=5
    )
    restored_profile = normalize_shop_profile(
        permanent_buff_purchase.profile.to_dict()
    )
    permanent_purchase_valid = bool(
        first_purchase.validation.result is PurchaseResult.OK
        and first_purchase.profile.meta_coins == 90
        and repeated_purchase.validation.result is PurchaseResult.ALREADY_OWNED
        and repeated_purchase.profile.meta_coins == 90
        and permanent_buff_purchase.validation.result is PurchaseResult.OK
        and permanent_buff_purchase.profile.meta_coins == 85
        and permanent_buff_purchase.profile.permanent_buffs
        == (BuffPurchase(gi_buff_entry.reward_id, 1),)
        and restored_profile == permanent_buff_purchase.profile
    )

    nonstarter_entries = []
    seen_targets = {'E1'}
    for entry in access_entries:
        if entry.target_id in seen_targets:
            continue
        seen_targets.add(entry.target_id)
        nonstarter_entries.append(entry)
        if len(nonstarter_entries) == 6:
            break
    five_extras = [entry.reward_id for entry in nonstarter_entries[:5]]
    six_extras = [entry.reward_id for entry in nonstarter_entries]
    entitlements = ['GI Access', *six_extras]
    accepted_loadout = validate_starting_loadout(
        starter_tech_ids=('E1',),
        selected_reward_ids=('GI Access', *five_extras),
        entitled_reward_ids=entitlements,
    )
    rejected_loadout = validate_starting_loadout(
        starter_tech_ids=('E1',),
        selected_reward_ids=six_extras,
        entitled_reward_ids=entitlements,
    )
    loadout_valid = bool(
        len(nonstarter_entries) == 6
        and accepted_loadout.allowed
        and accepted_loadout.extra_slots_used == 5
        and rejected_loadout.result is PurchaseResult.MAX_LOADOUT_SIZE
    )
    first_stock = rotating_unit_inventory(
        access_entries,
        run_seed='SHOP-INVENTORY-CHECK',
        stage=1,
        offer_count=SHOP_CONFIG.unit_inventory_size,
    )
    repeated_stock = rotating_unit_inventory(
        tuple(reversed(access_entries)),
        run_seed='SHOP-INVENTORY-CHECK',
        stage=1,
        offer_count=SHOP_CONFIG.unit_inventory_size,
    )
    next_stock = rotating_unit_inventory(
        access_entries,
        run_seed='SHOP-INVENTORY-CHECK',
        stage=2,
        offer_count=SHOP_CONFIG.unit_inventory_size,
    )
    rotating_inventory_valid = bool(
        len(first_stock) == SHOP_CONFIG.unit_inventory_size
        and first_stock == repeated_stock
        and {entry.reward_id for entry in first_stock}
        != {entry.reward_id for entry in next_stock}
    )
    owned_unit_target = first_stock[0].target_id
    filtered_unit_stock = rotating_unit_inventory(
        access_entries,
        run_seed='SHOP-INVENTORY-CHECK',
        stage=1,
        offer_count=SHOP_CONFIG.unit_inventory_size,
        excluded_target_ids=(owned_unit_target,),
    )
    repeated_filtered_unit_stock = rotating_unit_inventory(
        tuple(reversed(access_entries)),
        run_seed='SHOP-INVENTORY-CHECK',
        stage=1,
        offer_count=SHOP_CONFIG.unit_inventory_size,
        excluded_target_ids=(owned_unit_target,),
    )
    owned_unit_stock_excluded = bool(
        len(filtered_unit_stock) == SHOP_CONFIG.unit_inventory_size
        and filtered_unit_stock == repeated_filtered_unit_stock
        and all(
            entry.target_id != owned_unit_target
            for entry in filtered_unit_stock
        )
        and {
            entry.reward_id for entry in first_stock
            if entry.target_id != owned_unit_target
        }.issubset(entry.reward_id for entry in filtered_unit_stock)
    )
    power_entries = [
        entry for entry in catalogue
        if entry.reward_type is ShopRewardType.POWER_ACCESS
    ]
    power_stock = rotating_power_inventory(
        power_entries,
        run_seed='SHOP-INVENTORY-CHECK',
        stage=1,
        offer_count=SHOP_CONFIG.power_inventory_size,
    )
    repeated_power_stock = rotating_power_inventory(
        tuple(reversed(power_entries)),
        run_seed='SHOP-INVENTORY-CHECK',
        stage=1,
        offer_count=SHOP_CONFIG.power_inventory_size,
    )
    rotating_power_inventory_valid = bool(
        len(power_stock) == SHOP_CONFIG.power_inventory_size
        and power_stock == repeated_power_stock
        and all(
            entry.reward_type is ShopRewardType.POWER_ACCESS
            for entry in power_stock
        )
    )
    owned_power_target = power_stock[0].target_id
    filtered_power_stock = rotating_power_inventory(
        power_entries,
        run_seed='SHOP-INVENTORY-CHECK',
        stage=1,
        offer_count=SHOP_CONFIG.power_inventory_size,
        excluded_target_ids=(owned_power_target,),
    )
    owned_power_stock_excluded = bool(
        len(filtered_power_stock) == SHOP_CONFIG.power_inventory_size
        and all(
            entry.target_id != owned_power_target
            for entry in filtered_power_stock
        )
        and {
            entry.reward_id for entry in power_stock
            if entry.target_id != owned_power_target
        }.issubset(entry.reward_id for entry in filtered_power_stock)
    )

    mission_pool = [
        {
            'code': 'SC_A1_HERO',
            'reward_class': 'act_1',
            'true_no_build': True,
        },
        {'code': 'SC_A1_1', 'reward_class': 'act_1'},
        {'code': 'SC_A1_2', 'reward_class': 'act_1'},
        {'code': 'SC_A1_3', 'reward_class': 'act_1'},
        {'code': 'SC_A2_1', 'reward_class': 'act_2'},
        {'code': 'SC_A2_2', 'reward_class': 'act_2'},
        {'code': 'SC_A2_3', 'reward_class': 'act_2'},
        {'code': 'SC_OP_1', 'reward_class': 'operation'},
        {'code': 'SC_OP_2', 'reward_class': 'operation'},
        {'code': 'SC_OP_3', 'reward_class': 'operation'},
        {'code': 'SC_FIN_1', 'reward_class': 'finale'},
        {'code': 'SC_FIN_2', 'reward_class': 'finale'},
        {'code': 'SC_FIN_3', 'reward_class': 'finale'},
    ]
    offers = generate_mission_offers(
        mission_pool, run_seed='SHOP-SELF-CHECK', stage=1
    )
    rerolled = generate_mission_offers(
        mission_pool,
        run_seed='SHOP-SELF-CHECK',
        stage=1,
        reroll_count=1,
        previous_offer_codes=[offer.mission_code for offer in offers],
    )
    completed_code = offers[0].mission_code
    after_completion = generate_mission_offers(
        mission_pool,
        run_seed='SHOP-SELF-CHECK',
        stage=2,
        completed_codes=(completed_code,),
    )
    mission_rules_valid = bool(
        len(offers) == 3
        and len({offer.mission_code for offer in offers}) == 3
        and {
            offer.economy_class for offer in offers
        } == {MissionEconomyClass.ACT_1}
        and 'SC_A1_HERO' in {
            offer.mission_code for offer in offers
        }
        and mission_classes_for_stage(1) == {
            MissionEconomyClass.ACT_1
        }
        and MissionEconomyClass.FINALE not in mission_classes_for_stage(8)
        and MissionEconomyClass.FINALE in mission_classes_for_stage(9)
        and offers == generate_mission_offers(
            mission_pool, run_seed='SHOP-SELF-CHECK', stage=1
        )
        and {offer.mission_code for offer in rerolled}
        != {offer.mission_code for offer in offers}
        and completed_code not in {
            offer.mission_code for offer in after_completion
        }
        and classify_mission({'code': 'AREDDAWN'})
        is MissionEconomyClass.ACT_1
        and classify_mission({'code': 'ADEMON'})
        is MissionEconomyClass.OPERATION
    )
    modifier_samples = [
        mission_modifier_for_offer(
            'SHOP-MODIFIER-CHECK',
            1,
            MissionOffer(f'SC_MOD_{index}', MissionEconomyClass.ACT_1),
        )
        for index in range(100)
    ]
    active_modifiers = [item for item in modifier_samples if item is not None]
    late_modifier_samples = [
        mission_modifier_for_offer(
            'SHOP-MODIFIER-CHECK',
            6,
            MissionOffer(f'SC_MOD_{index}', MissionEconomyClass.ACT_1),
        )
        for index in range(100)
    ]
    early_challenges = sum(
        bool(item and item.challenge) for item in modifier_samples
    )
    early_boons = sum(
        bool(item and not item.challenge) for item in modifier_samples
    )
    late_challenges = sum(
        bool(item and item.challenge) for item in late_modifier_samples
    )
    late_boons = sum(
        bool(item and not item.challenge) for item in late_modifier_samples
    )
    challenge = next(
        (item for item in active_modifiers if item.challenge), None
    )
    challenge_reward = mission_reward(
        MissionEconomyClass.ACT_1,
        mission_modifier=challenge,
    ) if challenge is not None else None
    mission_modifier_valid = bool(
        active_modifiers
        and challenge is not None
        and challenge_reward.mission_bonus_run_coins
        == challenge.bonus_run_coins
        and challenge_reward.mission_bonus_meta_coins
        == challenge.bonus_meta_coins
        and mission_modifier_for_offer(
            'SHOP-MODIFIER-CHECK',
            1,
            MissionOffer('SC_OPERATION', MissionEconomyClass.OPERATION),
        ) is None
    )
    mission_modifier_curve_valid = bool(
        early_boons > early_challenges
        and late_challenges > late_boons
        and late_challenges > early_challenges
    )
    configured_effect_reward_ids = {
        reward_id
        for modifier in MISSION_MODIFIERS
        for reward_id in (
            *modifier.player_reward_ids,
            *((modifier.enemy_reward_id,) if modifier.enemy_reward_id else ()),
        )
    }
    owned_aid_powers = {
        'Great Tempest Power',
        'Paladin Aid Power',
        'Drakuv Prison Vehicle Power',
    }
    owned_modifier_samples = [
        mission_modifier_for_offer(
            'SHOP-OWNED-MODIFIER-CHECK',
            1,
            MissionOffer(f'SC_OWNED_MOD_{index}', MissionEconomyClass.ACT_1),
            owned_reward_ids=owned_aid_powers,
        )
        for index in range(100)
    ]
    mission_modifier_variety_valid = bool(
        {
            'Lightning Storm Power',
            'Nuclear Missile Power',
            'Psychic Dominator Power',
            'Great Tempest Power',
            'Paladin Aid Power',
            'Drakuv Prison Vehicle Power',
            'Engineering Team Power',
            'Moon Reinforcements Power',
        }.issubset(
            configured_effect_reward_ids
        )
        and {'paladin_support', 'drakuv_support'}.issubset(
            modifier.id for modifier in active_modifiers
        )
        and configured_effect_reward_ids.issubset(REWARD_BY_NAME)
        and any(
            modifier is not None and not modifier.challenge
            for modifier in owned_modifier_samples
        )
    )
    mission_modifier_choices_unique = True
    for sample in range(100):
        sample_offers = tuple(
            MissionOffer(
                f'SC_UNIQUE_{sample}_{index}', MissionEconomyClass.ACT_1
            )
            for index in range(3)
        )
        for stage in (1, 6):
            sample_run = ShopRun(
                run_id=f'shop-modifier-unique-{sample}-{stage}',
                seed=f'SHOP-MODIFIER-UNIQUE-{sample}',
                status=RunStatus.ACTIVE,
                stage=stage,
                run_length=SHOP_CONFIG.run_length,
                run_coins=0,
                mission_offers=sample_offers,
            )
            resolved_ids = [
                modifier.id
                for offer in sample_offers
                if (
                    modifier := mission_modifier_for_run_offer(
                        sample_run, offer, challenge_slots=2
                    )
                ) is not None
            ]
            if len(resolved_ids) != len(set(resolved_ids)):
                mission_modifier_choices_unique = False
                break
    shop_airfield_rules = {
        aircraft_family: _tier_one_airfield_rules(
            {'soviets'}, {aircraft_family}, (), (), chaos_mode=True
        )
        for aircraft_family in ('allies', 'soviets', 'epsilon', 'foehn')
    }
    shop_single_airfield_valid = bool(
        all(len(rules) <= 1 for rules in shop_airfield_rules.values())
        and all(
            len(shop_airfield_rules[family]) == 1
            for family in ('allies', 'soviets', 'epsilon')
        )
    )

    run = ShopRun(
        run_id='shop-self-check-run',
        seed='SHOP-SELF-CHECK',
        status=RunStatus.ACTIVE,
        stage=1,
        run_length=SHOP_CONFIG.run_length,
        run_coins=SHOP_CONFIG.starting_run_coins,
        rerolls_used=1,
        difficulty_assists_used=1,
        assisted_mission_code=offers[0].mission_code,
        starting_unit_ids=('MOR_T1_INFANTRY',),
        starting_defense_ids=('MOR_T1_DEFENSES',),
        permanent_buffs_snapshot=(BuffPurchase(gi_buff_entry.reward_id, 1),),
        mission_offers=offers,
    )
    restored_run = normalize_shop_run(run.to_dict())
    malformed_run = run.to_dict()
    malformed_run['modifiers'] = ['unknown_modifier']
    try:
        normalize_shop_run(malformed_run)
        invalid_state_rejected = False
    except ShopStateError:
        invalid_state_rejected = True
    kept = tuple(offers[1:])
    replacement_offer = generate_mission_offers(
        mission_pool,
        run_seed=run.seed,
        stage=run.stage,
        reroll_count=run.rerolls_used + 1,
        completed_codes=tuple(offer.mission_code for offer in kept),
        previous_offer_codes=(offers[0].mission_code,),
        offer_count=1,
    )
    targeted_reroll = reroll_missions(
        replace(run, assisted_mission_code=None),
        (replacement_offer[0], *kept),
        maximum_rerolls=3,
        replaced_mission_code=offers[0].mission_code,
    )
    assisted = apply_mission_difficulty_assist(
        replace(run, difficulty_assists_used=0, assisted_mission_code=None),
        offers[1].mission_code,
        maximum_assists=1,
    )
    mission_actions_valid = bool(
        targeted_reroll.mission_offers[1:] == kept
        and targeted_reroll.mission_offers[0] != offers[0]
        and targeted_reroll.rerolls_used == 2
        and assisted.assisted_mission_code == offers[1].mission_code
        and assisted.difficulty_assists_used == 1
    )
    state_round_trip_valid = bool(
        restored_run == run
        and restored_run.mission_offers == offers
        and restored_run.rerolls_used == 1
        and restored_run.difficulty_assists_used == 1
        and restored_run.permanent_buffs_snapshot
        == (BuffPurchase(gi_buff_entry.reward_id, 1),)
        and restored_run.starting_unit_ids == ('MOR_T1_INFANTRY',)
        and normalize_shop_run(None) is None
        and invalid_state_rejected
    )

    details = {
        'config_validation_valid': config_validation_valid,
        'economy_valid': economy_valid,
        'catalogue_valid': len(catalogue) > 100,
        'archipelago_cameo_asset_valid': bool(
            ARCHIPELAGO_CAMEO_PATH.is_file()
            and ARCHIPELAGO_CAMEO_PATH.read_bytes().startswith(
                b'\x89PNG\r\n\x1a\n'
            )
        ),
        'archipelago_purchase_display_valid': bool(
            archipelago_purchase_placement_text({
                'item_name': 'Progressive Sword',
                'item': 42,
                'recipient_player': 'Link',
                'player': 3,
                'recipient_game': 'A Link to the Past',
            }) == (
                'Progressive Sword',
                'Link (A Link to the Past)',
            )
            and archipelago_purchase_placement_text({}) == (
                'Awaiting server details', '—'
            )
        ),
        'shop_reward_exclusions_valid': bool(
            'Foehn Blast Trench Access' in SHOP_CONFIG.excluded_reward_ids
            and all(
                entry.reward_id != 'Foehn Blast Trench Access'
                for entry in catalogue
            )
        ),
        'shop_exact_access_mode_valid': SHOP_ACCESS_REWARD_MODE == 'Chaos',
        'shop_single_airfield_valid': shop_single_airfield_valid,
        'purchase_rules_valid': purchase_rules_valid,
        'permanent_purchase_valid': permanent_purchase_valid,
        'loadout_valid': loadout_valid,
        'rotating_inventory_valid': rotating_inventory_valid,
        'rotating_power_inventory_valid': rotating_power_inventory_valid,
        'owned_access_stock_excluded_valid': bool(
            owned_unit_stock_excluded and owned_power_stock_excluded
        ),
        'mission_rules_valid': mission_rules_valid,
        'mission_modifier_valid': mission_modifier_valid,
        'mission_modifier_curve_valid': mission_modifier_curve_valid,
        'mission_modifier_variety_valid': mission_modifier_variety_valid,
        'mission_modifier_choices_unique_valid': (
            mission_modifier_choices_unique
        ),
        'mission_actions_valid': mission_actions_valid,
        'state_round_trip_valid': state_round_trip_valid,
        'catalogue_entries': len(catalogue),
    }
    details.update(_phase_two_checks(mission_pool))
    details.update(_phase_four_checks())
    details.update(_phase_five_checks())
    details.update(_phase_six_checks())
    details.update(_phase_seven_checks())
    details.update(_permanent_feature_checks(mission_pool))
    details.update(_requested_upgrade_modifier_checks())
    details['valid'] = all(
        value for key, value in details.items()
        if key.endswith('_valid')
    )
    return details
