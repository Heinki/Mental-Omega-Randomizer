"""Entry point for source runs and the packaged launcher."""

import json
import random
import sys
import traceback

from randomizer_cameos import ensure_superweapon_cameos, ensure_unit_cameos
from randomizer_diagnostics import event as log_event
from randomizer_paths import (
    APP_DIR,
    GAME_EXE,
    GAME_LAUNCHER_EXE,
    GAME_ROOT,
    LAUNCHER_LOG,
    MAP_RENDERER_DIR,
    WINDOW_ICON_PATH,
)
from randomizer_version import APP_VERSION
from randomizer_static_config import REQUIRED_STATIC_CONFIGS, validate_static_configs


def run_launcher():
    """Load config-dependent application modules with visible startup errors."""
    try:
        from randomizer_app import main
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
        __import__('randomizer_app')
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
            'static_config_paths': [str(path) for path in static_config_paths],
            'application_imported': True,
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
                'application_imported',
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
