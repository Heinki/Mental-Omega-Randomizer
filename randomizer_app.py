import json
import random
import re
import shutil
import subprocess
import traceback

from randomizer_config import CONFIG_PATH, load_config, save_config
from randomizer_rewards import (
    BUFF_TARGETS,
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
    reward_display_lines,
    reward_display_name,
    reward_names,
    reward_rule_summary,
    unit_display_label,
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
    MAP_RENDERER_DIR,
    OPTIONS_INI,
    RULESMO_INI,
    SPAWN_INI,
    STATE_PATH,
    YR_OPTIONS_INI,
)
from randomizer_map import (
    HOOKED_MAP_MARKER,
    LOCKED_PREREQUISITE,
    LOCKED_TECH_LEVEL,
    RANDOMIZER_RULES_MARKER,
    SCRIPTED_TECH_BUILD_LIMIT,
    SCRIPTED_TECH_LOCK_EXCLUSIONS,
    action_has_code,
    action_has_objective_complete,
    action_line_ids,
    append_action_to_action_id,
    append_hook_team,
    backup_file_once,
    clone_player_country_for_house_buffs,
    controlled_tech_ids,
    find_section_bounds,
    hook_marker_name,
    is_generated_hooked_map,
    is_generated_rules_file,
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
    reward_unlock_tech_ids,
    section_lines,
    section_value_map,
    set_ini_value_lines,
    stacked_house_buff_values,
    tech_ids_for_rewards,
    techlevel_actions_for_rewards,
    trigger_action_ids_by_name,
    unique_in_order,
    unit_weapon_buff_rules,
)
DIFFICULTIES = [('Casual', 2), ('Normal', 1), ('Mental', 0)]
GAME_SPEEDS = [
    ('6 - Fastest', 6),
    ('5 - Faster', 5),
    ('4 - Fast', 4),
    ('3 - Medium', 3),
    ('2 - Slow', 2),
    ('1 - Slower', 1),
    ('0 - Slowest', 0),
]
CAMPAIGN_FILTERS = ['All Campaigns', 'Allies', 'Soviets', 'Epsilon', 'Foehn']

STARTING_UNLOCKED_MISSIONS = 3
DEFAULT_MISSION_GOAL = 15
FALLBACK_OBJECTIVE_COUNT = 3
CHECK_SCHEMA_VERSION = 16
HOOK_POLL_MS = 1500
MAX_OPTION_INI_BYTES = 2 * 1024 * 1024
MAX_GLOBAL_BUFF_REPEATS_PER_SEED = 3
MIXED_REWARD_MISSION_CODES = {'FREMNANT'}

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
            label = ttk.Label(self.tip, text=text, justify='left', padding=(8, 6, 8, 6), relief='solid')
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
        self.geometry('1180x720')
        self.minsize(940, 560)
        self.resizable(True, True)

        self.missions = []
        self.config = load_config()
        self.state = self.load_state()
        self.migrate_state()
        self._reward_factions_cache = {}
        self.active_game_process = None
        self.active_hook = None
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
        self.buff_allied_helpers_var = tk.BooleanVar(
            value=bool(generation_config.get('buff_allied_helpers', False))
        )
        self.log_visible_var = tk.BooleanVar(value=False)
        self.cleanup_generated_root_maps()
        self.disable_generated_rules_for_client()

        self.create_widgets()
        self.refresh_missions()
        self.refresh_progress_view()

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding=(12, 12, 12, 12))
        self.main_frame = main_frame
        main_frame.grid(row=0, column=0, sticky='nsew')
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        style = ttk.Style(self)
        style.configure('Randomizer.TNotebook', tabposition='n')
        style.configure('Randomizer.TNotebook.Tab', padding=(14, 6), font=('Segoe UI', 9, 'bold'))

        header = ttk.Label(main_frame, text='Mental Omega Randomizer Launcher', font=('Segoe UI', 14, 'bold'))
        header.grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 8))

        self.missions_tree = ttk.Treeview(
            main_frame,
            columns=('order', 'state', 'checks', 'faction', 'code', 'title'),
            show='headings',
            selectmode='browse',
            height=17,
        )
        self.missions_tree.heading('order', text='No.')
        self.missions_tree.heading('state', text='State')
        self.missions_tree.heading('checks', text='Rewards')
        self.missions_tree.heading('faction', text='Faction')
        self.missions_tree.heading('code', text='Code')
        self.missions_tree.heading('title', text='Mission Title')
        self.missions_tree.column('order', width=54, anchor='center', stretch=False)
        self.missions_tree.column('state', width=72, anchor='center', stretch=False)
        self.missions_tree.column('checks', width=72, anchor='center', stretch=False)
        self.missions_tree.column('faction', width=90, anchor='w', stretch=False)
        self.missions_tree.column('code', width=105, anchor='w', stretch=False)
        self.missions_tree.column('title', width=360, anchor='w', stretch=True)
        self.missions_tree.grid(row=1, column=0, rowspan=5, sticky='nsew', padx=(0, 8))
        self.missions_tree.bind('<<TreeviewSelect>>', self.on_mission_select, add='+')
        self.mission_tooltip = TreeTooltip(self.missions_tree, self.mission_tooltip_text)

        tree_scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=self.missions_tree.yview)
        tree_scrollbar.grid(row=1, column=1, rowspan=5, sticky='ns')
        self.missions_tree.configure(yscrollcommand=tree_scrollbar.set)

        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=1, column=2, rowspan=5, sticky='nsew')
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(4, weight=1)

        ttk.Label(right_frame, text='Seed').grid(row=0, column=0, sticky='w')
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
            width=8,
        )
        self.game_speed_combo.grid(row=0, column=3, sticky='ew')

        ttk.Label(options_row, text='Campaign').grid(row=1, column=0, sticky='w', pady=(6, 0), padx=(0, 8))
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
        ttk.Checkbutton(
            options_row,
            text='Buff allied helpers',
            variable=self.buff_allied_helpers_var,
        ).grid(row=2, column=2, columnspan=2, sticky='w', pady=(6, 0), padx=(14, 0))

        button_row = ttk.Frame(right_frame)
        button_row.grid(row=3, column=0, sticky='ew', pady=(0, 6))
        for column in range(2):
            button_row.columnconfigure(column, weight=1)
        ttk.Button(button_row, text='Launch Mission', command=self.on_launch_selected).grid(row=0, column=0, sticky='ew', padx=(0, 4), pady=(0, 4))
        ttk.Button(button_row, text='Mark Complete', command=self.on_mark_complete).grid(row=0, column=1, sticky='ew', pady=(0, 4))

        info_tabs = ttk.Notebook(right_frame, style='Randomizer.TNotebook')
        info_tabs.grid(row=4, column=0, sticky='nsew')
        info_tabs.enable_traversal()

        progress_frame = ttk.Frame(info_tabs, padding=(8, 8, 8, 8))
        progress_frame.columnconfigure(0, weight=1)
        progress_frame.rowconfigure(1, weight=1)
        info_tabs.add(progress_frame, text='Mission')

        self.progress_label = ttk.Label(progress_frame, text='No seed generated yet.', anchor='w', justify='left')
        self.progress_label.grid(row=0, column=0, sticky='ew', pady=(0, 6))

        self.rewards_text = scrolledtext.ScrolledText(progress_frame, height=16, wrap='word', state='disabled')
        self.rewards_text.grid(row=1, column=0, sticky='nsew')

        unlocks_frame = ttk.Frame(info_tabs, padding=(8, 8, 8, 8))
        unlocks_frame.columnconfigure(0, weight=1)
        unlocks_frame.rowconfigure(0, weight=1)
        info_tabs.add(unlocks_frame, text='Current Unlocks')
        self.unlocks_text = scrolledtext.ScrolledText(unlocks_frame, height=16, wrap='word', state='disabled')
        self.unlocks_text.grid(row=0, column=0, sticky='nsew')

        self.status_label = ttk.Label(main_frame, text='Ready', anchor='w')
        self.status_label.grid(row=6, column=0, columnspan=3, sticky='ew', pady=(8, 0))

        log_header = ttk.Frame(main_frame)
        log_header.grid(row=7, column=0, columnspan=3, sticky='ew', pady=(12, 4))
        log_header.columnconfigure(1, weight=1)
        self.log_toggle_button = ttk.Button(
            log_header,
            text='Show Launcher Log',
            command=self.toggle_log,
            width=18,
        )
        self.log_toggle_button.grid(row=0, column=0, sticky='w')
        ttk.Label(log_header, text='Detailed launch/debug output is still written here.').grid(
            row=0,
            column=1,
            sticky='w',
            padx=(8, 0),
        )

        self.log_text = scrolledtext.ScrolledText(
            main_frame,
            height=10,
            wrap='word',
            state='disabled',
            background='black',
            foreground='white',
        )
        self.log_text.grid(row=8, column=0, columnspan=3, sticky='nsew')
        self.log_text.grid_remove()

        main_frame.rowconfigure(1, weight=1)
        main_frame.rowconfigure(8, weight=0)
        main_frame.columnconfigure(0, weight=3)
        main_frame.columnconfigure(2, weight=2)

    def toggle_log(self):
        if self.log_visible_var.get():
            self.log_text.grid_remove()
            self.main_frame.rowconfigure(8, weight=0)
            self.log_toggle_button.configure(text='Show Launcher Log')
            self.log_visible_var.set(False)
        else:
            self.log_text.grid()
            self.main_frame.rowconfigure(8, weight=1)
            self.log_toggle_button.configure(text='Hide Launcher Log')
            self.log_visible_var.set(True)

    def append_log(self, message, error=False):
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
            pass
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

        if changed:
            self.state['earned_rewards'] = self.earned_rewards_from_checks()

        if changed:
            self.save_state()

    def save_state(self):
        STATE_PATH.write_text(json.dumps(self.state, indent=2), encoding='utf-8')

    def save_launcher_config(self, seed, mission_goal, rewards_per_check):
        self.config['seed'] = seed
        self.config['campaign_filter'] = self.campaign_var.get()
        self.config['mission_goal'] = mission_goal
        self.config['rewards_per_objective'] = rewards_per_check
        self.config['difficulty'] = self.difficulty_var.get()
        self.config['game_speed'] = self.game_speed_var.get()
        self.config.setdefault('generation', {})['starting_unlocked_missions'] = STARTING_UNLOCKED_MISSIONS
        self.config['generation']['buff_allied_helpers'] = bool(self.buff_allied_helpers_var.get())
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

    def reward_pool_for_code(self, code):
        factions = self.reward_factions_for_code(code)
        pool = [
            reward
            for reward in REWARD_POOL
            if not reward.get('factions') or factions.intersection(reward.get('factions', []))
        ]
        return pool or list(REWARD_POOL)

    def reward_factions_for_code(self, code):
        if not hasattr(self, '_reward_factions_cache'):
            self._reward_factions_cache = {}
        cached = self._reward_factions_cache.get(code)
        if cached:
            return set(cached)

        mission = self.mission_lookup().get(code, {})
        base_faction = self.normalize_faction(mission.get('side', ''))
        factions = {base_faction} if base_faction else set()
        if code not in MIXED_REWARD_MISSION_CODES:
            result = factions or {'Allies', 'Soviets', 'Epsilon', 'Foehn'}
            self._reward_factions_cache[code] = tuple(sorted(result))
            return result

        try:
            scenario = mission.get('scenario')
            if not scenario:
                result = factions or {'Allies', 'Soviets', 'Epsilon', 'Foehn'}
                self._reward_factions_cache[code] = tuple(sorted(result))
                return result
            lines = read_text(self.extract_campaign_map(scenario)).splitlines()
            player_house = player_house_from_map(lines)
            records = map_house_records(lines)
            player_record = records.get(player_house, {})
            family_to_faction = {
                'allies': 'Allies',
                'soviets': 'Soviets',
                'epsilon': 'Epsilon',
                'foehn': 'Foehn',
            }
            player_family = country_family(player_record)
            if player_family in family_to_faction:
                factions.add(family_to_faction[player_family])

            for helper in allied_helper_houses(lines, player_house):
                helper_family = country_family(records.get(helper, {}))
                if helper_family in family_to_faction:
                    factions.add(family_to_faction[helper_family])
        except Exception:
            pass

        result = factions or {'Allies', 'Soviets', 'Epsilon', 'Foehn'}
        self._reward_factions_cache[code] = tuple(sorted(result))
        return result

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
        global_buff_counts = {}
        plan = {}
        global_index = 0

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

        def draw_buff(code):
            buffs = buffs_by_code.get(code, [])
            if not buffs:
                return None

            unit_candidates = []
            global_candidates = []
            for reward in buffs:
                name = reward.get('name')
                limit = buff_stack_limit(reward)
                if limit is not None and buff_counts.get(name, 0) >= limit:
                    continue
                unit = reward.get('unit')
                if reward.get('global_buff') or not unit:
                    count = global_buff_counts.get(reward.get('name'), 0)
                    if count < MAX_GLOBAL_BUFF_REPEATS_PER_SEED:
                        global_candidates.append(reward)
                elif unit in seed_unlocked_tech_ids:
                    unit_candidates.append(reward)

            candidates = unit_candidates or global_candidates
            if not candidates:
                return None

            reward = dict(rng.choice(candidates))
            if reward.get('global_buff') or not reward.get('unit'):
                name = reward.get('name')
                global_buff_counts[name] = global_buff_counts.get(name, 0) + 1
            name = reward.get('name')
            buff_counts[name] = buff_counts.get(name, 0) + 1
            return reward

        def draw_repeatable_fallback(code):
            pool = [dict(reward) for reward in self.reward_pool_for_code(code)]
            buffs = [reward for reward in pool if reward.get('kind') == 'buff']
            candidates = []
            for reward in buffs or pool:
                limit = buff_stack_limit(reward)
                name = reward.get('name')
                if limit is not None and buff_counts.get(name, 0) >= limit:
                    continue
                candidates.append(reward)
            if not candidates:
                candidates = [dict(reward) for reward in REWARD_POOL if reward.get('kind') == 'buff']
            if not candidates:
                return None
            reward = dict(rng.choice(candidates))
            name = reward.get('name')
            if reward.get('kind') == 'buff':
                buff_counts[name] = buff_counts.get(name, 0) + 1
            return reward

        for code in mission_codes:
            rewards = []
            for _ in range(slots_by_code.get(code, 0)):
                reward = None
                if global_index % 5 == 4:
                    reward = draw_buff(code)
                if reward is None:
                    reward = draw_access(code)
                if reward is None:
                    reward = draw_buff(code)
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
        if hasattr(self, '_reward_factions_cache'):
            self._reward_factions_cache.clear()
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

    def update_mission_goal_limit(self):
        if not self.missions:
            return
        filtered_count = len(self.filtered_missions_for_seed())
        self.mission_goal_spinbox.configure(to=max(1, filtered_count))
        if self.mission_goal_var.get() > filtered_count:
            self.mission_goal_var.set(max(1, filtered_count))

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
                state = 'Open'
            else:
                state = 'Locked'
            checks_label = '' if not self.state else f'{checks_done}/{checks_total}'
            order = order_map.get(code, idx + 1)
            self.missions_tree.insert('', 'end', iid=str(idx), values=(f'{order:03}', state, checks_label, side, code, title))

        children = self.missions_tree.get_children()
        if children and str(self.selected_index.get()) not in children:
            self.missions_tree.selection_set(children[0])
            self.selected_index.set(int(children[0]))

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
        lines = ['Missing rewards:']
        for check in missing:
            rewards = check_rewards(check)
            lines.append(f'- {check.get("name", "Check")}: {reward_names(rewards)}')
            for reward in rewards:
                lines.extend(reward_display_lines(reward, indent='  '))
            lines.append(f'  {check.get("hint", "")}')
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

        mission_codes = [mission['code'] for mission in seed_missions]
        rng.shuffle(mission_codes)
        mission_codes = mission_codes[:mission_goal]

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
            'mission_goal': mission_goal,
            'rewards_per_check': rewards_per_check,
            'starting_unlocked_missions': min(STARTING_UNLOCKED_MISSIONS, len(mission_codes)),
            'mission_order': mission_codes,
            'completed_missions': [],
            'earned_rewards': [],
            'reward_queue': rewards,
            'mission_checks': mission_checks,
            'mission_objectives': mission_objectives,
            'check_schema_version': CHECK_SCHEMA_VERSION,
        }
        self.seed_var.set(seed)
        self.save_state()
        self.save_launcher_config(seed, mission_goal, rewards_per_check)
        self.disable_generated_rules_for_client()
        self.redraw_mission_tree()
        self.refresh_progress_view()
        self.append_log(
            f'Generated seed {seed}. Finish {mission_goal} missions. '
            f'{rewards_per_check} reward(s) per objective. '
            f'First {self.state["starting_unlocked_missions"]} missions are open. '
            f'Setup saved to {CONFIG_PATH}.'
        )

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

        self.state['earned_rewards'] = self.earned_rewards_from_checks()
        self.save_state()
        self.append_log(
            f'{source}: {code} {target.get("name", check_id)} complete. '
            f'Reward(s) earned: {reward_names(earned_now)}'
        )
        if check_id == 'victory' and len(earned_now) > len(check_rewards(target)):
            self.append_log('Victory granted any missed objective rewards for this mission.')
        self.redraw_mission_tree()
        self.refresh_progress_view()
        return True

    def on_mark_objective(self):
        if not self.state:
            messagebox.showwarning('No Seed', 'Generate a seed before marking randomizer progress.')
            return

        mission = self.selected_mission()
        if mission is None:
            self.append_log('Cannot mark objective: no valid mission selected.', error=True)
            return

        code = mission['code']
        next_check = None
        for check in self.mission_checks(code):
            if check.get('id') != 'victory' and not check.get('unlocked'):
                next_check = check
                break

        if next_check is None:
            self.append_log(f'All non-victory objectives already marked for {code}. Use Mark Complete after winning.')
            return

        self.unlock_mission_check(code, next_check['id'], 'Manual objective')

    def on_mark_complete(self):
        if not self.state:
            messagebox.showwarning('No Seed', 'Generate a seed before marking randomizer progress.')
            return

        mission = self.selected_mission()
        if mission is None:
            self.append_log('Cannot mark complete: no valid mission selected.', error=True)
            return

        code = mission['code']
        completed = self.state.setdefault('completed_missions', [])
        if self.is_mission_complete(code):
            self.append_log(f'Mission already completed: {code}')
            return

        if code not in completed:
            completed.append(code)

        earned_now = []
        for check in self.mission_checks(code):
            if not check.get('unlocked'):
                check['unlocked'] = True
                earned_now.extend(check_rewards(check))

        if earned_now:
            self.append_log(f'Marked {code} complete. Rewards earned: {reward_names(earned_now)}')
        else:
            self.append_log(f'Marked {code} complete.')

        self.state['earned_rewards'] = self.earned_rewards_from_checks()
        self.save_state()
        goal = self.state.get('mission_goal', len(self.state.get('mission_order', [])))
        if len(completed) >= goal:
            self.append_log('Randomizer goal complete.')
        self.disable_generated_rules_for_client()
        self.redraw_mission_tree()
        self.refresh_progress_view()

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
        if not self.state:
            return list(enumerate(self.missions))

        shown_codes = set(self.unlocked_mission_codes()) | set(self.state.get('completed_missions', []))
        order_map = self.randomizer_order_map()
        visible = [(idx, mission) for idx, mission in enumerate(self.missions) if mission['code'] in shown_codes]

        def sort_key(item):
            _, mission = item
            done = self.is_mission_complete(mission['code'])
            return (1 if done else 0, order_map.get(mission['code'], 9999))

        return sorted(visible, key=sort_key)

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
        for path in (OPTIONS_INI, YR_OPTIONS_INI, SPAWN_INI):
            label = self.read_game_speed_from_ini(path)
            if label:
                return label
        return next(label for label, code in GAME_SPEEDS if code == 3)

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

        dlls = [
            MAP_RENDERER_DIR / 'CNCMaps.Shared.dll',
            MAP_RENDERER_DIR / 'CNCMaps.FileFormats.dll',
        ]
        if any(not dll.exists() for dll in dlls):
            raise FileNotFoundError('Map Renderer CNCMaps DLLs are missing.')

        mix_paths = sorted(GAME_ROOT.glob('expandmo*.mix'), reverse=True)
        if not mix_paths:
            raise FileNotFoundError('No expandmo*.mix archives found.')

        escaped_name = scenario.upper().replace("'", "''")
        escaped_output = str(output_path).replace("'", "''")
        escaped_dlls = [str(dll).replace("'", "''") for dll in dlls]
        escaped_mixes = [str(path).replace("'", "''") for path in mix_paths]
        mix_array = ','.join(f"'{path}'" for path in escaped_mixes)
        script = f"""
$ErrorActionPreference = 'Stop'
Add-Type -Path '{escaped_dlls[0]}'
Add-Type -Path '{escaped_dlls[1]}'
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
        )
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or 'Map extraction failed.').strip())
        return output_path

    def map_rules_for_launch(self, extra_rules=None):
        rule_sections = {}
        reward_unlocks = reward_unlock_tech_ids()
        for section in sorted(controlled_tech_ids()):
            section_upper = section.upper()
            values = rule_sections.setdefault(section, {})
            if section_upper in SCRIPTED_TECH_LOCK_EXCLUSIONS or section_upper not in reward_unlocks:
                values['PrerequisiteOverride'] = LOCKED_PREREQUISITE
            if section_upper in SCRIPTED_TECH_LOCK_EXCLUSIONS:
                values['BuildLimit'] = SCRIPTED_TECH_BUILD_LIMIT
            else:
                values['TechLevel'] = LOCKED_TECH_LEVEL

        if self.state:
            earned_rewards = self.earned_rewards_from_checks()
            self.state['earned_rewards'] = earned_rewards
            for reward in earned_rewards:
                reward = canonical_reward(reward)
                if reward.get('kind') == 'buff' and reward.get('buff_type'):
                    continue
                for section, values in launch_rules_for_reward(reward).items():
                    rule_sections.setdefault(section, {}).update(values)

        for section, values in (extra_rules or {}).items():
            rule_sections.setdefault(section, {}).update(values)
        return rule_sections

    def prepare_hooked_map(self, mission, extra_rules=None):
        rule_sections = self.map_rules_for_launch(extra_rules)
        transient_rulesmo_sections = {}

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
        transient_rulesmo_buffs = bool(generation_config.get('transient_rulesmo_buffs', False))
        buff_allied_helpers = bool(self.buff_allied_helpers_var.get())
        if self.state and experimental_house_buffs:
            player_house, house_buffs = clone_player_country_for_house_buffs(lines, self.earned_rewards_from_checks())
            if house_buffs:
                buff_summary = ', '.join(f'{key}={value}' for key, value in sorted(house_buffs.items()))
                self.append_log(f'Applied player-house buffs to {player_house} via MORPLAYER: {buff_summary}')
        elif self.state and safe_player_country_buffs:
            player_house, player_country, house_rule_sections, shared_houses, buffed_helpers, skipped_helpers = player_country_buff_rules(
                lines,
                self.earned_rewards_from_checks(),
                allow_shared_country=allow_shared_country_buffs,
                buff_allied_helpers=buff_allied_helpers,
            )
            if house_rule_sections:
                merge_ini_section_values(lines, house_rule_sections)
                house_buffs = next(iter(house_rule_sections.values()))
                buff_summary = ', '.join(f'{key}={value}' for key, value in sorted(house_buffs.items()))
                shared_note = f' Shared country houses: {", ".join(shared_houses)}.' if shared_houses else ''
                helper_note = f' Allied helpers buffed: {", ".join(buffed_helpers)}.' if buffed_helpers else ''
                skipped_note = f' Allied helpers skipped: {", ".join(skipped_helpers)}.' if skipped_helpers else ''
                self.append_log(
                    f'Applied map-local player-country buffs for {player_house}/{player_country}: '
                    f'{buff_summary}.{shared_note}{helper_note}{skipped_note}'
                )
                if transient_rulesmo_buffs:
                    transient_rulesmo_sections.update(house_rule_sections)
            elif shared_houses:
                self.append_log(
                    f'Skipped player-country buffs for {player_house}/{player_country}: '
                    f'non-player house(s) share that country ({", ".join(shared_houses)}).'
                )
        elif self.state:
            pending_house_buffs = stacked_house_buff_values(self.earned_rewards_from_checks())
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
                    'Skipped guarded unit/weapon buffs because unsafe houses use those units: '
                    + '; '.join(weapon_skipped_units)
                    + '.',
                    error=True,
                )

        unlocked_tech_ids = tech_ids_for_rewards(self.earned_rewards_from_checks()) if self.state else set()
        removed_techlevel_actions = remove_locked_techlevel_actions(lines, unlocked_tech_ids)
        if removed_techlevel_actions:
            self.append_log(f'Removed {removed_techlevel_actions} native tech unlock action(s) blocked by the randomizer.')

        objective_action_ids = action_line_ids(
            lines,
            lambda groups: action_has_objective_complete(groups) and not action_has_code(groups, 1) and not action_has_code(groups, 67),
        )
        victory_action_ids = unique_in_order(
            action_line_ids(lines, lambda groups: action_has_code(groups, 1) or action_has_code(groups, 67))
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
            self.append_log(f'No automatic victory hook found for {scenario}. Use Mark Complete after winning if needed.', error=True)

        if not patch_plan and not rule_sections:
            self.append_log(f'No hookable objective/victory triggers found for {scenario}. Manual buttons are still available.')
            return None

        house = player_country_from_map(lines)
        markers = {}
        for index, (check, action_id) in enumerate(patch_plan, start=1):
            marker = hook_marker_name(code, check.get('id', f'check_{index}'))
            team_id = f'RND{index:05d}'
            taskforce_id = f'RNT{index:05d}'
            script_id = f'RNS{index:05d}'
            append_hook_team(lines, team_id, taskforce_id, script_id, marker, house)
            if append_action_to_action_id(lines, action_id, ['4', '1', team_id, '0', '0', '0', '0', 'A']):
                for action_tokens in techlevel_actions_for_rewards(check_rewards(check)):
                    append_action_to_action_id(lines, action_id, action_tokens)
                markers[marker] = check.get('id')

        if patch_plan and not markers:
            self.append_log(f'Hook map generation found triggers for {scenario}, but patching actions failed.', error=True)
            return None

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
            'rulesmo_sections': transient_rulesmo_sections,
        }

    def write_spawn_ini(self, scenario, difficulty_value, game_speed_value):
        try:
            backup_file_once(SPAWN_INI, 'original')
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
                'DifficultyModeComputer=0',
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
                if path.exists() and path.stat().st_size > MAX_OPTION_INI_BYTES:
                    skipped.append(f'{path.name} ({path.stat().st_size} bytes)')
                    continue
                backup_file_once(path, 'original')
                text = read_text(path) if path.exists() else ''
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
                    + '. GameSpeed and difficulty are still written to spawn.ini.'
                )
        except Exception:
            self.append_log('Failed to write launch options:', error=True)
            self.append_log(traceback.format_exc(), error=True)
            raise

    def write_transient_rulesmo_ini(self, rule_sections):
        if not rule_sections:
            self.disable_generated_rules_for_client()
            return False

        if not self.config.get('generation', {}).get('transient_rulesmo_buffs', False):
            self.disable_generated_rules_for_client()
            self.append_log('Skipped transient rulesmo.ini buffs because generation.transient_rulesmo_buffs is disabled.')
            return False

        if RULESMO_INI.exists() and not is_generated_rules_file(RULESMO_INI):
            backup = backup_file_once(RULESMO_INI, 'before-randomizer')
            self.append_log(f'Existing rulesmo.ini was backed up to {backup}')

        lines = [
            RANDOMIZER_RULES_MARKER,
            '; Temporary direct-launch rules generated by the randomizer.',
            '; The launcher disables this file again after the spawned mission exits.',
            '',
        ]
        for section in sorted(rule_sections):
            lines.append(f'[{section}]')
            for key, value in sorted(rule_sections[section].items()):
                lines.append(f'{key}={value}')
            lines.append('')

        RULESMO_INI.write_text('\r\n'.join(lines), encoding='utf-8')
        self.append_log(f'Written transient rulesmo.ini with {len(rule_sections)} section(s).')
        return True

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
                self.unlock_mission_check(code, check_id, 'In-game hook')

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
            hook = None
            try:
                hook = self.prepare_hooked_map(mission, extra_rules=extra_rules)
            except Exception:
                self.append_log('Objective hook preparation failed; launching without automatic objective detection.', error=True)
                self.append_log(traceback.format_exc(), error=True)
                self.cleanup_generated_root_maps()
            self.write_spawn_ini(scenario, difficulty_value, game_speed_value)
            self.write_launch_options(difficulty_value, game_speed_value)
            self.write_transient_rulesmo_ini((hook or {}).get('rulesmo_sections', {}))
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
                'Objective/victory hooks are watching debug.log. After winning, exit back to the launcher manually; '
                'use Mark Complete only if the victory marker is missed.'
            )

    def reward_group_label(self, tech_id):
        return unit_display_label(tech_id)

    def current_unlocks_text(self):
        if not self.state:
            return 'No randomizer seed generated yet.'

        earned = [canonical_reward(reward) for reward in self.earned_rewards_from_checks()]
        if not earned:
            return 'No unlocks or buffs earned yet.'

        groups = {}

        def group_for(tech_id):
            group = groups.setdefault(tech_id, {
                'label': self.reward_group_label(tech_id),
                'access': {},
                'buffs': {},
                'other': [],
            })
            return group

        for reward in earned:
            if reward.get('kind') == 'buff' and reward.get('unit'):
                group = group_for(reward['unit'])
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
        for tech_id in sorted(groups, key=lambda item: groups[item]['label']):
            group = groups[tech_id]
            lines.append(group['label'])
            lines.append('-' * len(group['label']))

            if group['access']:
                for reward in sorted(group['access'].values(), key=lambda item: item.get('name', '')):
                    lines.append(f'Access: {reward_display_name(reward)}')
                    for summary in reward_rule_summary(reward):
                        lines.append(f'  {summary}')

            if group['buffs']:
                for entry in sorted(group['buffs'].values(), key=lambda item: item['reward'].get('name', '')):
                    reward = entry['reward']
                    count = effective_buff_count(reward, entry['count'])
                    lines.append(f'Buff x{count}: {reward_display_name(reward)}')
                    for summary in buff_effect_lines(reward, count=count):
                        lines.append(f'  {summary}')

            for reward in group['other']:
                lines.append(f'Reward: {reward_display_name(reward)}')
                for summary in reward_rule_summary(reward):
                    lines.append(f'  {summary}')

            lines.append('')

        return '\n'.join(lines).rstrip()

    def refresh_progress_view(self):
        if not self.state:
            self.progress_label.config(text='No randomizer seed generated. Vanilla mission launching is still available.')
            self.set_rewards_text('')
            self.set_unlocks_text('No randomizer seed generated yet.')
            return

        completed = len(self.state.get('completed_missions', []))
        order = self.state.get('mission_order', [])
        unlocked = len(self.unlocked_mission_codes())
        earned = self.state.get('earned_rewards', [])
        goal = self.state.get('mission_goal', len(order))
        status = 'Finished' if completed >= goal else 'In progress'
        self.progress_label.config(
            text=f'Seed: {self.state.get("seed", "")}\nGoal: {completed}/{goal} | Open: {unlocked} | Rewards: {len(earned)} | {status}'
        )

        lines = []
        selected = self.selected_mission()
        if selected:
            code = selected['code']
            done_checks, total_checks = self.mission_check_counts(code)
            lines.append(f'Selected: {selected["title"]} ({code})')
            lines.append(f'Mission rewards: {done_checks}/{total_checks}')

            earned_checks = [check for check in self.mission_checks(code) if check.get('unlocked')]
            missing_checks = [check for check in self.mission_checks(code) if not check.get('unlocked')]
            if earned_checks:
                lines.append('')
                lines.append('Earned here:')
                for check in earned_checks:
                    rewards = check_rewards(check)
                    lines.append(f'- {check["name"]}: {reward_names(rewards)}')
                    for reward in rewards:
                        lines.extend(reward_display_lines(reward, indent='  '))
            if missing_checks:
                lines.append('')
                lines.append('Missing here:')
                for check in missing_checks:
                    rewards = check_rewards(check)
                    lines.append(f'- {check["name"]}: {reward_names(rewards)}')
                    for reward in rewards:
                        lines.extend(reward_display_lines(reward, indent='  '))
                    hint = check.get('hint')
                    if hint:
                        lines.append(f'  Hint: {hint}')

        if earned:
            if lines:
                lines.append('')
                lines.append('All earned rewards:')
            for idx, reward in enumerate(earned, start=1):
                reward = canonical_reward(reward)
                lines.append(f'{idx}. {reward["name"]}')
                lines.extend(reward_display_lines(reward, indent='   '))
        elif not lines:
            lines.append('No rewards earned yet.')

        self.set_rewards_text('\n'.join(lines))
        self.set_unlocks_text(self.current_unlocks_text())

    def set_rewards_text(self, text):
        self.rewards_text.configure(state='normal')
        self.rewards_text.delete('1.0', 'end')
        self.rewards_text.insert('end', text)
        self.rewards_text.configure(state='disabled')

    def set_unlocks_text(self, text):
        self.unlocks_text.configure(state='normal')
        self.unlocks_text.delete('1.0', 'end')
        self.unlocks_text.insert('end', text)
        self.unlocks_text.configure(state='disabled')


def main():
    app = LauncherApp()
    app.mainloop()

