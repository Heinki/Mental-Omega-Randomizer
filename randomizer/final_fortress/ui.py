"""Compact standalone play controls and on-demand Final Fortress help."""

import tkinter as tk
from tkinter import ttk

from .pressure import wave_size
from .reporting import reward_report


def _tree_scrollbars(parent, tree, row=0):
    vertical = ttk.Scrollbar(parent, command=tree.yview)
    vertical.grid(row=row, column=1, sticky='ns')
    horizontal = ttk.Scrollbar(parent, orient='horizontal', command=tree.xview)
    horizontal.grid(row=row + 1, column=0, sticky='ew')
    tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)


def _details_scrollbar(parent, text):
    scrollbar = ttk.Scrollbar(parent, command=text.yview)
    scrollbar.grid(row=0, column=1, sticky='ns')
    text.configure(yscrollcommand=scrollbar.set)


class _FortressViewport(ttk.Frame):
    """Fill available space and scroll overflowing controls on short displays."""

    def __init__(self, parent, background):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, width=1, height=1, highlightthickness=0,
                                borderwidth=0, background=background)
        scrollbar = ttk.Scrollbar(self, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set, yscrollincrement=24)
        self.canvas.grid(row=0, column=0, sticky='nsew')
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.content = ttk.Frame(self.canvas)
        self.window = self.canvas.create_window((0, 0), window=self.content, anchor='nw')
        self._pending = None
        self.layout = None
        self.canvas.bind('<Configure>', self._configure)
        self.content.bind('<Configure>', self._schedule_resize)

    def _configure(self, event):
        self.canvas.itemconfigure(self.window, width=max(1, event.width))
        if self.layout is not None:
            self.layout(event.width)
        self._schedule_resize()

    def _schedule_resize(self, _event=None):
        if self._pending is None:
            self._pending = self.after_idle(self._resize)

    def _resize(self):
        self._pending = None
        height = max(self.canvas.winfo_height(), self.content.winfo_reqheight())
        self.canvas.itemconfigure(self.window, height=height)
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def bind_controls(self):
        # Use a local bind tag so other modes and nested scrollable widgets keep
        # their own wheel handling. Prepend it to protect readonly comboboxes.
        tag = f'FortressScroll:{self}'
        for sequence in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
            self.bind_class(tag, sequence, self._mousewheel)

        def visit(widget):
            if isinstance(widget, (ttk.Treeview, tk.Text, ttk.Scrollbar)):
                return
            widget.bindtags((tag, *widget.bindtags()))
            for child in widget.winfo_children():
                visit(child)

        visit(self)

    def _mousewheel(self, event):
        delta = getattr(event, 'delta', 0)
        number = getattr(event, 'num', 0)
        if not delta and number not in (4, 5):
            return
        steps = max(1, abs(int(delta / 120)))
        self.canvas.yview_scroll(-steps if delta > 0 or number == 4 else steps, 'units')
        return 'break'


def build_final_fortress_tab(app, notebook):
    tab = ttk.Frame(notebook, padding=8)
    app.final_fortress_tab = tab
    # The game-mode controller inserts this frame only when selected.
    tab.columnconfigure(0, weight=1)
    tab.rowconfigure(0, weight=1)
    palette = app.ui_palette()
    viewport = _FortressViewport(tab, palette['background'])
    app.final_fortress_canvas = viewport.canvas
    viewport.grid(row=0, column=0, sticky='nsew')
    content = viewport.content
    content.columnconfigure(0, weight=1)
    content.rowconfigure(1, weight=1)
    title = ttk.Frame(content)
    title.grid(row=0, column=0, sticky='ew', pady=(0, 12))
    title.columnconfigure(0, weight=1)
    ttk.Label(title, text='Final Fortress', font=('Segoe UI', 18, 'bold')).grid(
        row=0, column=0, sticky='w')
    from .profiles import PROFILE_PATHS
    profiles = None
    if len(PROFILE_PATHS) > 1:
        profiles = ttk.Frame(title)
        profiles.grid(row=0, column=1, sticky='e', padx=(12, 16))
        ttk.Label(profiles, text='Profile').pack(side='left', padx=(0, 8))
        app.final_fortress_profile_combo = ttk.Combobox(
            profiles, textvariable=app.final_fortress_profile_var, values=tuple(PROFILE_PATHS),
            state='readonly', width=24)
        app.final_fortress_profile_combo.pack(side='left')
        app.final_fortress_profile_combo.bind('<<ComboboxSelected>>', app.on_final_fortress_profile_changed)
    help_choice = tk.StringVar(value='Help')
    help_button = ttk.Combobox(title, textvariable=help_choice, state='readonly',
                               values=('How to play', 'Wave forecast'), width=18)
    def open_help(_event):
        page = help_choice.get()
        help_choice.set('Help')
        app.show_final_fortress_help(page)
    help_button.bind('<<ComboboxSelected>>', open_help)
    help_button.grid(row=0, column=2, sticky='e')
    from randomizer.coop import feature
    if feature.COOP_FEATURE_ENABLED:
        coop_status = ttk.Label(title, textvariable=app.fortress_coop_status_var,
                                justify='left', style='Muted.TLabel')
        coop_status.grid(row=2, column=0, columnspan=3, sticky='ew', pady=(6, 0))

    progression = ttk.Notebook(content)
    app.final_fortress_progression_tabs = progression
    app.build_fortress_color_control(title)
    progression.grid(row=1, column=0, sticky='nsew', pady=(12, 0))
    perks = ttk.Frame(progression, padding=12)
    challenges = ttk.Frame(progression, padding=12)
    progression.add(perks, text='Permanent perks')
    progression.add(challenges, text='Challenge')
    perks.columnconfigure(0, weight=1)
    perks.rowconfigure(1, weight=1)
    ttk.Label(perks, textvariable=app.final_fortress_gems_var).grid(
        row=0, column=0, sticky='w', pady=(0, 8))
    panes = tk.PanedWindow(perks, orient='horizontal', sashwidth=6,
                           borderwidth=0, background=palette['background'])
    panes.grid(row=1, column=0, sticky='nsew')
    listing = ttk.Frame(panes)
    listing.columnconfigure(0, weight=1)
    listing.rowconfigure(0, weight=1)
    panes.add(listing, minsize=120)
    app.final_fortress_perks_tree = ttk.Treeview(
        listing, columns=('name', 'decrease', 'rank', 'increase', 'status', 'cost', 'effect'),
        displaycolumns=('name', 'decrease', 'rank', 'increase', 'status', 'cost'),
        show='headings', selectmode='browse', height=8)
    for column, label, width in (('name', 'Perk', 180), ('decrease', '', 38),
                                  ('rank', 'Rank', 65), ('increase', '', 38),
                                  ('status', 'Status', 125), ('cost', 'Next rank cost', 190),
                                  ('effect', 'Effect', 450)):
        app.final_fortress_perks_tree.heading(column, text=label)
        app.final_fortress_perks_tree.column(column, width=width, minwidth=width,
                                            stretch=column == 'name')
    for column in ('decrease', 'rank', 'increase'):
        app.final_fortress_perks_tree.column(column, anchor='center')
    app.final_fortress_perks_tree.grid(row=0, column=0, sticky='nsew')
    _tree_scrollbars(listing, app.final_fortress_perks_tree)
    app.final_fortress_perks_tree.bind('<<TreeviewSelect>>', app.select_final_fortress_perk)
    app.final_fortress_perks_tree.bind('<Button-1>', app.on_final_fortress_perk_click)
    app.final_fortress_perks_tree.bind('<Double-1>', app.on_final_fortress_perk_click)
    app.final_fortress_perks_tree.bind('<Left>', lambda _event: app.refund_final_fortress_perk())
    app.final_fortress_perks_tree.bind('<Right>', lambda _event: app.buy_final_fortress_perk())
    app.final_fortress_perks_tree.bind('<Return>', lambda _event: app.buy_final_fortress_perk())
    details = ttk.LabelFrame(panes, text='Rank effects', padding=(10, 4))
    details.columnconfigure(0, weight=1)
    details.rowconfigure(0, weight=1)
    panes.add(details, minsize=100)
    app.final_fortress_perk_details = tk.Text(
        details, width=1, height=5, wrap='word', relief='flat', borderwidth=0,
        font=('Segoe UI', 10), state='disabled',
        background=palette['background'], foreground=palette['foreground'],
        selectbackground=palette['select'], selectforeground=palette['select_foreground'])
    app.final_fortress_perk_details.grid(row=0, column=0, sticky='nsew')
    _details_scrollbar(details, app.final_fortress_perk_details)
    buttons = ttk.Frame(perks)
    buttons.grid(row=2, column=0, sticky='e', pady=(8, 0))
    app.final_fortress_refund_perk_button = ttk.Button(
        buttons, text='Refund rank', command=app.refund_final_fortress_perk)
    app.final_fortress_refund_perk_button.pack(side='left', padx=(0, 8))
    app.final_fortress_buy_perk_button = ttk.Button(
        buttons, text='Buy / upgrade', command=app.buy_final_fortress_perk)
    app.final_fortress_buy_perk_button.pack(side='left', padx=(0, 8))
    app.final_fortress_toggle_perk_button = ttk.Button(
        buttons, text='Enable / disable', command=app.toggle_final_fortress_perk)
    app.final_fortress_toggle_perk_button.pack(side='left')
    challenges.columnconfigure(0, weight=1)
    challenges.rowconfigure(0, weight=1)
    challenge_panes = tk.PanedWindow(challenges, orient='horizontal', sashwidth=6,
                                     borderwidth=0, background=palette['background'])
    app.final_fortress_panes = (panes, challenge_panes)
    challenge_panes.grid(row=0, column=0, sticky='nsew')
    challenge_listing = ttk.Frame(challenge_panes)
    challenge_listing.columnconfigure(0, weight=1)
    challenge_listing.rowconfigure(0, weight=1)
    challenge_panes.add(challenge_listing, minsize=120)
    app.final_fortress_challenge_tree = ttk.Treeview(challenge_listing,
        columns=('enabled', 'name', 'decrease', 'stacks', 'increase', 'gems', 'effect'),
        displaycolumns=('enabled', 'name', 'decrease', 'stacks', 'increase', 'gems'),
        show='headings', selectmode='extended', height=6)
    for key, title_text, width in (('enabled', 'Enabled', 70), ('name', 'Enemy modifier', 210),
                                 ('decrease', '', 38), ('stacks', 'Stacks', 65),
                                 ('increase', '', 38), ('gems', 'Victory Defensive Points', 190),
                                 ('effect', 'Effect at selected stacks', 360)):
        app.final_fortress_challenge_tree.heading(key, text=title_text)
        app.final_fortress_challenge_tree.column(key, width=width, minwidth=width,
                                                stretch=key == 'name')
    for key in ('decrease', 'stacks', 'increase'):
        app.final_fortress_challenge_tree.column(key, anchor='center')
    app.final_fortress_challenge_tree.grid(row=0, column=0, sticky='nsew')
    _tree_scrollbars(challenge_listing, app.final_fortress_challenge_tree)
    app.final_fortress_challenge_tree.bind('<<TreeviewSelect>>', app.select_final_fortress_challenge)
    app.final_fortress_challenge_tree.bind('<Button-1>', app.on_final_fortress_challenge_click)
    app.final_fortress_challenge_tree.bind('<Alt-Button-1>',
        lambda event: app.on_final_fortress_challenge_click(event, additive=True))
    app.final_fortress_challenge_tree.bind('<B1-Motion>', app.drag_final_fortress_challenges)
    app.final_fortress_challenge_tree.bind('<ButtonRelease-1>', app.end_final_fortress_challenge_drag)
    app.final_fortress_challenge_tree.bind('<Control-a>', app.select_all_final_fortress_challenges)
    app.final_fortress_challenge_tree.bind('<Control-A>', app.select_all_final_fortress_challenges)
    app.final_fortress_challenge_tree.bind('<Double-1>', app.toggle_final_fortress_challenge)
    for gesture in ('<Alt-Double-1>', '<Control-Double-1>'):
        app.final_fortress_challenge_tree.bind(gesture,
            lambda event: app.on_final_fortress_challenge_click(event, additive=True))
    app.final_fortress_challenge_tree.bind('<space>', app.toggle_final_fortress_challenge)
    app.final_fortress_challenge_tree.bind('<Return>', app.toggle_final_fortress_challenge)
    app.final_fortress_challenge_tree.bind('<Escape>', app.clear_final_fortress_challenge_selection)
    challenge_details = ttk.LabelFrame(challenge_panes, text='Effect at selected stacks', padding=(10, 4))
    challenge_details.columnconfigure(0, weight=1)
    challenge_details.rowconfigure(0, weight=1)
    challenge_panes.add(challenge_details, minsize=100)
    app.final_fortress_challenge_details = tk.Text(
        challenge_details, width=1, height=5, wrap='word', relief='flat', borderwidth=0,
        font=('Segoe UI', 10), state='disabled',
        background=palette['background'], foreground=palette['foreground'],
        selectbackground=palette['select'], selectforeground=palette['select_foreground'])
    app.final_fortress_challenge_details.grid(row=0, column=0, sticky='nsew')
    _details_scrollbar(challenge_details, app.final_fortress_challenge_details)
    controls = ttk.Frame(challenges)
    controls.grid(row=1, column=0, sticky='ew', pady=(8, 0))
    select_all = ttk.Button(controls, text='Select all', command=app.select_all_final_fortress_challenges)
    clear_selection = ttk.Button(controls, text='Clear selection', command=app.clear_final_fortress_challenge_selection)
    app.final_fortress_challenge_enable_button = ttk.Button(
        controls, text='Enable selected', state='disabled',
        command=lambda: app.set_final_fortress_challenges_enabled(True))
    app.final_fortress_challenge_disable_button = ttk.Button(
        controls, text='Disable selected', state='disabled',
        command=lambda: app.set_final_fortress_challenges_enabled(False))
    app.final_fortress_stack_max_button = ttk.Button(
        controls, text='Max stacks', state='disabled', command=app.max_final_fortress_challenge_stacks)
    challenge_buttons = (select_all, clear_selection,
                         app.final_fortress_challenge_enable_button,
                         app.final_fortress_challenge_disable_button,
                         app.final_fortress_stack_max_button)
    selection_hint = ttk.Label(controls, text='Drag / Ctrl / Alt to select · Ctrl+A: all',
                               style='Muted.TLabel', justify='left')

    results = ttk.Frame(progression, padding=12)
    app.final_fortress_results_tab = results
    progression.add(results, text='Run results')
    results.columnconfigure(0, weight=1)
    results.rowconfigure(1, weight=1)
    result_heading = ttk.Label(results, textvariable=app.final_fortress_result_var,
                               font=('Segoe UI', 12, 'bold'), justify='left')
    result_heading.grid(row=0, column=0, sticky='ew', pady=(0, 8))
    app.final_fortress_results_tree = ttk.Treeview(results,
        columns=('source', 'gems', 'detail'), show='headings', height=6)
    for key, title_text, width in (('source', 'Reward source', 240), ('gems', 'Defensive Points', 140),
                                 ('detail', 'Result / crate reward', 450)):
        app.final_fortress_results_tree.heading(key, text=title_text)
        app.final_fortress_results_tree.column(key, width=width, minwidth=width,
                                              stretch=key == 'detail')
    app.final_fortress_results_tree.grid(row=1, column=0, sticky='nsew')
    _tree_scrollbars(results, app.final_fortress_results_tree, row=1)

    setup = ttk.Frame(progression, padding=12)
    progression.insert(0, setup, text='Defense setup')
    progression.select(setup)
    setup.columnconfigure(1, weight=1)
    app.final_fortress_setup_combos = []
    setup_labels = []
    for row, (label, variable, values, handler) in enumerate((
        ('Game Mode', app.game_mode_var, app.game_mode_choices, app.on_game_mode_changed),
        ('Map', app.final_fortress_map_var, app.final_fortress_map_choices, app.on_final_fortress_map_changed),
        ('Player faction', app.final_fortress_country_var,
         tuple(app.final_fortress_country_choices), app.on_final_fortress_country_changed),
        ('AI difficulty', app.final_fortress_difficulty_var,
         tuple(app.final_fortress_difficulty_choices), app.on_final_fortress_difficulty_changed),
        ('Wave multiplier', app.final_fortress_wave_multiplier_var,
         tuple(app.final_fortress_wave_multiplier_choices),
         app.on_final_fortress_wave_multiplier_changed),
    )):
        setup_label = ttk.Label(setup, text=label)
        setup_labels.append(setup_label)
        setup_label.grid(row=row, column=0, sticky='w', padx=(0, 12), pady=5)
        combo = ttk.Combobox(setup, textvariable=variable, values=values, state='readonly', width=12)
        app.final_fortress_setup_combos.append(combo)
        combo.grid(row=row, column=1, sticky='ew', pady=5)
        if handler is not None:
            combo.bind('<<ComboboxSelected>>', handler)

    app.final_fortress_mental_ai_boost_check = ttk.Checkbutton(
                    setup, text='Mental AI Boost (enemy and allied AI)',
                    variable=app.final_fortress_mental_ai_boost_var,
                    command=app.on_final_fortress_mental_ai_boost_changed)
    app.final_fortress_mental_ai_boost_check.grid(row=5, column=1, sticky='w', pady=5)

    launch = ttk.Frame(tab)
    launch.grid(row=1, column=0, sticky='ew', pady=(8, 0))
    launch.columnconfigure(0, weight=1)
    status = ttk.Label(launch, textvariable=app.final_fortress_status_var, justify='left')
    status.grid(row=0, column=0, sticky='ew', padx=(0, 12))
    app.final_fortress_launch_button = ttk.Button(
        launch, text='Launch Final Fortress', command=app.launch_final_fortress,
        state='disabled', style='Launch.TButton')
    app.final_fortress_launch_button.grid(row=0, column=1, sticky='e')

    def layout(width):
        compact = width < 1100
        two_columns = width >= 700
        if profiles is not None:
            profiles.grid_configure(row=1 if compact else 0,
                                    column=0 if compact else 1,
                                    columnspan=2 if compact else 1,
                                    sticky='w' if compact else 'e',
                                    padx=0 if compact else (12, 16),
                                    pady=(6, 0) if compact else 0)
        if feature.COOP_FEATURE_ENABLED:
            coop_status.configure(wraplength=max(1, width - 16))
        setup.columnconfigure(3, weight=1 if two_columns else 0)
        for index, (label_widget, combo) in enumerate(zip(setup_labels, app.final_fortress_setup_combos)):
            row = index // 2 if two_columns else index
            column = (index % 2) * 2 if two_columns else 0
            label_widget.grid_configure(row=row, column=column,
                                        padx=(16 if column else 0, 8), pady=3)
            combo.grid_configure(row=row, column=column + 1, pady=3)
        app.final_fortress_mental_ai_boost_check.grid_configure(
            row=3 if two_columns else 5, column=0, columnspan=4 if two_columns else 2)
        orient = 'vertical' if compact else 'horizontal'
        for pane in (panes, challenge_panes):
            if str(pane.cget('orient')) != orient:
                pane.configure(orient=orient)
        button_columns = 3 if compact else 5
        for index, button in enumerate(challenge_buttons):
            button.grid(row=index // button_columns, column=index % button_columns,
                        sticky='w', padx=(0, 8), pady=(0, 4))
        selection_hint.grid(row=(len(challenge_buttons) - 1) // button_columns + 1,
                            column=0, columnspan=button_columns, sticky='ew')
        selection_hint.configure(wraplength=max(1, width - 56))
        result_heading.configure(wraplength=max(1, width - 56))

    launch.bind('<Configure>', lambda event: status.configure(
        wraplength=max(1, event.width - app.final_fortress_launch_button.winfo_reqwidth() - 16)))
    viewport.layout = layout
    viewport.bind_controls()
    app.refresh_final_fortress()


def show_final_fortress_help(app, page):
    if page not in ('How to play', 'Wave forecast'):
        return
    existing = getattr(app, '_final_fortress_help_window', None)
    if existing is not None and existing.winfo_exists():
        existing.destroy()
    window = tk.Toplevel(app)
    app._final_fortress_help_window = window
    window.title(f'Final Fortress — {page}')
    window.transient(app)
    width = min(740, app.winfo_screenwidth() - 80)
    height = min(420, app.winfo_screenheight() - 100)
    window.geometry(f'{width}x{height}')
    window.minsize(min(480, width), min(300, height))
    window.columnconfigure(0, weight=1)
    window.rowconfigure(0, weight=1)
    frame = ttk.Frame(window, padding=16)
    frame.grid(row=0, column=0, sticky='nsew')
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)
    if page == 'Wave forecast':
        _build_forecast(app, frame)
    else:
        text = tk.Text(frame, wrap='word', borderwidth=0, padx=8, pady=8, font='TkDefaultFont')
        background = app.style.lookup('TFrame', 'background')
        foreground = app.style.lookup('TLabel', 'foreground')
        if background:
            text.configure(background=background)
        if foreground:
            text.configure(foreground=foreground)
        text.grid(row=0, column=0, sticky='nsew')
        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=text.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        text.configure(yscrollcommand=scrollbar.set)
        text.insert('1.0', app.final_fortress_help_var.get())
        text.configure(state='disabled')
    ttk.Button(frame, text='Close', command=window.destroy).grid(
        row=2, column=0, columnspan=2, sticky='e', pady=(12, 0))
    window.bind('<Escape>', lambda _event: window.destroy())


def refresh_results(app, run):
    if not hasattr(app, 'final_fortress_results_tree'):
        return
    heading, rows = reward_report(run)
    content = (run['id'] if run else None, heading, tuple(rows))
    if getattr(app, '_final_fortress_result_content', None) == content:
        return
    app._final_fortress_result_content = content
    app.final_fortress_result_var.set(heading)
    tree = app.final_fortress_results_tree
    tree.delete(*tree.get_children())
    for row in rows:
        tree.insert('', 'end', values=row)
    if run and run['status'] != 'active' and getattr(app, '_final_fortress_results_shown', None) != run['id']:
        app.final_fortress_progression_tabs.select(app.final_fortress_results_tab)
        if (app.final_fortress_mode_selected()
                and str(app.final_fortress_tab) in app.workspace_tabs.tabs()):
            app.workspace_tabs.select(app.final_fortress_tab)
        app._final_fortress_results_shown = run['id']


def show_perk_details(app, text):
    _show_details(app, 'perk', text)


def show_challenge_details(app, text):
    _show_details(app, 'challenge', text)


def _show_details(app, kind, text):
    widget = getattr(app, f'final_fortress_{kind}_details')
    cache_key = f'_final_fortress_{kind}_details_text'
    if getattr(app, cache_key, None) == text:
        return
    setattr(app, cache_key, text)
    widget.configure(state='normal')
    widget.delete('1.0', 'end')
    widget.insert('1.0', text)
    widget.yview_moveto(0)
    widget.configure(state='disabled')


def _build_forecast(app, frame):
    tree = ttk.Treeview(frame, columns=('minute', 'sides', 'per_side', 'total', 'growth'),
                        show='headings', selectmode='none', height=8)
    for column, label in (('minute', 'Minute'), ('sides', 'Active sides'),
                          ('per_side', 'Units per side'), ('total', 'Total units'),
                          ('growth', 'Growth')):
        tree.heading(column, text=label)
        tree.column(column, width=110, minwidth=110, anchor='center')
    tree.grid(row=0, column=0, sticky='nsew')
    _tree_scrollbars(frame, tree)
    config, state = app.final_fortress_config, app.final_fortress_state
    if config is None or state is None or config.get('wave_pressure') is None:
        return
    preferences, settings = state['preferences'], config['settings']
    powerhouse = any(entry['id'] in preferences['selected_challenges']
                     and entry.get('enemy_effect_id') == 'powerhouse' for entry in config.get('challenges', []))
    try:
        for index, seconds in enumerate(range(settings['wave_interval_seconds'],
                                              settings['survival_seconds'],
                                              settings['wave_interval_seconds'])):
            size = wave_size(config, difficulty=preferences['difficulty'], wave_index=index,
                             wave_multiplier=preferences['wave_multiplier'])
            counts = [size['units_per_enemy']] * size.get('spawn_sides', 3)
            if powerhouse:
                headroom = min(settings['max_wave_units'], config['wave_pressure']['max_active_units']) - sum(counts)
                for side in range(len(counts)):
                    extra = min(2, headroom)
                    counts[side] += extra
                    headroom -= extra
            per_side = str(counts[0]) if min(counts) == max(counts) else f'{min(counts)}–{max(counts)}'
            tree.insert('', 'end', values=(f'{seconds / 60:g}', size.get('spawn_sides', 3),
                        per_side, sum(counts),
                        'Capped' if size['capped'] else 'Growing'))
    except ValueError:
        tree.delete(*tree.get_children())
