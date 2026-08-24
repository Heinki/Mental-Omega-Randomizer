"""Deterministic rotating Shop inventory selection."""

from hashlib import sha256
import random


def rotating_unit_inventory(entries, *, run_seed, stage, offer_count):
    """Return stable unit stock for one run stage.

    Membership changes only when seed or stage changes. Input order cannot
    affect the result.
    """
    ordered = tuple(sorted(entries, key=lambda entry: entry.reward_id.casefold()))
    count = max(0, min(int(offer_count), len(ordered)))
    if count == len(ordered):
        return ordered
    stream = f'shop_unit_inventory\0{run_seed}\0{int(stage)}'.encode('utf-8')
    seed = int.from_bytes(sha256(stream).digest()[:16], 'big')
    selected = random.Random(seed).sample(ordered, count)
    return tuple(selected)
