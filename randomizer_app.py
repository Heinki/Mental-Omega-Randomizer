import json
import logging
import queue
import random
import re
import shutil
import subprocess
import threading
import time
import traceback

from randomizer_config import CONFIG_PATH, load_config, save_config
from randomizer_cameos import (
    ensure_superweapon_cameos,
    ensure_unit_cameos,
    installed_rules_registry,
    mix_reader_assembly_paths,
    powershell_mix_reader_load_script,
)
from randomizer_diagnostics import event as log_event
from randomizer_version import APP_VERSION
from grid_progression import (
    COMPLETED as GRID_COMPLETED,
    LOCKED as GRID_LOCKED,
    UNLOCKED as GRID_UNLOCKED,
    completing_unlocks,
    create_grid,
    grid_opening_mission_codes,
    grid_opening_mission_count,
    is_complete as is_grid_complete,
    refresh_states as refresh_grid_states,
)
from randomizer_missions import (
    FACTION_ORDER,
    LATE_FOEHN_MISSION_CODES,
    LOW_LEVEL_MISSION_COUNT,
    NO_BUILD_MISSION_CODES,
    campaign_mission_counts,
    classic_mission_order,
    filter_missions_by_build_settings,
    normalize_faction,
    parse_missions,
    seed_campaign_limits,
    seed_mission_order,
)
from randomizer_mission_houses import (
    mission_house_config,
    mission_player_power_houses,
    mission_player_production_houses,
)
from randomizer_ini import (
    all_section_value_maps,
    merge_ini_section_values,
    read_text,
    set_ini_value_lines,
)
from randomizer_rewards import (
    AMPHIBIOUS_TRANSPORT_UNIT_IDS,
    BUFF_TARGETS,
    BUFF_TYPES,
    DEFAULT_REWARDS_PER_CHECK,
    ENGINEER_UNIT_IDS,
    effective_buff_count,
    buff_stack_limit,
    MAX_REWARDS_PER_CHECK,
    REWARD_POOL,
    buff_effect_lines,
    canonical_reward,
    canonical_rewards,
    check_rewards,
    clamp_int,
    reward_display_name,
    reward_names,
    reward_rule_summary,
    unit_display_label,
    unit_role_equivalents,
    valid_choice,
)

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
except ImportError:
    raise ImportError('tkinter is required to run this launcher UI.')


from randomizer_paths import (
    BATTLE_CLIENT_INI,
    DEBUG_LOG,
    DISABLED_RULESMO_INI,
    EXTRACTED_MAP_DIR,
    GAME_EXE,
    GAME_LAUNCHER_EXE,
    GAME_ROOT,
    GENERATED_MAP_DIR,
    LAUNCHER_LOG,
    OPTIONS_INI,
    RULESMO_INI,
    SPAWN_INI,
    STATE_PATH,
    WINDOW_ICON_PATH,
    YR_OPTIONS_INI,
)
from randomizer_map import (
    HOOKED_MAP_MARKER,
    LOCKED_TECH_LEVEL,
    SCRIPTED_TECH_BUILD_LIMIT,
    SCRIPTED_TECH_LOCK_EXCLUSIONS,
    action_has_code,
    action_has_objective_complete,
    action_line_ids,
    append_action_to_action_id,
    append_hook_team,
    append_parallel_global_hook,
    append_superweapon_grant_trigger,
    backup_file_once,
    cloned_superweapon_plan,
    clone_player_country_for_house_buffs,
    controlled_tech_ids,
    country_family,
    hook_marker_name,
    helper_ai_autobuild_plan,
    helper_ai_autobuild_rules,
    is_generated_hooked_map,
    is_generated_rules_file,
    insert_actions_before_codes,
    launch_rules_for_reward,
    mission_assistance_buff_rules,
    mission_assistance_direct_rewards,
    mission_assistance_multipliers,
    mission_assistance_unit_ids,
    now_stamp,
    player_controlled_houses,
    player_country_buff_rules,
    player_country_from_map,
    player_house_from_map,
    player_unit_clone_rules,
    map_house_records,
    remove_locked_techlevel_actions,
    resolve_configured_helper_houses,
    stacked_house_buff_values,
    tech_ids_for_rewards,
    unlocked_reward_tech_ids,
    trigger_action_ids_by_name,
    unique_in_order,
    unit_weapon_buff_rules,
)
from randomizer_mission_safety import (
    always_available_transport_rules,
    chaos_earned_access_rules,
    mission_basic_unit_rules,
    random_chaos_tier_one_unit_ids,
    safe_build_countries,
    single_engineer_rules,
    starting_tier_one_rules,
    summarize_basic_unit_rules,
    tier_one_unit_ids,
)
DIFFICULTIES = [('Casual', 0), ('Normal', 1), ('Mental', 2)]
GAME_SPEEDS = [
    # Keep the launcher labels aligned with the engine's option value. The
    # -SPEEDCONTROL runtime path still needs this value in spawn.ini, but high
    # values can normalize to the fast end during spawned campaign launches.
    ('0 - Slowest', 0),
    ('1 - Slower', 1),
    ('2 - Slow', 2),
    ('3 - Medium', 3),
    ('4 - Fast', 4),
    ('5 - Faster', 5),
    ('6 - Fastest', 6),
]
CAMPAIGN_FILTERS = ['All Campaigns', 'Allies', 'Soviets', 'Epsilon', 'Foehn']
REWARD_MODES = ['Standard', 'Chaos (Experimental)']
PROGRESSION_MODES = ['Classic', 'Mission List', 'Grid Mode']
DEFAULT_PROGRESSION_MODE = 'Mission List'

STARTING_UNLOCKED_MISSIONS = 3
DEFAULT_MISSION_GOAL = 15
FALLBACK_OBJECTIVE_COUNT = 3
CHECK_SCHEMA_VERSION = 16
HOOK_POLL_MS = 1500
VICTORY_CLOSE_DELAY_MS = 2500
MAX_OPTION_INI_BYTES = 2 * 1024 * 1024
MAX_GLOBAL_BUFF_REPEATS_PER_SEED = 3
GLOBAL_BUFF_REWARD_INTERVAL = 10
FACTION_TILE_COLORS = {
    'Allies': '#285f9e',
    'Soviets': '#a53636',
    'Epsilon': '#70429a',
    'Foehn': '#16898b',
}
LIGHT_UI_PALETTE = {
    'background': '#f0f0f0',
    'panel': '#ffffff',
    'canvas': '#e9ecef',
    'foreground': '#202124',
    'muted': '#555555',
    'field': '#ffffff',
    'border': '#b8bec5',
    'select': '#3478bd',
    'select_foreground': '#ffffff',
    'busy': '#edf3f8',
    'busy_card': '#f9fcff',
    'busy_title': '#172a3a',
    'busy_detail': '#4c6172',
}
DARK_UI_PALETTE = {
    'background': '#171a1f',
    'panel': '#20242b',
    'canvas': '#12151a',
    'foreground': '#e8eaed',
    'muted': '#aeb6c2',
    'field': '#111419',
    'border': '#49515c',
    'select': '#315f91',
    'select_foreground': '#ffffff',
    'busy': '#111419',
    'busy_card': '#202a34',
    'busy_title': '#f2f7fb',
    'busy_detail': '#b9c7d4',
}

# These campaign objects begin outside the player coalition, then become or
# affect player-owned mission objects through native triggers. Their placed
# identity stays native, so exact Event/Action references must stay native too.
MISSION_NATIVE_TRIGGER_REFERENCE_IDS = {
    'EPEACE': frozenset({'LCRF'}),
    'ESING': frozenset({'DRIL'}),
    'EBREED': frozenset({'DISK', 'KAOS'}),
}


class WidgetTooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind('<Enter>', self.show, add='+')
        widget.bind('<Leave>', self.hide, add='+')
        widget.bind('<ButtonPress>', self.hide, add='+')

    def show(self, event=None):
        if self.tip is not None or not self.text:
            return
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        label = ttk.Label(
            self.tip,
            text=self.text,
            justify='left',
            padding=(8, 6, 8, 6),
            relief='solid',
            wraplength=380,
        )
        label.grid(row=0, column=0)
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip.wm_geometry(f'+{x}+{y}')

    def hide(self, event=None):
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None

class TreeTooltip:
    def __init__(self, tree, text_callback):
        self.tree = tree
        self.text_callback = text_callback
        self.tip = None
        self.current_row = None
        tree.bind('<Motion>', self.on_motion, add='+')
        tree.bind('<Leave>', self.hide, add='+')

    def on_motion(self, event):
        row = self.tree.identify_row(event.y)
        if not row:
            self.hide()
            return

        text = self.text_callback(row)
        if not text:
            self.hide()
            return

        x = self.tree.winfo_rootx() + event.x + 18
        y = self.tree.winfo_rooty() + event.y + 12
        if row != self.current_row:
            self.hide()
            self.current_row = row
            self.tip = tk.Toplevel(self.tree)
            self.tip.wm_overrideredirect(True)
            label = ttk.Label(
                self.tip,
                text=text,
                justify='left',
                padding=(8, 6, 8, 6),
                relief='solid',
                wraplength=620,
            )
            label.grid(row=0, column=0)
        self.tip.wm_geometry(f'+{x}+{y}')

    def hide(self, event=None):
        self.current_row = None
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None


class LauncherApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f'Mental Omega Randomizer Launcher v{APP_VERSION}')
        if WINDOW_ICON_PATH.is_file():
            try:
                self.iconbitmap(str(WINDOW_ICON_PATH))
            except (OSError, tk.TclError):
                pass
        self.geometry('1240x760')
        self.minsize(940, 560)
        self.resizable(True, True)

        self.missions = []
        self._mission_by_code = {}
        self.config = load_config()
        self.dark_mode_var = tk.BooleanVar(value=bool(self.config.get('dark_mode', False)))
        self.hide_reward_details_var = tk.BooleanVar(
            value=bool(self.config.get('hide_reward_details', False))
        )
        self.state = self.load_state()
        self.migrate_state()
        self._reward_settings_override = None
        self._starting_unit_ids_override = None
        self.active_game_process = None
        self.active_hook = None
        self.active_mission_attempt = None
        self.mission_sort_column = None
        self.mission_sort_reverse = False
        self.grid_render_signature = None
        self.grid_tile_widgets = {}
        self.grid_configured_width = 0
        self.grid_configured_height = 0
        self.settings_panel_visible = True
        self.selected_index = tk.IntVar(value=0)
        difficulty_default = valid_choice(
            self.config.get('difficulty'),
            [name for name, _ in DIFFICULTIES],
            self.read_spawn_difficulty(),
        )
        game_speed_default = valid_choice(
            self.config.get('game_speed'),
            [name for name, _ in GAME_SPEEDS],
            self.read_spawn_game_speed(),
        )
        campaign_default = valid_choice(
            self.state.get('campaign_filter', self.config.get('campaign_filter')),
            CAMPAIGN_FILTERS,
            CAMPAIGN_FILTERS[0],
        )
        self.difficulty_var = tk.StringVar(value=difficulty_default)
        self.game_speed_var = tk.StringVar(value=game_speed_default)
        self.campaign_var = tk.StringVar(value=campaign_default)
        self.seed_var = tk.StringVar(value=self.state.get('seed', self.config.get('seed', '')))
        default_goal = self.state.get('mission_goal', self.config.get('mission_goal', DEFAULT_MISSION_GOAL))
        self.mission_goal_var = tk.IntVar(value=int(default_goal or DEFAULT_MISSION_GOAL))
        default_rewards_per_check = clamp_int(
            self.state.get('rewards_per_check', self.config.get('rewards_per_objective', DEFAULT_REWARDS_PER_CHECK)),
            1,
            MAX_REWARDS_PER_CHECK,
            DEFAULT_REWARDS_PER_CHECK,
        )
        self.rewards_per_check_var = tk.IntVar(value=default_rewards_per_check)
        generation_config = self.config.get('generation', {})
        reward_mode_default = valid_choice(
            self.state.get('reward_mode', generation_config.get('reward_mode')),
            REWARD_MODES,
            REWARD_MODES[0],
        )
        self.reward_mode_var = tk.StringVar(value=reward_mode_default)
        progression_mode_default = valid_choice(
            self.state.get('progression_mode', self.config.get('progression_mode')),
            PROGRESSION_MODES,
            DEFAULT_PROGRESSION_MODE,
        )
        self.progression_mode_var = tk.StringVar(value=progression_mode_default)
        grid_state = self.state.get('grid', {}) if isinstance(self.state.get('grid'), dict) else {}
        self.grid_two_starts_var = tk.BooleanVar(
            value=bool(grid_state.get(
                'two_start_positions',
                self.config.get('grid_two_start_positions', False),
            ))
        )
        self.include_no_build_missions_var = tk.BooleanVar(
            value=bool(generation_config.get('include_no_build_missions', True))
        )
        self.include_no_build_production_missions_var = tk.BooleanVar(
            value=bool(generation_config.get('include_no_build_production_missions', True))
        )
        self.prioritize_no_build_missions_var = tk.BooleanVar(
            value=bool(generation_config.get('prioritize_no_build_missions', False))
        )
        reward_settings = self.config_reward_settings()
        enabled_buff_types = set(reward_settings['enabled_buff_types'])
        self.buff_allied_helpers_var = tk.BooleanVar(
            value=bool(generation_config.get('buff_allied_helpers', False))
        )
        self.failure_assistance_var = tk.BooleanVar(
            value=bool(generation_config.get('failure_assistance', False))
        )
        self.randomize_unit_access_var = tk.BooleanVar(
            value=reward_settings['randomize_unit_access']
        )
        self.start_with_tier_one_units_var = tk.BooleanVar(
            value=reward_settings['start_with_tier_one_units']
        )
        self.include_defensive_buildings_var = tk.BooleanVar(
            value=reward_settings['include_defensive_buildings']
        )
        self.unlimited_hero_units_var = tk.BooleanVar(
            value=reward_settings['unlimited_hero_units']
        )
        self.share_chaos_role_buffs_var = tk.BooleanVar(
            value=reward_settings['share_chaos_role_buffs']
        )
        self.include_buff_rewards_var = tk.BooleanVar(
            value=reward_settings['include_buff_rewards']
        )
        self.include_superweapon_rewards_var = tk.BooleanVar(
            value=reward_settings['include_superweapon_rewards']
        )
        self.include_secondary_superweapon_rewards_var = tk.BooleanVar(
            value=reward_settings['include_secondary_superweapon_rewards']
        )
        self.include_aid_power_rewards_var = tk.BooleanVar(
            value=reward_settings['include_aid_power_rewards']
        )
        self.buff_type_vars = {
            buff_type['id']: tk.BooleanVar(value=buff_type['id'] in enabled_buff_types)
            for buff_type in BUFF_TYPES
        }
        self.log_visible_var = tk.BooleanVar(value=False)
        self.unlock_search_var = tk.StringVar(value='')
        self.unlock_search_current = None
        self.cameo_photo_cache = {}
        self.unlock_cameo_images = {}
        self.busy_depth = 0
        self.ui_queue = queue.Queue()
        self.cleanup_generated_root_maps()
        self.disable_generated_rules_for_client()

        self.create_widgets()
        self.show_busy(
            'Loading randomizer…',
            'Reading missions and restoring the current run. Please wait.',
        )
        try:
            self.refresh_missions()
            self.refresh_progress_view()
        finally:
            self.hide_busy()
        self.after(40, self.process_ui_queue)
        log_event(
            'launcher_ready',
            missions=len(self.missions),
            has_seed=bool(self.state),
            seed=self.state.get('seed', ''),
        )

    def report_callback_exception(self, exc_type, exc_value, exc_traceback):
        detail = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        log_event('ui_callback_failed', level=logging.ERROR, traceback=detail)
        if hasattr(self, 'log_text'):
            self.append_log(f'Unexpected launcher error: {exc_value}', error=True)
        messagebox.showerror(
            'Unexpected Error',
            f'The launcher encountered an error. Details were saved to:\n{LAUNCHER_LOG}',
        )

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding=(12, 12, 12, 12))
        self.main_frame = main_frame
        main_frame.grid(row=0, column=0, sticky='nsew')
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.style = ttk.Style(self)
        self.style.configure('Randomizer.TNotebook', tabposition='n')
        self.style.configure('Randomizer.TNotebook.Tab', padding=(16, 7), font=('Segoe UI', 10, 'bold'))
        self.style.configure('Launch.TButton', font=('Segoe UI', 10, 'bold'), padding=(10, 7))

        header = ttk.Label(
            main_frame,
            text=f'Mental Omega Randomizer Launcher v{APP_VERSION}',
            font=('Segoe UI', 14, 'bold'),
        )
        header.grid(row=0, column=0, sticky='w')
        self.settings_toggle_button = ttk.Button(
            main_frame,
            text='Hide Settings',
            command=self.toggle_settings_panel,
        )
        self.settings_toggle_button.grid(row=0, column=1, rowspan=2, sticky='ne')
        self.subtitle_label = ttk.Label(
            main_frame,
            text='Choose an open mission, earn randomized upgrades, and let victory tracking update your run.',
            style='Muted.TLabel',
        )
        self.subtitle_label.grid(row=1, column=0, sticky='w', pady=(2, 10))

        mission_view_frame = ttk.Frame(main_frame)
        self.mission_view_frame = mission_view_frame
        mission_view_frame.grid(row=2, column=0, rowspan=5, sticky='nsew', padx=(0, 12))
        mission_view_frame.columnconfigure(0, weight=1)
        mission_view_frame.rowconfigure(0, weight=1)

        self.missions_tree = ttk.Treeview(
            mission_view_frame,
            columns=('order', 'state', 'checks', 'faction', 'code', 'title'),
            show='headings',
            selectmode='browse',
            height=17,
        )
        self.mission_heading_labels = {
            'order': 'No.',
            'state': 'State',
            'checks': 'Rewards',
            'faction': 'Faction',
            'code': 'Code',
            'title': 'Mission Title',
        }
        for column, label in self.mission_heading_labels.items():
            self.missions_tree.heading(
                column,
                text=label,
                command=lambda selected=column: self.sort_missions_by(selected),
            )
        self.missions_tree.column('order', width=48, anchor='center', stretch=False)
        self.missions_tree.column('state', width=64, anchor='center', stretch=False)
        self.missions_tree.column('checks', width=70, anchor='center', stretch=False)
        self.missions_tree.column('faction', width=78, anchor='w', stretch=False)
        self.missions_tree.column('code', width=86, anchor='w', stretch=False)
        self.missions_tree.column('title', width=300, anchor='w', stretch=True)
        self.missions_tree.tag_configure(
            'completed',
            background='#dff2df',
            foreground='#176b2c',
        )
        self.missions_tree.grid(row=0, column=0, sticky='nsew')
        self.missions_tree.bind('<<TreeviewSelect>>', self.on_mission_select, add='+')
        self.mission_tooltip = TreeTooltip(self.missions_tree, self.mission_tooltip_text)

        tree_scrollbar = ttk.Scrollbar(
            mission_view_frame,
            orient='vertical',
            command=self.missions_tree.yview,
        )
        tree_scrollbar.grid(row=0, column=1, sticky='ns')
        self.missions_tree.configure(yscrollcommand=tree_scrollbar.set)
        self.tree_scrollbar = tree_scrollbar

        self.grid_frame = ttk.Frame(mission_view_frame, padding=(4, 4, 4, 4))
        self.grid_frame.grid(row=0, column=0, columnspan=2, sticky='nsew')
        self.grid_frame.columnconfigure(0, weight=1)
        self.grid_frame.rowconfigure(0, weight=1)
        self.grid_canvas = tk.Canvas(
            self.grid_frame,
            borderwidth=0,
            highlightthickness=0,
            background='#e9ecef',
        )
        self.grid_vertical_scrollbar = ttk.Scrollbar(
            self.grid_frame,
            orient='vertical',
            command=self.grid_canvas.yview,
        )
        self.grid_horizontal_scrollbar = ttk.Scrollbar(
            self.grid_frame,
            orient='horizontal',
            command=self.grid_canvas.xview,
        )
        self.grid_canvas.configure(
            xscrollcommand=self.grid_horizontal_scrollbar.set,
            yscrollcommand=self.grid_vertical_scrollbar.set,
        )
        self.grid_canvas.grid(row=0, column=0, sticky='nsew')
        self.grid_vertical_scrollbar.grid(row=0, column=1, sticky='ns')
        self.grid_horizontal_scrollbar.grid(row=1, column=0, sticky='ew')
        self.grid_content_frame = ttk.Frame(self.grid_canvas)
        self.grid_canvas_window = self.grid_canvas.create_window(
            (0, 0),
            window=self.grid_content_frame,
            anchor='nw',
        )
        self.grid_content_frame.bind(
            '<Configure>', self.on_grid_content_configure, add='+'
        )
        self.grid_canvas.bind('<Configure>', self.on_grid_canvas_configure, add='+')
        self.bind_all('<MouseWheel>', self.on_grid_mousewheel, add='+')
        self.bind_all('<Shift-MouseWheel>', self.on_grid_shift_mousewheel, add='+')
        self.grid_placeholder = ttk.Label(
            self.grid_content_frame,
            text='Generate a Grid Mode seed to create the mission grid.',
            anchor='center',
            justify='center',
        )

        right_frame = ttk.Frame(main_frame)
        self.right_frame = right_frame
        right_frame.grid(row=2, column=1, rowspan=5, sticky='nsew')
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(4, weight=1)

        ttk.Label(right_frame, text='Seed', font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, sticky='w')
        seed_row = ttk.Frame(right_frame)
        seed_row.grid(row=1, column=0, sticky='ew', pady=(0, 6))
        seed_row.columnconfigure(0, weight=1)
        ttk.Entry(seed_row, textvariable=self.seed_var, width=20).grid(row=0, column=0, sticky='ew', padx=(0, 6))
        ttk.Button(seed_row, text='Generate New Seed', command=self.on_new_seed).grid(row=0, column=1, sticky='ew')

        options_row = ttk.Frame(right_frame)
        options_row.grid(row=2, column=0, sticky='ew', pady=(0, 6))
        options_row.columnconfigure(1, weight=1)
        options_row.columnconfigure(3, weight=1)
        ttk.Label(options_row, text='Missions to finish').grid(row=0, column=0, sticky='w', padx=(0, 8))
        self.mission_goal_spinbox = ttk.Spinbox(
            options_row,
            from_=1,
            to=max(DEFAULT_MISSION_GOAL, self.mission_goal_var.get()),
            textvariable=self.mission_goal_var,
            width=6,
        )
        self.mission_goal_spinbox.grid(row=0, column=1, sticky='w')
        ttk.Label(options_row, text='Game speed').grid(row=0, column=2, sticky='w', padx=(14, 8))
        self.game_speed_combo = ttk.Combobox(
            options_row,
            state='readonly',
            textvariable=self.game_speed_var,
            values=[name for name, _ in GAME_SPEEDS],
            width=10,
        )
        self.game_speed_combo.grid(row=0, column=3, sticky='ew')

        self.campaign_label = ttk.Label(options_row, text='Campaign')
        self.campaign_label.grid(row=1, column=0, sticky='w', pady=(6, 0), padx=(0, 8))
        self.campaign_combo = ttk.Combobox(
            options_row,
            state='readonly',
            textvariable=self.campaign_var,
            values=CAMPAIGN_FILTERS,
            width=12,
        )
        self.campaign_combo.grid(row=1, column=1, sticky='ew', pady=(6, 0))
        self.campaign_combo.bind('<<ComboboxSelected>>', self.on_campaign_filter_changed, add='+')

        ttk.Label(options_row, text='Difficulty').grid(row=1, column=2, sticky='w', pady=(6, 0), padx=(14, 8))
        self.difficulty_combo = ttk.Combobox(
            options_row,
            state='readonly',
            textvariable=self.difficulty_var,
            values=[name for name, _ in DIFFICULTIES],
            width=12,
        )
        self.difficulty_combo.grid(row=1, column=3, sticky='ew', pady=(6, 0))

        ttk.Label(options_row, text='Rewards per objective').grid(row=2, column=0, sticky='w', pady=(6, 0), padx=(0, 8))
        self.rewards_per_check_spinbox = ttk.Spinbox(
            options_row,
            from_=1,
            to=MAX_REWARDS_PER_CHECK,
            textvariable=self.rewards_per_check_var,
            width=6,
            validate='key',
            validatecommand=(self.register(self.validate_rewards_per_check), '%P'),
        )
        self.rewards_per_check_spinbox.grid(row=2, column=1, sticky='w', pady=(6, 0))
        self.buff_allied_helpers_check = ttk.Checkbutton(
            options_row,
            text='Buff allied helpers',
            variable=self.buff_allied_helpers_var,
        )
        self.buff_allied_helpers_check.grid(row=2, column=2, columnspan=2, sticky='w', pady=(6, 0), padx=(14, 0))
        WidgetTooltip(
            self.buff_allied_helpers_check,
            'Gives reviewed allied AI helpers safe country buffs and compatible '
            'earned unit clones through extra Autocreate teams. Native units, '
            'TaskForces, timing, and scripts stay intact.',
        )
        self.rewards_per_check_message_label = ttk.Label(options_row, text='')
        self.rewards_per_check_message_label.grid(
            row=3,
            column=0,
            columnspan=4,
            sticky='w',
            pady=(4, 0),
        )
        self.rewards_per_check_var.trace_add('write', self.refresh_rewards_per_check_message)
        self.refresh_rewards_per_check_message()

        ttk.Label(options_row, text='Reward mode').grid(row=4, column=0, sticky='w', pady=(6, 0), padx=(0, 8))
        self.reward_mode_combo = ttk.Combobox(
            options_row,
            state='readonly',
            textvariable=self.reward_mode_var,
            values=REWARD_MODES,
            width=20,
        )
        self.reward_mode_combo.grid(row=4, column=1, columnspan=3, sticky='ew', pady=(6, 0))
        self.reward_mode_combo.bind('<<ComboboxSelected>>', self.on_reward_mode_changed, add='+')
        WidgetTooltip(
            self.reward_mode_combo,
            'Standard uses campaign-appropriate factions and translates equivalent roles on mixed maps. '
            'Chaos draws units from all four factions, forces randomized access/tech locking, and lets '
            'earned units use matching production structures that the mission gives the player. It does '
            'not grant foreign production structures.',
        )

        ttk.Label(options_row, text='Progression').grid(row=5, column=0, sticky='w', pady=(6, 0), padx=(0, 8))
        self.progression_mode_combo = ttk.Combobox(
            options_row,
            state='readonly',
            textvariable=self.progression_mode_var,
            values=PROGRESSION_MODES,
            width=12,
        )
        self.progression_mode_combo.grid(row=5, column=1, sticky='ew', pady=(6, 0))
        self.progression_mode_combo.bind('<<ComboboxSelected>>', self.on_progression_mode_changed, add='+')
        WidgetTooltip(
            self.progression_mode_combo,
            'Classic follows the installed campaign order and opens one mission at a time. '
            'Mission List uses a randomized linear order. Grid Mode uses randomized missions '
            'on an orthogonal-neighbor board.',
        )

        self.grid_options_frame = ttk.Frame(options_row)
        self.grid_options_frame.grid(row=6, column=0, columnspan=4, sticky='ew', pady=(6, 0))
        self.grid_two_starts_check = ttk.Checkbutton(
            self.grid_options_frame,
            text='Start with two available missions',
            variable=self.grid_two_starts_var,
        )
        self.grid_two_starts_check.grid(row=0, column=0, sticky='w')
        WidgetTooltip(
            self.grid_two_starts_check,
            'Opens the missions directly right of and below the top-left node at seed start. '
            'The board dimensions are calculated automatically from Missions to finish.',
        )
        button_row = ttk.Frame(right_frame)
        button_row.grid(row=3, column=0, sticky='ew', pady=(0, 6))
        button_row.columnconfigure(0, weight=1)
        ttk.Button(
            button_row,
            text='Launch Selected Mission',
            command=self.on_launch_selected,
            style='Launch.TButton',
        ).grid(row=0, column=0, sticky='ew', pady=(0, 4))

        info_tabs = ttk.Notebook(right_frame, style='Randomizer.TNotebook')
        self.info_tabs = info_tabs
        info_tabs.grid(row=4, column=0, sticky='nsew')
        info_tabs.enable_traversal()

        progress_frame = ttk.Frame(info_tabs, padding=(8, 8, 8, 8))
        progress_frame.columnconfigure(0, weight=1)
        progress_frame.rowconfigure(1, weight=1)
        info_tabs.add(progress_frame, text='Mission Details')

        self.progress_label = ttk.Label(progress_frame, text='No seed generated yet.', anchor='w', justify='left')
        self.progress_label.grid(row=0, column=0, sticky='ew', pady=(0, 6))

        self.rewards_text = scrolledtext.ScrolledText(
            progress_frame,
            height=16,
            wrap='word',
            state='disabled',
            font=('Segoe UI', 9),
        )
        self.rewards_text.grid(row=1, column=0, sticky='nsew')

        unlocks_frame = ttk.Frame(info_tabs, padding=(8, 8, 8, 8))
        self.unlocks_tab = unlocks_frame
        unlocks_frame.columnconfigure(0, weight=1)
        unlocks_frame.rowconfigure(1, weight=1)
        info_tabs.add(unlocks_frame, text='Unlocks')

        search_row = ttk.Frame(unlocks_frame)
        search_row.grid(row=0, column=0, sticky='ew', pady=(0, 6))
        search_row.columnconfigure(0, weight=1)
        self.unlock_search_entry = ttk.Entry(search_row, textvariable=self.unlock_search_var)
        self.unlock_search_entry.grid(row=0, column=0, sticky='ew', padx=(0, 4))
        ttk.Button(search_row, text='Prev', command=self.find_unlock_previous, width=8).grid(row=0, column=1, padx=(0, 4))
        ttk.Button(search_row, text='Next', command=self.find_unlock_next, width=8).grid(row=0, column=2, padx=(0, 4))
        ttk.Button(search_row, text='Clear', command=self.clear_unlock_search, width=8).grid(row=0, column=3)
        self.unlock_search_status = ttk.Label(search_row, text='', width=9, anchor='e')
        self.unlock_search_status.grid(row=0, column=4, padx=(6, 0))

        self.unlocks_text = scrolledtext.ScrolledText(
            unlocks_frame,
            height=16,
            wrap='word',
            state='disabled',
            font=('Segoe UI', 9),
        )
        self.unlocks_text.grid(row=1, column=0, sticky='nsew')
        self.unlocks_text.tag_configure('search_match', background='#fff0a6')
        self.unlocks_text.tag_configure('search_current', background='#ffbf69')
        self.unlock_search_var.trace_add('write', self.refresh_unlock_search)
        self.unlock_search_entry.bind('<Return>', self.find_unlock_next)
        self.unlock_search_entry.bind('<Shift-Return>', self.find_unlock_previous)
        self.unlock_search_entry.bind('<Escape>', self.clear_unlock_search)
        self.bind_all('<Control-f>', self.focus_unlock_search, add='+')
        self.bind_all('<F3>', self.find_unlock_next, add='+')
        self.bind_all('<Shift-F3>', self.find_unlock_previous, add='+')

        settings_tab = ttk.Frame(info_tabs)
        self.settings_tab = settings_tab
        settings_tab.columnconfigure(0, weight=1)
        settings_tab.rowconfigure(0, weight=1)
        info_tabs.add(settings_tab, text='Settings')

        settings_canvas = tk.Canvas(
            settings_tab,
            borderwidth=0,
            highlightthickness=0,
            background=self.style.lookup('TFrame', 'background') or '#f0f0f0',
        )
        self.settings_canvas = settings_canvas
        settings_scrollbar = ttk.Scrollbar(
            settings_tab,
            orient='vertical',
            command=settings_canvas.yview,
        )
        settings_canvas.configure(yscrollcommand=settings_scrollbar.set)
        settings_canvas.grid(row=0, column=0, sticky='nsew')
        settings_scrollbar.grid(row=0, column=1, sticky='ns')

        settings_frame = ttk.Frame(settings_canvas, padding=(8, 8, 8, 8))
        settings_frame.columnconfigure(0, weight=1)
        self.settings_frame = settings_frame
        self.settings_canvas_window = settings_canvas.create_window(
            (0, 0),
            window=settings_frame,
            anchor='nw',
        )
        settings_frame.bind('<Configure>', self.on_settings_content_configure, add='+')
        settings_canvas.bind('<Configure>', self.on_settings_canvas_configure, add='+')
        self.bind_all('<MouseWheel>', self.on_settings_mousewheel, add='+')

        self.settings_intro_label = ttk.Label(
            settings_frame,
            text=(
                'Gameplay settings are saved for the next generated seed. Existing runs keep '
                'their generated gameplay settings. Appearance and privacy apply immediately.'
            ),
            wraplength=340,
            style='Muted.TLabel',
        )
        self.settings_intro_label.grid(row=0, column=0, sticky='ew', pady=(0, 8))

        mission_pool_frame = ttk.LabelFrame(
            settings_frame,
            text='Mission Pool',
            padding=(8, 8, 8, 8),
        )
        mission_pool_frame.grid(row=1, column=0, sticky='ew')
        self.include_no_build_missions_check = ttk.Checkbutton(
            mission_pool_frame,
            text='Include true no-build / fixed-unit missions',
            variable=self.include_no_build_missions_var,
            command=self.on_mission_pool_settings_changed,
        )
        self.include_no_build_missions_check.grid(row=0, column=0, sticky='w')
        WidgetTooltip(
            self.include_no_build_missions_check,
            'Includes missions completed only with fixed units, heroes, or scripted map powers and no player production.',
        )
        self.include_no_build_production_missions_check = ttk.Checkbutton(
            mission_pool_frame,
            text='Include no-build missions with production',
            variable=self.include_no_build_production_missions_var,
            command=self.on_mission_pool_settings_changed,
        )
        self.include_no_build_production_missions_check.grid(
            row=1, column=0, sticky='w', pady=(4, 0)
        )
        WidgetTooltip(
            self.include_no_build_production_missions_check,
            'Includes missions without normal base building that still provide limited unit production.',
        )
        self.prioritize_no_build_missions_check = ttk.Checkbutton(
            mission_pool_frame,
            text='Prioritize included no-build missions in opening',
            variable=self.prioritize_no_build_missions_var,
        )
        self.prioritize_no_build_missions_check.grid(row=2, column=0, sticky='w', pady=(4, 0))
        WidgetTooltip(
            self.prioritize_no_build_missions_check,
            'Fills protected Mission List/Grid opening positions with easier enabled true-no-build and production-no-build missions first.',
        )

        reward_frame = ttk.LabelFrame(settings_frame, text='Reward Pool', padding=(8, 8, 8, 8))
        reward_frame.grid(row=2, column=0, sticky='ew', pady=(8, 0))
        reward_frame.columnconfigure(0, weight=1)
        self.randomize_unit_access_check = ttk.Checkbutton(
            reward_frame,
            text='Randomize unit access and lock unearned tech',
            variable=self.randomize_unit_access_var,
            command=self.refresh_setting_states,
        )
        self.randomize_unit_access_check.grid(row=0, column=0, sticky='w')
        WidgetTooltip(
            self.randomize_unit_access_check,
            'Turns combat units into access rewards. Units not yet earned are removed from production. '
            'Chaos always requires this option.',
        )
        self.start_with_tier_one_units_check = ttk.Checkbutton(
            reward_frame,
            text='Start with basic Tier 1 combat units',
            variable=self.start_with_tier_one_units_var,
        )
        self.start_with_tier_one_units_check.grid(row=1, column=0, sticky='w', pady=(4, 0))
        WidgetTooltip(
            self.start_with_tier_one_units_check,
            'Standard grants ground/anti-air infantry, vehicles, and one basic aircraft matching each '
            'Allied, Soviet, or Epsilon production family present in the mission. An available MCV or '
            'Construction Yard also unlocks the matching airfield. Chaos assigns every faction once '
            'across the four ground roles, then adds one seeded Allied, Soviet, or Epsilon aircraft. '
            'Starter units remain buffable.',
        )
        self.include_defensive_buildings_check = ttk.Checkbutton(
            reward_frame,
            text='Include defensive building rewards',
            variable=self.include_defensive_buildings_var,
        )
        self.include_defensive_buildings_check.grid(row=2, column=0, sticky='w', pady=(4, 0))
        WidgetTooltip(
            self.include_defensive_buildings_check,
            'Includes faction defenses such as Pillboxes, Tesla Coils, mines, and support defenses. '
            'With access randomization they can be locked/unlocked; with buffs enabled they can receive upgrades.',
        )
        self.include_buff_rewards_check = ttk.Checkbutton(
            reward_frame,
            text='Include buff rewards',
            variable=self.include_buff_rewards_var,
            command=self.refresh_setting_states,
        )
        self.include_buff_rewards_check.grid(row=3, column=0, sticky='w', pady=(4, 0))
        WidgetTooltip(
            self.include_buff_rewards_check,
            'Adds repeatable stat upgrades to the reward pool. Turning this off disables all buff-only settings below.',
        )
        self.share_chaos_role_buffs_check = ttk.Checkbutton(
            reward_frame,
            text='Share buffs with equivalent units (Chaos only)',
            variable=self.share_chaos_role_buffs_var,
        )
        self.share_chaos_role_buffs_check.grid(row=4, column=0, sticky='w', pady=(4, 0))
        WidgetTooltip(
            self.share_chaos_role_buffs_check,
            'In Chaos, a buff for one curated role also affects its peers—for example GI, Conscript, '
            'Initiate, and Knightframe. Shared groups are displayed together in Unlocks.',
        )
        self.unlimited_hero_units_check = ttk.Checkbutton(
            reward_frame,
            text='Unlimited unique / hero units',
            variable=self.unlimited_hero_units_var,
            command=self.refresh_setting_states,
        )
        self.unlimited_hero_units_check.grid(row=5, column=0, sticky='w', pady=(4, 0))
        WidgetTooltip(
            self.unlimited_hero_units_check,
            'Removes the simultaneous-unit cap from trainable unique and hero units for the player. '
            'Opted-in allied helpers share the same clones. This disables the +1 limit buff.',
        )
        self.include_superweapon_rewards_check = ttk.Checkbutton(
            reward_frame,
            text='Include offensive superweapon rewards',
            variable=self.include_superweapon_rewards_var,
        )
        self.include_superweapon_rewards_check.grid(row=6, column=0, sticky='w', pady=(4, 0))
        WidgetTooltip(
            self.include_superweapon_rewards_check,
            'Adds Lightning Storm, Tactical Nuke, Psychic Dominator, and Great Tempest as building-free rewards.',
        )
        self.include_secondary_superweapon_rewards_check = ttk.Checkbutton(
            reward_frame,
            text='Include secondary superweapon rewards',
            variable=self.include_secondary_superweapon_rewards_var,
        )
        self.include_secondary_superweapon_rewards_check.grid(row=7, column=0, sticky='w', pady=(4, 0))
        WidgetTooltip(
            self.include_secondary_superweapon_rewards_check,
            'Adds Chronoshift, Invulnerability, Rage, and Blasticade as building-free rewards.',
        )
        self.include_aid_power_rewards_check = ttk.Checkbutton(
            reward_frame,
            text='Include aid/reinforcement power rewards',
            variable=self.include_aid_power_rewards_var,
        )
        self.include_aid_power_rewards_check.grid(row=8, column=0, sticky='w', pady=(4, 0))
        WidgetTooltip(
            self.include_aid_power_rewards_check,
            'Adds faction unit drops, temporary reinforcements, deployable towers, mines, and other delivery-based support actions.',
        )

        buff_frame = ttk.LabelFrame(settings_frame, text='Enabled Buff Types', padding=(8, 8, 8, 8))
        buff_frame.grid(row=3, column=0, sticky='ew', pady=(8, 0))
        for column in range(2):
            buff_frame.columnconfigure(column, weight=1)
        self.buff_type_checks = []
        self.buff_type_checks_by_id = {}
        for index, buff_type in enumerate(BUFF_TYPES):
            row, column = divmod(index, 2)
            check = ttk.Checkbutton(
                buff_frame,
                text=buff_type.get('setting_label', buff_type['name']),
                variable=self.buff_type_vars[buff_type['id']],
                command=self.refresh_setting_states,
            )
            check.grid(row=row, column=column, sticky='w', padx=(0, 10), pady=(0, 3))
            self.buff_type_checks.append(check)
            self.buff_type_checks_by_id[buff_type['id']] = check
            description = buff_type.get('description', '').format(plural='Affected units')
            WidgetTooltip(check, description)
        assistance_frame = ttk.LabelFrame(
            settings_frame,
            text='Mission Assistance',
            padding=(8, 8, 8, 8),
        )
        assistance_frame.grid(row=4, column=0, sticky='ew', pady=(8, 0))
        self.failure_assistance_check = ttk.Checkbutton(
            assistance_frame,
            text='Strengthen failed missions on retry',
            variable=self.failure_assistance_var,
        )
        self.failure_assistance_check.grid(row=0, column=0, sticky='w')
        WidgetTooltip(
            self.failure_assistance_check,
            'Each unsuccessful attempt adds one assistance stack only to that mission. '
            'The stack applies on its next launch and is removed when the mission is completed.',
        )
        self.assistance_description_label = ttk.Label(
            assistance_frame,
            text=(
                'Per stack: faster production and per-unit weapon firing, cheaper units, and higher movement '
                'speed, health, weapon damage, armor effectiveness, and attack range. Infantry '
                'infantry movement is capped at Speed 8. Applies '
                'to earned units and units supplied by that mission; normal faction rosters '
                'are used when unit access is not randomized.'
            ),
            wraplength=340,
            justify='left',
            style='Muted.TLabel',
        )
        self.assistance_description_label.grid(row=1, column=0, sticky='ew', pady=(5, 0))

        appearance_frame = ttk.LabelFrame(
            settings_frame,
            text='Appearance & Privacy',
            padding=(8, 8, 8, 8),
        )
        appearance_frame.grid(row=5, column=0, sticky='ew', pady=(8, 0))
        self.dark_mode_check = ttk.Checkbutton(
            appearance_frame,
            text='Dark mode',
            variable=self.dark_mode_var,
            command=self.on_dark_mode_changed,
        )
        self.dark_mode_check.grid(row=0, column=0, sticky='w')
        self.hide_reward_details_check = ttk.Checkbutton(
            appearance_frame,
            text='Hide reward names in Mission Details',
            variable=self.hide_reward_details_var,
            command=self.on_hide_reward_details_changed,
        )
        self.hide_reward_details_check.grid(row=1, column=0, sticky='w', pady=(4, 0))
        WidgetTooltip(
            self.hide_reward_details_check,
            'Shows ????? for assigned rewards in Mission Details and mission-row hover text. '
            'Earned rewards remain visible in Unlocks.',
        )

        self.refresh_setting_states()

        self.status_label = ttk.Label(main_frame, text='Ready', anchor='w')
        self.status_label.grid(row=7, column=0, columnspan=2, sticky='ew', pady=(8, 0))

        log_header = ttk.Frame(main_frame)
        log_header.grid(row=8, column=0, columnspan=2, sticky='ew', pady=(12, 4))
        log_header.columnconfigure(1, weight=1)
        self.log_toggle_button = ttk.Button(
            log_header,
            text='Show Launcher Log',
            command=self.toggle_log,
            width=18,
        )
        self.log_toggle_button.grid(row=0, column=0, sticky='w')
        ttk.Label(log_header, text=f'Persistent diagnostics: {LAUNCHER_LOG}').grid(
            row=0,
            column=1,
            sticky='w',
            padx=(8, 0),
        )
        self.debug_complete_button = ttk.Button(
            log_header,
            text='Debug: Mark Complete',
            command=self.on_debug_mark_complete,
        )
        self.debug_complete_button.grid(row=0, column=2, sticky='e', padx=(8, 0))
        self.debug_complete_button.grid_remove()

        self.log_text = scrolledtext.ScrolledText(
            main_frame,
            height=10,
            wrap='word',
            state='disabled',
            background='black',
            foreground='white',
        )
        self.log_text.grid(row=9, column=0, columnspan=2, sticky='nsew')
        self.log_text.grid_remove()

        main_frame.rowconfigure(2, weight=1)
        main_frame.rowconfigure(9, weight=0)
        # Uniform sizing makes the mission view reliably wider than settings,
        # regardless of the settings widgets' requested width.
        main_frame.columnconfigure(0, weight=5, uniform='content')
        main_frame.columnconfigure(1, weight=3, uniform='content')

        # Long seed/map work runs on the single background worker. This overlay
        # blocks duplicate input while Tk keeps painting progress and elapsed time.
        self.busy_overlay = tk.Frame(main_frame, background='#edf3f8')
        self.busy_card = tk.Frame(
            self.busy_overlay,
            background='#f9fcff',
            highlightbackground='#79cfff',
            highlightthickness=3,
            padx=34,
            pady=26,
        )
        self.busy_card.place(relx=0.5, rely=0.5, anchor='center')
        self.busy_title = tk.Label(
            self.busy_card,
            text='',
            background='#f9fcff',
            foreground='#172a3a',
            font=('Segoe UI', 13, 'bold'),
        )
        self.busy_title.pack()
        self.busy_detail = tk.Label(
            self.busy_card,
            text='',
            background='#f9fcff',
            foreground='#4c6172',
            font=('Segoe UI', 9),
            wraplength=380,
            justify='center',
        )
        self.busy_detail.pack(pady=(8, 14))
        self.busy_progress = ttk.Progressbar(self.busy_card, mode='indeterminate', length=300)
        self.busy_progress.pack(fill='x')
        self.apply_color_mode()

    def toggle_settings_panel(self):
        self.settings_panel_visible = not self.settings_panel_visible
        if self.settings_panel_visible:
            self.right_frame.grid()
            self.mission_view_frame.grid_configure(columnspan=1, padx=(0, 12))
            self.settings_toggle_button.configure(text='Hide Settings')
        else:
            self.right_frame.grid_remove()
            self.mission_view_frame.grid_configure(columnspan=2, padx=0)
            self.settings_toggle_button.configure(text='Show Settings')
        self.after_idle(self.resize_grid_canvas_window)

    def ui_palette(self):
        return DARK_UI_PALETTE if self.dark_mode_var.get() else LIGHT_UI_PALETTE

    def ensure_checkbutton_indicator(self):
        """Use a real tick instead of Clam's X-shaped checkbox marker."""
        style = self.style

        def checkbox_image(fill, border, tick=None):
            photo = tk.PhotoImage(master=self, width=16, height=16)
            photo.put(border, to=(0, 0, 16, 16))
            photo.put(fill, to=(2, 2, 14, 14))
            if tick:
                # Thick, compact check mark that remains clear at 100% scaling.
                for x, y in (
                    (3, 8), (4, 9), (5, 10), (6, 11),
                    (7, 10), (8, 9), (9, 8), (10, 7),
                    (11, 6), (12, 5),
                ):
                    photo.put(tick, to=(x, y, min(16, x + 2), min(16, y + 2)))
            return photo

        if not hasattr(self, 'checkbox_indicator_images'):
            self.checkbox_indicator_images = {
                'light_off': checkbox_image('#eef0f2', '#68717a'),
                'light_on': checkbox_image('#68717a', '#4f565d', '#ffffff'),
                'light_disabled_off': checkbox_image('#e2e4e6', '#b2b6bb'),
                'light_disabled_on': checkbox_image('#b9bec4', '#a5aab0', '#f2f2f2'),
                'dark_off': checkbox_image('#353b43', '#8d97a3'),
                'dark_on': checkbox_image('#626b76', '#a5afb9', '#ffffff'),
                'dark_disabled_off': checkbox_image('#252a30', '#4d555f'),
                'dark_disabled_on': checkbox_image('#3b4149', '#505863', '#858c95'),
            }

        mode = 'dark' if self.dark_mode_var.get() else 'light'
        element = f'Randomizer.{mode}.Checkbutton.indicator'
        if element not in style.element_names():
            images = self.checkbox_indicator_images
            style.element_create(
                element,
                'image',
                images[f'{mode}_off'],
                ('disabled', 'selected', images[f'{mode}_disabled_on']),
                ('disabled', images[f'{mode}_disabled_off']),
                ('selected', images[f'{mode}_on']),
                sticky='',
            )
        style.layout(
            'TCheckbutton',
            [
                ('Checkbutton.padding', {
                    'sticky': 'nswe',
                    'children': [
                        (element, {'side': 'left', 'sticky': ''}),
                        ('Checkbutton.focus', {
                            'side': 'left',
                            'sticky': 'w',
                            'children': [
                                ('Checkbutton.label', {'sticky': 'nswe'}),
                            ],
                        }),
                    ],
                }),
            ],
        )

    def apply_color_mode(self):
        palette = self.ui_palette()
        style = self.style
        # Native Windows themes ignore several color and state overrides. Clam
        # honors the complete palette in both modes and keeps tab geometry stable.
        target_theme = 'clam'
        if target_theme in style.theme_names() and style.theme_use() != target_theme:
            style.theme_use(target_theme)

        background = palette['background']
        panel = palette['panel']
        foreground = palette['foreground']
        field = palette['field']
        border = palette['border']
        selected = palette['select']
        selected_foreground = palette['select_foreground']
        self.configure(background=background)

        style.configure('TFrame', background=background)
        style.configure('TLabel', background=background, foreground=foreground)
        style.configure('Muted.TLabel', background=background, foreground=palette['muted'])
        # ttk's canonical style name uses a lowercase "f". The old spelling
        # configured an unused style and left Settings group interiors light.
        style.configure('TLabelframe', background=background, bordercolor=border)
        style.configure('TLabelframe.Label', background=background, foreground=foreground)
        style.configure('TCheckbutton', background=background, foreground=foreground)
        self.ensure_checkbutton_indicator()
        style.configure('TRadiobutton', background=background, foreground=foreground)
        style.configure('TButton', background=panel, foreground=foreground, bordercolor=border)
        style.configure('Launch.TButton', background=panel, foreground=foreground, bordercolor=border)
        style.map(
            'TButton',
            background=[('active', selected), ('pressed', selected)],
            foreground=[('active', selected_foreground), ('pressed', selected_foreground)],
        )
        style.map(
            'TCheckbutton',
            background=[('active', background)],
            foreground=[('disabled', palette['muted']), ('active', foreground)],
        )
        style.configure('TEntry', fieldbackground=field, foreground=foreground, insertcolor=foreground)
        style.configure('TSpinbox', fieldbackground=field, foreground=foreground, arrowcolor=foreground)
        style.configure('TCombobox', fieldbackground=field, background=panel, foreground=foreground, arrowcolor=foreground)
        style.map(
            'TCombobox',
            fieldbackground=[('readonly', field)],
            foreground=[('readonly', foreground)],
            selectbackground=[('readonly', selected)],
            selectforeground=[('readonly', selected_foreground)],
        )
        style.configure('TNotebook', background=background, bordercolor=border)
        style.configure('TNotebook.Tab', background=panel, foreground=foreground)
        style.configure('Randomizer.TNotebook', background=background, bordercolor=border, tabposition='n')
        style.configure(
            'Randomizer.TNotebook.Tab',
            background=panel,
            foreground=foreground,
            padding=(16, 7),
            font=('Segoe UI', 10, 'bold'),
        )
        style.map(
            'Randomizer.TNotebook.Tab',
            background=[('selected', selected), ('active', palette['canvas'])],
            foreground=[('selected', selected_foreground), ('active', foreground)],
            padding=[('selected', (16, 7)), ('active', (16, 7))],
        )
        style.configure(
            'Treeview',
            background=field,
            fieldbackground=field,
            foreground=foreground,
            bordercolor=border,
        )
        style.map(
            'Treeview',
            background=[('selected', selected)],
            foreground=[('selected', selected_foreground)],
        )
        style.configure('Treeview.Heading', background=panel, foreground=foreground, bordercolor=border)
        style.map('Treeview.Heading', background=[('active', palette['canvas'])])
        style.configure('TScrollbar', background=panel, troughcolor=background, bordercolor=border, arrowcolor=foreground)

        if hasattr(self, 'missions_tree'):
            self.missions_tree.tag_configure(
                'completed',
                background='#244a32' if self.dark_mode_var.get() else '#dff2df',
                foreground='#b8efc5' if self.dark_mode_var.get() else '#176b2c',
            )
        for canvas_name in ('settings_canvas', 'grid_canvas'):
            canvas = getattr(self, canvas_name, None)
            if canvas is not None:
                canvas.configure(background=palette['canvas'])
        for text_name in ('rewards_text', 'unlocks_text'):
            text_widget = getattr(self, text_name, None)
            if text_widget is not None:
                text_widget.configure(
                    background=field,
                    foreground=foreground,
                    insertbackground=foreground,
                    selectbackground=selected,
                    selectforeground=selected_foreground,
                )
        if hasattr(self, 'unlocks_text'):
            self.unlocks_text.tag_configure(
                'search_match',
                background='#665c20' if self.dark_mode_var.get() else '#fff0a6',
                foreground=foreground,
            )
            self.unlocks_text.tag_configure(
                'search_current',
                background='#9b5d1f' if self.dark_mode_var.get() else '#ffbf69',
                foreground=foreground,
            )
        if hasattr(self, 'log_text'):
            self.log_text.configure(
                background=field,
                foreground=foreground,
                insertbackground=foreground,
                selectbackground=selected,
                selectforeground=selected_foreground,
            )
            self.log_text.tag_config('error', foreground='#ff7b72' if self.dark_mode_var.get() else '#b00020')
        if hasattr(self, 'busy_overlay'):
            self.busy_overlay.configure(background=palette['busy'])
            self.busy_card.configure(
                background=palette['busy_card'],
                highlightbackground=selected,
            )
            self.busy_title.configure(
                background=palette['busy_card'],
                foreground=palette['busy_title'],
            )
            self.busy_detail.configure(
                background=palette['busy_card'],
                foreground=palette['busy_detail'],
            )

    def save_ui_preferences(self):
        self.config['dark_mode'] = bool(self.dark_mode_var.get())
        self.config['hide_reward_details'] = bool(self.hide_reward_details_var.get())
        save_config(self.config)

    def on_dark_mode_changed(self):
        self.apply_color_mode()
        self.save_ui_preferences()
        if hasattr(self, 'grid_content_frame'):
            self.grid_render_signature = None
            self.redraw_grid()

    def on_hide_reward_details_changed(self):
        self.save_ui_preferences()
        self.refresh_progress_view()

    def show_busy(self, title, detail='Please wait.'):
        first_busy = self.busy_depth == 0
        self.busy_depth += 1
        self.busy_title.configure(text=title)
        self.busy_detail_text = detail
        if first_busy:
            self.busy_started_at = time.monotonic()
            self.update_busy_elapsed()
        self.busy_overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self.busy_overlay.lift()
        self.busy_progress.start(12)
        self.configure(cursor='wait')
        try:
            self.busy_overlay.grab_set()
        except tk.TclError:
            pass
        # Paint immediately; elapsed text then proves Tk remains responsive.
        self.update_idletasks()

    def update_busy_elapsed(self):
        if not self.busy_depth:
            return
        elapsed = max(0, int(time.monotonic() - self.busy_started_at))
        self.busy_detail.configure(
            text=f'{self.busy_detail_text}\nElapsed: {elapsed}s',
        )
        self.busy_update_after_id = self.after(250, self.update_busy_elapsed)

    def hide_busy(self):
        self.busy_depth = max(0, self.busy_depth - 1)
        if self.busy_depth:
            return
        busy_after_id = self.__dict__.pop('busy_update_after_id', None)
        if busy_after_id is not None:
            try:
                self.after_cancel(busy_after_id)
            except tk.TclError:
                pass
        self.busy_progress.stop()
        try:
            if self.grab_current() == self.busy_overlay:
                self.busy_overlay.grab_release()
        except tk.TclError:
            pass
        self.busy_overlay.place_forget()
        self.configure(cursor='')

    def run_in_background(self, title, detail, callback, on_success, on_error):
        """Run filesystem/CPU work without blocking Tk's event loop."""
        self.show_busy(title, detail)

        def worker():
            try:
                result = callback()
            except Exception as exc:
                error_detail = traceback.format_exc()

                def deliver_error(exc=exc, error_detail=error_detail):
                    try:
                        on_error(exc, error_detail)
                    finally:
                        self.hide_busy()

                self.ui_queue.put(('callback', deliver_error))
                return

            def deliver_result(result=result):
                try:
                    on_success(result)
                finally:
                    self.hide_busy()

            self.ui_queue.put(('callback', deliver_result))

        self.after(
            50,
            lambda: threading.Thread(
                target=worker,
                name='MentalOmegaRandomizerWorker',
                daemon=True,
            ).start(),
        )

    def process_ui_queue(self):
        try:
            try:
                while True:
                    kind, payload = self.ui_queue.get_nowait()
                    if kind == 'log':
                        message, error = payload
                        self.append_log_to_widgets(message, error=error)
                    elif kind == 'callback':
                        payload()
            except queue.Empty:
                pass
        finally:
            self.after(40, self.process_ui_queue)

    def on_settings_content_configure(self, event=None):
        if hasattr(self, 'settings_canvas'):
            self.settings_canvas.configure(scrollregion=self.settings_canvas.bbox('all'))

    def on_settings_canvas_configure(self, event):
        if hasattr(self, 'settings_canvas_window'):
            self.settings_canvas.itemconfigure(self.settings_canvas_window, width=event.width)
        if hasattr(self, 'settings_intro_label'):
            self.settings_intro_label.configure(wraplength=max(220, event.width - 32))

    def on_settings_mousewheel(self, event):
        if not hasattr(self, 'settings_canvas') or not hasattr(self, 'settings_tab'):
            return None
        if self.info_tabs.select() != str(self.settings_tab):
            return None
        pointer_x = self.winfo_pointerx()
        pointer_y = self.winfo_pointery()
        left = self.settings_canvas.winfo_rootx()
        top = self.settings_canvas.winfo_rooty()
        right = left + self.settings_canvas.winfo_width()
        bottom = top + self.settings_canvas.winfo_height()
        if not (left <= pointer_x <= right and top <= pointer_y <= bottom):
            return None
        steps = -1 if event.delta > 0 else 1
        self.settings_canvas.yview_scroll(steps, 'units')
        return 'break'

    def on_grid_content_configure(self, event=None):
        self.resize_grid_canvas_window()

    def on_grid_canvas_configure(self, event=None):
        self.resize_grid_canvas_window()

    def resize_grid_canvas_window(self):
        if not hasattr(self, 'grid_canvas_window'):
            return
        self.grid_content_frame.update_idletasks()
        width = max(
            self.grid_canvas.winfo_width(),
            self.grid_content_frame.winfo_reqwidth(),
        )
        height = max(
            self.grid_canvas.winfo_height(),
            self.grid_content_frame.winfo_reqheight(),
        )
        self.grid_canvas.itemconfigure(
            self.grid_canvas_window,
            width=width,
            height=height,
        )
        self.grid_canvas.configure(scrollregion=(0, 0, width, height))

    def grid_canvas_contains_pointer(self):
        if (
            not hasattr(self, 'grid_canvas')
            or self.active_progression_mode() != 'Grid Mode'
            or not self.grid_frame.winfo_ismapped()
        ):
            return False
        pointer_x = self.winfo_pointerx()
        pointer_y = self.winfo_pointery()
        left = self.grid_canvas.winfo_rootx()
        top = self.grid_canvas.winfo_rooty()
        return (
            left <= pointer_x <= left + self.grid_canvas.winfo_width()
            and top <= pointer_y <= top + self.grid_canvas.winfo_height()
        )

    def on_grid_mousewheel(self, event):
        if not self.grid_canvas_contains_pointer():
            return None
        self.grid_canvas.yview_scroll(-1 if event.delta > 0 else 1, 'units')
        return 'break'

    def on_grid_shift_mousewheel(self, event):
        if not self.grid_canvas_contains_pointer():
            return None
        self.grid_canvas.xview_scroll(-1 if event.delta > 0 else 1, 'units')
        return 'break'

    def focus_unlock_search(self, event=None):
        if hasattr(self, 'info_tabs') and hasattr(self, 'unlocks_tab'):
            self.info_tabs.select(self.unlocks_tab)
        if hasattr(self, 'unlock_search_entry'):
            self.unlock_search_entry.focus_set()
            self.unlock_search_entry.select_range(0, 'end')
        self.refresh_unlock_search()
        return 'break'

    def clear_unlock_search(self, event=None):
        self.unlock_search_var.set('')
        if hasattr(self, 'unlock_search_entry'):
            self.unlock_search_entry.focus_set()
        return 'break'

    def refresh_unlock_search(self, *args):
        if not hasattr(self, 'unlocks_text'):
            return

        term = self.unlock_search_var.get().strip()
        self.unlocks_text.tag_remove('search_match', '1.0', 'end')
        self.unlocks_text.tag_remove('search_current', '1.0', 'end')
        self.unlock_search_current = None
        if not term:
            if hasattr(self, 'unlock_search_status'):
                self.unlock_search_status.config(text='')
            return

        count = tk.IntVar(value=0)
        start = '1.0'
        first_match = None
        matches = 0
        while True:
            pos = self.unlocks_text.search(term, start, stopindex='end', nocase=True, count=count)
            if not pos or count.get() <= 0:
                break
            end = f'{pos}+{count.get()}c'
            if first_match is None:
                first_match = pos
            self.unlocks_text.tag_add('search_match', pos, end)
            matches += 1
            start = end

        if hasattr(self, 'unlock_search_status'):
            self.unlock_search_status.config(text=f'{matches} found' if matches else 'No match')
        if first_match:
            self.set_unlock_search_current(first_match, len(term))

    def set_unlock_search_current(self, pos, length):
        self.unlocks_text.tag_remove('search_current', '1.0', 'end')
        self.unlock_search_current = pos
        self.unlocks_text.tag_add('search_current', pos, f'{pos}+{length}c')
        self.unlocks_text.see(pos)

    def find_unlock_next(self, event=None):
        return self.find_unlock_match(forward=True)

    def find_unlock_previous(self, event=None):
        return self.find_unlock_match(forward=False)

    def find_unlock_match(self, forward=True):
        if not hasattr(self, 'unlocks_text'):
            return 'break'

        term = self.unlock_search_var.get().strip()
        if not term:
            self.focus_unlock_search()
            return 'break'

        count = tk.IntVar(value=0)
        if forward:
            start = f'{self.unlock_search_current}+1c' if self.unlock_search_current else '1.0'
            pos = self.unlocks_text.search(term, start, stopindex='end', nocase=True, count=count)
            if not pos:
                pos = self.unlocks_text.search(term, '1.0', stopindex='end', nocase=True, count=count)
        else:
            start = self.unlock_search_current if self.unlock_search_current else 'end'
            pos = self.unlocks_text.search(term, start, stopindex='1.0', backwards=True, nocase=True, count=count)
            if not pos:
                pos = self.unlocks_text.search(term, 'end', stopindex='1.0', backwards=True, nocase=True, count=count)

        if pos and count.get() > 0:
            self.set_unlock_search_current(pos, count.get())
        return 'break'

    def toggle_log(self):
        if self.log_visible_var.get():
            self.log_text.grid_remove()
            self.debug_complete_button.grid_remove()
            self.main_frame.rowconfigure(9, weight=0)
            self.log_toggle_button.configure(text='Show Launcher Log')
            self.log_visible_var.set(False)
        else:
            self.log_text.grid()
            self.debug_complete_button.grid()
            self.main_frame.rowconfigure(9, weight=1)
            self.log_toggle_button.configure(text='Hide Launcher Log')
            self.log_visible_var.set(True)
            self.log_text.see('end')

    def append_log(self, message, error=False):
        log_event(
            'launcher_message',
            level=logging.ERROR if error else logging.INFO,
            message=str(message),
        )
        if threading.current_thread() is not threading.main_thread():
            self.ui_queue.put(('log', (str(message), bool(error))))
            return
        self.append_log_to_widgets(message, error=error)

    def append_log_to_widgets(self, message, error=False):
        self.log_text.configure(state='normal')
        self.log_text.insert('end', f'{message}\n')
        if error:
            self.log_text.tag_add('error', 'end-2l', 'end-1c')
            self.log_text.tag_config(
                'error',
                foreground='#ff7b72' if self.dark_mode_var.get() else '#b00020',
            )
        self.log_text.configure(state='disabled')
        if self.log_visible_var.get():
            self.log_text.see('end')
        self.status_label.config(text='Error' if error else message[:120])

    def clear_log(self):
        self.log_text.configure(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.configure(state='disabled')

    def load_state(self):
        if not STATE_PATH.exists():
            return {}
        try:
            data = json.loads(read_text(STATE_PATH))
            if isinstance(data, dict):
                return data
        except Exception:
            log_event('state_load_failed', level=logging.ERROR, traceback=traceback.format_exc())
        return {}

    def migrate_state(self):
        if not self.state:
            return

        changed = False
        if 'mission_goal' not in self.state:
            self.state['mission_goal'] = len(self.state.get('mission_order', [])) or DEFAULT_MISSION_GOAL
            changed = True

        old_earned = self.state.get('earned_rewards', [])
        old_queue = self.state.get('reward_queue', [])
        if any('spawn' in reward for reward in old_earned + old_queue):
            old_earned = []
            old_queue = []
            self.state['earned_rewards'] = []
            self.state['reward_queue'] = []
            changed = True

        schema_changed = self.state.get('check_schema_version') != CHECK_SCHEMA_VERSION
        if self.missions and (schema_changed or 'mission_checks' not in self.state):
            self.state['mission_checks'] = self.build_mission_checks(
                self.state.get('mission_order', []),
                self.state.get('seed', ''),
                [] if schema_changed else old_earned,
                self.state.get('completed_missions', []),
                preserved_checks={} if schema_changed else self.state.get('mission_checks', {}),
                rewards_per_check=self.state.get('rewards_per_check', DEFAULT_REWARDS_PER_CHECK),
                progression_mode=self.state.get('progression_mode'),
                grid=self.state.get('grid'),
            )
            self.state['earned_rewards'] = self.earned_rewards_from_checks()
            self.state['reward_queue'] = [
                reward
                for code in self.state.get('mission_order', [])
                for check in self.state['mission_checks'].get(code, [])
                for reward in check_rewards(check)
            ]
            self.state['check_schema_version'] = CHECK_SCHEMA_VERSION
            changed = True

        completed = self.state.setdefault('completed_missions', [])
        mission_checks = self.state.get('mission_checks', {})
        for code, checks in mission_checks.items():
            victory_unlocked = any(check.get('id') == 'victory' and check.get('unlocked') for check in checks)
            if victory_unlocked or code in completed:
                if code not in completed:
                    completed.append(code)
                    changed = True
                for check in checks:
                    if not check.get('unlocked'):
                        check['unlocked'] = True
                        changed = True
                    if check.pop('released', None) is not None:
                        changed = True

        raw_failure_stacks = self.state.get('mission_failure_stacks', {})
        if not isinstance(raw_failure_stacks, dict):
            raw_failure_stacks = {}
        valid_codes = set(self.state.get('mission_order', []))
        normalized_failure_stacks = {}
        for code, value in raw_failure_stacks.items():
            try:
                count = max(0, int(value))
            except (TypeError, ValueError):
                count = 0
            if code in valid_codes and code not in completed and count:
                normalized_failure_stacks[code] = count
        if self.state.get('mission_failure_stacks') != normalized_failure_stacks:
            self.state['mission_failure_stacks'] = normalized_failure_stacks
            changed = True

        raw_assistance_units = self.state.get('mission_assistance_units', {})
        if not isinstance(raw_assistance_units, dict):
            raw_assistance_units = {}
        normalized_assistance_units = {}
        for code, unit_ids in raw_assistance_units.items():
            if code not in valid_codes or code in completed or not isinstance(unit_ids, list):
                continue
            normalized = sorted({
                str(unit_id).upper()
                for unit_id in unit_ids
                if BUFF_TARGETS.get(str(unit_id).upper(), {}).get('category')
                in {'infantry', 'units', 'aircraft'}
            })
            if normalized:
                normalized_assistance_units[code] = normalized
        if self.state.get('mission_assistance_units') != normalized_assistance_units:
            self.state['mission_assistance_units'] = normalized_assistance_units
            changed = True

        if self.state.get('progression_mode') == 'Grid Mode' and isinstance(self.state.get('grid'), dict):
            existing_grid = self.state['grid']
            if existing_grid.get('layout_version') != 3:
                try:
                    self.state['grid'] = create_grid(
                        self.state.get('mission_order', []),
                        bool(existing_grid.get('two_start_positions')),
                    )
                    changed = True
                except ValueError:
                    log_event(
                        'grid_layout_migration_failed',
                        level=logging.ERROR,
                        traceback=traceback.format_exc(),
                    )
            before = {
                code: node.get('state')
                for code, node in self.state['grid'].get('nodes', {}).items()
            }
            after = refresh_grid_states(self.state['grid'], completed)
            if after != before:
                changed = True
            goal_code = self.state['grid'].get('goal')
            if goal_code in completed:
                released_rewards, released_checks = self.release_remaining_grid_rewards()
                if released_checks:
                    changed = True
                    log_event(
                        'grid_goal_rewards_released_on_migration',
                        seed=self.state.get('seed', ''),
                        goal_code=goal_code,
                        released_rewards=len(released_rewards),
                        released_checks=len(released_checks),
                    )

        if changed:
            self.state['earned_rewards'] = self.earned_rewards_from_checks()

        if changed:
            self.save_state()

    def save_state(self):
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(self.state, indent=2), encoding='utf-8')

    def config_reward_settings(self):
        generation_config = self.config.get('generation', {})
        enabled_reward_types = generation_config.get('enabled_reward_types', ['access', 'buff', 'superweapon'])
        enabled_buff_types = generation_config.get('enabled_buff_types')
        if not isinstance(enabled_buff_types, list):
            enabled_buff_types = [buff_type['id'] for buff_type in BUFF_TYPES]
        enabled_buff_types = [
            str(buff_type)
            for buff_type in enabled_buff_types
            if str(buff_type) in {item['id'] for item in BUFF_TYPES}
        ]
        randomize_access = bool(generation_config.get('randomize_unit_access', 'access' in enabled_reward_types))
        start_with_tier_one_units = bool(generation_config.get('start_with_tier_one_units', False))
        include_buffs = bool(generation_config.get('include_buff_rewards', 'buff' in enabled_reward_types))
        include_superweapons = bool(generation_config.get('include_superweapon_rewards', True))
        include_secondary_superweapons = bool(
            generation_config.get('include_secondary_superweapon_rewards', True)
        )
        include_aid_powers = bool(generation_config.get('include_aid_power_rewards', True))
        include_defensive_buildings = bool(generation_config.get('include_defensive_buildings', True))
        unlimited_hero_units = bool(generation_config.get('unlimited_hero_units', False))
        if unlimited_hero_units:
            enabled_buff_types = [
                buff_type for buff_type in enabled_buff_types
                if buff_type != 'build_limit'
            ]
        share_chaos_role_buffs = bool(generation_config.get('share_chaos_role_buffs', False))
        buff_allied_helpers = bool(generation_config.get('buff_allied_helpers', False))
        failure_assistance = bool(generation_config.get('failure_assistance', False))
        if generation_config.get('reward_mode') == 'Chaos (Experimental)':
            randomize_access = True
        return {
            'randomize_unit_access': randomize_access,
            'start_with_tier_one_units': start_with_tier_one_units,
            'include_defensive_buildings': include_defensive_buildings,
            'unlimited_hero_units': unlimited_hero_units,
            'share_chaos_role_buffs': share_chaos_role_buffs,
            'buff_allied_helpers': buff_allied_helpers,
            'failure_assistance': failure_assistance,
            'include_buff_rewards': include_buffs,
            'include_superweapon_rewards': include_superweapons,
            'include_secondary_superweapon_rewards': include_secondary_superweapons,
            'include_aid_power_rewards': include_aid_powers,
            'enabled_reward_types': [
                reward_type
                for reward_type, enabled in (
                    ('access', randomize_access),
                    ('buff', include_buffs),
                    ('superweapon', include_superweapons),
                    ('secondary_superweapon', include_secondary_superweapons),
                    ('aid_power', include_aid_powers),
                )
                if enabled
            ],
            'enabled_buff_types': enabled_buff_types,
        }

    def current_reward_settings(self):
        if 'randomize_unit_access_var' not in self.__dict__:
            return self.config_reward_settings()
        chaos_mode = self.reward_mode_var.get() == 'Chaos (Experimental)'
        randomize_access = chaos_mode or bool(self.randomize_unit_access_var.get())
        start_with_tier_one_units = bool(self.start_with_tier_one_units_var.get())
        include_defensive_buildings = bool(self.include_defensive_buildings_var.get())
        unlimited_hero_units = bool(self.unlimited_hero_units_var.get())
        share_chaos_role_buffs = bool(self.share_chaos_role_buffs_var.get())
        buff_allied_helpers = bool(self.buff_allied_helpers_var.get())
        failure_assistance = bool(self.failure_assistance_var.get())
        include_buffs = bool(self.include_buff_rewards_var.get())
        include_superweapons = bool(self.include_superweapon_rewards_var.get())
        include_secondary_superweapons = bool(self.include_secondary_superweapon_rewards_var.get())
        include_aid_powers = bool(self.include_aid_power_rewards_var.get())
        enabled_buff_types = [
            buff_type['id']
            for buff_type in BUFF_TYPES
            if self.buff_type_vars[buff_type['id']].get()
        ]
        if unlimited_hero_units:
            enabled_buff_types = [
                buff_type for buff_type in enabled_buff_types
                if buff_type != 'build_limit'
            ]
        return {
            'randomize_unit_access': randomize_access,
            'start_with_tier_one_units': start_with_tier_one_units,
            'include_defensive_buildings': include_defensive_buildings,
            'unlimited_hero_units': unlimited_hero_units,
            'share_chaos_role_buffs': share_chaos_role_buffs,
            'buff_allied_helpers': buff_allied_helpers,
            'failure_assistance': failure_assistance,
            'include_buff_rewards': include_buffs,
            'include_superweapon_rewards': include_superweapons,
            'include_secondary_superweapon_rewards': include_secondary_superweapons,
            'include_aid_power_rewards': include_aid_powers,
            'enabled_reward_types': [
                reward_type
                for reward_type, enabled in (
                    ('access', randomize_access),
                    ('buff', include_buffs),
                    ('superweapon', include_superweapons),
                    ('secondary_superweapon', include_secondary_superweapons),
                    ('aid_power', include_aid_powers),
                )
                if enabled
            ],
            'enabled_buff_types': enabled_buff_types,
        }

    def active_reward_settings(self):
        override = self.__dict__.get('_reward_settings_override')
        if override is not None:
            settings = dict(override)
        elif self.state and isinstance(self.state.get('reward_settings'), dict):
            settings = dict(self.state.get('reward_settings', {}))
        else:
            settings = self.current_reward_settings()
        settings.setdefault('randomize_unit_access', True)
        settings.setdefault('start_with_tier_one_units', False)
        settings.setdefault('include_defensive_buildings', True)
        settings.setdefault('unlimited_hero_units', False)
        settings.setdefault('share_chaos_role_buffs', False)
        settings.setdefault(
            'buff_allied_helpers',
            bool(self.config.get('generation', {}).get('buff_allied_helpers', False)),
        )
        settings.setdefault('failure_assistance', False)
        # Legacy seeds may contain experimental_player_unit_clones. Clone
        # isolation is mandatory now, so the stored flag is deliberately ignored.
        settings.pop('experimental_player_unit_clones', None)
        if self.active_reward_mode() == 'Chaos (Experimental)':
            settings['randomize_unit_access'] = True
        settings.setdefault('include_buff_rewards', True)
        settings.setdefault('include_superweapon_rewards', False)
        settings.setdefault('include_secondary_superweapon_rewards', False)
        settings.setdefault('include_aid_power_rewards', False)
        if not isinstance(settings.get('enabled_buff_types'), list):
            settings['enabled_buff_types'] = [buff_type['id'] for buff_type in BUFF_TYPES]
        if settings['unlimited_hero_units']:
            settings['enabled_buff_types'] = [
                buff_type for buff_type in settings['enabled_buff_types']
                if buff_type != 'build_limit'
            ]
        return settings

    def randomize_unit_access_enabled(self):
        return bool(self.active_reward_settings().get('randomize_unit_access', True))

    def starting_tier_one_unit_ids_for_seed(self, seed, reward_settings=None):
        settings = reward_settings or self.active_reward_settings()
        if not settings.get('start_with_tier_one_units', False):
            return []
        if self.active_reward_mode() == 'Chaos (Experimental)':
            rng = random.Random(f'{seed}:starting-tier-one')
            return list(random_chaos_tier_one_unit_ids(rng))

        generation_context = self.__dict__.get('_seed_generation_context') or {}
        selected = generation_context.get('campaign_filter')
        if selected is None:
            selected = self.campaign_var.get() if hasattr(self, 'campaign_var') else 'All Campaigns'
        families = {
            'Allies': ('allies',),
            'Soviets': ('soviets',),
            'Epsilon': ('epsilon',),
            'Foehn': ('allies', 'soviets'),
            'All Campaigns': ('allies', 'soviets', 'epsilon'),
        }.get(selected, ('allies', 'soviets', 'epsilon'))
        return list(tier_one_unit_ids(families))

    def active_starting_tier_one_unit_ids(self):
        override = self.__dict__.get('_starting_unit_ids_override')
        if override is not None:
            return list(override)
        if self.state:
            return [
                str(unit_id).upper()
                for unit_id in self.state.get('starting_unit_ids', [])
                if unit_id
            ]
        return self.starting_tier_one_unit_ids_for_seed(
            self.seed_var.get() if hasattr(self, 'seed_var') else '',
        )

    def share_chaos_role_buffs_enabled(self):
        return bool(
            self.active_reward_mode() == 'Chaos (Experimental)'
            and self.active_reward_settings().get('share_chaos_role_buffs', False)
        )

    def failure_assistance_enabled(self):
        return bool(self.active_reward_settings().get('failure_assistance', False))

    def mission_failure_stack(self, code):
        if not self.state or not code:
            return 0
        try:
            return max(0, int(self.state.get('mission_failure_stacks', {}).get(code, 0)))
        except (TypeError, ValueError):
            return 0

    def cache_mission_assistance_units(self, code, unit_ids):
        if not self.state or not code or code not in self.state.get('mission_order', []):
            return
        normalized = sorted({
            str(unit_id).upper()
            for unit_id in unit_ids
            if BUFF_TARGETS.get(str(unit_id).upper(), {}).get('category')
            in {'infantry', 'units', 'aircraft'}
        })
        cached = self.state.setdefault('mission_assistance_units', {})
        if cached.get(code) == normalized:
            return
        if normalized:
            cached[code] = normalized
        else:
            cached.pop(code, None)
        self.save_state()

    def record_failed_mission_attempt(self, code, source):
        if (
            not self.state
            or not self.failure_assistance_enabled()
            or not code
            or code not in self.state.get('mission_order', [])
            or self.is_mission_complete(code)
        ):
            return False

        stacks = self.state.setdefault('mission_failure_stacks', {})
        next_stack = self.mission_failure_stack(code) + 1
        stacks[code] = next_stack
        self.save_state()
        self.append_log(
            f'{source}: {code} now has {next_stack} retry assistance stack(s). '
            'They will apply the next time this mission is launched.'
        )
        log_event(
            'mission_failure_assistance_added',
            seed=self.state.get('seed', ''),
            code=code,
            source=source,
            stacks=next_stack,
        )
        self.refresh_grid_tiles({code})
        self.refresh_progress_view()
        return True

    def active_reward_mode(self):
        generation_context = self.__dict__.get('_seed_generation_context') or {}
        if generation_context.get('reward_mode'):
            return generation_context['reward_mode']
        if self.__dict__.get('_reward_settings_override') is not None and hasattr(self, 'reward_mode_var'):
            return self.reward_mode_var.get()
        if self.state:
            return self.state.get('reward_mode', REWARD_MODES[0])
        if hasattr(self, 'reward_mode_var'):
            return self.reward_mode_var.get()
        return REWARD_MODES[0]

    def save_launcher_config(self, seed, mission_goal, rewards_per_check):
        self.config['dark_mode'] = bool(self.dark_mode_var.get())
        self.config['hide_reward_details'] = bool(self.hide_reward_details_var.get())
        self.config['seed'] = seed
        self.config['campaign_filter'] = self.campaign_var.get()
        self.config['mission_goal'] = mission_goal
        self.config['progression_mode'] = self.progression_mode_var.get()
        self.config.pop('grid_width', None)
        self.config.pop('grid_height', None)
        self.config['grid_two_start_positions'] = bool(self.grid_two_starts_var.get())
        self.config['rewards_per_objective'] = rewards_per_check
        self.config['difficulty'] = self.difficulty_var.get()
        self.config['game_speed'] = self.game_speed_var.get()
        reward_settings = self.current_reward_settings()
        self.config.setdefault('generation', {})['starting_unlocked_missions'] = STARTING_UNLOCKED_MISSIONS
        self.config['generation']['include_no_build_missions'] = bool(
            self.include_no_build_missions_var.get()
        )
        self.config['generation']['include_no_build_production_missions'] = bool(
            self.include_no_build_production_missions_var.get()
        )
        self.config['generation']['prioritize_no_build_missions'] = bool(
            self.prioritize_no_build_missions_var.get()
        )
        self.config['generation']['buff_allied_helpers'] = bool(self.buff_allied_helpers_var.get())
        self.config['generation']['failure_assistance'] = reward_settings['failure_assistance']
        self.config['generation'].pop('experimental_player_unit_clones', None)
        self.config['generation']['enabled_reward_types'] = reward_settings['enabled_reward_types']
        self.config['generation']['randomize_unit_access'] = reward_settings['randomize_unit_access']
        self.config['generation']['start_with_tier_one_units'] = reward_settings['start_with_tier_one_units']
        self.config['generation']['include_defensive_buildings'] = reward_settings['include_defensive_buildings']
        self.config['generation']['unlimited_hero_units'] = reward_settings['unlimited_hero_units']
        self.config['generation']['share_chaos_role_buffs'] = reward_settings['share_chaos_role_buffs']
        self.config['generation']['include_buff_rewards'] = reward_settings['include_buff_rewards']
        self.config['generation']['include_superweapon_rewards'] = reward_settings['include_superweapon_rewards']
        self.config['generation']['include_secondary_superweapon_rewards'] = reward_settings['include_secondary_superweapon_rewards']
        self.config['generation']['include_aid_power_rewards'] = reward_settings['include_aid_power_rewards']
        self.config['generation']['enabled_buff_types'] = reward_settings['enabled_buff_types']
        self.config['generation']['reward_mode'] = self.reward_mode_var.get()
        self.config['generation'].pop('close_game_on_victory', None)
        self.config.setdefault('archipelago', {}).setdefault('enabled', False)
        self.config['archipelago'].setdefault('slot_name', self.config.get('player_name', 'Commander'))
        save_config(self.config)

    def save_current_launcher_config(self):
        self.save_launcher_config(
            self.seed_var.get(),
            self.selected_mission_goal(),
            self.selected_rewards_per_check(),
        )

    def mission_lookup(self):
        return self._mission_by_code

    def objective_templates_for_code(self, code):
        mission = self.mission_lookup().get(code, {})
        objectives = mission.get('objectives') or []

        if objectives:
            templates = [
                (
                    f'objective_{idx}',
                    f'Objective {idx}',
                    objective,
                )
                for idx, objective in enumerate(objectives, start=1)
            ]
            templates.append(('victory', 'Mission Victory', 'Win the mission.'))
            return templates

        templates = [
            (
                f'objective_{idx}',
                f'Objective {idx}',
                'Objective details are not available yet. This mission probably needs map trigger analysis.',
            )
            for idx in range(1, FALLBACK_OBJECTIVE_COUNT + 1)
        ]
        templates.append(('victory', 'Mission Victory', 'Win the mission.'))
        return templates

    def foehn_standard_bundles_enabled(self):
        generation_context = self.__dict__.get('_seed_generation_context') or {}
        selected = generation_context.get('campaign_filter')
        if selected is None:
            selected = (
                self.campaign_var.get()
                if hasattr(self, 'campaign_var')
                else (self.state or {}).get('campaign_filter', '')
            )
        return selected == 'Foehn' and self.active_reward_mode() == 'Standard'

    def active_launch_reward_factions(self):
        """Return factions whose saved rewards may affect this launch.

        Existing state files retain their original serialized reward data.
        Canonicalizing and filtering again at launch prevents an old catalog
        mistake from leaking foreign technology into a single-faction seed.
        """
        if self.active_reward_mode() == 'Chaos (Experimental)':
            return None
        selected = (self.state or {}).get('campaign_filter', '')
        if selected == 'Foehn':
            # Foehn Standard intentionally uses bundled Allied/Soviet access;
            # native Foehn powers may also be valid campaign rewards.
            return {'Allies', 'Soviets', 'Foehn'}
        if selected in {'Allies', 'Soviets', 'Epsilon'}:
            return {selected}
        return None

    def active_launch_rewards(self):
        rewards = canonical_rewards(
            self.earned_rewards_from_checks() if self.state else []
        )
        allowed_factions = self.active_launch_reward_factions()
        if allowed_factions is None:
            return rewards
        return [
            reward
            for reward in rewards
            if (
                not reward.get('factions')
                or allowed_factions.intersection(reward.get('factions', ()))
            )
        ]

    def active_unlocked_reward_tech_ids(self):
        return unlocked_reward_tech_ids(self.active_launch_rewards())

    def mission_effective_unlocked_tech_ids(
        self,
        mission,
        lines,
        additional_tech_ids=(),
    ):
        """Limit Standard access to the factions this map can really use."""
        additional = {
            str(unit_id).upper()
            for unit_id in (additional_tech_ids or ())
            if unit_id
        }
        unlocked = set(self.active_unlocked_reward_tech_ids())
        if self.active_reward_mode() == 'Chaos (Experimental)':
            return unlocked | additional

        records = map_house_records(lines)
        family_names = {
            'allies': 'Allies',
            'soviets': 'Soviets',
            'epsilon': 'Epsilon',
            'foehn': 'Foehn',
        }
        primary_house = player_house_from_map(lines, records=records)
        primary_family = country_family(records.get(primary_house, {}))
        player_factions = (
            {family_names[primary_family]}
            if primary_family in family_names
            else set()
        )
        if not player_factions:
            fallback_faction = normalize_faction(mission.get('side', ''))
            if fallback_faction:
                player_factions.add(fallback_faction)

        return additional | {
            unit_id
            for unit_id in unlocked
            if not BUFF_TARGETS.get(unit_id, {}).get('factions')
            or player_factions.intersection(
                BUFF_TARGETS.get(unit_id, {}).get('factions', ())
            )
        }

    def bundle_foehn_standard_access(self, pool):
        """Bundle Allied/Soviet role peers into one Foehn access reward."""
        if not self.foehn_standard_bundles_enabled():
            return list(pool)

        access_by_tech = {}
        for reward in pool:
            if reward.get('kind') in {'buff', 'superweapon'}:
                continue
            tech_ids = tech_ids_for_rewards([reward])
            if len(tech_ids) != 1:
                continue
            tech_id = next(iter(tech_ids))
            factions = BUFF_TARGETS.get(tech_id, {}).get('factions') or []
            if len(factions) == 1 and factions[0] in {'Allies', 'Soviets'}:
                access_by_tech[tech_id] = reward

        bundled = []
        consumed = set()
        for reward in pool:
            if reward.get('kind') in {'buff', 'superweapon'}:
                bundled.append(reward)
                continue
            tech_ids = tech_ids_for_rewards([reward])
            if len(tech_ids) != 1:
                bundled.append(reward)
                continue
            tech_id = next(iter(tech_ids))
            if tech_id in consumed:
                continue
            if tech_id not in access_by_tech:
                bundled.append(reward)
                consumed.add(tech_id)
                continue

            peers = [
                peer
                for peer in unit_role_equivalents(tech_id)
                if peer in access_by_tech
            ]
            peer_factions = {
                (BUFF_TARGETS.get(peer, {}).get('factions') or [''])[0]
                for peer in peers
            }
            if not {'Allies', 'Soviets'}.issubset(peer_factions):
                bundled.append(reward)
                consumed.add(tech_id)
                continue

            peers.sort(key=self.unit_faction_sort_key)
            rules = {}
            source_names = []
            for peer in peers:
                peer_reward = access_by_tech[peer]
                source_names.append(peer_reward.get('name', peer))
                for section, values in peer_reward.get('rules', {}).items():
                    rules[section] = dict(values)

            labels = [unit_display_label(peer) for peer in peers]
            bundled.append({
                'name': 'Foehn Shared Access: ' + ' / '.join(labels),
                'description': (
                    'Unlocks the equivalent Allied and Soviet technologies '
                    'as one Foehn campaign reward.'
                ),
                'rules': rules,
                'factions': ['Allies', 'Soviets'],
                'bundle_units': peers,
                'bundle_reward_names': source_names,
            })
            consumed.update(peers)
        return bundled

    def reward_pool_for_code(self, code):
        reward_mode = self.active_reward_mode()
        if reward_mode == 'Chaos (Experimental)':
            return self.configured_reward_pool()
        factions = self.reward_factions_for_code(code)
        generation_context = self.__dict__.get('_seed_generation_context') or {}
        selected = generation_context.get('campaign_filter')
        if selected is None:
            selected = self.campaign_var.get() if hasattr(self, 'campaign_var') else ''
        pool = [
            reward
            for reward in REWARD_POOL
            if (
                not reward.get('factions')
                or factions.intersection(reward.get('factions', []))
                or (
                    selected == 'Foehn'
                    and reward.get('kind') == 'superweapon'
                    and 'Foehn' in reward.get('factions', [])
                )
            )
        ]
        return self.bundle_foehn_standard_access(self.filter_reward_pool(pool))

    def configured_reward_pool(self):
        return self.filter_reward_pool(REWARD_POOL)

    def reward_is_defensive_building(self, reward):
        if reward.get('access_category') == 'defense':
            return True
        unit_id = reward.get('unit')
        return bool(unit_id and BUFF_TARGETS.get(unit_id, {}).get('category') == 'defenses')

    def filter_reward_pool(self, pool):
        reward_settings = self.active_reward_settings()
        starting_unit_ids = set(self.active_starting_tier_one_unit_ids())
        randomize_access = bool(reward_settings.get('randomize_unit_access', True))
        include_buffs = bool(reward_settings.get('include_buff_rewards', True))
        include_superweapons = bool(reward_settings.get('include_superweapon_rewards', False))
        include_secondary_superweapons = bool(
            reward_settings.get('include_secondary_superweapon_rewards', False)
        )
        include_aid_powers = bool(reward_settings.get('include_aid_power_rewards', False))
        include_defensive_buildings = bool(reward_settings.get('include_defensive_buildings', True))
        enabled_buff_types = set(reward_settings.get('enabled_buff_types') or [])
        if reward_settings.get('unlimited_hero_units'):
            enabled_buff_types.discard('build_limit')
        chaos_mode = self.active_reward_mode() == 'Chaos (Experimental)'
        return [
            reward
            for reward in pool
            if (
                (
                    reward.get('kind') == 'buff'
                    and include_buffs
                    and (include_defensive_buildings or not self.reward_is_defensive_building(reward))
                    and reward.get('buff_type') in enabled_buff_types
                    and not (
                        chaos_mode
                        and reward.get('buff_type') == 'production'
                        and not reward.get('global_buff')
                    )
                )
                or (
                    reward.get('kind') == 'superweapon'
                    and (
                        (
                            reward.get('power_category', 'offensive') == 'offensive'
                            and include_superweapons
                        )
                        or (
                            reward.get('power_category') == 'secondary'
                            and include_secondary_superweapons
                        )
                        or (
                            reward.get('power_category') == 'aid'
                            and include_aid_powers
                        )
                    )
                )
                or (
                    reward.get('kind') not in {'buff', 'superweapon'}
                    and randomize_access
                    and (include_defensive_buildings or not self.reward_is_defensive_building(reward))
                    and not tech_ids_for_rewards([reward]).intersection(starting_unit_ids)
                )
            )
        ]

    def reward_factions_for_code(self, code):
        generation_context = self.__dict__.get('_seed_generation_context') or {}
        selected = generation_context.get('campaign_filter')
        if selected is None:
            selected = self.campaign_var.get() if hasattr(self, 'campaign_var') else ''
        if selected == 'Foehn':
            return {'Allies', 'Soviets'}
        if selected in {'Allies', 'Soviets', 'Epsilon'}:
            return {selected}
        return {'Allies', 'Soviets', 'Epsilon'}

    def state_objective_summary(self, mission_codes):
        return {
            code: [hint for _, _, hint in self.objective_templates_for_code(code)]
            for code in mission_codes
        }

    def sync_state_mission_objectives(self):
        if not self.state or not self.missions:
            return

        mission_codes = self.state.get('mission_order', [])
        summary = self.state_objective_summary(mission_codes)
        schema_current = self.state.get('check_schema_version') == CHECK_SCHEMA_VERSION
        checks_present = 'mission_checks' in self.state
        if schema_current and checks_present and self.state.get('mission_objectives') == summary:
            return

        self.state['mission_checks'] = self.build_mission_checks(
            mission_codes,
            self.state.get('seed', ''),
            self.state.get('earned_rewards', []) if schema_current else [],
            self.state.get('completed_missions', []),
            preserved_checks=self.state.get('mission_checks', {}) if schema_current else {},
            rewards_per_check=self.state.get('rewards_per_check', DEFAULT_REWARDS_PER_CHECK),
            progression_mode=self.state.get('progression_mode'),
            grid=self.state.get('grid'),
        )
        self.state['mission_objectives'] = summary
        grid = self.state.get('grid', {})
        if (
            self.state.get('progression_mode') == 'Grid Mode'
            and grid.get('goal') in self.state.get('completed_missions', [])
        ):
            released_rewards, released_checks = self.release_remaining_grid_rewards()
            if released_checks:
                log_event(
                    'grid_goal_rewards_released_after_check_sync',
                    seed=self.state.get('seed', ''),
                    goal_code=grid.get('goal'),
                    released_rewards=len(released_rewards),
                    released_checks=len(released_checks),
                )
        self.state['earned_rewards'] = self.earned_rewards_from_checks()
        self.state['reward_queue'] = [
            reward
            for code in mission_codes
            for check in self.state['mission_checks'].get(code, [])
            for reward in check_rewards(check)
        ]
        self.state['check_schema_version'] = CHECK_SCHEMA_VERSION
        self.save_state()

    def build_mission_checks(
        self,
        mission_codes,
        seed,
        earned_rewards=None,
        completed_missions=None,
        preserved_checks=None,
        rewards_per_check=DEFAULT_REWARDS_PER_CHECK,
        progression_mode=None,
        grid=None,
    ):
        templates_by_code = {code: self.objective_templates_for_code(code) for code in mission_codes}
        earned_rewards = list(earned_rewards or [])
        completed_missions = list(completed_missions or [])
        rewards_per_check = clamp_int(rewards_per_check, 1, MAX_REWARDS_PER_CHECK, DEFAULT_REWARDS_PER_CHECK)
        completed = set(completed_missions)
        completed_rewards = {
            code: reward
            for code, reward in zip(completed_missions, earned_rewards)
        }
        preserved_checks = preserved_checks or {}
        checks = {}
        slots_by_code = {
            code: len(templates_by_code[code]) * rewards_per_check
            for code in mission_codes
        }
        rewards_by_code = self.generate_seed_reward_plan(
            mission_codes,
            seed,
            slots_by_code,
            progression_mode=progression_mode,
            grid=grid,
        )

        for code in mission_codes:
            mission_checks = []
            rewards = rewards_by_code.get(code, [])
            reward_index = 0
            old_checks = {
                check.get('id'): check
                for check in preserved_checks.get(code, [])
                if check.get('id')
            }
            templates = templates_by_code[code]
            for check_id, name, hint in templates:
                old_check = old_checks.get(check_id)
                if (
                    old_check
                    and (old_check.get('unlocked') or old_check.get('released'))
                    and check_rewards(old_check)
                ):
                    rewards_for_check = check_rewards(old_check)
                    unlocked = bool(old_check.get('unlocked'))
                    released = bool(old_check.get('released')) and not unlocked
                elif check_id == 'objective_1' and code in completed_rewards:
                    rewards_for_check = canonical_rewards(completed_rewards[code])
                    unlocked = code in completed
                    released = False
                else:
                    rewards_for_check = rewards[reward_index:reward_index + rewards_per_check]
                    unlocked = False
                    released = False
                reward_index += rewards_per_check
                primary_reward = rewards_for_check[0] if rewards_for_check else {}
                mission_checks.append({
                    'id': check_id,
                    'name': name,
                    'hint': hint,
                    'reward': primary_reward,
                    'rewards': rewards_for_check,
                    'unlocked': unlocked or code in completed,
                    'released': released and code not in completed,
                })
            checks[code] = mission_checks

        return checks

    def generate_seed_reward_plan(
        self,
        mission_codes,
        seed,
        slots_by_code,
        progression_mode=None,
        grid=None,
    ):
        rng = random.Random(f'{seed}:seed-rewards')
        require_access_for_unit_buffs = self.randomize_unit_access_enabled()
        share_chaos_role_buffs = self.share_chaos_role_buffs_enabled()
        used_access_names = set()
        seed_unlocked_tech_ids = (
            set(self.active_starting_tier_one_unit_ids())
            | set(AMPHIBIOUS_TRANSPORT_UNIT_IDS)
        )
        buff_counts = {}
        unit_buff_counts = {}
        global_buff_counts = {}
        plan = {
            code: [None] * max(0, int(slots_by_code.get(code, 0)))
            for code in mission_codes
        }
        global_index = 0

        if progression_mode is None:
            progression_mode = (
                self.state.get('progression_mode')
                if getattr(self, 'state', None)
                else self.progression_mode_var.get()
                if hasattr(self, 'progression_mode_var')
                else DEFAULT_PROGRESSION_MODE
            )
        if grid is None and getattr(self, 'state', None):
            grid = self.state.get('grid')

        def unit_access_earned(unit):
            return (
                unit in seed_unlocked_tech_ids
                or (
                    share_chaos_role_buffs
                    and bool(unit_role_equivalents(unit).intersection(seed_unlocked_tech_ids))
                )
            )

        def buff_count_key(reward):
            unit = reward.get('unit')
            if share_chaos_role_buffs and unit and not reward.get('global_buff'):
                return (reward.get('buff_type'), tuple(sorted(unit_role_equivalents(unit))))
            return reward.get('name')

        def record_unit_buff(unit):
            units = unit_role_equivalents(unit) if share_chaos_role_buffs else {unit}
            for affected_unit in units:
                unit_buff_counts[affected_unit] = unit_buff_counts.get(affected_unit, 0) + 1

        # Reward settings are seed-wide, and the current faction selector does
        # not vary by mission code. Build/canonicalize each distinct faction
        # pool once instead of repeating it for every mission. Buff metadata is
        # also static during the draw and is therefore calculated once here.
        pool_cache = {}
        pool_by_code = {}
        access_by_code = {}
        buffs_by_code = {}
        for code in mission_codes:
            pool_key = tuple(sorted(self.reward_factions_for_code(code)))
            if pool_key not in pool_cache:
                canonical_pool = tuple(
                    canonical_reward(reward)
                    for reward in self.reward_pool_for_code(code)
                )
                access_template = tuple(
                    reward for reward in canonical_pool if reward.get('kind') != 'buff'
                )
                buff_metadata = tuple(
                    (
                        reward,
                        buff_stack_limit(reward),
                        buff_count_key(reward),
                        reward.get('unit'),
                        bool(reward.get('global_buff') or not reward.get('unit')),
                        reward.get('name'),
                    )
                    for reward in canonical_pool
                    if reward.get('kind') == 'buff'
                )
                pool_cache[pool_key] = (canonical_pool, access_template, buff_metadata)
            canonical_pool, access_template, buff_metadata = pool_cache[pool_key]
            access = list(access_template)
            rng.shuffle(access)
            pool_by_code[code] = canonical_pool
            access_by_code[code] = access
            buffs_by_code[code] = buff_metadata

        def is_unit_access(reward):
            return any(
                BUFF_TARGETS.get(unit_id, {}).get('category')
                in {'infantry', 'units', 'aircraft'}
                for unit_id in tech_ids_for_rewards([reward])
            )

        def draw_access(code, unit_only=False):
            access = access_by_code.get(code, [])
            for index in range(len(access) - 1, -1, -1):
                reward = access[index]
                name = reward.get('name')
                if name in used_access_names:
                    access.pop(index)
                    continue
                if unit_only and not is_unit_access(reward):
                    continue
                access.pop(index)
                used_access_names.add(name)
                return dict(reward)
            return None

        def draw_buff(code, prefer_global=False):
            buffs = buffs_by_code.get(code, [])
            if not buffs:
                return None

            unit_candidates = []
            global_candidates = []
            for reward, limit, count_key, unit, is_global, name in buffs:
                if limit is not None and buff_counts.get(count_key, 0) >= limit:
                    continue
                if is_global:
                    count = global_buff_counts.get(name, 0)
                    if count < MAX_GLOBAL_BUFF_REPEATS_PER_SEED:
                        global_candidates.append(reward)
                elif not require_access_for_unit_buffs or unit_access_earned(unit):
                    unit_candidates.append(reward)

            if prefer_global and global_candidates:
                candidates = global_candidates
            elif unit_candidates:
                # Spread positive rewards across the faction roster before
                # stacking more upgrades on units that already received one.
                # This is especially important for buffs-only seeds, where a
                # large reward count should visibly cover the whole army.
                least_buffs = min(unit_buff_counts.get(reward.get('unit'), 0) for reward in unit_candidates)
                candidates = [
                    reward
                    for reward in unit_candidates
                    if unit_buff_counts.get(reward.get('unit'), 0) == least_buffs
                ]
            else:
                candidates = global_candidates
            if not candidates:
                return None

            reward = dict(rng.choice(candidates))
            if reward.get('global_buff') or not reward.get('unit'):
                name = reward.get('name')
                global_buff_counts[name] = global_buff_counts.get(name, 0) + 1
            count_key = buff_count_key(reward)
            buff_counts[count_key] = buff_counts.get(count_key, 0) + 1
            unit = reward.get('unit')
            if unit:
                record_unit_buff(unit)
            return reward

        def draw_repeatable_fallback(code):
            pool = [dict(reward) for reward in pool_by_code.get(code, ())]
            buffs = [reward for reward in pool if reward.get('kind') == 'buff']
            candidates = []
            for reward in buffs or pool:
                limit = buff_stack_limit(reward)
                name = reward.get('name')
                if reward.get('kind') == 'superweapon' and name in used_access_names:
                    continue
                count_key = buff_count_key(reward)
                if limit is not None and buff_counts.get(count_key, 0) >= limit:
                    continue
                if reward.get('kind') == 'buff':
                    unit = reward.get('unit')
                    if (
                        require_access_for_unit_buffs
                        and unit
                        and not reward.get('global_buff')
                        and not unit_access_earned(unit)
                    ):
                        continue
                candidates.append(reward)
            if not candidates:
                candidates = [
                    dict(reward)
                    for reward in self.configured_reward_pool()
                    if reward.get('kind') == 'buff'
                    and (
                        not require_access_for_unit_buffs
                        or reward.get('global_buff')
                        or not reward.get('unit')
                        or unit_access_earned(reward.get('unit'))
                    )
                ]
            if not candidates:
                return None
            reward = dict(rng.choice(candidates))
            name = reward.get('name')
            if reward.get('kind') == 'buff':
                count_key = buff_count_key(reward)
                buff_counts[count_key] = buff_counts.get(count_key, 0) + 1
                unit = reward.get('unit')
                if unit:
                    record_unit_buff(unit)
            return reward

        slot_order = []
        reserved_opening_slots = set()
        if progression_mode == 'Grid Mode' and isinstance(grid, dict):
            for code in grid_opening_mission_codes(grid):
                if code in plan and plan[code]:
                    slot = (code, 0)
                    reserved_opening_slots.add(slot)
                    slot_order.append((code, 0, True))

            remaining_slots = [
                (code, slot_index, False)
                for code in mission_codes
                for slot_index in range(len(plan[code]))
                if (code, slot_index) not in reserved_opening_slots
            ]
            rng.shuffle(remaining_slots)
            slot_order.extend(remaining_slots)
        else:
            slot_order = [
                (code, slot_index, False)
                for code in mission_codes
                for slot_index in range(len(plan[code]))
            ]

        for code, slot_index, force_unit_access in slot_order:
            reward = None
            prefer_global = (global_index + 1) % GLOBAL_BUFF_REWARD_INTERVAL == 0
            if force_unit_access:
                reward = draw_access(code, unit_only=True)
            if reward is None and not force_unit_access and (
                global_index % 5 == 4 or prefer_global
            ):
                reward = draw_buff(code, prefer_global=prefer_global)
            if reward is None:
                reward = draw_access(code)
            if reward is None:
                reward = draw_buff(code, prefer_global=prefer_global)
            if reward is None:
                reward = draw_repeatable_fallback(code)
            if reward is not None:
                plan[code][slot_index] = reward
                seed_unlocked_tech_ids.update(tech_ids_for_rewards([reward]))
            global_index += 1

        return {
            code: [reward for reward in rewards if reward is not None]
            for code, rewards in plan.items()
        }

    def earned_rewards_from_checks(self):
        earned = []
        for code in self.state.get('mission_order', []):
            for check in self.state.get('mission_checks', {}).get(code, []):
                if check.get('unlocked') or check.get('released'):
                    earned.extend(check_rewards(check))
        return earned

    def release_remaining_grid_rewards(self):
        """Release pending Grid rewards without marking optional missions complete."""
        released_rewards = []
        released_checks = []
        for code in self.state.get('mission_order', []):
            for check in self.state.get('mission_checks', {}).get(code, []):
                if check.get('unlocked') or check.get('released'):
                    continue
                check['released'] = True
                rewards = check_rewards(check)
                released_rewards.extend(rewards)
                released_checks.append((code, check.get('id', '')))
        return released_rewards, released_checks

    def refresh_missions(self):
        self.append_log('Refreshing mission list...')
        self.missions = parse_missions(BATTLE_CLIENT_INI, FALLBACK_OBJECTIVE_COUNT)
        self._mission_by_code = {mission['code']: mission for mission in self.missions}
        self.mission_goal_spinbox.configure(to=max(1, len(self.missions)))
        if self.missions and self.mission_goal_var.get() > len(self.missions):
            self.mission_goal_var.set(len(self.missions))
        self.update_mission_goal_limit()
        self.sync_state_mission_objectives()
        self.redraw_mission_tree()

        if not self.missions:
            self.append_log('No missions found. Check INI/BattleClient.ini and game root paths.', error=True)
            return

        children = self.missions_tree.get_children()
        if children:
            self.missions_tree.selection_set(children[0])
            self.selected_index.set(int(children[0]))
        self.append_log(f'Loaded {len(self.missions)} missions.')

    def on_campaign_filter_changed(self, event=None):
        self.update_mission_goal_limit()

    def on_mission_pool_settings_changed(self):
        self.refresh_setting_states()
        self.update_mission_goal_limit()

    def on_reward_mode_changed(self, event=None):
        self.refresh_setting_states()

    def on_progression_mode_changed(self, event=None):
        self.refresh_progression_setting_states()
        if not self.state:
            self.redraw_progression_views()

    def refresh_progression_setting_states(self):
        if not hasattr(self, 'grid_options_frame'):
            return
        if self.progression_mode_var.get() == 'Grid Mode':
            self.grid_options_frame.grid()
        else:
            self.grid_options_frame.grid_remove()

    def refresh_setting_states(self):
        if not hasattr(self, 'randomize_unit_access_check'):
            return
        chaos_mode = self.reward_mode_var.get() == 'Chaos (Experimental)'
        buffs_enabled = bool(self.include_buff_rewards_var.get())
        unlimited_hero_units = bool(self.unlimited_hero_units_var.get())
        if unlimited_hero_units:
            self.buff_type_vars['build_limit'].set(False)
        if chaos_mode:
            self.randomize_unit_access_var.set(True)
            self.randomize_unit_access_check.configure(state='disabled')
            self.share_chaos_role_buffs_check.grid()
        else:
            self.randomize_unit_access_check.configure(state='normal')
            self.share_chaos_role_buffs_check.grid_remove()
        self.share_chaos_role_buffs_check.configure(state='normal' if buffs_enabled else 'disabled')
        reward_source_enabled = bool(self.randomize_unit_access_var.get()) or buffs_enabled
        self.buff_allied_helpers_check.configure(
            state='normal' if reward_source_enabled else 'disabled'
        )
        for check in getattr(self, 'buff_type_checks', []):
            check.configure(state='normal' if buffs_enabled else 'disabled')
        build_limit_check = getattr(self, 'buff_type_checks_by_id', {}).get('build_limit')
        if build_limit_check is not None:
            build_limit_check.configure(
                state='disabled' if unlimited_hero_units or not buffs_enabled else 'normal'
            )
        self.include_defensive_buildings_check.configure(
            state='normal' if reward_source_enabled else 'disabled'
        )
        self.prioritize_no_build_missions_check.configure(
            state=(
                'normal'
                if (
                    self.include_no_build_missions_var.get()
                    or self.include_no_build_production_missions_var.get()
                )
                else 'disabled'
            )
        )
        self.refresh_progression_setting_states()

    def update_mission_goal_limit(self):
        if not self.missions:
            return
        filtered_count = len(self.filtered_missions_for_seed())
        self.campaign_label.configure(text=f'Campaign ({filtered_count})')
        self.mission_goal_spinbox.configure(to=max(1, filtered_count))
        if self.mission_goal_var.get() > filtered_count:
            self.mission_goal_var.set(max(1, filtered_count))

    def active_progression_mode(self):
        if self.state:
            return self.state.get('progression_mode', DEFAULT_PROGRESSION_MODE)
        return self.progression_mode_var.get()

    def sync_grid_progression(self):
        if self.active_progression_mode() != 'Grid Mode':
            return {}
        grid = self.state.get('grid') if self.state else None
        if not isinstance(grid, dict):
            return {}
        return refresh_grid_states(grid, self.state.get('completed_missions', []))

    def mission_unlocks(self, code):
        """Return the mission codes that completing ``code`` would open now."""
        if self.active_progression_mode() != 'Grid Mode' or not self.state:
            return []
        self.sync_grid_progression()
        return completing_unlocks(self.state.get('grid', {}), code)

    def redraw_progression_views(self):
        grid_mode = self.active_progression_mode() == 'Grid Mode'
        if grid_mode:
            self.missions_tree.grid_remove()
            self.tree_scrollbar.grid_remove()
            self.grid_frame.grid()
            self.redraw_grid()
        else:
            self.grid_frame.grid_remove()
            self.missions_tree.grid()
            self.tree_scrollbar.grid()

    def redraw_grid(self):
        grid = self.state.get('grid') if self.state else None
        content_frame = self.grid_content_frame
        if not isinstance(grid, dict) or not grid.get('nodes'):
            if self.grid_render_signature != ('empty',):
                for child in content_frame.winfo_children():
                    child.destroy()
                for column in range(self.grid_configured_width):
                    content_frame.columnconfigure(
                        column, weight=0, minsize=0, uniform=''
                    )
                for row in range(self.grid_configured_height):
                    content_frame.rowconfigure(
                        row, weight=0, minsize=0, uniform=''
                    )
                self.grid_configured_width = 1
                self.grid_configured_height = 1
                self.grid_tile_widgets = {}
                self.grid_render_signature = ('empty',)
                ttk.Label(
                    content_frame,
                    text='Generate a Grid Mode seed to create the mission grid.',
                    anchor='center',
                    justify='center',
                ).grid(row=0, column=0, sticky='nsew', padx=20, pady=20)
                content_frame.columnconfigure(0, weight=1)
                content_frame.rowconfigure(0, weight=1)
                self.grid_canvas.xview_moveto(0)
                self.grid_canvas.yview_moveto(0)
                self.after_idle(self.resize_grid_canvas_window)
            return

        index_by_code = {mission['code']: idx for idx, mission in enumerate(self.missions)}
        width = int(grid.get('width', 1))
        height = int(grid.get('height', 1))
        signature = (
            'grid',
            width,
            height,
            tuple(sorted(
                (code, int(node['x']), int(node['y']))
                for code, node in grid['nodes'].items()
            )),
        )
        if signature == self.grid_render_signature:
            self.refresh_grid_tiles()
            return

        for child in content_frame.winfo_children():
            child.destroy()
        self.grid_tile_widgets = {}
        self.grid_render_signature = signature
        for column in range(max(width, self.grid_configured_width)):
            content_frame.columnconfigure(column, weight=0, minsize=0, uniform='')
        for row in range(max(height, self.grid_configured_height)):
            content_frame.rowconfigure(row, weight=0, minsize=0, uniform='')
        self.grid_configured_width = width
        self.grid_configured_height = height
        for column in range(width):
            content_frame.columnconfigure(
                column,
                weight=1,
                minsize=105,
                uniform='grid-column',
            )
        for row in range(height):
            content_frame.rowconfigure(row, weight=1, minsize=88, uniform='grid-row')

        positions = {
            (node['x'], node['y']): code
            for code, node in grid['nodes'].items()
        }
        # Create every coordinate slot, including a quiet background for a
        # trimmed corner. This keeps rows and columns visually aligned as a
        # board instead of allowing an irregular set of widgets to collapse.
        for row in range(height):
            for column in range(width):
                if (column, row) in positions:
                    continue
                spacer = tk.Frame(
                    content_frame,
                    background=self.ui_palette()['canvas'],
                    borderwidth=0,
                )
                spacer.grid(row=row, column=column, sticky='nsew', padx=3, pady=3)

        for code, node in grid['nodes'].items():
            tile = tk.Frame(
                content_frame,
                relief='flat',
                borderwidth=0,
                cursor='hand2',
            )
            tile.mission_code = code
            tile.columnconfigure(0, weight=1)
            tile.rowconfigure(0, weight=1)
            selection_frame = tk.Frame(
                tile,
                relief='flat',
                borderwidth=0,
                cursor='hand2',
            )
            selection_frame.columnconfigure(0, weight=1)
            selection_frame.rowconfigure(1, weight=1)
            is_goal = code == grid.get('goal')
            selection_frame.grid(
                row=0,
                column=0,
                sticky='nsew',
                padx=3 if is_goal else 0,
                pady=3 if is_goal else 0,
            )
            banner = tk.Label(
                selection_frame,
                font=('Segoe UI', 7, 'bold'),
                anchor='center',
                justify='center',
                wraplength=max(74, 520 // max(1, width)),
                padx=3,
                pady=3,
            )
            banner.grid(row=0, column=0, sticky='ew', padx=4, pady=(4, 0))
            body = tk.Label(
                selection_frame,
                font=('Segoe UI', 9, 'bold'),
                justify='center',
                anchor='center',
                wraplength=max(80, 560 // max(1, width)),
                padx=5,
                pady=6,
            )
            body.grid(row=1, column=0, sticky='nsew', padx=4, pady=(0, 4))
            mission_index = index_by_code.get(code, 0)
            for widget in (tile, selection_frame, banner, body):
                widget.bind(
                    '<Button-1>',
                    lambda event, index=mission_index: self.select_grid_mission(index),
                )
            tile.grid(row=node['y'], column=node['x'], sticky='nsew', padx=3, pady=3)
            self.grid_tile_widgets[code] = {
                'tile': tile,
                'selection': selection_frame,
                'banner': banner,
                'body': body,
            }
        self.grid_canvas.xview_moveto(0)
        self.grid_canvas.yview_moveto(0)
        self.after_idle(self.resize_grid_canvas_window)
        self.refresh_grid_tiles()

    def refresh_grid_tiles(self, mission_codes=None):
        if not self.grid_tile_widgets or not self.state:
            return
        grid = self.state.get('grid', {})
        states = self.sync_grid_progression()
        lookup = self.mission_lookup()
        selected_code = self.selected_mission_code()
        codes = list(mission_codes) if mission_codes is not None else list(self.grid_tile_widgets)
        for code in codes:
            widgets = self.grid_tile_widgets.get(code)
            if not widgets:
                continue
            mission = lookup.get(code, {})
            state = states.get(code, GRID_LOCKED)
            faction = normalize_faction(mission.get('side', ''))
            faction_color = FACTION_TILE_COLORS.get(faction, '#315b82')
            started = self.is_mission_started(code)
            if state == GRID_LOCKED:
                background, foreground = '#3f454b', '#aeb5bc'
                state_label = 'MISSION LOCKED'
                banner_color = '#555c63'
            elif state == GRID_COMPLETED:
                background, foreground = faction_color, '#ffffff'
                state_label = 'MISSION COMPLETED'
                banner_color = '#23864b'
            elif started:
                background, foreground = faction_color, '#ffffff'
                done, total = self.mission_check_counts(code)
                state_label = f'IN PROGRESS  ·  {done}/{total}'
                assistance_stacks = (
                    self.mission_failure_stack(code)
                    if self.failure_assistance_enabled()
                    else 0
                )
                if assistance_stacks:
                    state_label += f'\nASSISTANCE  ·  {assistance_stacks}'
                banner_color = '#b77913'
            else:
                background, foreground = faction_color, '#ffffff'
                state_label = ''
                banner_color = faction_color
            is_goal = code == grid.get('goal')
            widgets['tile'].configure(
                background='#d6ad37' if is_goal else background,
            )
            widgets['selection'].configure(
                background='#86cdf7' if code == selected_code else background,
            )
            if state == GRID_UNLOCKED and not started:
                widgets['banner'].grid_remove()
                widgets['body'].grid_configure(pady=4)
            else:
                widgets['banner'].configure(
                    text=state_label,
                    background=banner_color,
                    foreground='#ffffff' if state != GRID_LOCKED else '#d4d8dc',
                )
                widgets['banner'].grid()
                widgets['body'].grid_configure(pady=(0, 4))
            widgets['body'].configure(
                text=mission.get('title', code),
                background=background,
                foreground=foreground,
            )

    def select_grid_mission(self, index):
        previous_code = self.selected_mission_code()
        self.selected_index.set(index)
        current_code = self.selected_mission_code()
        self.refresh_grid_tiles({previous_code, current_code})
        self.refresh_progress_view()

    def redraw_mission_tree(self):
        for item in self.missions_tree.get_children():
            self.missions_tree.delete(item)

        order_map = self.randomizer_order_map()
        unlocked = set(self.unlocked_mission_codes())

        for idx, mission in self.visible_missions():
            code = mission['code']
            side = mission.get('side', '')
            title = mission.get('title', code)
            checks_done, checks_total = self.mission_check_counts(code)
            if self.is_mission_complete(code):
                state = 'Done'
            elif not self.state:
                state = 'Vanilla'
            elif code in unlocked:
                state = 'Started' if self.is_mission_started(code) else 'Open'
            else:
                state = 'Locked'
            checks_label = '' if not self.state else f'{checks_done}/{checks_total}'
            order = order_map.get(code, idx + 1)
            tags = ('completed',) if self.is_mission_complete(code) else ()
            self.missions_tree.insert(
                '',
                'end',
                iid=str(idx),
                values=(f'{order:03}', state, checks_label, side, code, title),
                tags=tags,
            )

        children = self.missions_tree.get_children()
        selected_iid = str(self.selected_index.get())
        if selected_iid in children:
            self.missions_tree.selection_set(selected_iid)
            self.missions_tree.see(selected_iid)
        elif children:
            self.missions_tree.selection_set(children[0])
            self.selected_index.set(int(children[0]))
        self.redraw_progression_views()

    def sort_missions_by(self, column):
        if column not in self.mission_heading_labels:
            return
        if self.mission_sort_column == column:
            self.mission_sort_reverse = not self.mission_sort_reverse
        else:
            self.mission_sort_column = column
            self.mission_sort_reverse = False

        for heading, label in self.mission_heading_labels.items():
            suffix = ''
            if heading == self.mission_sort_column:
                suffix = ' ↓' if self.mission_sort_reverse else ' ↑'
            self.missions_tree.heading(heading, text=label + suffix)
        self.redraw_mission_tree()

    def on_mission_select(self, event):
        selection = self.missions_tree.selection()
        if selection:
            self.selected_index.set(int(selection[0]))
            self.refresh_progress_view()

    def selected_mission(self):
        if not self.missions:
            return None
        index = self.selected_index.get()
        if index < 0 or index >= len(self.missions):
            return None
        return self.missions[index]

    def selected_mission_code(self):
        mission = self.selected_mission()
        return mission['code'] if mission else None

    def mission_checks(self, code):
        return self.state.get('mission_checks', {}).get(code, [])

    def mission_check_counts(self, code):
        checks = self.mission_checks(code)
        if not checks:
            return (0, 0)
        done = sum(
            len(check_rewards(check))
            for check in checks
            if check.get('unlocked') or check.get('released')
        )
        total = sum(max(1, len(check_rewards(check))) for check in checks)
        return (done, total)

    def is_mission_complete(self, code):
        checks = self.mission_checks(code)
        if checks:
            return any(check.get('id') == 'victory' and check.get('unlocked') for check in checks)
        return code in self.state.get('completed_missions', [])

    def is_mission_started(self, code):
        if not self.state or self.is_mission_complete(code):
            return False
        return (
            code in self.state.get('started_missions', [])
            or any(check.get('unlocked') for check in self.mission_checks(code))
        )

    def is_run_complete(self):
        if not self.state:
            return False
        if self.active_progression_mode() == 'Grid Mode':
            self.sync_grid_progression()
            return is_grid_complete(self.state.get('grid', {}))
        goal = self.state.get('mission_goal', len(self.state.get('mission_order', [])))
        return len(self.state.get('completed_missions', [])) >= goal

    def mission_tooltip_text(self, row_id):
        if not self.state:
            return ''
        try:
            code = self.missions[int(row_id)]['code']
        except (IndexError, ValueError):
            return ''
        missing = [
            check
            for check in self.mission_checks(code)
            if not check.get('unlocked') and not check.get('released')
        ]
        if not missing:
            return ''
        lines = ['Remaining mission checks:']
        for check in missing:
            rewards = check_rewards(check)
            lines.append(f'- {check.get("name", "Check")} ({len(rewards)} rewards)')
            for reward in rewards:
                reward_name = (
                    '?????'
                    if self.hide_reward_details_var.get()
                    else reward_display_name(reward)
                )
                lines.append(f'    • {reward_name}')
        return '\n'.join(lines)

    def on_launch_selected(self):
        mission = self.selected_mission()
        if mission is None:
            self.append_log('Cannot launch selected mission: no valid mission selected.', error=True)
            return

        if self.state:
            unlocked = set(self.unlocked_mission_codes())
            if mission['code'] not in unlocked and mission['code'] not in self.state.get('completed_missions', []):
                self.append_log(f'Mission is locked by current seed: {mission["code"]}', error=True)
                messagebox.showwarning('Mission Locked', 'Complete more open missions to unlock this one.')
                return

        self.save_current_launcher_config()
        self.append_log(f'Launching selected mission: {mission["code"]} ({mission["scenario"]})')
        log_event(
            'mission_launch_requested',
            seed=self.state.get('seed', ''),
            code=mission.get('code'),
            title=mission.get('title'),
            scenario=mission.get('scenario'),
            side=mission.get('side'),
            difficulty=self.difficulty_var.get(),
            game_speed=self.game_speed_var.get(),
            reward_mode=self.active_reward_mode(),
            completed_missions=len(self.state.get('completed_missions', [])),
            earned_rewards=len(self.state.get('earned_rewards', [])),
        )
        self.launch_mission_async(mission)

    def on_new_seed(self):
        if self.state and self.state.get('completed_missions'):
            confirmed = messagebox.askyesno(
                'Start New Seed',
                'This will replace the current randomizer progress. Start a new seed?',
            )
            if not confirmed:
                return

        self.seed_var.set(f'MO-{random.randrange(0x10000000):08X}')
        self.generate_seed_from_settings()

    def generate_seed_from_settings(self, force=False):
        if not self.missions:
            self.append_log('Cannot generate seed: no missions loaded.', error=True)
            return

        seed_missions = self.filtered_missions_for_seed()
        if not seed_missions:
            self.append_log(f'Cannot generate seed: no missions match {self.campaign_var.get()}.', error=True)
            return

        self.clear_log()
        seed = self.seed_var.get().strip() or f'MO-{random.randrange(0x10000000):08X}'
        mission_goal = self.selected_mission_goal()
        rewards_per_check = self.selected_rewards_per_check()
        reward_settings = self.current_reward_settings()
        if not any((
            reward_settings['randomize_unit_access'],
            reward_settings['include_buff_rewards'],
            reward_settings['include_superweapon_rewards'],
            reward_settings['include_secondary_superweapon_rewards'],
            reward_settings['include_aid_power_rewards'],
        )):
            self.append_log('Cannot generate seed: enable at least one reward-pool option.', error=True)
            return
        if reward_settings['include_buff_rewards'] and not reward_settings['enabled_buff_types']:
            self.append_log('Cannot generate seed: buff rewards are enabled but no buff types are selected.', error=True)
            return

        generation_context = {
            'campaign_filter': self.campaign_var.get(),
            'reward_mode': self.reward_mode_var.get(),
        }
        self._seed_generation_context = generation_context
        self._reward_settings_override = reward_settings
        starting_unit_ids = self.starting_tier_one_unit_ids_for_seed(seed, reward_settings)
        self._starting_unit_ids_override = starting_unit_ids
        options = {
            **generation_context,
            'seed': seed,
            'seed_missions': list(seed_missions),
            'mission_goal': mission_goal,
            'rewards_per_check': rewards_per_check,
            'reward_settings': reward_settings,
            'starting_unit_ids': starting_unit_ids,
            'progression_mode': self.progression_mode_var.get(),
            'two_start_positions': bool(self.grid_two_starts_var.get()),
            'mission_pool_settings': {
                'include_no_build_missions': bool(self.include_no_build_missions_var.get()),
                'include_no_build_production_missions': bool(
                    self.include_no_build_production_missions_var.get()
                ),
                'prioritize_no_build_missions': bool(
                    self.prioritize_no_build_missions_var.get()
                ),
            },
        }
        self.run_in_background(
            'Generating new randomizer run…',
            'Building mission order and reward plan. Large reward pools can take a while.',
            lambda: self.build_seed_generation(options),
            self.finish_seed_generation,
            self.handle_seed_generation_error,
        )

    def build_seed_generation(self, options):
        seed = options['seed']
        seed_missions = options['seed_missions']
        mission_goal = options['mission_goal']
        rewards_per_check = options['rewards_per_check']
        reward_settings = options['reward_settings']
        starting_unit_ids = options['starting_unit_ids']
        progression_mode = options['progression_mode']
        two_start_positions = options['two_start_positions']
        mission_pool_settings = options['mission_pool_settings']
        campaign_counts = campaign_mission_counts(seed_missions)
        rng = random.Random(seed)
        if progression_mode == 'Classic':
            mission_codes = classic_mission_order(seed_missions, mission_goal)
            campaign_limits = campaign_mission_counts(seed_missions[:len(mission_codes)])
        else:
            campaign_limits = seed_campaign_limits(seed_missions, mission_goal)
            try:
                low_level_count = (
                    grid_opening_mission_count(mission_goal, two_start_positions)
                    if progression_mode == 'Grid Mode'
                    else LOW_LEVEL_MISSION_COUNT
                )
            except ValueError as exc:
                raise ValueError(f'Cannot generate grid: {exc}.') from exc
            mission_codes = seed_mission_order(
                seed_missions,
                rng,
                mission_goal,
                low_level_count=low_level_count,
                preferred_opening_codes=(
                    NO_BUILD_MISSION_CODES
                    if mission_pool_settings['prioritize_no_build_missions']
                    else None
                ),
                excluded_opening_codes=LATE_FOEHN_MISSION_CODES,
            )
        grid = None
        if progression_mode == 'Grid Mode':
            try:
                grid = create_grid(
                    mission_codes,
                    two_start_positions,
                    protect_opening=True,
                )
            except ValueError as exc:
                raise ValueError(f'Cannot generate grid: {exc}.') from exc
        if not any(self.reward_pool_for_code(code) for code in mission_codes):
            raise ValueError(
                'Cannot generate seed: selected reward settings produce no available rewards.'
            )

        mission_checks = self.build_mission_checks(
            mission_codes,
            seed,
            rewards_per_check=rewards_per_check,
            progression_mode=progression_mode,
            grid=grid,
        )
        rewards = [
            reward
            for code in mission_codes
            for check in mission_checks[code]
            for reward in check_rewards(check)
        ]
        mission_objectives = self.state_objective_summary(mission_codes)

        state = {
            'version': 1,
            'seed': seed,
            'created_at': now_stamp(),
            'campaign_filter': options['campaign_filter'],
            'reward_mode': options['reward_mode'],
            'progression_mode': progression_mode,
            'mission_goal': mission_goal,
            'rewards_per_check': rewards_per_check,
            'starting_unlocked_missions': min(
                1 if progression_mode == 'Classic' else STARTING_UNLOCKED_MISSIONS,
                len(mission_codes),
            ),
            'mission_order': mission_codes,
            'campaign_mission_counts': campaign_counts,
            'campaign_mission_limits': campaign_limits,
            'mission_pool_settings': mission_pool_settings,
            'completed_missions': [],
            'started_missions': [],
            'mission_failure_stacks': {},
            'mission_assistance_units': {},
            'earned_rewards': [],
            'starting_unit_ids': starting_unit_ids,
            'reward_queue': rewards,
            'mission_checks': mission_checks,
            'mission_objectives': mission_objectives,
            'reward_settings': reward_settings,
            'check_schema_version': CHECK_SCHEMA_VERSION,
        }
        if grid is not None:
            state['grid'] = grid
        return {
            'state': state,
            'seed': seed,
            'mission_goal': mission_goal,
            'rewards_per_check': rewards_per_check,
            'starting_unit_ids': starting_unit_ids,
            'campaign_counts': campaign_counts,
            'campaign_limits': campaign_limits,
            'progression_mode': progression_mode,
            'grid': grid,
            'campaign_filter': options['campaign_filter'],
            'reward_mode': options['reward_mode'],
            'reward_settings': reward_settings,
            'mission_codes': mission_codes,
        }

    def finish_seed_generation(self, result):
        self.state = result['state']
        self._reward_settings_override = None
        self._starting_unit_ids_override = None
        self._seed_generation_context = None
        seed = result['seed']
        mission_goal = result['mission_goal']
        rewards_per_check = result['rewards_per_check']
        starting_unit_ids = result['starting_unit_ids']
        campaign_counts = result['campaign_counts']
        campaign_limits = result['campaign_limits']
        progression_mode = result['progression_mode']
        grid = result['grid']
        self.seed_var.set(seed)
        self.save_state()
        self.save_launcher_config(seed, mission_goal, rewards_per_check)
        self.disable_generated_rules_for_client()
        self.redraw_mission_tree()
        self.refresh_progress_view()
        opening = (
            'Start from the top-left neighbors.'
            if grid is not None and grid.get('two_start_positions')
            else 'Start from the top-left node.'
            if grid is not None
            else 'First campaign mission is open.'
            if progression_mode == 'Classic'
            else f'First {self.state["starting_unlocked_missions"]} missions are open.'
        )
        self.append_log(
            f'Generated seed {seed}. Finish {mission_goal} missions. '
            f'{rewards_per_check} reward(s) per objective. {opening} '
            f'Setup saved to {CONFIG_PATH}.'
        )
        if starting_unit_ids:
            self.append_log(
                'Starting Tier 1 units: '
                + ', '.join(unit_display_label(unit_id) for unit_id in starting_unit_ids)
                + '.'
            )
        if campaign_counts.get('Foehn') and len(campaign_counts) > 1:
            if progression_mode == 'Classic':
                self.append_log(
                    f'Classic catalogue prefix includes {campaign_limits.get("Foehn", 0)} '
                    'Foehn mission(s).'
                )
            else:
                self.append_log(
                    f'Foehn pool: {campaign_counts["Foehn"]} missions available; '
                    f'this seed is limited to {campaign_limits["Foehn"]} Foehn mission(s).'
                )
        log_event(
            'seed_generated',
            seed=seed,
            campaign=result['campaign_filter'],
            reward_mode=result['reward_mode'],
            progression_mode=progression_mode,
            grid=grid,
            mission_goal=mission_goal,
            rewards_per_check=rewards_per_check,
            mission_order=result['mission_codes'],
            campaign_mission_counts=campaign_counts,
            campaign_mission_limits=campaign_limits,
            reward_settings=result['reward_settings'],
            starting_unit_ids=starting_unit_ids,
        )

    def handle_seed_generation_error(self, exc, detail):
        self._reward_settings_override = None
        self._starting_unit_ids_override = None
        self._seed_generation_context = None
        message = str(exc) or 'Seed generation failed.'
        self.append_log(message, error=True)
        if isinstance(exc, ValueError):
            messagebox.showwarning('Cannot Generate Seed', message)
            return
        self.append_log(detail, error=True)
        messagebox.showerror('Generation Failed', 'Seed generation failed. See log for details.')

    def unlock_mission_check(self, code, check_id, source):
        if not self.state:
            return False

        checks = self.mission_checks(code)
        target = next((check for check in checks if check.get('id') == check_id), None)
        if target is None:
            return False
        if target.get('unlocked'):
            return False

        earned_now = []
        grid = self.state.get('grid', {})
        grid_goal_victory = (
            check_id == 'victory'
            and self.active_progression_mode() == 'Grid Mode'
            and code == grid.get('goal')
        )
        grid_unlocks = self.mission_unlocks(code) if check_id == 'victory' else []
        released_rewards = []
        released_checks = []
        previously_released_rewards = []
        if check_id == 'victory':
            completed = self.state.setdefault('completed_missions', [])
            if code not in completed:
                completed.append(code)
            cleared_assistance = self.state.setdefault('mission_failure_stacks', {}).pop(code, 0)
            self.state.setdefault('mission_assistance_units', {}).pop(code, None)
            for check in checks:
                if not check.get('unlocked'):
                    was_released = bool(check.pop('released', False))
                    check['unlocked'] = True
                    if was_released:
                        previously_released_rewards.extend(check_rewards(check))
                    else:
                        earned_now.extend(check_rewards(check))
        else:
            cleared_assistance = 0
            was_released = bool(target.pop('released', False))
            target['unlocked'] = True
            if was_released:
                previously_released_rewards.extend(check_rewards(target))
            else:
                earned_now.extend(check_rewards(target))

        self.sync_grid_progression()
        if grid_goal_victory:
            released_rewards, released_checks = self.release_remaining_grid_rewards()
        self.state['earned_rewards'] = self.earned_rewards_from_checks()
        self.save_state()
        reward_note = (
            f'Reward(s) earned: {reward_names(earned_now)}'
            if earned_now
            else f'{len(previously_released_rewards)} assigned reward(s) were already released at Grid victory.'
            if previously_released_rewards
            else 'No reward assigned.'
        )
        self.append_log(
            f'{source}: {code} {target.get("name", check_id)} complete. '
            + reward_note
        )
        log_event(
            'mission_check_unlocked',
            seed=self.state.get('seed', ''),
            code=code,
            check_id=check_id,
            check_name=target.get('name', check_id),
            source=source,
            rewards=[reward.get('name') for reward in earned_now],
            previously_released_rewards=len(previously_released_rewards),
        )
        if check_id == 'victory' and len(earned_now) > len(check_rewards(target)):
            self.append_log('Victory granted any missed objective rewards for this mission.')
        if cleared_assistance:
            self.append_log(
                f'Mission victory removed {cleared_assistance} retry assistance stack(s) from {code}.'
            )
        if grid_goal_victory:
            names = [self.mission_lookup().get(item, {}).get('title', item) for item in grid_unlocks]
            unlock_note = (
                f' Newly unlocked: {", ".join(names)}.'
                if names
                else ' No locked grid missions remained.'
            )
            self.append_log(
                f'Grid endgoal achieved: {code}. Randomizer victory achieved. '
                f'All remaining grid missions are unlocked and all {len(released_rewards)} '
                f'pending rewards are released.{unlock_note}'
            )
            log_event(
                'randomizer_victory_achieved',
                seed=self.state.get('seed', ''),
                progression_mode='Grid Mode',
                goal_code=code,
                unlocked_missions=grid_unlocks,
                released_rewards=len(released_rewards),
                released_checks=len(released_checks),
                completed_missions=len(self.state.get('completed_missions', [])),
            )
        elif grid_unlocks:
            names = [self.mission_lookup().get(item, {}).get('title', item) for item in grid_unlocks]
            self.append_log(f'Grid neighbors unlocked: {", ".join(names)}.')
        if check_id == 'victory' and self.is_run_complete():
            if not grid_goal_victory:
                self.append_log('Randomizer goal complete.')
            log_event(
                'randomizer_goal_complete',
                seed=self.state.get('seed', ''),
                progression_mode=self.active_progression_mode(),
                completed_missions=len(self.state.get('completed_missions', [])),
            )
        self.redraw_mission_tree()
        self.refresh_progress_view()
        return True

    def on_debug_mark_complete(self):
        if not self.state:
            messagebox.showwarning('No Seed', 'Generate a seed before changing debug progress.')
            return

        mission = self.selected_mission()
        if mission is None:
            self.append_log('Debug completion failed: no valid mission selected.', error=True)
            return

        code = mission['code']
        if self.is_mission_complete(code):
            self.append_log(f'Debug completion skipped; mission is already complete: {code}')
            return

        victory = next(
            (check for check in self.mission_checks(code) if check.get('id') == 'victory'),
            None,
        )
        if victory is None:
            self.append_log(f'Debug completion failed; no victory check exists for {code}.', error=True)
            return

        log_event(
            'debug_mission_completion_requested',
            seed=self.state.get('seed', ''),
            code=code,
            title=mission.get('title'),
            scenario=mission.get('scenario'),
        )
        if self.unlock_mission_check(code, victory['id'], 'Debug override'):
            self.disable_generated_rules_for_client()

    def filtered_missions_for_seed(self):
        selected = self.campaign_var.get()
        missions = list(self.missions) if selected == CAMPAIGN_FILTERS[0] else [
            mission
            for mission in self.missions
            if normalize_faction(mission.get('side', '')) == selected
        ]
        return filter_missions_by_build_settings(
            missions,
            include_true_no_build=self.include_no_build_missions_var.get(),
            include_no_build_production=(
                self.include_no_build_production_missions_var.get()
            ),
        )

    def randomizer_order_map(self):
        order = self.state.get('mission_order', [])
        return {code: idx + 1 for idx, code in enumerate(order)}

    def visible_missions(self):
        if self.state:
            shown_codes = set(self.unlocked_mission_codes()) | set(self.state.get('completed_missions', []))
            visible = [(idx, mission) for idx, mission in enumerate(self.missions) if mission['code'] in shown_codes]
        else:
            visible = list(enumerate(self.missions))
        order_map = self.randomizer_order_map()
        unlocked = set(self.unlocked_mission_codes())
        def default_sort_key(item):
            _, mission = item
            done = self.is_mission_complete(mission['code'])
            return (1 if done else 0, order_map.get(mission['code'], 9999))

        if not self.mission_sort_column:
            return sorted(visible, key=default_sort_key)

        column = self.mission_sort_column

        def selected_sort_key(item):
            idx, mission = item
            code = mission['code']
            checks_done, checks_total = self.mission_check_counts(code)
            if self.is_mission_complete(code):
                state = 'done'
            elif code in unlocked:
                state = 'open'
            elif self.state:
                state = 'locked'
            else:
                state = 'vanilla'
            values = {
                'order': order_map.get(code, idx + 1),
                'state': state,
                'checks': (
                    checks_done / checks_total if checks_total else -1,
                    checks_done,
                    checks_total,
                ),
                'faction': (mission.get('side') or '').casefold(),
                'code': code.casefold(),
                'title': (mission.get('title') or code).casefold(),
            }
            return (values[column], order_map.get(code, idx + 1))

        return sorted(visible, key=selected_sort_key, reverse=self.mission_sort_reverse)

    def selected_mission_goal(self):
        try:
            goal = int(self.mission_goal_var.get())
        except (TypeError, ValueError, tk.TclError):
            goal = DEFAULT_MISSION_GOAL
        mission_count = len(self.filtered_missions_for_seed()) or len(self.missions)
        return max(1, min(goal, mission_count))

    def selected_rewards_per_check(self):
        try:
            value = int(self.rewards_per_check_var.get())
        except (TypeError, ValueError, tk.TclError):
            value = DEFAULT_REWARDS_PER_CHECK
        value = max(1, min(value, MAX_REWARDS_PER_CHECK))
        self.rewards_per_check_var.set(value)
        return value

    @staticmethod
    def validate_rewards_per_check(proposed_value):
        if proposed_value == '':
            return True
        if not proposed_value.isdigit():
            return False
        return 1 <= int(proposed_value) <= MAX_REWARDS_PER_CHECK

    @staticmethod
    def rewards_per_check_message(value):
        if value >= MAX_REWARDS_PER_CHECK:
            return 'Ok that is now enough...'
        if value >= 20:
            return "So you don't feel powerful enough?"
        if value >= 10:
            return 'Wanting to feel good eh?'
        return ''

    def refresh_rewards_per_check_message(self, *_args):
        try:
            value = int(self.rewards_per_check_var.get())
        except (TypeError, ValueError, tk.TclError):
            value = 0

        message = self.rewards_per_check_message(value)

        self.rewards_per_check_message_label.configure(text=message)
        if message:
            self.rewards_per_check_message_label.grid()
        else:
            self.rewards_per_check_message_label.grid_remove()

    def unlocked_mission_codes(self):
        if not self.state:
            return [mission['code'] for mission in self.missions]

        if self.active_progression_mode() == 'Grid Mode':
            states = self.sync_grid_progression()
            return [
                code
                for code in self.state.get('mission_order', [])
                if states.get(code) in {GRID_UNLOCKED, GRID_COMPLETED}
            ]

        order = self.state.get('mission_order', [])
        completed_count = len(self.state.get('completed_missions', []))
        starting_count = self.state.get('starting_unlocked_missions', STARTING_UNLOCKED_MISSIONS)
        open_count = min(len(order), starting_count + completed_count)
        return order[:open_count]

    def get_selected_difficulty_value(self):
        return dict(DIFFICULTIES).get(self.difficulty_var.get(), 1)

    def get_selected_game_speed_value(self):
        return dict(GAME_SPEEDS).get(self.game_speed_var.get(), 3)

    def read_spawn_difficulty(self):
        if not SPAWN_INI.exists():
            return 'Normal'

        try:
            for line in read_text(SPAWN_INI).splitlines():
                stripped = line.strip()
                if stripped.lower().startswith('difficultymodehuman') and '=' in stripped:
                    _, value = stripped.split('=', 1)
                    mode = value.strip()
                    for label, code in DIFFICULTIES:
                        if str(code) == mode:
                            return label
        except Exception:
            pass

        return 'Normal'

    def read_spawn_game_speed(self):
        for path in (SPAWN_INI, OPTIONS_INI, YR_OPTIONS_INI):
            label = self.read_game_speed_from_ini(path)
            if label:
                return label
        return '3 - Medium'

    def read_game_speed_from_ini(self, path):
        if not path.exists():
            return ''

        try:
            for line in read_text(path).splitlines():
                stripped = line.strip()
                if stripped.lower().startswith('gamespeed') and '=' in stripped:
                    _, value = stripped.split('=', 1)
                    speed = value.strip()
                    for label, code in GAME_SPEEDS:
                        if str(code) == speed:
                            return label
        except Exception:
            pass

        return ''

    def spawn_reward_options(self):
        return {}

    def mission_required_launch_rules(self, mission):
        scenario = mission.get('scenario')
        if not scenario:
            return {}
        source_path = self.extract_campaign_map(scenario)
        lines = read_text(source_path).splitlines()
        starting_unit_ids = self.active_starting_tier_one_unit_ids()
        production_houses = mission_player_production_houses(
            mission.get('code')
        )
        if self.active_reward_mode() == 'Chaos (Experimental)':
            rules = chaos_earned_access_rules(
                lines,
                self.active_launch_rewards(),
                additional_build_houses=(),
                additional_production_houses=production_houses,
            )
            transport_rules = always_available_transport_rules(
                lines,
                chaos_mode=True,
                additional_build_houses=(),
                additional_production_houses=production_houses,
            )
            for section, values in transport_rules.items():
                rules.setdefault(section, {}).update(values)
            engineer_rules = single_engineer_rules(
                lines,
                chaos_mode=True,
                additional_build_houses=(),
                additional_production_houses=production_houses,
            )
            for section, values in engineer_rules.items():
                rules.setdefault(section, {}).update(values)
            starter_rules = starting_tier_one_rules(
                lines,
                starting_unit_ids,
                chaos_mode=True,
                additional_build_houses=(),
                additional_production_houses=production_houses,
            )
            for section, values in starter_rules.items():
                rules.setdefault(section, {}).update(values)
            return rules
        selected_campaign = self.state.get('campaign_filter', '') if self.state else ''
        translate_equivalents = selected_campaign in {
            'Allies', 'Soviets', 'Epsilon', 'Foehn'
        }
        earned_access_ids = (
            self.active_unlocked_reward_tech_ids()
            if self.randomize_unit_access_enabled()
            else controlled_tech_ids()
        )
        earned_access_ids.update(starting_unit_ids)
        rules = mission_basic_unit_rules(
            lines,
            earned_access_ids=earned_access_ids,
            translate_equivalents=translate_equivalents,
            additional_build_houses=(),
            additional_production_houses=production_houses,
        )
        transport_rules = always_available_transport_rules(
            lines,
            additional_build_houses=(),
            additional_production_houses=production_houses,
        )
        for section, values in transport_rules.items():
            rules.setdefault(section, {}).update(values)
        standard_starter_families = {
            'All Campaigns': ('allies', 'soviets', 'epsilon'),
            'Allies': ('allies', 'soviets', 'epsilon'),
            'Soviets': ('allies', 'soviets', 'epsilon'),
            'Epsilon': ('allies', 'soviets', 'epsilon'),
            # Foehn Standard deliberately operates Allied/Soviet technology.
            'Foehn': ('allies', 'soviets'),
        }.get(selected_campaign, ())
        starter_rules = starting_tier_one_rules(
            lines,
            starting_unit_ids,
            standard_families=standard_starter_families,
            additional_build_houses=(),
            additional_production_houses=production_houses,
        )
        for section, values in starter_rules.items():
            rules.setdefault(section, {}).update(values)
        return rules

    def cleanup_generated_root_maps(self):
        for path in list(GAME_ROOT.glob('*.MAP')) + list(GAME_ROOT.glob('*.map')):
            if is_generated_hooked_map(path):
                result = subprocess.run(
                    [
                        'powershell',
                        '-NoProfile',
                        '-Command',
                        f"Remove-Item -LiteralPath '{str(path).replace(chr(39), chr(39) + chr(39))}' -Force",
                    ],
                    cwd=GAME_ROOT,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0 and callable(self.__dict__.get('append_log')) and 'log_text' in self.__dict__:
                    detail = (result.stderr or 'Remove-Item failed.').strip()
                    self.append_log(f'Could not remove generated hooked map {path.name}: {detail}', error=True)

    def extract_campaign_map(self, scenario):
        EXTRACTED_MAP_DIR.mkdir(parents=True, exist_ok=True)
        output_path = EXTRACTED_MAP_DIR / scenario.upper()
        if output_path.exists():
            return output_path

        loose_root_map = GAME_ROOT / scenario
        if loose_root_map.exists():
            shutil.copy2(loose_root_map, output_path)
            return output_path

        assembly_paths = mix_reader_assembly_paths()
        if any(not path.exists() for path in assembly_paths):
            missing = ', '.join(path.name for path in assembly_paths if not path.exists())
            raise FileNotFoundError(f'Map Renderer dependency files are missing: {missing}.')

        mix_paths = sorted(GAME_ROOT.glob('expandmo*.mix'), reverse=True)
        if not mix_paths:
            raise FileNotFoundError('No expandmo*.mix archives found.')

        escaped_name = scenario.upper().replace("'", "''")
        escaped_output = str(output_path).replace("'", "''")
        escaped_mixes = [str(path).replace("'", "''") for path in mix_paths]
        mix_array = ','.join(f"'{path}'" for path in escaped_mixes)
        script = f"""
$ErrorActionPreference = 'Stop'
{powershell_mix_reader_load_script()}
$name = '{escaped_name}'
$output = '{escaped_output}'
foreach ($mixPath in @({mix_array})) {{
    $fs = [System.IO.File]::OpenRead($mixPath)
    try {{
        $mix = New-Object CNCMaps.FileFormats.MixFile($fs, [System.IO.Path]::GetFileName($mixPath), $false)
        if ($mix.ContainsFile($name)) {{
            $vf = $mix.OpenFile($name, [CNCMaps.FileFormats.FileFormat]::Ukn, [CNCMaps.FileFormats.VirtualFileSystem.CacheMethod]::NoCache)
            try {{
                $target = [System.IO.File]::Create($output)
                try {{ $vf.CopyTo($target) }} finally {{ $target.Dispose() }}
            }} finally {{
                if ($vf) {{ $vf.Dispose() }}
            }}
            Write-Output $mixPath
            exit 0
        }}
    }} finally {{
        $fs.Dispose()
    }}
}}
throw "Map $name was not found in expandmo*.mix"
"""
        result = subprocess.run(
            ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script],
            cwd=GAME_ROOT,
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or 'Map extraction failed.').strip()
            log_event(
                'map_extraction_failed',
                level=logging.ERROR,
                scenario=scenario,
                returncode=result.returncode,
                stderr=result.stderr.strip(),
                stdout=result.stdout.strip(),
            )
            raise RuntimeError(detail)
        return output_path

    def randomized_tech_ids(self):
        if not self.randomize_unit_access_enabled():
            return set()
        include_defenses = bool(
            self.active_reward_settings().get('include_defensive_buildings', True)
        )
        return {
            section.upper()
            for section in controlled_tech_ids()
            if include_defenses or BUFF_TARGETS.get(section.upper(), {}).get('category') != 'defenses'
        }

    def map_rules_for_launch(
        self,
        extra_rules=None,
        allowed_unlocked_tech_ids=None,
    ):
        rule_sections = {}
        randomized_tech_ids = self.randomized_tech_ids()
        allowed_unlocked = (
            None
            if allowed_unlocked_tech_ids is None
            else {
                str(unit_id).upper()
                for unit_id in allowed_unlocked_tech_ids
                if unit_id
            }
        )
        if randomized_tech_ids:
            for section in sorted(randomized_tech_ids):
                section_upper = section.upper()
                values = rule_sections.setdefault(section, {})
                values['BuildLimit'] = SCRIPTED_TECH_BUILD_LIMIT
                if section_upper not in SCRIPTED_TECH_LOCK_EXCLUSIONS:
                    values['TechLevel'] = LOCKED_TECH_LEVEL

            # Prepare ownership and basic production metadata for every access
            # item. BuildLimit keeps unearned tech out of player production
            # without preventing campaign scripts from spawning those units.
            # Earned access removes the limit on the next mission launch.
            for reward in REWARD_POOL:
                if reward.get('kind') == 'buff':
                    continue
                for section, values in launch_rules_for_reward(reward).items():
                    if section.upper() not in randomized_tech_ids:
                        continue
                    if (
                        allowed_unlocked is not None
                        and section.upper() not in allowed_unlocked
                    ):
                        continue
                    prepared_values = {
                        key: value
                        for key, value in values.items()
                        if key.lower() not in {'techlevel', 'buildlimit'}
                    }
                    rule_sections.setdefault(section, {}).update(prepared_values)

        if self.state:
            earned_rewards = self.earned_rewards_from_checks()
            self.state['earned_rewards'] = earned_rewards
            for reward in self.active_launch_rewards():
                if reward.get('kind') == 'buff' and reward.get('buff_type'):
                    continue
                for section, values in launch_rules_for_reward(reward).items():
                    if section.upper() not in randomized_tech_ids:
                        continue
                    if (
                        allowed_unlocked is not None
                        and section.upper() not in allowed_unlocked
                    ):
                        continue
                    section_rules = rule_sections.setdefault(section, {})
                    # Remove launcher-injected safety locks before applying an
                    # earned access reward. If the reward carries its own
                    # prerequisite override it is restored by the update.
                    section_rules.pop('BuildLimit', None)
                    section_rules.pop('PrerequisiteOverride', None)
                    section_rules.update(values)

        for section, values in (extra_rules or {}).items():
            section_rules = rule_sections.setdefault(section, {})
            if any(key.lower() == 'techlevel' for key in values):
                section_rules.pop('BuildLimit', None)
            section_rules.update(values)
        return rule_sections

    def prepare_hooked_map(self, mission, extra_rules=None):
        fallback_tech_ids = {
            section.upper()
            for section, values in (extra_rules or {}).items()
            if any(key.lower() == 'techlevel' for key in values)
        }
        share_basic_equivalent_buffs = bool(
            (
                self.state
                and self.state.get('campaign_filter') in {'Allies', 'Soviets', 'Epsilon', 'Foehn'}
                and self.active_reward_mode() != 'Chaos (Experimental)'
            )
            or self.share_chaos_role_buffs_enabled()
        )
        chaos_unit_specific_buffs = self.active_reward_mode() == 'Chaos (Experimental)'
        buff_allied_helpers = bool(self.active_reward_settings().get('buff_allied_helpers', False))

        scenario = mission.get('scenario')
        code = mission.get('code')
        if not scenario or not code:
            return None

        source_path = self.extract_campaign_map(scenario)
        lines = read_text(source_path).splitlines()
        # Preserve map-authored AI production fields before launcher access
        # locks and ownership rewrites are merged into this launch copy.
        native_map_sections = all_section_value_maps(lines)
        house_config = mission_house_config(code)
        records = map_house_records(lines)
        mission_effective_tech_ids = self.mission_effective_unlocked_tech_ids(
            mission,
            lines,
            fallback_tech_ids,
        )
        rule_sections = self.map_rules_for_launch(
            extra_rules,
            allowed_unlocked_tech_ids=mission_effective_tech_ids,
        )
        native_helpers, missing_helpers = resolve_configured_helper_houses(
            records,
            house_config['allies'],
            player_controlled_houses(lines, records=records),
        )
        configured_enemies, missing_enemies = resolve_configured_helper_houses(
            records,
            house_config['enemies'],
            (),
        )
        enemy_names = {house.lower() for house in configured_enemies}
        native_helpers = [
            house for house in native_helpers if house.lower() not in enemy_names
        ]
        # Native helper timing, scripts, and triggers stay intact. Compatible
        # TaskForce slots use buffed clones, while native unit IDs remain
        # buildable for dynamic AI requests outside those TaskForces.
        reward_helpers = tuple(native_helpers) if buff_allied_helpers else ()
        country_safety_helpers = tuple(unique_in_order(
            list(reward_helpers)
            + [
                house for house in records
                if house.lower() == 'sellmcv house'
            ]
        ))
        enemy_country_ids = unique_in_order(
            records.get(house, {}).get('country') or house.replace(' House', '')
            for house in configured_enemies
        )
        missing_config = unique_in_order(missing_helpers + missing_enemies)
        if missing_config:
            self.append_log(
                f'{code} house config contains names absent from this map: '
                + ', '.join(missing_config)
                + '.',
                error=True,
            )
        if buff_allied_helpers and house_config['allies']:
            self.append_log(
                f'{code} configured allied helper allowlist: '
                + (', '.join(reward_helpers) if reward_helpers else 'none')
                + '. Helper teams use buffed clones; native IDs remain buildable queue fallbacks.'
            )
        earned_rewards = self.active_launch_rewards() if self.state else []
        launch_power_rewards = list(earned_rewards)
        installed_superweapon_types, installed_rule_sections = installed_rules_registry()
        (
            cloned_power_rules,
            superweapon_actions,
            cloned_power_names,
            missing_power_sources,
        ) = cloned_superweapon_plan(
            lines,
            launch_power_rewards,
            installed_superweapon_types,
            installed_rule_sections,
        )
        for section, values in cloned_power_rules.items():
            rule_sections.setdefault(section, {}).update(values)
        if self.randomized_tech_ids():
            safe_owners = ','.join(
                safe_build_countries(lines, records, ())
            )
            denied_owners = ','.join(enemy_country_ids) if enemy_country_ids else 'none'
            for section in self.randomized_tech_ids():
                values = rule_sections.get(section)
                if not values:
                    continue
                values['Owner'] = safe_owners
                values['RequiredHouses'] = safe_owners
                values['ForbiddenHouses'] = denied_owners
        if missing_power_sources:
            self.append_log(
                'Skipped power clone(s) because installed source rules were unavailable: '
                + ', '.join(sorted(set(missing_power_sources)))
                + '.',
                error=True,
            )
        assistance_unit_ids = []
        mission_buff_unit_ids = []
        if self.state:
            mission_buff_unit_ids = mission_assistance_unit_ids(
                lines,
                unlocked_unit_ids=mission_effective_tech_ids,
                additional_unit_ids=fallback_tech_ids,
                randomized_access=self.randomize_unit_access_enabled(),
                fallback_faction=normalize_faction(mission.get('side', '')),
                configured_helper_houses=reward_helpers,
            )
        if self.state and self.failure_assistance_enabled():
            assistance_unit_ids = mission_buff_unit_ids
            self.cache_mission_assistance_units(code, assistance_unit_ids)
        if rule_sections:
            merge_ini_section_values(lines, rule_sections)
            self.append_log(f'Injected {len(rule_sections)} map rule section(s) into {scenario}.')

        generation_config = self.config.get('generation', {})
        experimental_house_buffs = bool(generation_config.get('experimental_house_buffs', False))
        safe_player_country_buffs = bool(generation_config.get('safe_player_country_buffs', True))
        require_unlocked_access_for_buffs = self.randomize_unit_access_enabled()
        buff_access_tech_ids = set(fallback_tech_ids) | set(mission_buff_unit_ids)
        if self.state and experimental_house_buffs:
            player_house, house_buffs = clone_player_country_for_house_buffs(
                lines,
                earned_rewards,
                require_unlocked_access=require_unlocked_access_for_buffs,
                additional_unlocked_tech_ids=buff_access_tech_ids,
                share_basic_equivalent_buffs=share_basic_equivalent_buffs,
                unit_specific_mode=chaos_unit_specific_buffs,
            )
            if house_buffs:
                buff_summary = ', '.join(f'{key}={value}' for key, value in sorted(house_buffs.items()))
                self.append_log(f'Applied trigger-safe player-country buffs to {player_house}: {buff_summary}')
        elif self.state and safe_player_country_buffs:
            player_house, player_country, house_rule_sections, shared_houses, buffed_allies, skipped_allies = player_country_buff_rules(
                lines,
                earned_rewards,
                configured_helper_houses=country_safety_helpers,
                require_unlocked_access=require_unlocked_access_for_buffs,
                additional_unlocked_tech_ids=buff_access_tech_ids,
                share_basic_equivalent_buffs=share_basic_equivalent_buffs,
                unit_specific_mode=chaos_unit_specific_buffs,
            )
            if house_rule_sections:
                merge_ini_section_values(lines, house_rule_sections)
                house_buffs = next(iter(house_rule_sections.values()))
                buff_summary = ', '.join(f'{key}={value}' for key, value in sorted(house_buffs.items()))
                shared_note = f' Shared country houses: {", ".join(shared_houses)}.' if shared_houses else ''
                helper_note = f' Allied player/helper houses buffed: {", ".join(buffed_allies)}.' if buffed_allies else ''
                skipped_note = f' Allied player/helper houses skipped: {", ".join(skipped_allies)}.' if skipped_allies else ''
                if player_country in house_rule_sections:
                    lead = f'Applied map-local player-country buffs for {player_house}/{player_country}'
                else:
                    lead = f'Skipped shared player country {player_house}/{player_country}; applied safe allied country buffs'
                self.append_log(f'{lead}: {buff_summary}.{shared_note}{helper_note}{skipped_note}')
            elif shared_houses:
                self.append_log(
                    f'Skipped player-country buffs for {player_house}/{player_country}: '
                    f'non-player house(s) share that country ({", ".join(shared_houses)}).'
                )
        elif self.state:
            pending_house_buffs = stacked_house_buff_values(
                earned_rewards,
                require_unlocked_access=require_unlocked_access_for_buffs,
                additional_unlocked_tech_ids=buff_access_tech_ids,
                share_basic_equivalent_buffs=share_basic_equivalent_buffs,
                unit_specific_mode=chaos_unit_specific_buffs,
            )
            if pending_house_buffs:
                self.append_log(
                    'Experimental player-house buffs are disabled for mission stability; '
                    'earned buff rewards are tracked but not injected into this map.'
                )

        assistance_stacks = self.mission_failure_stack(code)
        assistance_direct_rewards = []
        if self.failure_assistance_enabled() and assistance_stacks:
            assistance_rules, assisted_houses, skipped_assistance_countries = mission_assistance_buff_rules(
                lines,
                assistance_stacks,
                configured_helper_houses=reward_helpers,
            )
            if assisted_houses:
                if assistance_rules:
                    merge_ini_section_values(lines, assistance_rules)
                skip_note = ''
                if skipped_assistance_countries:
                    skip_note = ' Country-level bonuses skipped where enemies share the country: ' + ', '.join(
                        f'{country} ({", ".join(shared)})'
                        for country, _, shared in skipped_assistance_countries
                    ) + '.'
                self.append_log(
                    f'Applied {assistance_stacks} retry assistance stack(s) to {code} for '
                    f'{", ".join(assisted_houses)} across {len(assistance_unit_ids)} currently '
                    f'accessible or mission-provided unit type(s).{skip_note}'
                )
                # Direct health/damage/range rewards still pass through the
                # global type/weapon ownership guard even when a shared
                # country makes category multipliers unsafe.
                assistance_direct_rewards = mission_assistance_direct_rewards(
                    assistance_unit_ids,
                    assistance_stacks,
                )
            else:
                self.append_log(
                    f'Could not find a player house for {code}; retry assistance was not injected.',
                    error=True,
                )

        if self.state:
            guarded_rewards = list(earned_rewards)
            guarded_rewards.extend(assistance_direct_rewards)
            buildable_clone_ids = set(fallback_tech_ids)
            buildable_clone_ids.update(mission_effective_tech_ids)
            if not require_unlocked_access_for_buffs:
                buildable_clone_ids.update(
                    unit_id
                    for unit_id, target in BUFF_TARGETS.items()
                    if target.get('category') in {
                        'infantry', 'units', 'aircraft', 'defenses',
                    }
                )
            helper_autobuild = (
                helper_ai_autobuild_plan(
                    lines,
                    reward_helpers,
                    buildable_clone_ids,
                    guarded_rewards,
                    installed_rule_sections,
                    native_map_sections=native_map_sections,
                    allow_cross_faction=chaos_unit_specific_buffs,
                )
                if reward_helpers
                else {'variants': [], 'support': {}}
            )
            (
                clone_rule_sections,
                _cloned_source_unit_ids,
                clone_handled,
                cloned_unit_names,
                clone_warnings,
            ) = player_unit_clone_rules(
                lines,
                guarded_rewards,
                installed_rule_sections,
                native_ai_helper_houses=native_helpers,
                buffed_helper_houses=reward_helpers,
                native_map_sections=native_map_sections,
                require_unlocked_access=require_unlocked_access_for_buffs,
                additional_unlocked_tech_ids=buff_access_tech_ids,
                buildable_tech_ids=buildable_clone_ids,
                build_owner_ids=safe_build_countries(lines, records, ()),
                helper_autobuild_support=helper_autobuild.get('support'),
                forced_buildable_clone_ids=(
                    fallback_tech_ids.intersection(ENGINEER_UNIT_IDS)
                ),
                unlimited_build_limit_unit_ids=(
                    mission_buff_unit_ids
                    if self.active_reward_settings().get('unlimited_hero_units', False)
                    else ()
                ),
                share_basic_equivalent_buffs=share_basic_equivalent_buffs,
                unit_specific_mode=chaos_unit_specific_buffs,
                native_trigger_reference_ids=(
                    MISSION_NATIVE_TRIGGER_REFERENCE_IDS.get(code, ())
                ),
            )
            if clone_rule_sections:
                merge_ini_section_values(lines, clone_rule_sections)
                self.append_log(
                    'Prepared isolated standalone player unit/defense clones for: '
                    + ', '.join(cloned_unit_names)
                    + '. Compatible helper references use the same buffed clones; native IDs remain buildable fallbacks.'
                )
            if clone_warnings:
                self.append_log(
                    'Player unit/defense clone limitations: '
                    + '; '.join(clone_warnings)
                    + '.',
                    error=True,
                )
            (
                helper_ai_rules,
                helper_built_units,
                helper_ai_skipped,
            ) = helper_ai_autobuild_rules(
                lines,
                helper_autobuild,
                clone_handled,
                installed_rule_sections,
            )
            if helper_ai_rules:
                merge_ini_section_values(lines, helper_ai_rules)
                self.append_log(
                    'Added parallel allied-helper Autocreate teams for unlocked units: '
                    + ', '.join(helper_built_units)
                    + '. Native timing/scripts remain active and dynamic native-ID production stays valid.'
                )
            elif reward_helpers:
                self.append_log(
                    'No compatible parallel allied-helper unlock variants were found; '
                    'native helper timing remains active.'
                )
            if helper_ai_skipped:
                self.append_log(
                    'Skipped allied-helper unit clones without a complete player clone: '
                    + ', '.join(helper_ai_skipped)
                    + '.',
                    error=True,
                )
            (
                weapon_rule_sections,
                weapon_buffed_units,
                weapon_skipped_units,
            ) = unit_weapon_buff_rules(
                lines,
                guarded_rewards,
                configured_helper_houses=reward_helpers,
                require_unlocked_access=require_unlocked_access_for_buffs,
                additional_unlocked_tech_ids=buff_access_tech_ids,
                share_basic_equivalent_buffs=share_basic_equivalent_buffs,
                unit_specific_mode=chaos_unit_specific_buffs,
                clone_handled=clone_handled,
            )
            if weapon_rule_sections:
                merge_ini_section_values(lines, weapon_rule_sections)
                self.append_log(
                    'Applied guarded unit/weapon buffs for: '
                    + ', '.join(weapon_buffed_units)
                    + '.'
                )
            if weapon_skipped_units:
                self.append_log(
                    'Skipped guarded unit/weapon buffs because unsafe houses use the affected '
                    'unit or a shared weapon: '
                    + '; '.join(weapon_skipped_units)
                    + '.',
                    error=True,
                )
        configured_power_houses = mission_player_power_houses(code)
        power_house_names = configured_power_houses or (
            player_house_from_map(lines, records=records),
        )
        power_houses = unique_in_order(
            records.get(power_house, {}).get('country')
            or power_house.replace(' House', '')
            for power_house in power_house_names
            if power_house
        )
        if not power_houses:
            power_houses = [player_country_from_map(lines)]
        # Objective marker TeamTypes still need one concrete owner. Keep this
        # separate from the possibly multi-house superweapon grant list: the
        # latter replaced the old ``house`` local and accidentally left marker
        # generation referencing an undefined name, which made the launcher
        # fall back to the untouched source map (no rewards or access rules).
        hook_house = player_country_from_map(lines)
        superweapon_trigger = append_superweapon_grant_trigger(
            lines,
            power_houses,
            superweapon_actions,
        )
        if superweapon_trigger:
            power_names = [
                reward_display_name(reward)
                for reward in canonical_rewards(launch_power_rewards)
                if reward.get('kind') == 'superweapon'
            ]
            self.append_log(
                'Prepared isolated building-free power clones '
                f'({", ".join(cloned_power_names)}) for: '
                + ', '.join(power_names)
                + f'. Grant houses: {", ".join(power_houses)}.'
            )

        unlocked_tech_ids = set(mission_effective_tech_ids)
        randomized_tech_ids = self.randomized_tech_ids()
        removed_techlevel_actions = remove_locked_techlevel_actions(
            lines,
            unlocked_tech_ids,
            randomized_tech_ids=randomized_tech_ids,
        )
        if removed_techlevel_actions:
            self.append_log(f'Removed {removed_techlevel_actions} native tech unlock action(s) blocked by the randomizer.')
        objective_action_ids = action_line_ids(
            lines,
            lambda groups: action_has_objective_complete(groups) and not action_has_code(groups, 1) and not action_has_code(groups, 67),
        )
        # Prefer a real Winner action over Announce Win. Some missions contain
        # both, and choosing whichever appears first can fire the marker during
        # an earlier victory announcement instead of the terminal win action.
        victory_action_ids = unique_in_order(
            action_line_ids(lines, lambda groups: action_has_code(groups, 1))
            + action_line_ids(lines, lambda groups: action_has_code(groups, 67))
            + trigger_action_ids_by_name(lines, ['[win]', '/win', 'mission victory', 'mission successful'])
        )
        checks = self.mission_checks(code) if self.state else []

        patch_plan = []
        objective_checks = [check for check in checks if check.get('id') != 'victory']
        for check, action_id in zip(objective_checks, objective_action_ids):
            if not check.get('unlocked'):
                patch_plan.append((check, action_id))

        victory_check = next((check for check in checks if check.get('id') == 'victory'), None)
        if victory_check and not victory_check.get('unlocked') and victory_action_ids:
            patch_plan.append((victory_check, victory_action_ids[0]))
        elif victory_check and not victory_check.get('unlocked'):
            self.append_log(f'No automatic victory hook found for {scenario}. Victory may not be recorded.', error=True)

        if not patch_plan and not rule_sections and not superweapon_trigger:
            self.append_log(f'No hookable objective/victory triggers found for {scenario}. Progress may not be recorded.')
            return None

        markers = {}
        for index, (check, action_id) in enumerate(patch_plan, start=1):
            marker = hook_marker_name(code, check.get('id', f'check_{index}'))
            team_id = f'RND{index:05d}'
            taskforce_id = f'RNT{index:05d}'
            script_id = f'RNS{index:05d}'
            marker_action = ['4', '1', team_id, '0', '0', '0', '0', 'A']
            if check.get('id') == 'victory':
                patched = insert_actions_before_codes(
                    lines,
                    action_id,
                    [marker_action],
                    before_codes=('1', '67', '69'),
                )
                # A name-based fallback may identify a victory action list
                # without one of the standard terminal codes. Preserve the
                # previous append behavior for those unusual maps.
                if not patched:
                    patched = append_action_to_action_id(lines, action_id, marker_action)
            else:
                patched = append_action_to_action_id(lines, action_id, marker_action)
                if not patched:
                    patched = append_parallel_global_hook(
                        lines,
                        action_id,
                        marker_action,
                        marker,
                    )
            if patched:
                append_hook_team(
                    lines,
                    team_id,
                    taskforce_id,
                    script_id,
                    marker,
                    hook_house,
                )
                markers[marker] = check.get('id')
            else:
                self.append_log(
                    f'Skipped automatic {check.get("name", check.get("id", "check"))} hook for '
                    f'{scenario}: action {action_id} has no safe room for a marker.',
                    error=True,
                )

        if patch_plan and not markers:
            self.append_log(f'Hook map generation found triggers for {scenario}, but patching actions failed.', error=True)
            return None

        # Hook insertion can expose or rewrite action groups in unusual
        # campaign action lists. Run the native unlock filter again so a map
        # cannot restore access that is still locked by launcher state.
        removed_after_patching = remove_locked_techlevel_actions(
            lines,
            unlocked_tech_ids,
            randomized_tech_ids=randomized_tech_ids,
        )
        if removed_after_patching:
            self.append_log(
                f'Removed {removed_after_patching} additional native tech unlock action(s) after hook patching.'
            )

        GENERATED_MAP_DIR.mkdir(parents=True, exist_ok=True)
        generated_path = GENERATED_MAP_DIR / scenario.upper()
        generated_text = HOOKED_MAP_MARKER + '\r\n' + '\r\n'.join(lines) + '\r\n'
        # Path.write_text translates every ``\n`` on Windows. Because the map
        # text already uses CRLF, that produced CRCRLF and inserted a blank
        # line after every source line. Write bytes so campaign INI formatting
        # remains byte-for-byte conventional.
        generated_path.write_bytes(generated_text.encode('utf-8'))

        root_map = GAME_ROOT / scenario
        if root_map.exists() and not is_generated_hooked_map(root_map):
            backup_file_once(root_map, 'before-randomizer-hook')
        root_map.write_bytes(generated_text.encode('utf-8'))
        self.append_log(f'Prepared generated map {scenario}: {len(markers)} marker trigger(s).')

        return {
            'mission_code': code,
            'scenario': scenario,
            'markers': markers,
            'seen': set(),
            'offset': DEBUG_LOG.stat().st_size if DEBUG_LOG.exists() else 0,
            'root_map': root_map,
        }

    def write_spawn_ini(self, scenario, difficulty_value, game_speed_value):
        try:
            content = [
                '[Settings]',
                f'Scenario={scenario}',
                f'GameSpeed={game_speed_value}',
                f'Difficulty={difficulty_value}',
                f'CampDifficulty={difficulty_value}',
                'Firestorm=False',
                'IsSinglePlayer=Yes',
                'SidebarHack=False',
                'Side=0',
                'BuildOffAlly=True',
                f'DifficultyModeHuman={difficulty_value}',
                f'DifficultyModeComputer={difficulty_value}',
            ]
            for key, value in sorted(self.spawn_reward_options().items()):
                content.append(f'{key}={value}')

            SPAWN_INI.write_text('\r\n'.join(content) + '\r\n', encoding='utf-8')
            self.append_log(
                f'Written spawn.ini: Scenario={scenario}, DifficultyModeHuman={difficulty_value}, '
                f'Difficulty={difficulty_value}, GameSpeed={game_speed_value}'
            )
        except Exception:
            self.append_log('Failed to write spawn.ini:', error=True)
            self.append_log(traceback.format_exc(), error=True)
            raise

    def write_launch_options(self, difficulty_value, game_speed_value):
        try:
            written = []
            skipped = []
            for path in (OPTIONS_INI, YR_OPTIONS_INI):
                # Do not create option files that the installation does not
                # already use. Mental Omega normally provides RA2MO.ini;
                # RA2MD.INI is optional and was previously created needlessly.
                if not path.exists():
                    continue
                if path.exists() and path.stat().st_size > MAX_OPTION_INI_BYTES:
                    patched = self.patch_large_options_ini(
                        path,
                        {
                            'GameSpeed': game_speed_value,
                            'Difficulty': difficulty_value,
                            'CampDifficulty': difficulty_value,
                        },
                    )
                    if patched:
                        written.append(f'{path.name} (in-place)')
                    else:
                        skipped.append(f'{path.name} ({path.stat().st_size} bytes)')
                    continue
                text = read_text(path)
                text = set_ini_value_lines(text, 'Options', 'GameSpeed', game_speed_value)
                text = set_ini_value_lines(text, 'Options', 'Difficulty', difficulty_value)
                text = set_ini_value_lines(text, 'Options', 'CampDifficulty', difficulty_value)
                path.write_text(text, encoding='utf-8')
                written.append(path.name)

            if written:
                self.append_log(
                    f'Written {", ".join(written)}: GameSpeed={game_speed_value}, '
                    f'Difficulty={difficulty_value}, CampDifficulty={difficulty_value}'
                )
            if skipped:
                self.append_log(
                    'Skipped oversized option file(s): '
                    + ', '.join(skipped)
                    + '. GameSpeed and difficulty are still written to spawn.ini and other option files.'
                )
        except Exception:
            self.append_log('Failed to write launch options:', error=True)
            self.append_log(traceback.format_exc(), error=True)
            raise

    def patch_large_options_ini(self, path, values):
        """Patch one-digit option values in oversized/corrupt INIs without rewriting them."""
        try:
            patched = []
            with path.open('r+b') as handle:
                for key, value in values.items():
                    if self.patch_large_ini_key(handle, key, str(value)):
                        patched.append(key)
            missing = sorted(set(values) - set(patched))
            if missing:
                self.append_log(
                    f'{path.name}: could not in-place patch {", ".join(missing)} in oversized option file.',
                    error=True,
                )
            return len(patched) == len(values)
        except Exception:
            self.append_log(f'Failed to patch oversized option file {path.name}:', error=True)
            self.append_log(traceback.format_exc(), error=True)
            return False

    def patch_large_ini_key(self, handle, key, value):
        pattern = f'{key}='.encode('ascii')
        pattern_lower = pattern.lower()
        replacement = value.encode('ascii')
        chunk_size = 1024 * 1024
        overlap_size = len(pattern) + 32
        carry = b''
        offset = 0
        handle.seek(0)

        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                return False
            data = carry + chunk
            search = data.lower()
            base_offset = offset - len(carry)
            position = 0

            while True:
                index = search.find(pattern_lower, position)
                if index < 0:
                    break
                if index > 0 and data[index - 1] not in (10, 13):
                    position = index + len(pattern)
                    continue
                absolute_index = base_offset + index
                value_start = absolute_index + len(pattern)
                handle.seek(value_start)
                existing = handle.read(32)
                old_length = 0
                for byte in existing:
                    if byte in (10, 13):
                        break
                    old_length += 1
                if old_length >= len(replacement):
                    handle.seek(value_start)
                    handle.write(replacement + (b' ' * (old_length - len(replacement))))
                    return True
                position = index + len(pattern)

            if len(data) > overlap_size:
                carry = data[-overlap_size:]
            else:
                carry = data
            offset += len(chunk)

    def disable_generated_rules_for_client(self):
        for path in (RULESMO_INI, DISABLED_RULESMO_INI):
            if path.exists() and is_generated_rules_file(path):
                path.unlink()

    def build_command(self):
        return f'"{GAME_LAUNCHER_EXE}" "{GAME_EXE.name}" -SPAWN -CD -SPEEDCONTROL -LOG'

    def process_hook_log_text(self, text):
        if not self.active_hook or not text:
            return

        code = self.active_hook['mission_code']
        markers = self.active_hook.get('markers', {})
        seen = self.active_hook.setdefault('seen', set())
        for marker, check_id in markers.items():
            if marker in seen:
                continue
            if f'[LAUNCH] {marker}' in text or marker in text:
                seen.add(marker)
                unlocked = self.unlock_mission_check(code, check_id, 'In-game hook')
                if check_id == 'victory' and unlocked:
                    self.schedule_game_close_after_victory()

        # A normal game startup emits more than one Init_Clear message before
        # the scenario becomes interactive. Only an Init_Clear that occurs
        # after Capture_Mouse marks a genuine in-game restart. Process the log
        # in order so startup messages in the same polling chunk are not
        # mistaken for failed attempts.
        for line in text.splitlines():
            if 'MapClass::Init_Clear entry' in line:
                if self.active_hook.get('scenario_ready'):
                    self.active_hook['scenario_ready'] = False
                    if not self.is_mission_complete(code):
                        self.record_failed_mission_attempt(code, 'In-game mission restart detected')
            elif 'Capture_Mouse()' in line:
                self.active_hook['scenario_ready'] = True

    def schedule_game_close_after_victory(self):
        hook = self.active_hook
        process = self.active_game_process
        if hook is None or process is None or hook.get('victory_close_scheduled'):
            return
        hook['victory_close_scheduled'] = True
        self.append_log(
            f'Victory detected. Closing the spawned game in {VICTORY_CLOSE_DELAY_MS / 1000:g} seconds '
            'to prevent campaign continuation.'
        )
        self.after(
            VICTORY_CLOSE_DELAY_MS,
            lambda: self.close_game_after_victory(process, hook),
        )

    def close_game_after_victory(self, process, hook):
        # Do not close a later mission if the player managed to launch another
        # game during the short victory delay.
        if self.active_game_process is not process or self.active_hook is not hook:
            return
        if process.poll() is not None:
            return

        creation_flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        result = subprocess.run(
            ['taskkill', '/PID', str(process.pid), '/T', '/F'],
            cwd=GAME_ROOT,
            capture_output=True,
            text=True,
            creationflags=creation_flags,
        )
        if result.returncode == 0:
            self.append_log('Closed the spawned game after victory.')
            return

        # taskkill should close Syringe and gamemd as one tree. Keep a direct
        # process fallback for unusual Windows environments where it is absent.
        try:
            process.terminate()
            self.append_log('Closed the game launcher process after victory.')
        except OSError as exc:
            detail = (result.stderr or result.stdout or str(exc)).strip()
            self.append_log(f'Could not close the game after victory: {detail}', error=True)

    def poll_hook_log(self):
        if self.active_hook and DEBUG_LOG.exists():
            try:
                size = DEBUG_LOG.stat().st_size
                offset = self.active_hook.get('offset', 0)
                if size < offset:
                    offset = 0
                    # A truncated/recreated debug log starts a new startup
                    # sequence. Do not carry an earlier Capture_Mouse state
                    # across that boundary or the first Init_Clear in the new
                    # file is misclassified as an in-game restart.
                    self.active_hook['scenario_ready'] = False
                with DEBUG_LOG.open('r', encoding='utf-8', errors='ignore') as handle:
                    handle.seek(offset)
                    text = handle.read()
                    self.active_hook['offset'] = handle.tell()
                self.process_hook_log_text(text)
            except OSError as exc:
                self.append_log(f'Hook log read failed: {exc}', error=True)

        process = self.active_game_process
        if process is not None and process.poll() is None:
            self.after(HOOK_POLL_MS, self.poll_hook_log)
            return

        if self.active_hook:
            scenario = self.active_hook.get('scenario', 'mission')
            seen_count = len(self.active_hook.get('seen', set()))
            marker_count = len(self.active_hook.get('markers', {}))
            self.append_log(f'Hook watcher stopped for {scenario}. Seen {seen_count}/{marker_count} marker(s).')
            log_event(
                'mission_process_finished',
                code=self.active_hook.get('mission_code'),
                scenario=scenario,
                process_returncode=process.poll() if process is not None else None,
                markers_seen=seen_count,
                markers_expected=marker_count,
                completed=self.is_mission_complete(self.active_hook.get('mission_code')),
            )
        attempt = self.active_mission_attempt or {}
        attempt_code = attempt.get('mission_code')
        if attempt_code and not self.is_mission_complete(attempt_code):
            self.record_failed_mission_attempt(attempt_code, 'Mission closed without victory')
        self.active_hook = None
        self.active_game_process = None
        self.active_mission_attempt = None
        self.cleanup_generated_root_maps()
        self.disable_generated_rules_for_client()

    def launch_mission_async(self, mission, extra_rules=None, launch_note=''):
        missing = [path for path in (GAME_LAUNCHER_EXE, GAME_EXE) if not path.exists()]
        if missing:
            self.append_log('Missing launch executable(s): ' + ', '.join(str(path) for path in missing), error=True)
            return

        scenario = mission.get('scenario')
        if not scenario:
            self.append_log('Mission scenario is missing.', error=True)
            return

        difficulty_value = self.get_selected_difficulty_value()
        game_speed_value = self.get_selected_game_speed_value()
        self.run_in_background(
            'Starting game, please wait…',
            'Preparing the mission and applying earned rewards.',
            lambda: self.prepare_mission_launch_files(
                mission,
                extra_rules,
                difficulty_value,
                game_speed_value,
            ),
            lambda hook: self.start_mission_process(
                mission,
                hook,
                difficulty_value,
                game_speed_value,
                launch_note,
            ),
            self.handle_mission_prepare_error,
        )

    def handle_mission_prepare_error(self, exc, detail):
        self.cleanup_generated_root_maps()
        self.disable_generated_rules_for_client()
        self.append_log(detail, error=True)
        messagebox.showerror('Launch Failed', 'Failed to write launch files. See log for details.')

    def prepare_mission_launch_files(
        self,
        mission,
        extra_rules,
        difficulty_value,
        game_speed_value,
    ):
        scenario = mission['scenario']
        try:
            # Loose generated rulesmo.ini files can crash spawned missions or make
            # the MO client reject the install. Keep rewards in launcher state
            # until we have a safe map-specific injection path.
            self.disable_generated_rules_for_client()
            self.cleanup_generated_root_maps()
            launch_rules = {}
            for section, values in (extra_rules or {}).items():
                launch_rules.setdefault(section, {}).update(values)
            mission_required_rules = self.mission_required_launch_rules(mission)
            if mission_required_rules:
                for section, values in mission_required_rules.items():
                    launch_rules.setdefault(section, {}).update(values)
                self.append_log(
                    'Applied mission production access for '
                    + mission['code']
                    + ': '
                    + summarize_basic_unit_rules(mission_required_rules)
                    + '.'
                )
            hook = None
            try:
                hook = self.prepare_hooked_map(mission, extra_rules=launch_rules)
            except Exception:
                self.append_log('Objective hook preparation failed; launching without automatic objective detection.', error=True)
                self.append_log(traceback.format_exc(), error=True)
                self.cleanup_generated_root_maps()
            self.write_spawn_ini(scenario, difficulty_value, game_speed_value)
            self.write_launch_options(difficulty_value, game_speed_value)
        except Exception:
            self.cleanup_generated_root_maps()
            self.disable_generated_rules_for_client()
            raise
        return hook

    def start_mission_process(
        self,
        mission,
        hook,
        difficulty_value,
        game_speed_value,
        launch_note='',
    ):
        scenario = mission['scenario']
        cmd = self.build_command()
        self.append_log('Attempting game launch via: ' + cmd)

        try:
            process = subprocess.Popen(cmd, cwd=GAME_ROOT)
            self.append_log(f'Launched game process PID={process.pid}.')
            if self.state and mission.get('code') in self.state.get('mission_order', []):
                try:
                    started_missions = self.state.setdefault('started_missions', [])
                    if mission['code'] not in started_missions:
                        started_missions.append(mission['code'])
                        self.save_state()
                        self.redraw_mission_tree()
                        self.refresh_progress_view()
                except Exception:
                    self.append_log('Could not persist the mission in-progress state.', error=True)
                    log_event(
                        'mission_started_state_save_failed',
                        level=logging.ERROR,
                        code=mission.get('code'),
                        traceback=traceback.format_exc(),
                    )
            log_event(
                'mission_process_started',
                pid=process.pid,
                code=mission.get('code'),
                title=mission.get('title'),
                scenario=scenario,
                command=cmd,
                difficulty=difficulty_value,
                game_speed=game_speed_value,
                hook_markers=(hook or {}).get('markers', {}),
                generated_map=(hook or {}).get('generated_map'),
            )
            if launch_note:
                self.append_log(launch_note)
            self.active_game_process = process
            self.active_hook = hook
            if self.active_hook is not None:
                self.active_hook['scenario_ready'] = False
            self.active_mission_attempt = {
                'mission_code': mission.get('code'),
                'scenario': scenario,
            }
            self.after(HOOK_POLL_MS, self.poll_hook_log)
        except Exception:
            self.cleanup_generated_root_maps()
            self.disable_generated_rules_for_client()
            self.append_log('Failed to launch game process:', error=True)
            self.append_log(traceback.format_exc(), error=True)
            messagebox.showerror('Launch Failed', 'Failed to launch the game. See log for details.')
        else:
            self.append_log(
                'Objective/victory hooks are watching debug.log. A detected victory will update the run automatically.'
            )

    def reward_group_label(self, tech_id):
        return unit_display_label(tech_id)

    def unit_faction(self, tech_id):
        factions = BUFF_TARGETS.get(tech_id, {}).get('factions') or []
        if len(factions) == 1:
            return factions[0]
        return 'Global' if factions else 'Other'

    def unit_faction_sort_key(self, tech_id):
        faction = self.unit_faction(tech_id)
        rank = FACTION_ORDER.index(faction) if faction in FACTION_ORDER else len(FACTION_ORDER)
        return (rank, unit_display_label(tech_id).lower())

    def mission_assistance_effect_text(self, stacks):
        multipliers = mission_assistance_multipliers(stacks)
        range_cells = multipliers['range']
        range_unit = 'cell' if range_cells == 1 else 'cells'
        return (
            f'production time {round((1 - multipliers["production"]) * 100)}% shorter, '
            f'cost {round((1 - multipliers["cost"]) * 100)}% cheaper, '
            f'movement speed {round((multipliers["speed"] - 1) * 100)}% faster '
            f'(infantry capped at Speed 8), '
            f'health {round((multipliers["health"] - 1) * 100)}% higher, '
            f'weapon damage {round((multipliers["damage"] - 1) * 100)}% higher, '
            f'damage taken {round((1 - multipliers["armor"]) * 100)}% lower, '
            f'fire rate {round(((1 / multipliers["rof"]) - 1) * 100)}% faster, '
            f'attack range +{range_cells:g} {range_unit}'
        )

    def current_unlocks_text(self):
        if not self.state:
            return 'No randomizer seed generated yet.'

        lines = []
        starting_unit_ids = self.active_starting_tier_one_unit_ids()
        if starting_unit_ids:
            heading = 'Starting Tier 1 Units'
            lines.extend([heading, '=' * len(heading)])
            for unit_id in sorted(set(starting_unit_ids), key=self.unit_faction_sort_key):
                lines.append(unit_display_label(unit_id))
            lines.append('')
        selected = self.selected_mission()
        if selected and self.failure_assistance_enabled():
            code = selected['code']
            stacks = self.mission_failure_stack(code)
            if stacks:
                heading = f'Retry Assistance — {selected["title"]}'
                lines.extend([
                    heading,
                    '=' * len(heading),
                    f'{stacks} stack(s), for this mission only',
                    self.mission_assistance_effect_text(stacks).capitalize() + '.',
                    '',
                ])

        earned = [canonical_reward(reward) for reward in self.earned_rewards_from_checks()]
        if not earned:
            if lines:
                return '\n'.join(lines).rstrip()
            return 'No unlocks or buffs earned yet.'

        groups = {}
        shared_groups = {}
        share_chaos_role_buffs = self.share_chaos_role_buffs_enabled()
        share_foehn_roles = self.foehn_standard_bundles_enabled()

        def group_for(tech_id):
            group = groups.setdefault(tech_id, {
                'label': self.reward_group_label(tech_id),
                'access': {},
                'buffs': {},
                'other': [],
            })
            return group

        for reward in earned:
            bundle_units = reward.get('bundle_units') or []
            if bundle_units:
                unit_ids = tuple(sorted(set(bundle_units), key=self.unit_faction_sort_key))
                shared_group = shared_groups.setdefault(
                    unit_ids,
                    {'access': {}, 'buffs': {}},
                )
                shared_group['access'].setdefault(reward.get('name', 'Shared Access'), reward)
                continue

            if reward.get('kind') == 'buff' and reward.get('unit'):
                source_unit = reward['unit']
                equivalent_units = unit_role_equivalents(source_unit)
                if (
                    (share_chaos_role_buffs or share_foehn_roles)
                    and not reward.get('global_buff')
                    and len(equivalent_units) > 1
                ):
                    if share_foehn_roles:
                        equivalent_units = {
                            unit_id
                            for unit_id in equivalent_units
                            if self.unit_faction(unit_id) in {'Allies', 'Soviets'}
                        }
                    if len(equivalent_units) < 2:
                        group = group_for(source_unit)
                        key = reward.get('buff_type', reward.get('name', 'buff'))
                        entry = group['buffs'].setdefault(
                            key,
                            {'reward': reward, 'count': 0},
                        )
                        entry['count'] += 1
                        continue
                    unit_ids = tuple(sorted(equivalent_units, key=self.unit_faction_sort_key))
                    shared_group = shared_groups.setdefault(
                        unit_ids,
                        {'access': {}, 'buffs': {}},
                    )
                    key = reward.get('buff_type', reward.get('name', 'buff'))
                    display_reward = dict(reward)
                    display_reward.pop('name', None)
                    entry = shared_group['buffs'].setdefault(
                        key,
                        {'reward': display_reward, 'count': 0},
                    )
                    entry['count'] += 1
                else:
                    group = group_for(source_unit)
                    key = reward.get('buff_type', reward.get('name', 'buff'))
                    entry = group['buffs'].setdefault(key, {'reward': reward, 'count': 0})
                    entry['count'] += 1
                continue

            tech_ids = sorted(tech_ids_for_rewards([reward]))
            if tech_ids:
                for tech_id in tech_ids:
                    group_for(tech_id)['access'].setdefault(reward.get('name', tech_id), reward)
            else:
                groups.setdefault('Other', {
                    'label': 'Other',
                    'access': {},
                    'buffs': {},
                    'other': [],
                })['other'].append(reward)

        if shared_groups:
            heading = (
                'Shared Allied / Soviet Bundles'
                if share_foehn_roles
                else 'Shared Unit Buffs'
            )
            lines.append(heading)
            lines.append('=' * len(heading))
            lines.append(
                'Each pictured role is earned together; listed bonuses apply to every pictured unit.'
                if share_foehn_roles
                else 'Every pictured unit receives the bonuses listed beneath its group.'
            )
            lines.append('')
            for unit_ids, shared_group in sorted(
                shared_groups.items(),
                key=lambda item: tuple(unit_display_label(unit_id) for unit_id in item[0]),
            ):
                lines.append(f'[[MOR_SHARED:{",".join(unit_ids)}]]')
                lines.append('  •  '.join(unit_display_label(unit_id) for unit_id in unit_ids))
                for reward in sorted(
                    shared_group['access'].values(),
                    key=lambda item: item.get('name', ''),
                ):
                    source_names = reward.get('bundle_reward_names') or [reward_display_name(reward)]
                    lines.append('  Shared access: ' + '  •  '.join(source_names))
                for _, entry in sorted(shared_group['buffs'].items()):
                    reward = entry['reward']
                    count = effective_buff_count(reward, entry['count'])
                    for summary in buff_effect_lines(reward, count=count, include_label=False):
                        lines.append(f'  {summary}')
                lines.append('')

        current_faction = None
        for tech_id in sorted(groups, key=self.unit_faction_sort_key):
            group = groups[tech_id]
            faction = self.unit_faction(tech_id)
            if faction != current_faction:
                if lines and lines[-1] != '':
                    lines.append('')
                heading = (
                    f'{faction} Units'
                    if faction in FACTION_ORDER
                    else f'{faction} Rewards'
                )
                lines.append(heading)
                lines.append('=' * len(heading))
                lines.append('')
                current_faction = faction
            lines.append(group['label'])
            lines.append('-' * len(group['label']))

            if group['access']:
                for reward in sorted(group['access'].values(), key=lambda item: item.get('name', '')):
                    lines.append(reward_display_name(reward))

            if group['buffs']:
                for _, entry in sorted(group['buffs'].items()):
                    reward = entry['reward']
                    count = effective_buff_count(reward, entry['count'])
                    for summary in buff_effect_lines(reward, count=count, include_label=False):
                        lines.append(f'  {summary}')

            for reward in group['other']:
                power_token = ''
                if reward.get('kind') == 'superweapon' and reward.get('superweapon'):
                    cameo_superweapon = reward.get('cameo_superweapon', reward['superweapon'])
                    power_token = f'[[MOR_POWER:{cameo_superweapon}]]'
                lines.append(f'{power_token}Reward: {reward_display_name(reward)}')
                for summary in reward_rule_summary(reward):
                    lines.append(f'  {summary}')

            lines.append('')

        return '\n'.join(lines).rstrip()

    def current_unlock_unit_ids(self):
        if not self.state:
            return []
        unit_ids = set(self.active_starting_tier_one_unit_ids())
        share_chaos_role_buffs = self.share_chaos_role_buffs_enabled()
        share_foehn_roles = self.foehn_standard_bundles_enabled()
        for reward in self.earned_rewards_from_checks():
            reward = canonical_reward(reward)
            if reward.get('kind') == 'buff' and reward.get('unit'):
                if reward['unit'] != 'MOR_BUILDINGS':
                    if (
                        (share_chaos_role_buffs or share_foehn_roles)
                        and not reward.get('global_buff')
                    ):
                        equivalents = unit_role_equivalents(reward['unit'])
                        if share_foehn_roles:
                            equivalents = {
                                unit_id
                                for unit_id in equivalents
                                if self.unit_faction(unit_id) in {'Allies', 'Soviets'}
                            }
                        unit_ids.update(equivalents)
                    else:
                        unit_ids.add(reward['unit'])
                continue
            unit_ids.update(tech_ids_for_rewards([reward]))
        return sorted(unit_ids, key=self.unit_faction_sort_key)

    def refresh_progress_view(self):
        if not self.state:
            self.progress_label.config(text='No randomizer seed generated. Vanilla mission launching is still available.')
            self.set_rewards_text('')
            self.set_unlocks_text('No randomizer seed generated yet.')
            return

        completed = len(self.state.get('completed_missions', []))
        order = self.state.get('mission_order', [])
        unlocked = len([
            code for code in self.unlocked_mission_codes()
            if code not in self.state.get('completed_missions', [])
        ])
        earned = self.state.get('earned_rewards', [])
        goal = self.state.get('mission_goal', len(order))
        progression_mode = self.active_progression_mode()
        run_complete = self.is_run_complete()
        status = (
            'Victory achieved'
            if progression_mode == 'Grid Mode' and run_complete
            else 'Finished'
            if run_complete
            else 'In progress'
        )
        self.progress_label.config(
            text=(
                f'Seed: {self.state.get("seed", "")} | {progression_mode} | '
                f'Rewards: {self.state.get("reward_mode", REWARD_MODES[0])}\n'
                f'Completed: {completed}/{goal} | Open: {unlocked} | Rewards: {len(earned)} | {status}'
            )
        )

        lines = []
        selected = self.selected_mission()
        if selected:
            code = selected['code']
            done_checks, total_checks = self.mission_check_counts(code)
            lines.append(selected['title'])
            lines.append(f'Code: {code}  •  Faction: {selected.get("side", "Unknown")}')
            if progression_mode == 'Grid Mode':
                node = self.state.get('grid', {}).get('nodes', {}).get(code, {})
                node_state = node.get('state', GRID_LOCKED).title()
                if self.is_mission_started(code):
                    node_state = 'In Progress'
                lines.append(
                    f'Grid: column {int(node.get("x", 0)) + 1}, row {int(node.get("y", 0)) + 1}  '
                    f'•  {node_state}'
                )
                unlocks = self.mission_unlocks(code)
                if code == self.state.get('grid', {}).get('goal') and node.get('state') != GRID_COMPLETED:
                    lines.append(
                        'Completing this endgoal records Randomizer victory, releases every '
                        'pending reward, and unlocks every unfinished grid mission.'
                    )
                elif unlocks:
                    lookup = self.mission_lookup()
                    labels = [lookup.get(item, {}).get('title', item) for item in unlocks]
                    lines.append('Completing this node unlocks: ' + ', '.join(labels))
                elif node.get('state') == GRID_COMPLETED:
                    lines.append('This node is complete; its neighbors are already open.')
                else:
                    lines.append('Completing this node does not unlock a currently locked neighbor.')
            lines.append(f'Reward progress: {done_checks}/{total_checks}')
            if self.failure_assistance_enabled():
                assistance_stacks = self.mission_failure_stack(code)
                if assistance_stacks:
                    lines.append(
                        f'Retry assistance: {assistance_stacks} stack(s), for this mission only'
                    )
                    lines.append(
                        'Current retry buffs: '
                        + self.mission_assistance_effect_text(assistance_stacks)
                        + '.'
                    )
                    lines.append('Completing the mission removes all of its retry assistance stacks.')
                else:
                    lines.append('Retry assistance: 0 stacks for this mission')
            lines.append('')
            for check in self.mission_checks(code):
                status_label = (
                    'Complete'
                    if check.get('unlocked')
                    else 'Reward Released'
                    if check.get('released')
                    else 'Pending'
                )
                rewards = check_rewards(check)
                lines.append(
                    f'{status_label}: {check.get("name", "Check")} — {len(rewards)} reward(s)'
                )
                hint = check.get('hint')
                if hint:
                    lines.append(f'   {hint}')
                if rewards:
                    for reward in rewards:
                        reward_name = (
                            '?????'
                            if self.hide_reward_details_var.get()
                            else reward_display_name(reward)
                        )
                        lines.append(f'   • {reward_name}')
                else:
                    lines.append('   • No reward assigned')
            lines.append('')
            lines.append('Earned reward details are grouped in the Unlocks tab.')
        elif not lines:
            lines.append('No rewards earned yet.')

        self.set_rewards_text('\n'.join(lines))
        self.set_unlocks_text(self.current_unlocks_text(), self.current_unlock_unit_ids())

    def set_rewards_text(self, text):
        self.rewards_text.configure(state='normal')
        self.rewards_text.delete('1.0', 'end')
        self.rewards_text.insert('end', text)
        self.rewards_text.configure(state='disabled')

    def set_unlocks_text(self, text, unit_ids=None):
        self.unlocks_text.configure(state='normal')
        self.unlocks_text.delete('1.0', 'end')
        self.unlocks_text.insert('end', text)
        self.unlock_cameo_images = {}
        if unit_ids:
            try:
                cameo_paths = ensure_unit_cameos(unit_ids)
            except Exception:
                cameo_paths = {}
                log_event('cameo_load_failed', level=logging.ERROR, traceback=traceback.format_exc())
            log_event(
                'cameos_resolved',
                requested=len(unit_ids),
                resolved=len(cameo_paths),
                missing=sorted(set(unit_ids) - set(cameo_paths)),
            )
            photos = {}
            for unit_id in unit_ids:
                cameo_path = cameo_paths.get(unit_id)
                if not cameo_path:
                    continue
                photo = self.cameo_photo_cache.get(unit_id)
                if photo is None:
                    try:
                        photo = tk.PhotoImage(file=str(cameo_path))
                    except tk.TclError:
                        continue
                    self.cameo_photo_cache[unit_id] = photo
                photos[unit_id] = photo
                self.unlock_cameo_images[unit_id] = photo

            shared_rows = re.findall(r'\[\[MOR_SHARED:([A-Z0-9_,]+)\]\]', text)
            for shared_ids in shared_rows:
                token = f'[[MOR_SHARED:{shared_ids}]]'
                position = self.unlocks_text.search(token, '1.0', stopindex='end', exact=True)
                if not position:
                    continue
                self.unlocks_text.delete(position, f'{position}+{len(token)}c')
                row_units = [unit_id for unit_id in shared_ids.split(',') if unit_id]
                has_content = False
                for unit_id in reversed(row_units):
                    if has_content:
                        self.unlocks_text.insert(position, '   ')
                    photo = photos.get(unit_id)
                    if photo is not None:
                        self.unlocks_text.image_create(
                            position,
                            image=photo,
                            align='center',
                            padx=3,
                            pady=2,
                        )
                    else:
                        self.unlocks_text.insert(position, '[no cameo]')
                    has_content = True

            for unit_id in unit_ids:
                photo = photos.get(unit_id)
                if photo is None:
                    continue
                label = unit_display_label(unit_id)
                position = self.unlocks_text.search(label, '1.0', stopindex='end', exact=True)
                while position:
                    line_text = self.unlocks_text.get(f'{position} linestart', f'{position} lineend')
                    if line_text == label:
                        break
                    position = self.unlocks_text.search(
                        label,
                        f'{position}+{len(label)}c',
                        stopindex='end',
                        exact=True,
                    )
                if not position:
                    continue
                self.unlocks_text.image_create(
                    position,
                    image=photo,
                    align='center',
                    padx=5,
                    pady=2,
                )

        power_ids = sorted(set(re.findall(r'\[\[MOR_POWER:([A-Za-z0-9_]+)\]\]', text)))
        if power_ids:
            try:
                power_cameo_paths = ensure_superweapon_cameos(power_ids)
            except Exception:
                power_cameo_paths = {}
                log_event(
                    'superweapon_cameo_load_failed',
                    level=logging.ERROR,
                    traceback=traceback.format_exc(),
                )
            normalized_power_ids = {power_id.upper() for power_id in power_ids}
            log_event(
                'superweapon_cameos_resolved',
                requested=len(normalized_power_ids),
                resolved=len(power_cameo_paths),
                missing=sorted(normalized_power_ids - set(power_cameo_paths)),
            )
            for power_id in power_ids:
                token = f'[[MOR_POWER:{power_id}]]'
                position = self.unlocks_text.search(token, '1.0', stopindex='end', exact=True)
                while position:
                    self.unlocks_text.delete(position, f'{position}+{len(token)}c')
                    cache_key = f'power:{power_id.upper()}'
                    photo = self.cameo_photo_cache.get(cache_key)
                    cameo_path = power_cameo_paths.get(power_id.upper())
                    if photo is None and cameo_path:
                        try:
                            photo = tk.PhotoImage(file=str(cameo_path))
                        except tk.TclError:
                            photo = None
                        if photo is not None:
                            self.cameo_photo_cache[cache_key] = photo
                    if photo is not None:
                        self.unlocks_text.image_create(
                            position,
                            image=photo,
                            align='center',
                            padx=5,
                            pady=2,
                        )
                        self.unlock_cameo_images[cache_key] = photo
                    position = self.unlocks_text.search(
                        token,
                        position,
                        stopindex='end',
                        exact=True,
                    )
        self.unlocks_text.configure(state='disabled')
        self.refresh_unlock_search()


def main():
    app = LauncherApp()
    app.mainloop()
