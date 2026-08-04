"""AI-reward progress, applied-target state, and dashboard."""

from ._dependencies import (
    ENEMY_BUFF_BY_ID,
    ENEMY_BUFF_DEFINITIONS,
    ENEMY_BUFF_GROUP_DEFINITIONS,
    WidgetTooltip,
    canonical_reward,
    check_rewards,
    enemy_effect_text,
    normalize_enemy_scaling_settings,
    tk,
)


class EnemyScalingController:

    def enemy_buff_group_help_text(self, group):
        """List every concrete bonus behind one compact settings group."""
        definitions = [
            ENEMY_BUFF_BY_ID[effect_id]
            for effect_id in group.get('effect_ids', ())
            if effect_id in ENEMY_BUFF_BY_ID
        ]
        lines = [
            'Possible hostile-AI-only bonuses in this group:',
        ]
        for definition in definitions:
            effect_id = definition['id']
            cap_var = getattr(self, 'enemy_buff_cap_vars', {}).get(effect_id)
            cap = (
                cap_var.get()
                if cap_var is not None
                else definition.get('maximum_stacks', 1)
            )
            lines.append(
                f'- {definition["name"]}: '
                f'{enemy_effect_text(definition, 1)} per stack; cap {cap}'
            )
        lines.extend((
            '',
            'Bonuses apply only to verified hostile AI Houses. They never '
            'change player, allied, neutral, or civilian Houses.',
        ))
        return '\n'.join(lines)

    def refresh_enemy_reward_setting_help(self):
        """Explain stack counts and shared capacity using current controls."""
        if not hasattr(self, 'enemy_reward_capacity_label'):
            return
        enabled_ids = [
            definition['id']
            for definition in ENEMY_BUFF_DEFINITIONS
            if self.enemy_buff_enabled_vars[definition['id']].get()
            and int(self.enemy_buff_cap_vars[definition['id']].get()) > 0
        ]
        capacity = sum(
            max(0, int(self.enemy_buff_cap_vars[effect_id].get()))
            for effect_id in enabled_ids
        )
        self.enemy_reward_capacity_label.configure(text=(
            'Values are bonus stacks, not unique bonus types. Objective, '
            'mission, and normal-pool AI rewards share '
            f'{capacity} total configured stacks across '
            f'{len(enabled_ids)} enabled bonuses. Once every cap is filled, '
            'later completion rolls cannot grant another AI bonus.'
        ))
        for group in ENEMY_BUFF_GROUP_DEFINITIONS:
            tooltip = getattr(
                self, 'enemy_buff_group_tooltips', {}
            ).get(group['id'])
            if tooltip is not None:
                tooltip.text = self.enemy_buff_group_help_text(group)
        self._enemy_buffs_view_dirty = True
        if self.enemy_buffs_view_visible():
            self.after_idle(self.refresh_enemy_buffs_view)

    def on_enemy_buff_group_changed(self, group_id):
        group = next(
            (
                definition
                for definition in ENEMY_BUFF_GROUP_DEFINITIONS
                if definition['id'] == group_id
            ),
            None,
        )
        if not group:
            return
        enabled = bool(self.enemy_buff_group_vars[group_id].get())
        for effect_id in group['effect_ids']:
            self.enemy_buff_enabled_vars[effect_id].set(enabled)
        self.refresh_setting_states()

    def sync_enemy_buff_group_vars(self):
        for group in ENEMY_BUFF_GROUP_DEFINITIONS:
            self.enemy_buff_group_vars[group['id']].set(any(
                self.enemy_buff_enabled_vars[effect_id].get()
                for effect_id in group['effect_ids']
            ))

    def enemy_buffs_view_visible(self):
        return bool(
            hasattr(self, 'info_tabs')
            and hasattr(self, 'enemy_buffs_tab')
            and self.info_tabs.select() == str(self.enemy_buffs_tab)
        )

    def _completed_ai_reward_counts(self):
        objectives = sum(
            1
            for code in self.state.get('mission_order', [])
            for check in self.state.get('mission_checks', {}).get(code, [])
            if check.get('id') != 'victory' and check.get('unlocked')
        )
        return {
            'objectives': objectives,
            'missions': len(self.state.get('completed_missions', [])),
        }

    def _ai_reward_fallback_source(self, event_index, basis):
        mission_lookup = self.mission_lookup() if self.missions else {}
        if basis == 'missions':
            completed = self.state.get('completed_missions', [])
            if completed:
                code = completed[min(event_index, len(completed)) - 1]
                title = mission_lookup.get(code, {}).get('title', code)
                return f'{title} - Mission Victory'
            return 'Saved mission progress'
        completed_checks = []
        for code in self.state.get('mission_order', []):
            title = mission_lookup.get(code, {}).get('title', code)
            for check in self.state.get('mission_checks', {}).get(code, []):
                if check.get('id') == 'victory' or not check.get('unlocked'):
                    continue
                completed_checks.append(
                    f'{title} - {check.get("name", "Objective")}'
                )
        if completed_checks:
            return completed_checks[min(event_index, len(completed_checks)) - 1]
        return 'Saved objective progress'

    def sync_enemy_progress_milestones(self, code='', check=None):
        """Activate every planned reward belonging to completed events."""
        if not self.state:
            return False
        completed = self._completed_ai_reward_counts()
        earned = self.state.setdefault('enemy_progress_earned', [])
        existing = {
            (str(item.get('basis') or ''), int(item.get('event_index', 0)))
            for item in earned
            if isinstance(item, dict)
        }
        planned_events = []
        seen = set()
        for entry in self.state.get('enemy_progress_plan', []):
            if not isinstance(entry, dict):
                continue
            key = (
                str(entry.get('basis') or ''),
                int(entry.get('event_index', 0)),
            )
            if (
                key in seen
                or key[0] not in completed
                or key[1] <= 0
            ):
                continue
            seen.add(key)
            planned_events.append(key)

        mission = self.mission_lookup().get(code, {}) if code else {}
        title = mission.get('title', code)
        current_source = (
            f'{title} - {check.get("name", "Check")}'
            if code and isinstance(check, dict)
            else ''
        )
        missing_objectives = [
            key for key in planned_events
            if key[0] == 'objectives'
            and key not in existing
            and key[1] <= completed['objectives']
        ]
        victory_objective_sources = []
        if (
            code
            and isinstance(check, dict)
            and check.get('id') == 'victory'
            and missing_objectives
        ):
            all_sources = [
                f'{title} - {item.get("name", "Objective")}'
                for item in self.state.get('mission_checks', {}).get(code, [])
                if item.get('id') != 'victory' and item.get('unlocked')
            ]
            victory_objective_sources = all_sources[-len(missing_objectives):]

        changed = False
        objective_source_index = 0
        for basis, event_index in planned_events:
            key = (basis, event_index)
            if key in existing or event_index > completed[basis]:
                continue
            if basis == 'missions' and current_source:
                source = current_source
            elif (
                basis == 'objectives'
                and current_source
                and check.get('id') != 'victory'
            ):
                source = current_source
            elif basis == 'objectives' and victory_objective_sources:
                source = victory_objective_sources[
                    min(
                        objective_source_index,
                        len(victory_objective_sources) - 1,
                    )
                ]
                objective_source_index += 1
            else:
                source = self._ai_reward_fallback_source(event_index, basis)
            earned.append({
                'basis': basis,
                'event_index': event_index,
                'earned_from': source,
            })
            existing.add(key)
            changed = True
        if changed:
            self._enemy_buffs_view_dirty = True
        return changed

    def active_enemy_scaling_entries(self):
        """Return active completion and normal AI rewards with sources."""
        if not self.state:
            return []
        entries = []
        milestones = {
            (
                str(item.get('basis') or ''),
                int(item.get('event_index', 0)),
            ): item
            for item in self.state.get('enemy_progress_earned', [])
            if isinstance(item, dict)
        }
        for planned in self.state.get('enemy_progress_plan', []):
            if not isinstance(planned, dict):
                continue
            key = (
                str(planned.get('basis') or ''),
                int(planned.get('event_index', 0)),
            )
            milestone = milestones.get(key)
            reward = canonical_reward(planned.get('reward', {}))
            if not milestone or not reward.get('enemy_reward'):
                continue
            entries.append({
                'reward': reward,
                'source': (
                    'Objective completion'
                    if key[0] == 'objectives'
                    else 'Mission completion'
                ),
                'earned_from': milestone.get(
                    'earned_from', 'Saved AI reward progress'
                ),
            })
        mission_lookup = self.mission_lookup()
        for code in self.state.get('mission_order', []):
            title = mission_lookup.get(code, {}).get('title', code)
            for check in self.state.get('mission_checks', {}).get(code, []):
                if not (check.get('unlocked') or check.get('released')):
                    continue
                source = f'{title} - {check.get("name", "Check")}'
                for reward in check_rewards(check):
                    reward = canonical_reward(reward)
                    if reward.get('enemy_reward'):
                        entries.append({
                            'reward': reward,
                            'source': 'Normal reward',
                            'earned_from': source,
                        })
        return entries

    def active_enemy_scaling_rewards(self):
        return [entry['reward'] for entry in self.active_enemy_scaling_entries()]

    def record_enemy_reward_applications(self, code, applications):
        """Persist exact receipts only after generated map mutations succeed."""
        if not self.state or not code:
            return
        normalized = []
        for item in applications or ():
            if not isinstance(item, dict):
                continue
            effect_id = str(item.get('effect_id') or '')
            house = str(item.get('house') or '').strip()
            target = str(item.get('target') or '').strip()
            effect = str(item.get('effect') or '').strip()
            if (
                effect_id not in ENEMY_BUFF_BY_ID
                or not (house and target and effect)
            ):
                continue
            try:
                stack = max(1, int(item.get('stack', 1)))
                cap = max(stack, int(item.get('cap', stack)))
            except (TypeError, ValueError):
                continue
            normalized.append({
                'mission': str(item.get('mission') or code),
                'reward_name': str(
                    item.get('reward_name') or effect_id
                ).strip(),
                'effect_id': effect_id,
                'source': str(item.get('source') or 'AI reward').strip(),
                'earned_from': str(
                    item.get('earned_from') or 'Saved AI reward progress'
                ).strip(),
                'house': house,
                'country': str(item.get('country') or '').strip(),
                'target': target,
                'effect': effect,
                'stack': stack,
                'cap': cap,
            })
        normalized.sort(key=lambda item: (
            item['effect_id'], item['house'].casefold(), item['target'].casefold(),
            item['stack'], item['source'], item['earned_from'],
        ))
        records = self.state.setdefault('enemy_reward_applications', {})
        if records.get(code) == normalized:
            return
        records[code] = normalized
        self._enemy_buffs_view_dirty = True
        self.save_state()

    def enemy_scaling_dashboard_rows(self):
        grouped = {}
        for mission, applications in self.state.get(
            'enemy_reward_applications', {}
        ).items():
            for item in applications or ():
                if not isinstance(item, dict):
                    continue
                effect_id = str(item.get('effect_id') or '')
                house = str(item.get('house') or '').strip()
                target = str(item.get('target') or '').strip()
                effect = str(item.get('effect') or '').strip()
                if (
                    effect_id not in ENEMY_BUFF_BY_ID
                    or not (house and target and effect)
                ):
                    continue
                key = (str(mission), effect_id, house, target)
                group = grouped.setdefault(key, {
                    'mission': str(mission),
                    'effect_id': effect_id,
                    'name': str(item.get('reward_name') or effect_id),
                    'house': house,
                    'target': target,
                    'country': str(item.get('country') or ''),
                    'effect': effect,
                    'stack': 0,
                    'cap': 1,
                    'reward': dict(ENEMY_BUFF_BY_ID.get(effect_id, {})),
                    'sources': set(),
                    'earned_from': [],
                })
                try:
                    item_stack = max(1, int(item.get('stack', 1)))
                    item_cap = max(item_stack, int(item.get('cap', item_stack)))
                except (TypeError, ValueError):
                    continue
                if item_stack >= group['stack']:
                    group['effect'] = effect
                group['stack'] = max(group['stack'], item_stack)
                group['cap'] = max(group['cap'], item_cap)
                source = str(item.get('source') or 'AI reward')
                earned_from = str(
                    item.get('earned_from') or 'Saved AI reward progress'
                )
                group['sources'].add(source)
                if earned_from not in group['earned_from']:
                    group['earned_from'].append(earned_from)
        rows = []
        for key, group in grouped.items():
            rows.append({
                'id': '|'.join(key),
                'name': group['name'],
                'house': group['house'],
                'target': group['target'],
                'effect': group['effect'],
                'stacks': f'{group["stack"]}/{group["cap"]}',
                'source': ' + '.join(sorted(group['sources'])),
                'earned_from': (
                    f'{group["mission"]}: '
                    + '; '.join(group['earned_from'])
                ),
                'reward': group['reward'],
            })
        return sorted(rows, key=lambda row: (
            row['earned_from'].casefold(), row['name'].casefold(),
            row['house'].casefold(),
        ))

    def enemy_buff_catalogue_entries(self):
        """Show all supported bonuses; application receipts remain separate."""
        if self.state and isinstance(
            self.state.get('reward_settings'), dict
        ):
            settings = normalize_enemy_scaling_settings(
                self.state['reward_settings'].get('enemy_scaling')
            )
        else:
            settings = normalize_enemy_scaling_settings({
                'reward_enabled': bool(self.enemy_reward_pool_var.get()),
                'rewards_per_completed_objective': int(
                    self.enemy_objective_rewards_var.get()
                ),
                'rewards_per_completed_mission': int(
                    self.enemy_mission_rewards_var.get()
                ),
                'allowed_buff_ids': [
                    effect_id
                    for effect_id, variable
                    in self.enemy_buff_enabled_vars.items()
                    if variable.get()
                ],
                'caps': {
                    effect_id: variable.get()
                    for effect_id, variable
                    in self.enemy_buff_cap_vars.items()
                },
            })
        allowed = set(settings['allowed_buff_ids'])
        active_counts = {}
        active_sources = {}
        for entry in self.active_enemy_scaling_entries():
            effect_id = str(
                entry['reward'].get('enemy_effect_id') or ''
            )
            if not effect_id:
                continue
            active_counts[effect_id] = active_counts.get(effect_id, 0) + 1
            active_sources.setdefault(effect_id, set()).add(entry['source'])

        planned_counts = {}
        if self.state:
            planned_rewards = [
                item.get('reward', {})
                for item in self.state.get('enemy_progress_plan', ())
                if isinstance(item, dict)
            ]
            planned_rewards.extend(
                reward
                for checks in self.state.get('mission_checks', {}).values()
                for check in checks
                for reward in check_rewards(check)
                if reward.get('enemy_reward')
            )
            for reward in planned_rewards:
                effect_id = str(reward.get('enemy_effect_id') or '')
                if effect_id:
                    planned_counts[effect_id] = (
                        planned_counts.get(effect_id, 0) + 1
                    )

        applications = {}
        for mission, records in (
            (self.state or {}).get('enemy_reward_applications', {}).items()
        ):
            for record in records or ():
                if not isinstance(record, dict):
                    continue
                effect_id = str(record.get('effect_id') or '')
                if not effect_id or not record.get('house'):
                    continue
                data = applications.setdefault(effect_id, {
                    'missions': set(), 'houses': set(), 'stack': 0,
                })
                data['missions'].add(str(mission))
                data['houses'].add(str(record['house']))
                try:
                    data['stack'] = max(
                        data['stack'], int(record.get('stack', 0))
                    )
                except (TypeError, ValueError):
                    pass

        source_labels = []
        if settings['rewards_per_completed_objective'] > 0:
            source_labels.append(
                f'{settings["rewards_per_completed_objective"]}/objective'
            )
        if settings['rewards_per_completed_mission'] > 0:
            source_labels.append(
                f'{settings["rewards_per_completed_mission"]}/mission'
            )
        if settings['reward_enabled']:
            source_labels.append('normal reward pool')

        entries = []
        for definition in ENEMY_BUFF_DEFINITIONS:
            effect_id = definition['id']
            cap = int(settings['caps'].get(effect_id, 0))
            enabled = effect_id in allowed and cap > 0
            applied = applications.get(effect_id)
            active = min(active_counts.get(effect_id, 0), cap)
            planned = min(planned_counts.get(effect_id, 0), cap)
            status = (
                'applied' if applied
                else 'earned' if active
                else 'planned' if planned
                else 'enabled' if enabled and source_labels
                else 'disabled'
            )
            effect_text = enemy_effect_text(definition, 1)
            if definition.get('effect') == 'armor' and '+' in effect_text:
                tooltip = f'{effect_text.rsplit("+", 1)[1]} more armor'
            elif (
                definition.get('effect') == 'production'
                and '-' in effect_text
            ):
                tooltip = (
                    f'{effect_text.rsplit("-", 1)[1]} faster production'
                )
            else:
                tooltip = effect_text
            entries.append({
                'id': effect_id,
                'label': (
                    f'{definition["category"]}\n{definition["type"]}'
                ),
                'status': status,
                'tooltip': tooltip,
            })
        return entries

    def refresh_enemy_buff_catalogue(self):
        if not hasattr(self, 'enemy_buff_catalogue_frame'):
            return
        frame = self.enemy_buff_catalogue_frame
        for child in frame.winfo_children():
            child.destroy()
        field = '#20242b' if self.dark_mode_var.get() else '#ffffff'
        foreground = '#ff7b72' if self.dark_mode_var.get() else '#b00020'
        outlines = {
            'applied': '#4f86c6',
            'earned': '#ff7b72',
            'planned': '#858b95',
            'enabled': '#40d36d',
            'disabled': '#4a4a4a',
        }
        tooltips = []
        self.enemy_buff_cards = []
        for index, entry in enumerate(self.enemy_buff_catalogue_entries()):
            card = tk.Frame(
                frame,
                borderwidth=0,
                highlightthickness=2,
                highlightbackground=outlines[entry['status']],
                highlightcolor=outlines[entry['status']],
                background=field,
                cursor='hand2',
            )
            label = tk.Label(
                card,
                text=entry['label'],
                foreground=foreground,
                background=field,
                font=('Segoe UI', 9),
                justify='center',
                anchor='center',
                padx=8,
                pady=10,
                cursor='hand2',
            )
            label.pack(fill='both', expand=True)
            tooltips.append(WidgetTooltip(card, entry['tooltip']))
            tooltips.append(WidgetTooltip(label, entry['tooltip']))
            self.enemy_buff_cards.append((card, label))
        self.enemy_buff_card_tooltips = tooltips
        self.after_idle(self.layout_enemy_buff_cards)

    def layout_enemy_buff_cards(self, event=None):
        """Wrap cards into responsive columns without horizontal scrolling."""
        frame = getattr(self, 'enemy_buff_catalogue_frame', None)
        cards = getattr(self, 'enemy_buff_cards', ())
        if frame is None or not cards:
            return
        available = int(getattr(event, 'width', 0) or frame.winfo_width())
        if available <= 1:
            available = 720
        scale = max(1.0, float(frame.winfo_fpixels('1i')) / 96.0)
        minimum = max(130, int(155 * scale))
        columns = max(1, min(4, available // minimum))
        previous = int(getattr(self, '_enemy_buff_card_columns', 0))
        for column in range(max(previous, columns, 4)):
            frame.columnconfigure(
                column,
                weight=1 if column < columns else 0,
                uniform='enemy-bonus-cards' if column < columns else '',
            )
        wraplength = max(90, (available // columns) - int(24 * scale))
        for index, (card, label) in enumerate(cards):
            card.grid(
                row=index // columns,
                column=index % columns,
                padx=3,
                pady=3,
                sticky='nsew',
            )
            label.configure(wraplength=wraplength)
        self._enemy_buff_card_columns = columns

    def refresh_enemy_buffs_view(self):
        if not getattr(self, '_enemy_buffs_view_dirty', False):
            return
        if not hasattr(self, 'enemy_buff_catalogue_frame'):
            return
        self._enemy_buffs_view_dirty = False
        self.refresh_enemy_buff_catalogue()
