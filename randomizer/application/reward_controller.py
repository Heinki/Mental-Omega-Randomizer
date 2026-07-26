"""Reward filtering, mission checks, and earned reward state."""

from ._dependencies import (
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
    country_family,
    linked_buff_variant_ids,
    log_event,
    map_house_records,
    normalize_faction,
    parse_missions,
    plan_seed_rewards,
    player_house_from_map,
    tech_ids_for_rewards,
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
        return plan_seed_rewards(
            mission_codes,
            seed,
            slots_by_code,
            progression_mode=progression_mode,
            grid=grid,
            reward_factions_for_code=self.reward_factions_for_code,
            reward_pool_for_code=self.reward_pool_for_code,
            configured_reward_pool=self.configured_reward_pool,
            starting_unlocked_tech_ids=self.active_starting_tier_one_access_ids(),
            require_access_for_unit_buffs=self.randomize_unit_access_enabled(),
            share_role_buffs=self.share_chaos_role_buffs_enabled(),
        )

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
