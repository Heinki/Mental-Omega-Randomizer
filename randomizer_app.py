import json
import logging
import random
import re
import shutil
import subprocess
import traceback

from randomizer_config import CONFIG_PATH, load_config, save_config
from randomizer_cameos import (
    ensure_superweapon_cameos,
    ensure_unit_cameos,
    mix_reader_assembly_paths,
    powershell_mix_reader_load_script,
)
from randomizer_diagnostics import event as log_event
from grid_progression import (
    COMPLETED as GRID_COMPLETED,
    LOCKED as GRID_LOCKED,
    UNLOCKED as GRID_UNLOCKED,
    completing_unlocks,
    create_grid,
    is_complete as is_grid_complete,
    refresh_states as refresh_grid_states,
)
from randomizer_rewards import (
    BUFF_TARGETS,
    BUFF_TYPES,
    DEFAULT_REWARDS_PER_CHECK,
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
    APP_DIR,
    BATTLE_CLIENT_INI,
    DEBUG_LOG,
    DISABLED_RULESMO_INI,
    EXTRACTED_MAP_DIR,
    GAME_EXE,
    GAME_LAUNCHER_EXE,
    GAME_ROOT,
    GENERATED_MAP_DIR,
    LAUNCHER_LOG,
    MAP_RENDERER_DIR,
    OPTIONS_INI,
    RULESMO_INI,
    SPAWN_INI,
    STATE_PATH,
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
    append_superweapon_grant_trigger,
    backup_file_once,
    clone_player_country_for_house_buffs,
    controlled_tech_ids,
    find_section_bounds,
    hook_marker_name,
    is_generated_hooked_map,
    is_generated_rules_file,
    insert_actions_before_codes,
    allied_helper_houses,
    country_family,
    launch_rules_for_reward,
    map_house_records,
    merge_ini_section_values,
    now_stamp,
    player_country_buff_rules,
    player_country_from_map,
    player_house_from_map,
    read_text,
    remove_locked_techlevel_actions,
    section_lines,
    section_value_map,
    set_ini_value_lines,
    stacked_house_buff_values,
    superweapon_actions_for_rewards,
    superweapon_rule_sections_for_rewards,
    tech_ids_for_rewards,
    unlocked_reward_tech_ids,
    trigger_action_ids_by_name,
    unique_in_order,
    unit_weapon_buff_rules,
)
from randomizer_mission_safety import (
    chaos_earned_access_rules,
    mission_basic_unit_rules,
    summarize_basic_unit_rules,
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
PROGRESSION_MODES = ['Mission List', 'Grid Mode']

STARTING_UNLOCKED_MISSIONS = 3
DEFAULT_MISSION_GOAL = 15
FALLBACK_OBJECTIVE_COUNT = 3
CHECK_SCHEMA_VERSION = 16
HOOK_POLL_MS = 1500
VICTORY_CLOSE_DELAY_MS = 2500
MAX_OPTION_INI_BYTES = 2 * 1024 * 1024
MAX_GLOBAL_BUFF_REPEATS_PER_SEED = 3
GLOBAL_BUFF_REWARD_INTERVAL = 10
FACTION_ORDER = ('Allies', 'Soviets', 'Epsilon', 'Foehn')
FACTION_TILE_COLORS = {
    'Allies': '#285f9e',
    'Soviets': '#a53636',
    'Epsilon': '#70429a',
    'Foehn': '#16898b',
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
        self.title('Mental Omega Randomizer Launcher')
        self.geometry('1240x760')
        self.minsize(940, 560)
        self.resizable(True, True)

        self.missions = []
        self.config = load_config()
        self.state = self.load_state()
        self.migrate_state()
        self._reward_settings_override = None
        self.active_game_process = None
        self.active_hook = None
        self.mission_sort_column = None
        self.mission_sort_reverse = False
        self.grid_render_signature = None
        self.grid_tile_widgets = {}
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
            PROGRESSION_MODES[0],
        )
        self.progression_mode_var = tk.StringVar(value=progression_mode_default)
        grid_state = self.state.get('grid', {}) if isinstance(self.state.get('grid'), dict) else {}
        self.grid_two_starts_var = tk.BooleanVar(
            value=bool(grid_state.get(
                'two_start_positions',
                self.config.get('grid_two_start_positions', False),
            ))
        )
        reward_settings = self.config_reward_settings()
        enabled_buff_types = set(reward_settings['enabled_buff_types'])
        self.buff_allied_helpers_var = tk.BooleanVar(
            value=bool(generation_config.get('buff_allied_helpers', False))
        )
        self.randomize_unit_access_var = tk.BooleanVar(
            value=reward_settings['randomize_unit_access']
        )
        self.include_defensive_buildings_var = tk.BooleanVar(
            value=reward_settings['include_defensive_buildings']
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
        self.cleanup_generated_root_maps()
        self.disable_generated_rules_for_client()

        self.create_widgets()
        self.refresh_missions()
        self.refresh_progress_view()
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

        style = ttk.Style(self)
        style.configure('Randomizer.TNotebook', tabposition='n')
        style.configure('Randomizer.TNotebook.Tab', padding=(16, 7), font=('Segoe UI', 10, 'bold'))
        style.configure('Launch.TButton', font=('Segoe UI', 10, 'bold'), padding=(10, 7))

        header = ttk.Label(main_frame, text='Mental Omega Randomizer Launcher', font=('Segoe UI', 14, 'bold'))
        header.grid(row=0, column=0, columnspan=4, sticky='w')
        ttk.Label(
            main_frame,
            text='Choose an open mission, earn randomized upgrades, and let victory tracking update your run.',
            foreground='#555555',
        ).grid(row=1, column=0, columnspan=4, sticky='w', pady=(2, 10))

        self.missions_tree = ttk.Treeview(
            main_frame,
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
        self.missions_tree.grid(row=2, column=0, rowspan=5, sticky='nsew', padx=(0, 8))
        self.missions_tree.bind('<<TreeviewSelect>>', self.on_mission_select, add='+')
        self.mission_tooltip = TreeTooltip(self.missions_tree, self.mission_tooltip_text)

        tree_scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=self.missions_tree.yview)
        tree_scrollbar.grid(row=2, column=1, rowspan=5, sticky='ns')
        self.missions_tree.configure(yscrollcommand=tree_scrollbar.set)
        self.tree_scrollbar = tree_scrollbar

        self.grid_frame = ttk.Frame(main_frame, padding=(4, 4, 4, 4))
        self.grid_frame.grid(row=2, column=0, columnspan=2, rowspan=5, sticky='nsew', padx=(0, 8))
        self.grid_placeholder = ttk.Label(
            self.grid_frame,
            text='Generate a Grid Mode seed to create the mission grid.',
            anchor='center',
            justify='center',
        )

        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=2, column=2, rowspan=5, sticky='nsew')
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
            'Also applies earned buffs to AI-controlled allied helper houses. '
            'Player-controlled allied houses are always included.',
        )
        ttk.Label(options_row, text='Reward mode').grid(row=3, column=0, sticky='w', pady=(6, 0), padx=(0, 8))
        self.reward_mode_combo = ttk.Combobox(
            options_row,
            state='readonly',
            textvariable=self.reward_mode_var,
            values=REWARD_MODES,
            width=20,
        )
        self.reward_mode_combo.grid(row=3, column=1, columnspan=3, sticky='ew', pady=(6, 0))
        self.reward_mode_combo.bind('<<ComboboxSelected>>', self.on_reward_mode_changed, add='+')
        WidgetTooltip(
            self.reward_mode_combo,
            'Standard uses campaign-appropriate factions and translates equivalent roles on mixed maps. '
            'Chaos draws units from all four factions, forces randomized access/tech locking, and lets '
            'earned units use matching production structures that the mission gives the player. It does '
            'not grant foreign production structures.',
        )

        ttk.Label(options_row, text='Progression').grid(row=4, column=0, sticky='w', pady=(6, 0), padx=(0, 8))
        self.progression_mode_combo = ttk.Combobox(
            options_row,
            state='readonly',
            textvariable=self.progression_mode_var,
            values=PROGRESSION_MODES,
            width=12,
        )
        self.progression_mode_combo.grid(row=4, column=1, sticky='ew', pady=(6, 0))
        self.progression_mode_combo.bind('<<ComboboxSelected>>', self.on_progression_mode_changed, add='+')

        self.grid_options_frame = ttk.Frame(options_row)
        self.grid_options_frame.grid(row=5, column=0, columnspan=4, sticky='ew', pady=(6, 0))
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
            background=style.lookup('TFrame', 'background') or '#f0f0f0',
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
            text='Settings are saved for the next generated seed. Existing runs keep the settings they were generated with.',
            wraplength=340,
            foreground='#555555',
        )
        self.settings_intro_label.grid(row=0, column=0, sticky='ew', pady=(0, 8))

        reward_frame = ttk.LabelFrame(settings_frame, text='Reward Pool', padding=(8, 8, 8, 8))
        reward_frame.grid(row=1, column=0, sticky='ew')
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
        self.include_defensive_buildings_check = ttk.Checkbutton(
            reward_frame,
            text='Include defensive building rewards',
            variable=self.include_defensive_buildings_var,
        )
        self.include_defensive_buildings_check.grid(row=1, column=0, sticky='w', pady=(4, 0))
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
        self.include_buff_rewards_check.grid(row=2, column=0, sticky='w', pady=(4, 0))
        WidgetTooltip(
            self.include_buff_rewards_check,
            'Adds repeatable stat upgrades to the reward pool. Turning this off disables all buff-only settings below.',
        )
        self.share_chaos_role_buffs_check = ttk.Checkbutton(
            reward_frame,
            text='Share buffs with equivalent units (Chaos only)',
            variable=self.share_chaos_role_buffs_var,
        )
        self.share_chaos_role_buffs_check.grid(row=3, column=0, sticky='w', pady=(4, 0))
        WidgetTooltip(
            self.share_chaos_role_buffs_check,
            'In Chaos, a buff for one curated role also affects its peers—for example GI, Conscript, '
            'Initiate, and Knightframe. Shared groups are displayed together in Unlocks.',
        )
        self.include_superweapon_rewards_check = ttk.Checkbutton(
            reward_frame,
            text='Include offensive superweapon rewards',
            variable=self.include_superweapon_rewards_var,
        )
        self.include_superweapon_rewards_check.grid(row=4, column=0, sticky='w', pady=(4, 0))
        WidgetTooltip(
            self.include_superweapon_rewards_check,
            'Adds Lightning Storm, Tactical Nuke, Psychic Dominator, and Great Tempest as building-free rewards.',
        )
        self.include_secondary_superweapon_rewards_check = ttk.Checkbutton(
            reward_frame,
            text='Include secondary superweapon rewards',
            variable=self.include_secondary_superweapon_rewards_var,
        )
        self.include_secondary_superweapon_rewards_check.grid(row=5, column=0, sticky='w', pady=(4, 0))
        WidgetTooltip(
            self.include_secondary_superweapon_rewards_check,
            'Adds Chronoshift, Invulnerability, Rage, and Blasticade as building-free rewards.',
        )
        self.include_aid_power_rewards_check = ttk.Checkbutton(
            reward_frame,
            text='Include aid/reinforcement power rewards',
            variable=self.include_aid_power_rewards_var,
        )
        self.include_aid_power_rewards_check.grid(row=6, column=0, sticky='w', pady=(4, 0))
        WidgetTooltip(
            self.include_aid_power_rewards_check,
            'Adds faction unit drops, temporary reinforcements, deployable towers, mines, and other delivery-based support actions.',
        )

        buff_frame = ttk.LabelFrame(settings_frame, text='Enabled Buff Types', padding=(8, 8, 8, 8))
        buff_frame.grid(row=2, column=0, sticky='ew', pady=(8, 0))
        for column in range(2):
            buff_frame.columnconfigure(column, weight=1)
        self.buff_type_checks = []
        for index, buff_type in enumerate(BUFF_TYPES):
            row, column = divmod(index, 2)
            check = ttk.Checkbutton(
                buff_frame,
                text=buff_type.get('setting_label', buff_type['name']),
                variable=self.buff_type_vars[buff_type['id']],
            )
            check.grid(row=row, column=column, sticky='w', padx=(0, 10), pady=(0, 3))
            self.buff_type_checks.append(check)
            description = buff_type.get('description', '').format(plural='Affected units')
            WidgetTooltip(check, description)

        self.refresh_setting_states()

        self.status_label = ttk.Label(main_frame, text='Ready', anchor='w')
        self.status_label.grid(row=7, column=0, columnspan=3, sticky='ew', pady=(8, 0))

        log_header = ttk.Frame(main_frame)
        log_header.grid(row=8, column=0, columnspan=3, sticky='ew', pady=(12, 4))
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
        self.log_text.grid(row=9, column=0, columnspan=3, sticky='nsew')
        self.log_text.grid_remove()

        main_frame.rowconfigure(2, weight=1)
        main_frame.rowconfigure(9, weight=0)
        main_frame.columnconfigure(0, weight=4)
        main_frame.columnconfigure(2, weight=3)

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

    def append_log(self, message, error=False):
        log_event(
            'launcher_message',
            level=logging.ERROR if error else logging.INFO,
            message=str(message),
        )
        self.log_text.configure(state='normal')
        self.log_text.insert('end', f'{message}\n')
        if error:
            self.log_text.tag_add('error', 'end-2l', 'end-1c')
            self.log_text.tag_config('error', foreground='red')
        self.log_text.configure(state='disabled')
        self.log_text.see('end')
        self.status_label.config(text='Error' if error else message[:120])
        self.update_idletasks()

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
        include_buffs = bool(generation_config.get('include_buff_rewards', 'buff' in enabled_reward_types))
        include_superweapons = bool(generation_config.get('include_superweapon_rewards', True))
        include_secondary_superweapons = bool(
            generation_config.get('include_secondary_superweapon_rewards', True)
        )
        include_aid_powers = bool(generation_config.get('include_aid_power_rewards', True))
        include_defensive_buildings = bool(generation_config.get('include_defensive_buildings', True))
        share_chaos_role_buffs = bool(generation_config.get('share_chaos_role_buffs', False))
        buff_allied_helpers = bool(generation_config.get('buff_allied_helpers', False))
        if generation_config.get('reward_mode') == 'Chaos (Experimental)':
            randomize_access = True
        return {
            'randomize_unit_access': randomize_access,
            'include_defensive_buildings': include_defensive_buildings,
            'share_chaos_role_buffs': share_chaos_role_buffs,
            'buff_allied_helpers': buff_allied_helpers,
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
        include_defensive_buildings = bool(self.include_defensive_buildings_var.get())
        share_chaos_role_buffs = bool(self.share_chaos_role_buffs_var.get())
        buff_allied_helpers = bool(self.buff_allied_helpers_var.get())
        include_buffs = bool(self.include_buff_rewards_var.get())
        include_superweapons = bool(self.include_superweapon_rewards_var.get())
        include_secondary_superweapons = bool(self.include_secondary_superweapon_rewards_var.get())
        include_aid_powers = bool(self.include_aid_power_rewards_var.get())
        enabled_buff_types = [
            buff_type['id']
            for buff_type in BUFF_TYPES
            if self.buff_type_vars[buff_type['id']].get()
        ]
        return {
            'randomize_unit_access': randomize_access,
            'include_defensive_buildings': include_defensive_buildings,
            'share_chaos_role_buffs': share_chaos_role_buffs,
            'buff_allied_helpers': buff_allied_helpers,
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
        settings.setdefault('include_defensive_buildings', True)
        settings.setdefault('share_chaos_role_buffs', False)
        settings.setdefault(
            'buff_allied_helpers',
            bool(self.config.get('generation', {}).get('buff_allied_helpers', False)),
        )
        if self.active_reward_mode() == 'Chaos (Experimental)':
            settings['randomize_unit_access'] = True
        settings.setdefault('include_buff_rewards', True)
        settings.setdefault('include_superweapon_rewards', False)
        settings.setdefault('include_secondary_superweapon_rewards', False)
        settings.setdefault('include_aid_power_rewards', False)
        if not isinstance(settings.get('enabled_buff_types'), list):
            settings['enabled_buff_types'] = [buff_type['id'] for buff_type in BUFF_TYPES]
        return settings

    def randomize_unit_access_enabled(self):
        return bool(self.active_reward_settings().get('randomize_unit_access', True))

    def share_chaos_role_buffs_enabled(self):
        return bool(
            self.active_reward_mode() == 'Chaos (Experimental)'
            and self.active_reward_settings().get('share_chaos_role_buffs', False)
        )

    def buff_rewards_enabled(self):
        return bool(self.active_reward_settings().get('include_buff_rewards', True))

    def active_reward_mode(self):
        if self.__dict__.get('_reward_settings_override') is not None and hasattr(self, 'reward_mode_var'):
            return self.reward_mode_var.get()
        if self.state:
            return self.state.get('reward_mode', REWARD_MODES[0])
        if hasattr(self, 'reward_mode_var'):
            return self.reward_mode_var.get()
        return REWARD_MODES[0]

    def save_launcher_config(self, seed, mission_goal, rewards_per_check):
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
        self.config['generation']['buff_allied_helpers'] = bool(self.buff_allied_helpers_var.get())
        self.config['generation']['enabled_reward_types'] = reward_settings['enabled_reward_types']
        self.config['generation']['randomize_unit_access'] = reward_settings['randomize_unit_access']
        self.config['generation']['include_defensive_buildings'] = reward_settings['include_defensive_buildings']
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
        return {mission['code']: mission for mission in self.missions}

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

    def normalize_faction(self, side):
        side = (side or '').strip().lower()
        if 'allies' in side or 'allied' in side:
            return 'Allies'
        if 'soviet' in side:
            return 'Soviets'
        if 'epsilon' in side:
            return 'Epsilon'
        if 'foehn' in side:
            return 'Foehn'
        return ''

    def foehn_standard_bundles_enabled(self):
        selected = (
            self.campaign_var.get()
            if hasattr(self, 'campaign_var')
            else (self.state or {}).get('campaign_filter', '')
        )
        mode = (
            self.reward_mode_var.get()
            if hasattr(self, 'reward_mode_var')
            else self.active_reward_mode()
        )
        return selected == 'Foehn' and mode == 'Standard'

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
        reward_mode = self.reward_mode_var.get() if hasattr(self, 'reward_mode_var') else REWARD_MODES[0]
        if reward_mode == 'Chaos (Experimental)':
            return self.configured_reward_pool()
        factions = self.reward_factions_for_code(code)
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
        randomize_access = bool(reward_settings.get('randomize_unit_access', True))
        include_buffs = bool(reward_settings.get('include_buff_rewards', True))
        include_superweapons = bool(reward_settings.get('include_superweapon_rewards', False))
        include_secondary_superweapons = bool(
            reward_settings.get('include_secondary_superweapon_rewards', False)
        )
        include_aid_powers = bool(reward_settings.get('include_aid_power_rewards', False))
        include_defensive_buildings = bool(reward_settings.get('include_defensive_buildings', True))
        enabled_buff_types = set(reward_settings.get('enabled_buff_types') or [])
        chaos_mode = (
            hasattr(self, 'reward_mode_var')
            and self.reward_mode_var.get() == 'Chaos (Experimental)'
        )
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
                )
            )
        ]

    def reward_factions_for_code(self, code):
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
        )
        self.state['mission_objectives'] = summary
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
        rewards_by_code = self.generate_seed_reward_plan(mission_codes, seed, slots_by_code)

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
                if old_check and old_check.get('unlocked') and check_rewards(old_check):
                    rewards_for_check = check_rewards(old_check)
                    unlocked = True
                elif check_id == 'objective_1' and code in completed_rewards:
                    rewards_for_check = canonical_rewards(completed_rewards[code])
                    unlocked = code in completed
                else:
                    rewards_for_check = rewards[reward_index:reward_index + rewards_per_check]
                    unlocked = False
                reward_index += rewards_per_check
                primary_reward = rewards_for_check[0] if rewards_for_check else {}
                mission_checks.append({
                    'id': check_id,
                    'name': name,
                    'hint': hint,
                    'reward': primary_reward,
                    'rewards': rewards_for_check,
                    'unlocked': unlocked or code in completed,
                })
            checks[code] = mission_checks

        return checks

    def generate_seed_reward_plan(self, mission_codes, seed, slots_by_code):
        rng = random.Random(f'{seed}:seed-rewards')
        require_access_for_unit_buffs = self.randomize_unit_access_enabled()
        share_chaos_role_buffs = self.share_chaos_role_buffs_enabled()
        access_by_code = {}
        buffs_by_code = {}
        for code in mission_codes:
            pool = [canonical_reward(reward) for reward in self.reward_pool_for_code(code)]
            access = [dict(reward) for reward in pool if reward.get('kind') != 'buff']
            buffs = [dict(reward) for reward in pool if reward.get('kind') == 'buff']
            rng.shuffle(access)
            access_by_code[code] = access
            buffs_by_code[code] = buffs

        used_access_names = set()
        seed_unlocked_tech_ids = set()
        buff_counts = {}
        unit_buff_counts = {}
        global_buff_counts = {}
        plan = {}
        global_index = 0

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

        def draw_access(code):
            access = access_by_code.get(code, [])
            while access:
                reward = access.pop()
                name = canonical_reward(reward).get('name')
                if name in used_access_names:
                    continue
                used_access_names.add(name)
                return reward
            return None

        def draw_buff(code, prefer_global=False):
            buffs = buffs_by_code.get(code, [])
            if not buffs:
                return None

            unit_candidates = []
            global_candidates = []
            for reward in buffs:
                limit = buff_stack_limit(reward)
                count_key = buff_count_key(reward)
                if limit is not None and buff_counts.get(count_key, 0) >= limit:
                    continue
                unit = reward.get('unit')
                if reward.get('global_buff') or not unit:
                    count = global_buff_counts.get(reward.get('name'), 0)
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
            pool = [dict(reward) for reward in self.reward_pool_for_code(code)]
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

        for code in mission_codes:
            rewards = []
            for _ in range(slots_by_code.get(code, 0)):
                reward = None
                prefer_global = (global_index + 1) % GLOBAL_BUFF_REWARD_INTERVAL == 0
                if global_index % 5 == 4 or prefer_global:
                    reward = draw_buff(code, prefer_global=prefer_global)
                if reward is None:
                    reward = draw_access(code)
                if reward is None:
                    reward = draw_buff(code, prefer_global=prefer_global)
                if reward is None:
                    reward = draw_repeatable_fallback(code)
                if reward is not None:
                    rewards.append(reward)
                    seed_unlocked_tech_ids.update(tech_ids_for_rewards([reward]))
                global_index += 1
            plan[code] = rewards

        return plan

    def earned_rewards_from_checks(self):
        earned = []
        for code in self.state.get('mission_order', []):
            for check in self.state.get('mission_checks', {}).get(code, []):
                if check.get('unlocked'):
                    earned.extend(check_rewards(check))
        return earned

    def refresh_missions(self):
        self.append_log('Refreshing mission list...')
        self.missions = self.parse_missions()
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
        if chaos_mode:
            self.randomize_unit_access_var.set(True)
            self.randomize_unit_access_check.configure(state='disabled')
            self.share_chaos_role_buffs_check.grid()
        else:
            self.randomize_unit_access_check.configure(state='normal')
            self.share_chaos_role_buffs_check.grid_remove()
        self.share_chaos_role_buffs_check.configure(state='normal' if buffs_enabled else 'disabled')
        self.buff_allied_helpers_check.configure(state='normal' if buffs_enabled else 'disabled')
        for check in getattr(self, 'buff_type_checks', []):
            check.configure(state='normal' if buffs_enabled else 'disabled')
        reward_source_enabled = bool(self.randomize_unit_access_var.get()) or buffs_enabled
        self.include_defensive_buildings_check.configure(
            state='normal' if reward_source_enabled else 'disabled'
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
            return self.state.get('progression_mode', PROGRESSION_MODES[0])
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
        if not isinstance(grid, dict) or not grid.get('nodes'):
            if self.grid_render_signature != ('empty',):
                for child in self.grid_frame.winfo_children():
                    child.destroy()
                self.grid_tile_widgets = {}
                self.grid_render_signature = ('empty',)
                ttk.Label(
                    self.grid_frame,
                    text='Generate a Grid Mode seed to create the mission grid.',
                    anchor='center',
                    justify='center',
                ).grid(row=0, column=0, sticky='nsew', padx=20, pady=20)
                self.grid_frame.columnconfigure(0, weight=1)
                self.grid_frame.rowconfigure(0, weight=1)
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

        for child in self.grid_frame.winfo_children():
            child.destroy()
        self.grid_tile_widgets = {}
        self.grid_render_signature = signature
        for column in range(12):
            self.grid_frame.columnconfigure(column, weight=0, minsize=0, uniform='')
        for row in range(12):
            self.grid_frame.rowconfigure(row, weight=0, minsize=0, uniform='')
        for column in range(width):
            self.grid_frame.columnconfigure(
                column,
                weight=1,
                minsize=105,
                uniform='grid-column',
            )
        for row in range(height):
            self.grid_frame.rowconfigure(row, weight=1, minsize=88, uniform='grid-row')

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
                spacer = tk.Frame(self.grid_frame, background='#e9ecef', borderwidth=0)
                spacer.grid(row=row, column=column, sticky='nsew', padx=3, pady=3)

        for code, node in grid['nodes'].items():
            tile = tk.Frame(
                self.grid_frame,
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
            faction = self.normalize_faction(mission.get('side', ''))
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
        done = sum(len(check_rewards(check)) for check in checks if check.get('unlocked'))
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
        missing = [check for check in self.mission_checks(code) if not check.get('unlocked')]
        if not missing:
            return ''
        lines = ['Remaining mission checks:']
        for check in missing:
            rewards = check_rewards(check)
            lines.append(f'- {check.get("name", "Check")} ({len(rewards)} rewards)')
            for reward in rewards:
                lines.append(f'    • {reward_display_name(reward)}')
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
        self.launch_mission(mission)

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

    def on_generate_seed(self):
        if self.state and self.state.get('completed_missions'):
            confirmed = messagebox.askyesno(
                'Regenerate Seed',
                'This will replace the current randomizer progress. Continue?',
            )
            if not confirmed:
                return
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
        rng = random.Random(seed)
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

        self._reward_settings_override = reward_settings
        campaign_counts = self.campaign_mission_counts(seed_missions)
        campaign_limits = self.seed_campaign_limits(seed_missions, mission_goal)
        mission_codes = self.seed_mission_order(seed_missions, rng, mission_goal)
        progression_mode = self.progression_mode_var.get()
        grid = None
        if progression_mode == 'Grid Mode':
            try:
                grid = create_grid(
                    mission_codes,
                    bool(self.grid_two_starts_var.get()),
                )
            except ValueError as exc:
                self._reward_settings_override = None
                self.append_log(f'Cannot generate grid: {exc}.', error=True)
                messagebox.showwarning('Invalid Grid', str(exc))
                return
        if not any(self.reward_pool_for_code(code) for code in mission_codes):
            self._reward_settings_override = None
            self.append_log('Cannot generate seed: the selected reward settings produce no available rewards.', error=True)
            return

        mission_checks = self.build_mission_checks(
            mission_codes,
            seed,
            rewards_per_check=rewards_per_check,
        )
        rewards = [
            reward
            for code in mission_codes
            for check in mission_checks[code]
            for reward in check_rewards(check)
        ]
        mission_objectives = self.state_objective_summary(mission_codes)

        self.state = {
            'version': 1,
            'seed': seed,
            'created_at': now_stamp(),
            'campaign_filter': self.campaign_var.get(),
            'reward_mode': self.reward_mode_var.get(),
            'progression_mode': progression_mode,
            'mission_goal': mission_goal,
            'rewards_per_check': rewards_per_check,
            'starting_unlocked_missions': min(STARTING_UNLOCKED_MISSIONS, len(mission_codes)),
            'mission_order': mission_codes,
            'campaign_mission_counts': campaign_counts,
            'campaign_mission_limits': campaign_limits,
            'completed_missions': [],
            'started_missions': [],
            'earned_rewards': [],
            'reward_queue': rewards,
            'mission_checks': mission_checks,
            'mission_objectives': mission_objectives,
            'reward_settings': reward_settings,
            'check_schema_version': CHECK_SCHEMA_VERSION,
        }
        if grid is not None:
            self.state['grid'] = grid
        self._reward_settings_override = None
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
            else f'First {self.state["starting_unlocked_missions"]} missions are open.'
        )
        self.append_log(
            f'Generated seed {seed}. Finish {mission_goal} missions. '
            f'{rewards_per_check} reward(s) per objective. {opening} '
            f'Setup saved to {CONFIG_PATH}.'
        )
        if campaign_counts.get('Foehn') and len(campaign_counts) > 1:
            self.append_log(
                f'Foehn pool: {campaign_counts["Foehn"]} missions available; '
                f'this seed is limited to {campaign_limits["Foehn"]} Foehn mission(s).'
            )
        log_event(
            'seed_generated',
            seed=seed,
            campaign=self.campaign_var.get(),
            reward_mode=self.reward_mode_var.get(),
            progression_mode=progression_mode,
            grid=grid,
            mission_goal=mission_goal,
            rewards_per_check=rewards_per_check,
            mission_order=mission_codes,
            campaign_mission_counts=campaign_counts,
            campaign_mission_limits=campaign_limits,
            reward_settings=reward_settings,
        )

    def mission_stage_score(self, mission):
        title = mission.get('title', '') or ''
        code = mission.get('code', '') or ''
        match = re.search(r'\b(?:Allied|Soviet|Epsilon|Foehn)\s+(\d{1,2})\b', title, flags=re.IGNORECASE)
        if match:
            score = int(match.group(1))
        elif re.search(r'\bOp\b', title, flags=re.IGNORECASE):
            score = 9
        else:
            score = int(mission.get('index') or 12)

        if re.search(r'\b(finale|final)\b', title, flags=re.IGNORECASE):
            score = max(score, 24)
        if code.upper() in {'SHAND'}:
            score = max(score, 24)
        return score

    def campaign_mission_counts(self, missions):
        counts = {faction: 0 for faction in FACTION_ORDER}
        for mission in missions:
            faction = self.normalize_faction(mission.get('side', ''))
            if faction in counts:
                counts[faction] += 1
        return {faction: count for faction, count in counts.items() if count}

    def seed_campaign_limits(self, missions, mission_goal):
        """Cap short campaigns proportionally in a mixed-campaign seed."""
        counts = self.campaign_mission_counts(missions)
        if len(counts) <= 1 or 'Foehn' not in counts:
            return dict(counts)

        total = sum(counts.values())
        limits = dict(counts)
        # Foehn has seven installed missions versus thirty for each original
        # campaign. Ceil keeps it represented without letting its early-stage
        # missions dominate the staged random order.
        limits['Foehn'] = min(
            counts['Foehn'],
            max(1, (mission_goal * counts['Foehn'] + total - 1) // total),
        )
        return limits

    def seed_mission_order(self, missions, rng, mission_goal):
        missions = list(missions)
        mission_goal = max(1, min(mission_goal, len(missions)))
        if not missions:
            return []
        campaign_limits = self.seed_campaign_limits(missions, mission_goal)
        picked_by_faction = {faction: 0 for faction in campaign_limits}

        def bucket(mission):
            score = self.mission_stage_score(mission)
            if score <= 6:
                return 0
            if score <= 16:
                return 1
            if score < 24:
                return 2
            return 3

        def shuffled(items):
            items = list(items)
            rng.shuffle(items)
            return items

        early_mid = [mission for mission in missions if bucket(mission) <= 1]
        non_finale = [mission for mission in missions if bucket(mission) <= 2]
        if mission_goal <= 5 and len(early_mid) >= mission_goal:
            candidates = early_mid
        elif len(non_finale) >= mission_goal:
            candidates = non_finale
        else:
            candidates = missions

        start_count = min(STARTING_UNLOCKED_MISSIONS, mission_goal)
        starting_pool = shuffled([mission for mission in candidates if bucket(mission) == 0])
        if len(starting_pool) < start_count:
            starting_pool.extend(shuffled([mission for mission in candidates if bucket(mission) == 1]))
        if len(starting_pool) < start_count:
            starting_pool.extend(shuffled([mission for mission in candidates if bucket(mission) == 2]))
        if len(starting_pool) < start_count:
            starting_pool.extend(shuffled([mission for mission in candidates if bucket(mission) == 3]))

        picked_codes = set()
        ordered = []

        def can_add(mission):
            faction = self.normalize_faction(mission.get('side', ''))
            return picked_by_faction.get(faction, 0) < campaign_limits.get(
                faction,
                len(missions),
            )

        def add_mission(mission):
            if mission['code'] in picked_codes or not can_add(mission):
                return False
            ordered.append(mission)
            picked_codes.add(mission['code'])
            faction = self.normalize_faction(mission.get('side', ''))
            picked_by_faction[faction] = picked_by_faction.get(faction, 0) + 1
            return True

        for mission in starting_pool:
            if not add_mission(mission):
                continue
            if len(ordered) >= start_count:
                break

        if len(ordered) >= mission_goal:
            return [item['code'] for item in ordered]

        for bucket_index in range(4):
            for mission in shuffled([mission for mission in candidates if bucket(mission) == bucket_index]):
                if not add_mission(mission):
                    continue
                if len(ordered) >= mission_goal:
                    return [item['code'] for item in ordered]

        for mission in shuffled(missions):
            if not add_mission(mission):
                continue
            if len(ordered) >= mission_goal:
                break
        return [item['code'] for item in ordered]

    def generate_rewards_for_count(self, count, seed, reward_pool=None):
        rng = random.Random(f'{seed}:rewards')
        reward_pool = list(reward_pool or REWARD_POOL)
        access_pool = [reward for reward in reward_pool if reward.get('kind') != 'buff']
        buff_pool = [reward for reward in reward_pool if reward.get('kind') == 'buff']

        if not access_pool or not buff_pool or count < 2:
            rewards = []
            while len(rewards) < count:
                batch = [dict(item) for item in reward_pool]
                rng.shuffle(batch)
                rewards.extend(batch)
            return rewards[:count]

        access_batch = []
        buff_batch = []

        def draw(pool, batch):
            if not batch:
                batch.extend(dict(item) for item in pool)
                rng.shuffle(batch)
            return batch.pop()

        rewards = []
        for index in range(count):
            if index % 5 == 4:
                rewards.append(draw(buff_pool, buff_batch))
            else:
                rewards.append(draw(access_pool, access_batch))

        return rewards[:count]

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
        grid_unlocks = self.mission_unlocks(code) if check_id == 'victory' else []
        if check_id == 'victory':
            completed = self.state.setdefault('completed_missions', [])
            if code not in completed:
                completed.append(code)
            for check in checks:
                if not check.get('unlocked'):
                    check['unlocked'] = True
                    earned_now.extend(check_rewards(check))
        else:
            target['unlocked'] = True
            earned_now.extend(check_rewards(target))

        self.sync_grid_progression()
        self.state['earned_rewards'] = self.earned_rewards_from_checks()
        self.save_state()
        self.append_log(
            f'{source}: {code} {target.get("name", check_id)} complete. '
            f'Reward(s) earned: {reward_names(earned_now)}'
        )
        log_event(
            'mission_check_unlocked',
            seed=self.state.get('seed', ''),
            code=code,
            check_id=check_id,
            check_name=target.get('name', check_id),
            source=source,
            rewards=[reward.get('name') for reward in earned_now],
        )
        if check_id == 'victory' and len(earned_now) > len(check_rewards(target)):
            self.append_log('Victory granted any missed objective rewards for this mission.')
        if grid_unlocks:
            names = [self.mission_lookup().get(item, {}).get('title', item) for item in grid_unlocks]
            self.append_log(f'Grid neighbors unlocked: {", ".join(names)}.')
        if check_id == 'victory' and self.is_run_complete():
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

    def parse_missions(self):
        if not BATTLE_CLIENT_INI.exists():
            self.append_log(f'BattleClient.ini not found at {BATTLE_CLIENT_INI}', error=True)
            return []

        lines = read_text(BATTLE_CLIENT_INI).splitlines()
        mission_codes = []
        sections = {}
        current_section = None
        in_battles = False

        for line in lines:
            no_comment = line.split(';', 1)[0].strip()
            if not no_comment:
                continue
            if no_comment.startswith('[') and no_comment.endswith(']'):
                current_section = no_comment[1:-1].strip()
                in_battles = current_section == 'Battles'
                sections.setdefault(current_section, {})
                continue

            if in_battles and '=' in no_comment:
                _, value = no_comment.split('=', 1)
                code = value.strip()
                if code and code not in mission_codes:
                    mission_codes.append(code)
                continue

            if current_section and '=' in no_comment:
                key, value = no_comment.split('=', 1)
                sections.setdefault(current_section, {})[key.strip()] = value.strip()

        missions = []
        for position, code in enumerate(mission_codes, start=1):
            section = sections.get(code, {})
            scenario = section.get('Scenario') or section.get('SCENARIO')
            if not scenario:
                continue
            title = section.get('Description') or section.get('description') or code
            side = section.get('SideName') or section.get('Side') or ''
            objectives = self.parse_long_description_objectives(section.get('LongDescription', ''))
            missions.append({
                'index': position,
                'code': code,
                'scenario': scenario,
                'title': title,
                'side': side,
                'objectives': objectives,
                'objective_count': len(objectives) or FALLBACK_OBJECTIVE_COUNT,
            })

        return missions

    def parse_long_description_objectives(self, text):
        if not text:
            return []

        objectives = []
        for part in text.split('@'):
            match = re.match(r'\s*Objective\s+(\d+)\s*:\s*(.+?)\s*$', part, flags=re.IGNORECASE)
            if match:
                objectives.append(match.group(2).strip())
        return objectives

    def filtered_missions_for_seed(self):
        selected = self.campaign_var.get()
        if selected == CAMPAIGN_FILTERS[0]:
            return list(self.missions)
        return [
            mission
            for mission in self.missions
            if self.normalize_faction(mission.get('side', '')) == selected
        ]

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
        if self.active_reward_mode() == 'Chaos (Experimental)':
            return chaos_earned_access_rules(lines, self.earned_rewards_from_checks())
        selected_campaign = self.state.get('campaign_filter', '') if self.state else ''
        use_equivalent_access = selected_campaign in {'Allies', 'Soviets', 'Epsilon', 'Foehn'}
        earned_access_ids = (
            unlocked_reward_tech_ids(self.earned_rewards_from_checks())
            if use_equivalent_access
            else set()
        )
        return mission_basic_unit_rules(
            lines,
            earned_access_ids=earned_access_ids,
            use_equivalent_access=use_equivalent_access,
        )

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

    def map_rules_for_launch(self, extra_rules=None):
        rule_sections = {}
        randomized_tech_ids = self.randomized_tech_ids()
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
                    prepared_values = {
                        key: value
                        for key, value in values.items()
                        if key.lower() not in {'techlevel', 'buildlimit'}
                    }
                    rule_sections.setdefault(section, {}).update(prepared_values)

        if self.state:
            earned_rewards = self.earned_rewards_from_checks()
            self.state['earned_rewards'] = earned_rewards
            for reward in earned_rewards:
                reward = canonical_reward(reward)
                if reward.get('kind') == 'buff' and reward.get('buff_type'):
                    continue
                for section, values in launch_rules_for_reward(reward).items():
                    if section.upper() not in randomized_tech_ids:
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
        rule_sections = self.map_rules_for_launch(extra_rules)
        if self.state:
            for section, values in superweapon_rule_sections_for_rewards(
                self.earned_rewards_from_checks()
            ).items():
                rule_sections.setdefault(section, {}).update(values)
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

        scenario = mission.get('scenario')
        code = mission.get('code')
        if not scenario or not code:
            return None

        source_path = self.extract_campaign_map(scenario)
        lines = read_text(source_path).splitlines()
        if rule_sections:
            merge_ini_section_values(lines, rule_sections)
            self.append_log(f'Injected {len(rule_sections)} map rule section(s) into {scenario}.')

        generation_config = self.config.get('generation', {})
        experimental_house_buffs = bool(generation_config.get('experimental_house_buffs', False))
        safe_player_country_buffs = bool(generation_config.get('safe_player_country_buffs', True))
        allow_shared_country_buffs = bool(generation_config.get('allow_shared_country_buffs', False))
        buff_allied_helpers = bool(self.active_reward_settings().get('buff_allied_helpers', False))
        require_unlocked_access_for_buffs = self.randomize_unit_access_enabled()
        if self.state and experimental_house_buffs:
            player_house, house_buffs = clone_player_country_for_house_buffs(
                lines,
                self.earned_rewards_from_checks(),
                require_unlocked_access=require_unlocked_access_for_buffs,
                additional_unlocked_tech_ids=fallback_tech_ids,
                share_basic_equivalent_buffs=share_basic_equivalent_buffs,
                unit_specific_mode=chaos_unit_specific_buffs,
            )
            if house_buffs:
                buff_summary = ', '.join(f'{key}={value}' for key, value in sorted(house_buffs.items()))
                self.append_log(f'Applied player-house buffs to {player_house} via MORPLAYER: {buff_summary}')
        elif self.state and safe_player_country_buffs:
            player_house, player_country, house_rule_sections, shared_houses, buffed_allies, skipped_allies = player_country_buff_rules(
                lines,
                self.earned_rewards_from_checks(),
                allow_shared_country=allow_shared_country_buffs,
                buff_allied_helpers=buff_allied_helpers,
                require_unlocked_access=require_unlocked_access_for_buffs,
                additional_unlocked_tech_ids=fallback_tech_ids,
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
                self.append_log(
                    f'Applied map-local player-country buffs for {player_house}/{player_country}: '
                    f'{buff_summary}.{shared_note}{helper_note}{skipped_note}'
                )
            elif shared_houses:
                self.append_log(
                    f'Skipped player-country buffs for {player_house}/{player_country}: '
                    f'non-player house(s) share that country ({", ".join(shared_houses)}).'
                )
        elif self.state:
            pending_house_buffs = stacked_house_buff_values(
                self.earned_rewards_from_checks(),
                require_unlocked_access=require_unlocked_access_for_buffs,
                additional_unlocked_tech_ids=fallback_tech_ids,
                share_basic_equivalent_buffs=share_basic_equivalent_buffs,
                unit_specific_mode=chaos_unit_specific_buffs,
            )
            if pending_house_buffs:
                self.append_log(
                    'Experimental player-house buffs are disabled for mission stability; '
                    'earned buff rewards are tracked but not injected into this map.'
                )

        if self.state:
            weapon_rule_sections, weapon_buffed_units, weapon_skipped_units = unit_weapon_buff_rules(
                lines,
                self.earned_rewards_from_checks(),
                buff_allied_helpers=buff_allied_helpers,
                require_unlocked_access=require_unlocked_access_for_buffs,
                additional_unlocked_tech_ids=fallback_tech_ids,
                share_basic_equivalent_buffs=share_basic_equivalent_buffs,
                unit_specific_mode=chaos_unit_specific_buffs,
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

        earned_rewards = self.earned_rewards_from_checks() if self.state else []
        house = player_country_from_map(lines)
        superweapon_actions = superweapon_actions_for_rewards(earned_rewards)
        superweapon_trigger = append_superweapon_grant_trigger(lines, house, superweapon_actions)
        if superweapon_trigger:
            power_names = [
                reward_display_name(reward)
                for reward in canonical_rewards(earned_rewards)
                if reward.get('kind') == 'superweapon'
            ]
            self.append_log(
                'Prepared building-free superweapon grant for: '
                + ', '.join(power_names)
                + '.'
            )

        unlocked_tech_ids = tech_ids_for_rewards(earned_rewards)
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
        checks = [check for check in self.mission_checks(code) if not check.get('unlocked')] if self.state else []

        patch_plan = []
        objective_checks = [check for check in checks if check.get('id') != 'victory']
        for check, action_id in zip(objective_checks, objective_action_ids):
            patch_plan.append((check, action_id))

        victory_check = next((check for check in checks if check.get('id') == 'victory'), None)
        if victory_check and victory_action_ids:
            patch_plan.append((victory_check, victory_action_ids[0]))
        elif victory_check:
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
            append_hook_team(lines, team_id, taskforce_id, script_id, marker, house)
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
            if patched:
                markers[marker] = check.get('id')

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
        generated_path.write_text(generated_text, encoding='utf-8')

        root_map = GAME_ROOT / scenario
        if root_map.exists() and not is_generated_hooked_map(root_map):
            backup_file_once(root_map, 'before-randomizer-hook')
        root_map.write_text(generated_text, encoding='utf-8')
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
        self.active_hook = None
        self.active_game_process = None
        self.cleanup_generated_root_maps()
        self.disable_generated_rules_for_client()

    def launch_mission(self, mission, extra_rules=None, launch_note=''):
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
            messagebox.showerror('Launch Failed', 'Failed to write launch files. See log for details.')
            self.append_log(traceback.format_exc(), error=True)
            return

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

    def current_unlocks_text(self):
        if not self.state:
            return 'No randomizer seed generated yet.'

        earned = [canonical_reward(reward) for reward in self.earned_rewards_from_checks()]
        if not earned:
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

        lines = []
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
                    power_token = f'[[MOR_POWER:{reward["superweapon"]}]]'
                lines.append(f'{power_token}Reward: {reward_display_name(reward)}')
                for summary in reward_rule_summary(reward):
                    lines.append(f'  {summary}')

            lines.append('')

        return '\n'.join(lines).rstrip()

    def current_unlock_unit_ids(self):
        if not self.state:
            return []
        unit_ids = set()
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
        status = 'Finished' if self.is_run_complete() else 'In progress'
        progression_mode = self.active_progression_mode()
        self.progress_label.config(
            text=(
                f'Seed: {self.state.get("seed", "")} | {progression_mode} | '
                f'Rewards: {self.state.get("reward_mode", REWARD_MODES[0])}\n'
                f'Goal: {completed}/{goal} | Open: {unlocked} | Rewards: {len(earned)} | {status}'
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
                if unlocks:
                    lookup = self.mission_lookup()
                    labels = [lookup.get(item, {}).get('title', item) for item in unlocks]
                    lines.append('Completing this node unlocks: ' + ', '.join(labels))
                elif node.get('state') == GRID_COMPLETED:
                    lines.append('This node is complete; its neighbors are already open.')
                else:
                    lines.append('Completing this node does not unlock a currently locked neighbor.')
            lines.append(f'Reward progress: {done_checks}/{total_checks}')
            lines.append('')
            for check in self.mission_checks(code):
                status_label = 'Complete' if check.get('unlocked') else 'Pending'
                rewards = check_rewards(check)
                lines.append(
                    f'{status_label}: {check.get("name", "Check")} — {len(rewards)} reward(s)'
                )
                hint = check.get('hint')
                if hint and not check.get('unlocked'):
                    lines.append(f'   {hint}')
                if rewards:
                    for reward in rewards:
                        lines.append(f'   • {reward_display_name(reward)}')
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
