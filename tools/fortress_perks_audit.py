"""Inspect expansion perks in maps generated from the installed Fortress catalogue."""

from collections import Counter
from math import isclose

from randomizer.final_fortress.player_perks import coalition, human_actor
from randomizer.maps.ini import parse_action_groups
from randomizer.rewards.catalogue import BUFF_TARGETS
from randomizer.rewards.definitions import movement_speed_ceiling


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit_expansion(rows, effective, plan, rules, preloads, terrain, art, resources):
    if plan.get('plan_version', 1) < 41:
        return
    effects = plan['effects']
    from randomizer.final_fortress.arsenal import reviewed_rules
    installed = rules
    rules, _ = reviewed_rules(rules, set(effects.get('special_access', [])))
    aliases = rows.get('FFPlayerTypes', {})
    infantry = set(rules['InfantryTypes'].values())
    vehicles = set(rules['VehicleTypes'].values())
    buildings = set(rules['BuildingTypes'].values())
    for original, alias in aliases.items():
        native, row = rules[original], effective[alias]
        if original in buildings and native.get('IsBaseDefense', 'no').lower() == 'yes':
            expected = int(native['Strength']) * (100 + effects['defense_health_percent']) // 100
            require(int(row['Strength']) == expected, f'Wrong defense durability: {original}')
        if effects['mobility_stacks'] and original in BUFF_TARGETS and original not in buildings:
            cap = movement_speed_ceiling(BUFF_TARGETS[original])
            if cap is not None:
                base = int(round(float(native.get('Speed', '1'))))
                require(float(row.get('Speed', base)) <= max(base, cap), f'Unsafe movement speed: {original}')
                if float(row.get('Speed', base)) != base and 'JumpjetSpeed' in native:
                    require(row['JumpjetSpeed'] == row['Speed'], f'Misaligned jumpjet speed: {original}')
        if effects['factory_training_percent'] and original in buildings:
            factory = native.get('Factory', '').lower()
            if factory in ('infantrytype', 'unittype') and native.get('Naval', 'no').lower() != 'yes':
                eligible = row.get('Academy.Types', '').split(',')
                require(eligible and eligible != [''], f'Missing Factory Training types: {original}')
                inverse = {value: key for key, value in aliases.items()}
                for kind in eligible:
                    source = inverse.get(kind, kind)
                    require(source in (infantry if factory == 'infantrytype' else vehicles)
                            and rules[source].get('Naval', 'no').lower() != 'yes'
                            and rules[source].get('Trainable', 'yes').lower() != 'no',
                            f'Factory Training leaked onto another production category: {original}/{source}')
                require(isclose(float(row['Academy.VehicleVeterancy']), effects['factory_training_percent'] / 100),
                        f'Wrong Factory Training rank: {original}')
            elif factory in ('aircrafttype', 'unittype'):
                require(row.get('Academy.Types') == native.get('Academy.Types'),
                        f'Factory Training affected airfield or shipyard: {original}')
        if original in installed:
            require(effective[original].get('Speed') == installed[original].get('Speed'),
                    f'Player speed leaked to native type: {original}')

    for camp in plan['map']['camps']:
        reward = camp['crate_reward']
        require(reward['credits'] >= effects['camp_salvage_credits'], 'Camp salvage payout missing')
        if effects['camp_reward_units'] and reward['id'] in ('tier1_squad', 'tier2_squad'):
            require(reward['units'] == effects['camp_reward_units'], 'Advanced Spoils roster missing')
        teams = [row for row in effective.values()
                 if row.get('Name', '').startswith('Player camp reward ' + camp['id']) and 'TaskForce' in row]
        require(all(t['VeteranLevel'] == str(effects['camp_veterancy'] + 1) for t in teams),
                'Veteran Spoils rank missing on reward team')

    if effects.get('reinforcements'):
        interval = 300 - effects['reinforcement_interval_reduction_seconds']
        effect = effects['reinforcements']
        require(effect['first_seconds'] == effect['interval_seconds'] == interval, 'Wrong reinforcement interval')
        require([entry['seconds'] for entry in plan['reinforcement_schedule']]
                == list(range(interval, plan['survival_seconds'], interval)), 'Truncated priority reinforcement schedule')

    if not effects['outpost_rank']:
        require(not rows.get('FFOutpostTypes'), 'Disabled outposts emitted private structures')
        return
    from randomizer.final_fortress.placement import foundation
    types = rows['FFOutpostTypes']
    require(all(alias in preloads['rules'] for alias in types.values()), 'Outpost type missing from preloads')
    occupied = set()
    for camp in plan['map']['camps']:
        structures = camp['outpost']['structures']
        require(sum(int(effective[types[e['type']]].get('Power', '0')) for e in structures) >= 0,
                'Recovered outpost has insufficient power')
        require(len(rows.get('FFOutpostStructures.' + camp['id'], {})) == len(structures), 'Outpost structure omitted')
        for entry in structures:
            row = effective[types[entry['type']]]
            p = entry['position']
            cells = {(p['x'] + dx, p['y'] + dy) for dx, dy in foundation(row, art)}
            require(not cells & occupied, 'Outpost foundations overlap')
            occupied.update(cells)
            if terrain:
                require(terrain.clear(cells, allowed_overlays=resources), 'Outpost extends onto invalid terrain')
            require(row['Unsellable'] == 'yes' and row['Capturable'] == 'no' and row['TechLevel'] == '-1',
                    'Outpost copy can be sold, captured or built directly')
            normal = effective[aliases.get(entry['type'], entry['type'])]
            require(row['Strength'] == normal['Strength'], 'Outpost loses or doubles health perks')
            if row.get('IsBaseDefense', 'no').lower() == 'yes' and effects['defense_veterancy']:
                require(all(types[entry['type']] in effective[actor]['VeteranBuildings'].split(',')
                            for actor, _, _ in coalition(plan)), 'Outpost defenses lose initial veterancy')
            for field in ('Primary', 'Secondary', 'ElitePrimary', 'EliteSecondary', 'FreeUnit'):
                require(row.get(field) == normal.get(field), f'Outpost loses native or buffed {field}')
        for actor, _, _ in coalition(plan)[:len(plan.get('coop_players', [])) or 1]:
            current = rows['FFOutpostClaims.' + camp['id']][actor]
            found, seen = [], set()
            while current:
                require(current not in seen, 'Outpost creation trigger cycle')
                seen.add(current)
                require(rows['Triggers'][current].split(',')[0] == actor, 'Outpost belongs to another player')
                actions = parse_action_groups(rows['Actions'][current])[1]
                found.extend(a[2] for a in actions if a[0] == '125')
                next_keys = [a[2] for a in actions if a[0] == '53']
                require(len(next_keys) <= 1, 'Outpost creation branches or repeats')
                current = next_keys[0] if next_keys else None
            require(Counter(found) == Counter(types[e['type']] for e in structures), 'Outpost grants missing/duplicate buildings')
        for actor, _, _ in [*coalition(plan), *[(f'FFENEMY{i + 1}', country, wp) for i, (country, wp)
                          in enumerate(zip(plan['enemy_countries'], plan['map']['enemy_waypoints']))]]:
            claim = next(key for key, value in rows['Triggers'].items()
                         if value.split(',')[2] == f'Camp {camp["id"]} claim {actor}')
            actions = parse_action_groups(rows['Actions'][claim])[1]
            recipient = actor if human_actor(plan, actor) else 'FFPLAYER'
            grant = rows['FFOutpostClaims.' + camp['id']][recipient]
            require(sum(a[0] == '53' and a[2] == grant for a in actions) == 1, 'Outpost pickup has wrong human recipient')
