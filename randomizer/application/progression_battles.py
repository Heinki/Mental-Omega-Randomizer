"""Optional progression skirmishes and normal story order for Shop runs."""

from copy import deepcopy
import tkinter as tk
from tkinter import messagebox, ttk

from randomizer.config.player import save_config
from randomizer.core.paths import GAME_ROOT
from randomizer.shop.transitions import ShopTransitionError
from randomizer.ui.config import CAMPAIGN_FILTERS


class ProgressionBattlesController:
    def build_classic_shop_controls(self, parent):
        campaigns = [name for name in CAMPAIGN_FILTERS if name != 'All Campaigns']
        saved = self.config.get('classic_shop_campaign')
        self.classic_shop_var = tk.BooleanVar(self, value=bool(self.config.get('classic_shop', False)))
        self.classic_shop_campaign_var = tk.StringVar(
            self, value=saved if saved in campaigns else campaigns[0])
        frame = ttk.LabelFrame(parent, text='Classic Shop Mode', padding=8)
        frame.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(0, 12))
        frame.columnconfigure(1, weight=1)
        ttk.Checkbutton(frame, text='Classic Shop Mode (next run)',
                        variable=self.classic_shop_var,
                        command=self.save_classic_shop_options).grid(
                            row=0, column=0, columnspan=2, sticky='w')
        ttk.Label(frame, text='Campaign to play').grid(row=1, column=0, sticky='w', padx=(0, 12), pady=6)
        self.classic_shop_campaign_combo = ttk.Combobox(
            frame, values=campaigns, state='readonly',
            textvariable=self.classic_shop_campaign_var, width=28)
        self.classic_shop_campaign_combo.grid(row=1, column=1, sticky='ew', pady=6)
        self.classic_shop_campaign_combo.bind('<<ComboboxSelected>>', self.save_classic_shop_options)
        ttk.Label(frame, text=(
            'Play ALL missions in the selected campaign, one by one from start to finish in story order. '
            'The normal Shop stage limit does not apply to campaign runs. '
            'This changes only the missions and their order. Normal Shop Mode starting loadout, '
            'Ore, Gems, purchases, buffs, modifiers, victory rewards and defeat rules stay the same. '
            'Purchases and buffs carry between missions under the normal Shop rules. '
            'Optional 1v1 Skirmishes are included between story missions when enabled. '
            'Applies to the next run; an active run keeps its saved mission pool.'
        ), style='Muted.TLabel', justify='left', wraplength=900).grid(
            row=2, column=0, columnspan=2, sticky='ew')
        self.classic_shop_length_var = tk.StringVar(self)
        ttk.Label(frame, textvariable=self.classic_shop_length_var, style='Muted.TLabel',
                  wraplength=900).grid(row=3, column=0, columnspan=2, sticky='ew', pady=(6, 0))
        self.refresh_classic_shop_summary()

    def next_shop_run_length(self):
        variable = getattr(self, 'classic_shop_var', None)
        if variable is None or not variable.get():
            return self.shop_config.run_length
        if not getattr(self, 'missions', None):
            return 0
        try:
            return len(self.classic_shop_order(self._shop_run_mission_pool(), ()))
        except ShopTransitionError:
            return 0

    def refresh_classic_shop_summary(self):
        if not hasattr(self, 'classic_shop_length_var'):
            return
        count = self.next_shop_run_length()
        if self.classic_shop_var.get():
            total = f' {count} total battles.' if count else ''
            self.classic_shop_length_var.set(
                'Campaign run: ALL missions, one by one, in story order.'
                + total + ' No stage cap. Enabled Skirmishes add extra battles.')
        else:
            self.classic_shop_length_var.set(
                f'Normal Shop run: {self.shop_config.run_length} stages. '
                'Enable Classic Shop Mode to play the entire selected campaign without a stage cap.')
        if getattr(self, 'shop_run', None) is None and hasattr(self, 'shop_stage_var'):
            self.shop_stage_var.set(f'Stage — / {count}' if count else 'Campaign: ALL missions')


    def current_reward_settings(self):
        settings = dict(super().current_reward_settings())
        variable = getattr(self, 'include_skirmishes_var', None)
        settings['include_skirmishes'] = bool(variable.get() if variable is not None
                                             else self.config.get('include_skirmishes', False))
        return settings

    def save_classic_shop_options(self, _event=None):
        self.config['classic_shop'] = bool(self.classic_shop_var.get())
        self.config['classic_shop_campaign'] = self.classic_shop_campaign_var.get()
        save_config(self.config)
        if hasattr(self, 'shop_loadout_help_var'):
            self._refresh_shop_setup()
        self.refresh_classic_shop_summary()

    def apply_portable_settings(self, config):
        result = super().apply_portable_settings(config)
        self.include_skirmishes_var.set(bool(self.config.get('include_skirmishes', False)))
        self.classic_shop_var.set(bool(self.config.get('classic_shop', False)))
        campaign = self.config.get('classic_shop_campaign', CAMPAIGN_FILTERS[1])
        self.classic_shop_campaign_var.set(campaign if campaign in CAMPAIGN_FILTERS[1:] else CAMPAIGN_FILTERS[1])
        color = self.config.get('final_fortress_color', 'Default')
        self.fortress_color_var.set(color if color in self.fortress_color_values else 'Default')
        self.refresh_classic_shop_summary()
        return result

    def classic_shop_order(self, pool, modifiers):
        if not self.classic_shop_var.get():
            return ()
        if self.archipelago_run_active() or self.coop_mode_var.get():
            raise ShopTransitionError('Classic Shop requires a standalone campaign run')
        if not pool:
            raise ShopTransitionError('No campaign missions exist for Classic Shop')
        from randomizer.missions.catalogue import classic_mission_order
        story = [mission for mission in pool if not mission.get('skirmish')]
        order = classic_mission_order(story, len(story))
        skirmishes = iter(mission['code'] for mission in pool if mission.get('skirmish'))
        combined = []
        for index, code in enumerate(order, 1):
            combined.append(code)
            if index % 3 == 0 and index < len(order):
                extra = next(skirmishes, None)
                if extra:
                    combined.append(extra)
        return tuple(combined)

    def _shop_run_mission_pool(self, run=None):
        if run is None and getattr(self, 'classic_shop_var', None) and self.classic_shop_var.get():
            campaign = self.classic_shop_campaign_var.get()
            story_missions = [mission for mission in self.missions
                              if not mission.get('skirmish') and not mission.get('coop_name')
                              and not mission.get('challenge_name')
                              and mission.get('mission_category') != 'challenge']
            if campaign not in CAMPAIGN_FILTERS[1:]:
                raise ShopTransitionError('Choose a Classic Shop campaign')
            from . import _dependencies
            matches = (getattr(_dependencies, 'mission_matches_campaign_filter', None)
                       or getattr(_dependencies, 'mission_matches_campaign', None))
            if matches is not None:
                missions = [mission for mission in story_missions
                            if not mission.get('skirmish') and (campaign == CAMPAIGN_FILTERS[0] or matches(mission, campaign))]
                return self._with_skirmish_pool(missions, 'Shop Mode', campaign)
            from randomizer.missions.catalogue import normalize_faction
            missions = [mission for mission in story_missions
                        if not mission.get('skirmish') and not mission.get('coop_name') and (campaign == CAMPAIGN_FILTERS[0]
                            or normalize_faction(mission.get('side', '')) == campaign)]
            return self._with_skirmish_pool(missions, 'Shop Mode', campaign)
        missions = super()._shop_run_mission_pool(run)
        if run is not None:
            return missions
        return self._with_skirmish_pool(missions, 'Shop Mode', self.shop_campaign_filter())

    def build_fortress_color_control(self, title):
        from randomizer.skirmish import multiplayer_colors
        self.fortress_color_values = multiplayer_colors(GAME_ROOT)
        choices = ('Default', *self.fortress_color_values)
        selected = self.config.get('final_fortress_color', 'Default')
        self.fortress_color_var = tk.StringVar(self, value=selected if selected in choices else 'Default')
        row = ttk.Frame(title)
        row.grid(row=3, column=0, columnspan=3, sticky='w', pady=(6, 0))
        ttk.Label(row, text='Player color').pack(side='left', padx=(0, 8))
        combo = ttk.Combobox(row, state='readonly', values=choices,
                             textvariable=self.fortress_color_var, width=18)
        combo.pack(side='left')
        combo.bind('<<ComboboxSelected>>', self.save_fortress_color)

    def save_fortress_color(self, _event=None):
        self.config['final_fortress_color'] = self.fortress_color_var.get()
        save_config(self.config)

    def selected_fortress_color(self):
        return self.fortress_color_values.get(self.fortress_color_var.get())

    def initialize_skirmish_pool_settings(self):
        if not hasattr(self, 'include_skirmishes_var'):
            self.include_skirmishes_var = tk.BooleanVar(
                self, value=bool(self.config.get('include_skirmishes', False)))

    def build_skirmish_pool_control(self, parent, *, row, shop=False):
        from randomizer.ui.tooltips import WidgetTooltip
        self.initialize_skirmish_pool_settings()
        checkbox = ttk.Checkbutton(
            parent, text='Include 1v1 skirmish maps',
            variable=self.include_skirmishes_var,
            command=self.on_skirmish_pool_changed)
        checkbox.grid(row=row, column=0, columnspan=3, sticky='w', pady=(5, 0))
        checkbox._skirmish_pool_tooltip = WidgetTooltip(
            checkbox,
            'Adds installed skirmish maps to the next Shop mission pool or Grid nodes. '
            'Each battle is one human versus one AI and uses the run’s unlocked units, '
            'powers, purchased buffs and normal reward rules. Available in standalone '
            'Shop/Grid runs. Existing runs keep their generated mission pool.')
        name = 'shop_include_skirmishes_check' if shop else 'include_skirmishes_check'
        setattr(self, name, checkbox)
        self.refresh_skirmish_pool_controls()

    def refresh_skirmish_pool_controls(self):
        catalogue = getattr(self, '_skirmish_catalogue', None)
        count = len({mission['scenario'] for mission in catalogue}) if catalogue is not None else None
        text = 'Include 1v1 skirmish maps'
        if count is not None:
            text += f' ({count} installed)'
        for name in ('include_skirmishes_check', 'shop_include_skirmishes_check'):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.configure(text=text)

    def on_skirmish_pool_changed(self):
        self.config['include_skirmishes'] = bool(self.include_skirmishes_var.get())
        save_config(self.config)
        self.refresh_classic_shop_summary()
        self.refresh_skirmish_pool_controls()
        self.update_mission_goal_limit()
        self.redraw_mission_tree()
        self.append_log('Skirmish selection applies to the next Shop/Grid run; existing runs keep their saved mission pool.')

    def load_missions(self, *args, **kwargs):
        from randomizer.skirmish_progression import mission_catalogue
        missions = list(super().load_missions(*args, **kwargs))
        catalogue = mission_catalogue(GAME_ROOT)
        self._skirmish_catalogue = catalogue
        return missions + catalogue

    def apply_missions(self, missions):
        missions = list(missions)
        known = {mission['code'] for mission in missions}
        missions.extend(mission for mission in getattr(self, '_skirmish_catalogue', ())
                        if mission['code'] not in known)
        result = super().apply_missions(missions)
        self.refresh_classic_shop_summary()
        self.refresh_skirmish_pool_controls()
        return result

    def _with_skirmish_pool(self, missions, mode, campaign):
        from randomizer.skirmish_progression import select_pool
        from randomizer.missions.catalogue import normalize_faction
        catalogue = getattr(self, '_skirmish_catalogue', ())
        native = [mission for mission in missions if not mission.get('skirmish')]
        factions = {normalize_faction(mission.get('side', '')) for mission in native} - {''}
        if not factions and campaign != 'All Campaigns':
            from randomizer.missions import catalogue as mission_data
            resolver = getattr(mission_data, 'campaign_filter_factions', None)
            if resolver is not None:
                factions = set(resolver(campaign))
            else:
                resolver = getattr(mission_data, 'campaign_factions', None)
                if resolver is not None:
                    factions = set(resolver([mission for mission in self.missions
                                            if not mission.get('skirmish')], campaign))
                else:
                    faction = normalize_faction(campaign)
                    factions = {faction} if faction else set()
        # Shop faction pools and individual campaign selections can differ.
        if campaign in {'GDI', 'Nod', 'Allies', 'Soviet', 'Soviets', 'Yuri', 'Epsilon', 'Foehn'}:
            factions = {campaign}
        enabled = bool(self.include_skirmishes_var.get() and mode in ('Shop Mode', 'Grid Mode')
                       and not self.coop_mode_var.get() and not self.archipelago_run_active())
        return select_pool(native, catalogue, enabled=enabled, factions=factions,
                           excluded=getattr(self, 'excluded_mission_codes', ()))

    def filtered_missions_for_seed(self):
        missions = super().filtered_missions_for_seed()
        return self._with_skirmish_pool(missions, self.progression_mode_var.get(), self.campaign_var.get())

    def visible_missions(self):
        visible = super().visible_missions()
        if self.state:
            return visible
        eligible = {mission['code'] for mission in self.filtered_missions_for_seed()}
        return [(index, mission) for index, mission in visible
                if not mission.get('skirmish') or mission['code'] in eligible]

    def launch_mission_async(self, mission, *args, **kwargs):
        if getattr(self, '_skirmish_busy', False):
            self.append_log('Close the current Skirmish before launching a mission.', error=True)
            return
        if mission.get('skirmish'):
            return self.launch_progression_skirmish(mission)
        return super().launch_mission_async(mission, *args, **kwargs)

    def launch_final_fortress(self):
        if getattr(self, '_skirmish_busy', False):
            return
        return super().launch_final_fortress()

    def on_new_seed(self):
        if getattr(self, '_skirmish_busy', False):
            return
        return super().on_new_seed()

    def poll_hook_log(self):
        if getattr(self, '_skirmish_busy', False):
            return
        return super().poll_hook_log()

    def launch_progression_skirmish(self, mission):
        from randomizer.core.paths import DEBUG_LOG
        from randomizer.skirmish import GAME, multiplayer_colors, prepare_game
        from randomizer.skirmish_progression import SkirmishResultWatch
        process = getattr(self, 'active_game_process', None)
        if process is not None and process.poll() is None:
            return
        code, country = mission['code'], mission['skirmish_country']
        definition = deepcopy(mission['skirmish_map'])
        definition['path'] = str(GAME_ROOT / definition['path'])
        shop = self.shop_launch_active()
        if shop:
            run = self._shop_launch_run
            if not run.mission_committed or run.selected_mission_code != code:
                raise ShopTransitionError('Commit the offered Skirmish before launching')
        state = self.state
        if not shop and (not state or code not in state.get('mission_order', ())):
            messagebox.showwarning('Skirmish Locked', 'Generate a Shop/Grid run containing this Skirmish first.', parent=self)
            return
        seed = str(self.active_launch_seed())
        rewards = deepcopy(self.launch_rewards_for_mission(code))
        settings = deepcopy(self.active_reward_settings())
        settings['_skirmish_reward_mode'] = self.active_reward_mode()
        settings['_skirmish_share_buffs'] = bool(self.share_chaos_role_buffs_enabled())
        settings['_skirmish_starter_units'] = list(self.active_starting_tier_one_unit_ids())
        settings['_skirmish_starter_defenses'] = list(self.active_starting_tier_one_defense_ids())
        settings['_skirmish_access'] = []
        if shop:
            from randomizer.shop.active import active_shop_tech_ids
            settings['_skirmish_access'] = sorted(active_shop_tech_ids(run))
        speed = self.get_selected_game_speed_value()
        randomize = self.randomize_unit_access_enabled()
        colors = multiplayer_colors(GAME_ROOT)
        color = colors.get(self.player_color_var.get(), next(iter(colors.values())))
        difficulty = self.get_selected_difficulty_value()
        if GAME == 'dta':
            difficulty = self.resolve_selected_mission_difficulty(mission).label
        else:
            difficulty = ('Easy', 'Normal', 'Hard')[max(0, min(2, int(difficulty)))]
        self._skirmish_busy = True
        self.active_hook = None
        self.active_mission_attempt = None
        outcome_applied = False

        def prepare():
            command = self.build_command()
            preparation = getattr(self, 'begin_direct_game_preparation', None)
            if preparation:
                preparation()
            else:
                self.disable_generated_rules_for_client()
                self.cleanup_generated_root_maps()
                from randomizer.maps.assets import claim_runtime_asset_lease
                claim_runtime_asset_lease()
            prepare_game(GAME_ROOT, definition, rewards, settings, country=country,
                         color=color, opponents=1, difficulty=difficulty,
                         seed=seed, game_speed=speed, randomize_access=randomize)
            art = getattr(self, 'prepare_direct_game_art', None)
            if art:
                art()
            return command

        def finish(command):
            try:
                self._skirmish_watch = SkirmishResultWatch(DEBUG_LOG)
                spawn = getattr(self, 'spawn_game_process', None)
                if spawn:
                    process, _ = spawn(command)
                else:
                    import os
                    import subprocess
                    environment = os.environ.copy()
                    environment['WINEDLLOVERRIDES'] = ';'.join(filter(None,
                        (environment.get('WINEDLLOVERRIDES', ''), 'ddraw=n,b')))
                    process = subprocess.Popen(command, cwd=GAME_ROOT, env=environment,
                                               start_new_session=os.name != 'nt')
                self.active_game_process = process
                self.append_log(f'Started {mission["title"]}: one human versus one AI; normal progression applies.')
                self.after(1000, poll)
            except Exception as exc:
                failed(exc, str(exc))

        def same_run():
            if shop:
                current = self.shop_repository.load_run()
                return bool(current and current.run_id == run.run_id and current.stage == run.stage)
            return self.state is state and str(state.get('seed', '')) == seed

        def apply_outcome(result):
            nonlocal outcome_applied
            if outcome_applied or not same_run():
                return
            outcome_applied = True
            if result == 'victory':
                self.unlock_mission_check(code, 'victory', 'Verified 1v1 Skirmish victory')
            else:
                self.record_failed_mission_attempt(code, 'Skirmish defeat or closed without victory')

        def cleanup():
            self._skirmish_busy = False
            self.active_game_process = None
            self._skirmish_watch = None
            if shop:
                self.finish_progression_launch_context()
            self.disable_generated_rules_for_client()
            self.refresh_progress_view()
            self.refresh_shop_mode()
            if getattr(self, '_close_after_game', False):
                self.close_launcher()

        def poll():
            running = self.active_game_process.poll() is None
            result = self._skirmish_watch.poll(final=not running)
            if result:
                apply_outcome(result)
            if running:
                self.after(1000, poll)
                return
            if not outcome_applied:
                apply_outcome('defeat')
            if self._skirmish_watch.error:
                self.append_log(self._skirmish_watch.error, error=True)
            cleanup()

        def failed(exc, detail):
            cleanup()
            self.append_log(detail, error=True)
            messagebox.showerror('Progression Skirmish', str(exc), parent=self)

        self.run_in_background('Preparing 1v1 Skirmish…', 'Applying run rules, unlocks and buffs.', prepare, finish, failed)
