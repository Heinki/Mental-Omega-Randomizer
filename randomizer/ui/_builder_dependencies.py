"""Shared Tk and configuration dependencies for UI construction."""

"""Tk widget construction separated from launcher orchestration."""

import tkinter as tk
from tkinter import scrolledtext, ttk

from randomizer.config.player import DEFAULT_CONFIG
from randomizer.core.paths import LAUNCHER_LOG
from randomizer.rewards.catalogue import (
    BUFF_TYPES,
    MAX_REWARDS_PER_CHECK,
    POWER_BUFF_TYPES,
    REWARD_POOL,
    buff_stack_limit,
)
from randomizer.config.tuning import stacking_amount, stacking_multiplier
from randomizer.rewards.weights import (
    MAIN_REWARD_WEIGHT_TYPES,
    MAX_REWARD_WEIGHT,
    POWER_BUFF_WEIGHT_TYPES,
    UNIT_BUFF_WEIGHT_TYPES,
)
from randomizer.rewards.starting import (
    MAX_STARTING_REWARD_COUNT,
    STARTING_REWARD_TYPE_DEFINITIONS,
    STARTING_UNLOCK_CATEGORY_LABELS,
)
from randomizer.rewards.arsenal import (
    ARSENAL_FACTIONS,
    ARSENAL_POWER_TYPES,
    ARSENAL_TIERS,
    ARSENAL_UNIT_TYPES,
)
from randomizer.rewards.enemy_scaling import (
    ENEMY_BUFF_DEFINITIONS,
    ENEMY_BUFF_GROUP_DEFINITIONS,
    MAX_AI_REWARDS_PER_COMPLETION,
)
from randomizer.ui.tooltips import TreeTooltip, WidgetTooltip
from randomizer.ui.integer_slider import IntegerSlider
from randomizer.ui.config import (
    CAMPAIGN_FILTERS,
    DIFFICULTIES,
    EVA_VOICE_CHOICES,
    GAME_SPEEDS,
    PLAYER_COLORS,
    PROGRESSION_MODES,
    REWARD_MODES,
)
from randomizer.core.version import APP_VERSION

DEFAULT_MISSION_GOAL = int(DEFAULT_CONFIG['mission_goal'])
