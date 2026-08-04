"""Unlock dashboard and progression-view rendering."""

from ._dependencies import (
    GRID_COMPLETED,
    GRID_LOCKED,
    REWARD_MODES,
    WidgetTooltip,
    cameo_extraction_pending,
    check_rewards,
    custom_sidebar_preview,
    ensure_superweapon_cameos,
    ensure_unit_cameos,
    log_event,
    logging,
    re,
    tk,
    traceback,
    ttk,
    unit_display_label,
)

class UnlockViewController:

    def refresh_unlock_dashboard(self):
        if not hasattr(self, 'unlock_icon_frames'):
            return
        entries = self.unlock_dashboard_entries()
        signature = (
            bool(self.dark_mode_var.get()),
            tuple(
                (
                    entry['key'], entry['status'], entry['condition'], entry['privacy'],
                    entry.get('arsenal_mission_label', ''),
                    tuple(source for source, _ in entry['sources']['earned']),
                    tuple(source for source, _ in entry['sources']['available']),
                    tuple(source for source, _ in entry['sources']['available_unlocks']),
                    tuple(entry['sources']['available_codes']),
                )
                for entry in entries
            ),
        )
        if signature == getattr(self, 'unlock_dashboard_signature', None):
            return
        self.unlock_dashboard_signature = signature
        hovered_key = getattr(self, 'unlock_hover_card_key', None)
        hovered_entry = next(
            (entry for entry in entries if entry['key'] == hovered_key),
            None,
        )
        if hovered_entry is not None:
            hovered_codes = (
                hovered_entry['sources'].get('available_codes', ())
                if hovered_entry.get('status') == 'available'
                and not hovered_entry.get('privacy')
                else ()
            )
            self.set_unlock_grid_highlights(hovered_codes)
        elif hovered_key is not None:
            self.unlock_hover_card_key = None
            self.set_unlock_grid_highlights(())

        overlays = {
            'unlocked': (None, '#4f86c6'),
            'available': ('#15a34a', '#40d36d'),
            'locked': ('#6b7280', '#858b95'),
            'unavailable': ('#050505', '#343434'),
        }
        structure_signature = (
            bool(self.dark_mode_var.get()),
            tuple(
                (
                    entry['key'], entry['faction'], entry['category'],
                    entry['label'], entry['kind'], entry['id'],
                    str((entry.get('reward') or {}).get('superweapon_sidebar_image', '')),
                )
                for entry in entries
            ),
        )
        cards = getattr(self, 'unlock_dashboard_cards', {})
        if (
            structure_signature == getattr(self, 'unlock_dashboard_structure_signature', None)
            and set(cards) == {entry['key'] for entry in entries}
        ):
            # Completion changes statuses and tooltips, not catalogue layout.
            # Updating four canvas rectangles is dramatically cheaper than
            # destroying/recreating hundreds of widgets and reloading cameos.
            for entry in entries:
                record = cards[entry['key']]
                card = record['card']
                card.unlock_entry = entry
                record['tooltip'].text = self.unlock_dashboard_tooltip(entry)
                fill, outline = overlays[entry['status']]
                card.itemconfigure(
                    record['overlay'],
                    fill=fill or '',
                    outline=outline,
                    stipple=(
                        'gray75'
                        if entry['status'] == 'unavailable'
                        else 'gray50'
                        if fill else ''
                    ),
                )
            return

        self.unlock_dashboard_structure_signature = structure_signature

        unit_ids = [entry['id'] for entry in entries if entry['kind'] == 'unit']
        power_entries = [entry for entry in entries if entry['kind'] == 'power']
        try:
            unit_paths = ensure_unit_cameos(unit_ids)
        except Exception:
            unit_paths = {}
            log_event('unlock_dashboard_unit_cameos_failed', level=logging.ERROR,
                      traceback=traceback.format_exc())
        normal_power_ids = [
            entry['reward'].get('cameo_superweapon', entry['id'])
            for entry in power_entries
            if not entry['reward'].get('superweapon_sidebar_image')
        ]
        power_sidebar_overrides = {
            str(entry['reward'].get('cameo_superweapon', entry['id'])).upper():
                str(
                    (entry['reward'].get('superweapon_rules') or {}).get(
                        'SidebarPCX', ''
                    )
                )
            for entry in power_entries
            if not entry['reward'].get('superweapon_sidebar_image')
        }
        try:
            power_paths = ensure_superweapon_cameos(
                normal_power_ids, power_sidebar_overrides
            )
        except Exception:
            power_paths = {}
            log_event('unlock_dashboard_power_cameos_failed', level=logging.ERROR,
                      traceback=traceback.format_exc())

        photos = {}
        for entry in entries:
            cache_key = entry['id'] if entry['kind'] == 'unit' else entry['key']
            photo = self.cameo_photo_cache.get(cache_key)
            path = None
            if entry['kind'] == 'unit':
                path = unit_paths.get(entry['id'])
            elif entry['kind'] == 'power':
                asset_name = entry['reward'].get('superweapon_sidebar_image')
                if asset_name:
                    try:
                        path = custom_sidebar_preview(asset_name)
                    except Exception:
                        path = None
                else:
                    cameo_id = entry['reward'].get('cameo_superweapon', entry['id'])
                    path = power_paths.get(str(cameo_id).upper())
            if photo is None and path:
                try:
                    photo = tk.PhotoImage(file=str(path))
                except tk.TclError:
                    photo = None
                if photo is not None:
                    self.cameo_photo_cache[cache_key] = photo
            if photo is not None:
                scale_key = f'dashboard-scale:{cache_key}'
                scaled_photo = self.cameo_photo_cache.get(scale_key)
                if scaled_photo is None:
                    scaled_photo = photo.zoom(4, 4).subsample(3, 3)
                    self.cameo_photo_cache[scale_key] = scaled_photo
                photos[entry['key']] = scaled_photo
        self.unlock_dashboard_images = photos

        field = '#20242b' if self.dark_mode_var.get() else '#ffffff'
        foreground = '#f2f4f8' if self.dark_mode_var.get() else '#202124'
        order = {'Infantry': 0, 'Vehicles / Naval': 1, 'Aircraft': 2,
                 'Defenses': 3, 'Special': 4, 'Special Buildings': 5,
                 'Superweapons': 6, 'Global Buffs': 0,
                 'House-Wide Buffs': 1}
        self.unlock_dashboard_sections = {}
        self.unlock_dashboard_columns = {}
        self.unlock_dashboard_cards = {}
        for faction, content in self.unlock_icon_frames.items():
            canvas = self.unlock_icon_canvases[faction]
            for child in content.winfo_children():
                child.destroy()
            faction_entries = sorted(
                (entry for entry in entries if entry['faction'] == faction),
                key=lambda entry: (order[entry['category']], entry['label'].casefold()),
            )
            row = 0
            layout_sections = []
            for category in sorted(
                {entry['category'] for entry in faction_entries}, key=order.get
            ):
                heading = ttk.Label(
                    content, text=category, font=('Segoe UI', 11, 'bold')
                )
                heading.grid(row=row, column=0, columnspan=4, sticky='w', pady=(8, 4))
                row += 1
                category_entries = [
                    entry for entry in faction_entries if entry['category'] == category
                ]
                cards = []
                for index, entry in enumerate(category_entries):
                    card_row = row + index // 4
                    card_column = index % 4
                    card = tk.Canvas(
                        content, width=82, height=68, borderwidth=0,
                        highlightthickness=0, background=field, cursor='hand2',
                    )
                    card.grid(row=card_row, column=card_column, padx=1, pady=2)
                    cards.append(card)
                    photo = photos.get(entry['key'])
                    if photo is not None:
                        card.create_image(41, 34, image=photo, anchor='center')
                    else:
                        card.create_text(
                            41, 34, text=entry['label'], fill=foreground,
                            width=76, font=('Segoe UI', 9), justify='center',
                        )
                    fill, outline = overlays[entry['status']]
                    if fill:
                        overlay_id = card.create_rectangle(
                            1, 1, 81, 67, fill=fill,
                            stipple='gray50' if entry['status'] != 'unavailable' else 'gray75',
                            outline=outline, width=2,
                        )
                    else:
                        overlay_id = card.create_rectangle(
                            1, 1, 81, 67, outline=outline, width=2
                        )
                    card.unlock_entry = entry
                    card.bind(
                        '<Enter>',
                        lambda _event, target=card: self.on_unlock_card_enter(target),
                        add='+',
                    )
                    card.bind(
                        '<Leave>',
                        lambda _event, target=card: self.on_unlock_card_leave(target),
                        add='+',
                    )
                    card.bind(
                        '<MouseWheel>',
                        lambda event, target=canvas: self.on_unlock_mousewheel(
                            event, target
                        ),
                    )
                    tooltip = WidgetTooltip(card, self.unlock_dashboard_tooltip(entry))
                    self.unlock_dashboard_cards[entry['key']] = {
                        'card': card,
                        'overlay': overlay_id,
                        'tooltip': tooltip,
                    }
                row += (len(category_entries) + 3) // 4
                layout_sections.append((heading, cards))
            self.unlock_dashboard_sections[faction] = layout_sections
            self.layout_unlock_dashboard_faction(faction)
            content.update_idletasks()
            canvas.configure(background=field, scrollregion=canvas.bbox('all'))

        if entries and len(photos) < len(entries) and cameo_extraction_pending():
            self.schedule_cameo_refresh_retry()
        else:
            self.cameo_retry_count = 0

    def refresh_progress_view(self):
        if not self.state:
            self.progress_label.config(text='No randomizer seed generated. Vanilla mission launching is still available.')
            self.set_rewards_text('')
            self.set_unlocks_text('No randomizer seed generated yet.')
            return

        completed = len(self.state.get('completed_missions', []))
        order = self.state.get('mission_order', [])
        unlocked = len([
            code for code in self.unlocked_mission_codes()
            if code not in self.state.get('completed_missions', [])
        ])
        earned = self.state.get('earned_rewards', [])
        goal = self.state.get('mission_goal', len(order))
        progression_mode = self.active_progression_mode()
        run_complete = self.is_run_complete()
        status = (
            'Victory achieved'
            if progression_mode == 'Grid Mode' and run_complete
            else 'Finished'
            if run_complete
            else 'In progress'
        )
        self.progress_label.config(
            text=(
                f'Seed: {self.state.get("seed", "")} | {progression_mode} | '
                f'Rewards: {self.state.get("reward_mode", REWARD_MODES[0])}\n'
                f'Completed: {completed}/{goal} | Open: {unlocked} | Rewards: {len(earned)} | {status}'
            )
        )

        lines = []
        selected = self.selected_mission()
        if selected:
            code = selected['code']
            done_checks, total_checks = self.mission_check_counts(code)
            lines.append(selected['title'])
            lines.append(f'Code: {code}  •  Faction: {selected.get("side", "Unknown")}')
            if progression_mode == 'Grid Mode':
                node = self.state.get('grid', {}).get('nodes', {}).get(code, {})
                node_state = node.get('state', GRID_LOCKED).title()
                if self.is_mission_started(code):
                    node_state = 'In Progress'
                lines.append(
                    f'Grid: column {int(node.get("x", 0)) + 1}, row {int(node.get("y", 0)) + 1}  '
                    f'•  {node_state}'
                )
                unlocks = self.mission_unlocks(code)
                if code == self.state.get('grid', {}).get('goal') and node.get('state') != GRID_COMPLETED:
                    lines.append(
                        'Completing this endgoal records Randomizer victory, releases every '
                        'pending reward, and unlocks every unfinished grid mission.'
                    )
                elif unlocks:
                    if self.hide_locked_grid_missions_var.get():
                        lines.append(
                            f'Completing this node reveals {len(unlocks)} neighboring mission(s).'
                        )
                    else:
                        lookup = self.mission_lookup()
                        labels = [lookup.get(item, {}).get('title', item) for item in unlocks]
                        lines.append('Completing this node unlocks: ' + ', '.join(labels))
                elif node.get('state') == GRID_COMPLETED:
                    lines.append('This node is complete; its neighbors are already open.')
                else:
                    lines.append('Completing this node does not unlock a currently locked neighbor.')
            lines.append(f'Reward progress: {done_checks}/{total_checks}')
            reward_summary = self.mission_reward_summary(code)
            lines.append(
                'Mission Reward Multiplier: '
                f'x{reward_summary["multiplier"]}'
            )
            lines.append(
                f'Base rewards: {reward_summary["base_rewards"]}'
            )
            final_reward_text = (
                f'Final rewards: {reward_summary["final_rewards"]}'
            )
            if reward_summary['max_rewards_achieved']:
                final_reward_text += '  •  Max rewards achieved'
            lines.append(final_reward_text)
            if self.failure_assistance_enabled():
                assistance_stacks = self.mission_failure_stack(code)
                if assistance_stacks:
                    lines.append(
                        f'Retry assistance: {assistance_stacks} stack(s), for this mission only'
                    )
                    lines.append(
                        'Current retry buffs: '
                        + self.mission_assistance_effect_text(assistance_stacks)
                        + '.'
                    )
                    lines.append('Completing the mission removes all of its retry assistance stacks.')
                else:
                    lines.append('Retry assistance: 0 stacks for this mission')
            lines.append('')
            for check in self.mission_checks(code):
                status_label = (
                    'Complete'
                    if check.get('unlocked')
                    else 'Reward Released'
                    if check.get('released')
                    else 'Pending'
                )
                rewards = check_rewards(check)
                lines.append(
                    f'{status_label}: {check.get("name", "Check")} — {len(rewards)} reward(s)'
                )
                bonus_count = max(
                    0,
                    int(check.get('multiplier_bonus_count', 0)),
                )
                if bonus_count:
                    lines.append(
                        f'   Mission completion multiplier bonus: +{bonus_count} reward(s)'
                    )
                hint = check.get('hint')
                if hint:
                    lines.append(f'   {hint}')
                if rewards:
                    for reward in rewards:
                        reward_name = self.mission_check_reward_name(check, reward)
                        lines.append(f'   • {reward_name}')
                else:
                    lines.append('   • No reward assigned')
            lines.append('')
            lines.append('Earned reward details are grouped in the Unlocks tab.')
        elif not lines:
            lines.append('No rewards earned yet.')

        self.set_rewards_text('\n'.join(lines))
        self.set_unlocks_text(self.current_unlocks_text(), self.current_unlock_unit_ids())

    def set_rewards_text(self, text):
        self.rewards_text.configure(state='normal')
        self.rewards_text.delete('1.0', 'end')
        self.rewards_text.insert('end', text)
        self.rewards_text.configure(state='disabled')

    def set_unlocks_text(self, text, unit_ids=None):
        self.unlocks_text.configure(state='normal')
        self.unlocks_text.delete('1.0', 'end')
        self.unlocks_text.insert('end', text)
        self.unlock_cameo_images = {}
        if unit_ids:
            try:
                cameo_paths = ensure_unit_cameos(unit_ids)
            except Exception:
                cameo_paths = {}
                log_event('cameo_load_failed', level=logging.ERROR, traceback=traceback.format_exc())
            log_event(
                'cameos_resolved',
                requested=len(unit_ids),
                resolved=len(cameo_paths),
                missing=sorted(set(unit_ids) - set(cameo_paths)),
            )
            photos = {}
            for unit_id in unit_ids:
                cameo_path = cameo_paths.get(unit_id)
                if not cameo_path:
                    continue
                photo = self.cameo_photo_cache.get(unit_id)
                if photo is None:
                    try:
                        photo = tk.PhotoImage(file=str(cameo_path))
                    except tk.TclError:
                        continue
                    self.cameo_photo_cache[unit_id] = photo
                photos[unit_id] = photo
                self.unlock_cameo_images[unit_id] = photo

            shared_rows = re.findall(r'\[\[MOR_SHARED:([A-Z0-9_,]+)\]\]', text)
            for shared_ids in shared_rows:
                token = f'[[MOR_SHARED:{shared_ids}]]'
                position = self.unlocks_text.search(token, '1.0', stopindex='end', exact=True)
                if not position:
                    continue
                self.unlocks_text.delete(position, f'{position}+{len(token)}c')
                row_units = [unit_id for unit_id in shared_ids.split(',') if unit_id]
                has_content = False
                for unit_id in reversed(row_units):
                    if has_content:
                        self.unlocks_text.insert(position, '   ')
                    photo = photos.get(unit_id)
                    if photo is not None:
                        self.unlocks_text.image_create(
                            position,
                            image=photo,
                            align='center',
                            padx=3,
                            pady=2,
                        )
                    else:
                        self.unlocks_text.insert(position, '[no cameo]')
                    has_content = True

            for unit_id in unit_ids:
                photo = photos.get(unit_id)
                if photo is None:
                    continue
                label = unit_display_label(unit_id)
                position = self.unlocks_text.search(label, '1.0', stopindex='end', exact=True)
                while position:
                    line_text = self.unlocks_text.get(f'{position} linestart', f'{position} lineend')
                    if line_text == label:
                        break
                    position = self.unlocks_text.search(
                        label,
                        f'{position}+{len(label)}c',
                        stopindex='end',
                        exact=True,
                    )
                if not position:
                    continue
                self.unlocks_text.image_create(
                    position,
                    image=photo,
                    align='center',
                    padx=5,
                    pady=2,
                )

        power_ids = sorted(set(re.findall(r'\[\[MOR_POWER:([A-Za-z0-9_]+)\]\]', text)))
        if power_ids:
            try:
                power_cameo_paths = ensure_superweapon_cameos(power_ids)
            except Exception:
                power_cameo_paths = {}
                log_event(
                    'superweapon_cameo_load_failed',
                    level=logging.ERROR,
                    traceback=traceback.format_exc(),
                )
            normalized_power_ids = {power_id.upper() for power_id in power_ids}
            log_event(
                'superweapon_cameos_resolved',
                requested=len(normalized_power_ids),
                resolved=len(power_cameo_paths),
                missing=sorted(normalized_power_ids - set(power_cameo_paths)),
            )
            for power_id in power_ids:
                token = f'[[MOR_POWER:{power_id}]]'
                position = self.unlocks_text.search(token, '1.0', stopindex='end', exact=True)
                while position:
                    self.unlocks_text.delete(position, f'{position}+{len(token)}c')
                    cache_key = f'power:{power_id.upper()}'
                    photo = self.cameo_photo_cache.get(cache_key)
                    cameo_path = power_cameo_paths.get(power_id.upper())
                    if photo is None and cameo_path:
                        try:
                            photo = tk.PhotoImage(file=str(cameo_path))
                        except tk.TclError:
                            photo = None
                        if photo is not None:
                            self.cameo_photo_cache[cache_key] = photo
                    if photo is not None:
                        self.unlocks_text.image_create(
                            position,
                            image=photo,
                            align='center',
                            padx=5,
                            pady=2,
                        )
                        self.unlock_cameo_images[cache_key] = photo
                    position = self.unlocks_text.search(
                        token,
                        position,
                        stopindex='end',
                        exact=True,
                    )
        asset_names = sorted(set(re.findall(
            r'\[\[MOR_ASSET:([A-Za-z0-9_.-]+\.png)\]\]',
            text,
            flags=re.IGNORECASE,
        )))
        for asset_name in asset_names:
            token = f'[[MOR_ASSET:{asset_name}]]'
            try:
                preview_path = custom_sidebar_preview(asset_name)
            except Exception:
                preview_path = None
                log_event(
                    'custom_sidebar_preview_failed',
                    level=logging.ERROR,
                    asset=asset_name,
                    traceback=traceback.format_exc(),
                )
            position = self.unlocks_text.search(token, '1.0', stopindex='end', exact=True)
            while position:
                self.unlocks_text.delete(position, f'{position}+{len(token)}c')
                cache_key = f'asset:{asset_name.lower()}'
                photo = self.cameo_photo_cache.get(cache_key)
                if photo is None and preview_path:
                    try:
                        photo = tk.PhotoImage(file=str(preview_path))
                    except tk.TclError:
                        photo = None
                    if photo is not None:
                        self.cameo_photo_cache[cache_key] = photo
                if photo is not None:
                    self.unlocks_text.image_create(
                        position,
                        image=photo,
                        align='center',
                        padx=5,
                        pady=2,
                    )
                    self.unlock_cameo_images[cache_key] = photo
                position = self.unlocks_text.search(
                    token,
                    position,
                    stopindex='end',
                    exact=True,
                )
        self.unlocks_text.configure(state='disabled')
        self.refresh_unlock_search()
        self.refresh_unlock_dashboard()
