"""Compact AI-reward controls inside Reward Pool."""

from ._builder_dependencies import (
    ENEMY_BUFF_GROUP_DEFINITIONS,
    MAX_AI_REWARDS_PER_COMPLETION,
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

    self.enemy_reward_pool_check = ttk.Checkbutton(
        reward_frame,
        text='Include AI rewards in normal reward pool',
        variable=self.enemy_reward_pool_var,
        command=self.refresh_setting_states,
    )
    self.enemy_reward_pool_check.grid(row=17, column=0, sticky='w')
    WidgetTooltip(
        self.enemy_reward_pool_check,
        'AI rewards occupy normal reward slots, appear in red, and apply only '
        'to verified hostile AI houses. They never unlock player production.',
    )

    rates = ttk.Frame(reward_frame)
    rates.grid(row=18, column=0, sticky='ew', pady=(4, 0))
    rates.columnconfigure(1, weight=1)
    ttk.Label(rates, text='AI bonus stacks per completed objective').grid(
        row=0, column=0, sticky='w', padx=(0, 8)
    )
    self.enemy_objective_rewards_spinbox = ttk.Spinbox(
        rates,
        from_=0,
        to=MAX_AI_REWARDS_PER_COMPLETION,
        width=5,
        textvariable=self.enemy_objective_rewards_var,
        command=self.refresh_setting_states,
    )
    self.enemy_objective_rewards_spinbox.grid(row=0, column=1, sticky='w')
    ttk.Label(rates, text='AI bonus stacks per completed mission').grid(
        row=1, column=0, sticky='w', padx=(0, 8), pady=(3, 0)
    )
    self.enemy_mission_rewards_spinbox = ttk.Spinbox(
        rates,
        from_=0,
        to=MAX_AI_REWARDS_PER_COMPLETION,
        width=5,
        textvariable=self.enemy_mission_rewards_var,
        command=self.refresh_setting_states,
    )
    self.enemy_mission_rewards_spinbox.grid(
        row=1, column=1, sticky='w', pady=(3, 0)
    )
    for control in (
        self.enemy_objective_rewards_spinbox,
        self.enemy_mission_rewards_spinbox,
    ):
        control.bind('<FocusOut>', lambda _event: self.refresh_setting_states())
        control.bind('<Return>', lambda _event: self.refresh_setting_states())
        control.bind(
            '<MouseWheel>', self.on_settings_control_mousewheel, add='+'
        )
    WidgetTooltip(
        self.enemy_objective_rewards_spinbox,
        'Attempts to grant this many valid AI bonus stacks after every '
        'completed mission objective. All AI reward sources share per-bonus '
        'caps, so fewer or zero remain after every enabled bonus is capped.',
    )
    WidgetTooltip(
        self.enemy_mission_rewards_spinbox,
        'Attempts to grant this many additional valid AI bonus stacks after '
        'mission victory. All AI reward sources share per-bonus caps.',
    )
    self.enemy_reward_capacity_label = ttk.Label(
        reward_frame,
        text='',
        style='Muted.TLabel',
        justify='left',
        wraplength=590,
    )
    self.enemy_reward_capacity_label.grid(
        row=19, column=0, sticky='w', pady=(3, 5)
    )

    ttk.Label(
        reward_frame,
        text='Allowed AI rewards',
        style='Muted.TLabel',
    ).grid(row=20, column=0, sticky='w', pady=(0, 2))
    groups_frame = ttk.Frame(reward_frame)
    groups_frame.grid(row=21, column=0, sticky='ew')
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
