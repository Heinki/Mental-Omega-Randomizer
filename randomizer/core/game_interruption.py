"""Latch fresh engine desync/crash evidence for exactly one game attempt."""

from pathlib import Path
import re


_INTERRUPTION = re.compile(
    r'\b(?:out[- ]of[- ]sync|reconnection error|desynchroni[sz]ed|'
    r'desynchroni[sz]ation (?:detected|error|occurred)|'
    r'desync (?:detected|error|occurred)|DesyncDialog: opening|'
    r'writing sync log to file|failed to open sync log file|'
    r'synchroni[sz]ation (?:error|failed|failure))\b',
    re.IGNORECASE,
)


class GameInterruptionWatch:
    """Capture before spawning; old SYNC/EXCEPT files never taint a new run.

    A desynced engine can still emit native winner/loser records during
    teardown. Fresh interruption evidence takes precedence over those records.
    Directory/read errors also leave the outcome unverified rather than lost.
    """

    def __init__(self, game_root, debug_log):
        root = Path(game_root)
        debug = Path(debug_log)
        self.directories = tuple(dict.fromkeys((
            root, root / 'Debug', root / 'debug',
            debug if debug.is_dir() else debug.parent,
        )))
        self.reason = ''
        self._tail = ''
        self._baseline = self._snapshot()

    def _snapshot(self):
        files = {}
        for directory in self.directories:
            try:
                entries = directory.iterdir()
                for path in entries:
                    name = path.name.casefold()
                    if (not name.startswith(('sync', 'except'))
                            or path.suffix.casefold() not in {'.log', '.txt', '.dmp'}):
                        continue
                    try:
                        stat = path.stat()
                    except FileNotFoundError:
                        continue  # Rotated between directory enumeration and stat.
                    if path.is_file():
                        files[str(path)] = (stat.st_dev, stat.st_ino, stat.st_size,
                                            stat.st_mtime_ns, stat.st_ctime_ns)
            except FileNotFoundError:
                continue
            except OSError:
                self.reason = self.reason or 'Engine diagnostics could not be verified'
        return files

    def observe_text(self, text):
        """Inspect complete chunks together so split error lines are retained."""
        if not self.reason:
            combined = self._tail + str(text or '')
            if _INTERRUPTION.search(combined):
                self.reason = 'Engine desync/reconnection error detected'
            self._tail = combined[-512:]
        return self.poll()

    def poll(self):
        """Return a latched reason; never infer a loss from process exit codes."""
        if not self.reason:
            current = self._snapshot()
            for path, signature in sorted(current.items()):
                if self._baseline.get(path) != signature:
                    kind = 'desync' if Path(path).name.casefold().startswith('sync') else 'crash'
                    self.reason = f'Fresh engine {kind} diagnostic detected: {Path(path).name}'
                    break
        return self.reason
