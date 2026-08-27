"""Project Archipelago received-item history into Shop Mode state."""

import hashlib
import json
import random

from .catalogue import canonical_reward_for_id, catalogue_entry
from .model import ShopRewardType


ARCHIPELAGO_RECEIVED_UNIT_LOADOUT_RANDOM = 'random'
ARCHIPELAGO_RECEIVED_UNIT_LOADOUT_MANUAL = 'manual'
ARCHIPELAGO_RECEIVED_UNIT_LOADOUT_ALL = 'all'


def archipelago_shop_identity(ap_state):
    """Return a stable room/team/slot identity without using display name."""
    if not isinstance(ap_state, dict):
        return ''
    checkpoint = ap_state.get('checkpoint')
    checkpoint = checkpoint if isinstance(checkpoint, dict) else {}
    try:
        team = int(ap_state.get('team') or 0)
        slot = int(ap_state.get('slot') or 0)
    except (TypeError, ValueError):
        return ''
    identity = {
        'room_seed': str(checkpoint.get('seed_name') or ''),
        'manifest_checksum': str(ap_state.get('manifest_checksum') or ''),
        'team': team,
        'slot': slot,
    }
    if (
        not identity['manifest_checksum']
        or identity['team'] < 0
        or identity['slot'] <= 0
    ):
        return ''
    payload = json.dumps(
        identity, sort_keys=True, separators=(',', ':'), ensure_ascii=True
    ).encode('utf-8')
    return 'ap-v1:' + hashlib.sha256(payload).hexdigest()


def shop_reward_ids_from_ap_ledger(records):
    """Return canonical Shop rewards once per received AP item index."""
    reward_ids = []
    seen_indexes = set()
    for record in records or ():
        if not isinstance(record, dict):
            continue
        try:
            index = int(record['index'])
        except (KeyError, TypeError, ValueError):
            continue
        if index < 0 or index in seen_indexes:
            continue
        seen_indexes.add(index)
        reward = canonical_reward_for_id(record.get('reward_name', ''))
        entry = catalogue_entry(reward)
        if entry is not None:
            reward_ids.append(entry.reward_id)
    return tuple(reward_ids)


def ap_unit_entitlement_ids(reward_ids):
    """Return unique AP unit unlocks eligible for starting-loadout selection."""
    unit_ids = []
    seen = set()
    for reward_id in reward_ids or ():
        entry = catalogue_entry(canonical_reward_for_id(reward_id))
        if (
            entry is not None
            and entry.reward_type is ShopRewardType.UNIT_ACCESS
            and entry.reward_id not in seen
        ):
            seen.add(entry.reward_id)
            unit_ids.append(entry.reward_id)
    return tuple(unit_ids)


def random_ap_unit_entitlement_ids(
    reward_ids,
    *,
    run_seed,
    run_number,
    maximum_count,
    ap_identity='',
    excluded_reward_ids=(),
):
    """Choose a reproducible AP unit loadout for one disposable Shop run."""
    excluded = {
        str(reward_id) for reward_id in excluded_reward_ids if str(reward_id)
    }
    candidates = tuple(sorted(
        (
            reward_id for reward_id in ap_unit_entitlement_ids(reward_ids)
            if reward_id not in excluded
        ),
        key=str.casefold,
    ))
    count = max(0, min(int(maximum_count), len(candidates)))
    if count == len(candidates):
        return candidates
    stream = (
        'shop_archipelago_received_unit_loadout\0'
        f'{run_seed}\0{int(run_number)}\0{ap_identity}'
    ).encode('utf-8')
    seed = int.from_bytes(hashlib.sha256(stream).digest()[:16], 'big')
    selected = random.Random(seed).sample(candidates, count)
    return tuple(sorted(selected, key=str.casefold))


def ap_automatic_reward_ids(reward_ids):
    """Return every received AP reward, preserving legitimate effect stacks.

    Unit access is entitlement-like and therefore emitted once. Buff and power
    rewards retain received-item multiplicity so their configured stacking
    behavior remains unchanged.
    """
    automatic = []
    unit_ids = set()
    for reward_id in reward_ids or ():
        entry = catalogue_entry(canonical_reward_for_id(reward_id))
        if entry is None:
            continue
        if entry.reward_type is ShopRewardType.UNIT_ACCESS:
            if entry.reward_id in unit_ids:
                continue
            unit_ids.add(entry.reward_id)
        automatic.append(entry.reward_id)
    return tuple(automatic)
