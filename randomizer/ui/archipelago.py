"""Archipelago workspace tab."""

from ._builder_dependencies import scrolledtext, ttk
from randomizer.core.paths import LAUNCHER_LOG


def build_archipelago_tab(self, workspace_tabs):
    tab = ttk.Frame(workspace_tabs, padding=(12, 12, 12, 12))
    self.archipelago_tab = tab
    tab.columnconfigure(0, weight=1)
    tab.rowconfigure(3, weight=1)
    workspace_tabs.add(tab, text='Archipelago')

    connection = ttk.LabelFrame(tab, text='Connection', padding=(10, 10, 10, 10))
    connection.grid(row=0, column=0, sticky='ew')
    connection.columnconfigure(1, weight=1)
    connection.columnconfigure(3, weight=1)

    ttk.Label(connection, text='Server').grid(
        row=0, column=0, sticky='w', padx=(0, 6)
    )
    self.archipelago_server_entry = ttk.Entry(
        connection,
        textvariable=self.archipelago_server_var,
    )
    self.archipelago_server_entry.grid(
        row=0, column=1, sticky='ew', padx=(0, 12)
    )
    ttk.Label(connection, text='Port').grid(
        row=0, column=2, sticky='w', padx=(0, 6)
    )
    self.archipelago_port_entry = ttk.Entry(
        connection,
        textvariable=self.archipelago_port_var,
        width=8,
    )
    self.archipelago_port_entry.grid(row=0, column=3, sticky='w')

    ttk.Label(connection, text='Slot Name').grid(
        row=1, column=0, sticky='w', padx=(0, 6), pady=(8, 0)
    )
    self.archipelago_slot_entry = ttk.Entry(
        connection,
        textvariable=self.archipelago_slot_var,
    )
    self.archipelago_slot_entry.grid(
        row=1, column=1, sticky='ew', padx=(0, 12), pady=(8, 0)
    )
    ttk.Label(connection, text='Password').grid(
        row=1, column=2, sticky='w', padx=(0, 6), pady=(8, 0)
    )
    self.archipelago_password_entry = ttk.Entry(
        connection,
        textvariable=self.archipelago_password_var,
        show='*',
    )
    self.archipelago_password_entry.grid(
        row=1, column=3, sticky='ew', pady=(8, 0)
    )

    button_row = ttk.Frame(connection)
    button_row.grid(
        row=2, column=0, columnspan=4, sticky='ew', pady=(10, 0)
    )
    button_row.columnconfigure(0, weight=1)
    button_row.columnconfigure(1, weight=1)
    self.archipelago_connect_button = ttk.Button(
        button_row,
        text='Connect',
        command=self.connect_archipelago,
    )
    self.archipelago_connect_button.grid(
        row=0, column=0, sticky='ew', padx=(0, 4)
    )
    self.archipelago_disconnect_button = ttk.Button(
        button_row,
        text='Disconnect',
        command=self.disconnect_archipelago,
        state='disabled',
    )
    self.archipelago_disconnect_button.grid(
        row=0, column=1, sticky='ew', padx=(4, 0)
    )
    ttk.Label(
        connection,
        text=(
            'Hosted rooms: keep Server as archipelago.gg and copy only the '
            'port shown on the room page.'
        ),
        style='Muted.TLabel',
        wraplength=820,
        justify='left',
    ).grid(row=3, column=0, columnspan=4, sticky='ew', pady=(7, 0))

    status_frame = ttk.LabelFrame(tab, text='Status', padding=(10, 8, 10, 8))
    status_frame.grid(row=1, column=0, sticky='ew', pady=(10, 10))
    status_frame.columnconfigure(0, weight=1)
    self.archipelago_status_label = ttk.Label(
        status_frame,
        textvariable=self.archipelago_status_var,
        font=('Segoe UI', 10, 'bold'),
        style='Archipelago.Disconnected.TLabel',
    )
    self.archipelago_status_label.grid(row=0, column=0, sticky='w')

    yaml_frame = ttk.LabelFrame(
        tab,
        text='Player YAML Export',
        padding=(10, 8, 10, 8),
    )
    yaml_frame.grid(row=2, column=0, sticky='ew', pady=(0, 10))
    yaml_frame.columnconfigure(0, weight=1)
    self.archipelago_save_yaml_button = ttk.Button(
        yaml_frame,
        text='Save Player YAML',
        command=self.save_archipelago_yaml,
    )
    self.archipelago_save_yaml_button.grid(
        row=0, column=0, sticky='ew'
    )
    ttk.Label(
        yaml_frame,
        textvariable=self.archipelago_yaml_status_var,
        style='Muted.TLabel',
        wraplength=820,
        justify='left',
    ).grid(row=1, column=0, sticky='ew', pady=(7, 0))

    history_frame = ttk.LabelFrame(
        tab,
        text='Archipelago Activity',
        padding=(8, 8, 8, 8),
    )
    history_frame.grid(row=3, column=0, sticky='nsew')
    history_frame.columnconfigure(0, weight=1)
    history_frame.rowconfigure(0, weight=1)
    self.archipelago_history_text = scrolledtext.ScrolledText(
        history_frame,
        height=16,
        wrap='word',
        state='disabled',
        font=('Segoe UI', 9),
    )
    self.archipelago_history_text.grid(row=0, column=0, sticky='nsew')
    self.configure_archipelago_message_tags()

    chat_row = ttk.Frame(history_frame)
    chat_row.grid(row=1, column=0, sticky='ew', pady=(8, 0))
    chat_row.columnconfigure(1, weight=1)
    self.archipelago_chat_identity_label = ttk.Label(chat_row)
    self.archipelago_chat_identity_label.grid(
        row=0, column=0, sticky='w', padx=(0, 8)
    )

    def refresh_chat_identity(*_args):
        slot_name = self.archipelago_slot_var.get().strip() or 'Slot Name'
        self.archipelago_chat_identity_label.configure(
            text=f'Chat / Command as {slot_name}'
        )

    self._archipelago_chat_identity_trace = (
        self.archipelago_slot_var.trace_add('write', refresh_chat_identity)
    )
    refresh_chat_identity()
    self.archipelago_chat_entry = ttk.Entry(
        chat_row,
        textvariable=self.archipelago_chat_var,
        state='disabled',
    )
    self.archipelago_chat_entry.grid(
        row=0, column=1, sticky='ew', padx=(0, 8)
    )
    self.archipelago_chat_entry.bind(
        '<Return>', self.send_archipelago_chat
    )
    self.archipelago_chat_button = ttk.Button(
        chat_row,
        text='Send',
        command=self.send_archipelago_chat,
        state='disabled',
    )
    self.archipelago_chat_button.grid(row=0, column=2, sticky='e')
    ttk.Label(
        history_frame,
        text='Send normal chat or server commands such as !hint and !release.',
        style='Muted.TLabel',
    ).grid(row=2, column=0, sticky='w', pady=(5, 0))
    ttk.Label(
        history_frame,
        text=f'Full connection diagnostics: {LAUNCHER_LOG}',
        style='Muted.TLabel',
        wraplength=820,
        justify='left',
    ).grid(row=3, column=0, sticky='w', pady=(3, 0))

    ttk.Label(
        tab,
        text=(
            'YAML preparation keeps standalone rewards active. A validated '
            'connection activates AP rewards. After activation, disconnecting '
            'keeps AP mode active for safe offline play and reconnection; '
            'Generate New Seed returns to standalone.'
        ),
        style='Muted.TLabel',
        wraplength=820,
        justify='left',
    ).grid(row=4, column=0, sticky='ew', pady=(8, 0))
