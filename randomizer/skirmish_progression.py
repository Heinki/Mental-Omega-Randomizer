"""Installed 1v1 missions and verified native results for progression pools."""

from copy import deepcopy
import hashlib
import os
from pathlib import Path
import re

from randomizer.skirmish import GAME, discover_maps, playable_countries


def _mission_code(relative, country):
    return 'SK_' + hashlib.sha256(f'{relative}|{country}'.encode()).hexdigest()[:16].upper()


def mission_for_country(mission, country):
    """Materialize only a selected or saved country, keeping its original ID."""
    from randomizer.skirmish_factions import mission_countries, faction_for_country
    countries = mission_countries(mission)
    label = next(label for label, native in countries.items() if native == country)
    faction = faction_for_country(country)
    return dict(mission, code=_mission_code(mission['scenario'], country),
                skirmish_country=country, side=faction, faction=faction,
                title=f'1v1 Skirmish: {mission["skirmish_map"]["name"]} ({label})')


def mission_catalogue(root, *, codes=None):
    """One entry per installed map; the faction picker supplies other countries."""
    result = []
    countries = playable_countries()
    wanted = None if codes is None else set(codes)
    if wanted == set():
        return result
    accept_path = None if wanted is None else lambda relative: any(
        _mission_code(relative, country) in wanted for country in countries.values())
    for relative, definition in discover_maps(root, accept_path=accept_path, allow_legacy=wanted is not None).items():
        country = next((country for country in countries.values()
                        if country in definition['countries']), None)
        if country is None:
            continue
        map_info = deepcopy(definition)
        map_info['path'] = relative
        mission = dict(scenario=relative, campaign='Skirmish', skirmish=True,
                       skirmish_map=map_info, skirmish_eligible=definition.get('progression_eligible', True), index=6, mission_number=6,
                       objective_count=0, objectives=[], build_classification='base_build',
                       reward_class='act_1',
                       briefing='Defeat the single enemy AI. Normal run unlocks, buffs, rewards and failure rules apply.')
        result.append(mission_for_country(mission, country))
    return result


def referenced_missions(catalogue, codes):
    """Recover exact saved IDs without expanding every map into every faction."""
    from randomizer.skirmish_factions import mission_countries
    codes = set(codes)
    result = []
    for mission in catalogue:
        saved = [mission_for_country(mission, country)
                 for country in mission_countries(mission).values()
                 if _mission_code(mission['scenario'], country) in codes]
        result.extend(saved)
    return result


def restore_saved_maps(root, catalogue, codes):
    """Keep legacy map IDs resolvable without offering them in new pools."""
    missing = set(codes) - {mission['code'] for mission in referenced_missions(catalogue, codes)}
    if not missing:
        return catalogue
    scenarios = {mission['scenario'] for mission in catalogue}
    return list(catalogue) + [mission for mission in mission_catalogue(root, codes=missing)
                              if mission['scenario'] not in scenarios]


def normalize_exclusions(catalogue, excluded):
    """An exclusion represents a map, including old country-specific IDs."""
    from randomizer.skirmish_factions import mission_countries
    aliases = {_mission_code(mission['scenario'], country): mission['code']
               for mission in catalogue for country in mission_countries(mission).values()}
    return {aliases.get(code, code) for code in excluded}


def select_pool(missions, catalogue, *, enabled, factions=(), excluded=()):
    """Select one playable country per map, retaining saved country-specific IDs."""
    from randomizer.skirmish_factions import mission_countries, faction_for_country
    base = [mission for mission in missions if not mission.get('skirmish')]
    if not enabled:
        return base
    factions, excluded, seen = set(factions), set(excluded), set()
    for mission in catalogue:
        if not mission.get('skirmish_eligible', True):
            continue
        relative = mission['scenario']
        if relative in seen or (GAME == 'mo' and Path(relative).stem.casefold() == 'l_levelgrounddancing'):
            continue
        seen.add(relative)
        countries = list(mission_countries(mission).values())
        if mission['code'] in excluded or any(_mission_code(relative, country) in excluded for country in countries):
            continue
        countries = [country for country in countries
                     if not factions or faction_for_country(country) in factions]
        if countries:
            index = int(hashlib.sha256(relative.encode()).hexdigest()[:8], 16) % len(countries)
            base.append(mission_for_country(mission, countries[index]))
    return base


class SkirmishResultWatch:
    """Read both fresh, complete native 1v1 score records.

    Closing/restarting a game cannot award victory. DTA uses its existing
    directory-aware ScoreLog reader. RA2 can collect
    scores without sending network statistics, and its AI name is localized.
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
        self._scores = []
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
                self._scores = []
                self._pending = None
                continue
            if not self._scenario:
                continue
            if "quit, but didn't see completion" in line and len(self._scores) < 2:
                self._quit = True
            if 'Sending game results.' in line:
                self._completion = bool(re.search(r'\bSawCompletion=1\b', line))
                # Score collection and network-statistics delivery are
                # separate engine paths. Either can be logged first.
                continue
            if match := re.fullmatch(r'(.+): (Winner|Loser)\s*', line):
                self._pending = match[1], match[2]
            elif self._pending and re.fullmatch(r'\s+Score\s*=\s*-?\d+\s*', line):
                self._scores.append(self._pending)
                self._pending = None

    def _resolve(self, final):
        if not self._scenario or self._quit or self._unarmed:
            return
        if GAME != 'dta' and not final:
            return
        local = [outcome for name, outcome in self._scores if name == 'Commander']
        enemy = [outcome for name, outcome in self._scores if name != 'Commander']
        if len(self._scores) == 2 and local == ['Winner'] and enemy == ['Loser']:
            self.result = 'victory'
        elif len(self._scores) == 2 and local == ['Loser'] and enemy == ['Winner']:
            self.result = 'defeat'

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
            if not self._unarmed:
                self.error = ''
        except OSError as exc:
            self.error = str(exc)
        if final and self._tail:
            self._feed('\n')
        self._resolve(final)
        if final and not self.result and not self.error:
            self.error = (
                'No verified Skirmish result: '
                f'scenario={self._scenario}, completion={self._completion}, '
                f'quit={self._quit}, scores={self._scores!r}'
            )
        return self.result
