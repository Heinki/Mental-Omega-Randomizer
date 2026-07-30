"""Integer-only slider with a visible filled track and editable value field."""

import tkinter as tk
from tkinter import ttk


class IntegerSlider(ttk.Frame):
    """Bounded integer slider rendered consistently across Tk themes."""

    TRACK_HEIGHT = 9
    HANDLE_RADIUS = 11
    CANVAS_HEIGHT = 34

    def __init__(
        self,
        parent,
        *,
        variable,
        minimum=0,
        maximum=100,
        command=None,
        palette=None,
    ):
        super().__init__(parent)
        self.variable = variable
        self.minimum = int(minimum)
        self.maximum = max(self.minimum, int(maximum))
        self.command = command
        self.palette = dict(palette or {})
        self._current_value = self.minimum
        self._syncing_external = False
        self._syncing_field = False
        self._hovered = False

        self.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(
            self,
            width=250,
            height=self.CANVAS_HEIGHT,
            borderwidth=0,
            highlightthickness=2,
            takefocus=True,
            cursor='hand2',
        )
        self.canvas.grid(row=0, column=0, sticky='ew')

        self.field_var = tk.StringVar()
        validation = (self.register(self._valid_field_text), '%P')
        self.value_entry = ttk.Entry(
            self,
            textvariable=self.field_var,
            width=4,
            justify='right',
            validate='key',
            validatecommand=validation,
        )
        self.value_entry.grid(row=0, column=1, sticky='e', padx=(10, 0))

        self.canvas.bind('<Configure>', self._redraw, add='+')
        self.canvas.bind('<Button-1>', self._on_pointer, add='+')
        self.canvas.bind('<B1-Motion>', self._on_pointer, add='+')
        self.canvas.bind('<Enter>', self._on_enter, add='+')
        self.canvas.bind('<Leave>', self._on_leave, add='+')
        self.canvas.bind('<FocusIn>', self._redraw, add='+')
        self.canvas.bind('<FocusOut>', self._redraw, add='+')
        self.canvas.bind('<Left>', lambda _event: self._step(-1), add='+')
        self.canvas.bind('<Down>', lambda _event: self._step(-1), add='+')
        self.canvas.bind('<Right>', lambda _event: self._step(1), add='+')
        self.canvas.bind('<Up>', lambda _event: self._step(1), add='+')
        self.canvas.bind('<Home>', lambda _event: self._set_from_user(self.minimum), add='+')
        self.canvas.bind('<End>', lambda _event: self._set_from_user(self.maximum), add='+')

        self.value_entry.bind('<Return>', self._commit_field, add='+')
        self.value_entry.bind('<FocusOut>', self._commit_field, add='+')
        self.value_entry.bind('<Escape>', self._cancel_field, add='+')
        self.value_entry.bind('<Up>', lambda _event: self._step(1), add='+')
        self.value_entry.bind('<Down>', lambda _event: self._step(-1), add='+')

        self._variable_trace = self.variable.trace_add(
            'write', self._on_external_value_changed
        )
        self._field_trace = self.field_var.trace_add(
            'write', self._on_field_value_changed
        )
        self.bind('<Destroy>', self._on_destroy, add='+')

        self._sync_from_variable()
        self.refresh_theme(self.palette)

    def get(self):
        return self._current_value

    def set(self, value):
        self._set_value(value)

    def refresh_theme(self, palette):
        self.palette = dict(palette or {})
        background = self.palette.get('background', '#f0f0f0')
        accent = self.palette.get('select', '#3478bd')
        self.canvas.configure(
            background=background,
            highlightbackground=background,
            highlightcolor=accent,
        )
        self._redraw()

    def _raw_variable_value(self):
        try:
            return self.variable._tk.globalgetvar(self.variable._name)
        except (AttributeError, tk.TclError):
            return self._current_value

    def _clamp(self, value):
        try:
            value = int(str(value).strip())
        except (TypeError, ValueError):
            value = self._current_value
        return max(self.minimum, min(self.maximum, value))

    def _set_value(self, value, *, notify=False):
        value = self._clamp(value)
        raw_value = str(self._raw_variable_value()).strip()
        if raw_value != str(value):
            self._syncing_external = True
            try:
                self.variable.set(value)
            finally:
                self._syncing_external = False
        self._current_value = value
        self._sync_field()
        self._redraw()
        if notify and self.command is not None:
            self.command(value)
        return 'break'

    def _set_from_user(self, value):
        return self._set_value(value, notify=True)

    def _sync_from_variable(self):
        self._set_value(self._raw_variable_value())

    def _on_external_value_changed(self, *_args):
        if not self._syncing_external:
            self._sync_from_variable()

    def _sync_field(self):
        expected = str(self._current_value)
        if self.field_var.get() == expected:
            return
        self._syncing_field = True
        try:
            self.field_var.set(expected)
        finally:
            self._syncing_field = False

    @staticmethod
    def _valid_field_text(proposed):
        if proposed in {'', '-'}:
            return True
        if proposed.startswith('-'):
            return proposed[1:].isdigit()
        return proposed.isdigit()

    def _on_field_value_changed(self, *_args):
        if self._syncing_field:
            return
        text = self.field_var.get()
        if text in {'', '-'}:
            return
        try:
            entered = int(text)
        except ValueError:
            self._sync_field()
            return
        bounded = max(self.minimum, min(self.maximum, entered))
        if text != str(bounded):
            self._syncing_field = True
            try:
                self.field_var.set(str(bounded))
            finally:
                self._syncing_field = False
        self._set_from_user(bounded)

    def _commit_field(self, _event=None):
        text = self.field_var.get()
        if text in {'', '-'}:
            self._sync_field()
        else:
            self._set_from_user(text)
        return 'break'

    def _cancel_field(self, _event=None):
        self._sync_field()
        self.canvas.focus_set()
        return 'break'

    def _step(self, amount):
        return self._set_from_user(self._current_value + int(amount))

    def _track_bounds(self):
        width = max(self.canvas.winfo_width(), self.canvas.winfo_reqwidth())
        inset = self.HANDLE_RADIUS + 3
        return inset, max(inset + 1, width - inset)

    def _on_pointer(self, event):
        self.canvas.focus_set()
        start, end = self._track_bounds()
        fraction = (max(start, min(end, event.x)) - start) / (end - start)
        value = self.minimum + round(fraction * (self.maximum - self.minimum))
        return self._set_from_user(value)

    def _on_enter(self, _event=None):
        self._hovered = True
        self._redraw()

    def _on_leave(self, _event=None):
        self._hovered = False
        self._redraw()

    def _redraw(self, _event=None):
        if not self.canvas.winfo_exists():
            return
        palette = self.palette
        remaining = palette.get('border', '#b8bec5')
        filled = palette.get('select', '#3478bd')
        handle_fill = palette.get('select_foreground', '#ffffff')
        start, end = self._track_bounds()
        middle = self.CANVAS_HEIGHT // 2
        span = self.maximum - self.minimum
        fraction = (
            (self._current_value - self.minimum) / span
            if span
            else 0
        )
        handle_x = start + ((end - start) * fraction)
        radius = self.HANDLE_RADIUS + (1 if self._hovered else 0)

        self.canvas.delete('all')
        self.canvas.create_line(
            start,
            middle,
            end,
            middle,
            fill=remaining,
            width=self.TRACK_HEIGHT,
            capstyle=tk.ROUND,
        )
        if handle_x > start:
            self.canvas.create_line(
                start,
                middle,
                handle_x,
                middle,
                fill=filled,
                width=self.TRACK_HEIGHT,
                capstyle=tk.ROUND,
            )
        self.canvas.create_oval(
            handle_x - radius,
            middle - radius,
            handle_x + radius,
            middle + radius,
            fill=handle_fill,
            outline=filled,
            width=3,
        )

    def _on_destroy(self, event):
        if event.widget is not self:
            return
        try:
            self.variable.trace_remove('write', self._variable_trace)
            self.field_var.trace_remove('write', self._field_trace)
        except (AttributeError, tk.TclError):
            pass
