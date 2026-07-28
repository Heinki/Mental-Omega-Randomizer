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
)
from randomizer.config.tuning import stacking_amount, stacking_multiplier
from randomizer.ui.tooltips import TreeTooltip, WidgetTooltip
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
