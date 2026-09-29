"""Check default-off co-op UI gate and saved mode switching."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from randomizer.application import coop_controller
from randomizer.application.coop_controller import CoopController
from randomizer.config.player import DEFAULT_CONFIG


class Variable:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class Widget:
    visible = True

    def grid(self):
        self.visible = True

    def grid_remove(self):
        self.visible = False

    def configure(self, **_options):
        pass


class Gate(CoopController):
    def __init__(self):
        self.config = {'coop_mode': False, 'coop_feature_enabled': False}
        self.state = {}
        self.coop_feature_enabled_var = Variable(False)
        self.coop_mode_var = Variable(False)
        self.campaign_var = Variable('All Campaigns')
        self.progression_mode_var = Variable('Grid Mode')
        self.reward_mode_var = Variable('Chaos')
        self.active_game_process = None
        self._coop_lobby = None
        for name in (
            'coop_mode_check', 'coop_connection_button',
            'compact_coop_button', 'shop_coop_row',
            'shop_coop_connection_button', 'campaign_combo',
            'rewards_per_check_label', 'launch_selected_button',
            'compact_launch_button', 'debug_complete_button',
            'compact_complete_button',
        ):
            setattr(self, name, Widget())

    def sync_debug_completion_controls(self):
        pass

    def refresh_shop_settings_controls(self):
        pass

    def update_header_summary(self):
        pass

    def gameplay_settings_locked(self):
        return False

    def shop_mode_selected(self):
        return False

    def load_state(self):
        return {}

    def migrate_state(self):
        pass

    def apply_missions(self, _missions):
        pass

    def load_missions(self):
        return []

    def redraw_progression_views(self):
        pass

    def refresh_progress_view(self):
        pass

    def refresh_setting_states(self):
        pass

    def append_log(self, _message):
        pass


def main():
    assert DEFAULT_CONFIG['coop_feature_enabled'] is False
    saves = []
    original = coop_controller.save_config
    coop_controller.save_config = lambda config: saves.append(dict(config))
    try:
        app = Gate()
        app.refresh_coop_controls()
        assert not app.coop_mode_check.visible
        assert not app.coop_connection_button.visible
        assert not app.compact_coop_button.visible
        assert not app.shop_coop_row.visible
        app.coop_feature_enabled_var.set(True)
        app.on_coop_feature_enabled_changed()
        assert app.coop_mode_check.visible
        assert app.shop_coop_row.visible
        app.coop_mode_var.set(True)
        app.on_coop_mode_changed()
        assert app.config['coop_mode'] is True
        app.coop_feature_enabled_var.set(False)
        app.on_coop_feature_enabled_changed()
        assert app.config['coop_feature_enabled'] is False
        assert app.config['coop_mode'] is False
        assert not app.coop_mode_check.visible
        app.coop_mode_var.set(True)
        app.on_coop_mode_changed()
        assert app.coop_mode_var.get() is False
        assert saves[-1]['coop_feature_enabled'] is False
    finally:
        coop_controller.save_config = original
    print('Default-off co-op gate, UI visibility, mode switching: passed')


if __name__ == '__main__':
    main()
