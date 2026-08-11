"""Compose launcher controllers into the Tk application."""

import uuid

from ._dependencies import (
    ARSENAL_FACTIONS,
    ARSENAL_POWER_TYPES,
    ARSENAL_TIERS,
    ARSENAL_UNIT_TYPES,
    APP_VERSION,
    BUFF_TYPES,
    CAMPAIGN_FILTERS,
    DEFAULT_MISSION_GOAL,
    DEFAULT_PROGRESSION_MODE,
    DEFAULT_REWARDS_PER_CHECK,
    DIFFICULTIES,
    EVA_VOICE_CHOICES,
    ENEMY_BUFF_DEFINITIONS,
    ENEMY_BUFF_GROUP_DEFINITIONS,
    GAME_SPEEDS,
    MAIN_REWARD_WEIGHT_TYPES,
    MAX_REWARDS_PER_CHECK,
    PLAYER_COLORS,
    POWER_BUFF_TYPES,
    POWER_BUFF_WEIGHT_TYPES,
    PROGRESSION_MODES,
    REWARD_MODES,
    STARTING_REWARD_TYPE_DEFINITIONS,
    UNIT_BUFF_WEIGHT_TYPES,
    WINDOW_ICON_PATH,
    clamp_int,
    load_config,
    log_event,
    normalize_reward_weights,
    normalize_arsenal_settings,
    normalize_enemy_scaling_settings,
    queue,
    tk,
    valid_choice,
)

from .window import WindowController
from .state_controller import StateController
from .reward_controller import RewardController
from .advanced_settings import AdvancedSettingsController
from .starting_unlocks import StartingUnlocksController
from .power_buff_settings import PowerBuffSettingsController
from .progression_controller import ProgressionController
from .seed_controller import SeedController
from .launch_controller import LaunchController
from .unlock_data import UnlockDataController
from .unlock_view import UnlockViewController
from .enemy_scaling import EnemyScalingController
from .archipelago_controller import ArchipelagoController


class LauncherApp(
    WindowController,
    StateController,
    RewardController,
    AdvancedSettingsController,
    StartingUnlocksController,
    PowerBuffSettingsController,
    ProgressionController,
    SeedController,
    LaunchController,
    UnlockDataController,
    UnlockViewController,
    EnemyScalingController,
    ArchipelagoController,
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
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        window_width = min(1600, max(1100, screen_width - 160))
        window_height = min(1000, max(700, screen_height - 160))
        window_x = max(0, (screen_width - window_width) // 2)
        window_y = max(0, (screen_height - window_height) // 2)
        self.geometry(
            f'{window_width}x{window_height}+{window_x}+{window_y}'
        )
        self.minsize(1100, 700)
        self.resizable(True, True)
        self.protocol('WM_DELETE_WINDOW', self.close_launcher)

        self.missions = []
        self._mission_by_code = {}
        self.config = load_config()
        archipelago_config = self.config.setdefault('archipelago', {})
        self.archipelago_client_uuid = str(
            archipelago_config.get('client_uuid') or uuid.uuid4()
        )
        saved_archipelago_server = str(
            archipelago_config.get('server') or 'archipelago.gg'
        ).strip()
        if saved_archipelago_server.casefold() in {
            'archipelaog.gg',
            'ws://archipelaog.gg',
            'wss://archipelaog.gg',
            'ws://archipelago.gg',
            'wss://archipelago.gg',
        }:
            saved_archipelago_server = 'archipelago.gg'
        self.archipelago_server_var = tk.StringVar(
            value=saved_archipelago_server
        )
        self.archipelago_port_var = tk.StringVar(
            value=str(archipelago_config.get('port', 38281))
        )
        self.archipelago_slot_var = tk.StringVar(
            value=str(
                archipelago_config.get(
                    'slot_name', self.config.get('player_name', 'Commander')
                )
            )
        )
        self.archipelago_password_var = tk.StringVar(value='')
        self.archipelago_chat_var = tk.StringVar(value='')
        self.archipelago_status_var = tk.StringVar(value='Disconnected')
        self.archipelago_yaml_status_var = tk.StringVar(
            value='Save a Player YAML from the current Settings-page values.'
        )
        self._archipelago_yaml_text = ''
        self._archipelago_gameplay_locked = False
        self._archipelago_locked_widget_states = {}
        self._archipelago_gameplay_widgets = ()
        self._archipelago_connection_widgets = ()
        self._archipelago_session = None
        self._archipelago_slot_data = {}
        self._archipelago_item_names = {}
        self._archipelago_players = {}
        self._archipelago_location_info = {}
        self._archipelago_server_checked_locations = set()
        self._archipelago_displayed_receipts = set()
        self._archipelago_last_status = None
        self._archipelago_connection_error = ''
        self._archipelago_session_validated = False
        self._archipelago_standalone_state = None
        self._archipelago_standalone_config = None
        self._archipelago_cached_state = None
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
        self._arsenal_override = None
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
        self.rewards_on_victory_only_var = tk.BooleanVar(
            value=bool(self.state.get(
                'rewards_on_victory_only',
                self.config.get('rewards_on_victory_only', False),
            ))
        )
        self.use_act_reward_multipliers_var = tk.BooleanVar(
            value=bool(self.state.get(
                'use_act_based_reward_multipliers',
                self.config.get('use_act_based_reward_multipliers', True),
            ))
        )
        generation_config = self.config.get('generation', {})
        arsenal_settings = normalize_arsenal_settings(
            generation_config.get('arsenal')
        )
        enabled_arsenal_factions = set(arsenal_settings['factions'])
        self.arsenal_faction_vars = {
            faction: tk.BooleanVar(value=faction in enabled_arsenal_factions)
            for faction in ARSENAL_FACTIONS
        }
        self.arsenal_roster_size_vars = {
            tier: {
                unit_type: tk.IntVar(
                    value=arsenal_settings['roster_sizes'][tier][unit_type]
                )
                for unit_type in ARSENAL_UNIT_TYPES
            }
            for tier in ARSENAL_TIERS
        }
        self.arsenal_power_count_vars = {
            power_type: tk.IntVar(
                value=arsenal_settings['power_counts'][power_type]
            )
            for power_type in ARSENAL_POWER_TYPES
        }
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
        self.unlock_all_grid_rewards_var = tk.BooleanVar(
            value=bool(self.state.get(
                'unlock_all_rewards_after_final_grid_mission',
                self.config.get('unlock_all_rewards_after_final_grid_mission', False),
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
        enemy_settings = normalize_enemy_scaling_settings(
            reward_settings.get('enemy_scaling')
        )
        self.manual_starting_reward_names = set(
            reward_settings['starting_unlock_rewards']
        )
        enabled_buff_types = set(reward_settings['enabled_buff_types'])
        self.buff_allied_helpers_var = tk.BooleanVar(
            value=bool(generation_config.get('buff_allied_helpers', False))
        )
        self.failure_assistance_var = tk.BooleanVar(
            value=bool(generation_config.get('failure_assistance', False))
        )
        self.enemy_reward_pool_var = tk.BooleanVar(
            value=enemy_settings['reward_enabled']
        )
        self.enemy_objective_rewards_var = tk.IntVar(
            value=enemy_settings['rewards_per_completed_objective']
        )
        self.enemy_mission_rewards_var = tk.IntVar(
            value=enemy_settings['rewards_per_completed_mission']
        )
        allowed_enemy_buffs = set(enemy_settings['allowed_buff_ids'])
        self.enemy_buff_enabled_vars = {
            definition['id']: tk.BooleanVar(
                value=definition['id'] in allowed_enemy_buffs
            )
            for definition in ENEMY_BUFF_DEFINITIONS
        }
        self.enemy_buff_cap_vars = {
            definition['id']: tk.IntVar(
                value=enemy_settings['caps'][definition['id']]
            )
            for definition in ENEMY_BUFF_DEFINITIONS
        }
        self.enemy_buff_group_vars = {
            group['id']: tk.BooleanVar(value=any(
                effect_id in allowed_enemy_buffs
                for effect_id in group['effect_ids']
            ))
            for group in ENEMY_BUFF_GROUP_DEFINITIONS
        }
        self.randomize_unit_access_var = tk.BooleanVar(
            value=reward_settings['randomize_unit_access']
        )
        self.start_with_tier_one_units_var = tk.BooleanVar(
            value=reward_settings['start_with_tier_one_units']
        )
        self.start_with_tier_one_defenses_var = tk.BooleanVar(
            value=reward_settings['start_with_tier_one_defenses']
        )
        self.starting_reward_count_var = tk.StringVar(
            value=str(reward_settings['starting_reward_count'])
        )
        allowed_starting_reward_types = set(
            reward_settings['starting_reward_types']
        )
        self.starting_reward_type_vars = {
            definition['id']: tk.BooleanVar(
                value=definition['id'] in allowed_starting_reward_types
            )
            for definition in STARTING_REWARD_TYPE_DEFINITIONS
        }
        self.include_defensive_buildings_var = tk.BooleanVar(
            value=reward_settings['include_defensive_buildings']
        )
        self.include_special_buildings_var = tk.BooleanVar(
            value=reward_settings['include_special_buildings']
        )
        self.include_special_rewards_var = tk.BooleanVar(
            value=reward_settings['include_special_rewards']
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
        reward_weights = normalize_reward_weights(
            reward_settings.get('reward_weights')
        )
        self.main_reward_weight_vars = {
            definition['id']: tk.IntVar(
                value=reward_weights['main'][definition['id']]
            )
            for definition in MAIN_REWARD_WEIGHT_TYPES
        }
        self.unit_buff_weight_vars = {
            weight_id: tk.IntVar(
                value=reward_weights['unit_buffs'][weight_id]
            )
            for weight_id, _label in UNIT_BUFF_WEIGHT_TYPES
        }
        self.power_buff_weight_vars = {
            weight_id: tk.IntVar(
                value=reward_weights['power_buffs'][weight_id]
            )
            for weight_id, _label in POWER_BUFF_WEIGHT_TYPES
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
        self._unlocks_view_dirty = True
        self._enemy_buffs_view_dirty = True
        self.busy_depth = 0
        self.ui_queue = queue.Queue()
        self.cleanup_generated_root_maps()
        self.disable_generated_rules_for_client()

        self.create_widgets()
        self.after(40, self.process_ui_queue)

        self.after_idle(self.start_initial_load)

    def start_initial_load(self):
        self.run_in_background(
            'Loading randomizer…',
            'Reading missions and restoring the current run. Please wait.',
            self.load_missions,
            self.finish_initial_load,
            self.handle_initial_load_error,
        )

    def finish_initial_load(self, missions):
        self.apply_missions(missions)
        self.refresh_progress_view()
        self.initial_load_complete = True
        log_event(
            'launcher_ready',
            missions=len(self.missions),
            has_seed=bool(self.state),
            seed=self.state.get('seed', ''),
        )

    def handle_initial_load_error(self, exc, detail):
        self.initial_load_complete = True
        self.append_log(f'Launcher startup failed: {exc}', error=True)
        log_event('launcher_startup_failed', error=str(exc), traceback=detail)


def main():
    app = LauncherApp()
    app.mainloop()
