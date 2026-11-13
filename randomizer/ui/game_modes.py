"""Dedicated mode selection using the launcher's existing themed widgets."""

from tkinter import ttk

from .viewport import ScrollableViewport


MODE_DESCRIPTIONS = {
    'Conquest': 'Conquer territories solo or with up to four players over ZeroTier. Build personal armies, research upgrades, and fight skirmishes or autobattles.',
    'Classic': 'Follow the installed campaign order, opening one mission at a time.',
    'Mission List': 'Play through missions in a randomized linear order.',
    'Grid Mode': 'Explore a randomized mission board through neighboring victories.',
    'Shop Mode': 'Configure a roguelike run with a shop, purchases, and loadouts.',
    'Final Fortress': 'Set up survival defense with waves, challenges, and permanent perks.',
}


def build_game_mode_navigation(app):
    """Build both navigation surfaces once; keep existing settings widgets alive."""
    app.rowconfigure(0, weight=0)
    app.rowconfigure(1, weight=1)
    app.main_frame.grid_configure(row=1)

    navigation = app.game_mode_navigation = ttk.Frame(app, padding=(12, 10, 12, 0))
    navigation.columnconfigure(1, weight=1)
    app.game_mode_back_button = ttk.Button(
        navigation, text='Back to Game Modes', command=app.show_game_mode_selection,
    )
    app.game_mode_back_button.grid(row=0, column=0, sticky='w', padx=(0, 12))
    app.game_mode_page_label = ttk.Label(navigation, font=('Segoe UI', 12, 'bold'))
    app.game_mode_page_label.grid(row=0, column=1, sticky='ew')

    selection = app.game_mode_selection_frame = ttk.Frame(app, padding=12)
    selection.columnconfigure(0, weight=1)
    selection.rowconfigure(1, weight=1)
    heading = ttk.Label(
        selection, text=app._full_window_heading, font=('Segoe UI', 14, 'bold'),
        anchor='center', justify='center', wraplength=420,
    )
    heading.grid(row=0, column=0, sticky='ew', pady=(0, 8))

    viewport = app.game_mode_selection_viewport = ScrollableViewport(selection, padding=4)
    app.game_mode_selection_canvas = viewport.canvas
    viewport.canvas.configure(background=app.ui_palette()['canvas'])
    viewport.grid(row=1, column=0, sticky='nsew')
    viewport.content.columnconfigure(0, weight=1)
    viewport.content.rowconfigure(0, weight=1)
    viewport.content.rowconfigure(2, weight=1)
    menu = ttk.Frame(viewport.content)
    menu.grid(row=1, column=0)
    menu.columnconfigure(0, weight=1)
    title = ttk.Label(
        menu, text='Choose a Game Mode', font=('Segoe UI', 18, 'bold'),
        anchor='center', justify='center',
    )
    title.grid(row=0, column=0, sticky='ew', pady=(0, 6))
    app.game_mode_selection_hint = ttk.Label(
        menu, style='Muted.TLabel', anchor='center', justify='center', wraplength=420,
    )
    app.game_mode_selection_hint.grid(row=1, column=0, sticky='ew', pady=(0, 12))
    app.game_mode_cards = {}
    app.game_mode_buttons = {}
    app.game_mode_descriptions = {}
    for mode in app.game_mode_choices:
        card = ttk.Frame(menu, padding=12, relief='ridge', borderwidth=1)
        card.columnconfigure(0, weight=1)
        button = ttk.Button(card, text=mode, style='Launch.TButton',
                            command=lambda choice=mode: app.open_game_mode_settings(choice))
        button.grid(row=0, column=0, sticky='ew')
        archipelago_support = (
            'Archipelago: Supported'
            if mode in app._ARCHIPELAGO_PROGRESSION_MODES
            else 'Archipelago: Not supported (standalone only)'
        )
        description = ttk.Label(
            card, text=f'{MODE_DESCRIPTIONS.get(mode, f"Configure {mode}.")}\n{archipelago_support}',
            style='Muted.TLabel', wraplength=320, anchor='center', justify='center',
        )
        description.grid(row=1, column=0, sticky='ew', pady=(8, 0))
        app.game_mode_cards[mode] = card
        app.game_mode_buttons[mode] = button
        app.game_mode_descriptions[mode] = description

    def layout(width):
        modes = app.available_game_modes()
        scale = app.winfo_fpixels('1i') / 96
        signature = (modes, width, scale)
        if signature == getattr(app, '_game_mode_cards_layout', None):
            return
        app._game_mode_cards_layout = signature
        menu_width = max(240, min(round(640 * scale), width - 24))
        menu.columnconfigure(0, minsize=menu_width)
        heading.configure(wraplength=max(240, width - 24))
        title.configure(wraplength=menu_width)
        app.game_mode_selection_hint.configure(wraplength=menu_width - 16)
        for card in app.game_mode_cards.values():
            card.grid_forget()
        for index, mode in enumerate(modes):
            app.game_mode_cards[mode].grid(
                row=index + 2, column=0, sticky='ew', padx=4, pady=4,
            )
            app.game_mode_descriptions[mode].configure(
                wraplength=menu_width - 48)

    viewport.layout = layout
    viewport.bind_controls()
