"""Generation methods shared with launcher; no GUI dependency."""

from randomizer.rewards.arsenal import ARSENAL_MODE, normalize_arsenal_settings
from randomizer.rewards.catalogue import BUFF_TYPES, POWER_BUFF_TYPES, linked_buff_variant_ids
from randomizer.ui.config import REWARD_MODES
from randomizer.missions.overrides import STANDARD_STARTER_FAMILIES_BY_CAMPAIGN
from randomizer.missions.safety import expanded_tier_one_defense_ids, concrete_tier_one_starter_ids, random_chaos_tier_one_unit_ids, random_chaos_tier_one_defense_ids, select_tier_one_unit_variants, standard_tier_one_defense_markers, standard_tier_one_unit_markers, tier_one_defense_ids, tier_one_unit_ids
from randomizer.rewards.access_limits import normalize_access_limits
from randomizer.rewards.enemy_scaling import normalize_enemy_scaling_settings
from randomizer.rewards.weights import normalize_reward_weights
from randomizer.rewards.starting import normalize_starting_reward_count, normalize_starting_reward_types, normalize_starting_unlock_reward_names
import random




class GenerationSettings:
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
        access_limits = normalize_access_limits(
            generation_config.get('access_limits')
        )
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
        enemy_scaling = normalize_enemy_scaling_settings(
            generation_config.get('enemy_scaling')
        )
        if generation_config.get('reward_mode') in {
            'Chaos', 'Chaos (Experimental)', ARSENAL_MODE,
        }:
            randomize_access = True
        return {
            'arsenal': arsenal_settings,
            'randomize_unit_access': randomize_access,
            'access_limits': access_limits,
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
            'enemy_scaling': enemy_scaling,
        }

    def active_reward_settings(self):
        override = self.__dict__.get('_reward_settings_override')
        if override is not None:
            source = override
        elif self.state and isinstance(self.state.get('reward_settings'), dict):
            source = self.state.get('reward_settings', {})
        else:
            source = None
        reward_mode = self.active_reward_mode()
        cached = self.__dict__.get('_active_reward_settings_cache')
        if (
            source is not None
            and cached is not None
            and cached[0] is source
            and cached[1] == reward_mode
        ):
            return cached[2]
        settings = (
            dict(source)
            if source is not None
            else self.current_reward_settings()
        )
        settings.setdefault('randomize_unit_access', True)
        settings['access_limits'] = normalize_access_limits(
            settings.get('access_limits')
        )
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
        if reward_mode in {'Chaos', ARSENAL_MODE}:
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
        settings['enemy_scaling'] = normalize_enemy_scaling_settings(
            settings.get('enemy_scaling')
        )
        if source is not None:
            self._active_reward_settings_cache = (
                source, reward_mode, settings
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
            variant_id
            for unit_id in settings.get('excluded_unit_access_ids', [])
            for variant_id in linked_buff_variant_ids(unit_id)
        }
        if self.active_reward_mode() == 'Chaos':
            rng = random.Random(f'{seed}:starting-tier-one')
            return list(random_chaos_tier_one_unit_ids(
                rng,
                excluded_unit_ids=excluded_ids,
            ))

        selected = []
        for family in self.active_standard_starter_families():
            selected.extend(select_tier_one_unit_variants(
                random.Random(
                    f'{seed}:starting-tier-one-standard:{family}'
                ),
                tier_one_unit_ids((family,)),
                families=(family,),
                excluded_unit_ids=excluded_ids,
            ))
        return [
            unit_id
            for unit_id in selected
            if not linked_buff_variant_ids(unit_id).intersection(excluded_ids)
        ]

    def tier_one_starters_are_concrete(self):
        """Return whether one fixed roster covers the complete run."""
        return bool(
            self.active_reward_mode() == 'Chaos'
            or self.active_progression_mode() == 'Shop Mode'
        )

    def active_starting_tier_one_unit_ids(self):
        override = self.__dict__.get('_starting_unit_ids_override')
        if override is not None:
            unit_ids = list(override)
            return list(concrete_tier_one_starter_ids(unit_ids))
        elif self.state:
            unit_ids = [
                str(unit_id).upper()
                for unit_id in self.state.get('starting_unit_ids', [])
                if unit_id
            ]
        else:
            return self.starting_tier_one_unit_ids_for_seed(
                self.seed_var.get() if hasattr(self, 'seed_var') else '',
            )
        if self.tier_one_starters_are_concrete():
            concrete_ids = list(concrete_tier_one_starter_ids(unit_ids))
            if (
                self.active_reward_mode() == 'Chaos'
                and unit_ids
                and len(standard_tier_one_unit_markers(concrete_ids))
                < len(tier_one_unit_ids(('allies',)))
            ):
                seed = str(
                    (self.state or {}).get('seed')
                    or (
                        self.seed_var.get()
                        if hasattr(self, 'seed_var') else ''
                    )
                )
                return self.starting_tier_one_unit_ids_for_seed(
                    seed,
                    self.active_reward_settings(),
                )
            return concrete_ids
        if not unit_ids:
            return []
        seed = str(
            (self.state or {}).get('seed')
            or (self.seed_var.get() if hasattr(self, 'seed_var') else '')
        )
        return self.starting_tier_one_unit_ids_for_seed(
            seed,
            self.active_reward_settings(),
        )

    def active_starting_tier_one_expanded_ids(self):
        """Return the exact concrete starter identities active in this run."""
        excluded_ids = {
            str(unit_id).upper()
            for unit_id in self.active_reward_settings().get(
                'excluded_unit_access_ids', []
            )
        }
        unit_ids = self.active_starting_tier_one_unit_ids()
        return set(unit_ids) - excluded_ids

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
            variant_id
            for unit_id in settings.get('excluded_unit_access_ids', [])
            for variant_id in linked_buff_variant_ids(unit_id)
        }
        if self.active_reward_mode() == 'Chaos':
            if seed is None:
                seed = self.seed_var.get() if hasattr(self, 'seed_var') else ''
            rng = random.Random(f'{seed}:starting-tier-one-defenses')
            return list(random_chaos_tier_one_defense_ids(
                rng,
                excluded_unit_ids=excluded_ids,
            ))
        families = self.active_standard_starter_families()
        marker = tier_one_defense_ids(families)
        eligible_ids = expanded_tier_one_defense_ids(
            marker,
            families=families,
        )
        return list(marker) if eligible_ids - excluded_ids else []

    def active_starting_tier_one_defense_ids(self):
        override = self.__dict__.get('_starting_defense_ids_override')
        if override is not None:
            defense_ids = list(override)
        elif self.state:
            defense_ids = [
                str(unit_id).upper()
                for unit_id in self.state.get('starting_defense_ids', [])
                if unit_id
            ]
        else:
            return self.starting_tier_one_defense_ids_for_seed()
        if self.tier_one_starters_are_concrete():
            return defense_ids
        return list(standard_tier_one_defense_markers(defense_ids))

    def active_starting_tier_one_defense_expanded_ids(self):
        excluded_ids = {
            str(unit_id).upper()
            for unit_id in self.active_reward_settings().get(
                'excluded_unit_access_ids', []
            )
        }
        defense_ids = self.active_starting_tier_one_defense_ids()
        if self.tier_one_starters_are_concrete():
            return set(defense_ids) - excluded_ids
        return expanded_tier_one_defense_ids(
            defense_ids,
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

