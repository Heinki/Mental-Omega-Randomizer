"""Main window shell, side panel, and information tabs."""

from ._builder_dependencies import (
    APP_VERSION,
    CAMPAIGN_FILTERS,
    DEFAULT_MISSION_GOAL,
    DIFFICULTIES,
    GAME_SPEEDS,
    MAX_REWARDS_PER_CHECK,
    PROGRESSION_MODES,
    REWARD_MODES,
    TreeTooltip,
    WidgetTooltip,
    scrolledtext,
    tk,
    ttk,
)

def _build_window_shell(self):
    main_frame = ttk.Frame(self, padding=(12, 12, 12, 12))
    self.main_frame = main_frame
    main_frame.grid(row=0, column=0, sticky='nsew')
    self.columnconfigure(0, weight=1)
    self.rowconfigure(0, weight=1)

    self.style = ttk.Style(self)
    self.style.configure('Randomizer.TNotebook', tabposition='n')
    self.style.configure('Randomizer.TNotebook.Tab', padding=(16, 7), font=('Segoe UI', 10, 'bold'))
    self.style.configure('Unlocks.TNotebook', tabposition='n')
    self.style.configure('Unlocks.TNotebook.Tab', padding=(7, 7), font=('Segoe UI', 9, 'bold'))
    self.style.configure('Launch.TButton', font=('Segoe UI', 10, 'bold'), padding=(10, 7))

    header = ttk.Label(
        main_frame,
        text=f'Mental Omega Randomizer Launcher v{APP_VERSION}',
        font=('Segoe UI', 14, 'bold'),
    )
    header.grid(row=0, column=0, sticky='w')
    self.settings_toggle_button = ttk.Button(
        main_frame,
        text='Hide Details',
        command=self.toggle_settings_panel,
    )
    self.settings_toggle_button.grid(row=0, column=1, rowspan=2, sticky='ne')
    self.subtitle_label = ttk.Label(
        main_frame,
        textvariable=self.header_summary_var,
        style='Muted.TLabel',
    )
    self.subtitle_label.grid(row=1, column=0, sticky='w', pady=(2, 10))
    for variable in (
        self.campaign_var,
        self.reward_mode_var,
        self.progression_mode_var,
        self.difficulty_var,
        self.game_speed_var,
    ):
        variable.trace_add('write', self.update_header_summary)
    self.update_header_summary()

    workspace_tabs = ttk.Notebook(main_frame, style='Randomizer.TNotebook')
    self.workspace_tabs = workspace_tabs
    workspace_tabs.grid(
        row=2,
        column=0,
        rowspan=5,
        sticky='nsew',
        padx=(0, 12),
    )
    workspace_tabs.enable_traversal()
    workspace_tabs.bind(
        '<<NotebookTabChanged>>',
        self.on_workspace_tab_changed,
        add='+',
    )

    mission_view_frame = ttk.Frame(workspace_tabs)
    self.mission_view_frame = mission_view_frame
    mission_view_frame.columnconfigure(0, weight=1)
    mission_view_frame.rowconfigure(0, weight=1)
    workspace_tabs.add(
        mission_view_frame,
        text=(
            'Grid Mode'
            if self.active_progression_mode() == 'Grid Mode'
            else 'Mission List'
        ),
    )

    self.missions_tree = ttk.Treeview(
        mission_view_frame,
        columns=('order', 'state', 'checks', 'faction', 'code', 'title'),
        show='headings',
        selectmode='browse',
        height=17,
    )
    self.mission_heading_labels = {
        'order': 'No.',
        'state': 'State',
        'checks': 'Rewards',
        'faction': 'Faction',
        'code': 'Code',
        'title': 'Mission Title',
    }
    for column, label in self.mission_heading_labels.items():
        self.missions_tree.heading(
            column,
            text=label,
            command=lambda selected=column: self.sort_missions_by(selected),
        )
    self.missions_tree.column('order', width=48, anchor='center', stretch=False)
    self.missions_tree.column('state', width=64, anchor='center', stretch=False)
    self.missions_tree.column('checks', width=70, anchor='center', stretch=False)
    self.missions_tree.column('faction', width=78, anchor='w', stretch=False)
    self.missions_tree.column('code', width=86, anchor='w', stretch=False)
    self.missions_tree.column('title', width=300, anchor='w', stretch=True)
    self.missions_tree.tag_configure(
        'completed',
        background='#dff2df',
        foreground='#176b2c',
    )
    self.missions_tree.grid(row=0, column=0, sticky='nsew')
    self.missions_tree.bind('<<TreeviewSelect>>', self.on_mission_select, add='+')
    self.mission_tooltip = TreeTooltip(self.missions_tree, self.mission_tooltip_text)

    tree_scrollbar = ttk.Scrollbar(
        mission_view_frame,
        orient='vertical',
        command=self.missions_tree.yview,
    )
    tree_scrollbar.grid(row=0, column=1, sticky='ns')
    self.missions_tree.configure(yscrollcommand=tree_scrollbar.set)
    self.tree_scrollbar = tree_scrollbar

    self.grid_frame = ttk.Frame(mission_view_frame, padding=(4, 4, 4, 4))
    self.grid_frame.grid(row=0, column=0, columnspan=2, sticky='nsew')
    self.grid_frame.columnconfigure(0, weight=1)
    self.grid_frame.rowconfigure(0, weight=1)
    self.grid_canvas = tk.Canvas(
        self.grid_frame,
        borderwidth=0,
        highlightthickness=0,
        background='#e9ecef',
    )
    self.grid_vertical_scrollbar = ttk.Scrollbar(
        self.grid_frame,
        orient='vertical',
        command=self.grid_canvas.yview,
    )
    self.grid_horizontal_scrollbar = ttk.Scrollbar(
        self.grid_frame,
        orient='horizontal',
        command=self.grid_canvas.xview,
    )
    self.grid_canvas.configure(
        xscrollcommand=self.grid_horizontal_scrollbar.set,
        yscrollcommand=self.grid_vertical_scrollbar.set,
    )
    self.grid_canvas.grid(row=0, column=0, sticky='nsew')
    self.grid_vertical_scrollbar.grid(row=0, column=1, sticky='ns')
    self.grid_horizontal_scrollbar.grid(row=1, column=0, sticky='ew')
    self.grid_content_frame = ttk.Frame(self.grid_canvas)
    self.grid_canvas_window = self.grid_canvas.create_window(
        (0, 0),
        window=self.grid_content_frame,
        anchor='nw',
    )
    self.grid_content_frame.bind(
        '<Configure>', self.on_grid_configure, add='+'
    )
    self.grid_canvas.bind('<Configure>', self.on_grid_configure, add='+')
    self.bind_all('<MouseWheel>', self.on_grid_mousewheel, add='+')
    self.bind_all('<Shift-MouseWheel>', self.on_grid_shift_mousewheel, add='+')
    self.grid_placeholder = ttk.Label(
        self.grid_content_frame,
        text='Generate a Grid Mode seed to create the mission grid.',
        anchor='center',
        justify='center',
    )

    self.compact_action_row = ttk.Frame(mission_view_frame)
    self.compact_action_row.columnconfigure(0, weight=1)
    self.compact_action_row.columnconfigure(1, weight=1)
    ttk.Button(
        self.compact_action_row,
        text='Launch Selected Mission',
        command=self.on_launch_selected,
        style='Launch.TButton',
    ).grid(row=0, column=0, sticky='ew', padx=(0, 4), pady=(6, 0))
    compact_complete_button = ttk.Button(
        self.compact_action_row,
        text='Mark Mission Complete',
        command=self.on_debug_mark_complete,
    )
    compact_complete_button.grid(row=0, column=1, sticky='ew', padx=(4, 0), pady=(6, 0))
    WidgetTooltip(
        compact_complete_button,
        'Recovery only: use when a completed mission was not detected.',
    )
    self.compact_action_row.grid(row=1, column=0, columnspan=2, sticky='ew')
    self.compact_action_row.grid_remove()

    return main_frame

def _build_right_panel(self, main_frame):
    right_frame = ttk.Frame(main_frame)
    self.right_frame = right_frame
    right_frame.grid(row=2, column=1, rowspan=5, sticky='nsew')
    right_frame.columnconfigure(0, weight=1)
    right_frame.rowconfigure(1, weight=1)

    info_tabs = ttk.Notebook(right_frame, style='Randomizer.TNotebook')
    self.info_tabs = info_tabs
    info_tabs.grid(row=1, column=0, sticky='nsew')
    info_tabs.enable_traversal()

    # Settings occupies the wide workspace beside Mission List/Grid Mode.
    settings_tab = ttk.Frame(self.workspace_tabs)
    self.settings_tab = settings_tab
    settings_tab.columnconfigure(0, weight=1)
    settings_tab.rowconfigure(0, weight=1)
    self.workspace_tabs.add(settings_tab, text='Settings')
    settings_canvas = tk.Canvas(
        settings_tab,
        borderwidth=0,
        highlightthickness=0,
        background=self.style.lookup('TFrame', 'background') or '#f0f0f0',
    )
    self.settings_canvas = settings_canvas
    settings_scrollbar = ttk.Scrollbar(
        settings_tab,
        orient='vertical',
        command=settings_canvas.yview,
    )
    settings_canvas.configure(yscrollcommand=settings_scrollbar.set)
    settings_canvas.grid(row=0, column=0, sticky='nsew')
    settings_scrollbar.grid(row=0, column=1, sticky='ns')
    settings_frame = ttk.Frame(settings_canvas, padding=(8, 8, 8, 8))
    settings_frame.columnconfigure(0, weight=1)
    settings_frame.columnconfigure(1, weight=0)
    self.settings_frame = settings_frame
    self.settings_canvas_window = settings_canvas.create_window(
        (0, 0),
        window=settings_frame,
        anchor='nw',
    )
    settings_frame.bind('<Configure>', self.on_settings_content_configure, add='+')
    settings_canvas.bind('<Configure>', self.on_settings_canvas_configure, add='+')
    self.bind_all('<MouseWheel>', self.on_settings_mousewheel, add='+')

    seed_settings_frame = ttk.LabelFrame(
        settings_frame,
        text='Seed & Run',
        padding=(8, 8, 8, 8),
    )
    self.seed_settings_frame = seed_settings_frame
    seed_settings_frame.grid(row=0, column=0, sticky='ew')
    seed_settings_frame.columnconfigure(0, weight=1)

    ttk.Label(seed_settings_frame, text='Seed', font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, sticky='w')
    seed_row = ttk.Frame(seed_settings_frame)
    seed_row.grid(row=1, column=0, sticky='ew', pady=(0, 6))
    seed_row.columnconfigure(0, weight=1)
    ttk.Entry(seed_row, textvariable=self.seed_var, width=20).grid(row=0, column=0, sticky='ew', padx=(0, 6))
    ttk.Button(seed_row, text='Generate New Seed', command=self.on_new_seed).grid(row=0, column=1, sticky='ew')

    options_row = ttk.Frame(seed_settings_frame)
    options_row.grid(row=2, column=0, sticky='ew', pady=(0, 6))
    options_row.columnconfigure(1, weight=1)
    ttk.Label(options_row, text='Missions to finish').grid(row=0, column=0, sticky='w', padx=(0, 8))
    self.mission_goal_spinbox = ttk.Spinbox(
        options_row,
        from_=1,
        to=max(DEFAULT_MISSION_GOAL, self.mission_goal_var.get()),
        textvariable=self.mission_goal_var,
        width=6,
    )
    self.mission_goal_spinbox.grid(row=0, column=1, sticky='w')
    ttk.Label(options_row, text='Game speed').grid(row=1, column=0, sticky='w', pady=(6, 0), padx=(0, 8))
    self.game_speed_combo = ttk.Combobox(
        options_row,
        state='readonly',
        textvariable=self.game_speed_var,
        values=[name for name, _ in GAME_SPEEDS],
        width=10,
    )
    self.game_speed_combo.grid(row=1, column=1, sticky='ew', pady=(6, 0))

    self.campaign_label = ttk.Label(options_row, text='Campaign')
    self.campaign_label.grid(row=2, column=0, sticky='w', pady=(6, 0), padx=(0, 8))
    self.campaign_combo = ttk.Combobox(
        options_row,
        state='readonly',
        textvariable=self.campaign_var,
        values=CAMPAIGN_FILTERS,
        width=12,
    )
    self.campaign_combo.grid(row=2, column=1, sticky='ew', pady=(6, 0))
    self.campaign_combo.bind('<<ComboboxSelected>>', self.on_campaign_filter_changed, add='+')

    settings_file_row = ttk.Frame(seed_settings_frame)
    settings_file_row.grid(row=3, column=0, sticky='ew', pady=(2, 0))
    settings_file_row.columnconfigure(0, weight=1)
    settings_file_row.columnconfigure(1, weight=1)
    ttk.Button(
        settings_file_row,
        text='Save Settings',
        command=self.save_settings_file,
    ).grid(row=0, column=0, sticky='ew', padx=(0, 3))
    ttk.Button(
        settings_file_row,
        text='Load Settings',
        command=self.load_settings_file,
    ).grid(row=0, column=1, sticky='ew', padx=(3, 0))

    ttk.Label(options_row, text='Difficulty').grid(row=3, column=0, sticky='w', pady=(6, 0), padx=(0, 8))
    self.difficulty_combo = ttk.Combobox(
        options_row,
        state='readonly',
        textvariable=self.difficulty_var,
        values=[name for name, _ in DIFFICULTIES],
        width=12,
    )
    self.difficulty_combo.grid(row=3, column=1, sticky='ew', pady=(6, 0))

    ttk.Label(options_row, text='Rewards per objective').grid(row=4, column=0, sticky='w', pady=(6, 0), padx=(0, 8))
    self.rewards_per_check_spinbox = ttk.Spinbox(
        options_row,
        from_=1,
        to=MAX_REWARDS_PER_CHECK,
        textvariable=self.rewards_per_check_var,
        width=6,
        validate='key',
        validatecommand=(self.register(self.validate_rewards_per_check), '%P'),
    )
    self.rewards_per_check_spinbox.grid(row=4, column=1, sticky='w', pady=(6, 0))
    self.buff_allied_helpers_check = ttk.Checkbutton(
        options_row,
        text='Buff allied helpers',
        variable=self.buff_allied_helpers_var,
    )
    self.buff_allied_helpers_check.grid(row=5, column=0, columnspan=2, sticky='w', pady=(6, 0))
    WidgetTooltip(
        self.buff_allied_helpers_check,
        'Gives reviewed allied AI helpers safe country buffs and compatible '
        'earned unit clones through extra Autocreate teams. Native units, '
        'TaskForces, timing, and scripts stay intact.',
    )
    self.rewards_per_check_message_label = ttk.Label(
        options_row,
        text='',
        justify='left',
        wraplength=300,
    )
    self.rewards_per_check_message_label.grid(
        row=6,
        column=0,
        columnspan=2,
        sticky='ew',
        pady=(4, 0),
    )
    self.rewards_per_check_var.trace_add('write', self.refresh_rewards_per_check_message)
    self.refresh_rewards_per_check_message()

    ttk.Label(options_row, text='Reward mode').grid(row=7, column=0, sticky='w', pady=(6, 0), padx=(0, 8))
    self.reward_mode_combo = ttk.Combobox(
        options_row,
        state='readonly',
        textvariable=self.reward_mode_var,
        values=REWARD_MODES,
        width=20,
    )
    self.reward_mode_combo.grid(row=7, column=1, sticky='ew', pady=(6, 0))
    self.reward_mode_combo.bind('<<ComboboxSelected>>', self.on_reward_mode_changed, add='+')
    WidgetTooltip(
        self.reward_mode_combo,
        'Standard uses campaign-appropriate factions and translates equivalent roles on mixed maps. '
        'Chaos draws exact unit unlocks from all four factions, forces randomized access/tech locking, '
        'and lets every compatible Barracks, factory, airfield, shipyard, or Construction Yard build '
        'the unlocked roster. It does not grant production structures. Randomizer Arsenal creates a '
        'seed-fixed temporary mixed-faction roster and power set for each mission. Arsenal rewards are '
        'buffs only, target content present in that mission, and never permanently unlock units or powers.',
    )

    ttk.Label(options_row, text='Progression').grid(row=8, column=0, sticky='w', pady=(6, 0), padx=(0, 8))
    self.progression_mode_combo = ttk.Combobox(
        options_row,
        state='readonly',
        textvariable=self.progression_mode_var,
        values=PROGRESSION_MODES,
        width=12,
    )
    self.progression_mode_combo.grid(row=8, column=1, sticky='ew', pady=(6, 0))
    self.progression_mode_combo.bind('<<ComboboxSelected>>', self.on_progression_mode_changed, add='+')
    WidgetTooltip(
        self.progression_mode_combo,
        'Classic follows the installed campaign order and opens one mission at a time. '
        'Mission List uses a randomized linear order. Grid Mode uses randomized missions '
        'on an orthogonal-neighbor board.',
    )
    # Read-only ttk comboboxes retain focus after selection and their class
    # binding consumes the mouse wheel before bind_all sees it. Bind directly
    # so scrolling Settings never changes a previously focused option.
    for combo in (
        self.game_speed_combo,
        self.campaign_combo,
        self.difficulty_combo,
        self.reward_mode_combo,
        self.progression_mode_combo,
    ):
        combo.bind('<MouseWheel>', self.on_settings_control_mousewheel, add='+')

    self.grid_options_frame = ttk.Frame(options_row)
    self.grid_options_frame.grid(row=9, column=0, columnspan=2, sticky='ew', pady=(6, 0))
    self.grid_two_starts_check = ttk.Checkbutton(
        self.grid_options_frame,
        text='Start with two available missions',
        variable=self.grid_two_starts_var,
    )
    self.grid_two_starts_check.grid(row=0, column=0, sticky='w')
    WidgetTooltip(
        self.grid_two_starts_check,
        'Opens the missions directly right of and below the top-left node at seed start. '
        'The board dimensions are calculated automatically from Missions to finish.',
    )
    button_row = ttk.Frame(right_frame)
    button_row.grid(row=0, column=0, sticky='ew', pady=(0, 6))
    button_row.columnconfigure(0, weight=1)
    ttk.Button(
        button_row,
        text='Launch Selected Mission',
        command=self.on_launch_selected,
        style='Launch.TButton',
    ).grid(row=0, column=0, sticky='ew', pady=(0, 4))
    self.debug_complete_button = ttk.Button(
        button_row,
        text='Mark Mission Complete',
        command=self.on_debug_mark_complete,
    )
    self.debug_complete_button.grid(row=1, column=0, sticky='ew', pady=(0, 3))
    WidgetTooltip(
        self.debug_complete_button,
        'Recovery only: use when a completed mission was not detected.',
    )

    return info_tabs, settings_tab, settings_frame

def _build_info_tabs(self, info_tabs):
    progress_frame = ttk.Frame(info_tabs, padding=(8, 8, 8, 8))
    progress_frame.columnconfigure(0, weight=1)
    progress_frame.rowconfigure(1, weight=1)
    info_tabs.add(progress_frame, text='Details')

    self.progress_label = ttk.Label(progress_frame, text='No seed generated yet.', anchor='w', justify='left')
    self.progress_label.grid(row=0, column=0, sticky='ew', pady=(0, 6))

    self.rewards_text = scrolledtext.ScrolledText(
        progress_frame,
        height=16,
        wrap='word',
        state='disabled',
        font=('Segoe UI', 9),
    )
    self.rewards_text.grid(row=1, column=0, sticky='nsew')

    unlocks_frame = ttk.Frame(info_tabs, padding=(8, 8, 8, 8))
    self.unlocks_tab = unlocks_frame
    unlocks_frame.columnconfigure(0, weight=1)
    unlocks_frame.rowconfigure(1, weight=1)
    info_tabs.add(unlocks_frame, text='Unlocks')

    self.unlock_legend_label = ttk.Label(
        unlocks_frame,
        text='Normal: unlocked   Green: playable reward   Gray: locked   Black: unavailable',
        style='Muted.TLabel',
        wraplength=330,
        justify='left',
    )
    self.unlock_legend_label.grid(row=0, column=0, sticky='ew', pady=(0, 6))

    unlocks_notebook = ttk.Notebook(unlocks_frame, style='Unlocks.TNotebook')
    self.unlocks_notebook = unlocks_notebook
    unlocks_notebook.grid(row=1, column=0, sticky='nsew')
    unlocks_notebook.bind(
        '<<NotebookTabChanged>>',
        self.on_unlock_dashboard_tab_changed,
        add='+',
    )
    self.unlock_icon_canvases = {}
    self.unlock_icon_frames = {}
    for faction in ('Allies', 'Soviets', 'Epsilon', 'Foehn', 'Neutral'):
        faction_page = ttk.Frame(unlocks_notebook)
        faction_page.columnconfigure(0, weight=1)
        faction_page.rowconfigure(0, weight=1)
        unlocks_notebook.add(faction_page, text=faction)
        canvas = tk.Canvas(
            faction_page,
            borderwidth=0,
            highlightthickness=0,
            background=self.style.lookup('TFrame', 'background') or '#f0f0f0',
        )
        scrollbar = ttk.Scrollbar(faction_page, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky='nsew')
        scrollbar.grid(row=0, column=1, sticky='ns')
        content = ttk.Frame(canvas, padding=(4, 4, 4, 4))
        window = canvas.create_window((0, 0), window=content, anchor='nw')
        content.bind(
            '<Configure>',
            lambda _event, target=canvas: target.configure(scrollregion=target.bbox('all')),
        )
        canvas.bind(
            '<Configure>',
            lambda event, selected=faction, target=canvas, item=window: (
                self.on_unlock_canvas_configure(selected, target, item, event.width)
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
        self.unlock_icon_canvases[faction] = canvas
        self.unlock_icon_frames[faction] = content

    summary_page = ttk.Frame(unlocks_notebook)
    summary_page.columnconfigure(0, weight=1)
    summary_page.rowconfigure(1, weight=1)
    unlocks_notebook.add(summary_page, text='Summary')
    search_row = ttk.Frame(summary_page)
    search_row.grid(row=0, column=0, sticky='ew', pady=(0, 6))
    search_row.columnconfigure(0, weight=1)
    self.unlock_search_entry = ttk.Entry(search_row, textvariable=self.unlock_search_var)
    self.unlock_search_entry.grid(row=0, column=0, sticky='ew', padx=(0, 4))
    ttk.Button(search_row, text='Prev', command=self.find_unlock_previous, width=8).grid(row=0, column=1, padx=(0, 4))
    ttk.Button(search_row, text='Next', command=self.find_unlock_next, width=8).grid(row=0, column=2, padx=(0, 4))
    ttk.Button(search_row, text='Clear', command=self.clear_unlock_search, width=8).grid(row=0, column=3)
    self.unlock_search_status = ttk.Label(search_row, text='', width=9, anchor='e')
    self.unlock_search_status.grid(row=0, column=4, padx=(6, 0))
    self.unlocks_text = scrolledtext.ScrolledText(
        summary_page,
        height=16,
        wrap='word',
        state='disabled',
        font=('Segoe UI', 9),
    )
    self.unlocks_text.grid(row=1, column=0, sticky='nsew')
    self.unlocks_text.tag_configure('search_match', background='#fff0a6')
    self.unlocks_text.tag_configure('search_current', background='#ffbf69')
    self.unlock_search_var.trace_add('write', self.refresh_unlock_search)
    self.unlock_search_entry.bind('<Return>', self.find_unlock_next)
    self.unlock_search_entry.bind('<Shift-Return>', self.find_unlock_previous)
    self.unlock_search_entry.bind('<Escape>', self.clear_unlock_search)
    self.bind_all('<Control-f>', self.focus_unlock_search, add='+')
    self.bind_all('<F3>', self.find_unlock_next, add='+')
    self.bind_all('<Shift-F3>', self.find_unlock_previous, add='+')

    enemy_buffs_page = ttk.Frame(info_tabs, padding=(8, 8, 8, 8))
    self.enemy_buffs_tab = enemy_buffs_page
    enemy_buffs_page.columnconfigure(0, weight=1)
    enemy_buffs_page.rowconfigure(2, weight=1)
    info_tabs.add(enemy_buffs_page, text='Enemy Rewards')
    ttk.Label(
        enemy_buffs_page,
        text='Applied AI bonuses',
        font=('Segoe UI', 10, 'bold'),
        justify='left',
    ).grid(row=0, column=0, sticky='ew')
    ttk.Label(
        enemy_buffs_page,
        text='A bonus appears here only after a generated map applies it.',
        style='Muted.TLabel',
        wraplength=820,
        justify='left',
    ).grid(row=1, column=0, sticky='ew', pady=(1, 6))
    self.enemy_buff_catalogue_frame = ttk.Frame(enemy_buffs_page)
    self.enemy_buff_catalogue_frame.grid(
        row=2, column=0, sticky='nsew'
    )
    self.enemy_buff_catalogue_frame.bind(
        '<Configure>', self.layout_enemy_buff_cards, add='+'
    )
    info_tabs.bind(
        '<<NotebookTabChanged>>',
        self.on_info_tab_changed,
        add='+',
    )
