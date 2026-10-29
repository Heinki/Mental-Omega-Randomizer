"""Resizable workspaces with reachable controls when either axis overflows."""

import tkinter as tk
from tkinter import ttk


def _route_wheel(event):
    """Scroll the nearest content canvas or settings viewport."""
    widget = event.widget
    while widget is not None:
        handler = getattr(widget, '_content_scroll_handler', None)
        if handler is not None:
            return handler(event)
        if isinstance(widget, ScrollableViewport):
            return widget._mousewheel(event)
        widget = getattr(widget, 'master', None)


class ScrollableViewport(ttk.Frame):
    def __init__(self, parent, background=None, *, padding=0):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(
            self, width=1, height=1, highlightthickness=0, borderwidth=0,
            background=background or ttk.Style(self).lookup('TFrame', 'background'),
            yscrollincrement=24, xscrollincrement=24,
        )
        self.vertical = ttk.Scrollbar(self, command=self.canvas.yview)
        self.horizontal = ttk.Scrollbar(self, orient='horizontal', command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.vertical.set, xscrollcommand=self.horizontal.set)
        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.vertical.grid(row=0, column=1, sticky='ns')
        self.horizontal.grid(row=1, column=0, sticky='ew')
        self.horizontal.grid_remove()
        self.content = ttk.Frame(self.canvas, padding=padding)
        self.window = self.canvas.create_window((0, 0), window=self.content, anchor='nw')
        self.layout = None
        self._pending = None
        self.canvas.bind('<Configure>', self._configure, add='+')
        self.content.bind('<Configure>', self._schedule_resize, add='+')
        self.bind('<Destroy>', self._destroy, add='+')
        root = self._root()
        if not getattr(root, '_viewport_wheel_bound', False):
            root._viewport_wheel_bound = True
            for sequence in ('<MouseWheel>', '<Shift-MouseWheel>', '<Button-4>', '<Button-5>'):
                root.bind_all(sequence, _route_wheel, add='+')

    def _destroy(self, event):
        if event.widget is self and self._pending is not None:
            self.after_cancel(self._pending)
            self._pending = None

    def _configure(self, event):
        if self.layout is not None:
            self.layout(event.width)
        self._schedule_resize()

    def _schedule_resize(self, _event=None):
        if self._pending is None:
            self._pending = self.after_idle(self._resize)

    def _resize(self):
        self._pending = None
        width = max(self.canvas.winfo_width(), self.content.winfo_reqwidth())
        height = max(self.canvas.winfo_height(), self.content.winfo_reqheight())
        self.canvas.itemconfigure(self.window, width=width, height=height)
        self.canvas.configure(scrollregion=(0, 0, width, height))
        if width > self.canvas.winfo_width():
            self.horizontal.grid()
        else:
            self.horizontal.grid_remove()
            self.canvas.xview_moveto(0)

    def bind_controls(self):
        """Keep nested lists scrolling locally, then scroll their outer pane."""
        tag = f'ViewportScroll:{self}'
        for sequence in ('<MouseWheel>', '<Shift-MouseWheel>', '<Button-4>', '<Button-5>'):
            self.bind_class(tag, sequence, self._mousewheel)

        def visit(widget):
            if isinstance(widget, ScrollableViewport) and widget is not self:
                return
            if isinstance(widget, ttk.Scrollbar):
                return
            if tag not in widget.bindtags():
                widget.bindtags((tag, *widget.bindtags()))
                widget.bind('<Configure>', self._schedule_resize, add='+')
            for child in widget.winfo_children():
                visit(child)

        visit(self)

    def _mousewheel(self, event):
        delta, number = getattr(event, 'delta', 0), getattr(event, 'num', 0)
        if not delta and number not in (4, 5):
            return
        direction = -1 if delta > 0 or number == 4 else 1
        axis = 'x' if event.state & 1 else 'y'
        widget = event.widget
        if widget is not self.canvas and isinstance(widget, (tk.Canvas, tk.Text, tk.Listbox, ttk.Treeview)):
            view = getattr(widget, axis + 'view')()
            if view and (view[0] > 0 if direction < 0 else view[1] < 1):
                return
        view = getattr(self.canvas, axis + 'view')()
        if view and (view[0] > 0 if direction < 0 else view[1] < 1):
            steps = max(1, abs(int(delta / 120)))
            getattr(self.canvas, axis + 'view_scroll')(direction * steps, 'units')
            return 'break'
        parent = self.master
        while parent is not None:
            if isinstance(parent, ScrollableViewport):
                return parent._mousewheel(event)
            parent = parent.master
        if isinstance(widget, ttk.Combobox):
            return 'break'


def fit_dialog(dialog, content, *, width=760, height=620):
    """Size dialogs to the display while leaving room for window decorations."""
    dialog.update_idletasks()
    width = min(width, content.winfo_reqwidth() + 32, max(1, dialog.winfo_screenwidth() - 80))
    height = min(height, content.winfo_reqheight() + 32, max(1, dialog.winfo_screenheight() - 100))
    dialog.geometry(f'{max(1, width)}x{max(1, height)}')
    dialog.minsize(min(320, width), min(240, height))
    dialog.resizable(True, True)
