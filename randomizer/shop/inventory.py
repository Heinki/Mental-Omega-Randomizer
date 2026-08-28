"""Deterministic rotating Shop inventory selection."""

from hashlib import sha256
import random


_TIER_RANK = {None: 0, 'tier_1': 1, 'tier_2': 2, 'tier_3': 3}


def _rotating_inventory(
    entries,
    *,
    run_seed,
    stage,
    offer_count,
    stream_name,
    excluded_target_ids=(),
):
    """Return stable stock for one run stage.

    Baseline membership changes only when seed or stage changes. Active targets
    are removed and replaced without disturbing remaining baseline offers.
    Input order cannot affect the result.
    """
    ordered = tuple(sorted(entries, key=lambda entry: entry.reward_id.casefold()))
    count = max(0, min(int(offer_count), len(ordered)))
    if count == len(ordered):
        selected = ordered
    else:
        stream = f'{stream_name}\0{run_seed}\0{int(stage)}'.encode('utf-8')
        seed = int.from_bytes(sha256(stream).digest()[:16], 'big')
        selected = tuple(random.Random(seed).sample(ordered, count))
    excluded = {
        str(target_id).upper()
        for target_id in excluded_target_ids
        if str(target_id)
    }
    if not excluded:
        return selected
    visible = [
        entry for entry in selected
        if str(entry.target_id).upper() not in excluded
    ]
    selected_reward_ids = {entry.reward_id for entry in selected}
    replacements = sorted(
        (
            entry for entry in ordered
            if entry.reward_id not in selected_reward_ids
            and str(entry.target_id).upper() not in excluded
        ),
        key=lambda entry: (
            sha256(
                f'{stream_name}_refill\0{run_seed}\0{int(stage)}\0'
                f'{entry.reward_id}'.encode('utf-8')
            ).digest(),
            entry.reward_id.casefold(),
        ),
    )
    visible.extend(replacements[:count - len(visible)])
    return tuple(visible)


def rotating_unit_inventory(
    entries, *, run_seed, stage, offer_count, excluded_target_ids=()
):
    return _rotating_inventory(
        entries,
        run_seed=run_seed,
        stage=stage,
        offer_count=offer_count,
        stream_name='shop_unit_inventory',
        excluded_target_ids=excluded_target_ids,
    )


def rotating_power_inventory(
    entries, *, run_seed, stage, offer_count, excluded_target_ids=()
):
    """Return deterministic superweapon and aid-power stock for one stage."""
    return _rotating_inventory(
        entries,
        run_seed=run_seed,
        stage=stage,
        offer_count=offer_count,
        stream_name='shop_power_inventory',
        excluded_target_ids=excluded_target_ids,
    )


def preserve_locked_offer(stock, locked_entry, *, protected_reward_ids=()):
    """Keep one selected access offer without increasing stock size."""
    stock = list(stock)
    if locked_entry is None or any(
        entry.reward_id == locked_entry.reward_id for entry in stock
    ):
        return tuple(stock)
    protected = set(protected_reward_ids)
    replacement = next(
        (
            index for index in range(len(stock) - 1, -1, -1)
            if stock[index].reward_type is locked_entry.reward_type
            and stock[index].reward_id not in protected
        ),
        next(
            (
                index for index in range(len(stock) - 1, -1, -1)
                if stock[index].reward_id not in protected
            ),
            None,
        ),
    )
    if replacement is not None:
        stock[replacement] = locked_entry
    return tuple(stock)


def guarantee_premium_offer(
    stock,
    eligible_entries,
    *,
    run_seed,
    stage,
    minimum_stage,
    protected_reward_ids=(),
):
    """Guarantee one deterministic Tier 2/3 access offer in later stages."""
    stock = list(stock)
    if int(stage) < int(minimum_stage) or not stock:
        return tuple(stock)
    minimum_rank = 3 if int(stage) >= 7 else 2
    if any(_TIER_RANK.get(entry.tier, 0) >= minimum_rank for entry in stock):
        return tuple(stock)
    selected_ids = {entry.reward_id for entry in stock}
    candidates = [
        entry for entry in eligible_entries
        if entry.reward_id not in selected_ids
        and _TIER_RANK.get(entry.tier, 0) >= minimum_rank
    ]
    if not candidates:
        return tuple(stock)
    candidates.sort(key=lambda entry: (
        sha256(
            f'premium_supplier\0{run_seed}\0{int(stage)}\0'
            f'{entry.reward_id}'.encode('utf-8')
        ).digest(),
        entry.reward_id.casefold(),
    ))
    protected = set(protected_reward_ids)
    replacement = next(
        (
            index for index in range(len(stock) - 1, -1, -1)
            if stock[index].reward_id not in protected
        ),
        None,
    )
    if replacement is not None:
        stock[replacement] = candidates[0]
    return tuple(stock)
