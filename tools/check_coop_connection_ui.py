"""Exercise the actual co-op widgets without starting a network or game.

Requires a Tk display. Run with the runtime virtual environment.
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import queue
import sys
import tkinter as tk
from tkinter import ttk


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from check_coop_feature_gate import Gate
from randomizer.coop import feature
from randomizer.shop.model import RunStatus
from randomizer.ui.coop import build_coop_controls


class ConnectionUI(Gate, tk.Tk):
    def __init__(self):
        tk.Tk.__init__(self)
        self.withdraw()
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        Gate.__init__(self)
        self.coop_mode_var = tk.BooleanVar(master=self, value=False)
        self.workspace_tabs = ttk.Notebook(self)
        self.workspace_tabs.grid(row=0, column=0, sticky='nsew')
        self.other_tab = ttk.Frame(self.workspace_tabs)
        self.workspace_tabs.add(self.other_tab, text='Other')
        self.shop_run = None
        self.shop_selected = False
        self.locked = False
        self.calls = []
        self.coop_publish_state = lambda: None
        appearance = ttk.LabelFrame(self.other_tab, text='Mission Appearance')
        appearance.pack(fill='x', padx=8, pady=8)
        ttk.Label(appearance, text='Player color').grid(row=0, column=0)
        ttk.Checkbutton(appearance, text='Rainbowizer').grid(row=1, column=0)
        build_coop_controls(self, appearance, 2)
        shop = ttk.Frame(self.other_tab)
        shop.pack(fill='x')
        build_coop_controls(self, shop, 0, shop=True)

    def shop_mode_selected(self):
        return self.shop_selected

    def gameplay_settings_locked(self):
        return self.locked

    def _connect_coop(self, role, name, address, *, pairing_code=''):
        self.calls.append((role, name, address, pairing_code))


def main():
    original_feature = feature.COOP_FEATURE_ENABLED
    app = None
    try:
        feature.COOP_FEATURE_ENABLED = True
        app = ConnectionUI()
        app.refresh_coop_controls()
        assert app.coop_mode_check['text'] == 'Co-op mode (experimental)'
        assert app.coop_player_count_combo['values'] == ('2',)
        assert app.coop_player_count_var.get() == '2'
        assert app.coop_connection_button['text'] == 'Co-op Connection…'
        assert int(app.coop_controls_frame.grid_info()['row']) == 2
        assert int(app.coop_connection_button.grid_info()['row']) == 1
        assert len(app.workspace_tabs.tabs()) == 1
        app.coop_connection_button.invoke()
        app.update()
        assert isinstance(app._coop_dialog, tk.Toplevel)
        assert app.workspace_tabs.select() == str(app.other_tab)
        first_dialog = app._coop_dialog
        app.open_coop_dialog()
        assert app._coop_dialog is first_dialog
        assert not app.coop_mode_var.get()
        assert str(app._coop_start_button['state']) == 'disabled'
        assert str(app.coop_connection_button['state']) == 'normal'
        app._connect_coop_from_dialog()
        assert not app.calls

        app.coop_mode_var.set(True)
        app.refresh_coop_controls()
        assert str(app._coop_start_button['state']) == 'normal'
        assert app._coop_start_button['text'] == 'Connect'
        assert app._coop_host_code_label.grid_info()
        assert not app._coop_guest_code_entry.grid_info()
        assert not app._coop_address_widgets[1].grid_info()
        host_code = app._coop_host_pairing.get()
        app._coop_start_button.invoke()
        assert app.calls[-1] == ('host', 'CoopHost', '', host_code)

        app._coop_role.set('Join')
        app._on_coop_role_changed()
        app._coop_address.set('10.42.0.2')
        app._coop_pairing.set('guest-pairing-code-123456')
        assert app._coop_start_button['text'] == 'Connect'
        assert app._coop_name.get() == 'CoopGuest'
        assert app._coop_guest_code_entry.grid_info()
        assert app._coop_address_widgets[1].grid_info()
        assert not app._coop_host_code_label.grid_info()
        assert all(entry['show'] == '*' for entry in app._coop_private_entries)
        app._coop_show_details.set(True)
        app._toggle_coop_details()
        assert all(entry['show'] == '' for entry in app._coop_private_entries)
        app._close_coop_dialog()
        assert not first_dialog.winfo_exists()
        assert not app._coop_show_details.get()
        app.open_coop_dialog()
        assert all(entry['show'] == '*' for entry in app._coop_private_entries)
        assert app._coop_pairing.get() == 'guest-pairing-code-123456'
        assert app._coop_host_pairing.get() == host_code
        app._coop_start_button.invoke()
        assert app.calls[-1] == ('guest', 'CoopGuest', '10.42.0.2',
                                 'guest-pairing-code-123456')
        app._coop_role.set('Host')
        app._on_coop_role_changed()
        assert app._coop_pairing_code() == host_code

        closed = []
        app._coop_lobby = SimpleNamespace(
            role='host', address='', pairing_code=host_code,
            connected=True, events=queue.Queue(),
            close=lambda: closed.append(True),
        )
        app.refresh_coop_controls()
        app._set_coop_status('Waiting for guest…')
        assert str(app._coop_start_button['state']) == 'disabled'
        assert str(app._coop_disconnect_button['state']) == 'normal'
        assert str(app.coop_mode_check['state']) == 'disabled'
        app._close_coop_dialog()
        app._coop_lobby.events.put(('connected', 'CoopGuest'))
        app._poll_coop_lobby()
        app.coop_connection_button.invoke()
        assert app._coop_lobby is not None
        assert str(app._coop_disconnect_button['state']) == 'normal'
        assert app._coop_status_var.get() == 'Connected to CoopGuest. Host selects and launches.'
        app._coop_queue = queue.Queue()
        app._coop_queue.put(('error', 'Map preparation failed', 'Test diagnostic'))
        with patch('randomizer.application.coop_controller.messagebox.showerror') as error:
            app._poll_coop_session()
            error.assert_called_once()
        assert app._coop_status_var.get() == 'Game connection failed: Map preparation failed'
        app._coop_disconnect_button.invoke()
        assert closed == [True]
        assert app._coop_lobby is None
        assert app._coop_status_var.get() == 'Disconnected.'
        assert str(app._coop_disconnect_button['state']) == 'disabled'
        assert str(app._coop_start_button['state']) == 'normal'

        app.shop_selected = True
        app.shop_run = SimpleNamespace(status=RunStatus.ACTIVE)
        app.refresh_coop_controls()
        assert str(app.coop_mode_check['state']) == 'disabled'
        app.shop_run = None
        app.refresh_coop_controls()
        assert str(app.coop_mode_check['state']) == 'normal'
        app.locked = True
        app.refresh_coop_controls()
        assert str(app.coop_mode_check['state']) == 'disabled'

        feature.COOP_FEATURE_ENABLED = False
        app.refresh_coop_controls()
        assert not app.coop_controls_frame.grid_info()
        assert not app.shop_coop_row.grid_info()
        app._close_coop_dialog()
        app.open_coop_dialog()
        assert not app._coop_dialog.winfo_exists()
        feature.COOP_FEATURE_ENABLED = True
        app.refresh_coop_controls()
        assert app.coop_controls_frame.grid_info()
        app.shop_coop_connection_button.invoke()
        assert app._coop_dialog.winfo_exists()
        assert len(app.workspace_tabs.tabs()) == 1
        print('DTA-style settings controls, dialog access, Host/Join, masking, status, locks: passed')
    finally:
        feature.COOP_FEATURE_ENABLED = original_feature
        if app is not None:
            app.destroy()


if __name__ == '__main__':
    main()
