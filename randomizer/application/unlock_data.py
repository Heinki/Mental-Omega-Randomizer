"""Unlock display models, labels, sources, and tooltips."""

from ._dependencies import (
    ALWAYS_AVAILABLE_TECH_IDS,
    BUFF_TARGETS,
    FACTION_ORDER,
    REWARD_POOL,
    SPECIAL_BUILDING_DEFINITIONS,
    buff_effect_lines,
    canonical_reward,
    check_rewards,
    effective_buff_count,
    mission_assistance_multipliers,
    reward_cameo_token,
    reward_display_name,
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

    def mission_assistance_effect_text(self, stacks):
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

        return groups, shared_groups

    def current_unlocks_text(self):
        if not self.state:
            return 'No randomizer seed generated yet.'

        lines = []
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
        for reward in self.earned_rewards_from_checks():
            canonical = canonical_reward(reward)
            if (
                not canonical.get('retired_reward')
                and not self.standard_foehn_unit_reward(canonical)
            ):
                earned.append(canonical)
        if not earned:
            if lines:
                return '\n'.join(lines).rstrip()
            return 'No unlocks or buffs earned yet.'

        share_foehn_roles = self.foehn_standard_bundles_enabled()
        groups, shared_groups = self.build_unlock_display_groups(earned)

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

    def current_unlock_unit_ids(self):
        if not self.state:
            return []
        unit_ids = set(self.display_starting_tier_one_unit_ids())
        unit_ids.update(self.display_starting_tier_one_defense_ids())
        share_chaos_role_buffs = self.share_chaos_role_buffs_enabled()
        share_foehn_roles = self.foehn_standard_bundles_enabled()
        for reward in self.earned_rewards_from_checks():
            reward = canonical_reward(reward)
            if self.standard_foehn_unit_reward(reward):
                continue
            if reward.get('kind') == 'buff' and reward.get('unit'):
                if reward['unit'] != 'MOR_BUILDINGS':
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
        if self.active_reward_mode() != 'Chaos (Experimental)':
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

    def unlock_dashboard_reward_keys(self, reward):
        """Return catalogue icons affected by one serialized reward."""
        reward = canonical_reward(reward)
        keys = set()
        unit_id = str(reward.get('unit') or '').upper()
        if reward.get('kind') == 'buff' and unit_id and unit_id != 'MOR_BUILDINGS':
            keys.add(f'unit:{unit_id}')
            if (
                not reward.get('global_buff')
                and (self.share_chaos_role_buffs_enabled() or self.foehn_standard_bundles_enabled())
            ):
                equivalents = unit_role_equivalents(unit_id)
                if self.foehn_standard_bundles_enabled():
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
        indexed = {}
        if not self.state:
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
                    for key in self.unlock_dashboard_reward_keys(reward):
                        entry = indexed.setdefault(
                            key,
                            {
                                'assigned': [],
                                'earned': [],
                                'available': [],
                                'available_unlocks': [],
                                'available_codes': [],
                            },
                        )
                        item = (source, reward)
                        entry['assigned'].append(item)
                        if earned:
                            entry['earned'].append(item)
                        elif code in playable:
                            entry['available'].append(item)
                            if reward.get('kind') != 'buff':
                                entry['available_unlocks'].append(item)
                                if code not in entry['available_codes']:
                                    entry['available_codes'].append(code)
        return indexed

    def unlock_dashboard_entries(self):
        """Build privacy-aware icon states without changing seed data."""
        sources = self.unlock_dashboard_sources()
        privacy = bool(
            self.state
            and self.active_progression_mode() == 'Grid Mode'
            and self.hide_locked_grid_missions_var.get()
        )
        earned_rewards = [
            canonical_reward(reward)
            for reward in (self.earned_rewards_from_checks() if self.state else [])
        ]
        # Buff rules can contain TechLevel for clone construction but do not
        # grant access. Only non-buff rewards may make a card "unlocked".
        earned_access = unlocked_reward_tech_ids(earned_rewards)
        starting_access = self.active_starting_tier_one_access_ids()
        randomize_access = self.randomize_unit_access_enabled()
        foehn_units_available = self.active_reward_mode() == 'Chaos (Experimental)'

        entries = []
        category_labels = {
            'infantry': 'Infantry',
            'units': 'Vehicles / Naval',
            'aircraft': 'Aircraft',
            'defenses': 'Defenses',
        }
        for unit_id, target in BUFF_TARGETS.items():
            if target.get('linked_buff_source'):
                continue
            category = target.get('category')
            if category not in category_labels:
                continue
            factions = list(target.get('factions') or [])
            if len(factions) != 1 or factions[0] not in FACTION_ORDER:
                continue
            key = f'unit:{unit_id}'
            source_data = sources.get(
                key, {
                    'assigned': [], 'earned': [], 'available': [],
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
                    'assigned': [], 'earned': [], 'available': [],
                    'available_unlocks': [], 'available_codes': [],
                }
            unlocked = bool(
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
            status = (
                'unlocked'
                if unlocked
                else 'available'
                if source_data['available_unlocks'] and not privacy
                else 'locked'
                if source_data['assigned']
                else 'unavailable'
            )
            if unit_id in starting_access:
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
                    'assigned': [], 'earned': [], 'available': [],
                    'available_unlocks': [], 'available_codes': [],
                }
            )
            status = (
                'unlocked'
                if building_id in earned_access
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
                'condition': '',
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
            if len(factions) != 1 or factions[0] not in FACTION_ORDER:
                continue
            seen_powers.add(power_id)
            key = f'power:{power_id}'
            source_data = sources.get(
                key, {
                    'assigned': [], 'earned': [], 'available': [],
                    'available_unlocks': [], 'available_codes': [],
                }
            )
            status = (
                'unlocked'
                if source_data['earned']
                else 'available'
                if source_data['available_unlocks'] and not privacy
                else 'locked'
                if source_data['assigned']
                else 'unavailable'
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
                'condition': '',
                'sources': source_data,
                'privacy': privacy,
                'reward': reward,
            })
        return entries

    def unlock_dashboard_tooltip(self, entry):
        status_labels = {
            'unlocked': 'Unlocked',
            'available': 'Available now',
            'locked': 'Locked',
            'unavailable': 'Unavailable in this seed',
        }
        lines = [
            f'{entry["label"]} — {status_labels[entry["status"]]}',
            '─' * min(48, max(12, len(entry['label']) + 12)),
        ]
        sources = entry['sources']
        earned_source_names = list(dict.fromkeys(source for source, _ in sources['earned']))
        available_source_names = list(dict.fromkeys(
            source for source, _ in sources['available_unlocks']
        ))

        def compact_sources(names):
            visible = names[:3]
            text = '; '.join(visible)
            if len(names) > len(visible):
                text += f'; +{len(names) - len(visible)} more'
            return text

        if entry.get('condition'):
            lines.append(f'Condition: {entry["condition"]}')
        if earned_source_names:
            lines.append('Earned from: ' + compact_sources(earned_source_names))
        if entry['status'] == 'available' and available_source_names:
            lines.append('Available from: ' + compact_sources(available_source_names))
        elif entry['status'] == 'locked':
            lines.append(
                'Assigned later in this seed.'
                if not entry['privacy']
                else 'Access not currently available.'
            )
        elif entry['status'] == 'unavailable':
            lines.append('Not assigned by this seed and current reward settings.')

        earned = [reward for _, reward in sources['earned']]
        buffs = {}
        for reward in earned:
            if reward.get('kind') == 'buff':
                key = reward.get('buff_type') or reward.get('power_buff_type')
                display_reward = dict(reward)
                if entry.get('kind') == 'unit':
                    display_reward['unit'] = entry['id']
                buffs.setdefault(
                    key, {'reward': display_reward, 'count': 0}
                )['count'] += 1
        effect_lines = []
        for buff in buffs.values():
            effect_lines.extend(buff_effect_lines(
                buff['reward'], count=buff['count'], include_label=False
            ))
        if (
            entry.get('reward')
            and entry['status'] == 'unlocked'
            and entry['reward'].get('access_category') != 'special_building'
        ):
            effect_lines.extend(reward_rule_summary(entry['reward']))
        if effect_lines:
            lines.extend(['', 'Current effects:'])
            lines.extend(f'• {line}' for line in effect_lines)

        if entry['status'] == 'available':
            potential = []
            for _source, reward in sources['available_unlocks']:
                if reward.get('kind') == 'buff':
                    potential.extend(buff_effect_lines(
                        reward, include_label=False, include_stack=False
                    ))
                else:
                    potential.append(reward_display_name(reward))
            if potential:
                lines.extend(['', 'Potential reward:'])
                lines.extend(f'• {line}' for line in dict.fromkeys(potential))
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
            self.unlock_dashboard_structure_signature = None
            self.refresh_advanced_pool_views()
            self.refresh_progress_view()

        self.cameo_retry_after_id = self.after(1000, retry)
