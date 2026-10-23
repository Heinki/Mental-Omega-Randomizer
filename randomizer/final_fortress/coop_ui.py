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
        app._fortress_coop_seat_var = tk.StringVar(value='2')
        app._fortress_coop_name_var = tk.StringVar(value=app.config.get('player_name') or 'Commander')
        app._fortress_coop_address_var = tk.StringVar(value=app.config.get('coop_last_host', ''))
        app._fortress_coop_host_code = tk.StringVar(value=secrets.token_hex(12))
        app._fortress_coop_guest_code = tk.StringVar()
    dialog = tk.Toplevel(app)
    app._fortress_coop_dialog = dialog
    dialog.title('Final Fortress co-op — ZeroTier')
    dialog.transient(app)
    frame = ttk.Frame(dialog, padding=14)
    frame.pack(fill='both', expand=True)
    frame.columnconfigure(1, weight=1)
    app._fortress_connection_widgets = []
    fields = (
        ('Role', app._fortress_coop_role_var, ('Host', 'Join')),
        ('Human players (host)', app._fortress_coop_count_var, ('2', '3')),
        ('Guest player number', app._fortress_coop_seat_var, ('2', '3')),
        ('Player name', app._fortress_coop_name_var, None),
        ('Host ZeroTier IPv4', app._fortress_coop_address_var, None),
        ('Host pairing code', app._fortress_coop_host_code, None),
        ('Join pairing code', app._fortress_coop_guest_code, None),
    )
    for row, (label, variable, choices) in enumerate(fields):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky='w', padx=(0, 10), pady=3)
        widget = (ttk.Combobox(frame, textvariable=variable, values=choices, state='readonly', width=28)
                  if choices else ttk.Entry(frame, textvariable=variable, width=31,
                                            show='*' if row in (4, 5, 6) else ''))
        widget.grid(row=row, column=1, sticky='ew', pady=3)
        if row == 5:
            widget.configure(state='readonly')
        app._fortress_connection_widgets.append(widget)
    def copy_code():
        app.clipboard_clear()
        app.clipboard_append(app._fortress_coop_host_code.get())
    ttk.Button(frame, text='Copy host pairing code', command=copy_code).grid(
        row=7, column=0, columnspan=2, sticky='w', pady=6)
    app._fortress_connect_button = ttk.Button(frame, text='Connect', command=app.connect_fortress_coop)
    app._fortress_connect_button.grid(row=8, column=0, pady=8)
    app._fortress_disconnect_button = ttk.Button(frame, text='Disconnect', command=app.disconnect_fortress_coop)
    app._fortress_disconnect_button.grid(row=8, column=1, pady=8)
    ttk.Label(frame, textvariable=app.fortress_coop_status_var, wraplength=480).grid(
        row=9, column=0, columnspan=2, sticky='w', pady=6)
    ttk.Label(frame, text=(
        'Use the same authorized ZeroTier network and matching launcher/game builds. '
        'Host chooses 2 or 3 humans, then shares the private IPv4 and pairing code. '
        'Guests choose different player numbers (2 or 3) and distinct names. '
        'Host launches after everyone connects. All use the host’s faction and enabled perks. '
        'Two humans leave at most one AI helper; three humans leave none. '
        'Every player earns their own Defensive Points and buys their own permanent perks. '
        'Disconnect to return to solo play.'), wraplength=480, justify='left').grid(
            row=10, column=0, columnspan=2, sticky='w', pady=(8, 0))
    app.refresh_fortress_coop_controls()
