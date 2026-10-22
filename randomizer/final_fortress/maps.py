"""Read-only inspection of the single configured skirmish source."""

import hashlib
from pathlib import Path

from randomizer.maps.ini import IniLines, section_value_map


def inspect_map(game_root, definition):
    """Check source suitability without extracting or rewriting campaign maps."""
    if definition is None:
        raise ValueError('No Final Fortress map is configured.')
    root = Path(game_root).resolve()
    source = (root / definition['source']).resolve()
    if not source.is_relative_to(root):
        raise ValueError('Final Fortress map must be inside the game directory.')
    data = source.read_bytes()
    lines = IniLines(data.decode('latin-1').splitlines())
    basic = section_value_map(lines, 'Basic')
    if basic.get('multiplayeronly') not in {'1', 'yes', 'true'}:
        raise ValueError('Final Fortress requires a multiplayer skirmish map.')
    actors = [definition['player_waypoint'], *definition['enemy_waypoints'],
              *definition.get('allied_waypoints', [])]
    if int(basic.get('maxplayer', '0')) < len(actors):
        raise ValueError('Final Fortress requires enough spawn positions for enemies and configured helpers.')
    if basic.get('ignoreglobalaitriggers', 'no').lower() not in {'0', 'no', 'false'}:
        raise ValueError('This map disables normal skirmish AI triggers.')
    points = section_value_map(lines, 'Waypoints')
    positions = []
    for waypoint in actors:
        value = points.get(str(waypoint), '')
        if not value.isdigit():
            raise ValueError(f'Missing or invalid source waypoint {waypoint}.')
        cell = int(value)
        positions.append({'waypoint': waypoint, 'x': cell % 1000, 'y': cell // 1000})
    size = section_value_map(lines, 'Map').get('size', '').split(',')
    if len(size) != 4 or any(not part.strip().isdigit() for part in size):
        raise ValueError('Invalid skirmish map dimensions.')
    return {
        'source': str(source), 'sha256': hashlib.sha256(data).hexdigest(),
        'width': int(size[2]), 'height': int(size[3]), 'positions': positions,
    }
