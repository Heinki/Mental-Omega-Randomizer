"""UI choices and palettes for the launcher.

Keeping presentation data here prevents gameplay/orchestration code from
becoming the place contributors must edit for labels, colors, or themes.
"""

from randomizer_static_config import load_static_config


_UI_CONFIG = load_static_config('ui.json')

DIFFICULTIES = [tuple(item) for item in _UI_CONFIG['difficulties']]
GAME_SPEEDS = [tuple(item) for item in _UI_CONFIG['game_speeds']]
CAMPAIGN_FILTERS = list(_UI_CONFIG['campaign_filters'])
REWARD_MODES = list(_UI_CONFIG['reward_modes'])
PROGRESSION_MODES = list(_UI_CONFIG['progression_modes'])
DEFAULT_PROGRESSION_MODE = str(_UI_CONFIG['default_progression_mode'])

FACTION_TILE_COLORS = dict(_UI_CONFIG['faction_tile_colors'])
LIGHT_UI_PALETTE = dict(_UI_CONFIG['light_palette'])
DARK_UI_PALETTE = dict(_UI_CONFIG['dark_palette'])
