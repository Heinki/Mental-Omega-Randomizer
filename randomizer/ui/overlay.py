"""Log panel and busy overlay widgets."""

from ._builder_dependencies import (
    LAUNCHER_LOG,
    WidgetTooltip,
    scrolledtext,
    tk,
    ttk,
)

def _build_log_and_overlay(self, main_frame):
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
    self.shop_debug_mission_var = tk.StringVar(value='')
    self.shop_debug_mission_codes = {}
    self.shop_debug_mission_combo = ttk.Combobox(
        log_header,
        textvariable=self.shop_debug_mission_var,
        state='readonly',
        width=32,
    )
    self.shop_debug_mission_combo.grid(
        row=0, column=2, sticky='e', padx=(8, 6)
    )
    WidgetTooltip(
        self.shop_debug_mission_combo,
        'Choose which current Shop mission the developer override completes.',
    )
    self.shop_debug_complete_button = ttk.Button(
        log_header,
        text='Developer: Complete Mission',
        command=self.on_debug_mark_complete,
    )
    self.shop_debug_complete_button.grid(row=0, column=3, sticky='e')
    WidgetTooltip(
        self.shop_debug_complete_button,
        'Shop developer override: completes the chosen current mission and grants its rewards.',
    )
    self.shop_debug_mission_combo.grid_remove()
    self.shop_debug_complete_button.grid_remove()
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
    self.sync_debug_completion_controls()

    main_frame.rowconfigure(2, weight=1)
    main_frame.rowconfigure(9, weight=0)
    # Keep wide mission/settings workspace beside narrower details panel.
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
