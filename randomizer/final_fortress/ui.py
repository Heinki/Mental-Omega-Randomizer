"""Compact standalone play controls and on-demand Final Fortress help."""

import tkinter as tk
from tkinter import ttk
from randomizer.ui.config import GAME_SPEEDS

from .pressure import wave_size
from .reporting import reward_report


def build_final_fortress_tab(app, notebook):
    tab = ttk.Frame(notebook, padding=16)
    app.final_fortress_tab = tab
    # The game-mode controller inserts this frame only when selected.
    tab.columnconfigure(0, weight=1)
    tab.rowconfigure(2, weight=1)
    title = ttk.Frame(tab)
    title.grid(row=0, column=0, sticky='ew', pady=(0, 12))
    title.columnconfigure(0, weight=1)
    ttk.Label(title, text='Final Fortress', font=('Segoe UI', 18, 'bold')).grid(
        row=0, column=0, sticky='w')
    from .profiles import PROFILE_PATHS
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
        ttk.Label(title, textvariable=app.fortress_coop_status_var,
                  wraplength=900, justify='left', style='Muted.TLabel').grid(
            row=1, column=0, columnspan=3, sticky='w', pady=(6, 0))

    progression = ttk.Notebook(tab)
    app.final_fortress_progression_tabs = progression
    progression.grid(row=2, column=0, sticky='nsew', pady=(12, 0))
    perks = ttk.Frame(progression, padding=12)
    challenges = ttk.Frame(progression, padding=12)
    progression.add(perks, text='Permanent perks')
    progression.add(challenges, text='Challenge')
    perks.columnconfigure(0, weight=1)
    perks.rowconfigure(1, weight=1)
    ttk.Label(perks, textvariable=app.final_fortress_gems_var).grid(
        row=0, column=0, sticky='w', pady=(0, 8))
    panes = ttk.Panedwindow(perks, orient='horizontal')
    panes.grid(row=1, column=0, sticky='nsew')
    listing = ttk.Frame(panes)
    listing.columnconfigure(0, weight=1)
    listing.rowconfigure(0, weight=1)
    panes.add(listing, weight=2)
    app.final_fortress_perks_tree = ttk.Treeview(
        listing, columns=('name', 'cost', 'status', 'effect'),
        displaycolumns=('name', 'cost', 'status'), show='headings', selectmode='browse', height=8)
    for column, label, width in (('name', 'Perk', 180), ('cost', 'Next rank cost', 190),
                                  ('status', 'Rank / status', 145), ('effect', 'Effect', 450)):
        app.final_fortress_perks_tree.heading(column, text=label)
        app.final_fortress_perks_tree.column(column, width=width, stretch=column == 'name')
    app.final_fortress_perks_tree.grid(row=0, column=0, sticky='nsew')
    scroll = ttk.Scrollbar(listing, command=app.final_fortress_perks_tree.yview)
    scroll.grid(row=0, column=1, sticky='ns')
    app.final_fortress_perks_tree.configure(yscrollcommand=scroll.set)
    app.final_fortress_perks_tree.bind('<<TreeviewSelect>>', app.select_final_fortress_perk)
    app.final_fortress_perks_tree.bind('<Return>', lambda _event: app.buy_final_fortress_perk())
    details = ttk.LabelFrame(panes, text='Rank effects', padding=(10, 4))
    details.columnconfigure(0, weight=1)
    details.rowconfigure(0, weight=1)
    panes.add(details, weight=3)
    palette = app.ui_palette()
    app.final_fortress_perk_details = tk.Text(
        details, width=45, height=1, wrap='word', relief='flat', borderwidth=0,
        font=('Segoe UI', 10), state='disabled',
        background=palette['background'], foreground=palette['foreground'],
        selectbackground=palette['select'], selectforeground=palette['select_foreground'])
    app.final_fortress_perk_details.grid(row=0, column=0, sticky='nsew')
    buttons = ttk.Frame(perks)
    buttons.grid(row=2, column=0, sticky='e', pady=(8, 0))
    app.final_fortress_buy_perk_button = ttk.Button(
        buttons, text='Buy / upgrade', command=app.buy_final_fortress_perk)
    app.final_fortress_buy_perk_button.pack(side='left', padx=(0, 8))
    app.final_fortress_toggle_perk_button = ttk.Button(
        buttons, text='Enable / disable', command=app.toggle_final_fortress_perk)
    app.final_fortress_toggle_perk_button.pack(side='left')
    challenges.columnconfigure(0, weight=1)
    challenges.rowconfigure(0, weight=1)
    challenge_panes = ttk.Panedwindow(challenges, orient='horizontal')
    challenge_panes.grid(row=0, column=0, sticky='nsew')
    challenge_listing = ttk.Frame(challenge_panes)
    challenge_listing.columnconfigure(0, weight=1)
    challenge_listing.rowconfigure(0, weight=1)
    challenge_panes.add(challenge_listing, weight=3)
    app.final_fortress_challenge_tree = ttk.Treeview(challenge_listing,
        columns=('enabled', 'name', 'decrease', 'stacks', 'increase', 'gems', 'effect'),
        displaycolumns=('enabled', 'name', 'decrease', 'stacks', 'increase', 'gems'),
        show='headings', selectmode='extended', height=6)
    for key, title_text, width in (('enabled', 'Enabled', 70), ('name', 'Enemy modifier', 210),
                                 ('decrease', '', 38), ('stacks', 'Stacks', 65),
                                 ('increase', '', 38), ('gems', 'Victory Defensive Points', 190),
                                 ('effect', 'Effect at selected stacks', 360)):
        app.final_fortress_challenge_tree.heading(key, text=title_text)
        app.final_fortress_challenge_tree.column(key, width=width, stretch=key == 'name')
    for key in ('decrease', 'stacks', 'increase'):
        app.final_fortress_challenge_tree.column(key, anchor='center')
    app.final_fortress_challenge_tree.grid(row=0, column=0, sticky='nsew')
    scroll = ttk.Scrollbar(challenge_listing, command=app.final_fortress_challenge_tree.yview)
    scroll.grid(row=0, column=1, sticky='ns')
    app.final_fortress_challenge_tree.configure(yscrollcommand=scroll.set)
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
    challenge_panes.add(challenge_details, weight=2)
    app.final_fortress_challenge_details = tk.Text(
        challenge_details, width=40, height=1, wrap='word', relief='flat', borderwidth=0,
        font=('Segoe UI', 10), state='disabled',
        background=palette['background'], foreground=palette['foreground'],
        selectbackground=palette['select'], selectforeground=palette['select_foreground'])
    app.final_fortress_challenge_details.grid(row=0, column=0, sticky='nsew')
    controls = ttk.Frame(challenges)
    controls.grid(row=1, column=0, sticky='ew', pady=(8, 0))
    ttk.Button(controls, text='Select all', command=app.select_all_final_fortress_challenges).pack(side='left')
    ttk.Button(controls, text='Clear selection', command=app.clear_final_fortress_challenge_selection).pack(
        side='left', padx=(8, 0))
    app.final_fortress_challenge_enable_button = ttk.Button(
        controls, text='Enable selected', state='disabled',
        command=lambda: app.set_final_fortress_challenges_enabled(True))
    app.final_fortress_challenge_enable_button.pack(side='left', padx=(8, 0))
    app.final_fortress_challenge_disable_button = ttk.Button(
        controls, text='Disable selected', state='disabled',
        command=lambda: app.set_final_fortress_challenges_enabled(False))
    app.final_fortress_challenge_disable_button.pack(side='left', padx=(8, 0))
    app.final_fortress_stack_max_button = ttk.Button(
        controls, text='Max stacks', state='disabled', command=app.max_final_fortress_challenge_stacks)
    app.final_fortress_stack_max_button.pack(side='left', padx=(8, 0))
    ttk.Label(controls, text='Drag / Ctrl / Alt to select · Ctrl+A: all', style='Muted.TLabel').pack(
        side='left', padx=(16, 0))

    results = ttk.Frame(progression, padding=12)
    app.final_fortress_results_tab = results
    progression.add(results, text='Run results')
    results.columnconfigure(0, weight=1)
    results.rowconfigure(1, weight=1)
    ttk.Label(results, textvariable=app.final_fortress_result_var, font=('Segoe UI', 12, 'bold')).grid(
        row=0, column=0, sticky='w', pady=(0, 8))
    app.final_fortress_results_tree = ttk.Treeview(results,
        columns=('source', 'gems', 'detail'), show='headings', height=6)
    for key, title_text, width in (('source', 'Reward source', 240), ('gems', 'Defensive Points', 140),
                                 ('detail', 'Result / crate reward', 450)):
        app.final_fortress_results_tree.heading(key, text=title_text)
        app.final_fortress_results_tree.column(key, width=width, stretch=key == 'detail')
    app.final_fortress_results_tree.grid(row=1, column=0, sticky='nsew')
    scroll = ttk.Scrollbar(results, command=app.final_fortress_results_tree.yview)
    scroll.grid(row=1, column=1, sticky='ns')
    app.final_fortress_results_tree.configure(yscrollcommand=scroll.set)

    setup = ttk.LabelFrame(tab, text='Defense setup', padding=12)
    setup.grid(row=1, column=0, sticky='new')
    setup.columnconfigure(1, weight=1)
    app.final_fortress_setup_combos = []
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
        ('Game speed', app.game_speed_var, tuple(label for label, _ in GAME_SPEEDS),
         app.on_game_speed_changed),
    )):
        ttk.Label(setup, text=label).grid(row=row, column=0, sticky='w', padx=(0, 12), pady=5)
        combo = ttk.Combobox(setup, textvariable=variable, values=values, state='readonly')
        app.final_fortress_setup_combos.append(combo)
        combo.grid(row=row, column=1, sticky='ew', pady=5)
        if handler is not None:
            combo.bind('<<ComboboxSelected>>', handler)

    app.final_fortress_mental_ai_boost_check = ttk.Checkbutton(
                    setup, text='Mental AI Boost (enemy and allied AI)',
                    variable=app.final_fortress_mental_ai_boost_var,
                    command=app.on_final_fortress_mental_ai_boost_changed)
    app.final_fortress_mental_ai_boost_check.grid(row=6, column=1, sticky='w', pady=5)

    launch = ttk.Frame(tab)
    launch.grid(row=3, column=0, sticky='ew', pady=(12, 0))
    launch.columnconfigure(0, weight=1)
    ttk.Label(launch, textvariable=app.final_fortress_status_var).grid(
        row=0, column=0, sticky='w', padx=(0, 12))
    app.final_fortress_launch_button = ttk.Button(
        launch, text='Launch Final Fortress', command=app.launch_final_fortress,
        state='disabled', style='Launch.TButton')
    app.final_fortress_launch_button.grid(row=0, column=1, sticky='e')
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
    window.geometry('740x420')
    window.minsize(480, 300)
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
        row=1, column=0, columnspan=2, sticky='e', pady=(12, 0))
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
        tree.column(column, width=110, anchor='center')
    tree.grid(row=0, column=0, sticky='nsew')
    scrollbar = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
    scrollbar.grid(row=0, column=1, sticky='ns')
    tree.configure(yscrollcommand=scrollbar.set)
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
