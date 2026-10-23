"""Mission category, challenge player choice, and multiplayer connection."""

import tkinter as tk
from tkinter import ttk

from randomizer.challenges.catalogue import COUNTRY_LABELS
from randomizer.ui.tooltips import WidgetTooltip


def build_coop_controls(self, parent, row, *, shop=False):
    """Group co-op, optional challenges, player setup, and connection."""
    frame = ttk.LabelFrame(
        parent, text='Co-op' if shop else 'Co-op & Challenges', padding=8,
    )
    frame.columnconfigure(1, weight=1)
    frame.grid(row=row, column=0, columnspan=2 if shop else 1,
               sticky='ew', pady=(8, 8))
    toggle = ttk.Checkbutton(
        frame, text='Co-op', variable=self.coop_mode_var,
        command=self.on_coop_checkbox_changed,
    )
    toggle.grid(row=0, column=0, columnspan=3, sticky='w')
    toggle_tooltip = WidgetTooltip(toggle, 'Off: solo campaign missions. On: two-player co-op missions.')
    include = ttk.Checkbutton(
        frame, text='Include challenge maps',
        variable=self.include_challenge_missions_var,
        command=self.on_mission_pool_settings_changed,
    )
    include.grid(row=1, column=0, columnspan=3, sticky='w', pady=(5, 0))
    WidgetTooltip(
        include,
        'Adds installed challenges to the next seed. Mission goal and Advanced exclusions apply. '
        'Available in standalone Grid Mode, Mission List and Classic.',
    )
    player_label = ttk.Label(frame, text='Human players (legacy run)')
    player_label.grid(row=2, column=0, sticky='w', pady=(5, 0))
    count = ttk.Combobox(
        frame, textvariable=self.challenge_player_count_var, values=('1', '2'),
        state='readonly', width=3,
    )
    count.grid(row=2, column=1, sticky='w', padx=(8, 0), pady=(5, 0))
    count.bind('<<ComboboxSelected>>', self.on_challenge_setup_changed)
    fortress_label = ttk.Label(frame, text='Co-op players')
    fortress_label.grid(row=2, column=0, sticky='w', pady=(5, 0))
    fortress_count = ttk.Combobox(
        frame, textvariable=self._fortress_coop_count_var, values=('2', '3'),
        state='readonly', width=3,
    )
    fortress_count.grid(row=2, column=1, sticky='w', padx=(8, 0), pady=(5, 0))
    fortress_label.grid_remove()
    fortress_count.grid_remove()
    local = ttk.LabelFrame(frame, text='Local challenge players', padding=8)
    local.grid(row=3, column=0, columnspan=3, sticky='ew', pady=(8, 0))
    local.columnconfigure(1, weight=1)
    country_label = ttk.Label(local, text='Your house')
    country_label.grid(row=0, column=0, sticky='w', padx=(0, 8), pady=2)
    if not hasattr(self, 'challenge_country_label_var'):
        selected = self.challenge_country_var.get()
        self.challenge_country_label_var = tk.StringVar(
            master=self, value=COUNTRY_LABELS.get(selected, selected),
        )
    country = ttk.Combobox(
        local, textvariable=self.challenge_country_label_var,
        values=tuple(COUNTRY_LABELS.values()),
        state='readonly', width=18,
    )
    country.grid(row=0, column=1, sticky='ew', pady=2)
    country.bind('<<ComboboxSelected>>', self.on_challenge_country_selected)
    ttk.Label(local, text='Your color').grid(row=1, column=0, sticky='w', padx=(0, 8))
    human_color = ttk.Combobox(
        local, textvariable=self.challenge_solo_color_var, state='readonly', width=18,
    )
    human_color.grid(row=1, column=1, sticky='ew')
    ai_toggle = ttk.Checkbutton(
        local, text='Play with an AI teammate', variable=self.challenge_ai_enabled_var,
        command=self.on_challenge_local_options_changed,
    )
    ai_toggle.grid(row=2, column=0, columnspan=2, sticky='w', pady=(6, 2))
    if not hasattr(self, 'challenge_ai_country_label_var'):
        selected = self.challenge_ai_country_var.get()
        self.challenge_ai_country_label_var = tk.StringVar(
            master=self, value=COUNTRY_LABELS.get(selected, selected),
        )
    ai_fields = []
    ai_combos = {}
    for index, (name, text, variable) in enumerate((
            ('house', 'AI house', self.challenge_ai_country_label_var),
            ('color', 'AI color', self.challenge_ai_color_var),
            ('difficulty', 'AI difficulty', self.challenge_ai_difficulty_var)), start=3):
        field_label = ttk.Label(local, text=text)
        field_label.grid(row=index, column=0, sticky='w', padx=(0, 8), pady=2)
        combo = ttk.Combobox(local, textvariable=variable, state='readonly', width=18)
        combo.grid(row=index, column=1, sticky='ew', pady=2)
        combo.bind('<<ComboboxSelected>>', self.on_challenge_ai_house_selected
                   if name == 'house' else self.on_challenge_local_options_changed)
        ai_fields.extend((field_label, combo))
        ai_combos[name] = combo
    human_color.bind('<<ComboboxSelected>>', self.on_challenge_local_options_changed)
    if not hasattr(self, 'challenge_local_summary_var'):
        self.challenge_local_summary_var = tk.StringVar(master=self)
    ttk.Label(local, textvariable=self.challenge_local_summary_var, wraplength=330,
              justify='left', style='Muted.TLabel').grid(
                  row=6, column=0, columnspan=2, sticky='w', pady=(5, 0))
    connect = ttk.Button(
        frame, text='Co-op Connection…', command=self.open_coop_dialog,
    )
    connect.grid(row=4, column=0, columnspan=3, sticky='w', pady=(5, 0))
    if not hasattr(self, 'challenge_availability_var'):
        self.challenge_availability_var = tk.StringVar(master=self)
    availability = ttk.Label(
        frame, textvariable=self.challenge_availability_var,
        wraplength=360, justify='left', style='Muted.TLabel',
    )
    availability.grid(row=5, column=0, columnspan=3, sticky='w')
    prefix = 'shop_' if shop else ''
    setattr(self, prefix + 'fortress_player_count_fields', (fortress_label, fortress_count))
    setattr(self, prefix + 'fortress_player_count_combo', fortress_count)
    setattr(self, prefix + 'coop_mode_tooltip', toggle_tooltip)
    setattr(self, prefix + 'challenge_availability_label', availability)
    setattr(self, prefix + 'include_challenge_missions_check', include)
    setattr(self, prefix + 'challenge_local_frame', local)
    setattr(self, prefix + 'challenge_solo_color_combo', human_color)
    setattr(self, prefix + 'challenge_ai_toggle', ai_toggle)
    setattr(self, prefix + 'challenge_ai_fields', tuple(ai_fields))
    setattr(self, prefix + 'challenge_ai_combos', ai_combos)
    setattr(self, prefix + 'challenge_country_combo', country)
    setattr(self, prefix + 'challenge_country_label', country_label)
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
