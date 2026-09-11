"""Generation methods shared with launcher; no GUI dependency."""

from randomizer.rewards.arsenal import ARSENAL_MODE, generate_mission_arsenals
from randomizer.rewards.enemy_scaling import ENEMY_REWARD_PLAN_VERSION, plan_enemy_check_rewards
from randomizer.missions.catalogue import LATE_FOEHN_MISSION_CODES, LOW_LEVEL_MISSION_COUNT, NO_BUILD_MISSION_CODES, STARTING_UNLOCKED_MISSIONS, campaign_mission_counts, classic_mission_order, seed_campaign_limits, seed_mission_order
from randomizer.rewards.catalogue import REWARD_POOL, check_rewards
from randomizer.progression.grid import create_grid, grid_opening_mission_count
from randomizer.maps.rules import now_stamp
import random

CHECK_SCHEMA_VERSION = 18


class SeedGeneration:
    def build_seed_generation(self, options):
        progress = options.get('_progress') or (lambda *_args: None)
        progress('Building deterministic mission order.', 1, 5)
        seed = options['seed']
        seed_missions = options['seed_missions']
        mission_goal = options['mission_goal']
        rewards_per_check = options['rewards_per_check']
        rewards_on_victory_only = options['rewards_on_victory_only']
        use_act_based_reward_multipliers = options[
            'use_act_based_reward_multipliers'
        ]
        unlock_all_grid_rewards = options['unlock_all_grid_rewards']
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
        progress('Planning base mission rewards.', 3, 5)
        mission_checks = self.build_mission_checks(
            mission_codes,
            seed,
            rewards_per_check=rewards_per_check,
            rewards_on_victory_only=rewards_on_victory_only,
            use_act_based_reward_multipliers=(
                use_act_based_reward_multipliers
            ),
            progression_mode=progression_mode,
            grid=grid,
            starting_rewards=starting_rewards,
            progress=progress,
        )
        enemy_reward_plan = plan_enemy_check_rewards(
            seed,
            reward_settings.get('enemy_scaling'),
            REWARD_POOL,
            mission_codes,
            mission_checks,
        )
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
            'use_act_based_reward_multipliers': (
                use_act_based_reward_multipliers
            ),
            'unlock_all_rewards_after_final_grid_mission': unlock_all_grid_rewards,
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
            'enemy_reward_plan_version': ENEMY_REWARD_PLAN_VERSION,
            'enemy_reward_plan': enemy_reward_plan,
            'enemy_reward_applications': {},
            'mission_arsenals': mission_arsenals,
            'check_schema_version': CHECK_SCHEMA_VERSION,
        }
        if grid is not None:
            state['grid'] = grid
        return {
            'state': state,
            'seed': seed,
            'seed_was_explicit': options.get('seed_was_explicit', False),
            'mission_goal': mission_goal,
            'rewards_per_check': rewards_per_check,
            'rewards_on_victory_only': rewards_on_victory_only,
            'use_act_based_reward_multipliers': (
                use_act_based_reward_multipliers
            ),
            'unlock_all_rewards_after_final_grid_mission': unlock_all_grid_rewards,
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
        }

