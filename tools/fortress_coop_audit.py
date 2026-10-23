"""Review emitted Fortress network spawns, ownership and linked camp triggers."""

from copy import deepcopy
import hashlib

from randomizer.final_fortress.coop import spawn_data
from randomizer.final_fortress.player_perks import coalition
from randomizer.maps.ini import all_section_value_maps_preserve, parse_action_groups


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sections(data):
    return all_section_value_maps_preserve(data.decode('latin-1').splitlines())


def audit_coop_artifacts(output, name, plan, data, preloads, rules):
    rows = sections(data)
    effective = deepcopy(rules)
    for section, values in rows.items():
        effective.setdefault(section, {}).update(values)
    players = plan['coop_players']
    count = len(players)
    friends = coalition(plan)
    expected_helpers = min(plan['effects']['allied_helpers'], 3 - count)
    require(len(friends) == count + expected_helpers, 'Human players did not displace helper slots')
    endpoints = [{'name': player, 'address': f'127.0.0.{slot + 2}', 'port': 1234 + slot}
                 for slot, player in enumerate(players)]
    canonical = None
    host_spawn = None
    country_indices = {value: key for key, value in effective['Countries'].items()}
    for slot, player in enumerate(players):
        spawn = spawn_data(plan, data, slot=slot, endpoints=endpoints)
        (output / f'{name}.player{slot + 1}.spawn.ini').write_bytes(spawn)
        current = sections(spawn)
        settings = current['Settings']
        require(settings['PlayerCount'] == str(count)
                and settings['AIPlayers'] == str(3 + expected_helpers), 'Wrong native human/AI count')
        require(settings['Name'] == player and settings['Side'] == country_indices[friends[slot][0]],
                'Local human uses another house or native perk-free country')
        require(settings['Color'] == str((0, 4, 5)[slot]) and settings['Port'] == str(1234 + slot),
                'Local network color/port differs from the roster')
        require(settings['Host'] == ('Yes' if slot == 0 else 'No'), 'Guest is also a native host')
        peers = [current[f'Other{i + 1}'] for i in range(count - 1)]
        require({peer['Name'] for peer in peers} == set(players) - {player}, 'Human peer roster is incomplete')
        for peer in peers:
            other = players.index(peer['Name'])
            require(peer['Ip'] == endpoints[other]['address'] and peer['Port'] == str(1234 + other)
                    and peer['Side'] == country_indices[friends[other][0]]
                    and peer['Color'] == str((0, 4, 5)[other]), 'Wrong peer route, country or color')
        shared = {key: value for key, value in current.items()
                  if key != 'Settings' and not key.startswith('Other')}
        identity = (settings['Seed'], settings['GameID'], settings['MapSHA1'])
        if canonical is None:
            canonical = shared, identity
            host_spawn = spawn
        require(canonical == (shared, identity), 'Players disagree on native map identity, houses or alliances')
        require(settings['MapSHA1'] == hashlib.sha1(data).hexdigest(), 'Network scenario digest is wrong')
        for index, (_, _, waypoint) in enumerate(friends[:count], 1):
            require(shared['SpawnLocations'][f'Multi{index}'] == str(waypoint), 'Human starts overlap or moved')
        for index, waypoint in enumerate(plan['map']['enemy_waypoints'], count + 1):
            key = f'Multi{index}'
            require(shared['SpawnLocations'][key] == str(waypoint)
                    and shared['HouseCountries'][key] == country_indices[f'FFENEMY{index - count}'],
                    'Human displaced an enemy country/start')
        require(len(shared['SpawnLocations']) == 3 + len(friends), 'Extra phantom player/helper house')
    human_actors = {actor for actor, _, _ in friends[:count]}
    require(all(value.split(',')[2] not in human_actors for value in rows.get('AITriggerTypes', {}).values()),
            'Native AI recipes can take over a co-op human')
    for actor in human_actors:
        require(not any(effective[key].get('Name', '').startswith('Fortress helper starting army ' + actor)
                        for key in rows.get('TeamTypes', {}).values()), 'Human starting army has helper attack orders')
    if plan['effects'].get('reveal_map'):
        require(not any(action[0] == '16' for value in rows['Actions'].values()
                        for action in parse_action_groups(value)[1]), 'Unsafe local reveal-map action in multiplayer')
        require(any(row.get('SpySat') == 'yes' for row in preloads['rules'].values()),
                'Co-op map reveal has no native satellite provider')
    audit_transfers(rows, effective, plan)
    audit_camp_claims(rows, effective, plan)
    return host_spawn


def audit_transfers(rows, effective, plan):
    """Count actual preplaced ownership transfers, independently of perk formulas."""
    counts = {waypoint: 0 for _, _, waypoint in coalition(plan)}
    for section, tag_field in (('Structures', 6), ('Units', 7), ('Infantry', 8), ('Aircraft', 7)):
        for value in rows.get(section, {}).values():
            fields = value.split(',')
            tag = fields[tag_field]
            if tag not in rows['Tags']:
                continue
            trigger = rows['Tags'][tag].split(',')[2]
            visited = set()
            while trigger in rows['Triggers']:
                require(trigger not in visited, 'Ownership tags contain a trigger cycle')
                visited.add(trigger)
                if rows['Events'][trigger] == '1,13,0,0':
                    for action in parse_action_groups(rows['Actions'][trigger])[1]:
                        if action[0] == '14' and int(action[2]) - 4475 in counts:
                            counts[int(action[2]) - 4475] += 1
                trigger = rows['Triggers'][trigger].split(',')[1]
    for slot, (_, _, waypoint) in enumerate(coalition(plan)[:len(plan['coop_players'])]):
        require(counts[waypoint] == plan['coop_initial_transfer_kills'][slot],
                f'Player {slot + 1} setup transfers can mint kill rewards: '
                f'{counts[waypoint]} native transfers, {plan["coop_initial_transfer_kills"][slot]} excluded')


def audit_camp_claims(rows, effective, plan):
    names = {value.split(',')[2]: key for key, value in rows['Triggers'].items()}
    human_count = len(plan['coop_players'])
    for camp in plan['map']['camps']:
        tag = rows['CellTags'][str(camp['position']['y'] * 1000 + camp['position']['x'])]
        trigger = rows['Tags'][tag].split(',')[2]
        chain = []
        while trigger in rows['Triggers']:
            require(trigger not in chain, 'Camp claim trigger cycle')
            chain.append(trigger)
            trigger = rows['Triggers'][trigger].split(',')[1]
        require(len(chain) == human_count, 'One camp pickup cell does not cover every human')
        clear = names['Camp ' + camp['id'] + ' cleared']
        enabled = {action[2] for action in parse_action_groups(rows['Actions'][clear])[1] if action[0] == '53'}
        require(enabled == set(chain), 'Camp clearance does not enable every human pickup')
        shared = set()
        for slot, (actor, _, waypoint) in enumerate(coalition(plan)[:human_count]):
            claim = names[f'Camp {camp["id"]} claim {actor}']
            require(claim in chain and f'1,0,{4475 + waypoint}' in rows['Events'][claim],
                    'Camp pickup is not bound to its human collector')
            actions = parse_action_groups(rows['Actions'][claim])[1]
            shared.add(actions[0][2])
            require(actions[0][0] == '56' and f'37,0,{actions[0][2]}' in rows['Events'][claim],
                    'Camp pickup can be claimed repeatedly or by two players')
            for action in actions:
                if action[0] == '7':
                    require(effective[action[2]]['House'] == actor, 'Camp squad went to another player')
            require(plan['gem_rewards'][f'camp_pick:{slot}:{camp["id"]}'] == 0,
                    'Camp crate pickup duplicates shared Defensive Points')
        require(len(shared) == 1, 'Camp collectors do not share the same one-time pickup guard')
