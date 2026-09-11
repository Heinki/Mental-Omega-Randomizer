"""Generate a complete run from player settings without a launcher or game install."""

from copy import deepcopy

from randomizer.config.player import DEFAULT_CONFIG, deep_merge
from randomizer.missions.catalogue import filter_missions_by_build_settings, normalize_faction
from randomizer.rewards.arsenal import ARSENAL_MODE
from randomizer.rewards.catalogue import MAX_REWARDS_PER_CHECK
from randomizer.ui.config import CAMPAIGN_FILTERS, PROGRESSION_MODES, REWARD_MODES
from .reward_controller import RewardGeneration
from .seed_controller import SeedGeneration
from .starting_unlocks import StartingUnlocks
from .state_controller import GenerationSettings


class RunGenerator(SeedGeneration, RewardGeneration, GenerationSettings, StartingUnlocks):
    """Use the same generation methods as the GUI, with explicit inputs."""

    current_reward_settings = GenerationSettings.config_reward_settings

    def __init__(self, settings, missions):
        if not isinstance(settings, dict):
            raise ValueError('launcher_settings must be a mapping.')
        if 'generation' in settings and not isinstance(settings['generation'], dict):
            raise ValueError('launcher_settings.generation must be a mapping.')
        self.config = deep_merge(DEFAULT_CONFIG, settings)
        self.state = {}
        self.missions = deepcopy(missions)
        self._mission_by_code = {mission['code']: mission for mission in self.missions}

    def active_progression_mode(self):
        return self._seed_generation_context['progression_mode']

    def generate(self, seed):
        config = self.config
        generation = config['generation']
        mode = config['progression_mode']
        campaign = config['campaign_filter']
        reward_mode = generation['reward_mode']
        for name, value, choices in (
            ('progression_mode', mode, PROGRESSION_MODES),
            ('campaign_filter', campaign, CAMPAIGN_FILTERS),
            ('generation.reward_mode', reward_mode, REWARD_MODES),
        ):
            if value not in choices:
                raise ValueError(f'Invalid {name}: {value!r}. Expected one of {choices}.')
        mission_settings = {
            key: bool(generation[key]) for key in (
                'include_no_build_missions', 'include_no_build_production_missions',
                'include_operation_missions', 'prioritize_no_build_missions',
            )
        }
        excluded = {str(code).upper() for code in generation['excluded_mission_codes']}
        missions = [
            mission for mission in self.missions
            if mission['code'].upper() not in excluded
            and (campaign == CAMPAIGN_FILTERS[0] or normalize_faction(mission.get('side', '')) == campaign)
        ]
        missions = filter_missions_by_build_settings(
            missions,
            include_true_no_build=mission_settings['include_no_build_missions'],
            include_no_build_production=mission_settings['include_no_build_production_missions'],
            include_operation_missions=mission_settings['include_operation_missions'],
        )
        if not missions:
            raise ValueError('Selected settings leave no missions to generate.')
        for key, maximum in (
            ('mission_goal', len(self.missions)),
            ('rewards_per_objective', MAX_REWARDS_PER_CHECK),
        ):
            value = config[key]
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
                raise ValueError(f'{key} must be an integer between 1 and {maximum}.')

        self._seed_generation_context = {
            'campaign_filter': campaign,
            'reward_mode': reward_mode,
            'progression_mode': mode,
            'use_act_based_reward_multipliers': bool(config['use_act_based_reward_multipliers']),
        }
        settings = self.config_reward_settings()
        if reward_mode == ARSENAL_MODE:
            settings.update(
                randomize_unit_access=True,
                start_with_tier_one_units=False,
                start_with_tier_one_defenses=False,
                starting_reward_count=0,
                starting_unlock_rewards=[],
            )
            arsenal = settings['arsenal']
            if not arsenal['factions']:
                raise ValueError('Randomizer Arsenal requires at least one faction.')
            if not any(count for tier in arsenal['roster_sizes'].values() for count in tier.values()) and not any(arsenal['power_counts'].values()):
                raise ValueError('Randomizer Arsenal roster sizes are all zero.')
            if not (settings['include_buff_rewards'] or settings['include_power_buff_rewards']):
                raise ValueError('Randomizer Arsenal requires unit or power buffs.')
        power_sources = any(settings[key] for key in (
            'include_superweapon_rewards', 'include_secondary_superweapon_rewards',
            'include_aid_power_rewards',
        ))
        if not any((
            settings['randomize_unit_access'], settings['include_buff_rewards'],
            settings['include_superweapon_rewards'],
            settings['include_secondary_superweapon_rewards'],
            settings['include_aid_power_rewards'],
            settings['include_power_buff_rewards'] and power_sources,
        )):
            raise ValueError('Enable at least one reward-pool option.')
        if settings['include_buff_rewards'] and not settings['enabled_buff_types']:
            raise ValueError('Buff rewards need at least one enabled buff type.')
        if settings['include_power_buff_rewards'] and power_sources and not settings['enabled_power_buff_types']:
            raise ValueError('Power buffs need at least one enabled power buff type.')
        if not any(settings['reward_weights']['main'].values()):
            raise ValueError('Enable at least one main reward weight.')
        if settings['starting_reward_count'] and not settings['starting_reward_types']:
            raise ValueError('Starting Rewards needs at least one allowed reward type.')

        self._reward_settings_override = settings
        units = self.starting_tier_one_unit_ids_for_seed(seed, settings)
        defenses = self.starting_tier_one_defense_ids_for_seed(settings, seed=seed)
        self._starting_unit_ids_override = units
        self._starting_defense_ids_override = defenses
        options = {
            **self._seed_generation_context,
            'seed': seed,
            'seed_was_explicit': False,
            'seed_missions': missions,
            'mission_goal': len(missions) if mode == 'Shop Mode' else min(config['mission_goal'], len(missions)),
            'rewards_per_check': config['rewards_per_objective'],
            'rewards_on_victory_only': bool(config['rewards_on_victory_only']),
            'unlock_all_grid_rewards': config['unlock_all_rewards_after_final_grid_mission'],
            'reward_settings': settings,
            'starting_unit_ids': units,
            'starting_defense_ids': defenses,
            'progression_mode': mode,
            'two_start_positions': config['grid_two_start_positions'],
            'mission_pool_settings': mission_settings,
        }
        state = self.build_seed_generation(options)['state']
        state.pop('created_at', None)
        return state
