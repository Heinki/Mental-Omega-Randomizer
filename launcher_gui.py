"""Entry point for source runs and the packaged launcher."""

import json
from hashlib import sha256
import random
import sys
import traceback

from randomizer.ui.cameos import ensure_superweapon_cameos, ensure_unit_cameos
from randomizer.core.diagnostics import event as log_event
from randomizer.core.paths import (
    APP_DIR,
    GAME_EXE,
    GAME_LAUNCHER_EXE,
    GAME_ROOT,
    LAUNCHER_LOG,
    MAP_RENDERER_DIR,
    WINDOW_ICON_PATH,
)
from randomizer.core.version import APP_VERSION
from randomizer.config.static import REQUIRED_STATIC_CONFIGS, validate_static_configs
from randomizer.maps.settings import validate_eva_voice_profiles
from randomizer.rewards.roster import (
    MAX_PLAYER_BUILD_TIME_MULTIPLIER,
    ROSTER_FILENAMES,
    validate_drakuv_contracts,
    validate_hidden_passenger_payloads,
    validate_house_wide_buff_policy,
    validate_limited_hero_build_limits,
    validate_randomizer_unit_health,
    validate_randomizer_unit_roster,
    validate_reviewed_vehicle_identity_contracts,
    validate_special_roster_contracts,
    validate_special_reward_build_times,
    validate_transport_buff_eligibility,
    validate_unit_buff_application_contracts,
)
from randomizer.ui.config import EVA_APPEARANCE_PROFILES, EVA_VOICE_TAGS


def run_launcher():
    """Load config-dependent application modules with visible startup errors."""
    try:
        from randomizer.application.app import main
        main()
        return 0
    except Exception:
        detail = traceback.format_exc()
        log_event('launcher_startup_failed', traceback=detail)
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                'Mental Omega Randomizer Startup Failed',
                'The launcher could not load its configuration or runtime.\n\n'
                f'{detail.splitlines()[-1]}\n\nSee {LAUNCHER_LOG} for details.',
            )
            root.destroy()
        except Exception:
            pass
        return 1


def run_self_check():
    """Write an installation report without opening the GUI."""
    report_path = APP_DIR / 'self_check.json'
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        cameos = ensure_unit_cameos(['ABRM'])
        power_cameos = ensure_superweapon_cameos(['LightningStormSpecial'])
        static_config_paths = validate_static_configs(REQUIRED_STATIC_CONFIGS)
        from randomizer.shop.self_check import validate_shop_domain
        shop_domain = validate_shop_domain()
        import websockets
        from websockets.sync.client import connect as websocket_connect
        from Archipelago.client.handshake import (
            normalize_server_uri,
            validate_slot_data,
        )
        from Archipelago.client import (
            ArchipelagoSession,
            ReceivedItemLedger,
            SessionConfig,
        )
        from Archipelago.catalogue_contract import runtime_catalogue_checksum
        from Archipelago.run_manifest import expected_logic_spheres
        from Archipelago.shop_self_check import validate_shop_slot_contract
        from Archipelago.yaml_config import (
            parse_player_yaml,
            serialize_player_yaml,
        )
        archipelago_catalogue_checksum = runtime_catalogue_checksum()
        archipelago_manifest = {
            'schema_version': 1,
            'randomizer_version': APP_VERSION,
            'randomizer_seed': 'APWORLD-SELF-CHECK',
            'catalogue_checksum': archipelago_catalogue_checksum,
            'campaign_filter': 'Allies',
            'progression_mode': 'Classic',
            'mission_goal': 1,
            'mission_order': ['AREDDAWN'],
            'progression': {
                'type': 'victory_count',
                'starting_missions': ['AREDDAWN'],
                'mission_requirements': {'AREDDAWN': 0},
            },
            'goal': {'type': 'mission', 'mission_code': 'AREDDAWN'},
            'locations': {
                'AREDDAWN': {'objective_1': 1, 'victory': 1},
            },
            'item_pool': {'GI Access': 1, 'Soviet Conscript Access': 1},
            'starting_items': {},
            'local_placements': [],
            'grid': None,
            'frozen_settings': {
                'launcher': {
                    'seed': 'APWORLD-SELF-CHECK',
                    'campaign_filter': 'Allies',
                    'mission_goal': 1,
                    'progression_mode': 'Classic',
                    'rewards_per_objective': 1,
                    'rewards_on_victory_only': False,
                    'use_act_based_reward_multipliers': True,
                    'unlock_all_rewards_after_final_grid_mission': False,
                    'generation': {'reward_mode': 'Standard'},
                },
            },
            'state_snapshot': {
                'seed': 'APWORLD-SELF-CHECK',
                'campaign_filter': 'Allies',
                'progression_mode': 'Classic',
                'mission_order': ['AREDDAWN'],
                'mission_checks': {
                    'AREDDAWN': [
                        {'id': 'objective_1'},
                        {'id': 'victory'},
                    ],
                },
            },
        }
        archipelago_manifest['manifest_checksum'] = sha256(json.dumps(
            archipelago_manifest,
            ensure_ascii=False,
            sort_keys=True,
            separators=(',', ':'),
        ).encode('utf-8')).hexdigest()
        archipelago_grid_logic_spheres = expected_logic_spheres({
            'mission_order': ['START_A', 'START_B', 'INNER', 'OUTER'],
            'progression': {
                'type': 'grid_neighbors',
                'starting_missions': ['START_A', 'START_B'],
                'mission_requirements': {
                    'START_A': ['INNER'],
                    'START_B': ['INNER'],
                    'INNER': ['START_A', 'START_B', 'OUTER'],
                    'OUTER': ['INNER'],
                },
            },
            'goal': {'type': 'mission', 'mission_code': 'OUTER'},
        })
        archipelago_player_yaml = serialize_player_yaml(
            archipelago_manifest, "Self Checker's Slot"
        )
        archipelago_player_document = parse_player_yaml(
            archipelago_player_yaml
        )
        archipelago_slot_data = validate_slot_data({
            'slot_data_version': 5,
            'randomizer_version': APP_VERSION,
            'randomizer_seed': 'APWORLD-SELF-CHECK',
            'catalogue_checksum': archipelago_catalogue_checksum,
            'manifest_checksum': archipelago_manifest['manifest_checksum'],
            'campaign_filter': 'Allies',
            'progression_mode': 'Classic',
            'mission_goal': 1,
            'mission_order': ['AREDDAWN'],
            'goal': {'type': 'mission', 'mission_code': 'AREDDAWN'},
            'run_manifest': archipelago_manifest,
            'items': {
                str(0x4D4F000): 'GI Access',
                str(0x4D4F001): 'Soviet Conscript Access',
                str(0x4DFF000): 'Mental Omega Local Victory: AREDDAWN',
            },
            'locations': {
                'AREDDAWN': {
                    'objective_1': [0x4D5F000],
                    'victory': [0x4D5F001],
                }
            },
            'local_victories': {
                'AREDDAWN': {
                    'item': 0x4DFF000,
                    'location': 0x4DFF000,
                },
            },
        })
        archipelago_shop_slot_contract_valid = validate_shop_slot_contract()
        archipelago_ledger = ReceivedItemLedger()
        archipelago_pending, archipelago_desynchronized = (
            archipelago_ledger.ingest(0, [{
                'item': 0x4D4F000,
                'location': 0x4D5F000,
                'player': 1,
                'flags': 1,
            }])
        )
        archipelago_ledger.acknowledge([0])
        archipelago_session = ArchipelagoSession(
            SessionConfig('localhost', 'MOSmoke')
        )
        archipelago_first_locations = archipelago_session.report_locations(
            [0x4D5F000, 0x4D5F001, 0x4D5F001]
        )
        archipelago_repeat_locations = archipelago_session.report_locations(
            [0x4D5F000, 0x4D5F001]
        )
        archipelago_first_goal = archipelago_session.mark_goal_complete()
        archipelago_repeat_goal = archipelago_session.mark_goal_complete()
        archipelago_client_contract_valid = bool(
            websockets.__version__ == '17.0'
            and callable(websocket_connect)
            and normalize_server_uri('localhost') == 'ws://localhost:38281/'
            and archipelago_slot_data['mission_order'] == ['AREDDAWN']
            and archipelago_shop_slot_contract_valid
            and archipelago_slot_data['items'][0x4D4F000] == 'GI Access'
            and archipelago_slot_data['items'][0x4D4F001]
            == 'Soviet Conscript Access'
            and archipelago_slot_data['items'][0x4DFF000]
            == 'Mental Omega Local Victory: AREDDAWN'
            and archipelago_slot_data['local_victories']['AREDDAWN']
            == {'item': 0x4DFF000, 'location': 0x4DFF000}
            and archipelago_slot_data['catalogue_checksum']
            == archipelago_catalogue_checksum
            and archipelago_grid_logic_spheres == {
                'mission_spheres': {
                    'START_A': 1,
                    'START_B': 1,
                    'INNER': 2,
                    'OUTER': 3,
                },
                'goal_sphere': 4,
            }
            and archipelago_player_document['name']
            == "Self Checker's Slot"
            and archipelago_player_document['run_manifest']
            == archipelago_manifest
            and 'generated_world:' in archipelago_player_yaml
            and 'run_manifest:' not in archipelago_player_yaml
            and 'Generated run data.' not in archipelago_player_yaml
            and 'progression_balancing:' not in archipelago_player_yaml
            and 'accessibility:' not in archipelago_player_yaml
            and archipelago_slot_data['run_manifest']['state_snapshot'][
                'seed'
            ] == 'APWORLD-SELF-CHECK'
            and SessionConfig('localhost', 'MOSmoke').normalized().server
            == 'ws://localhost:38281/'
            and not archipelago_desynchronized
            and len(archipelago_pending) == 1
            and not archipelago_ledger.pending
            and archipelago_first_locations == (0x4D5F000, 0x4D5F001)
            and archipelago_repeat_locations == ()
            and archipelago_first_goal
            and not archipelago_repeat_goal
            and archipelago_session.checkpoint()['format'] == 2
            and archipelago_session.checkpoint()['pending_locations']
            == [0x4D5F000, 0x4D5F001]
            and archipelago_session.checkpoint()['goal_complete']
        )
        unit_roster = validate_randomizer_unit_roster()
        drakuv_contracts = validate_drakuv_contracts()
        unit_buff_applications = validate_unit_buff_application_contracts()
        limited_hero_limits = validate_limited_hero_build_limits()
        special_roster = validate_special_roster_contracts()
        hidden_passenger_payloads = validate_hidden_passenger_payloads()
        reviewed_vehicle_identities = validate_reviewed_vehicle_identity_contracts()
        unit_health = validate_randomizer_unit_health()
        special_build_times = validate_special_reward_build_times()
        transport_buffs = validate_transport_buff_eligibility()
        house_wide_buffs = validate_house_wide_buff_policy()
        from randomizer.maps.special_buildings import (
            validate_ore_purifier_miner_docks,
            validate_original_refinery_contract,
            validate_reprocessor_bounty_support,
        )
        ore_purifier_docks = validate_ore_purifier_miner_docks()
        player_refineries = validate_original_refinery_contract()
        reprocessor_bounty = validate_reprocessor_bounty_support()
        from randomizer.rewards.catalogue import (
            AID_POWER_MAP_CONFIGS,
            AID_POWER_UNLOCK_REWARDS,
            BUFF_TARGETS,
            POWER_BUFF_REWARDS,
            REWARD_POOL,
            buff_stack_limit,
            canonical_reward,
            linked_buff_variant_ids,
        )
        from randomizer.rewards.enemy_scaling import (
            ENEMY_BUFF_DEFINITIONS,
            ENEMY_BUFF_GROUP_DEFINITIONS,
            enemy_buff_capacity,
            enemy_effect_values,
            normalize_enemy_scaling_settings,
            plan_enemy_trap_rewards,
        )
        from randomizer.maps.enemy_scaling import (
            enemy_existing_power_grant_plan,
            enemy_existing_power_rule_overrides,
            enemy_power_launch_rewards,
            enemy_weapon_supports_direct_buff,
        )
        from randomizer.maps.base import randomizer_clone_type_id
        from randomizer.maps.clone_builder import player_clone_selection_group
        from randomizer.config.player import DEFAULT_CONFIG
        from randomizer.rewards.arsenal import (
            ARSENAL_MODE,
            arsenal_reward_pool,
            generate_mission_arsenals,
            reward_matches_arsenal,
        )
        from randomizer.ui.config import REWARD_MODES
        from randomizer.missions.catalogue import (
            MISSION_BUILD_CLASSIFICATIONS,
            MISSION_REWARD_CLASS_BY_CODE,
            mission_reward_multiplier,
        )
        mission_reward_multipliers_valid = bool(
            set(MISSION_REWARD_CLASS_BY_CODE)
            == set(MISSION_BUILD_CLASSIFICATIONS)
            and len(MISSION_REWARD_CLASS_BY_CODE) == 127
            and mission_reward_multiplier('AREDDAWN') == 1
            and mission_reward_multiplier('ASIREN') == 2
            and mission_reward_multiplier('APANIC') == 3
            and mission_reward_multiplier('FNOBODY') == 2
            and mission_reward_multiplier('FBEYOND') == 2
            and mission_reward_multiplier('FPOINT') == 3
            and mission_reward_multiplier('FREMNANT') == 3
            and mission_reward_multiplier('ADEMON') == 2
            and mission_reward_multiplier('FCAPSULE') == 2
            and mission_reward_multiplier('A01') == 1
            and mission_reward_multiplier('A11') == 3
            and mission_reward_multiplier('ACO1') == 2
            and mission_reward_multiplier('S01') == 1
            and mission_reward_multiplier('S11') == 3
            and mission_reward_multiplier('SCO1') == 2
        )
        player_clone_selection_groups = {
            'default_source_id': player_clone_selection_group('E2', {}) == 'E2',
            'authored_group': player_clone_selection_group(
                'E2', {'GroupAs': 'Conscripts'}
            ) == 'Conscripts',
            'case_insensitive_key': player_clone_selection_group(
                'E2', {'groupas': 'InfantryGroup'}
            ) == 'InfantryGroup',
        }
        enemy_settings = normalize_enemy_scaling_settings({
            'stack_model_version': 4,
            'maximum_total_buffs': 7,
        })
        enemy_traps = plan_enemy_trap_rewards(
            'MO-SELF-CHECK', enemy_settings, REWARD_POOL
        )
        enemy_traps_repeat = plan_enemy_trap_rewards(
            'MO-SELF-CHECK', enemy_settings, REWARD_POOL
        )
        armor_values = [
            enemy_effect_values(
                next(
                    definition for definition in ENEMY_BUFF_DEFINITIONS
                    if definition['id'] == 'infantry_armor'
                ),
                stacks,
            )
            for stacks in range(1, 6)
        ]
        production_values = [
            enemy_effect_values(
                next(
                    definition for definition in ENEMY_BUFF_DEFINITIONS
                    if definition['id'] == 'vehicle_production'
                ),
                stacks,
            )
            for stacks in range(1, 6)
        ]
        armor_only_settings = normalize_enemy_scaling_settings({
            'stack_model_version': 4,
            'maximum_total_buffs': 999,
            'allowed_buff_ids': ['infantry_armor'],
            'caps': {'infantry_armor': 5},
        })
        armor_only_traps = plan_enemy_trap_rewards(
            'MO-AI-CAP-CHECK',
            armor_only_settings,
            REWARD_POOL,
        )
        enemy_power_rewards = enemy_power_launch_rewards(
            reward for reward in REWARD_POOL
            if reward.get('enemy_reward')
            and reward.get('enemy_effect') == 'power'
        )
        enemy_unit_rewards = [
            reward for reward in REWARD_POOL
            if reward.get('enemy_reward')
            and reward.get('enemy_effect') == 'unit'
        ]
        native_enemy_power_rewards = [
            reward for reward in REWARD_POOL
            if reward.get('enemy_reward')
            and reward.get('enemy_effect') == 'power'
        ]
        native_enemy_power_ids = (
            'LightningStormSpecial',
            'NukeSpecial',
            'PsychicDominatorSpecial',
            'GreatTempestSpecial',
        )
        (
            existing_enemy_power_actions,
            existing_enemy_power_names,
            missing_existing_enemy_powers,
        ) = enemy_existing_power_grant_plan(
            ['[SuperWeaponTypes]'],
            native_enemy_power_rewards,
            native_enemy_power_ids,
        )
        existing_enemy_power_rules = enemy_existing_power_rule_overrides(
            native_enemy_power_rewards,
            existing_enemy_power_names,
        )
        capped_total_settings = normalize_enemy_scaling_settings({
            'stack_model_version': 4,
            'maximum_total_buffs': 3,
        })
        capped_total_traps = plan_enemy_trap_rewards(
            'MO-AI-TOTAL-CAP-CHECK',
            capped_total_settings,
            REWARD_POOL,
        )
        enemy_paratroopers = [
            definition for definition in ENEMY_BUFF_DEFINITIONS
            if definition.get('id') == 'ai_paratroopers'
        ]
        enemy_scaling_contract_valid = bool(
            len(ENEMY_BUFF_DEFINITIONS) == 48
            and tuple(
                group['label'] for group in ENEMY_BUFF_GROUP_DEFINITIONS
            ) == (
                'AI unit stat bonuses',
                'AI weapon bonuses',
                'AI production-speed bonuses',
                'AI support powers',
                'AI superweapons',
            )
            and len(enemy_traps) == 7
            and enemy_traps == enemy_traps_repeat
            and all(definition['maximum_stacks'] in {1, 5}
                    for definition in ENEMY_BUFF_DEFINITIONS)
            and [value['displayed_percentage'] for value in armor_values]
            == [11, 22, 33, 44, 55]
            and [
                value['displayed_percentage']
                for value in production_values
            ] == [10, 20, 30, 40, 50]
            and enemy_buff_capacity(armor_only_settings) == 5
            and armor_only_settings['maximum_total_buffs'] == 5
            and len(armor_only_traps) == 5
            and len(capped_total_traps) == 3
            and len(enemy_paratroopers) == 1
            and enemy_paratroopers[0].get('use_existing_power') is False
            and enemy_paratroopers[0].get('superweapon') == 'ParaDropSpecial'
            and len(enemy_unit_rewards) == 33
            and all(
                reward.get('tier') in {1, 2, 3}
                and reward.get('unit_buff_type')
                and not reward.get('superweapon')
                for reward in enemy_unit_rewards
            )
            and existing_enemy_power_actions == [
                ['34', '0', str(index), '0', '0', '0', '0', 'A']
                for index in range(4)
            ]
            and existing_enemy_power_names == list(native_enemy_power_ids)
            and not missing_existing_enemy_powers
            and all(
                existing_enemy_power_rules[power_id]['SW.AllowAI'] == 'yes'
                and existing_enemy_power_rules[power_id]['SW.AITargeting']
                not in {'', 'None'}
                for power_id in native_enemy_power_ids
            )
            and all(
                reward.get('enemy_reward')
                for reward in enemy_traps
            )
            and enemy_weapon_supports_direct_buff({'Damage': '10'})
            and not enemy_weapon_supports_direct_buff({'Spawner': 'yes'})
            and not enemy_weapon_supports_direct_buff({'spawner': 'TRUE'})
            and {
                reward.get('enemy_effect_id')
                for reward in enemy_power_rewards
            } == {
                'ai_paratroopers',
                'ai_bloodhounds',
                'ai_moon_reinforcements',
            }
            and all(
                reward.get('kind') == 'superweapon'
                and reward.get('enemy_reward') is False
                and reward.get('superweapon_rules', {}).get(
                    'SW.AllowAI'
                ) == 'yes'
                and reward.get('superweapon_rules', {}).get(
                    'SW.AllowPlayer'
                ) == 'no'
                and reward.get('superweapon_rules', {}).get(
                    'SW.UseAITargeting'
                ) == 'yes'
                and reward.get('superweapon_rules', {}).get(
                    'SW.InitialReady'
                ) == 'yes'
                and reward.get('superweapon_rules', {}).get(
                    'SW.AITargeting'
                ) == 'ParaDrop'
                and reward.get('superweapon_rules', {}).get(
                    'SW.AITargeting.Constraints'
                ) == 'none'
                and reward.get('enemy_faction_families') == (
                    'allies', 'soviets', 'epsilon', 'foehn'
                )
                and reward.get('superweapon_recharge_multiplier') == 2
                and len(reward.get('superweapon_clone', '')) <= 21
                for reward in enemy_power_rewards
            )
            and len(randomizer_clone_type_id(
                'AmericanParaDropSpecial'
            )) <= 21
            and len(randomizer_clone_type_id(
                'AnExtremelyLongGeneratedSupportPowerSpecial'
            )) <= 21
        )
        arsenal_settings = DEFAULT_CONFIG['generation']
        arsenal_codes = ('AREDDAWN', 'AEAGLESFLY')
        arsenal_first = generate_mission_arsenals(
            'MO-SELF-CHECK',
            arsenal_codes,
            arsenal_settings,
            arsenal_settings.get('arsenal'),
        )
        arsenal_second = generate_mission_arsenals(
            'MO-SELF-CHECK',
            arsenal_codes,
            arsenal_settings,
            arsenal_settings.get('arsenal'),
        )
        arsenal_contract_valid = bool(
            ARSENAL_MODE in REWARD_MODES
            and arsenal_first == arsenal_second
            and all(
                arsenal.get('seed_fixed')
                and arsenal.get('units')
                and not any(
                    set(entry.get('equivalent_ids', ())).intersection(
                        other.get('equivalent_ids', ())
                    )
                    for index, entry in enumerate(arsenal.get('units', ()))
                    for other in arsenal.get('units', ())[index + 1:]
                )
                and all(
                    reward.get('kind') == 'buff'
                    and reward_matches_arsenal(reward, arsenal)
                    for reward in arsenal_reward_pool(REWARD_POOL, arsenal)
                )
                for arsenal in arsenal_first.values()
            )
        )
        all_buff_caps_valid = bool(
            any(reward.get('kind') == 'buff' for reward in REWARD_POOL)
            and all(
                buff_stack_limit(reward) is not None
                for reward in REWARD_POOL
                if reward.get('kind') == 'buff'
            )
        )
        from randomizer.rewards.rules import (
            buffs_with_unlocked_access,
            expand_equivalent_role_buffs,
            unlocked_reward_tech_ids,
        )
        scud_access = canonical_reward({'name': 'Scud Launcher Access'})
        scud_buff = canonical_reward({
            'name': 'Scud Launcher Reinforced Frames I'
        })
        scoped_scud_rewards = expand_equivalent_role_buffs(
            [scud_access, scud_buff],
            enabled=True,
            allowed_unit_ids={'V3', 'VCARR'},
        )
        active_scud_rewards = buffs_with_unlocked_access(
            scoped_scud_rewards,
            additional_unlocked_tech_ids={'V3', 'VCARR'},
            share_basic_equivalent_buffs=False,
        )
        equivalent_buff_access_isolation_valid = bool(
            unlocked_reward_tech_ids(scoped_scud_rewards) == {'V3'}
            and {
                reward.get('unit')
                for reward in active_scud_rewards
                if reward.get('kind') == 'buff'
            } == {'V3', 'VCARR'}
            and any(
                reward.get('unit') == 'VCARR'
                and reward.get('_runtime_canonical') is True
                for reward in scoped_scud_rewards
            )
            and not any(
                reward.get('unit') in {'TELE', 'TARCHIA'}
                for reward in scoped_scud_rewards
            )
        )
        shin_access = [
            reward for reward in REWARD_POOL
            if reward.get('name') == 'Shin Tsurugi Decimator Access'
        ]
        shin_allied_tech_valid = bool(
            len(shin_access) == 1
            and shin_access[0].get('factions') == ['Allies']
            and shin_access[0].get('rules', {}).get('SHINBOT', {}).get(
                'Prerequisite'
            ) == 'GAWEAP'
            and BUFF_TARGETS.get('SHINBOT', {}).get('factions') == ['Allies']
            and all(
                reward.get('factions') == ['Allies']
                for reward in REWARD_POOL
                if reward.get('unit') == 'SHINBOT'
            )
        )
        from randomizer.missions.access import access_catalog
        from randomizer.missions.tier_one import TIER_ONE_DEFENSE_UNITS
        runtime_access_catalog = access_catalog()
        indexed_access_ids = {
            str(entry[0]).upper() for entry in runtime_access_catalog
        }
        tier_one_defense_ids = {
            unit_id
            for family_ids in TIER_ONE_DEFENSE_UNITS.values()
            for unit_id in family_ids
        }
        access_catalog_valid = bool(
            runtime_access_catalog
            and tier_one_defense_ids.issubset(indexed_access_ids)
        )
        from randomizer.ui.cameos import installed_rules_registry
        _installed_types, installed_sections = installed_rules_registry()
        installed_by_upper = {
            str(section).upper(): {
                str(key).lower(): value for key, value in values.items()
            }
            for section, values in installed_sections.items()
        }
        engineering_configs = [
            config
            for config in AID_POWER_MAP_CONFIGS
            if config.get('superweapon') == 'MOREngineeringTeamSpecial'
        ]
        engineering_rewards = [
            reward
            for reward in AID_POWER_UNLOCK_REWARDS
            if reward.get('name') == 'Engineering Team Power'
        ]
        engineering_buffs = {
            reward.get('power_buff_type')
            for reward in POWER_BUFF_REWARDS
            if reward.get('power_name') == 'Engineering Team Power'
        }
        engineering_team_valid = bool(
            len(engineering_configs) == 1
            and len(engineering_rewards) == 1
            and engineering_configs[0].get('source_superweapon')
            == 'AmericanParaDropSpecial'
            and 'AMERICANPARADROPSPECIAL' in installed_by_upper
            and engineering_configs[0].get('values', {}).get(
                'ParaDrop.Types'
            ) == 'SENGINEER'
            and engineering_configs[0].get('values', {}).get(
                'ParaDrop.Num'
            ) == '3'
            and engineering_rewards[0].get(
                'superweapon_ignore_foreign_tech_gate'
            ) is True
            and 'ParaDrop.Aircraft'
            not in engineering_configs[0].get('values', {})
            and not engineering_configs[0].get('preserve_prerequisites')
            and engineering_buffs == {'recharge', 'cost', 'payload'}
        )
        deploy_clone_link_gaps = []
        for unit_id, values in installed_by_upper.items():
            if unit_id not in BUFF_TARGETS:
                continue
            for key in ('deploysinto', 'undeploysinto'):
                target_id = str(values.get(key, '') or '').upper()
                if target_id in {'', 'NONE', '<NONE>'}:
                    continue
                if target_id not in linked_buff_variant_ids(unit_id):
                    deploy_clone_link_gaps.append(
                        f'{unit_id}.{key}={target_id}'
                    )
        moon_configs = [
            config
            for config in AID_POWER_MAP_CONFIGS
            if config.get('superweapon') == 'KnightfallSpawn'
        ]
        moon_initial_cooldown_valid = bool(
            len(moon_configs) == 1
            and str(
                moon_configs[0].get('values', {}).get('SW.InitialReady', '')
            ).lower() == 'no'
        )
        zephyr_configs = [
            config
            for config in AID_POWER_MAP_CONFIGS
            if config.get('superweapon') == 'ZephyrBeaconSpecial'
        ]
        zephyr_enabled_valid = bool(
            len(zephyr_configs) == 1
            and not zephyr_configs[0].get('disabled')
            and any(
                reward.get('superweapon') == 'ZephyrBeaconSpecial'
                for reward in AID_POWER_UNLOCK_REWARDS
            )
            and {
                reward.get('power_buff_type')
                for reward in POWER_BUFF_REWARDS
                if reward.get('superweapon') == 'ZephyrBeaconSpecial'
            } == {'recharge', 'cost'}
        )
        portable_power_ids = {
            'BackwarpSpecial',
            'NuclearPathSpecial',
            'GearChangeSpecial',
            'PsychicFlashSpecial',
            'BlackoutMissileSpecial',
            'NanochargeSpecial',
        }
        portable_rewards = {
            reward.get('superweapon'): reward
            for reward in AID_POWER_UNLOCK_REWARDS
            if reward.get('superweapon') in portable_power_ids
        }
        portable_configs = {
            config.get('superweapon'): config
            for config in AID_POWER_MAP_CONFIGS
            if config.get('superweapon') in portable_power_ids
        }
        cleared_power_gates = {
            'IsPowered': 'false',
            'SW.RequiredHouses': '',
            'SW.ForbiddenHouses': '',
            'SW.AuxBuildings': '',
            'SW.NegBuildings': '',
            'SW.Inhibitors': '',
        }
        portable_powers_valid = bool(
            set(portable_rewards) == portable_power_ids
            and set(portable_configs) == portable_power_ids
            and all(
                all(
                    str(config.get('values', {}).get(key, '')).lower()
                    == expected
                    for key, expected in cleared_power_gates.items()
                )
                for config in portable_configs.values()
            )
            and set(
                portable_rewards['PsychicFlashSpecial'].get(
                    'requires_any_tech_ids', ()
                )
            ) == {'YARAIL', 'YAHADE'}
            and portable_configs['PsychicFlashSpecial'].get(
                'player_clone_reference_fields', {}
            ).get('Battery.Overpower') == ['YARAIL', 'YAHADE']
            and portable_configs['NanochargeSpecial'].get(
                'player_clone_reference_fields', {}
            ).get('SW.Designators') == ['LEVI', 'PROME']
            and set(
                portable_configs['NanochargeSpecial'].get(
                    'player_clone_value_overrides', {}
                )
            ) == {'LEVI', 'PROME'}
            and not any(
                reward.get('superweapon')
                in {'GoldenWindSpecial', 'BlasticadeSpecial'}
                for reward in AID_POWER_UNLOCK_REWARDS
            )
        )
        geneburst_config = next(
            (
                config for config in AID_POWER_MAP_CONFIGS
                if config.get('superweapon') == 'MutationSpecial'
            ),
            {},
        )
        geneburst_clones = geneburst_config.get('techno_clones', {})
        geneburst_power_valid = bool(
            geneburst_config.get('ignore_foreign_tech_gate') is True
            and geneburst_config.get('values', {}).get('EMPulse.Cannons')
            == 'MORGeneburstProvider'
            and geneburst_config.get('values', {}).get('SW.AuxBuildings') == ''
            and geneburst_config.get('values', {}).get('SW.RangeMaximum') == '-1'
            and set(geneburst_clones) == {
                'GeneburstProvider', 'GeneburstWeapon',
                'GeneburstProjectile', 'GeneburstWarhead',
            }
            and geneburst_clones.get('GeneburstProvider', {}).get(
                'static_startup'
            ) is True
            and geneburst_clones.get('GeneburstProvider', {}).get(
                'values', {}
            ).get('EMPulseCannon') == 'yes'
            and geneburst_clones.get('GeneburstWeapon', {}).get(
                'values', {}
            ).get('Warhead') == 'MORGeneburstWH'
            and geneburst_clones.get('GeneburstWeapon', {}).get(
                'values', {}
            ).get('Range') == '384'
        )
        from randomizer.application import (
            advanced_settings as advanced_settings_module,
            app as application_module,
            reward_controller as reward_controller_module,
            starting_unlocks as starting_unlocks_module,
            state_controller as state_controller_module,
        )
        required_runtime_symbols = {
            application_module: (
                'MAIN_REWARD_WEIGHT_TYPES',
                'POWER_BUFF_WEIGHT_TYPES',
                'UNIT_BUFF_WEIGHT_TYPES',
                'normalize_reward_weights',
            ),
            advanced_settings_module: (
                'DEFAULT_REWARD_WEIGHT',
                'MAIN_REWARD_WEIGHT_TYPES',
                'POWER_BUFF_WEIGHT_TYPES',
                'UNIT_BUFF_WEIGHT_TYPES',
                'clamp_reward_weight',
            ),
            reward_controller_module: (
                'normalize_reward_weights',
                'reward_selection_weight',
            ),
            state_controller_module: (
                'normalize_arsenal_settings',
                'MAIN_REWARD_WEIGHT_TYPES',
                'POWER_BUFF_WEIGHT_TYPES',
                'UNIT_BUFF_WEIGHT_TYPES',
                'clamp_reward_weight',
                'normalize_reward_weights',
                'normalize_starting_reward_count',
                'normalize_starting_reward_types',
                'normalize_starting_unlock_reward_names',
                'read_portable_settings',
                'write_portable_settings',
            ),
            starting_unlocks_module: (
                'STARTING_UNLOCK_CATEGORY_LABELS',
                'normalize_starting_unlock_reward_names',
            ),
        }
        missing_runtime_symbols = [
            f'{module.__name__}.{name}'
            for module, names in required_runtime_symbols.items()
            for name in names
            if not hasattr(module, name)
        ]
        starting_unlock_controller = (
            starting_unlocks_module.StartingUnlocksController()
        )
        starting_unlock_entries = starting_unlock_controller.starting_unlock_entries()
        starting_unlock_catalogue_valid = bool(
            starting_unlock_entries
            and all(
                starting_unlock_controller.reward_is_permanent_starting_unlock(
                    entry['reward']
                )
                for entry in starting_unlock_entries
            )
            and not any(
                entry['reward'].get('kind') == 'buff'
                for entry in starting_unlock_entries
            )
        )
        state_stub = object.__new__(state_controller_module.StateController)
        state_stub.config = {'generation': {}}
        runtime_reward_settings = (
            state_controller_module.StateController.config_reward_settings(
                state_stub
            )
        )
        reward_weight_connections_valid = bool(
            not missing_runtime_symbols
            and runtime_reward_settings.get('reward_weights')
            and runtime_reward_settings.get('starting_reward_count') == 0
            and set(runtime_reward_settings.get('starting_reward_types', ()))
            == {
                'access', 'superweapon',
                'secondary_superweapon', 'aid_power',
            }
            and runtime_reward_settings.get('starting_unlock_rewards') == []
        )
        eva_voice_profiles = validate_eva_voice_profiles(
            EVA_VOICE_TAGS,
            EVA_APPEARANCE_PROFILES,
        )
        checks = {
            'app_version': APP_VERSION,
            'game_root': str(GAME_ROOT),
            'runtime_data_writable': APP_DIR.exists(),
            'syringe_exists': GAME_LAUNCHER_EXE.exists(),
            'gamemd_exists': GAME_EXE.exists(),
            'map_renderer_exists': MAP_RENDERER_DIR.exists(),
            'window_icon_exists': WINDOW_ICON_PATH.is_file(),
            'abrams_cameo_extracted': 'ABRM' in cameos,
            'abrams_cameo_path': str(cameos.get('ABRM', '')),
            'lightning_storm_cameo_extracted': 'LIGHTNINGSTORMSPECIAL' in power_cameos,
            'lightning_storm_cameo_path': str(power_cameos.get('LIGHTNINGSTORMSPECIAL', '')),
            'static_configs_valid': len(static_config_paths) == len(REQUIRED_STATIC_CONFIGS),
            'shop_domain_valid': shop_domain['valid'],
            'shop_domain': shop_domain,
            'archipelago_client_contract_valid': (
                archipelago_client_contract_valid
            ),
            'archipelago_websockets_version': websockets.__version__,
            'randomizer_unit_roster_valid': (
                unit_roster['files'] == len(ROSTER_FILENAMES)
                and unit_roster['types'] > 0
            ),
            'randomizer_unit_roster_paths': unit_roster['paths'],
            'drakuv_contracts_valid': bool(
                drakuv_contracts['clone_id'] == 'MORPRAVA'
                and drakuv_contracts['build_time_multiplier'] == '1'
                and drakuv_contracts['trainable'].lower() == 'yes'
                and drakuv_contracts['image'].upper() == 'RAVA'
                and drakuv_contracts['access_entries'] == 1
                and drakuv_contracts['power_entries'] == 1
                and drakuv_contracts['clone_registrations'] == 1
                and not drakuv_contracts['duplicate_reward_names']
            ),
            'drakuv_contracts': drakuv_contracts,
            'unit_buff_applications_valid': bool(
                unit_buff_applications['all_change_generated_rules']
            ),
            'unit_buff_applications': unit_buff_applications,
            'limited_hero_build_limits_valid': bool(
                limited_hero_limits['types']
                == limited_hero_limits['command_capacity_rewards']
                and 'SHINBOT' in limited_hero_limits['unit_ids']
            ),
            'limited_hero_build_limits': limited_hero_limits,
            'special_roster_contracts_valid': bool(
                special_roster['space_commando_theater_gate_removed']
                and special_roster['boomer_brute_excluded']
                and special_roster['paradox_source_id'] == 'STARDUSTB'
                and special_roster['paradox_ai_alias_excluded']
                and all(
                    count == 1
                    for count in special_roster['access_counts'].values()
                )
            ),
            'special_roster_contracts': special_roster,
            'hidden_passenger_payloads_valid': bool(
                set(hidden_passenger_payloads) == {'STHOR', 'SALA'}
                and all(
                    details['payload_size'] == details['capacity']
                    for details in hidden_passenger_payloads.values()
                )
            ),
            'hidden_passenger_payloads': hidden_passenger_payloads,
            'reviewed_vehicle_identities_valid': True,
            'reviewed_vehicle_identities': reviewed_vehicle_identities,
            'randomizer_unit_health_valid': bool(
                unit_health['types'] == unit_roster['types']
                and unit_health['minimum_strength'] >= 2
            ),
            'randomizer_unit_health': unit_health,
            'special_reward_build_times_valid': bool(
                special_build_times['types']
                and special_build_times['max_effective_multiplier']
                <= MAX_PLAYER_BUILD_TIME_MULTIPLIER
            ),
            'special_reward_build_times': special_build_times,
            'moon_reinforcements_initial_cooldown_valid': (
                moon_initial_cooldown_valid
            ),
            'zephyr_bombardment_enabled_valid': zephyr_enabled_valid,
            'portable_aid_powers_valid': portable_powers_valid,
            'geneburst_power_valid': geneburst_power_valid,
            'engineering_team_power_valid': engineering_team_valid,
            'all_buff_caps_valid': all_buff_caps_valid,
            'equivalent_buff_access_isolation_valid': (
                equivalent_buff_access_isolation_valid
            ),
            'shin_allied_tech_valid': shin_allied_tech_valid,
            'access_catalog_valid': access_catalog_valid,
            'access_catalog_entries': len(runtime_access_catalog),
            'deploy_clone_links_valid': not deploy_clone_link_gaps,
            'deploy_clone_link_gaps': deploy_clone_link_gaps,
            'player_clone_selection_groups_valid': all(
                player_clone_selection_groups.values()
            ),
            'player_clone_selection_groups': player_clone_selection_groups,
            'transport_buff_eligibility_valid': bool(
                transport_buffs['gunner_ids']
                and set(
                    transport_buffs[
                        'hidden_weapon_passenger_capacity_excluded'
                    ]
                ) == {'SALA', 'STHOR'}
                and transport_buffs['stallion_capacity_enabled']
                and transport_buffs['stallion_open_topped_excluded']
                and transport_buffs['engineer_clone_identity_ids']
                and transport_buffs['rhino_ammo_migrated_to_reload']
            ),
            'transport_buff_eligibility': transport_buffs,
            'house_wide_buff_policy_valid': bool(
                house_wide_buffs['house_wide_scopes']
                == [['All', 'production']]
                and house_wide_buffs['all_production_direct_results']
            ),
            'house_wide_buff_policy': house_wide_buffs,
            'reprocessor_bounty_support_valid': bool(
                reprocessor_bounty['runtime_enablers']
                and all(
                    reprocessor_bounty['representative_results'].values()
                )
            ),
            'reprocessor_bounty_support': reprocessor_bounty,
            'ore_purifier_miner_docks_valid': bool(
                ore_purifier_docks['miner_ids']
                and not ore_purifier_docks['static_missing']
                and not ore_purifier_docks['runtime_missing']
                and not ore_purifier_docks['runtime_issues']
            ),
            'ore_purifier_miner_docks': ore_purifier_docks,
            'original_refinery_contract_valid': bool(
                len(player_refineries['pairs']) == 4
                and not player_refineries['issues']
            ),
            'original_refinery_contract': player_refineries,
            'static_config_paths': [str(path) for path in static_config_paths],
            'application_imported': True,
            'starting_unlock_catalogue_valid': starting_unlock_catalogue_valid,
            'reward_weight_connections_valid': (
                reward_weight_connections_valid
            ),
            'randomizer_arsenal_contract_valid': arsenal_contract_valid,
            'mission_reward_multipliers_valid': (
                mission_reward_multipliers_valid
            ),
            'enemy_scaling_contract_valid': enemy_scaling_contract_valid,
            'eva_voice_profiles_valid': eva_voice_profiles['valid'],
            'eva_voice_profiles': eva_voice_profiles['profiles'],
            'missing_runtime_symbols': missing_runtime_symbols,
            'diagnostic_log': str(LAUNCHER_LOG),
            'deterministic_seed_rng_works': 0 <= random.Random('MO-SELF-CHECK').random() < 1,
        }
        checks['passed'] = all(
            checks[key]
            for key in (
                'runtime_data_writable',
                'syringe_exists',
                'gamemd_exists',
                'map_renderer_exists',
                'window_icon_exists',
                'abrams_cameo_extracted',
                'lightning_storm_cameo_extracted',
                'static_configs_valid',
                'shop_domain_valid',
                'archipelago_client_contract_valid',
                'randomizer_unit_roster_valid',
                'drakuv_contracts_valid',
                'unit_buff_applications_valid',
                'limited_hero_build_limits_valid',
                'special_roster_contracts_valid',
                'hidden_passenger_payloads_valid',
                'reviewed_vehicle_identities_valid',
                'randomizer_unit_health_valid',
                'special_reward_build_times_valid',
                'moon_reinforcements_initial_cooldown_valid',
                'zephyr_bombardment_enabled_valid',
                'portable_aid_powers_valid',
                'geneburst_power_valid',
                'engineering_team_power_valid',
                'all_buff_caps_valid',
                'equivalent_buff_access_isolation_valid',
                'shin_allied_tech_valid',
                'access_catalog_valid',
                'deploy_clone_links_valid',
                'player_clone_selection_groups_valid',
                'transport_buff_eligibility_valid',
                'house_wide_buff_policy_valid',
                'reprocessor_bounty_support_valid',
                'ore_purifier_miner_docks_valid',
                'original_refinery_contract_valid',
                'application_imported',
                'starting_unlock_catalogue_valid',
                'reward_weight_connections_valid',
                'randomizer_arsenal_contract_valid',
                'mission_reward_multipliers_valid',
                'enemy_scaling_contract_valid',
                'eva_voice_profiles_valid',
                'deterministic_seed_rng_works',
            )
        )
        report_path.write_text(json.dumps(checks, indent=2), encoding='utf-8')
        log_event('self_check_finished', **checks)
        return 0 if checks['passed'] else 1
    except Exception:
        detail = traceback.format_exc()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps({'passed': False, 'traceback': detail}, indent=2), encoding='utf-8')
        log_event('self_check_failed', traceback=detail)
        return 1


if __name__ == '__main__':
    if '--self-check' in sys.argv:
        raise SystemExit(run_self_check())
    raise SystemExit(run_launcher())
