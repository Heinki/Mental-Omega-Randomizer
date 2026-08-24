"""Project Archipelago received-item history into Shop Mode state."""

import hashlib
import json

from .catalogue import canonical_reward_for_id, catalogue_entry
from .model import ShopRewardType


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


def ap_automatic_reward_ids(reward_ids):
    """Return received AP buffs and powers, preserving legitimate stacks."""
    automatic = []
    for reward_id in reward_ids or ():
        entry = catalogue_entry(canonical_reward_for_id(reward_id))
        if entry is not None and entry.reward_type is not ShopRewardType.UNIT_ACCESS:
            automatic.append(entry.reward_id)
    return tuple(automatic)
