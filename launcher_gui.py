"""Entry point for source runs and the packaged launcher."""

import json
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
from randomizer.rewards.roster import (
    MAX_PLAYER_BUILD_TIME_MULTIPLIER,
    ROSTER_FILENAMES,
    validate_randomizer_unit_health,
    validate_randomizer_unit_roster,
    validate_special_reward_build_times,
    validate_transport_buff_eligibility,
)


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
        unit_roster = validate_randomizer_unit_roster()
        unit_health = validate_randomizer_unit_health()
        special_build_times = validate_special_reward_build_times()
        transport_buffs = validate_transport_buff_eligibility()
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
            REWARD_POOL,
            buff_stack_limit,
            linked_buff_variant_ids,
        )
        all_buff_caps_valid = bool(
            any(reward.get('kind') == 'buff' for reward in REWARD_POOL)
            and all(
                buff_stack_limit(reward) is not None
                for reward in REWARD_POOL
                if reward.get('kind') == 'buff'
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
        zephyr_disabled_valid = bool(
            len(zephyr_configs) == 1
            and zephyr_configs[0].get('disabled') is True
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
        from randomizer.application import (
            advanced_settings as advanced_settings_module,
            app as application_module,
            reward_controller as reward_controller_module,
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
                'MAIN_REWARD_WEIGHT_TYPES',
                'POWER_BUFF_WEIGHT_TYPES',
                'UNIT_BUFF_WEIGHT_TYPES',
                'clamp_reward_weight',
                'normalize_reward_weights',
                'read_portable_settings',
                'write_portable_settings',
            ),
        }
        missing_runtime_symbols = [
            f'{module.__name__}.{name}'
            for module, names in required_runtime_symbols.items()
            for name in names
            if not hasattr(module, name)
        ]
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
            'randomizer_unit_roster_valid': (
                unit_roster['files'] == len(ROSTER_FILENAMES)
                and unit_roster['types'] > 0
            ),
            'randomizer_unit_roster_paths': unit_roster['paths'],
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
            'zephyr_bombardment_disabled_valid': zephyr_disabled_valid,
            'portable_aid_powers_valid': portable_powers_valid,
            'all_buff_caps_valid': all_buff_caps_valid,
            'access_catalog_valid': access_catalog_valid,
            'access_catalog_entries': len(runtime_access_catalog),
            'deploy_clone_links_valid': not deploy_clone_link_gaps,
            'deploy_clone_link_gaps': deploy_clone_link_gaps,
            'transport_buff_eligibility_valid': bool(
                transport_buffs['gunner_ids']
                and transport_buffs['stallion_capacity_enabled']
                and transport_buffs['stallion_open_topped_excluded']
                and transport_buffs['engineer_clone_identity_ids']
                and transport_buffs['rhino_ammo_migrated_to_reload']
            ),
            'transport_buff_eligibility': transport_buffs,
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
            'reward_weight_connections_valid': (
                reward_weight_connections_valid
            ),
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
                'randomizer_unit_roster_valid',
                'randomizer_unit_health_valid',
                'special_reward_build_times_valid',
                'moon_reinforcements_initial_cooldown_valid',
                'zephyr_bombardment_disabled_valid',
                'portable_aid_powers_valid',
                'all_buff_caps_valid',
                'access_catalog_valid',
                'deploy_clone_links_valid',
                'transport_buff_eligibility_valid',
                'reprocessor_bounty_support_valid',
                'ore_purifier_miner_docks_valid',
                'original_refinery_contract_valid',
                'application_imported',
                'reward_weight_connections_valid',
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
