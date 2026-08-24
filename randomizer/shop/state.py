"""Normalization and version gates for persisted Shop Mode documents."""

from copy import deepcopy

from .config import SHOP_CONFIG
from .model import (
    SHOP_PROFILE_SCHEMA_VERSION,
    SHOP_RUN_SCHEMA_VERSION,
    BuffPurchase,
    MissionEconomyClass,
    MissionOffer,
    PurchaseRecord,
    RunStatus,
    ShopProfile,
    ShopRun,
)


class ShopStateError(ValueError):
    """Raised when explicit Shop state cannot be normalized safely."""


def _object(value, field):
    if not isinstance(value, dict):
        raise ShopStateError(f'Shop state field {field!r} must be an object')
    return value


def _nonnegative_int(value, field, default=0):
    if value is None:
        value = default
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ShopStateError(
            f'Shop state field {field!r} must be a non-negative integer'
        )
    return value


def _positive_int(value, field, default):
    value = default if value is None else value
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ShopStateError(
            f'Shop state field {field!r} must be a positive integer'
        )
    return value


def _string(value, field, *, required=False):
    if value is None and not required:
        return None
    if not isinstance(value, str) or (required and not value):
        requirement = 'a non-empty string' if required else 'a string or null'
        raise ShopStateError(f'Shop state field {field!r} must be {requirement}')
    return value


def _unique_strings(value, field):
    if value is None:
        return ()
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ShopStateError(
            f'Shop state field {field!r} must be a list of non-empty strings'
        )
    return tuple(dict.fromkeys(value))


def _strings(value, field):
    if value is None:
        return ()
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ShopStateError(
            f'Shop state field {field!r} must be a list of non-empty strings'
        )
    return tuple(value)


def _unique_mission_codes(value, field):
    return tuple(dict.fromkeys(
        code.upper() for code in _unique_strings(value, field)
    ))


def _version(document, current, state_name):
    version = document.get('schema_version', current)
    if not isinstance(version, int) or isinstance(version, bool):
        raise ShopStateError(f'{state_name} schema_version must be an integer')
    if version != current:
        raise ShopStateError(
            f'Unsupported {state_name} schema_version {version!r}; expected {current}'
        )
    return version


def migrate_shop_profile(document):
    document = deepcopy(_object(document, 'profile'))
    _version(document, SHOP_PROFILE_SCHEMA_VERSION, 'Shop profile')
    return document


def _archipelago_profiles(value):
    profiles = deepcopy(_object(value, 'archipelago_profiles'))
    for identity, scoped in profiles.items():
        if not isinstance(identity, str) or not identity:
            raise ShopStateError(
                'Shop Archipelago profile identities must be non-empty strings'
            )
        scoped = _object(scoped, f'archipelago_profiles.{identity}')
        transactions = _object(
            scoped.get('shop_purchase_transactions', {}),
            f'archipelago_profiles.{identity}.shop_purchase_transactions',
        )
        for location_id, record in transactions.items():
            try:
                numeric_location = int(location_id)
            except (TypeError, ValueError) as exc:
                raise ShopStateError(
                    f'Invalid AP Shop purchase location {location_id!r}'
                ) from exc
            if str(numeric_location) != str(location_id) or numeric_location < 1:
                raise ShopStateError(
                    f'Invalid AP Shop purchase location {location_id!r}'
                )
            record = _object(
                record,
                f'archipelago_profiles.{identity}.'
                f'shop_purchase_transactions.{location_id}',
            )
            if set(record) != {'cost', 'status'}:
                raise ShopStateError(
                    f'Invalid AP Shop purchase record for location '
                    f'{location_id!r}'
                )
            _positive_int(
                record.get('cost'),
                f'archipelago_profiles.{identity}.'
                f'shop_purchase_transactions.{location_id}.cost',
                1,
            )
            if record.get('status') not in {'pending', 'checked'}:
                raise ShopStateError(
                    f'Invalid AP Shop purchase status for location '
                    f'{location_id!r}'
                )
    return profiles


def normalize_shop_profile(document=None, *, config=SHOP_CONFIG):
    if document is None:
        document = {}
    document = migrate_shop_profile(document)
    unlocks = _unique_strings(
        document.get('permanent_unit_unlocks'), 'permanent_unit_unlocks'
    )
    raw_upgrades = document.get('permanent_upgrades')
    raw_upgrades = {} if raw_upgrades is None else _object(
        raw_upgrades, 'permanent_upgrades'
    )
    upgrades = {}
    legacy_names = {
        'mission_reroll_level': 'mission_reroll',
        'victory_run_coin_bonus_level': 'victory_run_coin_bonus',
    }
    for raw_id, raw_level in raw_upgrades.items():
        upgrade_id = legacy_names.get(str(raw_id), str(raw_id))
        definition = config.permanent_upgrades.get(upgrade_id)
        if definition is None:
            raise ShopStateError(
                f'Unknown Shop profile permanent upgrade {upgrade_id!r}'
            )
        level = _nonnegative_int(
            raw_level, f'permanent_upgrades.{raw_id}'
        )
        if level > definition.max_level:
            raise ShopStateError(
                f'Shop profile upgrade {upgrade_id!r} exceeds maximum level '
                f'{definition.max_level}'
            )
        upgrades[upgrade_id] = level
    archipelago_profiles = _archipelago_profiles(
        document.get('archipelago_profiles', {})
    )
    permanent_buffs = _purchase_records(
        document.get('permanent_buffs'),
        'permanent_buffs',
        'stacks',
        BuffPurchase,
    )
    return ShopProfile(
        schema_version=SHOP_PROFILE_SCHEMA_VERSION,
        meta_coins=_nonnegative_int(document.get('meta_coins'), 'meta_coins'),
        lifetime_meta_coins_earned=_nonnegative_int(
            document.get('lifetime_meta_coins_earned'),
            'lifetime_meta_coins_earned',
        ),
        lifetime_runs_started=_nonnegative_int(
            document.get('lifetime_runs_started'), 'lifetime_runs_started'
        ),
        lifetime_runs_completed=_nonnegative_int(
            document.get('lifetime_runs_completed'), 'lifetime_runs_completed'
        ),
        lifetime_missions_completed=_nonnegative_int(
            document.get('lifetime_missions_completed'),
            'lifetime_missions_completed',
        ),
        permanent_unit_unlocks=unlocks,
        permanent_buffs=permanent_buffs,
        permanent_upgrades=upgrades,
        salvaged_run_coins=_nonnegative_int(
            document.get('salvaged_run_coins'), 'salvaged_run_coins'
        ),
        archipelago_profiles=archipelago_profiles,
    )


def migrate_shop_run(document):
    document = deepcopy(_object(document, 'run'))
    _version(document, SHOP_RUN_SCHEMA_VERSION, 'Shop run')
    return document


def _purchase_records(value, field, quantity_field, record_type):
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ShopStateError(f'Shop state field {field!r} must be a list')
    combined = {}
    for index, raw_record in enumerate(value):
        record = _object(raw_record, f'{field}[{index}]')
        reward_id = _string(
            record.get('reward_id'), f'{field}[{index}].reward_id', required=True
        )
        quantity = _positive_int(
            record.get(quantity_field),
            f'{field}[{index}].{quantity_field}',
            1,
        )
        combined[reward_id] = combined.get(reward_id, 0) + quantity
    return tuple(
        record_type(reward_id, quantity)
        for reward_id, quantity in combined.items()
    )


def _mission_offers(value):
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ShopStateError('Shop state field mission_offers must be a list')
    offers = []
    seen = set()
    for index, raw_offer in enumerate(value):
        offer = _object(raw_offer, f'mission_offers[{index}]')
        code = _string(
            offer.get('mission_code'),
            f'mission_offers[{index}].mission_code',
            required=True,
        ).upper()
        if code in seen:
            raise ShopStateError(f'Duplicate Shop mission offer {code!r}')
        try:
            economy_class = MissionEconomyClass(offer.get('class'))
        except ValueError as exc:
            raise ShopStateError(
                f'Invalid Shop mission class for offer {code!r}'
            ) from exc
        seen.add(code)
        offers.append(MissionOffer(code, economy_class))
    return tuple(offers)


def normalize_shop_run(document, *, config=SHOP_CONFIG):
    if document is None:
        return None
    document = migrate_shop_run(document)
    try:
        status = RunStatus(document.get('status', RunStatus.ACTIVE.value))
    except ValueError as exc:
        raise ShopStateError(
            f'Invalid Shop run status {document.get("status")!r}'
        ) from exc
    run_length = _positive_int(
        document.get('run_length'), 'run_length', config.run_length
    )
    stage = _positive_int(document.get('stage'), 'stage', 1)
    if stage > run_length:
        raise ShopStateError(
            f'Shop run stage {stage} exceeds run length {run_length}'
        )
    offers = _mission_offers(document.get('mission_offers'))
    if len(offers) > config.mission_offer_count:
        raise ShopStateError(
            f'Shop run has {len(offers)} mission offers; maximum is '
            f'{config.mission_offer_count}'
        )
    selected_mission = _string(
        document.get('selected_mission_code'), 'selected_mission_code'
    )
    selected_mission = selected_mission.upper() if selected_mission else None
    offer_codes = {offer.mission_code for offer in offers}
    if selected_mission and selected_mission not in offer_codes:
        raise ShopStateError(
            f'Selected Shop mission {selected_mission!r} is not in current offer'
        )
    assisted_mission = _string(
        document.get('assisted_mission_code'), 'assisted_mission_code'
    )
    assisted_mission = assisted_mission.upper() if assisted_mission else None
    if assisted_mission and assisted_mission not in offer_codes:
        raise ShopStateError(
            f'Assisted Shop mission {assisted_mission!r} is not in current offer'
        )
    mission_committed = document.get('mission_committed', False)
    if not isinstance(mission_committed, bool):
        raise ShopStateError('Shop state field mission_committed must be boolean')
    if mission_committed and not selected_mission:
        raise ShopStateError('Committed Shop run has no selected mission')
    failed_stage = document.get('failed_stage')
    if failed_stage is not None:
        failed_stage = _positive_int(failed_stage, 'failed_stage', 1)
    failed_mission = _string(
        document.get('failed_mission_code'), 'failed_mission_code'
    )
    failed_mission = failed_mission.upper() if failed_mission else None
    if status is RunStatus.FAILED and (not failed_mission or failed_stage is None):
        raise ShopStateError(
            'Failed Shop run must record failed_mission_code and failed_stage'
        )
    if status is not RunStatus.FAILED and (failed_mission or failed_stage is not None):
        raise ShopStateError(
            'Only a failed Shop run may record failure fields'
        )
    modifiers = _unique_strings(document.get('modifiers'), 'modifiers')
    unknown_modifiers = [
        modifier_id for modifier_id in modifiers
        if modifier_id not in config.modifiers
    ]
    if unknown_modifiers:
        raise ShopStateError(
            f'Unknown Shop run modifier IDs: {unknown_modifiers}'
        )
    return ShopRun(
        schema_version=SHOP_RUN_SCHEMA_VERSION,
        run_id=_string(document.get('run_id'), 'run_id', required=True),
        seed=_string(document.get('seed'), 'seed', required=True),
        status=status,
        stage=stage,
        run_length=run_length,
        run_coins=_nonnegative_int(document.get('run_coins'), 'run_coins'),
        campaign_filter=_string(
            document.get('campaign_filter', 'All Campaigns'),
            'campaign_filter',
            required=True,
        ),
        reward_mode=_string(
            document.get('reward_mode', 'Standard'),
            'reward_mode',
            required=True,
        ),
        reward_settings=deepcopy(_object(
            document.get('reward_settings', {}), 'reward_settings'
        )),
        eligible_mission_codes=_unique_mission_codes(
            document.get('eligible_mission_codes'), 'eligible_mission_codes'
        ),
        rerolls_used=_nonnegative_int(
            document.get('rerolls_used'), 'rerolls_used'
        ),
        difficulty_assists_used=_nonnegative_int(
            document.get('difficulty_assists_used'),
            'difficulty_assists_used',
        ),
        assisted_mission_code=assisted_mission,
        starting_unit_ids=_unique_mission_codes(
            document.get('starting_unit_ids'), 'starting_unit_ids'
        ),
        starting_defense_ids=_unique_mission_codes(
            document.get('starting_defense_ids'), 'starting_defense_ids'
        ),
        selected_permanent_units=_unique_strings(
            document.get('selected_permanent_units'), 'selected_permanent_units'
        ),
        permanent_buffs_snapshot=_purchase_records(
            document.get('permanent_buffs_snapshot'),
            'permanent_buffs_snapshot',
            'stacks',
            BuffPurchase,
        ),
        ap_identity=_string(document.get('ap_identity'), 'ap_identity'),
        ap_entitlements_snapshot=_strings(
            document.get('ap_entitlements_snapshot'),
            'ap_entitlements_snapshot',
        ),
        run_purchases=_purchase_records(
            document.get('run_purchases'),
            'run_purchases',
            'quantity',
            PurchaseRecord,
        ),
        run_buffs=_purchase_records(
            document.get('run_buffs'),
            'run_buffs',
            'stacks',
            BuffPurchase,
        ),
        starting_draft_buffs=_purchase_records(
            document.get('starting_draft_buffs'),
            'starting_draft_buffs',
            'stacks',
            BuffPurchase,
        ),
        free_buff_tokens_used=_nonnegative_int(
            document.get('free_buff_tokens_used'), 'free_buff_tokens_used'
        ),
        emergency_revivals_used=_nonnegative_int(
            document.get('emergency_revivals_used'),
            'emergency_revivals_used',
        ),
        mission_offers=offers,
        selected_mission_code=selected_mission,
        mission_committed=mission_committed,
        completed_missions=_unique_mission_codes(
            document.get('completed_missions'), 'completed_missions'
        ),
        rewarded_victories=_unique_strings(
            document.get('rewarded_victories'), 'rewarded_victories'
        ),
        modifiers=modifiers,
        failed_mission_code=failed_mission,
        failed_stage=failed_stage,
    )
