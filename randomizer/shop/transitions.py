"""Pure Shop run lifecycle transitions and idempotency rules."""

from dataclasses import dataclass, replace
from collections import Counter

from .config import SHOP_CONFIG
from .catalogue import (
    canonical_reward_for_id,
    catalogue_entry,
    shop_entry_available,
)
from .economy import mission_reward, starting_run_coins
from .meta import validate_starting_loadout
from .model import (
    CurrencyReward,
    MissionOffer,
    RunStatus,
    ShopModeConfig,
    ShopProfile,
    ShopRun,
)
from .state import normalize_shop_run


class ShopTransitionError(ValueError):
    """Raised when an event conflicts with persisted Shop run state."""


@dataclass(frozen=True)
class StartRunTransition:
    profile: ShopProfile
    run: ShopRun
    transaction_id: str


@dataclass(frozen=True)
class VictoryTransition:
    profile: ShopProfile
    run: ShopRun
    reward: CurrencyReward
    victory_key: str
    changed: bool


@dataclass(frozen=True)
class FailureTransition:
    run: ShopRun
    changed: bool


def victory_key(run_id, stage, mission_code):
    mission_code = str(mission_code or '').upper()
    if not run_id or not mission_code:
        raise ValueError('Victory key requires run_id and mission_code')
    return f'{run_id}:{int(stage)}:{mission_code}:victory'


def _victory_already_rewarded(run, mission_code):
    prefix = f'{run.run_id}:'
    suffix = f':{mission_code}:victory'
    return any(
        key.startswith(prefix) and key.endswith(suffix)
        for key in run.rewarded_victories
    )


def start_new_run(
    profile,
    *,
    run_id,
    seed,
    mission_offers,
    campaign_filter='All Campaigns',
    reward_mode='Standard',
    reward_settings=None,
    eligible_mission_codes=(),
    starter_tech_ids=(),
    starting_unit_ids=(),
    starting_defense_ids=(),
    selected_reward_ids=(),
    permanent_buffs=(),
    permanent_entitlement_ids=(),
    ap_entitlement_ids=(),
    ap_identity=None,
    modifiers=(),
    config: ShopModeConfig = SHOP_CONFIG,
):
    run_id = str(run_id or '')
    seed = str(seed or '')
    if not run_id or not seed:
        raise ShopTransitionError('New Shop run requires run_id and seed')
    offers = tuple(mission_offers)
    if not offers or len(offers) > config.mission_offer_count or any(
        not isinstance(offer, MissionOffer) for offer in offers
    ):
        raise ShopTransitionError('New Shop run has invalid mission offers')
    ap_entitlements = tuple(
        str(reward_id) for reward_id in ap_entitlement_ids if str(reward_id)
    )
    entitlements = tuple(permanent_entitlement_ids) + ap_entitlements
    loadout = validate_starting_loadout(
        starter_tech_ids=starter_tech_ids,
        selected_reward_ids=selected_reward_ids,
        entitled_reward_ids=entitlements,
        config=config,
    )
    if not loadout.allowed:
        raise ShopTransitionError(
            f'Invalid Shop starting loadout: {loadout.result.value}'
        )
    reward_settings = dict(reward_settings or {})
    faction_filter = str(
        reward_settings.get('shop_faction_filter') or campaign_filter
    )
    unavailable_loadout = [
        reward_id for reward_id in loadout.selected_reward_ids
        if not shop_entry_available(
            catalogue_entry(canonical_reward_for_id(reward_id)),
            campaign_filter=faction_filter,
            reward_mode=reward_mode,
            strict_faction=bool(reward_settings.get('shop_faction_filter')),
        )
    ]
    if unavailable_loadout:
        raise ShopTransitionError(
            'Shop starting loadout is unavailable for current campaign: '
            + ', '.join(unavailable_loadout)
        )
    modifier_ids = tuple(dict.fromkeys(
        str(modifier_id) for modifier_id in modifiers if str(modifier_id)
    ))
    unknown_modifiers = [
        modifier_id for modifier_id in modifier_ids
        if modifier_id not in config.modifiers
    ]
    if unknown_modifiers:
        raise ShopTransitionError(
            f'Unknown Shop run modifier IDs: {unknown_modifiers}'
        )
    updated_profile = replace(
        profile,
        lifetime_runs_started=profile.lifetime_runs_started + 1,
    )
    run = ShopRun(
        run_id=run_id,
        seed=seed,
        status=RunStatus.ACTIVE,
        stage=1,
        run_length=config.run_length,
        run_coins=starting_run_coins(
            starting_capital_level=profile.upgrade_level('starting_capital'),
            modifiers=modifier_ids,
            config=config,
        ),
        campaign_filter=str(campaign_filter or 'All Campaigns'),
        reward_mode=str(reward_mode or 'Standard'),
        reward_settings=reward_settings,
        eligible_mission_codes=tuple(dict.fromkeys(
            str(code).upper() for code in eligible_mission_codes if str(code)
        )),
        starting_unit_ids=tuple(dict.fromkeys(
            str(unit_id).upper()
            for unit_id in starting_unit_ids
            if str(unit_id)
        )),
        starting_defense_ids=tuple(dict.fromkeys(
            str(unit_id).upper()
            for unit_id in starting_defense_ids
            if str(unit_id)
        )),
        selected_permanent_units=loadout.selected_reward_ids,
        permanent_buffs_snapshot=tuple(permanent_buffs),
        ap_identity=str(ap_identity or '') or None,
        ap_entitlements_snapshot=ap_entitlements,
        mission_offers=offers,
        modifiers=modifier_ids,
    )
    run = normalize_shop_run(run.to_dict(), config=config)
    return StartRunTransition(
        updated_profile,
        run,
        f'{run_id}:start',
    )


def merge_archipelago_entitlements(run, ap_identity, reward_ids):
    """Add newly received items for the AP identity bound to an active run."""
    identity = str(ap_identity or '')
    if (
        run.status is not RunStatus.ACTIVE
        or not identity
        or run.ap_identity != identity
    ):
        return run
    incoming = tuple(
        str(reward_id) for reward_id in reward_ids if str(reward_id)
    )
    existing_counts = Counter(run.ap_entitlements_snapshot)
    incoming_counts = Counter(incoming)
    missing_counts = incoming_counts - existing_counts
    if not missing_counts:
        return run
    additions = []
    for reward_id in incoming:
        if missing_counts[reward_id] > 0:
            additions.append(reward_id)
            missing_counts[reward_id] -= 1
    return replace(
        run,
        ap_entitlements_snapshot=(
            run.ap_entitlements_snapshot + tuple(additions)
        ),
    )


def select_mission(run, mission_code):
    mission_code = str(mission_code or '').upper()
    if run.status is not RunStatus.ACTIVE:
        raise ShopTransitionError('Only an active Shop run can select a mission')
    if run.mission_committed:
        if run.selected_mission_code == mission_code:
            return run
        raise ShopTransitionError(
            f'Shop stage already committed to {run.selected_mission_code}'
        )
    if mission_code not in {offer.mission_code for offer in run.mission_offers}:
        raise ShopTransitionError(
            f'Mission {mission_code!r} is not in current Shop offer'
        )
    return replace(run, selected_mission_code=mission_code)


def reroll_missions(
    run,
    mission_offers,
    *,
    maximum_rerolls,
    replaced_mission_code=None,
    config: ShopModeConfig = SHOP_CONFIG,
):
    if run.status is not RunStatus.ACTIVE:
        raise ShopTransitionError('Only an active Shop run can reroll missions')
    if run.mission_committed:
        raise ShopTransitionError('Cannot reroll after a mission is committed')
    maximum_rerolls = max(0, int(maximum_rerolls))
    if run.rerolls_used >= maximum_rerolls:
        raise ShopTransitionError('No Shop mission rerolls remain')
    offers = tuple(mission_offers)
    if not offers or len(offers) > config.mission_offer_count or any(
        not isinstance(offer, MissionOffer) for offer in offers
    ):
        raise ShopTransitionError('Shop reroll produced invalid mission offers')
    replaced_mission_code = str(replaced_mission_code or '').upper()
    if replaced_mission_code:
        old_codes = {offer.mission_code for offer in run.mission_offers}
        new_codes = {offer.mission_code for offer in offers}
        if (
            replaced_mission_code not in old_codes
            or len(offers) != len(run.mission_offers)
            or old_codes - {replaced_mission_code}
            != new_codes.intersection(old_codes - {replaced_mission_code})
            or replaced_mission_code in new_codes
        ):
            raise ShopTransitionError(
                'Shop reroll must replace only selected mission offer'
            )
    return replace(
        run,
        rerolls_used=run.rerolls_used + 1,
        mission_offers=offers,
        selected_mission_code=(
            None
            if not replaced_mission_code
            or run.selected_mission_code == replaced_mission_code
            else run.selected_mission_code
        ),
        assisted_mission_code=(
            None
            if run.assisted_mission_code == replaced_mission_code
            else run.assisted_mission_code
        ),
    )


def apply_mission_difficulty_assist(
    run, mission_code, *, maximum_assists
):
    mission_code = str(mission_code or '').upper()
    if run.status is not RunStatus.ACTIVE:
        raise ShopTransitionError('Only an active Shop run can ease a mission')
    if run.mission_committed:
        raise ShopTransitionError('Cannot ease a committed mission')
    if mission_code not in {offer.mission_code for offer in run.mission_offers}:
        raise ShopTransitionError('Mission is not in current Shop offer')
    if run.assisted_mission_code:
        raise ShopTransitionError('One mission is already eased for this stage')
    if run.difficulty_assists_used >= max(0, int(maximum_assists)):
        raise ShopTransitionError('No Shop difficulty assists remain')
    return replace(
        run,
        difficulty_assists_used=run.difficulty_assists_used + 1,
        assisted_mission_code=mission_code,
    )


def commit_selected_mission(run, mission_code):
    mission_code = str(mission_code or '').upper()
    if run.status is not RunStatus.ACTIVE:
        raise ShopTransitionError('Only an active Shop run can commit a mission')
    if run.mission_committed:
        if run.selected_mission_code == mission_code:
            return run
        raise ShopTransitionError(
            f'Shop stage already committed to {run.selected_mission_code}'
        )
    offered = {offer.mission_code for offer in run.mission_offers}
    if mission_code not in offered:
        raise ShopTransitionError(
            f'Mission {mission_code!r} is not in current Shop offer'
        )
    if mission_code in set(run.completed_missions):
        raise ShopTransitionError(
            f'Mission {mission_code!r} is already completed in this run'
        )
    return replace(
        run,
        selected_mission_code=mission_code,
        mission_committed=True,
    )


def apply_mission_victory(
    profile,
    run,
    mission_code,
    *,
    next_offers=(),
    config: ShopModeConfig = SHOP_CONFIG,
):
    mission_code = str(mission_code or '').upper()
    if _victory_already_rewarded(run, mission_code):
        existing_key = next(
            key for key in run.rewarded_victories
            if key.startswith(f'{run.run_id}:')
            and key.endswith(f':{mission_code}:victory')
        )
        return VictoryTransition(
            profile, run, CurrencyReward(), existing_key, False
        )
    if run.status is not RunStatus.ACTIVE:
        raise ShopTransitionError('Only an active Shop run can record victory')
    if not run.mission_committed or run.selected_mission_code != mission_code:
        raise ShopTransitionError(
            f'Mission {mission_code!r} is not committed for current Shop stage'
        )
    offer = next(
        (
            offer for offer in run.mission_offers
            if offer.mission_code == mission_code
        ),
        None,
    )
    if offer is None:
        raise ShopTransitionError(
            f'Committed mission {mission_code!r} is missing from Shop offer'
        )
    final_victory = run.stage == run.run_length
    next_offers = tuple(next_offers)
    if final_victory:
        if next_offers:
            raise ShopTransitionError('Completed Shop run cannot create more offers')
    elif not next_offers or len(next_offers) > config.mission_offer_count:
        raise ShopTransitionError('Next Shop stage requires valid mission offers')
    completed_codes = set(run.completed_missions)
    completed_codes.add(mission_code)
    if any(
        not isinstance(next_offer, MissionOffer)
        or next_offer.mission_code in completed_codes
        for next_offer in next_offers
    ):
        raise ShopTransitionError('Next Shop offer contains invalid mission data')

    reward = mission_reward(
        offer.economy_class,
        victory_coin_bonus_level=profile.upgrade_level(
            'victory_run_coin_bonus'
        ),
        modifiers=run.modifiers,
        config=config,
    )
    key = victory_key(run.run_id, run.stage, mission_code)
    updated_profile = replace(
        profile,
        meta_coins=profile.meta_coins + reward.meta_coins,
        lifetime_meta_coins_earned=(
            profile.lifetime_meta_coins_earned + reward.meta_coins
        ),
        lifetime_missions_completed=profile.lifetime_missions_completed + 1,
        lifetime_runs_completed=(
            profile.lifetime_runs_completed + (1 if final_victory else 0)
        ),
    )
    updated_run = replace(
        run,
        status=RunStatus.COMPLETED if final_victory else RunStatus.ACTIVE,
        stage=run.stage if final_victory else run.stage + 1,
        run_coins=run.run_coins + reward.run_coins,
        mission_offers=() if final_victory else next_offers,
        selected_mission_code=None,
        mission_committed=False,
        assisted_mission_code=None,
        completed_missions=run.completed_missions + (mission_code,),
        rewarded_victories=run.rewarded_victories + (key,),
    )
    updated_run = normalize_shop_run(updated_run.to_dict(), config=config)
    return VictoryTransition(
        updated_profile, updated_run, reward, key, True
    )


def apply_mission_failure(run, mission_code):
    mission_code = str(mission_code or '').upper()
    if run.status is RunStatus.FAILED:
        if run.failed_mission_code == mission_code:
            return FailureTransition(run, False)
        raise ShopTransitionError('Shop run already failed on another mission')
    if run.status is not RunStatus.ACTIVE:
        raise ShopTransitionError('Only an active Shop run can record failure')
    if not run.mission_committed or run.selected_mission_code != mission_code:
        raise ShopTransitionError(
            f'Mission {mission_code!r} is not committed for current Shop stage'
        )
    failed = replace(
        run,
        status=RunStatus.FAILED,
        failed_mission_code=mission_code,
        failed_stage=run.stage,
    )
    return FailureTransition(failed, True)


def abandon_run(run):
    """End an active run without treating an offered mission as failed."""
    if run.status is not RunStatus.ACTIVE:
        raise ShopTransitionError('Only an active Shop run can be given up')
    abandoned = replace(
        run,
        status=RunStatus.FAILED,
        mission_offers=(),
        selected_mission_code=None,
        mission_committed=False,
        failed_mission_code='GAVE_UP',
        failed_stage=run.stage,
    )
    return FailureTransition(abandoned, True)
