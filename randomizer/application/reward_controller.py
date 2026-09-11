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

from randomizer.generation.reward_controller import RewardGeneration

class RewardController(RewardGeneration):






    def manual_starting_reward_names_in_state(self):
        return {
            canonical_reward(reward).get('name')
            for reward in self.state.get('manual_starting_rewards', [])
        }

    def active_launch_rewards(self):
        rewards = canonical_rewards(
            self.earned_rewards_from_checks() if self.state else []
        )
        rewards = [
            reward for reward in rewards if not reward.get('enemy_reward')
        ]
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




    def access_limit_capacities(self):
        """Return unique available unit/building and power identities."""
        if self.active_reward_mode() == ARSENAL_MODE:
            return {'units': 0, 'powers': 0}
        unit_ids = set()
        power_ids = set()
        for reward in self.reward_pool_for_code('__access_limits__'):
            if reward.get('kind') == 'buff':
                continue
            if reward.get('kind') == 'superweapon':
                power_id = str(reward.get('superweapon') or '').upper()
                if power_id:
                    power_ids.add(power_id)
                continue
            unit_ids.update(tech_ids_for_rewards([reward]))
        return {'units': len(unit_ids), 'powers': len(power_ids)}









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
            rewards_on_victory_only=bool(
                self.state.get('rewards_on_victory_only', False)
            ),
            use_act_based_reward_multipliers=bool(
                self.state.get('use_act_based_reward_multipliers', True)
            ),
            progression_mode=self.state.get('progression_mode'),
            grid=self.state.get('grid'),
            starting_rewards=self.state.get('starting_rewards', []),
        )
        self.state['mission_objectives'] = summary
        grid = self.state.get('grid', {})
        if (
            self.state.get('progression_mode') == 'Grid Mode'
            and grid.get('goal') in self.state.get('completed_missions', [])
            and self.state.get('unlock_all_rewards_after_final_grid_mission', False)
            and not self.archipelago_run_active()
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




    def mission_reward_summary(self, code):
        checks = self.mission_checks(code)
        if not checks:
            return {
                'multiplier': (
                    mission_reward_multiplier(code)
                    if self.act_reward_multipliers_enabled()
                    else 1
                ),
                'base_rewards': 0,
                'final_rewards': 0,
                'max_rewards_achieved': False,
            }
        multiplier = next((
            check.get('reward_multiplier')
            for check in checks
            if isinstance(check.get('reward_multiplier'), int)
            and check.get('reward_multiplier') >= 1
        ), (
            mission_reward_multiplier(code)
            if self.act_reward_multipliers_enabled()
            else 1
        ))
        base_rewards = sum(
            max(0, int(check.get('base_reward_count', 0)))
            for check in checks
        )
        archipelago_counts = self.archipelago_mission_location_counts(code)
        final_rewards = (
            int(archipelago_counts[1])
            if archipelago_counts is not None
            else sum(
                1
                for check in checks
                for reward in check_rewards(check)
                if not is_max_rewards_achieved_reward(reward)
            )
        )
        return {
            'multiplier': multiplier,
            'base_rewards': base_rewards,
            'final_rewards': final_rewards,
            'max_rewards_achieved': (
                False
                if archipelago_counts is not None
                else any(
                    is_max_rewards_achieved_reward(reward)
                    for check in checks
                    for reward in check_rewards(check)
                )
            ),
        }

    def earned_rewards_from_checks(self, include_starting=True):
        archipelago_rewards = self.archipelago_reward_history()
        if archipelago_rewards is not None:
            return list(archipelago_rewards)
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

    def canonical_earned_rewards(self):
        """Return one cached canonical view of current earned reward history."""
        cached = self.__dict__.get('_canonical_earned_rewards_cache')
        if cached is not None:
            return cached
        rewards = tuple(
            canonical_reward(reward)
            for reward in self.earned_rewards_from_checks()
        )
        self._canonical_earned_rewards_cache = rewards
        return rewards

    def configured_grid_full_unlock_rewards(self):
        """Return every enabled permanent arsenal unlock for this seed."""
        goal_code = str((self.state.get('grid') or {}).get('goal') or '')
        pool = self.reward_pool_for_code(goal_code)
        result = []
        seen_names = set()
        for candidate in pool:
            reward = canonical_reward(candidate)
            name = reward.get('name')
            if (
                not name
                or name in seen_names
                or reward.get('enemy_reward')
                or reward.get('retired_reward')
                or reward.get('kind') in {'buff', 'message', 'retired'}
                or is_max_rewards_achieved_reward(reward)
            ):
                continue
            if (
                reward.get('kind') != 'superweapon'
                and not tech_ids_for_rewards([reward])
            ):
                continue
            seen_names.add(name)
            result.append(reward)
        return result

    def release_remaining_grid_rewards(self):
        """Release pending rewards and grant the configured full arsenal."""
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

        # A seed assigns only a finite sample of the enabled catalogue. The
        # explicit full-unlock option promises the complete configured arsenal,
        # so add missing unit/building/power access to the completed goal check.
        # Buffs remain the exact stacks generated by the seed.
        assigned_names = {
            canonical_reward(reward).get('name')
            for reward in self.state.get('starting_rewards', [])
        }
        assigned_names.update(
            canonical_reward(reward).get('name')
            for code in self.state.get('mission_order', [])
            for check in self.state.get('mission_checks', {}).get(code, [])
            for reward in check_rewards(check)
        )
        missing_unlocks = [
            reward
            for reward in self.configured_grid_full_unlock_rewards()
            if reward.get('name') not in assigned_names
        ]
        if missing_unlocks:
            goal_code = str((self.state.get('grid') or {}).get('goal') or '')
            goal_checks = self.state.get('mission_checks', {}).get(goal_code, [])
            target_check = next(
                (check for check in goal_checks if check.get('id') == 'victory'),
                goal_checks[0] if goal_checks else None,
            )
            if target_check is not None:
                combined = check_rewards(target_check) + missing_unlocks
                target_check['reward'] = combined[0] if combined else None
                target_check['rewards'] = combined
                released_rewards.extend(missing_unlocks)
                released_checks.append((goal_code, 'full_arsenal'))
        return released_rewards, released_checks

    def refresh_missions(self):
        self.append_log('Refreshing mission list...')
        self.apply_missions(
            parse_missions(BATTLE_CLIENT_INI, FALLBACK_OBJECTIVE_COUNT)
        )

    def load_missions(self):
        """Read mission catalogue without touching Tk state."""
        return parse_missions(BATTLE_CLIENT_INI, FALLBACK_OBJECTIVE_COUNT)

    def apply_missions(self, missions):
        """Apply a previously parsed mission catalogue to launcher widgets."""
        self.missions = missions
        self._mission_by_code = {mission['code']: mission for mission in self.missions}
        self.mission_goal_spinbox.configure(to=max(1, len(self.missions)))
        if self.missions and self.mission_goal_var.get() > len(self.missions):
            self.mission_goal_var.set(len(self.missions))
        self.update_mission_goal_limit()
        self.sync_state_mission_objectives()
        self.redraw_mission_tree()
        if (
            hasattr(self, 'workspace_tabs')
            and hasattr(self, 'advanced_tab')
            and self.workspace_tabs.select() == str(self.advanced_tab)
        ):
            self.refresh_advanced_pool_views()

        if not self.missions:
            self.append_log('No missions found. Check INI/BattleClient.ini and game root paths.', error=True)
            return

        children = self.missions_tree.get_children()
        if children:
            self.missions_tree.selection_set(children[0])
            self.selected_index.set(int(children[0]))
        self.append_log(f'Loaded {len(self.missions)} missions.')
