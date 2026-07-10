"""Shared filesystem paths for the Mental Omega randomizer launcher."""
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
GAME_ROOT = APP_DIR.parent
CLIENT_EXE = GAME_ROOT / 'MentalOmegaClient.exe'
GAME_LAUNCHER_EXE = GAME_ROOT / 'Syringe.exe'
GAME_EXE = GAME_ROOT / 'gamemd.exe'
SPAWN_INI = GAME_ROOT / 'spawn.ini'
OPTIONS_INI = GAME_ROOT / 'RA2MO.ini'
YR_OPTIONS_INI = GAME_ROOT / 'RA2MD.INI'
DEBUG_LOG = GAME_ROOT / 'debug' / 'debug.log'
RULESMO_INI = GAME_ROOT / 'rulesmo.ini'
DISABLED_RULESMO_INI = GAME_ROOT / 'rulesmo.ini.randomizer-disabled'
BATTLE_CLIENT_INI = GAME_ROOT / 'INI' / 'BattleClient.ini'
NO_BASES_INI = GAME_ROOT / 'INI' / 'Map Code' / 'No Bases.ini'
STATE_PATH = APP_DIR / 'randomizer_state.json'
BACKUP_DIR = APP_DIR / 'backups'
EXTRACTED_MAP_DIR = APP_DIR / 'extracted_maps'
GENERATED_MAP_DIR = APP_DIR / 'generated_maps'
CAMEO_CACHE_DIR = APP_DIR / 'cameo_cache'
MAP_RENDERER_DIR = GAME_ROOT / 'Map Renderer'
