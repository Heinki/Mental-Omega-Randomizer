"""Conquest-native score receipts tied to a unique emitted attempt marker."""

import re
import os
import csv
import io
import subprocess
from pathlib import Path
from .score_log import ScoreLog, debug_logs
from .engine import marker
from .teams import participants


def native_game_running(root, *, any_installation=False):
    """Do not recover or replace a map while an orphaned native game is alive."""
    if os.name == 'nt':
        output = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq gamemd.exe', '/FO', 'CSV', '/NH'],
            capture_output=True, text=True, check=True,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return any(row and row[0].casefold() == 'gamemd.exe' for row in csv.reader(io.StringIO(output.stdout)))
    root = Path(root).resolve()
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            arguments = (entry / 'cmdline').read_bytes().decode(errors='replace').lower().split('\0')
            executables = [arg.replace('\\', '/').rsplit('/', 1)[-1] for arg in arguments[:2]]
            if 'gamemd.exe' in executables and (any_installation or (entry / 'cwd').resolve() == root):
                return True
        except (OSError, RuntimeError):
            continue
    return False


class ResultReader:
    def __init__(self, attempt_id, battle=None):
        self.marker = marker(attempt_id)
        self.started = False
        self.result = None
        self.error = ''
        self.scores = {}
        self.pending = None
        self.tail = ''
        self.closed = False
        self.in_scores = False
        # Old two-house attempts retain their original receipt format. New
        # battles identify AI teammates by their unique native color scheme;
        # all of them have the same native display name, "Computer".
        self.members = participants(battle) if battle and 'participants' in battle else None
        self.player_team = next((m['team'] for m in self.members or [] if m['controller'] == 'human'), None)

    def _score(self, record):
        if self.members is None:
            key = record['name']
            if key not in ('Commander', 'Computer'):
                return
        else:
            member = next((m for m in self.members if m['scheme'] == record.get('Scheme') and
                record['name'] == (m.get('name', 'Commander') if m['controller'] == 'human' else 'Computer')), None)
            if member is None:
                return
            key = member['slot']
        if key in self.scores:
            self.error = 'Duplicate native Conquest score record.'
            self.closed = True
            return
        self.scores[key] = record['outcome']
        if self.members is None:
            if self.scores == {'Commander': 'Winner', 'Computer': 'Loser'}:
                self.result = 'victory'
            elif self.scores == {'Commander': 'Loser', 'Computer': 'Winner'}:
                self.result = 'defeat'
            elif len(self.scores) == 2:
                self.error = 'Native Conquest scores disagree; battle remains unresolved.'
                self.closed = True
            return
        if len(self.scores) != len(self.members):
            return
        # An eliminated commander can still win through a surviving teammate.
        # Require the final score record for every committed participant.
        winners = {m['team'] for m in self.members if self.scores[m['slot']] == 'Winner'}
        if len(winners) == 1:
            self.result = 'victory' if self.player_team in winners else 'defeat'
        else:
            self.error = 'No unambiguous winning Conquest coalition; battle remains unresolved.'
            self.closed = True

    def feed(self, text):
        lines = (self.tail + text).splitlines(keepends=True)
        self.tail = ''
        if lines and not lines[-1].endswith(('\n', '\r')):
            self.tail = lines.pop()[-65536:]
        for raw in lines:
            line = raw.strip()
            if self.result or self.closed:
                continue
            if re.search(r'Reading scenario:', line, re.I) and self.started:
                self.error = 'Another scenario started before a complete Conquest result.'
                self.closed = True
                continue
            if "Creating a new team named '" + self.marker + "'" in line:
                if self.started:
                    self.error = 'Conquest battle was restarted; this attempt remains unresolved.'
                    self.closed = True
                self.started = True
                continue
            if not self.started:
                continue
            if "quit, but didn't see completion" in line:
                self.closed = True
                continue
            if 'Sending game results.' in line:
                self.in_scores = True
                if re.search(r'SawCompletion=0(?:\D|$)', line):
                    self.closed = True
                continue
            if not self.in_scores:
                continue
            match = re.fullmatch(r'([^:]+): (Winner|Loser|Losser)', line)
            if match:
                self.pending = dict(name=match[1], outcome='Loser' if match[2] == 'Losser' else match[2])
            elif self.pending:
                field = re.fullmatch(r'(Scheme|Score)\s*(?:=|:)\s*(-?\d+)', line)
                if field:
                    self.pending[field[1]] = int(field[2])
                    if field[1] == 'Score':
                        self._score(self.pending)
                        self.pending = None


class ResultWatch(ResultReader):
    def __init__(self, directory, attempt_id, battle=None):
        super().__init__(attempt_id, battle)
        self.log = ScoreLog(directory)

    def poll(self, *, final=False):
        if not self.result:
            try:
                self.feed(self.log.read_text(final=final))
            except OSError as exc:
                self.error = str(exc)
        return self.result


def recover(directory, attempt_id, battle=None):
    """Scan saved native logs; no generic Winner record can resolve an attempt."""
    outcomes = set()
    for path in debug_logs(directory):
        reader = ResultReader(attempt_id, battle)
        with path.open('r', encoding='utf-8', errors='replace') as handle:
            while chunk := handle.read(262144):
                reader.feed(chunk)
        reader.feed('\n')
        if reader.result:
            outcomes.add(reader.result)
    if len(outcomes) > 1:
        raise ValueError('Conflicting logs for this Conquest battle. Preserve the save and logs for recovery.')
    return next(iter(outcomes), None)
