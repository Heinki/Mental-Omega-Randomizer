"""Grid Mode widget construction and redraw behavior."""

import tkinter as tk
from tkinter import ttk


def redraw_grid(self):
    """Rebuild the mission grid only when its topology changes."""
    grid = self.state.get('grid') if self.state else None
    content_frame = self.grid_content_frame
    if not isinstance(grid, dict) or not grid.get('nodes'):
        if self.grid_render_signature != ('empty',):
            for child in content_frame.winfo_children():
                child.destroy()
            for column in range(self.grid_configured_width):
                content_frame.columnconfigure(
                    column, weight=0, minsize=0, uniform=''
                )
            for row in range(self.grid_configured_height):
                content_frame.rowconfigure(
                    row, weight=0, minsize=0, uniform=''
                )
            self.grid_configured_width = 1
            self.grid_configured_height = 1
            self.grid_tile_widgets = {}
            self.grid_render_signature = ('empty',)
            ttk.Label(
                content_frame,
                text='Generate a Grid Mode seed to create the mission grid.',
                anchor='center',
                justify='center',
            ).grid(row=0, column=0, sticky='nsew', padx=20, pady=20)
            content_frame.columnconfigure(0, weight=1)
            content_frame.rowconfigure(0, weight=1)
            self.grid_canvas.xview_moveto(0)
            self.grid_canvas.yview_moveto(0)
            self.after_idle(self.resize_grid_canvas_window)
        return

    index_by_code = {
        mission['code']: index for index, mission in enumerate(self.missions)
    }
    width = int(grid.get('width', 1))
    height = int(grid.get('height', 1))
    signature = (
        'grid',
        width,
        height,
        tuple(
            sorted(
                (code, int(node['x']), int(node['y']))
                for code, node in grid['nodes'].items()
            )
        ),
    )
    if signature == self.grid_render_signature:
        self.refresh_grid_tiles()
        return

    for child in content_frame.winfo_children():
        child.destroy()
    self.grid_tile_widgets = {}
    self.grid_render_signature = signature
    for column in range(max(width, self.grid_configured_width)):
        content_frame.columnconfigure(column, weight=0, minsize=0, uniform='')
    for row in range(max(height, self.grid_configured_height)):
        content_frame.rowconfigure(row, weight=0, minsize=0, uniform='')
    self.grid_configured_width = width
    self.grid_configured_height = height
    for column in range(width):
        content_frame.columnconfigure(
            column,
            weight=1,
            minsize=105,
            uniform='grid-column',
        )
    for row in range(height):
        content_frame.rowconfigure(
            row,
            weight=1,
            minsize=88,
            uniform='grid-row',
        )

    positions = {
        (node['x'], node['y']): code
        for code, node in grid['nodes'].items()
    }
    # Create every coordinate slot, including a quiet background for a
    # trimmed corner. This keeps rows and columns visually aligned as a
    # board instead of allowing an irregular set of widgets to collapse.
    for row in range(height):
        for column in range(width):
            if (column, row) in positions:
                continue
            spacer = tk.Frame(
                content_frame,
                background=self.ui_palette()['canvas'],
                borderwidth=0,
            )
            spacer.grid(row=row, column=column, sticky='nsew', padx=3, pady=3)

    for code, node in grid['nodes'].items():
        tile = tk.Frame(
            content_frame,
            relief='flat',
            borderwidth=0,
            highlightthickness=3,
            highlightbackground=self.ui_palette()['canvas'],
            cursor='hand2',
        )
        tile.mission_code = code
        tile.columnconfigure(0, weight=1)
        tile.rowconfigure(0, weight=1)
        selection_frame = tk.Frame(
            tile,
            relief='flat',
            borderwidth=0,
            cursor='hand2',
        )
        selection_frame.columnconfigure(0, weight=1)
        selection_frame.rowconfigure(1, weight=1)
        is_goal = code == grid.get('goal')
        selection_frame.grid(
            row=0,
            column=0,
            sticky='nsew',
            padx=3 if is_goal else 0,
            pady=3 if is_goal else 0,
        )
        banner = tk.Label(
            selection_frame,
            font=('Segoe UI', 7, 'bold'),
            anchor='center',
            justify='center',
            wraplength=max(74, 520 // max(1, width)),
            padx=3,
            pady=3,
        )
        banner.grid(row=0, column=0, sticky='ew', padx=4, pady=(4, 0))
        body = tk.Label(
            selection_frame,
            font=('Segoe UI', 9, 'bold'),
            justify='center',
            anchor='center',
            wraplength=max(80, 560 // max(1, width)),
            padx=5,
            pady=6,
        )
        body.grid(row=1, column=0, sticky='nsew', padx=4, pady=(0, 4))
        mission_index = index_by_code.get(code, 0)
        for widget in (tile, selection_frame, banner, body):
            widget.bind(
                '<Button-1>',
                lambda event, index=mission_index: self.select_grid_mission(index),
            )
        tile.grid(
            row=node['y'],
            column=node['x'],
            sticky='nsew',
            padx=3,
            pady=3,
        )
        self.grid_tile_widgets[code] = {
            'tile': tile,
            'selection': selection_frame,
            'banner': banner,
            'body': body,
        }
    self.grid_canvas.xview_moveto(0)
    self.grid_canvas.yview_moveto(0)
    self.after_idle(self.resize_grid_canvas_window)
    self.refresh_grid_tiles()
