"""Persistent state, player configuration, starters, and assistance."""

from randomizer.config.tuning import mission_assistance_stack_count

from ._dependencies import (
    ARSENAL_FACTIONS,
    ARSENAL_MODE,
    ARSENAL_POWER_TYPES,
    ARSENAL_TIERS,
    ARSENAL_UNIT_TYPES,
    BUFF_TARGETS,
    BUFF_TYPES,
    CAMPAIGN_FILTERS,
    CHECK_SCHEMA_VERSION,
    DEFAULT_MISSION_GOAL,
    DEFAULT_REWARDS_PER_CHECK,
    DIFFICULTIES,
    EVA_VOICE_CHOICES,
    GAME_SPEEDS,
    MAIN_REWARD_WEIGHT_TYPES,
    MAX_REWARDS_PER_CHECK,
    PLAYER_COLORS,
    POWER_BUFF_TYPES,
    POWER_BUFF_WEIGHT_TYPES,
    PROGRESSION_MODES,
    REWARD_MODES,
    STANDARD_STARTER_FAMILIES_BY_CAMPAIGN,
    STARTING_UNLOCKED_MISSIONS,
    STARTING_REWARD_TYPE_DEFINITIONS,
    STATE_PATH,
    atomic_write_json,
    check_rewards,
    clamp_reward_weight,
    create_grid,
    expanded_tier_one_defense_ids,
    expanded_tier_one_unit_ids,
    filedialog,
    linked_buff_variant_ids,
    log_event,
    logging,
    messagebox,
    normalize_assistance_units,
    normalize_arsenal_settings,
    normalize_completed_checks,
    normalize_failure_stacks,
    normalize_reward_weights,
    normalize_starting_reward_count,
    normalize_starting_reward_types,
    normalize_starting_unlock_reward_names,
    random,
    random_chaos_tier_one_defense_ids,
    random_chaos_tier_one_unit_ids,
    read_json_object,
    read_portable_settings,
    refresh_grid_states,
    save_config,
    tier_one_defense_ids,
    tier_one_unit_ids,
    traceback,
    UNIT_BUFF_WEIGHT_TYPES,
    valid_choice,
    write_portable_settings,
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
        if self.state.get('reward_mode') == 'Chaos (Experimental)':
            self.state['reward_mode'] = 'Chaos'
            changed = True
        if 'mission_goal' not in self.state:
            self.state['mission_goal'] = len(self.state.get('mission_order', [])) or DEFAULT_MISSION_GOAL
            changed = True
        old_earned = self.earned_rewards_from_checks(include_starting=False) if self.state.get('starting_rewards') and self.state.get('mission_checks') else self.state.get('earned_rewards', [])
        old_queue = self.state.get('reward_queue', [])
        discard_old_reward_history = False
        if any('spawn' in reward for reward in old_earned + old_queue):
            discard_old_reward_history = True
            old_earned = []
            old_queue = []
            self.state['earned_rewards'] = []
            self.state['reward_queue'] = []
            changed = True
        previous_schema = self.state.get('check_schema_version')
        schema_changed = previous_schema != CHECK_SCHEMA_VERSION
        preserve_capped_reward_history = (
            previous_schema == 16 and not discard_old_reward_history
        )
        if self.missions and (schema_changed or 'mission_checks' not in self.state):
            self.state['mission_checks'] = self.build_mission_checks(
                self.state.get('mission_order', []),
                self.state.get('seed', ''),
                (
                    old_earned
                    if not schema_changed or preserve_capped_reward_history
                    else []
                ),
                self.state.get('completed_missions', []),
                preserved_checks=(
                    self.state.get('mission_checks', {})
                    if not schema_changed or preserve_capped_reward_history
                    else {}
                ),
                rewards_per_check=self.state.get('rewards_per_check', DEFAULT_REWARDS_PER_CHECK),
                progression_mode=self.state.get('progression_mode'),
                grid=self.state.get('grid'),
                starting_rewards=self.state.get('starting_rewards', []),
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
            self.save_state()

    def save_state(self):
        atomic_write_json(STATE_PATH, self.state)

    def config_reward_settings(self):
        generation_config = self.config.get('generation', {})
        arsenal_settings = normalize_arsenal_settings(
            generation_config.get('arsenal')
        )
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
        if generation_config.get('reward_mode') in {
            'Chaos', 'Chaos (Experimental)', ARSENAL_MODE,
        }:
            randomize_access = True
        return {
            'arsenal': arsenal_settings,
            'randomize_unit_access': randomize_access,
            'start_with_tier_one_units': start_with_tier_one_units,
            'start_with_tier_one_defenses': start_with_tier_one_defenses,
            'starting_reward_count': normalize_starting_reward_count(generation_config.get('starting_reward_count', 0)),
            'starting_reward_types': normalize_starting_reward_types(generation_config.get('starting_reward_types')),
            'starting_unlock_rewards': self.filter_permanent_starting_unlock_names(generation_config.get('starting_unlock_rewards')) if hasattr(self, 'filter_permanent_starting_unlock_names') else normalize_starting_unlock_reward_names(generation_config.get('starting_unlock_rewards')),
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
        all_faction_mode = self.reward_mode_var.get() in {'Chaos', ARSENAL_MODE}
        randomize_access = all_faction_mode or bool(self.randomize_unit_access_var.get())
        arsenal_settings = normalize_arsenal_settings({
            'factions': [
                faction for faction in ARSENAL_FACTIONS
                if self.arsenal_faction_vars[faction].get()
            ],
            'roster_sizes': {
                tier: {
                    unit_type: self.arsenal_roster_size_vars[tier][unit_type].get()
                    for unit_type in ARSENAL_UNIT_TYPES
                }
                for tier in ARSENAL_TIERS
            },
            'power_counts': {
                power_type: self.arsenal_power_count_vars[power_type].get()
                for power_type in ARSENAL_POWER_TYPES
            },
        })
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
            'arsenal': arsenal_settings,
            'randomize_unit_access': randomize_access,
            'start_with_tier_one_units': start_with_tier_one_units,
            'start_with_tier_one_defenses': start_with_tier_one_defenses,
            'starting_reward_count': normalize_starting_reward_count(self.starting_reward_count_var.get()),
            'starting_reward_types': normalize_starting_reward_types([
                definition['id']
                for definition in STARTING_REWARD_TYPE_DEFINITIONS
                if self.starting_reward_type_vars[definition['id']].get()
            ]),
            'starting_unlock_rewards': self.canonical_starting_unlock_names(),
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
        settings['arsenal'] = normalize_arsenal_settings(
            settings.get('arsenal')
        )
        settings.setdefault('start_with_tier_one_units', False)
        settings.setdefault('start_with_tier_one_defenses', False)
        settings['starting_reward_count'] = normalize_starting_reward_count(settings.get('starting_reward_count', 0))
        settings['starting_reward_types'] = normalize_starting_reward_types(settings.get('starting_reward_types'))
        settings['starting_unlock_rewards'] = self.filter_permanent_starting_unlock_names(settings.get('starting_unlock_rewards')) if hasattr(self, 'filter_permanent_starting_unlock_names') else normalize_starting_unlock_reward_names(settings.get('starting_unlock_rewards'))
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
        if self.active_reward_mode() in {'Chaos', ARSENAL_MODE}:
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
        if self.active_reward_mode() == ARSENAL_MODE:
            return []
        if not settings.get('start_with_tier_one_units', False):
            return []
        excluded_ids = {
            str(unit_id).upper()
            for unit_id in settings.get('excluded_unit_access_ids', [])
        }
        if self.active_reward_mode() == 'Chaos':
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
        if self.active_reward_mode() == ARSENAL_MODE:
            return []
        if not settings.get('start_with_tier_one_defenses', False):
            return []
        excluded_ids = {
            str(unit_id).upper()
            for unit_id in settings.get('excluded_unit_access_ids', [])
        }
        if self.active_reward_mode() == 'Chaos':
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
                self.active_reward_mode() == 'Chaos'
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
                self.active_reward_mode() == 'Chaos'
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
                self.active_reward_mode() == 'Chaos'
                or selected_campaign == 'All Campaigns'
            )
            and self.active_reward_settings().get('share_chaos_role_buffs', False)
        )

    def failure_assistance_enabled(self):
        return bool(self.active_reward_settings().get('failure_assistance', False))

    def mission_failure_stack(self, code):
        if not self.state or not code:
            return 0
        return mission_assistance_stack_count(
            self.state.get('mission_failure_stacks', {}).get(code, 0)
        )

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
        current_stack = self.mission_failure_stack(code)
        next_stack = mission_assistance_stack_count(current_stack + 1)
        if next_stack == current_stack:
            return False
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
            mode = generation_context['reward_mode']
        elif (
            self.__dict__.get('_reward_settings_override') is not None
            and hasattr(self, 'reward_mode_var')
        ):
            mode = self.reward_mode_var.get()
        elif self.state:
            mode = self.state.get('reward_mode', REWARD_MODES[0])
        elif hasattr(self, 'reward_mode_var'):
            mode = self.reward_mode_var.get()
        else:
            mode = REWARD_MODES[0]
        return 'Chaos' if mode == 'Chaos (Experimental)' else mode

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
        self.config['generation']['starting_reward_count'] = reward_settings['starting_reward_count']
        self.config['generation']['starting_reward_types'] = reward_settings['starting_reward_types']
        self.config['generation']['starting_unlock_rewards'] = reward_settings['starting_unlock_rewards']
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
        self.config['generation']['arsenal'] = reward_settings['arsenal']
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

    def save_settings_file(self):
        """Export every launcher option without active seed progress."""
        path = filedialog.asksaveasfilename(
            parent=self,
            title='Save Randomizer Settings',
            defaultextension='.json',
            initialfile='Mental Omega Randomizer Settings.json',
            filetypes=(
                ('Randomizer settings', '*.json'),
                ('All files', '*.*'),
            ),
        )
        if not path:
            return
        try:
            self.save_current_launcher_config()
            write_portable_settings(path, self.config)
        except Exception as exc:
            log_event(
                'portable_settings_save_failed',
                level=logging.ERROR,
                path=str(path),
                traceback=traceback.format_exc(),
            )
            messagebox.showerror(
                'Save Settings Failed',
                f'Could not save settings.\n\n{exc}',
                parent=self,
            )
            return
        self.append_log(f'Saved portable settings: {path}')
        messagebox.showinfo(
            'Settings Saved',
            'Portable settings saved. Copy this JSON file to another PC to '
            'load the identical setup.',
            parent=self,
        )

    def load_settings_file(self):
        """Import every launcher option while preserving run progress."""
        path = filedialog.askopenfilename(
            parent=self,
            title='Load Randomizer Settings',
            filetypes=(
                ('Randomizer settings', '*.json'),
                ('All files', '*.*'),
            ),
        )
        if not path:
            return
        try:
            config = read_portable_settings(path)
            self.apply_portable_settings(config)
        except Exception as exc:
            log_event(
                'portable_settings_load_failed',
                level=logging.ERROR,
                path=str(path),
                traceback=traceback.format_exc(),
            )
            messagebox.showerror(
                'Load Settings Failed',
                f'Could not load settings.\n\n{exc}',
                parent=self,
            )
            return
        self.append_log(f'Loaded portable settings: {path}')
        messagebox.showinfo(
            'Settings Loaded',
            'All settings loaded. They apply to the next generated seed; '
            'current run progress was not changed.',
            parent=self,
        )

    def apply_portable_settings(self, config):
        """Apply one validated portable config to every live setting control."""
        self.config = config
        generation = self.config.get('generation', {})
        if generation.get('reward_mode') == 'Chaos (Experimental)':
            generation['reward_mode'] = 'Chaos'
        reward_settings = self.config_reward_settings()
        generation['starting_unlock_rewards'] = reward_settings['starting_unlock_rewards']
        self.dark_mode_var.set(bool(self.config.get('dark_mode', False)))
        self.hide_reward_details_var.set(bool(
            self.config.get('hide_reward_details', False)
        ))
        self.hide_locked_grid_missions_var.set(bool(
            self.config.get('hide_locked_grid_missions', False)
        ))
        self.seed_var.set(str(self.config.get('seed', '')))
        self.campaign_var.set(valid_choice(
            self.config.get('campaign_filter'),
            CAMPAIGN_FILTERS,
            CAMPAIGN_FILTERS[0],
        ))
        self.mission_goal_var.set(max(
            1, int(self.config.get('mission_goal', DEFAULT_MISSION_GOAL))
        ))
        self.progression_mode_var.set(valid_choice(
            self.config.get('progression_mode'),
            PROGRESSION_MODES,
            PROGRESSION_MODES[0],
        ))
        self.grid_two_starts_var.set(bool(
            self.config.get('grid_two_start_positions', False)
        ))
        self.rewards_per_check_var.set(max(1, min(
            MAX_REWARDS_PER_CHECK,
            int(self.config.get(
                'rewards_per_objective', DEFAULT_REWARDS_PER_CHECK
            )),
        )))
        self.difficulty_var.set(valid_choice(
            self.config.get('difficulty'),
            [name for name, _ in DIFFICULTIES],
            DIFFICULTIES[0][0],
        ))
        self.game_speed_var.set(valid_choice(
            self.config.get('game_speed'),
            [name for name, _ in GAME_SPEEDS],
            GAME_SPEEDS[0][0],
        ))
        self.player_color_var.set(valid_choice(
            self.config.get('player_color'),
            PLAYER_COLORS,
            PLAYER_COLORS[0],
        ))
        self.rainbowizer_var.set(bool(
            self.config.get('rainbowizer', False)
        ))
        self.eva_voice_var.set(valid_choice(
            self.config.get('eva_voice'),
            EVA_VOICE_CHOICES,
            EVA_VOICE_CHOICES[0],
        ))

        self.include_no_build_missions_var.set(bool(
            generation.get('include_no_build_missions', True)
        ))
        self.include_no_build_production_missions_var.set(bool(
            generation.get('include_no_build_production_missions', True)
        ))
        self.include_operation_missions_var.set(bool(
            generation.get('include_operation_missions', True)
        ))
        self.prioritize_no_build_missions_var.set(bool(
            generation.get('prioritize_no_build_missions', False)
        ))
        self.reward_mode_var.set(valid_choice(
            generation.get('reward_mode'),
            REWARD_MODES,
            REWARD_MODES[0],
        ))

        self.excluded_mission_codes = {
            str(code).upper()
            for code in generation.get('excluded_mission_codes', [])
            if str(code).strip()
        }
        self.excluded_unit_access_ids = {
            str(unit_id).upper()
            for unit_id in reward_settings['excluded_unit_access_ids']
        }
        self.excluded_superweapon_ids = {
            str(power_id).upper()
            for power_id in reward_settings['excluded_superweapon_ids']
        }
        self.excluded_unit_buff_types = {
            str(unit_id).upper(): set(buff_types)
            for unit_id, buff_types in reward_settings[
                'excluded_unit_buff_types'
            ].items()
        }
        self.excluded_power_buff_types = {
            str(power_id).upper(): set(buff_types)
            for power_id, buff_types in reward_settings[
                'excluded_power_buff_types'
            ].items()
        }
        arsenal_settings = reward_settings['arsenal']
        enabled_arsenal_factions = set(arsenal_settings['factions'])
        for faction in ARSENAL_FACTIONS:
            self.arsenal_faction_vars[faction].set(
                faction in enabled_arsenal_factions
            )
        for tier in ARSENAL_TIERS:
            for unit_type in ARSENAL_UNIT_TYPES:
                self.arsenal_roster_size_vars[tier][unit_type].set(
                    arsenal_settings['roster_sizes'][tier][unit_type]
                )
        for power_type in ARSENAL_POWER_TYPES:
            self.arsenal_power_count_vars[power_type].set(
                arsenal_settings['power_counts'][power_type]
            )

        setting_vars = {
            'randomize_unit_access': self.randomize_unit_access_var,
            'start_with_tier_one_units': self.start_with_tier_one_units_var,
            'start_with_tier_one_defenses': self.start_with_tier_one_defenses_var,
            'include_defensive_buildings': self.include_defensive_buildings_var,
            'include_special_buildings': self.include_special_buildings_var,
            'include_special_rewards': self.include_special_rewards_var,
            'unlimited_hero_units': self.unlimited_hero_units_var,
            'share_chaos_role_buffs': self.share_chaos_role_buffs_var,
            'buff_allied_helpers': self.buff_allied_helpers_var,
            'failure_assistance': self.failure_assistance_var,
            'include_buff_rewards': self.include_buff_rewards_var,
            'include_superweapon_rewards': self.include_superweapon_rewards_var,
            'include_secondary_superweapon_rewards': (
                self.include_secondary_superweapon_rewards_var
            ),
            'include_aid_power_rewards': self.include_aid_power_rewards_var,
            'include_power_buff_rewards': self.include_power_buff_rewards_var,
        }
        for key, variable in setting_vars.items():
            variable.set(bool(reward_settings[key]))
        self.starting_reward_count_var.set(str(reward_settings['starting_reward_count']))
        allowed_starting_types = set(reward_settings['starting_reward_types'])
        for definition in STARTING_REWARD_TYPE_DEFINITIONS:
            self.starting_reward_type_vars[definition['id']].set(
                definition['id'] in allowed_starting_types
            )
        self.manual_starting_reward_names = set(reward_settings['starting_unlock_rewards'])

        enabled_unit_buffs = set(reward_settings['enabled_buff_types'])
        for buff_type in BUFF_TYPES:
            self.buff_type_vars[buff_type['id']].set(
                buff_type['id'] in enabled_unit_buffs
            )
        enabled_power_buffs = set(
            reward_settings['enabled_power_buff_types']
        )
        for buff_type in POWER_BUFF_TYPES:
            self.power_buff_type_vars[buff_type['id']].set(
                buff_type['id'] in enabled_power_buffs
            )

        weights = reward_settings['reward_weights']
        for definition in MAIN_REWARD_WEIGHT_TYPES:
            weight_id = definition['id']
            self.main_reward_weight_vars[weight_id].set(
                weights['main'][weight_id]
            )
        for weight_id, _label in UNIT_BUFF_WEIGHT_TYPES:
            self.unit_buff_weight_vars[weight_id].set(
                weights['unit_buffs'][weight_id]
            )
        for weight_id, _label in POWER_BUFF_WEIGHT_TYPES:
            self.power_buff_weight_vars[weight_id].set(
                weights['power_buffs'][weight_id]
            )

        save_config(self.config)
        self.apply_color_mode()
        self.refresh_setting_states()
        self.update_mission_goal_limit()
        self.refresh_advanced_pool_views()
        self.grid_render_signature = None
        self.unlock_dashboard_signature = None
        self.refresh_progress_view()
