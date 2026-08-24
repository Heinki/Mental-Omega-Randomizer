"""Durable Mental Coin transactions for generated AP Shop locations."""

from copy import deepcopy
from dataclasses import replace

from .model import PurchaseResult, PurchaseValidation


TRANSACTION_KEY = 'shop_purchase_transactions'


def archipelago_purchase_records(profile, identity):
    scoped = profile.archipelago_profiles.get(str(identity), {})
    if not isinstance(scoped, dict):
        return {}
    records = scoped.get(TRANSACTION_KEY, {})
    return deepcopy(records) if isinstance(records, dict) else {}


def pending_archipelago_purchase_ids(profile, identity):
    return tuple(sorted(
        int(location_id)
        for location_id, record in archipelago_purchase_records(
            profile, identity
        ).items()
        if record.get('status') == 'pending'
    ))


def validate_archipelago_purchase(
    profile,
    identity,
    location_id,
    *,
    cost,
    connected,
    available_location_ids,
    checked_location_ids=(),
):
    identity = str(identity or '')
    location_id = int(location_id or 0)
    cost = int(cost)
    if not connected or not identity:
        return PurchaseValidation(PurchaseResult.AP_NOT_CONNECTED)
    if location_id not in set(int(value) for value in available_location_ids):
        return PurchaseValidation(PurchaseResult.NOT_SHOP_ELIGIBLE)
    records = archipelago_purchase_records(profile, identity)
    if (
        location_id in set(int(value) for value in checked_location_ids)
        or str(location_id) in records
    ):
        return PurchaseValidation(
            PurchaseResult.AP_LOCATION_ALREADY_CHECKED,
            str(location_id),
            cost,
        )
    if profile.meta_coins < cost:
        return PurchaseValidation(
            PurchaseResult.INSUFFICIENT_CURRENCY,
            str(location_id),
            cost,
        )
    return PurchaseValidation(PurchaseResult.OK, str(location_id), cost)


def commit_archipelago_purchase(profile, identity, validation):
    if not validation.allowed:
        return profile
    identity = str(identity)
    location_id = str(validation.reward_id)
    profiles = deepcopy(dict(profile.archipelago_profiles))
    scoped = deepcopy(profiles.get(identity, {}))
    records = deepcopy(scoped.get(TRANSACTION_KEY, {}))
    if location_id in records:
        return profile
    records[location_id] = {
        'cost': validation.cost,
        'status': 'pending',
    }
    scoped[TRANSACTION_KEY] = records
    profiles[identity] = scoped
    return replace(
        profile,
        meta_coins=profile.meta_coins - validation.cost,
        archipelago_profiles=profiles,
    )


def reconcile_archipelago_purchases(profile, identity, checked_location_ids):
    identity = str(identity or '')
    records = archipelago_purchase_records(profile, identity)
    checked = {int(value) for value in checked_location_ids}
    changed = False
    for location_id, record in records.items():
        if (
            int(location_id) in checked
            and record.get('status') != 'checked'
        ):
            record['status'] = 'checked'
            changed = True
    if not changed:
        return profile
    profiles = deepcopy(dict(profile.archipelago_profiles))
    scoped = deepcopy(profiles.get(identity, {}))
    scoped[TRANSACTION_KEY] = records
    profiles[identity] = scoped
    return replace(profile, archipelago_profiles=profiles)
