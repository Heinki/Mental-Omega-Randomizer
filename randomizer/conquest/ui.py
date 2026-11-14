"""Responsive Conquest workspace with a strategic canvas and ranked purchases."""

import math
import time
import tkinter as tk
from tkinter import ttk

from randomizer.ui.viewport import ScrollableViewport
from randomizer.ui.tooltips import WidgetTooltip
from randomizer.ui.conquest_widgets import PurchaseCard, EscortRoster, configure_purchase_style
from . import campaign
from .teams import participants, team_power, deployment
from .players import roster, human_ids, human, label as actor_label, country, bonus_owners
from .network import decision_actor
from .catalogue import (FACTIONS, DIFFICULTIES, SIZES, STATS, PERKS, MAX_STRENGTH,
                        RECRUIT_COST, RESEARCH_COST, SUPPLY_COST, LOCAL_PERKS,
                        REPAIR_KIT_COST, MAX_REPAIR_KITS, BATTLE_CREDITS_PER_RANK,
                        AIRCRAFT_BUILDING_LABELS, FACTORY_TRAINING_PERCENT, deployment_rank, perk_rank,
                        MAX_ARMIES_PER_NODE, MAX_RESEARCH_RANK, starting_structures)


class ConquestView(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=12)
        self.app = app
        self.state = None
        self.busy = False
        self.show_details = False
        self.selected = None
        self.selected_army_id = None
        self.purchase_cards = {}
        self.scale = 1
        self._campaign_id = None
        self._history_signature = None
        self._history_nodes = {}
        self._history_follow_pending = False
        self._fit_pending = False
        self._fit_after = None
        self._auto_fit = True
        self._army_images = {}
        self._animation = None
        self._animation_after = None
        self._result_shown = set()
        self._result_after = None
        self._result_dialog = None
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)
        self.heading = tk.StringVar(value='Conquest · Build an army. Claim a territory. Hold the front.')
        self.summary = tk.StringVar(value='Create a campaign to begin.')
        self.notice = tk.StringVar(value='Campaign credits, research and perks are saved independently.')
        self.heading_label = ttk.Label(self, textvariable=self.heading, font=('Segoe UI', 15, 'bold'), wraplength=900)
        self.heading_label.grid(row=0, column=0, sticky='ew')
        self.summary_label = ttk.Label(self, textvariable=self.summary, style='Muted.TLabel', wraplength=900)
        self.summary_label.grid(row=1, column=0, sticky='ew', pady=(4, 10))
        connection = ttk.Frame(self)
        connection.grid(row=2, column=0, sticky='ew', pady=(0, 8))
        connection.columnconfigure(1, weight=1)
        ttk.Button(connection, text='ZeroTier co-op…', command=app.open_conquest_coop).grid(row=0, column=0, sticky='w')
        self.coop_status_label = ttk.Label(connection, textvariable=app._cq_status, style='Muted.TLabel', wraplength=700)
        self.coop_status_label.grid(row=0, column=1, sticky='ew', padx=10)
        self.book = ttk.Notebook(self)
        self.book.grid(row=3, column=0, sticky='nsew')
        self.map_page = ttk.Frame(self.book, padding=6)
        self.book.add(self.map_page, text='Campaign')
        self._build_map()
        self.node_page = self._page('Node upgrades')
        self._build_node_upgrades()
        self.research_page = self._page('Research & supplies')
        self._build_research()
        self.perks_page = self._page('Perk shop')
        self._build_perks()
        self.bonuses_page = self._page('Bonuses')
        self._build_bonuses()
        self.setup_page = self._page('New campaign')
        self._build_setup()
        self.notice_label = ttk.Label(self, textvariable=self.notice, style='Muted.TLabel', wraplength=900)
        self.notice_label.grid(row=4, column=0, sticky='ew', pady=(8, 0))
        self.recovery = ttk.Frame(self)
        ttk.Label(self.recovery, text='Campaign could not be loaded or saved. Resolve the error, then retry.',
                  wraplength=600).pack(side='left', fill='x', expand=True)
        ttk.Button(self.recovery, text='Retry loading campaign', command=app.reload_conquest).pack(side='right')
        self.bind('<Configure>', self._resize, add='+')
        self.bind('<Map>', lambda event: self._schedule_result() if event.widget is self else None, add='+')
        self.bind('<Destroy>', self._destroy_result, add='+')
        self.apply_theme()
        self.refresh(None)

    def _page(self, title):
        viewport = ScrollableViewport(self.book, padding=14)
        viewport.content.columnconfigure(0, weight=1)
        self.book.add(viewport, text=title)
        return viewport

    def _build_map(self):
        page = self.map_page
        page.columnconfigure(0, weight=1)
        page.rowconfigure(1, weight=1)
        toolbar = self.toolbar = ttk.Frame(page)
        toolbar.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 6))
        self.buttons = {}
        self.battle_odds = tk.StringVar(value='Select an army, then a connected territory to move or attack.')
        self.odds_label = ttk.Label(toolbar, textvariable=self.battle_odds, width=1, wraplength=760,
                                   font=('Segoe UI', 10, 'bold'))
        self.odds_label.grid(row=0, column=0, columnspan=4, sticky='ew', pady=(0, 4))
        actions = (
            ('recruit', f'Recruit army · {RECRUIT_COST:,}', lambda: self.app.conquest_action('recruit', node=self.selected, new_army=True)),
            ('reinforce', f'Reinforce · {RECRUIT_COST:,}', self._reinforce_selected),
            ('end', 'End turn', lambda: self.app.conquest_action('end')),
            ('battle', 'Start battle', self.app.launch_conquest),
            ('auto', 'Autobattle', lambda: self.app.conquest_action('auto')),
            ('fortify', 'Fortify node…', self._open_node_upgrades),
            ('overview', 'Overview', self.fit_map),
            ('in', 'Zoom +', lambda: self.zoom(1.25)),
            ('out', 'Zoom −', lambda: self.zoom(.8)),
            ('details', 'Map / details', self._toggle_details),
            ('gift', 'Give territory…', self._gift),
        )
        for i, (key, label, command) in enumerate(actions):
            button = (self._purchase_button(toolbar, text=label, command=command)
                      if key in ('recruit', 'reinforce') else ttk.Button(toolbar, text=label, command=command))
            button.configure(width=1)
            button.grid(row=1 + i // 4, column=i % 4, sticky='ew', padx=2, pady=2)
            toolbar.columnconfigure(i % 4, weight=1)
            self.buttons[key] = button
        self.reinforce_tooltip = WidgetTooltip(self.buttons['reinforce'],
            'Add troops to the selected army, up to 40 strength. Costs 1,000 credits and uses its action.')
        self.army_controls = ttk.Frame(toolbar)
        self.army_controls.grid(row=4, column=0, columnspan=4, sticky='w', pady=(4, 6))
        ttk.Label(self.army_controls, text='Army:').pack(side='left', padx=(0, 6))
        self.army_selector = ttk.Combobox(self.army_controls, state='disabled', width=46)
        self.army_selector.pack(side='left')
        self.army_selector.bind('<<ComboboxSelected>>', self._choose_army)
        self.army_hint = ttk.Label(self.army_controls, text='Up to 4 allied armies per territory.', style='Muted.TLabel')
        self.army_hint.pack(side='left', padx=10)
        # Keep the body inside its allocated space, independent of the natural
        # width of notebook tabs, text, and history entries.
        self.map_body = ttk.Frame(page, width=1, height=1)
        self.map_body.grid(row=1, column=0, columnspan=2, sticky='nsew')
        self.map_body.grid_propagate(False)
        self.map_body.columnconfigure(0, weight=1)
        self.map_body.rowconfigure(0, weight=1)
        self.canvas_frame = ttk.Frame(self.map_body)
        self.canvas_frame.columnconfigure(0, weight=1)
        self.canvas_frame.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self.canvas_frame, width=1, height=1, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky='nsew')
        vertical = ttk.Scrollbar(self.canvas_frame, command=self.canvas.yview)
        horizontal = ttk.Scrollbar(self.canvas_frame, orient='horizontal', command=self.canvas.xview)
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        self.canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.canvas.bind('<Button-1>', self._click)
        self.canvas.bind('<Button-3>', self._start_pan)
        self.canvas.bind('<B3-Motion>', lambda e: self.canvas.scan_dragto(e.x, e.y, gain=1))
        self.canvas.bind('<Button-2>', self._start_pan)
        self.canvas.bind('<B2-Motion>', lambda e: self.canvas.scan_dragto(e.x, e.y, gain=1))
        self.canvas._content_scroll_handler = self._wheel
        for key, dx, dy in (('Left', -1, 0), ('Right', 1, 0), ('Up', 0, -1), ('Down', 0, 1)):
            self.canvas.bind('<' + key + '>', lambda e, x=dx, y=dy: self._pan(x, y))
        self.canvas.bind('<Escape>', lambda _e: self.select(None))
        self.canvas.bind('<Configure>', self._canvas_resize)
        self.side = ttk.Notebook(self.map_body)
        inspector = ttk.Frame(self.side, padding=8)
        inspector.columnconfigure(0, weight=1)
        inspector.rowconfigure(0, weight=1)
        self.side.add(inspector, text='Territory / battle')
        self.inspector = tk.Text(inspector, width=1, height=1, wrap='word', relief='flat',
                                 state='disabled', padx=8, pady=8, font=('Segoe UI', 10))
        self.inspector.grid(row=0, column=0, sticky='nsew')
        scrollbar = ttk.Scrollbar(inspector, command=self.inspector.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.inspector.configure(yscrollcommand=scrollbar.set)
        self.fortify_button = ttk.Button(inspector, text='Node defenses & buildings…', command=self._open_node_upgrades)
        self.fortify_button.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        history = ttk.Frame(self.side, padding=6)
        history.columnconfigure(0, weight=1)
        history.rowconfigure(2, weight=1)
        self.side.add(history, text='History')
        self.history_filter = tk.StringVar(value='All actions')
        selector = ttk.Combobox(history, textvariable=self.history_filter,
                               values=('All actions', 'Your actions', 'Team actions', 'AI actions'), state='readonly', width=18)
        selector.grid(row=0, column=0, sticky='ew', pady=(0, 4))
        selector.bind('<<ComboboxSelected>>', lambda _: self._refresh_history())
        self.history_heading = ttk.Label(history, width=1, wraplength=260,
            text='Latest 500 actions · double-click to locate', style='Muted.TLabel')
        self.history_heading.grid(row=1, column=0, sticky='ew', pady=(0, 6))
        self.history = tk.Text(history, width=1, height=1, wrap='word', relief='flat',
                               state='disabled', padx=8, pady=8, font=('Segoe UI', 10))
        self.history.grid(row=2, column=0, sticky='nsew')
        scroll = ttk.Scrollbar(history, command=self.history.yview)
        scroll.grid(row=2, column=1, sticky='ns')
        self.history.configure(yscrollcommand=scroll.set)
        self.history.bind('<Double-1>', self._history_select)
        self.history.bind('<Map>', lambda _event: self.after_idle(self._follow_history), add='+')
        controls = ttk.Frame(self.side, padding=12)
        controls.columnconfigure(0, weight=1)
        self.side.add(controls, text='Turn controls')
        ttk.Label(controls, text='Enemy turn pace', font=('Segoe UI', 11, 'bold')).grid(row=0, column=0, sticky='w')
        self.pace = tk.StringVar(value='Normal')
        ttk.Combobox(controls, textvariable=self.pace, values=('Normal', '2×', '4×', 'Instant'),
                     width=12, state='readonly').grid(row=1, column=0, sticky='ew', pady=8)
        self.pace_help = ttk.Label(controls, width=1,
            text='Enemy turns continue on every campaign tab. Normal, 2× and 4× show moving armies. Instant skips movement animation.',
            wraplength=270, justify='left')
        self.pace_help.grid(row=2, column=0, sticky='ew')
        self.side.bind('<Configure>', self._resize_sidebar, add='+')
        bottom = ttk.Frame(page)
        bottom.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(6, 0))
        self.legend = tk.StringVar(value='Blue: you · Red: enemy · Gold: selected · /: action spent')
        ttk.Label(bottom, textvariable=self.legend, width=1,
                  style='Muted.TLabel', wraplength=460).pack(side='left', fill='x', expand=True)
        page.bind('<Configure>', self._layout_map)

    def _layout_map(self, event=None):
        width = event.width if event else self.map_page.winfo_width()
        wide = width >= 850
        columns = 4 if width >= 650 else 3
        sidebar_width = min(420, max(300, int(width * .36)))
        signature = wide, columns, self.show_details, sidebar_width
        if signature == getattr(self, '_map_layout', None):
            return
        self._map_layout = signature
        self._wide = wide
        for column in range(4):
            self.toolbar.columnconfigure(column, weight=1 if column < columns else 0,
                                         uniform='campaign-actions' if column < columns else '')
        for i, button in enumerate(self.buttons.values()):
            button.grid_configure(row=1 + i // columns, column=i % columns)
        self.army_controls.grid_configure(row=1 + (len(self.buttons) + columns - 1) // columns, columnspan=columns)
        self.army_selector.configure(width=max(22, min(46, (width - 80) // 8)))
        if width < 700:
            self.army_hint.pack_forget()
        else:
            self.army_hint.pack(side='left', padx=10)
        self.odds_label.grid_configure(columnspan=columns)
        self.odds_label.configure(wraplength=max(240, width - 24))
        if wide:
            self.buttons['details'].grid_remove()
        self.canvas_frame.grid_forget()
        self.side.grid_forget()
        if wide:
            self.side.configure(width=sidebar_width)
            self.map_body.columnconfigure(1, weight=0, minsize=sidebar_width)
            self.canvas_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 8))
            self.side.grid(row=0, column=1, sticky='nsew')
        else:
            self.side.configure(width=1)
            self.map_body.columnconfigure(1, weight=0, minsize=0)
            if self.show_details:
                self.side.grid(row=0, column=0, columnspan=2, sticky='nsew')
            else:
                self.canvas_frame.grid(row=0, column=0, columnspan=2, sticky='nsew')

    def _resize_sidebar(self, event):
        width = max(80, event.width - 40)
        self.history_heading.configure(wraplength=width)
        self.pace_help.configure(wraplength=width)

    def _toggle_details(self):
        self.show_details = not self.show_details
        self._layout_map()

    def _selected_army(self):
        if not self.state or self.selected is None:
            return None
        chosen = campaign.army_at(self.state, self.selected, army_id=self.selected_army_id) if self.selected_army_id is not None else None
        return chosen or campaign.army_at(self.state, self.selected, self.app.conquest_local_actor()) or campaign.army_at(self.state, self.selected)

    def _sync_army_selector(self):
        armies = campaign.armies_at(self.state, self.selected) if self.state and self.selected is not None else []
        self._army_choices = [a['id'] for a in armies]
        chosen = self._selected_army()
        self.selected_army_id = chosen['id'] if chosen else None
        self.army_selector.configure(values=tuple(
            f'Army {a["id"]} · {actor_label(self.state, a["faction"])} · {a["strength"]} strength · {"Spent" if a["acted"] else "Ready"}'
            for a in armies), state='readonly' if armies else 'disabled')
        if chosen:
            self.army_selector.current(self._army_choices.index(chosen['id']))
        else:
            self.army_selector.set('No army here')

    def _choose_army(self, _event=None):
        index = self.army_selector.current()
        if 0 <= index < len(self._army_choices):
            self.selected_army_id = self._army_choices[index]
            self.refresh(self.state, busy=self.busy)

    def _reinforce_selected(self):
        army = self._selected_army()
        if army and not self.buttons['reinforce'].instate(('disabled',)):
            self.app.conquest_action('recruit', node=self.selected, army_id=army['id'])

    def _gift(self):
        if not self.state or not self.state.get('coop') or self.selected is None:
            return
        window = tk.Toplevel(self)
        window.title('Give territory')
        window.transient(self.winfo_toplevel())
        frame = ttk.Frame(window, padding=16)
        frame.pack(fill='both', expand=True)
        frame.columnconfigure(0, weight=1)
        choices = {p['name']: p['id'] for p in roster(self.state) if p['id'] != self.app.conquest_local_actor()}
        value = tk.StringVar(value=next(iter(choices)))
        ttk.Label(frame, text=self.state['nodes'][self.selected]['map']['name'], font=('Segoe UI', 12, 'bold')).grid(row=0, column=0, sticky='w')
        ttk.Label(frame, text='Give this empty territory to a teammate. One gift per turn; keep at least one territory. Bonuses transfer now, income starts next round. No same-round regifting or capture reward.', wraplength=400).grid(row=1, column=0, sticky='ew', pady=10)
        ttk.Combobox(frame, textvariable=value, values=tuple(choices), state='readonly').grid(row=2, column=0, sticky='ew')
        node = self.selected
        def send():
            self.app.conquest_action('gift', node=node, recipient=choices[value.get()])
            window.destroy()
        ttk.Button(frame, text='Give territory', command=send).grid(row=3, column=0, sticky='w', pady=10)

    def _build_research(self):
        parent = self.research_page.content
        ttk.Label(parent, text='Permanent research', font=('Segoe UI', 14, 'bold')).grid(row=0, column=0, sticky='w')
        self._label(parent, 'Each rank adds 10%, up to 50%. Prices rise after each upgrade.', 1)
        self.research_rows = {}
        for i, (key, name) in enumerate(STATS.items(), 2):
            card = PurchaseCard(parent, padding=(12, 10))
            card.grid(row=i, column=0, sticky='ew', pady=5)
            row = card.body
            row.columnconfigure(0, weight=1)
            value = tk.StringVar()
            label = ttk.Label(row, textvariable=value)
            label.grid(row=0, column=0, sticky='w')
            card.labels.append(label)
            button = self._purchase_button(row, card=card, text=f'Buy · {RESEARCH_COST}',
                command=lambda k=key: self.app.conquest_action('purchase', kind='research', key=k))
            button.grid(row=0, column=1, padx=(12, 0))
            self.research_rows[key] = value, button
        ttk.Separator(parent).grid(row=8, column=0, sticky='ew', pady=14)
        ttk.Label(parent, text='Battle supplies', font=('Segoe UI', 14, 'bold')).grid(row=9, column=0, sticky='w')
        self.supply_text = tk.StringVar()
        ttk.Label(parent, textvariable=self.supply_text, wraplength=650).grid(row=10, column=0, sticky='w', pady=8)
        self.supply_button = self._purchase_button(parent, text=f'Buy charge · {SUPPLY_COST}',
            command=lambda: self.app.conquest_action('purchase', kind='supply'))
        self.supply_button.grid(row=11, column=0, sticky='w')
        ttk.Separator(parent).grid(row=12, column=0, sticky='ew', pady=14)
        ttk.Label(parent, text='Field Repairs · consumable item', font=('Segoe UI', 14, 'bold')).grid(row=13, column=0, sticky='w')
        self._label(parent, 'Buy and arm a kit to heal damaged troops in your next battle.', 14)
        self.repairs_text = tk.StringVar()
        ttk.Label(parent, textvariable=self.repairs_text, wraplength=650).grid(row=15, column=0, sticky='ew', pady=8)
        actions = ttk.Frame(parent)
        actions.grid(row=16, column=0, sticky='ew')
        self.repairs_buy = self._purchase_button(actions, text=f'Buy repair kit · {REPAIR_KIT_COST}',
            command=lambda: self.app.conquest_action('purchase', kind='item', key='field_repairs'))
        self.repairs_buy.pack(side='left', padx=(0, 8))
        self.repairs_use = ttk.Button(actions, text='Arm for next battle',
            command=lambda: self.app.conquest_action('use_item', key='field_repairs'))
        self.repairs_use.pack(side='left')
        self.research_page.bind_controls()

    def _label(self, parent, text, row):
        label = ttk.Label(parent, text=text, wraplength=650, style='Muted.TLabel', justify='left')
        label.grid(row=row, column=0, sticky='ew', pady=(8, 12))
        parent.bind('<Configure>', lambda e, w=label: w.configure(wraplength=max(220, e.width - 24)), add='+')
        return label

    def _purchase_button(self, parent, *, card=None, **options):
        button = ttk.Button(parent, style='Conquest.Purchase.TButton', **options)
        self.purchase_cards[button] = card
        return button

    def _set_purchase_available(self, button, available, **options):
        button.configure(state='normal' if available else 'disabled', **options)
        card = self.purchase_cards.get(button)
        if card is not None:
            card.set_available(bool(available), self.app.ui_palette(), self.app.dark_mode_var.get())

    def _refresh_escort_rosters(self):
        actor = self.app.conquest_local_actor()
        faction = country(self.state, actor) if self.state else FACTIONS[0]
        inventory = self.state[actor]['perks'] if self.state else {}
        for key, roster in self.escort_rosters.items():
            rank = perk_rank(inventory, key)
            roster.show_roster(faction, rank, getattr(self.app, '_conquest_names', {}),
                bool(self.state) and str(self.perk_rows[key][1]['state']) != 'disabled',
                self.app.ui_palette(), self.app.dark_mode_var.get())

    def _build_perks(self):
        parent = self.perks_page.content
        ttk.Label(parent, text='Campaign perk shop', font=('Segoe UI', 14, 'bold')).grid(row=0, column=0, sticky='w')
        self._label(parent, 'Upgrade your armies here. Upgrade territories in Node upgrades. Prices rise after each purchase.', 1)
        self.perk_rows = {}
        self.perk_titles = {}
        self.perk_descriptions = {}
        self.escort_rosters = {}
        for i, (key, perk) in enumerate(((k, p) for k, p in PERKS.items() if not p['local'] and not p.get('legacy')), 2):
            border = PurchaseCard(parent)
            border.grid(row=i, column=0, sticky='ew', pady=5)
            card = border.body
            card.columnconfigure(0, weight=1)
            title = self.perk_titles[key] = ttk.Label(card, text=perk['name'], font=('Segoe UI', 11, 'bold'))
            title.grid(row=0, column=0, sticky='w')
            self.perk_descriptions[key] = self._label(card, perk['description'], 1)
            value = tk.StringVar()
            value_label = ttk.Label(card, textvariable=value)
            value_label.grid(row=2, column=0, sticky='w')
            border.labels.extend((title, self.perk_descriptions[key], value_label))
            if key in ('infantry', 'vehicles'):
                self.perk_descriptions[key].grid_remove()
                value_label.grid_configure(row=1, pady=(6, 0))
                roster = self.escort_rosters[key] = EscortRoster(card, key)
                roster.grid(row=2, column=0, sticky='ew', pady=(8, 4))
            button = self._purchase_button(card, card=border, text=f'Buy · {perk["cost"]}',
                command=lambda k=key: self.app.conquest_action('purchase', kind='perk', key=k, node=self.selected))
            button.grid(row=3, column=0, sticky='w', pady=(8, 0))
            self.perk_rows[key] = value, button
        self.perks_page.bind_controls()

    def _open_node_upgrades(self):
        if (self.state and self.selected is not None and not self.busy and
            self.state['phase'] == self.app.conquest_local_actor() and not self.state['pending'] and
            self.state['nodes'][self.selected]['owner'] == self.app.conquest_local_actor()):
            self.book.select(self.node_page)

    def _choose_upgrade_node(self, _event=None):
        index = self.node_selector.current()
        if 0 <= index < len(self._upgrade_nodes):
            self.select(self._upgrade_nodes[index])

    def _build_node_upgrades(self):
        parent = self.node_page.content
        ttk.Label(parent, text='Node defenses & buildings', font=('Segoe UI', 14, 'bold')).grid(row=0, column=0, sticky='w')
        self._label(parent, 'Choose a territory below, or select it on the campaign map and click Fortify node. Improvements defend only their own node, remain after capture, and do not consume an army action. Buy during your turn, before a battle is committed.', 1)
        self.node_selector = ttk.Combobox(parent, state='readonly', width=54)
        self.node_selector.grid(row=2, column=0, sticky='w', pady=(0, 10))
        self.node_selector.bind('<<ComboboxSelected>>', self._choose_upgrade_node)
        self.node_summary = tk.StringVar(value='Select a territory to see its stats and upgrades.')
        summary = ttk.Label(parent, textvariable=self.node_summary, justify='left', wraplength=650)
        summary.grid(row=3, column=0, sticky='ew', pady=(0, 10))
        parent.bind('<Configure>', lambda e: summary.configure(wraplength=max(220, e.width - 24)), add='+')
        self.node_rows = {}
        for i, key in enumerate(LOCAL_PERKS, 4):
            perk = PERKS[key]
            border = PurchaseCard(parent)
            border.grid(row=i, column=0, sticky='ew', pady=5)
            card = border.body
            card.columnconfigure(0, weight=1)
            title = ttk.Label(card, text=perk['name'], font=('Segoe UI', 11, 'bold'))
            title.grid(row=0, column=0, sticky='w')
            description = self._label(card, perk['description'], 1)
            value = tk.StringVar()
            value_label = ttk.Label(card, textvariable=value, wraplength=600)
            value_label.grid(row=2, column=0, sticky='ew')
            border.labels.extend((title, description, value_label))
            button = self._purchase_button(card, card=border, text=f'Build · {perk["cost"]} credits',
                command=lambda k=key: self.app.conquest_action('purchase', kind='perk', key=k, node=self._upgrade_node_id))
            button.grid(row=3, column=0, sticky='w', pady=(8, 0))
            self.node_rows[key] = value, button
        self.node_page.bind_controls()

    def _node_fortifications(self, state, node):
        structures = campaign.node_structures(state, node, getattr(self.app, '_conquest_building_power', None))
        names = getattr(self.app, '_conquest_names', {})
        return [f'Fortifications: {sum(structures.values())} starting buildings',
                'Buildings: ' + (', '.join(f'{count}× {names.get(kind, kind)}' for kind, count in structures.items()) or 'None'),
                f'Territory garrison rank: {node["perks"].get("garrison", 0)}/{PERKS["garrison"]["maximum"]}']

    def _refresh_node_upgrades(self, state, node, actor, active):
        owned = [n for n in state['nodes'] if n['owner'] == actor] if state else []
        self._upgrade_nodes = [n['id'] for n in owned]
        self.node_selector.configure(values=tuple(
            f'{n["map"]["name"]} · Territory {n["id"] + 1}' for n in owned),
            state='readonly' if owned else 'disabled')
        if not node or node['id'] not in self._upgrade_nodes:
            previous = getattr(self, '_upgrade_node_id', None)
            node = next((n for n in owned if n['id'] == previous), owned[0] if owned else None)
        self._upgrade_node_id = node['id'] if node else None
        if node:
            self.node_selector.current(self._upgrade_nodes.index(node['id']))
            armies = campaign.armies_at(state, node['id'])
            upgrades = ', '.join(f'{PERKS[k]["name"]}: {node["perks"].get(k, 0)}/{PERKS[k]["maximum"]}' for k in LOCAL_PERKS)
            self.node_summary.set(f'{node["map"]["name"]} · {actor_label(state, node["owner"])}\n'
                f'Income: {node["income"]} credits/turn · Armies: {len(armies)}/4 · Total strength: {sum(a["strength"] for a in armies)}\n'
                + 'Territory bonuses: ' + (', '.join(f'{STATS[k]} +{v}%' for k, v in node['buffs'].items()) or 'None')
                + '\n' + '\n'.join(self._node_fortifications(state, node))
                + f'\nLocal upgrade ranks: {sum(node["perks"].values())}\n' + upgrades
                + f'\nCivil Engineers: {state[actor]["perks"].get("civil_engineers", 0) * 10}% discount on your local purchases.')
        else:
            self.node_selector.set('')
            self.node_summary.set('You do not own any territories to upgrade.' if state else 'Create a campaign to upgrade your territories.')
        for key, (value, button) in self.node_rows.items():
            perk = PERKS[key]
            cost = campaign.purchase_cost(state, actor, key, node['id'] if node else None) if state else perk['cost']
            rank = node['perks'].get(key, 0) if node else 0
            if not node:
                reason = 'Select a territory.'
            elif node['owner'] != actor:
                reason = 'You can improve only your own territories.'
            elif rank >= perk['maximum']:
                reason = 'Fully upgraded.'
            elif not active:
                reason = 'Available during your turn, outside a committed battle or save.'
            elif state[actor]['credits'] < cost:
                reason = f'Need {cost - state[actor]["credits"]} more campaign credits.'
            else:
                reason = 'Ready to build.'
            allowed = bool(active and node and node['owner'] == actor and rank < perk['maximum'] and
                           state[actor]['credits'] >= cost)
            value.set(f'Rank {rank}/{perk["maximum"]} · {reason}')
            self._set_purchase_available(button, allowed,
                             text=('Fully upgraded' if rank >= perk['maximum'] else f'Build rank {rank + 1} · {cost} credits'))

    def _build_bonuses(self):
        parent = self.bonuses_page.content
        ttk.Label(parent, text='Faction overview', font=('Segoe UI', 14, 'bold')).grid(row=0, column=0, sticky='w')
        self.bonus_intro = ttk.Label(parent, text='No campaign yet.', wraplength=650, width=1)
        self.bonus_intro.grid(row=1, column=0, sticky='ew', pady=(8, 4))
        self.bonus_cards_frame = ttk.Frame(parent)
        self.bonus_cards_frame.grid(row=2, column=0, sticky='ew')
        self.bonus_cards_frame.columnconfigure(0, weight=1)
        self.bonus_cards = {}
        self.bonus_footer = ttk.Label(parent, width=1, wraplength=650, style='Muted.TLabel',
            text='Territory upgrades defend their own node. Stacked armies defend together.')
        self.bonus_footer.grid(row=3, column=0, sticky='ew', pady=12)
        parent.bind('<Configure>', self._resize_bonuses, add='+')
        self.bonuses_page.bind_controls()

    def _resize_bonuses(self, event=None):
        width = max(220, self.bonuses_page.canvas.winfo_width() - 58)
        if width == getattr(self, '_bonus_wrap_width', None):
            return
        self._bonus_wrap_width = width
        for label in (self.bonus_intro, self.bonus_footer):
            label.configure(wraplength=width)
        for card in self.bonus_cards.values():
            for key in ('header', 'wallet', 'stats', 'effects'):
                card[key].configure(wraplength=width)

    def _theme_bonus_cards(self):
        dark = self.app.dark_mode_var.get()
        colors = (('#79c0ff', '#7ee787', '#d2a8ff', '#56d4dd', '#ff7b72') if dark else
                  ('#0969da', '#1a7f37', '#8250df', '#0a6670', '#cf222e'))
        for actor, card in self.bonus_cards.items():
            color = colors[('player', 'player2', 'player3', 'player4', 'ai').index(actor)]
            card['frame'].configure(background=color)
            card['header'].configure(foreground=color)
            card['wallet'].configure(foreground='#f2cc60' if dark else '#7d4e00')
            card['stats'].configure(foreground='#7ee787' if dark else '#1a7f37')

    def _build_setup(self):
        parent = self.setup_page.content
        ttk.Label(parent, text='New Conquest campaign', font=('Segoe UI', 14, 'bold')).grid(row=0, column=0, sticky='w')
        self._label(parent, 'Capture every enemy territory. Each army acts once per turn. Up to four allied armies can share a territory and move out separately.', 1)
        self.settings = {}
        self.setup_controls = []
        fields = (
            ('size', 'Campaign size', list(SIZES), list(SIZES)[1]),
            ('player_country', 'Your faction', FACTIONS, FACTIONS[0]),
            ('ai_country', 'Enemy faction', FACTIONS, FACTIONS[1]),
            ('difficulty', 'Battle AI difficulty', tuple(DIFFICULTIES), 'Normal'),
            ('credits', 'Starting campaign credits', ('500', '1000', '2000', '5000', '10000'), '2000'),
            ('density', 'Territory bonuses', ('Few', 'Normal', 'Many'), 'Normal'),
            ('seed', 'Campaign seed (optional)', None, ''),
        )
        for i, (key, label, options, default) in enumerate(fields, 2):
            row = ttk.Frame(parent, padding=(0, 7))
            row.grid(row=i, column=0, sticky='ew')
            row.columnconfigure(1, weight=1)
            ttk.Label(row, text=label, width=23).grid(row=0, column=0, sticky='w')
            value = self.settings[key] = tk.StringVar(value=default)
            widget = ttk.Entry(row, textvariable=value, width=28) if options is None else ttk.Combobox(
                row, textvariable=value, values=options, state='readonly', width=28)
            widget.grid(row=0, column=1, sticky='ew')
            self.setup_controls.append((widget, options is not None))
        self._label(parent, 'Recruit a new army for 1,000 credits, or reinforce a selected army for the same price. All armies stationed on a territory defend it together.', 9)
        self._label(parent, 'Escort upgrades unlock stronger troops. Research reaches 50%. Upgrade prices rise for both you and the enemy.', 10)
        self.create_button = ttk.Button(parent, text='Start new campaign', style='Launch.TButton', command=self.app.new_conquest)
        self.create_button.grid(row=11, column=0, sticky='w', pady=12)
        self.map_count = tk.StringVar(value='Installed map catalogue loads when opening Conquest.')
        ttk.Label(parent, textvariable=self.map_count, style='Muted.TLabel').grid(row=12, column=0, sticky='w')
        self.setup_page.bind_controls()

    def setup_values(self):
        values = {key: variable.get().strip() for key, variable in self.settings.items()}
        values['size'] = SIZES[values['size']]
        values['credits'] = int(values['credits'])
        values['density'] = ('Few', 'Normal', 'Many').index(values['density'])
        return values

    def apply_theme(self):
        palette = self.app.ui_palette()
        dark = self.app.dark_mode_var.get()
        configure_purchase_style(self.app.style, palette, dark)
        for button, card in self.purchase_cards.items():
            if card is not None:
                card.set_available(str(button['state']) != 'disabled', palette, dark)
        self._refresh_escort_rosters()
        self.background = palette['canvas']
        self.foreground = palette.get('foreground', '#dce8ee')
        self.canvas.configure(background=self.background)
        self.inspector.configure(background=palette['background'], foreground=self.foreground,
                                 insertbackground=self.foreground)
        self.history.configure(background=palette['background'], foreground=self.foreground,
                               insertbackground=self.foreground, selectbackground=palette['select'],
                               selectforeground=palette['select_foreground'])
        for page in (self.node_page, self.research_page, self.perks_page, self.bonuses_page, self.setup_page):
            page.canvas.configure(background=palette['background'])
        self.history.tag_configure('player', foreground='#3596d0')
        self.history.tag_configure('player2', foreground='#58c987')
        self.history.tag_configure('player3', foreground='#bc88ed')
        self.history.tag_configure('player4', foreground='#65dad4')
        self.history.tag_configure('ai', foreground='#dd6659')
        self._theme_bonus_cards()
        self.render_map()

    def refresh(self, state, *, busy=False, message=None):
        previous = self.state
        self.state, self.busy = state, busy
        actor = self.app.conquest_local_actor()
        for page in (self.map_page, self.node_page, self.research_page, self.perks_page, self.bonuses_page):
            self.book.tab(page, state='normal' if state else 'disabled')
        self.recovery.grid_remove()
        if message is not None:
            self.notice.set(message)
        if state is None:
            self._cancel_animation()
            self._campaign_id = None
            self.selected = None
            self.heading.set('Conquest · New campaign')
            self.summary.set('Create a campaign to begin.')
            self.book.select(self.setup_page)
        else:
            if self._campaign_id != state['id']:
                self._campaign_id = state['id']
                self.selected = next((n['id'] for n in state['nodes'] if n['owner'] == actor), 0)
                self._fit_pending = True
                self._auto_fit = True
                self._history_signature = None
                self.book.select(self.map_page)
                self.after_idle(self.fit_map)
            phase = (actor_label(state, state['phase']) + (' · Your turn' if state['phase'] == actor else ' · Their turn')
                     if human(state, state['phase']) else {'ai': 'Enemy turn', 'battle': 'Battle pending · ' + actor_label(state, decision_actor(state)),
                     'finished': 'Victory' if state['winner'] == 'player' else 'Campaign defeated'}[state['phase']])
            self.heading.set(f'Conquest · Round {state["turn"]} · {phase}')
            self.summary.set(f'{actor_label(state, actor)} · {country(state, actor)} vs {state["settings"]["ai_country"]}  ·  '
                f'Credits: {state[actor]["credits"]} (+{campaign.income(state, actor)}/turn)  ·  '
                f'Supplies: {state[actor]["supplies"]}/3  ·  Seed: {state["settings"]["seed"]}')
            if self.selected is not None and not 0 <= self.selected < len(state['nodes']):
                self.selected = None
        active = bool(state and state['phase'] == actor and not busy)
        node = state['nodes'][self.selected] if state and self.selected is not None else None
        self._sync_army_selector()
        army = self._selected_army()
        stationed = campaign.armies_at(state, self.selected) if node else []
        pending = state and state['pending']
        human_battle = bool(pending and (human(state, pending['attacker']) or human(state, pending['defense']['faction'])))
        can_battle = human_battle and not pending['attempt'] and not busy and decision_actor(state) == actor
        statuses = dict(recruit=active and node and node['owner'] == actor and len(stationed) < MAX_ARMIES_PER_NODE and state[actor]['credits'] >= RECRUIT_COST,
                        reinforce=active and army and army['faction'] == actor and not army['acted'] and army['strength'] < MAX_STRENGTH and state[actor]['credits'] >= RECRUIT_COST,
                        end=active, battle=can_battle, auto=can_battle,
                        overview=bool(state), fortify=bool(active and node and node['owner'] == actor), details=True, gift=bool(active and state.get('coop') and node and node['owner'] == actor and not stationed
                        and state['coop']['gifts'][actor] != state['turn'] and node.get('gifted_round') != state['turn']
                        and sum(n['owner'] == actor for n in state['nodes']) > 1), **{'in': bool(state), 'out': bool(state)})
        for key, button in self.buttons.items():
            if button in self.purchase_cards:
                self._set_purchase_available(button, statuses[key])
            else:
                button.configure(state='normal' if statuses[key] else 'disabled')
        reinforce_amount = min(5 + state[actor]['perks'].get('recruitment', 0), MAX_STRENGTH - army['strength']) if state and army and army['faction'] == actor else 0
        if not army or army['faction'] != actor:
            reinforce_help = 'Select one of your armies to add troops to it.'
        elif not active:
            reinforce_help = 'Reinforce during your turn, before committing a battle.'
        elif army['acted']:
            reinforce_help = 'This army has used its action. Reinforce it next turn.'
        elif not reinforce_amount:
            reinforce_help = f'This army already has the maximum {MAX_STRENGTH} strength.'
        elif state[actor]['credits'] < RECRUIT_COST:
            reinforce_help = f'Reinforcing costs {RECRUIT_COST:,} campaign credits.'
        else:
            reinforce_help = (f'Add {reinforce_amount} strength to army #{army["id"]}: '
                              f'{army["strength"]} to {army["strength"] + reinforce_amount}/{MAX_STRENGTH}. '
                              f'Costs {RECRUIT_COST:,} credits and uses this army\'s action.')
        self.reinforce_tooltip.text = reinforce_help
        if human_battle:
            chance = campaign.player_chance(pending)
            self.battle_odds.set(f'Autobattle odds: {chance:.1%} win · {1-chance:.1%} loss · '
                                + ('Your team attacks.' if human(state, pending['attacker']) else 'Your team defends.'))
            self.buttons['auto'].configure(text=f'Autobattle · {chance:.1%} win')
        else:
            self.battle_odds.set('Enemy turn in progress…' if state and state['phase'] in ('ai', 'battle') else
                                'Select an army, then a connected territory to move or attack.')
            self.buttons['auto'].configure(text='Autobattle')
        self.fortify_button.configure(state='normal' if statuses['fortify'] else 'disabled')
        self._refresh_node_upgrades(state, node, actor, active)
        for key, (value, button) in self.research_rows.items():
            rank = state[actor]['research'][key] if state else 0
            cost = campaign.research_cost(state, actor, key) if state else RESEARCH_COST
            value.set(f'{STATS[key]}: +{rank * 10}% · Rank {rank}/{MAX_RESEARCH_RANK}')
            self._set_purchase_available(button, active and rank < MAX_RESEARCH_RANK and state[actor]['credits'] >= cost,
                text='Fully upgraded' if rank >= MAX_RESEARCH_RANK else f'Upgrade · {cost:,} credits')
        self.supply_text.set(f'Charges: {state[actor]["supplies"] if state else 0}/3. Each adds 20% damage to your next battle.')
        self._set_purchase_available(self.supply_button, active and state[actor]['supplies'] < 3 and state[actor]['credits'] >= SUPPLY_COST)
        kits = state[actor].get('repair_kits', 0) if state else 0
        armed = bool(state and state[actor].get('repairs_armed'))
        self.repairs_text.set(f'Inventory: {kits}/{MAX_REPAIR_KITS} kits · ' +
                              ('Armed for your next encounter.' if armed else 'Not armed. Buy and arm a kit to enable healing.'))
        if pending and any(m['loadout']['faction'] == actor and m['loadout'].get('field_repairs') for m in participants(pending)):
            self.repairs_text.set(self.repairs_text.get() + '\nField Repairs active in the pending battle. Its kit is already consumed; retries keep the effect.')
        self._set_purchase_available(self.repairs_buy, active and kits < MAX_REPAIR_KITS and state[actor]['credits'] >= REPAIR_KIT_COST)
        self.repairs_use.configure(text='Disarm · keep kit' if armed else 'Arm for next battle',
                                   state='normal' if active and kits else 'disabled')
        for key, (value, button) in self.perk_rows.items():
            perk = PERKS[key]
            inventory = node['perks'] if perk['local'] and node else state[actor]['perks'] if state and not perk['local'] else {}
            rank = perk_rank(inventory, key)
            cost = campaign.purchase_cost(state, actor, key) if state else perk['cost']
            location = f' · {node["map"]["name"]}' if perk['local'] and node else ' · Select an owned territory' if perk['local'] else ' · Personal armies'
            value.set(f'Rank {rank}/{perk["maximum"]}{location}')
            allowed = active and rank < perk['maximum'] and state[actor]['credits'] >= cost
            button_text = 'Fully upgraded' if rank >= perk['maximum'] else f'Buy rank {rank + 1} · {cost:,} credits'
            if key == 'veterans':
                level = ('Rookie', 'Veteran', 'Elite')[rank]
                value.set(f'Rank {rank}/2 · Starting combat troops: {level}')
                if rank < 2:
                    next_level = ('Veteran', 'Elite')[rank]
                    button_text = f'Buy rank {rank + 1} · {next_level} · {cost:,} credits'
            elif key == 'recruitment':
                value.set(f'Rank {rank}/3 · Recruiting adds {5 + rank} strength.')
            elif key in ('infantry', 'vehicles'):
                value.set(f'Owned rank: {rank}/6')
            elif key == 'helipad':
                building = AIRCRAFT_BUILDING_LABELS[country(state, actor)] if state else 'faction aircraft building'
                self.perk_titles[key].configure(text=f'Forward {building}')
                self.perk_descriptions[key].configure(text=f'Start with your {building}.')
            if perk['local']:
                allowed = allowed and node and node['owner'] == actor
            self._set_purchase_available(button, allowed, text=button_text)
        self._refresh_escort_rosters()
        self.create_button.configure(state='disabled' if busy or not self.app.conquest_can_create() else 'normal')
        for widget, dropdown in self.setup_controls:
            widget.configure(state='disabled' if busy else 'readonly' if dropdown else 'normal')
        if state and state.get('coop'):
            self.legend.set(' · '.join(f'{color}: {p["name"]}' for color, p in zip(('Blue', 'Green', 'Purple', 'Cyan'), roster(state))) + ' · Red: enemy')
        else:
            self.legend.set('Blue: you · Red: enemy · Gold: selected · Crossed out: action used')
        self._refresh_bonuses()
        self._refresh_inspector()
        self._refresh_history()
        self._detect_ai_movement(previous, state)
        self.render_map()
        self._schedule_result()

    def _schedule_result(self):
        if (self.state and self.state['winner'] and not self.busy and self.winfo_ismapped() and
            self.state['id'] not in self._result_shown and self._result_after is None and
            self._result_dialog is None):
            self._result_after = self.after_idle(self._show_result)

    def _show_result(self):
        self._result_after = None
        state = self.state
        if (not state or not state['winner'] or self.busy or not self.winfo_ismapped() or
            state['id'] in self._result_shown or getattr(self.app, '_close_after_game', False)):
            return
        if self.tk.call('grab', 'current', self._w):
            self._result_after = self.after(200, self._show_result)
            return
        self._result_shown.add(state['id'])
        self._cancel_animation()
        won = state['winner'] == 'player'
        title = 'Campaign victory' if won else 'Campaign defeated'
        dialog = self._result_dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.transient(self.app)
        dialog.resizable(False, False)
        body = ttk.Frame(dialog, padding=24)
        body.pack(fill='both', expand=True)
        color = ('#7ee787' if won else '#ff7b72') if self.app.dark_mode_var.get() else ('#1a7f37' if won else '#cf222e')
        ttk.Label(body, text=title, foreground=color, font=('Segoe UI', 17, 'bold')).pack(anchor='w')
        ttk.Label(body, text=('All enemy territories captured.' if won else 'All your territories have been lost.'),
                  wraplength=340, justify='left').pack(anchor='w', pady=(12, 6))
        ttk.Label(body, text=f'Campaign ended in round {state["turn"]}.',
                  style='Muted.TLabel').pack(anchor='w', pady=(0, 18))

        def finish(_event=None):
            self._result_dialog = None
            dialog.destroy()
            if self.state and self.state['id'] == state['id'] and self.state['winner']:
                self.book.select(self.setup_page)
                self.create_button.focus_set()

        button = ttk.Button(body, text='New campaign', command=finish)
        button.pack(anchor='e')
        dialog.protocol('WM_DELETE_WINDOW', finish)
        dialog.bind('<Return>', finish)
        dialog.bind('<Escape>', finish)
        dialog.update_idletasks()
        width, height = dialog.winfo_reqwidth(), dialog.winfo_reqheight()
        x = self.app.winfo_rootx() + max(0, (self.app.winfo_width() - width) // 2)
        y = self.app.winfo_rooty() + max(0, (self.app.winfo_height() - height) // 2)
        dialog.geometry(f'+{x}+{y}')
        dialog.grab_set()
        button.focus_set()

    def _destroy_result(self, event):
        if event.widget is self and self._result_after is not None:
            self.after_cancel(self._result_after)
            self._result_after = None

    def show_recovery(self):
        self.recovery.grid(row=5, column=0, sticky='ew', pady=(6, 0))

    def _refresh_bonuses(self):
        if not self.state:
            self.bonus_intro.configure(text='No campaign yet.')
            for card in self.bonus_cards.values():
                card['frame'].grid_remove()
            return
        intro = 'Permanent campaign upgrades and the bonuses used in your battles.'
        if self.state.get('coop'):
            intro = ('Territory stat bonuses: ' + ('shared by all commanders' if self.state['coop']['shared_nodes'] else 'personal')
                     + '. Income, research, purchased perks and supplies stay personal.')
        self.bonus_intro.configure(text=intro)
        factions = (*human_ids(self.state), 'ai')
        for faction, card in self.bonus_cards.items():
            if faction not in factions:
                card['frame'].grid_remove()
        for index, faction in enumerate(factions):
            state, wallet = self.state, self.state[faction]
            if faction not in self.bonus_cards:
                self._bonus_wrap_width = None
                frame = tk.Frame(self.bonus_cards_frame, padx=2, pady=2)
                body = ttk.Frame(frame, padding=12)
                body.pack(fill='both', expand=True)
                body.columnconfigure(0, weight=1)
                card = self.bonus_cards[faction] = {'frame': frame}
                for row, key in enumerate(('header', 'wallet', 'stats', 'effects')):
                    label = card[key] = ttk.Label(body, width=1, wraplength=650, justify='left',
                        font=('Segoe UI', 13, 'bold') if key == 'header' else ('Segoe UI', 10))
                    label.grid(row=row, column=0, sticky='ew', pady=(0, 8) if key != 'effects' else 0)
            card = self.bonus_cards[faction]
            card['frame'].grid(row=index, column=0, sticky='ew', pady=6)
            role = 'Enemy' if faction == 'ai' else 'Player' if faction == 'player' else f'Player {faction[-1]}'
            heading = ' · '.join(dict.fromkeys((role, actor_label(state, faction), country(state, faction))))
            money = f'{wallet["credits"]:,} campaign credits · +{campaign.income(state, faction):,} per turn'
            stats = []
            total = campaign.totals(state, faction)
            for key, label in STATS.items():
                stats.append(f'{label}: +{total[key]}%')
            owned = [f'{PERKS[k]["name"]} {perk_rank(wallet["perks"], k)}/{PERKS[k]["maximum"]}'
                     for k in PERKS if not PERKS[k].get('legacy') and perk_rank(wallet['perks'], k)]
            lines = ['Permanent perks: ' + (', '.join(owned) or 'None')]
            lines.append(f'Supplies: {wallet["supplies"]}/3 · recruitment: +{5 + wallet["perks"].get("recruitment", 0)} strength')
            lines.append(f'AI allies available: {wallet["perks"].get("allies", 0)}/3 · deployment depends on spare map starts')
            lines.append(f'Battle credits per commander: {10000 + BATTLE_CREDITS_PER_RANK * wallet["perks"].get("battle_treasury", 0):,}')
            lines.append(f'Extended Arsenal: +{wallet["perks"].get("extended_arsenal", 0)} cells · Civil Engineers: {10 * wallet["perks"].get("civil_engineers", 0)}% off local upgrades')
            lines.append(f'Hardened Infrastructure: +{10 * wallet["perks"].get("hardened_infrastructure", 0)}% building health')
            lines.append('Defenses start: ' + ('Veteran' if wallet['perks'].get('veteran_defenses') else 'Native rank'))
            lines.append(f'Unique-unit limits: +{wallet["perks"].get("unique_unit_capacity", 0)} · Special-building limits: +{wallet["perks"].get("special_building_limit", 0)} (supported types; normal tech required)')
            lines.append(f'Factory Training: {FACTORY_TRAINING_PERCENT[wallet["perks"].get("factory_training", 0)]}% progress toward Veteran for barracks/land-factory units')
            lines.append(f'Fortified Emplacements: +{15 * wallet["perks"].get("fortified_emplacements", 0)}% defense health · Generator Efficiency: +{25 * wallet["perks"].get("generator_efficiency", 0)}% output')
            if 'transport_capacity' in PERKS:
                lines.append(f'Transport Capacity: +{wallet["perks"].get("transport_capacity", 0)} slots · Open-topped Transports: ' + ('enabled' if wallet['perks'].get('open_topped_transports') else 'not purchased') + ' (reviewed types only)')
            lines.append('Starting combat rank: ' + ('Rookie', 'Veteran', 'Elite')[deployment_rank(wallet['perks'])])
            lines.append(f'Field Repairs kits: {wallet.get("repair_kits", 0)}/{MAX_REPAIR_KITS} · ' + ('armed' if wallet.get('repairs_armed') else 'not armed'))
            signature = (heading, money, '\n'.join(stats), '\n'.join(lines))
            if signature != card.get('signature'):
                for key, text in zip(('header', 'wallet', 'stats', 'effects'), signature):
                    card[key].configure(text=text)
                card['signature'] = signature
        self._theme_bonus_cards()
        self._resize_bonuses()

    def _refresh_inspector(self):
        state, lines = self.state, []
        if state and self.selected is not None:
            node = state['nodes'][self.selected]
            lines += [node['map']['name'], f'{len(node["map"]["starts"])} starting positions', actor_label(state, node['owner']), f'Income: +{node["income"]} credits/turn', '']
            if node.get('hq'):
                lines += [f'HQ · {actor_label(state, node["hq"])}',
                          'HQ guard: +8 rifle infantry and +2 powered faction defenses.' if node['owner'] == node['hq'] else
                          'HQ captured. Original defender bonus inactive.', '']
            lines += self._node_fortifications(state, node)
            lines += ['Includes node upgrades, owner perks, HQ defenses and required generators.',
                      f'Local upgrade ranks: {sum(node["perks"].values())}',
                      'Use Node upgrades to add defenses, power plants, barracks, refineries and vehicle factories.', '']
            lines += [f'{STATS[k]} +{v}%' for k, v in node['buffs'].items()]
            if node['reward']:
                claimed = 'Collected' if self.app.conquest_local_actor() in node['claimed'] else 'First-capture reward'
                lines.append(f'{claimed}: {PERKS[node["reward"]]["name"]}')
            for key, value in node['perks'].items():
                lines.append(f'Local: {PERKS[key]["name"]} rank {value}')
            armies = campaign.armies_at(state, node['id'])
            army = self._selected_army()
            if armies:
                lines += ['', f'Armies here: {len(armies)}/4', f'All {len(armies)} defend together.']
                lines += [f'#{a["id"]} · {actor_label(state, a["faction"])} · {a["strength"]} strength' for a in armies]
            if army:
                from .catalogue import ROSTERS
                unit = ROSTERS[country(state, army['faction'])][2]
                lines += ['', f'Selected army #{army["id"]}', f'Army marker: {getattr(self.app, "_conquest_names", {}).get(unit, unit)}',
                          f'Army strength: {army["strength"]}/{MAX_STRENGTH}',
                          'Action spent' if army['acted'] else 'Ready to move, attack, or recruit']
            elif node['owner'] != self.app.conquest_local_actor():
                lines += ['', 'Unoccupied defense strength: 2']
        else:
            lines += ['Select a territory to inspect it.', 'Select your ready army, then a connected node to move or attack.']
        if state and state['pending']:
            battle = state['pending']
            chance = campaign.player_chance(battle)
            lines += ['', 'PENDING BATTLE', state['nodes'][battle['target']]['map']['name'],
                      'Your team attacks.' if human(state, battle['attacker']) else 'Your team defends.',
                      'Encounter decision: ' + actor_label(state, decision_actor(state)),
                      f'Autobattle: {chance:.1%} win / {1-chance:.1%} loss',
                      f'Defending armies: {max(1, len(battle.get("defending_armies", ())))}']
            for key in ('attack', 'defense'):
                deployed, requested = deployment(battle, key)
                lines.append(f'{('Human team' if battle.get('human_team') == key else actor_label(state, battle[key]['faction']))} AI allies: {deployed}/{requested} deployed · {requested-deployed} in reserve')
            for member in participants(battle):
                loadout = member['loadout']
                force = loadout['force']
                structures = starting_structures(force, loadout['perks'], getattr(self.app, '_conquest_building_power', None))
                names = getattr(self.app, '_conquest_names', {})
                lines += ['', f'{actor_label(state, loadout['faction'])} · {loadout["country"]} · {member["role"]}:',
                          f'Battle credits: {10000 + BATTLE_CREDITS_PER_RANK * loadout["perks"].get("battle_treasury", 0):,}',
                          f'Weapon range: +{loadout["perks"].get("extended_arsenal", 0)} cells · Field Repairs: ' + ('active for this battle' if loadout.get('field_repairs') else 'inactive'),
                          f'Infrastructure health: +{(10 if battle.get("team_version", 1) >= 4 else 15) * loadout["perks"].get("hardened_infrastructure", 0)}%',
                          'Defense rank: ' + ('Veteran' if loadout['perks'].get('veteran_defenses') else 'Native rank'),
                          f'Capacity bonuses: units +{loadout["perks"].get("unique_unit_capacity", 0)}, special buildings +{loadout["perks"].get("special_building_limit", 0)}; no technology unlocks',
                          f'Factory Training: {FACTORY_TRAINING_PERCENT[loadout["perks"].get("factory_training", 0)]}% progress toward Veteran (new barracks/land-factory troops)',
                          f'Defense health: +{15 * loadout["perks"].get("fortified_emplacements", 0)}% · Generator output: +{25 * loadout["perks"].get("generator_efficiency", 0)}%',
                          'Starting troop rank: ' + ('Elite' if force['veterancy'] == 2 else 'Veteran' if force['veterancy'] == 1 else 'Rookie'),
                          ', '.join(f'{count}× {names.get(kind, kind)}' for kind, count in force['units'].items()),
                          'Buildings: ' + (', '.join(f'{count}× {names.get(kind, kind)}' for kind, count in structures.items()) or 'None')]
                if 'transport_capacity' in PERKS:
                    lines.append(f'Transport slots: +{loadout["perks"].get("transport_capacity", 0)} · Open-topped: ' + ('enabled' if loadout['perks'].get('open_topped_transports') else 'not purchased') + ' (reviewed types only)')
            lines += ['', 'Required power is included. Bonuses are already committed. These battle buttons stay tied to this encounter.']
        lines += ['', 'Wheel: zoom · Right/middle drag: pan']
        self.inspector.configure(state='normal')
        self.inspector.delete('1.0', 'end')
        self.inspector.insert('1.0', '\n'.join(lines))
        self.inspector.configure(state='disabled')

    def _refresh_history(self):
        choice = self.history_filter.get()
        signature = (self.state['id'], self.state['next_event'], choice) if self.state else None
        if signature == self._history_signature:
            return
        self._history_signature = signature
        follow = self.history.index('end-1c') == '1.0' or self.history.yview()[1] >= .98
        self.history.configure(state='normal')
        self.history.delete('1.0', 'end')
        if getattr(self, '_history_nodes', None):
            self.history.tag_delete(*self._history_nodes)
        self._history_nodes = {}
        entries = self.state['history'] if self.state else []
        if choice != 'All actions':
            actors = human_ids(self.state) if self.state and choice == 'Team actions' else (self.app.conquest_local_actor() if choice == 'Your actions' else 'ai',)
            entries = [e for e in entries if e['faction'] in actors]
        for entry in entries[-500:]:
            key = f'event:{entry["id"]}'
            self.history.insert('end', f'Round {entry["turn"]} · {actor_label(self.state, entry["faction"])}: {entry["text"]}\n',
                                (entry['faction'], key))
            self._history_nodes[key] = entry['node']
        self.history.configure(state='disabled')
        if entries and follow:
            self._history_follow_pending = True
            self.after_idle(self._follow_history)

    def _follow_history(self):
        if self._history_follow_pending and self.history.winfo_ismapped():
            self.history.see('end')
            self._history_follow_pending = False

    def _history_select(self, event):
        tags = self.history.tag_names(f'@{event.x},{event.y}')
        node = next((self._history_nodes[tag] for tag in tags
                     if tag in self._history_nodes and self._history_nodes[tag] is not None), None)
        if node is not None:
            self.select(node)
            x, y = self._point(self.state['nodes'][node])
            self.canvas.xview_moveto(max(0, x - self.canvas.winfo_width() / 2) / self.world_width)
            self.canvas.yview_moveto(max(0, y - self.canvas.winfo_height() / 2) / self.world_height)

    def _point(self, node):
        return ((node['x'] - self.min_x) * self.scale + 60, (node['y'] - self.min_y) * self.scale + 60)

    def load_army_sprites(self, sprites):
        self._army_images = {}
        for faction, frames in sprites.items():
            images = [tk.PhotoImage(master=self, data=data, format='png') for data in frames]
            self._army_images[faction] = (images, [image.subsample(2) for image in images])

    @property
    def animating(self):
        return self._animation is not None

    def _cancel_animation(self):
        if self._animation_after is not None:
            self.after_cancel(self._animation_after)
            self._animation_after = None
        self._animation = None
        self.canvas.delete('movement')

    def _detect_ai_movement(self, previous, state):
        if not state or not previous or previous['id'] != state['id']:
            self._cancel_animation()
            return
        if previous is state or self.pace.get() == 'Instant' or not self.canvas.winfo_ismapped():
            return
        before = {a['id']: a for a in previous['armies'] if a['faction'] == 'ai'}
        movement = None
        battle = state['pending']
        if battle and battle['attacker'] == 'ai' and (not previous['pending'] or previous['pending']['id'] != battle['id']):
            movement = (battle['source'], battle['target'], before.get(battle['army']))
        else:
            for army in state['armies']:
                old = before.get(army['id'])
                if old and old['node'] != army['node']:
                    pending = previous['pending']
                    if not pending or pending['army'] != army['id'] or pending['target'] != army['node']:
                        movement = (old['node'], army['node'], old)
                    break
        if movement and movement[2]:
            self._cancel_animation()
            source, target, army = movement
            self._animation = dict(source=source, target=target, army=army,
                                   started=time.monotonic(), duration={'Normal': .65, '2×': .325, '4×': .16}[self.pace.get()])
            self._animation_after = self.after(16, self._animate_ai)

    def _draw_army(self, x, y, army, faction, color, tags, direction=2):
        canvas = self.canvas
        frames = self._army_images.get(faction)
        if frames:
            canvas.create_image(x, y, image=frames[self.scale < .55][direction], tags=tags)
        else:
            # Keep the map usable if optional installed artwork is unavailable.
            canvas.create_polygon(x-13, y-6, x+7, y-6, x+13, y+3, x+8, y+9, x-13, y+9,
                                  fill=self.background, outline=color, width=2, tags=tags)
            canvas.create_line(x, y, x+19, y-8, fill=color, width=3, tags=tags)
        if army['acted'] and 'movement' not in tags:
            canvas.create_line(x-15, y+12, x+15, y-12, fill='#ffffff', width=2, tags=tags)

    def _draw_movement(self):
        self.canvas.delete('movement')
        movement = self._animation
        if not movement or not self.state:
            return
        start = self._point(self.state['nodes'][movement['source']])
        end = self._point(self.state['nodes'][movement['target']])
        progress = min(1, (time.monotonic() - movement['started']) / movement['duration'])
        progress = progress * progress * (3 - 2 * progress)
        x, y = (a + (b - a) * progress for a, b in zip(start, end))
        direction = round(math.atan2(end[0] - start[0], start[1] - end[1]) / (math.pi / 4)) % 8
        self._draw_army(x, y, movement['army'], country(self.state, 'ai'), '#e7c85a', ('movement',), direction)

    def _animate_ai(self):
        self._animation_after = None
        if not self._animation:
            return
        movement = self._animation
        if self.pace.get() == 'Instant' or time.monotonic() - movement['started'] >= movement['duration']:
            self._cancel_animation()
            self.render_map()
            return
        self._draw_movement()
        self._animation_after = self.after(16, self._animate_ai)

    def destroy(self):
        self._cancel_animation()
        if self._fit_after is not None:
            self.after_cancel(self._fit_after)
        super().destroy()

    def render_map(self):
        canvas = self.canvas
        canvas.delete('all')
        state = self.state
        if not state:
            canvas.create_text(180, 100, text='Create a campaign to explore Conquest.', fill=self.foreground, width=300)
            return
        nodes = state['nodes']
        self.min_x, self.min_y = min(n['x'] for n in nodes), min(n['y'] for n in nodes)
        self.world_width = max(canvas.winfo_width(), (max(n['x'] for n in nodes) - self.min_x) * self.scale + 120)
        self.world_height = max(canvas.winfo_height(), (max(n['y'] for n in nodes) - self.min_y) * self.scale + 120)
        canvas.configure(scrollregion=(0, 0, self.world_width, self.world_height))
        army = self._selected_army()
        ready = army and army['faction'] == self.app.conquest_local_actor() and not army['acted'] and state['phase'] == self.app.conquest_local_actor()
        destinations = set(campaign.neighbors(state, self.selected)) if ready else set()
        for a, b in state['edges']:
            highlighted = self.selected in (a, b) and (b if a == self.selected else a) in destinations
            canvas.create_line(*self._point(nodes[a]), *self._point(nodes[b]),
                               fill='#56b393' if highlighted else '#5b6c78', width=2 if highlighted else 1)
        armies = {}
        for stationed in state['armies']:
            armies.setdefault(stationed['node'], []).append(stationed)
        offsets = {1: ((0, 0),), 2: ((-16, 0), (16, 0)),
                   3: ((-16, -12), (16, -12), (0, 16)),
                   4: ((-16, -16), (16, -16), (-16, 16), (16, 16))}
        colors = {'player': '#3eabe2', 'player2': '#58c987', 'player3': '#bc88ed', 'player4': '#65dad4', 'ai': '#e66d63'}
        for node in nodes:
            x, y = self._point(node)
            color = {'player': '#3eabe2', 'player2': '#58c987', 'player3': '#bc88ed', 'player4': '#65dad4', 'ai': '#e66d63', 'neutral': '#8b9da8'}[node['owner']]
            tag = 'node:' + str(node['id'])
            selected = node['id'] == self.selected
            radius = (23 if self.scale >= .55 else 15) if node['id'] in armies else max(3, min(8, round(10 * self.scale)))
            stack = armies.get(node['id'], [])
            if len(stack) > 1:
                radius = 39 if self.scale >= .55 else 29
            canvas.create_oval(x-radius, y-radius, x+radius, y+radius, fill=self.background if node['id'] in armies else color,
                               outline='#e7c85a' if selected else color, width=4 if selected else 1, tags=(tag,))
            for current, (dx, dy) in zip(stack, offsets.get(len(stack), ())):
                if self._animation and self._animation['army']['id'] == current['id']:
                    continue
                tags = tag, f'army:{current["id"]}'
                if selected and current['id'] == self.selected_army_id:
                    canvas.create_oval(x+dx-18, y+dy-18, x+dx+18, y+dy+18,
                                       outline='#e7c85a', width=2, tags=tags)
                self._draw_army(x+dx, y+dy, current, country(state, current['faction']), colors[current['faction']], tags)
            if node.get('hq'):
                size = radius + 5
                canvas.create_rectangle(x-size, y-size, x+size, y+size, outline='#e7c85a', width=2, tags=(tag,))
                canvas.create_text(x, y-size-8, text='HQ', fill='#e7c85a', font=('Segoe UI', 9, 'bold'), tags=(tag,))
            if state['pending'] and node['id'] == state['pending']['target']:
                canvas.create_oval(x-30, y-30, x+30, y+30, outline='#edb04e', width=2, dash=(3, 3), tags=(tag,))
            if self.scale >= .65 or selected:
                name = node['map']['name']
                canvas.create_text(x, y+radius+13, text=name[:25] + ('…' if len(name) > 25 else ''),
                                   fill=self.foreground, font=('Segoe UI', 8), tags=(tag,))
        self._draw_movement()

    def select(self, node, army_id=None):
        if node != self.selected or army_id is not None:
            self.selected_army_id = army_id
        self.selected = node
        self.refresh(self.state, busy=getattr(self, 'busy', False))

    def _click(self, event):
        self.canvas.focus_set()
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        found = self.canvas.find_overlapping(x-4, y-4, x+4, y+4)
        target = next((int(tag.split(':')[1]) for item in reversed(found)
                       for tag in self.canvas.gettags(item) if tag.startswith('node:')), None)
        army_id = next((int(tag.split(':')[1]) for item in reversed(found)
                        for tag in self.canvas.gettags(item) if tag.startswith('army:')), None)
        if army_id is not None and self.state:
            clicked = next((a for a in self.state['armies'] if a['id'] == army_id), None)
            if clicked:
                target = clicked['node']
        if target is not None and self.state and self.selected is not None and target != self.selected:
            army = self._selected_army()
            if (not self.busy and self.state['phase'] == self.app.conquest_local_actor() and army and
                army['faction'] == self.app.conquest_local_actor() and not army['acted'] and
                target in campaign.neighbors(self.state, self.selected)):
                source = self.selected
                self.selected = target
                self.app.conquest_action('move', source=source, target=target, army_id=army['id'])
                return
        self.select(target, army_id)

    def fit_map(self):
        if not self.state:
            return
        self._auto_fit = True
        nodes = self.state['nodes']
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if width < 50 or height < 50:
            self._fit_pending = True
            return
        self._fit_pending = False
        self.scale = max(.12, min(1.5, (width-120) / max(1, max(n['x'] for n in nodes) - min(n['x'] for n in nodes)),
                                      (height-120) / max(1, max(n['y'] for n in nodes) - min(n['y'] for n in nodes))))
        self.render_map()
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)

    def zoom(self, factor, x=None, y=None):
        if not self.state:
            return
        self._auto_fit = False
        x = self.canvas.winfo_width() / 2 if x is None else x
        y = self.canvas.winfo_height() / 2 if y is None else y
        wx = (self.canvas.canvasx(x) - 60) / self.scale
        wy = (self.canvas.canvasy(y) - 60) / self.scale
        self.scale = max(.12, min(3, self.scale * factor))
        self.render_map()
        self.canvas.xview_moveto(max(0, wx * self.scale + 60 - x) / self.world_width)
        self.canvas.yview_moveto(max(0, wy * self.scale + 60 - y) / self.world_height)

    def _wheel(self, event):
        self.zoom(1.15 if getattr(event, 'delta', 0) > 0 or getattr(event, 'num', 0) == 4 else 1/1.15,
                  event.x, event.y)
        return 'break'

    def _pan(self, dx, dy):
        self._auto_fit = False
        self.canvas.xview_scroll(dx, 'units')
        self.canvas.yview_scroll(dy, 'units')
        return 'break'

    def _start_pan(self, event):
        self._auto_fit = False
        self.canvas.scan_mark(event.x, event.y)

    def _canvas_resize(self, _event=None):
        if self._fit_after is not None:
            self.after_cancel(self._fit_after)
        def fit():
            self._fit_after = None
            if self._auto_fit or self._fit_pending:
                self.fit_map()
        self._fit_after = self.after(80, fit)

    def _resize(self, event):
        if event.widget is self:
            for label in (self.heading_label, self.summary_label, self.notice_label, self.coop_status_label):
                label.configure(wraplength=max(200, event.width - 32))
            titles = ('Map', 'Nodes', 'Research', 'Perks', 'Bonuses', 'New') if event.width < 650 else (
                'Campaign', 'Node upgrades', 'Research & supplies', 'Perk shop', 'Bonuses', 'New campaign')
            for page, title in zip(self.book.tabs(), titles):
                self.book.tab(page, text=title)
