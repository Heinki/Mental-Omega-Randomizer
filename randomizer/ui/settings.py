"""Advanced and gameplay settings widgets."""

from .starting_unlocks import build_starting_unlocks_tab
from .enemy_scaling import build_enemy_scaling_settings
from .general_settings import build_general_settings

from ._builder_dependencies import (
    ARSENAL_FACTIONS,
    ARSENAL_POWER_TYPES,
    ARSENAL_TIERS,
    ARSENAL_UNIT_TYPES,
    BUFF_TYPES,
    CAMPAIGN_FILTERS,
    EVA_VOICE_CHOICES,
    IntegerSlider,
    MAIN_REWARD_WEIGHT_TYPES,
    MAX_STARTING_REWARD_COUNT,
    MAX_REWARD_WEIGHT,
    PLAYER_COLORS,
    POWER_BUFF_TYPES,
    POWER_BUFF_WEIGHT_TYPES,
    REWARD_POOL,
    STARTING_REWARD_TYPE_DEFINITIONS,
    UNIT_BUFF_WEIGHT_TYPES,
    WidgetTooltip,
    buff_stack_limit,
    stacking_amount,
    stacking_multiplier,
    tk,
    ttk,
)


def _weight_slider(self, parent, label, variable, row, tooltip):
    ttk.Label(parent, text=label).grid(
        row=row, column=0, sticky='w', padx=(0, 8), pady=(0, 4)
    )
    slider = IntegerSlider(
        parent,
        variable=variable,
        minimum=0,
        maximum=MAX_REWARD_WEIGHT,
        palette=self.ui_palette(),
        command=lambda value, target=variable: (
            self.on_reward_weight_slider_changed(target, value)
        ),
    )
    slider.grid(row=row, column=1, sticky='ew', pady=(0, 4))
    self.reward_weight_slider_controls.append(slider)
    WidgetTooltip(slider.canvas, tooltip)
    WidgetTooltip(slider.value_entry, tooltip)
    return slider


def buff_setting_amount_text(buff_type):
    buff_id = buff_type['id']
    if buff_id in {'production', 'cost'}:
        amount = round((1.0 - stacking_multiplier(buff_id, 1)) * 100)
        name = 'Production' if buff_id == 'production' else 'Cost'
        return f'{name} (-{amount}%)'
    if buff_id == 'reload':
        amount = round(
            ((1.0 / stacking_multiplier(buff_id, 1)) - 1.0) * 100
        )
        return f'Fire rate (+{amount}%)'
    if buff_id in {'speed', 'health', 'damage'}:
        amount = round((stacking_multiplier(buff_id, 1) - 1.0) * 100)
        name = {'speed': 'Speed', 'health': 'Health', 'damage': 'Damage'}[buff_id]
        return f'{name} (+{amount}%)'
    if buff_id == 'armor':
        multiplier = stacking_multiplier('armor', 1)
        amount = round(((1.0 / multiplier) - 1.0) * 100)
        return f'Armor (+{amount}% durability)'
    if buff_id in {'sight', 'ammo', 'storage', 'income'}:
        amount = int(stacking_amount(buff_id, 1))
        return f'{buff_type["setting_label"]} (+{amount})'
    if buff_id == 'passenger_capacity':
        return 'Passenger capacity (+1)'
    if buff_id == 'range':
        amount = stacking_amount('range', 1)
        return f'{buff_type["setting_label"]} (+{amount:g})'
    return buff_type['setting_label']


def _limit_text(limit):
    if limit is None:
        return 'no limit'
    return f'max {limit} stack' + ('s' if limit != 1 else '')


def unit_buff_limit_text(buff_id):
    """Summarize per-target stack limits for one broad unit buff switch."""
    rewards = [
        reward
        for reward in REWARD_POOL
        if reward.get('kind') == 'buff'
        and reward.get('unit')
        and reward.get('buff_type') == buff_id
    ]
    limits = {buff_stack_limit(reward) for reward in rewards}
    if not limits or limits == {None}:
        return _limit_text(None)
    finite = sorted(limit for limit in limits if limit is not None)
    if None in limits:
        return 'target-specific limit'
    if len(finite) == 1:
        return _limit_text(finite[0])
    return f'max {finite[0]}-{finite[-1]} stacks by unit'


def power_buff_setting_text(definition):
    return (
        f'{definition["setting_label"]} '
        f'({_limit_text(definition.get("maximum_stacks"))})'
    )


def _append_advanced_common_actions(self, parent, pool_key):
    ttk.Separator(parent, orient='vertical').pack(
        side='left', fill='y', padx=(2, 6)
    )
    ttk.Label(parent, text='All:').pack(side='left', padx=(0, 4))
    ttk.Button(
        parent,
        text='Include',
        width=7,
        padding=(6, 3),
        command=lambda key=pool_key: self.set_advanced_pool_all(key, True),
    ).pack(side='left', padx=(0, 4))
    ttk.Button(
        parent,
        text='Exclude',
        width=7,
        padding=(6, 3),
        command=lambda key=pool_key: self.set_advanced_pool_all(key, False),
    ).pack(side='left')
    ttk.Separator(parent, orient='vertical').pack(
        side='left', fill='y', padx=(6, 6)
    )
    ttk.Label(parent, text='Special:').pack(side='left', padx=(0, 4))
    ttk.Button(
        parent,
        text='Include',
        width=7,
        padding=(6, 3),
        command=lambda key=pool_key: self.set_advanced_pool_group(
            key, 'special', 'special', True
        ),
    ).pack(side='left', padx=(0, 4))
    ttk.Button(
        parent,
        text='Exclude',
        width=7,
        padding=(6, 3),
        command=lambda key=pool_key: self.set_advanced_pool_group(
            key, 'special', 'special', False
        ),
    ).pack(side='left')


def _append_advanced_selected_actions(
    self,
    parent,
    pool_key,
    faction_var,
    category_var,
):
    ttk.Label(parent, text='Selected:').pack(side='left', padx=(0, 4))
    ttk.Button(
        parent,
        text='Include',
        width=7,
        padding=(6, 3),
        command=lambda key=pool_key: self.set_advanced_pool_groups(
            key,
            faction_var.get(),
            category_var.get(),
            True,
        ),
    ).pack(side='left', padx=(0, 4))
    ttk.Button(
        parent,
        text='Exclude',
        width=7,
        padding=(6, 3),
        command=lambda key=pool_key: self.set_advanced_pool_groups(
            key,
            faction_var.get(),
            category_var.get(),
            False,
        ),
    ).pack(side='left')
    _append_advanced_common_actions(self, parent, pool_key)


def _build_advanced_tab(self, workspace_tabs):
    advanced_tab = ttk.Frame(workspace_tabs, padding=(8, 8, 8, 8))
    self.advanced_tab = advanced_tab
    advanced_tab.columnconfigure(0, weight=1)
    advanced_tab.rowconfigure(2, weight=1)
    workspace_tabs.add(advanced_tab, text='Advanced')
    advanced_tab.bind('<Configure>', self.on_advanced_tab_configure, add='+')
    self.advanced_pool_intro_label = ttk.Label(
        advanced_tab,
        text=(
            'Choose what may appear in the next generated seed. Mission, unit, and superpower '
            'cards toggle pool inclusion; buff-page cards select one target for detailed options. '
            'Excluded units lose both access and unit-specific buff rewards. Always-available '
            'essentials remain available. The current run is never changed.'
        ),
        wraplength=340,
        style='Muted.TLabel',
        justify='left',
    )
    self.advanced_pool_intro_label.grid(row=0, column=0, sticky='ew', pady=(0, 6))
    self.advanced_pool_status_label = ttk.Label(
        advanced_tab, text='', style='Muted.TLabel', wraplength=340, justify='left'
    )
    self.advanced_pool_status_label.grid(row=1, column=0, sticky='ew', pady=(0, 6))
    advanced_notebook = ttk.Notebook(advanced_tab, style='Unlocks.TNotebook')
    self.advanced_notebook = advanced_notebook
    advanced_notebook.grid(row=2, column=0, sticky='nsew')
    self.advanced_pool_canvases = {}
    self.advanced_pool_frames = {}
    self.advanced_pool_column_counts = {}
    self.advanced_pool_group_vars = {}
    self.advanced_pool_search_vars = {}
    for pool_key, pool_label in (
        ('missions', 'Missions'),
        ('units', 'Units / Buildings'),
        ('powers', 'Superpowers'),
    ):
        page = ttk.Frame(advanced_notebook)
        page.columnconfigure(0, weight=1)
        page.rowconfigure(1, weight=1)
        advanced_notebook.add(page, text=pool_label)
        controls = ttk.LabelFrame(page, text='Filters', padding=(8, 6, 8, 6))
        controls.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 6))
        if pool_key == 'missions':
            row = ttk.Frame(controls)
            row.grid(row=0, column=0, sticky='w')
            ttk.Label(row, text='Only:').pack(side='left', padx=(0, 4))
            for faction in CAMPAIGN_FILTERS[1:]:
                label = 'Allied' if faction == 'Allies' else faction
                ttk.Button(
                    row,
                    text=f'Only {label}',
                    command=lambda key=pool_key, value=faction: (
                        self.set_advanced_pool_only(key, value)
                    ),
                ).pack(side='left', padx=(0, 4))
            ttk.Button(
                row,
                text='Only Special',
                command=lambda key=pool_key: self.set_advanced_pool_only(
                    key, 'special'
                ),
            ).pack(side='left', padx=(0, 4))
            ttk.Separator(row, orient='vertical').pack(
                side='left', fill='y', padx=(2, 6)
            )
            ttk.Label(row, text='All:').pack(side='left', padx=(0, 4))
            ttk.Button(
                row,
                text='Include All',
                command=lambda key=pool_key: self.set_advanced_pool_all(
                    key, True
                ),
            ).pack(side='left', padx=(0, 4))
            ttk.Button(
                row,
                text='Exclude All',
                command=lambda key=pool_key: self.set_advanced_pool_all(
                    key, False
                ),
            ).pack(side='left')
        else:
            choices = self.advanced_pool_group_choices(pool_key)
            grouped_choices = {
                group_type: [
                    (value, label)
                    for choice_type, value, label in choices
                    if choice_type == group_type
                ]
                for group_type in ('faction', 'category')
            }
            group_vars = {}
            self.advanced_pool_group_vars[pool_key] = group_vars
            selector_frame = ttk.Frame(controls)
            selector_frame.grid(row=0, column=0, sticky='w')
            ttk.Label(selector_frame, text='Faction:').grid(
                row=0, column=0, sticky='w', padx=(0, 4)
            )
            faction_choices = grouped_choices['faction']
            faction_var = tk.StringVar(
                value=faction_choices[0][0] if faction_choices else ''
            )
            group_vars['faction'] = faction_var
            for column, (value, label) in enumerate(
                faction_choices, start=1
            ):
                ttk.Radiobutton(
                    selector_frame,
                    text=label,
                    value=value,
                    variable=faction_var,
                    padding=(0, 0),
                ).grid(
                    row=0,
                    column=column,
                    sticky='w',
                    padx=(0, 2),
                )
            ttk.Label(selector_frame, text='Category:').grid(
                row=1, column=0, sticky='w', padx=(0, 4), pady=(6, 0)
            )
            category_choices = [
                *grouped_choices['category'],
                ('all', 'All'),
            ]
            category_var = tk.StringVar(
                value=category_choices[0][0] if category_choices else ''
            )
            group_vars['category'] = category_var
            for column, (value, label) in enumerate(
                category_choices, start=1
            ):
                ttk.Radiobutton(
                    selector_frame,
                    text=label,
                    value=value,
                    variable=category_var,
                    padding=(0, 0),
                ).grid(
                    row=1,
                    column=column,
                    sticky='w',
                    padx=(0, 2),
                    pady=(6, 0),
                )
            ttk.Separator(controls, orient='vertical').grid(
                row=0, column=1, sticky='ns', padx=(6, 6)
            )
            action_row = ttk.Frame(controls)
            action_row.grid(row=0, column=2, sticky='n')
            _append_advanced_selected_actions(
                self,
                action_row,
                pool_key,
                faction_var,
                category_var,
            )
        search_row = ttk.Frame(controls)
        search_row.grid(
            row=1, column=0, columnspan=3, sticky='ew', pady=(6, 0)
        )
        search_row.columnconfigure(1, weight=1)
        ttk.Label(search_row, text='Search:').grid(
            row=0, column=0, sticky='w', padx=(0, 6)
        )
        search_var = tk.StringVar(value='')
        self.advanced_pool_search_vars[pool_key] = search_var
        ttk.Entry(search_row, textvariable=search_var).grid(
            row=0, column=1, sticky='ew', padx=(0, 4)
        )
        ttk.Button(
            search_row,
            text='Clear',
            width=8,
            command=lambda target=search_var: target.set(''),
        ).grid(row=0, column=2)
        search_var.trace_add(
            'write',
            lambda *_args, key=pool_key: (
                self.schedule_advanced_pool_search_refresh(key)
            ),
        )
        canvas = tk.Canvas(
            page,
            borderwidth=0,
            highlightthickness=0,
            background=self.style.lookup('TFrame', 'background') or '#f0f0f0',
        )
        scrollbar = ttk.Scrollbar(page, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=1, column=0, sticky='nsew')
        scrollbar.grid(row=1, column=1, sticky='ns')
        content = ttk.Frame(canvas, padding=(4, 4, 4, 4))
        window = canvas.create_window((0, 0), window=content, anchor='nw')
        content.bind(
            '<Configure>',
            lambda _event, target=canvas: target.configure(scrollregion=target.bbox('all')),
        )
        canvas.bind(
            '<Configure>',
            lambda event, key=pool_key, target=canvas, item=window: (
                target.itemconfigure(item, width=event.width),
                self.on_advanced_pool_canvas_configure(key, event.width),
            ),
        )
        canvas.bind(
            '<MouseWheel>',
            lambda event, target=canvas: self.on_unlock_mousewheel(event, target),
        )
        content.bind(
            '<MouseWheel>',
            lambda event, target=canvas: self.on_unlock_mousewheel(event, target),
        )
        self.advanced_pool_canvases[pool_key] = canvas
        self.advanced_pool_frames[pool_key] = content

    buff_page = ttk.Frame(advanced_notebook)
    buff_page.columnconfigure(0, weight=1)
    buff_page.rowconfigure(2, weight=1)
    advanced_notebook.add(buff_page, text='Unit Buffs')
    buff_controls = ttk.Frame(buff_page)
    buff_controls.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 4))
    buff_controls.columnconfigure(0, weight=1)
    self.advanced_buff_unit_label = ttk.Label(
        buff_controls,
        text='Select an included unit below.',
        style='Muted.TLabel',
        wraplength=210,
    )
    self.advanced_buff_unit_label.grid(row=0, column=0, sticky='w')
    ttk.Button(
        buff_controls, text='Enable All',
        command=lambda: self.set_advanced_unit_buffs(True),
    ).grid(row=0, column=1, padx=(4, 0))
    ttk.Button(
        buff_controls, text='Disable All',
        command=lambda: self.set_advanced_unit_buffs(False),
    ).grid(row=0, column=2, padx=(4, 0))
    unit_buff_search = tk.StringVar(value='')
    self.advanced_pool_search_vars['unit_buffs'] = unit_buff_search
    unit_buff_search_row = ttk.Frame(buff_controls)
    unit_buff_search_row.grid(
        row=1, column=0, columnspan=3, sticky='ew', pady=(6, 0)
    )
    unit_buff_search_row.columnconfigure(1, weight=1)
    ttk.Label(unit_buff_search_row, text='Search:').grid(
        row=0, column=0, sticky='w', padx=(0, 6)
    )
    ttk.Entry(unit_buff_search_row, textvariable=unit_buff_search).grid(
        row=0, column=1, sticky='ew', padx=(0, 4)
    )
    ttk.Button(
        unit_buff_search_row,
        text='Clear',
        width=8,
        command=lambda: unit_buff_search.set(''),
    ).grid(row=0, column=2)
    unit_buff_search.trace_add(
        'write',
        lambda *_args: self.schedule_advanced_pool_search_refresh(
            'unit_buffs'
        ),
    )
    buff_options = ttk.Frame(buff_page)
    buff_options.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(0, 6))
    buff_options.columnconfigure(0, weight=1)
    buff_options.columnconfigure(1, weight=1)
    self.advanced_unit_buff_vars = {}
    self.advanced_unit_buff_checks = {}
    self.advanced_unit_buff_base_text = {}
    self.advanced_unit_bulk_buff_vars = {}
    self.advanced_unit_bulk_buff_combos = {}
    for index, buff_type in enumerate(BUFF_TYPES):
        buff_id = buff_type['id']
        variable = tk.BooleanVar(value=True)
        option_text = buff_setting_amount_text(buff_type)
        option = ttk.Frame(buff_options)
        option.grid(
            row=index // 2,
            column=index % 2,
            sticky='ew',
            padx=(0, 8),
        )
        option.columnconfigure(0, weight=1)
        check = ttk.Checkbutton(
            option,
            text=option_text,
            variable=variable,
            command=lambda item=buff_id: self.on_advanced_unit_buff_changed(item),
        )
        check.grid(row=0, column=0, sticky='w')
        bulk_variable = tk.StringVar(value='Mixed')
        bulk_combo = ttk.Combobox(
            option,
            state='readonly',
            textvariable=bulk_variable,
            values=('Enabled', 'Disabled'),
            width=10,
        )
        bulk_combo.grid(row=0, column=1, padx=(6, 0))
        bulk_combo.bind(
            '<<ComboboxSelected>>',
            lambda _event, item=buff_id, target=bulk_variable: (
                self.set_all_advanced_unit_buff_type(
                    item, target.get() == 'Enabled'
                )
            ),
        )
        WidgetTooltip(
            bulk_combo,
            f'Enable or disable {buff_type["setting_label"]} for every applicable entry. Mixed means entries differ.',
        )
        self.advanced_unit_buff_vars[buff_id] = variable
        self.advanced_unit_buff_checks[buff_id] = check
        self.advanced_unit_buff_base_text[buff_id] = option_text
        self.advanced_unit_bulk_buff_vars[buff_id] = bulk_variable
        self.advanced_unit_bulk_buff_combos[buff_id] = bulk_combo
    buff_canvas = tk.Canvas(
        buff_page,
        borderwidth=0,
        highlightthickness=0,
        background=self.style.lookup('TFrame', 'background') or '#f0f0f0',
    )
    buff_scrollbar = ttk.Scrollbar(buff_page, orient='vertical', command=buff_canvas.yview)
    buff_canvas.configure(yscrollcommand=buff_scrollbar.set)
    buff_canvas.grid(row=2, column=0, sticky='nsew')
    buff_scrollbar.grid(row=2, column=1, sticky='ns')
    buff_content = ttk.Frame(buff_canvas, padding=(4, 4, 4, 4))
    buff_window = buff_canvas.create_window((0, 0), window=buff_content, anchor='nw')
    buff_content.bind(
        '<Configure>',
        lambda _event, target=buff_canvas: target.configure(scrollregion=target.bbox('all')),
    )
    buff_canvas.bind(
        '<Configure>',
        lambda event, target=buff_canvas, item=buff_window: (
            target.itemconfigure(item, width=event.width),
            self.on_advanced_pool_canvas_configure('unit_buffs', event.width),
        ),
    )
    for widget in (buff_canvas, buff_content):
        widget.bind(
            '<MouseWheel>',
            lambda event, target=buff_canvas: self.on_unlock_mousewheel(event, target),
        )
    self.advanced_pool_canvases['unit_buffs'] = buff_canvas
    self.advanced_pool_frames['unit_buffs'] = buff_content

    power_buff_page = ttk.Frame(advanced_notebook)
    power_buff_page.columnconfigure(0, weight=1)
    power_buff_page.rowconfigure(2, weight=1)
    advanced_notebook.add(power_buff_page, text='Superpower Buffs')

    power_buff_controls = ttk.Frame(power_buff_page)
    power_buff_controls.grid(
        row=0, column=0, columnspan=2, sticky='ew', pady=(0, 4)
    )
    power_buff_controls.columnconfigure(0, weight=1)
    self.advanced_power_buff_label = ttk.Label(
        power_buff_controls,
        text='Select an included power below.',
        style='Muted.TLabel',
        wraplength=210,
    )
    self.advanced_power_buff_label.grid(row=0, column=0, sticky='w')
    ttk.Button(
        power_buff_controls,
        text='Enable All',
        command=lambda: self.set_selected_power_buffs(True),
    ).grid(row=0, column=1, padx=(4, 0))
    ttk.Button(
        power_buff_controls,
        text='Disable All',
        command=lambda: self.set_selected_power_buffs(False),
    ).grid(row=0, column=2, padx=(4, 0))
    power_buff_search = tk.StringVar(value='')
    self.advanced_pool_search_vars['power_buffs'] = power_buff_search
    power_buff_search_row = ttk.Frame(power_buff_controls)
    power_buff_search_row.grid(
        row=1, column=0, columnspan=3, sticky='ew', pady=(6, 0)
    )
    power_buff_search_row.columnconfigure(1, weight=1)
    ttk.Label(power_buff_search_row, text='Search:').grid(
        row=0, column=0, sticky='w', padx=(0, 6)
    )
    ttk.Entry(
        power_buff_search_row, textvariable=power_buff_search
    ).grid(row=0, column=1, sticky='ew', padx=(0, 4))
    ttk.Button(
        power_buff_search_row,
        text='Clear',
        width=8,
        command=lambda: power_buff_search.set(''),
    ).grid(row=0, column=2)
    power_buff_search.trace_add(
        'write',
        lambda *_args: self.schedule_advanced_pool_search_refresh(
            'power_buffs'
        ),
    )
    selected_power_buff_options = ttk.Frame(power_buff_page)
    selected_power_buff_options.grid(
        row=1, column=0, columnspan=2, sticky='ew', pady=(0, 6)
    )
    for column in range(2):
        selected_power_buff_options.columnconfigure(column, weight=1)
    self.advanced_power_buff_vars = {}
    self.advanced_power_buff_checks = {}
    self.advanced_power_bulk_buff_vars = {}
    self.advanced_power_bulk_buff_combos = {}
    for index, definition in enumerate(POWER_BUFF_TYPES):
        buff_id = definition['id']
        variable = tk.BooleanVar(value=True)
        option = ttk.Frame(selected_power_buff_options)
        option.grid(
            row=index // 2,
            column=index % 2,
            sticky='ew',
            padx=(0, 8),
        )
        option.columnconfigure(0, weight=1)
        check = ttk.Checkbutton(
            option,
            text=power_buff_setting_text(definition),
            variable=variable,
            command=lambda item=buff_id: (
                self.on_power_buff_power_type_changed(item)
            ),
        )
        check.grid(row=0, column=0, sticky='w')
        bulk_variable = tk.StringVar(value='Mixed')
        bulk_combo = ttk.Combobox(
            option,
            state='readonly',
            textvariable=bulk_variable,
            values=('Enabled', 'Disabled'),
            width=10,
        )
        bulk_combo.grid(row=0, column=1, padx=(6, 0))
        bulk_combo.bind(
            '<<ComboboxSelected>>',
            lambda _event, item=buff_id, target=bulk_variable: (
                self.set_all_power_buff_type(
                    item, target.get() == 'Enabled'
                )
            ),
        )
        self.advanced_power_buff_vars[buff_id] = variable
        self.advanced_power_buff_checks[buff_id] = check
        self.advanced_power_bulk_buff_vars[buff_id] = bulk_variable
        self.advanced_power_bulk_buff_combos[buff_id] = bulk_combo
        WidgetTooltip(check, definition['description'])
        WidgetTooltip(
            bulk_combo,
            f'Enable or disable {definition["setting_label"]} for every applicable power. Mixed means powers differ.',
        )

    power_buff_canvas = tk.Canvas(
        power_buff_page,
        borderwidth=0,
        highlightthickness=0,
        background=self.style.lookup('TFrame', 'background') or '#f0f0f0',
    )
    power_buff_scrollbar = ttk.Scrollbar(
        power_buff_page,
        orient='vertical',
        command=power_buff_canvas.yview,
    )
    power_buff_canvas.configure(yscrollcommand=power_buff_scrollbar.set)
    power_buff_canvas.grid(row=2, column=0, sticky='nsew')
    power_buff_scrollbar.grid(row=2, column=1, sticky='ns')
    power_buff_content = ttk.Frame(
        power_buff_canvas, padding=(4, 4, 4, 4)
    )
    power_buff_canvas_item = power_buff_canvas.create_window(
        (0, 0), window=power_buff_content, anchor='nw'
    )
    power_buff_content.bind(
        '<Configure>',
        lambda _event, target=power_buff_canvas: (
            target.configure(scrollregion=target.bbox('all'))
        ),
    )
    power_buff_canvas.bind(
        '<Configure>',
        lambda event, target=power_buff_canvas, item=power_buff_canvas_item: (
            target.itemconfigure(item, width=event.width),
            self.on_advanced_pool_canvas_configure(
                'power_buffs', event.width
            ),
        ),
    )
    for widget in (power_buff_canvas, power_buff_content):
        widget.bind(
            '<MouseWheel>',
            lambda event, target=power_buff_canvas: (
                self.on_unlock_mousewheel(event, target)
            ),
        )
    self.advanced_pool_canvases['power_buffs'] = power_buff_canvas
    self.advanced_pool_frames['power_buffs'] = power_buff_content
    build_starting_unlocks_tab(self, advanced_notebook)

def _build_gameplay_settings(self, settings_frame):
    self.settings_intro_label = ttk.Label(
        settings_frame,
        text=(
            'Gameplay settings are saved for the next generated seed. Existing runs keep '
            'their generated gameplay settings. Appearance and privacy apply immediately.'
        ),
        wraplength=340,
        style='Muted.TLabel',
    )
    self.settings_intro_label.grid(row=1, column=0, sticky='ew', pady=(8, 8))

    map_colors_frame = ttk.LabelFrame(
        settings_frame,
        text='Mission Appearance',
        padding=(8, 8, 8, 8),
    )
    self.map_colors_frame = map_colors_frame
    map_colors_frame.grid(row=2, column=0, sticky='ew')
    map_colors_frame.columnconfigure(1, weight=1)
    ttk.Label(map_colors_frame, text='Player color').grid(
        row=0, column=0, sticky='w', padx=(0, 8)
    )
    self.player_color_combo = ttk.Combobox(
        map_colors_frame,
        state='readonly',
        textvariable=self.player_color_var,
        values=PLAYER_COLORS,
        width=15,
    )
    self.player_color_combo.grid(row=0, column=1, sticky='ew')
    self.player_color_combo.bind(
        '<MouseWheel>', self.on_settings_control_mousewheel, add='+'
    )
    self.rainbowizer_check = ttk.Checkbutton(
        map_colors_frame,
        text='Rainbowizer: randomize allied and enemy AI colors',
        variable=self.rainbowizer_var,
    )
    self.rainbowizer_check.grid(
        row=1, column=0, columnspan=2, sticky='w', pady=(5, 0)
    )
    WidgetTooltip(
        self.rainbowizer_check,
        'Assigns deterministic random colors to non-neutral allied and enemy AI houses. '
        'Civilian, neutral, and script-only neutral houses keep their authored colors.',
    )
    ttk.Label(map_colors_frame, text='EVA voice').grid(
        row=2, column=0, sticky='w', padx=(0, 8), pady=(5, 0)
    )
    self.eva_voice_combo = ttk.Combobox(
        map_colors_frame,
        state='readonly',
        textvariable=self.eva_voice_var,
        values=EVA_VOICE_CHOICES,
        width=15,
    )
    self.eva_voice_combo.grid(row=2, column=1, sticky='ew', pady=(5, 0))
    self.eva_voice_combo.bind(
        '<MouseWheel>', self.on_settings_control_mousewheel, add='+'
    )
    WidgetTooltip(
        self.eva_voice_combo,
        'Uses one announcer for the whole mission. Random is deterministic for the seed and mission.',
    )

    mission_pool_frame = ttk.LabelFrame(
        settings_frame,
        text='Mission Pool',
        padding=(8, 8, 8, 8),
    )
    self.mission_pool_frame = mission_pool_frame
    mission_pool_frame.grid(row=3, column=0, sticky='ew', pady=(8, 0))
    self.include_no_build_missions_check = ttk.Checkbutton(
        mission_pool_frame,
        text='Include true no-build / fixed-unit missions',
        variable=self.include_no_build_missions_var,
        command=self.on_mission_pool_settings_changed,
    )
    self.include_no_build_missions_check.grid(row=0, column=0, sticky='w')
    WidgetTooltip(
        self.include_no_build_missions_check,
        'Includes missions completed only with fixed units, heroes, or scripted map powers and no player production.',
    )
    self.include_no_build_production_missions_check = ttk.Checkbutton(
        mission_pool_frame,
        text='Include no-build missions with production',
        variable=self.include_no_build_production_missions_var,
        command=self.on_mission_pool_settings_changed,
    )
    self.include_no_build_production_missions_check.grid(
        row=1, column=0, sticky='w', pady=(4, 0)
    )
    WidgetTooltip(
        self.include_no_build_production_missions_check,
        'Includes missions without normal base building that still provide limited unit production.',
    )
    self.include_operation_missions_check = ttk.Checkbutton(
        mission_pool_frame,
        text='Include optional Special Operation missions',
        variable=self.include_operation_missions_var,
        command=self.on_mission_pool_settings_changed,
    )
    self.include_operation_missions_check.grid(
        row=2, column=0, sticky='w', pady=(4, 0)
    )
    WidgetTooltip(
        self.include_operation_missions_check,
        'Includes the Allied, Soviet, Epsilon, and Foehn missions labelled “Op”. '
        'These optional missions are excluded from both the next mission seed and Advanced Pool when disabled.',
    )
    self.prioritize_no_build_missions_check = ttk.Checkbutton(
        mission_pool_frame,
        text='Prioritize included no-build missions in opening',
        variable=self.prioritize_no_build_missions_var,
    )
    self.prioritize_no_build_missions_check.grid(row=3, column=0, sticky='w', pady=(4, 0))
    WidgetTooltip(
        self.prioritize_no_build_missions_check,
        'Fills protected Mission List/Grid opening positions with easier enabled true-no-build and production-no-build missions first.',
    )

    reward_frame = ttk.LabelFrame(settings_frame, text='Reward Pool', padding=(8, 8, 8, 8))
    self.reward_frame = reward_frame
    reward_frame.grid(row=4, column=0, sticky='ew', pady=(8, 0))
    reward_frame.columnconfigure(0, weight=1)
    self.randomize_unit_access_check = ttk.Checkbutton(
        reward_frame,
        text='Randomize unit access and lock unearned tech',
        variable=self.randomize_unit_access_var,
        command=self.refresh_setting_states,
    )
    self.randomize_unit_access_check.grid(row=0, column=0, sticky='w')
    WidgetTooltip(
        self.randomize_unit_access_check,
        'Turns combat units into access rewards. Units not yet earned are removed from production. '
        'Chaos always requires this option.',
    )
    self.start_with_tier_one_units_check = ttk.Checkbutton(
        reward_frame,
        text='Start with basic Tier 1 combat units',
        variable=self.start_with_tier_one_units_var,
    )
    self.start_with_tier_one_units_check.grid(row=1, column=0, sticky='w', pady=(4, 0))
    WidgetTooltip(
        self.start_with_tier_one_units_check,
        'Standard seed-selects five exact units for every usable faction family: infantry, anti-air infantry, '
        'tank, anti-air tank, and aircraft. Each mission uses only its matching family\'s five; sibling variants are not granted. '
        'Chaos and Shop instead seed-select only five units total, one for each role. '
        'Starter units remain buffable.',
    )
    self.start_with_tier_one_defenses_check = ttk.Checkbutton(
        reward_frame,
        text='Start with basic Tier 1 defensive structures',
        variable=self.start_with_tier_one_defenses_var,
    )
    self.start_with_tier_one_defenses_check.grid(
        row=2, column=0, sticky='w', pady=(4, 0)
    )
    WidgetTooltip(
        self.start_with_tier_one_defenses_check,
        'Standard grants ground and anti-air defense roles and resolves each mission to its matching faction equivalents. '
        'Each defense keeps its exact Construction Yard prerequisite. '
        'Allies receive Pillbox and Patriot; Soviets Sentry Gun and Flak Cannon; Epsilon Gatling Cannon. '
        'Chaos also includes Foehn Sonic Emitter and Shrike Nest. Structures remain gated by a matching Construction Yard. '
        'When defensive-building rewards are enabled, starter access rewards are removed while buffs remain eligible.',
    )
    self.include_defensive_buildings_check = ttk.Checkbutton(
        reward_frame,
        text='Include defensive building rewards',
        variable=self.include_defensive_buildings_var,
    )
    self.include_defensive_buildings_check.grid(row=3, column=0, sticky='w', pady=(4, 0))
    WidgetTooltip(
        self.include_defensive_buildings_check,
        'Includes faction defenses such as Pillboxes, Tesla Coils, mines, and support defenses. '
        'With access randomization they can be locked/unlocked; with buffs enabled they can receive upgrades.',
    )
    self.include_special_buildings_check = ttk.Checkbutton(
        reward_frame,
        text='Include special economy building rewards',
        variable=self.include_special_buildings_var,
        command=self.refresh_setting_states,
    )
    self.include_special_buildings_check.grid(row=4, column=0, sticky='w', pady=(4, 0))
    WidgetTooltip(
        self.include_special_buildings_check,
        'Includes Ore Purifier, Industrial Plant, Cloning Vats, and Reprocessor access, '
        'plus repeatable +1 structure-limit rewards when that buff type is enabled.',
    )
    self.include_special_rewards_check = ttk.Checkbutton(
        reward_frame,
        text='Include campaign/map-only Special rewards',
        variable=self.include_special_rewards_var,
        command=self.refresh_setting_states,
    )
    self.include_special_rewards_check.grid(
        row=5, column=0, sticky='w', pady=(4, 0)
    )
    WidgetTooltip(
        self.include_special_rewards_check,
        'Includes units, marked buildings, and powers shown as Special, plus their matching buffs. '
        'Normal roster units, economy buildings, and aid powers are unchanged.',
    )
    self.include_buff_rewards_check = ttk.Checkbutton(
        reward_frame,
        text='Include buff rewards',
        variable=self.include_buff_rewards_var,
        command=self.refresh_setting_states,
    )
    self.include_buff_rewards_check.grid(row=6, column=0, sticky='w', pady=(4, 0))
    WidgetTooltip(
        self.include_buff_rewards_check,
        'Adds repeatable stat upgrades to the reward pool. Turning this off disables all buff-only settings below.',
    )
    self.share_chaos_role_buffs_check = ttk.Checkbutton(
        reward_frame,
        text='Share buffs with equivalent units (Chaos / All Campaigns)',
        variable=self.share_chaos_role_buffs_var,
    )
    self.share_chaos_role_buffs_check.grid(row=7, column=0, sticky='w', pady=(4, 0))
    WidgetTooltip(
        self.share_chaos_role_buffs_check,
        'In Chaos or Standard All Campaigns, a buff for one curated role also affects its peers—'
        'for example GI, Conscript, Initiate, and Knightframe. Shared groups are displayed '
        'together in Unlocks.',
    )
    self.unlimited_hero_units_check = ttk.Checkbutton(
        reward_frame,
        text='Unlimited unique / hero units',
        variable=self.unlimited_hero_units_var,
        command=self.refresh_setting_states,
    )
    self.unlimited_hero_units_check.grid(row=8, column=0, sticky='w', pady=(4, 0))
    WidgetTooltip(
        self.unlimited_hero_units_check,
        'Removes the simultaneous-unit cap from trainable unique and hero units for the player. '
        'Opted-in allied helpers share the same clones. Hero +1 rewards are omitted; '
        'special-building capacity rewards can remain enabled.',
    )
    self.include_superweapon_rewards_check = ttk.Checkbutton(
        reward_frame,
        text='Include offensive superweapon rewards',
        variable=self.include_superweapon_rewards_var,
        command=self.on_unlimited_hero_units_changed,
    )
    self.include_superweapon_rewards_check.grid(row=9, column=0, sticky='w', pady=(4, 0))
    WidgetTooltip(
        self.include_superweapon_rewards_check,
        'Adds Lightning Storm, Tactical Nuke, Psychic Dominator, and Great Tempest as building-free rewards.',
    )
    self.include_secondary_superweapon_rewards_check = ttk.Checkbutton(
        reward_frame,
        text='Include secondary superweapon rewards',
        variable=self.include_secondary_superweapon_rewards_var,
        command=self.refresh_setting_states,
    )
    self.include_secondary_superweapon_rewards_check.grid(row=10, column=0, sticky='w', pady=(4, 0))
    WidgetTooltip(
        self.include_secondary_superweapon_rewards_check,
        'Adds Chronoshift, Invulnerability, and Rage as building-free rewards.',
    )
    self.include_aid_power_rewards_check = ttk.Checkbutton(
        reward_frame,
        text='Include support/aid power rewards',
        variable=self.include_aid_power_rewards_var,
        command=self.refresh_setting_states,
    )
    self.include_aid_power_rewards_check.grid(row=11, column=0, sticky='w', pady=(4, 0))
    WidgetTooltip(
        self.include_aid_power_rewards_check,
        'Adds faction strikes, buffs, scouting, unit drops, deployable support structures, minefields, and grid spawners.',
    )
    self.include_power_buff_rewards_check = ttk.Checkbutton(
        reward_frame,
        text='Include superweapon / aid power buff rewards',
        variable=self.include_power_buff_rewards_var,
        command=self.refresh_setting_states,
    )
    self.include_power_buff_rewards_check.grid(
        row=12, column=0, sticky='w', pady=(4, 0)
    )
    WidgetTooltip(
        self.include_power_buff_rewards_check,
        'Adds only buffs valid for already-unlocked powers. Native mission powers remain unchanged.',
    )

    self.access_limits_frame = ttk.Frame(reward_frame)
    self.access_limits_frame.grid(row=13, column=0, sticky='ew', pady=(8, 0))
    self.access_limits_frame.columnconfigure(0, weight=1)
    self.limit_access_rewards_check = ttk.Checkbutton(
        self.access_limits_frame,
        text='Limit Units/Powers',
        variable=self.limit_access_rewards_var,
        command=self.refresh_setting_states,
    )
    self.limit_access_rewards_check.grid(
        row=0, column=0, columnspan=3, sticky='w'
    )
    WidgetTooltip(
        self.limit_access_rewards_check,
        'Caps total unit/building and power unlocks across Starting Rewards and mission rewards. '
        'Exact Starting Unlocks count toward the caps but are never removed. Tier 1 starters and '
        'always-available essentials remain outside them. Disabled preserves unrestricted planning. '
        'Shop Mode and Randomizer Arsenal do not use these caps.',
    )
    self.access_limit_options_frame = ttk.Frame(
        self.access_limits_frame,
        padding=(20, 6, 0, 2),
    )
    self.access_limit_options_frame.grid(row=1, column=0, sticky='ew')
    self.access_limit_options_frame.columnconfigure(0, weight=1)

    self.unit_access_limit_row = ttk.Frame(self.access_limit_options_frame)
    self.unit_access_limit_row.grid(row=0, column=0, sticky='ew')
    self.unit_access_limit_row.columnconfigure(0, weight=1)
    ttk.Label(
        self.unit_access_limit_row,
        text='Units / buildings',
        font=('Segoe UI', 9, 'bold'),
    ).grid(row=0, column=0, sticky='w')
    self.unit_access_limit_max_label = ttk.Label(
        self.unit_access_limit_row,
        text='',
        style='Muted.TLabel',
    )
    self.unit_access_limit_max_label.grid(row=0, column=1, sticky='e')
    self.unit_access_limit_slider = IntegerSlider(
        self.unit_access_limit_row,
        variable=self.unit_access_limit_var,
        minimum=1,
        maximum=max(1, len(REWARD_POOL)),
        palette=self.ui_palette(),
    )
    self.unit_access_limit_slider.grid(
        row=1, column=0, columnspan=2, sticky='ew', pady=(1, 0)
    )

    self.power_access_limit_row = ttk.Frame(self.access_limit_options_frame)
    self.power_access_limit_row.grid(row=1, column=0, sticky='ew', pady=(7, 0))
    self.power_access_limit_row.columnconfigure(0, weight=1)
    ttk.Label(
        self.power_access_limit_row,
        text='Superpowers / aid powers',
        font=('Segoe UI', 9, 'bold'),
    ).grid(row=0, column=0, sticky='w')
    self.power_access_limit_max_label = ttk.Label(
        self.power_access_limit_row,
        text='',
        style='Muted.TLabel',
    )
    self.power_access_limit_max_label.grid(row=0, column=1, sticky='e')
    self.power_access_limit_slider = IntegerSlider(
        self.power_access_limit_row,
        variable=self.power_access_limit_var,
        minimum=1,
        maximum=max(1, len(REWARD_POOL)),
        palette=self.ui_palette(),
    )
    self.power_access_limit_slider.grid(
        row=1, column=0, columnspan=2, sticky='ew', pady=(1, 0)
    )
    for control in (
        self.unit_access_limit_slider,
        self.power_access_limit_slider,
    ):
        WidgetTooltip(
            control.canvas,
            'Maximum unique access identities assigned to this generated seed. '
            'Remaining reward slots use eligible buffs when possible.',
        )
        WidgetTooltip(
            control.value_entry,
            'Type an exact value or use arrow keys. The value is clamped to '
            'the currently available reward pool.',
        )

    ttk.Separator(reward_frame, orient='horizontal').grid(
        row=14, column=0, sticky='ew', pady=(8, 6)
    )
    starting_rewards_frame = ttk.Frame(reward_frame)
    starting_rewards_frame.grid(row=15, column=0, sticky='ew')
    starting_rewards_frame.columnconfigure(1, weight=1)
    ttk.Label(starting_rewards_frame, text='Starting Rewards').grid(
        row=0, column=0, sticky='w', padx=(0, 8)
    )
    self.starting_reward_count_spinbox = ttk.Spinbox(
        starting_rewards_frame,
        from_=0,
        to=MAX_STARTING_REWARD_COUNT,
        textvariable=self.starting_reward_count_var,
        width=8,
    )
    self.starting_reward_count_spinbox.grid(row=0, column=1, sticky='w')
    self.starting_unlocks_settings_button = ttk.Button(
        starting_rewards_frame,
        text='Configure Starting Unlocks...',
        command=self.show_starting_unlocks_settings,
    )
    self.starting_unlocks_settings_button.grid(
        row=0, column=2, sticky='e', padx=(8, 0)
    )
    WidgetTooltip(
        self.starting_reward_count_spinbox,
        'Number of random content unlocks received when the seed is created. '
        'Buffs remain normal progression rewards. '
        'Zero disables Starting Rewards.',
    )
    ttk.Label(
        starting_rewards_frame,
        text='Choose exactly which rewards you want to start with.',
        style='Muted.TLabel',
    ).grid(row=1, column=0, columnspan=3, sticky='w', pady=(6, 0))
    ttk.Label(
        starting_rewards_frame,
        text='Allowed types',
        style='Muted.TLabel',
    ).grid(row=2, column=0, columnspan=3, sticky='w', pady=(6, 2))
    allowed_types_frame = ttk.Frame(starting_rewards_frame)
    allowed_types_frame.grid(row=3, column=0, columnspan=3, sticky='ew')
    for column in range(2):
        allowed_types_frame.columnconfigure(column, weight=1)
    self.starting_reward_type_checks = {}
    for index, definition in enumerate(STARTING_REWARD_TYPE_DEFINITIONS):
        reward_type = definition['id']
        check = ttk.Checkbutton(
            allowed_types_frame,
            text=definition['label'],
            variable=self.starting_reward_type_vars[reward_type],
        )
        check.grid(
            row=index // 2,
            column=index % 2,
            sticky='w',
            padx=(0, 8),
            pady=(0, 2),
        )
        self.starting_reward_type_checks[reward_type] = check
        WidgetTooltip(
            check,
            definition['description']
            + ' Existing pool toggles, exclusions, weights, prerequisites, and caps still apply.',
        )

    build_enemy_scaling_settings(self, reward_frame)

    arsenal_frame = ttk.LabelFrame(
        settings_frame,
        text='Randomizer Arsenal',
        padding=(8, 8, 8, 8),
    )
    self.arsenal_frame = arsenal_frame
    arsenal_frame.grid(row=5, column=0, sticky='ew', pady=(8, 0))
    ttk.Label(
        arsenal_frame,
        text=(
            'Each mission receives one seed-fixed mixed roster. Counts request '
            'unique, non-equivalent units in each TechLevel tier.'
        ),
        style='Muted.TLabel',
        wraplength=620,
        justify='left',
    ).grid(row=0, column=0, columnspan=5, sticky='ew', pady=(0, 6))
    faction_frame = ttk.Frame(arsenal_frame)
    faction_frame.grid(row=1, column=0, columnspan=5, sticky='ew', pady=(0, 6))
    ttk.Label(faction_frame, text='Factions:').grid(
        row=0, column=0, sticky='w', padx=(0, 6)
    )
    self.arsenal_faction_checks = {}
    for column, faction in enumerate(ARSENAL_FACTIONS, start=1):
        check = ttk.Checkbutton(
            faction_frame,
            text=faction,
            variable=self.arsenal_faction_vars[faction],
            command=self.refresh_advanced_pool_views,
        )
        check.grid(row=0, column=column, sticky='w', padx=(0, 8))
        self.arsenal_faction_checks[faction] = check
    type_labels = {
        'infantry': 'Infantry',
        'vehicles': 'Vehicles',
        'aircraft': 'Aircraft',
        'naval': 'Naval',
    }
    tier_labels = {'tier_1': 'Tier 1', 'tier_2': 'Tier 2', 'tier_3': 'Tier 3'}
    ttk.Label(arsenal_frame, text='Tier').grid(row=2, column=0, sticky='w')
    for column, unit_type in enumerate(ARSENAL_UNIT_TYPES, start=1):
        ttk.Label(arsenal_frame, text=type_labels[unit_type]).grid(
            row=2, column=column, sticky='w', padx=(4, 0)
        )
    self.arsenal_roster_size_spinboxes = {}
    for row, tier in enumerate(ARSENAL_TIERS, start=3):
        ttk.Label(arsenal_frame, text=tier_labels[tier]).grid(
            row=row, column=0, sticky='w', pady=(3, 0)
        )
        for column, unit_type in enumerate(ARSENAL_UNIT_TYPES, start=1):
            spinbox = ttk.Spinbox(
                arsenal_frame,
                from_=0,
                to=20,
                width=6,
                textvariable=self.arsenal_roster_size_vars[tier][unit_type],
            )
            spinbox.grid(
                row=row, column=column, sticky='w', padx=(4, 0), pady=(3, 0)
            )
            self.arsenal_roster_size_spinboxes[(tier, unit_type)] = spinbox
    power_frame = ttk.Frame(arsenal_frame)
    power_frame.grid(row=6, column=0, columnspan=5, sticky='ew', pady=(8, 0))
    ttk.Label(power_frame, text='Powers per mission:').grid(
        row=0, column=0, sticky='w', padx=(0, 6)
    )
    power_labels = {
        'offensive': 'Offensive', 'secondary': 'Secondary', 'aid': 'Aid',
    }
    self.arsenal_power_count_spinboxes = {}
    for index, power_type in enumerate(ARSENAL_POWER_TYPES):
        ttk.Label(power_frame, text=power_labels[power_type]).grid(
            row=0, column=1 + index * 2, sticky='w', padx=(5, 3)
        )
        spinbox = ttk.Spinbox(
            power_frame,
            from_=0,
            to=20,
            width=6,
            textvariable=self.arsenal_power_count_vars[power_type],
        )
        spinbox.grid(row=0, column=2 + index * 2, sticky='w')
        self.arsenal_power_count_spinboxes[power_type] = spinbox

    buff_frame = ttk.LabelFrame(
        settings_frame,
        text='Units / Buildings',
        padding=(8, 8, 8, 8),
    )
    self.buff_frame = buff_frame
    buff_frame.grid(row=6, column=0, sticky='ew', pady=(8, 0))
    for column in range(2):
        buff_frame.columnconfigure(column, weight=1)
    self.buff_type_checks = []
    self.buff_type_checks_by_id = {}
    for index, buff_type in enumerate(BUFF_TYPES):
        row, column = divmod(index, 2)
        check = ttk.Checkbutton(
            buff_frame,
            text=(
                f'{buff_type.get("setting_label", buff_type["name"])} '
                f'({unit_buff_limit_text(buff_type["id"])})'
            ),
            variable=self.buff_type_vars[buff_type['id']],
            command=(
                self.on_hero_limit_buff_changed
                if buff_type['id'] == 'build_limit'
                else self.refresh_setting_states
            ),
        )
        check.grid(row=row, column=column, sticky='w', padx=(0, 10), pady=(0, 3))
        self.buff_type_checks.append(check)
        self.buff_type_checks_by_id[buff_type['id']] = check
        description = buff_type.get('description', '').format(plural='Affected units')
        WidgetTooltip(check, description)

    power_buff_frame = ttk.LabelFrame(
        settings_frame,
        text='Superweapons',
        padding=(8, 8, 8, 8),
    )
    self.power_buff_frame = power_buff_frame
    power_buff_frame.grid(row=7, column=0, sticky='ew', pady=(8, 0))
    for column in range(2):
        power_buff_frame.columnconfigure(column, weight=1)
    self.power_buff_type_checks = []
    for index, buff_type in enumerate(POWER_BUFF_TYPES):
        row, column = divmod(index, 2)
        check = ttk.Checkbutton(
            power_buff_frame,
            text=power_buff_setting_text(buff_type),
            variable=self.power_buff_type_vars[buff_type['id']],
            command=self.on_power_buff_global_type_changed,
        )
        check.grid(
            row=row,
            column=column,
            sticky='w',
            padx=(0, 10),
            pady=(0, 3),
        )
        self.power_buff_type_checks.append(check)
        WidgetTooltip(check, buff_type['description'])

    weight_settings_frame = ttk.LabelFrame(
        settings_frame,
        text='Weight Settings',
        padding=(8, 8, 8, 8),
    )
    self.weight_settings_frame = weight_settings_frame
    weight_settings_frame.grid(
        row=8, column=0, sticky='ew', pady=(8, 0)
    )
    weight_settings_frame.columnconfigure(0, weight=1)
    self.reward_weight_slider_controls = []
    weight_header = ttk.Frame(weight_settings_frame)
    weight_header.grid(row=0, column=0, sticky='ew', pady=(0, 6))
    weight_header.columnconfigure(0, weight=1)
    ttk.Label(
        weight_header,
        text=(
            'Weights are relative; totals do not need to equal 100. '
            '0 means never selected. 100 is maximum. Buff strength is unchanged.'
        ),
        style='Muted.TLabel',
        wraplength=620,
        justify='left',
    ).grid(row=0, column=0, sticky='ew', padx=(0, 8))
    ttk.Button(
        weight_header,
        text='Default',
        command=self.reset_reward_weights,
    ).grid(row=0, column=1, sticky='e')

    reward_weight_frame = ttk.LabelFrame(
        weight_settings_frame,
        text='Reward weights',
        padding=(8, 8, 8, 8),
    )
    self.reward_weight_frame = reward_weight_frame
    reward_weight_frame.grid(row=1, column=0, sticky='ew')
    reward_weight_frame.columnconfigure(0, minsize=190)
    reward_weight_frame.columnconfigure(1, weight=1)
    self.main_reward_weight_sliders = {}
    for row, definition in enumerate(MAIN_REWARD_WEIGHT_TYPES):
        weight_id = definition['id']
        self.main_reward_weight_sliders[weight_id] = _weight_slider(
            self,
            reward_weight_frame,
            definition['label'],
            self.main_reward_weight_vars[weight_id],
            row,
            (
                f'{definition["description"]} Selection chance only; '
                f'range 0-{MAX_REWARD_WEIGHT}.'
            ),
        )

    unit_weight_frame = ttk.LabelFrame(
        weight_settings_frame,
        text='Unit buff weights',
        padding=(8, 8, 8, 8),
    )
    self.unit_weight_frame = unit_weight_frame
    unit_weight_frame.grid(row=2, column=0, sticky='ew', pady=(8, 0))
    unit_weight_frame.columnconfigure(0, minsize=190)
    unit_weight_frame.columnconfigure(1, weight=1)
    self.unit_buff_weight_sliders = {}
    for row, (weight_id, label) in enumerate(UNIT_BUFF_WEIGHT_TYPES):
        self.unit_buff_weight_sliders[weight_id] = _weight_slider(
            self,
            unit_weight_frame,
            label,
            self.unit_buff_weight_vars[weight_id],
            row,
            (
                f'{label} reward selection chance only; '
                f'range 0-{MAX_REWARD_WEIGHT}.'
            ),
        )

    power_weight_frame = ttk.LabelFrame(
        weight_settings_frame,
        text='Superweapon buff weights',
        padding=(8, 8, 8, 8),
    )
    self.power_weight_frame = power_weight_frame
    power_weight_frame.grid(row=3, column=0, sticky='ew', pady=(8, 0))
    power_weight_frame.columnconfigure(0, minsize=190)
    power_weight_frame.columnconfigure(1, weight=1)
    self.power_buff_weight_sliders = {}
    for row, (weight_id, label) in enumerate(POWER_BUFF_WEIGHT_TYPES):
        self.power_buff_weight_sliders[weight_id] = _weight_slider(
            self,
            power_weight_frame,
            label,
            self.power_buff_weight_vars[weight_id],
            row,
            (
                f'{label} reward selection chance only; '
                f'range 0-{MAX_REWARD_WEIGHT}.'
            ),
        )

    build_general_settings(self, settings_frame)
    self.layout_settings_sections(self.settings_canvas.winfo_width())
