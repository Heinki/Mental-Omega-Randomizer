"""Grid victory dialog and mission times."""

import tkinter as tk
from tkinter import ttk

from randomizer.progression.grid import required_goals
from randomizer.ui.viewport import fit_dialog


def _grid_run_key(state):
    grid = state.get('grid')
    if (state.get('progression_mode') != 'Grid Mode'
            or not isinstance(grid, dict) or not grid.get('nodes')):
        return None
    return state.get('seed'), state.get('created_at'), tuple(required_goals(grid))


def show_synced_grid_victory(app, previous_state):
    """Announce victory when a live co-op update completes the current Grid run."""
    run = _grid_run_key(app.state)
    if run is None or run != _grid_run_key(previous_state):
        return
    goals = set(run[2])
    if (not goals.issubset(previous_state.get('completed_missions', ()))
            and goals.issubset(app.state.get('completed_missions', ()))):
        schedule_grid_victory(app)


def schedule_grid_victory(app):
    run = _grid_run_key(app.state)
    if run is None:
        return

    goals = set(run[2])

    def show_when_ready():
        if (getattr(app, '_close_after_game', False)
                or run != _grid_run_key(app.state)
                or not goals.issubset(app.state.get('completed_missions', ()))):
            return
        if app.active_game_process is not None or app.grab_current() or not app.winfo_viewable():
            app.after(200, show_when_ready)
            return
        _show_grid_victory(app, len(run[2]))

    app.after_idle(show_when_ready)


def _format_time(seconds):
    if type(seconds) is not int or seconds < 0:
        return 'Unavailable'
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f'{hours}:{minutes:02d}:{seconds:02d}'


def _show_grid_victory(app, goal_count):
    state = app.state
    completed = state.get('completed_missions', ())
    times = state.get('grid_mission_times', {})
    if not isinstance(times, dict):
        times = {}
    missions = app.mission_lookup()

    title = 'Grid victory'
    dialog = tk.Toplevel(app)
    dialog.title(title)
    dialog.transient(app)
    body = ttk.Frame(dialog, padding=24)
    body.pack(fill='both', expand=True)

    color = '#7ee787' if app.dark_mode_var.get() else '#1a7f37'
    ttk.Label(body, text=title, foreground=color, font=('Segoe UI', 17, 'bold')).pack(anchor='w')
    ttk.Label(body, text=f'All required missions complete ({goal_count}/{goal_count}).').pack(
        anchor='w', pady=(12, 12),
    )

    results = ttk.Frame(body)
    results.pack(fill='both', expand=True)
    rows = ttk.Treeview(
        results, columns=('mission', 'time'), show='headings', selectmode='none',
        height=min(10, len(completed)),
    )
    rows.heading('mission', text='Completed mission', anchor='w')
    rows.heading('time', text='Launch to victory', anchor='e')
    rows.column('mission', width=320, minwidth=130)
    rows.column('time', width=135, minwidth=135, anchor='e', stretch=False)
    scroll = ttk.Scrollbar(results, orient='vertical', command=rows.yview)
    rows.configure(yscrollcommand=scroll.set)
    scroll.pack(side='right', fill='y')
    rows.pack(side='left', fill='both', expand=True)
    for code in completed:
        name = missions.get(code, {}).get('title') or code
        rows.insert('', 'end', values=(name, _format_time(times.get(code))))

    def finish(_event=None):
        dialog.destroy()

    button = ttk.Button(body, text='Continue playing', command=finish)
    button.pack(anchor='e', pady=(16, 0))
    dialog.protocol('WM_DELETE_WINDOW', finish)
    dialog.bind('<Return>', finish)
    dialog.bind('<Escape>', finish)
    fit_dialog(dialog, body, width=560, height=460)
    dialog.update_idletasks()
    x = max(0, app.winfo_rootx() + (app.winfo_width() - dialog.winfo_width()) // 2)
    y = max(0, app.winfo_rooty() + (app.winfo_height() - dialog.winfo_height()) // 2)
    dialog.geometry(f'+{x}+{y}')
    dialog.grab_set()
    button.focus_set()
