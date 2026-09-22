"""Detailed Advanced-tab controls for hostile-AI reward buffs."""

from randomizer.rewards.enemy_scaling import (
    ENEMY_BUFF_DEFINITIONS,
    enemy_effect_text,
)
from randomizer.ui.tooltips import WidgetTooltip

from ._builder_dependencies import tk, ttk


def build_negative_buffs_tab(self, advanced_notebook):
    page = ttk.Frame(advanced_notebook, padding=(6, 6, 6, 6))
    page.columnconfigure(0, weight=1)
    page.rowconfigure(2, weight=1)
    advanced_notebook.add(page, text='Negative Buffs')

    ttk.Label(
        page,
        text=(
            'Choose exact hostile-AI buffs allowed in generated reward pools. '
            'Checked entries are active; maximum stacks limits each buff.'
        ),
        style='Muted.TLabel',
        wraplength=820,
        justify='left',
    ).grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 6))

    actions = ttk.Frame(page)
    actions.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(0, 6))
    self.advanced_enemy_buff_status_var = tk.StringVar(value='')
    ttk.Label(
        actions,
        textvariable=self.advanced_enemy_buff_status_var,
        style='Muted.TLabel',
    ).pack(side='left')
    ttk.Button(
        actions,
        text='Enable All',
        command=lambda: self.set_advanced_enemy_buffs(True),
    ).pack(side='right', padx=(4, 0))
    ttk.Button(
        actions,
        text='Disable All',
        command=lambda: self.set_advanced_enemy_buffs(False),
    ).pack(side='right')

    canvas = tk.Canvas(
        page,
        borderwidth=0,
        highlightthickness=0,
        background=self.style.lookup('TFrame', 'background') or '#f0f0f0',
    )
    scrollbar = ttk.Scrollbar(page, orient='vertical', command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.grid(row=2, column=0, sticky='nsew')
    scrollbar.grid(row=2, column=1, sticky='ns')
    content = ttk.Frame(canvas, padding=(4, 4, 4, 4))
    window = canvas.create_window((0, 0), window=content, anchor='nw')
    content.columnconfigure(0, weight=1)
    content.bind(
        '<Configure>',
        lambda _event: canvas.configure(scrollregion=canvas.bbox('all')),
    )
    canvas.bind(
        '<Configure>',
        lambda event: canvas.itemconfigure(window, width=event.width),
    )
    for widget in (canvas, content):
        widget.bind(
            '<MouseWheel>',
            lambda event, target=canvas: self.on_unlock_mousewheel(event, target),
        )

    self.advanced_enemy_buff_controls = []
    self.advanced_enemy_buff_state_vars = {}
    for row, definition in enumerate(ENEMY_BUFF_DEFINITIONS):
        effect_id = definition['id']
        entry = ttk.Frame(content, padding=(4, 4, 4, 4))
        entry.grid(row=row, column=0, sticky='ew', pady=(0, 3))
        entry.columnconfigure(0, weight=1)
        check = ttk.Checkbutton(
            entry,
            text=definition['name'],
            variable=self.enemy_buff_enabled_vars[effect_id],
            command=lambda item=effect_id: (
                self.on_advanced_enemy_buff_changed(item)
            ),
        )
        check.grid(row=0, column=0, sticky='w')
        state_var = tk.StringVar(value='')
        self.advanced_enemy_buff_state_vars[effect_id] = state_var
        ttk.Label(
            entry,
            textvariable=state_var,
            width=9,
            anchor='center',
            style='Muted.TLabel',
        ).grid(row=0, column=1, padx=(8, 8))
        ttk.Label(entry, text='Max stacks:').grid(
            row=0, column=2, sticky='e', padx=(0, 4)
        )
        cap = ttk.Spinbox(
            entry,
            from_=0,
            to=max(0, int(definition.get('maximum_stacks', 1))),
            width=5,
            textvariable=self.enemy_buff_cap_vars[effect_id],
            command=lambda item=effect_id: (
                self.on_advanced_enemy_buff_changed(item)
            ),
        )
        cap.grid(row=0, column=3, sticky='e')
        cap.bind(
            '<FocusOut>',
            lambda _event, item=effect_id: (
                self.on_advanced_enemy_buff_changed(item)
            ),
            add='+',
        )
        effect = enemy_effect_text(definition, 1)
        ttk.Label(
            entry,
            text=effect,
            style='Muted.TLabel',
            wraplength=720,
            justify='left',
        ).grid(row=1, column=0, columnspan=4, sticky='w', padx=(20, 0))
        WidgetTooltip(
            check,
            f'{definition["name"]}\n{effect}\nOnly verified hostile AI Houses receive this buff.',
        )
        self.advanced_enemy_buff_controls.append((check, cap))

    self.refresh_advanced_enemy_buff_controls()
