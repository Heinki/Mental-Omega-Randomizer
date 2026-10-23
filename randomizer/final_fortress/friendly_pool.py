"""Independent friendly arrivals using small reusable population reservations."""

from .player_perks import coalition, human_actor
from .wave_pool import _batches


def apply_friendly_pool(writer, plan, rules, overrides, finished, *, friendly_clocks=None):
    from .engine import _action, _waypoint
    from .messages import message_actions

    effect = plan['effects']['reinforcements']
    actors = coalition(plan)
    limit = effect['max_active_units']
    # At most fifteen alternatives keep every native action line below 511
    # bytes. Sharing the slots lets the human use capacity released by helpers.
    capacity = (limit + 14) // 15
    slot_count = min(15, limit // capacity)
    slots = []
    for _ in range(slot_count):
        slot = writer.key()
        busy = writer.flag('Friendly pool occupied ' + slot)
        aliases = writer.wave_types([{'units': effect['units']}], rules, overrides)
        release, _ = writer.trigger('Friendly pool release ' + slot,
            [(36, 0, busy), *((61, 2, 0, alias) for alias in aliases.values())],
            [_action(57, busy)], persistence=2)
        writer.put('FFFriendlyPools', slot, f'coalition,{capacity},{busy},{release}')
        for original, alias in aliases.items():
            writer.put('FFFriendlyPoolTypes.' + slot, original, alias)
        slots.append((slot, busy, aliases))
    for actor_index, (owner, _, waypoint) in enumerate(actors):
        position = plan['map']['perk_layouts'][str(waypoint)]['units']
        writer.put('Waypoints', 10 + actor_index, (position['y'] + 1) * 1000 + position['x'] + 2)
        schedule = plan['reinforcement_schedule']
        timers = [writer.trigger(f'Friendly arrival {i + 1} {owner} interval',
                    [(13, 0, effect['interval_seconds'] if i else effect['first_seconds'])],
                    [], disabled=i > 0)[0] for i in range(len(schedule))]
        for index, arrival in enumerate(schedule):
            group = next(g for g in arrival['groups'] if g['owner'] == owner)
            batches = list(_batches(group['units'], capacity))
            relays = [writer.trigger(f'Friendly arrival {index + 1} {owner} delivery {n + 1}',
                        [(13, 0, 0), (37, 0, finished)], [], disabled=True)[0]
                      for n in range(len(batches) + 1)]
            warning = reminder = None
            if human_actor(plan, owner):
                prefix = f'Player {actor_index + 1}: ' if plan.get('coop_players') else ''
                notice = message_actions(prefix + 'Allied arrival waiting for capacity. '
                                         f'Shared reinforcement cap: {limit}. '
                                         'Countdown resumes after delivery.')
                waiting = [(37, 0, finished), *((36, 0, busy) for _, busy, _ in slots)]
                warning, _ = writer.trigger(f'Friendly arrival {index + 1} {owner} capacity notice',
                    waiting, notice, disabled=True)
                reminder, _ = writer.trigger(f'Friendly arrival {index + 1} {owner} capacity reminder',
                    [(13, 0, 30), *waiting], notice, disabled=True, persistence=2)
            actions = [_action(53, trigger=relays[0])]
            if warning:
                actions.append(_action(53, trigger=warning))
                actions.append(_action(53, trigger=reminder))
            writer.put('Actions', timers[index], str(len(actions)) + ',' + ','.join(t for a in actions for t in a))
            for n, units in enumerate(batches):
                alternatives = []
                for slot, busy, aliases in slots:
                    helper = not human_actor(plan, owner)
                    team = writer.team(f'Fortress friendly arrival {index + 1} {owner} batch {n + 1} slot {slot}',
                        [{'type': aliases[u['type']], 'count': u['count']} for u in units],
                        waypoint, attack=helper, owner=owner)
                    writer.put(team, 'Waypoint', _waypoint(10 + actor_index))
                    writer.put(team, 'VeteranLevel', effect.get('veterancy', 0) + 1)
                    writer.put(team, 'AreTeamMembersRecruitable', 'no' if helper else 'yes')
                    gate, _ = writer.trigger(f'Friendly arrival {index + 1} {owner} slot dispatch',
                        [(37, 0, busy), (37, 0, finished)], [], disabled=True)
                    writer.put('FFFriendlyDispatches', gate, f'{slot},{team},{relays[n]},{relays[n + 1]}')
                    alternatives.append((gate, busy, team))
                writer.put('FFFriendlyChunks', relays[n], f'{index + 1},{owner},{sum(u["count"] for u in units)}')
                actions = [_action(53, trigger=gate) for gate, _, _ in alternatives]
                writer.put('Actions', relays[n], str(len(actions)) + ',' + ','.join(t for a in actions for t in a))
                for gate, busy, team in alternatives:
                    actions = [*[_action(54, trigger=other) for other, _, _ in alternatives],
                               _action(56, busy), writer.reinforce(team), _action(53, trigger=relays[n + 1])]
                    writer.put('Actions', gate, str(len(actions)) + ',' + ','.join(t for a in actions for t in a))
            actions = [_action(54, trigger=key) for key in (warning, reminder) if key]
            if plan.get('plan_version', 1) >= 29 and human_actor(plan, owner):
                count = sum(unit['count'] for unit in group['units'])
                level = ('Rookie', 'Veteran', 'Elite')[effect.get('veterancy', 0)]
                actions.extend(message_actions(f'Player {actor_index + 1}: +{count} units'))
                actions.extend(message_actions(f'{level} reinforcements ready'))
            if index + 1 < len(timers):
                actions.append(_action(53, trigger=timers[index + 1]))
            if friendly_clocks and owner in friendly_clocks:
                actions.append(_action(56, friendly_clocks[owner][0 if index + 1 < len(timers) else 1]))
            if not actions:
                # An event-guarded no-op keeps the native action list valid.
                actions = [_action(54, trigger=relays[-1])]
            writer.put('Actions', relays[-1], str(len(actions)) + ',' + ','.join(t for a in actions for t in a))
