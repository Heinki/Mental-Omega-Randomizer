"""Tk widget construction separated from launcher orchestration."""

import tkinter as tk
from tkinter import scrolledtext, ttk

from randomizer_config import DEFAULT_CONFIG
from randomizer_paths import LAUNCHER_LOG
from randomizer_rewards import BUFF_TYPES, MAX_REWARDS_PER_CHECK
from randomizer_ui import (
    CAMPAIGN_FILTERS,
    DIFFICULTIES,
    GAME_SPEEDS,
    PROGRESSION_MODES,
    REWARD_MODES,
)
from randomizer_version import APP_VERSION

DEFAULT_MISSION_GOAL = int(DEFAULT_CONFIG['mission_goal'])


class WidgetTooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind('<Enter>', self.show, add='+')
        widget.bind('<Leave>', self.hide, add='+')
        widget.bind('<ButtonPress>', self.hide, add='+')

    def show(self, event=None):
        if self.tip is not None or not self.text:
            return
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        label = ttk.Label(
            self.tip,
            text=self.text,
            justify='left',
            font=('Segoe UI', 10),
            padding=(8, 6, 8, 6),
            relief='solid',
            wraplength=380,
        )
        label.grid(row=0, column=0)
        self.tip.update_idletasks()
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        tip_width = self.tip.winfo_reqwidth()
        tip_height = self.tip.winfo_reqheight()
        screen_width = self.widget.winfo_screenwidth()
        screen_height = self.widget.winfo_screenheight()
        x = max(0, min(x, screen_width - tip_width - 4))
        if y + tip_height > screen_height:
            y = max(0, self.widget.winfo_rooty() - tip_height - 4)
        self.tip.wm_geometry(f'+{x}+{y}')

    def hide(self, event=None):
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None


class TreeTooltip:
    def __init__(self, tree, text_callback):
        self.tree = tree
        self.text_callback = text_callback
        self.tip = None
        self.current_row = None
        tree.bind('<Motion>', self.on_motion, add='+')
        tree.bind('<Leave>', self.hide, add='+')

    def on_motion(self, event):
        row = self.tree.identify_row(event.y)
        if not row:
            self.hide()
            return

        text = self.text_callback(row)
        if not text:
            self.hide()
            return

        x = self.tree.winfo_rootx() + event.x + 18
        y = self.tree.winfo_rooty() + event.y + 12
        if row != self.current_row:
            self.hide()
            self.current_row = row
            self.tip = tk.Toplevel(self.tree)
            self.tip.wm_overrideredirect(True)
            label = ttk.Label(
                self.tip,
                text=text,
                justify='left',
                padding=(8, 6, 8, 6),
                relief='solid',
                wraplength=620,
            )
            label.grid(row=0, column=0)
        self.tip.wm_geometry(f'+{x}+{y}')

    def hide(self, event=None):
        self.current_row = None
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None


def create_widgets(self):
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
        text='Choose an open mission, earn randomized upgrades, and let victory tracking update your run.',
        style='Muted.TLabel',
    )
    self.subtitle_label.grid(row=1, column=0, sticky='w', pady=(2, 10))

    mission_view_frame = ttk.Frame(main_frame)
    self.mission_view_frame = mission_view_frame
    mission_view_frame.grid(row=2, column=0, rowspan=5, sticky='nsew', padx=(0, 12))
    mission_view_frame.columnconfigure(0, weight=1)
    mission_view_frame.rowconfigure(0, weight=1)

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
        '<Configure>', self.on_grid_content_configure, add='+'
    )
    self.grid_canvas.bind('<Configure>', self.on_grid_canvas_configure, add='+')
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

    right_frame = ttk.Frame(main_frame)
    self.right_frame = right_frame
    right_frame.grid(row=2, column=1, rowspan=5, sticky='nsew')
    right_frame.columnconfigure(0, weight=1)
    right_frame.rowconfigure(1, weight=1)

    info_tabs = ttk.Notebook(right_frame, style='Randomizer.TNotebook')
    self.info_tabs = info_tabs
    info_tabs.grid(row=1, column=0, sticky='nsew')
    info_tabs.enable_traversal()

    # Build Settings now so every seed/run control can be parented inside its
    # scrollable tab. The tab itself is added after Mission Details/Unlocks.
    settings_tab = ttk.Frame(info_tabs)
    self.settings_tab = settings_tab
    settings_tab.columnconfigure(0, weight=1)
    settings_tab.rowconfigure(0, weight=1)
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
    self.rewards_per_check_message_label = ttk.Label(options_row, text='')
    self.rewards_per_check_message_label.grid(
        row=6,
        column=0,
        columnspan=2,
        sticky='w',
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
        'Chaos draws units from all four factions, forces randomized access/tech locking, and lets '
        'earned units use matching production structures that the mission gives the player. It does '
        'not grant foreign production structures.',
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

    progress_frame = ttk.Frame(info_tabs, padding=(8, 8, 8, 8))
    progress_frame.columnconfigure(0, weight=1)
    progress_frame.rowconfigure(1, weight=1)
    info_tabs.add(progress_frame, text='Mission Details')

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
    self.unlock_icon_canvases = {}
    self.unlock_icon_frames = {}
    for faction in ('Allies', 'Soviets', 'Epsilon', 'Foehn'):
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

    info_tabs.add(settings_tab, text='Settings')

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

    mission_pool_frame = ttk.LabelFrame(
        settings_frame,
        text='Mission Pool',
        padding=(8, 8, 8, 8),
    )
    mission_pool_frame.grid(row=2, column=0, sticky='ew')
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
    self.prioritize_no_build_missions_check = ttk.Checkbutton(
        mission_pool_frame,
        text='Prioritize included no-build missions in opening',
        variable=self.prioritize_no_build_missions_var,
    )
    self.prioritize_no_build_missions_check.grid(row=2, column=0, sticky='w', pady=(4, 0))
    WidgetTooltip(
        self.prioritize_no_build_missions_check,
        'Fills protected Mission List/Grid opening positions with easier enabled true-no-build and production-no-build missions first.',
    )

    reward_frame = ttk.LabelFrame(settings_frame, text='Reward Pool', padding=(8, 8, 8, 8))
    reward_frame.grid(row=3, column=0, sticky='ew', pady=(8, 0))
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
        'Standard grants ground/anti-air infantry, vehicles, and one basic aircraft matching each '
        'Allied, Soviet, or Epsilon production family and player subfaction in the mission. An available MCV or '
        'Construction Yard also unlocks the matching airfield. Chaos assigns every faction once '
        'across the four ground roles using valid subfaction variants, then adds one seeded Allied, Soviet, or Epsilon aircraft. '
        'Starter units remain buffable.',
    )
    self.include_defensive_buildings_check = ttk.Checkbutton(
        reward_frame,
        text='Include defensive building rewards',
        variable=self.include_defensive_buildings_var,
    )
    self.include_defensive_buildings_check.grid(row=2, column=0, sticky='w', pady=(4, 0))
    WidgetTooltip(
        self.include_defensive_buildings_check,
        'Includes faction defenses such as Pillboxes, Tesla Coils, mines, and support defenses. '
        'With access randomization they can be locked/unlocked; with buffs enabled they can receive upgrades.',
    )
    self.include_buff_rewards_check = ttk.Checkbutton(
        reward_frame,
        text='Include buff rewards',
        variable=self.include_buff_rewards_var,
        command=self.refresh_setting_states,
    )
    self.include_buff_rewards_check.grid(row=3, column=0, sticky='w', pady=(4, 0))
    WidgetTooltip(
        self.include_buff_rewards_check,
        'Adds repeatable stat upgrades to the reward pool. Turning this off disables all buff-only settings below.',
    )
    self.share_chaos_role_buffs_check = ttk.Checkbutton(
        reward_frame,
        text='Share buffs with equivalent units (Chaos only)',
        variable=self.share_chaos_role_buffs_var,
    )
    self.share_chaos_role_buffs_check.grid(row=4, column=0, sticky='w', pady=(4, 0))
    WidgetTooltip(
        self.share_chaos_role_buffs_check,
        'In Chaos, a buff for one curated role also affects its peers—for example GI, Conscript, '
        'Initiate, and Knightframe. Shared groups are displayed together in Unlocks.',
    )
    self.unlimited_hero_units_check = ttk.Checkbutton(
        reward_frame,
        text='Unlimited unique / hero units',
        variable=self.unlimited_hero_units_var,
        command=self.refresh_setting_states,
    )
    self.unlimited_hero_units_check.grid(row=5, column=0, sticky='w', pady=(4, 0))
    WidgetTooltip(
        self.unlimited_hero_units_check,
        'Removes the simultaneous-unit cap from trainable unique and hero units for the player. '
        'Opted-in allied helpers share the same clones. This disables the +1 limit buff.',
    )
    self.include_superweapon_rewards_check = ttk.Checkbutton(
        reward_frame,
        text='Include offensive superweapon rewards',
        variable=self.include_superweapon_rewards_var,
    )
    self.include_superweapon_rewards_check.grid(row=6, column=0, sticky='w', pady=(4, 0))
    WidgetTooltip(
        self.include_superweapon_rewards_check,
        'Adds Lightning Storm, Tactical Nuke, Psychic Dominator, and Great Tempest as building-free rewards.',
    )
    self.include_secondary_superweapon_rewards_check = ttk.Checkbutton(
        reward_frame,
        text='Include secondary superweapon rewards',
        variable=self.include_secondary_superweapon_rewards_var,
    )
    self.include_secondary_superweapon_rewards_check.grid(row=7, column=0, sticky='w', pady=(4, 0))
    WidgetTooltip(
        self.include_secondary_superweapon_rewards_check,
        'Adds Chronoshift, Invulnerability, and Rage as building-free rewards.',
    )
    self.include_aid_power_rewards_check = ttk.Checkbutton(
        reward_frame,
        text='Include support/aid power rewards',
        variable=self.include_aid_power_rewards_var,
    )
    self.include_aid_power_rewards_check.grid(row=8, column=0, sticky='w', pady=(4, 0))
    WidgetTooltip(
        self.include_aid_power_rewards_check,
        'Adds faction strikes, buffs, scouting, unit drops, deployable support structures, minefields, and grid spawners.',
    )

    buff_frame = ttk.LabelFrame(settings_frame, text='Enabled Buff Types', padding=(8, 8, 8, 8))
    buff_frame.grid(row=4, column=0, sticky='ew', pady=(8, 0))
    for column in range(2):
        buff_frame.columnconfigure(column, weight=1)
    self.buff_type_checks = []
    self.buff_type_checks_by_id = {}
    for index, buff_type in enumerate(BUFF_TYPES):
        row, column = divmod(index, 2)
        check = ttk.Checkbutton(
            buff_frame,
            text=buff_type.get('setting_label', buff_type['name']),
            variable=self.buff_type_vars[buff_type['id']],
            command=self.refresh_setting_states,
        )
        check.grid(row=row, column=column, sticky='w', padx=(0, 10), pady=(0, 3))
        self.buff_type_checks.append(check)
        self.buff_type_checks_by_id[buff_type['id']] = check
        description = buff_type.get('description', '').format(plural='Affected units')
        WidgetTooltip(check, description)
    assistance_frame = ttk.LabelFrame(
        settings_frame,
        text='Mission Assistance',
        padding=(8, 8, 8, 8),
    )
    assistance_frame.grid(row=5, column=0, sticky='ew', pady=(8, 0))
    self.failure_assistance_check = ttk.Checkbutton(
        assistance_frame,
        text='Strengthen failed missions on retry',
        variable=self.failure_assistance_var,
    )
    self.failure_assistance_check.grid(row=0, column=0, sticky='w')
    WidgetTooltip(
        self.failure_assistance_check,
        'Each unsuccessful attempt adds one assistance stack only to that mission. '
        'The stack applies on its next launch and is removed when the mission is completed.',
    )
    self.assistance_description_label = ttk.Label(
        assistance_frame,
        text=(
            'Per stack: faster production and per-unit weapon firing, cheaper units, and higher movement '
            'speed, health, weapon damage, armor effectiveness, and attack range. Infantry '
            'infantry movement is capped at Speed 8. Applies '
            'to earned units and units supplied by that mission; normal faction rosters '
            'are used when unit access is not randomized.'
        ),
        wraplength=340,
        justify='left',
        style='Muted.TLabel',
    )
    self.assistance_description_label.grid(row=1, column=0, sticky='ew', pady=(5, 0))

    appearance_frame = ttk.LabelFrame(
        settings_frame,
        text='Appearance & Privacy',
        padding=(8, 8, 8, 8),
    )
    appearance_frame.grid(row=6, column=0, sticky='ew', pady=(8, 0))
    self.dark_mode_check = ttk.Checkbutton(
        appearance_frame,
        text='Dark mode',
        variable=self.dark_mode_var,
        command=self.on_dark_mode_changed,
    )
    self.dark_mode_check.grid(row=0, column=0, sticky='w')
    self.hide_reward_details_check = ttk.Checkbutton(
        appearance_frame,
        text='Hide reward names in Mission Details',
        variable=self.hide_reward_details_var,
        command=self.on_hide_reward_details_changed,
    )
    self.hide_reward_details_check.grid(row=1, column=0, sticky='w', pady=(4, 0))
    WidgetTooltip(
        self.hide_reward_details_check,
        'Shows ????? for pending rewards in Mission Details and mission-row hover text. '
        'Completed or released rewards reveal their names.',
    )
    self.hide_locked_grid_missions_check = ttk.Checkbutton(
        appearance_frame,
        text='Hide locked Grid Mode mission names',
        variable=self.hide_locked_grid_missions_var,
        command=self.on_hide_locked_grid_missions_changed,
    )
    self.hide_locked_grid_missions_check.grid(row=2, column=0, sticky='w', pady=(4, 0))
    WidgetTooltip(
        self.hide_locked_grid_missions_check,
        'Shows locked grid nodes as ? tiles. Completing a visible mission reveals '
        'newly unlocked mission names and faction colors.',
    )

    self.refresh_setting_states()

    self.status_label = ttk.Label(main_frame, text='Ready', anchor='w')
    self.status_label.grid(row=7, column=0, columnspan=2, sticky='ew', pady=(8, 0))

    log_header = ttk.Frame(main_frame)
    log_header.grid(row=8, column=0, columnspan=2, sticky='ew', pady=(12, 4))
    log_header.columnconfigure(1, weight=1)
    self.log_toggle_button = ttk.Button(
        log_header,
        text='Show Launcher Log',
        command=self.toggle_log,
        width=18,
    )
    self.log_toggle_button.grid(row=0, column=0, sticky='w')
    ttk.Label(log_header, text=f'Persistent diagnostics: {LAUNCHER_LOG}').grid(
        row=0,
        column=1,
        sticky='w',
        padx=(8, 0),
    )
    self.log_text = scrolledtext.ScrolledText(
        main_frame,
        height=10,
        wrap='word',
        state='disabled',
        background='black',
        foreground='white',
    )
    self.log_text.grid(row=9, column=0, columnspan=2, sticky='nsew')
    self.log_text.grid_remove()

    main_frame.rowconfigure(2, weight=1)
    main_frame.rowconfigure(9, weight=0)
    # Uniform sizing makes the mission view reliably wider than settings,
    # regardless of the settings widgets' requested width.
    main_frame.columnconfigure(0, weight=13, uniform='content')
    main_frame.columnconfigure(1, weight=6, minsize=396, uniform='content')

    # Long seed/map work runs on the single background worker. This overlay
    # blocks duplicate input while Tk keeps painting progress and elapsed time.
    self.busy_overlay = tk.Frame(main_frame, background='#edf3f8')
    self.busy_card = tk.Frame(
        self.busy_overlay,
        background='#f9fcff',
        highlightbackground='#79cfff',
        highlightthickness=3,
        padx=34,
        pady=26,
    )
    self.busy_card.place(relx=0.5, rely=0.5, anchor='center')
    self.busy_title = tk.Label(
        self.busy_card,
        text='',
        background='#f9fcff',
        foreground='#172a3a',
        font=('Segoe UI', 13, 'bold'),
    )
    self.busy_title.pack()
    self.busy_detail = tk.Label(
        self.busy_card,
        text='',
        background='#f9fcff',
        foreground='#4c6172',
        font=('Segoe UI', 9),
        wraplength=380,
        justify='center',
    )
    self.busy_detail.pack(pady=(8, 14))
    self.busy_progress = ttk.Progressbar(self.busy_card, mode='indeterminate', length=300)
    self.busy_progress.pack(fill='x')
    self.apply_color_mode()


def apply_color_mode(self):
    palette = self.ui_palette()
    style = self.style
    # Native Windows themes ignore several color and state overrides. Clam
    # honors the complete palette in both modes and keeps tab geometry stable.
    target_theme = 'clam'
    if target_theme in style.theme_names() and style.theme_use() != target_theme:
        style.theme_use(target_theme)

    background = palette['background']
    panel = palette['panel']
    foreground = palette['foreground']
    field = palette['field']
    border = palette['border']
    selected = palette['select']
    selected_foreground = palette['select_foreground']
    self.configure(background=background)

    style.configure('TFrame', background=background)
    style.configure('TLabel', background=background, foreground=foreground)
    style.configure('Muted.TLabel', background=background, foreground=palette['muted'])
    # ttk's canonical style name uses a lowercase "f". The old spelling
    # configured an unused style and left Settings group interiors light.
    style.configure('TLabelframe', background=background, bordercolor=border)
    style.configure('TLabelframe.Label', background=background, foreground=foreground)
    style.configure('TCheckbutton', background=background, foreground=foreground)
    self.ensure_checkbutton_indicator()
    style.configure('TRadiobutton', background=background, foreground=foreground)
    style.configure('TButton', background=panel, foreground=foreground, bordercolor=border)
    style.configure('Launch.TButton', background=panel, foreground=foreground, bordercolor=border)
    style.map(
        'TButton',
        background=[('active', selected), ('pressed', selected)],
        foreground=[('active', selected_foreground), ('pressed', selected_foreground)],
    )
    style.map(
        'TCheckbutton',
        background=[('active', background)],
        foreground=[('disabled', palette['muted']), ('active', foreground)],
    )
    style.configure('TEntry', fieldbackground=field, foreground=foreground, insertcolor=foreground)
    style.configure('TSpinbox', fieldbackground=field, foreground=foreground, arrowcolor=foreground)
    style.configure('TCombobox', fieldbackground=field, background=panel, foreground=foreground, arrowcolor=foreground)
    style.map(
        'TCombobox',
        fieldbackground=[('readonly', field)],
        foreground=[('readonly', foreground)],
        selectbackground=[('readonly', selected)],
        selectforeground=[('readonly', selected_foreground)],
    )
    style.configure('TNotebook', background=background, bordercolor=border)
    style.configure('TNotebook.Tab', background=panel, foreground=foreground)
    style.configure('Randomizer.TNotebook', background=background, bordercolor=border, tabposition='n')
    style.configure(
        'Randomizer.TNotebook.Tab',
        background=panel,
        foreground=foreground,
        padding=(16, 7),
        font=('Segoe UI', 10, 'bold'),
    )
    style.map(
        'Randomizer.TNotebook.Tab',
        background=[('selected', selected), ('active', palette['canvas'])],
        foreground=[('selected', selected_foreground), ('active', foreground)],
        padding=[('selected', (16, 7)), ('active', (16, 7))],
    )
    style.configure('Unlocks.TNotebook', background=background, bordercolor=border, tabposition='n')
    style.configure(
        'Unlocks.TNotebook.Tab',
        background=panel,
        foreground=foreground,
        padding=(7, 7),
        font=('Segoe UI', 9, 'bold'),
    )
    style.map(
        'Unlocks.TNotebook.Tab',
        background=[('selected', selected), ('active', palette['canvas'])],
        foreground=[('selected', selected_foreground), ('active', foreground)],
        padding=[('selected', (7, 7)), ('active', (7, 7))],
    )
    style.configure(
        'Treeview',
        background=field,
        fieldbackground=field,
        foreground=foreground,
        bordercolor=border,
    )
    style.map(
        'Treeview',
        background=[('selected', selected)],
        foreground=[('selected', selected_foreground)],
    )
    style.configure('Treeview.Heading', background=panel, foreground=foreground, bordercolor=border)
    style.map('Treeview.Heading', background=[('active', palette['canvas'])])
    style.configure('TScrollbar', background=panel, troughcolor=background, bordercolor=border, arrowcolor=foreground)

    if hasattr(self, 'missions_tree'):
        self.missions_tree.tag_configure(
            'completed',
            background='#244a32' if self.dark_mode_var.get() else '#dff2df',
            foreground='#b8efc5' if self.dark_mode_var.get() else '#176b2c',
        )
        self.missions_tree.tag_configure(
            'unlock_available',
            foreground='#65f58c' if self.dark_mode_var.get() else '#087a2f',
            font=('Segoe UI', 9, 'bold underline'),
        )
    for canvas_name in ('settings_canvas', 'grid_canvas'):
        canvas = getattr(self, canvas_name, None)
        if canvas is not None:
            canvas.configure(background=palette['canvas'])
    for text_name in ('rewards_text', 'unlocks_text'):
        text_widget = getattr(self, text_name, None)
        if text_widget is not None:
            text_widget.configure(
                background=field,
                foreground=foreground,
                insertbackground=foreground,
                selectbackground=selected,
                selectforeground=selected_foreground,
            )
    if hasattr(self, 'unlocks_text'):
        self.unlocks_text.tag_configure(
            'search_match',
            background='#665c20' if self.dark_mode_var.get() else '#fff0a6',
            foreground=foreground,
        )
        self.unlocks_text.tag_configure(
            'search_current',
            background='#9b5d1f' if self.dark_mode_var.get() else '#ffbf69',
            foreground=foreground,
        )
    if hasattr(self, 'log_text'):
        self.log_text.configure(
            background=field,
            foreground=foreground,
            insertbackground=foreground,
            selectbackground=selected,
            selectforeground=selected_foreground,
        )
        self.log_text.tag_config('error', foreground='#ff7b72' if self.dark_mode_var.get() else '#b00020')
    if hasattr(self, 'busy_overlay'):
        self.busy_overlay.configure(background=palette['busy'])
        self.busy_card.configure(
            background=palette['busy_card'],
            highlightbackground=selected,
        )
        self.busy_title.configure(
            background=palette['busy_card'],
            foreground=palette['busy_title'],
        )
        self.busy_detail.configure(
            background=palette['busy_card'],
            foreground=palette['busy_detail'],
        )


def redraw_grid(self):
    grid = self.state.get('grid') if self.state else None
    content_frame = self.grid_content_frame
    if not isinstance(grid, dict) or not grid.get('nodes'):
        if self.grid_render_signature != ('empty',):
            for child in content_frame.winfo_children():
                child.destroy()
            for column in range(self.grid_configured_width):
                content_frame.columnconfigure(
                    column, weight=0, minsize=0, uniform=''
                )
            for row in range(self.grid_configured_height):
                content_frame.rowconfigure(
                    row, weight=0, minsize=0, uniform=''
                )
            self.grid_configured_width = 1
            self.grid_configured_height = 1
            self.grid_tile_widgets = {}
            self.grid_render_signature = ('empty',)
            ttk.Label(
                content_frame,
                text='Generate a Grid Mode seed to create the mission grid.',
                anchor='center',
                justify='center',
            ).grid(row=0, column=0, sticky='nsew', padx=20, pady=20)
            content_frame.columnconfigure(0, weight=1)
            content_frame.rowconfigure(0, weight=1)
            self.grid_canvas.xview_moveto(0)
            self.grid_canvas.yview_moveto(0)
            self.after_idle(self.resize_grid_canvas_window)
        return

    index_by_code = {mission['code']: idx for idx, mission in enumerate(self.missions)}
    width = int(grid.get('width', 1))
    height = int(grid.get('height', 1))
    signature = (
        'grid',
        width,
        height,
        tuple(sorted(
            (code, int(node['x']), int(node['y']))
            for code, node in grid['nodes'].items()
        )),
    )
    if signature == self.grid_render_signature:
        self.refresh_grid_tiles()
        return

    for child in content_frame.winfo_children():
        child.destroy()
    self.grid_tile_widgets = {}
    self.grid_render_signature = signature
    for column in range(max(width, self.grid_configured_width)):
        content_frame.columnconfigure(column, weight=0, minsize=0, uniform='')
    for row in range(max(height, self.grid_configured_height)):
        content_frame.rowconfigure(row, weight=0, minsize=0, uniform='')
    self.grid_configured_width = width
    self.grid_configured_height = height
    for column in range(width):
        content_frame.columnconfigure(
            column,
            weight=1,
            minsize=105,
            uniform='grid-column',
        )
    for row in range(height):
        content_frame.rowconfigure(row, weight=1, minsize=88, uniform='grid-row')

    positions = {
        (node['x'], node['y']): code
        for code, node in grid['nodes'].items()
    }
    # Create every coordinate slot, including a quiet background for a
    # trimmed corner. This keeps rows and columns visually aligned as a
    # board instead of allowing an irregular set of widgets to collapse.
    for row in range(height):
        for column in range(width):
            if (column, row) in positions:
                continue
            spacer = tk.Frame(
                content_frame,
                background=self.ui_palette()['canvas'],
                borderwidth=0,
            )
            spacer.grid(row=row, column=column, sticky='nsew', padx=3, pady=3)

    for code, node in grid['nodes'].items():
        tile = tk.Frame(
            content_frame,
            relief='flat',
            borderwidth=0,
            highlightthickness=3,
            highlightbackground=self.ui_palette()['canvas'],
            cursor='hand2',
        )
        tile.mission_code = code
        tile.columnconfigure(0, weight=1)
        tile.rowconfigure(0, weight=1)
        selection_frame = tk.Frame(
            tile,
            relief='flat',
            borderwidth=0,
            cursor='hand2',
        )
        selection_frame.columnconfigure(0, weight=1)
        selection_frame.rowconfigure(1, weight=1)
        is_goal = code == grid.get('goal')
        selection_frame.grid(
            row=0,
            column=0,
            sticky='nsew',
            padx=3 if is_goal else 0,
            pady=3 if is_goal else 0,
        )
        banner = tk.Label(
            selection_frame,
            font=('Segoe UI', 7, 'bold'),
            anchor='center',
            justify='center',
            wraplength=max(74, 520 // max(1, width)),
            padx=3,
            pady=3,
        )
        banner.grid(row=0, column=0, sticky='ew', padx=4, pady=(4, 0))
        body = tk.Label(
            selection_frame,
            font=('Segoe UI', 9, 'bold'),
            justify='center',
            anchor='center',
            wraplength=max(80, 560 // max(1, width)),
            padx=5,
            pady=6,
        )
        body.grid(row=1, column=0, sticky='nsew', padx=4, pady=(0, 4))
        mission_index = index_by_code.get(code, 0)
        for widget in (tile, selection_frame, banner, body):
            widget.bind(
                '<Button-1>',
                lambda event, index=mission_index: self.select_grid_mission(index),
            )
        tile.grid(row=node['y'], column=node['x'], sticky='nsew', padx=3, pady=3)
        self.grid_tile_widgets[code] = {
            'tile': tile,
            'selection': selection_frame,
            'banner': banner,
            'body': body,
        }
    self.grid_canvas.xview_moveto(0)
    self.grid_canvas.yview_moveto(0)
    self.after_idle(self.resize_grid_canvas_window)
    self.refresh_grid_tiles()
