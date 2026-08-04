"""Reward filtering, mission checks, and earned reward state."""

from ._dependencies import (
    ARSENAL_MODE,
    ALWAYS_AVAILABLE_TECH_IDS,
    BATTLE_CLIENT_INI,
    BUFF_TARGETS,
    CHECK_SCHEMA_VERSION,
    DEFAULT_PROGRESSION_MODE,
    DEFAULT_REWARDS_PER_CHECK,
    FALLBACK_OBJECTIVE_COUNT,
    MAX_REWARDS_PER_CHECK,
    REWARD_POOL,
    canonical_reward,
    canonical_rewards,
    check_rewards,
    clamp_int,
    filter_starting_reward_pool,
    linked_buff_variant_ids,
    log_event,
    MAX_REWARDS_ACHIEVED_REWARD,
    normalize_reward_weights,
    normalize_starting_reward_count,
    normalize_starting_reward_types,
    parse_missions,
    plan_seed_rewards,
    mission_player_production_houses,
    mission_production_families,
    mission_reward_class,
    mission_reward_multiplier,
    tech_ids_for_rewards,
    reward_selection_weight,
    is_max_rewards_achieved_reward,
    arsenal_launch_rewards,
    arsenal_power_ids,
    arsenal_reward_pool,
    arsenal_unit_ids,
    unit_display_label,
    unit_role_equivalents,
    unlocked_reward_tech_ids,
)

class RewardController:

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
        if self.active_reward_mode() in {'Chaos', ARSENAL_MODE}:
            return None
        selected = (self.state or {}).get('campaign_filter', '')
        if selected == 'Foehn':
            # Foehn Standard intentionally uses bundled Allied/Soviet access;
            # native Foehn powers may also be valid campaign rewards.
            return {'Allies', 'Soviets', 'Foehn', 'Neutral'}
        if selected in {'Allies', 'Soviets', 'Epsilon'}:
            return {selected, 'Neutral'}
        if selected == 'All Campaigns':
            return {'Allies', 'Soviets', 'Epsilon', 'Neutral'}
        return None

    def standard_foehn_unit_reward(self, reward):
        """Keep native Foehn unit access exclusive to Chaos reward mode."""
        reward = canonical_reward(reward)
        return bool(
            self.active_reward_mode() not in {'Chaos', ARSENAL_MODE}
            and reward.get('kind') != 'superweapon'
            and reward.get('access_category') != 'special_building'
            and not self.reward_is_special_building(reward)
            and not self.reward_is_special_reward(reward)
            and set(reward.get('factions') or ()) == {'Foehn'}
        )

    def manual_starting_reward_names_in_state(self):
        return {
            canonical_reward(reward).get('name')
            for reward in self.state.get('manual_starting_rewards', [])
        }

    def active_launch_rewards(self):
        rewards = canonical_rewards(
            self.earned_rewards_from_checks() if self.state else []
        )
        manual_names = self.manual_starting_reward_names_in_state()

        def is_manual(reward):
            return reward.get('name') in manual_names

        if not self.active_reward_settings().get('include_special_rewards', True):
            rewards = [
                reward
                for reward in rewards
                if is_manual(reward) or not self.reward_is_special_reward(reward)
            ]
        rewards = [
            reward
            for reward in rewards
            if is_manual(reward) or not self.standard_foehn_unit_reward(reward)
        ]
        allowed_factions = self.active_launch_reward_factions()
        if allowed_factions is None:
            return rewards
        return [
            reward
            for reward in rewards
            if (
                is_manual(reward)
                or not reward.get('factions')
                or allowed_factions.intersection(reward.get('factions', ()))
            )
        ]

    def mission_arsenal(self, code):
        code = str(code or '').upper()
        override = self.__dict__.get('_arsenal_override')
        if isinstance(override, dict):
            return override.get(code, {})
        return (self.state or {}).get('mission_arsenals', {}).get(code, {})

    def launch_rewards_for_mission(self, code):
        rewards = self.active_launch_rewards()
        if self.active_reward_mode() != ARSENAL_MODE:
            return rewards
        return arsenal_launch_rewards(self.mission_arsenal(code), rewards)

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
        if self.active_reward_mode() == ARSENAL_MODE:
            return arsenal_unit_ids(
                self.mission_arsenal(mission.get('code'))
            ) | additional
        unlocked = set(self.active_unlocked_reward_tech_ids())
        if self.active_reward_mode() == 'Chaos':
            return unlocked | additional

        family_names = {
            'allies': 'Allies',
            'soviets': 'Soviets',
            'epsilon': 'Epsilon',
            'foehn': 'Foehn',
        }
        production_factions = {
            family_names[family]
            for family in mission_production_families(
                lines,
                additional_production_houses=mission_player_production_houses(
                    mission.get('code')
                ),
                include_capturable=True,
            )
            if family in family_names
        }

        return additional | {
            unit_id
            for unit_id in unlocked
            if not BUFF_TARGETS.get(unit_id, {}).get('factions')
            or 'Neutral' in BUFF_TARGETS.get(
                unit_id, {}
            ).get('factions', ())
            or production_factions.intersection(
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
        if reward_mode == ARSENAL_MODE:
            return arsenal_reward_pool(
                self.configured_reward_pool(),
                self.mission_arsenal(code),
            )
        if reward_mode == 'Chaos':
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
                or 'Neutral' in reward.get('factions', [])
                or (
                    selected == 'Foehn'
                    and (
                        reward.get('kind') == 'superweapon'
                        or reward.get('access_category') == 'special_building'
                        or self.reward_is_special_building(reward)
                        or self.reward_is_special_reward(reward)
                    )
                    and 'Foehn' in reward.get('factions', [])
                )
            )
        ]
        return self.bundle_foehn_standard_access(self.filter_reward_pool(pool))

    def configured_reward_pool(self):
        return self.filter_reward_pool(REWARD_POOL)

    def configured_manual_starting_rewards(self):
        """Resolve exact selected rewards, omitting duplicate TechnoType access."""
        selected = set(self.active_starting_unlock_names())
        seen_tech_ids = (
            set(self.active_starting_tier_one_access_ids())
            | set(ALWAYS_AVAILABLE_TECH_IDS)
        )
        rewards = []
        for source in REWARD_POOL:
            reward = canonical_reward(source)
            if reward.get('name') not in selected:
                continue
            if (
                reward.get('kind') in {'buff', 'message', 'retired'}
                or not self.reward_is_permanent_starting_unlock(reward)
            ):
                continue
            tech_ids = tech_ids_for_rewards([reward])
            if reward.get('kind') != 'buff' and tech_ids & seen_tech_ids:
                continue
            rewards.append(dict(reward))
            if reward.get('kind') != 'buff':
                seen_tech_ids.update(tech_ids)
        return rewards

    def generate_starting_reward_plan(self, seed, initial_rewards=()):
        """Roll pre-run rewards on an RNG stream isolated from mission slots."""
        settings = self.active_reward_settings()
        count = normalize_starting_reward_count(
            settings.get('starting_reward_count', 0)
        )
        if count <= 0:
            return []
        allowed_types = normalize_starting_reward_types(
            settings.get('starting_reward_types')
        )
        code = '__starting_rewards__'

        def allowed_pool(pool):
            return filter_starting_reward_pool(pool, allowed_types)

        plan = plan_seed_rewards(
            [code],
            seed,
            {code: count},
            progression_mode='Starting Rewards',
            grid=None,
            reward_factions_for_code=self.reward_factions_for_code,
            reward_pool_for_code=lambda _code: allowed_pool(
                self.reward_pool_for_code(code)
            ),
            configured_reward_pool=lambda: allowed_pool(
                self.configured_reward_pool()
            ),
            starting_unlocked_tech_ids=(
                self.active_starting_tier_one_access_ids()
            ),
            initial_rewards=initial_rewards,
            require_access_for_unit_buffs=self.randomize_unit_access_enabled(),
            share_role_buffs=self.share_chaos_role_buffs_enabled(),
            reward_weights=settings.get('reward_weights'),
            rng_namespace='starting-rewards',
            avoid_unlocked_access=True,
            blocked_reward_names=self.active_starting_unlock_names(),
        )
        rewards = plan[code]
        real_rewards = [
            reward for reward in rewards
            if not is_max_rewards_achieved_reward(reward)
        ]
        if len(real_rewards) != len(rewards):
            real_rewards.append(dict(MAX_REWARDS_ACHIEVED_REWARD))
        return real_rewards

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

    def reward_is_special_reward(self, reward):
        if reward.get('special_reward') or reward.get('access_category') == 'special':
            return True
        unit_id = str(reward.get('unit') or '').upper()
        if not unit_id:
            tech_ids = tech_ids_for_rewards([reward])
            unit_id = next(iter(tech_ids), '')
        return bool(
            unit_id and BUFF_TARGETS.get(unit_id, {}).get('special_reward')
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
        include_power_buffs = bool(
            reward_settings.get('include_power_buff_rewards', False)
        )
        include_defensive_buildings = bool(reward_settings.get('include_defensive_buildings', True))
        include_special_buildings = bool(reward_settings.get('include_special_buildings', True))
        include_special_rewards = bool(reward_settings.get('include_special_rewards', True))
        enabled_buff_types = set(reward_settings.get('enabled_buff_types') or [])
        enabled_power_buff_types = set(
            reward_settings.get('enabled_power_buff_types') or []
        )
        excluded_unit_buff_types = {
            str(unit_id).upper(): {str(buff_type) for buff_type in buff_types}
            for unit_id, buff_types in reward_settings.get(
                'excluded_unit_buff_types', {}
            ).items()
            if isinstance(buff_types, (list, tuple, set))
        }
        excluded_power_buff_types = {
            str(power_id).upper(): {str(buff_type) for buff_type in buff_types}
            for power_id, buff_types in reward_settings.get(
                'excluded_power_buff_types', {}
            ).items()
            if isinstance(buff_types, (list, tuple, set))
        }
        chaos_mode = self.active_reward_mode() == 'Chaos'
        reward_weights = normalize_reward_weights(
            reward_settings.get('reward_weights')
        )

        def power_category_enabled(reward):
            category = reward.get('power_category', 'offensive')
            return (
                (category == 'offensive' and include_superweapons)
                or (
                    category == 'secondary'
                    and include_secondary_superweapons
                )
                or (category == 'aid' and include_aid_powers)
            )

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
                reward_selection_weight(reward, reward_weights) > 0
                and
                (
                    (
                        reward.get('kind') == 'buff'
                        and reward.get('power_buff_type')
                        and include_power_buffs
                        and (include_special_rewards or not self.reward_is_special_reward(reward))
                        and power_category_enabled(reward)
                        and reward.get('power_buff_type')
                        in enabled_power_buff_types
                        and str(reward.get('superweapon') or '').upper()
                        not in excluded_superweapon_ids
                        and reward.get('power_buff_type')
                        not in excluded_power_buff_types.get(
                            str(reward.get('superweapon') or '').upper(), set()
                        )
                    )
                    or (
                        reward.get('kind') == 'buff'
                        and not reward.get('power_buff_type')
                        and include_buffs
                        and (include_special_rewards or not self.reward_is_special_reward(reward))
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
                        and (include_special_rewards or not self.reward_is_special_reward(reward))
                        and power_category_enabled(reward)
                        and str(reward.get('superweapon') or '').upper()
                        not in excluded_superweapon_ids
                    )
                    or (
                        reward.get('kind') not in {'buff', 'superweapon'}
                        and randomize_access
                        and (include_special_rewards or not self.reward_is_special_reward(reward))
                        and (include_defensive_buildings or not self.reward_is_defensive_building(reward))
                        and (include_special_buildings or not self.reward_is_special_building(reward))
                        and not tech_ids_for_rewards([reward]).intersection(starting_access_ids)
                        and not tech_ids_for_rewards([reward]).intersection(excluded_access_ids)
                    )
                )
            )
        ]

    def reward_factions_for_code(self, _code):
        if self.active_reward_mode() == ARSENAL_MODE:
            return set(
                self.active_reward_settings().get('arsenal', {}).get(
                    'factions', ()
                )
            )
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
        preserve_history = schema_current or self.state.get(
            'check_schema_version'
        ) in {16, 17}
        checks_present = 'mission_checks' in self.state
        if schema_current and checks_present and self.state.get('mission_objectives') == summary:
            return

        self.state['mission_checks'] = self.build_mission_checks(
            mission_codes,
            self.state.get('seed', ''),
            (
                self.earned_rewards_from_checks(include_starting=False)
                if preserve_history else []
            ),
            self.state.get('completed_missions', []),
            preserved_checks=(
                self.state.get('mission_checks', {})
                if preserve_history else {}
            ),
            rewards_per_check=self.state.get('rewards_per_check', DEFAULT_REWARDS_PER_CHECK),
            progression_mode=self.state.get('progression_mode'),
            grid=self.state.get('grid'),
            starting_rewards=self.state.get('starting_rewards', []),
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
        starting_rewards=None,
    ):
        templates_by_code = {code: self.objective_templates_for_code(code) for code in mission_codes}
        earned_rewards = list(earned_rewards or [])
        starting_rewards = list(starting_rewards or [])
        completed_missions = list(completed_missions or [])
        rewards_per_check = clamp_int(rewards_per_check, 1, MAX_REWARDS_PER_CHECK, DEFAULT_REWARDS_PER_CHECK)
        completed = set(completed_missions)
        completed_rewards = {
            code: reward
            for code, reward in zip(completed_missions, earned_rewards)
        }
        preserved_checks = preserved_checks or {}
        checks = {}
        preserved_reward_check_ids = {}
        for code in mission_codes:
            old_checks = {
                check.get('id'): check
                for check in preserved_checks.get(code, [])
                if check.get('id')
            }
            preserved_reward_check_ids[code] = {
                check_id
                for check_id, _name, _hint in templates_by_code[code]
                if (
                    check_id in old_checks
                    and (
                        old_checks[check_id].get('unlocked')
                        or old_checks[check_id].get('released')
                    )
                    and check_rewards(old_checks[check_id])
                ) or (
                    check_id == 'objective_1' and code in completed_rewards
                )
            }
        multipliers_by_code = {}
        for code in mission_codes:
            old_multiplier = next((
                check.get('reward_multiplier')
                for check in preserved_checks.get(code, [])
                if isinstance(check.get('reward_multiplier'), int)
                and not isinstance(check.get('reward_multiplier'), bool)
                and check.get('reward_multiplier') >= 1
            ), None)
            multipliers_by_code[code] = (
                old_multiplier
                if old_multiplier is not None
                else mission_reward_multiplier(code)
            )
        base_slots_by_code = {
            code: (
                len(templates_by_code[code])
                - len(preserved_reward_check_ids[code])
            ) * rewards_per_check
            for code in mission_codes
        }
        base_rewards_by_code = self.generate_seed_reward_plan(
            mission_codes,
            seed,
            base_slots_by_code,
            progression_mode=progression_mode,
            grid=grid,
            initial_rewards=starting_rewards + earned_rewards,
            avoid_unlocked_access=bool(starting_rewards),
        )
        bonus_slots_by_code = {
            code: (
                len(templates_by_code[code])
                * rewards_per_check
                * (multipliers_by_code[code] - 1)
                if 'victory' not in preserved_reward_check_ids[code]
                else 0
            )
            for code in mission_codes
        }
        bonus_rewards_by_code = self.generate_mission_bonus_reward_plan(
            mission_codes,
            seed,
            bonus_slots_by_code,
            base_rewards_by_code,
            progression_mode=progression_mode,
            grid=grid,
            initial_rewards=starting_rewards + earned_rewards,
        )

        for code in mission_codes:
            mission_checks = []
            base_rewards = base_rewards_by_code.get(code, [])
            bonus_rewards = bonus_rewards_by_code.get(code, [])
            base_reward_index = 0
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
                    rewards_for_check = base_rewards[
                        base_reward_index:base_reward_index + rewards_per_check
                    ]
                    if check_id == 'victory':
                        rewards_for_check += bonus_rewards
                    real_rewards = [
                        reward for reward in rewards_for_check
                        if not is_max_rewards_achieved_reward(reward)
                    ]
                    if len(real_rewards) != len(rewards_for_check):
                        rewards_for_check = real_rewards + [
                            dict(MAX_REWARDS_ACHIEVED_REWARD)
                        ]
                    unlocked = False
                    released = False
                if check_id not in preserved_reward_check_ids[code]:
                    base_reward_index += rewards_per_check
                primary_reward = rewards_for_check[0] if rewards_for_check else {}
                mission_checks.append({
                    'id': check_id,
                    'name': name,
                    'hint': hint,
                    'reward': primary_reward,
                    'rewards': rewards_for_check,
                    'base_reward_count': rewards_per_check,
                    'multiplier_bonus_count': (
                        bonus_slots_by_code[code]
                        if check_id == 'victory' else 0
                    ),
                    'reward_multiplier': multipliers_by_code[code],
                    'reward_class': mission_reward_class(code),
                    'unlocked': unlocked or code in completed,
                    'released': released and code not in completed,
                })
            checks[code] = mission_checks

        return checks

    def generate_mission_bonus_reward_plan(
        self,
        mission_codes,
        seed,
        slots_by_code,
        base_rewards_by_code,
        *,
        progression_mode=None,
        grid=None,
        initial_rewards=(),
    ):
        """Plan valid completion bonuses without changing base assignments."""
        bonus_plan = {code: [] for code in mission_codes}
        all_base_rewards = {
            code: list(base_rewards_by_code.get(code, ()))
            for code in mission_codes
        }
        prior_bonus_rewards = []
        for code in mission_codes:
            slot_count = max(0, int(slots_by_code.get(code, 0)))
            if slot_count <= 0:
                continue
            reserved = [
                reward
                for other_code in mission_codes
                if other_code != code
                for reward in all_base_rewards[other_code]
            ] + prior_bonus_rewards
            plan = self.generate_seed_reward_plan(
                [code],
                seed,
                {code: slot_count},
                progression_mode=progression_mode,
                grid=None,
                initial_rewards=(
                    list(initial_rewards) + all_base_rewards[code]
                ),
                avoid_unlocked_access=True,
                rng_namespace=f'mission-reward-multiplier:{code}',
                reserved_rewards=reserved,
            )
            bonus_plan[code] = plan.get(code, [])
            prior_bonus_rewards.extend(bonus_plan[code])
        return bonus_plan

    def generate_seed_reward_plan(
        self,
        mission_codes,
        seed,
        slots_by_code,
        progression_mode=None,
        grid=None,
        initial_rewards=(),
        avoid_unlocked_access=False,
        rng_namespace='seed-rewards',
        reserved_rewards=(),
    ):
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
        arsenal_units = set()
        arsenal_powers = set()
        if self.active_reward_mode() == ARSENAL_MODE:
            for code in mission_codes:
                arsenal = self.mission_arsenal(code)
                arsenal_units.update(arsenal_unit_ids(arsenal))
                arsenal_powers.update(arsenal_power_ids(arsenal))
        return plan_seed_rewards(
            mission_codes,
            seed,
            slots_by_code,
            progression_mode=progression_mode,
            grid=grid,
            reward_factions_for_code=self.reward_factions_for_code,
            reward_pool_for_code=self.reward_pool_for_code,
            configured_reward_pool=self.configured_reward_pool,
            reward_pool_cache_key_for_code=(
                (lambda code: ('arsenal', str(code).upper()))
                if self.active_reward_mode() == ARSENAL_MODE
                else None
            ),
            allow_cross_pool_fallback=(
                self.active_reward_mode() != ARSENAL_MODE
            ),
            starting_unlocked_tech_ids=(
                arsenal_units or self.active_starting_tier_one_access_ids()
            ),
            starting_unlocked_power_ids=arsenal_powers,
            initial_rewards=initial_rewards,
            require_access_for_unit_buffs=self.randomize_unit_access_enabled(),
            share_role_buffs=self.share_chaos_role_buffs_enabled(),
            reward_weights=self.active_reward_settings().get(
                'reward_weights'
            ),
            avoid_unlocked_access=avoid_unlocked_access,
            blocked_reward_names=self.active_starting_unlock_names(),
            rng_namespace=rng_namespace,
            reserved_rewards=reserved_rewards,
        )

    def mission_reward_summary(self, code):
        checks = self.mission_checks(code)
        if not checks:
            return {
                'multiplier': mission_reward_multiplier(code),
                'base_rewards': 0,
                'final_rewards': 0,
                'max_rewards_achieved': False,
            }
        multiplier = next((
            check.get('reward_multiplier')
            for check in checks
            if isinstance(check.get('reward_multiplier'), int)
            and check.get('reward_multiplier') >= 1
        ), mission_reward_multiplier(code))
        base_rewards = sum(
            max(0, int(check.get('base_reward_count', 0)))
            for check in checks
        )
        final_rewards = sum(
            1
            for check in checks
            for reward in check_rewards(check)
            if not is_max_rewards_achieved_reward(reward)
        )
        return {
            'multiplier': multiplier,
            'base_rewards': base_rewards,
            'final_rewards': final_rewards,
            'max_rewards_achieved': any(
                is_max_rewards_achieved_reward(reward)
                for check in checks
                for reward in check_rewards(check)
            ),
        }

    def earned_rewards_from_checks(self, include_starting=True):
        earned = [
            reward
            for reward in self.state.get('starting_rewards', [])
            if include_starting and not is_max_rewards_achieved_reward(reward)
        ]
        for code in self.state.get('mission_order', []):
            for check in self.state.get('mission_checks', {}).get(code, []):
                if check.get('unlocked') or check.get('released'):
                    earned.extend(
                        reward for reward in check_rewards(check)
                        if not is_max_rewards_achieved_reward(reward)
                    )
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
