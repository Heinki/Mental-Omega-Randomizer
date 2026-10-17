"""A small, label-compatible Canvas with a moving rainbow background."""

import colorsys
import tkinter as tk


class AnimatedGradientLabel(tk.Canvas):
    """Draw readable label text over a reusable strip of rainbow rectangles.

    Only visible, enabled tiles own an animation callback. Keeping this a
    single widget also preserves the grid's click and tooltip bindings.
    """

    _STRIPES = 40
    _FRAME_MS = 90
    _LABEL_DEFAULTS = {
        'text': '',
        'foreground': '#ffffff',
        'font': ('Segoe UI', 9, 'bold'),
        'anchor': 'center',
        'justify': 'center',
        'wraplength': 0,
        'padx': 0,
        'pady': 0,
    }
    _ALIASES = {'fg': 'foreground', 'bg': 'background'}

    def __init__(self, master=None, **kwargs):
        self._label_options = self._LABEL_DEFAULTS.copy()
        for alias, name in self._ALIASES.items():
            if alias in kwargs:
                kwargs[name] = kwargs.pop(alias)
        for name in self._label_options:
            if name in kwargs:
                self._label_options[name] = kwargs.pop(name)
        kwargs.setdefault('background', '#315b82')
        kwargs.setdefault('borderwidth', 0)
        kwargs.setdefault('highlightthickness', 0)
        kwargs.setdefault('width', 1)
        kwargs.setdefault('height', 1)
        kwargs.setdefault('takefocus', 0)
        super().__init__(master, **kwargs)
        self._gradient_enabled = True
        self._animation_id = None
        self._phase = 0.0
        self._alive = True
        self._stripes = [
            self.create_rectangle(0, 0, 1, 1, outline='')
            for _ in range(self._STRIPES)
        ]
        self._text_item = self.create_text(0, 0)
        self._window = self.winfo_toplevel()
        self._window_bindings = {
            '<Map>': self._window.bind('<Map>', self._on_window_map, add='+'),
            '<Unmap>': self._window.bind('<Unmap>', self._on_window_unmap, add='+'),
        }
        self.bind('<Configure>', self._on_resize, add='+')
        self.bind('<Map>', self._on_map, add='+')
        self.bind('<Unmap>', self._on_unmap, add='+')
        self.bind('<Destroy>', self._on_destroy, add='+')
        self._update_requested_size()
        self._redraw()

    def configure(self, cnf=None, **kwargs):
        """Accept the label options used by the mission grid."""
        if isinstance(cnf, str):
            name = self._ALIASES.get(cnf, cnf)
            if name in self._label_options:
                return (name, name, name.title(),
                        self._LABEL_DEFAULTS[name], self._label_options[name])
            return super().configure(name)
        options = dict(cnf or {})
        options.update(kwargs)
        if not options:
            result = super().configure()
            result.update({name: self.configure(name)
                           for name in self._label_options})
            return result
        for alias, name in self._ALIASES.items():
            if alias in options:
                options[name] = options.pop(alias)
        label_changed = False
        for name in self._label_options:
            if name in options:
                value = options.pop(name)
                label_changed |= self._label_options[name] != value
                self._label_options[name] = value
        result = super().configure(**options) if options else None
        if hasattr(self, '_text_item'):
            if label_changed:
                self._update_requested_size()
            self._redraw()
        return result

    config = configure

    def cget(self, key):
        name = self._ALIASES.get(key, key)
        if name in self._label_options:
            return self._label_options[name]
        return super().cget(name)

    __getitem__ = cget

    def set_gradient_enabled(self, enabled):
        """Use the configured solid background for locked or hidden tiles."""
        enabled = bool(enabled)
        if self._gradient_enabled != enabled:
            self._gradient_enabled = enabled
            self._redraw()
        if enabled:
            self._resume_animation()
        else:
            self._cancel_animation()

    def _pixels(self, name):
        return max(0, self.winfo_pixels(self._label_options[name]))

    def _update_requested_size(self):
        options = self._label_options
        self.itemconfigure(
            self._text_item,
            text=options['text'],
            fill=options['foreground'],
            font=options['font'],
            justify=options['justify'],
            anchor='nw',
            width=self._pixels('wraplength'),
        )
        self.coords(self._text_item, 0, 0)
        bounds = self.bbox(self._text_item) or (0, 0, 1, 1)
        super().configure(
            width=max(1, bounds[2] - bounds[0]) + 2 * self._pixels('padx'),
            height=max(1, bounds[3] - bounds[1]) + 2 * self._pixels('pady'),
        )

    def _redraw(self):
        if not self._alive:
            return
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        stripe_state = 'normal' if self._gradient_enabled else 'hidden'
        for index, stripe in enumerate(self._stripes):
            self.coords(
                stripe,
                index * width // self._STRIPES,
                0,
                (index + 1) * width // self._STRIPES + 1,
                height,
            )
            self.itemconfigure(stripe, state=stripe_state)
        if self._gradient_enabled:
            self._paint_colors()
        options = self._label_options
        padx, pady = self._pixels('padx'), self._pixels('pady')
        anchor = options['anchor']
        x, y = width / 2, height / 2
        if anchor != 'center':
            x = padx if 'w' in anchor else width - padx if 'e' in anchor else x
            y = pady if 'n' in anchor else height - pady if 's' in anchor else y
        wraplength = self._pixels('wraplength')
        available = max(1, width - 2 * padx)
        self.itemconfigure(
            self._text_item,
            text=options['text'],
            fill=options['foreground'],
            font=options['font'],
            justify=options['justify'],
            anchor=anchor,
            width=min(available, wraplength) if wraplength else available,
        )
        self.coords(self._text_item, x, y)
        self.tag_raise(self._text_item)

    def _paint_colors(self):
        for index, stripe in enumerate(self._stripes):
            hue = (self._phase + index / self._STRIPES) % 1.0
            rgb = colorsys.hsv_to_rgb(hue, 0.76, 0.43)
            color = '#{:02x}{:02x}{:02x}'.format(
                *(round(channel * 255) for channel in rgb)
            )
            self.itemconfigure(stripe, fill=color)

    def _visible(self):
        return (
            self._alive
            and self.winfo_viewable()
            and self._window.wm_state() not in ('withdrawn', 'iconic')
        )

    def _resume_animation(self):
        if (self._gradient_enabled and self._animation_id is None
                and self._visible()):
            self._animation_id = self.after(self._FRAME_MS, self._animate)

    def _animate(self):
        self._animation_id = None
        if not self._gradient_enabled or not self._visible():
            return
        self._phase = (self._phase + 0.012) % 1.0
        self._paint_colors()
        self._resume_animation()

    def _cancel_animation(self):
        if self._animation_id is not None:
            try:
                self.after_cancel(self._animation_id)
            except tk.TclError:
                pass
            self._animation_id = None

    def _on_resize(self, _event):
        self._redraw()

    def _on_map(self, _event):
        self._resume_animation()

    def _on_unmap(self, _event):
        self._cancel_animation()

    def _on_window_map(self, event):
        if event.widget is self._window:
            self._resume_animation()

    def _on_window_unmap(self, event):
        if event.widget is self._window:
            self._cancel_animation()

    def _on_destroy(self, event):
        if event.widget is not self:
            return
        self._alive = False
        self._cancel_animation()
        for sequence, binding_id in self._window_bindings.items():
            try:
                self._window.unbind(sequence, binding_id)
            except tk.TclError:
                pass
        self._window_bindings.clear()
