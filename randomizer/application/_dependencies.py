"""Shared imports and constants for launcher controllers."""

import logging
import os
import queue
import random
import re
import signal
import shutil
import subprocess
import sys
import threading
import time
import traceback

from randomizer.config.player import CONFIG_PATH, DEFAULT_CONFIG, load_config, save_config
from randomizer.config.portable import (
    read_portable_settings,
    write_portable_settings,
)
from randomizer.core.storage import atomic_write_json, read_json_object
from randomizer.progression.state import (
    normalize_assistance_units,
    normalize_completed_checks,
    normalize_failure_stacks,
)
from randomizer.rewards.planning import (
    MAX_REWARDS_ACHIEVED_REWARD,
    is_max_rewards_achieved_reward,
    plan_seed_rewards,
)
from randomizer.rewards.arsenal import (
    ARSENAL_FACTIONS,
    ARSENAL_MODE,
    ARSENAL_POWER_TYPES,
    ARSENAL_TIERS,
    ARSENAL_UNIT_TYPES,
    arsenal_launch_rewards,
    arsenal_power_ids,
    arsenal_reward_pool,
    arsenal_unit_ids,
    generate_mission_arsenals,
    normalize_arsenal_settings,
    reward_matches_arsenal,
)
from randomizer.rewards.weights import (
    DEFAULT_REWARD_WEIGHT,
    MAIN_REWARD_WEIGHT_TYPES,
    POWER_BUFF_WEIGHT_TYPES,
    UNIT_BUFF_WEIGHT_TYPES,
    clamp_reward_weight,
    normalize_reward_weights,
    reward_selection_weight,
)
from randomizer.rewards.enemy_scaling import (
    ENEMY_BUFF_BY_ID,
    ENEMY_BUFF_DEFINITIONS,
    ENEMY_BUFF_GROUP_DEFINITIONS,
    ENEMY_REWARD_PLAN_VERSION,
    MAX_ENEMY_TOTAL_BUFFS,
    NEW_ENEMY_POWER_IDS,
    configured_enemy_reward,
    enemy_buff_capacity,
    enemy_effect_text,
    normalize_enemy_scaling_settings,
    plan_enemy_check_rewards,
)
from randomizer.rewards.starting import (
    DEFAULT_STARTING_REWARD_TYPES,
    MAX_STARTING_REWARD_COUNT,
    STARTING_REWARD_TYPE_DEFINITIONS,
    STARTING_UNLOCK_CATEGORY_LABELS,
    filter_starting_reward_pool,
    normalize_starting_reward_count,
    normalize_starting_reward_types,
    normalize_starting_unlock_reward_names,
)
from randomizer.launch.options import (
    choice_label_from_ini,
    patch_large_ini_key,
    patch_or_append_large_ini_value,
    spawn_ini_text,
)
from randomizer.ui.cameos import (
    cameo_extraction_pending,
    ensure_superweapon_cameos,
    ensure_unit_cameos,
    extract_mix_files_sync,
)
from randomizer.core.mix import extract_mix_members
from randomizer.core.diagnostics import event as log_event
from randomizer.maps.assets import (
    claim_runtime_asset_lease,
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
    mission_reward_class,
    mission_reward_multiplier,
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
    REWARD_BY_NAME,
    REWARD_POOL,
    SPECIAL_BUILDING_DEFINITIONS,
    buff_stack_limit,
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
    payload_buff_power_ids_for_unit,
    unit_role_equivalents,
    valid_choice,
)

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, scrolledtext
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
    UIMD_INI,
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
from randomizer.rewards.access_limits import normalize_access_limits
from randomizer.missions.safety import (
    always_available_miner_rules,
    always_available_transport_rules,
    chaos_earned_access_rules,
    expanded_tier_one_defense_ids,
    expanded_tier_one_unit_ids,
    concrete_tier_one_starter_ids,
    mission_basic_unit_rules,
    original_mcv_access_rules,
    mission_production_families,
    random_chaos_tier_one_unit_ids,
    random_chaos_tier_one_defense_ids,
    select_tier_one_defense_variants,
    select_tier_one_unit_variants,
    single_engineer_rules,
    standard_tier_one_defense_markers,
    standard_tier_one_unit_markers,
    starting_tier_one_defense_rules,
    starting_tier_one_rules,
    summarize_basic_unit_rules,
    tier_one_defense_ids,
    tier_one_unit_ids,
    tier_one_role_label,
)
from randomizer.maps.pipeline import prepare_hooked_map as prepare_hooked_mission_map
from randomizer.maps.progress_hooks import NEXT_OBJECTIVE_CHECK_ID
from randomizer.missions.overrides import (
    MISSION_ORIGINAL_MCV_ACCESS_IDS,
    MISSION_NATIVE_TECH_UNLOCK_IDS,
    MISSION_REQUIRED_ACCESS_RULES,
    MISSION_SPECIAL_INFANTRY_FACTORY_EXCLUSIONS,
    MISSION_TRANSPORT_FACTORY_EXCEPTIONS,
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
CHECK_SCHEMA_VERSION = 18
HOOK_POLL_MS = 1500
RESTART_FAILURE_GRACE_MS = 3000
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
