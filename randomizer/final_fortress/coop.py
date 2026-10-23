"""Fortress roster and native spawner settings for two or three humans."""

import ipaddress

from randomizer.coop.direct import _name, _port
from randomizer.coop.lobby import LOBBY_PORT
from randomizer.maps.ini import IniLines, all_section_value_maps_preserve, section_value_map

from .player_perks import coalition


def lobby_port(slot):
    if type(slot) is not int or slot not in (1, 2):
        raise ValueError('Choose guest player 2 or 3.')
    return LOBBY_PORT + (slot - 1) * 2


def validate_endpoints(plan, endpoints):
    players = plan.get('coop_players', [])
    if not isinstance(endpoints, list) or not 2 <= len(players) <= 3 or len(endpoints) != len(players):
        raise ValueError('Fortress network roster differs from the frozen run.')
    addresses = set()
    for name, endpoint in zip(players, endpoints):
        if not isinstance(endpoint, dict) or set(endpoint) != {'name', 'address', 'port'}:
            raise ValueError('Invalid Fortress network player.')
        if _name(endpoint['name']) != name:
            raise ValueError('Fortress player names differ from the frozen run.')
        address = str(ipaddress.IPv4Address(endpoint['address']))
        if ipaddress.IPv4Address(address).is_unspecified or ipaddress.IPv4Address(address).is_multicast:
            raise ValueError('Use private network IPv4 addresses for Fortress players.')
        if type(endpoint['port']) is not int:
            raise ValueError('Invalid Fortress game port.')
        pair = (address, _port(endpoint['port']))
        if pair in addresses:
            raise ValueError('Fortress players cannot share the same game endpoint.')
        addresses.add(pair)


def spawn_data(plan, map_data, *, slot, endpoints, game_speed=2):
    """Humans occupy Multi1..N, ordered by their fixed distinct colors."""
    from .engine import spawn_data as solo_spawn_data
    validate_endpoints(plan, endpoints)
    players = plan['coop_players']
    if type(slot) is not int or not 0 <= slot < len(players):
        raise ValueError('Invalid local Fortress player.')
    base = all_section_value_maps_preserve(
        solo_spawn_data(plan, map_data, game_speed=game_speed).decode('latin-1').splitlines())
    countries = section_value_map(IniLines(map_data.decode('latin-1').splitlines()), 'Countries')
    indices = {country: key for key, country in countries.items()}
    friends = coalition(plan)
    human_count = len(players)
    colors = [0, 4, 5]
    settings = dict(base['Settings'])
    settings.update(Name=players[slot], Host='Yes' if slot == 0 else 'No',
                    Side=indices[friends[slot][0]], Color=str(colors[slot]),
                    PlayerCount=str(human_count),
                    AIPlayers=str(3 + len(friends) - human_count),
                    Port=str(endpoints[slot]['port']), BuildOffAlly='Yes')
    sections = {'Settings': settings, 'SpawnLocations': {},
                'HouseCountries': {}, 'HouseColors': {}, 'HouseHandicaps': {}}
    for index, peer in enumerate(i for i in range(human_count) if i != slot):
        sections[f'Other{index + 1}'] = {
            'Name': players[peer], 'Side': indices[friends[peer][0]],
            'Color': str(colors[peer]), 'IsSpectator': 'No',
            'Ip': endpoints[peer]['address'], 'Port': str(endpoints[peer]['port']),
        }
    for index, (_, _, waypoint) in enumerate(friends[:human_count], 1):
        sections['SpawnLocations'][f'Multi{index}'] = str(waypoint)
    enemies = []
    for index, waypoint in enumerate(plan['map']['enemy_waypoints']):
        house = human_count + index + 1
        enemies.append(house - 1)
        key = f'Multi{house}'
        sections['SpawnLocations'][key] = str(waypoint)
        sections['HouseCountries'][key] = indices[f'FFENEMY{index + 1}']
        sections['HouseColors'][key] = str(index + 1)
        sections['HouseHandicaps'][key] = str(2 - plan['engine_difficulty'])
    friendly_houses = list(range(human_count))
    for index, (actor, _, waypoint) in enumerate(friends[human_count:], human_count + 4):
        key = f'Multi{index}'
        friendly_houses.append(index - 1)
        sections['SpawnLocations'][key] = str(waypoint)
        sections['HouseCountries'][key] = indices[actor]
        sections['HouseColors'][key] = str(colors[len(friendly_houses) - 1])
        sections['HouseHandicaps'][key] = str(2 - plan['engine_difficulty'])
    ordinals = ('One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven')
    for team in (friendly_houses, enemies):
        for house in team:
            sections[f'Multi{house + 1}_Alliances'] = {
                'HouseAlly' + ordinal: str(other)
                for ordinal, other in zip(ordinals, (other for other in team if other != house))}
    return '\r\n'.join(line for section, values in sections.items()
                       for line in (f'[{section}]', *(f'{key}={value}' for key, value in values.items()), '')).encode('latin-1')


def result_identity(run):
    """Resolve the local score row and exclude only that house's setup transfers."""
    slot = run.get('coop_player', 0)
    plan = run['plan']
    if not plan.get('coop_players'):
        return 'Commander', plan.get('initial_transfer_kills', 0), None
    return (plan['coop_players'][slot], plan['coop_initial_transfer_kills'][slot], slot)
