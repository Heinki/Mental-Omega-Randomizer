"""Locked, durable campaign transactions with frozen battle attempts."""

from contextlib import contextmanager
from collections import Counter
from copy import deepcopy
from pathlib import Path
import os
import re

from randomizer.core.paths import APP_DIR
from randomizer.core.storage import atomic_write_json, read_json_object
from .catalogue import (FACTIONS, DIFFICULTIES, STATS, PERKS, RULES_VERSION,
                        MAX_STRENGTH, MAX_REPAIR_KITS, combat_power, starting_force,
                        MAX_ARMIES_PER_NODE, MAX_RESEARCH_RANK)
from .campaign import record, resolve, allied, armies_at
from .teams import validate_teams
from .players import human_ids, human, country, roster, validate_roster


class PersistenceError(RuntimeError):
    pass


def _integer(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def _id(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{32}', value) is not None


def _inventory(values, *, local):
    return isinstance(values, dict) and all(k in PERKS and PERKS[k]['local'] == local and
        _integer(v, 1, PERKS[k]['maximum']) for k, v in values.items())


def _map(value):
    return (isinstance(value, dict) and isinstance(value.get('path'), str) and
        isinstance(value.get('name'), str) and isinstance(value.get('sha256'), str) and
        re.fullmatch('[0-9a-f]{64}', value['sha256']) is not None and
        isinstance(value.get('starts'), list) and 2 <= len(value['starts']) <= 8 and
        len(set(value['starts'])) == len(value['starts']) and
        all(_integer(v, 0, 7) for v in value['starts']) and
        isinstance(value.get('countries'), list) and
        all(c in FACTIONS for c in value['countries']) and
        ('positions' not in value or isinstance(value['positions'], dict) and
         set(value['positions']) == {str(w) for w in value['starts']} and
         all(isinstance(p, list) and len(p) == 2 and all(_integer(v, 0, 511) for v in p)
             for p in value['positions'].values())))


def _validate_loadout(state, loadout, actor):
    version = state['pending'].get('team_version', 1)
    count = loadout.get('army_count', 1) if version >= 4 else 1
    multiplier = loadout.get('defense_multiplier', 1) if version >= 4 else 1
    if not _integer(count, 1, MAX_ARMIES_PER_NODE) or not _integer(multiplier, 1, MAX_ARMIES_PER_NODE):
        raise ValueError('Invalid defending army stack.')
    sizing = dict(balance_version=version, army_count=count, defense_multiplier=multiplier)
    if (loadout['faction'] != actor or loadout['country'] != country(state, actor) or
        not _integer(loadout['strength'], 1, MAX_STRENGTH * count) or
        set(loadout['stats']) != set(STATS) or
        any(not _integer(v, 0, 120 if k == 'damage' else 100) for k, v in loadout['stats'].items()) or
        any(k not in PERKS or not _integer(v, 1, PERKS[k]['maximum']) for k, v in loadout['perks'].items()) or
        type(loadout.get('headquarters', False)) is not bool or
        type(loadout.get('field_repairs', False)) is not bool or
        loadout['force'] != starting_force(loadout['country'], loadout['strength'], loadout['perks'],
                                          headquarters=loadout.get('headquarters', False),
                                          legacy_aircraft=version < 3, **sizing) or
        loadout['power'] != combat_power(loadout['strength'], loadout['stats'], loadout['perks'],
                                        headquarters=loadout.get('headquarters', False),
                                        field_repairs=loadout.get('field_repairs', False), **sizing)):
        raise ValueError('Invalid frozen Conquest loadout.')


def validate(state):
    """Reject corrupt saves before any purchase, native launch, or recovery."""
    try:
        if 'coop' in state:
            co = state['coop']
            validate_roster(co['players'])
            if (co['version'] != 1 or type(co['shared_nodes']) is not bool or
                set(co['gifts']) != set(human_ids(state)) or
                any(not _integer(v, 0, state['turn']) for v in co['gifts'].values()) or
                co['players'][0]['country'] != state['settings']['player_country']):
                raise ValueError('Invalid cooperative campaign settings.')
        humans = human_ids(state)
        actors = (*humans, 'ai')
        if (state['schema'] != 1 or state['rules_version'] != RULES_VERSION or state['game'] != 'mo' or
            not _id(state['id']) or not _integer(state['revision'], 0, 2**63 - 1) or
            not _integer(state['turn'], 1, 1000000) or not _integer(state['random'], 1, 2**32 - 1) or
            state['phase'] not in (*actors, 'battle', 'finished')):
            raise ValueError('Unsupported or invalid Conquest save.')
        settings = state['settings']
        count = settings['size']
        if (count not in (9, 25, 64, 100) or settings['player_country'] not in FACTIONS or
            settings['ai_country'] not in FACTIONS or settings['difficulty'] not in DIFFICULTIES or
            not isinstance(settings['seed'], str) or not 1 <= len(settings['seed']) <= 80 or
            not _integer(settings['density'], 0, 2) or not _integer(settings['credits'], 100, 10000)):
            raise ValueError('Invalid Conquest campaign settings.')
        nodes, edges, armies = state['nodes'], state['edges'], state['armies']
        if len(nodes) != count or [n['id'] for n in nodes] != list(range(count)):
            raise ValueError('Invalid Conquest territories.')
        for node in nodes:
            if (node['owner'] not in (*actors, 'neutral') or
                node.get('hq') not in (None, *actors) or
                any(type(node[k]) not in (int, float) or not -100 <= node[k] <= 2000 for k in ('x', 'y')) or
                not _integer(node['income'], 0, 1000) or
                not isinstance(node['buffs'], dict) or
                any(k not in STATS or not _integer(v, 0, 100) for k, v in node['buffs'].items()) or
                not _inventory(node['perks'], local=True) or not _map(node['map']) or
                any(c not in node['map']['countries'] for c in (*[p['country'] for p in roster(state)], settings['ai_country'])) or
                len(node['map']['starts']) < len(humans) + 1 or
                not _integer(node.get('gifted_round', 0), 0, state['turn']) or
                not _integer(node.get('income_after', 0), 0, state['turn'] + 1) or
                node['reward'] is not None and (node['reward'] not in PERKS or PERKS[node['reward']]['local']) or
                not isinstance(node['claimed'], list) or len(set(node['claimed'])) != len(node['claimed']) or
                any(v not in actors for v in node['claimed'])):
                raise ValueError('Invalid Conquest territory data.')
        headquarters = [n['hq'] for n in nodes if n.get('hq')]
        if len(headquarters) != len(set(headquarters)):
            raise ValueError('A Conquest commander cannot have multiple headquarters.')
        if (not edges or any(len(e) != 2 or not all(_integer(v, 0, count - 1) for v in e) or e[0] >= e[1] for e in edges)
            or len({tuple(e) for e in edges}) != len(edges)):
            raise ValueError('Invalid Conquest routes.')
        reached, pending = set(), [0]
        while pending:
            index = pending.pop()
            if index in reached:
                continue
            reached.add(index)
            pending.extend(b if a == index else a for a, b in edges if a == index or b == index)
        if len(reached) != count:
            raise ValueError('Conquest routes are disconnected.')
        if not _integer(state['next_army'], 3, 2**63 - 1):
            raise ValueError('Invalid Conquest army counter.')
        if (len({a['id'] for a in armies}) != len(armies) or
            any(count > MAX_ARMIES_PER_NODE for count in Counter(a['node'] for a in armies).values()) or
            any(not _integer(a['id'], 1, state['next_army'] - 1) or
                not _integer(a['node'], 0, count - 1) or not _integer(a['strength'], 1, MAX_STRENGTH) or
                type(a['acted']) is not bool or a['faction'] not in actors or
                not allied(state, nodes[a['node']]['owner'], a['faction']) for a in armies)):
            raise ValueError('Invalid Conquest armies.')
        for side in actors:
            wallet = state[side]
            if (not _integer(wallet['credits'], 0, 100000000) or not _integer(wallet['supplies'], 0, 3) or
                not _integer(wallet.get('repair_kits', 0), 0, MAX_REPAIR_KITS) or
                type(wallet.get('repairs_armed', False)) is not bool or
                wallet.get('repairs_armed', False) and not wallet.get('repair_kits', 0) or
                set(wallet['research']) != set(STATS) or
                not all(_integer(v, 0, MAX_RESEARCH_RANK) for v in wallet['research'].values()) or
                not _integer(wallet.get('upgrades_bought', 0), 0, 1000000) or
                not _inventory(wallet['perks'], local=False)):
                raise ValueError('Invalid Conquest economy.')
        if type(state['ai_purchase']) is not bool or not _integer(state['ai_recruits'], 0, 3):
            raise ValueError('Invalid Conquest AI continuation.')
        if ((state['phase'] == 'finished') != (state['winner'] is not None) or
            state['winner'] not in (None, 'player', 'ai')):
            raise ValueError('Invalid Conquest outcome.')
        if state['winner'] and any(n['owner'] not in ((*humans, 'neutral') if state['winner'] == 'player' else ('ai', 'neutral')) for n in nodes):
            raise ValueError('Conquest victory still has opposing territories.')
        history = state['history']
        if (not _integer(state['next_event'], 1, 2**63 - 1) or
            state['next_event'] != len(history) + 1 or
            any(e['id'] != i for i, e in enumerate(history, 1)) or
            any(not isinstance(e['text'], str) or len(e['text']) > 2000 or
                e['faction'] not in (*actors, 'neutral') or
                not _integer(e['turn'], 1, state['turn']) or
                e['node'] is not None and not _integer(e['node'], 0, count - 1) for e in history)):
            raise ValueError('Invalid Conquest history.')
        battle = state['pending']
        if (state['phase'] == 'battle') != (battle is not None):
            raise ValueError('Invalid pending Conquest battle.')
        if battle:
            army = next((a for a in armies if a['id'] == battle['army']), None)
            if (not _id(battle['id']) or battle['rules_version'] != RULES_VERSION or
                battle['attacker'] not in actors or not army or not army['acted'] or
                army['node'] != battle['source'] or army['faction'] != battle['attacker'] or
                not _integer(battle['target'], 0, count - 1) or
                sorted((battle['source'], battle['target'])) not in edges or
                allied(state, nodes[battle['target']]['owner'], battle['attacker']) or
                not _map(battle['map']) or battle['map'] != nodes[battle['target']]['map'] or
                len(battle['starts']) != 2 or battle['starts'][0] == battle['starts'][1] or
                any(s not in battle['map']['starts'] for s in battle['starts']) or
                not _integer(battle['seed'], 1, 2**31 - 1) or battle['difficulty'] not in DIFFICULTIES):
                raise ValueError('Invalid committed Conquest battle.')
            if battle.get('team_version', 1) >= 4:
                defenders = armies_at(state, battle['target'])
                own = [a for a in defenders if a['faction'] == nodes[battle['target']]['owner']]
                defense, attack = battle['defense'], battle['attack']
                if (battle.get('defending_armies') != [a['id'] for a in defenders] or
                    defense.get('army_count') != max(1, len(own)) or
                    defense.get('defense_multiplier') != max(1, len(defenders)) or
                    defense['strength'] != (sum(a['strength'] for a in own) or 2) or
                    attack.get('army_count') != 1 or attack.get('defense_multiplier') != 1 or
                    attack['strength'] != army['strength']):
                    raise ValueError('Frozen battle differs from its stationed armies.')
            for key in ('attack', 'defense'):
                expected = battle['attacker'] if key == 'attack' else nodes[battle['target']]['owner']
                _validate_loadout(state, battle[key], expected)
                if battle[key].get('headquarters') and (key != 'defense' or nodes[battle['target']].get('hq') != expected):
                    raise ValueError('Invalid headquarters defense bonus.')
            human_battle = human(state, battle['attacker']) or human(state, battle['defense']['faction'])
            if state.get('coop') and human_battle:
                team = 'attack' if human(state, battle['attacker']) else 'defense'
                if (battle.get('human_team') != team or battle.get('decision_actor') != battle[team]['faction'] or
                    not isinstance(battle.get('human_loadouts'), list) or
                    [e['player'] for e in battle['human_loadouts']] != roster(state)):
                    raise ValueError('Invalid cooperative battle roster.')
                for entry in battle['human_loadouts']:
                    actor = entry['player']['id']
                    _validate_loadout(state, entry['loadout'], actor)
                    if entry['loadout'].get('headquarters') and (team != 'defense' or actor != battle[team]['faction']):
                        raise ValueError('HQ guards belong only to the defending commander.')
                    if actor == battle[team]['faction'] and entry['loadout'] != battle[team]:
                        raise ValueError('Commander loadout differs from the committed battle.')
                    if battle.get('team_version', 1) >= 4 and actor != battle[team]['faction']:
                        stationed = [a for a in armies_at(state, battle['target']) if a['faction'] == actor] if team == 'defense' else []
                        strength = sum(a['strength'] for a in stationed) if stationed else max(
                            (a['strength'] for a in armies if a['faction'] == actor), default=2)
                        if (entry['loadout'].get('army_count') != max(1, len(stationed)) or
                            entry['loadout'].get('defense_multiplier') != 1 or entry['loadout']['strength'] != strength):
                            raise ValueError('Teammate loadout differs from its stationed armies.')
            elif 'human_loadouts' in battle or 'human_team' in battle:
                raise ValueError('Unexpected cooperative battle roster.')
            validate_teams(battle)
            attempt = battle['attempt']
            if attempt is not None and (not _id(attempt['id']) or attempt['status'] not in ('prepared', 'launched') or
                any(not isinstance(attempt[k], str) or not re.fullmatch('[0-9a-f]{64}', attempt[k])
                    for k in ('map_hash', 'spawn_hash'))):
                raise ValueError('Invalid Conquest launch attempt.')
        if any(not _id(a['id']) or not _id(a['battle']) or
               a['result'] not in ('victory', 'defeat', 'unresolved') for a in state['attempts']):
            raise ValueError('Invalid Conquest battle receipts.')
        if len({a['id'] for a in state['attempts']}) != len(state['attempts']):
            raise ValueError('Duplicate Conquest battle receipts.')
    except (KeyError, TypeError, IndexError, AttributeError) as exc:
        raise ValueError('Malformed Conquest save; preserve the file and restore its backup.') from exc
    return state


class Repository:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else APP_DIR / 'conquest_state.json'

    @contextmanager
    def _lock(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.with_suffix('.lock').open('a+b') as handle:
            if os.name == 'nt':
                import msvcrt
                if handle.seek(0, os.SEEK_END) == 0:
                    handle.write(b'\0')
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                if os.name == 'nt':
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

    def _read(self):
        if not self.path.exists():
            return None
        state = validate(read_json_object(self.path))
        # Original launch saves identify starting nodes in their first history
        # entries. Preserve any already committed battle's original loadouts.
        for actor in (*human_ids(state), 'ai'):
            if not any(n.get('hq') == actor for n in state['nodes']):
                event = next((e for e in state['history'] if e['faction'] == actor and
                              e['text'].startswith('Campaign started with ') and e['node'] is not None), None)
                if event:
                    state['nodes'][event['node']]['hq'] = actor
        return state

    def load(self):
        try:
            with self._lock():
                return self._read()
        except (OSError, ValueError) as exc:
            raise PersistenceError(f'Cannot read Conquest: {exc}') from exc

    def _write(self, state, old):
        validate(state)
        if old is not None:
            atomic_write_json(self.path.with_suffix('.json.bak'), old, durable=True)
        atomic_write_json(self.path, state, durable=True)

    def create(self, state, expected=None):
        try:
            with self._lock():
                old = self._read()
                if ((old['id'], old['revision']) if old else None) != expected:
                    raise ValueError('The campaign changed in another launcher. Reload before replacing it.')
                self._write(state, old)
                return deepcopy(state)
        except (OSError, ValueError) as exc:
            raise PersistenceError(f'Cannot save Conquest: {exc}') from exc

    def mirror(self, snapshot):
        """Persist an authenticated host snapshot in a separate guest repository."""
        try:
            with self._lock():
                validate(snapshot)
                old = self._read()
                if old and old['id'] == snapshot['id'] and old['revision'] > snapshot['revision']:
                    raise ValueError('Host snapshot is older than the saved campaign.')
                self._write(snapshot, old)
                return deepcopy(snapshot)
        except OSError as exc:
            raise PersistenceError(f'Cannot save cooperative campaign snapshot: {exc}') from exc

    def update(self, campaign_id, revision, operation):
        try:
            with self._lock():
                try:
                    old = self._read()
                except ValueError as exc:
                    raise PersistenceError(f'Cannot read Conquest: {exc}') from exc
                if old is None or old['id'] != campaign_id or old['revision'] != revision:
                    raise PersistenceError('The campaign changed in another launcher. Retry loading the campaign before continuing.')
                state = deepcopy(old)
                result = operation(state)
                if state != old:
                    state['revision'] += 1
                    self._write(state, old)
                return state, result
        except OSError as exc:
            raise PersistenceError(f'Conquest save failed. No action was committed: {exc}') from exc


def commit_attempt(state, battle_id, attempt_id, map_hash, spawn_hash):
    battle = state['pending']
    if not battle or battle['id'] != battle_id or battle['attempt']:
        raise ValueError('This battle is no longer available for launch.')
    battle['attempt'] = dict(id=attempt_id, status='prepared', map_hash=map_hash, spawn_hash=spawn_hash)


def mark_launched(state, attempt_id):
    battle = state['pending']
    if not battle or not battle['attempt'] or battle['attempt']['id'] != attempt_id:
        raise ValueError('The prepared Conquest battle changed.')
    battle['attempt']['status'] = 'launched'
    record(state, 'Real battle launched. Committed supplies and perks are frozen.', 'player', battle['target'])


def finish_attempt(state, attempt_id, outcome):
    battle = state['pending']
    if not battle or not battle['attempt'] or battle['attempt']['id'] != attempt_id:
        return False
    state['attempts'].append(dict(id=attempt_id, battle=battle['id'], result=outcome or 'unresolved'))
    battle['attempt'] = None
    if outcome in ('victory', 'defeat'):
        return resolve(state, battle['id'], (outcome == 'victory') == human(state, battle['attacker']), method='Real battle')
    record(state, 'No verified result. Battle remains pending; retry or autobattle with the same committed bonuses.', 'player', battle['target'])
    return True
