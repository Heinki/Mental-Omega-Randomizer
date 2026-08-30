"""Shared Tk tooltip ownership and lifecycle."""

import tkinter as tk
from tkinter import ttk


_active_tooltip = None
_TOOLTIP_MARGIN = 4


def _owner_bounds(widget):
    """Return client-area screen bounds for the window owning a widget."""
    owner = widget.winfo_toplevel()
    owner.update_idletasks()
    left = owner.winfo_rootx()
    top = owner.winfo_rooty()
    return (
        left,
        top,
        left + max(1, owner.winfo_width()),
        top + max(1, owner.winfo_height()),
    )


def _confined_tooltip_position(
    widget,
    tip_width,
    tip_height,
    pointer_x,
    pointer_y,
    horizontal_gap,
    vertical_gap,
):
    """Place a tooltip beside the pointer inside its launcher window."""
    left, top, right, bottom = _owner_bounds(widget)
    x = pointer_x + horizontal_gap
    if x + tip_width > right - _TOOLTIP_MARGIN:
        x = pointer_x - horizontal_gap - tip_width
    maximum_x = max(left + _TOOLTIP_MARGIN, right - tip_width - _TOOLTIP_MARGIN)
    maximum_y = max(top + _TOOLTIP_MARGIN, bottom - tip_height - _TOOLTIP_MARGIN)
    return (
        max(left + _TOOLTIP_MARGIN, min(x, maximum_x)),
        max(
            top + _TOOLTIP_MARGIN,
            min(pointer_y + vertical_gap, maximum_y),
        ),
    )


def _activate_tooltip(owner):
    global _active_tooltip
    if _active_tooltip is not None and _active_tooltip is not owner:
        _active_tooltip.hide()
    _active_tooltip = owner


def _deactivate_tooltip(owner):
    global _active_tooltip
    if _active_tooltip is owner:
        _active_tooltip = None


class WidgetTooltip:
    """Delayed tooltip for any Tk widget."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        self.pending_show = None
        self.pending_hide = None
        widget.bind('<Enter>', self.schedule_show, add='+')
        widget.bind('<Leave>', self.schedule_hide, add='+')
        widget.bind('<ButtonPress>', self.hide, add='+')
        widget.bind('<Unmap>', self.hide, add='+')
        widget.bind('<Destroy>', self.hide, add='+')

    def schedule_show(self, _event=None):
        self.cancel_pending_hide()
        self.cancel_pending_show()
        self.pending_show = self.widget.after(250, self.show)

    def cancel_pending_show(self):
        if self.pending_show is not None:
            try:
                self.widget.after_cancel(self.pending_show)
            except tk.TclError:
                pass
            self.pending_show = None

    def cancel_pending_hide(self):
        if self.pending_hide is not None:
            try:
                self.widget.after_cancel(self.pending_hide)
            except tk.TclError:
                pass
            self.pending_hide = None

    def schedule_hide(self, _event=None):
        self.cancel_pending_hide()

        def hide_if_outside():
            self.pending_hide = None
            try:
                pointer_x = self.widget.winfo_pointerx()
                pointer_y = self.widget.winfo_pointery()
                left = self.widget.winfo_rootx()
                top = self.widget.winfo_rooty()
                inside = (
                    left <= pointer_x < left + self.widget.winfo_width()
                    and top <= pointer_y < top + self.widget.winfo_height()
                )
            except tk.TclError:
                inside = False
            if not inside:
                self.hide()

        self.pending_hide = self.widget.after(30, hide_if_outside)

    def show(self, _event=None):
        self.pending_show = None
        if self.tip is not None or not self.text:
            return
        _activate_tooltip(self)
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        try:
            self.tip.wm_attributes('-disabled', True)
        except tk.TclError:
            pass
        label = ttk.Label(
            self.tip,
            text=self.text,
            justify='left',
            font=('Segoe UI', 10),
            padding=(8, 6, 8, 6),
            relief='solid',
            wraplength=380,
        )
        label.grid(row=0, column=0)
        self.tip.update_idletasks()
        tip_width = self.tip.winfo_reqwidth()
        tip_height = self.tip.winfo_reqheight()
        pointer_x = self.widget.winfo_pointerx()
        pointer_y = self.widget.winfo_pointery()
        x, y = _confined_tooltip_position(
            self.widget,
            tip_width,
            tip_height,
            pointer_x,
            pointer_y,
            24,
            12,
        )
        self.tip.wm_geometry(f'+{x}+{y}')

    def hide(self, _event=None):
        self.cancel_pending_show()
        self.cancel_pending_hide()
        if self.tip is not None:
            try:
                self.tip.destroy()
            except tk.TclError:
                pass
            self.tip = None
        _deactivate_tooltip(self)


class TreeTooltip:
    """Immediate row-aware tooltip for a ttk Treeview."""

    def __init__(self, tree, text_callback):
        self.tree = tree
        self.text_callback = text_callback
        self.tip = None
        self.current_row = None
        tree.bind('<Motion>', self.on_motion, add='+')
        tree.bind('<Leave>', self.hide, add='+')
        tree.bind('<Unmap>', self.hide, add='+')
        tree.bind('<Destroy>', self.hide, add='+')

    def on_motion(self, event):
        row = self.tree.identify_row(event.y)
        if not row:
            self.hide()
            return

        text = self.text_callback(row)
        if not text:
            self.hide()
            return

        pointer_x = self.tree.winfo_rootx() + event.x
        pointer_y = self.tree.winfo_rooty() + event.y
        if row != self.current_row:
            self.hide()
            self.current_row = row
            _activate_tooltip(self)
            self.tip = tk.Toplevel(self.tree)
            self.tip.wm_overrideredirect(True)
            if 'AI Reward:' in text:
                self._build_reward_tooltip(text)
            else:
                label = ttk.Label(
                    self.tip,
                    text=text,
                    justify='left',
                    padding=(8, 6, 8, 6),
                    relief='solid',
                    wraplength=620,
                )
                label.grid(row=0, column=0)
        self.tip.update_idletasks()
        x, y = _confined_tooltip_position(
            self.tree,
            self.tip.winfo_reqwidth(),
            self.tip.winfo_reqheight(),
            pointer_x,
            pointer_y,
            18,
            12,
        )
        self.tip.wm_geometry(f'+{x}+{y}')

    def _build_reward_tooltip(self, text):
        """Render enemy-reward lines red while preserving normal reward text."""
        style = ttk.Style(self.tree)
        background = style.lookup('TFrame', 'background') or 'SystemButtonFace'
        foreground = style.lookup('TLabel', 'foreground') or 'SystemButtonText'
        red = '#b00020'
        try:
            red = (
                '#ff7b72'
                if sum(self.tree.winfo_rgb(background)) < 3 * 32768
                else '#b00020'
            )
        except tk.TclError:
            pass
        frame = tk.Frame(
            self.tip,
            background=background,
            borderwidth=1,
            relief='solid',
            padx=8,
            pady=6,
        )
        frame.grid(row=0, column=0)
        for row, line in enumerate(text.splitlines()):
            label = tk.Label(
                frame,
                text=line or ' ',
                background=background,
                foreground=red if 'AI Reward:' in line else foreground,
                justify='left',
                anchor='w',
                wraplength=620,
            )
            label.grid(row=row, column=0, sticky='w')

    def hide(self, _event=None):
        self.current_row = None
        if self.tip is not None:
            try:
                self.tip.destroy()
            except tk.TclError:
                pass
            self.tip = None
        _deactivate_tooltip(self)
