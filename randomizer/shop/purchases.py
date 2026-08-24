"""Pure validation and application of run-local Shop purchases."""

from dataclasses import replace

from randomizer.rewards.catalogue import buff_stack_limit, canonical_reward
from randomizer.rewards.rules import tech_ids_for_rewards

from .catalogue import canonical_reward_id, catalogue_entry
from .model import (
    BuffPurchase,
    PurchaseRecord,
    PurchaseResult,
    PurchaseValidation,
    RunStatus,
    ShopRewardType,
)


def validate_run_purchase(
    reward,
    *,
    price,
    run_coins,
    run_status=RunStatus.ACTIVE,
    mission_committed=False,
    owned_reward_ids=(),
    active_tech_ids=(),
    active_power_ids=(),
    current_stacks=0,
    maximum_stacks=None,
    shop_eligible=True,
):
    canonical = canonical_reward(reward)
    reward_id = canonical_reward_id(canonical)
    entry = catalogue_entry(canonical) if shop_eligible else None
    try:
        price = int(price)
        run_coins = int(run_coins)
        current_stacks = int(current_stacks)
    except (TypeError, ValueError):
        return PurchaseValidation(PurchaseResult.NOT_SHOP_ELIGIBLE, reward_id)
    if RunStatus(run_status) is not RunStatus.ACTIVE:
        return PurchaseValidation(PurchaseResult.RUN_NOT_ACTIVE, reward_id, price)
    if mission_committed:
        return PurchaseValidation(
            PurchaseResult.PURCHASE_LOCKED_DURING_MISSION, reward_id, price
        )
    if entry is None or price < 0:
        return PurchaseValidation(PurchaseResult.NOT_SHOP_ELIGIBLE, reward_id, price)
    owned = set()
    for item in owned_reward_ids:
        owned_id = canonical_reward_id(item)
        if owned_id:
            owned.add(owned_id)
    if entry.reward_type in {
        ShopRewardType.UNIT_ACCESS,
        ShopRewardType.POWER_ACCESS,
    } and reward_id in owned:
        return PurchaseValidation(PurchaseResult.ALREADY_OWNED, reward_id, price)
    if entry.reward_type is ShopRewardType.UNIT_ACCESS:
        unlocked = {str(item).upper() for item in active_tech_ids}
        if tech_ids_for_rewards([canonical]).intersection(unlocked):
            return PurchaseValidation(PurchaseResult.ALREADY_OWNED, reward_id, price)
    if entry.reward_type is ShopRewardType.UNIT_BUFF:
        if entry.target_id not in {str(item).upper() for item in active_tech_ids}:
            return PurchaseValidation(
                PurchaseResult.REQUIRES_UNIT_ACCESS, reward_id, price
            )
    if entry.reward_type is ShopRewardType.POWER_BUFF:
        if entry.target_id not in {str(item).upper() for item in active_power_ids}:
            return PurchaseValidation(
                PurchaseResult.REQUIRES_UNIT_ACCESS, reward_id, price
            )
    if entry.reward_type in {
        ShopRewardType.UNIT_BUFF,
        ShopRewardType.POWER_BUFF,
    }:
        limit = buff_stack_limit(canonical) if maximum_stacks is None else maximum_stacks
        if limit is not None and current_stacks >= int(limit):
            return PurchaseValidation(PurchaseResult.MAX_STACKS, reward_id, price)
    if run_coins < price:
        return PurchaseValidation(
            PurchaseResult.INSUFFICIENT_CURRENCY, reward_id, price
        )
    return PurchaseValidation(PurchaseResult.OK, reward_id, price)


def apply_validated_run_purchase(
    run, reward, validation, *, consume_free_buff_token=False
):
    """Return updated immutable run after a successful validation."""
    if not validation.allowed:
        return run
    entry = catalogue_entry(reward)
    if entry is None or validation.reward_id != entry.reward_id:
        raise ValueError('Shop purchase validation does not match reward')
    if entry.reward_type in {
        ShopRewardType.UNIT_BUFF,
        ShopRewardType.POWER_BUFF,
    }:
        existing = {item.reward_id: item.stacks for item in run.run_buffs}
        existing[entry.reward_id] = existing.get(entry.reward_id, 0) + 1
        run_buffs = tuple(
            BuffPurchase(reward_id, stacks)
            for reward_id, stacks in existing.items()
        )
        return replace(
            run,
            run_coins=run.run_coins - validation.cost,
            run_buffs=run_buffs,
            free_buff_tokens_used=(
                run.free_buff_tokens_used + 1
                if consume_free_buff_token else run.free_buff_tokens_used
            ),
        )
    existing = {item.reward_id: item.quantity for item in run.run_purchases}
    existing[entry.reward_id] = existing.get(entry.reward_id, 0) + 1
    run_purchases = tuple(
        PurchaseRecord(reward_id, quantity)
        for reward_id, quantity in existing.items()
    )
    return replace(
        run,
        run_coins=run.run_coins - validation.cost,
        run_purchases=run_purchases,
    )
