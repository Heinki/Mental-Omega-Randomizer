"""Deterministic rotating Shop inventory selection."""

from hashlib import sha256
import random


def _rotating_inventory(entries, *, run_seed, stage, offer_count, stream_name):
    """Return stable stock for one run stage.

    Membership changes only when seed or stage changes. Input order cannot
    affect the result.
    """
    ordered = tuple(sorted(entries, key=lambda entry: entry.reward_id.casefold()))
    count = max(0, min(int(offer_count), len(ordered)))
    if count == len(ordered):
        return ordered
    stream = f'{stream_name}\0{run_seed}\0{int(stage)}'.encode('utf-8')
    seed = int.from_bytes(sha256(stream).digest()[:16], 'big')
    selected = random.Random(seed).sample(ordered, count)
    return tuple(selected)


def rotating_unit_inventory(entries, *, run_seed, stage, offer_count):
    return _rotating_inventory(
        entries,
        run_seed=run_seed,
        stage=stage,
        offer_count=offer_count,
        stream_name='shop_unit_inventory',
    )


def rotating_power_inventory(entries, *, run_seed, stage, offer_count):
    """Return deterministic superweapon and aid-power stock for one stage."""
    return _rotating_inventory(
        entries,
        run_seed=run_seed,
        stage=stage,
        offer_count=offer_count,
        stream_name='shop_power_inventory',
    )
