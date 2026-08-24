"""Mission visibility, Grid state, selection, and launch validation."""

from ._dependencies import (
    DEFAULT_PROGRESSION_MODE,
    FACTION_TILE_COLORS,
    GRID_COMPLETED,
    GRID_LOCKED,
    GRID_UNLOCKED,
    canonical_reward,
    check_rewards,
    completing_unlocks,
    is_grid_complete,
    log_event,
    messagebox,
    normalize_faction,
    redraw_launcher_grid,
    refresh_grid_states,
    reward_display_name,
    time,
)

class ProgressionController:

    def mission_matches_search(self, mission):
        query = self.mission_search_var.get().strip().casefold()
        if not query:
            return True
        haystack = ' '.join(str(value) for value in (
            mission.get('code', ''),
            mission.get('title', ''),
            mission.get('side', ''),
            mission.get('operation', ''),
            mission.get('scenario', ''),
        )).casefold()
        return all(term in haystack for term in query.split())

    def mission_search_codes(self):
        if not self.mission_search_var.get().strip():
            return set()
        return {
            mission['code'] for mission in self.missions
            if self.mission_matches_search(mission)
        }

    def on_mission_search_changed(self, *_args):
        if not hasattr(self, 'missions_tree'):
            return
        if self.active_progression_mode() == 'Grid Mode':
            self.refresh_grid_tiles()
            self.after_idle(self.scroll_to_first_grid_search_match)
        else:
            self.redraw_mission_tree()

    def scroll_to_first_grid_search_match(self):
        matches = self.mission_search_codes()
        if not matches or not getattr(self, 'grid_tile_widgets', None):
            return
        grid = self.state.get('grid', {}) if self.state else {}
        code = min(
            (value for value in matches if value in self.grid_tile_widgets),
            key=lambda value: (
                int(grid.get('nodes', {}).get(value, {}).get('y', 0)),
                int(grid.get('nodes', {}).get(value, {}).get('x', 0)),
            ),
            default=None,
        )
        if not code:
            return
        tile = self.grid_tile_widgets[code]['tile']
        self.grid_content_frame.update_idletasks()
        total_width = max(1, self.grid_content_frame.winfo_width())
        total_height = max(1, self.grid_content_frame.winfo_height())
        self.grid_canvas.xview_moveto(max(0.0, tile.winfo_x() / total_width))
        self.grid_canvas.yview_moveto(max(0.0, tile.winfo_y() / total_height))

    def active_progression_mode(self):
        archipelago_mode = getattr(
            self, 'archipelago_progression_mode', lambda: None
        )()
        if archipelago_mode:
            return archipelago_mode
        if self.state:
            return self.state.get('progression_mode', DEFAULT_PROGRESSION_MODE)
        return self.progression_mode_var.get()

    def sync_grid_progression(self):
        if self.active_progression_mode() != 'Grid Mode':
            return {}
        grid = self.state.get('grid') if self.state else None
        if not isinstance(grid, dict):
            return {}
        return refresh_grid_states(
            grid,
            self.state.get('completed_missions', []),
            unlock_all_after_goal=bool(
                self.state.get(
                    'unlock_all_rewards_after_final_grid_mission', False
                )
            ),
        )

    def mission_unlocks(self, code):
        """Return the mission codes that completing ``code`` would open now."""
        if self.active_progression_mode() != 'Grid Mode' or not self.state:
            return []
        self.sync_grid_progression()
        return completing_unlocks(
            self.state.get('grid', {}),
            code,
            unlock_all_after_goal=bool(
                self.state.get(
                    'unlock_all_rewards_after_final_grid_mission', False
                )
            ),
        )

    def redraw_progression_views(self):
        progression_mode = self.active_progression_mode()
        if progression_mode == 'Shop Mode':
            return
        grid_mode = progression_mode == 'Grid Mode'
        if hasattr(self, 'workspace_tabs') and hasattr(self, 'mission_view_frame'):
            if str(self.mission_view_frame) in set(self.workspace_tabs.tabs()):
                self.workspace_tabs.tab(
                    self.mission_view_frame,
                    text='Grid Mode' if grid_mode else 'Mission List',
                )
        if grid_mode:
            self.missions_tree.grid_remove()
            self.tree_scrollbar.grid_remove()
            self.grid_frame.grid()
            self.redraw_grid()
        else:
            self.grid_frame.grid_remove()
            self.missions_tree.grid()
            self.tree_scrollbar.grid()

    def redraw_grid(self):
        started = time.perf_counter()
        previous_signature = self.grid_render_signature
        redraw_launcher_grid(self)
        if self.archipelago_run_active():
            grid = self.state.get('grid', {}) if self.state else {}
            log_event(
                'archipelago_grid_redrawn',
                topology_changed=previous_signature != self.grid_render_signature,
                nodes=len(grid.get('nodes', {})),
                width=grid.get('width'),
                height=grid.get('height'),
                goal=grid.get('goal'),
                elapsed_ms=round(
                    (time.perf_counter() - started) * 1000, 1
                ),
                **self._archipelago_log_context(),
            )

    def refresh_grid_tiles(self, mission_codes=None):
        if not self.grid_tile_widgets or not self.state:
            return
        grid = self.state.get('grid', {})
        states = self.sync_grid_progression()
        lookup = self.mission_lookup()
        selected_code = self.selected_mission_code()
        search_codes = self.mission_search_codes()
        codes = list(mission_codes) if mission_codes is not None else list(self.grid_tile_widgets)
        for code in codes:
            widgets = self.grid_tile_widgets.get(code)
            if not widgets:
                continue
            mission = lookup.get(code, {})
            state = states.get(code, GRID_LOCKED)
            if self.hide_locked_grid_missions_var.get() and state == GRID_LOCKED:
                widgets['tile'].grid()
                background, foreground = '#3f454b', '#d4d8dc'
                for widget in widgets.values():
                    widget.configure(cursor='arrow')
                widgets['tile'].configure(
                    background=background,
                    highlightthickness=(
                        6 if code in search_codes else 3
                    ),
                    highlightbackground=(
                        '#00eaff'
                        if code in search_codes
                        else self.ui_palette()['canvas']
                    ),
                )
                widgets['selection'].configure(background=background)
                widgets['banner'].grid_remove()
                widgets['body'].grid_configure(pady=4)
                widgets['body'].configure(
                    text='?',
                    background=background,
                    foreground=foreground,
                )
                continue
            widgets['tile'].grid()
            for widget in widgets.values():
                widget.configure(cursor='hand2')
            faction = normalize_faction(mission.get('side', ''))
            faction_color = FACTION_TILE_COLORS.get(faction, '#315b82')
            started = self.is_mission_started(code)
            if state == GRID_LOCKED:
                background, foreground = '#3f454b', '#aeb5bc'
                state_label = 'MISSION LOCKED'
                banner_color = '#555c63'
            elif state == GRID_COMPLETED:
                background, foreground = faction_color, '#ffffff'
                state_label = 'MISSION COMPLETED'
                banner_color = '#23864b'
            elif started:
                background, foreground = faction_color, '#ffffff'
                done, total = self.mission_check_counts(code)
                state_label = f'IN PROGRESS  ·  {done}/{total}'
                assistance_stacks = (
                    self.mission_failure_stack(code)
                    if self.failure_assistance_enabled()
                    else 0
                )
                if assistance_stacks:
                    state_label += f'\nASSISTANCE  ·  {assistance_stacks}'
                banner_color = '#b77913'
            else:
                background, foreground = faction_color, '#ffffff'
                state_label = ''
                banner_color = faction_color
            is_goal = code == grid.get('goal')
            hover_highlight = code in getattr(self, 'unlock_hover_grid_codes', set())
            widgets['tile'].configure(
                background='#d6ad37' if is_goal else background,
                highlightthickness=6 if code in search_codes else 3,
                highlightbackground=(
                    '#00eaff'
                    if code in search_codes
                    else '#45ef7a'
                    if hover_highlight
                    else self.ui_palette()['canvas']
                ),
            )
            widgets['selection'].configure(
                background='#86cdf7' if code == selected_code else background,
            )
            if state == GRID_UNLOCKED and not started:
                widgets['banner'].grid_remove()
                widgets['body'].grid_configure(pady=4)
            else:
                widgets['banner'].configure(
                    text=state_label,
                    background=banner_color,
                    foreground='#ffffff' if state != GRID_LOCKED else '#d4d8dc',
                )
                widgets['banner'].grid()
                widgets['body'].grid_configure(pady=(0, 4))
            widgets['body'].configure(
                text=mission.get('title', code),
                background=background,
                foreground=foreground,
            )

    def select_grid_mission(self, index):
        if self.hide_locked_grid_missions_var.get() and self.state:
            try:
                code = self.missions[index]['code']
            except (IndexError, TypeError):
                return
            if self.sync_grid_progression().get(code) == GRID_LOCKED:
                return
        previous_code = self.selected_mission_code()
        self.selected_index.set(index)
        current_code = self.selected_mission_code()
        if self.archipelago_run_active():
            log_event(
                'archipelago_grid_mission_selected',
                previous_mission=previous_code,
                selected_mission=current_code,
                **self._archipelago_log_context(
                    self.mission_lookup().get(current_code, {})
                ),
            )
        self.refresh_grid_tiles({previous_code, current_code})
        self.refresh_progress_view()

    def redraw_mission_tree(self):
        for item in self.missions_tree.get_children():
            self.missions_tree.delete(item)

        order_map = self.randomizer_order_map()
        unlocked = set(self.unlocked_mission_codes())

        for idx, mission in self.visible_missions():
            code = mission['code']
            side = mission.get('side', '')
            title = mission.get('title', code)
            checks_done, checks_total = self.mission_check_counts(code)
            if self.is_mission_complete(code):
                state = 'Done'
            elif not self.state:
                state = 'Vanilla'
            elif code in unlocked:
                state = 'Started' if self.is_mission_started(code) else 'Open'
            else:
                state = 'Locked'
            checks_label = '' if not self.state else f'{checks_done}/{checks_total}'
            order = order_map.get(code, idx + 1)
            tags = []
            if self.is_mission_complete(code):
                tags.append('completed')
            if code in getattr(self, 'unlock_hover_grid_codes', set()):
                tags.append('unlock_available')
            self.missions_tree.insert(
                '',
                'end',
                iid=str(idx),
                values=(f'{order:03}', state, checks_label, side, code, title),
                tags=tuple(tags),
            )

        children = self.missions_tree.get_children()
        selected_iid = str(self.selected_index.get())
        if selected_iid in children:
            self.missions_tree.selection_set(selected_iid)
            self.missions_tree.see(selected_iid)
        elif children:
            self.missions_tree.selection_set(children[0])
            self.selected_index.set(int(children[0]))
        self.redraw_progression_views()

    def sort_missions_by(self, column):
        if column not in self.mission_heading_labels:
            return
        if self.mission_sort_column == column:
            self.mission_sort_reverse = not self.mission_sort_reverse
        else:
            self.mission_sort_column = column
            self.mission_sort_reverse = False

        for heading, label in self.mission_heading_labels.items():
            suffix = ''
            if heading == self.mission_sort_column:
                suffix = ' ↓' if self.mission_sort_reverse else ' ↑'
            self.missions_tree.heading(heading, text=label + suffix)
        self.redraw_mission_tree()

    def on_mission_select(self, _event):
        selection = self.missions_tree.selection()
        if selection:
            self.selected_index.set(int(selection[0]))
            if self.archipelago_run_active():
                mission = self.selected_mission()
                log_event(
                    'archipelago_list_mission_selected',
                    **self._archipelago_log_context(mission),
                )
            self.refresh_progress_view()

    def selected_mission(self):
        if not self.missions:
            return None
        index = self.selected_index.get()
        if index < 0 or index >= len(self.missions):
            return None
        return self.missions[index]

    def selected_mission_code(self):
        mission = self.selected_mission()
        return mission['code'] if mission else None

    def mission_checks(self, code):
        return self.state.get('mission_checks', {}).get(code, [])

    def mission_check_counts(self, code):
        checks = self.mission_checks(code)
        if not checks:
            return (0, 0)
        if self.state.get('rewards_on_victory_only', False):
            done = sum(
                len(check_rewards(check))
                for check in checks
                if check.get('unlocked') or check.get('released')
            )
            total = sum(len(check_rewards(check)) for check in checks)
            return (done, total)
        done = sum(
            len(check_rewards(check))
            for check in checks
            if check.get('unlocked') or check.get('released')
        )
        total = sum(max(1, len(check_rewards(check))) for check in checks)
        return (done, total)

    def is_mission_complete(self, code):
        checks = self.mission_checks(code)
        if checks:
            return any(check.get('id') == 'victory' and check.get('unlocked') for check in checks)
        return code in self.state.get('completed_missions', [])

    def is_mission_started(self, code):
        if not self.state or self.is_mission_complete(code):
            return False
        return (
            code in self.state.get('started_missions', [])
            or any(check.get('unlocked') for check in self.mission_checks(code))
        )

    def is_run_complete(self):
        if not self.state:
            return False
        if self.active_progression_mode() == 'Grid Mode':
            self.sync_grid_progression()
            return is_grid_complete(self.state.get('grid', {}))
        goal = self.state.get('mission_goal', len(self.state.get('mission_order', [])))
        return len(self.state.get('completed_missions', [])) >= goal

    def mission_tooltip_text(self, row_id):
        if not self.state:
            return ''
        try:
            code = self.missions[int(row_id)]['code']
        except (IndexError, ValueError):
            return ''
        missing = [
            check
            for check in self.mission_checks(code)
            if not check.get('unlocked') and not check.get('released')
        ]
        archipelago_active = bool(
            getattr(self, 'archipelago_run_active', lambda: False)()
        )
        found_enemy_traps = []
        found_enemy_bonuses = []
        if archipelago_active:
            for check in self.mission_checks(code):
                if not check.get('unlocked'):
                    continue
                for record in self.archipelago_check_item_details(
                    code, str(check.get('id', ''))
                ) or ():
                    item_name = str(record.get('item_name') or '').strip()
                    reward = canonical_reward({'name': item_name})
                    if not reward.get('enemy_reward'):
                        continue
                    recipient = str(
                        record.get('recipient_player') or ''
                    ).strip() or f'Player {int(record.get("player", 0))}'
                    location = str(
                        record.get('location_name') or ''
                    ).strip() or f'Location #{int(record.get("location", 0))}'
                    found_enemy_traps.append((
                        str(check.get('name') or 'Check'),
                        item_name,
                        recipient,
                        location,
                    ))
        else:
            for check in self.mission_checks(code):
                if not (check.get('unlocked') or check.get('released')):
                    continue
                for reward in self.enemy_rewards_for_check(
                    code, str(check.get('id', ''))
                ):
                    found_enemy_bonuses.append((
                        str(check.get('name') or 'Check'),
                        self.enemy_reward_text(reward),
                    ))
        if not missing and not found_enemy_traps and not found_enemy_bonuses:
            return ''
        reward_summary = self.mission_reward_summary(code)
        lines = []
        if self.act_reward_multipliers_enabled():
            lines.append(
                f'Mission Reward Multiplier: x{reward_summary["multiplier"]}'
            )
        lines.extend((
            f'Base rewards: {reward_summary["base_rewards"]}',
            f'Final rewards: {reward_summary["final_rewards"]}',
        ))
        if missing:
            lines.extend(('', 'Remaining mission checks:'))
        for check in missing:
            if archipelago_active:
                check_id = str(check.get('id', ''))
                expected = (
                    self.archipelago_check_location_count(code, check_id) or 0
                )
                lines.append(
                    f'- {check.get("name", "Check")} ({expected} AP item(s))'
                )
                if self.hide_reward_details_var.get():
                    lines.extend('    - ?????' for _ in range(expected))
                    continue
                details = self.archipelago_check_item_details(
                    code, check_id
                ) or ()
                for record in details:
                    item_name = str(record.get('item_name') or '').strip()
                    if not item_name:
                        item_name = f'Item #{int(record.get("item", 0))}'
                    recipient = str(
                        record.get('recipient_player') or ''
                    ).strip() or f'Player {int(record.get("player", 0))}'
                    recipient_game = str(
                        record.get('recipient_game') or ''
                    ).strip() or 'game unavailable'
                    item_reward = canonical_reward({'name': item_name})
                    prefix = (
                        '[Enemy Trap] '
                        if item_reward.get('enemy_reward') else ''
                    )
                    lines.append(
                        f'    - {prefix}{item_name} -> '
                        f'{recipient} ({recipient_game})'
                    )
                missing_details = max(0, expected - len(details))
                if missing_details:
                    lines.append(
                        f'    - Waiting for {missing_details} server item detail(s)'
                    )
                continue
            rewards = check_rewards(check)
            enemy_rewards = self.enemy_rewards_for_check(
                code, str(check.get('id', ''))
            )
            lines.append(
                f'- {check.get("name", "Check")} '
                f'({len(rewards)} rewards, '
                f'{len(enemy_rewards)} additional enemy bonuses)'
            )
            for reward in rewards:
                reward_name = self.mission_check_reward_name(check, reward)
                lines.append(f'    • {reward_name}')
            for reward in enemy_rewards:
                reward_name = self.mission_check_enemy_reward_name(
                    check, reward
                )
                lines.append(f'    • Enemy bonus: {reward_name}')
        if found_enemy_traps:
            lines.extend(('', 'Enemy Traps found on this mission:'))
            for check_name, item_name, recipient, location in found_enemy_traps:
                lines.append(f'- {check_name}: {item_name} -> {recipient}')
                lines.append(f'    Found at {location}')
        if found_enemy_bonuses:
            lines.extend(('', 'Enemy bonuses acquired on this mission:'))
            for check_name, reward_name in found_enemy_bonuses:
                lines.append(f'- {check_name}: {reward_name}')
        return '\n'.join(lines)

    def mission_check_reward_name(self, check, reward):
        if (
            self.hide_reward_details_var.get()
            and not check.get('unlocked')
            and not check.get('released')
        ):
            return '?????'
        return reward_display_name(reward)

    def mission_check_enemy_reward_name(self, check, reward):
        if (
            self.hide_reward_details_var.get()
            and not check.get('unlocked')
            and not check.get('released')
        ):
            return '?????'
        return self.enemy_reward_text(reward)

    def on_launch_selected(self):
        mission = self.selected_mission()
        if mission is None:
            self.append_log('Cannot launch selected mission: no valid mission selected.', error=True)
            return

        if self.state:
            unlocked = set(self.unlocked_mission_codes())
            if mission['code'] not in unlocked and mission['code'] not in self.state.get('completed_missions', []):
                self.append_log(f'Mission is locked by current seed: {mission["code"]}', error=True)
                messagebox.showwarning('Mission Locked', 'Complete more open missions to unlock this one.')
                return

        self.save_current_launcher_config()
        self.append_log(f'Launching selected mission: {mission["code"]} ({mission["scenario"]})')
        if self.state:
            reward_summary = self.mission_reward_summary(mission['code'])
            multiplier_note = (
                'Mission Reward Multiplier: '
                f'x{reward_summary["multiplier"]}. '
                if self.act_reward_multipliers_enabled()
                else ''
            )
            self.append_log(
                multiplier_note
                +
                f'Base rewards: {reward_summary["base_rewards"]}. '
                f'Final rewards: {reward_summary["final_rewards"]}.'
            )
        log_event(
            'mission_launch_requested',
            seed=self.state.get('seed', ''),
            code=mission.get('code'),
            title=mission.get('title'),
            scenario=mission.get('scenario'),
            side=mission.get('side'),
            difficulty=self.difficulty_var.get(),
            game_speed=self.game_speed_var.get(),
            reward_mode=self.active_reward_mode(),
            completed_missions=len(self.state.get('completed_missions', [])),
            earned_rewards=len(self.state.get('earned_rewards', [])),
            archipelago=(
                self._archipelago_log_context(mission)
                if self.archipelago_run_active()
                else None
            ),
        )
        self.launch_mission_async(mission)
