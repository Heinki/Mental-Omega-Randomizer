"""Mission category, challenge player choice, and multiplayer connection."""

import tkinter as tk
from tkinter import ttk

from randomizer.challenges.catalogue import COUNTRY_LABELS


def build_coop_controls(self, parent, row, *, shop=False):
    """Group mode, player count, connection button and help below appearance."""
    frame = ttk.Frame(parent)
    frame.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(8, 0))
    ttk.Label(frame, text='Mission category').grid(row=0, column=0, sticky='w')
    toggle = ttk.Combobox(
        frame, textvariable=self.mission_category_var,
        values=('campaign', 'coop', 'challenge'), state='readonly', width=12,
    )
    toggle.grid(row=0, column=1, columnspan=2, sticky='ew', padx=(8, 0))
    toggle.bind('<<ComboboxSelected>>', self.on_mission_category_changed)
    player_label = ttk.Label(frame, text='Players')
    player_label.grid(row=1, column=0, sticky='w', pady=(5, 0))
    count = ttk.Combobox(
        frame, textvariable=self.challenge_player_count_var, values=('1', '2'),
        state='readonly', width=3,
    )
    count.grid(row=1, column=1, sticky='w', padx=(8, 0), pady=(5, 0))
    count.bind('<<ComboboxSelected>>', self.on_challenge_setup_changed)
    country_label = ttk.Label(frame, text='Mission pool country')
    country_label.grid(row=2, column=0, sticky='w', pady=(5, 0))
    if not hasattr(self, 'challenge_country_label_var'):
        selected = self.challenge_country_var.get()
        self.challenge_country_label_var = tk.StringVar(
            master=self, value=COUNTRY_LABELS.get(selected, selected),
        )
    country = ttk.Combobox(
        frame, textvariable=self.challenge_country_label_var,
        values=tuple(COUNTRY_LABELS.values()),
        state='readonly', width=18,
    )
    country.grid(row=2, column=1, columnspan=2, sticky='ew', padx=(8, 0), pady=(5, 0))
    country.bind('<<ComboboxSelected>>', self.on_challenge_country_selected)
    connect = ttk.Button(
        frame, text='Co-op Connection…', command=self.open_coop_dialog,
    )
    connect.grid(row=3, column=0, columnspan=3, sticky='w', pady=(5, 0))
    ttk.Label(
        frame, text='Challenges support solo or two players. Country choice filters '
                    'compatible maps. Generate a seed after changing the setup. '
                    'Each player chooses their own house and color in Co-op Connection. '
                    'Host controls progression and game speed.',
        wraplength=360, justify='left', style='Muted.TLabel',
    ).grid(row=4, column=0, columnspan=3, sticky='w')
    prefix = 'shop_' if shop else ''
    setattr(self, prefix + 'challenge_country_combo', country)
    setattr(self, prefix + 'challenge_fields', (player_label, count, country_label, country))
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
