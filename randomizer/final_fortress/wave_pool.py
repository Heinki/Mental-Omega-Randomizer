"""Small reusable population reservations for scripted enemy attacks.

Each enemy has an equal share of the living-unit ceiling. Empty slots can be
reused immediately by the pending wave; a survivor holds at most twenty slots,
not an entire multi-house wave. Private identities also track captured units
and native deployment conversions without depending on team death callbacks.
"""

from copy import deepcopy


def _batches(units, capacity):
    """Keep each delivery mixed while preserving every frozen roster count."""
    remaining = deepcopy(units)
    while any(unit['count'] for unit in remaining):
        counts = [0] * len(remaining)
        for _ in range(capacity):
            available = [i for i, unit in enumerate(remaining) if unit['count']]
            if not available:
                break
            index = min(available, key=lambda i: (counts[i], i))
            remaining[index]['count'] -= 1
            counts[index] += 1
        yield [{'type': unit['type'], 'count': count}
               for unit, count in zip(units, counts) if count]


def apply_wave_pool(writer, plan, rules, overrides, marker_teams, finished, *, wave_clock=None):
    from .engine import _action, _waypoint

    schedule = plan['wave_schedule']
    if not schedule:
        return
    limit = plan['wave_pressure']['max_active_units']
    if not 3 <= limit <= 480:
        raise ValueError('Reusable wave pools support a shared living-unit ceiling of 3–480.')
    capacity = min(20, limit // 3)
    if capacity < 1:
        raise ValueError('The wave population ceiling must allow at least one unit per enemy.')
    slots_per_enemy = min(8, limit // (3 * capacity))
    pools = {}
    for enemy, waypoint in enumerate(plan['map']['enemy_waypoints'], 1):
        groups = [group for wave in schedule for group in wave['groups'] if group['waypoint'] == waypoint]
        slots = []
        for _ in range(slots_per_enemy):
            key = writer.key()
            busy = writer.flag('Wave pool occupied ' + key)
            aliases = writer.wave_types(groups, rules, overrides)
            if len(aliases) > 30:
                raise ValueError('Enemy wave roster exceeds the native slot-release event limit.')
            release, _ = writer.trigger('Wave pool release ' + key,
                [(36, 0, busy), *((61, 2, 0, alias) for alias in aliases.values())],
                [_action(57, busy)], persistence=2)
            writer.put('FFWavePools', key, f'FFENEMY{enemy},{capacity},{busy},{release}')
            for original, alias in aliases.items():
                writer.put('FFWavePoolTypes.' + key, original, alias)
            slots.append((key, busy, aliases))
        pools[waypoint] = slots

    # Timers and handoff relays are created before their forward references.
    timers = [writer.trigger(f'Wave {i + 1} interval', [(13, 0, plan['wave_interval_seconds'])],
                             [], disabled=i > 0)[0] for i in range(len(schedule))]
    for index, wave in enumerate(schedule):
        grouped = []
        for group in wave['groups']:
            air = set(group.get('air_types', []))
            ground_units = [unit for unit in group['units'] if unit['type'] not in air]
            air_units = [unit for unit in group['units'] if unit['type'] in air]
            chunks = [*_batches(ground_units, capacity), *_batches(air_units, capacity)]
            grouped.append((group, chunks))
        # Alternate active fronts instead of exhausting one before the others.
        batches = [(group, chunks[n]) for n in range(max(len(chunks) for _, chunks in grouped))
                   for group, chunks in grouped if n < len(chunks)]
        relays = [writer.trigger(f'Wave {index + 1} delivery {n + 1}',
                                 [(13, 0, 0), (37, 0, finished)], [], disabled=True)[0]
                  for n in range(len(batches) + 1)]
        writer.put('Actions', timers[index], '1,' + ','.join(_action(53, trigger=relays[0])))
        for n, (group, units) in enumerate(batches):
            alternatives = []
            for slot, busy, aliases in pools[group['waypoint']]:
                team = writer.team(f'Final Fortress wave {index + 1} {group["house"]} batch {n + 1} slot {slot}',
                    [{'type': aliases[unit['type']], 'count': unit['count']} for unit in units],
                    group['waypoint'], owner=f'FFENEMY{plan["map"]["enemy_waypoints"].index(group["waypoint"]) + 1}')
                writer.put(team, 'VeteranLevel', group.get('veteran_level', 1))
                writer.put(team, 'Waypoint', _waypoint(16 + plan['map']['enemy_waypoints'].index(group['waypoint'])))
                gate, _ = writer.trigger(f'Wave {index + 1} slot dispatch',
                    [(37, 0, busy), (37, 0, finished)], [], disabled=True)
                alternatives.append((gate, busy, team))
                writer.put('FFWaveDispatches', gate, f'{slot},{team},{relays[n]},{relays[n + 1]}')
            writer.put('FFWaveChunks', relays[n], f'{index + 1},{group["house"]},{sum(u["count"] for u in units)}')
            actions = [_action(53, trigger=gate) for gate, _, _ in alternatives]
            writer.put('Actions', relays[n], str(len(actions)) + ',' + ','.join(t for a in actions for t in a))
            for gate, busy, team in alternatives:
                # Reserve before spawning and disable every alternative now;
                # later gates cannot double-dispatch this same delivery.
                actions = [*[_action(54, trigger=other) for other, _, _ in alternatives],
                           _action(56, busy), writer.reinforce(team),
                           _action(53, trigger=relays[n + 1])]
                writer.put('Actions', gate, str(len(actions)) + ',' + ','.join(t for a in actions for t in a))
        actions = [_action(4, team=marker_teams[f'wave:{index + 1}'])]
        if index + 1 < len(timers):
            actions.append(_action(53, trigger=timers[index + 1]))
        if wave_clock is not None:
            actions.append(_action(56, wave_clock[0] if index + 1 < len(timers) else wave_clock[1]))
        writer.put('Actions', relays[-1], str(len(actions)) + ',' + ','.join(t for a in actions for t in a))
