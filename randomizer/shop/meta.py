"""Permanent unlock, upgrade, and starting-loadout rules."""

from dataclasses import dataclass, replace

from randomizer.rewards.rules import tech_ids_for_rewards

from .catalogue import (
    canonical_reward_for_id,
    canonical_reward_id,
    catalogue_entry,
)
from .config import SHOP_CONFIG
from .economy import permanent_upgrade_price
from .model import (
    BuffPurchase,
    LoadoutValidation,
    PurchaseResult,
    PurchaseValidation,
    ShopModeConfig,
    ShopProfile,
    ShopRewardType,
)


@dataclass(frozen=True)
class ProfilePurchaseOutcome:
    profile: ShopProfile
    validation: PurchaseValidation


def purchase_permanent_unit(profile, reward, *, price, shop_eligible=True):
    reward_id = canonical_reward_id(reward)
    entry = catalogue_entry(reward) if shop_eligible else None
    if entry is None or entry.reward_type is not ShopRewardType.UNIT_ACCESS:
        validation = PurchaseValidation(
            PurchaseResult.NOT_SHOP_ELIGIBLE, reward_id, int(price)
        )
        return ProfilePurchaseOutcome(profile, validation)
    owned = {canonical_reward_id(item) for item in profile.permanent_unit_unlocks}
    if reward_id in owned:
        validation = PurchaseValidation(
            PurchaseResult.ALREADY_OWNED, reward_id, int(price)
        )
        return ProfilePurchaseOutcome(profile, validation)
    if profile.meta_coins < int(price):
        validation = PurchaseValidation(
            PurchaseResult.INSUFFICIENT_CURRENCY, reward_id, int(price)
        )
        return ProfilePurchaseOutcome(profile, validation)
    validation = PurchaseValidation(PurchaseResult.OK, reward_id, int(price))
    updated = replace(
        profile,
        meta_coins=profile.meta_coins - int(price),
        permanent_unit_unlocks=profile.permanent_unit_unlocks + (reward_id,),
    )
    return ProfilePurchaseOutcome(updated, validation)


def purchase_permanent_buff(profile, reward, *, price, shop_eligible=True):
    reward_id = canonical_reward_id(reward)
    entry = catalogue_entry(reward) if shop_eligible else None
    if entry is None or entry.reward_type is not ShopRewardType.UNIT_BUFF:
        return ProfilePurchaseOutcome(
            profile,
            PurchaseValidation(
                PurchaseResult.NOT_SHOP_ELIGIBLE, reward_id, int(price)
            ),
        )
    owned_targets = {
        owned_entry.target_id
        for owned_id in profile.permanent_unit_unlocks
        for owned_entry in [catalogue_entry(canonical_reward_for_id(owned_id))]
        if owned_entry is not None
        and owned_entry.reward_type is ShopRewardType.UNIT_ACCESS
    }
    if entry.target_id not in owned_targets:
        return ProfilePurchaseOutcome(
            profile,
            PurchaseValidation(
                PurchaseResult.REQUIRES_UNIT_ACCESS, reward_id, int(price)
            ),
        )
    current = next((
        item.stacks for item in profile.permanent_buffs
        if item.reward_id == reward_id
    ), 0)
    if entry.stack_limit is not None and current >= entry.stack_limit:
        return ProfilePurchaseOutcome(
            profile,
            PurchaseValidation(PurchaseResult.MAX_STACKS, reward_id, int(price)),
        )
    if profile.meta_coins < int(price):
        return ProfilePurchaseOutcome(
            profile,
            PurchaseValidation(
                PurchaseResult.INSUFFICIENT_CURRENCY, reward_id, int(price)
            ),
        )
    buffs = [
        item for item in profile.permanent_buffs if item.reward_id != reward_id
    ]
    buffs.append(BuffPurchase(reward_id, current + 1))
    return ProfilePurchaseOutcome(
        replace(
            profile,
            meta_coins=profile.meta_coins - int(price),
            permanent_buffs=tuple(buffs),
        ),
        PurchaseValidation(PurchaseResult.OK, reward_id, int(price)),
    )


def purchase_permanent_upgrade(
    profile,
    upgrade_id,
    *,
    config: ShopModeConfig = SHOP_CONFIG,
):
    definition = config.permanent_upgrades.get(str(upgrade_id))
    if definition is None:
        validation = PurchaseValidation(PurchaseResult.NOT_SHOP_ELIGIBLE)
        return ProfilePurchaseOutcome(profile, validation)
    current_level = profile.upgrade_level(definition.id)
    if current_level >= definition.max_level:
        validation = PurchaseValidation(PurchaseResult.MAX_UPGRADE_LEVEL)
        return ProfilePurchaseOutcome(profile, validation)
    price = permanent_upgrade_price(
        definition.id, current_level + 1, config=config
    )
    if profile.meta_coins < price:
        validation = PurchaseValidation(
            PurchaseResult.INSUFFICIENT_CURRENCY, definition.id, price
        )
        return ProfilePurchaseOutcome(profile, validation)
    levels = dict(profile.permanent_upgrades)
    levels[definition.id] = current_level + 1
    validation = PurchaseValidation(PurchaseResult.OK, definition.id, price)
    return ProfilePurchaseOutcome(
        replace(
            profile,
            meta_coins=profile.meta_coins - price,
            permanent_upgrades=levels,
        ),
        validation,
    )


def validate_starting_loadout(
    *,
    starter_tech_ids,
    selected_reward_ids,
    entitled_reward_ids,
    maximum_extra_units=None,
    config: ShopModeConfig = SHOP_CONFIG,
):
    maximum = (
        config.max_selected_permanent_units
        if maximum_extra_units is None
        else int(maximum_extra_units)
    )
    entitled = set()
    for item in entitled_reward_ids:
        reward_id = canonical_reward_id(item)
        if reward_id:
            entitled.add(reward_id)
    active = {str(item).upper() for item in starter_tech_ids if str(item)}
    selected = []
    selected_ids = set()
    slots = 0
    for raw_reward_id in selected_reward_ids:
        reward_id = canonical_reward_id(raw_reward_id)
        if not reward_id or reward_id not in entitled:
            return LoadoutValidation(
                PurchaseResult.NOT_ENTITLED,
                tuple(selected),
                tuple(sorted(active)),
                slots,
            )
        if reward_id in selected_ids:
            continue
        reward = canonical_reward_for_id(reward_id)
        entry = catalogue_entry(reward)
        if entry is None or entry.reward_type is not ShopRewardType.UNIT_ACCESS:
            return LoadoutValidation(
                PurchaseResult.NOT_SHOP_ELIGIBLE,
                tuple(selected),
                tuple(sorted(active)),
                slots,
            )
        reward_tech_ids = tech_ids_for_rewards([reward])
        selected.append(reward_id)
        selected_ids.add(reward_id)
        if reward_tech_ids - active:
            slots += 1
            if slots > maximum:
                return LoadoutValidation(
                    PurchaseResult.MAX_LOADOUT_SIZE,
                    tuple(selected),
                    tuple(sorted(active)),
                    slots,
                )
            active.update(reward_tech_ids)
    return LoadoutValidation(
        PurchaseResult.OK,
        tuple(selected),
        tuple(sorted(active)),
        slots,
    )
