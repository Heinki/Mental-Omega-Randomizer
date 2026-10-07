"""Check Shop-host guidance for a Grid guest without changing saved runs."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import queue
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from randomizer.application.coop_controller import CoopController
from randomizer.shop.model import RunStatus


class Variable:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class Guest(CoopController):
    def __init__(self, run=None, mode='Grid Mode'):
        self.coop_mode_var = Variable(True)
        self.progression_mode_var = Variable(mode)
        self.seed_var = Variable('LOCAL-SEED')
        self.state = {'local': True}
        self.active_game_process = None
        self.shop_repository = SimpleNamespace(load_run=lambda: run)
        self.settings_tab = 'shop-setup'
        self.selected_tabs = []
        self.workspace_tabs = SimpleNamespace(select=self.selected_tabs.append)
        self.logs = []
        self.closed = []
        self.sent = []
        self.scheduled = []
        self.workspaces = []
        self._coop_lobby = SimpleNamespace(
            role='guest', connected=True, events=queue.Queue(),
            close=lambda: self.closed.append(True), send=self.sent.append,
        )
        # Exercise actual disconnect restoration before opening Shop setup.
        self._coop_local_snapshot = (
            self.state, {'progression_mode_var': mode, 'seed_var': 'LOCAL-SEED'},
        )

    def shop_mode_selected(self):
        return self.progression_mode_var.get() == 'Shop Mode'

    def _record_coop_log(self, message, **_kwargs):
        self.logs.append(message)

    def _set_coop_status(self, message):
        self.status = message

    def refresh_coop_controls(self):
        pass

    def _refresh_coop_connection_fields(self):
        pass

    def _refresh_coop_state_views(self):
        pass

    def refresh_setting_states(self):
        pass

    def sync_shop_workspace(self):
        self.workspaces.append(self.progression_mode_var.get())

    def after(self, *args):
        self.scheduled.append(args)


def check_case(run=None, mode='Grid Mode'):
    guest = Guest(run, mode)
    guest._coop_lobby.events.put(('connected', 'Host'))
    guest._coop_lobby.events.put(('message', {
        'type': 'shop_stage', 'data': {'seed': 'HOST-SEED', 'stage': 1},
    }))
    with patch('randomizer.application.coop_controller.messagebox.showwarning') as warning:
        guest._poll_coop_lobby()
        warning.assert_called_once()
        assert 'HOST-SEED' in warning.call_args.args[1]
        assert 'same stage' in warning.call_args.args[1]
    assert guest._coop_lobby is None
    assert guest.closed == [True]
    assert not guest.sent and not guest.scheduled
    assert guest.progression_mode_var.get() == 'Shop Mode'
    assert guest.workspaces == ['Shop Mode']
    assert guest.selected_tabs == ['shop-setup']
    assert guest.shop_repository.load_run() is run
    expected_seed = 'LOCAL-SEED' if run and run.status is RunStatus.ACTIVE else 'HOST-SEED'
    assert guest.seed_var.get() == expected_seed
    assert guest.state == {'local': True}
    assert guest.status == 'Shop setup required. Start a matching run, then reconnect.'


def main():
    check_case()
    check_case(mode='Shop Mode')
    check_case(SimpleNamespace(status=RunStatus.ACTIVE, run_coins=37,
                               run_purchases=('guest-only',)))
    check_case(SimpleNamespace(status=RunStatus.COMPLETED))
    guest = Guest()
    guest._coop_lobby.events.put(('message', {
        'type': 'shop_stage', 'data': {'seed': 'HOST-SEED', 'stage': True},
    }))
    with patch('randomizer.application.coop_controller.messagebox.showwarning') as warning:
        guest._poll_coop_lobby()
        warning.assert_not_called()
    assert guest.progression_mode_var.get() == 'Grid Mode'
    assert guest.seed_var.get() == 'LOCAL-SEED'
    print('Grid guest Shop guidance, host seed, disconnect, saved run preservation: passed')


if __name__ == '__main__':
    main()
