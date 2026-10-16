"""Conservative, fresh-session challenge results from the native debug log.

The engine can print ``Name: Winner`` when an unfinished game is closed: the
installed logs contain full all-Winner score tables with SawCompletion=0.
Therefore a local Winner alone is insufficient. Victory requires complete
human statistics and a Loser record for every registered enemy. Paired wins
also require native completion and a winning teammate, including when the
other human was defeated earlier.
"""

from __future__ import annotations

import os
from pathlib import Path
import re


_SCENARIO = re.compile(r'(?:Reading scenario:|----- Starting sc[en]*ario:)\s*(\S+)', re.I)
_RESULT = re.compile(r'([^\r\n:]+): (Winner|Loser)\s*\Z')
_SCORE = re.compile(r'\s+Score\s*=\s*-?\d+\s*\Z')
_RESULTS_START = 'Sending game results.'
_QUIT = "Sending game results because I quit, but didn't see completion"


class ChallengeResultParser:
    """Incremental native records scoped to a fresh, actually started map."""

    def __init__(self, local_name: str, enemy_count: int, *,
                 scenario: str = 'spawnmap.ini', expected_human_names=()):
        names = tuple(dict.fromkeys((local_name, *expected_human_names)))
        if any(not str(name).strip() or str(name).casefold() == 'computer' for name in names):
            raise ValueError('Challenge human names must be distinct from the Computer AI name.')
        if type(enemy_count) is not int or not 1 <= enemy_count <= 6:
            raise ValueError('Challenge result detection needs 1–6 registered enemies.')
        self.local_name = local_name
        self.enemy_count = enemy_count
        self.scenario = str(scenario).replace('\\', '/').rsplit('/', 1)[-1].casefold()
        self.expected_human_names = names
        self.result = None
        self.reset()

    def reset(self) -> None:
        """Discard partial records when a debug log is replaced or truncated."""
        self._remainder = ''
        self._scenario_seen = False
        self._game_started = False
        self._in_results = False
        self._saw_completion = False
        self._quit_without_completion = False
        self._records = []
        self._pending_record = None

    def feed(self, text: str) -> str | None:
        """Return an outcome at most once; partial lines never count as results."""
        if self.result is not None:
            return None
        text = self._remainder + text
        lines = text.splitlines(keepends=True)
        self._remainder = ''
        if lines and not lines[-1].endswith(('\n', '\r')):
            self._remainder = lines.pop()
            # A corrupt single line must not retain a growing log in memory.
            if len(self._remainder) > 65536:
                self._remainder = ''
        for line in lines:
            self._line(line.rstrip('\r\n'))
            if self.result is not None:
                return self.result
        return None

    def _line(self, line: str) -> None:
        scenario = _SCENARIO.search(line)
        if scenario:
            self._scenario_seen = (
                scenario.group(1).replace('\\', '/').rsplit('/', 1)[-1].casefold()
                == self.scenario
            )
            self._game_started = False
            self._in_results = False
            self._saw_completion = False
            self._quit_without_completion = False
            self._records = []
            self._pending_record = None
            return
        if self._scenario_seen and line.strip() == 'Capture_Mouse()':
            self._game_started = True
        if _QUIT in line:
            self._quit_without_completion = True
        if _RESULTS_START in line:
            self._in_results = self._scenario_seen and self._game_started
            self._saw_completion = bool(re.search(r'\bSawCompletion=1\b', line))
            self._records = []
            self._pending_record = None
            return
        if not self._in_results:
            return
        match = _RESULT.fullmatch(line)
        if match:
            self._pending_record = (match.group(1), match.group(2))
            return
        if self._pending_record and _SCORE.fullmatch(line):
            self._records.append(self._pending_record)
            self._pending_record = None
            self._resolve()

    def _resolve(self) -> None:
        humans = {name: [] for name in self.expected_human_names}
        enemies = []
        for name, result in self._records:
            if name in humans:
                humans[name].append(result)
            elif name == 'Computer':
                enemies.append(result)
        if len(humans) > 1:
            # One teammate may already be defeated when the remaining ally
            # wins. Wait for both humans and every authored enemy; resolving
            # the host's first Loser row would hide the later team victory.
            if (any(len(results) != 1 for results in humans.values())
                    or len(enemies) != self.enemy_count):
                return
            if (self._saw_completion and not self._quit_without_completion
                    and all(result == 'Loser' for result in enemies)
                    and any(results == ['Winner'] for results in humans.values())):
                self.result = 'victory'
            elif all(results == ['Loser'] for results in humans.values()):
                self.result = 'defeat'
            return
        # A solo local loss remains sufficient even if other result rows are
        # still being written. Unrelated AI losses never fail this run.
        if humans[self.local_name] == ['Loser']:
            self.result = 'defeat'
            return
        if (not self._quit_without_completion
                and all(results == ['Winner'] for results in humans.values())
                and len(enemies) == self.enemy_count
                and all(result == 'Loser' for result in enemies)):
            self.result = 'victory'


class ChallengeResultWatch:
    """Snapshot before spawning, then poll only newly written debug-log bytes."""

    def __init__(self, path: Path, local_name: str, enemy_count: int, *,
                 scenario: str = 'spawnmap.ini', expected_human_names=()):
        self.path = Path(path)
        self.parser = ChallengeResultParser(
            local_name, enemy_count, scenario=scenario,
            expected_human_names=expected_human_names,
        )
        self.error = ''
        self.result = None
        self._offset = 0
        self._file_id = None
        self._anchor = b''
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
            # A failed initial snapshot cannot distinguish old data. Do not
            # arm later and risk counting a previous session's score table.
            self.error = str(exc)
            self._unarmed = True

    def poll(self) -> str | None:
        """Return victory/defeat once; absence, crashes and exits return None."""
        if self.result is not None or getattr(self, '_unarmed', False):
            return None
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
                    self.parser.reset()
                handle.seek(offset)
                # Feed chunks so noisy debug logs do not require one large
                # allocation. Keep consuming the file after a result to save
                # a correct cursor; duplicate emission is already suppressed.
                detected = None
                while data := handle.read(1_048_576):
                    outcome = self.parser.feed(data.decode('latin-1'))
                    detected = detected or outcome
                self._offset = handle.tell()
                handle.seek(max(0, self._offset - 64))
                self._anchor = handle.read()
                self._file_id = identity
        except FileNotFoundError:
            return None
        except OSError as exc:
            self.error = str(exc)
            return None
        self.error = ''
        self.result = detected or self.parser.result
        return detected


ResultLogWatcher = ChallengeResultWatch
