"""Periodic friendly arrivals with their own conservative living-unit budget."""

from copy import deepcopy

from .player_perks import coalition


def reserve_staging(writer, plan, rules):
    """Reserve the reviewed 5x3 army apron with walkable building foundations.

    Passable, invisible 1x1 buildings prevent construction without obstructing
    arriving units. They remain passive Neutral objects, require no ownership
    transfers and cannot grant cash, score, build adjacency or survival credit.
    """
    friendly = plan.get('plan_version', 1) >= 14 and bool(
        plan.get('reinforcement_schedule') or plan['effects'].get('lab_reserve_units'))
    enemy = plan.get('plan_version', 1) >= 16
    if not friendly and not enemy:
        return
    from .engine import _place
    from randomizer.maps.buff_values import _register_map_type
    kind = writer.key()
    row = deepcopy(rules['CABHUT'])
    row.update(Name='Final Fortress reserved reinforcement apron', Image='CABHUT',
               InvisibleInGame='yes', IsPassable='yes', Immune='yes', LegalTarget='no',
               Selectable='no', Capturable='no', Repairable='no', Unsellable='yes',
               CanBeOccupied='no', BridgeRepairHut='no', BaseNormal='no',
               Insignificant='yes', DontScore='yes', KeepAlive='no', RadarInvisible='yes',
               TechLevel='-1', BuildLimit='0', AIBuildThis='no', Sight='0', Power='0',
               Powered='no', ImmuneToPsionics='yes', ImmuneToEMP='yes',
               ImmuneToTemporal='yes', Warpable='no', ProduceCashStartup='0',
               ProduceCashAmount='0', ProduceCashDelay='0')
    writer.sections[kind] = row
    _register_map_type(writer.sections, writer.lines, rules, 'BuildingTypes', kind)
    aprons = []
    if friendly:
        writer.put('FFReinforcementPads', 'Type', kind)
        for actor, _, waypoint in coalition(plan):
            position = plan['map']['perk_layouts'][str(waypoint)]['units']
            writer.put('FFReinforcementPads', actor, position['y'] * 1000 + position['x'])
            aprons.append((position, 5, 3))
    if enemy:
        writer.put('FFEnemyWavePads', 'Type', kind)
        for index, waypoint in enumerate(plan['map']['enemy_waypoints']):
            position = plan['map']['enemy_wave_positions'][str(waypoint)]
            cell = position['y'] * 1000 + position['x']
            writer.put('FFEnemyWavePads', f'FFENEMY{index + 1}', cell)
            writer.put('Waypoints', 16 + index, cell + 1002)
            aprons.append((position, 5, 3))
    for position, width, height in aprons:
        for dx in range(width):
            for dy in range(height):
                _place(writer, 'Structures', f'Neutral,{kind},256,{position["x"] + dx},'
                       f'{position["y"] + dy},64,None,1,0,1,0,0,None,None,None,0,0')


def build_schedule(plan):
    effect = plan['effects'].get('reinforcements')
    if not effect:
        return []
    groups = []
    for actor, _, waypoint in coalition(plan):
        if str(waypoint) not in plan['map'].get('perk_layouts', {}):
            raise ValueError('Reinforcements need a reviewed friendly staging location.')
        groups.append({'owner': actor, 'waypoint': waypoint, 'units': deepcopy(effect['units'])})
    total = sum(unit['count'] for group in groups for unit in group['units'])
    if total > effect['max_active_units']:
        raise ValueError('A friendly reinforcement arrival exceeds its shared living-unit cap.')
    times = range(effect['first_seconds'], plan['survival_seconds'], effect['interval_seconds'])
    if len(times) > 11:
        raise ValueError('Final Fortress supports at most eleven friendly reinforcement arrivals.')
    return [{'seconds': seconds, 'groups': deepcopy(groups)} for seconds in times]


def apply_reinforcements(writer, plan, rules, player_aliases, finished, *, friendly_clocks=None):
    """Reserve a complete arrival until all its private unit types disappear.

    Native type-absence checks remain valid after team disbanding, capture and
    deploy conversions. Starting armies and ordinary production do not consume
    this separate cap. A delayed arrival starts the next five-minute timer only
    after admission, preventing queued arrivals from bursting into the base.
    """
    from .engine import _action, _capacity_subsets, _waypoint

    schedule = plan.get('reinforcement_schedule', [])
    if not schedule:
        return
    effect = plan['effects']['reinforcements']
    inverse = {alias: original for original, alias in player_aliases.items()}
    overrides = {}
    for original, alias in player_aliases.items():
        row = deepcopy(writer.sections[alias])
        for field in ('Convert.Deploy', 'Convert.Land', 'Convert.Water'):
            row[field] = inverse.get(row.get(field), row.get(field, 'none'))
        overrides[original] = row
    if plan.get('plan_version', 1) >= 17:
        from .friendly_pool import apply_friendly_pool
        apply_friendly_pool(writer, plan, rules, overrides, finished, friendly_clocks=friendly_clocks)
        return
    ready = [writer.flag(f'Friendly arrival {i + 1} ready') for i in range(len(schedule))]
    spawned = [writer.flag(f'Friendly arrival {i + 1} spawned') for i in range(len(schedule))]
    cleared = [writer.flag(f'Friendly arrival {i + 1} cleared') for i in range(len(schedule))]
    timers = [writer.trigger(f'Friendly arrival {i + 1} interval',
                            [(13, 0, effect['interval_seconds'] if i else effect['first_seconds'])],
                            [_action(56, flag)], disabled=i > 0)[0]
              for i, flag in enumerate(ready)]
    staging = {}
    for index, (actor, _, waypoint) in enumerate(coalition(plan)):
        position = plan['map']['perk_layouts'][str(waypoint)]['units']
        staging[actor] = 10 + index
        writer.put('Waypoints', 10 + index, position['y'] * 1000 + position['x'])
    counts = []
    for index, arrival in enumerate(schedule):
        aliases = writer.wave_types(arrival['groups'], rules, overrides)
        actions = []
        for group in arrival['groups']:
            helper = plan.get('plan_version', 1) >= 14 and group['owner'] != 'FFPLAYER'
            team = writer.team(f'Fortress friendly arrival {index + 1} {group["owner"]}',
                               [{'type': aliases[unit['type']], 'count': unit['count']}
                                for unit in group['units']], group['waypoint'],
                               attack=helper, owner=group['owner'])
            writer.put(team, 'Waypoint', _waypoint(staging[group['owner']]))
            writer.put(team, 'VeteranLevel', effect.get('veterancy', 0) + 1)
            # Batch identities are deliberately absent from normal AI recipes.
            # Helpers need their own attack team; human arrivals remain guarded
            # and available for selection. Do not let native AI steal partial
            # helper teams and strand the remainder of a capped batch.
            writer.put(team, 'AreTeamMembersRecruitable', 'no' if helper else 'yes')
            actions.append(writer.reinforce(team))
        completed, _ = writer.trigger(f'Friendly arrival {index + 1} complete',
                                     [(13, 0, 0), (36, 0, spawned[index]),
                                      *((61, 2, 0, alias) for alias in aliases.values())],
                                     [_action(56, cleared[index])], disabled=True)
        actions.extend((_action(56, spawned[index]), _action(53, trigger=completed)))
        if index + 1 < len(timers):
            actions.append(_action(53, trigger=timers[index + 1]))
        admission, _ = writer.trigger(f'Friendly arrival {index + 1} spawn',
                                     [(13, 0, 0), (37, 0, finished)], actions, disabled=True)
        count = sum(unit['count'] for group in arrival['groups'] for unit in group['units'])
        for subset in _capacity_subsets(counts, count, effect['max_active_units']):
            writer.trigger(f'Friendly arrival {index + 1} capacity',
                           [(36, 0, ready[index]), (37, 0, spawned[index]), (37, 0, finished),
                            *((36, 0, cleared[prior]) for prior in subset)],
                           [_action(53, trigger=admission)])
        counts.append(count)
