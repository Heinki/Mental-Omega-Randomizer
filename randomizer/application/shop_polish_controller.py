"""Shop Mode presentation, sorting, tooltips, and run summaries."""

from collections import Counter
from tkinter import ttk

from randomizer.rewards.definitions import unit_display_label
from randomizer.rewards.display import buff_effect_lines, reward_display_name
from randomizer.shop.active import (
    active_shop_power_ids,
    active_shop_rewards,
    active_shop_tech_ids,
)
from randomizer.shop.catalogue import canonical_reward_for_id
from randomizer.shop.economy import (
    mission_reward,
    run_reward_price,
)
from randomizer.shop.model import RunStatus, ShopRewardType
from randomizer.shop.modifiers import (
    hidden_offer_codes,
    modifier_difficulty,
    modifier_effects,
)
from randomizer.shop.text import gem_text
from randomizer.shop.inventory import (
    guarantee_premium_offer,
    preserve_locked_offer,
    rotating_power_inventory,
    rotating_unit_inventory,
)
from randomizer.shop.mission_modifiers import (
    mission_modifier_for_run_offer,
)
from randomizer.shop.summary import reward_breakdown_lines, run_summary_lines
from randomizer.shop.transitions import ShopTransitionError

from .shop_archipelago_controller import ShopArchipelagoController


class ShopPolishController(ShopArchipelagoController):
    def configure_shop_embedded_button_tree(self, tree, button_attribute):
        """Keep real buttons aligned with visible Treeview action cells."""
        scrollbar = getattr(tree, '_shop_vertical_scrollbar', None)

        def schedule_reflow(_event=None):
            self.after_idle(
                lambda: self._position_shop_tree_buttons(
                    tree, button_attribute
                )
            )

        if scrollbar is not None:
            def update_scrollbar(first, last):
                scrollbar.set(first, last)
                schedule_reflow()

            def scroll_tree(*args):
                tree.yview(*args)
                schedule_reflow()

            tree.configure(yscrollcommand=update_scrollbar)
            scrollbar.configure(command=scroll_tree)
        tree.bind('<Configure>', schedule_reflow, add='+')
        tree.bind('<MouseWheel>', schedule_reflow, add='+')
        tree.bind('<Button-4>', schedule_reflow, add='+')
        tree.bind('<Button-5>', schedule_reflow, add='+')

    def _clear_shop_tree_buttons(self, button_attribute):
        buttons = self.__dict__.get(button_attribute, {})
        for button in buttons.values():
            button.destroy()
        self.__dict__[button_attribute] = {}

    def _position_shop_tree_buttons(self, tree, button_attribute):
        if not tree.winfo_exists():
            return
        for iid, button in self.__dict__.get(button_attribute, {}).items():
            if not button.winfo_exists():
                continue
            bounds = tree.bbox(iid, 'upgrades')
            if not bounds:
                button.place_forget()
                continue
            x, y, width, height = bounds
            inset = 5
            button_height = min(30, max(22, height - 8))
            button.place(
                x=x + inset,
                y=y + max(0, (height - button_height) // 2),
                width=max(24, width - inset * 2),
                height=button_height,
            )

    def _rebuild_shop_catalogue_upgrade_buttons(self):
        attribute = '_shop_catalogue_upgrade_buttons'
        self._clear_shop_tree_buttons(attribute)
        buttons = {}
        for iid, target in self._shop_catalogue_upgrade_targets.items():
            button = ttk.Button(
                self.shop_catalogue_tree,
                text='Open Upgrades',
                style='Launch.TButton',
                takefocus=False,
                command=lambda row=iid, value=target: (
                    self._open_shop_catalogue_upgrade_button(row, value)
                ),
            )
            buttons[iid] = button
        self.__dict__[attribute] = buttons
        self.after_idle(lambda: self._position_shop_tree_buttons(
            self.shop_catalogue_tree, attribute
        ))

    def _open_shop_catalogue_upgrade_button(self, iid, target):
        self.shop_catalogue_tree.selection_set(iid)
        self._show_shop_buffs_for_target(target[0], power=target[1])

    def _rebuild_shop_loadout_upgrade_buttons(self):
        attribute = '_shop_loadout_upgrade_buttons'
        self._clear_shop_tree_buttons(attribute)
        buttons = {}
        for iid, target in self._shop_current_loadout_targets.items():
            button = ttk.Button(
                self.shop_loadout_tree,
                text='Open Upgrades',
                style='Launch.TButton',
                takefocus=False,
                command=lambda row=iid, value=target: (
                    self._open_shop_loadout_upgrade_button(row, value)
                ),
            )
            buttons[iid] = button
        self.__dict__[attribute] = buttons
        self.after_idle(lambda: self._position_shop_tree_buttons(
            self.shop_loadout_tree, attribute
        ))

    def _open_shop_loadout_upgrade_button(self, iid, target):
        self.shop_loadout_tree.selection_set(iid)
        self._show_shop_buffs_for_target(target[0], power=target[1])

    def configure_shop_tree_tags(self):
        dark = bool(self.dark_mode_var.get())
        colors = {
            'available': (
                '#183d28' if dark else '#dafbe1',
                '#7ee787' if dark else '#116329',
            ),
            'owned': (
                '#17365d' if dark else '#ddf4ff',
                '#79c0ff' if dark else '#0550ae',
            ),
            'stacked': (
                '#3b285e' if dark else '#fbefff',
                '#d2a8ff' if dark else '#8250df',
            ),
            'maxed': (
                '#4d3b16' if dark else '#fff8c5',
                '#f2cc60' if dark else '#7d4e00',
            ),
            'unavailable': (
                '#161b22' if dark else '#f6f8fa',
                '#6e7681' if dark else '#8c959f',
            ),
            'selected_loadout': (
                '#17365d' if dark else '#ddf4ff',
                '#79c0ff' if dark else '#0550ae',
            ),
        }
        for tree_name in (
            'shop_catalogue_tree',
            'shop_permanent_unit_tree',
            'shop_upgrade_tree',
            'shop_permanent_buff_tree',
            'shop_loadout_select_tree',
        ):
            tree = getattr(self, tree_name, None)
            if tree is None:
                continue
            for tag, (background, foreground) in colors.items():
                tree.tag_configure(
                    tag, background=background, foreground=foreground
                )

    def _shop_mode_context_selected(self):
        variable = self.__dict__.get('progression_mode_var')
        return bool(variable is not None and variable.get() == 'Shop Mode')

    def _shop_context_run(self):
        launch_run = self.__dict__.get('_shop_launch_run')
        if launch_run is not None:
            return launch_run
        if not self._shop_mode_context_selected():
            return None
        repository = self.__dict__.get('shop_repository')
        if repository is None:
            return self.__dict__.get('shop_run')
        return repository.load_run()

    def _shop_ui_rewards(self):
        run = self._shop_context_run()
        if run is not None:
            return tuple(active_shop_rewards(run))
        if not self._shop_mode_context_selected():
            return None
        profile = self.__dict__.get('shop_profile')
        return tuple(
            canonical_reward_for_id(reward_id)
            for reward_id in (
                profile.permanent_unit_unlocks if profile is not None else ()
            )
        )

    def canonical_earned_rewards(self):
        rewards = self._shop_ui_rewards()
        if rewards is not None:
            return rewards
        return super().canonical_earned_rewards()

    def starting_reward_source_items(self):
        """Keep the reused unlock dashboard isolated from an older normal seed."""
        if not self._shop_mode_context_selected():
            return super().starting_reward_source_items()
        run = self._shop_context_run()
        if run is None:
            return []
        return [
            ('Selected permanent Shop unlock', canonical_reward_for_id(reward_id))
            for reward_id in run.selected_permanent_units
        ]

    def unlock_dashboard_sources(self):
        rewards = self._shop_ui_rewards()
        if rewards is None:
            return super().unlock_dashboard_sources()
        run = self._shop_context_run()
        source = (
            'Current Shop loadout'
            if run is not None
            else 'Permanent Shop unlock'
        )
        indexed = {}
        for reward in rewards:
            for key in self.unlock_dashboard_reward_keys(reward):
                entry = indexed.setdefault(key, {
                    'assigned': [],
                    'earned': [],
                    'earned_unlocks': [],
                    'available': [],
                    'available_unlocks': [],
                    'available_codes': [],
                })
                item = (source, reward)
                entry['assigned'].append(item)
                entry['earned'].append(item)
                if reward.get('kind') != 'buff':
                    entry['earned_unlocks'].append(item)
        return indexed

    def refresh_unlocks_view(self):
        if not self._shop_mode_context_selected():
            return super().refresh_unlocks_view()
        if not getattr(self, '_unlocks_view_dirty', False):
            return
        self._unlocks_view_dirty = False
        run = self._shop_context_run()
        rewards = self._shop_ui_rewards() or ()
        tech_ids = tuple(active_shop_tech_ids(run)) if run is not None else ()
        lines = []
        if run is None:
            lines.extend((
                'Shop Mode Permanent Unlocks',
                '===========================',
            ))
            if rewards:
                lines.extend(
                    reward_display_name(reward) for reward in rewards
                )
            else:
                lines.append('No permanent Shop unlocks purchased yet.')
        else:
            lines.extend((
                'Current Shop Loadout',
                '====================',
                f'Seed: {run.seed}',
                f'Stage: {run.stage}/{run.run_length}',
                '',
                'Active Units and Defenses',
                '-------------------------',
            ))
            lines.extend(
                unit_display_label(tech_id) for tech_id in tech_ids
            )
            lines.extend(('', 'Active Unlocks and Buffs', '------------------------'))
            counts = Counter(reward_display_name(reward) for reward in rewards)
            if counts:
                for name in sorted(counts, key=str.casefold):
                    suffix = f' x{counts[name]}' if counts[name] > 1 else ''
                    lines.append(f'{name}{suffix}')
            else:
                lines.append('No purchased unlocks or buffs yet.')
        self.set_unlocks_text('\n'.join(lines), tech_ids)

    def refresh_progress_view(self):
        if not self._shop_mode_context_selected():
            return super().refresh_progress_view()
        run = self._shop_context_run()
        if run is None:
            self.progress_label.config(
                text='Shop Mode | No active run\nStart a run from Settings.'
            )
            self.set_rewards_text(
                'Shop mission details appear here after a run starts.'
            )
        else:
            self.progress_label.config(text=(
                f'Seed: {run.seed} | Shop Mode | {run.reward_mode}\n'
                f'Stage: {run.stage}/{run.run_length} | '
                f'Completed: {len(run.completed_missions)} | '
                f'Ore: {run.run_coins} | '
                f'Status: {run.status.value.title()}'
            ))
            lines = ['Current mission offers', '======================']
            for offer in run.mission_offers:
                mission = self._shop_mission(offer.mission_code)
                mission_modifier = mission_modifier_for_run_offer(
                    run,
                    offer,
                    challenge_slots=self._shop_challenge_slots(),
                )
                definition = self.shop_config.mission_rewards[
                    offer.economy_class
                ]
                selected = bool(
                    run.mission_committed
                    and run.selected_mission_code == offer.mission_code
                )
                normal_difficulty, eased_difficulty = (
                    self.shop_eased_difficulty_labels(
                        run, offer.mission_code
                    )
                )
                marker = ' [IN PROGRESS]' if selected else ''
                lines.extend((
                    '',
                    f'{mission.get("title") or offer.mission_code} '
                    f'({offer.mission_code}){marker}',
                    f'{mission.get("side") or "Unknown faction"} | '
                    f'{definition.display_name} | '
                    f'Reward Tier {definition.difficulty} | '
                    f'Game difficulty {normal_difficulty}'
                    + (
                        f' -> {eased_difficulty}'
                        if run.assisted_mission_code == offer.mission_code
                        else ''
                    ),
                ))
                if mission_modifier is not None:
                    kind = 'Challenge' if mission_modifier.challenge else 'Boon'
                    lines.append(
                        f'{kind}: {mission_modifier.title} — '
                        f'{mission_modifier.description} '
                        f'Reward bonus: {mission_modifier.reward_text}.'
                    )
                if selected:
                    lines.extend(reward_breakdown_lines(
                        offer.economy_class,
                        victory_coin_bonus_level=(
                            self.shop_profile.upgrade_level(
                                'victory_run_coin_bonus'
                            )
                        ),
                        modifiers=run.modifiers,
                        mission_modifier=mission_modifier,
                        challenge_hunter_level=(
                            self.shop_profile.upgrade_level('challenge_hunter')
                        ),
                    ))
            if not run.mission_offers:
                lines.append('Run finished. See Run Summary and Run History.')
            self.set_rewards_text('\n'.join(lines))
        self.__dict__.pop('_unlock_dashboard_sources_cache', None)
        self.__dict__.pop('_canonical_earned_rewards_cache', None)
        self.unlock_dashboard_signature = None
        self._unlocks_view_dirty = True
        self._enemy_buffs_view_dirty = True
        if self.unlocks_view_visible():
            self.refresh_unlocks_view()
        if self.enemy_buffs_view_visible():
            self.refresh_enemy_buffs_view()

    def _refresh_shop_missions(self):
        run = self.shop_run
        offers = run.mission_offers if run is not None else ()
        hidden = set(hidden_offer_codes(run)) if run is not None else set()
        reroll_capacity = self._shop_reroll_capacity()
        assist_capacity = self._shop_difficulty_assist_capacity()
        rerolls_left = max(
            0, reroll_capacity - (run.rerolls_used if run is not None else 0)
        )
        assists_left = max(
            0,
            assist_capacity
            - (run.difficulty_assists_used if run is not None else 0),
        )
        for index, card in enumerate(self.shop_mission_cards):
            if index >= len(offers):
                card['frame'].grid_remove()
                card['frame'].configure(text=f'Choice {index + 1}')
                card['code'] = ''
                card['name'].set('No mission')
                card['detail'].set('')
                card['difficulty'].set('')
                card['difficulty_label'].configure(
                    style='Shop.Difficulty.Casual.TLabel'
                )
                card['reward'].set('')
                card['effect'].set('')
                card['effect_label'].configure(style='Shop.Help.TLabel')
                card['tooltip'].text = ''
                card['launch_button'].configure(
                    state='disabled', text='Launch This Mission'
                )
                card['reroll_button'].configure(
                    state='disabled', text='Reroll This Mission'
                )
                card['ease_button'].configure(
                    state='disabled', text='Ease Difficulty'
                )
                continue
            card['frame'].grid()
            offer = offers[index]
            mission_modifier = mission_modifier_for_run_offer(
                run,
                offer,
                challenge_slots=self._shop_challenge_slots(),
            )
            mission = self._shop_mission(offer.mission_code)
            definition = self.shop_config.mission_rewards[offer.economy_class]
            reward = mission_reward(
                offer.economy_class,
                victory_coin_bonus_level=self.shop_profile.upgrade_level(
                    'victory_run_coin_bonus'
                ),
                modifiers=run.modifiers,
                mission_modifier=mission_modifier,
                challenge_hunter_level=self.shop_profile.upgrade_level(
                    'challenge_hunter'
                ),
            )
            selected = bool(
                run.mission_committed
                and run.selected_mission_code == offer.mission_code
            )
            assisted = run.assisted_mission_code == offer.mission_code
            normal_difficulty, eased_difficulty = (
                self.shop_eased_difficulty_labels(run, offer.mission_code)
            )
            reward_hidden = offer.mission_code in hidden and not selected
            title = mission.get('title') or offer.mission_code
            faction = mission.get('side') or 'Unknown faction'
            card['code'] = offer.mission_code
            card['name'].set(f'{title} ({offer.mission_code})')
            card['detail'].set(
                f'Faction: {faction}\n'
                f'Mission class: {definition.display_name}\n'
                f'Reward tier: {definition.difficulty}\n'
                f'Run difficulty: +{modifier_difficulty(run.modifiers)}'
            )
            effective_difficulty = (
                eased_difficulty if assisted else normal_difficulty
            )
            card['difficulty'].set(
                f'Game difficulty: {normal_difficulty}'
                + (
                    f' → {eased_difficulty} (Eased)'
                    if assisted else ''
                )
            )
            card['difficulty_label'].configure(
                style=f'Shop.Difficulty.{effective_difficulty}.TLabel'
            )
            card['reward'].set(
                'Exact reward hidden until mission launch'
                if reward_hidden else
                f'Base +{definition.run_coins} Ore / '
                f'+{gem_text(definition.meta_coins)}  •  '
                f'Estimated +{reward.run_coins} / +{reward.meta_coins}'
                + ('  •  Full reward retained' if assisted else '')
            )
            card['effect'].set(
                (
                    f'{"Challenge" if mission_modifier.challenge else "Bonus"}: '
                    f'{mission_modifier.title} — {mission_modifier.description} '
                    f'Reward bonus: {mission_modifier.reward_text}.'
                )
                if mission_modifier is not None else ''
            )
            card['effect_label'].configure(
                style=(
                    'Shop.EnemyBuff.TLabel'
                    if mission_modifier is not None and mission_modifier.challenge
                    else 'Shop.PlayerBuff.TLabel'
                    if mission_modifier is not None
                    else 'Shop.Help.TLabel'
                )
            )
            breakdown = reward_breakdown_lines(
                offer.economy_class,
                victory_coin_bonus_level=self.shop_profile.upgrade_level(
                    'victory_run_coin_bonus'
                ),
                modifiers=run.modifiers,
                mission_modifier=mission_modifier,
                challenge_hunter_level=self.shop_profile.upgrade_level(
                    'challenge_hunter'
                ),
            )
            card['tooltip'].text = (
                'Blind Choice hides this reward until mission launch.'
                if reward_hidden else '\n'.join(breakdown)
                + (
                    f'\n\n{mission_modifier.title}: '
                    f'{mission_modifier.description}'
                    if mission_modifier is not None else ''
                )
            )
            card['frame'].configure(
                text=(
                    f'Choice {index + 1}'
                    + (' — In Progress' if selected else '')
                )
            )
            enabled = bool(
                run.status is RunStatus.ACTIVE
                and not run.mission_committed
                and not self.shop_launch_active()
            )
            launchable = bool(
                run.status is RunStatus.ACTIVE
                and not self.shop_launch_active()
                and (
                    not run.mission_committed
                    or run.selected_mission_code == offer.mission_code
                )
            )
            card['launch_button'].configure(
                state='normal' if launchable else 'disabled',
                text=(
                    'Relaunch This Mission'
                    if run.mission_committed and selected
                    else 'Launch This Mission'
                ),
            )
            card['reroll_button'].configure(
                state='normal' if enabled and rerolls_left else 'disabled',
                text=(
                    f'Reroll This Mission ({rerolls_left} left)'
                    if rerolls_left else 'No Rerolls Left'
                ),
            )
            base_difficulty = self.shop_mission_difficulty_value(
                run, offer.mission_code
            )
            can_assist = bool(
                enabled
                and assists_left
                and base_difficulty > 0
                and not run.assisted_mission_code
            )
            if assisted:
                assist_text = (
                    f'Eased: {normal_difficulty} -> {eased_difficulty}'
                )
            elif base_difficulty <= 0:
                assist_text = 'Already Casual'
            elif run.assisted_mission_code:
                assist_text = 'Assist Used This Stage'
            elif assists_left:
                assist_text = f'Ease Difficulty ({assists_left} left)'
            else:
                assist_text = 'No Assists Left'
            card['ease_button'].configure(
                state='normal' if can_assist else 'disabled',
                text=assist_text,
            )
        can_give_up = bool(
            run is not None
            and run.status is RunStatus.ACTIVE
            and not self.shop_launch_active()
        )
        self.shop_give_up_button.configure(
            state='normal' if can_give_up else 'disabled'
        )

    def _entry_price(self, entry):
        run = self.shop_run
        if run is None:
            return None
        if entry.reward_type in {
            ShopRewardType.UNIT_BUFF, ShopRewardType.POWER_BUFF
        }:
            definition = self.shop_config.permanent_upgrades['free_buff_token']
            capacity = (
                self.shop_profile.upgrade_level('free_buff_token')
                * int(definition.effects['tokens_per_level'])
            )
            if run.free_buff_tokens_used < capacity:
                return 0
        coupon_definition = self.shop_config.permanent_upgrades['coupon_book']
        coupon_discount = (
            self.shop_profile.upgrade_level('coupon_book')
            * int(coupon_definition.effects['ore_per_level'])
            if run.coupon_used_stage != run.stage else 0
        )
        return run_reward_price(
            entry,
            shop_discount_level=self.shop_profile.upgrade_level('shop_discount'),
            modifiers=run.modifiers,
            specialization_level=self.shop_profile.upgrade_level(
                'discount_specialization'
            ),
            coupon_discount_ore=coupon_discount,
        )

    def _selected_shop_catalogue_entries(self):
        return {
            'Offers': (*self._shop_unit_entries, *self._shop_power_entries),
            'Units': self._shop_unit_entries,
            'Unit Buffs': self._shop_buff_entries,
            'Powers': self._shop_power_entries,
            'Power Buffs': self._shop_power_buff_entries,
        }.get(self.shop_category_var.get(), ())

    def _sync_shop_buff_target_selector(
        self, category, candidates, active_tech, active_powers
    ):
        buff_category = category in {'Unit Buffs', 'Power Buffs'}
        if not buff_category:
            self.shop_buff_target_frame.pack_forget()
            self.shop_catalogue_back_button.pack_forget()
            if not self.shop_access_view_frame.winfo_manager():
                self.shop_access_view_frame.pack(
                    side='left', before=self.shop_search_label
                )
            self._shop_buff_target_ids = {}
            return ''
        self.shop_access_view_frame.pack_forget()
        self.shop_buff_target_frame.pack(
            side='left', before=self.shop_search_label
        )
        self.shop_catalogue_back_button.pack(
            side='left', before=self.shop_buff_target_frame, padx=(0, 10)
        )
        is_unit = category == 'Unit Buffs'
        self.shop_buff_target_label.configure(
            text='Upgrade unit:' if is_unit else 'Upgrade power:'
        )
        owned = active_tech if is_unit else active_powers
        target_ids = sorted({
            entry.target_id for entry in candidates
            if entry.target_id in owned
        })
        labels = []
        mapping = {}
        for target_id in target_ids:
            name = unit_display_label(target_id) if is_unit else target_id
            label = f'{name} [{target_id}]'
            labels.append(label)
            mapping[label] = target_id
        self._shop_buff_target_ids = mapping
        requested = self.__dict__.pop('_shop_requested_buff_target_id', '')
        current = self.shop_buff_target_var.get()
        if requested:
            current = next(
                (label for label, value in mapping.items() if value == requested),
                '',
            )
        if not requested and current not in mapping:
            current = labels[0] if labels else ''
        self.shop_buff_target_var.set(current)
        return mapping.get(current, '')

    def _shop_catalogue_entry_state(
        self, entry, run, active_tech, active_powers
    ):
        price = self._entry_price(entry)
        stacks = 0
        if run is not None:
            stacks = next((
                item.stacks for item in run.run_buffs
                if item.reward_id == entry.reward_id
            ), 0) + next((
                item.stacks for item in run.permanent_buffs_snapshot
                if item.reward_id == entry.reward_id
            ), 0)
            stacks += next((
                item.stacks for item in run.starting_draft_buffs
                if item.reward_id == entry.reward_id
            ), 0)
        locked = (
            entry.reward_type is ShopRewardType.UNIT_BUFF
            and entry.target_id not in active_tech
        ) or (
            entry.reward_type is ShopRewardType.POWER_BUFF
            and entry.target_id not in active_powers
        )
        access_active = (
            entry.reward_type is ShopRewardType.UNIT_ACCESS
            and entry.target_id in active_tech
        ) or (
            entry.reward_type is ShopRewardType.POWER_ACCESS
            and entry.target_id in active_powers
        )
        if access_active:
            state = 'Active / Owned'
        elif locked:
            state = 'Requires unit or power access'
        elif entry.stack_limit is not None and stacks >= entry.stack_limit:
            state = 'MAX'
        elif run is None:
            state = 'Start a run first'
        elif run.status is not RunStatus.ACTIVE:
            state = 'Run not active'
        elif run.mission_committed:
            state = 'Locked during mission'
        elif self.shop_launch_active():
            state = 'Previous mission closing'
        elif price is not None and run.run_coins < price:
            state = f'Need {price - run.run_coins} more Ore'
        elif stacks:
            maximum = entry.stack_limit if entry.stack_limit is not None else '∞'
            state = f'Stacks {stacks} / {maximum}'
        else:
            state = 'Available'
        return state, price, locked, stacks

    @staticmethod
    def _shop_catalogue_display_name(entry, state, stacks):
        if entry.reward_type not in {
            ShopRewardType.UNIT_BUFF,
            ShopRewardType.POWER_BUFF,
        }:
            return entry.reward_id
        count = max(1, stacks if state == 'MAX' else stacks + 1)
        effects = buff_effect_lines(
            canonical_reward_for_id(entry.reward_id),
            count=count,
            include_label=False,
            include_stack=False,
        )
        effect = '; '.join(effects) or reward_display_name(
            canonical_reward_for_id(entry.reward_id)
        )
        if state == 'MAX':
            return f'{effect} (MAX)'
        if stacks:
            return f'Next stack: {effect}'
        return effect

    def refresh_shop_catalogue(self, *_args):
        if not hasattr(self, 'shop_catalogue_tree'):
            return
        tree = self.shop_catalogue_tree
        previous_selection = tree.selection()
        selected_reward_id = self.__dict__.pop(
            '_shop_focus_reward_id', ''
        ) or (
            self._shop_catalogue_rows.get(previous_selection[0], '')
            if previous_selection else ''
        )
        self._clear_shop_tree_buttons('_shop_catalogue_upgrade_buttons')
        tree.delete(*tree.get_children())
        self._shop_catalogue_rows = {}
        self._shop_catalogue_buyable = {}
        self._shop_catalogue_upgrade_targets = {}
        self._shop_catalogue_details = {}
        term = self.shop_search_var.get().strip().casefold()
        run = self.shop_run
        modifier_values = modifier_effects(run.modifiers) if run else None
        active_tech = set(active_shop_tech_ids(run))
        active_powers = set(active_shop_power_ids(run))
        visible = []
        category = self.shop_category_var.get()
        access_category = category in {'Offers', 'Units', 'Powers'}
        buff_category = category in {'Unit Buffs', 'Power Buffs'}
        owned_view = bool(
            access_category and self.shop_access_view_var.get() == 'Owned'
        )
        tree.column(
            'upgrades',
            width=130 if access_category else 0,
            minwidth=100 if access_category else 0,
            stretch=access_category,
        )
        tree.heading(
            'upgrades',
            text=(
                'Upgrades'
                if access_category else ''
            ),
        )
        tree.heading('name', text='Effect' if buff_category else 'Reward')
        candidates = tuple(
            entry for entry in self._selected_shop_catalogue_entries()
            if owned_view or self._shop_entry_available(entry, run)
        )
        selected_target = self._sync_shop_buff_target_selector(
            category, candidates, active_tech, active_powers
        )
        access_candidates = candidates
        stock_definition = self.shop_config.permanent_upgrades[
            'extra_shop_stock'
        ]
        unit_offer_count = (
            self.shop_config.unit_inventory_size
            + self.shop_profile.upgrade_level('extra_shop_stock')
            * int(stock_definition.effects['units_per_level'])
            + (modifier_values['unit_inventory_flat'] if modifier_values else 0)
        )
        power_offer_count = (
            self.shop_config.power_inventory_size
            + self.shop_profile.upgrade_level('extra_shop_stock')
            * int(stock_definition.effects['powers_per_level'])
            + (modifier_values['power_inventory_flat'] if modifier_values else 0)
        )
        if owned_view:
            candidates = tuple(
                entry for entry in candidates
                if (
                    entry.reward_type is ShopRewardType.UNIT_ACCESS
                    and entry.target_id in active_tech
                ) or (
                    entry.reward_type is ShopRewardType.POWER_ACCESS
                    and entry.target_id in active_powers
                )
            )
        elif category == 'Offers':
            unit_candidates = tuple(
                entry for entry in candidates
                if entry.reward_type is ShopRewardType.UNIT_ACCESS
            )
            power_candidates = tuple(
                entry for entry in candidates
                if entry.reward_type is ShopRewardType.POWER_ACCESS
            )
            candidates = (
                (*rotating_unit_inventory(
                    unit_candidates,
                    run_seed=run.seed,
                    stage=run.stage,
                    offer_count=(
                        unit_offer_count
                    ),
                    excluded_target_ids=active_tech,
                ), *rotating_power_inventory(
                    power_candidates,
                    run_seed=run.seed,
                    stage=run.stage,
                    offer_count=(
                        power_offer_count
                    ),
                    excluded_target_ids=active_powers,
                ))
                if run is not None else ()
            )
        elif category == 'Units':
            candidates = (
                rotating_unit_inventory(
                    candidates,
                    run_seed=run.seed,
                    stage=run.stage,
                    offer_count=(
                        unit_offer_count
                    ),
                    excluded_target_ids=active_tech,
                )
                if run is not None else ()
            )
        elif category == 'Powers':
            candidates = (
                rotating_power_inventory(
                    candidates,
                    run_seed=run.seed,
                    stage=run.stage,
                    offer_count=(
                        power_offer_count
                    ),
                    excluded_target_ids=active_powers,
                )
                if run is not None else ()
            )
        elif buff_category:
            candidates = tuple(
                entry for entry in candidates
                if entry.target_id == selected_target
            )
        if run is not None and access_category and not owned_view:
            locked_entry = self._shop_entry_by_reward_id.get(
                run.stock_lock_reward_id or ''
            )
            if (
                locked_entry is not None
                and run.stock_lock_stage is not None
                and run.stage <= run.stock_lock_stage + 1
                and self._shop_entry_available(locked_entry, run)
                and locked_entry.target_id not in active_tech
                and locked_entry.target_id not in active_powers
            ):
                candidates = preserve_locked_offer(candidates, locked_entry)
            protected = (
                (locked_entry.reward_id,)
                if locked_entry is not None else ()
            )
            premium = self.shop_config.permanent_upgrades['premium_supplier']
            if self.shop_profile.upgrade_level('premium_supplier'):
                eligible = tuple(
                    entry for entry in access_candidates
                    if entry.target_id not in active_tech
                    and entry.target_id not in active_powers
                )
                candidates = guarantee_premium_offer(
                    candidates,
                    eligible,
                    run_seed=run.seed,
                    stage=run.stage,
                    minimum_stage=int(premium.effects['minimum_stage']),
                    protected_reward_ids=protected,
                )
        for entry in candidates:
            if term and term not in (
                entry.reward_id + ' ' + entry.target_id
            ).casefold():
                continue
            detail = self._shop_catalogue_entry_state(
                entry, run, active_tech, active_powers
            )
            if buff_category and detail[2]:
                continue
            visible.append((entry, detail))
        tier_order = {'tier_1': 1, 'tier_2': 2, 'tier_3': 3, None: 0}
        sort_mode = self.shop_sort_var.get()
        key = {
            'Tier': lambda item: (
                tier_order.get(item[0].tier, 99), item[0].reward_id.casefold()
            ),
            'Price': lambda item: (
                item[1][1] if item[1][1] is not None else 10**9,
                item[0].reward_id.casefold(),
            ),
            'Status': lambda item: (
                item[1][0].casefold(), item[0].reward_id.casefold()
            ),
        }.get(
            sort_mode,
            lambda item: item[0].reward_id.casefold(),
        )
        visible.sort(key=key)
        if category == 'Unit Buffs':
            self.shop_catalogue_help_var.set(
                f'Buffing {self.shop_buff_target_var.get()}. '
                'Buy a buff repeatedly to stack it up to its listed limit.'
                if visible else
                'Select an owned unit above. No unavailable-unit buffs are shown.'
            )
        elif category == 'Power Buffs':
            self.shop_catalogue_help_var.set(
                f'Buffing {self.shop_buff_target_var.get()}. '
                'Buy a buff repeatedly to add stacks up to its listed limit.'
                if visible else
                'Select an owned power above. No unavailable-power buffs are shown.'
            )
        elif owned_view:
            unit_count = sum(
                entry.reward_type is ShopRewardType.UNIT_ACCESS
                for entry in candidates
            )
            self.shop_catalogue_help_var.set(
                f'{len(candidates)} active purchases and starting unlocks '
                f'({unit_count} units/buildings, '
                f'{len(candidates) - unit_count} powers). Use Open Upgrades '
                'to buy more buff stacks.'
            )
        elif category == 'Offers':
            power_count = sum(
                entry.reward_type is ShopRewardType.POWER_ACCESS
                for entry in candidates
            )
            self.shop_catalogue_help_var.set(
                f'{len(candidates)} current offers, including {power_count} '
                f'powers, for stage {run.stage if run is not None else "—"}. '
                'Stock changes after each mission victory. Buy an item, then '
                'use its Open Upgrades button.'
            )
        elif category == 'Units':
            self.shop_catalogue_help_var.set(
                f'{len(candidates)} units stocked for stage '
                f'{run.stage if run is not None else "—"}. '
                'Stock changes after each mission victory. Buy a unit, then '
                'use its Open Upgrades button.'
            )
        elif category == 'Powers':
            self.shop_catalogue_help_var.set(
                f'{len(candidates)} random superweapons and aid powers stocked '
                f'for stage {run.stage if run is not None else "—"}. '
                'Stock changes after each mission victory.'
            )
        else:
            self.shop_catalogue_help_var.set(
                'Green rows can be bought now. Grey rows are unavailable; '
                'blue rows are already active.'
            )
        cameo_images = self._prepare_shop_unit_cameos(
            entry.reward_id for entry, _detail in visible
        )
        restore_iid = ''
        for index, (entry, detail) in enumerate(visible):
            state, price, locked, stacks = detail
            iid = f'shop-{index}'
            buyable = state == 'Available' or state.startswith('Stacks ')
            row_tag = (
                'owned' if state == 'Active / Owned'
                else 'maxed' if state == 'MAX'
                else 'stacked' if state.startswith('Stacks ')
                else 'available' if buyable
                else 'unavailable'
            )
            matching_buffs = (
                self._shop_buff_entries
                if entry.reward_type is ShopRewardType.UNIT_ACCESS
                else self._shop_power_buff_entries
                if entry.reward_type is ShopRewardType.POWER_ACCESS
                else ()
            )
            has_upgrades = any(
                buff.target_id == entry.target_id for buff in matching_buffs
            )
            owns_access = (
                entry.reward_type is ShopRewardType.UNIT_ACCESS
                and entry.target_id in active_tech
            ) or (
                entry.reward_type is ShopRewardType.POWER_ACCESS
                and entry.target_id in active_powers
            )
            upgrade_available = has_upgrades and owns_access
            upgrade_action = (
                ''
                if upgrade_available
                else 'Buy Unit First'
                if has_upgrades and entry.reward_type is ShopRewardType.UNIT_ACCESS
                else 'Buy Power First'
                if has_upgrades and entry.reward_type is ShopRewardType.POWER_ACCESS
                else '—'
            )
            insert_options = {
                'iid': iid,
                'tags': (row_tag,),
                'values': (
                self._shop_catalogue_display_name(entry, state, stacks),
                (
                    'Power'
                    if entry.reward_type is ShopRewardType.POWER_ACCESS
                    else (entry.tier or '').replace('_', ' ').title()
                ),
                (
                    state + ' • Locked'
                    if run is not None
                    and entry.reward_id == run.stock_lock_reward_id
                    else state
                ),
                (
                    'FREE TOKEN'
                    if price == 0 and entry.reward_type in {
                        ShopRewardType.UNIT_BUFF, ShopRewardType.POWER_BUFF
                    }
                    else f'{price} Ore' if price is not None else '—'
                ),
                upgrade_action,
                ),
            }
            cameo = cameo_images.get(entry.reward_id)
            if cameo is not None:
                insert_options['image'] = cameo
            tree.insert('', 'end', **insert_options)
            self._shop_catalogue_rows[iid] = entry.reward_id
            self._shop_catalogue_buyable[iid] = buyable
            if upgrade_available:
                self._shop_catalogue_upgrade_targets[iid] = (
                    entry.target_id,
                    entry.reward_type is ShopRewardType.POWER_ACCESS,
                )
            reason = (
                'Purchase/unlock this unit first.'
                if locked and entry.reward_type is ShopRewardType.UNIT_BUFF
                else 'Purchase/unlock this power first.'
                if locked else state
            )
            self._shop_catalogue_details[iid] = (
                f'{entry.reward_id}\nType: '
                f'{entry.reward_type.value.replace("_", " ").title()}\n'
                f'Target: {entry.target_id or "—"}\n'
                f'Price: {"FREE TOKEN" if price == 0 else str(price) + " Ore" if price is not None else "—"}\n'
                f'State: {reason}'
                + (
                    '\nEffect: '
                    + self._shop_catalogue_display_name(entry, state, stacks)
                    if buff_category else ''
                )
                + (f'\nCurrent stacks: {stacks}' if stacks else '')
                + (
                    '\nStock Lock: preserved through the next stage rotation.'
                    if run is not None
                    and entry.reward_id == run.stock_lock_reward_id
                    else ''
                )
            )
            if entry.reward_id == selected_reward_id:
                restore_iid = iid
        if restore_iid:
            tree.selection_set(restore_iid)
            tree.see(restore_iid)
        self._rebuild_shop_catalogue_upgrade_buttons()
        self.refresh_shop_purchase_buttons()

    def click_shop_catalogue_upgrade_link(self, event):
        if self.shop_catalogue_tree.identify_column(event.x) != '#5':
            return
        iid = self.shop_catalogue_tree.identify_row(event.y)
        target = self._shop_catalogue_upgrade_targets.get(iid)
        if target:
            self.shop_catalogue_tree.selection_set(iid)
            self._show_shop_buffs_for_target(target[0], power=target[1])
            return 'break'

    def update_shop_catalogue_upgrade_cursor(self, event):
        iid = self.shop_catalogue_tree.identify_row(event.y)
        clickable = bool(
            self.shop_catalogue_tree.identify_column(event.x) == '#5'
            and iid in self._shop_catalogue_upgrade_targets
        )
        self.shop_catalogue_tree.configure(
            cursor='hand2' if clickable else ''
        )

    def click_loadout_upgrade_link(self, event):
        if self.shop_loadout_tree.identify_column(event.x) != '#3':
            return
        iid = self.shop_loadout_tree.identify_row(event.y)
        target = self._shop_current_loadout_targets.get(iid)
        if target:
            self.shop_loadout_tree.selection_set(iid)
            self._show_shop_buffs_for_target(target[0], power=target[1])
            return 'break'

    def update_loadout_upgrade_cursor(self, event):
        iid = self.shop_loadout_tree.identify_row(event.y)
        clickable = bool(
            self.shop_loadout_tree.identify_column(event.x) == '#3'
            and iid in self._shop_current_loadout_targets
        )
        self.shop_loadout_tree.configure(
            cursor='hand2' if clickable else ''
        )

    def activate_selected_shop_reward(self, _event=None):
        selected = self.shop_catalogue_tree.selection()
        reward_id = self._shop_catalogue_rows.get(
            selected[0], ''
        ) if selected else ''
        entry = self._shop_entry_by_reward_id.get(reward_id)
        active_tech = set(active_shop_tech_ids(self.shop_run))
        active_powers = set(active_shop_power_ids(self.shop_run))
        if (
            entry is not None
            and entry.reward_type in {
                ShopRewardType.UNIT_ACCESS,
                ShopRewardType.POWER_ACCESS,
            }
            and (
                entry.reward_type is ShopRewardType.UNIT_ACCESS
                and entry.target_id in active_tech
                or entry.reward_type is ShopRewardType.POWER_ACCESS
                and entry.target_id in active_powers
            )
        ):
            self.view_selected_shop_buffs()
        else:
            self.buy_selected_shop_reward()
        return 'break'

    def _show_shop_buffs_for_target(self, target_id, *, power=False):
        if not target_id:
            return
        self.shop_category_var.set('Power Buffs' if power else 'Unit Buffs')
        if self.shop_search_var.get():
            self.shop_search_var.set('')
        # shop_search_var has a write trace that refreshes the catalogue.
        # Arm the exact target only after clearing it so an intermediate
        # refresh cannot consume the request and fall back to the first unit.
        self._shop_requested_buff_target_id = target_id
        self.refresh_shop_catalogue()
        self.shop_panels.select(0)

    def show_shop_offers(self):
        self.shop_category_var.set('Offers')
        self.shop_search_var.set('')
        self.refresh_shop_catalogue()

    def show_shop_owned_access(self):
        self.shop_access_view_var.set('Owned')
        self.show_shop_offers()

    def view_selected_shop_buffs(self):
        selected = self.shop_catalogue_tree.selection()
        reward_id = self._shop_catalogue_rows.get(
            selected[0], ''
        ) if selected else ''
        entry = self._shop_entry_by_reward_id.get(reward_id)
        if entry is None:
            self.browse_owned_unit_upgrades(
                power=self.shop_category_var.get() == 'Powers'
            )
            return
        if entry.reward_type is ShopRewardType.UNIT_ACCESS:
            self._show_shop_buffs_for_target(entry.target_id)
        elif entry.reward_type is ShopRewardType.POWER_ACCESS:
            self._show_shop_buffs_for_target(entry.target_id, power=True)

    def browse_owned_unit_upgrades(self, *, power=False):
        del power
        if self.shop_run is not None:
            self.show_shop_owned_access()
            self.shop_panels.select(0)

    def view_selected_loadout_buffs(self, _event=None):
        selected = self.shop_loadout_tree.selection()
        target = self._shop_current_loadout_targets.get(
            selected[0]
        ) if selected else ''
        if target:
            self._show_shop_buffs_for_target(target[0], power=target[1])
        return 'break'

    def refresh_shop_purchase_buttons(self, _event=None):
        if not hasattr(self, 'shop_purchase_button'):
            return
        selected = self.shop_catalogue_tree.selection()
        buyable = bool(
            selected
            and self._shop_catalogue_buyable.get(selected[0], False)
            and not self.shop_launch_active()
        )
        self.shop_purchase_button.configure(
            state='normal' if buyable else 'disabled'
        )
        if hasattr(self, 'shop_stock_lock_button'):
            reward_id = self._shop_catalogue_rows.get(
                selected[0], ''
            ) if selected else ''
            entry = self._shop_entry_by_reward_id.get(reward_id)
            access_offer = bool(
                entry is not None
                and entry.reward_type in {
                    ShopRewardType.UNIT_ACCESS,
                    ShopRewardType.POWER_ACCESS,
                }
                and selected
                and self._shop_catalogue_buyable.get(selected[0], False)
            )
            has_upgrade = self.shop_profile.upgrade_level('stock_lock') > 0
            already_locked = bool(
                self.shop_run is not None
                and reward_id
                and self.shop_run.stock_lock_reward_id == reward_id
            )
            self.shop_stock_lock_button.configure(
                state=(
                    'normal'
                    if access_offer and has_upgrade and not already_locked
                    and not self.shop_launch_active()
                    else 'disabled'
                ),
                text=(
                    'Locked for Next Stage'
                    if already_locked else 'Lock Selected Offer'
                    if has_upgrade else 'Stock Lock Locked'
                ),
            )
        self.refresh_permanent_purchase_buttons()

    def lock_selected_shop_offer(self):
        selected = self.shop_catalogue_tree.selection()
        reward_id = self._shop_catalogue_rows.get(
            selected[0], ''
        ) if selected else ''
        if not reward_id:
            return
        try:
            self.shop_run = self.shop_service.lock_shop_offer(reward_id)
        except ShopTransitionError as exc:
            self._set_shop_message(exc, error=True)
        else:
            self._shop_focus_reward_id = reward_id
            self._set_shop_message(
                f'Locked {reward_id}; it remains offered next stage.'
            )
        self.refresh_shop_mode()

    def _shop_upgrade_effect_text(self, upgrade_id, definition):
        effects = definition.effects
        templates = {
            'mission_reroll': (
                f'Each level grants +{effects.get("rerolls_per_level", 0)} '
                'single-mission reroll per run.'
            ),
            'mission_difficulty_assist': (
                f'Each level grants +{effects.get("assists_per_level", 0)} '
                'mission assist per run. Assist lowers game difficulty one '
                'step for chosen mission without reducing its reward.'
            ),
            'victory_run_coin_bonus': (
                f'Each level grants +{effects.get("run_coins_per_level", 0)} '
                'Ore after every mission victory.'
            ),
            'starting_capital': (
                f'Each level grants +{effects.get("run_coins_per_level", 0)} '
                f'starting Ore, capped at {self.shop_config.maximum_starting_ore}.'
            ),
            'mission_starting_credits': (
                f'Each level adds '
                f'{effects.get("credits_per_level", 0):,} in-game Credits '
                'at every mission start, capped at 20,000. '
                'This is not Shop Ore.'
            ),
            'shop_discount': (
                f'Each level reduces run-shop prices by '
                f'{effects.get("ore_per_level", 0)} Ore, minimum price 1 Ore.'
            ),
            'extra_shop_stock': (
                f'Each level adds +{effects.get("units_per_level", 0)} unit '
                f'and +{effects.get("powers_per_level", 0)} power to every '
                'stage stock rotation.'
            ),
            'expanded_loadout': (
                f'Each level adds +{effects.get("slots_per_level", 0)} '
                'permanent/AP unit slot to the starting loadout.'
            ),
            'emergency_revival': (
                f'Each level grants {effects.get("revivals_per_run", 0)} '
                'automatic mission-failure rescue per run. Same stage, new offers.'
            ),
            'free_buff_token': (
                f'Each level grants +{effects.get("tokens_per_level", 0)} '
                'free run-shop buff purchase per run. Tokens are used first.'
            ),
            'challenge_hunter': (
                f'Each level adds +{effects.get("run_coins_per_level", 0)} '
                'Ore to challenge victories; every '
                f'{effects.get("meta_coins_every_levels", 0)} levels also adds '
                f'+{gem_text(1)}.'
            ),
            'recovery_salvage': (
                f'Each level saves up to {effects.get("ore_per_level", 0)} '
                'unused Ore after a mission failure for the next run, capped '
                f'at {effects.get("maximum_saved_ore", 0)} Ore.'
            ),
            'discount_specialization': (
                f'Each level reduces all run-shop unit, buff, and power prices '
                f'by {effects.get("ore_per_level", 0)} Ore, minimum price 1 Ore.'
            ),
            'permanent_challenge_slots': (
                f'Each level guarantees +{effects.get("slots_per_level", 0)} '
                'special mission choice. Stages 1-5 grant player support; '
                'stages 6+ become AI challenges with bonus rewards.'
            ),
            'coupon_book': (
                f'First paid shop purchase each stage costs '
                f'{effects.get("ore_per_level", 0)} less Ore per level.'
            ),
            'stock_lock': (
                'Preserve one selected unit, building, or power offer through '
                'the next mission-victory stock rotation.'
            ),
            'veteran_academy': (
                'Units selected in the permanent starting loadout begin '
                'missions as Veterans.'
            ),
            'gem_dividend': (
                f'On run victory, gain 1 Gem per '
                f'{effects.get("ore_per_gem", 0)} remaining Ore, capped at '
                f'{effects.get("maximum_gems_per_level", 0)} Gem per level.'
            ),
            'premium_supplier': (
                f'From stage {effects.get("minimum_stage", 0)}, guarantee '
                'one higher-tier access offer in each stock rotation.'
            ),
        }
        return templates.get(
            upgrade_id,
            ', '.join(
                f'{key.replace("_", " ")}: {value}'
                for key, value in effects.items()
            ),
        )

    def refresh_permanent_purchase_buttons(self, _event=None):
        if not hasattr(self, 'shop_permanent_unit_button'):
            return
        active = bool(
            self.shop_run is not None
            and self.shop_run.status is RunStatus.ACTIVE
        )
        unit_selection = self.shop_permanent_unit_tree.selection()
        upgrade_selection = self.shop_upgrade_tree.selection()
        unit_allowed = bool(
            not active
            and unit_selection
            and self._shop_permanent_buyable.get(unit_selection[0], False)
        )
        upgrade_allowed = bool(
            not active
            and upgrade_selection
            and self._shop_upgrade_buyable.get(upgrade_selection[0], False)
        )
        self.shop_permanent_unit_button.configure(
            state='normal' if unit_allowed else 'disabled'
        )
        owned_unit_selected = bool(
            unit_selection
            and self._shop_permanent_rows.get(unit_selection[0], '')
            in self.shop_profile.permanent_unit_unlocks
        )
        self.shop_permanent_unit_buffs_button.configure(
            state='normal' if owned_unit_selected else 'disabled'
        )
        self.shop_permanent_upgrade_button.configure(
            state='normal' if upgrade_allowed else 'disabled'
        )
        if unit_selection:
            values = self.shop_permanent_unit_tree.item(
                unit_selection[0], 'values'
            )
            reward_id = self._shop_permanent_rows.get(unit_selection[0], '')
            self.shop_permanent_unit_info_var.set(
                f'{values[0]} • {values[1]} • {values[2]} • {values[3]}. '
                'Permanent access can be selected in future starting loadouts.'
            )
            self.shop_permanent_unit_button.configure(
                text=(
                    f'Buy {reward_id} — {values[3]}'
                    if unit_allowed else values[2]
                )
            )
        else:
            self.shop_permanent_unit_info_var.set(
                'Select a unit to see its permanent price and availability.'
            )
            self.shop_permanent_unit_button.configure(text='Select a Unit')
        if upgrade_selection:
            values = self.shop_upgrade_tree.item(
                upgrade_selection[0], 'values'
            )
            upgrade_id = self._shop_upgrade_rows.get(
                upgrade_selection[0], ''
            )
            definition = self.shop_config.permanent_upgrades.get(upgrade_id)
            effect = (
                self._shop_upgrade_effect_text(upgrade_id, definition)
                if definition is not None else ''
            )
            self.shop_permanent_upgrade_info_var.set(
                f'{values[0]} • Level {values[1]} • {values[2]} • '
                f'Next: {values[3]}. {effect}'
            )
            self.shop_permanent_upgrade_button.configure(
                text=(
                    f'Buy Next Level — {values[3]}'
                    if upgrade_allowed else values[2]
                )
            )
        else:
            self.shop_permanent_upgrade_info_var.set(
                'Select an upgrade to see its effect, level, and next price.'
            )
            self.shop_permanent_upgrade_button.configure(
                text='Select an Upgrade'
            )

    def shop_catalogue_tooltip(self, row_id):
        return getattr(self, '_shop_catalogue_details', {}).get(row_id, '')

    def shop_loadout_tooltip(self, row_id):
        return getattr(self, '_shop_loadout_details', {}).get(row_id, '')

    def shop_permanent_tooltip(self, row_id):
        reward_id = self._shop_permanent_rows.get(row_id)
        if not reward_id:
            return ''
        return (
            f'{reward_id}\nPermanent local entitlement. '
            'Selectable in future Shop run loadouts.'
        )

    def shop_upgrade_tooltip(self, row_id):
        upgrade_id = self._shop_upgrade_rows.get(row_id)
        definition = self.shop_config.permanent_upgrades.get(upgrade_id)
        if definition is None:
            return ''
        effects = ', '.join(
            f'{key.replace("_", " ")}: {value}'
            for key, value in definition.effects.items()
        )
        return f'{definition.display_name}\n{effects}'

    def _refresh_shop_history(self):
        tree = self.shop_history_tree
        tree.delete(*tree.get_children())
        if self.shop_run is not None:
            for stage, code in enumerate(
                self.shop_run.completed_missions, start=1
            ):
                mission = self._shop_mission(code)
                tree.insert(
                    '', 'end', values=(stage, mission.get('title') or code)
                )
        self.refresh_shop_summary()

    def refresh_shop_summary(self):
        titles = {
            code: mission.get('title') or code
            for code, mission in self._mission_by_code.items()
        }
        self.shop_summary_var.set('\n'.join(run_summary_lines(
            self.shop_profile, self.shop_run, titles
        )))

    def show_shop_victory_result(self, source, code, previous_run, transition):
        offer = next(
            item for item in previous_run.mission_offers
            if item.mission_code == code
        )
        lines = reward_breakdown_lines(
            offer.economy_class,
            victory_coin_bonus_level=self.shop_profile.upgrade_level(
                'victory_run_coin_bonus'
            ),
            modifiers=previous_run.modifiers,
            mission_modifier=mission_modifier_for_run_offer(
                previous_run,
                offer,
                challenge_slots=self._shop_challenge_slots(),
            ),
            challenge_hunter_level=self.shop_profile.upgrade_level(
                'challenge_hunter'
            ),
        )
        dividend = transition.reward.gem_dividend_meta_coins
        self._set_shop_message(
            f'{source}: {code} victory. ' + ' | '.join(lines)
            + (
                f' | Gem Dividend: +{gem_text(dividend)}'
                if dividend else ''
            )
        )
        if transition.run.status is RunStatus.COMPLETED:
            self.shop_panels.select(self.shop_summary_panel)

    def show_shop_failure_result(self, source, code, transition):
        if transition.revived:
            self._set_shop_message(
                f'{source}: {code} failed. Emergency Revival used; stage '
                f'{transition.run.stage} continues with new mission choices.'
            )
            self.shop_panels.select(0)
            return
        self._set_shop_message(
            f'{source}: {code} failed at stage '
            f'{transition.run.failed_stage}. Shop run ended.'
            + (
                f' Recovery Salvage saved {transition.salvaged_run_coins} Ore '
                'for the next run.'
                if transition.salvaged_run_coins else ''
            ),
            error=True,
        )
        self.shop_panels.select(self.shop_summary_panel)
