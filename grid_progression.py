"""Pure progression rules for the launcher's grid mode.

The UI stores this structure directly in the run-state JSON.  Keeping the
topology here makes it possible to inspect and test progression without a
Tkinter window or a running game.
"""

from __future__ import annotations


LOCKED = 'locked'
UNLOCKED = 'unlocked'
COMPLETED = 'completed'
VALID_STATES = {LOCKED, UNLOCKED, COMPLETED}


def _positive_int(value, name):
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValueError(f'{name} must be a positive integer') from None
    if value < 1:
        raise ValueError(f'{name} must be a positive integer')
    return value


def trimmed_cells(width, height, node_count, required_cells=None):
    """Return row-major cells with incomplete grids trimmed at two corners.

    Top-left and bottom-right are always retained.  Cells furthest from the
    top-left-to-bottom-right diagonal are removed first, which produces the
    familiar clipped top-right/bottom-left corners.  A connected orthogonal
    path between start and goal therefore requires at least ``W + H - 1``
    nodes (except for a one-dimensional grid, where every cell is required).
    """
    width = _positive_int(width, 'width')
    height = _positive_int(height, 'height')
    node_count = _positive_int(node_count, 'node_count')
    capacity = width * height
    if node_count > capacity:
        raise ValueError(f'{node_count} nodes do not fit in a {width}x{height} grid')

    minimum = width + height - 1
    if node_count < minimum:
        raise ValueError(
            f'a connected {width}x{height} grid needs at least {minimum} nodes'
        )

    cells = [(x, y) for y in range(height) for x in range(width)]
    if node_count == capacity:
        return cells

    # Start with a balanced orthogonal staircase between both required
    # corners. This is the sparsest valid shape and guarantees connectivity.
    path = [(0, 0)]
    x = y = 0
    while (x, y) != (width - 1, height - 1):
        if x == width - 1:
            y += 1
        elif y == height - 1:
            x += 1
        else:
            right_error = abs((x + 1) * (height - 1) - y * (width - 1))
            down_error = abs(x * (height - 1) - (y + 1) * (width - 1))
            if right_error <= down_error:
                x += 1
            else:
                y += 1
        path.append((x, y))

    path_set = set(path)
    required_cells = set(required_cells or ())
    if not required_cells.issubset(cells):
        raise ValueError('required cells must be inside the grid')
    path_set.update(required_cells)
    if node_count < len(path_set):
        raise ValueError(
            f'the selected start layout needs at least {len(path_set)} nodes in this grid'
        )

    # Grow outward from the staircase. Manhattan-distance layers ensure every
    # partially added layer still touches an earlier layer, while the diagonal
    # error makes the omitted cells collect at top-right and bottom-left.
    def keep_priority(cell):
        x, y = cell
        path_distance = min(abs(x - px) + abs(y - py) for px, py in path)
        diagonal_error = abs(x * (height - 1) - y * (width - 1))
        return (path_distance, diagonal_error, x + y, x)

    extras = sorted((cell for cell in cells if cell not in path_set), key=keep_priority)
    keep = path_set | set(extras[:node_count - len(path_set)])
    result = [cell for cell in cells if cell in keep]
    if not _is_connected(result):
        # This is defensive: the diagonal band is connected for all supported
        # counts, but a clear error is preferable if its ordering is changed.
        raise ValueError('corner trimming produced a disconnected grid')
    return result


def _is_connected(cells):
    cells = set(cells)
    if not cells:
        return False
    seen = set()
    pending = [next(iter(cells))]
    while pending:
        cell = pending.pop()
        if cell in seen:
            continue
        seen.add(cell)
        x, y = cell
        pending.extend(
            neighbor for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
            if neighbor in cells and neighbor not in seen
        )
    return seen == cells


def automatic_dimensions(node_count, two_start_positions=False):
    """Choose a dense landscape grid from the mission count alone."""
    node_count = _positive_int(node_count, 'node_count')
    candidates = []
    for width in range(1, node_count + 1):
        for height in range(1, width + 1):
            if two_start_positions and (width < 2 or height < 2):
                continue
            # Avoid technically exact but unusable strips such as 7x1. Exact
            # factor pairs up to 2.5:1 still win over rectangles with gaps.
            if node_count > 2 and width / height > 2.5:
                continue
            minimum_nodes = width + height - 1 + (1 if two_start_positions else 0)
            if width * height < node_count or node_count < minimum_nodes:
                continue
            candidates.append((width, height))

    if not candidates:
        if two_start_positions:
            raise ValueError('two start positions require at least four missions')
        return (node_count, 1)
    return min(
        candidates,
        key=lambda size: (
            size[0] * size[1] - node_count,
            abs(size[0] - size[1]),
            size[0] * size[1],
        ),
    )


def _layout_cells(node_count, two_start_positions=False):
    width, height = automatic_dimensions(node_count, two_start_positions)
    required_starts = {(1, 0), (0, 1)} if two_start_positions else set()
    cells = trimmed_cells(
        width,
        height,
        node_count,
        required_cells=required_starts,
    )
    return width, height, cells


def _protected_opening_cells(cells, two_start_positions=False):
    """Return starts and every cell one move from a start, in grid order."""
    cells = list(cells)
    cell_set = set(cells)
    starts = {(1, 0), (0, 1)} if two_start_positions else {(0, 0)}
    protected = set(starts) & cell_set
    for x, y in tuple(protected):
        protected.update(
            cell
            for cell in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
            if cell in cell_set
        )
    return [cell for cell in cells if cell in protected]


def grid_opening_mission_count(node_count, two_start_positions=False):
    """Count missions that must be low-level around the grid entrance."""
    _, _, cells = _layout_cells(node_count, two_start_positions)
    return len(_protected_opening_cells(cells, two_start_positions))


def grid_opening_mission_codes(grid):
    """Return mission codes at a start or one orthogonal move from one."""
    nodes = grid.get('nodes', {}) if isinstance(grid, dict) else {}
    positioned = {
        (node.get('x'), node.get('y')): code
        for code, node in nodes.items()
        if isinstance(node, dict)
    }
    cells = sorted(positioned, key=lambda cell: (cell[1], cell[0]))
    opening_cells = _protected_opening_cells(
        cells,
        bool(grid.get('two_start_positions', False)),
    )
    return [positioned[cell] for cell in opening_cells]


def create_grid(mission_codes, two_start_positions=False, protect_opening=False):
    """Create a serializable grid state for the supplied mission content."""
    mission_codes = list(mission_codes)
    if not mission_codes or len(set(mission_codes)) != len(mission_codes):
        raise ValueError('mission codes must be a non-empty unique sequence')

    width, height, cells = _layout_cells(len(mission_codes), two_start_positions)
    placement_cells = cells
    if protect_opening:
        opening_cells = _protected_opening_cells(cells, two_start_positions)
        opening_set = set(opening_cells)
        placement_cells = opening_cells + [cell for cell in cells if cell not in opening_set]

    nodes = {
        code: {'x': x, 'y': y, 'state': LOCKED}
        for code, (x, y) in zip(mission_codes, placement_cells)
    }
    grid = {
        'layout_version': 3,
        'width': int(width),
        'height': int(height),
        'two_start_positions': bool(two_start_positions),
        'goal': mission_codes[-1],
        'nodes': nodes,
    }
    refresh_states(grid, [])
    return grid


def node_at(grid, x, y):
    for code, node in grid.get('nodes', {}).items():
        if node.get('x') == x and node.get('y') == y:
            return code
    return None


def neighbors(grid, code):
    """Return the orthogonal neighbor IDs of ``code`` in stable grid order."""
    node = grid.get('nodes', {}).get(code)
    if node is None:
        return []
    x, y = node['x'], node['y']
    positions = {(item['x'], item['y']): item_code for item_code, item in grid['nodes'].items()}
    return [
        positions[position]
        for position in ((x, y - 1), (x - 1, y), (x + 1, y), (x, y + 1))
        if position in positions
    ]


def starting_nodes(grid):
    if not grid.get('two_start_positions'):
        start = node_at(grid, 0, 0)
        return [start] if start else []
    starts = [node_at(grid, 1, 0), node_at(grid, 0, 1)]
    return [code for code in starts if code]


def refresh_states(grid, completed_codes):
    """Update and return every node's explicit locked/open/completed state."""
    nodes = grid.get('nodes', {})
    completed = set(completed_codes) & set(nodes)
    unlocked = set(starting_nodes(grid))
    for code in completed:
        unlocked.update(neighbors(grid, code))
    if grid.get('goal') in completed:
        unlocked.update(nodes)

    for code, node in nodes.items():
        node['state'] = COMPLETED if code in completed else UNLOCKED if code in unlocked else LOCKED
    return {code: node['state'] for code, node in nodes.items()}


def completing_unlocks(grid, code):
    """Query which currently locked nodes would open after completing code."""
    nodes = grid.get('nodes', {})
    if code not in nodes:
        return []
    if code == grid.get('goal'):
        return [
            node_code
            for node_code, node in nodes.items()
            if node_code != code and node.get('state') == LOCKED
        ]
    return [
        neighbor
        for neighbor in neighbors(grid, code)
        if nodes[neighbor].get('state') == LOCKED
    ]


def is_complete(grid):
    """A grid run is complete when its designated endgoal is cleared."""
    nodes = grid.get('nodes', {})
    goal = grid.get('goal')
    return bool(nodes and goal in nodes) and nodes[goal].get('state') == COMPLETED
