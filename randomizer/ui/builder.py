"""Public launcher widget-construction facade."""

from .layout import _build_info_tabs, _build_right_panel, _build_window_shell
from .overlay import _build_log_and_overlay
from .settings import _build_advanced_tab, _build_gameplay_settings
from .archipelago import build_archipelago_tab
from .shop import build_shop_tab


def create_widgets(self):
    """Construct launcher widgets by delegating each cohesive UI region."""
    main_frame = _build_window_shell(self)
    info_tabs, _, settings_frame = _build_right_panel(
        self,
        main_frame,
    )
    _build_info_tabs(self, info_tabs)
    build_shop_tab(self, self.workspace_tabs)
    _build_advanced_tab(self, self.workspace_tabs)
    build_archipelago_tab(self, self.workspace_tabs)
    _build_gameplay_settings(self, settings_frame)
    self.sync_shop_workspace()
    self.layout_settings_sections(self.settings_canvas.winfo_width())
    self.initialize_archipelago_control_registry()
    self.refresh_archipelago_yaml_status()
    self.refresh_setting_states()
    _build_log_and_overlay(self, main_frame)
