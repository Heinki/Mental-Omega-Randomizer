"""Compose launcher controllers into the Tk application."""

from ._dependencies import (
    APP_VERSION,
    BUFF_TYPES,
    CAMPAIGN_FILTERS,
    DEFAULT_MISSION_GOAL,
    DEFAULT_PROGRESSION_MODE,
    DEFAULT_REWARDS_PER_CHECK,
    DIFFICULTIES,
    EVA_VOICE_CHOICES,
    GAME_SPEEDS,
    MAX_REWARDS_PER_CHECK,
    PLAYER_COLORS,
    POWER_BUFF_TYPES,
    PROGRESSION_MODES,
    REWARD_MODES,
    WINDOW_ICON_PATH,
    clamp_int,
    load_config,
    log_event,
    queue,
    tk,
    valid_choice,
)

from .window import WindowController
from .state_controller import StateController
from .reward_controller import RewardController
from .advanced_settings import AdvancedSettingsController
from .power_buff_settings import PowerBuffSettingsController
from .progression_controller import ProgressionController
from .seed_controller import SeedController
from .launch_controller import LaunchController
from .unlock_data import UnlockDataController
from .unlock_view import UnlockViewController


class LauncherApp(
    WindowController,
    StateController,
    RewardController,
    AdvancedSettingsController,
    PowerBuffSettingsController,
    ProgressionController,
    SeedController,
    LaunchController,
    UnlockDataController,
    UnlockViewController,
    tk.Tk,
):
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
        self.hide_locked_grid_missions_var = tk.BooleanVar(
            value=bool(self.config.get('hide_locked_grid_missions', False))
        )
        self.state = self.load_state()
        self.migrate_state()
        self._reward_settings_override = None
        self._starting_defense_ids_override = None
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
        self.player_color_var = tk.StringVar(value=valid_choice(
            self.config.get('player_color'), PLAYER_COLORS, PLAYER_COLORS[0]
        ))
        self.rainbowizer_var = tk.BooleanVar(
            value=bool(self.config.get('rainbowizer', False))
        )
        self.eva_voice_var = tk.StringVar(value=valid_choice(
            self.config.get('eva_voice'),
            EVA_VOICE_CHOICES,
            EVA_VOICE_CHOICES[0],
        ))
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
        self.excluded_mission_codes = {
            str(code).upper()
            for code in generation_config.get('excluded_mission_codes', [])
            if str(code).strip()
        }
        self.excluded_unit_access_ids = {
            str(unit_id).upper()
            for unit_id in generation_config.get('excluded_unit_access_ids', [])
            if str(unit_id).strip()
        }
        self.excluded_superweapon_ids = {
            str(power_id).upper()
            for power_id in generation_config.get('excluded_superweapon_ids', [])
            if str(power_id).strip()
        }
        raw_buff_exclusions = generation_config.get('excluded_unit_buff_types', {})
        self.excluded_unit_buff_types = {
            str(unit_id).upper(): {
                str(buff_type)
                for buff_type in buff_types
                if str(buff_type).strip()
            }
            for unit_id, buff_types in (
                raw_buff_exclusions.items()
                if isinstance(raw_buff_exclusions, dict) else ()
            )
            if str(unit_id).strip() and isinstance(buff_types, list)
        }
        self.advanced_buff_unit_id = ''
        raw_power_buff_exclusions = generation_config.get(
            'excluded_power_buff_types', {}
        )
        self.excluded_power_buff_types = {
            str(power_id).upper(): {
                str(buff_type)
                for buff_type in buff_types
                if str(buff_type).strip()
            }
            for power_id, buff_types in (
                raw_power_buff_exclusions.items()
                if isinstance(raw_power_buff_exclusions, dict) else ()
            )
            if str(power_id).strip() and isinstance(buff_types, list)
        }
        self.advanced_power_buff_id = ''
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
        self.include_operation_missions_var = tk.BooleanVar(
            value=bool(generation_config.get('include_operation_missions', True))
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
        self.start_with_tier_one_defenses_var = tk.BooleanVar(
            value=reward_settings['start_with_tier_one_defenses']
        )
        self.include_defensive_buildings_var = tk.BooleanVar(
            value=reward_settings['include_defensive_buildings']
        )
        self.include_special_buildings_var = tk.BooleanVar(
            value=reward_settings['include_special_buildings']
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
        self.include_power_buff_rewards_var = tk.BooleanVar(
            value=reward_settings['include_power_buff_rewards']
        )
        self.buff_type_vars = {
            buff_type['id']: tk.BooleanVar(value=buff_type['id'] in enabled_buff_types)
            for buff_type in BUFF_TYPES
        }
        enabled_power_buff_types = set(
            reward_settings['enabled_power_buff_types']
        )
        self.power_buff_type_vars = {
            buff_type['id']: tk.BooleanVar(
                value=buff_type['id'] in enabled_power_buff_types
            )
            for buff_type in POWER_BUFF_TYPES
        }
        if self.unlimited_hero_units_var.get():
            self.buff_type_vars['build_limit'].set(False)
        self.log_visible_var = tk.BooleanVar(value=False)
        self.unlock_search_var = tk.StringVar(value='')
        self.header_summary_var = tk.StringVar(value='')
        self.unlock_search_current = None
        self.cameo_photo_cache = {}
        self.unlock_cameo_images = {}
        self.advanced_pool_images = {}
        self.cameo_retry_count = 0
        self.cameo_retry_after_id = None
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


def main():
    app = LauncherApp()
    app.mainloop()
