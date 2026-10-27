"""Installed 1v1 missions and verified native results for progression pools."""

from copy import deepcopy
import hashlib
import os
from pathlib import Path
import re

from randomizer.skirmish import GAME, discover_maps, playable_countries


def mission_catalogue(root):
    """Stable IDs preserve saved nodes/offers independently of the checkbox."""
    result = []
    countries = playable_countries()
    for relative, definition in discover_maps(root).items():
        for label, country in countries.items():
            if GAME == 'dta':
                faction = country
            elif GAME == 'reloaded':
                faction = label
            else:
                from randomizer.challenges.catalogue import SIDE_COUNTRIES, SIDE_FAMILIES
                family = SIDE_FAMILIES[SIDE_COUNTRIES.index(country)]
                faction = dict(allies='Allies', soviets='Soviets', epsilon='Epsilon', foehn='Foehn')[family]
            code = 'SK_' + hashlib.sha256(f'{relative}|{country}'.encode()).hexdigest()[:16].upper()
            map_info = deepcopy(definition)
            map_info['path'] = relative
            result.append({
                'code': code, 'title': f'1v1 Skirmish: {definition["name"]} ({label})',
                'scenario': relative, 'side': faction, 'faction': faction,
                'campaign': 'Skirmish', 'skirmish': True,
                'skirmish_country': country, 'skirmish_map': map_info,
                'index': 6, 'mission_number': 6, 'objective_count': 0,
                'objectives': [], 'build_classification': 'base_build',
                'reward_class': 'act_1',
                'briefing': 'Defeat the single enemy AI. Normal run unlocks, buffs, rewards and failure rules apply.',
            })
    return result


def select_pool(missions, catalogue, *, enabled, factions=(), excluded=()):
    """Choose one fixed playable country per map, without duplicate map weight."""
    base = [mission for mission in missions if not mission.get('skirmish')]
    if not enabled:
        return base
    factions, excluded = set(factions), set(excluded)
    grouped = {}
    for mission in catalogue:
        if mission['code'] in excluded or (factions and mission['faction'] not in factions):
            continue
        grouped.setdefault(mission['scenario'], []).append(mission)
    for relative, variants in grouped.items():
        index = int(hashlib.sha256(relative.encode()).hexdigest()[:8], 16) % len(variants)
        base.append(variants[index])
    return base


class SkirmishResultWatch:
    """Read fresh native completion plus both complete 1v1 score records.

    Closing/restarting a game cannot award victory. DTA uses its existing
    directory-aware ScoreLog reader; RA2 profiles follow their current log.
    """
    def __init__(self, path):
        self.path = Path(path)
        self.result = None
        self.error = ''
        self._offset = 0
        self._identity = None
        self._anchor = b''
        self._tail = ''
        self._scenario = False
        self._completion = False
        self._quit = False
        self._pending = None
        self._scores = {}
        self._unarmed = False
        self._directory_log = None
        if GAME == 'dta':
            from randomizer.coop.victory import ScoreLog
            self._directory_log = ScoreLog(self.path)
        else:
            try:
                with self.path.open('rb') as handle:
                    stat = os.fstat(handle.fileno())
                    self._identity = (stat.st_dev, stat.st_ino)
                    self._offset = stat.st_size
                    handle.seek(max(0, self._offset - 64))
                    self._anchor = handle.read()
            except FileNotFoundError:
                pass
            except OSError as exc:
                self.error, self._unarmed = str(exc), True

    def _feed(self, text):
        lines = (self._tail + text).splitlines(keepends=True)
        self._tail = ''
        if lines and not lines[-1].endswith(('\n', '\r')):
            self._tail = lines.pop()[-65536:]
        for raw in lines:
            line = raw.rstrip('\r\n')
            if match := re.search(r'Reading scenario:\s*(\S+)', line, re.I):
                if self._scenario:
                    self.error = 'Skirmish restarted; this attempt cannot earn progression.'
                    self._unarmed = True
                self._scenario = match[1].replace('\\', '/').rsplit('/', 1)[-1].casefold() == 'spawnmap.ini'
                self._completion = False
                self._scores = {}
                continue
            if not self._scenario:
                continue
            if "quit, but didn't see completion" in line:
                self._quit = True
            if 'Sending game results.' in line:
                self._completion = bool(re.search(r'\bSawCompletion=1\b', line))
                self._scores = {}
                self._pending = None
                continue
            if match := re.fullmatch(r'(Commander|Computer): (Winner|Loser)', line):
                self._pending = match[1], match[2]
            elif self._pending and re.fullmatch(r'\s+Score\s*=\s*-?\d+', line):
                name, outcome = self._pending
                self._scores.setdefault(name, []).append(outcome)
                self._pending = None
                if self._completion and not self._quit and not self._unarmed:
                    if self._scores.get('Commander') == ['Loser']:
                        self.result = 'defeat'
                    elif self._scores == {'Commander': ['Winner'], 'Computer': ['Loser']}:
                        self.result = 'victory'

    def poll(self, *, final=False):
        if self.result or self._unarmed:
            return self.result
        try:
            if self._directory_log is not None:
                self._feed(self._directory_log.read_text(final=final))
            else:
                with self.path.open('rb') as handle:
                    stat = os.fstat(handle.fileno())
                    identity = (stat.st_dev, stat.st_ino)
                    replaced = identity != self._identity or stat.st_size < self._offset
                    if not replaced and self._offset:
                        handle.seek(max(0, self._offset - 64))
                        replaced = handle.read(min(self._offset, 64)) != self._anchor
                    if replaced:
                        self._offset, self._tail = 0, ''
                        # A replaced log after a started game is a restart, not a new attempt.
                        if self._scenario:
                            self._unarmed = True
                            self.error = 'Skirmish log replaced during this attempt.'
                            return None
                    handle.seek(self._offset)
                    while data := handle.read(262144):
                        self._feed(data.decode('latin-1'))
                    self._offset, self._identity = handle.tell(), identity
                    handle.seek(max(0, self._offset - 64))
                    self._anchor = handle.read(min(self._offset, 64))
        except OSError as exc:
            self.error = str(exc)
        return self.result
