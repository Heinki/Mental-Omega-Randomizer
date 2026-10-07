"""Co-op settings, shared Grid lobby, suggestions, and direct game launch."""

import copy
import json
import os
import queue
import secrets
import threading
import traceback
from tkinter import messagebox

from .coop_connection_controller import CoopConnectionController
from randomizer.config.player import save_config
from randomizer.coop import feature
from randomizer.coop.direct import host_session, join_session
from randomizer.coop.lobby import LOBBY_PORT, Lobby, decode_state, encode_state
from randomizer.coop.prototype import available_units, build_manifest, shop_unit_loadout
from randomizer.coop.shop_stage import (
    apply_stage_snapshot, recovery_result_message, stage_digest, stage_snapshot,
)
from randomizer.coop.victory import victory_marker_name
from randomizer.core.diagnostics import event as log_event
from randomizer.core.paths import DEBUG_LOG, GAME_ROOT
from randomizer.rewards.arsenal import ARSENAL_MODE
from randomizer.shop.model import RunStatus


def normalize_network_mode(value):
    """Migrate all previously offered connection modes to ZeroTier."""
    return 'zerotier'


class CoopShopSetupRequired(ValueError):
    """A paired guest must prepare its own Shop run before stage sync."""

    def __init__(self, snapshot):
        seed = snapshot.get('seed') if isinstance(snapshot, dict) else None
        stage = snapshot.get('stage') if isinstance(snapshot, dict) else None
        if (not isinstance(seed, str) or not seed or len(seed) > 128
                or type(stage) is not int or stage < 1):
            raise ValueError('Invalid host Shop stage snapshot.')
        self.seed = seed
        super().__init__(
            f'Host is playing Shop Mode. Host seed: {seed}; stage: {stage}.\n\n'
            'Select Shop Mode, enable co-op, and start your own Shop run with '
            'the same seed before joining. Both runs must have the same stage '
            'and completed missions. Your profile and purchases stay separate.'
        )


class CoopController(CoopConnectionController):
    def refresh_coop_controls(self):
        if not hasattr(self, 'coop_connection_button'):
            return
        available = feature.COOP_FEATURE_ENABLED
        for widget in (self.coop_controls_frame, self.shop_coop_row):
            widget.grid() if available else widget.grid_remove()
        enabled = available and self.coop_mode_var.get()
        guest = self.coop_guest_connected()
        self.campaign_combo.configure(values=(
            ('All Campaigns', 'Allies', 'Soviets', 'Epsilon') if enabled else
            ('All Campaigns', 'Allies', 'Soviets', 'Epsilon', 'Foehn')
        ))
        if enabled and self.campaign_var.get() == 'Foehn':
            self.campaign_var.set('All Campaigns')
        self.rewards_per_check_label.configure(
            text='Rewards per mission' if enabled else 'Rewards per objective'
        )
        for button in (self.coop_connection_button, self.shop_coop_connection_button):
            button.configure(state='normal' if available else 'disabled')
        process = getattr(self, 'active_game_process', None)
        active_game = process is not None and process.poll() is None
        run = getattr(self, 'shop_run', None)
        active_shop = bool(self.shop_mode_selected() and run is not None
                           and run.status is RunStatus.ACTIVE)
        locked = (not available or bool(getattr(self, '_coop_lobby', None))
                  or active_game or active_shop or self.gameplay_settings_locked())
        for widget in (self.coop_mode_check, self.shop_coop_mode_check):
            widget.configure(state='disabled' if locked else 'normal')
        for widget in (self.coop_player_count_combo, self.shop_coop_player_count_combo):
            widget.configure(state='disabled' if locked else 'readonly')
        self._refresh_coop_connection_fields()
        for button in (self.launch_selected_button, self.compact_launch_button):
            button.configure(text='Suggest Mission' if guest else 'Launch Selected Mission')
        for button in (self.debug_complete_button, self.compact_complete_button):
            button.configure(text='Record Co-op Victory' if enabled else 'Mark Mission Complete')
        self.sync_debug_completion_controls()

    def active_mission_exclusions(self):
        return (self.excluded_coop_mission_codes if self.coop_mode_var.get()
                else self.excluded_mission_codes)

    def coop_guest_connected(self):
        lobby = getattr(self, '_coop_lobby', None)
        return bool(lobby and lobby.role == 'guest')

    def on_coop_mode_changed(self):
        if self.coop_mode_var.get() and not feature.COOP_FEATURE_ENABLED:
            self.coop_mode_var.set(False)
            return
        process = getattr(self, 'active_game_process', None)
        if (self.gameplay_settings_locked() or getattr(self, '_coop_lobby', None)
                or (process is not None and process.poll() is None)):
            self.coop_mode_var.set(bool(self.config.get('coop_mode', False)))
            return
        enabled = bool(self.coop_mode_var.get())
        if self.shop_mode_selected():
            run = self.shop_repository.load_run()
            if run is not None and run.status is RunStatus.ACTIVE:
                co_op_run = bool(run.eligible_mission_codes) and all(
                    str(code).startswith('COOP_') for code in run.eligible_mission_codes
                )
                if co_op_run != enabled:
                    self.coop_mode_var.set(bool(self.config.get('coop_mode', False)))
                    messagebox.showwarning(
                        'Co-op Shop',
                        'Finish the active Shop run before switching its mission pool.',
                        parent=self,
                    )
                    return
        self.config['coop_mode'] = enabled
        self.config['progression_mode'] = self.progression_mode_var.get()
        self.refresh_coop_controls()
        self.config['campaign_filter'] = self.campaign_var.get()
        save_config(self.config)
        self.state = self.load_state()
        self.migrate_state()
        if self.state and not self.shop_mode_selected():
            self.progression_mode_var.set(self.state.get('progression_mode', 'Grid Mode'))
            self.reward_mode_var.set(self.state.get('reward_mode', self.reward_mode_var.get()))
            self.campaign_var.set(self.state.get('campaign_filter', self.campaign_var.get()))
            self.mission_goal_var.set(self.state.get('mission_goal', self.mission_goal_var.get()))
            self.rewards_per_check_var.set(self.state.get(
                'rewards_per_check', self.rewards_per_check_var.get()
            ))
        self.apply_missions(self.load_missions())
        if self.shop_mode_selected():
            self.sync_shop_workspace()
            self.refresh_shop_mode()
        self.grid_render_signature = None
        self.redraw_progression_views()
        self.update_header_summary()
        self.refresh_progress_view()
        self.refresh_setting_states()
        self._record_coop_log('Co-op map pool selected.' if enabled else 'Campaign map pool selected.')

    def _connect_coop(self, role, name, address, *, pairing_code=''):
        if not feature.COOP_FEATURE_ENABLED:
            return
        if getattr(self, '_coop_lobby', None):
            return
        if self.active_game_process is not None and self.active_game_process.poll() is None:
            messagebox.showwarning('Co-op', 'Close current game first.')
            return
        if self.shop_mode_selected():
            run = self.shop_repository.load_run()
            if run is None:
                messagebox.showwarning('Co-op', 'Start a Shop run first.')
                return
            if run.status is not RunStatus.ACTIVE:
                try:
                    recoverable = role == 'host' and recovery_result_message(run) is not None
                except ValueError as exc:
                    messagebox.showwarning('Co-op', str(exc))
                    return
                if not recoverable:
                    messagebox.showwarning(
                        'Co-op', 'A finished Shop run can reconnect only as host to sync its result.'
                    )
                    return
            if (not run.eligible_mission_codes or any(
                    not str(code).startswith('COOP_')
                    for code in run.eligible_mission_codes)):
                messagebox.showwarning('Co-op', 'Start a Shop run from the co-op map pool.')
                return
        elif role == 'host' and not self.state.get('coop_mode'):
            messagebox.showwarning('Co-op', 'Generate or load a co-op seed first.')
            return
        try:
            pairing_code = pairing_code.strip()
            port = LOBBY_PORT
            if not 16 <= len(pairing_code) <= 128:
                raise ValueError('Enter the host pairing code (16–128 characters).')
            lobby = Lobby(GAME_ROOT, role, name.strip(), address=address.strip(),
                          port=port, pairing_code=pairing_code)
        except (ValueError, OSError) as exc:
            self._record_coop_log('Co-op connection failed: ' + str(exc), error=True)
            messagebox.showerror('Co-op', self._coop_safe_message(exc))
            return
        self.config['coop_network_mode'] = normalize_network_mode(
            self.config.get('coop_network_mode')
        )
        if role == 'guest':
            self.config['coop_last_host'] = address.strip()
            names = ('campaign_var', 'reward_mode_var', 'seed_var', 'difficulty_var',
                     'progression_mode_var', 'mission_goal_var', 'rewards_per_check_var',
                     'selected_index')
            self._coop_local_snapshot = (copy.deepcopy(self.state), {
                key: getattr(self, key).get() for key in names
            })
        save_config(self.config)
        self._coop_lobby = lobby
        self._coop_connection_error = False
        self._coop_shop_ready = False
        self._coop_shop_stage_digest = ''
        self._refresh_coop_connection_fields()
        self._set_coop_status('Waiting for guest…' if role == 'host' else 'Connecting…')
        self._record_coop_log(f'Co-op starting as {role}; lobby TCP {port}.')
        self.refresh_coop_controls()
        lobby.start()
        self.after(100, self._poll_coop_lobby)

    def disconnect_coop(self):
        process = getattr(self, 'active_game_process', None)
        if process is not None and process.poll() is None:
            self._record_coop_log('Close the active game before disconnecting.', error=True)
            return
        lobby = getattr(self, '_coop_lobby', None)
        if not lobby:
            return
        was_guest = lobby.role == 'guest'
        lobby.close()
        self._coop_lobby = None
        self._coop_shop_ready = False
        self._coop_shop_stage_digest = ''
        if was_guest:
            snapshot = self.__dict__.pop('_coop_local_snapshot', None)
            if snapshot:
                self.state, settings = snapshot
                for key, value in settings.items():
                    getattr(self, key).set(value)
            else:
                self.state = self.load_state()
                self.migrate_state()
            self._refresh_coop_state_views()
        self._refresh_coop_connection_fields()
        if not getattr(self, '_coop_connection_error', False):
            self._set_coop_status('Disconnected.')
        self._record_coop_log('Co-op lobby disconnected.')
        self.refresh_coop_controls()

    def _refresh_coop_state_views(self):
        for key in ('_active_reward_settings_cache', '_canonical_earned_rewards_cache',
                    '_unlock_dashboard_sources_cache', '_configured_reward_pool_cache'):
            self.__dict__.pop(key, None)
        self._enemy_buffs_view_dirty = True
        self.grid_render_signature = None
        self._coop_applying_selection = True
        try:
            self.redraw_mission_tree()
            self.redraw_progression_views()
            self.refresh_progress_view()
            self.update_header_summary()
            self.refresh_setting_states()
            self.refresh_coop_controls()
        finally:
            self._coop_applying_selection = False

    def _poll_coop_lobby(self):
        lobby = getattr(self, '_coop_lobby', None)
        if not lobby:
            return
        try:
            while True:
                event = lobby.events.get_nowait()
                if event[0] == 'status':
                    self._record_coop_log('Co-op: ' + event[1])
                    self._set_coop_status(event[1])
                elif event[0] == 'diagnostic':
                    label, details = event[1]
                    log_event(label, **details)
                    self._record_coop_log(label + ': ' + json.dumps(details, sort_keys=True))
                elif event[0] == 'listening':
                    self._record_coop_log(f'Co-op lobby listening on TCP {event[1]}.')
                elif event[0] == 'connected':
                    self._record_coop_log(f'Co-op lobby connected to {event[1]}.')
                    self.refresh_coop_controls()
                    self._set_coop_status(f'Connected to {event[1]}. Host selects and launches.')
                    if lobby.role == 'host':
                        self.coop_publish_state()
                elif event[0] == 'message':
                    self._handle_coop_message(lobby, event[1])
                elif event[0] == 'error':
                    self._record_coop_log('Co-op lobby: ' + event[1], error=True)
                    self._coop_connection_error = True
                    self._set_coop_status('Disconnected: ' + event[1])
                elif event[0] == 'disconnected':
                    self.disconnect_coop()
                    return
        except queue.Empty:
            pass
        except CoopShopSetupRequired as exc:
            self._record_coop_log('Co-op Shop setup required: ' + str(exc), error=True)
            self._coop_connection_error = True
            self.disconnect_coop()
            # Disconnect restores the guest's previous settings first. Show the
            # local Shop setup afterward, without replacing an existing run.
            self.progression_mode_var.set('Shop Mode')
            run = self.shop_repository.load_run()
            if run is None or run.status is not RunStatus.ACTIVE:
                self.seed_var.set(exc.seed)
            self.sync_shop_workspace()
            self.workspace_tabs.select(self.settings_tab)
            self.refresh_setting_states()
            self._set_coop_status('Shop setup required. Start a matching run, then reconnect.')
            messagebox.showwarning('Co-op Shop Setup', str(exc), parent=self)
            return
        except Exception as exc:
            self._record_coop_log('Co-op lobby message failed: ' + str(exc), error=True)
            self._coop_connection_error = True
            self._set_coop_status('Disconnected: ' + str(exc))
            self.disconnect_coop()
            return
        self.after(100, self._poll_coop_lobby)

    def coop_publish_state(self):
        lobby = getattr(self, '_coop_lobby', None)
        if not (lobby and lobby.connected and lobby.role == 'host'):
            return
        if self.shop_mode_selected() and self.coop_mode_var.get():
            try:
                run = self.shop_repository.load_run()
                result = recovery_result_message(run)
                if result:
                    lobby.send(result)
                if run is not None and run.status is RunStatus.ACTIVE:
                    self.coop_publish_shop_stage()
            except (OSError, ValueError) as exc:
                self._record_coop_log('Co-op Shop recovery sync failed: ' + str(exc), error=True)
            return
        if not self.state.get('coop_mode'):
            return
        try:
            lobby.send({'type': 'state', 'data': encode_state(self.state)})
            self.coop_broadcast_selection()
        except (OSError, ValueError) as exc:
            self._record_coop_log('Co-op state sync failed: ' + str(exc), error=True)

    def coop_publish_shop_stage(self):
        lobby = getattr(self, '_coop_lobby', None)
        if not (lobby and lobby.connected and lobby.role == 'host'
                and self.coop_mode_var.get() and self.shop_mode_selected()):
            return
        try:
            snapshot = stage_snapshot(self.shop_repository.load_run())
            self._coop_shop_stage_digest = stage_digest(snapshot)
            self._coop_shop_ready = False
            lobby.send({'type': 'shop_stage', 'data': snapshot})
        except (OSError, ValueError) as exc:
            self._record_coop_log('Co-op Shop stage sync failed: ' + str(exc), error=True)

    def coop_broadcast_selection(self):
        lobby = getattr(self, '_coop_lobby', None)
        mission = self.selected_mission()
        if lobby and lobby.connected and lobby.role == 'host' and mission:
            try:
                lobby.send({'type': 'select', 'code': mission['code']})
            except OSError as exc:
                self._record_coop_log('Co-op selection sync failed: ' + str(exc), error=True)

    def coop_selection_changed(self):
        if getattr(self, '_coop_applying_selection', False):
            return
        lobby = getattr(self, '_coop_lobby', None)
        mission = self.selected_mission()
        if not (lobby and lobby.connected and mission and self.state.get('coop_mode')):
            return
        if lobby.role == 'host':
            self.coop_broadcast_selection()
        else:
            try:
                lobby.send({'type': 'suggest', 'code': mission['code']})
                self._record_coop_log(f'Suggested {mission["title"]} to host.')
            except OSError as exc:
                self._record_coop_log('Co-op suggestion failed: ' + str(exc), error=True)

    def _handle_coop_message(self, lobby, message):
        kind = message['type']
        if lobby.role == 'guest':
            if kind == 'shop_stage':
                if not self.coop_mode_var.get():
                    raise ValueError('Enable co-op before joining a Shop host.')
                run = self.shop_repository.load_run()
                snapshot = message.get('data')
                if (not self.shop_mode_selected() or run is None
                        or run.status is not RunStatus.ACTIVE):
                    raise CoopShopSetupRequired(snapshot)
                updated = apply_stage_snapshot(run, snapshot, self.mission_lookup())
                if updated != run:
                    self.shop_repository.save_run(updated)
                self.shop_run = updated
                self.refresh_shop_mode()
                lobby.send({'type': 'shop_ready', 'digest': stage_digest(snapshot)})
                self._record_coop_log(f'Host Shop stage {updated.stage} synced.')
            elif kind == 'shop_victory':
                if not (self.coop_mode_var.get() and self.shop_mode_selected()):
                    raise ValueError('Host Shop victory reached a non-Shop guest.')
                run = self.shop_repository.load_run()
                code = message.get('code')
                stage = message.get('stage')
                if type(stage) is not int:
                    raise ValueError('Host Shop victory has invalid stage.')
                if (run is not None and run.seed == message.get('seed')
                        and code in run.completed_missions
                        and (run.stage > stage or run.status is RunStatus.COMPLETED)):
                    return
                if (run is None or run.status is not RunStatus.ACTIVE
                        or run.seed != message.get('seed') or run.stage != stage
                        or not run.mission_committed
                        or run.selected_mission_code != code):
                    raise ValueError('Host Shop victory differs from guest committed stage.')
                self._shop_launch_run = run
                self._shop_launch_mission_pool = tuple(self._shop_run_mission_pool(run))
                if not self.unlock_mission_check(code, 'victory', 'Co-op host victory'):
                    raise ValueError('Guest Shop victory could not be recorded.')
                self._record_coop_log(f'Co-op Shop victory synced for {code}.')
                process = getattr(self, 'active_game_process', None)
                if process is None or process.poll() is not None:
                    self.finish_progression_launch_context()
            elif kind == 'shop_failure':
                if not (self.coop_mode_var.get() and self.shop_mode_selected()):
                    raise ValueError('Host Shop failure reached a non-Shop guest.')
                run = self.shop_repository.load_run()
                code = message.get('code')
                stage = message.get('stage')
                token = message.get('session_token')
                recovery = message.get('recovery') is True
                if (type(stage) is not int or not isinstance(code, str)
                        or not code.startswith('COOP_')
                        or type(message.get('revived')) is not bool
                        or message.get('recovery') not in (None, True)
                        or (not recovery and (
                            not isinstance(token, str) or len(token) < 24
                            or token != getattr(self, '_coop_active_game_token', None)
                        ))):
                    raise ValueError('Host Shop failure has invalid game identity.')
                if (run is None or run.seed != message.get('seed')
                        or run.stage != stage):
                    raise ValueError('Host Shop failure differs from guest run.')
                if (run.status is RunStatus.FAILED
                        and run.failed_stage == stage
                        and run.failed_mission_code == code):
                    return
                if (run.status is RunStatus.ACTIVE and not run.mission_committed
                        and run.emergency_revivals_used > 0):
                    return
                if (run.status is not RunStatus.ACTIVE or not run.mission_committed
                        or run.selected_mission_code != code):
                    raise ValueError('Host Shop failure differs from guest committed stage.')
                self.shop_profile, run = self.shop_repository.load()
                self._shop_launch_run = run
                self._shop_launch_mission_pool = tuple(self._shop_run_mission_pool(run))
                self._coop_host_revival = message['revived']
                try:
                    recorded = self.record_failed_mission_attempt(
                        code, 'Co-op host failure'
                    )
                finally:
                    self._coop_host_revival = None
                if not recorded:
                    raise ValueError('Guest Shop failure could not be recorded.')
                self._record_coop_log(f'Co-op Shop failure synced for {code}.')
                process = getattr(self, 'active_game_process', None)
                if process is None or process.poll() is not None:
                    self.finish_progression_launch_context()
            elif kind == 'state':
                state = decode_state(message.get('data', ''))
                codes = state.get('mission_order', [])
                available = {mission['code'] for mission in self.missions}
                if not isinstance(codes, list) or not codes or not all(
                        code in available for code in codes):
                    raise ValueError('Host co-op maps differ from installed catalogue.')
                self.state = state
                for key, variable in (
                    ('seed', self.seed_var), ('campaign_filter', self.campaign_var),
                    ('reward_mode', self.reward_mode_var),
                    ('progression_mode', self.progression_mode_var),
                    ('mission_goal', self.mission_goal_var),
                    ('rewards_per_check', self.rewards_per_check_var),
                ):
                    if key in state:
                        variable.set(state[key])
                self._refresh_coop_state_views()
                self._record_coop_log(f'Host Grid synced: {len(codes)} maps, seed {state["seed"]}.')
            elif kind == 'select':
                code = message.get('code')
                index = next((i for i, mission in enumerate(self.missions)
                              if mission['code'] == code), None)
                if index is not None:
                    self._coop_applying_selection = True
                    try:
                        if self.active_progression_mode() == 'Grid Mode':
                            self.select_grid_mission(index)
                        else:
                            self.selected_index.set(index)
                            self.refresh_progress_view(refresh_unlocks=False)
                    finally:
                        self._coop_applying_selection = False
            elif kind == 'launch':
                code = message.get('code')
                if self.shop_mode_selected() and self.coop_mode_var.get():
                    run = self.shop_repository.load_run()
                    if (run is None or run.status is not RunStatus.ACTIVE
                            or not run.mission_committed
                            or run.selected_mission_code != code):
                        raise ValueError('Host Shop launch differs from guest committed mission.')
                    self._shop_launch_run = run
                    self._shop_launch_victory_key = None
                    self._shop_launch_mission_pool = tuple(self._shop_run_mission_pool(run))
                elif code not in self.state.get('mission_order', []):
                    raise ValueError('Host selected map outside shared run.')
                session_token = message.get('session_token')
                if not isinstance(session_token, str) or len(session_token) < 24:
                    raise ValueError('Host sent invalid co-op game token.')
                self._start_coop_game('guest', code, session_token=session_token)
        elif kind == 'shop_ready':
            if (self.shop_mode_selected() and self.coop_mode_var.get()
                    and getattr(self, '_coop_shop_stage_digest', '')
                    and message.get('digest') == self._coop_shop_stage_digest):
                self._coop_shop_ready = True
                self._record_coop_log('Guest Shop stage ready.')
                self.refresh_shop_mode()
            else:
                raise ValueError('Guest acknowledged a different Shop stage.')
        elif kind == 'suggest':
            code = message.get('code')
            mission = self.mission_lookup().get(code)
            if mission and code in self.state.get('mission_order', []):
                self._record_coop_log(f'{lobby.peer} suggests {mission["title"]} ({code}).')
                self._set_coop_status(f'{lobby.peer} suggests {mission["title"]}. Select it in Grid to play.')

    def request_coop_launch(self):
        if not feature.COOP_FEATURE_ENABLED:
            messagebox.showwarning('Co-op', 'Co-op is disabled in this build.')
            return
        lobby = getattr(self, '_coop_lobby', None)
        mission = self.selected_mission()
        if not self.state.get('coop_mode') or mission is None:
            messagebox.showwarning('Co-op', 'Generate a co-op seed and select a map first.')
            return
        if mission['code'] not in set(self.unlocked_mission_codes()) | set(
                self.state.get('completed_missions', [])):
            messagebox.showwarning('Co-op', 'Selected co-op map is locked.')
            return
        if not lobby or not lobby.connected:
            messagebox.showwarning('Co-op', 'Connect both launchers first.')
            return
        if lobby.role == 'guest':
            self.coop_selection_changed()
        else:
            self._start_coop_game('host', mission['code'])

    def _start_coop_game(self, role, code, *, session_token=''):
        if not feature.COOP_FEATURE_ENABLED:
            return
        lobby = getattr(self, '_coop_lobby', None)
        if getattr(self, '_coop_busy', False) or not lobby or not lobby.connected:
            return
        if self.active_game_process is not None and self.active_game_process.poll() is None:
            messagebox.showwarning('Co-op', 'Close current game first.')
            return
        self._coop_busy = True
        if role == 'host':
            session_token = secrets.token_urlsafe(24)
        self._coop_queue = queue.Queue()
        self._coop_active_game_code = code
        self._coop_active_game_role = role
        self._coop_active_game_token = session_token
        mission = self.mission_lookup().get(code)
        state_snapshot = copy.deepcopy(self.state)
        shop_run = (self.shop_repository.load_run()
                    if self.shop_mode_selected() and self.coop_mode_var.get()
                    else None)
        difficulty = {'Casual': 'easy', 'Normal': 'normal',
                      'Mental': 'hard'}.get(self.difficulty_var.get(), 'normal')
        if shop_run is not None:
            level = self.shop_mission_difficulty_value(shop_run, code)
            if shop_run.assisted_mission_code == code:
                level = max(0, level - 1)
            difficulty = ('easy', 'normal', 'hard')[min(2, max(0, level))]
        self._record_coop_log(f'Preparing co-op map {code} as {role}.')
        self._set_coop_status('Preparing map and connecting game…')

        def worker():
            try:
                if role == 'host':
                    if not mission:
                        raise ValueError('Selected co-op map is missing.')
                    if shop_run is not None:
                        if (shop_run.status is not RunStatus.ACTIVE
                                or not shop_run.mission_committed
                                or shop_run.selected_mission_code != code):
                            raise ValueError('Host Shop mission is not committed.')
                        manifest = None
                        shop_setup = {
                            'seed': shop_run.seed, 'stage': shop_run.stage,
                            'coop_name': mission['coop_name'],
                            'loadout': shop_unit_loadout(shop_run, self.shop_profile),
                        }
                    else:
                        source_mission = code if state_snapshot.get('reward_mode') == ARSENAL_MODE else ''
                        available = available_units(state_snapshot, source_mission)
                        manifest, _ = build_manifest(
                            GAME_ROOT, state_snapshot, mission['coop_name'],
                            source_mission=source_mission,
                            unit_id='' if available else 'FV', allow_test_unit=True,
                        )
                        shop_setup = None
                    lobby.send({'type': 'launch', 'code': code,
                                'session_token': session_token})
                    result = host_session(
                        GAME_ROOT, manifest, name=lobby.name,
                        control_port=lobby.port + 1,
                        difficulty=difficulty,
                        session_token=session_token,
                        shop_setup=shop_setup,
                    )
                else:
                    same_machine = lobby.address.lower() in ('127.0.0.1', 'localhost')
                    shop_setup = ({
                        'seed': shop_run.seed, 'stage': shop_run.stage,
                        'loadout': shop_unit_loadout(shop_run, self.shop_profile),
                    } if shop_run is not None else None)
                    result = join_session(
                        GAME_ROOT, lobby.address, name=lobby.name,
                        control_port=lobby.port + 1,
                        game_port=1235 if same_machine else 1234,
                        session_token=session_token,
                        shop_setup=shop_setup,
                    )
                self._coop_queue.put(('ready', result))
            except Exception as exc:
                self._coop_queue.put(('error', str(exc), traceback.format_exc()))

        threading.Thread(target=worker, name='CoopGame', daemon=True).start()
        self.after(100, self._poll_coop_session)

    def _poll_coop_session(self):
        try:
            event = self._coop_queue.get_nowait()
        except queue.Empty:
            if getattr(self, '_coop_busy', False):
                self.after(100, self._poll_coop_session)
            return
        if event[0] == 'error':
            self._coop_busy = False
            if self.shop_mode_selected():
                self.finish_progression_launch_context()
            self._record_coop_log('Co-op game failed: ' + event[1], error=True)
            self._record_coop_log(event[2], error=True)
            self._set_coop_status('Game connection failed: ' + event[1])
            messagebox.showerror('Co-op', self._coop_safe_message(event[1]))
            return
        result = event[1]
        self._record_coop_log(f'Co-op paired with {result["peer"]}; game ID {result["game_id"]}; '
                        f'map {result["map_sha256"]}.')
        try:
            process, _ = self.spawn_game_process(self.build_command())
        except Exception as exc:
            self._coop_busy = False
            if self.shop_mode_selected():
                self.finish_progression_launch_context()
            self._record_coop_log('Co-op game launch failed: ' + str(exc), error=True)
            messagebox.showerror('Co-op', self._coop_safe_message(exc))
            return
        self.active_game_process = process
        if result['role'] == 'host':
            try:
                with DEBUG_LOG.open('rb') as handle:
                    log_stat = os.fstat(handle.fileno())
                    handle.seek(max(0, log_stat.st_size - 64))
                    log_anchor = handle.read(64)
            except OSError:
                log_stat = None
                log_anchor = b''
            self._coop_victory_watch = {
                'code': self._coop_active_game_code,
                'marker': victory_marker_name(self._coop_active_game_code.lower()),
                'offset': log_stat.st_size if log_stat else 0,
                'file_id': (log_stat.st_dev, log_stat.st_ino) if log_stat else None,
                'anchor': log_anchor,
                'detected': False,
            }
        else:
            self._coop_victory_watch = None
        self._record_coop_log(f'Co-op game started as {result["role"]}.')
        self._set_coop_status('Game running. Lobby stays connected.')
        self.after(1000, self._poll_coop_game)

    def _poll_coop_game(self):
        self._scan_coop_victory()
        process = self.active_game_process
        if process is not None and process.poll() is None:
            self.after(1000, self._poll_coop_game)
            return
        self.active_game_process = None
        self._coop_busy = False
        self._record_coop_log('Co-op game process exited.')
        watch = getattr(self, '_coop_victory_watch', None)
        if watch and not watch['detected'] and not self.is_mission_complete(watch['code']):
            if (self.shop_mode_selected() and self.coop_mode_var.get()
                    and getattr(self, '_coop_active_game_role', '') == 'host'
                    and DEBUG_LOG.exists() and not watch.get('log_error')):
                if self.record_failed_mission_attempt(
                        watch['code'], 'Co-op game closed without victory'):
                    self._record_coop_log('Co-op Shop attempt recorded as failed for both players.')
            else:
                self._record_coop_log('No co-op victory marker detected. Host can record a won mission manually.')
        self._coop_victory_watch = None
        if self.shop_mode_selected() and self.coop_mode_var.get():
            self.finish_progression_launch_context()
        lobby = getattr(self, '_coop_lobby', None)
        self._set_coop_status(
            'Game ended. Host may select another map.' if lobby and lobby.connected else
            'Game ended. Lobby disconnected; click Disconnect before reconnecting.'
        )
        if getattr(self, '_close_after_game', False):
            self.disconnect_coop()
            self.shutdown_archipelago()
            self.destroy()

    def _scan_coop_victory(self):
        watch = getattr(self, '_coop_victory_watch', None)
        if not watch or watch['detected'] or not DEBUG_LOG.exists():
            return
        try:
            with DEBUG_LOG.open('rb') as handle:
                log_stat = os.fstat(handle.fileno())
                file_id = (log_stat.st_dev, log_stat.st_ino)
                offset = watch['offset']
                if log_stat.st_size < offset or watch.get('file_id') != file_id:
                    offset = 0
                elif offset and watch.get('anchor') is not None:
                    anchor_start = max(0, offset - 64)
                    handle.seek(anchor_start)
                    if handle.read(offset - anchor_start) != watch['anchor']:
                        offset = 0
                handle.seek(offset)
                data = handle.read()
                watch['offset'] = handle.tell()
                anchor_start = max(0, watch['offset'] - 64)
                handle.seek(anchor_start)
                watch['anchor'] = handle.read(watch['offset'] - anchor_start)
                watch['file_id'] = file_id
        except OSError as exc:
            watch['log_error'] = True
            self._record_coop_log('Co-op victory log read failed: ' + str(exc), error=True)
            return
        if not any(watch['marker'] in line for line in data.decode(
                'utf-8', errors='ignore').splitlines()):
            return
        watch['detected'] = True
        code = watch['code']
        if self.is_mission_complete(code):
            return
        self._record_coop_log(f'Co-op victory marker detected for {code}.')
        self.unlock_mission_check(code, 'victory', 'Co-op in-game victory')
