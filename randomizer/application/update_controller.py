"""Non-blocking release checks and one automatic notice per released version."""

import os
from pathlib import Path
import queue
import sys
import threading
from tkinter import TclError, messagebox, ttk

from randomizer.core.diagnostics import event as log_event
from randomizer.core.paths import APP_DIR, FROZEN
from randomizer.core.update_profile import APWORLD_NAME, PRODUCT_NAME
from randomizer.core.updater import (
    check_latest_release,
    notice_shown,
    remember_notice,
    stage_update,
    start_update_helper,
)
from randomizer.core.version import APP_VERSION


class UpdateController:
    def create_update_button(self, parent):
        self.update_button = ttk.Button(parent, text='Check for updates', command=self.check_or_offer_update)
        self.update_button.grid(row=0, column=0, sticky='ne', padx=(0, 8))
        if not FROZEN or os.name != 'nt':
            self.update_button.grid_remove()

    def check_or_offer_update(self):
        if getattr(self, '_available_update', None) is not None:
            self.offer_update()
        else:
            self.start_update_check(manual=True)

    def start_update_check(self, manual=False):
        """Source/developer launches never offer to replace a packaged EXE."""
        if not FROZEN or os.name != 'nt':
            log_event('update_check_skipped', reason='requires_packaged_windows_launcher')
            return
        if getattr(self, '_update_check_running', False):
            return
        self._update_check_running = True
        self._update_check_manual = manual
        self._update_results = queue.Queue()
        self.update_button.configure(text='Checking…', state='disabled')
        log_event('update_check_started', installed_version=APP_VERSION, manual=manual)

        def worker():
            try:
                self._update_results.put(('release', check_latest_release(APP_VERSION)))
            except Exception as exc:
                self._update_results.put(('error', str(exc)))

        threading.Thread(target=worker, name='GitHubReleaseCheck', daemon=True).start()
        self.after(200, self.poll_update_check)

    def poll_update_check(self):
        try:
            kind, value = self._update_results.get_nowait()
        except queue.Empty:
            self.after(200, self.poll_update_check)
            return
        self._update_check_running = False
        self.update_button.configure(text='Check for updates', state='normal')
        if kind == 'error':
            # Offline, rate-limited, and incomplete releases never block play.
            log_event('update_check_unavailable', error=value)
            if self._update_check_manual:
                messagebox.showinfo(
                    'Update check unavailable',
                    f'Could not check for updates.\n\n{value}\n\n'
                    'You can keep playing and retry with Check for updates.',
                    parent=self,
                )
            return
        if value is None:
            log_event('update_check_current', installed_version=APP_VERSION)
            if self._update_check_manual:
                messagebox.showinfo(
                    'No update available',
                    f'No newer stable release is available. You have {APP_VERSION}.',
                    parent=self,
                )
            return
        self._available_update = value
        self.update_button.configure(text='Update')
        log_event('update_available', installed_version=APP_VERSION, version=value.version)
        if self._update_check_manual:
            self.offer_update()
        else:
            self.after(300, self.offer_automatic_update)

    def update_activity_locked(self):
        process = getattr(self, 'active_game_process', None)
        session = getattr(self, '_archipelago_session', None)
        return bool(
            (process is not None and process.poll() is None)
            or getattr(self, 'busy_depth', 0)
            or getattr(self, '_coop_busy', False)
            or getattr(self, '_coop_lobby', None) is not None
            or getattr(self, '_challenge_preparing', False)
            or getattr(self, '_close_after_game', False)
            or getattr(self, '_update_installing', False)
            or session is not None
            or (callable(getattr(self, 'coop_guest_connected', None))
                and self.coop_guest_connected())
        )

    def offer_automatic_update(self):
        update = self._available_update
        if update is None or getattr(self, '_update_notice_handled', False):
            return
        if notice_shown(APP_DIR, update.version):
            self._update_notice_handled = True
            return
        if self.update_activity_locked() or self.grab_current() is not None:
            self.after(2000, self.offer_automatic_update)
            return
        self.offer_update(automatic=True)

    def offer_update(self, automatic=False):
        update = getattr(self, '_available_update', None)
        if update is None:
            return
        if self.update_activity_locked():
            if not automatic:
                messagebox.showinfo(
                    'Update available',
                    'Finish the current operation or mission and disconnect multiplayer '
                    'before updating. Your Update button will remain available.',
                    parent=self,
                )
            return
        self._update_notice_handled = True
        accepted = messagebox.askyesno(
            f'{PRODUCT_NAME} update',
            f'Version {update.version} is available. You have {APP_VERSION}.\n\n'
            'Download the update and restart the launcher?\n'
            'Your saves, settings, and current run will be kept.\n\n'
            'Choose No to finish your run. This version will not prompt again; '
            'the Update button stays available.\n\n'
            f'The matching {APWORLD_NAME} will be saved beside the launcher. '
            'Install it in Archipelago before generating a new multiworld.',
            parent=self,
        )
        try:
            # Only a dialog that was actually displayed can suppress a notice.
            remember_notice(APP_DIR, update.version)
        except (OSError, ValueError) as exc:
            log_event('update_notice_persistence_failed', error=str(exc))
        if not accepted:
            return
        # Tk message boxes run a nested event loop; recheck before staging.
        if self.update_activity_locked():
            return
        self._update_installing = True
        self.update_button.configure(state='disabled')
        self.run_in_background(
            'Downloading update…', 'Downloading and verifying release files.',
            lambda: stage_update(
                update, APP_DIR, Path(sys.executable), self.queue_busy_progress,
            ),
            self.finish_update_download,
            self.handle_update_error,
        )

    def finish_update_download(self, request):
        self._update_installing = False
        if self.update_activity_locked():
            self.handle_update_error(
                RuntimeError('Launcher became busy. Finish the mission or disconnect before retrying.'), '',
            )
            return
        helper = None
        try:
            self.save_current_launcher_config()
            helper = start_update_helper(request)
            self.close_launcher()
            # Only a successful close authorizes replacement. The helper waits
            # for this process and the one-file bootloader to release the EXE.
            (Path(request).parent / 'approved').write_text('approved\n', encoding='ascii')
        except Exception as exc:
            if helper is not None:
                helper.terminate()
            self.handle_update_error(exc, '')

    def handle_update_error(self, exc, detail):
        self._update_installing = False
        try:
            self.update_button.configure(state='normal')
            parent = self if self.winfo_exists() else None
        except TclError:
            parent = None
        log_event('update_failed', error=str(exc), traceback=detail)
        messagebox.showerror(
            'Update failed',
            f'{exc}\n\nYou can keep playing and retry with the Update button.',
            parent=parent,
        )
