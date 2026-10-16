"""Recover a spawned Windows game that stalls after its game loop has ended.

This watches native lifecycle messages only. It never determines mission results
and never closes a game merely because a player won, lost, or disconnected.
"""

from __future__ import annotations

import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time


_SCENARIO = re.compile(r'(?:Reading scenario:|----- Starting sc[en]*ario:)\s*(\S+)', re.I)
_GAME_LOOP_FINISHED = re.compile(r'Game loop finished\. Average FPS\s*=\s*\d+(?:\.\d+)?\s*\Z')
_EXIT_PROCESSED = re.compile(r'Processing EXIT event on frame \d+\s*\Z')


class GameShutdownWatch:
    """Capture before launch, bind once, and poll from the owning UI thread.

    ``poll`` returns ``(message, is_error)`` pairs for the UI to log. Recovery
    runs on a worker, targets only the captured Syringe process tree, and gives
    normal native teardown three seconds before intervening. A local quit event
    must be both submitted and processed before the terminal game-loop message;
    an ordinary victory's score screen does not arm recovery.
    """

    def __init__(self, path: Path, *, scenario: str = 'spawnmap.ini',
                 grace_seconds: float = 3.0):
        self.path = Path(path)
        self.scenario = str(scenario).replace('\\', '/').rsplit('/', 1)[-1].casefold()
        self.grace_seconds = grace_seconds
        self.process = None
        self.error = ''
        self._offset = 0
        self._file_id = None
        self._anchor = b''
        self._unarmed = False
        self._attempted = False
        self._cancelled = threading.Event()
        self._recovering = threading.Event()
        self._messages = queue.SimpleQueue()
        self._reset_session()
        try:
            with self.path.open('rb') as handle:
                stat = os.fstat(handle.fileno())
                self._file_id = (stat.st_dev, stat.st_ino)
                self._offset = stat.st_size
                handle.seek(max(0, self._offset - 64))
                self._anchor = handle.read()
        except FileNotFoundError:
            pass
        except OSError as exc:
            # Without a trustworthy old boundary, never arm against old logs.
            self.error = str(exc)
            self._unarmed = True
            self._messages.put(('Game shutdown recovery could not watch the log: ' + self.error, True))

    def bind(self, process: subprocess.Popen) -> None:
        """Associate this pre-launch snapshot with exactly one spawned process."""
        if self.process is not None:
            raise ValueError('A shutdown watcher cannot be reused for another game.')
        self.process = process

    def close(self) -> None:
        """Disarm when the tracked process exits or its launch is abandoned."""
        self._cancelled.set()

    @property
    def recovery_pending(self) -> bool:
        """Keep polling long enough to deliver the worker's final log message."""
        # The worker enqueues its final message before clearing _recovering. A
        # poll may have drained just before that enqueue, so keep the queue in
        # this condition as well to avoid losing the final recovery diagnostic.
        return self._recovering.is_set() or not self._messages.empty()

    def _reset_session(self) -> None:
        self._remainder = ''
        self._scenario_seen = False
        self._game_started = False
        self._local_exit_added = False
        self._local_exit_processed = False
        self._finished_at = None

    def _feed(self, text: str) -> None:
        lines = (self._remainder + text).splitlines(keepends=True)
        self._remainder = ''
        if lines and not lines[-1].endswith(('\n', '\r')):
            self._remainder = lines.pop()
            if len(self._remainder) > 65536:
                self._remainder = ''
        for line in lines:
            line = line.rstrip('\r\n')
            scenario = _SCENARIO.search(line)
            if scenario:
                self._scenario_seen = (
                    scenario.group(1).replace('\\', '/').rsplit('/', 1)[-1].casefold()
                    == self.scenario
                )
                self._game_started = False
                self._local_exit_added = False
                self._local_exit_processed = False
                self._finished_at = None
            elif self._scenario_seen and line.strip() == 'Capture_Mouse()':
                self._game_started = True
                # A resumed/restarted game must not inherit an old deadline.
                if self._finished_at is not None:
                    self._local_exit_added = False
                    self._local_exit_processed = False
                self._finished_at = None
            elif (self._scenario_seen and self._game_started
                  and line.strip() == 'Adding event EXIT'):
                self._local_exit_added = True
            elif self._local_exit_added and _EXIT_PROCESSED.fullmatch(line):
                self._local_exit_processed = True
            elif (self._scenario_seen and self._game_started
                  and self._local_exit_processed and _GAME_LOOP_FINISHED.fullmatch(line)):
                if self._finished_at is None:
                    self._finished_at = time.monotonic()

    def _read_log(self) -> bool:
        try:
            with self.path.open('rb') as handle:
                stat = os.fstat(handle.fileno())
                identity = (stat.st_dev, stat.st_ino)
                offset = self._offset
                replaced = identity != self._file_id or stat.st_size < offset
                if not replaced and offset:
                    start = max(0, offset - 64)
                    handle.seek(start)
                    replaced = handle.read(offset - start) != self._anchor
                if replaced:
                    offset = 0
                    self._reset_session()
                handle.seek(offset)
                while data := handle.read(1_048_576):
                    self._feed(data.decode('latin-1'))
                self._offset = handle.tell()
                handle.seek(max(0, self._offset - 64))
                self._anchor = handle.read()
                self._file_id = identity
        except FileNotFoundError:
            # A missing or unreadable log cannot confirm it is still safe to act.
            self._finished_at = None
            return False
        except OSError as exc:
            if self.error != str(exc):
                self._messages.put(('Game shutdown recovery could not read the log: ' + str(exc), True))
            self.error = str(exc)
            self._finished_at = None
            return False
        self.error = ''
        return True

    def poll(self, process: subprocess.Popen | None) -> list[tuple[str, bool]]:
        """Read fresh lifecycle messages; never act on a different active game."""
        if self.process is not process:
            self.close()
        elif (not self._cancelled.is_set() and not self._unarmed
              and self.process is not None and self.process.poll() is None):
            read_ok = self._read_log()
            if (sys.platform == 'win32' and read_ok and not self._attempted
                    and self._finished_at is not None
                    and time.monotonic() - self._finished_at >= self.grace_seconds):
                self._attempted = True
                self._messages.put((
                    'The game loop ended, but the game did not close after '
                    f'{self.grace_seconds:g} seconds. Recovering only this spawned game '
                    f'(PID={self.process.pid}).', False,
                ))
                self._recovering.set()
                threading.Thread(target=self._recover, daemon=True,
                                 name='game-shutdown-recovery').start()
        messages = []
        while True:
            try:
                messages.append(self._messages.get_nowait())
            except queue.Empty:
                return messages

    def _recover(self) -> None:
        try:
            self._recover_process()
        finally:
            self._recovering.clear()

    def _recover_process(self) -> None:
        process = self.process
        if self._cancelled.is_set() or process is None or process.poll() is not None:
            return
        detail = ''
        try:
            result = subprocess.run(
                ['taskkill', '/PID', str(process.pid), '/T', '/F'],
                capture_output=True, text=True,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                timeout=10,
            )
            if result.returncode:
                detail = (result.stderr or result.stdout).strip()
                self._messages.put((
                    f'Game shutdown recovery taskkill failed for PID={process.pid}: '
                    + (detail or f'exit code {result.returncode}'), True,
                ))
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
            if process.poll() is not None:
                self._messages.put((f'Recovered the stalled game shutdown (PID={process.pid}).', False))
                return
        except (OSError, subprocess.SubprocessError) as exc:
            detail = str(exc)
            self._messages.put((
                f'Game shutdown recovery taskkill failed for PID={process.pid}: {detail}', True,
            ))
        if self._cancelled.is_set() or process.poll() is not None:
            return
        # Popen.terminate uses the original Windows process handle, never a name
        # lookup or a later process that happens to use the same executable.
        try:
            process.terminate()
            process.wait(timeout=3)
            self._messages.put((
                f'Closed the captured game launcher after shutdown recovery (PID={process.pid}).', False,
            ))
        except (OSError, subprocess.SubprocessError) as exc:
            self._messages.put((
                f'Game shutdown recovery failed for PID={process.pid}: {exc}', True,
            ))
