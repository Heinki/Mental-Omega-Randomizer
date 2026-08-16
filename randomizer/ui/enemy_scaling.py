"""Compact AI-reward controls inside Reward Pool."""

from ._builder_dependencies import (
    ENEMY_BUFF_GROUP_DEFINITIONS,
    MAX_ENEMY_TOTAL_BUFFS,
    WidgetTooltip,
    ttk,
)


def build_enemy_scaling_settings(self, reward_frame):
    ttk.Separator(reward_frame, orient='horizontal').grid(
        row=15, column=0, sticky='ew', pady=(8, 6)
    )
    ttk.Label(
        reward_frame,
        text='AI Enemy Rewards',
        style='Muted.TLabel',
    ).grid(row=16, column=0, sticky='w', pady=(0, 3))

    rates = ttk.Frame(reward_frame)
    rates.grid(row=17, column=0, sticky='ew', pady=(4, 0))
    rates.columnconfigure(1, weight=1)
    self.enemy_maximum_total_buffs_label = ttk.Label(
        rates, text='Maximum total AI bonus stacks'
    )
    self.enemy_maximum_total_buffs_label.grid(
        row=0, column=0, sticky='w', padx=(0, 8)
    )
    self.enemy_maximum_total_buffs_spinbox = ttk.Spinbox(
        rates,
        from_=0,
        to=MAX_ENEMY_TOTAL_BUFFS,
        width=5,
        textvariable=self.enemy_maximum_total_buffs_var,
        command=self.refresh_setting_states,
    )
    self.enemy_maximum_total_buffs_spinbox.grid(
        row=0, column=1, sticky='w'
    )
    for control in (
        self.enemy_maximum_total_buffs_spinbox,
    ):
        control.bind('<FocusOut>', lambda _event: self.refresh_setting_states())
        control.bind('<Return>', lambda _event: self.refresh_setting_states())
        control.bind(
            '<MouseWheel>', self.on_settings_control_mousewheel, add='+'
        )
    WidgetTooltip(
        self.enemy_maximum_total_buffs_spinbox,
        'Maximum additional enemy-bonus stacks granted beside normal rewards. '
        'In Archipelago, these become Trap items with extra locations. The '
        'displayed range follows enabled per-buff caps.',
    )
    self.enemy_reward_capacity_label = ttk.Label(
        reward_frame,
        text='',
        style='Muted.TLabel',
        justify='left',
        wraplength=590,
    )
    self.enemy_reward_capacity_label.grid(
        row=18, column=0, sticky='w', pady=(3, 5)
    )

    ttk.Label(
        reward_frame,
        text='Allowed AI rewards',
        style='Muted.TLabel',
    ).grid(row=19, column=0, sticky='w', pady=(0, 2))
    groups_frame = ttk.Frame(reward_frame)
    groups_frame.grid(row=20, column=0, sticky='ew')
    groups_frame.columnconfigure(0, weight=1)
    groups_frame.columnconfigure(1, weight=1)
    self.enemy_buff_group_controls = []
    self.enemy_buff_group_tooltips = {}
    for index, group in enumerate(ENEMY_BUFF_GROUP_DEFINITIONS):
        check = ttk.Checkbutton(
            groups_frame,
            text=group['label'],
            variable=self.enemy_buff_group_vars[group['id']],
            command=lambda group_id=group['id']: (
                self.on_enemy_buff_group_changed(group_id)
            ),
        )
        check.grid(
            row=index // 2,
            column=index % 2,
            sticky='w',
            padx=(0, 10),
            pady=(0, 2),
        )
        self.enemy_buff_group_controls.append((group, check))
        tooltip = WidgetTooltip(
            check,
            self.enemy_buff_group_help_text(group),
        )
        self.enemy_buff_group_tooltips[group['id']] = tooltip
    self.refresh_enemy_reward_setting_help()
