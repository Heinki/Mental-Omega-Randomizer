"""Synthetic Shop Mode slot-data v6 contract check."""

import json
from hashlib import sha256

from randomizer.core.version import APP_VERSION
from randomizer.shop.config import SHOP_CONFIG

from .catalogue_contract import runtime_catalogue_checksum
from .client.handshake import validate_slot_data
from .yaml_config import serialize_player_yaml


def validate_shop_slot_contract():
    run_length = SHOP_CONFIG.run_length
    purchase_count = SHOP_CONFIG.archipelago_purchase_locations
    victories_are_locations = (
        SHOP_CONFIG.archipelago_mission_victories_are_locations
    )
    mission_order = [
        f'SHOP_TEST_{index}' for index in range(1, run_length + 1)
    ]
    shop = {
        'run_length': run_length,
        'mission_pool': mission_order,
        'mission_victories_are_locations': victories_are_locations,
        'purchase_location_count': purchase_count,
        'purchase_meta_coin_cost': (
            SHOP_CONFIG.archipelago_purchase_meta_coin_cost
        ),
        'starting_extra_unit_limit': (
            SHOP_CONFIG.max_selected_permanent_units
        ),
        'received_unit_loadout': 'random',
    }
    manifest = {
        'schema_version': 1,
        'randomizer_version': APP_VERSION,
        'randomizer_seed': 'AP-SHOP-SELF-CHECK',
        'catalogue_checksum': runtime_catalogue_checksum(),
        'campaign_filter': 'All Campaigns',
        'progression_mode': 'Shop Mode',
        'mission_goal': run_length,
        'mission_order': mission_order,
        'progression': {
            'type': 'shop_stages',
            'starting_missions': mission_order,
            'mission_requirements': {code: [] for code in mission_order},
        },
        'goal': {'type': 'shop_run', 'run_length': run_length},
        'shop': shop,
        'locations': {code: {} for code in mission_order},
        'item_pool': {'GI Access': purchase_count + (
            run_length if victories_are_locations else 0
        )},
        'starting_items': {},
        'local_placements': [],
        'grid': None,
        'frozen_settings': {'launcher': {'progression_mode': 'Shop Mode'}},
        'state_snapshot': {
            'seed': 'AP-SHOP-SELF-CHECK',
            'campaign_filter': 'All Campaigns',
            'progression_mode': 'Shop Mode',
            'mission_order': mission_order,
            'mission_checks': {code: [] for code in mission_order},
        },
    }
    manifest['manifest_checksum'] = sha256(json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    ).encode('utf-8')).hexdigest()
    player_yaml = serialize_player_yaml(manifest, 'Shop Contract Test')
    purchase_locations = [
        0x4DFE000 + index for index in range(purchase_count)
    ]
    stages = [{
        'stage': stage,
        'location': (
            0x4DFE100 + stage - 1 if victories_are_locations else None
        ),
        'logic_item': 0x4DFE200 + stage - 1,
        'logic_location': 0x4DFE200 + stage - 1,
    } for stage in range(1, run_length + 1)]
    slot_data = {
        'slot_data_version': 6,
        'randomizer_version': APP_VERSION,
        'randomizer_seed': manifest['randomizer_seed'],
        'catalogue_checksum': manifest['catalogue_checksum'],
        'manifest_checksum': manifest['manifest_checksum'],
        'campaign_filter': manifest['campaign_filter'],
        'progression_mode': 'Shop Mode',
        'mission_goal': run_length,
        'mission_order': mission_order,
        'goal': manifest['goal'],
        'shop': {
            **shop,
            'purchase_locations': purchase_locations,
            'stage_victories': stages,
        },
        'run_manifest': manifest,
        'items': {str(0x4D4F000): 'GI Access'},
        'locations': {code: {} for code in mission_order},
        'local_victories': {},
    }
    normalized = validate_slot_data(slot_data)
    legacy_manifest = json.loads(json.dumps(manifest))
    legacy_manifest['shop'].pop('received_unit_loadout')
    legacy_manifest['manifest_checksum'] = sha256(json.dumps(
        {
            key: value for key, value in legacy_manifest.items()
            if key != 'manifest_checksum'
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    ).encode('utf-8')).hexdigest()
    legacy_slot_data = json.loads(json.dumps(slot_data))
    legacy_slot_data['shop'].pop('received_unit_loadout')
    legacy_slot_data['run_manifest'] = legacy_manifest
    legacy_slot_data['manifest_checksum'] = legacy_manifest[
        'manifest_checksum'
    ]
    legacy_normalized = validate_slot_data(legacy_slot_data)
    return bool(
        normalized['slot_data_version'] == 6
        and '"received_unit_loadout": "random"' in player_yaml
        and normalized['shop']['received_unit_loadout'] == 'random'
        and normalized['shop']['purchase_locations'] == purchase_locations
        and len(normalized['shop']['stage_victories']) == run_length
        and legacy_normalized['shop']['received_unit_loadout'] == 'manual'
    )
