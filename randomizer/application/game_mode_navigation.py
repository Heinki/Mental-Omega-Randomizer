"""Mode navigation independent of gameplay configuration and run state."""

from randomizer.final_fortress import DISPLAY_NAME
from randomizer.ui.game_modes import build_game_mode_navigation


class GameModeNavigationController:
    def initialize_game_mode_navigation(self):
        self._game_mode_settings_scroll = {}
        self._game_mode_page_open = False
        build_game_mode_navigation(self)
        self.show_game_mode_selection()

    def available_game_modes(self):
        return tuple(self.game_mode_choices)

    def game_mode_switch_locked(self):
        process = getattr(self, 'active_game_process', None)
        return bool(
            self.gameplay_settings_locked()
            or getattr(self, 'busy_depth', 0)
            or getattr(self, '_coop_lobby', None)
            or getattr(self, '_coop_busy', False)
            or getattr(self, '_challenge_preparing', False)
            or getattr(self, '_fortress_lobby', None)
            or getattr(self, '_fortress_lobbies', None)
            or getattr(self, '_final_fortress_preparing', False)
            or getattr(self, '_final_fortress_watch', None)
            or self.shop_launch_active()
            or (process is not None and process.poll() is None)
        )

    def refresh_game_mode_navigation(self):
        if not hasattr(self, 'game_mode_selection_frame'):
            return
        current = self.game_mode_var.get()
        locked = self.game_mode_switch_locked()
        available = self.available_game_modes()
        for mode, button in self.game_mode_buttons.items():
            button.configure(state=(
                'normal' if mode in available and (not locked or mode == current) else 'disabled'
            ))
        self.game_mode_selection_hint.configure(text=(
            f'Current mode: {current}. Mode switching is locked while a game, lobby, '
            'or connected session is active. You can return to the current mode.'
            if locked else 'Choose a mode to configure its settings. Back returns here '
            'without starting a game or resetting your settings.'
        ))
        viewport = self.game_mode_selection_viewport
        viewport.layout(viewport.canvas.winfo_width())

    def show_game_mode_selection(self):
        """Leave all settings and runs untouched when returning to the menu."""
        if self._game_mode_page_open:
            self._game_mode_settings_scroll[self.game_mode_var.get()] = self.settings_canvas.yview()[0]
        self._game_mode_page_open = False
        self.main_frame.grid_remove()
        self.game_mode_navigation.grid_remove()
        self.game_mode_selection_frame.grid(row=0, column=0, rowspan=2, sticky='nsew')
        self.refresh_game_mode_navigation()
        for mode in self.available_game_modes():
            button = self.game_mode_buttons[mode]
            if not button.instate(('disabled',)):
                button.focus_set()
                break

    def open_game_mode_settings(self, mode):
        """Apply a mode only from its selection card, then reveal existing setup."""
        if mode not in self.available_game_modes():
            return
        previous = self.game_mode_var.get()
        if mode != previous:
            if self.game_mode_switch_locked():
                self.refresh_game_mode_navigation()
                return
            self.game_mode_var.set(mode)
            if not self.apply_game_mode_selection():
                self.game_mode_var.set(previous)
                self.refresh_game_mode_navigation()
                return
        self._game_mode_page_open = True
        self.game_mode_page_label.configure(text=f'{mode} Settings')
        self.game_mode_selection_frame.grid_remove()
        self.game_mode_navigation.grid(row=0, column=0, sticky='ew')
        self.main_frame.grid()
        self._compact_details_visible = False
        self.__dict__.pop('_workspace_layout_signature', None)
        self.sync_workspace_layout()
        target = self.final_fortress_tab if mode == DISPLAY_NAME else self.settings_tab
        self.workspace_tabs.select(target)
        self.layout_settings_sections(self.settings_canvas.winfo_width())
        self.settings_canvas.yview_moveto(self._game_mode_settings_scroll.get(mode, 0))
        self.game_mode_back_button.focus_set()
