"""Mission-assistance and appearance settings widgets."""

from ._builder_dependencies import WidgetTooltip, ttk


def build_general_settings(self, settings_frame):
    assistance_frame = ttk.LabelFrame(
        settings_frame,
        text='Mission Assistance',
        padding=(8, 8, 8, 8),
    )
    self.assistance_frame = assistance_frame
    assistance_frame.grid(row=9, column=0, sticky='ew', pady=(8, 0))
    self.failure_assistance_check = ttk.Checkbutton(
        assistance_frame,
        text='Strengthen failed missions on retry',
        variable=self.failure_assistance_var,
    )
    self.failure_assistance_check.grid(row=0, column=0, sticky='w')
    WidgetTooltip(
        self.failure_assistance_check,
        'Each unsuccessful attempt adds one assistance stack only to that mission. '
        'The stack applies on its next launch and is removed when the mission is completed.',
    )
    self.assistance_description_label = ttk.Label(
        assistance_frame,
        text=(
            'Per stack: 15% shorter production time, faster per-unit weapon firing, cheaper units, and higher movement '
            'speed, health, weapon damage, armor effectiveness, and attack range. Movement '
            'uses safe per-unit ceilings: infantry 8, vehicles/naval 12, aircraft 30. Applies '
            'to earned units and units supplied by that mission; normal faction rosters '
            'are used when unit access is not randomized.'
        ),
        wraplength=340,
        justify='left',
        style='Muted.TLabel',
    )
    self.assistance_description_label.grid(row=1, column=0, sticky='ew', pady=(5, 0))

    appearance_frame = ttk.LabelFrame(
        settings_frame,
        text='Appearance & Hidden Settings',
        padding=(8, 8, 8, 8),
    )
    self.appearance_frame = appearance_frame
    appearance_frame.grid(row=10, column=0, sticky='ew', pady=(8, 0))
    self.dark_mode_check = ttk.Checkbutton(
        appearance_frame,
        text='Dark mode',
        variable=self.dark_mode_var,
        command=self.on_dark_mode_changed,
    )
    self.dark_mode_check.grid(row=0, column=0, sticky='w')
    self.hide_reward_details_check = ttk.Checkbutton(
        appearance_frame,
        text='Hide reward names in Mission Details',
        variable=self.hide_reward_details_var,
        command=self.on_hide_reward_details_changed,
    )
    self.hide_reward_details_check.grid(row=1, column=0, sticky='w', pady=(4, 0))
    WidgetTooltip(
        self.hide_reward_details_check,
        'Shows ????? for pending rewards in Mission Details and mission-row hover text. '
        'Completed or released rewards reveal their names.',
    )
    self.hide_locked_grid_missions_check = ttk.Checkbutton(
        appearance_frame,
        text='Hide locked Grid Mode mission names',
        variable=self.hide_locked_grid_missions_var,
        command=self.on_hide_locked_grid_missions_changed,
    )
    self.hide_locked_grid_missions_check.grid(row=2, column=0, sticky='w', pady=(4, 0))
    WidgetTooltip(
        self.hide_locked_grid_missions_check,
        'Shows locked grid nodes as ? tiles. Completing a visible mission reveals '
        'newly unlocked mission names and faction colors.',
    )
