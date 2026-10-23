"""Private-network connection dialog for the independent Fortress lobby."""

import secrets
import tkinter as tk
from tkinter import ttk


def connection_dialog(app):
    old = getattr(app, '_fortress_coop_dialog', None)
    if old is not None and old.winfo_exists():
        old.lift()
        return
    if not hasattr(app, '_fortress_coop_role_var'):
        app._fortress_coop_role_var = tk.StringVar(value='Host')
        app._fortress_coop_name_var = tk.StringVar(value=app.config.get('player_name') or 'Commander')
        app._fortress_coop_address_var = tk.StringVar(value=app.config.get('coop_last_host', ''))
        app._fortress_coop_host_code = tk.StringVar(value=secrets.token_hex(12))
        app._fortress_coop_guest_code = tk.StringVar()
    dialog = tk.Toplevel(app)
    app._fortress_coop_dialog = dialog
    dialog.title('Final Fortress co-op — ZeroTier')
    dialog.transient(app)
    dialog.resizable(False, False)
    frame = ttk.Frame(dialog, padding=12)
    frame.pack(fill='both', expand=True)
    frame.columnconfigure(1, weight=1)
    app._fortress_connection_fields = {}
    fields = (
        ('role', 0, 'Role', app._fortress_coop_role_var, ('Host', 'Join')),
        ('name', 1, 'Player name', app._fortress_coop_name_var, None),
        ('address', 2, 'ZeroTier IPv4', app._fortress_coop_address_var, None),
        ('pairing', 3, 'Host pairing code', app._fortress_coop_host_code, None),
    )
    for key, row, text, variable, choices in fields:
        label = ttk.Label(frame, text=text)
        label.grid(row=row, column=0, sticky='w', padx=(0, 8), pady=3)
        widget = (ttk.Combobox(frame, textvariable=variable, values=choices, state='readonly', width=26)
                  if choices else ttk.Entry(frame, textvariable=variable, width=29,
                                            show='*' if key == 'address' else ''))
        widget.grid(row=row, column=1, sticky='ew', pady=3)
        app._fortress_connection_fields[key] = (label, widget)
        if key == 'role':
            widget.bind('<<ComboboxSelected>>', lambda _event: app.refresh_fortress_coop_controls())

    def copy_code():
        app.clipboard_clear()
        app.clipboard_append(app._fortress_coop_host_code.get())

    app._fortress_copy_code_button = ttk.Button(frame, text='Copy pairing code', command=copy_code)
    app._fortress_copy_code_button.grid(row=4, column=1, sticky='e', pady=(3, 0))
    buttons = ttk.Frame(frame)
    buttons.grid(row=5, column=0, columnspan=2, sticky='e', pady=(8, 0))
    app._fortress_connect_button = ttk.Button(buttons, text='Connect', command=app.connect_fortress_coop)
    app._fortress_connect_button.grid(row=0, column=0, padx=(0, 8))
    app._fortress_disconnect_button = ttk.Button(buttons, text='Disconnect', command=app.disconnect_fortress_coop)
    app._fortress_disconnect_button.grid(row=0, column=1)
    ttk.Label(frame, textvariable=app.fortress_coop_status_var, wraplength=410, justify='left').grid(
        row=6, column=0, columnspan=2, sticky='w', pady=(8, 0))
    app.refresh_fortress_coop_controls()


def refresh_connection_dialog(app, *, connected, busy):
    """Switch role-specific fields while retaining each role's pairing code."""
    joining = app._fortress_coop_role_var.get() == 'Join'
    for key, (_, widget) in app._fortress_connection_fields.items():
        readonly = isinstance(widget, ttk.Combobox) or (key == 'pairing' and not joining)
        widget.configure(state='disabled' if connected or busy else 'readonly' if readonly else 'normal')
    address_label, _ = app._fortress_connection_fields['address']
    address_label.configure(text='Host ZeroTier IPv4' if joining else 'ZeroTier IPv4')
    pairing_label, pairing_entry = app._fortress_connection_fields['pairing']
    pairing_label.configure(text='Join pairing code' if joining else 'Host pairing code')
    pairing_entry.configure(textvariable=app._fortress_coop_guest_code if joining
                            else app._fortress_coop_host_code, show='*' if joining else '')
    copy_button = app._fortress_copy_code_button
    copy_button.grid_remove() if joining else copy_button.grid()
    app._fortress_connect_button.configure(state='disabled' if connected or busy else 'normal')
    app._fortress_disconnect_button.configure(state='normal' if connected and not busy else 'disabled')
