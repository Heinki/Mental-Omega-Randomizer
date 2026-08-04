"""Window lifecycle, layout, busy state, search, and logging."""

from ._dependencies import (
    DARK_UI_PALETTE,
    GRID_LOCKED,
    LAUNCHER_LOG,
    LIGHT_UI_PALETTE,
    apply_launcher_color_mode,
    build_launcher_widgets,
    log_event,
    logging,
    messagebox,
    queue,
    save_config,
    sys,
    tk,
    threading,
    time,
    traceback,
)

class WindowController:

    def report_callback_exception(self, exc_type, exc_value, exc_traceback):
        detail = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        log_event('ui_callback_failed', level=logging.ERROR, traceback=detail)
        if hasattr(self, 'log_text'):
            self.append_log(f'Unexpected launcher error: {exc_value}', error=True)
        messagebox.showerror(
            'Unexpected Error',
            f'The launcher encountered an error. Details were saved to:\n{LAUNCHER_LOG}',
        )

    def create_widgets(self):
        build_launcher_widgets(self)

    def update_header_summary(self, *_args):
        """Show the core selected run settings beneath the launcher title."""
        self.header_summary_var.set(' • '.join((
            self.campaign_var.get(),
            self.reward_mode_var.get(),
            self.progression_mode_var.get(),
            self.difficulty_var.get(),
            self.game_speed_var.get(),
        )))

    def toggle_settings_panel(self):
        self.unlock_hover_card_key = None
        self.set_unlock_grid_highlights(())
        self.settings_panel_visible = not self.settings_panel_visible
        if self.settings_panel_visible:
            self.right_frame.grid()
            self.workspace_tabs.grid_configure(columnspan=1, padx=(0, 12))
            self.compact_action_row.grid_remove()
            self.settings_toggle_button.configure(text='Hide Details')
        else:
            self.right_frame.grid_remove()
            self.workspace_tabs.grid_configure(columnspan=2, padx=0)
            self.compact_action_row.grid()
            self.settings_toggle_button.configure(text='Show Details')
        self.after_idle(self.resize_grid_canvas_window)

    def on_workspace_tab_changed(self, _event=None):
        """Refresh content whose layout depends on wide workspace dimensions."""
        if not hasattr(self, 'workspace_tabs'):
            return
        selected = self.workspace_tabs.select()
        if hasattr(self, 'settings_tab') and selected == str(self.settings_tab):
            self.after_idle(
                lambda: self.layout_settings_sections(
                    self.settings_canvas.winfo_width()
                )
            )
        elif hasattr(self, 'advanced_tab') and selected == str(self.advanced_tab):
            self.after_idle(self.refresh_advanced_pool_views)
        elif (
            hasattr(self, 'mission_view_frame')
            and selected == str(self.mission_view_frame)
        ):
            self.after_idle(self.resize_grid_canvas_window)

    def on_info_tab_changed(self, _event=None):
        if (
            not getattr(self, '_unlocks_view_dirty', False)
            or not hasattr(self, 'info_tabs')
            or not hasattr(self, 'unlocks_tab')
            or self.info_tabs.select() != str(self.unlocks_tab)
        ):
            return
        self.after_idle(self.refresh_unlocks_view)

    def ui_palette(self):
        return DARK_UI_PALETTE if self.dark_mode_var.get() else LIGHT_UI_PALETTE

    def ensure_checkbutton_indicator(self):
        """Use a real tick instead of Clam's X-shaped checkbox marker."""
        style = self.style

        def checkbox_image(fill, border, tick=None):
            photo = tk.PhotoImage(master=self, width=16, height=16)
            photo.put(border, to=(0, 0, 16, 16))
            photo.put(fill, to=(2, 2, 14, 14))
            if tick:
                # Thick, compact check mark that remains clear at 100% scaling.
                for x, y in (
                    (3, 8), (4, 9), (5, 10), (6, 11),
                    (7, 10), (8, 9), (9, 8), (10, 7),
                    (11, 6), (12, 5),
                ):
                    photo.put(tick, to=(x, y, min(16, x + 2), min(16, y + 2)))
            return photo

        if not hasattr(self, 'checkbox_indicator_images'):
            self.checkbox_indicator_images = {
                'light_off': checkbox_image('#eef0f2', '#68717a'),
                'light_on': checkbox_image('#68717a', '#4f565d', '#ffffff'),
                'light_disabled_off': checkbox_image('#e2e4e6', '#b2b6bb'),
                'light_disabled_on': checkbox_image('#b9bec4', '#a5aab0', '#f2f2f2'),
                'dark_off': checkbox_image('#353b43', '#8d97a3'),
                'dark_on': checkbox_image('#626b76', '#a5afb9', '#ffffff'),
                'dark_disabled_off': checkbox_image('#252a30', '#4d555f'),
                'dark_disabled_on': checkbox_image('#3b4149', '#505863', '#858c95'),
            }

        mode = 'dark' if self.dark_mode_var.get() else 'light'
        element = f'Randomizer.{mode}.Checkbutton.indicator'
        if element not in style.element_names():
            images = self.checkbox_indicator_images
            style.element_create(
                element,
                'image',
                images[f'{mode}_off'],
                ('disabled', 'selected', images[f'{mode}_disabled_on']),
                ('disabled', images[f'{mode}_disabled_off']),
                ('selected', images[f'{mode}_on']),
                sticky='',
            )
        style.layout(
            'TCheckbutton',
            [
                ('Checkbutton.padding', {
                    'sticky': 'nswe',
                    'children': [
                        (element, {'side': 'left', 'sticky': ''}),
                        ('Checkbutton.focus', {
                            'side': 'left',
                            'sticky': 'w',
                            'children': [
                                ('Checkbutton.label', {'sticky': 'nswe'}),
                            ],
                        }),
                    ],
                }),
            ],
        )

    def apply_color_mode(self):
        apply_launcher_color_mode(self)

    def save_ui_preferences(self):
        self.config['dark_mode'] = bool(self.dark_mode_var.get())
        self.config['hide_reward_details'] = bool(self.hide_reward_details_var.get())
        self.config['hide_locked_grid_missions'] = bool(
            self.hide_locked_grid_missions_var.get()
        )
        save_config(self.config)

    def on_dark_mode_changed(self):
        self.apply_color_mode()
        self.save_ui_preferences()
        if hasattr(self, 'grid_content_frame'):
            self.grid_render_signature = None
            self.redraw_grid()
        self.unlock_dashboard_signature = None
        self.refresh_progress_view()

    def on_hide_reward_details_changed(self):
        self.save_ui_preferences()
        self.refresh_progress_view()

    def on_hide_locked_grid_missions_changed(self):
        self.save_ui_preferences()
        if (
            self.hide_locked_grid_missions_var.get()
            and self.active_progression_mode() == 'Grid Mode'
            and self.state
        ):
            states = self.sync_grid_progression()
            selected_code = self.selected_mission_code()
            if states.get(selected_code) == GRID_LOCKED:
                visible_code = next(
                    (code for code, state in states.items() if state != GRID_LOCKED),
                    None,
                )
                if visible_code:
                    visible_index = next(
                        (
                            index
                            for index, mission in enumerate(self.missions)
                            if mission.get('code') == visible_code
                        ),
                        None,
                    )
                    if visible_index is not None:
                        self.selected_index.set(visible_index)
        self.refresh_grid_tiles()
        self.refresh_progress_view()

    def show_busy(self, title, detail='Please wait.'):
        first_busy = self.busy_depth == 0
        self.busy_depth += 1
        self.busy_title.configure(text=title)
        self.busy_detail_text = detail
        if first_busy:
            self.busy_started_at = time.monotonic()
            self.update_busy_elapsed()
        self.busy_overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self.busy_overlay.lift()
        self.busy_progress.configure(
            mode='indeterminate', maximum=100, value=0
        )
        self.busy_progress.start(12)
        self.configure(cursor='wait')
        try:
            self.busy_overlay.grab_set()
        except tk.TclError:
            pass
        # Paint immediately; elapsed text then proves Tk remains responsive.
        self.update_idletasks()

    def update_busy_elapsed(self):
        if not self.busy_depth:
            return
        elapsed = max(0, int(time.monotonic() - self.busy_started_at))
        self.busy_detail.configure(
            text=f'{self.busy_detail_text}\nElapsed: {elapsed}s',
        )
        self.busy_update_after_id = self.after(250, self.update_busy_elapsed)

    def hide_busy(self):
        self.busy_depth = max(0, self.busy_depth - 1)
        if self.busy_depth:
            return
        busy_after_id = self.__dict__.pop('busy_update_after_id', None)
        if busy_after_id is not None:
            try:
                self.after_cancel(busy_after_id)
            except tk.TclError:
                pass
        self.busy_progress.stop()
        try:
            if self.grab_current() == self.busy_overlay:
                self.busy_overlay.grab_release()
        except tk.TclError:
            pass
        self.busy_overlay.place_forget()
        self.configure(cursor='')

    def queue_busy_progress(self, detail, current=None, total=None):
        """Queue a real worker stage without reading Tk from that worker."""
        self.ui_queue.put(('progress', (detail, current, total)))

    def update_busy_progress(self, detail, current=None, total=None):
        if not self.busy_depth:
            return
        self.busy_detail_text = detail
        if total is not None and current is not None and total > 0:
            self.busy_progress.stop()
            self.busy_progress.configure(
                mode='determinate',
                maximum=total,
                value=max(0, min(current, total)),
            )
        else:
            self.busy_progress.configure(mode='indeterminate')
            self.busy_progress.start(12)
        elapsed = max(0, int(time.monotonic() - self.busy_started_at))
        self.busy_detail.configure(
            text=f'{self.busy_detail_text}\nElapsed: {elapsed}s',
        )

    def run_in_background(self, title, detail, callback, on_success, on_error):
        """Run filesystem/CPU work without blocking Tk's event loop."""
        self.show_busy(title, detail)

        def worker():
            previous_switch_interval = sys.getswitchinterval()
            # Reward planning is Python-heavy. A shorter handoff interval keeps
            # Tk's elapsed label and indeterminate bar repainting smoothly.
            sys.setswitchinterval(min(previous_switch_interval, 0.0005))
            try:
                result = callback()
            except Exception as exc:
                error_detail = traceback.format_exc()

                def deliver_error(exc=exc, error_detail=error_detail):
                    self.hide_busy()
                    try:
                        on_error(exc, error_detail)
                    except Exception:
                        self.append_log(traceback.format_exc(), error=True)

                self.ui_queue.put(('callback', deliver_error))
                return
            finally:
                sys.setswitchinterval(previous_switch_interval)

            def deliver_result(result=result):
                # The background phase is finished. Remove the animated
                # overlay before the main-thread UI refresh so it cannot look
                # like a frozen loading screen while cards/grid are painted.
                self.hide_busy()
                try:
                    on_success(result)
                except Exception as exc:
                    on_error(exc, traceback.format_exc())

            self.ui_queue.put(('callback', deliver_result))

        self.after(
            50,
            lambda: threading.Thread(
                target=worker,
                name='MentalOmegaRandomizerWorker',
                daemon=True,
            ).start(),
        )

    def process_ui_queue(self):
        try:
            try:
                while True:
                    kind, payload = self.ui_queue.get_nowait()
                    if kind == 'log':
                        message, error = payload
                        self.append_log_to_widgets(message, error=error)
                    elif kind == 'callback':
                        payload()
                    elif kind == 'progress':
                        self.update_busy_progress(*payload)
            except queue.Empty:
                pass
        finally:
            self.after(40, self.process_ui_queue)

    def on_settings_content_configure(self, _event=None):
        if hasattr(self, 'settings_canvas'):
            self.settings_canvas.configure(scrollregion=self.settings_canvas.bbox('all'))

    def layout_settings_sections(self, width):
        """Use two Settings columns when workspace width can support them."""
        required = (
            'settings_intro_label',
            'seed_settings_frame',
            'map_colors_frame',
            'mission_pool_frame',
            'reward_frame',
            'arsenal_frame',
            'buff_frame',
            'power_buff_frame',
            'weight_settings_frame',
            'assistance_frame',
            'appearance_frame',
        )
        if not all(hasattr(self, name) for name in required):
            return
        wide = int(width or 0) >= 720
        buff_columns = 1 if int(width or 0) < 600 else 2
        layout_signature = (wide, buff_columns)
        if self.__dict__.get('_settings_layout_signature') == layout_signature:
            return
        self._settings_layout_signature = layout_signature
        widgets = [getattr(self, name) for name in required]
        for widget in widgets:
            widget.grid_forget()

        self.settings_frame.columnconfigure(
            0, weight=1, uniform='settings-column' if wide else ''
        )
        self.settings_frame.columnconfigure(
            1, weight=1 if wide else 0, uniform='settings-column' if wide else ''
        )
        self.settings_intro_label.grid(
            row=0,
            column=0,
            columnspan=2 if wide else 1,
            sticky='ew',
            pady=(0, 8),
        )
        if wide:
            self.seed_settings_frame.grid(
                row=1, column=0, sticky='nsew', padx=(0, 4)
            )
            self.map_colors_frame.grid(
                row=1, column=1, sticky='nsew', padx=(4, 0)
            )
            self.mission_pool_frame.grid(
                row=2, column=0, sticky='nsew', padx=(0, 4), pady=(8, 0)
            )
            self.assistance_frame.grid(
                row=2, column=1, sticky='nsew', padx=(4, 0), pady=(8, 0)
            )
            self.reward_frame.grid(
                row=3, column=0, sticky='nsew', padx=(0, 4), pady=(8, 0)
            )
            self.appearance_frame.grid(
                row=3, column=1, sticky='nsew', padx=(4, 0), pady=(8, 0)
            )
            self.buff_frame.grid(
                row=4,
                column=0,
                columnspan=2,
                sticky='nsew',
                pady=(8, 0),
            )
            self.arsenal_frame.grid(
                row=5,
                column=0,
                columnspan=2,
                sticky='nsew',
                pady=(8, 0),
            )
            self.power_buff_frame.grid(
                row=6,
                column=0,
                columnspan=2,
                sticky='nsew',
                pady=(8, 0),
            )
            self.weight_settings_frame.grid(
                row=7,
                column=0,
                columnspan=2,
                sticky='nsew',
                pady=(8, 0),
            )
        else:
            for row, widget in enumerate(widgets[1:], start=1):
                widget.grid(row=row, column=0, sticky='ew', pady=(8, 0))
        if self.reward_mode_var.get() != 'Randomizer Arsenal':
            self.arsenal_frame.grid_remove()
        for frame, checks in (
            (self.buff_frame, self.buff_type_checks),
            (self.power_buff_frame, self.power_buff_type_checks),
        ):
            frame.columnconfigure(0, weight=1)
            frame.columnconfigure(1, weight=1 if buff_columns == 2 else 0)
            for index, check in enumerate(checks):
                check.grid_configure(
                    row=index // buff_columns,
                    column=index % buff_columns,
                )
        self.on_settings_content_configure()

    def on_settings_canvas_configure(self, event):
        if hasattr(self, 'settings_canvas_window'):
            self.settings_canvas.itemconfigure(self.settings_canvas_window, width=event.width)
        self.layout_settings_sections(event.width)
        if hasattr(self, 'settings_intro_label'):
            self.settings_intro_label.configure(wraplength=max(220, event.width - 32))
        if hasattr(self, 'rewards_per_check_message_label'):
            self.rewards_per_check_message_label.configure(
                wraplength=max(
                    180,
                    (event.width // 2 if event.width >= 720 else event.width) - 64,
                )
            )
        if hasattr(self, 'assistance_description_label'):
            self.assistance_description_label.configure(
                wraplength=max(
                    220,
                    (event.width // 2 if event.width >= 720 else event.width) - 64,
                )
            )

    def on_settings_mousewheel(self, event):
        if not hasattr(self, 'settings_canvas') or not hasattr(self, 'settings_tab'):
            return None
        if self.workspace_tabs.select() != str(self.settings_tab):
            return None
        pointer_x = self.winfo_pointerx()
        pointer_y = self.winfo_pointery()
        left = self.settings_canvas.winfo_rootx()
        top = self.settings_canvas.winfo_rooty()
        right = left + self.settings_canvas.winfo_width()
        bottom = top + self.settings_canvas.winfo_height()
        if not (left <= pointer_x <= right and top <= pointer_y <= bottom):
            return None
        steps = -1 if event.delta > 0 else 1
        self.settings_canvas.yview_scroll(steps, 'units')
        return 'break'

    def on_settings_control_mousewheel(self, event):
        """Scroll Settings without changing the focused readonly control."""
        if hasattr(self, 'settings_canvas'):
            self.settings_canvas.yview_scroll(-1 if event.delta > 0 else 1, 'units')
        return 'break'

    def on_grid_configure(self, _event=None):
        """Keep cached Grid content and canvas viewport dimensions aligned."""
        self.resize_grid_canvas_window()

    def resize_grid_canvas_window(self):
        if not hasattr(self, 'grid_canvas_window'):
            return
        self.grid_content_frame.update_idletasks()
        width = max(
            self.grid_canvas.winfo_width(),
            self.grid_content_frame.winfo_reqwidth(),
        )
        height = max(
            self.grid_canvas.winfo_height(),
            self.grid_content_frame.winfo_reqheight(),
        )
        self.grid_canvas.itemconfigure(
            self.grid_canvas_window,
            width=width,
            height=height,
        )
        self.grid_canvas.configure(scrollregion=(0, 0, width, height))

    def grid_canvas_contains_pointer(self):
        if (
            not hasattr(self, 'grid_canvas')
            or self.active_progression_mode() != 'Grid Mode'
            or not self.grid_frame.winfo_ismapped()
        ):
            return False
        pointer_x = self.winfo_pointerx()
        pointer_y = self.winfo_pointery()
        left = self.grid_canvas.winfo_rootx()
        top = self.grid_canvas.winfo_rooty()
        return (
            left <= pointer_x <= left + self.grid_canvas.winfo_width()
            and top <= pointer_y <= top + self.grid_canvas.winfo_height()
        )

    def on_grid_mousewheel(self, event):
        if not self.grid_canvas_contains_pointer():
            return None
        self.grid_canvas.yview_scroll(-1 if event.delta > 0 else 1, 'units')
        return 'break'

    def on_grid_shift_mousewheel(self, event):
        if not self.grid_canvas_contains_pointer():
            return None
        self.grid_canvas.xview_scroll(-1 if event.delta > 0 else 1, 'units')
        return 'break'

    @staticmethod
    def on_unlock_mousewheel(event, canvas):
        canvas.yview_scroll(-1 if event.delta > 0 else 1, 'units')
        return 'break'

    def on_unlock_canvas_configure(self, faction, canvas, window, width):
        canvas.itemconfigure(window, width=max(1, width))
        self.after_idle(
            lambda selected=faction: self.layout_unlock_dashboard_faction(selected)
        )

    def layout_unlock_dashboard_faction(self, faction):
        sections = getattr(self, 'unlock_dashboard_sections', {}).get(faction)
        canvas = getattr(self, 'unlock_icon_canvases', {}).get(faction)
        if not sections or canvas is None:
            return
        columns = max(2, min(4, max(1, canvas.winfo_width() - 8) // 84))
        column_cache = getattr(self, 'unlock_dashboard_columns', {})
        if column_cache.get(faction) == columns:
            return
        column_cache[faction] = columns
        self.unlock_dashboard_columns = column_cache
        row = 0
        for heading, cards in sections:
            heading.grid_configure(row=row, column=0, columnspan=columns)
            row += 1
            for index, card in enumerate(cards):
                card.grid_configure(
                    row=row + index // columns,
                    column=index % columns,
                )
            row += (len(cards) + columns - 1) // columns

    def set_unlock_grid_highlights(self, mission_codes):
        previous = set(getattr(self, 'unlock_hover_grid_codes', set()))
        current = set(mission_codes or ())
        if previous == current:
            return
        self.unlock_hover_grid_codes = current
        if self.active_progression_mode() == 'Grid Mode':
            self.refresh_grid_tiles(previous | current)
        else:
            self.refresh_mission_tree_unlock_highlights(previous | current)

    def refresh_mission_tree_unlock_highlights(self, mission_codes=None):
        current = set(getattr(self, 'unlock_hover_grid_codes', set()))
        codes = set(mission_codes or current)
        for item in self.missions_tree.get_children():
            try:
                code = self.missions[int(item)]['code']
            except (IndexError, TypeError, ValueError):
                continue
            if mission_codes is not None and code not in codes:
                continue
            tags = [tag for tag in self.missions_tree.item(item, 'tags')
                    if tag != 'unlock_available']
            if code in current:
                tags.append('unlock_available')
            self.missions_tree.item(item, tags=tuple(tags))

    def on_unlock_card_enter(self, card, entry=None):
        entry = entry or getattr(card, 'unlock_entry', {})
        self.unlock_hover_card_key = entry.get('key')
        mission_codes = (
            entry['sources'].get('available_codes', ())
            if entry.get('status') == 'available' and not entry.get('privacy')
            else ()
        )
        self.set_unlock_grid_highlights(mission_codes)

    def on_unlock_card_leave(self, card=None):
        # Tk can briefly report Leave while creating a tooltip Toplevel. Wait
        # one event turn and clear only when the pointer truly left the card.
        def clear_if_outside():
            entry = getattr(card, 'unlock_entry', {}) if card is not None else {}
            card_key = entry.get('key')
            if card_key != getattr(self, 'unlock_hover_card_key', None):
                return
            current_card = getattr(self, 'unlock_dashboard_cards', {}).get(
                card_key, {}
            ).get('card')
            # A cameo refresh may replace the widget beneath a stationary
            # pointer. The replacement still represents the hovered reward.
            if current_card is not None and current_card is not card:
                return
            if card is not None and card.winfo_exists():
                x, y = self.winfo_pointerx(), self.winfo_pointery()
                left, top = card.winfo_rootx(), card.winfo_rooty()
                if left <= x < left + card.winfo_width() and top <= y < top + card.winfo_height():
                    return
            self.unlock_hover_card_key = None
            self.set_unlock_grid_highlights(())

        self.after(20, clear_if_outside)

    def focus_unlock_search(self, _event=None):
        if hasattr(self, 'info_tabs') and hasattr(self, 'unlocks_tab'):
            self.info_tabs.select(self.unlocks_tab)
        if hasattr(self, 'unlocks_notebook'):
            tabs = self.unlocks_notebook.tabs()
            if tabs:
                self.unlocks_notebook.select(tabs[-1])
        if hasattr(self, 'unlock_search_entry'):
            self.unlock_search_entry.focus_set()
            self.unlock_search_entry.select_range(0, 'end')
        self.refresh_unlock_search()
        return 'break'

    def clear_unlock_search(self, _event=None):
        self.unlock_search_var.set('')
        if hasattr(self, 'unlock_search_entry'):
            self.unlock_search_entry.focus_set()
        return 'break'

    def refresh_unlock_search(self, *_args):
        if not hasattr(self, 'unlocks_text'):
            return

        term = self.unlock_search_var.get().strip()
        self.unlocks_text.tag_remove('search_match', '1.0', 'end')
        self.unlocks_text.tag_remove('search_current', '1.0', 'end')
        self.unlock_search_current = None
        if not term:
            if hasattr(self, 'unlock_search_status'):
                self.unlock_search_status.config(text='')
            return

        count = tk.IntVar(value=0)
        start = '1.0'
        first_match = None
        matches = 0
        while True:
            pos = self.unlocks_text.search(term, start, stopindex='end', nocase=True, count=count)
            if not pos or count.get() <= 0:
                break
            end = f'{pos}+{count.get()}c'
            if first_match is None:
                first_match = pos
            self.unlocks_text.tag_add('search_match', pos, end)
            matches += 1
            start = end

        if hasattr(self, 'unlock_search_status'):
            self.unlock_search_status.config(text=f'{matches} found' if matches else 'No match')
        if first_match:
            self.set_unlock_search_current(first_match, len(term))

    def set_unlock_search_current(self, pos, length):
        self.unlocks_text.tag_remove('search_current', '1.0', 'end')
        self.unlock_search_current = pos
        self.unlocks_text.tag_add('search_current', pos, f'{pos}+{length}c')
        self.unlocks_text.see(pos)

    def find_unlock_next(self, _event=None):
        return self.find_unlock_match(forward=True)

    def find_unlock_previous(self, _event=None):
        return self.find_unlock_match(forward=False)

    def find_unlock_match(self, forward=True):
        if not hasattr(self, 'unlocks_text'):
            return 'break'
        if hasattr(self, 'unlocks_notebook'):
            tabs = self.unlocks_notebook.tabs()
            if tabs:
                self.unlocks_notebook.select(tabs[-1])

        term = self.unlock_search_var.get().strip()
        if not term:
            self.focus_unlock_search()
            return 'break'

        count = tk.IntVar(value=0)
        if forward:
            start = f'{self.unlock_search_current}+1c' if self.unlock_search_current else '1.0'
            pos = self.unlocks_text.search(term, start, stopindex='end', nocase=True, count=count)
            if not pos:
                pos = self.unlocks_text.search(term, '1.0', stopindex='end', nocase=True, count=count)
        else:
            start = self.unlock_search_current if self.unlock_search_current else 'end'
            pos = self.unlocks_text.search(term, start, stopindex='1.0', backwards=True, nocase=True, count=count)
            if not pos:
                pos = self.unlocks_text.search(term, 'end', stopindex='1.0', backwards=True, nocase=True, count=count)

        if pos and count.get() > 0:
            self.set_unlock_search_current(pos, count.get())
        return 'break'

    def toggle_log(self):
        if self.log_visible_var.get():
            self.log_text.grid_remove()
            self.main_frame.rowconfigure(9, weight=0)
            self.log_toggle_button.configure(text='Show Launcher Log')
            self.log_visible_var.set(False)
        else:
            self.log_text.grid()
            self.main_frame.rowconfigure(9, weight=1)
            self.log_toggle_button.configure(text='Hide Launcher Log')
            self.log_visible_var.set(True)
            self.log_text.see('end')

    def append_log(self, message, error=False):
        log_event(
            'launcher_message',
            level=logging.ERROR if error else logging.INFO,
            message=str(message),
        )
        if threading.current_thread() is not threading.main_thread():
            self.ui_queue.put(('log', (str(message), bool(error))))
            return
        self.append_log_to_widgets(message, error=error)

    def append_log_to_widgets(self, message, error=False):
        self.log_text.configure(state='normal')
        self.log_text.insert('end', f'{message}\n')
        if error:
            self.log_text.tag_add('error', 'end-2l', 'end-1c')
            self.log_text.tag_config(
                'error',
                foreground='#ff7b72' if self.dark_mode_var.get() else '#b00020',
            )
        self.log_text.configure(state='disabled')
        if self.log_visible_var.get():
            self.log_text.see('end')
        self.status_label.config(text='Error' if error else message[:120])

    def clear_log(self):
        self.log_text.configure(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.configure(state='disabled')
