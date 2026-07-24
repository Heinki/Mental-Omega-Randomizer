import json
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

from randomizer_config import CONFIG_PATH, DEFAULT_CONFIG, load_config, save_config
from randomizer_storage import atomic_write_text
from randomizer_cameos import (
    cameo_extraction_pending,
    ensure_superweapon_cameos,
    ensure_unit_cameos,
    mix_reader_assembly_paths,
    powershell_mix_reader_load_script,
)
from randomizer_diagnostics import event as log_event
from randomizer_custom_assets import custom_sidebar_preview
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
    FALLBACK_OBJECTIVE_COUNT,
    LATE_FOEHN_MISSION_CODES,
    LOW_LEVEL_MISSION_COUNT,
    NO_BUILD_MISSION_CODES,
    OPERATION_MISSION_CODES,
    STARTING_UNLOCKED_MISSIONS,
    campaign_mission_counts,
    classic_mission_order,
    filter_missions_by_build_settings,
    normalize_faction,
    parse_missions,
    seed_campaign_limits,
    seed_mission_order,
)
from randomizer_mission_houses import (
    mission_player_production_houses,
)
from randomizer_ini import (
    read_text,
    set_ini_value_lines,
)
from randomizer_rewards import (
    ALWAYS_AVAILABLE_TECH_IDS,
    BUFF_TARGETS,
    BUFF_TYPES,
    DEFAULT_REWARDS_PER_CHECK,
    effective_buff_count,
    buff_stack_limit,
    MAX_REWARDS_PER_CHECK,
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


from randomizer_paths import (
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
from randomizer_map import (
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
    tech_ids_for_rewards,
    unlocked_reward_tech_ids,
)
from randomizer_mission_safety import (
    always_available_transport_rules,
    chaos_earned_access_rules,
    expanded_tier_one_defense_ids,
    expanded_tier_one_unit_ids,
    mission_basic_unit_rules,
    random_chaos_tier_one_unit_ids,
    single_engineer_rules,
    starting_tier_one_defense_rules,
    starting_tier_one_rules,
    summarize_basic_unit_rules,
    tier_one_defense_ids,
    tier_one_unit_ids,
    tier_one_role_label,
)
from randomizer_map_pipeline import prepare_hooked_map as prepare_hooked_mission_map
from randomizer_mission_overrides import (
    MISSION_REQUIRED_ACCESS_RULES,
    MISSIONS_WITH_ALL_CONYARD_DEFENSE_ACCESS,
    STANDARD_STARTER_FAMILIES_BY_CAMPAIGN,
)
from randomizer_ui import (
    CAMPAIGN_FILTERS,
    DARK_UI_PALETTE,
    DEFAULT_PROGRESSION_MODE,
    DIFFICULTIES,
    FACTION_TILE_COLORS,
    GAME_SPEEDS,
    LIGHT_UI_PALETTE,
    PLAYER_COLORS,
    PROGRESSION_MODES,
    RAINBOWIZER_COLORS,
    REWARDS_PER_CHECK_MAXIMUM_MESSAGE,
    REWARDS_PER_CHECK_MESSAGE_THRESHOLDS,
    REWARD_MODES,
)
from randomizer_ui_builder import (
    WidgetTooltip,
    apply_color_mode as apply_launcher_color_mode,
    create_widgets as build_launcher_widgets,
    redraw_grid as redraw_launcher_grid,
)
from randomizer_tuning import REWARD_PLANNING

DEFAULT_MISSION_GOAL = int(DEFAULT_CONFIG['mission_goal'])
CHECK_SCHEMA_VERSION = 16
HOOK_POLL_MS = 1500
VICTORY_CLOSE_DELAY_MS = 2500
MAX_OPTION_INI_BYTES = 2 * 1024 * 1024
MAX_GLOBAL_BUFF_REPEATS_PER_SEED = int(
    REWARD_PLANNING['maximum_global_buff_repeats_per_seed']
)
GLOBAL_BUFF_REWARD_INTERVAL = int(REWARD_PLANNING['global_buff_reward_interval'])


def reward_cameo_token(reward):
    """Return Unlocks placeholder, preferring configured custom artwork."""
    if reward.get('kind') != 'superweapon' or not reward.get('superweapon'):
        return ''
    sidebar_image = reward.get('superweapon_sidebar_image')
    if sidebar_image:
        return f'[[MOR_ASSET:{sidebar_image}]]'
    cameo_superweapon = reward.get('cameo_superweapon', reward['superweapon'])
    return f'[[MOR_POWER:{cameo_superweapon}]]'




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
        self.buff_type_vars = {
            buff_type['id']: tk.BooleanVar(value=buff_type['id'] in enabled_buff_types)
            for buff_type in BUFF_TYPES
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
        build_launcher_widgets(self)

    def update_header_summary(self, *_args):
        """Show the core selected run settings beneath the launcher title."""
        self.header_summary_var.set(' • '.join((
            self.campaign_var.get(),
            self.reward_mode_var.get(),
            self.progression_mode_var.get(),
            self.difficulty_var.get(),
            self.game_speed_var.get(),
        )))

    def toggle_settings_panel(self):
        self.unlock_hover_card_key = None
        self.set_unlock_grid_highlights(())
        self.settings_panel_visible = not self.settings_panel_visible
        if self.settings_panel_visible:
            self.right_frame.grid()
            self.mission_view_frame.grid_configure(columnspan=1, padx=(0, 12))
            self.compact_action_row.grid_remove()
            self.settings_toggle_button.configure(text='Hide Details')
        else:
            self.right_frame.grid_remove()
            self.mission_view_frame.grid_configure(columnspan=2, padx=0)
            self.compact_action_row.grid()
            self.settings_toggle_button.configure(text='Show Details')
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
        apply_launcher_color_mode(self)

    def save_ui_preferences(self):
        self.config['dark_mode'] = bool(self.dark_mode_var.get())
        self.config['hide_reward_details'] = bool(self.hide_reward_details_var.get())
        self.config['hide_locked_grid_missions'] = bool(
            self.hide_locked_grid_missions_var.get()
        )
        save_config(self.config)

    def on_dark_mode_changed(self):
        self.apply_color_mode()
        self.save_ui_preferences()
        if hasattr(self, 'grid_content_frame'):
            self.grid_render_signature = None
            self.redraw_grid()
        self.unlock_dashboard_signature = None
        self.refresh_progress_view()

    def on_hide_reward_details_changed(self):
        self.save_ui_preferences()
        self.refresh_progress_view()

    def on_hide_locked_grid_missions_changed(self):
        self.save_ui_preferences()
        if (
            self.hide_locked_grid_missions_var.get()
            and self.active_progression_mode() == 'Grid Mode'
            and self.state
        ):
            states = self.sync_grid_progression()
            selected_code = self.selected_mission_code()
            if states.get(selected_code) == GRID_LOCKED:
                visible_code = next(
                    (code for code, state in states.items() if state != GRID_LOCKED),
                    None,
                )
                if visible_code:
                    visible_index = next(
                        (
                            index
                            for index, mission in enumerate(self.missions)
                            if mission.get('code') == visible_code
                        ),
                        None,
                    )
                    if visible_index is not None:
                        self.selected_index.set(visible_index)
        self.refresh_grid_tiles()
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
            previous_switch_interval = sys.getswitchinterval()
            # Reward planning is Python-heavy. A shorter handoff interval keeps
            # Tk's elapsed label and indeterminate bar repainting smoothly.
            sys.setswitchinterval(min(previous_switch_interval, 0.001))
            try:
                result = callback()
            except Exception as exc:
                error_detail = traceback.format_exc()

                def deliver_error(exc=exc, error_detail=error_detail):
                    self.hide_busy()
                    try:
                        on_error(exc, error_detail)
                    except Exception:
                        self.append_log(traceback.format_exc(), error=True)

                self.ui_queue.put(('callback', deliver_error))
                return
            finally:
                sys.setswitchinterval(previous_switch_interval)

            def deliver_result(result=result):
                # The background phase is finished. Remove the animated
                # overlay before the main-thread UI refresh so it cannot look
                # like a frozen loading screen while cards/grid are painted.
                self.hide_busy()
                try:
                    on_success(result)
                except Exception as exc:
                    on_error(exc, traceback.format_exc())

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
        if hasattr(self, 'rewards_per_check_message_label'):
            self.rewards_per_check_message_label.configure(
                wraplength=max(180, event.width - 64)
            )

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

    def on_settings_control_mousewheel(self, event):
        """Scroll Settings without changing the focused readonly control."""
        if hasattr(self, 'settings_canvas'):
            self.settings_canvas.yview_scroll(-1 if event.delta > 0 else 1, 'units')
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

    @staticmethod
    def on_unlock_mousewheel(event, canvas):
        canvas.yview_scroll(-1 if event.delta > 0 else 1, 'units')
        return 'break'

    def on_unlock_canvas_configure(self, faction, canvas, window, width):
        canvas.itemconfigure(window, width=max(1, width))
        self.after_idle(
            lambda selected=faction: self.layout_unlock_dashboard_faction(selected)
        )

    def layout_unlock_dashboard_faction(self, faction):
        sections = getattr(self, 'unlock_dashboard_sections', {}).get(faction)
        canvas = getattr(self, 'unlock_icon_canvases', {}).get(faction)
        if not sections or canvas is None:
            return
        columns = max(2, min(4, max(1, canvas.winfo_width() - 8) // 84))
        column_cache = getattr(self, 'unlock_dashboard_columns', {})
        if column_cache.get(faction) == columns:
            return
        column_cache[faction] = columns
        self.unlock_dashboard_columns = column_cache
        row = 0
        for heading, cards in sections:
            heading.grid_configure(row=row, column=0, columnspan=columns)
            row += 1
            for index, card in enumerate(cards):
                card.grid_configure(
                    row=row + index // columns,
                    column=index % columns,
                )
            row += (len(cards) + columns - 1) // columns

    def set_unlock_grid_highlights(self, mission_codes):
        previous = set(getattr(self, 'unlock_hover_grid_codes', set()))
        current = set(mission_codes or ())
        if previous == current:
            return
        self.unlock_hover_grid_codes = current
        if self.active_progression_mode() == 'Grid Mode':
            self.refresh_grid_tiles(previous | current)
        else:
            self.refresh_mission_tree_unlock_highlights(previous | current)

    def refresh_mission_tree_unlock_highlights(self, mission_codes=None):
        current = set(getattr(self, 'unlock_hover_grid_codes', set()))
        codes = set(mission_codes or current)
        for item in self.missions_tree.get_children():
            try:
                code = self.missions[int(item)]['code']
            except (IndexError, TypeError, ValueError):
                continue
            if mission_codes is not None and code not in codes:
                continue
            tags = [tag for tag in self.missions_tree.item(item, 'tags')
                    if tag != 'unlock_available']
            if code in current:
                tags.append('unlock_available')
            self.missions_tree.item(item, tags=tuple(tags))

    def on_unlock_card_enter(self, card, entry=None):
        entry = entry or getattr(card, 'unlock_entry', {})
        self.unlock_hover_card_key = entry.get('key')
        mission_codes = (
            entry['sources'].get('available_codes', ())
            if entry.get('status') == 'available' and not entry.get('privacy')
            else ()
        )
        self.set_unlock_grid_highlights(mission_codes)

    def on_unlock_card_leave(self, card=None):
        # Tk can briefly report Leave while creating a tooltip Toplevel. Wait
        # one event turn and clear only when the pointer truly left the card.
        def clear_if_outside():
            entry = getattr(card, 'unlock_entry', {}) if card is not None else {}
            card_key = entry.get('key')
            if card_key != getattr(self, 'unlock_hover_card_key', None):
                return
            current_card = getattr(self, 'unlock_dashboard_cards', {}).get(
                card_key, {}
            ).get('card')
            # A cameo refresh may replace the widget beneath a stationary
            # pointer. The replacement still represents the hovered reward.
            if current_card is not None and current_card is not card:
                return
            if card is not None and card.winfo_exists():
                x, y = self.winfo_pointerx(), self.winfo_pointery()
                left, top = card.winfo_rootx(), card.winfo_rooty()
                if left <= x < left + card.winfo_width() and top <= y < top + card.winfo_height():
                    return
            self.unlock_hover_card_key = None
            self.set_unlock_grid_highlights(())

        self.after(20, clear_if_outside)

    def focus_unlock_search(self, event=None):
        if hasattr(self, 'info_tabs') and hasattr(self, 'unlocks_tab'):
            self.info_tabs.select(self.unlocks_tab)
        if hasattr(self, 'unlocks_notebook'):
            tabs = self.unlocks_notebook.tabs()
            if tabs:
                self.unlocks_notebook.select(tabs[-1])
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
        if hasattr(self, 'unlocks_notebook'):
            tabs = self.unlocks_notebook.tabs()
            if tabs:
                self.unlocks_notebook.select(tabs[-1])

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
            self.main_frame.rowconfigure(9, weight=0)
            self.log_toggle_button.configure(text='Show Launcher Log')
            self.log_visible_var.set(False)
        else:
            self.log_text.grid()
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
        atomic_write_text(STATE_PATH, json.dumps(self.state, indent=2))

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
        start_with_tier_one_defenses = bool(
            generation_config.get('start_with_tier_one_defenses', False)
        )
        include_buffs = bool(generation_config.get('include_buff_rewards', 'buff' in enabled_reward_types))
        include_superweapons = bool(generation_config.get('include_superweapon_rewards', True))
        include_secondary_superweapons = bool(
            generation_config.get('include_secondary_superweapon_rewards', True)
        )
        include_aid_powers = bool(generation_config.get('include_aid_power_rewards', True))
        include_defensive_buildings = bool(generation_config.get('include_defensive_buildings', True))
        include_special_buildings = bool(generation_config.get('include_special_buildings', True))
        unlimited_hero_units = bool(generation_config.get('unlimited_hero_units', False))
        share_chaos_role_buffs = bool(generation_config.get('share_chaos_role_buffs', False))
        buff_allied_helpers = bool(generation_config.get('buff_allied_helpers', False))
        failure_assistance = bool(generation_config.get('failure_assistance', False))
        if generation_config.get('reward_mode') == 'Chaos (Experimental)':
            randomize_access = True
        return {
            'randomize_unit_access': randomize_access,
            'start_with_tier_one_units': start_with_tier_one_units,
            'start_with_tier_one_defenses': start_with_tier_one_defenses,
            'include_defensive_buildings': include_defensive_buildings,
            'include_special_buildings': include_special_buildings,
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
            'excluded_unit_access_ids': sorted({
                str(unit_id).upper()
                for unit_id in generation_config.get('excluded_unit_access_ids', [])
                if str(unit_id).strip()
            }),
            'excluded_superweapon_ids': sorted({
                str(power_id).upper()
                for power_id in generation_config.get('excluded_superweapon_ids', [])
                if str(power_id).strip()
            }),
            'excluded_unit_buff_types': {
                str(unit_id).upper(): sorted({str(item) for item in buff_types})
                for unit_id, buff_types in generation_config.get(
                    'excluded_unit_buff_types', {}
                ).items()
                if isinstance(buff_types, list)
            } if isinstance(
                generation_config.get('excluded_unit_buff_types', {}), dict
            ) else {},
        }

    def current_reward_settings(self):
        if 'randomize_unit_access_var' not in self.__dict__:
            return self.config_reward_settings()
        chaos_mode = self.reward_mode_var.get() == 'Chaos (Experimental)'
        randomize_access = chaos_mode or bool(self.randomize_unit_access_var.get())
        start_with_tier_one_units = bool(self.start_with_tier_one_units_var.get())
        start_with_tier_one_defenses = bool(
            self.start_with_tier_one_defenses_var.get()
        )
        include_defensive_buildings = bool(self.include_defensive_buildings_var.get())
        include_special_buildings = bool(self.include_special_buildings_var.get())
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
        return {
            'randomize_unit_access': randomize_access,
            'start_with_tier_one_units': start_with_tier_one_units,
            'start_with_tier_one_defenses': start_with_tier_one_defenses,
            'include_defensive_buildings': include_defensive_buildings,
            'include_special_buildings': include_special_buildings,
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
            'excluded_unit_access_ids': sorted(self.excluded_unit_access_ids),
            'excluded_superweapon_ids': sorted(self.excluded_superweapon_ids),
            'excluded_unit_buff_types': {
                unit_id: sorted(buff_types)
                for unit_id, buff_types in sorted(self.excluded_unit_buff_types.items())
                if buff_types
            },
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
        settings.setdefault('start_with_tier_one_defenses', False)
        settings.setdefault('include_defensive_buildings', True)
        settings.setdefault('include_special_buildings', True)
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
        settings.setdefault('excluded_unit_access_ids', [])
        settings.setdefault('excluded_superweapon_ids', [])
        settings.setdefault('excluded_unit_buff_types', {})
        if not isinstance(settings.get('enabled_buff_types'), list):
            settings['enabled_buff_types'] = [buff_type['id'] for buff_type in BUFF_TYPES]
        return settings

    def randomize_unit_access_enabled(self):
        return bool(self.active_reward_settings().get('randomize_unit_access', True))

    def starting_tier_one_unit_ids_for_seed(self, seed, reward_settings=None):
        settings = reward_settings or self.active_reward_settings()
        if not settings.get('start_with_tier_one_units', False):
            return []
        excluded_ids = {
            str(unit_id).upper()
            for unit_id in settings.get('excluded_unit_access_ids', [])
        }
        if self.active_reward_mode() == 'Chaos (Experimental)':
            rng = random.Random(f'{seed}:starting-tier-one')
            return [
                unit_id
                for unit_id in random_chaos_tier_one_unit_ids(rng)
                if not linked_buff_variant_ids(unit_id).intersection(excluded_ids)
            ]

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
        return [
            marker
            for marker in tier_one_unit_ids(families)
            if expanded_tier_one_unit_ids([marker]) - excluded_ids
        ]

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

    def active_starting_tier_one_expanded_ids(self):
        """Resolve starter markers after authoritative Advanced Pool exclusions."""
        excluded_ids = {
            str(unit_id).upper()
            for unit_id in self.active_reward_settings().get(
                'excluded_unit_access_ids', []
            )
        }
        return expanded_tier_one_unit_ids(
            self.active_starting_tier_one_unit_ids()
        ) - excluded_ids

    def active_standard_starter_families(self):
        generation_context = self.__dict__.get('_seed_generation_context') or {}
        selected = generation_context.get('campaign_filter')
        if selected is None:
            selected = (self.state or {}).get('campaign_filter')
        if not selected:
            selected = (
                self.campaign_var.get()
                if hasattr(self, 'campaign_var')
                else self.config.get('campaign_filter', 'All Campaigns')
            )
        return tuple(
            STANDARD_STARTER_FAMILIES_BY_CAMPAIGN.get(
                selected,
                ('allies', 'soviets', 'epsilon'),
            )
        )

    def starting_tier_one_defense_ids_for_seed(self, reward_settings=None):
        settings = reward_settings or self.active_reward_settings()
        if not settings.get('start_with_tier_one_defenses', False):
            return []
        excluded_ids = {
            str(unit_id).upper()
            for unit_id in settings.get('excluded_unit_access_ids', [])
        }
        families = self.active_standard_starter_families()
        marker = tier_one_defense_ids(families)
        eligible_ids = expanded_tier_one_defense_ids(
            marker,
            include_foehn=(
                self.active_reward_mode() == 'Chaos (Experimental)'
            ),
            families=families,
        )
        return list(marker) if eligible_ids - excluded_ids else []

    def active_starting_tier_one_defense_ids(self):
        override = self.__dict__.get('_starting_defense_ids_override')
        if override is not None:
            return list(override)
        if self.state:
            return [
                str(unit_id).upper()
                for unit_id in self.state.get('starting_defense_ids', [])
                if unit_id
            ]
        return self.starting_tier_one_defense_ids_for_seed()

    def active_starting_tier_one_defense_expanded_ids(self):
        excluded_ids = {
            str(unit_id).upper()
            for unit_id in self.active_reward_settings().get(
                'excluded_unit_access_ids', []
            )
        }
        return expanded_tier_one_defense_ids(
            self.active_starting_tier_one_defense_ids(),
            include_foehn=(
                self.active_reward_mode() == 'Chaos (Experimental)'
            ),
            families=self.active_standard_starter_families(),
        ) - excluded_ids

    def active_starting_tier_one_access_ids(self):
        return (
            self.active_starting_tier_one_expanded_ids()
            | self.active_starting_tier_one_defense_expanded_ids()
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
        self.config['hide_locked_grid_missions'] = bool(
            self.hide_locked_grid_missions_var.get()
        )
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
        self.config['player_color'] = self.player_color_var.get()
        self.config['rainbowizer'] = bool(self.rainbowizer_var.get())
        reward_settings = self.current_reward_settings()
        self.config.setdefault('generation', {})['starting_unlocked_missions'] = STARTING_UNLOCKED_MISSIONS
        self.config['generation']['include_no_build_missions'] = bool(
            self.include_no_build_missions_var.get()
        )
        self.config['generation']['include_no_build_production_missions'] = bool(
            self.include_no_build_production_missions_var.get()
        )
        self.config['generation']['include_operation_missions'] = bool(
            self.include_operation_missions_var.get()
        )
        self.config['generation']['prioritize_no_build_missions'] = bool(
            self.prioritize_no_build_missions_var.get()
        )
        self.config['generation']['excluded_mission_codes'] = sorted(self.excluded_mission_codes)
        self.config['generation']['excluded_unit_access_ids'] = sorted(
            self.excluded_unit_access_ids
        )
        self.config['generation']['excluded_superweapon_ids'] = sorted(
            self.excluded_superweapon_ids
        )
        self.config['generation']['excluded_unit_buff_types'] = {
            unit_id: sorted(buff_types)
            for unit_id, buff_types in sorted(self.excluded_unit_buff_types.items())
            if buff_types
        }
        self.config['generation']['buff_allied_helpers'] = bool(self.buff_allied_helpers_var.get())
        self.config['generation']['failure_assistance'] = reward_settings['failure_assistance']
        self.config['generation'].pop('experimental_player_unit_clones', None)
        self.config['generation']['enabled_reward_types'] = reward_settings['enabled_reward_types']
        self.config['generation']['randomize_unit_access'] = reward_settings['randomize_unit_access']
        self.config['generation']['start_with_tier_one_units'] = reward_settings['start_with_tier_one_units']
        self.config['generation']['start_with_tier_one_defenses'] = reward_settings['start_with_tier_one_defenses']
        self.config['generation']['include_defensive_buildings'] = reward_settings['include_defensive_buildings']
        self.config['generation']['include_special_buildings'] = reward_settings['include_special_buildings']
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
        if selected == 'All Campaigns':
            return {'Allies', 'Soviets', 'Epsilon'}
        return None

    def standard_foehn_unit_reward(self, reward):
        """Keep native Foehn unit access exclusive to Chaos reward mode."""
        reward = canonical_reward(reward)
        return bool(
            self.active_reward_mode() != 'Chaos (Experimental)'
            and reward.get('kind') != 'superweapon'
            and reward.get('access_category') != 'special_building'
            and not self.reward_is_special_building(reward)
            and set(reward.get('factions') or ()) == {'Foehn'}
        )

    def active_launch_rewards(self):
        rewards = canonical_rewards(
            self.earned_rewards_from_checks() if self.state else []
        )
        rewards = [
            reward
            for reward in rewards
            if not self.standard_foehn_unit_reward(reward)
        ]
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
                    and (
                        reward.get('kind') == 'superweapon'
                        or reward.get('access_category') == 'special_building'
                        or self.reward_is_special_building(reward)
                    )
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

    def reward_is_special_building(self, reward):
        if reward.get('access_category') == 'special_building':
            return True
        unit_id = str(reward.get('unit') or '').upper()
        return bool(
            unit_id
            and BUFF_TARGETS.get(unit_id, {}).get('category') == 'special_buildings'
        )

    def filter_reward_pool(self, pool):
        reward_settings = self.active_reward_settings()
        excluded_access_ids = {
            str(unit_id).upper()
            for unit_id in reward_settings.get('excluded_unit_access_ids', [])
        }
        excluded_superweapon_ids = {
            str(power_id).upper()
            for power_id in reward_settings.get('excluded_superweapon_ids', [])
        }
        starting_access_ids = self.active_starting_tier_one_access_ids()
        randomize_access = bool(reward_settings.get('randomize_unit_access', True))
        include_buffs = bool(reward_settings.get('include_buff_rewards', True))
        include_superweapons = bool(reward_settings.get('include_superweapon_rewards', False))
        include_secondary_superweapons = bool(
            reward_settings.get('include_secondary_superweapon_rewards', False)
        )
        include_aid_powers = bool(reward_settings.get('include_aid_power_rewards', False))
        include_defensive_buildings = bool(reward_settings.get('include_defensive_buildings', True))
        include_special_buildings = bool(reward_settings.get('include_special_buildings', True))
        enabled_buff_types = set(reward_settings.get('enabled_buff_types') or [])
        excluded_unit_buff_types = {
            str(unit_id).upper(): {str(buff_type) for buff_type in buff_types}
            for unit_id, buff_types in reward_settings.get(
                'excluded_unit_buff_types', {}
            ).items()
            if isinstance(buff_types, (list, tuple, set))
        }
        chaos_mode = self.active_reward_mode() == 'Chaos (Experimental)'

        def buff_unit_is_allowed(reward):
            unit_id = str(reward.get('unit') or '').upper()
            if not unit_id or unit_id in ALWAYS_AVAILABLE_TECH_IDS:
                return True
            return not linked_buff_variant_ids(unit_id).intersection(
                excluded_access_ids
            )

        return [
            reward
            for reward in pool
            if (
                (
                    reward.get('kind') == 'buff'
                    and include_buffs
                    and (include_defensive_buildings or not self.reward_is_defensive_building(reward))
                    and (include_special_buildings or not self.reward_is_special_building(reward))
                    and reward.get('buff_type') in enabled_buff_types
                    and reward.get('buff_type') not in excluded_unit_buff_types.get(
                        str(reward.get('unit') or '').upper(), set()
                    )
                    and buff_unit_is_allowed(reward)
                    and not (
                        reward_settings.get('unlimited_hero_units')
                        and reward.get('buff_type') == 'build_limit'
                        and not self.reward_is_special_building(reward)
                    )
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
                    and str(reward.get('superweapon') or '').upper()
                    not in excluded_superweapon_ids
                )
                or (
                    reward.get('kind') not in {'buff', 'superweapon'}
                    and randomize_access
                    and (include_defensive_buildings or not self.reward_is_defensive_building(reward))
                    and (include_special_buildings or not self.reward_is_special_building(reward))
                    and not tech_ids_for_rewards([reward]).intersection(starting_access_ids)
                    and not tech_ids_for_rewards([reward]).intersection(excluded_access_ids)
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
            self.active_starting_tier_one_access_ids()
            | set(ALWAYS_AVAILABLE_TECH_IDS)
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
        self.refresh_advanced_pool_views()

        if not self.missions:
            self.append_log('No missions found. Check INI/BattleClient.ini and game root paths.', error=True)
            return

        children = self.missions_tree.get_children()
        if children:
            self.missions_tree.selection_set(children[0])
            self.selected_index.set(int(children[0]))
        self.append_log(f'Loaded {len(self.missions)} missions.')

    def advanced_unit_pool_entries(self):
        """Return combat-unit access targets represented by the reward pool."""
        entries = {}
        for reward in REWARD_POOL:
            if reward.get('kind') in {'buff', 'superweapon'}:
                continue
            factions = tuple(reward.get('factions') or ('Other',))
            for unit_id in tech_ids_for_rewards([reward]):
                linked_ids = linked_buff_variant_ids(unit_id)
                unit_id = next(
                    (
                        candidate
                        for candidate in linked_ids
                        if not BUFF_TARGETS.get(candidate, {}).get('linked_buff_source')
                    ),
                    unit_id,
                )
                target = BUFF_TARGETS.get(unit_id, {})
                if target.get('category') not in {
                    'infantry', 'units', 'aircraft', 'defenses',
                    'special_buildings',
                }:
                    continue
                entries.setdefault(unit_id, {
                    'id': unit_id,
                    'label': unit_display_label(unit_id),
                    'faction': factions[0],
                })
        faction_rank = {'Allies': 0, 'Soviets': 1, 'Epsilon': 2, 'Foehn': 3, 'Other': 4}
        return sorted(
            entries.values(),
            key=lambda entry: (
                faction_rank.get(entry['faction'], 4),
                entry['label'].casefold(),
                entry['id'],
            ),
        )

    def advanced_buff_unit_entries(self):
        """Return units that can receive at least one configured buff reward."""
        entries = {}
        for reward in REWARD_POOL:
            if reward.get('kind') != 'buff' or not reward.get('unit'):
                continue
            unit_id = str(reward['unit']).upper()
            target = BUFF_TARGETS.get(unit_id, {})
            if target.get('category') not in {
                'infantry', 'units', 'aircraft', 'defenses', 'special_buildings',
            }:
                continue
            entry = entries.setdefault(unit_id, {
                'id': unit_id,
                'label': unit_display_label(unit_id),
                'faction': self.unit_faction(unit_id),
                'buff_types': set(),
            })
            entry['buff_types'].add(str(reward.get('buff_type') or ''))
        faction_rank = {'Allies': 0, 'Soviets': 1, 'Epsilon': 2, 'Foehn': 3, 'Other': 4}
        return sorted(
            entries.values(),
            key=lambda entry: (
                faction_rank.get(entry['faction'], 4),
                entry['label'].casefold(),
                entry['id'],
            ),
        )

    def advanced_buff_unit_is_visible(self, entry):
        unit_id = entry['id']
        if (
            not self.include_special_buildings_var.get()
            and BUFF_TARGETS.get(unit_id, {}).get('category') == 'special_buildings'
        ):
            return False
        if unit_id not in ALWAYS_AVAILABLE_TECH_IDS and linked_buff_variant_ids(
            unit_id
        ).intersection(self.excluded_unit_access_ids):
            return False
        selected_campaign = self.campaign_var.get()
        return (
            selected_campaign == CAMPAIGN_FILTERS[0]
            or entry.get('faction') == selected_campaign
        )

    def draw_advanced_buff_unit_card(self, parent, row, column, entry, photo=None):
        unit_id = entry['id']
        selected = unit_id == self.advanced_buff_unit_id
        possible = set(entry['buff_types'])
        excluded = self.excluded_unit_buff_types.get(unit_id, set())
        enabled_count = len(possible - excluded)
        border = '#73d673' if selected else '#4d92d8'
        card = tk.Canvas(
            parent, width=130, height=112, highlightthickness=3 if selected else 2,
            highlightbackground=border, highlightcolor=border,
            background=FACTION_TILE_COLORS.get(entry.get('faction'), '#315b82'),
            cursor='hand2',
        )
        card.grid(row=row, column=column, padx=4, pady=4, sticky='nw')
        if photo is not None:
            card.create_image(65, 35, image=photo, anchor='center')
        else:
            card.create_text(
                65, 35, text=entry.get('faction') or '?', fill='#ffffff',
                font=('Segoe UI', 10, 'bold'), width=122, justify='center',
            )
        card.create_rectangle(0, 72, 130, 112, fill='#151a20', outline='')
        card.create_text(
            65, 87, text=entry['label'], fill='#ffffff',
            font=('Segoe UI', 9, 'bold'), width=122, justify='center',
        )
        card.create_text(
            65, 105, text=f'{enabled_count}/{len(possible)} buffs',
            fill='#73d673' if enabled_count else '#aeb4bb',
            font=('Segoe UI', 8), width=122, justify='center',
        )
        card.bind(
            '<Button-1>',
            lambda _event, item_id=unit_id: self.select_advanced_buff_unit(item_id),
        )
        card.bind(
            '<MouseWheel>',
            lambda event, target=self.advanced_pool_canvases['unit_buffs']: (
                self.on_unlock_mousewheel(event, target)
            ),
        )
        WidgetTooltip(
            card,
            f'{entry["label"]} ({unit_id})\n{enabled_count} of {len(possible)} buff types enabled',
        )

    def refresh_advanced_buff_view(self):
        if 'unit_buffs' not in getattr(self, 'advanced_pool_frames', {}):
            return
        frame = self.advanced_pool_frames['unit_buffs']
        for child in frame.winfo_children():
            child.destroy()
        entries = [
            entry for entry in self.advanced_buff_unit_entries()
            if self.advanced_buff_unit_is_visible(entry)
        ]
        if not entries:
            self.advanced_buff_unit_id = ''
        elif self.advanced_buff_unit_id not in {entry['id'] for entry in entries}:
            self.advanced_buff_unit_id = entries[0]['id']

        cameo_paths = getattr(self, 'advanced_unit_cameo_paths', {}) or {}
        missing_ids = [entry['id'] for entry in entries if entry['id'] not in cameo_paths]
        if missing_ids:
            try:
                cameo_paths.update(ensure_unit_cameos(missing_ids))
            except Exception:
                log_event(
                    'advanced_buff_cameos_failed', level=logging.ERROR,
                    traceback=traceback.format_exc(),
                )
            self.advanced_unit_cameo_paths = cameo_paths
        for index, entry in enumerate(entries):
            photo = self.advanced_pool_photo(
                f'unit:{entry["id"]}', cameo_paths.get(entry['id'])
            )
            if photo is not None:
                large_key = f'advanced:buff-large:{entry["id"]}'
                large_photo = self.advanced_pool_images.get(large_key)
                if large_photo is None:
                    large_photo = photo.zoom(6, 6).subsample(5, 5)
                    self.advanced_pool_images[large_key] = large_photo
                photo = large_photo
            self.draw_advanced_buff_unit_card(
                frame, index // 3, index % 3, entry, photo
            )
        self.refresh_advanced_buff_controls(entries)

    def refresh_advanced_buff_controls(self, entries=None):
        if not hasattr(self, 'advanced_unit_buff_vars'):
            return
        entries = entries if entries is not None else [
            entry for entry in self.advanced_buff_unit_entries()
            if self.advanced_buff_unit_is_visible(entry)
        ]
        selected = next(
            (entry for entry in entries if entry['id'] == self.advanced_buff_unit_id),
            None,
        )
        possible = set(selected['buff_types']) if selected else set()
        excluded = self.excluded_unit_buff_types.get(
            self.advanced_buff_unit_id, set()
        )
        enabled_count = len(possible - excluded)
        self.advanced_buff_unit_label.configure(
            text=(
                f'{selected["label"]}: {enabled_count}/{len(possible)} default buff types enabled. Values shown per stack.'
                if selected else 'No included buffable units in this campaign.'
            )
        )
        for buff_type in BUFF_TYPES:
            buff_id = buff_type['id']
            self.advanced_unit_buff_vars[buff_id].set(
                buff_id in possible and buff_id not in excluded
            )
            self.advanced_unit_buff_checks[buff_id].configure(
                state='normal' if buff_id in possible else 'disabled'
            )

    def select_advanced_buff_unit(self, unit_id):
        self.advanced_buff_unit_id = str(unit_id).upper()
        self.refresh_advanced_buff_view()

    def on_advanced_unit_buff_changed(self, buff_id):
        unit_id = self.advanced_buff_unit_id
        if not unit_id:
            return
        excluded = self.excluded_unit_buff_types.setdefault(unit_id, set())
        if self.advanced_unit_buff_vars[buff_id].get():
            excluded.discard(buff_id)
        else:
            excluded.add(buff_id)
        if not excluded:
            self.excluded_unit_buff_types.pop(unit_id, None)
        self.save_current_launcher_config()
        self.refresh_advanced_buff_view()

    def set_advanced_unit_buffs(self, include):
        unit_id = self.advanced_buff_unit_id
        if not unit_id:
            return
        entry = next(
            (item for item in self.advanced_buff_unit_entries() if item['id'] == unit_id),
            None,
        )
        if not entry:
            return
        if include:
            self.excluded_unit_buff_types.pop(unit_id, None)
        else:
            self.excluded_unit_buff_types[unit_id] = set(entry['buff_types'])
        self.save_current_launcher_config()
        self.refresh_advanced_buff_view()

    def advanced_power_pool_entries(self):
        entries = {}
        for reward in REWARD_POOL:
            if reward.get('kind') != 'superweapon' or not reward.get('superweapon'):
                continue
            factions = tuple(reward.get('factions') or ('Other',))
            if len(factions) != 1:
                continue
            power_id = str(reward['superweapon']).upper()
            entries.setdefault(power_id, {
                'id': power_id,
                'label': reward_display_name(reward),
                'faction': factions[0],
                'reward': reward,
            })
        faction_rank = {'Allies': 0, 'Soviets': 1, 'Epsilon': 2, 'Foehn': 3, 'Other': 4}
        return sorted(
            entries.values(),
            key=lambda entry: (
                faction_rank.get(entry['faction'], 4),
                entry['label'].casefold(),
            ),
        )

    def advanced_pool_photo(self, key, path):
        if not path:
            return None
        cache_key = f'advanced:{key}'
        if cache_key in self.advanced_pool_images:
            return self.advanced_pool_images[cache_key]
        try:
            photo = tk.PhotoImage(file=str(path))
            if photo.width() <= 70 and photo.height() <= 55:
                photo = photo.zoom(4, 4).subsample(3, 3)
            else:
                factor = max(1, (photo.width() + 87) // 88, (photo.height() + 55) // 56)
                if factor > 1:
                    photo = photo.subsample(factor, factor)
        except (OSError, tk.TclError):
            return None
        self.advanced_pool_images[cache_key] = photo
        return photo

    def draw_advanced_pool_card(self, parent, row, column, entry, pool_key, photo=None):
        excluded_sets = {
            'missions': self.excluded_mission_codes,
            'units': self.excluded_unit_access_ids,
            'powers': self.excluded_superweapon_ids,
        }
        excluded = entry['id'] in excluded_sets[pool_key]
        faction = entry.get('faction', '')
        base_color = FACTION_TILE_COLORS.get(faction, '#315b82')
        border = '#777777' if excluded else '#4d92d8'
        card = tk.Canvas(
            parent,
            width=102,
            height=90,
            highlightthickness=2,
            highlightbackground=border,
            highlightcolor=border,
            background=base_color,
            cursor='hand2',
        )
        card.grid(row=row, column=column, padx=4, pady=4, sticky='nw')
        if photo is not None:
            card.create_image(51, 31, image=photo, anchor='center')
        else:
            card.create_text(
                51, 31, text=faction or '?', fill='#ffffff',
                font=('Segoe UI', 10, 'bold'), width=94, justify='center',
            )
        card.create_rectangle(0, 62, 102, 90, fill='#151a20', outline='')
        card.create_text(
            51, 76,
            text=entry['label'],
            fill='#aeb4bb' if excluded else '#ffffff',
            font=('Segoe UI', 8, 'bold'),
            width=96,
            justify='center',
        )
        if excluded:
            card.create_rectangle(
                0, 0, 102, 90, fill='#777777', outline='', stipple='gray50'
            )
            card.create_text(
                51, 44, text='EXCLUDED', fill='#ffffff',
                font=('Segoe UI', 8, 'bold'),
            )
        card.bind(
            '<Button-1>',
            lambda _event, key=pool_key, item_id=entry['id']: (
                self.toggle_advanced_pool_entry(key, item_id)
            ),
        )
        card.bind(
            '<MouseWheel>',
            lambda event, target=self.advanced_pool_canvases[pool_key]: (
                self.on_unlock_mousewheel(event, target)
            ),
        )
        status = 'Excluded from next seeds' if excluded else 'Included in next seeds'
        WidgetTooltip(card, f'{entry["label"]} ({entry["id"]})\n{status}')

    def refresh_advanced_pool_views(self):
        if not hasattr(self, 'advanced_pool_frames'):
            return
        for frame in self.advanced_pool_frames.values():
            for child in frame.winfo_children():
                child.destroy()

        selected_campaign = self.campaign_var.get()

        def visible_for_campaign(entry):
            return (
                selected_campaign == CAMPAIGN_FILTERS[0]
                or entry.get('faction') == selected_campaign
            )

        mission_frame = self.advanced_pool_frames['missions']
        mission_icons = {}
        for faction in ('Allies', 'Soviets', 'Epsilon', 'Foehn'):
            path = GAME_ROOT / 'Resources' / f'{faction}icon.png'
            mission_icons[faction] = self.advanced_pool_photo(f'mission:{faction}', path)
        campaign_missions = [
            mission for mission in self.missions
            if selected_campaign == CAMPAIGN_FILTERS[0]
            or normalize_faction(mission.get('side', '')) == selected_campaign
        ]
        visible_missions = filter_missions_by_build_settings(
            campaign_missions,
            include_true_no_build=self.include_no_build_missions_var.get(),
            include_no_build_production=(
                self.include_no_build_production_missions_var.get()
            ),
            include_operation_missions=self.include_operation_missions_var.get(),
        )
        for index, mission in enumerate(visible_missions):
            faction = normalize_faction(mission.get('side', ''))
            self.draw_advanced_pool_card(
                mission_frame,
                index // 3,
                index % 3,
                {
                    'id': mission['code'].upper(),
                    'label': mission.get('title') or mission['code'],
                    'faction': faction,
                },
                'missions',
                mission_icons.get(faction),
            )

        all_unit_entries = self.advanced_unit_pool_entries()
        unit_entries = [
            entry for entry in all_unit_entries
            if visible_for_campaign(entry)
            and (
                self.include_special_buildings_var.get()
                or BUFF_TARGETS.get(entry['id'], {}).get('category')
                != 'special_buildings'
            )
        ]
        unit_ids = [entry['id'] for entry in all_unit_entries]
        cameo_paths = getattr(self, 'advanced_unit_cameo_paths', None)
        if cameo_paths is None:
            try:
                cameo_paths = ensure_unit_cameos(unit_ids)
            except Exception:
                cameo_paths = {}
                log_event(
                    'advanced_pool_cameos_failed',
                    level=logging.ERROR,
                    traceback=traceback.format_exc(),
                )
            self.advanced_unit_cameo_paths = cameo_paths
        unit_frame = self.advanced_pool_frames['units']
        for index, entry in enumerate(unit_entries):
            photo = self.advanced_pool_photo(
                f'unit:{entry["id"]}', cameo_paths.get(entry['id'])
            )
            self.draw_advanced_pool_card(
                unit_frame, index // 3, index % 3, entry, 'units', photo
            )

        all_power_entries = self.advanced_power_pool_entries()
        enabled_power_categories = {
            category
            for category, enabled in (
                ('offensive', self.include_superweapon_rewards_var.get()),
                ('secondary', self.include_secondary_superweapon_rewards_var.get()),
                ('aid', self.include_aid_power_rewards_var.get()),
            )
            if enabled
        }
        power_entries = [
            entry for entry in all_power_entries
            if visible_for_campaign(entry)
            and entry['reward'].get('power_category', 'offensive')
            in enabled_power_categories
        ]
        normal_power_ids = [
            entry['reward'].get('cameo_superweapon', entry['id'])
            for entry in power_entries
            if not entry['reward'].get('superweapon_sidebar_image')
        ]
        try:
            power_paths = ensure_superweapon_cameos(normal_power_ids)
        except Exception:
            power_paths = {}
            log_event(
                'advanced_pool_power_cameos_failed',
                level=logging.ERROR,
                traceback=traceback.format_exc(),
            )
        power_frame = self.advanced_pool_frames['powers']
        for index, entry in enumerate(power_entries):
            reward = entry['reward']
            asset_name = reward.get('superweapon_sidebar_image')
            if asset_name:
                try:
                    path = custom_sidebar_preview(asset_name)
                except Exception:
                    path = None
            else:
                path = power_paths.get(
                    str(reward.get('cameo_superweapon', entry['id'])).upper()
                )
            photo = self.advanced_pool_photo(f'power:{entry["id"]}', path)
            self.draw_advanced_pool_card(
                power_frame, index // 3, index % 3, entry, 'powers', photo
            )

        self.refresh_advanced_buff_view()

        included_missions = len(visible_missions) - len(
            {mission['code'].upper() for mission in visible_missions}
            & self.excluded_mission_codes
        )
        visible_unit_ids = {entry['id'] for entry in unit_entries}
        included_units = len(visible_unit_ids - self.excluded_unit_access_ids)
        visible_power_ids = {entry['id'] for entry in power_entries}
        included_powers = len(visible_power_ids - self.excluded_superweapon_ids)
        self.advanced_pool_status_label.configure(
            text=(
                f'{selected_campaign}: missions {included_missions}/{len(visible_missions)}, '
                f'units/buildings {included_units}/{len(visible_unit_ids)}, '
                f'superpowers {included_powers}/{len(visible_power_ids)} included'
            )
        )

    def toggle_advanced_pool_entry(self, pool_key, item_id):
        target = {
            'missions': self.excluded_mission_codes,
            'units': self.excluded_unit_access_ids,
            'powers': self.excluded_superweapon_ids,
        }[pool_key]
        item_id = str(item_id).upper()
        if item_id in target:
            target.remove(item_id)
        else:
            target.add(item_id)
        self.save_current_launcher_config()
        self.update_mission_goal_limit()
        self.refresh_advanced_pool_views()

    def set_advanced_pool_all(self, pool_key, include):
        selected_campaign = self.campaign_var.get()
        if pool_key == 'missions':
            mission_entries = [
                {'id': mission['code'].upper(), 'faction': normalize_faction(mission.get('side', ''))}
                for mission in filter_missions_by_build_settings(
                    self.missions,
                    include_true_no_build=self.include_no_build_missions_var.get(),
                    include_no_build_production=(
                        self.include_no_build_production_missions_var.get()
                    ),
                    include_operation_missions=self.include_operation_missions_var.get(),
                )
            ]
            entries = mission_entries
            target = self.excluded_mission_codes
        elif pool_key == 'units':
            entries = [
                entry for entry in self.advanced_unit_pool_entries()
                if self.include_special_buildings_var.get()
                or BUFF_TARGETS.get(entry['id'], {}).get('category')
                != 'special_buildings'
            ]
            target = self.excluded_unit_access_ids
        else:
            enabled_categories = {
                category
                for category, enabled in (
                    ('offensive', self.include_superweapon_rewards_var.get()),
                    ('secondary', self.include_secondary_superweapon_rewards_var.get()),
                    ('aid', self.include_aid_power_rewards_var.get()),
                )
                if enabled
            }
            entries = [
                entry for entry in self.advanced_power_pool_entries()
                if entry['reward'].get('power_category', 'offensive')
                in enabled_categories
            ]
            target = self.excluded_superweapon_ids
        all_ids = {
            entry['id'] for entry in entries
            if selected_campaign == CAMPAIGN_FILTERS[0]
            or entry.get('faction') == selected_campaign
        }
        if include:
            target.difference_update(all_ids)
        else:
            target.update(all_ids)
        self.save_current_launcher_config()
        self.update_mission_goal_limit()
        self.refresh_advanced_pool_views()

    def on_campaign_filter_changed(self, event=None):
        self.update_mission_goal_limit()
        self.refresh_advanced_pool_views()

    def on_mission_pool_settings_changed(self):
        self.refresh_setting_states()
        self.update_mission_goal_limit()

    def on_reward_mode_changed(self, event=None):
        self.refresh_setting_states()

    def on_unlimited_hero_units_changed(self):
        if self.unlimited_hero_units_var.get():
            self.buff_type_vars['build_limit'].set(False)
        self.refresh_setting_states()

    def on_hero_limit_buff_changed(self):
        if self.buff_type_vars['build_limit'].get():
            self.unlimited_hero_units_var.set(False)
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
        special_buildings_enabled = bool(self.include_special_buildings_var.get())
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
                state='normal' if buffs_enabled and not unlimited_hero_units else 'disabled'
            )
        building_limit_check = getattr(
            self, 'buff_type_checks_by_id', {}
        ).get('building_limit')
        if building_limit_check is not None:
            building_limit_check.configure(
                state=(
                    'normal'
                    if buffs_enabled and special_buildings_enabled
                    else 'disabled'
                )
            )
        self.include_defensive_buildings_check.configure(
            state='normal' if reward_source_enabled else 'disabled'
        )
        self.include_special_buildings_check.configure(
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
        self.refresh_advanced_pool_views()

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
        redraw_launcher_grid(self)

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
            if self.hide_locked_grid_missions_var.get() and state == GRID_LOCKED:
                widgets['tile'].grid()
                background, foreground = '#3f454b', '#d4d8dc'
                for widget in widgets.values():
                    widget.configure(cursor='arrow')
                widgets['tile'].configure(
                    background=background,
                    highlightbackground=self.ui_palette()['canvas'],
                )
                widgets['selection'].configure(background=background)
                widgets['banner'].grid_remove()
                widgets['body'].grid_configure(pady=4)
                widgets['body'].configure(
                    text='?',
                    background=background,
                    foreground=foreground,
                )
                continue
            widgets['tile'].grid()
            for widget in widgets.values():
                widget.configure(cursor='hand2')
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
            hover_highlight = code in getattr(self, 'unlock_hover_grid_codes', set())
            widgets['tile'].configure(
                background='#d6ad37' if is_goal else background,
                highlightbackground=(
                    '#45ef7a'
                    if hover_highlight
                    else self.ui_palette()['canvas']
                ),
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
        if self.hide_locked_grid_missions_var.get() and self.state:
            try:
                code = self.missions[index]['code']
            except (IndexError, TypeError):
                return
            if self.sync_grid_progression().get(code) == GRID_LOCKED:
                return
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
            tags = []
            if self.is_mission_complete(code):
                tags.append('completed')
            if code in getattr(self, 'unlock_hover_grid_codes', set()):
                tags.append('unlock_available')
            self.missions_tree.insert(
                '',
                'end',
                iid=str(idx),
                values=(f'{order:03}', state, checks_label, side, code, title),
                tags=tuple(tags),
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
                reward_name = self.mission_check_reward_name(check, reward)
                lines.append(f'    • {reward_name}')
        return '\n'.join(lines)

    def mission_check_reward_name(self, check, reward):
        if (
            self.hide_reward_details_var.get()
            and not check.get('unlocked')
            and not check.get('released')
        ):
            return '?????'
        return reward_display_name(reward)

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
        starting_defense_ids = self.starting_tier_one_defense_ids_for_seed(
            reward_settings
        )
        self._starting_unit_ids_override = starting_unit_ids
        self._starting_defense_ids_override = starting_defense_ids
        options = {
            **generation_context,
            'seed': seed,
            'seed_missions': list(seed_missions),
            'mission_goal': mission_goal,
            'rewards_per_check': rewards_per_check,
            'reward_settings': reward_settings,
            'starting_defense_ids': starting_defense_ids,
            'starting_unit_ids': starting_unit_ids,
            'progression_mode': self.progression_mode_var.get(),
            'two_start_positions': bool(self.grid_two_starts_var.get()),
            'mission_pool_settings': {
                'include_no_build_missions': bool(self.include_no_build_missions_var.get()),
                'include_no_build_production_missions': bool(
                    self.include_no_build_production_missions_var.get()
                ),
                'include_operation_missions': bool(
                    self.include_operation_missions_var.get()
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
        starting_defense_ids = options['starting_defense_ids']
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
            'starting_defense_ids': starting_defense_ids,
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
            'starting_defense_ids': starting_defense_ids,
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
        self._starting_defense_ids_override = None
        self._starting_unit_ids_override = None
        self._seed_generation_context = None
        seed = result['seed']
        mission_goal = result['mission_goal']
        rewards_per_check = result['rewards_per_check']
        starting_defense_ids = result['starting_defense_ids']
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
                + ', '.join(
                    tier_one_role_label(unit_id) or unit_display_label(unit_id)
                    for unit_id in starting_unit_ids
                )
                + '.'
            )
        if starting_defense_ids:
            self.append_log(
                'Starting Tier 1 defenses: '
                + ', '.join(
                    unit_display_label(unit_id)
                    for unit_id in self.display_starting_tier_one_defense_ids()
                )
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
            starting_defense_ids=starting_defense_ids,
            starting_unit_ids=starting_unit_ids,
        )

    def handle_seed_generation_error(self, exc, detail):
        self._reward_settings_override = None
        self._starting_defense_ids_override = None
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
        missions = [
            mission for mission in missions
            if mission.get('code', '').upper() not in self.excluded_mission_codes
        ]
        return filter_missions_by_build_settings(
            missions,
            include_true_no_build=self.include_no_build_missions_var.get(),
            include_no_build_production=(
                self.include_no_build_production_missions_var.get()
            ),
            include_operation_missions=self.include_operation_missions_var.get(),
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
            return REWARDS_PER_CHECK_MAXIMUM_MESSAGE
        for threshold, message in REWARDS_PER_CHECK_MESSAGE_THRESHOLDS:
            if value >= threshold:
                return message
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
        starting_defense_ids = self.active_starting_tier_one_defense_ids()
        starting_unit_ids = self.active_starting_tier_one_unit_ids()
        production_houses = mission_player_production_houses(
            mission.get('code')
        )
        mission_required_rules = MISSION_REQUIRED_ACCESS_RULES.get(
            str(mission.get('code') or '').upper(),
            {},
        )
        mission_code = str(mission.get('code') or '').upper()

        def merge_required_rules(rules):
            if mission_code in MISSIONS_WITH_ALL_CONYARD_DEFENSE_ACCESS:
                # Juggernaut eventually hands the player an SMCV. Expose every
                # earned defense through any construction yard, including
                # cross-faction Chaos rewards; do not reduce this to the two
                # native Action 106 defenses.
                earned_defense_rewards = [
                    reward
                    for reward in self.active_launch_rewards()
                    if reward.get('kind') not in {'buff', 'superweapon'}
                    and any(
                        BUFF_TARGETS.get(str(tech_id).upper(), {}).get('category')
                        == 'defenses'
                        for tech_id in reward.get('rules', {})
                    )
                ]
                defense_rules = chaos_earned_access_rules(
                    lines,
                    earned_defense_rewards,
                    additional_build_houses=(),
                    additional_production_houses=production_houses,
                )
                for section, values in defense_rules.items():
                    rules.setdefault(section, {}).update(values)
            for section, values in mission_required_rules.items():
                rules.setdefault(section, {}).update(values)
            return rules

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
                excluded_unit_ids=self.active_reward_settings().get(
                    'excluded_unit_access_ids', []
                ),
            )
            for section, values in starter_rules.items():
                rules.setdefault(section, {}).update(values)
            starter_defense_rules = starting_tier_one_defense_rules(
                lines,
                starting_defense_ids,
                chaos_mode=True,
                additional_build_houses=(),
                additional_production_houses=production_houses,
                excluded_unit_ids=self.active_reward_settings().get(
                    'excluded_unit_access_ids', []
                ),
            )
            for section, values in starter_defense_rules.items():
                rules.setdefault(section, {}).update(values)
            return merge_required_rules(rules)
        selected_campaign = self.state.get('campaign_filter', '') if self.state else ''
        translate_equivalents = selected_campaign in {
            'Allies', 'Soviets', 'Epsilon', 'Foehn'
        }
        earned_access_ids = (
            self.active_unlocked_reward_tech_ids()
            if self.randomize_unit_access_enabled()
            else controlled_tech_ids()
        )
        earned_access_ids.update(self.active_starting_tier_one_expanded_ids())
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
        standard_starter_families = STANDARD_STARTER_FAMILIES_BY_CAMPAIGN.get(
            selected_campaign, ()
        )
        starter_rules = starting_tier_one_rules(
            lines,
            starting_unit_ids,
            standard_families=standard_starter_families,
            additional_build_houses=(),
            additional_production_houses=production_houses,
            excluded_unit_ids=self.active_reward_settings().get(
                'excluded_unit_access_ids', []
            ),
        )
        for section, values in starter_rules.items():
            rules.setdefault(section, {}).update(values)
        starter_defense_rules = starting_tier_one_defense_rules(
            lines,
            starting_defense_ids,
            standard_families=standard_starter_families,
            additional_build_houses=(),
            additional_production_houses=production_houses,
            excluded_unit_ids=self.active_reward_settings().get(
                'excluded_unit_access_ids', []
            ),
        )
        for section, values in starter_defense_rules.items():
            rules.setdefault(section, {}).update(values)
        return merge_required_rules(rules)

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
        include_special_buildings = bool(
            self.active_reward_settings().get('include_special_buildings', True)
        )
        return {
            section.upper()
            for section in controlled_tech_ids()
            if (
                include_defenses
                or BUFF_TARGETS.get(section.upper(), {}).get('category') != 'defenses'
            )
            and (
                include_special_buildings
                or BUFF_TARGETS.get(section.upper(), {}).get('category')
                != 'special_buildings'
            )
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
        return prepare_hooked_mission_map(self, mission, extra_rules=extra_rules)

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

    def build_unlock_display_groups(self, earned):
        """Group canonical earned rewards for Unlocks text rendering."""
        groups = {}
        shared_groups = {}
        share_chaos_role_buffs = self.share_chaos_role_buffs_enabled()
        share_foehn_roles = self.foehn_standard_bundles_enabled()

        def group_for(tech_id):
            return groups.setdefault(tech_id, {
                'label': self.reward_group_label(tech_id),
                'access': {},
                'buffs': {},
                'other': [],
            })

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

        return groups, shared_groups

    def current_unlocks_text(self):
        if not self.state:
            return 'No randomizer seed generated yet.'

        lines = []
        starting_unit_ids = self.display_starting_tier_one_unit_ids()
        if starting_unit_ids:
            heading = 'Starting Tier 1 Units'
            lines.extend([heading, '=' * len(heading)])
            for unit_id in sorted(set(starting_unit_ids), key=self.unit_faction_sort_key):
                lines.append(unit_display_label(unit_id))
            lines.append('')
        starting_defense_ids = self.display_starting_tier_one_defense_ids()
        if starting_defense_ids:
            heading = 'Starting Tier 1 Defenses'
            lines.extend([heading, '=' * len(heading)])
            for unit_id in starting_defense_ids:
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

        earned = []
        for reward in self.earned_rewards_from_checks():
            canonical = canonical_reward(reward)
            if (
                not canonical.get('retired_reward')
                and not self.standard_foehn_unit_reward(canonical)
            ):
                earned.append(canonical)
        if not earned:
            if lines:
                return '\n'.join(lines).rstrip()
            return 'No unlocks or buffs earned yet.'

        share_chaos_role_buffs = self.share_chaos_role_buffs_enabled()
        share_foehn_roles = self.foehn_standard_bundles_enabled()
        groups, shared_groups = self.build_unlock_display_groups(earned)

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
        def summary_section(unit_id):
            if BUFF_TARGETS.get(unit_id, {}).get('category') == 'special_buildings':
                return 'Special Buildings'
            return self.unit_faction(unit_id)

        for tech_id in sorted(
            groups,
            key=lambda unit_id: (
                summary_section(unit_id) == 'Special Buildings',
                self.unit_faction_sort_key(unit_id),
            ),
        ):
            group = groups[tech_id]
            faction = summary_section(tech_id)
            if faction != current_faction:
                if lines and lines[-1] != '':
                    lines.append('')
                heading = (
                    faction
                    if faction == 'Special Buildings'
                    else
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
                power_token = reward_cameo_token(reward)
                lines.append(f'{power_token}Reward: {reward_display_name(reward)}')
                for summary in reward_rule_summary(reward):
                    lines.append(f'  {summary}')

            lines.append('')

        return '\n'.join(lines).rstrip()

    def current_unlock_unit_ids(self):
        if not self.state:
            return []
        unit_ids = set(self.display_starting_tier_one_unit_ids())
        unit_ids.update(self.display_starting_tier_one_defense_ids())
        share_chaos_role_buffs = self.share_chaos_role_buffs_enabled()
        share_foehn_roles = self.foehn_standard_bundles_enabled()
        for reward in self.earned_rewards_from_checks():
            reward = canonical_reward(reward)
            if self.standard_foehn_unit_reward(reward):
                continue
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

    def display_starting_tier_one_unit_ids(self):
        """Return concrete starter variants represented by saved role markers."""
        unit_ids = self.active_starting_tier_one_expanded_ids()
        if self.active_reward_mode() != 'Chaos (Experimental)':
            unit_ids = {
                unit_id
                for unit_id in unit_ids
                if self.unit_faction(unit_id) != 'Foehn'
            }
        return sorted(unit_ids, key=self.unit_faction_sort_key)

    def display_starting_tier_one_defense_ids(self):
        return sorted(
            self.active_starting_tier_one_defense_expanded_ids(),
            key=self.unit_faction_sort_key,
        )

    def unlock_dashboard_reward_keys(self, reward):
        """Return catalogue icons affected by one serialized reward."""
        reward = canonical_reward(reward)
        keys = set()
        unit_id = str(reward.get('unit') or '').upper()
        if reward.get('kind') == 'buff' and unit_id and unit_id != 'MOR_BUILDINGS':
            keys.add(f'unit:{unit_id}')
            if (
                not reward.get('global_buff')
                and (self.share_chaos_role_buffs_enabled() or self.foehn_standard_bundles_enabled())
            ):
                equivalents = unit_role_equivalents(unit_id)
                if self.foehn_standard_bundles_enabled():
                    equivalents = {
                        equivalent
                        for equivalent in equivalents
                        if self.unit_faction(equivalent) in {'Allies', 'Soviets'}
                    }
                keys.update(f'unit:{equivalent}' for equivalent in equivalents)
        for tech_id in tech_ids_for_rewards([reward]):
            if tech_id in BUFF_TARGETS and tech_id != 'MOR_BUILDINGS':
                keys.add(f'unit:{tech_id}')
            elif reward.get('access_category') == 'special_building':
                keys.add(f'unit:{tech_id}')
        if reward.get('kind') == 'superweapon' and reward.get('superweapon'):
            keys.add(f'power:{reward["superweapon"]}')
        return keys

    def unlock_dashboard_sources(self):
        """Index assigned, earned, and presently playable rewards by icon."""
        indexed = {}
        if not self.state:
            return indexed
        playable = {
            code
            for code in self.unlocked_mission_codes()
            if not self.is_mission_complete(code)
        }
        mission_lookup = self.mission_lookup()
        for code in self.state.get('mission_order', []):
            mission_title = mission_lookup.get(code, {}).get('title', code)
            for check in self.mission_checks(code):
                earned = bool(check.get('unlocked') or check.get('released'))
                source = f'{mission_title} — {check.get("name", "Check")}'
                for reward in check_rewards(check):
                    reward = canonical_reward(reward)
                    if reward.get('retired_reward'):
                        continue
                    for key in self.unlock_dashboard_reward_keys(reward):
                        entry = indexed.setdefault(
                            key,
                            {
                                'assigned': [],
                                'earned': [],
                                'available': [],
                                'available_unlocks': [],
                                'available_codes': [],
                            },
                        )
                        item = (source, reward)
                        entry['assigned'].append(item)
                        if earned:
                            entry['earned'].append(item)
                        elif code in playable:
                            entry['available'].append(item)
                            if reward.get('kind') != 'buff':
                                entry['available_unlocks'].append(item)
                                if code not in entry['available_codes']:
                                    entry['available_codes'].append(code)
        return indexed

    def unlock_dashboard_entries(self):
        """Build privacy-aware icon states without changing seed data."""
        sources = self.unlock_dashboard_sources()
        privacy = bool(
            self.state
            and self.active_progression_mode() == 'Grid Mode'
            and self.hide_locked_grid_missions_var.get()
        )
        earned_rewards = [
            canonical_reward(reward)
            for reward in (self.earned_rewards_from_checks() if self.state else [])
        ]
        # Buff rules can contain TechLevel for clone construction but do not
        # grant access. Only non-buff rewards may make a card "unlocked".
        earned_access = unlocked_reward_tech_ids(earned_rewards)
        starting_access = self.active_starting_tier_one_access_ids()
        randomize_access = self.randomize_unit_access_enabled()
        foehn_units_available = self.active_reward_mode() == 'Chaos (Experimental)'

        entries = []
        category_labels = {
            'infantry': 'Infantry',
            'units': 'Vehicles / Naval',
            'aircraft': 'Aircraft',
            'defenses': 'Defenses',
        }
        for unit_id, target in BUFF_TARGETS.items():
            if target.get('linked_buff_source'):
                continue
            category = target.get('category')
            if category not in category_labels:
                continue
            factions = list(target.get('factions') or [])
            if len(factions) != 1 or factions[0] not in FACTION_ORDER:
                continue
            key = f'unit:{unit_id}'
            source_data = sources.get(
                key, {
                    'assigned': [], 'earned': [], 'available': [],
                    'available_unlocks': [], 'available_codes': [],
                }
            )
            if factions[0] == 'Foehn' and not foehn_units_available:
                source_data = {
                    'assigned': [], 'earned': [], 'available': [],
                    'available_unlocks': [], 'available_codes': [],
                }
            unlocked = bool(
                (factions[0] != 'Foehn' or foehn_units_available)
                and (
                    not randomize_access
                    or unit_id in ALWAYS_AVAILABLE_TECH_IDS
                    or unit_id in starting_access
                    or unit_id in earned_access
                    or any(
                        reward.get('kind') != 'buff'
                        for _source, reward in source_data['earned']
                    )
                )
            )
            status = (
                'unlocked'
                if unlocked
                else 'available'
                if source_data['available_unlocks'] and not privacy
                else 'locked'
                if source_data['assigned']
                else 'unavailable'
            )
            if unit_id in starting_access:
                condition = 'Pre-generation settings'
            elif unit_id in ALWAYS_AVAILABLE_TECH_IDS or not randomize_access:
                condition = 'Pre-generation settings'
            else:
                condition = ''
            entries.append({
                'key': key,
                'kind': 'unit',
                'id': unit_id,
                'label': target.get('label', unit_id),
                'faction': factions[0],
                'category': category_labels[category],
                'status': status,
                'condition': condition,
                'sources': source_data,
                'privacy': privacy,
            })

        special_rewards = {
            next(iter(tech_ids_for_rewards([reward])), ''): reward
            for reward in REWARD_POOL
            if reward.get('access_category') == 'special_building'
        }
        for definition in SPECIAL_BUILDING_DEFINITIONS:
            building_id = str(definition['id']).upper()
            faction = str(definition['faction'])
            reward = special_rewards.get(building_id)
            if not reward or faction not in FACTION_ORDER:
                continue
            key = f'unit:{building_id}'
            source_data = sources.get(
                key, {
                    'assigned': [], 'earned': [], 'available': [],
                    'available_unlocks': [], 'available_codes': [],
                }
            )
            status = (
                'unlocked'
                if building_id in earned_access
                else 'available'
                if source_data['available_unlocks'] and not privacy
                else 'locked'
                if source_data['assigned']
                else 'unavailable'
            )
            entries.append({
                'key': key,
                'kind': 'unit',
                'id': building_id,
                'label': str(definition['name']),
                'faction': faction,
                'category': 'Special Buildings',
                'status': status,
                'condition': '',
                'sources': source_data,
                'privacy': privacy,
                'reward': reward,
            })

        seen_powers = set()
        for reward in REWARD_POOL:
            if reward.get('kind') != 'superweapon' or not reward.get('superweapon'):
                continue
            reward = canonical_reward(reward)
            power_id = reward['superweapon']
            if power_id in seen_powers:
                continue
            factions = list(reward.get('factions') or [])
            if len(factions) != 1 or factions[0] not in FACTION_ORDER:
                continue
            seen_powers.add(power_id)
            key = f'power:{power_id}'
            source_data = sources.get(
                key, {
                    'assigned': [], 'earned': [], 'available': [],
                    'available_unlocks': [], 'available_codes': [],
                }
            )
            status = (
                'unlocked'
                if source_data['earned']
                else 'available'
                if source_data['available_unlocks'] and not privacy
                else 'locked'
                if source_data['assigned']
                else 'unavailable'
            )
            entries.append({
                'key': key,
                'kind': 'power',
                'id': power_id,
                'label': reward_display_name(reward),
                'faction': factions[0],
                'category': 'Superweapons',
                'status': status,
                'condition': '',
                'sources': source_data,
                'privacy': privacy,
                'reward': reward,
            })
        return entries

    def unlock_dashboard_tooltip(self, entry):
        status_labels = {
            'unlocked': 'Unlocked',
            'available': 'Available now',
            'locked': 'Locked',
            'unavailable': 'Unavailable in this seed',
        }
        lines = [
            f'{entry["label"]} — {status_labels[entry["status"]]}',
            '─' * min(48, max(12, len(entry['label']) + 12)),
        ]
        sources = entry['sources']
        earned_source_names = list(dict.fromkeys(source for source, _ in sources['earned']))
        available_source_names = list(dict.fromkeys(
            source for source, _ in sources['available_unlocks']
        ))

        def compact_sources(names):
            visible = names[:3]
            text = '; '.join(visible)
            if len(names) > len(visible):
                text += f'; +{len(names) - len(visible)} more'
            return text

        if entry.get('condition'):
            lines.append(f'Condition: {entry["condition"]}')
        if earned_source_names:
            lines.append('Earned from: ' + compact_sources(earned_source_names))
        if entry['status'] == 'available' and available_source_names:
            lines.append('Available from: ' + compact_sources(available_source_names))
        elif entry['status'] == 'locked':
            lines.append(
                'Assigned later in this seed.'
                if not entry['privacy']
                else 'Access not currently available.'
            )
        elif entry['status'] == 'unavailable':
            lines.append('Not assigned by this seed and current reward settings.')

        earned = [reward for _, reward in sources['earned']]
        buffs = {}
        for reward in earned:
            if reward.get('kind') == 'buff':
                key = reward.get('buff_type')
                display_reward = dict(reward)
                if entry.get('kind') == 'unit':
                    display_reward['unit'] = entry['id']
                buffs.setdefault(
                    key, {'reward': display_reward, 'count': 0}
                )['count'] += 1
        effect_lines = []
        for buff in buffs.values():
            effect_lines.extend(buff_effect_lines(
                buff['reward'], count=buff['count'], include_label=False
            ))
        if (
            entry.get('reward')
            and entry['status'] == 'unlocked'
            and entry['reward'].get('access_category') != 'special_building'
        ):
            effect_lines.extend(reward_rule_summary(entry['reward']))
        if effect_lines:
            lines.extend(['', 'Current effects:'])
            lines.extend(f'• {line}' for line in effect_lines)

        if entry['status'] == 'available':
            potential = []
            for _source, reward in sources['available_unlocks']:
                if reward.get('kind') == 'buff':
                    potential.extend(buff_effect_lines(
                        reward, include_label=False, include_stack=False
                    ))
                else:
                    potential.append(reward_display_name(reward))
            if potential:
                lines.extend(['', 'Potential reward:'])
                lines.extend(f'• {line}' for line in dict.fromkeys(potential))
        return '\n'.join(lines)

    def schedule_cameo_refresh_retry(self):
        """Redraw image consumers after asynchronous MIX extraction finishes."""
        if self.cameo_retry_after_id is not None or self.cameo_retry_count >= 20:
            return
        self.cameo_retry_count += 1

        def retry():
            self.cameo_retry_after_id = None
            if not self.winfo_exists():
                return
            self.advanced_unit_cameo_paths = None
            self.unlock_dashboard_signature = None
            self.unlock_dashboard_structure_signature = None
            self.refresh_advanced_pool_views()
            self.refresh_progress_view()

        self.cameo_retry_after_id = self.after(1000, retry)

    def refresh_unlock_dashboard(self):
        if not hasattr(self, 'unlock_icon_frames'):
            return
        entries = self.unlock_dashboard_entries()
        signature = (
            bool(self.dark_mode_var.get()),
            tuple(
                (
                    entry['key'], entry['status'], entry['condition'], entry['privacy'],
                    tuple(source for source, _ in entry['sources']['earned']),
                    tuple(source for source, _ in entry['sources']['available']),
                    tuple(source for source, _ in entry['sources']['available_unlocks']),
                    tuple(entry['sources']['available_codes']),
                )
                for entry in entries
            ),
        )
        if signature == getattr(self, 'unlock_dashboard_signature', None):
            return
        self.unlock_dashboard_signature = signature
        hovered_key = getattr(self, 'unlock_hover_card_key', None)
        hovered_entry = next(
            (entry for entry in entries if entry['key'] == hovered_key),
            None,
        )
        if hovered_entry is not None:
            hovered_codes = (
                hovered_entry['sources'].get('available_codes', ())
                if hovered_entry.get('status') == 'available'
                and not hovered_entry.get('privacy')
                else ()
            )
            self.set_unlock_grid_highlights(hovered_codes)
        elif hovered_key is not None:
            self.unlock_hover_card_key = None
            self.set_unlock_grid_highlights(())

        overlays = {
            'unlocked': (None, '#4f86c6'),
            'available': ('#15a34a', '#40d36d'),
            'locked': ('#6b7280', '#858b95'),
            'unavailable': ('#050505', '#343434'),
        }
        structure_signature = (
            bool(self.dark_mode_var.get()),
            tuple(
                (
                    entry['key'], entry['faction'], entry['category'],
                    entry['label'], entry['kind'], entry['id'],
                    str((entry.get('reward') or {}).get('superweapon_sidebar_image', '')),
                )
                for entry in entries
            ),
        )
        cards = getattr(self, 'unlock_dashboard_cards', {})
        if (
            structure_signature == getattr(self, 'unlock_dashboard_structure_signature', None)
            and set(cards) == {entry['key'] for entry in entries}
        ):
            # Completion changes statuses and tooltips, not catalogue layout.
            # Updating four canvas rectangles is dramatically cheaper than
            # destroying/recreating hundreds of widgets and reloading cameos.
            for entry in entries:
                record = cards[entry['key']]
                card = record['card']
                card.unlock_entry = entry
                record['tooltip'].text = self.unlock_dashboard_tooltip(entry)
                fill, outline = overlays[entry['status']]
                card.itemconfigure(
                    record['overlay'],
                    fill=fill or '',
                    outline=outline,
                    stipple=(
                        'gray75'
                        if entry['status'] == 'unavailable'
                        else 'gray50'
                        if fill else ''
                    ),
                )
            return

        self.unlock_dashboard_structure_signature = structure_signature

        unit_ids = [entry['id'] for entry in entries if entry['kind'] == 'unit']
        power_entries = [entry for entry in entries if entry['kind'] == 'power']
        try:
            unit_paths = ensure_unit_cameos(unit_ids)
        except Exception:
            unit_paths = {}
            log_event('unlock_dashboard_unit_cameos_failed', level=logging.ERROR,
                      traceback=traceback.format_exc())
        normal_power_ids = [
            entry['reward'].get('cameo_superweapon', entry['id'])
            for entry in power_entries
            if not entry['reward'].get('superweapon_sidebar_image')
        ]
        try:
            power_paths = ensure_superweapon_cameos(normal_power_ids)
        except Exception:
            power_paths = {}
            log_event('unlock_dashboard_power_cameos_failed', level=logging.ERROR,
                      traceback=traceback.format_exc())

        photos = {}
        for entry in entries:
            cache_key = entry['id'] if entry['kind'] == 'unit' else entry['key']
            photo = self.cameo_photo_cache.get(cache_key)
            path = None
            if entry['kind'] == 'unit':
                path = unit_paths.get(entry['id'])
            else:
                asset_name = entry['reward'].get('superweapon_sidebar_image')
                if asset_name:
                    try:
                        path = custom_sidebar_preview(asset_name)
                    except Exception:
                        path = None
                else:
                    cameo_id = entry['reward'].get('cameo_superweapon', entry['id'])
                    path = power_paths.get(str(cameo_id).upper())
            if photo is None and path:
                try:
                    photo = tk.PhotoImage(file=str(path))
                except tk.TclError:
                    photo = None
                if photo is not None:
                    self.cameo_photo_cache[cache_key] = photo
            if photo is not None:
                scale_key = f'dashboard-scale:{cache_key}'
                scaled_photo = self.cameo_photo_cache.get(scale_key)
                if scaled_photo is None:
                    scaled_photo = photo.zoom(4, 4).subsample(3, 3)
                    self.cameo_photo_cache[scale_key] = scaled_photo
                photos[entry['key']] = scaled_photo
        self.unlock_dashboard_images = photos

        field = '#20242b' if self.dark_mode_var.get() else '#ffffff'
        foreground = '#f2f4f8' if self.dark_mode_var.get() else '#202124'
        order = {'Infantry': 0, 'Vehicles / Naval': 1, 'Aircraft': 2,
                 'Defenses': 3, 'Special Buildings': 4, 'Superweapons': 5}
        self.unlock_dashboard_sections = {}
        self.unlock_dashboard_columns = {}
        self.unlock_dashboard_cards = {}
        for faction, content in self.unlock_icon_frames.items():
            canvas = self.unlock_icon_canvases[faction]
            for child in content.winfo_children():
                child.destroy()
            faction_entries = sorted(
                (entry for entry in entries if entry['faction'] == faction),
                key=lambda entry: (order[entry['category']], entry['label'].casefold()),
            )
            row = 0
            layout_sections = []
            for category in sorted(
                {entry['category'] for entry in faction_entries}, key=order.get
            ):
                heading = ttk.Label(
                    content, text=category, font=('Segoe UI', 11, 'bold')
                )
                heading.grid(row=row, column=0, columnspan=4, sticky='w', pady=(8, 4))
                row += 1
                category_entries = [
                    entry for entry in faction_entries if entry['category'] == category
                ]
                cards = []
                for index, entry in enumerate(category_entries):
                    card_row = row + index // 4
                    card_column = index % 4
                    card = tk.Canvas(
                        content, width=82, height=68, borderwidth=0,
                        highlightthickness=0, background=field, cursor='hand2',
                    )
                    card.grid(row=card_row, column=card_column, padx=1, pady=2)
                    cards.append(card)
                    photo = photos.get(entry['key'])
                    if photo is not None:
                        card.create_image(41, 34, image=photo, anchor='center')
                    else:
                        card.create_text(
                            41, 34, text=entry['label'], fill=foreground,
                            width=76, font=('Segoe UI', 9), justify='center',
                        )
                    fill, outline = overlays[entry['status']]
                    if fill:
                        overlay_id = card.create_rectangle(
                            1, 1, 81, 67, fill=fill,
                            stipple='gray50' if entry['status'] != 'unavailable' else 'gray75',
                            outline=outline, width=2,
                        )
                    else:
                        overlay_id = card.create_rectangle(
                            1, 1, 81, 67, outline=outline, width=2
                        )
                    card.unlock_entry = entry
                    card.bind(
                        '<Enter>',
                        lambda _event, target=card: self.on_unlock_card_enter(target),
                        add='+',
                    )
                    card.bind(
                        '<Leave>',
                        lambda _event, target=card: self.on_unlock_card_leave(target),
                        add='+',
                    )
                    card.bind(
                        '<MouseWheel>',
                        lambda event, target=canvas: self.on_unlock_mousewheel(
                            event, target
                        ),
                    )
                    tooltip = WidgetTooltip(card, self.unlock_dashboard_tooltip(entry))
                    self.unlock_dashboard_cards[entry['key']] = {
                        'card': card,
                        'overlay': overlay_id,
                        'tooltip': tooltip,
                    }
                row += (len(category_entries) + 3) // 4
                layout_sections.append((heading, cards))
            self.unlock_dashboard_sections[faction] = layout_sections
            self.layout_unlock_dashboard_faction(faction)
            content.update_idletasks()
            canvas.configure(background=field, scrollregion=canvas.bbox('all'))

        if entries and len(photos) < len(entries) and cameo_extraction_pending():
            self.schedule_cameo_refresh_retry()
        else:
            self.cameo_retry_count = 0

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
                    if self.hide_locked_grid_missions_var.get():
                        lines.append(
                            f'Completing this node reveals {len(unlocks)} neighboring mission(s).'
                        )
                    else:
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
                        reward_name = self.mission_check_reward_name(check, reward)
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
        asset_names = sorted(set(re.findall(
            r'\[\[MOR_ASSET:([A-Za-z0-9_.-]+\.png)\]\]',
            text,
            flags=re.IGNORECASE,
        )))
        for asset_name in asset_names:
            token = f'[[MOR_ASSET:{asset_name}]]'
            try:
                preview_path = custom_sidebar_preview(asset_name)
            except Exception:
                preview_path = None
                log_event(
                    'custom_sidebar_preview_failed',
                    level=logging.ERROR,
                    asset=asset_name,
                    traceback=traceback.format_exc(),
                )
            position = self.unlocks_text.search(token, '1.0', stopindex='end', exact=True)
            while position:
                self.unlocks_text.delete(position, f'{position}+{len(token)}c')
                cache_key = f'asset:{asset_name.lower()}'
                photo = self.cameo_photo_cache.get(cache_key)
                if photo is None and preview_path:
                    try:
                        photo = tk.PhotoImage(file=str(preview_path))
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
        self.refresh_unlock_dashboard()


def main():
    app = LauncherApp()
    app.mainloop()
