"""Advanced Starting Unlocks selector widgets."""

from ._builder_dependencies import (
    STARTING_UNLOCK_CATEGORY_LABELS,
    tk,
    ttk,
)


def build_starting_unlocks_tab(self, advanced_notebook):
    tab = ttk.Frame(advanced_notebook, padding=(6, 6, 6, 6))
    self.starting_unlocks_tab = tab
    tab.columnconfigure(0, weight=1)
    tab.rowconfigure(3, weight=1)
    advanced_notebook.add(tab, text='Starting Unlocks')

    ttk.Label(
        tab,
        text=(
            'Choose permanent unit, building, and power unlocks already owned '
            'before the first mission. Buffs remain progression rewards.'
        ),
        style='Muted.TLabel',
        wraplength=760,
        justify='left',
    ).grid(row=0, column=0, sticky='ew', pady=(0, 6))

    controls = ttk.Frame(tab)
    controls.grid(row=1, column=0, sticky='ew', pady=(0, 6))
    controls.columnconfigure(3, weight=1)
    ttk.Label(controls, text='Category').grid(row=0, column=0, sticky='w')
    self.starting_unlock_category_var = tk.StringVar(value='All categories')
    category = ttk.Combobox(
        controls,
        state='readonly',
        textvariable=self.starting_unlock_category_var,
        values=('All categories',) + STARTING_UNLOCK_CATEGORY_LABELS,
        width=19,
    )
    category.grid(row=0, column=1, sticky='w', padx=(6, 12))
    category.bind(
        '<<ComboboxSelected>>',
        lambda _event: self.refresh_starting_unlocks_view(),
    )
    ttk.Label(controls, text='Search').grid(row=0, column=2, sticky='w')
    self.starting_unlock_search_var = tk.StringVar(value='')
    self.starting_unlock_search_entry = ttk.Entry(
        controls,
        textvariable=self.starting_unlock_search_var,
    )
    self.starting_unlock_search_entry.grid(
        row=0, column=3, sticky='ew', padx=(6, 12)
    )
    self.starting_unlock_search_var.trace_add(
        'write', lambda *_args: self.refresh_starting_unlocks_view()
    )
    ttk.Button(
        controls,
        text='Select Visible',
        command=lambda: self.set_visible_starting_unlocks(True),
    ).grid(row=0, column=4, padx=(0, 6))
    ttk.Button(
        controls,
        text='Clear Visible',
        command=lambda: self.set_visible_starting_unlocks(False),
    ).grid(row=0, column=5)

    self.starting_unlock_status_label = ttk.Label(
        tab, text='', style='Muted.TLabel'
    )
    self.starting_unlock_status_label.grid(row=2, column=0, sticky='ew', pady=(0, 4))

    tree_frame = ttk.Frame(tab)
    tree_frame.grid(row=3, column=0, sticky='nsew')
    tree_frame.columnconfigure(0, weight=1)
    tree_frame.rowconfigure(0, weight=1)
    ttk.Style(self).configure('StartingUnlocks.Treeview', rowheight=52)
    tree = ttk.Treeview(
        tree_frame,
        columns=('reward', 'category', 'faction'),
        show='tree headings',
        selectmode='extended',
        style='StartingUnlocks.Treeview',
    )
    self.starting_unlocks_tree = tree
    tree.heading('#0', text='Cameo')
    tree.heading('reward', text='Reward')
    tree.heading('category', text='Type')
    tree.heading('faction', text='Faction')
    tree.column('#0', width=72, minwidth=72, stretch=False, anchor='center')
    tree.column('reward', width=390, minwidth=220, stretch=True)
    tree.column('category', width=130, minwidth=105, stretch=False)
    tree.column('faction', width=100, minwidth=85, stretch=False)
    tree.tag_configure('starting_selected', background='#245c36', foreground='#ffffff')
    scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    tree.grid(row=0, column=0, sticky='nsew')
    scrollbar.grid(row=0, column=1, sticky='ns')
    tree.bind('<Double-1>', self.toggle_starting_unlock_tree_selection)
    tree.bind('<Return>', self.toggle_starting_unlock_tree_selection)
    tree.bind('<space>', self.toggle_starting_unlock_tree_selection)
    self.starting_unlock_tree_names = {}
