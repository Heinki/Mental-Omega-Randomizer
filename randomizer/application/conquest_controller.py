"""Conquest menu lifecycle, campaign actions, native launches, and recovery."""

import hashlib
import os
import subprocess
import sys
import threading
import time
import traceback
import uuid
from tkinter import messagebox

from randomizer.core.paths import GAME_ROOT, DEBUG_LOG
from randomizer.conquest import DISPLAY_NAME
from randomizer.conquest import campaign
from randomizer.conquest.feature import enabled as conquest_enabled
from randomizer.conquest.persistence import (
    Repository, PersistenceError, commit_attempt, mark_launched, finish_attempt,
)


from .conquest_coop_controller import ConquestCoopController


class ConquestController(ConquestCoopController):
    def initialize_conquest(self):
        if conquest_enabled():
            self.game_mode_choices = (*self.game_mode_choices, DISPLAY_NAME)
        self.conquest_repository = Repository()
        self.conquest_state = None
        self._conquest_maps = None
        self._conquest_preparing = False
        self._conquest_loading = False
        self._conquest_saving = False
        self._conquest_watch = None
        self._conquest_attempt_id = None
        self._conquest_error = ''
        self._conquest_last_ai = 0
        self._conquest_runtime_owned = False
        self._conquest_result_saved = False
        self.initialize_conquest_coop()

    def create_widgets(self):
        super().create_widgets()
        if not conquest_enabled():
            return
        from randomizer.conquest.ui import ConquestView
        self.conquest_view = ConquestView(self, self)
        self.conquest_view.grid(row=1, column=0, sticky='nsew')
        self.conquest_view.grid_remove()
        self.after(150, self._tick_conquest)

    def conquest_selected(self):
        variable = getattr(self, 'game_mode_var', None)
        return conquest_enabled() and variable is not None and variable.get() == DISPLAY_NAME

    def conquest_busy(self):
        return bool(getattr(self, '_conquest_preparing', False) or
                    getattr(self, '_conquest_loading', False) or
                    getattr(self, '_conquest_saving', False) or
                    getattr(self, '_conquest_watch', None))

    def available_game_modes(self):
        modes = super().available_game_modes()
        if not conquest_enabled():
            return tuple(mode for mode in modes if mode != DISPLAY_NAME)
        return modes if DISPLAY_NAME in modes else (*modes, DISPLAY_NAME)

    def game_mode_switch_locked(self):
        return self.conquest_busy() or bool(getattr(self, '_cq_lobby', None)) or super().game_mode_switch_locked()

    def _sync_game_mode_choice(self, *_args):
        if not self.conquest_selected():
            return super()._sync_game_mode_choice(*_args)

    def apply_game_mode_selection(self):
        if self.conquest_selected():
            if self.conquest_busy() or bool(getattr(self, '_final_fortress_preparing', False) or getattr(self, '_final_fortress_watch', None)) or self.gameplay_settings_locked() or self.busy_depth:
                return False
            try:
                self.final_fortress_repository.set_workspace_selected(False)
            except RuntimeError as exc:
                messagebox.showerror(DISPLAY_NAME, str(exc), parent=self)
                return False
            return True
        return super().apply_game_mode_selection()

    def open_game_mode_settings(self, mode):
        if mode != DISPLAY_NAME:
            super().open_game_mode_settings(mode)
            if not self.conquest_selected() and hasattr(self, 'conquest_view'):
                self.conquest_view.grid_remove()
            return
        if mode not in self.available_game_modes():
            return
        previous = self.game_mode_var.get()
        if previous != mode:
            if self.game_mode_switch_locked():
                return
            self.game_mode_var.set(mode)
            if not self.apply_game_mode_selection():
                self.game_mode_var.set(previous)
                return
        self._game_mode_page_open = True
        self.game_mode_page_label.configure(text='Conquest')
        self.game_mode_selection_frame.grid_remove()
        self.main_frame.grid_remove()
        self.game_mode_navigation.grid(row=0, column=0, sticky='ew')
        self.conquest_view.grid()
        self.game_mode_back_button.focus_set()
        if self._conquest_maps is None:
            self.reload_conquest()
        else:
            self.refresh_conquest()

    def show_game_mode_selection(self):
        view = getattr(self, 'conquest_view', None)
        if view is not None:
            view.grid_remove()
        return super().show_game_mode_selection()

    def apply_color_mode(self):
        super().apply_color_mode()
        if hasattr(self, 'conquest_view'):
            self.conquest_view.apply_theme()

    def refresh_conquest(self, message=None):
        if not hasattr(self, 'conquest_view'):
            return
        busy = self.conquest_busy() or bool(self.busy_depth) or bool(self._conquest_error) or self.conquest_orders_locked()
        self.conquest_view.refresh(self.conquest_state, busy=busy, message=message or self._conquest_error or None)
        # A failed transaction blocks further orders but remains recoverable.
        if self._conquest_error and not self.conquest_busy() and not self._cq_lobby:
            self.conquest_view.show_recovery()
        self.refresh_game_mode_navigation()

    def _conquest_change(self, operation):
        state = self.conquest_state
        if state is None:
            raise ValueError('Create or load a Conquest campaign first.')
        self.conquest_state, result = self.conquest_repository.update(state['id'], state['revision'], operation)
        self.publish_conquest()
        return result

    def _queue_conquest_change(self, operation, message=None, *, pause_on_error=False):
        """Keep validation, JSON serialization and durable saves off Tk."""
        state, repository = self.conquest_state, self.conquest_repository
        if state is None:
            return
        self._conquest_saving = True
        self.refresh_conquest('Saving campaign order…')

        def deliver(result=None, error=None, detail=None):
            self._conquest_saving = False
            if error is None:
                self.conquest_state, operation_message = result
                try:
                    self.publish_conquest()
                except (ValueError, RuntimeError, OSError) as exc:
                    error, detail = exc, traceback.format_exc()
            if error is None:
                self.refresh_conquest(operation_message if isinstance(operation_message, str) else message)
            else:
                if pause_on_error or not isinstance(error, ValueError):
                    self._conquest_error = str(error)
                self.append_log(detail, error=True)
                self.refresh_conquest(str(error))
                if not getattr(self, '_close_after_game', False):
                    messagebox.showerror(DISPLAY_NAME, str(error), parent=self)
            if getattr(self, '_close_after_game', False):
                self.close_launcher()

        def work():
            try:
                result = repository.update(state['id'], state['revision'], operation)
            except Exception as exc:
                detail = traceback.format_exc()
                self.ui_queue.put(('callback', lambda exc=exc, detail=detail: deliver(error=exc, detail=detail)))
            else:
                self.ui_queue.put(('callback', lambda: deliver(result=result)))

        threading.Thread(target=work, name='ConquestSave', daemon=True).start()

    def conquest_action(self, action, **values):
        if not conquest_enabled():
            return
        if self.conquest_cooperative():
            return self.coop_conquest_action(action, values)
        if self.conquest_busy() or self.busy_depth or self._conquest_error:
            return
        handlers = {
            'recruit': lambda s: campaign.recruit(s, **values),
            'move': lambda s: campaign.move(s, **values),
            'purchase': lambda s: campaign.purchase(s, **values),
            'use_item': lambda s: campaign.use_item(s, **values),
            'end': campaign.end_turn,
            'auto': campaign.autobattle,
        }
        try:
            self._queue_conquest_change(handlers[action], 'Campaign saved.')
        except (ValueError, PersistenceError, OSError) as exc:
            if isinstance(exc, (PersistenceError, OSError)):
                self._conquest_error = str(exc)
            self.refresh_conquest(str(exc))
            messagebox.showerror(DISPLAY_NAME, str(exc), parent=self)

    def reload_conquest(self):
        if not conquest_enabled() or self.conquest_busy() or self._cq_lobby:
            return
        from randomizer.conquest.engine import catalogue
        from randomizer.conquest.results import recover, native_game_running
        self._conquest_loading = True
        self.refresh_conquest('Reading installed maps and recovering any committed battle…')

        def work():
            state = self.conquest_repository.load()
            if state and not state.get('coop') and state['pending'] and state['pending']['attempt']:
                if native_game_running(GAME_ROOT):
                    raise ValueError('The game is still running. Close its battle before recovering Conquest.')
                attempt = state['pending']['attempt']
                outcome = recover(DEBUG_LOG, attempt['id'], state['pending'])
                state, _ = self.conquest_repository.update(state['id'], state['revision'],
                    lambda s: finish_attempt(s, attempt['id'], outcome))
            maps, fingerprint = catalogue(GAME_ROOT)
            from randomizer.conquest.profile import installed_rules
            names = {key: row.get('Name', key) for key, row in installed_rules().items()}
            from randomizer.conquest.appearance import army_sprites
            sprites = army_sprites()
            return state, maps, fingerprint, names, sprites

        def finish(result):
            self._conquest_loading = False
            self._conquest_error = ''
            self.conquest_state, self._conquest_maps, self._conquest_installation_hash, self._conquest_names, sprites = result
            self.conquest_view.load_army_sprites(sprites)
            self.conquest_view.map_count.set(f'{len(self._conquest_maps)} installed 2–8-player skirmish maps available.')
            self.refresh_conquest('Campaign loaded. Select an army, then a connected territory; right/middle drag to pan.')
            if getattr(self, '_close_after_game', False):
                self.close_launcher()

        def failed(exc, detail):
            self._conquest_loading = False
            self._conquest_error = str(exc)
            self.append_log(detail, error=True)
            self.refresh_conquest()
            if getattr(self, '_close_after_game', False):
                self.close_launcher()

        self.run_in_background('Opening Conquest…', 'Reading the campaign and native battle catalogue.', work, finish, failed)

    def new_conquest(self):
        if not conquest_enabled() or not self.conquest_can_create():
            return
        if self.conquest_busy() or self.busy_depth or self._conquest_error:
            return
        if not self._conquest_maps:
            return self.reload_conquest()
        try:
            old = self.conquest_state or self.conquest_repository.load()
            if old and not messagebox.askyesno(DISPLAY_NAME,
                f'Replace the current Conquest campaign? Its previous snapshot will remain in {self.conquest_repository.path.name}.bak.', parent=self):
                return
            settings = self.conquest_view.setup_values()
            settings['installation_hash'] = self._conquest_installation_hash
            settings = self.cooperative_new_settings(settings)
        except (ValueError, PersistenceError, OSError) as exc:
            self.refresh_conquest(str(exc))
            messagebox.showerror(DISPLAY_NAME, str(exc), parent=self)
            return
        self._conquest_loading = True
        self.refresh_conquest('Generating campaign…')
        maps, repository = self._conquest_maps, self.conquest_repository

        def work():
            if settings.get('coop_players'):
                from randomizer.conquest.transport_lobby import installation_details
                settings['coop_runtime_hash'] = installation_details(GAME_ROOT)[0]
            state = campaign.new_campaign(settings, maps)
            return repository.create(state, expected=(old['id'], old['revision']) if old else None)

        def finish(state):
            self._conquest_loading = False
            self.conquest_state = state
            self.conquest_view.settings['seed'].set(state['settings']['seed'])
            self.publish_conquest()
            self.refresh_conquest('Campaign started. HQ defenders receive 8 extra infantry and 2 defenses. Select an owned node to fortify it.')
            if getattr(self, '_close_after_game', False):
                self.close_launcher()

        def failed(exc, detail):
            self._conquest_loading = False
            if isinstance(exc, (PersistenceError, OSError)):
                self._conquest_error = str(exc)
            self.append_log(detail, error=True)
            self.refresh_conquest(str(exc))
            if getattr(self, '_close_after_game', False):
                self.close_launcher()
            else:
                messagebox.showerror(DISPLAY_NAME, str(exc), parent=self)

        self.run_in_background('Creating Conquest…', 'Building routes, assigning territories and saving your campaign.', work, finish, failed)

    def _tick_conquest(self):
        if not conquest_enabled():
            return
        visible = False
        try:
            view = self.conquest_view
            visible = self.conquest_selected() and view.winfo_ismapped()
            if not visible:
                return
            busy = self.conquest_busy() or bool(self.busy_depth) or bool(self._conquest_error) or self.conquest_orders_locked()
            if visible and view.busy != busy:
                self.refresh_conquest()
            # ttk combobox popdowns are Tcl widgets, not Python children.
            # grab_current() attempts to resolve them and raises KeyError.
            grab = self.tk.call('grab', 'current', self._w)
            if (visible and not busy and not view.animating and self.conquest_can_advance() and self.conquest_state and not grab):
                speed = view.pace.get()
                interval = {'Normal': .8, '2×': .4, '4×': .2, 'Instant': .05}[speed]
                now = time.monotonic()
                if now - self._conquest_last_ai >= interval:
                    state = self.conquest_state
                    auto_neutral = state['pending'] and state['pending']['attacker'] == 'ai' and state['pending']['defense']['faction'] == 'neutral'
                    if state['phase'] == 'ai' or auto_neutral:
                        def advance(current):
                            changed = False
                            for _ in range(8 if speed == 'Instant' else 1):
                                if not campaign.step_ai(current):
                                    break
                                changed = True
                            return changed
                        self._queue_conquest_change(advance, 'Enemy orders saved.', pause_on_error=True)
                        self._conquest_last_ai = now
        except Exception as exc:
            self._conquest_error = str(exc)
            self.refresh_conquest()
            self.append_log(traceback.format_exc(), error=True)
        finally:
            self.after(50 if visible else 500, self._tick_conquest)

    def launch_conquest(self):
        if not conquest_enabled():
            return
        if self.conquest_cooperative():
            return self.coop_conquest_action('launch', {})
        if self.conquest_busy() or self.busy_depth or self._conquest_error:
            return
        state = self.conquest_state
        if not state or not state['pending'] or state['pending']['attempt']:
            return
        from randomizer.conquest.engine import render, install
        from randomizer.conquest.results import native_game_running
        from randomizer.maps.assets import claim_runtime_asset_lease
        self._conquest_preparing = True
        self._conquest_attempt_id = uuid.uuid4().hex
        attempt_id = self._conquest_attempt_id
        speed = self.get_selected_game_speed_value()
        self.refresh_conquest('Preparing starting armies, buildings, and committed bonuses…')

        def prepare():
            command = self.build_command()
            if native_game_running(GAME_ROOT, any_installation=True):
                raise ValueError('Close the running game before launching Conquest.')
            claim_runtime_asset_lease()
            self._conquest_runtime_owned = True
            self.cleanup_generated_root_maps()
            self.disable_generated_rules_for_client()
            claim_runtime_asset_lease()
            prepared = render(GAME_ROOT, state, attempt_id, game_speed=speed)
            committed, _ = self.conquest_repository.update(state['id'], state['revision'],
                lambda s: commit_attempt(s, state['pending']['id'], attempt_id,
                    hashlib.sha256(prepared['map']).hexdigest(), hashlib.sha256(prepared['spawn']).hexdigest()))
            install(GAME_ROOT, prepared)
            return committed, command

        def finish(result):
            from randomizer.conquest.engine import verify_prepared
            from randomizer.conquest.results import ResultWatch
            self.conquest_state, command = result
            if getattr(self, '_close_after_game', False):
                self._conquest_change(lambda s: finish_attempt(s, attempt_id, None))
                self._conquest_preparing = False
                self._release_conquest_runtime()
                self.close_launcher()
                return
            verify_prepared(GAME_ROOT, self.conquest_state['pending']['attempt'])
            self._conquest_change(lambda s: mark_launched(s, attempt_id))
            watch = ResultWatch(DEBUG_LOG, attempt_id, self.conquest_state['pending'])
            options = {}
            if sys.platform == 'win32':
                from .launch_controller import windows_syringe_command_line
                options['executable'] = command[0]
                command = windows_syringe_command_line(command)
            else:
                environment = os.environ.copy()
                environment['WINEDLLOVERRIDES'] = ';'.join(filter(None, (environment.get('WINEDLLOVERRIDES', ''), 'ddraw=n,b')))
                options.update(env=environment, start_new_session=True)
            self.active_game_process = subprocess.Popen(command, cwd=GAME_ROOT, **options)
            self._conquest_watch = watch
            self._conquest_result_saved = False
            self._conquest_preparing = False
            self.refresh_conquest('Battle running. Close the native result screen to return to Conquest.')
            self.after(400, self._poll_conquest)

        self.run_in_background('Starting Conquest battle…', 'Preparing both factions and safe starting grants.',
                               prepare, finish, self._conquest_launch_failed)

    def _conquest_launch_failed(self, exc, detail):
        self._conquest_preparing = False
        try:
            self.conquest_state = self.conquest_repository.load()
            if self.conquest_state:
                self._conquest_change(lambda s: finish_attempt(s, self._conquest_attempt_id, None))
        except (ValueError, PersistenceError, OSError) as save_error:
            self._conquest_error = str(save_error)
        self._release_conquest_runtime()
        self.append_log(detail, error=True)
        self.refresh_conquest(str(exc))
        if getattr(self, '_close_after_game', False):
            self.close_launcher()
        else:
            messagebox.showerror(DISPLAY_NAME, str(exc), parent=self)

    def _poll_conquest(self):
        if self.conquest_state and self.conquest_state.get('coop') and self._conquest_watch:
            return self._poll_conquest_coop()
        from randomizer.conquest.results import recover, native_game_running
        watch, process = self._conquest_watch, self.active_game_process
        if watch is None or process is None:
            return
        try:
            running = process.poll() is None
            if not running:
                running = native_game_running(GAME_ROOT)
            outcome = watch.poll(final=not running)
            if not running and not outcome and not self._conquest_result_saved:
                outcome = recover(DEBUG_LOG, self._conquest_attempt_id, self.conquest_state['pending'])
            if not self._conquest_result_saved and (outcome or not running):
                self._conquest_change(lambda s: finish_attempt(s, self._conquest_attempt_id, outcome))
                self._conquest_result_saved = True
                self._conquest_error = ''
        except (ValueError, PersistenceError, OSError, subprocess.SubprocessError) as exc:
            self._conquest_error = str(exc)
            self.refresh_conquest()
            self.after(1000, self._poll_conquest)
            return
        if running:
            self.after(500, self._poll_conquest)
            return
        self.active_game_process = None
        self._conquest_watch = None
        self._release_conquest_runtime()
        self.refresh_conquest('Battle result saved.' if outcome else 'No verified result. Retry or autobattle; committed supplies are retained.')
        if watch.error:
            self.append_log(watch.error, error=True)
        if getattr(self, '_close_after_game', False):
            self.close_launcher()

    def _release_conquest_runtime(self):
        if self._conquest_runtime_owned:
            from randomizer.maps.assets import remove_generated_runtime_assets
            from randomizer.conquest.engine import cleanup
            cleanup(GAME_ROOT)
            self.disable_generated_rules_for_client()
            remove_generated_runtime_assets()
            self._conquest_runtime_owned = False

    def close_launcher(self):
        if getattr(self, '_cq_pending', None):
            self._close_after_game = True
            self.withdraw()
            self.disconnect_conquest_coop()
            if not self._cq_pending:
                self.close_launcher()
            return
        if (getattr(self, '_conquest_preparing', False) or getattr(self, '_conquest_loading', False) or
            getattr(self, '_conquest_saving', False)):
            self._close_after_game = True
            self.withdraw()
            return
        if getattr(self, '_conquest_watch', None) is not None:
            self._close_after_game = True
            self.withdraw()
            return
        if getattr(self, '_cq_lobby', None):
            self.disconnect_conquest_coop()
        return super().close_launcher()
