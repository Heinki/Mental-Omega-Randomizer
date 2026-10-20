"""Challenge selection, supported launch modes, and native result tracking."""

import copy
import re
from tkinter import messagebox

from randomizer.challenges.results import ChallengeResultWatch
from randomizer.challenges.catalogue import (
    COUNTRY_LABELS, allowed_colors, allowed_countries, automatic_ai_teammate, map_config,
)
from randomizer.config.player import save_config
from randomizer.coop import feature
from randomizer.coop.direct import prepare_solo_game
from randomizer.coop.prototype import build_manifest
from randomizer.core.game_shutdown import GameShutdownWatch
from randomizer.core.paths import DEBUG_LOG, GAME_ROOT
from randomizer.rewards.arsenal import ARSENAL_MODE
from randomizer.ui.config import PROGRESSION_MODES
from randomizer.missions.pool import is_challenge, select_mission_pool


class ChallengeController:
    def optional_challenges_enabled(self):
        """Next-seed option; saved runs keep their original pool and launch rules."""
        variable = getattr(self, 'include_challenge_missions_var', None)
        enabled = (variable.get() if variable is not None else
                   self.config.get('generation', {}).get('include_challenge_missions', False))
        return bool(enabled and self.progression_mode_var.get() != 'Shop Mode'
                    and not self.archipelago_run_active())

    def challenges_available(self):
        if self.progression_mode_var.get() == 'Shop Mode' or self.archipelago_run_active():
            return False
        return (self.selected_mission_category() == 'challenge'
                or self.optional_challenges_enabled()
                or any(str(code).startswith('C_') for code in self.state.get('mission_order', ())))

    def challenge_mission(self, code=None):
        if code is not None:
            return is_challenge(self.mission_lookup().get(code))
        if self.shop_mode_selected():
            return False
        mission = self.selected_mission()
        return is_challenge(mission)

    def mission_pool_candidates(self, *, apply_exclusions=True):
        return select_mission_pool(
            self.missions, category=self.selected_mission_category(),
            campaign=self.campaign_var.get(),
            include_challenges=self.optional_challenges_enabled(),
            excluded_codes=self.active_mission_exclusions() if apply_exclusions else (),
        )

    def automatic_challenge_helper(self, mission):
        # Mixed solo runs always fill the native second allied slot. Legacy
        # challenge-only runs keep their optional teammate preference.
        return bool(is_challenge(mission) and self.state
                    and self.state.get('mission_category') != 'challenge'
                    and not self.state.get('coop_mode'))

    def challenge_launch_active(self):
        process = getattr(self, 'active_game_process', None)
        return bool(getattr(self, '_challenge_preparing', False)
                    or getattr(self, '_challenge_result_watch', None)
                    or (self.challenge_mission() and (
                        getattr(self, '_coop_busy', False)
                        or (process is not None and process.poll() is None))))

    def capture_challenge_run_identity(self):
        state = self.state
        return state, (
            state.get('seed'), state.get('mission_category'),
            state.get('challenge_player_count'),
        )

    def challenge_run_identity_matches(self, snapshot):
        if not snapshot or snapshot[0] is not self.state:
            return False
        return snapshot[1] == self.capture_challenge_run_identity()[1]

    def selected_mission_category(self):
        variable = getattr(self, 'mission_category_var', None)
        category = variable.get() if variable is not None else self.config.get('mission_category')
        if category in {'campaign', 'coop', 'challenge'}:
            return category
        return 'coop' if self.config.get('coop_mode') else 'campaign'

    def selected_challenge_player_count(self):
        variable = getattr(self, 'challenge_player_count_var', None)
        value = variable.get() if variable is not None else self.config.get('challenge_player_count', 1)
        return 2 if str(value) == '2' else 1

    def selected_mission_setup(self):
        country = getattr(self, 'challenge_country_var', None)
        category = self.selected_mission_category()
        return (category, self.selected_challenge_player_count(),
                None if category == 'challenge' else (
                    country.get() if country is not None else self.config.get('challenge_country')
                ))

    def sync_mission_transport_mode(self):
        category = self.selected_mission_category()
        multiplayer = category == 'coop' or (
            category == 'challenge' and self.selected_challenge_player_count() == 2
        )
        self.coop_mode_var.set(bool(multiplayer and feature.COOP_FEATURE_ENABLED))

    def restore_mission_setup_from_config(self):
        self.mission_category_var.set(self.config.get('mission_category') or (
            'coop' if self.config.get('coop_mode') else 'campaign'
        ))
        self.challenge_player_count_var.set(str(self.config.get('challenge_player_count', 1)))
        self.restore_challenge_local_options_from_config()
        self.sync_mission_transport_mode()

    def restore_challenge_local_options_from_config(self):
        self.challenge_country_var.set(str(self.config.get('challenge_country') or 'UnitedStates'))
        self.challenge_ai_enabled_var.set(bool(self.config.get('challenge_ai_enabled', False)))
        self.challenge_ai_country_var.set(str(self.config.get('challenge_ai_country') or 'USSR'))
        self.challenge_ai_color_var.set(str(self.config.get('challenge_ai_color') or 'Red'))
        difficulty = self.config.get('challenge_ai_difficulty', 'Normal')
        self.challenge_ai_difficulty_var.set(
            difficulty if difficulty in ('Easy', 'Normal', 'Hard') else 'Normal'
        )
        self.challenge_solo_color_var.set(str(self.config.get('challenge_solo_color') or 'Teal'))

    def store_challenge_local_options(self):
        """Launch preferences stay separate from the saved challenge seed."""
        self.config['challenge_country'] = self.challenge_country_var.get()
        self.config['challenge_ai_enabled'] = bool(self.challenge_ai_enabled_var.get())
        self.config['challenge_ai_country'] = self.challenge_ai_country_var.get()
        self.config['challenge_ai_color'] = self.challenge_ai_color_var.get()
        self.config['challenge_ai_difficulty'] = self.challenge_ai_difficulty_var.get()
        self.config['challenge_solo_color'] = self.challenge_solo_color_var.get()

    def challenge_local_options_locked(self):
        return bool(self.challenge_launch_active() or self.gameplay_settings_locked()
                    or getattr(self, '_coop_lobby', None))

    def on_challenge_ai_house_selected(self, event=None):
        selected = self.challenge_ai_country_label_var.get()
        country = next((country for country, label in COUNTRY_LABELS.items()
                        if label == selected), None)
        if country:
            self.challenge_ai_country_var.set(country)
        self.on_challenge_local_options_changed(event)

    def on_challenge_local_options_changed(self, _event=None):
        if self.challenge_local_options_locked():
            self.restore_challenge_local_options_from_config()
            self.refresh_challenge_local_controls()
            return
        self.refresh_challenge_local_controls()
        self.store_challenge_local_options()
        save_config(self.config)
        self.update_header_summary()

    def coop_selection_changed(self):
        result = super().coop_selection_changed()
        self.refresh_challenge_local_controls()
        self.refresh_challenge_player_controls()
        return result

    def refresh_challenge_local_controls(self):
        local = self.challenges_available() and not self.coop_mode_var.get()
        frames = [getattr(self, prefix + 'challenge_local_frame', None)
                  for prefix in ('', 'shop_')]
        for frame in frames:
            if frame is not None:
                frame.grid() if local else frame.grid_remove()
        if not local or not any(frame is not None for frame in frames):
            return
        self.ensure_challenge_player_options()
        mission = self.selected_mission()
        countries = tuple(COUNTRY_LABELS)
        color_choices = tuple(self._coop_color_values)
        country = self.challenge_ai_country_var.get()
        self.challenge_ai_country_label_var.set(COUNTRY_LABELS.get(country, country))
        country = self.challenge_country_var.get()
        self.challenge_country_label_var.set(COUNTRY_LABELS.get(country, country))
        automatic = self.selected_mission_category() != 'challenge'
        enabled = automatic or bool(self.challenge_ai_enabled_var.get())
        locked = self.challenge_local_options_locked()
        state = 'disabled' if locked else 'readonly'
        for prefix in ('', 'shop_'):
            frame = getattr(self, prefix + 'challenge_local_frame', None)
            if frame is None:
                continue
            getattr(self, prefix + 'challenge_solo_color_combo').configure(
                state=state, values=color_choices,
            )
            getattr(self, prefix + 'challenge_country_combo').configure(
                state=state, values=tuple(COUNTRY_LABELS.values()),
            )
            toggle = getattr(self, prefix + 'challenge_ai_toggle')
            toggle.configure(state='disabled' if locked else 'normal')
            toggle.grid_remove() if automatic else toggle.grid()
            for widget in getattr(self, prefix + 'challenge_ai_fields'):
                widget.grid() if enabled else widget.grid_remove()
            combos = getattr(self, prefix + 'challenge_ai_combos')
            combos['house'].configure(state=state, values=tuple(
                COUNTRY_LABELS[country] for country in countries
            ))
            combos['color'].configure(state=state, values=color_choices)
            combos['difficulty'].configure(state=state, values=('Easy', 'Normal', 'Hard'))
        if automatic:
            text = 'AI helper fills the second allied slot. Invalid AI preferences use safe defaults.'
        elif enabled:
            text = 'AI uses the second allied slot. Its difficulty is independent.'
        else:
            text = 'Choose your house and color for this map.'
        if is_challenge(mission):
            if mission.get('requires_teammate'):
                text += '\nThis map requires two allied participants: an AI teammate or two humans.'
            available = mission.get('allowed_countries', countries)
            restricted = []
            if self.challenge_country_var.get() not in available:
                restricted.append('you')
            if enabled and not automatic and self.challenge_ai_country_var.get() not in available:
                restricted.append('the AI teammate')
            if restricted:
                text += '\nChoose another house for ' + ' and '.join(restricted) + ' on this map.'
            colors = mission.get('allowed_colors', tuple(range(13)))
            if (self._coop_color_values.get(self.challenge_solo_color_var.get()) not in colors
                    or (enabled and not automatic and self._coop_color_values.get(
                        self.challenge_ai_color_var.get()) not in colors)):
                text += '\nA selected color is reserved by this map.'
        if enabled and not automatic and self.challenge_solo_color_var.get() == self.challenge_ai_color_var.get():
            text += '\nChoose different colors for you and the AI.'
        self.challenge_local_summary_var.set(text)

    def challenge_local_launch_options(self, mission):
        """Capture validated native color indices before background preparation."""
        self.refresh_challenge_local_controls()
        self.ensure_challenge_player_options()
        _, _, metadata, _, _ = map_config(GAME_ROOT, mission['coop_name'])
        countries = allowed_countries(metadata)
        colors = allowed_colors(metadata)
        errors = []
        automatic = self.automatic_challenge_helper(mission)
        ai_country = self.challenge_ai_country_var.get()
        ai_color = self.challenge_ai_color_var.get()
        if automatic:
            helper = automatic_ai_teammate(
                metadata, self._coop_color_values.get(self.challenge_solo_color_var.get()),
                country=ai_country, color=self._coop_color_values.get(ai_color),
                difficulty=('Easy', 'Normal', 'Hard').index(self.challenge_ai_difficulty_var.get()),
            )
            ai_country = helper['country']
            ai_color = next(label for label, color in self._coop_color_values.items()
                            if color == helper['color'])
        players = [('Your', self.challenge_country_var.get(), self.challenge_solo_color_var.get())]
        if automatic or self.challenge_ai_enabled_var.get():
            players.append(('AI teammate', ai_country, ai_color))
        for role, country, color in players:
            if country not in countries:
                errors.append(f'{role} house {COUNTRY_LABELS.get(country, country)} is '
                              'restricted or reserved for an enemy on this challenge.')
            if self._coop_color_values.get(color) not in colors:
                errors.append(f'{role} color {color} is unavailable on this challenge.')
        if len(players) == 2 and players[0][2] == players[1][2]:
            errors.append('You and the AI teammate must use different colors.')
        if errors:
            errors.append('Allowed houses: ' + ', '.join(COUNTRY_LABELS[country]
                                                       for country in countries) + '.')
            errors.append('Allowed colors: ' + ', '.join(
                label for label, color in self._coop_color_values.items() if color in colors
            ) + '.')
            raise ValueError('\n\n'.join(errors))
        human_color = self._coop_color_values[self.challenge_solo_color_var.get()]
        ai = None
        if automatic or self.challenge_ai_enabled_var.get():
            ai = {
                'country': ai_country,
                'color': self._coop_color_values[ai_color],
                'difficulty': ('Easy', 'Normal', 'Hard').index(
                    self.challenge_ai_difficulty_var.get()
                ),
            }
        return human_color, ai

    def on_coop_checkbox_changed(self):
        """Map the simple co-op toggle to the existing saved mission pools."""
        self.mission_category_var.set('coop' if self.coop_mode_var.get() else 'campaign')
        self.on_mission_category_changed()

    def on_mission_category_changed(self, _event=None):
        if self.selected_mission_category() == 'coop' and not feature.COOP_FEATURE_ENABLED:
            self.restore_mission_setup_from_config()
            return
        if self.gameplay_settings_locked() or self.challenge_launch_active() or getattr(self, '_coop_lobby', None):
            self.restore_mission_setup_from_config()
            return
        self.config.setdefault('generation', {})['include_challenge_missions'] = bool(
            self.include_challenge_missions_var.get()
        )
        self.sync_mission_transport_mode()
        self.on_coop_mode_changed()

    def initialize_challenge_defaults(self):
        """Restore category-specific Tier 1 starter preferences."""
        category = self.selected_mission_category()
        previous = getattr(self, '_starter_settings_category', None)
        if previous == category:
            return
        variables = {
            'start_with_tier_one_units': self.start_with_tier_one_units_var,
            'start_with_tier_one_defenses': self.start_with_tier_one_defenses_var,
        }
        if previous is not None:
            destination = self.config.setdefault(
                'challenge_starters' if previous == 'challenge' else 'generation', {}
            )
            destination.update({
                key: bool(variable.get()) for key, variable in variables.items()
            })
        source = self.config.setdefault(
            'challenge_starters' if category == 'challenge' else 'generation', {}
        )
        legacy = (
            self.config.get('generation', {})
            if category == 'challenge' and self.config.get('challenge_defaults_initialized')
            else {}
        )
        for key, variable in variables.items():
            variable.set(bool(source.setdefault(key, legacy.get(key, category == 'challenge'))))
        self._starter_settings_category = category

    def on_challenge_country_selected(self, event=None):
        if self.challenge_local_options_locked():
            self.restore_challenge_local_options_from_config()
            self.refresh_challenge_support_controls()
            return
        selected = self.challenge_country_label_var.get()
        country = next((country for country, label in COUNTRY_LABELS.items()
                        if label == selected), None)
        if country:
            self.challenge_country_var.set(country)
        self.on_challenge_local_options_changed(event)

    def on_challenge_setup_changed(self, _event=None):
        if self.challenge_launch_active():
            self.restore_mission_setup_from_config()
            self.refresh_coop_controls()
            return
        if not feature.COOP_FEATURE_ENABLED and self.selected_challenge_player_count() == 2:
            self.challenge_player_count_var.set('1')
        self.sync_mission_transport_mode()
        self.on_coop_mode_changed()

    def refresh_setting_states(self):
        super().refresh_setting_states()
        self.refresh_challenge_support_controls()

    def refresh_coop_controls(self):
        super().refresh_coop_controls()
        if self.challenge_launch_active():
            for name in ('coop_mode_check', 'shop_coop_mode_check',
                         'coop_player_count_combo', 'shop_coop_player_count_combo',
                         'challenge_country_combo', 'shop_challenge_country_combo',
                         'difficulty_combo'):
                widget = getattr(self, name, None)
                if widget is not None:
                    widget.configure(state='disabled')

    def refresh_challenge_support_controls(self):
        challenge = self.selected_mission_category() == 'challenge'
        label = getattr(self, 'challenge_country_label_var', None)
        if label is not None:
            country = self.challenge_country_var.get()
            label.set(COUNTRY_LABELS.get(country, country))
        count = sum(is_challenge(mission) for mission in getattr(self, 'missions', ()))
        availability = getattr(self, 'challenge_availability_var', None)
        if availability is not None:
            text = ('Solo gets an AI helper; Co-op uses two players.\n'
                    'Map house/color restrictions apply.')
            if self.progression_mode_var.get() == 'Shop Mode' or self.archipelago_run_active():
                text = 'Challenges are unavailable in Shop Mode and Archipelago.'
            if challenge:
                text = ('Saved challenge-only run. Toggle Co-op to switch mission pools.\n'
                        'Map house/color restrictions apply.')
            availability.set(text)
        for prefix in ('', 'shop_'):
            widget = getattr(self, prefix + 'include_challenge_missions_check', None)
            if widget is not None:
                supported = (not challenge and self.progression_mode_var.get() != 'Shop Mode'
                             and not self.gameplay_settings_locked() and not self.coop_guest_connected())
                widget.configure(
                    text=f'Include challenge maps ({count} installed)',
                    state='normal' if supported else 'disabled',
                )
        assistance = getattr(self, 'failure_assistance_check', None)
        if assistance is not None:
            assistance.configure(
                state='disabled' if challenge or self.gameplay_settings_locked() else 'normal'
            )
        description = getattr(self, 'assistance_description_label', None)
        if description is not None:
            description.grid_remove() if challenge else description.grid()
        if assistance is not None:
            assistance.configure(text=(
                'Retry assistance is unavailable for challenges'
                if challenge else 'Strengthen failed missions on retry'
            ))
        for prefix in ('', 'shop_'):
            for suffix in ('challenge_country_combo', 'challenge_country_label'):
                widget = getattr(self, prefix + suffix, None)
                if widget is not None:
                    widget.grid() if self.challenges_available() and not self.coop_mode_var.get() else widget.grid_remove()
        if challenge and self.progression_mode_var.get() == 'Shop Mode':
            self.progression_mode_var.set('Grid Mode')
        modes = tuple(mode for mode in PROGRESSION_MODES
                      if not challenge or mode != 'Shop Mode')
        for name in ('progression_mode_combo', 'shop_progression_mode_combo'):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.configure(values=modes)
        for name in ('archipelago_connect_button', 'archipelago_save_yaml_button'):
            widget = getattr(self, name, None)
            if widget is not None and not self.gameplay_settings_locked():
                widget.configure(state='disabled' if challenge else 'normal')
        if challenge:
            button = getattr(self, 'shop_setup_start_button', None)
            if button is not None:
                button.configure(state='disabled')
        self.refresh_challenge_local_controls()

    def on_progression_mode_changed(self, event=None):
        if (self.selected_mission_category() == 'challenge'
                and self.progression_mode_var.get() == 'Shop Mode'):
            self.progression_mode_var.set('Grid Mode')
        result = super().on_progression_mode_changed(event)
        self.refresh_challenge_support_controls()
        self.update_mission_goal_limit()
        self.refresh_advanced_pool_views()
        return result

    def connect_archipelago(self):
        if self.selected_mission_category() == 'challenge':
            messagebox.showwarning('Challenges', 'Challenge testing supports standalone seeds only.')
            return
        return super().connect_archipelago()

    def save_archipelago_yaml(self):
        if self.selected_mission_category() == 'challenge':
            return
        return super().save_archipelago_yaml()

    def start_shop_run(self):
        if self.selected_mission_category() == 'challenge':
            messagebox.showwarning('Challenges', 'Choose Grid Mode, Mission List, or Classic for challenges.')
            return
        return super().start_shop_run()

    def challenge_run_ready(self):
        legacy = self.selected_mission_category() == 'challenge'
        expected = ('challenge', self.selected_challenge_player_count())
        active = (self.state.get('mission_category'), self.state.get('challenge_player_count', 1))
        if not self.state or (legacy and active != expected):
            messagebox.showwarning(
                'Challenge Seed Required',
                'Generate a seed including challenges for the selected player mode first.',
            )
            return False
        if (self.state.get('coop_mode', False) != self.coop_mode_var.get()
                or self.selected_mission_code() not in self.state.get('mission_order', ())):
            messagebox.showwarning('Challenge Seed Required',
                                   'Select a challenge from the current generated mission pool.')
            return False
        if self.shop_mode_selected() or self.archipelago_run_active():
            messagebox.showwarning('Challenges', 'Choose a standalone Grid, Mission List, or Classic seed.')
            return False
        return True

    def on_launch_selected(self):
        if not self.challenge_mission():
            return super().on_launch_selected()
        if self.challenge_launch_active():
            messagebox.showwarning('Challenges', 'Close the current game before launching another challenge.')
            return
        if not self.challenge_run_ready():
            return
        if self.coop_mode_var.get():
            return self.request_coop_launch()
        mission = self.selected_mission()
        if mission is None:
            return
        if mission['code'] not in set(self.unlocked_mission_codes()) | set(
                self.state.get('completed_missions', [])):
            messagebox.showwarning('Challenge Locked', 'Complete an open challenge to unlock this one.')
            return
        process = self.active_game_process
        if process is not None and process.poll() is None:
            messagebox.showwarning('Challenges', 'Close the current game first.')
            return
        self.save_current_launcher_config()
        self.start_solo_challenge(mission)

    def on_debug_mark_complete(self):
        process = self.active_game_process
        if (self.challenge_mission()
                and process is not None and process.poll() is None):
            messagebox.showinfo('Challenges', 'Close the current game before recording a manual victory.')
            return
        return super().on_debug_mark_complete()

    def create_challenge_result_watch(self, mission, name, *, peer='', ai_teammate=False):
        return ChallengeResultWatch(
            DEBUG_LOG, name, int(mission['enemy_count']),
            expected_human_names=(peer,) if peer else (),
            ai_teammate=ai_teammate,
        )

    def start_solo_challenge(self, mission):
        try:
            human_color, ai_teammate = self.challenge_local_launch_options(mission)
        except (OSError, ValueError) as exc:
            messagebox.showwarning('Challenge Player Conflict', str(exc))
            return
        launch_snapshot = self.capture_challenge_run_identity()
        state = copy.deepcopy(self.state)
        country = self.challenge_country_var.get()
        name = re.sub(r'[^A-Za-z0-9_-]', '', str(
            self.config.get('player_name') or 'Commander'
        ))[:14] or 'Commander'
        if name.casefold() == 'computer':
            name = 'Commander'
        difficulty = self.get_selected_difficulty_value()
        game_speed = self.get_selected_game_speed_value()
        self._challenge_preparing = True
        self.refresh_coop_controls()

        def prepare():
            self.begin_direct_game_preparation()
            manifest, _ = build_manifest(
                GAME_ROOT, state, mission['coop_name'], country=country,
                player_count=1, difficulty=difficulty, game_speed=game_speed,
                player_colors=[human_color], ai_teammate=ai_teammate,
                source_mission=(mission['code'] if state.get('reward_mode') == ARSENAL_MODE else ''),
            )
            prepare_solo_game(
                GAME_ROOT, manifest, name=name,
                difficulty=('easy', 'normal', 'hard')[difficulty],
                game_speed=game_speed,
            )
            self.prepare_direct_game_art()
            # Capture the old log boundary before the engine can emit results.
            watch = self.create_challenge_result_watch(mission, name, ai_teammate=bool(ai_teammate))
            shutdown_watch = GameShutdownWatch(DEBUG_LOG)
            process, command_text = self.spawn_game_process(self.build_command())
            shutdown_watch.bind(process)
            return process, watch, shutdown_watch, command_text

        def finish(result):
            process, watch, shutdown_watch, command_text = result
            self.active_game_process = process
            self._challenge_preparing = False
            self._challenge_launch_snapshot = launch_snapshot
            self._challenge_result_watch = watch
            self._challenge_shutdown_watch = shutdown_watch
            self._challenge_active_code = mission['code']
            self._challenge_result_applied = False
            partner = (f'AI teammate {COUNTRY_LABELS[ai_teammate["country"]]} '
                       f'({self.challenge_ai_difficulty_var.get()})' if ai_teammate else 'solo')
            self.append_log(f'Challenge started: {mission["title"]}, {country}, {partner}; '
                            f'game speed {self.game_speed_var.get()}.')
            self.append_log(command_text)
            self.refresh_coop_controls()
            self.after(1000, self.poll_solo_challenge)

        def fail(exc, detail):
            self.disable_generated_rules_for_client()
            self._challenge_preparing = False
            self.append_log(detail, error=True)
            self.refresh_coop_controls()
            if getattr(self, '_close_after_game', False):
                self.close_launcher()
                return
            messagebox.showerror('Challenge Launch Failed', str(exc))

        self.run_in_background(
            'Starting challenge…', 'Applying native challenge rules and earned rewards.',
            prepare, finish, fail,
        )

    def poll_solo_challenge(self):
        watch = getattr(self, '_challenge_result_watch', None)
        code = getattr(self, '_challenge_active_code', '')
        if watch is not None:
            watch.poll()
        result = watch.result if watch is not None else None
        if result and not getattr(self, '_challenge_result_applied', False):
            self._challenge_result_applied = True
            if not self.challenge_run_identity_matches(
                    getattr(self, '_challenge_launch_snapshot', None)):
                self.append_log('Challenge result belongs to a different run; no victory awarded.', error=True)
            elif result == 'victory':
                self.append_log(f'Challenge native victory verified for {code}.')
                if not self.is_mission_complete(code):
                    self.unlock_mission_check(code, 'victory', 'Challenge in-game victory')
            else:
                self.append_log(f'Challenge defeat detected for {code}; no victory awarded.')
        process = self.active_game_process
        shutdown_watch = getattr(self, '_challenge_shutdown_watch', None)
        if shutdown_watch is not None:
            for message, is_error in shutdown_watch.poll(process):
                self.append_log(message, error=is_error)
        if process is not None and process.poll() is None:
            self.after(1000, self.poll_solo_challenge)
            return
        if shutdown_watch is not None and shutdown_watch.recovery_pending:
            self.after(100, self.poll_solo_challenge)
            return
        self.active_game_process = None
        self.disable_generated_rules_for_client()
        if shutdown_watch is not None:
            shutdown_watch.close()
        self._challenge_shutdown_watch = None
        if not result:
            self.append_log('Challenge ended without a verified result; no victory awarded.')
        if watch is not None and watch.error:
            self.append_log('Challenge result log: ' + watch.error, error=True)
        self._challenge_result_watch = None
        self._challenge_launch_snapshot = None
        self.refresh_coop_controls()
        if getattr(self, '_close_after_game', False):
            self.shutdown_archipelago()
            self.destroy()
