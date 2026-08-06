"""Deterministic seed creation and mission-check completion."""

from ._dependencies import (
    ARSENAL_MODE,
    CAMPAIGN_FILTERS,
    CHECK_SCHEMA_VERSION,
    CONFIG_PATH,
    DEFAULT_MISSION_GOAL,
    DEFAULT_REWARDS_PER_CHECK,
    LATE_FOEHN_MISSION_CODES,
    LOW_LEVEL_MISSION_COUNT,
    MAX_REWARDS_PER_CHECK,
    NO_BUILD_MISSION_CODES,
    REWARDS_PER_CHECK_MAXIMUM_MESSAGE,
    REWARDS_PER_CHECK_MESSAGE_THRESHOLDS,
    REWARD_POOL,
    STARTING_UNLOCKED_MISSIONS,
    campaign_mission_counts,
    check_rewards,
    classic_mission_order,
    create_grid,
    filter_missions_by_build_settings,
    generate_mission_arsenals,
    grid_opening_mission_count,
    log_event,
    messagebox,
    normalize_faction,
    now_stamp,
    random,
    reward_display_name,
    reward_names,
    seed_campaign_limits,
    seed_mission_order,
    tk,
    tier_one_role_label,
    unit_display_label,
    UNSUPPORTED_AI_REWARD_REASONS,
    enemy_progress_events,
    normalize_enemy_scaling_settings,
    plan_enemy_progress_rewards,
)

class SeedController:

    def on_new_seed(self):
        if self.gameplay_settings_locked():
            return
        if self.state and self.state.get('completed_missions'):
            confirmed = messagebox.askyesno(
                'Start New Seed',
                'This will replace the current randomizer progress. Start a new seed?',
            )
            if not confirmed:
                return

        self.seed_var.set(f'MO-{random.randrange(0x10000000):08X}')
        self.generate_seed_from_settings()

    def generate_seed_from_settings(self):
        if self.gameplay_settings_locked():
            return
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
        rewards_on_victory_only = bool(
            self.rewards_on_victory_only_var.get()
        )
        reward_settings = self.current_reward_settings()
        arsenal_mode = self.reward_mode_var.get() == ARSENAL_MODE
        if arsenal_mode:
            reward_settings = dict(reward_settings)
            reward_settings.update({
                'randomize_unit_access': True,
                'start_with_tier_one_units': False,
                'start_with_tier_one_defenses': False,
                'starting_reward_count': 0,
                'starting_unlock_rewards': [],
            })
            arsenal_settings = reward_settings['arsenal']
            if not arsenal_settings['factions']:
                self.append_log(
                    'Cannot generate seed: Randomizer Arsenal needs at least one faction.',
                    error=True,
                )
                return
            if not any(
                count
                for tier in arsenal_settings['roster_sizes'].values()
                for count in tier.values()
            ) and not any(arsenal_settings['power_counts'].values()):
                self.append_log(
                    'Cannot generate seed: Randomizer Arsenal roster sizes are all zero.',
                    error=True,
                )
                return
            if not (
                reward_settings['include_buff_rewards']
                or reward_settings['include_power_buff_rewards']
            ):
                self.append_log(
                    'Cannot generate seed: Randomizer Arsenal rewards must enable unit or power buffs.',
                    error=True,
                )
                return
        power_sources_enabled = any((
            reward_settings['include_superweapon_rewards'],
            reward_settings['include_secondary_superweapon_rewards'],
            reward_settings['include_aid_power_rewards'],
        ))
        if not any((
            reward_settings['randomize_unit_access'],
            reward_settings['include_buff_rewards'],
            reward_settings['include_superweapon_rewards'],
            reward_settings['include_secondary_superweapon_rewards'],
            reward_settings['include_aid_power_rewards'],
            (
                reward_settings['include_power_buff_rewards']
                and power_sources_enabled
            ),
            reward_settings['enemy_scaling']['reward_enabled'],
        )):
            self.append_log('Cannot generate seed: enable at least one reward-pool option.', error=True)
            return
        if reward_settings['include_buff_rewards'] and not reward_settings['enabled_buff_types']:
            self.append_log('Cannot generate seed: buff rewards are enabled but no buff types are selected.', error=True)
            return
        if (
            reward_settings['include_power_buff_rewards']
            and power_sources_enabled
            and not reward_settings['enabled_power_buff_types']
        ):
            self.append_log(
                'Cannot generate seed: power buffs are enabled but no power buff types are selected.',
                error=True,
            )
            return
        if not any(
            reward_settings['reward_weights']['main'].values()
        ):
            self.append_log(
                'Cannot generate seed: enable at least one main reward weight.',
                error=True,
            )
            return
        if (
            reward_settings['starting_reward_count'] > 0
            and not reward_settings['starting_reward_types']
        ):
            self.append_log(
                'Cannot generate seed: Starting Rewards has no allowed reward types.',
                error=True,
            )
            return

        generation_context = {
            'campaign_filter': self.campaign_var.get(),
            'reward_mode': self.reward_mode_var.get(),
        }
        self._seed_generation_context = generation_context
        self._reward_settings_override = reward_settings
        starting_unit_ids = self.starting_tier_one_unit_ids_for_seed(seed, reward_settings)
        starting_defense_ids = self.starting_tier_one_defense_ids_for_seed(
            reward_settings,
            seed=seed,
        )
        self._starting_unit_ids_override = starting_unit_ids
        self._starting_defense_ids_override = starting_defense_ids
        options = {
            **generation_context,
            'seed': seed,
            'seed_missions': list(seed_missions),
            'mission_goal': mission_goal,
            'rewards_per_check': rewards_per_check,
            'rewards_on_victory_only': rewards_on_victory_only,
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
            '_progress': self.queue_busy_progress,
        }
        self.run_in_background(
            'Generating new randomizer run…',
            'Building mission order and reward plan. Large reward pools can take a while.',
            lambda: self.build_seed_generation(options),
            self.finish_seed_generation,
            self.handle_seed_generation_error,
        )

    def build_seed_generation(self, options):
        progress = options.get('_progress') or (lambda *_args: None)
        progress('Building deterministic mission order.', 1, 5)
        seed = options['seed']
        seed_missions = options['seed_missions']
        mission_goal = options['mission_goal']
        rewards_per_check = options['rewards_per_check']
        rewards_on_victory_only = options['rewards_on_victory_only']
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
        mission_arsenals = {}
        if options['reward_mode'] == ARSENAL_MODE:
            progress('Building seed-fixed mission arsenals.', 2, 5)
            mission_arsenals = generate_mission_arsenals(
                seed,
                mission_codes,
                reward_settings,
                reward_settings.get('arsenal'),
            )
            empty_codes = [
                code for code, arsenal in mission_arsenals.items()
                if not arsenal.get('units') and not arsenal.get('powers')
            ]
            if empty_codes:
                raise ValueError(
                    'Cannot generate seed: Arsenal exclusions leave no content for '
                    + ', '.join(empty_codes[:5])
                    + ('.' if len(empty_codes) <= 5 else ', and more.')
                )
            self._arsenal_override = mission_arsenals
        empty_reward_codes = (
            [
                code for code in mission_codes
                if not self.reward_pool_for_code(code)
            ]
            if options['reward_mode'] == ARSENAL_MODE
            else (
                [] if any(
                    self.reward_pool_for_code(code) for code in mission_codes
                ) else list(mission_codes[:1])
            )
        )
        if empty_reward_codes:
            detail = (
                ' for ' + ', '.join(empty_reward_codes[:5])
                + (', and more' if len(empty_reward_codes) > 5 else '')
                if options['reward_mode'] == ARSENAL_MODE else ''
            )
            raise ValueError(
                'Cannot generate seed: selected reward settings produce no '
                f'available rewards{detail}.'
            )

        progress('Selecting starting rewards.', 2, 5)
        manual_starting_rewards = (
            [] if options['reward_mode'] == ARSENAL_MODE
            else self.configured_manual_starting_rewards()
        )
        random_starting_rewards = (
            [] if options['reward_mode'] == ARSENAL_MODE
            else self.generate_starting_reward_plan(
                seed,
                initial_rewards=manual_starting_rewards,
            )
        )
        starting_rewards = manual_starting_rewards + random_starting_rewards
        enemy_settings = normalize_enemy_scaling_settings(
            reward_settings.get('enemy_scaling')
        )
        enemy_event_checks = {
            code: [
                {'id': check_id}
                for check_id, _name, _hint
                in self.objective_templates_for_code(code)
            ]
            for code in mission_codes
        }
        completion_events = enemy_progress_events(
            mission_codes, enemy_event_checks
        )
        enemy_progress_requested = sum(
            enemy_settings['rewards_per_completed_objective']
            if event['basis'] == 'objectives'
            else enemy_settings['rewards_per_completed_mission']
            for event in completion_events
        )
        progress_planning_settings = enemy_settings
        if (
            enemy_settings['reward_enabled']
            and enemy_progress_requested > 0
        ):
            # Both sources share one global cap. Reserve one stack per
            # multi-stack effect for normal reward rolls. For cap-one
            # effects, split effect IDs between the two sources so neither
            # option silently starves the other when several are enabled.
            progress_planning_settings = dict(enemy_settings)
            allowed_ids = sorted(enemy_settings['allowed_buff_ids'])
            progress_planning_settings['caps'] = {
                effect_id: (
                    max(0, cap - 1)
                    if cap > 1
                    else (
                        cap
                        if effect_id in allowed_ids
                        and allowed_ids.index(effect_id) % 2 == 0
                        else 0
                    )
                )
                for effect_id, cap in enemy_settings['caps'].items()
            }
        enemy_progress_plan = plan_enemy_progress_rewards(
            seed,
            progress_planning_settings,
            REWARD_POOL,
            completion_events,
            starting_rewards,
        )
        for entry in enemy_progress_plan:
            reward = dict(entry.get('reward', {}))
            effect_id = str(reward.get('enemy_effect_id') or '')
            reward['enemy_maximum'] = enemy_settings['caps'].get(
                effect_id, reward.get('enemy_maximum', 1)
            )
            entry['reward'] = reward
        progress('Planning base mission rewards.', 3, 5)
        mission_checks = self.build_mission_checks(
            mission_codes,
            seed,
            rewards_per_check=rewards_per_check,
            rewards_on_victory_only=rewards_on_victory_only,
            progression_mode=progression_mode,
            grid=grid,
            starting_rewards=starting_rewards,
            enemy_progress_plan=enemy_progress_plan,
            progress=progress,
        )
        ai_rewards_enabled = bool(
            enemy_settings['reward_enabled']
            or enemy_settings['rewards_per_completed_objective'] > 0
            or enemy_settings['rewards_per_completed_mission'] > 0
        )
        unsupported_ai_rewards = (
            list(UNSUPPORTED_AI_REWARD_REASONS) if ai_rewards_enabled else []
        )
        for reason in unsupported_ai_rewards:
            log_event('ai_reward_type_skipped', reason=reason)
        progress('Finalizing generated run.', 5, 5)
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
            'rewards_on_victory_only': rewards_on_victory_only,
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
            'earned_rewards': [
                reward for reward in starting_rewards
                if not reward.get('max_rewards_achieved')
            ],
            'starting_rewards': starting_rewards,
            'manual_starting_rewards': manual_starting_rewards,
            'random_starting_rewards': random_starting_rewards,
            'starting_defense_ids': starting_defense_ids,
            'starting_unit_ids': starting_unit_ids,
            'reward_queue': rewards,
            'mission_checks': mission_checks,
            'mission_objectives': mission_objectives,
            'reward_settings': reward_settings,
            'enemy_progress_plan': enemy_progress_plan,
            'enemy_progress_earned': [],
            'enemy_progress_requested': enemy_progress_requested,
            'enemy_reward_applications': {},
            'mission_arsenals': mission_arsenals,
            'check_schema_version': CHECK_SCHEMA_VERSION,
        }
        if grid is not None:
            state['grid'] = grid
        return {
            'state': state,
            'seed': seed,
            'mission_goal': mission_goal,
            'rewards_per_check': rewards_per_check,
            'rewards_on_victory_only': rewards_on_victory_only,
            'starting_defense_ids': starting_defense_ids,
            'starting_unit_ids': starting_unit_ids,
            'starting_rewards': starting_rewards,
            'manual_starting_rewards': manual_starting_rewards,
            'random_starting_rewards': random_starting_rewards,
            'campaign_counts': campaign_counts,
            'campaign_limits': campaign_limits,
            'progression_mode': progression_mode,
            'grid': grid,
            'campaign_filter': options['campaign_filter'],
            'reward_mode': options['reward_mode'],
            'reward_settings': reward_settings,
            'mission_codes': mission_codes,
            'unsupported_ai_rewards': unsupported_ai_rewards,
            'enemy_progress_requested': enemy_progress_requested,
        }

    def finish_seed_generation(self, result):
        self.state = result['state']
        self._reward_settings_override = None
        self._starting_defense_ids_override = None
        self._starting_unit_ids_override = None
        self._arsenal_override = None
        self._seed_generation_context = None
        seed = result['seed']
        mission_goal = result['mission_goal']
        rewards_per_check = result['rewards_per_check']
        rewards_on_victory_only = result['rewards_on_victory_only']
        starting_defense_ids = result['starting_defense_ids']
        starting_unit_ids = result['starting_unit_ids']
        starting_rewards = result['starting_rewards']
        manual_starting_rewards = result['manual_starting_rewards']
        random_starting_rewards = result['random_starting_rewards']
        campaign_counts = result['campaign_counts']
        campaign_limits = result['campaign_limits']
        progression_mode = result['progression_mode']
        grid = result['grid']
        self.seed_var.set(seed)
        self.reset_archipelago_after_new_seed()
        self.save_state()
        self.save_launcher_config(seed, mission_goal, rewards_per_check)
        self.disable_generated_rules_for_client()
        self.redraw_mission_tree()
        self.update_header_summary()
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
            f'{rewards_per_check} reward(s) per '
            f'{"mission, multiplied by mission weight" if rewards_on_victory_only else "objective"}. '
            f'{opening} '
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
        if manual_starting_rewards:
            self.append_log(
                'Starting unlocks: ' + reward_names(manual_starting_rewards)
            )
        if random_starting_rewards:
            self.append_log(
                'Random starting rewards: ' + reward_names(random_starting_rewards)
            )
        for reason in result.get('unsupported_ai_rewards', []):
            self.append_log(f'Skipped unsupported reward type: {reason}')
        planned_ai_completions = len(
            self.state.get('enemy_progress_plan', [])
        )
        requested_ai_completions = int(
            result.get('enemy_progress_requested', 0)
        )
        if planned_ai_completions < requested_ai_completions:
            self.append_log(
                'AI completion rewards reached configured global caps: '
                f'{planned_ai_completions}/{requested_ai_completions} '
                'requested rewards planned. Later completion draws reroll '
                'until every supported effect is capped, then stop.'
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
            ai_completion_rewards=len(
                result['state'].get('enemy_progress_plan', [])
            ),
            ai_completion_rewards_requested=result.get(
                'enemy_progress_requested', 0
            ),
            starting_defense_ids=starting_defense_ids,
            starting_unit_ids=starting_unit_ids,
            starting_rewards=[reward.get('name') for reward in starting_rewards],
            manual_starting_rewards=[
                reward.get('name') for reward in manual_starting_rewards
            ],
        )

    def handle_seed_generation_error(self, exc, detail):
        self._reward_settings_override = None
        self._starting_defense_ids_override = None
        self._starting_unit_ids_override = None
        self._arsenal_override = None
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
        archipelago_active = self.archipelago_run_active()
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
                    if was_released and not archipelago_active:
                        previously_released_rewards.extend(check_rewards(check))
                    elif not archipelago_active:
                        earned_now.extend(check_rewards(check))
        else:
            cleared_assistance = 0
            was_released = bool(target.pop('released', False))
            target['unlocked'] = True
            if was_released and not archipelago_active:
                previously_released_rewards.extend(check_rewards(target))
            elif not archipelago_active:
                earned_now.extend(check_rewards(target))

        self.sync_grid_progression()
        if grid_goal_victory and not archipelago_active:
            released_rewards, released_checks = self.release_remaining_grid_rewards()
        self.state['earned_rewards'] = self.earned_rewards_from_checks()
        prior_ai_milestones = {
            (
                str(item.get('basis') or ''),
                int(item.get('event_index', 0)),
            )
            for item in self.state.get('enemy_progress_earned', [])
            if isinstance(item, dict)
        }
        enemy_progress_changed = self.sync_enemy_progress_milestones(
            code, target
        )
        self.save_state()
        if check_id == 'victory':
            self.report_archipelago_mission_completion(code)
        else:
            self.report_archipelago_objective_check(code, check_id)
        reward_note = (
            'Archipelago check reported; rewards arrive from server.'
            if archipelago_active
            else f'Reward(s) earned: {reward_names(earned_now)}'
            if earned_now
            else f'{len(previously_released_rewards)} assigned reward(s) were already released at Grid victory.'
            if previously_released_rewards
            else 'No reward assigned.'
        )
        self.append_log(
            f'{source}: {code} {target.get("name", check_id)} complete. '
            + reward_note
        )
        if enemy_progress_changed:
            milestones = {
                (
                    str(item.get('basis') or ''),
                    int(item.get('event_index', 0)),
                ): item
                for item in self.state.get('enemy_progress_earned', [])
                if isinstance(item, dict)
            }
            new_keys = set(milestones) - prior_ai_milestones
            newly_earned_ai = [
                planned
                for planned in self.state.get('enemy_progress_plan', [])
                if (
                    str(planned.get('basis') or ''),
                    int(planned.get('event_index', 0)),
                ) in new_keys
            ]
            counts_by_basis = {}
            for planned in newly_earned_ai:
                basis = str(planned.get('basis') or '')
                counts_by_basis[basis] = counts_by_basis.get(basis, 0) + 1
            for basis in ('objectives', 'missions'):
                count = counts_by_basis.get(basis, 0)
                if count:
                    label = 'objective' if basis == 'objectives' else 'mission'
                    self.append_log(
                        f'AI {label} bonus stacks earned: {count}. '
                        'These are separate from the normal player reward count.'
                    )
            for planned in newly_earned_ai:
                key = (
                    str(planned.get('basis') or ''),
                    int(planned.get('event_index', 0)),
                )
                label = (
                    'AI Objective Bonus'
                    if key[0] == 'objectives'
                    else 'AI Mission Bonus'
                )
                reward_text = reward_display_name(
                    planned.get('reward', {})
                ).removeprefix('AI Reward: ')
                self.append_log(
                    f'{label}: {reward_text} - '
                    f'{milestones[key].get("earned_from", "completed progress")}. '
                    'Exact hostile Houses apply on next prepared mission map.'
                )
        reward_summary = self.mission_reward_summary(code)
        if check_id == 'victory':
            final_note = (
                f'Mission Reward Multiplier: x{reward_summary["multiplier"]}. '
                f'Base rewards: {reward_summary["base_rewards"]}. '
                f'Final rewards: {reward_summary["final_rewards"]}.'
            )
            if reward_summary['max_rewards_achieved']:
                final_note += ' Max rewards achieved.'
            self.append_log(final_note)
        log_event(
            'mission_check_unlocked',
            seed=self.state.get('seed', ''),
            code=code,
            check_id=check_id,
            check_name=target.get('name', check_id),
            source=source,
            rewards=[reward.get('name') for reward in earned_now],
            previously_released_rewards=len(previously_released_rewards),
            reward_multiplier=reward_summary['multiplier'],
            base_rewards=reward_summary['base_rewards'],
            final_rewards=reward_summary['final_rewards'],
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
            if archipelago_active:
                self.append_log(
                    f'Grid endgoal achieved: {code}. Randomizer victory achieved. '
                    'All remaining grid missions are unlocked. Unchecked '
                    f'Archipelago locations remain pending.{unlock_note}'
                )
            else:
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

        victory_only = bool(self.rewards_on_victory_only_var.get())
        self.rewards_per_check_label.configure(
            text=(
                'Rewards per mission'
                if victory_only else 'Rewards per objective'
            )
        )
        message = self.rewards_per_check_message(value)

        self.rewards_per_check_message_label.configure(text=message)
        if message:
            self.rewards_per_check_message_label.grid()
        else:
            self.rewards_per_check_message_label.grid_remove()
