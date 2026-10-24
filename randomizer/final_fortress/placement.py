"""Playable isometric bounds and complete building-foundation validation."""

import re

from randomizer.maps.ini import all_section_value_maps_preserve


def validate_enemy_arrivals(writer, plan):
    """Keep hostile waves beside their bases and friendly deliveries on their aprons.

    Validate the emitted action's coordinates, not just the TeamType's label.
    This also protects frozen plans, which still use their original base starts.
    """
    from randomizer.maps.ini import parse_action_groups, section_value_map

    points = {**section_value_map(writer.lines, 'Waypoints'),
              **writer.sections.get('Waypoints', {})}
    definition = plan['map']

    def position(waypoint):
        value = points.get(str(waypoint), '')
        if not value.isdigit():
            raise ValueError(f'Missing Final Fortress arrival waypoint {waypoint}.')
        cell = int(value)
        return cell % 1000, cell // 1000

    friendly = [position(waypoint) for waypoint in (
        definition['player_waypoint'], *plan.get('allied_waypoints', []))]
    expected = {}
    from .player_perks import coalition
    friendly_arrivals = {actor: chr(65 + 10 + index)
                         for index, (actor, _, _) in enumerate(coalition(plan))}
    for index, waypoint in enumerate(definition['enemy_waypoints']):
        base = position(waypoint)
        arrival = 16 + index if plan.get('plan_version', 1) >= 16 else waypoint
        x, y = position(arrival)
        # The entire 5x3 apron must remain within sixteen cells of its own
        # start and outside the thirty-two-cell friendly expansion buffer.
        cells = {(x + dx, y + dy) for dx in range(-2, 3) for dy in range(-1, 2)}
        if any(max(abs(cx - base[0]), abs(cy - base[1])) > 16
               or any(max(abs(cx - fx), abs(cy - fy)) < 32 for fx, fy in friendly)
               for cx, cy in cells):
            raise ValueError('Final Fortress enemy arrivals must stay beside their own base and away from friendly bases.')
        expected[f'FFENEMY{index + 1}'] = (chr(65 + waypoint), chr(65 + arrival))
    for value in writer.sections.get('Actions', {}).values():
        for action in parse_action_groups(value)[1]:
            if action[0] not in ('7', '80'):
                continue
            team = writer.sections.get(action[2], {})
            name = team.get('Name', '')
            if name.startswith('Fortress friendly arrival '):
                waypoint = friendly_arrivals.get(team.get('House'))
                if action[0] != '80' or waypoint is None or action[7] != waypoint or team.get('Waypoint') != waypoint:
                    raise ValueError('Final Fortress friendly reinforcement has no explicit owned arrival waypoint.')
                continue
            if not name.startswith(('Final Fortress wave ', 'Final Fortress AI controller')):
                continue
            owner = team.get('House')
            target = expected.get(owner)
            waypoint = target[1 if name.startswith('Final Fortress wave ') else 0] if target else None
            if action[0] != '80' or action[7] != waypoint or team.get('Waypoint') != waypoint:
                raise ValueError('Final Fortress enemy reinforcement action has no explicit safe spawn waypoint.')


class PlayableBounds:
    def __init__(self, section):
        row = {key.lower(): value for key, value in section.items()}
        size = list(map(int, row['size'].split(',')))
        local = list(map(int, row['localsize'].split(',')))
        if len(size) != 4 or len(local) != 4 or min(local[2:]) <= 0:
            raise ValueError('Invalid playable map rectangle.')
        self.width = size[2]
        self.left, self.top, self.width_local, self.height_local = local

    def project(self, x, y, height=0):
        # Native isometric cell top-left, in whole rendered-cell dimensions.
        # See World-Altering Editor GameMath/CellMath.cs; LocalSize is a
        # rendered rectangle, not the bounding box of packed diamond cells.
        return (x - y + self.width - 1) / 2, (x + y - self.width - 1 - height) / 2

    def contains(self, cells, *, margin=0, heights=None, maximum_height=None):
        for x, y in cells:
            levels = [heights.get((x, y), 0)] if heights is not None else [0]
            if maximum_height is not None:
                levels.append(maximum_height)
            for height in levels:
                u, v = self.project(x, y, height)
                if not (self.left + margin <= u and u + 1 <= self.left + self.width_local - margin
                        and self.top + margin <= v and v + 1 <= self.top + self.height_local - margin):
                    return False
        return True


def foundation(row, art):
    image = row.get('Image', '')
    entry = art.get(image.casefold(), {})
    value = row.get('Foundation', entry.get('Foundation', '1x1'))
    match = re.fullmatch(r'(\d+)[xX](\d+)', value)
    if match:
        return {(x, y) for x in range(int(match[1])) for y in range(int(match[2]))}
    if value.lower() != 'custom':
        raise ValueError(f'Unknown building foundation: {image}: {value}.')
    cells = {tuple(map(int, value.split(','))) for key, value in entry.items()
             if re.fullmatch(r'Foundation\.\d+', key)}
    if not cells:
        raise ValueError(f'Empty custom building foundation: {image}.')
    return cells


def installed_art():
    from randomizer.ui.cameos import ART_CACHE_PATH, extract_mix_files_sync
    if not ART_CACHE_PATH.exists() and not extract_mix_files_sync([('ARTMO.INI', ART_CACHE_PATH)]):
        raise ValueError('Installed art foundations are unavailable for safe Fortress placement.')
    return {key.casefold(): value for key, value in all_section_value_maps_preserve(
        ART_CACHE_PATH.read_text(encoding='latin-1').splitlines()).items()}


def deployment_cells(x, y):
    """Reserve the 4x4 yard plus room for native deployment and unit exits."""
    return {(x + dx, y + dy) for dx in range(-3, 4) for dy in range(-3, 4)}


def validate_camp_access(writer, plan):
    """Keep crates and their complete guard formations outside hostile bases."""
    if plan.get('plan_version', 1) < 24:
        return
    from .camps import guard_positions
    from randomizer.maps.ini import section_value_map
    points = section_value_map(writer.lines, 'Waypoints')
    starts = [int(points[str(waypoint)]) for waypoint in plan['map']['enemy_waypoints']]
    friendly = [int(points[str(waypoint)]) for waypoint in (
        plan['map']['player_waypoint'], *plan.get('allied_waypoints', []))]
    centers = []
    for camp in plan['map']['camps']:
        center = camp['position']
        minimum = plan['map'].get('camp_minimum_spacing', 0)
        if any(max(abs(center['x'] - x), abs(center['y'] - y)) < minimum for x, y in centers):
            raise ValueError('Final Fortress camp centers are too close: ' + camp['id'])
        centers.append((center['x'], center['y']))
        for point in [camp['position'], *guard_positions(camp)]:
            if minimum and plan.get('plan_version', 1) >= 29 and any(
                    max(abs(point['x'] - cell % 1000), abs(point['y'] - cell // 1000)) < 32
                    for cell in friendly):
                raise ValueError('Final Fortress camp overlaps a friendly base: ' + camp['id'])
            if any(max(abs(point['x'] - cell % 1000), abs(point['y'] - cell // 1000)) < 40
                   for cell in starts):
                raise ValueError('Final Fortress camp overlaps a protected enemy base: ' + camp['id'])


def generator_access(plan, rules, art):
    """Return actual generator footprints and reserved production/arrival space."""
    from .maps import perk_layout
    from .player_perks import coalition
    generators = []
    reserved = set()
    effects = plan['effects']
    for actor, country, waypoint in coalition(plan):
        layout = perk_layout(plan['map'], waypoint, country)
        if not layout:
            continue
        p = layout['units']
        # Two cells around every side let arrivals turn and leave their apron.
        reserved.update((p['x'] + dx, p['y'] + dy)
                        for dx in range(-2, 7) for dy in range(-2, 5))
        placements = [(kind, layout['buildings'][i]) for i, kind in
                      enumerate(effects.get('starting_buildings', []))]
        placements.extend((kind, layout['power'][i]) for i, kind in
                          enumerate(effects.get('starting_power_buildings', [])))
        for kind, p in placements:
            row = dict(rules[kind])
            row.setdefault('Image', kind)
            cells = {(p['x'] + dx, p['y'] + dy) for dx, dy in foundation(row, art)}
            if int(row.get('Power', '0')) > 0:
                generators.append((actor, kind, p, cells))
            else:
                # Keep native exits and refinery docking edges free on all sides.
                reserved.update((x + dx, y + dy) for x, y in cells
                                for dx in range(-1, 2) for dy in range(-1, 2))
    return generators, reserved


def validate_placements(writer, rules, plan=None):
    """Reject off-map added objects before any runtime files are written.

    Evaluate ground level and the map's audited maximum terrain height (or a
    conservative 14-level allowance) without a platform-specific LZO dependency
    at launch. The terrain audit verifies the configured height bound.
    """
    from randomizer.maps.ini import section_value_map
    bounds = PlayableBounds(section_value_map(writer.lines, 'Map'))
    maximum_height = (plan['map'].get('maximum_terrain_height', 14)
                      if plan and plan.get('plan_version', 1) >= 33 else 14)
    art = installed_art()
    if plan and plan.get('plan_version', 1) >= 37:
        generators, access = generator_access(plan, rules, art)
        for actor, kind, position, cells in generators:
            if cells & access:
                raise ValueError(f'Final Fortress {kind} for {actor} blocks a building exit or reinforcement apron.')
    reserved = set()
    if plan and plan.get('plan_version', 1) >= 23:
        points = section_value_map(writer.lines, 'Waypoints')
        for waypoint in (plan['map']['player_waypoint'], *plan['map']['enemy_waypoints'],
                         *plan.get('allied_waypoints', [])):
            cell = int(points[str(waypoint)])
            reserved.update(deployment_cells(cell % 1000, cell // 1000))
    for category in ('Structures', 'Infantry', 'Units'):
        for value in writer.sections.get(category, {}).values():
            fields = value.split(',')
            kind = fields[1]
            x, y = map(int, fields[3:5])
            row = {**rules.get(kind, {}), **writer.sections.get(kind, {})}
            row.setdefault('Image', kind)
            offsets = foundation(row, art) if category == 'Structures' else {(0, 0)}
            cells = {(x + dx, y + dy) for dx, dy in offsets} or {(x, y)}
            if not bounds.contains(cells, maximum_height=maximum_height):
                raise ValueError(f'Final Fortress {kind} at ({x}, {y}) extends outside playable map bounds.')
            if cells & reserved:
                raise ValueError(f'Final Fortress {kind} at ({x}, {y}) blocks an MCV deployment area.')
