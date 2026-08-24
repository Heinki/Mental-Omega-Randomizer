"""Shop Mode workspace widgets."""

from ._builder_dependencies import TreeTooltip, WidgetTooltip, tk, ttk


def _tree(
    parent, columns, headings, *, selectmode='browse', height=12, cameos=False
):
    tree = ttk.Treeview(
        parent,
        columns=columns,
        show='tree headings' if cameos else 'headings',
        style='ShopCameo.Treeview' if cameos else 'Treeview',
        selectmode=selectmode,
        height=height,
    )
    if cameos:
        tree.heading('#0', text='Cameo')
        tree.column('#0', width=90, minwidth=90, stretch=False, anchor='center')
    for column, heading, width in headings:
        tree.heading(column, text=heading)
        tree.column(column, width=width, minwidth=50, stretch=True)
    scrollbar = ttk.Scrollbar(parent, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    tree._shop_vertical_scrollbar = scrollbar
    tree.grid(row=0, column=0, sticky='nsew')
    scrollbar.grid(row=0, column=1, sticky='ns')
    parent.columnconfigure(0, weight=1)
    parent.rowconfigure(0, weight=1)
    return tree


def build_shop_tab(self, workspace_tabs):
    tab = ttk.Frame(workspace_tabs, padding=8)
    self.shop_tab = tab
    tab.columnconfigure(0, weight=1)
    tab.rowconfigure(3, weight=1)

    header = ttk.Frame(tab)
    header.grid(row=0, column=0, sticky='ew', pady=(0, 8))
    for column in range(5):
        header.columnconfigure(column, weight=1)
    header_items = (
        (self.shop_stage_var, 'Shop.Stage.TLabel'),
        (self.shop_status_var, 'Shop.Status.TLabel'),
        (self.shop_run_coins_var, 'Shop.Ore.TLabel'),
        (self.shop_meta_coins_var, 'Shop.Mental.TLabel'),
        (self.shop_rerolls_var, 'Shop.Reroll.TLabel'),
    )
    self.shop_header_labels = []
    for column, (variable, label_style) in enumerate(header_items):
        label = ttk.Label(
            header,
            textvariable=variable,
            font=('Segoe UI', 10, 'bold'),
            style=label_style,
        )
        label.grid(row=0, column=column, sticky='w', padx=(0, 10))
        self.shop_header_labels.append(label)
    self.shop_status_label = self.shop_header_labels[1]

    choices = ttk.LabelFrame(tab, text='Mission Choices', padding=8)
    choices.grid(row=1, column=0, sticky='ew')
    for column in range(3):
        choices.columnconfigure(column, weight=1, uniform='shop_missions')
    self.shop_mission_cards = []
    for index in range(3):
        card = ttk.LabelFrame(choices, text=f'Choice {index + 1}', padding=8)
        card.grid(row=0, column=index, sticky='nsew', padx=(0 if index == 0 else 4, 0))
        name_var = tk.StringVar(value='No mission')
        detail_var = tk.StringVar(value='')
        reward_var = tk.StringVar(value='')
        effect_var = tk.StringVar(value='')
        ttk.Label(card, textvariable=name_var, font=('Segoe UI', 10, 'bold')).grid(
            row=0, column=0, sticky='w'
        )
        ttk.Label(card, textvariable=detail_var, style='Muted.TLabel').grid(
            row=1, column=0, sticky='w', pady=(3, 0)
        )
        ttk.Label(card, textvariable=reward_var, style='Shop.Reward.TLabel').grid(
            row=2, column=0, sticky='w', pady=(3, 7)
        )
        effect_label = ttk.Label(
            card,
            textvariable=effect_var,
            style='Shop.Help.TLabel',
            wraplength=330,
            justify='left',
        )
        effect_label.grid(row=3, column=0, sticky='ew', pady=(0, 7))
        launch_button = ttk.Button(
            card,
            text='Launch This Mission',
            command=lambda selected=index: self.launch_shop_mission(selected),
            state='disabled',
            style='Launch.TButton',
        )
        launch_button.grid(row=4, column=0, sticky='ew')
        mission_actions = ttk.Frame(card)
        mission_actions.grid(row=5, column=0, sticky='ew', pady=(5, 0))
        mission_actions.columnconfigure(0, weight=1)
        mission_actions.columnconfigure(1, weight=1)
        reroll_button = ttk.Button(
            mission_actions,
            text='Reroll This Mission',
            command=lambda selected=index: self.reroll_shop_mission(selected),
            state='disabled',
        )
        reroll_button.grid(row=0, column=0, sticky='ew', padx=(0, 3))
        ease_button = ttk.Button(
            mission_actions,
            text='Ease Difficulty',
            command=lambda selected=index: self.ease_shop_mission(selected),
            state='disabled',
        )
        ease_button.grid(row=0, column=1, sticky='ew', padx=(3, 0))
        card.columnconfigure(0, weight=1)
        tooltip = WidgetTooltip(card, '')
        self.shop_mission_cards.append({
            'frame': card,
            'name': name_var,
            'detail': detail_var,
            'reward': reward_var,
            'effect': effect_var,
            'effect_label': effect_label,
            'launch_button': launch_button,
            'reroll_button': reroll_button,
            'ease_button': ease_button,
            'tooltip': tooltip,
            'code': '',
        })

    actions = ttk.Frame(tab)
    actions.grid(row=2, column=0, sticky='ew', pady=8)
    self.shop_give_up_button = ttk.Button(
        actions,
        text='Give Up Run',
        state='disabled',
        style='Danger.TButton',
        command=self.give_up_shop_run,
    )
    self.shop_give_up_button.pack(side='left')
    ttk.Label(actions, textvariable=self.shop_message_var).pack(
        side='left', padx=(12, 0)
    )

    panels = ttk.Notebook(tab, style='Unlocks.TNotebook')
    self.shop_panels = panels
    panels.grid(row=3, column=0, sticky='nsew')

    run_shop = ttk.Frame(panels, padding=8)
    panels.add(run_shop, text='Run Shop')
    run_shop.columnconfigure(0, weight=1)
    run_shop.rowconfigure(2, weight=1)
    filters = ttk.Frame(run_shop)
    filters.grid(row=0, column=0, sticky='ew', pady=(0, 6))
    ttk.Label(filters, text='Category:').pack(side='left')
    category = ttk.Combobox(
        filters,
        textvariable=self.shop_category_var,
        values=('Units', 'Unit Buffs', 'Powers', 'Power Buffs'),
        state='readonly',
        width=14,
    )
    category.pack(side='left', padx=(5, 10))
    category.bind('<<ComboboxSelected>>', self.refresh_shop_catalogue)
    self.shop_buff_target_frame = ttk.Frame(filters)
    ttk.Label(
        self.shop_buff_target_frame, text='Upgrade unit:'
    ).pack(side='left')
    self.shop_buff_target_combo = ttk.Combobox(
        self.shop_buff_target_frame,
        textvariable=self.shop_buff_target_var,
        state='readonly',
        width=25,
    )
    self.shop_buff_target_combo.pack(side='left', padx=(5, 10))
    self.shop_buff_target_combo.bind(
        '<<ComboboxSelected>>', self.refresh_shop_catalogue
    )
    self.shop_search_label = ttk.Label(filters, text='Search:')
    self.shop_search_label.pack(side='left')
    ttk.Entry(filters, textvariable=self.shop_search_var).pack(
        side='left', fill='x', expand=True, padx=(5, 0)
    )
    ttk.Label(filters, text='Sort:').pack(side='left', padx=(10, 0))
    sort_box = ttk.Combobox(
        filters,
        textvariable=self.shop_sort_var,
        values=('Name', 'Tier', 'Price', 'Status'),
        state='readonly',
        width=9,
    )
    sort_box.pack(side='left', padx=(5, 0))
    sort_box.bind('<<ComboboxSelected>>', self.refresh_shop_catalogue)
    self.shop_show_locked_button = ttk.Checkbutton(
        filters,
        text='Show unavailable',
        variable=self.shop_show_locked_var,
        command=self.refresh_shop_catalogue,
    )
    self.shop_show_locked_button.pack(side='left', padx=(10, 0))
    self.shop_catalogue_help_var = tk.StringVar(value='')
    ttk.Label(
        run_shop,
        textvariable=self.shop_catalogue_help_var,
        style='Shop.Help.TLabel',
        wraplength=850,
    ).grid(row=1, column=0, sticky='w', pady=(0, 6))
    run_tree_frame = ttk.Frame(run_shop)
    run_tree_frame.grid(row=2, column=0, sticky='nsew')
    self.shop_catalogue_tree = _tree(
        run_tree_frame,
        ('name', 'tier', 'state', 'price', 'upgrades'),
        (
            ('name', 'Reward', 270),
            ('tier', 'Tier', 75),
            ('state', 'State', 155),
            ('price', 'Price', 85),
            ('upgrades', 'Upgrades', 145),
        ),
        cameos=True,
    )
    self.shop_catalogue_tree.column('upgrades', anchor='center')
    self.shop_catalogue_tree.bind(
        '<Double-1>', self.activate_selected_shop_reward
    )
    self.configure_shop_embedded_button_tree(
        self.shop_catalogue_tree, '_shop_catalogue_upgrade_buttons'
    )
    self.shop_catalogue_tree.bind(
        '<<TreeviewSelect>>', self.refresh_shop_purchase_buttons
    )
    self.shop_catalogue_tooltip_view = TreeTooltip(
        self.shop_catalogue_tree, self.shop_catalogue_tooltip
    )
    shop_action_row = ttk.Frame(run_shop)
    shop_action_row.grid(row=3, column=0, sticky='e', pady=(7, 0))
    self.shop_upgrade_selected_button = ttk.Button(
        shop_action_row,
        text='Upgrade Selected Unit',
        command=self.view_selected_shop_buffs,
        state='disabled',
        style='Launch.TButton',
    )
    self.shop_upgrade_selected_button.pack(side='left')
    self.shop_purchase_button = ttk.Button(
        shop_action_row,
        text='Purchase Selected',
        command=self.buy_selected_shop_reward,
        state='disabled',
    )
    self.shop_purchase_button.pack(side='left', padx=(8, 0))

    loadout = ttk.Frame(panels, padding=8)
    panels.add(loadout, text='Current Loadout')
    loadout.rowconfigure(1, weight=1)
    loadout.columnconfigure(0, weight=1)
    loadout_help = ttk.Frame(loadout)
    loadout_help.grid(row=0, column=0, sticky='ew', pady=(0, 6))
    loadout_help.columnconfigure(0, weight=1)
    ttk.Label(
        loadout_help,
        text=(
            'Every owned unit can be upgraded. Use its Open Upgrades button.'
        ),
        style='Shop.Help.TLabel',
    ).grid(row=0, column=0, sticky='w')
    self.shop_loadout_upgrade_button = ttk.Button(
        loadout_help,
        text='Browse Owned Unit Upgrades',
        command=self.browse_owned_unit_upgrades,
        style='Launch.TButton',
        state='disabled',
    )
    self.shop_loadout_upgrade_button.grid(row=0, column=1, sticky='e')
    loadout_search = ttk.Frame(loadout_help)
    loadout_search.grid(
        row=1, column=0, columnspan=2, sticky='ew', pady=(6, 0)
    )
    ttk.Label(loadout_search, text='Search:').pack(side='left')
    ttk.Entry(
        loadout_search, textvariable=self.shop_loadout_search_var
    ).pack(side='left', fill='x', expand=True, padx=(6, 0))
    loadout_tree_frame = ttk.Frame(loadout)
    loadout_tree_frame.grid(row=1, column=0, sticky='nsew')
    self.shop_loadout_tree = _tree(
        loadout_tree_frame,
        ('source', 'item', 'buffs', 'upgrades'),
        (
            ('source', 'Source', 170),
            ('item', 'Active Item', 380),
            ('buffs', 'Attached Buffs', 150),
            ('upgrades', 'Upgrades', 150),
        ),
        cameos=True,
    )
    self.shop_loadout_tree.column('upgrades', anchor='center')
    self.configure_shop_embedded_button_tree(
        self.shop_loadout_tree, '_shop_loadout_upgrade_buttons'
    )
    self.shop_loadout_tooltip_view = TreeTooltip(
        self.shop_loadout_tree, self.shop_loadout_tooltip
    )
    self.shop_loadout_tree.bind(
        '<Double-1>', self.view_selected_loadout_buffs
    )

    permanent = ttk.Frame(panels, padding=8)
    panels.add(permanent, text='Permanent Unlocks')
    permanent.columnconfigure(0, weight=1)
    permanent.rowconfigure(1, weight=1)
    permanent_search = ttk.Frame(permanent)
    permanent_search.grid(row=0, column=0, sticky='ew', pady=(0, 6))
    permanent_search.columnconfigure(1, weight=1)
    ttk.Label(permanent_search, text='Search units, buffs, upgrades:').grid(
        row=0, column=0, sticky='w', padx=(0, 6)
    )
    ttk.Entry(
        permanent_search, textvariable=self.shop_permanent_search_var
    ).grid(row=0, column=1, sticky='ew')
    permanent_tabs = ttk.Notebook(permanent, style='Unlocks.TNotebook')
    permanent_tabs.grid(row=1, column=0, sticky='nsew')

    permanent_units = ttk.Frame(permanent_tabs, padding=8)
    permanent_tabs.add(permanent_units, text='Units')
    permanent_units.columnconfigure(0, weight=1)
    permanent_units.rowconfigure(0, weight=1)
    unit_frame = ttk.Frame(permanent_units)
    unit_frame.grid(row=0, column=0, sticky='nsew')
    self.shop_permanent_unit_tree = _tree(
        unit_frame,
        ('name', 'tier', 'state', 'price'),
        (
            ('name', 'Unit', 300), ('tier', 'Tier', 80),
            ('state', 'State', 160), ('price', 'Price', 90),
        ),
        height=10,
        cameos=True,
    )
    self.shop_permanent_unit_tree.bind(
        '<<TreeviewSelect>>', self.refresh_permanent_purchase_buttons
    )
    self.shop_permanent_tooltip_view = TreeTooltip(
        self.shop_permanent_unit_tree, self.shop_permanent_tooltip
    )
    self.shop_permanent_unit_info_var = tk.StringVar(
        value='Select a unit to see its permanent price and availability.'
    )
    ttk.Label(
        permanent_units,
        textvariable=self.shop_permanent_unit_info_var,
        wraplength=820,
        justify='left',
    ).grid(row=1, column=0, sticky='w', pady=(7, 4))
    self.shop_permanent_unit_button = ttk.Button(
        permanent_units,
        text='Select a Unit',
        command=self.buy_selected_permanent_unit,
        state='disabled',
    )
    self.shop_permanent_unit_button.grid(row=2, column=0, sticky='e')

    permanent_upgrades = ttk.Frame(permanent_tabs, padding=8)
    permanent_tabs.add(permanent_upgrades, text='Upgrades')
    permanent_upgrades.columnconfigure(0, weight=1)
    permanent_upgrades.rowconfigure(0, weight=1)
    upgrade_frame = ttk.Frame(permanent_upgrades)
    upgrade_frame.grid(row=0, column=0, sticky='nsew')
    self.shop_upgrade_tree = _tree(
        upgrade_frame,
        ('name', 'level', 'state', 'price'),
        (
            ('name', 'Upgrade', 230), ('level', 'Level', 80),
            ('state', 'State', 130),
            ('price', 'Next Price', 90),
        ),
        height=10,
    )
    self.shop_upgrade_tree.bind(
        '<<TreeviewSelect>>', self.refresh_permanent_purchase_buttons
    )
    self.shop_upgrade_tooltip_view = TreeTooltip(
        self.shop_upgrade_tree, self.shop_upgrade_tooltip
    )
    self.shop_permanent_upgrade_info_var = tk.StringVar(
        value='Select an upgrade to see its effect, level, and next price.'
    )
    ttk.Label(
        permanent_upgrades,
        textvariable=self.shop_permanent_upgrade_info_var,
        wraplength=820,
        justify='left',
    ).grid(row=1, column=0, sticky='w', pady=(7, 4))
    self.shop_permanent_upgrade_button = ttk.Button(
        permanent_upgrades,
        text='Select an Upgrade',
        command=self.buy_selected_permanent_upgrade,
        state='disabled',
    )
    self.shop_permanent_upgrade_button.grid(row=2, column=0, sticky='e')

    permanent_buffs = ttk.Frame(permanent_tabs, padding=8)
    permanent_tabs.add(permanent_buffs, text='Permanent Unit Buffs')
    permanent_buffs.columnconfigure(0, weight=1)
    permanent_buffs.rowconfigure(2, weight=1)
    ttk.Label(
        permanent_buffs,
        text=(
            'Spend Mental Coins on lasting unit buff stacks. Buffs apply in '
            'future runs whenever that permanently unlocked unit is used.'
        ),
        style='Shop.Help.TLabel',
        wraplength=820,
    ).grid(row=0, column=0, sticky='w', pady=(0, 6))
    permanent_buff_filter = ttk.Frame(permanent_buffs)
    permanent_buff_filter.grid(row=1, column=0, sticky='ew', pady=(0, 6))
    ttk.Label(permanent_buff_filter, text='Upgrade unit:').pack(side='left')
    self.shop_permanent_buff_target_combo = ttk.Combobox(
        permanent_buff_filter,
        textvariable=self.shop_permanent_buff_target_var,
        state='readonly',
        width=34,
    )
    self.shop_permanent_buff_target_combo.pack(side='left', padx=(6, 0))
    self.shop_permanent_buff_target_combo.bind(
        '<<ComboboxSelected>>', lambda _event: self._refresh_permanent_shop()
    )
    permanent_buff_tree_frame = ttk.Frame(permanent_buffs)
    permanent_buff_tree_frame.grid(row=2, column=0, sticky='nsew')
    self.shop_permanent_buff_tree = _tree(
        permanent_buff_tree_frame,
        ('effect', 'stacks', 'state', 'price'),
        (
            ('effect', 'Permanent Effect', 380),
            ('stacks', 'Stacks', 90),
            ('state', 'State', 160),
            ('price', 'Next Price', 100),
        ),
        height=10,
        cameos=True,
    )
    self.shop_permanent_buff_tree.bind(
        '<<TreeviewSelect>>', self.refresh_permanent_buff_button
    )
    self.shop_permanent_buff_info_var = tk.StringVar(
        value='Select a permanently unlocked unit, then choose a buff.'
    )
    ttk.Label(
        permanent_buffs,
        textvariable=self.shop_permanent_buff_info_var,
        wraplength=820,
        justify='left',
    ).grid(row=3, column=0, sticky='w', pady=(7, 4))
    self.shop_permanent_buff_button = ttk.Button(
        permanent_buffs,
        text='Select a Permanent Buff',
        command=self.buy_selected_permanent_buff,
        state='disabled',
    )
    self.shop_permanent_buff_button.grid(row=4, column=0, sticky='e')

    ap_purchases = ttk.Frame(panels, padding=8)
    self.shop_ap_panel = ap_purchases
    ap_purchases.columnconfigure(0, weight=1)
    ap_purchases.rowconfigure(1, weight=1)
    ttk.Label(
        ap_purchases,
        textvariable=self.shop_ap_purchase_status_var,
        wraplength=760,
    ).grid(row=0, column=0, sticky='w', pady=(0, 6))
    ap_purchase_frame = ttk.Frame(ap_purchases)
    ap_purchase_frame.grid(row=1, column=0, sticky='nsew')
    self.shop_ap_purchase_tree = _tree(
        ap_purchase_frame,
        ('purchase', 'status', 'cost'),
        (
            ('purchase', 'Generated Purchase', 160),
            ('status', 'Status', 330),
            ('cost', 'Mental Coin Cost', 150),
        ),
        height=10,
    )
    self.shop_ap_purchase_tree.bind(
        '<Double-1>', self.buy_selected_archipelago_purchase
    )
    self.shop_ap_purchase_button = ttk.Button(
        ap_purchases,
        text='Buy Generated Check',
        command=self.buy_selected_archipelago_purchase,
        state='disabled',
    )
    self.shop_ap_purchase_button.grid(row=2, column=0, sticky='e', pady=(7, 0))

    summary = ttk.Frame(panels, padding=12)
    self.shop_summary_panel = summary
    panels.add(summary, text='Run Summary')
    summary.columnconfigure(0, weight=1)
    ttk.Label(
        summary,
        textvariable=self.shop_summary_var,
        justify='left',
        anchor='nw',
        font=('Consolas', 10),
        wraplength=760,
    ).grid(row=0, column=0, sticky='nw')

    history = ttk.Frame(panels, padding=8)
    panels.add(history, text='Run History')
    history.columnconfigure(0, weight=1)
    history.rowconfigure(0, weight=1)
    history_frame = ttk.Frame(history)
    history_frame.grid(row=0, column=0, sticky='nsew')
    self.shop_history_tree = _tree(
        history_frame,
        ('stage', 'mission'),
        (('stage', 'Stage', 80), ('mission', 'Completed Mission', 500)),
    )

    self.shop_search_var.trace_add('write', self.refresh_shop_catalogue)
    self.shop_loadout_search_var.trace_add(
        'write', lambda *_args: self._refresh_shop_loadout()
    )
    self.shop_setup_search_var.trace_add(
        'write', lambda *_args: self._refresh_shop_setup()
    )
    self.shop_permanent_search_var.trace_add(
        'write', lambda *_args: self._refresh_permanent_shop()
    )
    self.sync_shop_workspace()
