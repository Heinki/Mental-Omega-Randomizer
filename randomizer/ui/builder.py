"""Public launcher widget-construction facade."""

from .layout import _build_info_tabs, _build_right_panel, _build_window_shell
from .overlay import _build_log_and_overlay
from .settings import _build_advanced_tab, _build_gameplay_settings


def create_widgets(self):
    """Construct launcher widgets by delegating each cohesive UI region."""
    main_frame = _build_window_shell(self)
    info_tabs, settings_tab, settings_frame = _build_right_panel(
        self,
        main_frame,
    )
    _build_info_tabs(self, info_tabs)
    _build_advanced_tab(self, self.workspace_tabs)
    _build_gameplay_settings(self, settings_frame)
    self.refresh_setting_states()
    _build_log_and_overlay(self, main_frame)
