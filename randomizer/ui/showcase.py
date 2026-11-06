"""Shared Advanced-style cards and the permanent Shop roster showcase."""

import tkinter as tk
from tkinter import ttk

from .config import FACTION_TILE_COLORS
from .tooltips import WidgetTooltip
from .viewport import ScrollableViewport


def scale_showcase_photo(photo):
    """Use Advanced's cameo scale for every showcase."""
    if photo.width() <= 70 and photo.height() <= 55:
        return photo.zoom(4, 4).subsample(3, 3)
    factor = max(1, (photo.width() + 87) // 88, (photo.height() + 55) // 56)
    return photo.subsample(factor, factor) if factor > 1 else photo


def draw_showcase_card(
    parent, row, column, entry, *, photo=None, excluded=False,
    disabled=False, command=None,
):
    """Draw the same cameo, faction tile, label, and exclusion treatment."""
    width, height = 102, 90
    center = 51
    muted = excluded or disabled
    border = '#777777' if muted else '#4d92d8'
    faction = entry.get('faction', '')
    card = tk.Canvas(
        parent, width=width, height=height, highlightthickness=2,
        highlightbackground=border, highlightcolor=border,
        background=FACTION_TILE_COLORS.get(faction, '#315b82'),
        cursor='hand2' if command else 'arrow', takefocus=bool(command),
    )
    card.grid(row=row, column=column, padx=4, pady=4, sticky='nw')
    card.photo = photo
    if photo is not None:
        card.create_image(center, 31, image=photo, anchor='center')
    else:
        card.create_text(
            center, 31, text=faction or '?', fill='#ffffff',
            font=('Segoe UI', 10, 'bold'), width=width - 8, justify='center',
        )
    card.create_rectangle(0, 62, width, height, fill='#151a20', outline='')
    card.create_text(
        center, 76, text=entry['label'],
        fill='#aeb4bb' if excluded else '#ffffff',
        font=('Segoe UI', 8, 'bold'), width=width - 6, justify='center',
    )
    if muted:
        card.create_rectangle(
            0, 0, width, height,
            fill='#777777', outline='', stipple='gray50',
        )
        card.create_text(
            center, 44, text='EXCLUDED' if excluded else 'DISABLED',
            fill='#ffffff', font=('Segoe UI', 8, 'bold'),
        )
    if command is not None:
        def activate(_event):
            card.focus_set()
            command()
            return 'break'

        card.bind('<Button-1>', activate)
        card.bind('<space>', activate)
        card.bind('<Return>', activate)
    return card


def build_showcase_selectors(controls, choices, *, selected=None, all_items=None, special=None):
    """Build faction/category selectors, with optional Advanced bulk actions."""
    selector_frame = ttk.Frame(controls)
    selector_frame.grid(row=0, column=0, sticky='w')
    variables = {}
    for row, (group, title) in enumerate((('faction', 'Faction:'), ('category', 'Category:'))):
        values = [(value, label) for kind, value, label in choices if kind == group]
        if group == 'category':
            values.append(('all', 'All'))
        variable = tk.StringVar(master=controls, value=values[0][0] if values else '')
        variables[group] = variable
        pady = (6, 0) if row else 0
        ttk.Label(selector_frame, text=title).grid(
            row=row, column=0, sticky='w', padx=(0, 4), pady=pady,
        )
        for column, (value, label) in enumerate(values, start=1):
            ttk.Radiobutton(
                selector_frame, text=label, value=value,
                variable=variable, padding=(0, 0),
            ).grid(row=row, column=column, sticky='w', padx=(0, 2), pady=pady)
    if selected is None:
        return variables, []
    ttk.Separator(controls, orient='vertical').grid(
        row=0, column=1, sticky='ns', padx=(6, 6),
    )
    actions = ttk.Frame(controls)
    actions.grid(row=0, column=2, sticky='n')
    buttons = []
    for index, (label, callback) in enumerate((
        ('Selected:', lambda include: selected(
            variables['faction'].get(), variables['category'].get(), include,
        )),
        ('All:', all_items),
        ('Special:', special),
    )):
        if index:
            ttk.Separator(actions, orient='vertical').pack(
                side='left', fill='y', padx=(2, 6) if index == 1 else (6, 6),
            )
        ttk.Label(actions, text=label).pack(side='left', padx=(0, 4))
        for include, text in ((True, 'Include'), (False, 'Exclude')):
            button = ttk.Button(
                actions, text=text, width=7, padding=(6, 3),
                command=lambda value=include, action=callback: action(value),
            )
            button.pack(side='left', padx=(0, 4) if include else 0)
            buttons.append(button)
    return variables, buttons


def build_showcase_search(controls, search_var):
    """Build the full-width search row used by Advanced."""
    row = ttk.Frame(controls)
    row.grid(row=1, column=0, columnspan=3, sticky='ew', pady=(6, 0))
    row.columnconfigure(1, weight=1)
    ttk.Label(row, text='Search:').grid(row=0, column=0, sticky='w', padx=(0, 6))
    ttk.Entry(row, textvariable=search_var).grid(row=0, column=1, sticky='ew', padx=(0, 4))
    ttk.Button(row, text='Clear', width=8, command=lambda: search_var.set('')).grid(row=0, column=2)


class RosterShowcase(ttk.Frame):
    """Scrollable responsive cards; selection remains owned by the controller."""

    def __init__(self, parent, *, command, refresh, search_var, choices, palette):
        super().__init__(parent)
        self.command = command
        self.refresh = refresh
        self.search_var = search_var
        self.cards = []
        self._photos = {}
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        controls = ttk.LabelFrame(self, text='Filters', padding=(8, 6, 8, 6))
        controls.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 6))
        self.group_vars, _buttons = build_showcase_selectors(
            controls, [*choices, ('faction', 'all', 'All')],
        )
        for variable in self.group_vars.values():
            variable.set('all')
        build_showcase_search(controls, search_var)
        self.canvas = tk.Canvas(
            self, width=1, height=338, borderwidth=0, highlightthickness=0,
            background=palette['canvas'],
            yscrollincrement=28,
        )
        scrollbar = ttk.Scrollbar(self, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.grid(row=1, column=0, sticky='nsew')
        scrollbar.grid(row=1, column=1, sticky='ns')
        self.content = ttk.Frame(self.canvas, padding=4)
        self.window = self.canvas.create_window(
            (0, 0), window=self.content, anchor='nw',
        )
        self.content.bind('<Configure>', self._update_scrollregion)
        self.canvas.bind('<Configure>', self._configure)
        self._content_scroll_handler = self._mousewheel
        for variable in self.group_vars.values():
            variable.trace_add('write', self._filter_changed)

    def _filter_changed(self, *_args):
        self.canvas.yview_moveto(0)
        self.refresh()

    def _update_scrollregion(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def _configure(self, event):
        self.canvas.itemconfigure(self.window, width=event.width)
        self._layout_cards(event.width)

    def _layout_cards(self, width):
        columns = max(1, width // 112)
        for index, card in enumerate(self.cards):
            card.grid_configure(row=index // columns, column=index % columns)

    def _mousewheel(self, event):
        delta, number = getattr(event, 'delta', 0), getattr(event, 'num', 0)
        if not delta and number not in (4, 5):
            return
        direction = -1 if delta > 0 or number == 4 else 1
        first, last = self.canvas.yview()
        if (direction < 0 and first > 0) or (direction > 0 and last < 1):
            self.canvas.yview_scroll(
                direction * max(1, abs(int(delta / 120))), 'units',
            )
            return 'break'
        parent = self.master
        while parent is not None:
            if isinstance(parent, ScrollableViewport):
                return parent._mousewheel(event)
            parent = parent.master

    def set_items(self, items, *, active_run=False):
        """Render authoritative states without reading selection from widgets."""
        focus = self.focus_get()
        focused_key = getattr(focus, 'roster_key', None)
        for child in self.content.winfo_children():
            child.destroy()
        self.cards = []
        query = self.search_var.get().strip().casefold()
        faction = self.group_vars['faction'].get()
        category = self.group_vars['category'].get()
        for item in items:
            if faction != 'all' and item['faction'] != faction:
                continue
            if category != 'all' and item['category'] != category:
                continue
            if query and query not in (
                item['label'] + ' ' + item['key'] + ' ' + item['target_id']
            ).casefold():
                continue
            included = item['included']
            status = 'Included' if included else 'Excluded'
            locked = active_run or item.get('locked', False)
            if locked:
                status += ' · Locked'
            photo = item.get('photo')
            if photo is not None:
                photo_key = str(photo)
                if photo_key not in self._photos:
                    self._photos[photo_key] = scale_showcase_photo(photo)
                photo = self._photos[photo_key]
            card = draw_showcase_card(
                self.content, 0, 0, item, photo=photo,
                excluded=not included,
                command=None if locked else (
                    lambda reward_id=item['id']: self.command(reward_id)
                ),
            )
            card.roster_key = item['key']
            self.cards.append(card)
            roster = 'Active run roster' if active_run else 'Next run roster'
            if active_run:
                explanation = 'Selection is locked during the active run.'
            elif locked:
                explanation = item['reason']
            else:
                explanation = (
                    'Click or press Space / Enter to include or exclude. '
                    'Excluding never removes permanent ownership.'
                )
            WidgetTooltip(
                card, f"{item['label']}\n{item['tier']} · {item['source']}\n"
                f'{roster}: {status}\n{explanation}',
            )
            if item['key'] == focused_key:
                card.focus_set()
        if not self.cards:
            ttk.Label(
                self.content,
                text='No permanent unlocks match the search or current roster restrictions.',
                style='Muted.TLabel', wraplength=480, padding=12,
            ).grid(row=0, column=0, sticky='w')
        self._layout_cards(self.canvas.winfo_width())
        self.after_idle(self._update_scrollregion)
