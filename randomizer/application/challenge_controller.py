"""Challenge selection, supported launch modes, and native result tracking."""

import copy
import re
from tkinter import messagebox

from randomizer.challenges.results import ChallengeResultWatch
from randomizer.challenges.catalogue import COUNTRY_LABELS
from randomizer.config.player import save_config
from randomizer.coop import feature
from randomizer.coop.direct import prepare_solo_game
from randomizer.coop.prototype import build_manifest
from randomizer.core.game_shutdown import GameShutdownWatch
from randomizer.core.paths import DEBUG_LOG, GAME_ROOT
from randomizer.rewards.arsenal import ARSENAL_MODE
from randomizer.ui.config import PROGRESSION_MODES


class ChallengeController:
    def challenge_launch_active(self):
        process = getattr(self, 'active_game_process', None)
        return bool(getattr(self, '_challenge_preparing', False) or (
            self.selected_mission_category() == 'challenge' and (
                getattr(self, '_coop_busy', False)
                or (process is not None and process.poll() is None)
            )
        ))

    def capture_challenge_run_identity(self):
        state = self.state
        return state, (
            state.get('seed'), state.get('mission_category'),
            state.get('challenge_player_count'), state.get('challenge_country'),
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
        return (self.selected_mission_category(), self.selected_challenge_player_count(),
                country.get() if country is not None else self.config.get('challenge_country'))

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
        self.challenge_country_var.set(str(self.config.get('challenge_country') or 'UnitedStates'))
        self.sync_mission_transport_mode()

    def on_mission_category_changed(self, _event=None):
        if self.selected_mission_category() == 'coop' and not feature.COOP_FEATURE_ENABLED:
            self.restore_mission_setup_from_config()
            return
        self.sync_mission_transport_mode()
        self.initialize_challenge_defaults()
        self.on_coop_mode_changed()

    def initialize_challenge_defaults(self):
        """Give the first challenge seed a usable production roster."""
        if (self.selected_mission_category() != 'challenge'
                or self.config.get('challenge_defaults_initialized')):
            return
        generation = self.config.setdefault('generation', {})
        for key, variable in (
                ('start_with_tier_one_units', self.start_with_tier_one_units_var),
                ('start_with_tier_one_defenses', self.start_with_tier_one_defenses_var)):
            generation[key] = True
            variable.set(True)
        self.config['challenge_defaults_initialized'] = True
        save_config(self.config)

    def on_challenge_country_selected(self, event=None):
        selected = self.challenge_country_label_var.get()
        country = next((country for country, label in COUNTRY_LABELS.items()
                        if label == selected), None)
        if country:
            self.challenge_country_var.set(country)
        self.on_challenge_setup_changed(event)

    def on_challenge_setup_changed(self, _event=None):
        if not feature.COOP_FEATURE_ENABLED and self.selected_challenge_player_count() == 2:
            self.challenge_player_count_var.set('1')
        self.sync_mission_transport_mode()
        self.on_coop_mode_changed()

    def refresh_setting_states(self):
        super().refresh_setting_states()
        self.refresh_challenge_support_controls()

    def refresh_challenge_support_controls(self):
        challenge = self.selected_mission_category() == 'challenge'
        label = getattr(self, 'challenge_country_label_var', None)
        if label is not None:
            country = self.challenge_country_var.get()
            label.set(COUNTRY_LABELS.get(country, country))
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

    def on_progression_mode_changed(self, event=None):
        if (self.selected_mission_category() == 'challenge'
                and self.progression_mode_var.get() == 'Shop Mode'):
            self.progression_mode_var.set('Grid Mode')
        result = super().on_progression_mode_changed(event)
        self.refresh_challenge_support_controls()
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
        expected = ('challenge', self.selected_challenge_player_count(),
                    self.challenge_country_var.get())
        active = (self.state.get('mission_category'),
                  self.state.get('challenge_player_count', 1),
                  self.state.get('challenge_country'))
        if not self.state or active != expected:
            messagebox.showwarning(
                'Challenge Seed Required',
                'Generate a challenge seed for the selected country and player count first.',
            )
            return False
        if self.shop_mode_selected() or self.archipelago_run_active():
            messagebox.showwarning('Challenges', 'Choose a standalone Grid, Mission List, or Classic seed.')
            return False
        return True

    def on_launch_selected(self):
        if self.selected_mission_category() != 'challenge':
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
        if (self.selected_mission_category() == 'challenge'
                and process is not None and process.poll() is None):
            messagebox.showinfo('Challenges', 'Close the current game before recording a manual victory.')
            return
        return super().on_debug_mark_complete()

    def create_challenge_result_watch(self, mission, name, *, peer=''):
        return ChallengeResultWatch(
            DEBUG_LOG, name, int(mission['enemy_count']),
            expected_human_names=(peer,) if peer else (),
        )

    def start_solo_challenge(self, mission):
        launch_snapshot = self.capture_challenge_run_identity()
        state = copy.deepcopy(self.state)
        country = str(state['challenge_country'])
        name = re.sub(r'[^A-Za-z0-9_-]', '', str(
            self.config.get('player_name') or 'Commander'
        ))[:14] or 'Commander'
        if name.casefold() == 'computer':
            name = 'Commander'
        difficulty = self.get_selected_difficulty_value()
        game_speed = self.get_selected_game_speed_value()
        self._challenge_preparing = True
        self.refresh_game_speed_controls()

        def prepare():
            manifest, _ = build_manifest(
                GAME_ROOT, state, mission['coop_name'], country=country,
                player_count=1, difficulty=difficulty, game_speed=game_speed,
                source_mission=(mission['code'] if state.get('reward_mode') == ARSENAL_MODE else ''),
            )
            prepare_solo_game(
                GAME_ROOT, manifest, name=name,
                difficulty=('easy', 'normal', 'hard')[difficulty],
                game_speed=game_speed,
            )
            # Capture the old log boundary before the engine can emit results.
            watch = self.create_challenge_result_watch(mission, name)
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
            self.append_log(f'Challenge started: {mission["title"]}, {country}, solo; '
                            f'game speed {self.game_speed_var.get()}.')
            self.append_log(command_text)
            self.refresh_coop_controls()
            self.after(1000, self.poll_solo_challenge)

        def fail(exc, detail):
            self._challenge_preparing = False
            self.append_log(detail, error=True)
            self.refresh_coop_controls()
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
