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
        special_build_times = validate_special_reward_build_times()
        transport_buffs = validate_transport_buff_eligibility()
        from randomizer.maps.special_buildings import (
            validate_reprocessor_bounty_support,
        )
        reprocessor_bounty = validate_reprocessor_bounty_support()
        from randomizer.rewards.catalogue import AID_POWER_MAP_CONFIGS
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
            'transport_buff_eligibility_valid': bool(
                transport_buffs['gunner_ids']
                and transport_buffs['stallion_capacity_enabled']
                and transport_buffs['stallion_open_topped_excluded']
            ),
            'transport_buff_eligibility': transport_buffs,
            'reprocessor_bounty_support_valid': bool(
                reprocessor_bounty['runtime_enablers']
                and all(
                    reprocessor_bounty['representative_results'].values()
                )
            ),
            'reprocessor_bounty_support': reprocessor_bounty,
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
                'special_reward_build_times_valid',
                'moon_reinforcements_initial_cooldown_valid',
                'zephyr_bombardment_disabled_valid',
                'transport_buff_eligibility_valid',
                'reprocessor_bounty_support_valid',
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
