"""Fresh native map markers bound to exactly one Final Fortress run."""

import os
from pathlib import Path
import re

from .engine import marker_names


_CREATED = re.compile(r"Creating a new team named '([^']+)'\.")


class FinalFortressResultWatch:
    @property
    def ready_to_close(self):
        """The fresh result and complete friendly scores have all been parsed."""
        return (self.started and self.result in ('victory', 'defeat')
                and self._scores_read and self._performance_credited
                and self.caught_up and not self.error)

    def __init__(self, path, run_id, plan=None, *, from_start=False,
                 player_name='Commander', initial_transfers=None, coop_slot=None):
        self.path = Path(path)
        self.run_id = run_id
        self.markers = {name: event for event, name in marker_names(run_id, plan).items()}
        self.plan = plan
        self.player_name = player_name
        self.initial_transfers = ((plan or {}).get('initial_transfer_kills', 0)
                                  if initial_transfers is None else initial_transfers)
        self.coop_slot = coop_slot
        self.events = []
        self._in_scores = False
        self._local_record = False
        self._kills = None
        self._scores_read = False
        self._performance_credited = False
        self._score_record = None
        self._coalition_records = {}
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
                    self._score_record = None
                    self._coalition_records = {}
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
    def read_completed_log(cls, path, run_id, plan, **identity):
        """Replay real native evidence on a worker, requiring this run's START."""
        watch = cls(path, run_id, plan, from_start=True, **identity)
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
                result_row = re.fullmatch(r'([^:]+): (Winner|Loser)\s*', line)
                if (self.plan or {}).get('coalition_scores'):
                    self._read_coalition_score(line, result_row)
                elif result_row:
                    self._local_record = result_row.group(1) == self.player_name
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
                                     and ((f'camp_pick:{self.coop_slot}:' if self.coop_slot is not None
                                           else 'camp:') + camp['id']) in self.events)
                combat_kills = (self._kills if (self.plan or {}).get('coalition_scores') else
                                max(0, self._kills - self.initial_transfers - cash_transfers))
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
            elif self.started and not self.result and event and event.startswith(
                    ('milestone:', 'camp:', 'camp_clear:', 'camp_pick:')):
                if event not in self.events:
                    self.events.append(event)

    def _read_coalition_score(self, line, result_row):
        """Read every friendly house once; enemies never contribute currency."""
        if result_row:
            self._score_record = {'name': result_row.group(1)}
            return
        if self._score_record is None:
            return
        field = re.fullmatch(r'\s+(Scheme|Kills|Score)(?: =|:) (-?\d+)\s*', line)
        if not field:
            return
        key, value = field.groups()
        self._score_record[key] = int(value)
        if key != 'Score':
            return
        record, self._score_record = self._score_record, None
        for actor in self.plan['coalition_scores']:
            if (record.get('Scheme') == actor['scheme'] and 'Kills' in record
                    and (actor['name'] is None or record['name'] == actor['name'])):
                self._coalition_records.setdefault(actor['actor'], record['Kills'])
        if len(self._coalition_records) != len(self.plan['coalition_scores']):
            return
        self._kills = 0
        for actor in self.plan['coalition_scores']:
            # Cash escrow ownership is another setup transfer, credited only
            # to its actual collector. AI helpers cannot collect these gifts.
            cash = sum(1 for camp in self.plan['map']['camps']
                       if actor['name'] is not None and camp.get('crate_reward', {}).get('credits')
                       and ((f'camp_pick:{actor["camp_slot"]}:' if self.plan.get('coop_players')
                             else 'camp:') + camp['id']) in self.events)
            self._kills += max(0, self._coalition_records[actor['actor']]
                               - actor['initial_transfers'] - cash)
        self._scores_read = True
