"""Separate settings window for superweapon and aid-power buff rewards."""

from ._dependencies import (
    CAMPAIGN_FILTERS,
    POWER_BUFF_TYPES,
    REWARD_POOL,
    reward_display_name,
    tk,
    ttk,
)
from randomizer.rewards.power_buff_definitions import power_buff_type_ids


class PowerBuffSettingsController:

    def power_buff_entries(self):
        entries = []
        selected_campaign = self.campaign_var.get()
        enabled_categories = set()
        if self.include_superweapon_rewards_var.get():
            enabled_categories.add('offensive')
        if self.include_secondary_superweapon_rewards_var.get():
            enabled_categories.add('secondary')
        if self.include_aid_power_rewards_var.get():
            enabled_categories.add('aid')
        for reward in REWARD_POOL:
            if (
                reward.get('kind') != 'superweapon'
                or reward.get('power_category', 'offensive')
                not in enabled_categories
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

    def open_power_buff_settings(self):
        window = self.power_buff_window
        if window is not None and window.winfo_exists():
            window.deiconify()
            window.lift()
            window.focus_force()
            return

        window = tk.Toplevel(self)
        self.power_buff_window = window
        window.title('Power Buff Rewards')
        window.geometry('900x620')
        window.minsize(720, 480)
        window.transient(self)
        window.protocol('WM_DELETE_WINDOW', self.close_power_buff_settings)
        window.columnconfigure(0, weight=1)
        window.rowconfigure(2, weight=1)

        intro = ttk.Label(
            window,
            text=(
                'Power buffs affect only earned map-local power clones. '
                'Choose global reward types, then tune valid buffs per power.'
            ),
            wraplength=850,
        )
        intro.grid(row=0, column=0, sticky='ew', padx=12, pady=(12, 6))

        type_frame = ttk.LabelFrame(
            window, text='Power Buff Reward Types', padding=8
        )
        type_frame.grid(row=1, column=0, sticky='ew', padx=12, pady=(0, 8))
        for column in range(3):
            type_frame.columnconfigure(column, weight=1)
        for index, definition in enumerate(POWER_BUFF_TYPES):
            check = ttk.Checkbutton(
                type_frame,
                text=definition['setting_label'],
                variable=self.power_buff_type_vars[definition['id']],
                command=self.on_power_buff_global_type_changed,
            )
            check.grid(
                row=index // 3,
                column=index % 3,
                sticky='w',
                padx=(0, 10),
                pady=2,
            )

        content = ttk.Frame(window)
        content.grid(row=2, column=0, sticky='nsew', padx=12)
        content.columnconfigure(0, weight=2)
        content.columnconfigure(1, weight=3)
        content.rowconfigure(0, weight=1)

        list_frame = ttk.LabelFrame(content, text='Included Powers', padding=6)
        list_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 8))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        tree = ttk.Treeview(
            list_frame,
            columns=('faction', 'category'),
            show='tree headings',
            selectmode='browse',
        )
        tree.heading('#0', text='Power')
        tree.heading('faction', text='Faction')
        tree.heading('category', text='Class')
        tree.column('#0', width=230, stretch=True)
        tree.column('faction', width=75, anchor='center')
        tree.column('category', width=75, anchor='center')
        tree.grid(row=0, column=0, sticky='nsew')
        scrollbar = ttk.Scrollbar(
            list_frame, orient='vertical', command=tree.yview
        )
        scrollbar.grid(row=0, column=1, sticky='ns')
        tree.configure(yscrollcommand=scrollbar.set)
        tree.bind('<<TreeviewSelect>>', self.on_power_buff_power_selected)
        self.power_buff_tree = tree

        detail = ttk.LabelFrame(content, text='Selected Power', padding=10)
        detail.grid(row=0, column=1, sticky='nsew')
        detail.columnconfigure(0, weight=1)
        self.power_buff_selected_label = ttk.Label(
            detail, text='Select a power.', wraplength=430
        )
        self.power_buff_selected_label.grid(
            row=0, column=0, sticky='ew', pady=(0, 8)
        )
        self.power_buff_power_vars = {
            definition['id']: tk.BooleanVar(value=False)
            for definition in POWER_BUFF_TYPES
        }
        self.power_buff_power_checks = {}
        for index, definition in enumerate(POWER_BUFF_TYPES, start=1):
            check = ttk.Checkbutton(
                detail,
                text=(
                    f'{definition["setting_label"]}: '
                    f'{definition["description"]}'
                ),
                variable=self.power_buff_power_vars[definition['id']],
                command=lambda buff_id=definition['id']: (
                    self.on_power_buff_power_type_changed(buff_id)
                ),
            )
            check.grid(row=index, column=0, sticky='w', pady=3)
            self.power_buff_power_checks[definition['id']] = check
        buttons = ttk.Frame(detail)
        buttons.grid(
            row=len(POWER_BUFF_TYPES) + 1,
            column=0,
            sticky='w',
            pady=(10, 0),
        )
        ttk.Button(
            buttons,
            text='Enable valid',
            command=lambda: self.set_selected_power_buffs(True),
        ).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(
            buttons,
            text='Disable all',
            command=lambda: self.set_selected_power_buffs(False),
        ).grid(row=0, column=1)

        footer = ttk.Frame(window)
        footer.grid(row=3, column=0, sticky='ew', padx=12, pady=12)
        footer.columnconfigure(0, weight=1)
        self.power_buff_status_label = ttk.Label(footer, text='')
        self.power_buff_status_label.grid(row=0, column=0, sticky='w')
        ttk.Button(
            footer, text='Close', command=self.close_power_buff_settings
        ).grid(row=0, column=1)
        self.refresh_power_buff_window()

    def close_power_buff_settings(self):
        window = self.power_buff_window
        self.power_buff_window = None
        if window is not None and window.winfo_exists():
            window.destroy()

    def refresh_power_buff_window(self):
        window = self.power_buff_window
        if window is None or not window.winfo_exists():
            return
        entries = self.power_buff_entries()
        self._power_buff_entries_by_id = {
            entry['id']: entry for entry in entries
        }
        tree = self.power_buff_tree
        selected = self.power_buff_power_id
        for item in tree.get_children():
            tree.delete(item)
        for entry in entries:
            tree.insert(
                '',
                'end',
                iid=entry['id'],
                text=entry['label'],
                values=(entry['faction'], entry['category'].title()),
            )
        if selected not in self._power_buff_entries_by_id:
            selected = entries[0]['id'] if entries else ''
        self.power_buff_power_id = selected
        if selected:
            tree.selection_set(selected)
            tree.see(selected)
        self.refresh_selected_power_buff_controls()

    def refresh_selected_power_buff_controls(self):
        entry = getattr(self, '_power_buff_entries_by_id', {}).get(
            self.power_buff_power_id
        )
        possible = set(entry['buff_types']) if entry else set()
        excluded = self.excluded_power_buff_types.get(
            self.power_buff_power_id, set()
        )
        globally_enabled = {
            definition['id']
            for definition in POWER_BUFF_TYPES
            if self.power_buff_type_vars[definition['id']].get()
        }
        for definition in POWER_BUFF_TYPES:
            buff_id = definition['id']
            self.power_buff_power_vars[buff_id].set(
                buff_id in possible and buff_id not in excluded
            )
            self.power_buff_power_checks[buff_id].configure(
                state=(
                    'normal'
                    if buff_id in possible and buff_id in globally_enabled
                    else 'disabled'
                )
            )
        if entry:
            enabled = possible - excluded
            self.power_buff_selected_label.configure(
                text=(
                    f'{entry["label"]} ({entry["faction"]}): '
                    f'{len(enabled)}/{len(possible)} valid buffs enabled.'
                )
            )
        else:
            self.power_buff_selected_label.configure(
                text='No included powers for current campaign/settings.'
            )
        self.power_buff_status_label.configure(
            text=f'{len(getattr(self, "_power_buff_entries_by_id", {}))} powers'
        )

    def on_power_buff_power_selected(self, _event=None):
        selection = self.power_buff_tree.selection()
        if selection:
            self.power_buff_power_id = selection[0]
        self.refresh_selected_power_buff_controls()

    def on_power_buff_global_type_changed(self):
        self.save_current_launcher_config()
        self.refresh_selected_power_buff_controls()

    def on_power_buff_power_type_changed(self, buff_id):
        power_id = self.power_buff_power_id
        if not power_id:
            return
        excluded = self.excluded_power_buff_types.setdefault(power_id, set())
        if self.power_buff_power_vars[buff_id].get():
            excluded.discard(buff_id)
        else:
            excluded.add(buff_id)
        if not excluded:
            self.excluded_power_buff_types.pop(power_id, None)
        self.save_current_launcher_config()
        self.refresh_selected_power_buff_controls()

    def set_selected_power_buffs(self, include):
        entry = getattr(self, '_power_buff_entries_by_id', {}).get(
            self.power_buff_power_id
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
        self.refresh_selected_power_buff_controls()
