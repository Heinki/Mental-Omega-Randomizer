"""Purchase feedback and reusable escort-rank previews for Conquest."""

import tkinter as tk
from tkinter import ttk

from randomizer.conquest.catalogue import ESCORT_ROSTERS, ESCORT_COUNTS, escort_units


def configure_purchase_style(style, palette, dark):
    green = '#3fb950' if dark else '#1a7f37'
    grey = '#484f58' if dark else '#afb8c1'
    style.configure(
        'Conquest.Purchase.TButton', borderwidth=2, relief='raised',
        background='#163b25' if dark else '#dafbe1',
        foreground='#e6ffed' if dark else '#116329',
        bordercolor=green, lightcolor=green, darkcolor=green,
    )
    for option in ('bordercolor', 'lightcolor', 'darkcolor'):
        style.map('Conquest.Purchase.TButton', **{
            option: [('disabled', grey), ('!disabled', green)],
        })
    style.map(
        'Conquest.Purchase.TButton',
        background=[('disabled', '#292e35' if dark else '#eaeef2'),
                    ('active', '#245b35' if dark else '#aceebb'),
                    ('!disabled', '#163b25' if dark else '#dafbe1')],
        foreground=[('disabled', palette['muted']),
                    ('!disabled', '#e6ffed' if dark else '#116329')],
    )


class PurchaseCard(tk.Frame):
    """An actual Tk border remains visible across ttk themes and platforms."""

    def __init__(self, parent, *, padding=12):
        super().__init__(parent, borderwidth=0, highlightthickness=2,
                         highlightbackground='#484f58', highlightcolor='#484f58')
        self.body = ttk.Frame(self, padding=padding)
        self.body.pack(fill='both', expand=True)
        self.body.columnconfigure(0, weight=1)
        self.labels = []
        self._signature = None

    def set_available(self, available, palette, dark):
        border = ('#3fb950' if dark else '#1a7f37') if available else ('#484f58' if dark else '#afb8c1')
        foreground = palette['foreground'] if available else palette['muted']
        signature = border, foreground, palette['background']
        if signature == self._signature:
            return
        self._signature = signature
        self.configure(background=palette['background'],
                       highlightbackground=border, highlightcolor=border)
        for label in self.labels:
            label.configure(foreground=foreground)


class EscortRoster(ttk.Frame):
    """Show every cumulative rank without rebuilding rows on campaign ticks."""

    def __init__(self, parent, key):
        super().__init__(parent)
        self.key = key
        self.columnconfigure(1, weight=3)
        self.columnconfigure(2, weight=2)
        for column, title in enumerate(('Rank', 'Full escort', 'Adds at this rank')):
            ttk.Label(self, text=title, font=('Segoe UI', 9, 'bold')).grid(
                row=0, column=column, sticky='w', padx=(0, 12), pady=(0, 5))
        self.rows = []
        for rank in range(1, len(ESCORT_COUNTS[key]) + 1):
            cells = []
            for column in range(3):
                label = ttk.Label(self, width=11 if column == 0 else 1,
                                  wraplength=320, justify='left')
                label.grid(row=rank, column=column, sticky='nw' if column == 0 else 'new',
                           padx=(0, 12), pady=4)
                cells.append(label)
            self.rows.append(cells)
        self._signature = None
        self._wrap_width = None
        self._resize_after = None
        self.bind('<Configure>', self._resize, add='+')
        self.bind('<Destroy>', self._destroy, add='+')

    def _resize(self, _event=None):
        if self._resize_after is None:
            self._resize_after = self.after_idle(self._wrap_labels)

    def _wrap_labels(self):
        self._resize_after = None
        widths = max(80, self.grid_bbox(1, 0)[2] - 12), max(80, self.grid_bbox(2, 0)[2] - 12)
        if widths == self._wrap_width:
            return
        self._wrap_width = widths
        for _, full, additions in self.rows:
            full.configure(wraplength=widths[0])
            additions.configure(wraplength=widths[1])

    def _destroy(self, event):
        if event.widget is self and self._resize_after is not None:
            self.after_cancel(self._resize_after)
            self._resize_after = None

    def show_roster(self, faction, current, names, available, palette, dark):
        unit_names = tuple((kind, names.get(kind, kind)) for kind in ESCORT_ROSTERS[faction][self.key])
        signature = faction, current, available, unit_names, dark, palette['foreground'], palette['muted']
        if signature == self._signature:
            return
        self._signature = signature

        def text(units):
            return ', '.join(f'{names.get(kind, kind)} ×{count}' for kind, count in units.items())

        previous = {}
        for rank, (rank_label, full_label, added_label) in enumerate(self.rows, 1):
            full = escort_units(faction, self.key, rank)
            added = {kind: count - previous.get(kind, 0) for kind, count in full.items()
                     if count > previous.get(kind, 0)}
            if rank == current:
                status = 'Current'
                color = '#79c0ff' if dark else '#0969da'
            elif rank == current + 1:
                status = 'Next'
                color = ('#7ee787' if dark else '#1a7f37') if available else palette['muted']
            else:
                status = 'Owned' if rank < current else 'Later'
                color = palette['foreground'] if rank < current else palette['muted']
            rank_label.configure(text=f'{rank} · {status}', foreground=color,
                                 font=('Segoe UI', 9, 'bold') if status in ('Current', 'Next') else ('Segoe UI', 9))
            full_label.configure(text=text(full), foreground=color)
            added_label.configure(text=text(added), foreground=color)
            previous = full
