"""Frozen battle participants, independent of campaign ownership and transport.

A participant identifies a controller, coalition, starting slot and loadout.
The native adapter binds up to four authenticated human controllers to seats
without changing personal ownership, purchase rules or coalition results.
"""

from copy import deepcopy

from .catalogue import LOCAL_PERKS, combat_power, starting_force

TEAM_VERSION = 4
ALLY_STRENGTH = 8
HOUSE_ALIASES = tuple(f'CQC{i}' for i in range(8))
COLOR_SCHEMES = (1, 3, 7, 9, 11, 13, 15, 17)


def _member(battle, team, role, waypoint, slot):
    loadout = deepcopy(battle[team])
    if role == 'ally':
        loadout['strength'] = ALLY_STRENGTH
        # Territory defenses belong to the defending commander. Allies share
        # faction research, supplies, escort and economic perks. Node buildings
        # and defenses belong only to the defending commander.
        for key in LOCAL_PERKS:
            loadout['perks'].pop(key, None)
        loadout['perks'].pop('allies', None)
        loadout.pop('headquarters', None)
        sizing = dict(balance_version=battle.get('team_version', 1))
        if battle.get('team_version', 1) >= 4:
            loadout.update(army_count=1, defense_multiplier=1)
        loadout['force'] = starting_force(loadout['country'], ALLY_STRENGTH, loadout['perks'],
                                         legacy_aircraft=battle.get('team_version', 1) < 3, **sizing)
        loadout['power'] = combat_power(ALLY_STRENGTH, loadout['stats'], loadout['perks'],
                                       field_repairs=loadout.get('field_repairs', False), **sizing)
    return dict(id=f'{team}:{slot}', team=team, role=role,
        controller='human' if role == 'commander' and loadout['faction'] == 'player' else 'ai',
        slot=slot, waypoint=waypoint, color=slot, scheme=COLOR_SCHEMES[slot], loadout=loadout)


def plan_participants(battle, *, legacy=False):
    """Allocate spare starts fairly and cluster allies around their commander."""
    if 'human_loadouts' in battle and not legacy:
        return _cooperative_participants(battle)
    first = 'attack' if battle['attacker'] == 'player' else 'defense'
    second = 'defense' if first == 'attack' else 'attack'
    members = [_member(battle, first, 'commander', battle['starts'][0], 0),
               _member(battle, second, 'commander', battle['starts'][1], 1)]
    if legacy:
        return members
    requested = {team: battle[team]['perks'].get('allies', 0) for team in ('attack', 'defense')}
    deployed = dict.fromkeys(requested, 0)
    available = sorted(set(battle['map']['starts']) - set(battle['starts']))
    positions = battle['map'].get('positions', {})
    leaders = {m['team']: m['waypoint'] for m in members}
    order = ('attack', 'defense') if battle['seed'] % 2 else ('defense', 'attack')
    while available:
        eligible = [team for team in order if deployed[team] < requested[team]]
        if not eligible:
            break
        team = min(eligible, key=lambda t: deployed[t])
        center = positions.get(str(leaders[team]))
        def distance(waypoint):
            point = positions.get(str(waypoint))
            return (sum((point[i] - center[i]) ** 2 for i in (0, 1))
                    if center is not None and point is not None else waypoint)
        waypoint = min(available, key=lambda w: (distance(w), w))
        available.remove(waypoint)
        members.append(_member(battle, team, 'ally', waypoint, len(members)))
        deployed[team] += 1
    return members


def participants(battle):
    # Existing pending encounters retain their original two-house commitment.
    return battle['participants'] if 'participants' in battle else plan_participants(battle, legacy=True)


def team_power(battle, team):
    return round(sum(m['loadout']['power'] for m in participants(battle) if m['team'] == team), 3)


def deployment(battle, team):
    return (sum(m['team'] == team and m['role'] == 'ally' for m in participants(battle)),
            requested_allies(battle, team))


def validate_teams(battle):
    if 'participants' not in battle:
        if 'team_version' in battle or any(battle[t]['perks'].get('allies') for t in ('attack', 'defense')):
            raise ValueError('Missing committed Conquest participants.')
        return
    if (battle.get('team_version') not in (1, 2, 3, TEAM_VERSION) or
        'human_loadouts' in battle and battle['team_version'] not in (2, 3, TEAM_VERSION) or
        battle['participants'] != plan_participants(battle)):
        raise ValueError('Invalid committed Conquest teams or starting positions.')


def requested_allies(battle, team):
    if battle.get('human_team') == team:
        return sum(entry['loadout']['perks'].get('allies', 0) for entry in battle['human_loadouts'])
    return battle[team]['perks'].get('allies', 0)


def _cooperative_participants(battle):
    human_team = battle['human_team']
    enemy_team = 'defense' if human_team == 'attack' else 'attack'
    positions = battle['map'].get('positions', {})
    available = sorted(set(battle['map']['starts']) - set(battle['starts']))
    if len(available) < len(battle['human_loadouts']) - 1:
        raise ValueError('This map cannot fit every human commander plus the enemy.')

    def take_near(center):
        point = positions.get(str(center))
        waypoint = min(available, key=lambda w: (
            sum((positions[str(w)][i] - point[i])**2 for i in (0, 1)) if point else w, w))
        available.remove(waypoint)
        return waypoint

    members = []
    leaders = {}
    for entry in battle['human_loadouts']:
        player, loadout = entry['player'], entry['loadout']
        waypoint = battle['starts'][0] if player['id'] == battle[human_team]['faction'] else take_near(battle['starts'][0])
        slot = len(members)
        members.append(dict(id=player['id'], actor=player['id'], name=player['name'], team=human_team,
            role='commander', controller='human', slot=slot, waypoint=waypoint, color=slot,
            scheme=COLOR_SCHEMES[slot], loadout=deepcopy(loadout)))
        leaders[player['id']] = waypoint
    enemy = _member(battle, enemy_team, 'commander', battle['starts'][1], len(members))
    members.append(enemy)
    leaders[battle[enemy_team]['faction']] = battle['starts'][1]
    sources = [(human_team, entry['loadout']) for entry in battle['human_loadouts']]
    sources.append((enemy_team, battle[enemy_team]))
    counts = {loadout['faction']: 0 for _, loadout in sources}
    coalition_counts = {human_team: 0, enemy_team: 0}
    order = (human_team, enemy_team) if battle['seed'] % 2 else (enemy_team, human_team)
    while available:
        eligible = [(team, loadout) for team, loadout in sources
                    if counts[loadout['faction']] < loadout['perks'].get('allies', 0)]
        if not eligible:
            break
        team, loadout = min(eligible, key=lambda pair: (
            coalition_counts[pair[0]], order.index(pair[0]), counts[pair[1]['faction']]))
        owner = loadout['faction']
        # Reuse the normal ally loadout rules with its personal sponsor.
        member = _member({**battle, team: loadout}, team, 'ally', take_near(leaders[owner]), len(members))
        member['actor'] = owner
        members.append(member)
        counts[owner] += 1
        coalition_counts[team] += 1
    return members
