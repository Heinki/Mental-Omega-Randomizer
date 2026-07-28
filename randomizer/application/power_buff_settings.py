"""Advanced-tab controls for superweapon and aid-power buff rewards."""

from ._dependencies import (
    CAMPAIGN_FILTERS,
    FACTION_TILE_COLORS,
    POWER_BUFF_TYPES,
    REWARD_POOL,
    WidgetTooltip,
    custom_sidebar_preview,
    ensure_superweapon_cameos,
    log_event,
    logging,
    reward_display_name,
    tk,
    traceback,
)
from randomizer.rewards.power_buff_definitions import power_buff_type_ids


class PowerBuffSettingsController:

    def power_buff_entries(self):
        entries = []
        selected_campaign = self.campaign_var.get()
        enabled_categories = {
            category
            for category, enabled in (
                ('offensive', self.include_superweapon_rewards_var.get()),
                ('secondary', self.include_secondary_superweapon_rewards_var.get()),
                ('aid', self.include_aid_power_rewards_var.get()),
            )
            if enabled
        }
        for reward in REWARD_POOL:
            if (
                reward.get('kind') != 'superweapon'
                or reward.get('power_category', 'offensive')
                not in enabled_categories
                or (
                    not self.include_special_rewards_var.get()
                    and reward.get('special_reward')
                )
            ):
                continue
            power_id = str(reward.get('superweapon') or '').upper()
            factions = list(reward.get('factions') or ())
            faction = factions[0] if len(factions) == 1 else 'Other'
            if (
                not power_id
                or power_id in self.excluded_superweapon_ids
                or (
                    selected_campaign != CAMPAIGN_FILTERS[0]
                    and faction != selected_campaign
                )
            ):
                continue
            entries.append({
                'id': power_id,
                'label': reward_display_name(reward),
                'faction': faction,
                'category': reward.get('power_category', 'offensive'),
                'buff_types': power_buff_type_ids(power_id),
                'reward': reward,
            })
        faction_rank = {
            'Allies': 0, 'Soviets': 1, 'Epsilon': 2, 'Foehn': 3, 'Other': 4,
        }
        return sorted(
            entries,
            key=lambda entry: (
                faction_rank.get(entry['faction'], 4),
                entry['label'].casefold(),
            ),
        )

    def draw_advanced_power_buff_card(
        self,
        parent,
        row,
        column,
        entry,
        photo=None,
    ):
        power_id = entry['id']
        selected = power_id == self.advanced_power_buff_id
        possible = set(entry['buff_types'])
        excluded = self.excluded_power_buff_types.get(power_id, set())
        globally_enabled = {
            definition['id']
            for definition in POWER_BUFF_TYPES
            if self.power_buff_type_vars[definition['id']].get()
        }
        active_count = len(possible.intersection(globally_enabled) - excluded)
        border = '#73d673' if selected else '#4d92d8'
        card = tk.Canvas(
            parent,
            width=130,
            height=112,
            highlightthickness=3 if selected else 2,
            highlightbackground=border,
            highlightcolor=border,
            background=FACTION_TILE_COLORS.get(
                entry.get('faction'), '#315b82'
            ),
            cursor='hand2',
        )
        card.grid(row=row, column=column, padx=4, pady=4, sticky='nw')
        if photo is not None:
            card.create_image(65, 35, image=photo, anchor='center')
        else:
            card.create_text(
                65,
                35,
                text=entry.get('faction') or '?',
                fill='#ffffff',
                font=('Segoe UI', 10, 'bold'),
                width=122,
                justify='center',
            )
        card.create_rectangle(0, 72, 130, 112, fill='#151a20', outline='')
        card.create_text(
            65,
            87,
            text=entry['label'],
            fill='#ffffff',
            font=('Segoe UI', 9, 'bold'),
            width=122,
            justify='center',
        )
        card.create_text(
            65,
            105,
            text=f'{active_count}/{len(possible)} buffs',
            fill='#73d673' if active_count else '#aeb4bb',
            font=('Segoe UI', 8),
            width=122,
            justify='center',
        )
        card.bind(
            '<Button-1>',
            lambda _event, item_id=power_id: (
                self.select_advanced_power_buff(item_id)
            ),
        )
        card.bind(
            '<MouseWheel>',
            lambda event, target=self.advanced_pool_canvases['power_buffs']: (
                self.on_unlock_mousewheel(event, target)
            ),
        )
        WidgetTooltip(
            card,
            (
                f'{entry["label"]} ({power_id})\n'
                f'{active_count} of {len(possible)} valid buff types enabled'
            ),
        )

    def refresh_advanced_power_buff_view(self):
        if 'power_buffs' not in getattr(self, 'advanced_pool_frames', {}):
            return
        frame = self.advanced_pool_frames['power_buffs']
        for child in frame.winfo_children():
            child.destroy()
        entries = self.power_buff_entries()
        entry_ids = {entry['id'] for entry in entries}
        if not entries:
            self.advanced_power_buff_id = ''
        elif self.advanced_power_buff_id not in entry_ids:
            self.advanced_power_buff_id = entries[0]['id']

        normal_power_ids = [
            entry['reward'].get('cameo_superweapon', entry['id'])
            for entry in entries
            if not entry['reward'].get('superweapon_sidebar_image')
        ]
        power_paths = dict(
            getattr(self, 'advanced_power_cameo_paths', {}) or {}
        )
        missing_power_ids = [
            power_id
            for power_id in normal_power_ids
            if str(power_id).upper() not in power_paths
        ]
        if missing_power_ids:
            try:
                power_paths.update(
                    ensure_superweapon_cameos(missing_power_ids)
                )
            except Exception:
                log_event(
                    'advanced_power_buff_cameos_failed',
                    level=logging.ERROR,
                    traceback=traceback.format_exc(),
                )
        self.advanced_power_cameo_paths = power_paths
        columns = self.advanced_pool_column_count('power_buffs')
        for index, entry in enumerate(entries):
            reward = entry['reward']
            asset_name = reward.get('superweapon_sidebar_image')
            if asset_name:
                try:
                    path = custom_sidebar_preview(asset_name)
                except Exception:
                    path = None
            else:
                path = power_paths.get(
                    str(
                        reward.get('cameo_superweapon', entry['id'])
                    ).upper()
                )
            photo = self.advanced_pool_photo(
                f'power-buff:{entry["id"]}', path
            )
            if photo is not None:
                large_key = f'advanced:power-buff-large:{entry["id"]}'
                large_photo = self.advanced_pool_images.get(large_key)
                if large_photo is None:
                    large_photo = photo.zoom(6, 6).subsample(5, 5)
                    self.advanced_pool_images[large_key] = large_photo
                photo = large_photo
            self.draw_advanced_power_buff_card(
                frame,
                index // columns,
                index % columns,
                entry,
                photo,
            )
        self.refresh_advanced_power_buff_controls(entries)

    def refresh_advanced_power_buff_controls(self, entries=None):
        if not hasattr(self, 'advanced_power_buff_vars'):
            return
        entries = entries if entries is not None else self.power_buff_entries()
        selected = next(
            (
                entry
                for entry in entries
                if entry['id'] == self.advanced_power_buff_id
            ),
            None,
        )
        possible = set(selected['buff_types']) if selected else set()
        excluded = self.excluded_power_buff_types.get(
            self.advanced_power_buff_id, set()
        )
        globally_enabled = {
            definition['id']
            for definition in POWER_BUFF_TYPES
            if self.power_buff_type_vars[definition['id']].get()
        }
        active = possible.intersection(globally_enabled) - excluded
        self.advanced_power_buff_label.configure(
            text=(
                f'{selected["label"]}: {len(active)}/{len(possible)} valid buff types enabled.'
                if selected
                else 'No included powers in this campaign/reward pool.'
            )
        )
        for definition in POWER_BUFF_TYPES:
            buff_id = definition['id']
            self.advanced_power_buff_vars[buff_id].set(
                buff_id in possible and buff_id not in excluded
            )
            self.advanced_power_buff_checks[buff_id].configure(
                state=(
                    'normal'
                    if buff_id in possible and buff_id in globally_enabled
                    else 'disabled'
                )
            )

    def select_advanced_power_buff(self, power_id):
        self.advanced_power_buff_id = str(power_id).upper()
        self.refresh_advanced_power_buff_view()

    def on_power_buff_global_type_changed(self):
        self.save_current_launcher_config()
        self.refresh_advanced_power_buff_view()

    def on_power_buff_power_type_changed(self, buff_id):
        power_id = self.advanced_power_buff_id
        if not power_id:
            return
        excluded = self.excluded_power_buff_types.setdefault(power_id, set())
        if self.advanced_power_buff_vars[buff_id].get():
            excluded.discard(buff_id)
        else:
            excluded.add(buff_id)
        if not excluded:
            self.excluded_power_buff_types.pop(power_id, None)
        self.save_current_launcher_config()
        self.refresh_advanced_power_buff_view()

    def set_selected_power_buffs(self, include):
        entry = next(
            (
                item
                for item in self.power_buff_entries()
                if item['id'] == self.advanced_power_buff_id
            ),
            None,
        )
        if not entry:
            return
        if include:
            self.excluded_power_buff_types.pop(entry['id'], None)
        else:
            self.excluded_power_buff_types[entry['id']] = set(
                entry['buff_types']
            )
        self.save_current_launcher_config()
        self.refresh_advanced_power_buff_view()
