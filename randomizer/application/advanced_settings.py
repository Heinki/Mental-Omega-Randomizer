"""Advanced reward-pool controls and setting dependencies."""

from ._dependencies import (
    ALWAYS_AVAILABLE_TECH_IDS,
    BUFF_TARGETS,
    BUFF_TYPES,
    CAMPAIGN_FILTERS,
    FACTION_TILE_COLORS,
    GAME_ROOT,
    REWARD_POOL,
    WidgetTooltip,
    custom_sidebar_preview,
    ensure_superweapon_cameos,
    ensure_unit_cameos,
    filter_missions_by_build_settings,
    linked_buff_variant_ids,
    log_event,
    logging,
    normalize_faction,
    reward_display_name,
    tk,
    tech_ids_for_rewards,
    traceback,
    unit_display_label,
)

class AdvancedSettingsController:

    def on_advanced_tab_configure(self, event):
        wraplength = max(340, int(event.width or 0) - 32)
        if hasattr(self, 'advanced_pool_intro_label'):
            self.advanced_pool_intro_label.configure(wraplength=wraplength)
        if hasattr(self, 'advanced_pool_status_label'):
            self.advanced_pool_status_label.configure(wraplength=wraplength)
        if hasattr(self, 'advanced_buff_unit_label'):
            self.advanced_buff_unit_label.configure(
                wraplength=max(260, wraplength - 160)
            )
        if hasattr(self, 'advanced_power_buff_label'):
            self.advanced_power_buff_label.configure(
                wraplength=max(260, wraplength - 160)
            )

    def advanced_pool_column_count(self, pool_key):
        """Return card columns fitting current Advanced canvas width."""
        counts = getattr(self, 'advanced_pool_column_counts', {})
        if pool_key in counts:
            return max(1, int(counts[pool_key]))
        canvas = getattr(self, 'advanced_pool_canvases', {}).get(pool_key)
        width = canvas.winfo_width() if canvas is not None else 0
        card_span = (
            140 if pool_key in {'unit_buffs', 'power_buffs'} else 112
        )
        return max(1, int(width or card_span * 3) // card_span)

    def on_advanced_pool_canvas_configure(self, pool_key, width):
        """Reflow Advanced cards only when available column count changes."""
        card_span = (
            140 if pool_key in {'unit_buffs', 'power_buffs'} else 112
        )
        columns = max(1, int(width or 0) // card_span)
        counts = getattr(self, 'advanced_pool_column_counts', None)
        if counts is None:
            return
        if counts.get(pool_key) == columns:
            return
        counts[pool_key] = columns
        if not hasattr(self, 'advanced_pool_frames'):
            return
        if self.__dict__.get('_advanced_pool_refresh_after_id') is not None:
            return

        def refresh():
            self._advanced_pool_refresh_after_id = None
            self.refresh_advanced_pool_views()

        self._advanced_pool_refresh_after_id = self.after_idle(refresh)

    def advanced_unit_pool_entries(self):
        """Return combat-unit access targets represented by the reward pool."""
        entries = {}
        for reward in REWARD_POOL:
            if reward.get('kind') in {'buff', 'superweapon'}:
                continue
            factions = tuple(reward.get('factions') or ('Other',))
            for unit_id in tech_ids_for_rewards([reward]):
                linked_ids = linked_buff_variant_ids(unit_id)
                unit_id = next(
                    (
                        candidate
                        for candidate in linked_ids
                        if not BUFF_TARGETS.get(candidate, {}).get('linked_buff_source')
                    ),
                    unit_id,
                )
                target = BUFF_TARGETS.get(unit_id, {})
                if target.get('category') not in {
                    'infantry', 'units', 'aircraft', 'defenses',
                    'special_buildings',
                }:
                    continue
                entries.setdefault(unit_id, {
                    'id': unit_id,
                    'label': unit_display_label(unit_id),
                    'faction': factions[0],
                })
        faction_rank = {'Allies': 0, 'Soviets': 1, 'Epsilon': 2, 'Foehn': 3, 'Other': 4}
        return sorted(
            entries.values(),
            key=lambda entry: (
                faction_rank.get(entry['faction'], 4),
                entry['label'].casefold(),
                entry['id'],
            ),
        )

    def advanced_buff_unit_entries(self):
        """Return units that can receive at least one configured buff reward."""
        entries = {}
        for reward in REWARD_POOL:
            if reward.get('kind') != 'buff' or not reward.get('unit'):
                continue
            unit_id = str(reward['unit']).upper()
            target = BUFF_TARGETS.get(unit_id, {})
            if target.get('category') not in {
                'infantry', 'units', 'aircraft', 'defenses', 'special_buildings',
            }:
                continue
            entry = entries.setdefault(unit_id, {
                'id': unit_id,
                'label': unit_display_label(unit_id),
                'faction': self.unit_faction(unit_id),
                'buff_types': set(),
            })
            entry['buff_types'].add(str(reward.get('buff_type') or ''))
        faction_rank = {'Allies': 0, 'Soviets': 1, 'Epsilon': 2, 'Foehn': 3, 'Other': 4}
        return sorted(
            entries.values(),
            key=lambda entry: (
                faction_rank.get(entry['faction'], 4),
                entry['label'].casefold(),
                entry['id'],
            ),
        )

    def advanced_buff_unit_is_visible(self, entry):
        unit_id = entry['id']
        if (
            not self.include_special_buildings_var.get()
            and BUFF_TARGETS.get(unit_id, {}).get('category') == 'special_buildings'
        ):
            return False
        if unit_id not in ALWAYS_AVAILABLE_TECH_IDS and linked_buff_variant_ids(
            unit_id
        ).intersection(self.excluded_unit_access_ids):
            return False
        selected_campaign = self.campaign_var.get()
        return (
            selected_campaign == CAMPAIGN_FILTERS[0]
            or entry.get('faction') == selected_campaign
        )

    def draw_advanced_buff_unit_card(self, parent, row, column, entry, photo=None):
        unit_id = entry['id']
        selected = unit_id == self.advanced_buff_unit_id
        possible = set(entry['buff_types'])
        excluded = self.excluded_unit_buff_types.get(unit_id, set())
        enabled_count = len(possible - excluded)
        border = '#73d673' if selected else '#4d92d8'
        card = tk.Canvas(
            parent, width=130, height=112, highlightthickness=3 if selected else 2,
            highlightbackground=border, highlightcolor=border,
            background=FACTION_TILE_COLORS.get(entry.get('faction'), '#315b82'),
            cursor='hand2',
        )
        card.grid(row=row, column=column, padx=4, pady=4, sticky='nw')
        if photo is not None:
            card.create_image(65, 35, image=photo, anchor='center')
        else:
            card.create_text(
                65, 35, text=entry.get('faction') or '?', fill='#ffffff',
                font=('Segoe UI', 10, 'bold'), width=122, justify='center',
            )
        card.create_rectangle(0, 72, 130, 112, fill='#151a20', outline='')
        card.create_text(
            65, 87, text=entry['label'], fill='#ffffff',
            font=('Segoe UI', 9, 'bold'), width=122, justify='center',
        )
        card.create_text(
            65, 105, text=f'{enabled_count}/{len(possible)} buffs',
            fill='#73d673' if enabled_count else '#aeb4bb',
            font=('Segoe UI', 8), width=122, justify='center',
        )
        card.bind(
            '<Button-1>',
            lambda _event, item_id=unit_id: self.select_advanced_buff_unit(item_id),
        )
        card.bind(
            '<MouseWheel>',
            lambda event, target=self.advanced_pool_canvases['unit_buffs']: (
                self.on_unlock_mousewheel(event, target)
            ),
        )
        WidgetTooltip(
            card,
            f'{entry["label"]} ({unit_id})\n{enabled_count} of {len(possible)} buff types enabled',
        )

    def refresh_advanced_buff_view(self):
        if 'unit_buffs' not in getattr(self, 'advanced_pool_frames', {}):
            return
        frame = self.advanced_pool_frames['unit_buffs']
        for child in frame.winfo_children():
            child.destroy()
        entries = [
            entry for entry in self.advanced_buff_unit_entries()
            if self.advanced_buff_unit_is_visible(entry)
        ]
        if not entries:
            self.advanced_buff_unit_id = ''
        elif self.advanced_buff_unit_id not in {entry['id'] for entry in entries}:
            self.advanced_buff_unit_id = entries[0]['id']

        cameo_paths = getattr(self, 'advanced_unit_cameo_paths', {}) or {}
        missing_ids = [entry['id'] for entry in entries if entry['id'] not in cameo_paths]
        if missing_ids:
            try:
                cameo_paths.update(ensure_unit_cameos(missing_ids))
            except Exception:
                log_event(
                    'advanced_buff_cameos_failed', level=logging.ERROR,
                    traceback=traceback.format_exc(),
                )
            self.advanced_unit_cameo_paths = cameo_paths
        columns = self.advanced_pool_column_count('unit_buffs')
        for index, entry in enumerate(entries):
            photo = self.advanced_pool_photo(
                f'unit:{entry["id"]}', cameo_paths.get(entry['id'])
            )
            if photo is not None:
                large_key = f'advanced:buff-large:{entry["id"]}'
                large_photo = self.advanced_pool_images.get(large_key)
                if large_photo is None:
                    large_photo = photo.zoom(6, 6).subsample(5, 5)
                    self.advanced_pool_images[large_key] = large_photo
                photo = large_photo
            self.draw_advanced_buff_unit_card(
                frame, index // columns, index % columns, entry, photo
            )
        self.refresh_advanced_buff_controls(entries)

    def refresh_advanced_buff_controls(self, entries=None):
        if not hasattr(self, 'advanced_unit_buff_vars'):
            return
        entries = entries if entries is not None else [
            entry for entry in self.advanced_buff_unit_entries()
            if self.advanced_buff_unit_is_visible(entry)
        ]
        selected = next(
            (entry for entry in entries if entry['id'] == self.advanced_buff_unit_id),
            None,
        )
        possible = set(selected['buff_types']) if selected else set()
        excluded = self.excluded_unit_buff_types.get(
            self.advanced_buff_unit_id, set()
        )
        enabled_count = len(possible - excluded)
        self.advanced_buff_unit_label.configure(
            text=(
                f'{selected["label"]}: {enabled_count}/{len(possible)} default buff types enabled. Values shown per stack.'
                if selected else 'No included buffable units in this campaign.'
            )
        )
        for buff_type in BUFF_TYPES:
            buff_id = buff_type['id']
            self.advanced_unit_buff_vars[buff_id].set(
                buff_id in possible and buff_id not in excluded
            )
            self.advanced_unit_buff_checks[buff_id].configure(
                state='normal' if buff_id in possible else 'disabled'
            )

    def select_advanced_buff_unit(self, unit_id):
        self.advanced_buff_unit_id = str(unit_id).upper()
        self.refresh_advanced_buff_view()

    def on_advanced_unit_buff_changed(self, buff_id):
        unit_id = self.advanced_buff_unit_id
        if not unit_id:
            return
        excluded = self.excluded_unit_buff_types.setdefault(unit_id, set())
        if self.advanced_unit_buff_vars[buff_id].get():
            excluded.discard(buff_id)
        else:
            excluded.add(buff_id)
        if not excluded:
            self.excluded_unit_buff_types.pop(unit_id, None)
        self.save_current_launcher_config()
        self.refresh_advanced_buff_view()

    def set_advanced_unit_buffs(self, include):
        unit_id = self.advanced_buff_unit_id
        if not unit_id:
            return
        entry = next(
            (item for item in self.advanced_buff_unit_entries() if item['id'] == unit_id),
            None,
        )
        if not entry:
            return
        if include:
            self.excluded_unit_buff_types.pop(unit_id, None)
        else:
            self.excluded_unit_buff_types[unit_id] = set(entry['buff_types'])
        self.save_current_launcher_config()
        self.refresh_advanced_buff_view()

    def advanced_power_pool_entries(self):
        entries = {}
        for reward in REWARD_POOL:
            if reward.get('kind') != 'superweapon' or not reward.get('superweapon'):
                continue
            factions = tuple(reward.get('factions') or ('Other',))
            if len(factions) != 1:
                continue
            power_id = str(reward['superweapon']).upper()
            entries.setdefault(power_id, {
                'id': power_id,
                'label': reward_display_name(reward),
                'faction': factions[0],
                'reward': reward,
            })
        faction_rank = {'Allies': 0, 'Soviets': 1, 'Epsilon': 2, 'Foehn': 3, 'Other': 4}
        return sorted(
            entries.values(),
            key=lambda entry: (
                faction_rank.get(entry['faction'], 4),
                entry['label'].casefold(),
            ),
        )

    def advanced_pool_photo(self, key, path):
        if not path:
            return None
        cache_key = f'advanced:{key}'
        if cache_key in self.advanced_pool_images:
            return self.advanced_pool_images[cache_key]
        try:
            photo = tk.PhotoImage(file=str(path))
            if photo.width() <= 70 and photo.height() <= 55:
                photo = photo.zoom(4, 4).subsample(3, 3)
            else:
                factor = max(1, (photo.width() + 87) // 88, (photo.height() + 55) // 56)
                if factor > 1:
                    photo = photo.subsample(factor, factor)
        except (OSError, tk.TclError):
            return None
        self.advanced_pool_images[cache_key] = photo
        return photo

    def draw_advanced_pool_card(self, parent, row, column, entry, pool_key, photo=None):
        excluded_sets = {
            'missions': self.excluded_mission_codes,
            'units': self.excluded_unit_access_ids,
            'powers': self.excluded_superweapon_ids,
        }
        excluded = entry['id'] in excluded_sets[pool_key]
        faction = entry.get('faction', '')
        base_color = FACTION_TILE_COLORS.get(faction, '#315b82')
        border = '#777777' if excluded else '#4d92d8'
        card = tk.Canvas(
            parent,
            width=102,
            height=90,
            highlightthickness=2,
            highlightbackground=border,
            highlightcolor=border,
            background=base_color,
            cursor='hand2',
        )
        card.grid(row=row, column=column, padx=4, pady=4, sticky='nw')
        if photo is not None:
            card.create_image(51, 31, image=photo, anchor='center')
        else:
            card.create_text(
                51, 31, text=faction or '?', fill='#ffffff',
                font=('Segoe UI', 10, 'bold'), width=94, justify='center',
            )
        card.create_rectangle(0, 62, 102, 90, fill='#151a20', outline='')
        card.create_text(
            51, 76,
            text=entry['label'],
            fill='#aeb4bb' if excluded else '#ffffff',
            font=('Segoe UI', 8, 'bold'),
            width=96,
            justify='center',
        )
        if excluded:
            card.create_rectangle(
                0, 0, 102, 90, fill='#777777', outline='', stipple='gray50'
            )
            card.create_text(
                51, 44, text='EXCLUDED', fill='#ffffff',
                font=('Segoe UI', 8, 'bold'),
            )
        card.bind(
            '<Button-1>',
            lambda _event, key=pool_key, item_id=entry['id']: (
                self.toggle_advanced_pool_entry(key, item_id)
            ),
        )
        card.bind(
            '<MouseWheel>',
            lambda event, target=self.advanced_pool_canvases[pool_key]: (
                self.on_unlock_mousewheel(event, target)
            ),
        )
        status = 'Excluded from next seeds' if excluded else 'Included in next seeds'
        WidgetTooltip(card, f'{entry["label"]} ({entry["id"]})\n{status}')

    def refresh_advanced_pool_views(self):
        if not hasattr(self, 'advanced_pool_frames'):
            return
        for frame in self.advanced_pool_frames.values():
            for child in frame.winfo_children():
                child.destroy()

        selected_campaign = self.campaign_var.get()

        def visible_for_campaign(entry):
            return (
                selected_campaign == CAMPAIGN_FILTERS[0]
                or entry.get('faction') == selected_campaign
            )

        mission_frame = self.advanced_pool_frames['missions']
        mission_icons = {}
        for faction in ('Allies', 'Soviets', 'Epsilon', 'Foehn'):
            path = GAME_ROOT / 'Resources' / f'{faction}icon.png'
            mission_icons[faction] = self.advanced_pool_photo(f'mission:{faction}', path)
        campaign_missions = [
            mission for mission in self.missions
            if selected_campaign == CAMPAIGN_FILTERS[0]
            or normalize_faction(mission.get('side', '')) == selected_campaign
        ]
        visible_missions = filter_missions_by_build_settings(
            campaign_missions,
            include_true_no_build=self.include_no_build_missions_var.get(),
            include_no_build_production=(
                self.include_no_build_production_missions_var.get()
            ),
            include_operation_missions=self.include_operation_missions_var.get(),
        )
        mission_columns = self.advanced_pool_column_count('missions')
        for index, mission in enumerate(visible_missions):
            faction = normalize_faction(mission.get('side', ''))
            self.draw_advanced_pool_card(
                mission_frame,
                index // mission_columns,
                index % mission_columns,
                {
                    'id': mission['code'].upper(),
                    'label': mission.get('title') or mission['code'],
                    'faction': faction,
                },
                'missions',
                mission_icons.get(faction),
            )

        all_unit_entries = self.advanced_unit_pool_entries()
        unit_entries = [
            entry for entry in all_unit_entries
            if visible_for_campaign(entry)
            and (
                self.include_special_buildings_var.get()
                or BUFF_TARGETS.get(entry['id'], {}).get('category')
                != 'special_buildings'
            )
        ]
        unit_ids = [entry['id'] for entry in all_unit_entries]
        cameo_paths = getattr(self, 'advanced_unit_cameo_paths', None)
        if cameo_paths is None:
            try:
                cameo_paths = ensure_unit_cameos(unit_ids)
            except Exception:
                cameo_paths = {}
                log_event(
                    'advanced_pool_cameos_failed',
                    level=logging.ERROR,
                    traceback=traceback.format_exc(),
                )
            self.advanced_unit_cameo_paths = cameo_paths
        unit_frame = self.advanced_pool_frames['units']
        unit_columns = self.advanced_pool_column_count('units')
        for index, entry in enumerate(unit_entries):
            photo = self.advanced_pool_photo(
                f'unit:{entry["id"]}', cameo_paths.get(entry['id'])
            )
            self.draw_advanced_pool_card(
                unit_frame,
                index // unit_columns,
                index % unit_columns,
                entry,
                'units',
                photo,
            )

        all_power_entries = self.advanced_power_pool_entries()
        enabled_power_categories = {
            category
            for category, enabled in (
                ('offensive', self.include_superweapon_rewards_var.get()),
                ('secondary', self.include_secondary_superweapon_rewards_var.get()),
                ('aid', self.include_aid_power_rewards_var.get()),
            )
            if enabled
        }
        power_entries = [
            entry for entry in all_power_entries
            if visible_for_campaign(entry)
            and entry['reward'].get('power_category', 'offensive')
            in enabled_power_categories
        ]
        normal_power_ids = [
            entry['reward'].get('cameo_superweapon', entry['id'])
            for entry in power_entries
            if not entry['reward'].get('superweapon_sidebar_image')
        ]
        try:
            power_paths = ensure_superweapon_cameos(normal_power_ids)
        except Exception:
            power_paths = {}
            log_event(
                'advanced_pool_power_cameos_failed',
                level=logging.ERROR,
                traceback=traceback.format_exc(),
            )
        self.advanced_power_cameo_paths = power_paths
        power_frame = self.advanced_pool_frames['powers']
        power_columns = self.advanced_pool_column_count('powers')
        for index, entry in enumerate(power_entries):
            reward = entry['reward']
            asset_name = reward.get('superweapon_sidebar_image')
            if asset_name:
                try:
                    path = custom_sidebar_preview(asset_name)
                except Exception:
                    path = None
            else:
                path = power_paths.get(
                    str(reward.get('cameo_superweapon', entry['id'])).upper()
                )
            photo = self.advanced_pool_photo(f'power:{entry["id"]}', path)
            self.draw_advanced_pool_card(
                power_frame,
                index // power_columns,
                index % power_columns,
                entry,
                'powers',
                photo,
            )

        self.refresh_advanced_buff_view()
        self.refresh_advanced_power_buff_view()

        included_missions = len(visible_missions) - len(
            {mission['code'].upper() for mission in visible_missions}
            & self.excluded_mission_codes
        )
        visible_unit_ids = {entry['id'] for entry in unit_entries}
        included_units = len(visible_unit_ids - self.excluded_unit_access_ids)
        visible_power_ids = {entry['id'] for entry in power_entries}
        included_powers = len(visible_power_ids - self.excluded_superweapon_ids)
        self.advanced_pool_status_label.configure(
            text=(
                f'{selected_campaign}: missions {included_missions}/{len(visible_missions)}, '
                f'units/buildings {included_units}/{len(visible_unit_ids)}, '
                f'superpowers {included_powers}/{len(visible_power_ids)} included'
            )
        )

    def toggle_advanced_pool_entry(self, pool_key, item_id):
        target = {
            'missions': self.excluded_mission_codes,
            'units': self.excluded_unit_access_ids,
            'powers': self.excluded_superweapon_ids,
        }[pool_key]
        item_id = str(item_id).upper()
        if item_id in target:
            target.remove(item_id)
        else:
            target.add(item_id)
        self.save_current_launcher_config()
        self.update_mission_goal_limit()
        self.refresh_advanced_pool_views()

    def set_advanced_pool_all(self, pool_key, include):
        selected_campaign = self.campaign_var.get()
        if pool_key == 'missions':
            mission_entries = [
                {'id': mission['code'].upper(), 'faction': normalize_faction(mission.get('side', ''))}
                for mission in filter_missions_by_build_settings(
                    self.missions,
                    include_true_no_build=self.include_no_build_missions_var.get(),
                    include_no_build_production=(
                        self.include_no_build_production_missions_var.get()
                    ),
                    include_operation_missions=self.include_operation_missions_var.get(),
                )
            ]
            entries = mission_entries
            target = self.excluded_mission_codes
        elif pool_key == 'units':
            entries = [
                entry for entry in self.advanced_unit_pool_entries()
                if self.include_special_buildings_var.get()
                or BUFF_TARGETS.get(entry['id'], {}).get('category')
                != 'special_buildings'
            ]
            target = self.excluded_unit_access_ids
        else:
            enabled_categories = {
                category
                for category, enabled in (
                    ('offensive', self.include_superweapon_rewards_var.get()),
                    ('secondary', self.include_secondary_superweapon_rewards_var.get()),
                    ('aid', self.include_aid_power_rewards_var.get()),
                )
                if enabled
            }
            entries = [
                entry for entry in self.advanced_power_pool_entries()
                if entry['reward'].get('power_category', 'offensive')
                in enabled_categories
            ]
            target = self.excluded_superweapon_ids
        all_ids = {
            entry['id'] for entry in entries
            if selected_campaign == CAMPAIGN_FILTERS[0]
            or entry.get('faction') == selected_campaign
        }
        if include:
            target.difference_update(all_ids)
        else:
            target.update(all_ids)
        self.save_current_launcher_config()
        self.update_mission_goal_limit()
        self.refresh_advanced_pool_views()

    def on_campaign_filter_changed(self, _event=None):
        self.refresh_setting_states()
        self.update_mission_goal_limit()
        self.refresh_advanced_pool_views()

    def on_mission_pool_settings_changed(self):
        self.refresh_setting_states()
        self.update_mission_goal_limit()

    def on_reward_mode_changed(self, _event=None):
        self.refresh_setting_states()

    def on_unlimited_hero_units_changed(self):
        if self.unlimited_hero_units_var.get():
            self.buff_type_vars['build_limit'].set(False)
        self.refresh_setting_states()

    def on_hero_limit_buff_changed(self):
        if self.buff_type_vars['build_limit'].get():
            self.unlimited_hero_units_var.set(False)
        self.refresh_setting_states()

    def on_progression_mode_changed(self, _event=None):
        self.refresh_progression_setting_states()
        if not self.state:
            self.redraw_progression_views()

    def refresh_progression_setting_states(self):
        if not hasattr(self, 'grid_options_frame'):
            return
        if self.progression_mode_var.get() == 'Grid Mode':
            self.grid_options_frame.grid()
        else:
            self.grid_options_frame.grid_remove()

    def refresh_setting_states(self):
        if not hasattr(self, 'randomize_unit_access_check'):
            return
        chaos_mode = self.reward_mode_var.get() == 'Chaos (Experimental)'
        buffs_enabled = bool(self.include_buff_rewards_var.get())
        unlimited_hero_units = bool(self.unlimited_hero_units_var.get())
        special_buildings_enabled = bool(self.include_special_buildings_var.get())
        power_rewards_enabled = any((
            self.include_superweapon_rewards_var.get(),
            self.include_secondary_superweapon_rewards_var.get(),
            self.include_aid_power_rewards_var.get(),
        ))
        if chaos_mode:
            self.randomize_unit_access_var.set(True)
            self.randomize_unit_access_check.configure(state='disabled')
        else:
            self.randomize_unit_access_check.configure(state='normal')
        if chaos_mode or self.campaign_var.get() == 'All Campaigns':
            self.share_chaos_role_buffs_check.grid()
        else:
            self.share_chaos_role_buffs_check.grid_remove()
        self.share_chaos_role_buffs_check.configure(state='normal' if buffs_enabled else 'disabled')
        reward_source_enabled = bool(self.randomize_unit_access_var.get()) or buffs_enabled
        self.buff_allied_helpers_check.configure(
            state='normal' if reward_source_enabled else 'disabled'
        )
        for check in getattr(self, 'buff_type_checks', []):
            check.configure(state='normal' if buffs_enabled else 'disabled')
        build_limit_check = getattr(self, 'buff_type_checks_by_id', {}).get('build_limit')
        if build_limit_check is not None:
            build_limit_check.configure(
                state='normal' if buffs_enabled and not unlimited_hero_units else 'disabled'
            )
        building_limit_check = getattr(
            self, 'buff_type_checks_by_id', {}
        ).get('building_limit')
        if building_limit_check is not None:
            building_limit_check.configure(
                state=(
                    'normal'
                    if buffs_enabled and special_buildings_enabled
                    else 'disabled'
                )
            )
        self.include_defensive_buildings_check.configure(
            state='normal' if reward_source_enabled else 'disabled'
        )
        self.include_special_buildings_check.configure(
            state='normal' if reward_source_enabled else 'disabled'
        )
        self.include_power_buff_rewards_check.configure(
            state='normal' if power_rewards_enabled else 'disabled'
        )
        power_buffs_enabled = bool(
            power_rewards_enabled
            and self.include_power_buff_rewards_var.get()
        )
        for check in getattr(self, 'power_buff_type_checks', []):
            check.configure(
                state='normal' if power_buffs_enabled else 'disabled'
            )
        self.prioritize_no_build_missions_check.configure(
            state=(
                'normal'
                if (
                    self.include_no_build_missions_var.get()
                    or self.include_no_build_production_missions_var.get()
                )
                else 'disabled'
            )
        )
        self.refresh_progression_setting_states()
        self.refresh_advanced_pool_views()

    def update_mission_goal_limit(self):
        if not self.missions:
            return
        filtered_count = len(self.filtered_missions_for_seed())
        self.campaign_label.configure(text=f'Campaign ({filtered_count})')
        self.mission_goal_spinbox.configure(to=max(1, filtered_count))
        if self.mission_goal_var.get() > filtered_count:
            self.mission_goal_var.set(max(1, filtered_count))
