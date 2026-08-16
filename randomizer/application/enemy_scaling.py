"""AI-reward progress, applied-target state, and dashboard."""

from ._dependencies import (
    ENEMY_BUFF_BY_ID,
    ENEMY_BUFF_DEFINITIONS,
    ENEMY_BUFF_GROUP_DEFINITIONS,
    MAX_ENEMY_TOTAL_BUFFS,
    canonical_reward,
    configured_enemy_reward,
    enemy_buff_capacity,
    enemy_effect_text,
    normalize_enemy_scaling_settings,
    tk,
)


class EnemyScalingController:

    def enemy_reward_text(self, reward):
        """Return one assignment's concise effect without reward/stack noise."""
        return enemy_effect_text(canonical_reward(reward), 1)

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
        per_effect_capacity = sum(
            max(0, int(self.enemy_buff_cap_vars[effect_id].get()))
            for effect_id in enabled_ids
        )
        try:
            maximum_total = max(
                0, int(self.enemy_maximum_total_buffs_var.get())
            )
        except (tk.TclError, TypeError, ValueError):
            maximum_total = 0
        capacity = min(maximum_total, per_effect_capacity)
        possible = enemy_buff_capacity({
            'maximum_total_buffs': per_effect_capacity,
            'allowed_buff_ids': enabled_ids,
            'caps': {
                effect_id: self.enemy_buff_cap_vars[effect_id].get()
                for effect_id in enabled_ids
            },
        })
        if hasattr(self, 'enemy_maximum_total_buffs_spinbox'):
            self.enemy_maximum_total_buffs_spinbox.configure(
                to=min(MAX_ENEMY_TOTAL_BUFFS, possible)
            )
        if hasattr(self, 'enemy_maximum_total_buffs_label'):
            self.enemy_maximum_total_buffs_label.configure(
                text=f'Maximum total AI bonus stacks [0-{possible}]'
            )
        if maximum_total > possible:
            maximum_total = possible
            self.enemy_maximum_total_buffs_var.set(possible)
            capacity = possible
        self.enemy_reward_capacity_label.configure(text=(
            f'Base Randomizer can grant up to {capacity} additional AI bonus '
            'stack(s) beside normal rewards. Archipelago exports them as Trap '
            f'items. {len(enabled_ids)} enabled bonuses allow at most '
            f'{possible} stacks under their per-bonus caps.'
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

    def active_enemy_scaling_entries(self):
        """Return received AP traps or acquired standalone enemy bonuses."""
        if not self.state:
            return []
        enemy_settings = normalize_enemy_scaling_settings(
            self.state.get('reward_settings', {}).get('enemy_scaling')
        )

        def active_reward(value):
            reward = canonical_reward(value)
            return configured_enemy_reward(reward, enemy_settings) or {}

        entries = []
        if self.archipelago_run_active():
            for source, reward in self.archipelago_reward_source_items() or ():
                reward = active_reward(reward)
                if reward.get('enemy_reward'):
                    entries.append({
                        'reward': reward,
                        'source': 'Archipelago item',
                        'earned_from': source,
                    })
        else:
            checks = {
                (str(code), str(check.get('id'))): check
                for code in self.state.get('mission_order', ())
                for check in self.state.get('mission_checks', {}).get(code, ())
                if isinstance(check, dict) and check.get('id')
            }
            mission_lookup = (
                self.mission_lookup() if getattr(self, 'missions', None) else {}
            )
            for planned in self.state.get('enemy_reward_plan', ()):
                if not isinstance(planned, dict):
                    continue
                code = str(planned.get('mission') or '')
                check_id = str(planned.get('check_id') or '')
                check = checks.get((code, check_id))
                if not check or not (
                    check.get('unlocked') or check.get('released')
                ):
                    continue
                reward = active_reward(planned.get('reward', {}))
                if not reward.get('enemy_reward'):
                    continue
                title = mission_lookup.get(code, {}).get('title', code)
                entries.append({
                    'reward': reward,
                    'source': 'Randomizer consequence',
                    'earned_from': (
                        f'{title} - {check.get("name", check_id)}'
                    ),
                })
        maximum_total = enemy_settings['maximum_total_buffs']
        capped = []
        counts = {}
        for entry in entries:
            reward = entry['reward']
            effect_id = str(reward.get('enemy_effect_id') or '')
            if len(capped) >= maximum_total:
                break
            if counts.get(effect_id, 0) >= int(
                reward.get('enemy_maximum', 1)
            ):
                continue
            counts[effect_id] = counts.get(effect_id, 0) + 1
            capped.append(entry)
        return capped

    def enemy_rewards_for_check(self, code, check_id):
        """Return standalone enemy bonuses assigned beside one normal check."""
        if not self.state or self.archipelago_run_active():
            return []
        enemy_settings = normalize_enemy_scaling_settings(
            self.state.get('reward_settings', {}).get('enemy_scaling')
        )
        rewards = []
        for planned in self.state.get('enemy_reward_plan', ()):
            if not isinstance(planned, dict):
                continue
            if (
                str(planned.get('mission') or '') != str(code)
                or str(planned.get('check_id') or '') != str(check_id)
            ):
                continue
            reward = canonical_reward(planned.get('reward', {}))
            reward = configured_enemy_reward(reward, enemy_settings)
            if reward and reward.get('enemy_reward'):
                rewards.append(reward)
        return rewards

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
                current_stacks = max(1, int(item['current_stacks']))
                maximum_stacks = max(
                    current_stacks, int(item['maximum_stacks'])
                )
                per_stack_value = max(0.0, float(item['per_stack_value']))
                base_engine_value = max(
                    0.001, float(item['base_engine_value'])
                )
                final_engine_value = max(
                    0.001, float(item['final_engine_value'])
                )
                displayed_percentage = max(
                    0, int(item['displayed_percentage'])
                )
            except (KeyError, TypeError, ValueError):
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
                'category': str(item.get('category') or '').strip(),
                'target': target,
                'effect': effect,
                'per_stack_value': per_stack_value,
                'current_stacks': current_stacks,
                'maximum_stacks': maximum_stacks,
                'engine_field': str(
                    item.get('engine_field') or ''
                ).strip(),
                'base_engine_value': base_engine_value,
                'final_engine_value': final_engine_value,
                'displayed_percentage': displayed_percentage,
            })
        normalized.sort(key=lambda item: (
            item['effect_id'], item['house'].casefold(), item['target'].casefold(),
            item['current_stacks'], item['source'], item['earned_from'],
        ))
        records = self.state.setdefault('enemy_reward_applications', {})
        if records.get(code) == normalized:
            return
        records[code] = normalized
        self._enemy_buffs_view_dirty = True
        self.save_state()

    def enemy_scaling_dashboard_rows(self):
        rows = []
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
                try:
                    current = max(1, int(item['current_stacks']))
                    maximum = max(current, int(item['maximum_stacks']))
                except (KeyError, TypeError, ValueError):
                    continue
                rows.append({
                    'id': '|'.join((str(mission), effect_id, house, target)),
                    'name': str(item.get('reward_name') or effect_id),
                    'house': house,
                    'target': target,
                    'effect': effect,
                    'stacks': f'{current}/{maximum}',
                    'source': str(item.get('source') or 'AI reward'),
                    'earned_from': (
                        f'{mission}: '
                        + str(item.get('earned_from') or 'Saved AI progress')
                    ),
                    'reward': dict(ENEMY_BUFF_BY_ID.get(effect_id, {})),
                })
        return sorted(rows, key=lambda row: (
            row['earned_from'].casefold(), row['name'].casefold(),
            row['house'].casefold(),
        ))

    def enemy_buff_catalogue_entries(self):
        """Show only enemy bonuses actually received by this player."""
        if not self.state:
            return []
        earned = {}
        for entry in self.active_enemy_scaling_entries():
            reward = entry.get('reward') if isinstance(entry, dict) else None
            effect_id = str((reward or {}).get('enemy_effect_id') or '')
            if effect_id in ENEMY_BUFF_BY_ID and isinstance(reward, dict):
                earned.setdefault(effect_id, []).append(entry)
        applications = {}
        for mission, records in (
            (self.state or {}).get('enemy_reward_applications', {}).items()
        ):
            for record in records or ():
                if not isinstance(record, dict):
                    continue
                effect_id = str(record.get('effect_id') or '')
                if (
                    not effect_id
                    or not record.get('house')
                    or not record.get('target')
                    or not record.get('effect')
                ):
                    continue
                try:
                    current = max(1, int(record['current_stacks']))
                    maximum = max(current, int(record['maximum_stacks']))
                    per_stack = max(0.0, float(record['per_stack_value']))
                    final_engine = max(
                        0.001, float(record['final_engine_value'])
                    )
                    displayed = max(0, int(record['displayed_percentage']))
                except (KeyError, TypeError, ValueError):
                    continue
                applications.setdefault(effect_id, []).append({
                    **record,
                    'mission': str(mission),
                    'current_stacks': current,
                    'maximum_stacks': maximum,
                    'per_stack_value': per_stack,
                    'final_engine_value': final_engine,
                    'displayed_percentage': displayed,
                })

        entries = []
        for definition in ENEMY_BUFF_DEFINITIONS:
            effect_id = definition['id']
            receipts = applications.get(effect_id, ())
            earned_entries = earned.get(effect_id, ())
            if not earned_entries:
                continue
            reward = earned_entries[0]['reward']
            maximum = max(1, int(reward.get(
                'enemy_maximum', definition.get('maximum_stacks', 1)
            )))
            earned_count = min(maximum, len(earned_entries))
            applied = None
            applied_count = 0
            if receipts:
                _index, applied = max(
                    enumerate(receipts),
                    key=lambda pair: (
                        pair[1]['current_stacks'], pair[0]
                    ),
                )
                applied_count = applied['current_stacks']

            status = (
                'applied'
                if applied is not None and applied_count >= earned_count
                else 'earned'
            )
            if definition.get('effect') == 'power':
                power_name = definition['type']
                if power_name in {'Support Power', 'Aid Power'}:
                    power_name = str(definition['name']).removeprefix('AI ')
                entries.append({
                    'id': effect_id,
                    'label': (
                        f'{definition["category"]}\n{power_name}\n'
                        'Acquired'
                    ),
                    'status': status,
                })
                continue

            effect = enemy_effect_text(reward, earned_count)
            category_prefix = f'{definition["category"]} '
            if effect.startswith(category_prefix):
                effect = effect[len(category_prefix):]
            entries.append({
                'id': effect_id,
                'label': (
                    f'{definition["category"]}\n{effect} '
                    f'({earned_count}/{maximum})'
                ),
                'status': status,
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
        self.enemy_buff_cards = []
        for entry in self.enemy_buff_catalogue_entries():
            card = tk.Frame(
                frame,
                borderwidth=0,
                highlightthickness=2,
                highlightbackground=foreground,
                highlightcolor=foreground,
                background=field,
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
            )
            label.pack(fill='both', expand=True)
            canvas = getattr(self, 'enemy_buffs_canvas', None)
            if canvas is not None:
                for widget in (card, label):
                    widget.bind(
                        '<MouseWheel>',
                        lambda event, target=canvas: (
                            self.on_unlock_mousewheel(event, target)
                        ),
                        add='+',
                    )
            self.enemy_buff_cards.append((card, label))
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
