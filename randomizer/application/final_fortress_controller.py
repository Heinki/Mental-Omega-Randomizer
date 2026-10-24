"""Independent Final Fortress selection, workspace, and launcher bridge."""

import tkinter as tk
from tkinter import messagebox
import secrets

from randomizer.challenges.catalogue import COUNTRY_LABELS
from randomizer.core.paths import DEBUG_LOG, GAME_EXE, GAME_LAUNCHER_EXE, GAME_ROOT
from randomizer.core.game_shutdown import GameShutdownWatch
from randomizer.final_fortress import DISPLAY_NAME
from randomizer.final_fortress.config import (
    DIFFICULTY_IDS, WAVE_MULTIPLIERS, configuration_gaps, load_config,
)
from randomizer.final_fortress.maps import inspect_map, map_definitions, select_map
from randomizer.final_fortress.engine import prepare_game, cleanup_ai_preload
from randomizer.final_fortress.results import FinalFortressResultWatch
from randomizer.final_fortress.pressure import wave_growth
from randomizer.final_fortress.persistence import (
    FinalFortressPersistenceError, FinalFortressRepository,
)
from randomizer.final_fortress.ui import show_final_fortress_help, refresh_results
from randomizer.final_fortress.profiles import PROFILE_PATHS, STANDARD_PROFILE, ALL_UNLOCKS_PROFILE
from randomizer.final_fortress.challenges import label, description, maximum
from randomizer.ui.config import DIFFICULTIES, PROGRESSION_MODES
from randomizer.ui.cameos import installed_rules_registry
from .fortress_coop_controller import FortressCoopController


class FinalFortressController(FortressCoopController):
    def apply_color_mode(self):
        super().apply_color_mode()
        for name in ('final_fortress_perk_details', 'final_fortress_challenge_details'):
            details = getattr(self, name, None)
            if details is not None:
                palette = self.ui_palette()
                details.configure(background=palette['background'], foreground=palette['foreground'],
                                  selectbackground=palette['select'],
                                  selectforeground=palette['select_foreground'])

    def disable_generated_rules_for_client(self):
        from randomizer.maps.assets import _other_live_runtime_asset_owner
        if _other_live_runtime_asset_owner():
            return
        result = super().disable_generated_rules_for_client()
        cleanup_ai_preload(GAME_ROOT)
        return result

    def final_fortress_mode_selected(self):
        variable = getattr(self, 'game_mode_var', None)
        return variable is not None and variable.get() == DISPLAY_NAME

    def final_fortress_selected(self):
        return (self.final_fortress_mode_selected()
                and hasattr(self, 'final_fortress_tab')
                and self.workspace_tabs.select() == str(self.final_fortress_tab))

    def initialize_final_fortress_controller(self):
        self._final_fortress_preparing = False
        self._final_fortress_watch = None
        self._final_fortress_shutdown = None
        self._final_fortress_logged_waves = 0
        self._final_fortress_recorded_events = set()
        self._final_fortress_recorded_kills = None
        self._final_fortress_recovery_checked = set()
        self._final_fortress_launch_blockers = []
        self._fortress_lobbies = {}
        self.final_fortress_coop_var = tk.BooleanVar(value=False)
        self._fortress_coop_count_var = tk.StringVar(value='2')
        self._fortress_challenge_maps_var = tk.BooleanVar(value=False)
        self.fortress_coop_status_var = tk.StringVar(value='Disconnected')
        self.final_fortress_repository = FinalFortressRepository()
        self._final_fortress_profile = STANDARD_PROFILE
        self.final_fortress_profile_var = tk.StringVar(value=STANDARD_PROFILE)
        self.final_fortress_config = None
        self.final_fortress_state = None
        self._final_fortress_saved_tabs = None
        self.game_mode_choices = (*PROGRESSION_MODES, DISPLAY_NAME)
        self.game_mode_var = tk.StringVar(value=self.progression_mode_var.get())
        self.final_fortress_map_choices = ()
        self.final_fortress_country_choices = {
            label: country for country, label in COUNTRY_LABELS.items()
        }
        self.final_fortress_difficulty_choices = {
            label: DIFFICULTY_IDS[index] for label, index in DIFFICULTIES
        }
        self.final_fortress_wave_multiplier_choices = {
            f'x{value}': value for value in WAVE_MULTIPLIERS
        }
        self.final_fortress_map_var = tk.StringVar()
        self.final_fortress_country_var = tk.StringVar()
        self.final_fortress_difficulty_var = tk.StringVar()
        self.final_fortress_wave_multiplier_var = tk.StringVar(value='x1')
        self.final_fortress_mental_ai_boost_var = tk.BooleanVar(value=False)
        self.final_fortress_status_var = tk.StringVar(value='Launch unavailable — see Help.')
        self.final_fortress_help_var = tk.StringVar()
        self.final_fortress_result_var = tk.StringVar(value='Finish a run to see its rewards.')
        self.final_fortress_header_var = tk.StringVar(value='Final Fortress · Survival defense')
        self.final_fortress_gems_var = tk.StringVar(value='Defensive Points: 0')
        self.progression_mode_var.trace_add('write', self._sync_game_mode_choice)
        try:
            self.final_fortress_map_catalogue = load_config()
            self.final_fortress_config = self.final_fortress_map_catalogue
            definition = self.final_fortress_config['map']
            self.final_fortress_map_choices = tuple(
                entry['display_name'] for entry in map_definitions(self.final_fortress_map_catalogue))
            if definition is not None:
                self.final_fortress_map_var.set(definition['display_name'])
            self.final_fortress_state = self.final_fortress_repository.load()
            if self.final_fortress_state['preferences']['workspace_selected']:
                self.game_mode_var.set(DISPLAY_NAME)
        except (RuntimeError, ValueError, OSError) as exc:
            self.final_fortress_status_var.set(str(exc))

    def _sync_game_mode_choice(self, *_args):
        if not self.final_fortress_mode_selected():
            self.game_mode_var.set(self.progression_mode_var.get())

    def on_final_fortress_profile_changed(self, _event=None):
        selected = self.final_fortress_profile_var.get()
        process = getattr(self, 'active_game_process', None)
        if (selected not in PROFILE_PATHS or self._final_fortress_preparing or self._fortress_lobbies
                or self._final_fortress_watch is not None
                or (process is not None and process.poll() is None)):
            self.final_fortress_profile_var.set(self._final_fortress_profile)
            return
        try:
            repository = FinalFortressRepository(PROFILE_PATHS[selected])
            if selected == ALL_UNLOCKS_PROFILE:
                repository.initialize_all_unlocks(self.final_fortress_config)
            state = repository.load()
        except (ValueError, FinalFortressPersistenceError) as exc:
            self.final_fortress_profile_var.set(self._final_fortress_profile)
            messagebox.showerror(DISPLAY_NAME, str(exc), parent=self)
            return
        self.final_fortress_repository = repository
        self.final_fortress_state = state
        self._final_fortress_profile = selected
        self._final_fortress_result_content = None
        self._final_fortress_results_shown = None
        self.refresh_final_fortress()
        if selected == ALL_UNLOCKS_PROFILE:
            self.final_fortress_progression_tabs.select(0)

    def on_game_mode_changed(self, event=None):
        selected = self.game_mode_var.get()
        if selected not in self.game_mode_choices:
            return
        final_fortress = selected == DISPLAY_NAME
        process = getattr(self, 'active_game_process', None)
        if (getattr(self, '_coop_lobby', None) or getattr(self, '_coop_busy', False)
                or self._fortress_lobbies
                or self._final_fortress_preparing
                or (process is not None and process.poll() is None)):
            self.game_mode_var.set(
                DISPLAY_NAME if self._final_fortress_saved_tabs is not None
                else self.progression_mode_var.get())
            return
        if final_fortress or self._final_fortress_saved_tabs is not None:
            try:
                self.final_fortress_repository.set_workspace_selected(final_fortress)
            except FinalFortressPersistenceError as exc:
                messagebox.showerror(DISPLAY_NAME, str(exc), parent=self)
                if final_fortress:
                    self.game_mode_var.set(self.progression_mode_var.get())
                    return
        if final_fortress:
            # Never pass this standalone mode into campaign seed generation.
            self.sync_shop_workspace()
            self.refresh_coop_controls()
            return
        self.progression_mode_var.set(selected)
        self.on_progression_mode_changed(event)
        self._sync_game_mode_choice()
        self.update_header_summary()
        self.refresh_coop_controls()

    def refresh_challenge_support_controls(self):
        result = super().refresh_challenge_support_controls()
        self.refresh_fortress_settings_controls()
        for name in ('progression_mode_combo', 'shop_progression_mode_combo'):
            widget = getattr(self, name, None)
            if widget is not None:
                choices = tuple(widget.cget('values'))
                if DISPLAY_NAME not in choices:
                    widget.configure(values=(*choices, DISPLAY_NAME))
        return result

    def sync_shop_workspace(self):
        """Swap the primary workspace without changing Shop or Grid state."""
        if not hasattr(self, 'final_fortress_tab'):
            return super().sync_shop_workspace()
        notebook = self.workspace_tabs
        if self.final_fortress_mode_selected():
            if self._final_fortress_saved_tabs is None:
                super().sync_shop_workspace()
                self._final_fortress_saved_tabs = [
                    (self.nametowidget(tab), notebook.tab(tab, 'text'))
                    for tab in notebook.tabs() if tab != str(self.final_fortress_tab)
                ]
            for tab in tuple(notebook.tabs()):
                if tab not in (str(self.final_fortress_tab), str(self.settings_tab)):
                    notebook.forget(tab)
            if str(self.final_fortress_tab) not in notebook.tabs():
                notebook.insert(0, self.final_fortress_tab, text=DISPLAY_NAME)
            notebook.select(self.final_fortress_tab)
            self.on_workspace_tab_changed()
            return
        if self._final_fortress_saved_tabs is not None:
            for index, (widget, label) in enumerate(self._final_fortress_saved_tabs):
                notebook.insert(index, widget, text=label)
            self._final_fortress_saved_tabs = None
        if str(self.final_fortress_tab) in notebook.tabs():
            notebook.forget(self.final_fortress_tab)
        return super().sync_shop_workspace()

    def on_workspace_tab_changed(self, _event=None):
        self.refresh_challenge_support_controls()
        if self.final_fortress_mode_selected():
            self._final_fortress_workspace_active = True
            self.subtitle_label.configure(textvariable=self.final_fortress_header_var)
            self.copy_seed_button.grid_remove()
            self.right_frame.grid_remove()
            self.workspace_tabs.grid_configure(columnspan=2, padx=0)
            self.settings_toggle_button.grid_remove()
            self.compact_action_row.grid_remove()
            self.sync_debug_completion_controls()
            if self.workspace_tabs.select() == str(self.settings_tab):
                self.after_idle(lambda: self.layout_settings_sections(
                    self.settings_canvas.winfo_width()))
            self.after_idle(self.refresh_final_fortress)
            return
        leaving = getattr(self, '_final_fortress_workspace_active', False)
        if leaving:
            self._final_fortress_workspace_active = False
            self.subtitle_label.configure(textvariable=self.header_summary_var)
            self.copy_seed_button.grid()
        result = super().on_workspace_tab_changed(_event)
        if leaving:
            self.sync_debug_completion_controls()
        return result

    def sync_debug_completion_controls(self):
        if self.final_fortress_mode_selected():
            for name in ('shop_debug_mission_combo', 'shop_debug_complete_button'):
                widget = getattr(self, name, None)
                if widget is not None:
                    widget.grid_remove()
            return
        return super().sync_debug_completion_controls()

    def on_new_seed(self):
        if self.final_fortress_mode_selected():
            self.show_final_fortress_help('How to play')
            return
        return super().on_new_seed()

    def refresh_final_fortress(self):
        if self.final_fortress_config is None:
            return
        try:
            state = self.final_fortress_repository.load()
        except FinalFortressPersistenceError as exc:
            self.final_fortress_state = None
            self.final_fortress_status_var.set('Saved state unavailable: ' + str(exc))
            return
        self.final_fortress_state = state
        preferences = state['preferences']
        catalogue = self.final_fortress_map_catalogue
        map_id = preferences['map_id'] or (catalogue['map'] or {}).get('id')
        if self.fortress_coop_guest():
            map_id = getattr(self, '_fortress_host_map_id', None) or map_id
        try:
            self.final_fortress_config = select_map(catalogue, map_id) if map_id else catalogue
        except ValueError as exc:
            self._final_fortress_launch_blockers = [str(exc)]
            self.final_fortress_status_var.set(str(exc))
            if hasattr(self, 'final_fortress_launch_button'):
                self.final_fortress_launch_button.configure(state='disabled')
            return
        self.final_fortress_map_var.set((self.final_fortress_config['map'] or {}).get('display_name', ''))
        self.final_fortress_country_var.set(COUNTRY_LABELS.get(preferences['player_country'], ''))
        self.final_fortress_difficulty_var.set(next(
            label for label, key in self.final_fortress_difficulty_choices.items()
            if key == preferences['difficulty']))
        self.final_fortress_wave_multiplier_var.set(f'x{preferences["wave_multiplier"]}')
        self.final_fortress_mental_ai_boost_var.set(preferences['mental_ai_boost'])
        config = self.final_fortress_config
        settings = config['settings']
        pressure = config.get('wave_pressure')
        rules = [
            'Co-op supports two or three humans over ZeroTier. In Settings, enable Co-op '
            'and open Co-op Connection; '
            'the host selects the human count, faction, difficulty and enabled perks. '
            'All teammates share those perks except Fundraising: each human uses their own enabled rank. '
            'Two humans leave at most one perk-enabled AI helper; '
            'three humans leave none. Every human earns their own Defensive Points and buys '
            'their own permanent perks. Camp crates are present from the start. Any human can collect '
            'one; collection awards Defensive Points to everyone and the cash or units to its collector. '
            'Enemy and helper AI pickups award the host the contents and collection credit.',
            'Defend Einstein’s Lab beside your starting MCV for '
            f'{settings["survival_seconds"] / 60:g} in-game minutes against three enemy AIs.',
            'Lab durability increases the Lab’s maximum health for the whole run. '
            'Emergency Lab repair restores that full maximum once per run below '
            '35% health. Lab reserve squad has ten ranks, growing from 4 to 25 faction units '
            'per friendly house once below 50%; ranks 9 and 10 arrive Veteran and Elite. '
            'It grants 10 seconds of Iron Curtain on the Lab '
            'while squads arrive. Each human controls their own reserve; '
            'both perks reset for the next run.',
            'Cheaper Construction and Cheaper Production separately reduce building/defense and unit costs '
            'by 5% per rank, up to 25%. Special Building Limit adds up to three to special-building caps. '
            'Fundraising automatically deposits 1,000 credits per rank every five in-game minutes, '
            'up to 4,000; no collection required. AI helpers use the host Fundraising rank.',
            f'Additional waves start after {settings["wave_interval_seconds"] / 60:g} minutes '
            'and repeat at the same interval. Normal AI attacks continue throughout.',
            'AI difficulty sets the opening wave count. The wave multiplier applies only '
            'to additional reinforcements. Composition varies with time and faction.',
            'Next enemy wave counts down separately from Until Victory. At zero, a wave may '
            'wait for free unit capacity; the clock restarts after its complete delivery. '
            'It disappears after the last scheduled wave.',
            'Friendly reinforcements use a separate shared cap. They arrive in small groups; '
            'each house has its own timer, and a message explains capacity waits. '
            'Their scorched arrival tiles cannot be built over.',
        ]
        if pressure is not None and pressure['growth_per_wave'] is not None:
            rules.append(f'Growth: +{wave_growth(config, preferences["difficulty"])} base units '
                         f'per active side per wave, before x{preferences["wave_multiplier"]}.')
            if 'spawn_sides' in pressure:
                rules.append('Spawn sides: ' + ', '.join(
                    f'{stage["count"]} at {stage["from_seconds"] / 60:g} min'
                    for stage in pressure['spawn_sides']) + '.')
            rules.append(f'Provisional shared limits: {settings["max_wave_units"]} per wave; '
                         f'{pressure["max_active_units"]} reserved wave units. '
                         'Waves arrive in groups of up to twenty; each enemy has one third of the living limit. '
                         'Empty group slots are reused without waiting for an entire earlier wave to die. '
                         'Five minutes separate a completed delivery and the next wave. '
                         'Normal AI production is excluded. These limits need gameplay balance review.')
        rules.append('Mental AI Boost uses the installed skirmish option: faster team creation, '
                     'AI economy bonuses and parallel production. It affects enemy and allied AI; '
                     'normal AI production is outside the scripted-wave cap.')
        for stage in config.get('wave_air_support', []):
            rules.append(f'From {stage["from_seconds"] / 60:g} minutes, faction air attacks replace '
                         f'{stage["percent"]}% of each wave (at least one aircraft where space allows). '
                         'Air and ground attack teams share the existing wave cap.')
        if config.get('wave_priorities'):
            priorities = config['wave_priorities']
            rules.append('Advanced/special ground-wave shares, where available: ' + '; '.join(
                f'{stage["advanced_percent"] + stage["special_percent"]}% from {stage["from_seconds"] / 60:g} minutes'
                for stage in priorities['stages'])
                + f'. From {priorities["late_seconds"] / 60:g} minutes, pending early-wave deliveries also '
                  'upgrade and later ground waves send stronger units first. The living-unit limit remains unchanged.')
        self.final_fortress_gems_var.set(f'Defensive Points: {state["gems"]}')
        tree = getattr(self, 'final_fortress_perks_tree', None)
        if tree is not None:
            from randomizer.final_fortress.perks import ranks, owned_rank, next_price
            selection = tree.selection()
            for perk in config['perks']:
                key = perk['id']
                rank = owned_rank(state, key)
                status = ('Enabled' if key in state['selected_perks'] else 'Disabled'
                          if rank else 'Not purchased')
                price = next_price(perk, rank)
                values = (perk['display_name'], f'{price} Defensive Points' if price is not None else 'MAX',
                          f'{rank}/{len(ranks(perk))} · {status}', perk['description'])
                if tree.exists(key):
                    tree.item(key, values=values)
                else:
                    tree.insert('', 'end', iid=key, values=values)
            if not selection and tree.get_children():
                tree.selection_set(tree.get_children()[0])
            self.select_final_fortress_perk()
        challenge_tree = getattr(self, 'final_fortress_challenge_tree', None)
        if challenge_tree is not None:
            initial = not challenge_tree.get_children()
            for entry in config.get('challenges', []):
                key = entry['id']
                stacks = min(preferences['challenge_stacks'].get(key, 1), maximum(entry))
                process = getattr(self, 'active_game_process', None)
                busy = self._final_fortress_preparing or (process is not None and process.poll() is None)
                values = ('Yes' if key in preferences['selected_challenges'] else 'No',
                          label(entry), '◀' if stacks > 1 and not busy else '', stacks,
                          '▶' if stacks < maximum(entry) and not busy else '',
                          stacks * entry.get('victory_gems_per_stack', entry.get('victory_gems', 0)),
                          description(entry, stacks))
                if challenge_tree.exists(key):
                    challenge_tree.item(key, values=values)
                else:
                    challenge_tree.insert('', 'end', iid=key, values=values)
            if initial and challenge_tree.get_children():
                challenge_tree.selection_set(challenge_tree.get_children()[0])
            self.select_final_fortress_challenge()
        total = 0
        milestones = []
        for milestone in sorted(config['milestones'], key=lambda entry: entry['seconds']):
            total += milestone['gems']
            milestones.append(f'{total} total Defensive Points at {milestone["seconds"] / 60:g} minutes')
        total += settings['completion_gems'] or 0
        milestones.append(f'{total} total Defensive Points on victory, plus enabled Challenge bonuses')
        rules.extend([
            'The periodic reinforcement perk adds a Next allied reinforcements countdown for each human. '
            'Its next interval starts after that player receives the complete arrival; capacity can delay delivery.',
            'The Faction offensive superweapons Challenge grants real enemy powers through hidden launch providers. '
            'No visible silo is required. Disable that Challenge before a new run to remove those powers. '
            'Hidden providers no longer announce newly discovered superweapon buildings.',
            'Survival rewards: ' + '; '.join(milestones) + '. Balance is provisional and configurable.',
            'Collect crates at stationary enemy camp centers; defeating their guards is optional. '
            'Each camp grants Defensive Points and a random credit, squad, or faction special-unit reward. '
            'Enemy and helper AI collect for the player; in co-op, AI pickups deliver cash/squads to the host. '
            'Each crate awards its reward and Defensive Points once. Crate rewards are frozen for each run.',
            'Perk purchases and upgrades enable that perk automatically for subsequent runs. '
            'Challenge uses Grid enemy stat and production buffs, excluding vision, sensors and defense buffs. '
            'Drag or Shift-click to select a range; '
            'Ctrl/Alt-click adds or removes individual rows; Select all or Ctrl+A selects every modifier. '
            'Enable selected, Disable selected and Max stacks apply to the selected group. '
            'Clear selection or Escape deselects all rows. '
            'Double-click, Space or Enter enables a mixed group, or disables a fully enabled group. '
            'Inline arrows change only their own row; Max stacks does not enable disabled modifiers. '
            'Each stack adds its configured victory Defensive Points.',
        ])
        if config['map'] and config['map']['camps']:
            if config.get('camp_balance'):
                balance = config['camp_balance']
                rules.append('Camp Defensive Points and cash/unit rewards are awarded when any unit collects '
                             'the crate; enemy and helper AI pickups count for the player. '
                             f'Outer guards: {balance["guards_by_difficulty"][preferences["difficulty"]]} base × '
                             f'{preferences["wave_multiplier"]}, capped at {balance["max_guards_per_camp"]} '
                             f'per camp and {balance["max_total_guards"]} total. '
                             'Camp rosters cover Allies, Soviets, Epsilon and Foehn independently of enemy bases. '
                             f'Outer groups have a {balance["special_chance_percent"]}% chance of a hero or heavy.')
                starter = balance.get('starter_camps')
                if starter:
                    rules.append('Nearby starter camps use basic infantry only, without vehicles, artillery or heroes: '
                                 f'{starter["guards_by_difficulty"][preferences["difficulty"]]} base × '
                                 f'{preferences["wave_multiplier"]}, capped at '
                                 f'{starter["max_guards_by_difficulty"][preferences["difficulty"]]} guards. '
                                 'Their normal Defensive Points and random crate rewards are retained.')
            rules.append('Camp centers: ' + '; '.join(
                f'{camp["display_name"]} ({camp["position"]["x"]}, {camp["position"]["y"]}), '
                f'{camp["gems"]} Defensive Points' for camp in config['map']['camps']
                if 'position' in camp) + '.')
        if config.get('crate_rewards'):
            weight = sum(entry['weight'] for entry in config['crate_rewards'])
            rules.append('Random crate rewards: ' + '; '.join(
                f'{entry["display_name"]} ({entry["weight"] / weight:.0%})'
                for entry in config['crate_rewards']) + '.')
        performance = config.get('performance')
        if performance:
            rules.append(f'Combined player and allied combat kills award '
                         f'{performance["gems_per_tier"]} Defensive Points per {performance["units_per_tier"]} kills, '
                         f'capped at {performance["gems_per_tier"] * performance["max_tiers"]} Defensive Points '
                         f'({performance["units_per_tier"] * performance["max_tiers"]:,} kills), '
                         'after a verified victory or defeat. Setup ownership transfers are excluded. '
                         'Closing an unfinished game grants no kill bonus.')
        self.final_fortress_help_var.set('\n\n'.join(rules))
        blockers = []
        try:
            inspect_map(GAME_ROOT, config['map'])
        except (OSError, ValueError) as exc:
            blockers.append(str(exc))
        blockers.extend(configuration_gaps(config, preferences['difficulty'],
                                            preferences['wave_multiplier']))
        if preferences['player_country'] is None:
            blockers.append('Choose your player faction.')
        for executable in (GAME_EXE, GAME_LAUNCHER_EXE):
            if not executable.is_file():
                blockers.append(f'Missing launch executable: {executable.name}.')
        self._final_fortress_launch_blockers = blockers
        process = getattr(self, 'active_game_process', None)
        busy = self._final_fortress_preparing or (process is not None and process.poll() is None)
        if hasattr(self, 'final_fortress_profile_combo'):
            self.final_fortress_profile_combo.configure(
                state='disabled' if busy or self._final_fortress_watch is not None else 'readonly')
        status = ('Preparing game…' if self._final_fortress_preparing else 'Game running.' if busy
                  else 'Choose your faction.' if preferences['player_country'] is None
                  else 'Cannot launch: ' + '; '.join(blockers) if blockers
                  else f'Ready — defend for {settings["survival_seconds"] / 60:g} in-game minutes.')
        run = state.get('run')
        if not busy and not blockers and run and run['status'] != 'active':
            outcome = {'victory': 'Victory', 'defeat': 'Defeat',
                       'abandoned': 'Previous run ended without a result'}[run['status']]
            status = outcome + ' — ready for a new run.'
        self.final_fortress_status_var.set(status)
        refresh_results(self, run)
        if hasattr(self, 'final_fortress_launch_button'):
            self.final_fortress_launch_button.configure(state='disabled' if busy or blockers else 'normal')
            self.refresh_fortress_coop_controls()
            if (run and (run['status'] in ('active', 'abandoned') or 'kill_counts' not in run)
                    and not busy
                    and self._final_fortress_watch is None
                    and run['id'] not in self._final_fortress_recovery_checked):
                self._final_fortress_recovery_checked.add(run['id'])
                self.after_idle(self._recover_final_fortress_result)

    def _recover_final_fortress_result(self):
        process = getattr(self, 'active_game_process', None)
        if self._final_fortress_preparing or (process is not None and process.poll() is None):
            return
        if getattr(self, 'busy_depth', 0):
            self.after(200, self._recover_final_fortress_result)
            return
        repository = self.final_fortress_repository

        def finish(result):
            state, changed = result
            if changed:
                self.append_log('Recovered verified Final Fortress result and missing reward receipts.')
                if self.final_fortress_repository.path == repository.path:
                    self.refresh_final_fortress()

        def failed(exc, _detail):
            self.append_log('Final Fortress result recovery failed: ' + str(exc), error=True)

        self.run_in_background('Checking Final Fortress result…', 'Reading native result markers.',
                               lambda: repository.recover_finished_run(DEBUG_LOG), finish, failed)

    def close_launcher(self):
        if (getattr(self, '_final_fortress_preparing', False)
                or getattr(self, '_final_fortress_watch', None) is not None):
            self._close_after_game = True
            self.withdraw()
            return
        return super().close_launcher()

    def launch_final_fortress(self):
        if self._fortress_lobbies:
            return self.launch_fortress_coop()
        if self.final_fortress_coop_var.get():
            return self.open_fortress_coop_dialog()
        self.refresh_final_fortress()
        process = getattr(self, 'active_game_process', None)
        if (self._final_fortress_launch_blockers or self._final_fortress_preparing
                or (process is not None and process.poll() is None)
                or getattr(self, '_coop_busy', False) or getattr(self, '_coop_lobby', None)
                or getattr(self, '_challenge_preparing', False)):
            return
        preferences = dict(self.final_fortress_state['preferences'])
        speed = self.get_selected_game_speed_value()
        self._final_fortress_preparing = True
        self.refresh_final_fortress()
        launch = {}

        def prepare():
            _, rules = installed_rules_registry(synchronous=True)
            command = self.build_command()
            self.begin_direct_game_preparation()
            # The runtime lease prevents this from ending another launcher's run.
            previous = self.final_fortress_repository.load()['run']
            if previous is not None and previous['status'] == 'active':
                self.final_fortress_repository.record_event(previous['id'], 'abandoned')
            state, run_id = self.final_fortress_repository.begin_run(
                self.final_fortress_config, difficulty=preferences['difficulty'],
                seed='FF-' + secrets.token_hex(8), player_country=preferences['player_country'],
                wave_multiplier=preferences['wave_multiplier'],
                mental_ai_boost=preferences['mental_ai_boost'])
            launch['run_id'] = run_id
            digest = prepare_game(GAME_ROOT, state['run'], rules, game_speed=speed)
            return run_id, digest, command

        def finish(result):
            run_id, digest, command = result
            watch = FinalFortressResultWatch(DEBUG_LOG, run_id, self.final_fortress_repository.load()['run']['plan'])
            shutdown = GameShutdownWatch(DEBUG_LOG)
            process, _ = self.spawn_game_process(command)
            shutdown.bind(process)
            self.active_game_process = process
            self._final_fortress_watch = watch
            self._final_fortress_shutdown = shutdown
            self._final_fortress_logged_waves = 0
            self._final_fortress_recorded_events = set()
            self._final_fortress_recorded_kills = None
            self._final_fortress_preparing = False
            self.append_log(f'Final Fortress started: run {run_id}; map {digest}.')
            self.refresh_game_speed_controls()
            self.refresh_final_fortress()
            self.after(500, self._poll_final_fortress_game)

        def failed(exc, detail):
            self._final_fortress_preparing = False
            run_id = launch.get('run_id')
            if run_id:
                try:
                    self.final_fortress_repository.record_event(run_id, 'abandoned')
                except (ValueError, FinalFortressPersistenceError) as save_error:
                    self.append_log(str(save_error), error=True)
            self.disable_generated_rules_for_client()
            self.append_log(detail, error=True)
            self.refresh_final_fortress()
            if getattr(self, '_close_after_game', False):
                self.close_launcher()
            else:
                messagebox.showerror(DISPLAY_NAME, f'Launch failed: {exc}', parent=self)

        self.run_in_background('Starting Final Fortress…', 'Preparing survival map and skirmish AI.',
                               prepare, finish, failed)

    def _poll_final_fortress_game(self):
        watch = self._final_fortress_watch
        process = self.active_game_process
        shutdown = self._final_fortress_shutdown
        running = process is not None and process.poll() is None
        outcome = watch.poll()
        pending = [event for event in watch.events
                   if event not in self._final_fortress_recorded_events and not event.startswith('kills:')]
        if outcome and outcome not in self._final_fortress_recorded_events:
            pending.append(outcome)
        pending.extend(event for event in watch.events
                       if event not in self._final_fortress_recorded_events and event.startswith('kills:'))
        counts = watch.kill_counts if outcome in ('victory', 'defeat') else None
        if pending or counts != self._final_fortress_recorded_kills:
            try:
                state, credited = self.final_fortress_repository.record_events(
                    watch.run_id, pending, kill_counts=counts)
                self._final_fortress_recorded_events.update(pending)
                self._final_fortress_recorded_kills = counts
                if credited:
                    self.final_fortress_gems_var.set(f'Defensive Points: {state["gems"]}')
                    self.append_log('Final Fortress receipts: ' + ', '.join(pending) + '.' if pending
                                    else 'Final Fortress kill statistics saved.')
                    refresh_results(self, state['run'])
            except (ValueError, FinalFortressPersistenceError) as exc:
                self.append_log('Final Fortress reward save failed: ' + str(exc), error=True)
        for wave in watch.waves[self._final_fortress_logged_waves:]:
            self.append_log(f'Final Fortress wave {wave} admitted.')
        self._final_fortress_logged_waves = len(watch.waves)
        for text, error in shutdown.poll(process):
            self.append_log(text, error=error)
        if (running and watch.ready_to_close and shutdown.caught_up
                and outcome in self._final_fortress_recorded_events
                and counts == self._final_fortress_recorded_kills
                and all(event in self._final_fortress_recorded_events for event in watch.events)):
            shutdown.request_result_close()
        if running or shutdown.recovery_pending or not watch.caught_up:
            self.after(10 if not watch.caught_up or not shutdown.caught_up else 500,
                       self._poll_final_fortress_game)
            return
        if not outcome:
            try:
                self.final_fortress_repository.record_event(watch.run_id, 'abandoned')
            except (ValueError, FinalFortressPersistenceError) as exc:
                self.append_log(str(exc), error=True)
        shutdown.close()
        self.active_game_process = None
        self._final_fortress_watch = None
        self._final_fortress_shutdown = None
        self.disable_generated_rules_for_client()
        self.fortress_coop_game_finished(watch.run_id)
        self.refresh_game_speed_controls()
        self.refresh_final_fortress()
        if getattr(self, '_close_after_game', False):
            self.close_launcher()

    def show_final_fortress_help(self, page='How to play'):
        show_final_fortress_help(self, page)

    def _final_fortress_action(self, action):
        process = getattr(self, 'active_game_process', None)
        if self._final_fortress_preparing or (process is not None and process.poll() is None):
            self.refresh_final_fortress()
            return
        try:
            action()
        except (ValueError, FinalFortressPersistenceError) as exc:
            messagebox.showerror(DISPLAY_NAME, str(exc), parent=self)
        self.refresh_final_fortress()

    def on_final_fortress_map_changed(self, _event=None):
        if self.fortress_coop_guest():
            self.refresh_final_fortress()
            return
        selected = self.final_fortress_map_var.get()
        definition = next(entry for entry in map_definitions(self.final_fortress_map_catalogue)
                          if entry['display_name'] == selected)
        self._final_fortress_action(lambda: self.final_fortress_repository.set_map(
            self.final_fortress_map_catalogue, definition['id']))
        if self._fortress_lobbies:
            self._publish_fortress_roster()

    def on_final_fortress_country_changed(self, _event=None):
        country = self.final_fortress_country_choices[self.final_fortress_country_var.get()]
        self._final_fortress_action(lambda: self.final_fortress_repository.set_player_country(country))

    def buy_final_fortress_perk(self):
        selection = self.final_fortress_perks_tree.selection()
        if selection:
            self._final_fortress_action(lambda: self.final_fortress_repository.purchase_perk(
                self.final_fortress_config, selection[0]))

    def select_final_fortress_perk(self, _event=None):
        from randomizer.final_fortress.perks import ranks, owned_rank, next_price
        from randomizer.final_fortress.perk_descriptions import rank_descriptions
        from randomizer.final_fortress.ui import show_perk_details
        selection = self.final_fortress_perks_tree.selection()
        state = self.final_fortress_state
        if not selection or state is None:
            show_perk_details(self, 'Select a perk to see its ranks.')
            self.final_fortress_buy_perk_button.configure(state='disabled')
            self.final_fortress_toggle_perk_button.configure(state='disabled')
            return
        perk = next(entry for entry in self.final_fortress_config['perks'] if entry['id'] == selection[0])
        rank = owned_rank(state, perk['id'])
        price = next_price(perk, rank)
        process = getattr(self, 'active_game_process', None)
        busy = self._final_fortress_preparing or (process is not None and process.poll() is None)
        enabled = perk['id'] in state['selected_perks']
        show_perk_details(self, rank_descriptions(perk, state['preferences']['player_country']))
        self.final_fortress_buy_perk_button.configure(
            text='Maximum rank' if price is None else 'Upgrade' if rank else 'Buy',
            state='disabled' if busy or price is None or state['gems'] < price else 'normal')
        self.final_fortress_toggle_perk_button.configure(
            text='Disable perk' if enabled else 'Enable perk',
            state='normal' if rank and not busy else 'disabled')

    def toggle_final_fortress_perk(self):
        selection = self.final_fortress_perks_tree.selection()
        if selection:
            key = selection[0]
            self._final_fortress_action(lambda: self.final_fortress_repository.select_perk(
                key, key not in self.final_fortress_state['selected_perks']))

    def select_final_fortress_challenge(self, _event=None):
        from randomizer.final_fortress.ui import show_challenge_details
        selection = self.final_fortress_challenge_tree.selection()
        if not selection or self.final_fortress_state is None:
            show_challenge_details(self, 'Select a modifier to see its full effect.')
            for button in (self.final_fortress_stack_max_button,
                           self.final_fortress_challenge_enable_button,
                           self.final_fortress_challenge_disable_button):
                button.configure(state='disabled')
            return
        preferences = self.final_fortress_state['preferences']
        entries = [entry for entry in self.final_fortress_config['challenges'] if entry['id'] in selection]
        effects = [description(entry, min(maximum(entry), preferences['challenge_stacks'].get(entry['id'], 1)))
                   for entry in entries]
        show_challenge_details(self, effects[0] if len(entries) == 1 else
                               f'{len(entries)} modifiers selected\n\n' + '\n\n'.join(
                                   f'{label(entry)}: {effect}' for entry, effect in zip(entries, effects)))
        process = getattr(self, 'active_game_process', None)
        busy = self._final_fortress_preparing or (process is not None and process.poll() is None)
        self.final_fortress_stack_max_button.configure(
            state='normal' if not busy and any(preferences['challenge_stacks'].get(entry['id'], 1)
                                               < maximum(entry) for entry in entries) else 'disabled')
        self.final_fortress_challenge_enable_button.configure(
            state='normal' if not busy and any(entry['id'] not in preferences['selected_challenges']
                                               for entry in entries) else 'disabled')
        self.final_fortress_challenge_disable_button.configure(
            state='normal' if not busy and any(entry['id'] in preferences['selected_challenges']
                                               for entry in entries) else 'disabled')

    def on_final_fortress_challenge_click(self, event, *, additive=False):
        tree = self.final_fortress_challenge_tree
        self._final_fortress_challenge_drag = None
        if tree.identify_region(event.x, event.y) != 'cell':
            return
        key = tree.identify_row(event.y)
        column = tree.column(tree.identify_column(event.x), 'id')
        if not key:
            return
        selected = tree.selection()
        if column not in ('decrease', 'increase'):
            anchor = tree.focus() if event.state & 1 else key
            extending = additive or bool(event.state & 4)
            self._final_fortress_challenge_drag = (
                anchor or key, selected if extending else (),
                extending and key in selected, False)
            if additive:
                self._final_fortress_challenge_click_selection = None
                tree.selection_toggle(key)
            else:
                # Let a normal click reduce even an all-row selection. Save
                # the group so a subsequent double-click can still toggle it.
                self._final_fortress_challenge_click_selection = (
                    (key, selected) if key in selected and not event.state & 5 else None)
                return
            tree.focus(key)
            tree.focus_set()
            return 'break'
        if key not in selected:
            tree.selection_set(key)
        self._final_fortress_challenge_click_selection = None
        tree.focus(key)
        tree.focus_set()
        self._set_final_fortress_challenge_stacks(
            delta=-1 if column == 'decrease' else 1, keys=(key,))
        return 'break'

    def drag_final_fortress_challenges(self, event):
        drag = getattr(self, '_final_fortress_challenge_drag', None)
        if drag is None:
            return
        tree = self.final_fortress_challenge_tree
        if event.y < 0:
            tree.yview_scroll(-1, 'units')
        elif event.y >= tree.winfo_height():
            tree.yview_scroll(1, 'units')
        key = tree.identify_row(max(0, min(event.y, tree.winfo_height() - 1)))
        anchor, previous, removing, moved = drag
        children = tree.get_children()
        if key and anchor in children:
            if key == anchor and not moved:
                return 'break'
            self._final_fortress_challenge_drag = (anchor, previous, removing, True)
            self._final_fortress_challenge_click_selection = None
            first, last = sorted((children.index(anchor), children.index(key)))
            span = children[first:last + 1]
            chosen = set(previous) - set(span) if removing else set(previous) | set(span)
            tree.selection_set([child for child in children if child in chosen])
            tree.focus(key)
        return 'break'

    def end_final_fortress_challenge_drag(self, _event=None):
        self._final_fortress_challenge_drag = None

    def select_all_final_fortress_challenges(self, _event=None):
        tree = self.final_fortress_challenge_tree
        self._final_fortress_challenge_click_selection = None
        children = tree.get_children()
        tree.selection_set(children)
        if children and not tree.focus():
            tree.focus(children[0])
        tree.focus_set()
        self.select_final_fortress_challenge()
        return 'break'

    def set_final_fortress_challenges_enabled(self, enabled):
        self._update_final_fortress_challenges(enabled=enabled)

    def clear_final_fortress_challenge_selection(self, _event=None):
        tree = self.final_fortress_challenge_tree
        tree.selection_remove(tree.selection())
        self._final_fortress_challenge_drag = None
        self._final_fortress_challenge_click_selection = None
        self.select_final_fortress_challenge()
        return 'break'

    def change_final_fortress_challenge_stacks(self, delta):
        self._set_final_fortress_challenge_stacks(delta=delta)

    def max_final_fortress_challenge_stacks(self):
        self._set_final_fortress_challenge_stacks()

    def _set_final_fortress_challenge_stacks(self, *, delta=None, keys=None):
        self._update_final_fortress_challenges(delta=delta, max_stacks=delta is None, keys=keys)

    def _update_final_fortress_challenges(self, *, enabled=None, delta=None, max_stacks=False, keys=None):
        selection = self.final_fortress_challenge_tree.selection() if keys is None else keys
        if not selection or self.final_fortress_state is None:
            return
        preferences = self.final_fortress_state['preferences']
        choices = {}
        for entry in self.final_fortress_config['challenges']:
            key = entry['id']
            if key not in selection:
                continue
            limit = maximum(entry)
            current = min(limit, preferences['challenge_stacks'].get(key, 1))
            selected = key in preferences['selected_challenges']
            stacks = limit if max_stacks else min(limit, max(1, current + (delta or 0)))
            chosen = selected if enabled is None else enabled
            if stacks != current or chosen != selected:
                choices[key] = (chosen, stacks)
        if choices:
            self._final_fortress_action(lambda: self.final_fortress_repository.select_challenges(
                self.final_fortress_config, choices))

    def toggle_final_fortress_challenge(self, event=None):
        tree = self.final_fortress_challenge_tree
        if event is not None and getattr(event, 'num', None) == 1:
            if tree.identify_region(event.x, event.y) != 'cell':
                return 'break'
            column = tree.column(tree.identify_column(event.x), 'id')
            if column in ('decrease', 'increase'):
                # Tk dispatches the second rapid click as Double-1. Keep it
                # an adjustment, never a modifier enable/disable gesture.
                return self.on_final_fortress_challenge_click(event)
            key = tree.identify_row(event.y)
            if not key:
                return 'break'
            previous = getattr(self, '_final_fortress_challenge_click_selection', None)
            if previous and previous[0] == key:
                tree.selection_set(previous[1])
            self._final_fortress_challenge_click_selection = None
            if key not in tree.selection():
                tree.selection_set(key)
        if not tree.selection() or self.final_fortress_state is None:
            return 'break'
        preferences = self.final_fortress_state['preferences']
        # A mixed group enables together; an entirely enabled group disables.
        self.set_final_fortress_challenges_enabled(any(
            key not in preferences['selected_challenges'] for key in tree.selection()))
        return 'break'

    def on_final_fortress_difficulty_changed(self, _event=None):
        difficulty = self.final_fortress_difficulty_choices[self.final_fortress_difficulty_var.get()]
        self._final_fortress_action(lambda: self.final_fortress_repository.set_difficulty(difficulty))

    def on_final_fortress_mental_ai_boost_changed(self):
        enabled = self.final_fortress_mental_ai_boost_var.get()
        self._final_fortress_action(lambda: self.final_fortress_repository.set_mental_ai_boost(enabled))

    def on_final_fortress_wave_multiplier_changed(self, _event=None):
        multiplier = self.final_fortress_wave_multiplier_choices[
            self.final_fortress_wave_multiplier_var.get()]
        self._final_fortress_action(
            lambda: self.final_fortress_repository.set_wave_multiplier(multiplier))
