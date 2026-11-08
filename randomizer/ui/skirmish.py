"""Bounded faction dropdown shared by Shop cards and mission Details.

Uses the same label-and-readonly-dropdown layout as DTA's PreconditionPicker.
"""

import tkinter as tk
from tkinter import ttk

from randomizer.skirmish_factions import mission_countries, selected_mission
from randomizer.ui.tooltips import WidgetTooltip
from randomizer.ui.viewport import fit_dialog


class SkirmishFactionPicker(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.mission = None
        self.countries = {}
        self.columnconfigure(0, weight=1, minsize=0)
        ttk.Label(self, text='Skirmish faction').grid(row=0, column=0, sticky='w')
        self.value = tk.StringVar(self)
        self.combo = ttk.Combobox(self, textvariable=self.value, state='readonly',
                                  width=1, height=12)
        self.combo.grid(row=1, column=0, sticky='ew')
        self.combo.bind('<<ComboboxSelected>>', self._save)
        self.tooltip = WidgetTooltip(
            self.combo, 'Choose your faction before launching this skirmish. '
            'The chosen faction supplies its native MCV, base and technology. '
            'Run unlocks, purchases, buffs and rewards still apply.')

    def set_mission(self, mission, *, editable=True):
        self.mission = mission
        if not mission or not mission.get('skirmish'):
            self.grid_remove()
            return
        self.countries = mission_countries(mission)
        current = selected_mission(mission, self.app.config.get('skirmish_factions', {}))
        self.combo.configure(values=tuple(self.countries),
                             state='readonly' if editable else 'disabled')
        self.value.set(next(label for label, country in self.countries.items()
                            if country == current['skirmish_country']))
        self.grid()

    def _save(self, _event=None):
        country = self.countries.get(self.value.get())
        if not country or not self.mission or self.combo.instate(['disabled']):
            return
        selections = self.app.config.get('skirmish_factions')
        if not isinstance(selections, dict):
            selections = self.app.config['skirmish_factions'] = {}
        selections[self.mission['scenario']] = country
        self.app.save_current_launcher_config()
        self.app.refresh_progress_view()
        self.app.refresh_shop_mode()


def choose_skirmish_faction(app, mission):
    """Let a committed Blind Choice select its faction without revealing offers."""
    window = tk.Toplevel(app)
    window.title('Skirmish faction')
    window.transient(app)
    frame = ttk.Frame(window, padding=12)
    frame.pack(fill='both', expand=True)
    frame.columnconfigure(0, weight=1)
    picker = SkirmishFactionPicker(frame, app)
    picker.grid(row=0, column=0, sticky='ew')
    picker.set_mission(mission)
    result = None

    def launch():
        nonlocal result
        result = selected_mission(mission, app.config.get('skirmish_factions', {}))
        window.destroy()

    buttons = ttk.Frame(frame)
    buttons.grid(row=1, column=0, sticky='e', pady=(12, 0))
    ttk.Button(buttons, text='Launch', command=launch).pack(side='left', padx=(0, 8))
    ttk.Button(buttons, text='Cancel', command=window.destroy).pack(side='left')
    window.bind('<Escape>', lambda _event: window.destroy())
    fit_dialog(window, frame, width=480, height=240)
    window.wait_visibility()
    window.grab_set()
    picker.combo.focus_set()
    app.wait_window(window)
    return result
