"""ZeroTier connection dialog, private fields, and connection diagnostics."""

import time
import secrets
import tkinter as tk
from tkinter import ttk

from randomizer.coop import feature
from randomizer.coop.privacy import redact_connection_details
from randomizer.core.paths import LAUNCHER_LOG


class CoopConnectionController:
    def open_coop_dialog(self):
        if not feature.COOP_FEATURE_ENABLED or not self.coop_mode_var.get():
            return
        old = getattr(self, '_coop_dialog', None)
        if old and old.winfo_exists():
            old.lift()
            return
        dialog = tk.Toplevel(self)
        self._coop_dialog = dialog
        dialog.title('ZeroTier co-op connection')
        dialog.transient(self)
        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill='both', expand=True)
        if not hasattr(self, '_coop_role'):
            self._coop_role = tk.StringVar(value='Host')
            self._coop_name = tk.StringVar(value='CoopHost')
            self._coop_address = tk.StringVar(value=self.config.get('coop_last_host', ''))
            self._coop_host_pairing = tk.StringVar(value=secrets.token_hex(12))
            self._coop_pairing = tk.StringVar(value='')
            self._coop_status_var = tk.StringVar(value='Disconnected')
        self._coop_show_details = tk.BooleanVar(value=False)
        self._coop_private_entries = []
        self._coop_connection_entries = []
        frame.columnconfigure(1, weight=1)
        for row, (label, variable) in enumerate((('Role', self._coop_role), ('Player name', self._coop_name), ('Host ZeroTier IPv4', self._coop_address), ('Pairing code', self._coop_pairing))):
            field_label = ttk.Label(frame, text=label)
            field_label.grid(row=row, column=0, sticky='w', padx=(0, 8))
            widget = ttk.Combobox(frame, textvariable=variable, values=('Host', 'Join'), state='readonly') if row == 0 else ttk.Entry(frame, textvariable=variable, width=30)
            widget.grid(row=row, column=1, pady=3, sticky='ew')
            self._coop_connection_entries.append(widget)
            if variable is self._coop_role:
                widget.bind('<<ComboboxSelected>>', self._on_coop_role_changed)
            elif variable is self._coop_address:
                self._coop_address_widgets = (field_label, widget)
            elif variable is self._coop_pairing:
                self._coop_guest_code_entry = widget
                self._coop_host_code_label = ttk.Label(frame, textvariable=self._coop_host_pairing)
                self._coop_host_code_label.grid(row=row, column=1, pady=3, sticky='w')
            if variable is self._coop_address or variable is self._coop_pairing:
                widget.configure(show='*')
                self._coop_private_entries.append(widget)
        self._coop_show_details_check = ttk.Checkbutton(
            frame, variable=self._coop_show_details, command=self._toggle_coop_details)
        self._coop_show_details_check.grid(row=4, column=0, columnspan=2, sticky='w', pady=(6, 0))
        ttk.Button(frame, text='Copy pairing code', command=self._copy_coop_pairing).grid(row=5, column=0, sticky='w', pady=5)
        self._coop_start_button = ttk.Button(frame, text='Connect', command=self._connect_coop_from_dialog)
        self._coop_start_button.grid(row=6, column=0, pady=8)
        ttk.Button(frame, text='Disconnect', command=self.disconnect_coop).grid(row=6, column=1)
        ttk.Label(frame, textvariable=self._coop_status_var, wraplength=430).grid(row=7, column=0, columnspan=2)
        ttk.Button(frame, text='Show connection log', command=self._show_coop_log).grid(
            row=8, column=0, columnspan=2, sticky='w', pady=(8, 0))
        dialog.protocol('WM_DELETE_WINDOW', self._close_coop_dialog)
        ttk.Label(frame, text=(
            'Use the same authorized private ZeroTier network. Guest enters the host’s '
            'Managed IPv4 and pairing code. Host generates the Grid first; Shop players '
            'start separate runs with the same seed and stage. Ports are automatic.'
        ), wraplength=430, justify='left').grid(row=9, column=0, columnspan=2, pady=(8, 0))
        self._refresh_coop_connection_fields()

    def _hide_coop_details(self):
        if hasattr(self, '_coop_show_details'):
            self._coop_show_details.set(False)
        for entry in getattr(self, '_coop_private_entries', ()):
            if entry.winfo_exists():
                entry.configure(show='*')

    def _toggle_coop_details(self):
        if not self._coop_show_details.get():
            self._hide_coop_details()
            return
        for entry in self._coop_private_entries:
            entry.configure(show='')

    def _close_coop_dialog(self):
        self._hide_coop_details()
        self._coop_dialog.destroy()

    def _copy_coop_pairing(self):
        self._hide_coop_details()
        self.clipboard_clear()
        self.clipboard_append(self._coop_pairing_code())

    def _coop_pairing_code(self):
        return (self._coop_host_pairing if self._coop_role.get() == 'Host' else self._coop_pairing).get()

    def _on_coop_role_changed(self, *_args):
        if self._coop_name.get() in ('CoopHost', 'CoopGuest'):
            self._coop_name.set('CoopHost' if self._coop_role.get() == 'Host' else 'CoopGuest')
        self._refresh_coop_connection_fields()

    def _record_coop_log(self, message, error=False):
        message = self._coop_safe_message(message)
        self.append_log(message, error=error)
        lines = self.__dict__.setdefault('_coop_connection_log', [])
        lines.append(time.strftime('%H:%M:%S') + ' ' + message)
        del lines[:-200]
        self._refresh_coop_log()

    def _refresh_coop_log(self):
        widget = getattr(self, '_coop_log_text', None)
        if widget and widget.winfo_exists():
            widget.configure(state='normal')
            widget.delete('1.0', 'end')
            widget.insert('end', '\n'.join(getattr(self, '_coop_connection_log', ())))
            widget.configure(state='disabled')
            widget.see('end')

    def _show_coop_log(self):
        old = getattr(self, '_coop_log_dialog', None)
        if old and old.winfo_exists():
            old.lift()
            return
        dialog = tk.Toplevel(self)
        self._coop_log_dialog = dialog
        dialog.title('Co-op connection log')
        dialog.transient(self)
        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text=f'Persistent log: {LAUNCHER_LOG}', wraplength=700).pack(anchor='w')
        text_frame = ttk.Frame(frame)
        text_frame.pack(fill='both', expand=True, pady=8)
        self._coop_log_text = tk.Text(text_frame, width=100, height=22, wrap='word', state='disabled')
        scrollbar = ttk.Scrollbar(text_frame, command=self._coop_log_text.yview)
        self._coop_log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self._coop_log_text.pack(side='left', fill='both', expand=True)
        ttk.Button(frame, text='Copy connection log', command=self._copy_coop_log).pack(anchor='w')
        self._refresh_coop_log()

    def _copy_coop_log(self):
        self.clipboard_clear()
        self.clipboard_append('\n'.join(getattr(self, '_coop_connection_log', ())))

    def _refresh_coop_connection_fields(self):
        connected = bool(getattr(self, '_coop_lobby', None))
        joining = hasattr(self, '_coop_role') and self._coop_role.get() == 'Join'
        for name, visible in (('_coop_host_code_label', not joining), ('_coop_guest_code_entry', joining)):
            widget = getattr(self, name, None)
            if widget and widget.winfo_exists():
                widget.grid() if visible else widget.grid_remove()
        for widget in getattr(self, '_coop_address_widgets', ()):
            if widget.winfo_exists():
                if joining:
                    widget.grid()
                else:
                    widget.grid_remove()
        reveal = getattr(self, '_coop_show_details_check', None)
        if reveal and reveal.winfo_exists():
            reveal.configure(text='Show IP and code (visible on stream)')
            reveal.grid() if joining else reveal.grid_remove()
        for widget in getattr(self, '_coop_connection_entries', ()):
            if widget.winfo_exists():
                widget.configure(state='disabled' if connected else 'readonly' if isinstance(widget, ttk.Combobox) else 'normal')
        button = getattr(self, '_coop_start_button', None)
        if button and button.winfo_exists():
            button.configure(state='disabled' if connected else 'normal')

    def _coop_safe_message(self, value):
        private = [getattr(self, name).get() for name in
                   ('_coop_address', '_coop_pairing', '_coop_host_pairing') if hasattr(self, name)]
        lobby = getattr(self, '_coop_lobby', None)
        if lobby:
            private.extend((lobby.address, lobby.pairing_code))
        return redact_connection_details(value, *private)

    def _connect_coop_from_dialog(self):
        self._connect_coop(
            'host' if self._coop_role.get() == 'Host' else 'guest',
            self._coop_name.get(), self._coop_address.get(),
            pairing_code=self._coop_pairing_code(),
        )

    def _set_coop_status(self, message):
        variable = getattr(self, '_coop_status_var', None)
        if variable is not None:
            variable.set(self._coop_safe_message(message))
