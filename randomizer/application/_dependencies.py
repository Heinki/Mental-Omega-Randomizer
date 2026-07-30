"""Shared imports and constants for launcher controllers."""

import logging
import queue
import random
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback

from randomizer.config.player import CONFIG_PATH, DEFAULT_CONFIG, load_config, save_config
from randomizer.core.storage import atomic_write_json, read_json_object
from randomizer.progression.state import (
    normalize_assistance_units,
    normalize_completed_checks,
    normalize_failure_stacks,
)
from randomizer.rewards.planning import plan_seed_rewards
from randomizer.rewards.weights import (
    DEFAULT_REWARD_WEIGHT,
    MAIN_REWARD_WEIGHT_TYPES,
    POWER_BUFF_WEIGHT_TYPES,
    UNIT_BUFF_WEIGHT_TYPES,
    clamp_reward_weight,
    normalize_reward_weights,
    reward_selection_weight,
)
from randomizer.launch.options import (
    choice_label_from_ini,
    patch_large_ini_key,
    spawn_ini_text,
)
from randomizer.ui.cameos import (
    cameo_extraction_pending,
    ensure_superweapon_cameos,
    ensure_unit_cameos,
    mix_reader_assembly_paths,
    powershell_mix_reader_load_script,
)
from randomizer.core.diagnostics import event as log_event
from randomizer.maps.assets import (
    custom_sidebar_preview,
    deploy_generated_unit_art,
    remove_generated_unit_art,
)
from randomizer.core.version import APP_VERSION
from randomizer.progression.grid import (
    COMPLETED as GRID_COMPLETED,
    LOCKED as GRID_LOCKED,
    UNLOCKED as GRID_UNLOCKED,
    completing_unlocks,
    create_grid,
    grid_opening_mission_count,
    is_complete as is_grid_complete,
    refresh_states as refresh_grid_states,
)
from randomizer.missions.catalogue import (
    FACTION_ORDER,
    FALLBACK_OBJECTIVE_COUNT,
    LATE_FOEHN_MISSION_CODES,
    LOW_LEVEL_MISSION_COUNT,
    NO_BUILD_MISSION_CODES,
    STARTING_UNLOCKED_MISSIONS,
    campaign_mission_counts,
    classic_mission_order,
    filter_missions_by_build_settings,
    normalize_faction,
    parse_missions,
    seed_campaign_limits,
    seed_mission_order,
)
from randomizer.missions.houses import (
    mission_player_production_houses,
)
from randomizer.maps.ini import (
    read_text,
    set_ini_value_lines,
)
from randomizer.rewards.catalogue import (
    ALWAYS_AVAILABLE_TECH_IDS,
    BUFF_TARGETS,
    BUFF_TYPES,
    DEFAULT_REWARDS_PER_CHECK,
    effective_buff_count,
    house_wide_buff_effect_lines,
    house_wide_buff_label,
    house_wide_buff_scope,
    MAX_REWARDS_PER_CHECK,
    POWER_BUFF_TYPES,
    REWARD_POOL,
    SPECIAL_BUILDING_DEFINITIONS,
    buff_effect_lines,
    canonical_reward,
    canonical_rewards,
    check_rewards,
    clamp_int,
    reward_display_name,
    reward_names,
    reward_rule_summary,
    unit_display_label,
    linked_buff_variant_ids,
    unit_role_equivalents,
    valid_choice,
)

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
except ImportError:
    raise ImportError('tkinter is required to run this launcher UI.')


from randomizer.core.paths import (
    BATTLE_CLIENT_INI,
    DEBUG_LOG,
    DISABLED_RULESMO_INI,
    EXTRACTED_MAP_DIR,
    GAME_EXE,
    GAME_LAUNCHER_EXE,
    GAME_ROOT,
    LAUNCHER_LOG,
    OPTIONS_INI,
    RULESMO_INI,
    SPAWN_INI,
    STATE_PATH,
    WINDOW_ICON_PATH,
    YR_OPTIONS_INI,
)
from randomizer.maps.rules import (
    LOCKED_TECH_LEVEL,
    SCRIPTED_TECH_BUILD_LIMIT,
    SCRIPTED_TECH_LOCK_EXCLUSIONS,
    controlled_tech_ids,
    country_family,
    is_generated_hooked_map,
    is_generated_rules_file,
    launch_rules_for_reward,
    mission_assistance_multipliers,
    now_stamp,
    player_house_from_map,
    map_house_records,
)
from randomizer.rewards.rules import tech_ids_for_rewards, unlocked_reward_tech_ids
from randomizer.missions.safety import (
    always_available_transport_rules,
    chaos_earned_access_rules,
    expanded_tier_one_defense_ids,
    expanded_tier_one_unit_ids,
    mission_basic_unit_rules,
    random_chaos_tier_one_unit_ids,
    random_chaos_tier_one_defense_ids,
    single_engineer_rules,
    starting_tier_one_defense_rules,
    starting_tier_one_rules,
    summarize_basic_unit_rules,
    tier_one_defense_ids,
    tier_one_unit_ids,
    tier_one_role_label,
)
from randomizer.maps.pipeline import prepare_hooked_map as prepare_hooked_mission_map
from randomizer.missions.overrides import (
    MISSION_REQUIRED_ACCESS_RULES,
    MISSIONS_WITH_ALL_CONYARD_DEFENSE_ACCESS,
    STANDARD_STARTER_FAMILIES_BY_CAMPAIGN,
)
from randomizer.ui.config import (
    CAMPAIGN_FILTERS,
    DARK_UI_PALETTE,
    DEFAULT_PROGRESSION_MODE,
    DIFFICULTIES,
    EVA_VOICE_CHOICES,
    FACTION_TILE_COLORS,
    GAME_SPEEDS,
    LIGHT_UI_PALETTE,
    PLAYER_COLORS,
    PROGRESSION_MODES,
    REWARDS_PER_CHECK_MAXIMUM_MESSAGE,
    REWARDS_PER_CHECK_MESSAGE_THRESHOLDS,
    REWARD_MODES,
)
from randomizer.ui.builder import create_widgets as build_launcher_widgets
from randomizer.ui.grid import redraw_grid as redraw_launcher_grid
from randomizer.ui.theme import apply_color_mode as apply_launcher_color_mode
from randomizer.ui.tooltips import WidgetTooltip

DEFAULT_MISSION_GOAL = int(DEFAULT_CONFIG['mission_goal'])
CHECK_SCHEMA_VERSION = 16
HOOK_POLL_MS = 1500
VICTORY_CLOSE_DELAY_MS = 2500
MAX_OPTION_INI_BYTES = 2 * 1024 * 1024


def reward_cameo_token(reward):
    """Return Unlocks placeholder, preferring configured custom artwork."""
    if reward.get('kind') != 'superweapon' or not reward.get('superweapon'):
        return ''
    sidebar_image = reward.get('superweapon_sidebar_image')
    if sidebar_image:
        return f'[[MOR_ASSET:{sidebar_image}]]'
    cameo_superweapon = reward.get('cameo_superweapon', reward['superweapon'])
    return f'[[MOR_POWER:{cameo_superweapon}]]'
