"""Unlock display models, labels, sources, and tooltips."""

from randomizer.config.tuning import mission_assistance_stack_count

from ._dependencies import (
    ARSENAL_MODE,
    ALWAYS_AVAILABLE_TECH_IDS,
    BUFF_TARGETS,
    FACTION_ORDER,
    REWARD_POOL,
    SPECIAL_BUILDING_DEFINITIONS,
    buff_effect_lines,
    buff_stack_limit,
    canonical_reward,
    check_rewards,
    effective_buff_count,
    house_wide_buff_effect_lines,
    house_wide_buff_label,
    house_wide_buff_scope,
    is_max_rewards_achieved_reward,
    mission_assistance_multipliers,
    reward_cameo_token,
    reward_display_name,
    reward_matches_arsenal,
    reward_rule_summary,
    tech_ids_for_rewards,
    unit_display_label,
    unit_role_equivalents,
    unlocked_reward_tech_ids,
)

class UnlockDataController:

    def reward_group_label(self, tech_id):
        return unit_display_label(tech_id)

    def unit_faction(self, tech_id):
        factions = BUFF_TARGETS.get(tech_id, {}).get('factions') or []
        if len(factions) == 1:
            return factions[0]
        return 'Global' if factions else 'Other'

    def unit_faction_sort_key(self, tech_id):
        faction = self.unit_faction(tech_id)
        rank = FACTION_ORDER.index(faction) if faction in FACTION_ORDER else len(FACTION_ORDER)
        return (rank, unit_display_label(tech_id).lower())

    def reward_house_wide_buff_scope(self, reward):
        return house_wide_buff_scope(
            reward,
            unit_specific_mode=(
                self.active_reward_mode() in {'Chaos', ARSENAL_MODE}
            ),
        )

    def mission_assistance_effect_text(self, stacks):
        stacks = mission_assistance_stack_count(stacks)
        multipliers = mission_assistance_multipliers(stacks)
        range_cells = multipliers['range']
        range_unit = 'cell' if range_cells == 1 else 'cells'
        return (
            f'production time {round((1 - multipliers["production"]) * 100)}% shorter, '
            f'cost {round((1 - multipliers["cost"]) * 100)}% cheaper, '
            f'movement speed up to {round((multipliers["speed"] - 1) * 100)}% faster '
            '(safe ceilings: infantry 8, vehicles/naval 12, aircraft 30), '
            f'health {round((multipliers["health"] - 1) * 100)}% higher, '
            f'weapon damage {round((multipliers["damage"] - 1) * 100)}% higher, '
            f'damage taken {round((1 - multipliers["armor"]) * 100)}% lower, '
            f'fire rate {round(((1 / multipliers["rof"]) - 1) * 100)}% faster, '
            f'attack range +{range_cells:g} {range_unit}'
        )

    def build_unlock_display_groups(self, earned):
        """Group canonical earned rewards for Unlocks text rendering."""
        groups = {}
        shared_groups = {}
        house_buff_groups = {}
        share_chaos_role_buffs = self.share_chaos_role_buffs_enabled()
        share_foehn_roles = self.foehn_standard_bundles_enabled()

        def group_for(tech_id):
            return groups.setdefault(tech_id, {
                'label': self.reward_group_label(tech_id),
                'access': {},
                'buffs': {},
                'other': [],
            })

        for reward in earned:
            house_scope = self.reward_house_wide_buff_scope(reward)
            if house_scope:
                entry = house_buff_groups.setdefault(
                    house_scope,
                    {'reward': reward, 'count': 0},
                )
                entry['count'] += 1
                continue

            bundle_units = reward.get('bundle_units') or []
            if bundle_units:
                unit_ids = tuple(sorted(set(bundle_units), key=self.unit_faction_sort_key))
                shared_group = shared_groups.setdefault(
                    unit_ids,
                    {'access': {}, 'buffs': {}},
                )
                shared_group['access'].setdefault(reward.get('name', 'Shared Access'), reward)
                continue

            if reward.get('kind') == 'buff' and reward.get('unit'):
                source_unit = reward['unit']
                equivalent_units = unit_role_equivalents(source_unit)
                if (
                    (share_chaos_role_buffs or share_foehn_roles)
                    and not reward.get('global_buff')
                    and len(equivalent_units) > 1
                ):
                    if share_foehn_roles:
                        equivalent_units = {
                            unit_id
                            for unit_id in equivalent_units
                            if self.unit_faction(unit_id) in {'Allies', 'Soviets'}
                        }
                    if len(equivalent_units) < 2:
                        group = group_for(source_unit)
                        key = reward.get('buff_type', reward.get('name', 'buff'))
                        entry = group['buffs'].setdefault(
                            key,
                            {'reward': reward, 'count': 0},
                        )
                        entry['count'] += 1
                        continue
                    unit_ids = tuple(sorted(equivalent_units, key=self.unit_faction_sort_key))
                    shared_group = shared_groups.setdefault(
                        unit_ids,
                        {'access': {}, 'buffs': {}},
                    )
                    key = reward.get('buff_type', reward.get('name', 'buff'))
                    display_reward = dict(reward)
                    display_reward.pop('name', None)
                    entry = shared_group['buffs'].setdefault(
                        key,
                        {'reward': display_reward, 'count': 0},
                    )
                    entry['count'] += 1
                else:
                    group = group_for(source_unit)
                    key = reward.get('buff_type', reward.get('name', 'buff'))
                    entry = group['buffs'].setdefault(key, {'reward': reward, 'count': 0})
                    entry['count'] += 1
                continue

            tech_ids = sorted(tech_ids_for_rewards([reward]))
            if tech_ids:
                for tech_id in tech_ids:
                    group_for(tech_id)['access'].setdefault(reward.get('name', tech_id), reward)
            else:
                groups.setdefault('Other', {
                    'label': 'Other',
                    'access': {},
                    'buffs': {},
                    'other': [],
                })['other'].append(reward)

        return groups, shared_groups, house_buff_groups

    def current_unlocks_text(self):
        if not self.state:
            return 'No randomizer seed generated yet.'

        lines = self.mission_arsenal_summary_lines()
        starting_unit_ids = self.display_starting_tier_one_unit_ids()
        if starting_unit_ids:
            heading = 'Starting Tier 1 Units'
            lines.extend([heading, '=' * len(heading)])
            for unit_id in sorted(set(starting_unit_ids), key=self.unit_faction_sort_key):
                lines.append(unit_display_label(unit_id))
            lines.append('')
        starting_defense_ids = self.display_starting_tier_one_defense_ids()
        if starting_defense_ids:
            heading = 'Starting Tier 1 Defenses'
            lines.extend([heading, '=' * len(heading)])
            for unit_id in starting_defense_ids:
                lines.append(unit_display_label(unit_id))
            lines.append('')
        if any(
            is_max_rewards_achieved_reward(reward)
            for reward in self.state.get('starting_rewards', [])
        ):
            heading = 'Starting Rewards'
            lines.extend([heading, '=' * len(heading), 'Max rewards achieved.', ''])
        selected = self.selected_mission()
        if selected and self.failure_assistance_enabled():
            code = selected['code']
            stacks = self.mission_failure_stack(code)
            if stacks:
                heading = f'Retry Assistance — {selected["title"]}'
                lines.extend([
                    heading,
                    '=' * len(heading),
                    f'{stacks} stack(s), for this mission only',
                    self.mission_assistance_effect_text(stacks).capitalize() + '.',
                    '',
                ])

        earned = []
        manual_names = self.manual_starting_reward_names_in_state()
        for canonical in self.canonical_earned_rewards():
            if (
                not canonical.get('retired_reward')
                and not canonical.get('enemy_reward')
                and (
                    canonical.get('name') in manual_names
                    or not self.standard_foehn_unit_reward(canonical)
                )
            ):
                earned.append(canonical)
        if not earned:
            if lines:
                return '\n'.join(lines).rstrip()
            return 'No unlocks or buffs earned yet.'

        share_foehn_roles = self.foehn_standard_bundles_enabled()
        groups, shared_groups, house_buff_groups = (
            self.build_unlock_display_groups(earned)
        )

        if house_buff_groups:
            heading = 'Global / House-Wide Buffs'
            lines.extend([heading, '=' * len(heading)])
            global_production_count = house_buff_groups.get(
                ('All', 'production'), {}
            ).get('count', 0)
            for scope, entry in sorted(
                house_buff_groups.items(),
                key=lambda item: house_wide_buff_label(item[0]).casefold(),
            ):
                combined_count = entry['count']
                if scope[1] == 'production' and scope[0] != 'All':
                    combined_count += global_production_count
                count = effective_buff_count(
                    entry['reward'], combined_count
                )
                lines.extend(
                    house_wide_buff_effect_lines(
                        scope,
                        count=count,
                        stack_limit=buff_stack_limit(entry['reward']),
                    )
                )
            lines.append('')

        if shared_groups:
            heading = (
                'Shared Allied / Soviet Bundles'
                if share_foehn_roles
                else 'Shared Unit Buffs'
            )
            lines.append(heading)
            lines.append('=' * len(heading))
            lines.append(
                'Each pictured role is earned together; listed bonuses apply to every pictured unit.'
                if share_foehn_roles
                else 'Every pictured unit receives the bonuses listed beneath its group.'
            )
            lines.append('')
            for unit_ids, shared_group in sorted(
                shared_groups.items(),
                key=lambda item: tuple(unit_display_label(unit_id) for unit_id in item[0]),
            ):
                lines.append(f'[[MOR_SHARED:{",".join(unit_ids)}]]')
                lines.append('  •  '.join(unit_display_label(unit_id) for unit_id in unit_ids))
                for reward in sorted(
                    shared_group['access'].values(),
                    key=lambda item: item.get('name', ''),
                ):
                    source_names = reward.get('bundle_reward_names') or [reward_display_name(reward)]
                    lines.append('  Shared access: ' + '  •  '.join(source_names))
                for _, entry in sorted(shared_group['buffs'].items()):
                    reward = entry['reward']
                    count = effective_buff_count(reward, entry['count'])
                    for summary in buff_effect_lines(reward, count=count, include_label=False):
                        lines.append(f'  {summary}')
                lines.append('')

        current_faction = None
        def summary_section(unit_id):
            if BUFF_TARGETS.get(unit_id, {}).get('category') == 'special_buildings':
                return 'Special Buildings'
            return self.unit_faction(unit_id)

        for tech_id in sorted(
            groups,
            key=lambda unit_id: (
                summary_section(unit_id) == 'Special Buildings',
                self.unit_faction_sort_key(unit_id),
            ),
        ):
            group = groups[tech_id]
            faction = summary_section(tech_id)
            if faction != current_faction:
                if lines and lines[-1] != '':
                    lines.append('')
                heading = (
                    faction
                    if faction == 'Special Buildings'
                    else
                    f'{faction} Units'
                    if faction in FACTION_ORDER
                    else f'{faction} Rewards'
                )
                lines.append(heading)
                lines.append('=' * len(heading))
                lines.append('')
                current_faction = faction
            lines.append(group['label'])
            lines.append('-' * len(group['label']))

            if group['access']:
                for reward in sorted(group['access'].values(), key=lambda item: item.get('name', '')):
                    lines.append(reward_display_name(reward))

            if group['buffs']:
                for _, entry in sorted(group['buffs'].items()):
                    reward = entry['reward']
                    count = effective_buff_count(reward, entry['count'])
                    for summary in buff_effect_lines(reward, count=count, include_label=False):
                        lines.append(f'  {summary}')

            for reward in group['other']:
                power_token = reward_cameo_token(reward)
                lines.append(f'{power_token}Reward: {reward_display_name(reward)}')
                for summary in reward_rule_summary(reward):
                    lines.append(f'  {summary}')

            lines.append('')

        return '\n'.join(lines).rstrip()

    def mission_arsenal_summary_lines(self):
        """Describe selected mission's temporary roster inside existing Summary."""
        if not self.state or self.active_reward_mode() != ARSENAL_MODE:
            return []
        selected = self.selected_mission()
        if not selected:
            return [
                'Mission Arsenal',
                '===============',
                'Select a mission to inspect its seed-fixed temporary arsenal.',
                '',
            ]
        code = selected.get('code', '')
        arsenal = self.mission_arsenal(code)
        heading = f'Mission Arsenal - {selected.get("title", code)} ({code})'
        lines = [
            heading,
            '=' * len(heading),
            'Seed-fixed for this mission. Temporary; no permanent unit or power unlocks.',
            '',
        ]
        if not arsenal:
            lines.extend(('Mission is not part of the current seed.', ''))
            return lines
        tier_labels = {
            'tier_1': 'Tier 1 (TechLevel 1-2)',
            'tier_2': 'Tier 2 (TechLevel 3-6)',
            'tier_3': 'Tier 3 (TechLevel 7+)',
        }
        type_labels = {
            'infantry': 'Infantry',
            'vehicles': 'Vehicles',
            'aircraft': 'Aircraft',
            'naval': 'Naval',
        }
        for tier in ('tier_1', 'tier_2', 'tier_3'):
            tier_units = [
                entry for entry in arsenal.get('units', ())
                if entry.get('tier') == tier
            ]
            if not tier_units:
                continue
            lines.append(tier_labels[tier])
            for unit_type in ('infantry', 'vehicles', 'aircraft', 'naval'):
                units = [
                    entry for entry in tier_units
                    if entry.get('production_type') == unit_type
                ]
                if units:
                    lines.append(
                        f'  {type_labels[unit_type]}: '
                        + ', '.join(
                            f'{entry.get("label", entry.get("unit_id", "?"))} '
                            f'[{entry.get("faction", "?")}]'
                            for entry in units
                        )
                    )
            lines.append('')
        power_rewards = {
            canonical_reward(reward).get('name'): canonical_reward(reward)
            for reward in REWARD_POOL
            if canonical_reward(reward).get('kind') == 'superweapon'
        }
        lines.append('Temporary powers')
        powers = arsenal.get('powers', ())
        if powers:
            for power_type in ('offensive', 'secondary', 'aid'):
                selected_powers = [
                    entry for entry in powers
                    if entry.get('power_type') == power_type
                ]
                if selected_powers:
                    values = []
                    for entry in selected_powers:
                        reward = power_rewards.get(entry.get('reward_name'), {})
                        values.append(
                            reward_cameo_token(reward)
                            + entry.get('label', entry.get('power_id', '?'))
                        )
                    lines.append(f'  {power_type.title()}: ' + ', '.join(values))
        else:
            lines.append('  None')
        lines.extend(('', 'Active mission buffs'))
        counts = {}
        for reward in self.canonical_earned_rewards():
            if (
                not reward.get('enemy_reward')
                and reward_matches_arsenal(reward, arsenal)
            ):
                name = reward_display_name(reward)
                counts[name] = counts.get(name, 0) + 1
        if counts:
            for name in sorted(counts, key=str.casefold):
                suffix = f' x{counts[name]}' if counts[name] > 1 else ''
                lines.append(f'  {name}{suffix}')
        else:
            lines.append('  None earned yet')
        lines.append('')
        return lines

    def current_unlock_unit_ids(self):
        if not self.state:
            return []
        unit_ids = set(self.display_starting_tier_one_unit_ids())
        unit_ids.update(self.display_starting_tier_one_defense_ids())
        if self.active_reward_mode() == ARSENAL_MODE:
            selected = self.selected_mission()
            arsenal = self.mission_arsenal(selected.get('code', '')) if selected else {}
            unit_ids.update(
                str(entry.get('unit_id') or '').upper()
                for entry in arsenal.get('units', ())
                if entry.get('unit_id')
            )
        share_chaos_role_buffs = self.share_chaos_role_buffs_enabled()
        share_foehn_roles = self.foehn_standard_bundles_enabled()
        manual_names = self.manual_starting_reward_names_in_state()
        for reward in self.canonical_earned_rewards():
            if (
                reward.get('name') not in manual_names
                and self.standard_foehn_unit_reward(reward)
            ):
                continue
            if reward.get('kind') == 'buff' and reward.get('unit'):
                if not self.reward_house_wide_buff_scope(reward):
                    if (
                        (share_chaos_role_buffs or share_foehn_roles)
                        and not reward.get('global_buff')
                    ):
                        equivalents = unit_role_equivalents(reward['unit'])
                        if share_foehn_roles:
                            equivalents = {
                                unit_id
                                for unit_id in equivalents
                                if self.unit_faction(unit_id) in {'Allies', 'Soviets'}
                            }
                        unit_ids.update(equivalents)
                    else:
                        unit_ids.add(reward['unit'])
                continue
            unit_ids.update(tech_ids_for_rewards([reward]))
        return sorted(unit_ids, key=self.unit_faction_sort_key)

    def display_starting_tier_one_unit_ids(self):
        """Return concrete starter variants represented by saved role markers."""
        unit_ids = self.active_starting_tier_one_expanded_ids()
        if self.active_reward_mode() != 'Chaos':
            unit_ids = {
                unit_id
                for unit_id in unit_ids
                if self.unit_faction(unit_id) != 'Foehn'
            }
        return sorted(unit_ids, key=self.unit_faction_sort_key)

    def display_starting_tier_one_defense_ids(self):
        return sorted(
            self.active_starting_tier_one_defense_expanded_ids(),
            key=self.unit_faction_sort_key,
        )

    def unlock_dashboard_reward_keys(
        self,
        reward,
        *,
        share_role_buffs=None,
        share_foehn_roles=None,
    ):
        """Return catalogue icons affected by one serialized reward."""
        reward = canonical_reward(reward)
        if share_role_buffs is None:
            share_role_buffs = self.share_chaos_role_buffs_enabled()
        if share_foehn_roles is None:
            share_foehn_roles = self.foehn_standard_bundles_enabled()
        keys = set()
        if reward.get('buff_type') == 'starting_credits':
            keys.add('global:starting_credits')
            return keys
        house_scope = self.reward_house_wide_buff_scope(reward)
        if house_scope:
            suffix, buff_type = house_scope
            keys.add(f'house:{suffix.lower()}:{buff_type}')
            return keys
        unit_id = str(reward.get('unit') or '').upper()
        if reward.get('kind') == 'buff' and unit_id:
            keys.add(f'unit:{unit_id}')
            if (
                not reward.get('global_buff')
                and (share_role_buffs or share_foehn_roles)
            ):
                equivalents = unit_role_equivalents(unit_id)
                if share_foehn_roles:
                    equivalents = {
                        equivalent
                        for equivalent in equivalents
                        if self.unit_faction(equivalent) in {'Allies', 'Soviets'}
                    }
                keys.update(f'unit:{equivalent}' for equivalent in equivalents)
        for tech_id in tech_ids_for_rewards([reward]):
            if tech_id in BUFF_TARGETS and tech_id != 'MOR_BUILDINGS':
                keys.add(f'unit:{tech_id}')
            elif reward.get('access_category') == 'special_building':
                keys.add(f'unit:{tech_id}')
        if (
            reward.get('superweapon')
            and (
                reward.get('kind') == 'superweapon'
                or reward.get('power_buff_type')
            )
        ):
            keys.add(f'power:{reward["superweapon"]}')
        return keys

    def unlock_dashboard_sources(self):
        """Index assigned, earned, and presently playable rewards by icon."""
        cached = self.__dict__.get('_unlock_dashboard_sources_cache')
        if cached is not None:
            return cached
        indexed = {}
        if not self.state:
            return indexed
        share_role_buffs = self.share_chaos_role_buffs_enabled()
        share_foehn_roles = self.foehn_standard_bundles_enabled()
        source_getter = getattr(self, 'archipelago_reward_source_items', None)
        archipelago_sources = source_getter() if source_getter else None
        if archipelago_sources is not None:
            assignment_getter = getattr(
                self, 'archipelago_reward_assignment_source_items', None
            )
            assignments = (
                assignment_getter() if assignment_getter else ()
            ) or ()
            for source, reward, available in assignments:
                reward = canonical_reward(reward)
                if reward.get('retired_reward'):
                    continue
                for key in self.unlock_dashboard_reward_keys(
                    reward,
                    share_role_buffs=share_role_buffs,
                    share_foehn_roles=share_foehn_roles,
                ):
                    entry = indexed.setdefault(
                        key,
                        {
                            'assigned': [],
                            'earned': [],
                            'earned_unlocks': [],
                            'available': [],
                            'available_unlocks': [],
                            'available_codes': [],
                        },
                    )
                    item = (source, reward)
                    entry['assigned'].append(item)
                    if available:
                        entry['available'].append(item)
                        if reward.get('kind') != 'buff':
                            entry['available_unlocks'].append(item)
            for source, reward in archipelago_sources:
                reward = canonical_reward(reward)
                if reward.get('retired_reward'):
                    continue
                for key in self.unlock_dashboard_reward_keys(
                    reward,
                    share_role_buffs=share_role_buffs,
                    share_foehn_roles=share_foehn_roles,
                ):
                    entry = indexed.setdefault(
                        key,
                        {
                            'assigned': [],
                            'earned': [],
                            'earned_unlocks': [],
                            'available': [],
                            'available_unlocks': [],
                            'available_codes': [],
                        },
                    )
                    item = (source, reward)
                    entry['assigned'].append(item)
                    entry['earned'].append(item)
                    if reward.get('kind') != 'buff':
                        entry['earned_unlocks'].append(item)
            self._unlock_dashboard_sources_cache = indexed
            return indexed
        playable = {
            code
            for code in self.unlocked_mission_codes()
            if not self.is_mission_complete(code)
        }
        mission_lookup = self.mission_lookup()
        for code in self.state.get('mission_order', []):
            mission_title = mission_lookup.get(code, {}).get('title', code)
            for check in self.mission_checks(code):
                earned = bool(check.get('unlocked') or check.get('released'))
                source = f'{mission_title} — {check.get("name", "Check")}'
                for reward in check_rewards(check):
                    reward = canonical_reward(reward)
                    if reward.get('retired_reward'):
                        continue
                    for key in self.unlock_dashboard_reward_keys(
                        reward,
                        share_role_buffs=share_role_buffs,
                        share_foehn_roles=share_foehn_roles,
                    ):
                        entry = indexed.setdefault(
                            key,
                            {
                                'assigned': [],
                                'earned': [],
                                'earned_unlocks': [],
                                'available': [],
                                'available_unlocks': [],
                                'available_codes': [],
                            },
                        )
                        item = (source, reward)
                        entry['assigned'].append(item)
                        if earned:
                            entry['earned'].append(item)
                            if reward.get('kind') != 'buff':
                                entry['earned_unlocks'].append(item)
                        elif code in playable:
                            entry['available'].append(item)
                            if reward.get('kind') != 'buff':
                                entry['available_unlocks'].append(item)
                                if code not in entry['available_codes']:
                                    entry['available_codes'].append(code)
        # Starting rewards are active launch/progression rewards, not mission
        # assignments. Index buffs too, so a starting power buff cannot be
        # mislabeled with a later mission source. Buffs still never grant
        # access because they remain absent from earned_unlocks.
        for starting_source, reward in self.starting_reward_source_items():
            reward = canonical_reward(reward)
            if reward.get('retired_reward'):
                continue
            for key in self.unlock_dashboard_reward_keys(
                reward,
                share_role_buffs=share_role_buffs,
                share_foehn_roles=share_foehn_roles,
            ):
                entry = indexed.setdefault(
                    key,
                    {
                        'assigned': [],
                        'earned': [],
                        'earned_unlocks': [],
                        'available': [],
                        'available_unlocks': [],
                        'available_codes': [],
                    },
                )
                item = (starting_source, reward)
                entry['assigned'].append(item)
                entry['earned'].append(item)
                if reward.get('kind') != 'buff':
                    entry['earned_unlocks'].append(item)
        self._unlock_dashboard_sources_cache = indexed
        return indexed

    def starting_reward_source_items(self):
        """Return every starting reward with its exact seed source."""
        if not self.state:
            return []
        manual_candidates = list(self.state.get('manual_starting_rewards', []))
        manual_candidates.extend(
            {'name': name}
            for name in self.state.get('reward_settings', {}).get(
                'starting_unlock_rewards', []
            )
        )
        manual_names = {
            reward.get('name')
            for candidate in manual_candidates
            for reward in (canonical_reward(candidate),)
            if reward.get('name') and not reward.get('retired_reward')
        }
        random_candidates = self.state.get('random_starting_rewards')
        if not isinstance(random_candidates, list):
            random_candidates = [
                candidate
                for candidate in self.state.get('starting_rewards', [])
                if canonical_reward(candidate).get('name') not in manual_names
            ]
        candidates = (
            [('Preselected reward', item) for item in manual_candidates]
            + [('Starting Bonus', item) for item in random_candidates]
        )
        items = []
        seen = set()
        for source, candidate in candidates:
            reward = canonical_reward(candidate)
            name = reward.get('name')
            key = (source, name)
            if (
                not name or key in seen or reward.get('retired_reward')
                or reward.get('kind') == 'retired'
            ):
                continue
            seen.add(key)
            items.append((source, reward))
        return items

    def preselected_unlock_rewards(self):
        """Return active starting unlocks; starting buffs grant no access."""
        return [
            reward for _source, reward in self.starting_reward_source_items()
            if reward.get('kind') != 'buff'
        ]

    def unlock_dashboard_entries(self):
        """Build privacy-aware icon states without changing seed data."""
        sources = self.unlock_dashboard_sources()
        privacy = bool(
            self.state
            and self.active_progression_mode() == 'Grid Mode'
            and self.hide_locked_grid_missions_var.get()
        )
        earned_rewards = list(
            self.canonical_earned_rewards() if self.state else ()
        )
        starting_unlock_source_by_key = {
            key: source
            for source, reward in self.starting_reward_source_items()
            if reward.get('kind') != 'buff'
            for key in self.unlock_dashboard_reward_keys(reward)
        }
        arsenal_mode = self.active_reward_mode() == ARSENAL_MODE
        selected_mission = self.selected_mission() if arsenal_mode else None
        selected_arsenal = (
            self.mission_arsenal(selected_mission.get('code', ''))
            if selected_mission else {}
        )
        selected_arsenal_units = {
            str(entry.get('unit_id') or '').upper()
            for entry in selected_arsenal.get('units', ())
            if entry.get('unit_id')
        }
        selected_arsenal_powers = {
            str(entry.get('power_id') or '').upper()
            for entry in selected_arsenal.get('powers', ())
            if entry.get('power_id')
        }
        arsenal_mission_label = (
            f'{selected_mission.get("title", selected_mission.get("code", ""))} '
            f'({selected_mission.get("code", "")})'
            if selected_mission else ''
        )
        # Buff rules can contain TechLevel for clone construction but do not
        # grant access. Only non-buff rewards may make a card "unlocked".
        earned_access = unlocked_reward_tech_ids(earned_rewards)
        starting_access = self.active_starting_tier_one_access_ids()
        randomize_access = self.randomize_unit_access_enabled()
        foehn_units_available = self.active_reward_mode() in {
            'Chaos', ARSENAL_MODE,
        }

        entries = []
        category_labels = {
            'infantry': 'Infantry',
            'units': 'Vehicles / Naval',
            'aircraft': 'Aircraft',
            'defenses': 'Defenses',
        }
        house_scopes = {}
        for reward in REWARD_POOL:
            scope = self.reward_house_wide_buff_scope(reward)
            if scope:
                house_scopes.setdefault(scope, reward)
        global_production_count = sum(
            1
            for reward in earned_rewards
            if self.reward_house_wide_buff_scope(reward)
            == ('All', 'production')
        )
        for scope, reward in sorted(
            house_scopes.items(),
            key=lambda item: house_wide_buff_label(item[0]).casefold(),
        ):
            suffix, buff_type = scope
            key = f'house:{suffix.lower()}:{buff_type}'
            source_data = sources.get(
                key, {
                    'assigned': [], 'earned': [], 'earned_unlocks': [], 'available': [],
                    'available_unlocks': [], 'available_codes': [],
                }
            )
            status = (
                'unlocked'
                if source_data['earned']
                else 'available'
                if source_data['available'] and not privacy
                else 'locked'
                if source_data['assigned']
                else 'unavailable'
            )
            entries.append({
                'key': key,
                'kind': 'house',
                'id': f'{suffix}:{buff_type}',
                'label': house_wide_buff_label(scope),
                'faction': 'Neutral',
                'category': (
                    'Global Buffs'
                    if suffix == 'All'
                    else 'House-Wide Buffs'
                ),
                'status': status,
                'condition': '',
                'sources': source_data,
                'privacy': privacy,
                'reward': reward,
                'house_scope': scope,
                'global_production_count': (
                    global_production_count
                    if scope[1] == 'production' and scope[0] != 'All'
                    else 0
                ),
            })

        starting_credit_reward = next(
            (
                reward for reward in REWARD_POOL
                if reward.get('buff_type') == 'starting_credits'
            ),
            None,
        )
        if starting_credit_reward:
            key = 'global:starting_credits'
            source_data = sources.get(
                key, {
                    'assigned': [], 'earned': [], 'earned_unlocks': [],
                    'available': [], 'available_unlocks': [],
                    'available_codes': [],
                }
            )
            status = (
                'unlocked'
                if source_data['earned']
                else 'available'
                if source_data['available'] and not privacy
                else 'locked'
                if source_data['assigned']
                else 'unavailable'
            )
            entries.append({
                'key': key,
                'kind': 'global',
                'id': 'starting_credits',
                'label': 'Starting Credits',
                'faction': 'Neutral',
                'category': 'Global Buffs',
                'status': status,
                'condition': '',
                'sources': source_data,
                'privacy': privacy,
                'reward': starting_credit_reward,
            })

        for unit_id, target in BUFF_TARGETS.items():
            if target.get('linked_buff_source'):
                continue
            category = target.get('category')
            if category not in category_labels:
                continue
            factions = list(target.get('factions') or [])
            if (
                len(factions) != 1
                or factions[0] not in (*FACTION_ORDER, 'Neutral')
            ):
                continue
            key = f'unit:{unit_id}'
            source_data = sources.get(
                key, {
                    'assigned': [], 'earned': [], 'earned_unlocks': [], 'available': [],
                    'available_unlocks': [], 'available_codes': [],
                }
            )
            special_reward = bool(target.get('special_reward'))
            if (
                factions[0] == 'Foehn'
                and not foehn_units_available
                and not special_reward
            ):
                source_data = {
                    'assigned': [], 'earned': [], 'earned_unlocks': [], 'available': [],
                    'available_unlocks': [], 'available_codes': [],
                }
            arsenal_selected = arsenal_mode and unit_id in selected_arsenal_units
            unlocked = (
                arsenal_selected
                if arsenal_mode
                else bool(
                    (factions[0] != 'Foehn' or foehn_units_available or special_reward)
                    and (
                        not randomize_access
                        or unit_id in ALWAYS_AVAILABLE_TECH_IDS
                        or unit_id in starting_access
                        or unit_id in earned_access
                        or any(
                            reward.get('kind') != 'buff'
                            for _source, reward in source_data['earned']
                        )
                    )
                )
            )
            status = (
                ('unlocked' if arsenal_selected else 'unavailable')
                if arsenal_mode
                else (
                    'unlocked'
                    if unlocked
                    else 'available'
                    if source_data['available_unlocks'] and not privacy
                    else 'locked'
                    if source_data['assigned']
                    else 'unavailable'
                )
            )
            if arsenal_selected:
                condition = 'Seed-fixed temporary mission arsenal'
            elif key in starting_unlock_source_by_key:
                condition = starting_unlock_source_by_key[key]
            elif unit_id in starting_access:
                condition = 'Pre-generation settings'
            elif unit_id in ALWAYS_AVAILABLE_TECH_IDS or not randomize_access:
                condition = 'Pre-generation settings'
            else:
                condition = ''
            entries.append({
                'key': key,
                'kind': 'unit',
                'id': unit_id,
                'label': target.get('label', unit_id),
                'faction': factions[0],
                'category': (
                    'Special' if special_reward else category_labels[category]
                ),
                'status': status,
                'condition': condition,
                'sources': source_data,
                'privacy': privacy,
                'arsenal_mode': arsenal_mode,
                'arsenal_selected': arsenal_selected,
                'arsenal_mission_label': arsenal_mission_label,
            })

        special_rewards = {
            next(iter(tech_ids_for_rewards([reward])), ''): reward
            for reward in REWARD_POOL
            if reward.get('access_category') == 'special_building'
        }
        for definition in SPECIAL_BUILDING_DEFINITIONS:
            building_id = str(definition['id']).upper()
            faction = str(definition['faction'])
            reward = special_rewards.get(building_id)
            if not reward or faction not in FACTION_ORDER:
                continue
            key = f'unit:{building_id}'
            source_data = sources.get(
                key, {
                    'assigned': [], 'earned': [], 'earned_unlocks': [], 'available': [],
                    'available_unlocks': [], 'available_codes': [],
                }
            )
            status = (
                'unlocked'
                if building_id in earned_access or source_data['earned_unlocks']
                else 'available'
                if source_data['available_unlocks'] and not privacy
                else 'locked'
                if source_data['assigned']
                else 'unavailable'
            )
            entries.append({
                'key': key,
                'kind': 'unit',
                'id': building_id,
                'label': str(definition['name']),
                'faction': faction,
                'category': (
                    'Special'
                    if definition.get('special_reward')
                    else 'Special Buildings'
                ),
                'status': status,
                'condition': (
                    starting_unlock_source_by_key.get(key, '')
                ),
                'sources': source_data,
                'privacy': privacy,
                'reward': reward,
            })

        seen_powers = set()
        for reward in REWARD_POOL:
            if reward.get('kind') != 'superweapon' or not reward.get('superweapon'):
                continue
            reward = canonical_reward(reward)
            power_id = reward['superweapon']
            if power_id in seen_powers:
                continue
            factions = list(reward.get('factions') or [])
            if (
                len(factions) != 1
                or factions[0] not in (*FACTION_ORDER, 'Neutral')
            ):
                continue
            seen_powers.add(power_id)
            key = f'power:{power_id}'
            source_data = sources.get(
                key, {
                    'assigned': [], 'earned': [], 'earned_unlocks': [], 'available': [],
                    'available_unlocks': [], 'available_codes': [],
                }
            )
            arsenal_selected = (
                arsenal_mode and str(power_id).upper() in selected_arsenal_powers
            )
            status = (
                ('unlocked' if arsenal_selected else 'unavailable')
                if arsenal_mode
                else (
                    'unlocked'
                    if source_data['earned_unlocks']
                    else 'available'
                    if source_data['available_unlocks'] and not privacy
                    else 'locked'
                    if source_data['assigned']
                    else 'unavailable'
                )
            )
            entries.append({
                'key': key,
                'kind': 'power',
                'id': power_id,
                'label': reward_display_name(reward),
                'faction': factions[0],
                'category': (
                    'Special' if reward.get('special_reward') else 'Superweapons'
                ),
                'status': status,
                'condition': (
                    'Seed-fixed temporary mission arsenal'
                    if arsenal_selected
                    else starting_unlock_source_by_key.get(key, '')
                ),
                'sources': source_data,
                'privacy': privacy,
                'reward': reward,
                'arsenal_mode': arsenal_mode,
                'arsenal_selected': arsenal_selected,
                'arsenal_mission_label': arsenal_mission_label,
            })
        # One final shared pass covers units, defenses/buildings, support
        # powers, and superweapons without category-specific drift.
        for entry in entries:
            if entry['key'] in starting_unlock_source_by_key:
                entry['condition'] = starting_unlock_source_by_key[entry['key']]
        return entries

    def unlock_dashboard_tooltip(self, entry):
        archipelago_active = bool(
            getattr(self, 'archipelago_run_active', lambda: False)()
        )
        status_labels = {
            'unlocked': 'Unlocked',
            'available': 'Available now',
            'locked': 'Locked',
            'unavailable': (
                'Not yet received'
                if archipelago_active
                else 'Unavailable in this seed'
            ),
        }
        arsenal_entry = bool(
            entry.get('arsenal_mode')
            and entry.get('kind') in {'unit', 'power'}
        )
        status_label = (
            'Active in selected mission'
            if arsenal_entry and entry.get('arsenal_selected')
            else 'Not in selected mission arsenal'
            if arsenal_entry
            else status_labels[entry['status']]
        )
        lines = [
            f'{entry["label"]} - {status_label}',
            '─' * min(48, max(12, len(entry['label']) + 12)),
        ]
        sources = entry['sources']
        earned_source_names = list(dict.fromkeys(source for source, _ in sources['earned']))
        available_source_items = (
            sources['available']
            if entry.get('kind') in {'house', 'global'}
            else sources['available_unlocks']
        )
        available_source_names = list(dict.fromkeys(
            source for source, _ in available_source_items
        ))

        def compact_sources(names):
            visible = names[:3]
            text = '; '.join(visible)
            if len(names) > len(visible):
                text += f'; +{len(names) - len(visible)} more'
            return text

        starting_source_labels = {'Starting Bonus', 'Preselected reward'}
        if (
            entry.get('condition')
            and entry.get('condition') not in starting_source_labels
        ):
            lines.append(f'Condition: {entry["condition"]}')
        if arsenal_entry and entry.get('arsenal_mission_label'):
            lines.append(f'Mission: {entry["arsenal_mission_label"]}')
        starting_source_names = [
            source for source in earned_source_names
            if source in starting_source_labels
        ]
        mission_source_names = [
            source for source in earned_source_names
            if source not in starting_source_labels
        ]
        if starting_source_names:
            lines.append(
                'Reward source: ' + compact_sources(starting_source_names)
            )
        if (
            mission_source_names
            and (not arsenal_entry or entry.get('arsenal_selected'))
        ):
            lines.append('Earned from: ' + compact_sources(mission_source_names))
        availability_lines = []
        if entry['status'] == 'available' and available_source_names:
            lines.append('Available from: ' + compact_sources(available_source_names))
        elif entry['status'] == 'locked':
            availability_lines.append(
                'Assigned later in this seed.'
                if not entry['privacy']
                else 'Access not currently available.'
            )
        elif entry['status'] == 'unavailable':
            availability_lines.append(
                'Not part of this mission\'s seed-fixed temporary arsenal.'
                if arsenal_entry
                else 'May be received later from this Archipelago multiworld.'
                if archipelago_active
                else 'Not assigned by this seed and current reward settings.'
            )

        earned = [reward for _, reward in sources['earned']]
        effect_lines = []
        if entry.get('kind') == 'house':
            buff_count = sum(
                1 for reward in earned if reward.get('kind') == 'buff'
            )
            if buff_count:
                buff_count += int(entry.get('global_production_count', 0))
                effect_lines.extend(house_wide_buff_effect_lines(
                    entry['house_scope'],
                    count=effective_buff_count(entry['reward'], buff_count),
                    stack_limit=buff_stack_limit(entry['reward']),
                ))
        else:
            buffs = {}
            active_effect_rewards = earned
            if (
                (arsenal_entry and not entry.get('arsenal_selected'))
                or (
                    not arsenal_entry
                    and entry.get('kind') == 'power'
                    and entry['status'] != 'unlocked'
                )
            ):
                active_effect_rewards = ()
            for reward in active_effect_rewards:
                if reward.get('kind') == 'buff':
                    key = (
                        reward.get('buff_type')
                        or reward.get('power_buff_type')
                    )
                    display_reward = dict(reward)
                    if entry.get('kind') == 'unit':
                        display_reward['unit'] = entry['id']
                    buffs.setdefault(
                        key, {'reward': display_reward, 'count': 0}
                    )['count'] += 1
            for buff in buffs.values():
                effect_lines.extend(buff_effect_lines(
                    buff['reward'],
                    count=buff['count'],
                    include_label=False,
                ))
        if (
            entry.get('reward')
            and entry['status'] == 'unlocked'
            and entry.get('kind') != 'global'
            and entry['reward'].get('access_category') != 'special_building'
        ):
            effect_lines.extend(reward_rule_summary(entry['reward']))
        if effect_lines:
            lines.append('Current effects:')
            lines.extend(f'• {line}' for line in effect_lines)

        inactive_arsenal_buffs = [
            reward
            for reward in earned
            if arsenal_entry
            and not entry.get('arsenal_selected')
            and reward.get('kind') == 'buff'
        ]
        if inactive_arsenal_buffs:
            deferred = {}
            for reward in inactive_arsenal_buffs:
                key = reward.get('buff_type') or reward.get('power_buff_type')
                deferred.setdefault(
                    key, {'reward': reward, 'count': 0}
                )['count'] += 1
            lines.append('Earned buffs inactive in this mission:')
            for buff in deferred.values():
                for summary in buff_effect_lines(
                    buff['reward'],
                    count=buff['count'],
                    include_label=False,
                ):
                    lines.append(f'  {summary}')

        deferred_power_buffs = [
            reward
            for reward in earned
            if not arsenal_entry
            and entry.get('kind') == 'power'
            and entry['status'] != 'unlocked'
            and reward.get('kind') == 'buff'
        ]
        if deferred_power_buffs:
            deferred = {}
            for reward in deferred_power_buffs:
                key = reward.get('power_buff_type')
                deferred.setdefault(
                    key, {'reward': reward, 'count': 0}
                )['count'] += 1
            lines.append('Stored buffs (apply after unlock):')
            for buff in deferred.values():
                for summary in buff_effect_lines(
                    buff['reward'],
                    count=buff['count'],
                    include_label=False,
                ):
                    lines.append(f'  {summary}')

        if entry['status'] == 'available':
            potential = []
            for _source, reward in available_source_items:
                if reward.get('kind') == 'buff':
                    if entry.get('kind') == 'house':
                        potential.extend(house_wide_buff_effect_lines(
                            entry['house_scope'],
                            include_stack=False,
                        ))
                    else:
                        potential.extend(buff_effect_lines(
                            reward,
                            include_label=False,
                            include_stack=False,
                        ))
                else:
                    potential.append(reward_display_name(reward))
            if potential:
                lines.append('Potential reward:')
                lines.extend(f'• {line}' for line in dict.fromkeys(potential))
        lines.extend(availability_lines)
        return '\n'.join(lines)

    def schedule_cameo_refresh_retry(self):
        """Redraw image consumers after asynchronous MIX extraction finishes."""
        if self.cameo_retry_after_id is not None or self.cameo_retry_count >= 20:
            return
        self.cameo_retry_count += 1

        def retry():
            self.cameo_retry_after_id = None
            if not self.winfo_exists():
                return
            self.advanced_unit_cameo_paths = None
            self.unlock_dashboard_signature = None
            self.unlock_dashboard_structure_signatures = {}
            self.refresh_advanced_pool_views()
            self.refresh_progress_view()

        self.cameo_retry_after_id = self.after(1000, retry)
