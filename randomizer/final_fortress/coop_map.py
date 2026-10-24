"""Shared camp pickups: humans keep rewards; AI collectors deliver to the host."""

from .player_perks import coalition, human_actor, needs_countries


def escrow_cell(writer, plan, rules, spare_cell):
    """Keep passable cash proxies clear of all granted defenses and camp guards."""
    from randomizer.maps.ini import section_value_map
    from .camps import guard_positions
    from .placement import PlayableBounds, deployment_cells, foundation, installed_art
    if not hasattr(writer, '_coop_escrow_cells'):
        occupied = set()
        art = installed_art()
        for category in ('Structures', 'Units', 'Infantry', 'Aircraft'):
            placed = {**section_value_map(writer.lines, category),
                      **writer.sections.get(category, {})}
            for value in placed.values():
                fields = value.split(',')
                x, y = map(int, fields[3:5])
                row = {**rules.get(fields[1], {}), **writer.sections.get(fields[1], {})}
                row.setdefault('Image', fields[1])
                offsets = foundation(row, art) if category == 'Structures' else {(0, 0)}
                occupied.update((x + dx, y + dy) for dx, dy in offsets)
        for camp in plan['map']['camps']:
            occupied.add((camp['position']['x'], camp['position']['y']))
            occupied.update((p['x'], p['y']) for p in guard_positions(camp))
        points = section_value_map(writer.lines, 'Waypoints')
        for waypoint in [plan['map']['player_waypoint'], *plan['map']['enemy_waypoints'],
                         *plan['allied_waypoints']]:
            cell = int(points[str(waypoint)])
            if plan.get('plan_version', 1) >= 31:
                occupied.update(deployment_cells(cell % 1000, cell // 1000))
            else:
                occupied.update((cell % 1000 + dx, cell // 1000 + dy)
                                for dx in range(-2, 2) for dy in range(-1, 2))
        bounds = PlayableBounds(section_value_map(writer.lines, 'Map'))
        x, y = spare_cell % 1000, spare_cell // 1000
        writer._coop_escrow_cells = iter((x + dx, y + dy) for dy in range(5, 30)
            for dx in range(12) if (x + dx, y + dy) not in occupied
            and bounds.contains({(x + dx, y + dy)}, maximum_height=14))
    try:
        return next(writer._coop_escrow_cells)
    except StopIteration:
        raise ValueError('No safe utility cells remain for Fortress co-op camp rewards.') from None


def camp_claims(writer, plan, rules, camp, index, waypoint, cleared,
                marker_teams, finished, clear, player_aliases):
    from .engine import _action, _cash_reward, _camp_squad, _waypoint
    from .messages import camp_clear_actions, message_actions

    reward = camp.get('crate_reward', {})
    pickup = plan.get('plan_version', 1) >= 25
    claimed = writer.flag('Camp ' + camp['id'] + ' reward claimed')
    claims = []
    linked = '<none>'
    friends = coalition(plan)
    collectors = friends if plan.get('plan_version', 1) >= 32 else friends[:len(plan['coop_players'])]
    if plan.get('plan_version', 1) >= 39:
        collectors = [*collectors, *[(f'FFENEMY{i + 1}', country, start)
                      for i, (country, start) in enumerate(zip(
                          plan['enemy_countries'], plan['map']['enemy_waypoints']))]]
    cash_selectors = {}
    for slot, (actor, _, start) in enumerate(collectors):
        # All AI collect for the host. Human co-op collectors retain their
        # own cash/squad ownership; the shared Defensive Points receipt pays once.
        recipient_slot = slot if human_actor(plan, actor) else 0
        recipient, _, recipient_start = friends[recipient_slot]
        recipient_name = (plan['coop_players'][recipient_slot] if plan.get('coop_players') else 'Commander')
        actions = [_action(56, claimed),
                   _action(4, team=marker_teams['camp:' + camp['id']]),
                   *([_action(4, team=marker_teams[f'camp_pick:{recipient_slot}:{camp["id"]}'])]
                     if plan.get('coop_players') else []),
                   *message_actions('Reward for ' + recipient_name),
                   *message_actions('Reward: ' + reward.get('display_name', 'Collected'))]
        if pickup:
            actions.extend(message_actions(f'+{camp["gems"]} Defensive Points'))
        if reward.get('credits'):
            # Every AI routes to the same host escrow. Sharing its selector
            # keeps six-collector maps within the native 100-local limit.
            selector_key = recipient_slot if plan.get('plan_version', 1) >= 39 else slot
            if selector_key not in cash_selectors:
                cash_selectors[selector_key] = writer.flag(f'Camp {camp["id"]} collector {slot}')
                _cash_reward(writer, plan, rules, camp, cash_selectors[selector_key], index,
                             waypoint=recipient_start)
            selector = cash_selectors[selector_key]
            actions.insert(1, _action(56, selector))
        if reward.get('units'):
            owner = recipient if needs_countries(plan) else plan['player_country']
            actions.extend(_camp_squad(writer, plan, camp, waypoint, recipient_start, owner, player_aliases))
        trigger, tag = writer.trigger(f'Camp {camp["id"]} claim {actor}',
            [(1, 0, 4475 + start), (36, 0, cleared), (37, 0, finished), (37, 0, claimed)],
            actions, disabled=True)
        writer.put('Triggers', trigger,
                   f'<none>,{linked},Camp {camp["id"]} claim {actor},1,1,1,1,0')
        linked = trigger
        claims.append(trigger)
    position = camp['position']
    writer.put('CellTags', position['y'] * 1000 + position['x'], tag)
    actions = [_action(54, trigger=clear), _action(56, cleared),
               _action(108, 0, waypoint=_waypoint(waypoint)),
               *[_action(53, trigger=trigger) for trigger in claims]]
    if not pickup:
        actions.extend([_action(4, team=marker_teams['camp_clear:' + camp['id']]),
                        *camp_clear_actions(camp, coop=True)])
    writer.put('Actions', clear, str(len(actions)) + ',' + ','.join(
        token for action in actions for token in action))
