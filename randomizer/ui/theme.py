"""Tk theme application for the launcher window."""


def apply_color_mode(self):
    """Apply the current launcher palette to all constructed widgets."""
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
    shop_colors = {
        'Stage': '#79c0ff' if self.dark_mode_var.get() else '#0969da',
        'Status': '#7ee787' if self.dark_mode_var.get() else '#1a7f37',
        'Ore': '#f2cc60' if self.dark_mode_var.get() else '#9a6700',
        'Gem': '#d2a8ff' if self.dark_mode_var.get() else '#8250df',
        'Reroll': '#76e3ea' if self.dark_mode_var.get() else '#096b72',
        'Reward': '#f2cc60' if self.dark_mode_var.get() else '#825800',
        'Help': '#79c0ff' if self.dark_mode_var.get() else '#0550ae',
        'PlayerBuff': '#7ee787' if self.dark_mode_var.get() else '#1a7f37',
        'EnemyBuff': '#ff7b72' if self.dark_mode_var.get() else '#cf222e',
    }
    for name, color in shop_colors.items():
        style.configure(
            f'Shop.{name}.TLabel', background=background, foreground=color
        )
    style.configure(
        'Archipelago.Disconnected.TLabel',
        background=background,
        foreground='#ff6b6b' if self.dark_mode_var.get() else '#b00020',
    )
    style.configure(
        'Archipelago.Connected.TLabel',
        background=background,
        foreground='#55d67a' if self.dark_mode_var.get() else '#087a2f',
    )
    style.configure(
        'Archipelago.Waiting.TLabel',
        background=background,
        foreground='#f0c75e' if self.dark_mode_var.get() else '#8a5a00',
    )
    style.configure(
        'Error.TLabel',
        background=background,
        foreground='#ff7b72' if self.dark_mode_var.get() else '#b00020',
    )
    # ttk's canonical style name uses a lowercase "f". The old spelling
    # configured an unused style and left Settings group interiors light.
    style.configure('TLabelframe', background=background, bordercolor=border)
    style.configure('TLabelframe.Label', background=background, foreground=foreground)
    style.configure('TCheckbutton', background=background, foreground=foreground)
    self.ensure_checkbutton_indicator()
    style.configure('TRadiobutton', background=background, foreground=foreground)
    style.configure('TButton', background=panel, foreground=foreground, bordercolor=border)
    style.configure('Launch.TButton', background=panel, foreground=foreground, bordercolor=border)
    style.configure(
        'Danger.TButton',
        background='#5c2327' if self.dark_mode_var.get() else '#ffebe9',
        foreground='#ffb3b8' if self.dark_mode_var.get() else '#cf222e',
        bordercolor='#f85149' if self.dark_mode_var.get() else '#cf222e',
    )
    style.map(
        'Danger.TButton',
        background=[
            ('disabled', panel),
            ('active', '#8b3036' if self.dark_mode_var.get() else '#ffcecb'),
        ],
        foreground=[('disabled', palette['muted'])],
    )
    style.map(
        'TButton',
        background=[
            ('disabled', panel), ('active', selected), ('pressed', selected),
        ],
        foreground=[
            ('disabled', foreground),
            ('active', selected_foreground),
            ('pressed', selected_foreground),
        ],
    )
    style.map(
        'TCheckbutton',
        background=[('disabled', background), ('active', background)],
        foreground=[('disabled', foreground), ('active', foreground)],
    )
    style.map(
        'TRadiobutton',
        background=[('disabled', background), ('active', background)],
        foreground=[('disabled', foreground), ('active', foreground)],
    )
    style.configure('TEntry', fieldbackground=field, foreground=foreground, insertcolor=foreground)
    style.configure('TSpinbox', fieldbackground=field, foreground=foreground, arrowcolor=foreground)
    style.map(
        'TEntry',
        fieldbackground=[('disabled', field)],
        foreground=[('disabled', foreground)],
    )
    style.map(
        'TSpinbox',
        fieldbackground=[('disabled', field)],
        background=[('disabled', panel)],
        foreground=[('disabled', foreground)],
        arrowcolor=[('disabled', foreground)],
    )
    style.configure(
        'TCombobox',
        fieldbackground=field,
        background=panel,
        foreground=foreground,
        arrowcolor=foreground,
    )
    # ttk combobox popdowns are Tk Listboxes, not ttk widgets. Keep their
    # palette aligned with the themed field instead of using native light
    # colors in dark mode.
    self.option_add('*TCombobox*Listbox.background', field)
    self.option_add('*TCombobox*Listbox.foreground', foreground)
    self.option_add('*TCombobox*Listbox.selectBackground', selected)
    self.option_add(
        '*TCombobox*Listbox.selectForeground', selected_foreground
    )
    for combo_map_name in (
        'advanced_unit_bulk_buff_combos',
        'advanced_power_bulk_buff_combos',
    ):
        for combo in getattr(self, combo_map_name, {}).values():
            try:
                popdown = self.tk.call(
                    'ttk::combobox::PopdownWindow', str(combo)
                )
                listbox = f'{popdown}.f.l'
                self.tk.call(
                    listbox,
                    'configure',
                    '-background', field,
                    '-foreground', foreground,
                    '-selectbackground', selected,
                    '-selectforeground', selected_foreground,
                )
            except Exception:
                pass
    style.map(
        'TCombobox',
        fieldbackground=[('disabled', field), ('readonly', field)],
        background=[('disabled', panel)],
        foreground=[('disabled', foreground), ('readonly', foreground)],
        arrowcolor=[('disabled', foreground)],
        selectbackground=[('readonly', selected)],
        selectforeground=[('readonly', selected_foreground)],
    )
    style.configure('TNotebook', background=background, bordercolor=border)
    style.configure(
        'TNotebook.Tab',
        background=panel,
        foreground=foreground,
        padding=(8, 6),
    )
    style.map(
        'TNotebook.Tab',
        background=[
            ('selected', selected),
            ('active', palette['canvas']),
            ('disabled', panel),
        ],
        foreground=[
            ('selected', selected_foreground),
            ('active', foreground),
            ('disabled', palette['muted']),
        ],
        padding=[('selected', (8, 6)), ('active', (8, 6))],
    )
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
        background=[
            ('selected', selected),
            ('active', palette['canvas']),
            ('disabled', panel),
        ],
        foreground=[
            ('selected', selected_foreground),
            ('active', foreground),
            ('disabled', palette['muted']),
        ],
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
        background=[
            ('selected', selected),
            ('active', palette['canvas']),
            ('disabled', panel),
        ],
        foreground=[
            ('selected', selected_foreground),
            ('active', foreground),
            ('disabled', palette['muted']),
        ],
        padding=[('selected', (7, 7)), ('active', (7, 7))],
    )
    style.configure(
        'Treeview',
        background=field,
        fieldbackground=field,
        foreground=foreground,
        bordercolor=border,
    )
    style.configure('StartingUnlocks.Treeview', rowheight=52)
    style.configure('ShopCameo.Treeview', rowheight=52)
    style.map(
        'Treeview',
        background=[('selected', selected)],
        foreground=[('selected', selected_foreground)],
    )
    style.configure('Treeview.Heading', background=panel, foreground=foreground, bordercolor=border)
    style.map('Treeview.Heading', background=[('active', palette['canvas'])])
    if hasattr(self, 'configure_shop_tree_tags'):
        self.configure_shop_tree_tags()
    style.configure(
        'TScrollbar',
        background=panel,
        troughcolor=background,
        bordercolor=border,
        arrowcolor=foreground,
    )

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
    if hasattr(self, 'enemy_buff_catalogue_frame'):
        self._enemy_buffs_view_dirty = True
        if self.enemy_buffs_view_visible():
            self.after_idle(self.refresh_enemy_buffs_view)
    for canvas_name in ('settings_canvas', 'grid_canvas', 'enemy_buffs_canvas'):
        canvas = getattr(self, canvas_name, None)
        if canvas is not None:
            canvas.configure(background=palette['canvas'])
    for canvas in getattr(self, 'advanced_pool_canvases', {}).values():
        canvas.configure(background=palette['canvas'])
    for slider in getattr(self, 'reward_weight_slider_controls', ()):
        slider.refresh_theme(palette)
    for text_name in (
        'rewards_text', 'unlocks_text', 'archipelago_history_text'
    ):
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
        self.log_text.tag_config(
            'error',
            foreground='#ff7b72' if self.dark_mode_var.get() else '#b00020',
        )
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
