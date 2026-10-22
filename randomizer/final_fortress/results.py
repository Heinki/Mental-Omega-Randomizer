"""Fresh native map markers bound to exactly one Final Fortress run."""

import os
from pathlib import Path
import re

from .engine import marker_names


_CREATED = re.compile(r"Creating a new team named '([^']+)'\.")


class FinalFortressResultWatch:
    def __init__(self, path, run_id, plan=None, *, from_start=False):
        self.path = Path(path)
        self.run_id = run_id
        self.markers = {name: event for event, name in marker_names(run_id, plan).items()}
        self.plan = plan
        self.events = []
        self._in_scores = False
        self._local_record = False
        self._kills = None
        self._scores_read = False
        self._performance_credited = False
        self.result = None
        self.error = ''
        self.started = False
        self.waves = []
        self._remainder = ''
        self._offset = 0
        self._identity = None
        self._anchor = b''
        self.caught_up = False
        try:
            with self.path.open('rb') as handle:
                stat = os.fstat(handle.fileno())
                self._identity = (stat.st_dev, stat.st_ino)
                self._offset = 0 if from_start else stat.st_size
                handle.seek(max(0, self._offset - 64))
                self._anchor = handle.read(min(64, self._offset))
                self.caught_up = self._offset == stat.st_size
        except FileNotFoundError:
            pass

    def poll(self):
        try:
            with self.path.open('rb') as handle:
                stat = os.fstat(handle.fileno())
                identity = (stat.st_dev, stat.st_ino)
                changed = identity != self._identity or stat.st_size < self._offset
                if not changed and self._offset:
                    start = max(0, self._offset - 64)
                    handle.seek(start)
                    changed = handle.read(self._offset - start) != self._anchor
                if changed:
                    self._offset = 0
                    self._remainder = ''
                    self.started = False
                    self._in_scores = False
                    self._local_record = False
                    self._kills = None
                    self._scores_read = False
                    self._performance_credited = False
                handle.seek(self._offset)
                # Bound Tk-thread work even when native logging grows quickly.
                if data := handle.read(262_144):
                    self._feed(data.decode('latin-1'))
                self._offset = handle.tell()
                handle.seek(max(0, self._offset - 64))
                # Only checkpoint the bytes immediately BEFORE our cursor.
                # Reading the unread tail here makes the next 64-byte check
                # report a false replacement whenever a backlog exists.
                self._anchor = handle.read(min(64, self._offset))
                self._identity = identity
                self.caught_up = self._offset >= os.fstat(handle.fileno()).st_size
            self.error = ''
        except FileNotFoundError:
            self.caught_up = True
        except OSError as exc:
            self.error = str(exc)
            self.caught_up = True
        return self.result

    @classmethod
    def read_completed_log(cls, path, run_id, plan):
        """Replay real native evidence on a worker, requiring this run's START."""
        watch = cls(path, run_id, plan, from_start=True)
        while not watch.caught_up:
            watch.poll()
            if watch.error:
                raise OSError(watch.error)
        return watch

    def _feed(self, text):
        lines = (self._remainder + text).splitlines(keepends=True)
        self._remainder = ''
        if lines and not lines[-1].endswith(('\r', '\n')):
            self._remainder = lines.pop()[-65536:]
        for line in lines:
            if not self._in_scores and 'MFF_' not in line and 'Sending game results.' not in line:
                continue
            if self.started and 'Sending game results.' in line:
                self._in_scores = True
                self._local_record = False
            if self._in_scores and not self._scores_read:
                if re.fullmatch(r'Commander: (Winner|Loser)\s*', line):
                    self._local_record = True
                elif self._local_record:
                    kills = re.fullmatch(r'\s+Kills = (\d+)\s*', line)
                    if kills:
                        self._kills = int(kills.group(1))
                    if re.fullmatch(r'\s+Score = -?\d+\s*', line):
                        self._scores_read = True
                        self._local_record = False
            if (self.result in ('victory', 'defeat') and self._scores_read
                    and self._kills is not None and not self._performance_credited):
                self._performance_credited = True
                cash_transfers = sum(1 for camp in (self.plan or {}).get('map', {}).get('camps', [])
                                     if camp.get('crate_reward', {}).get('credits')
                                     and 'camp:' + camp['id'] in self.events)
                combat_kills = max(0, self._kills - (self.plan or {}).get('initial_transfer_kills', 0)
                                   - cash_transfers)
                for event in (self.plan or {}).get('gem_rewards', {}):
                    if event.startswith('kills:') and combat_kills >= int(event.split(':')[1]):
                        if event not in self.events:
                            self.events.append(event)
            match = _CREATED.search(line)
            event = self.markers.get(match.group(1)) if match else None
            if event == 'started':
                # Restarting the same map must never mint another result.
                if self.started:
                    self.result = 'abandoned'
                self.started = True
            elif self.started and not self.result and event in ('victory', 'defeat'):
                self.result = event
            elif self.started and not self.result and event and event.startswith('wave:'):
                wave = int(event.split(':')[1])
                if wave not in self.waves:
                    self.waves.append(wave)
            elif self.started and not self.result and event and event.startswith(('milestone:', 'camp:', 'camp_clear:')):
                if event not in self.events:
                    self.events.append(event)
