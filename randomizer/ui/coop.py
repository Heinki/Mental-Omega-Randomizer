"""Compact DTA-style co-op controls for launcher settings."""

import tkinter as tk
from tkinter import ttk


def build_coop_controls(self, parent, row, *, shop=False):
    """Group mode, player count, connection button and help below appearance."""
    frame = ttk.Frame(parent)
    frame.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(8, 0))
    toggle = ttk.Checkbutton(
        frame, text='Co-op mode (experimental)', variable=self.coop_mode_var,
        command=self.on_coop_mode_changed,
    )
    toggle.grid(row=0, column=0, sticky='w')
    ttk.Label(frame, text='Players').grid(row=0, column=1, padx=(12, 4))
    if not hasattr(self, 'coop_player_count_var'):
        # Mental Omega currently supports native two-player co-op maps only.
        self.coop_player_count_var = tk.StringVar(master=self, value='2')
    count = ttk.Combobox(
        frame, textvariable=self.coop_player_count_var, values=('2',),
        state='readonly', width=3,
    )
    count.grid(row=0, column=2)
    connect = ttk.Button(
        frame, text='Co-op Connection…', command=self.open_coop_dialog,
    )
    connect.grid(row=1, column=0, sticky='w', pady=(5, 0))
    ttk.Label(
        frame, text='Host controls the shared Grid and mission selection. '
                    'Shop players keep separate runs, Ore, purchases, units and buffs.',
        wraplength=360, justify='left', style='Muted.TLabel',
    ).grid(row=2, column=0, columnspan=3, sticky='w')
    if shop:
        self.shop_coop_row = frame
        self.shop_coop_mode_check = toggle
        self.shop_coop_player_count_combo = count
        self.shop_coop_connection_button = connect
    else:
        self.coop_controls_frame = frame
        self.coop_mode_check = toggle
        self.coop_player_count_combo = count
        self.coop_connection_button = connect
