"""Persistent state, player configuration, starters, and assistance."""

from ._dependencies import (
    BUFF_TARGETS,
    BUFF_TYPES,
    CHECK_SCHEMA_VERSION,
    DEFAULT_MISSION_GOAL,
    DEFAULT_REWARDS_PER_CHECK,
    MAIN_REWARD_WEIGHT_TYPES,
    POWER_BUFF_TYPES,
    POWER_BUFF_WEIGHT_TYPES,
    REWARD_MODES,
    STANDARD_STARTER_FAMILIES_BY_CAMPAIGN,
    STARTING_UNLOCKED_MISSIONS,
    STATE_PATH,
    atomic_write_json,
    check_rewards,
    clamp_reward_weight,
    create_grid,
    expanded_tier_one_defense_ids,
    expanded_tier_one_unit_ids,
    linked_buff_variant_ids,
    log_event,
    logging,
    normalize_assistance_units,
    normalize_completed_checks,
    normalize_failure_stacks,
    normalize_reward_weights,
    random,
    random_chaos_tier_one_defense_ids,
    random_chaos_tier_one_unit_ids,
    read_json_object,
    refresh_grid_states,
    save_config,
    tier_one_defense_ids,
    tier_one_unit_ids,
    traceback,
    UNIT_BUFF_WEIGHT_TYPES,
)

class StateController:

    def load_state(self):
        if not STATE_PATH.exists():
            return {}
        try:
            return read_json_object(STATE_PATH)
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

        changed = normalize_completed_checks(self.state) or changed
        changed = normalize_failure_stacks(self.state) or changed
        changed = normalize_assistance_units(self.state, BUFF_TARGETS) or changed
        completed = self.state['completed_missions']

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
        atomic_write_json(STATE_PATH, self.state)

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
        include_power_buffs = bool(
            generation_config.get('include_power_buff_rewards', True)
        )
        known_power_buff_type_ids = [
            buff_type['id'] for buff_type in POWER_BUFF_TYPES
        ]
        known_power_buff_types = set(known_power_buff_type_ids)
        enabled_power_buff_types = generation_config.get(
            'enabled_power_buff_types'
        )
        if not isinstance(enabled_power_buff_types, list):
            enabled_power_buff_types = list(known_power_buff_type_ids)
        enabled_power_buff_types = [
            str(buff_type)
            for buff_type in enabled_power_buff_types
            if str(buff_type) in known_power_buff_types
        ]
        include_defensive_buildings = bool(generation_config.get('include_defensive_buildings', True))
        include_special_buildings = bool(generation_config.get('include_special_buildings', True))
        include_special_rewards = bool(generation_config.get('include_special_rewards', True))
        unlimited_hero_units = bool(generation_config.get('unlimited_hero_units', False))
        share_chaos_role_buffs = bool(generation_config.get('share_chaos_role_buffs', False))
        buff_allied_helpers = bool(generation_config.get('buff_allied_helpers', False))
        failure_assistance = bool(generation_config.get('failure_assistance', False))
        reward_weights = normalize_reward_weights(
            generation_config.get('reward_weights')
        )
        if generation_config.get('reward_mode') == 'Chaos (Experimental)':
            randomize_access = True
        return {
            'randomize_unit_access': randomize_access,
            'start_with_tier_one_units': start_with_tier_one_units,
            'start_with_tier_one_defenses': start_with_tier_one_defenses,
            'include_defensive_buildings': include_defensive_buildings,
            'include_special_buildings': include_special_buildings,
            'include_special_rewards': include_special_rewards,
            'unlimited_hero_units': unlimited_hero_units,
            'share_chaos_role_buffs': share_chaos_role_buffs,
            'buff_allied_helpers': buff_allied_helpers,
            'failure_assistance': failure_assistance,
            'include_buff_rewards': include_buffs,
            'include_superweapon_rewards': include_superweapons,
            'include_secondary_superweapon_rewards': include_secondary_superweapons,
            'include_aid_power_rewards': include_aid_powers,
            'include_power_buff_rewards': include_power_buffs,
            'enabled_reward_types': [
                reward_type
                for reward_type, enabled in (
                    ('access', randomize_access),
                    ('buff', include_buffs),
                    ('superweapon', include_superweapons),
                    ('secondary_superweapon', include_secondary_superweapons),
                    ('aid_power', include_aid_powers),
                    ('power_buff', include_power_buffs),
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
            'enabled_power_buff_types': enabled_power_buff_types,
            'excluded_power_buff_types': {
                str(power_id).upper(): sorted({
                    str(item) for item in buff_types
                })
                for power_id, buff_types in generation_config.get(
                    'excluded_power_buff_types', {}
                ).items()
                if isinstance(buff_types, list)
            } if isinstance(
                generation_config.get('excluded_power_buff_types', {}), dict
            ) else {},
            'reward_weights': reward_weights,
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
        include_special_rewards = bool(self.include_special_rewards_var.get())
        unlimited_hero_units = bool(self.unlimited_hero_units_var.get())
        share_chaos_role_buffs = bool(self.share_chaos_role_buffs_var.get())
        buff_allied_helpers = bool(self.buff_allied_helpers_var.get())
        failure_assistance = bool(self.failure_assistance_var.get())
        include_buffs = bool(self.include_buff_rewards_var.get())
        include_superweapons = bool(self.include_superweapon_rewards_var.get())
        include_secondary_superweapons = bool(self.include_secondary_superweapon_rewards_var.get())
        include_aid_powers = bool(self.include_aid_power_rewards_var.get())
        include_power_buffs = bool(self.include_power_buff_rewards_var.get())
        enabled_buff_types = [
            buff_type['id']
            for buff_type in BUFF_TYPES
            if self.buff_type_vars[buff_type['id']].get()
        ]
        enabled_power_buff_types = [
            buff_type['id']
            for buff_type in POWER_BUFF_TYPES
            if self.power_buff_type_vars[buff_type['id']].get()
        ]
        reward_weights = normalize_reward_weights({
            'main': {
                definition['id']: clamp_reward_weight(
                    self.main_reward_weight_vars[definition['id']].get()
                )
                for definition in MAIN_REWARD_WEIGHT_TYPES
            },
            'unit_buffs': {
                weight_id: clamp_reward_weight(
                    self.unit_buff_weight_vars[weight_id].get()
                )
                for weight_id, _label in UNIT_BUFF_WEIGHT_TYPES
            },
            'power_buffs': {
                weight_id: clamp_reward_weight(
                    self.power_buff_weight_vars[weight_id].get()
                )
                for weight_id, _label in POWER_BUFF_WEIGHT_TYPES
            },
        })
        return {
            'randomize_unit_access': randomize_access,
            'start_with_tier_one_units': start_with_tier_one_units,
            'start_with_tier_one_defenses': start_with_tier_one_defenses,
            'include_defensive_buildings': include_defensive_buildings,
            'include_special_buildings': include_special_buildings,
            'include_special_rewards': include_special_rewards,
            'unlimited_hero_units': unlimited_hero_units,
            'share_chaos_role_buffs': share_chaos_role_buffs,
            'buff_allied_helpers': buff_allied_helpers,
            'failure_assistance': failure_assistance,
            'include_buff_rewards': include_buffs,
            'include_superweapon_rewards': include_superweapons,
            'include_secondary_superweapon_rewards': include_secondary_superweapons,
            'include_aid_power_rewards': include_aid_powers,
            'include_power_buff_rewards': include_power_buffs,
            'enabled_reward_types': [
                reward_type
                for reward_type, enabled in (
                    ('access', randomize_access),
                    ('buff', include_buffs),
                    ('superweapon', include_superweapons),
                    ('secondary_superweapon', include_secondary_superweapons),
                    ('aid_power', include_aid_powers),
                    ('power_buff', include_power_buffs),
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
            'enabled_power_buff_types': enabled_power_buff_types,
            'excluded_power_buff_types': {
                power_id: sorted(buff_types)
                for power_id, buff_types in sorted(
                    self.excluded_power_buff_types.items()
                )
                if buff_types
            },
            'reward_weights': reward_weights,
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
        settings.setdefault('include_special_rewards', True)
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
        # Old generated runs contain no power-buff rewards. Keep their saved
        # pool policy unchanged while new launcher configs default this on.
        settings.setdefault('include_power_buff_rewards', False)
        settings.setdefault('excluded_unit_access_ids', [])
        settings.setdefault('excluded_superweapon_ids', [])
        settings.setdefault('excluded_unit_buff_types', {})
        settings.setdefault('excluded_power_buff_types', {})
        if not isinstance(settings.get('enabled_buff_types'), list):
            settings['enabled_buff_types'] = [buff_type['id'] for buff_type in BUFF_TYPES]
        if not isinstance(settings.get('enabled_power_buff_types'), list):
            settings['enabled_power_buff_types'] = [
                buff_type['id'] for buff_type in POWER_BUFF_TYPES
            ]
        settings['reward_weights'] = normalize_reward_weights(
            settings.get('reward_weights')
        )
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

    def starting_tier_one_defense_ids_for_seed(
        self,
        reward_settings=None,
        seed=None,
    ):
        settings = reward_settings or self.active_reward_settings()
        if not settings.get('start_with_tier_one_defenses', False):
            return []
        excluded_ids = {
            str(unit_id).upper()
            for unit_id in settings.get('excluded_unit_access_ids', [])
        }
        if self.active_reward_mode() == 'Chaos (Experimental)':
            if seed is None:
                seed = self.seed_var.get() if hasattr(self, 'seed_var') else ''
            rng = random.Random(f'{seed}:starting-tier-one-defenses')
            return [
                unit_id
                for unit_id in random_chaos_tier_one_defense_ids(rng)
                if unit_id not in excluded_ids
            ]
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
        generation_context = self.__dict__.get('_seed_generation_context') or {}
        selected_campaign = generation_context.get('campaign_filter')
        if selected_campaign is None:
            selected_campaign = (self.state or {}).get('campaign_filter')
        if not selected_campaign and hasattr(self, 'campaign_var'):
            selected_campaign = self.campaign_var.get()
        return bool(
            (
                self.active_reward_mode() == 'Chaos (Experimental)'
                or selected_campaign == 'All Campaigns'
            )
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
        self.config['eva_voice'] = self.eva_voice_var.get()
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
        self.config['generation']['excluded_power_buff_types'] = {
            power_id: sorted(buff_types)
            for power_id, buff_types in sorted(
                self.excluded_power_buff_types.items()
            )
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
        self.config['generation']['include_special_rewards'] = reward_settings['include_special_rewards']
        self.config['generation']['unlimited_hero_units'] = reward_settings['unlimited_hero_units']
        self.config['generation']['share_chaos_role_buffs'] = reward_settings['share_chaos_role_buffs']
        self.config['generation']['include_buff_rewards'] = reward_settings['include_buff_rewards']
        self.config['generation']['include_superweapon_rewards'] = reward_settings['include_superweapon_rewards']
        self.config['generation']['include_secondary_superweapon_rewards'] = reward_settings['include_secondary_superweapon_rewards']
        self.config['generation']['include_aid_power_rewards'] = reward_settings['include_aid_power_rewards']
        self.config['generation']['include_power_buff_rewards'] = reward_settings['include_power_buff_rewards']
        self.config['generation']['enabled_buff_types'] = reward_settings['enabled_buff_types']
        self.config['generation']['enabled_power_buff_types'] = reward_settings['enabled_power_buff_types']
        self.config['generation']['reward_weights'] = reward_settings['reward_weights']
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
