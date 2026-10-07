"""Shared-slot co-op projections; the host owns the Archipelago connection."""

from copy import deepcopy
from dataclasses import replace

from randomizer.rewards.catalogue import REWARD_BY_NAME, canonical_reward
from randomizer.shop.archipelago import archipelago_shop_identity, shop_reward_ids_from_ap_ledger
from randomizer.shop.model import RunStatus
from randomizer.shop.transitions import merge_archipelago_entitlements


def received_rewards(state):
    """Use the same indexed AP ledger as campaign and Shop progression."""
    ap = state.get('archipelago')
    if not isinstance(ap, dict) or not ap.get('enabled'):
        return None
    result = []
    seen = set()
    for record in ap.get('received_rewards', ()):
        if not isinstance(record, dict):
            continue
        try:
            index = int(record['index'])
        except (KeyError, TypeError, ValueError):
            continue
        reward = canonical_reward({'name': record.get('reward_name', '')})
        if index < 0 or index in seen or reward.get('name') not in REWARD_BY_NAME:
            continue
        seen.add(index)
        result.append((index, reward))
    return [reward for _index, reward in sorted(result, key=lambda item: item[0])]


def shared_run_state(state, slot_data=None):
    """Mirror AP inventory and identity without credentials or local backups."""
    shared = deepcopy(state)
    ap = shared.get('archipelago')
    if isinstance(ap, dict):
        allowed = (
            'enabled', 'activation', 'manifest_checksum', 'run_manifest',
            'slot_data', 'team', 'slot', 'received_rewards',
        )
        shared['archipelago'] = {key: ap[key] for key in allowed if key in ap}
        shared['archipelago']['shared_coop'] = True
        if isinstance(slot_data, dict):
            mapping = shared['archipelago'].setdefault('slot_data', {})
            for key in ('locations', 'local_victories', 'items'):
                if key in slot_data:
                    mapping[key] = deepcopy(slot_data[key])
        # Shop identity includes the room seed; no session cursor/UUID is shared.
        shared['archipelago']['checkpoint'] = {
            'seed_name': (ap.get('checkpoint') or {}).get('seed_name', ''),
        }
    return shared


def shared_shop_inventory(run, state):
    """Bind a matching guest run to shared AP items, preserving its economy."""
    ap = state.get('archipelago')
    if (run is None or run.status is not RunStatus.ACTIVE
            or not isinstance(ap, dict) or not ap.get('enabled')):
        return run
    identity = archipelago_shop_identity(ap)
    if not identity or run.seed != state.get('seed'):
        return run
    if run.ap_identity and run.ap_identity != identity:
        raise ValueError('Guest Shop run belongs to another Archipelago slot.')
    if not run.eligible_mission_codes or any(
        not code.startswith('COOP_') for code in run.eligible_mission_codes
    ):
        raise ValueError('Shared Archipelago requires a co-op Shop run.')
    shop = (ap.get('slot_data') or {}).get('shop') or {}
    pool = tuple(shop.get('mission_pool') or run.eligible_mission_codes)
    if any(not code.startswith('COOP_') for code in pool):
        raise ValueError('Shared Archipelago Shop pool contains a campaign mission.')
    run = replace(run, ap_identity=identity, eligible_mission_codes=pool)
    return merge_archipelago_entitlements(
        run, identity, shop_reward_ids_from_ap_ledger(ap.get('received_rewards', ())),
    )
