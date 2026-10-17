"""Preserve existing runs when retiring the old solo house-filtered pool."""

from __future__ import annotations

from randomizer.progression.grid import LOCKED, UNLOCKED


CHALLENGE_CATALOGUE_VERSION = 2


def _neighbors(cell):
    x, y = cell
    return ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))


def _expanded_grid(grid, order, added, completed, unlock_after_goal):
    """Add connected cells while retaining every existing node and the goal."""
    if not isinstance(grid, dict) or not isinstance(grid.get('nodes'), dict):
        return None
    width, height = grid.get('width'), grid.get('height')
    if (type(width) is not int or type(height) is not int
            or width < 1 or height < 1 or set(grid['nodes']) != set(order)
            or grid.get('goal') not in grid['nodes']):
        return None
    nodes = {}
    occupied = set()
    for code, node in grid['nodes'].items():
        if not isinstance(node, dict):
            return None
        x, y = node.get('x'), node.get('y')
        if (type(x) is not int or type(y) is not int
                or not 0 <= x < width or not 0 <= y < height
                or (x, y) in occupied):
            return None
        nodes[code] = dict(node)
        occupied.add((x, y))
    if not occupied:
        return None
    reached = set()
    pending = [next(iter(occupied))]
    while pending:
        cell = pending.pop()
        if cell not in reached:
            reached.add(cell)
            pending.extend(neighbor for neighbor in _neighbors(cell)
                           if neighbor in occupied and neighbor not in reached)
    if reached != occupied:
        return None

    completed_cells = {(node['x'], node['y']) for code, node in nodes.items()
                       if code in completed}
    goal_completed = unlock_after_goal and grid['goal'] in completed
    for code in added:
        cells = [(x, y) for y in range(height) for x in range(width)
                 if (x, y) not in occupied
                 and any(neighbor in occupied for neighbor in _neighbors((x, y)))]
        if not cells:
            # Grow one connected edge, choosing the smaller new rectangle.
            # Keeping positive coordinates preserves both native start cells.
            frontier = [(width, y) for y in range(height)
                        if (width - 1, y) in occupied]
            frontier += [(x, height) for x in range(width)
                         if (x, height - 1) in occupied]
            if not frontier:
                return None
            cells = sorted(frontier, key=lambda cell: (
                max(width, cell[0] + 1) * max(height, cell[1] + 1),
                cell[1], cell[0],
            ))
        x, y = cells[0]
        occupied.add((x, y))
        width, height = max(width, x + 1), max(height, y + 1)
        unlocked = goal_completed or any(
            neighbor in completed_cells for neighbor in _neighbors((x, y))
        )
        nodes[code] = {'x': x, 'y': y, 'state': UNLOCKED if unlocked else LOCKED}
    return {**grid, 'width': width, 'height': height, 'nodes': nodes}


def expand_legacy_challenge_catalogue(state, missions, *, excluded_codes=()):
    """Append only maps omitted by the old complete solo house-filtered pool.

    The caller supplies the full installed catalogue. A run deliberately
    shortened by its mission goal, campaign filter or exclusions is retained.
    New runs should record ``challenge_catalogue_version`` at generation so
    future loads never reinterpret their selected subset as a legacy pool.

    This changes only mission order, grid bounds/new nodes, and the migration
    marker. Seed, mission goal, original endgoal, existing node records, checks
    and rewards remain intact. Added maps are optional and must receive their
    own checks from the existing reward generator. Call on a state copy and
    persist it only after those checks/objectives/plans have been appended.
    Noneligible legacy runs receive the version marker without changing their
    selected missions, so a later preference change cannot expand them.
    """
    if not isinstance(state, dict) or state.get('mission_category') != 'challenge':
        return []
    version = state.get('challenge_catalogue_version')
    if type(version) is int and version >= CHALLENGE_CATALOGUE_VERSION:
        return []
    state['challenge_catalogue_version'] = CHALLENGE_CATALOGUE_VERSION
    if (state.get('challenge_player_count', 1) != 1
            or state.get('campaign_filter', 'All Campaigns') != 'All Campaigns'
            or (state.get('archipelago') or {}).get('enabled')
            or state.get('progression_mode') not in {'Classic', 'Grid Mode', 'Mission List'}
            or excluded_codes):
        return []
    for settings in (state, state.get('mission_pool_settings') or {},
                     state.get('reward_settings') or {}):
        if settings.get('excluded_challenge_mission_codes'):
            return []
    country = state.get('challenge_country')
    registered = {mission['code']: mission for mission in missions}
    compatible = {code for code, mission in registered.items()
                  if country in mission.get('allowed_countries', ())}
    order = state.get('mission_order')
    if (not isinstance(order, list) or len(compatible) not in (18, 19)
            or len(order) != len(compatible) or set(order) != compatible
            or type(state.get('mission_goal')) is not int
            or state['mission_goal'] != len(order)):
        return []
    added = [code for code in registered if code not in compatible]
    if not added:
        return []
    grid = None
    if state['progression_mode'] == 'Grid Mode':
        grid = _expanded_grid(
            state.get('grid'), order, added,
            set(state.get('completed_missions', ())),
            bool(state.get('unlock_all_rewards_after_final_grid_mission', False)),
        )
        if grid is None:
            return []
    state['mission_order'] = [*order, *added]
    if grid is not None:
        state['grid'] = grid
    state['challenge_catalogue_version'] = CHALLENGE_CATALOGUE_VERSION
    return added


def migrate_legacy_challenge_run(state, missions, settings):
    """Return a complete upgraded copy, planning rewards only for added maps."""
    if (not state or state.get('mission_category') != 'challenge'
            or state.get('challenge_catalogue_version') == CHALLENGE_CATALOGUE_VERSION):
        return None
    from copy import deepcopy
    from randomizer.generation.service import RunGenerator
    from randomizer.rewards.arsenal import ARSENAL_MODE, generate_mission_arsenals
    from randomizer.rewards.catalogue import check_rewards

    upgraded = deepcopy(state)
    added = expand_legacy_challenge_catalogue(
        upgraded, missions,
        excluded_codes=(settings.get('generation') or {}).get(
            'excluded_challenge_mission_codes', ()),
    )
    if upgraded == state:
        return None
    if not added:
        return upgraded, []
    planner = RunGenerator(settings, missions)
    planner.state = upgraded
    planner._seed_generation_context = {
        'mission_category': 'challenge',
        'campaign_filter': upgraded.get('campaign_filter', 'All Campaigns'),
        'reward_mode': upgraded.get('reward_mode', 'Standard'),
        'progression_mode': upgraded['progression_mode'],
    }
    saved_settings = upgraded.get('reward_settings') or {}
    if upgraded.get('reward_mode') == ARSENAL_MODE:
        arsenals = generate_mission_arsenals(
            upgraded['seed'], added, saved_settings, saved_settings.get('arsenal'),
        )
        upgraded.setdefault('mission_arsenals', {}).update(arsenals)
    # Reserve every existing planned reward, including unopened checks. Passing
    # the old maps through build_mission_checks would reroll pending rewards.
    existing_checks = upgraded.setdefault('mission_checks', {})
    reserved = [reward for checks in existing_checks.values()
                for check in checks for reward in check_rewards(check)]
    new_checks = planner.build_mission_checks(
        added, upgraded['seed'], earned_rewards=reserved,
        rewards_per_check=upgraded.get('rewards_per_check', 4),
        rewards_on_victory_only=bool(upgraded.get('rewards_on_victory_only', False)),
        use_act_based_reward_multipliers=bool(
            upgraded.get('use_act_based_reward_multipliers', True)),
        progression_mode=upgraded['progression_mode'], grid=upgraded.get('grid'),
        starting_rewards=upgraded.get('starting_rewards', []),
    )
    existing_checks.update(new_checks)
    upgraded.setdefault('mission_objectives', {}).update(
        planner.state_objective_summary(added))
    upgraded.setdefault('reward_queue', []).extend(
        reward for code in added for check in new_checks[code]
        for reward in check_rewards(check))
    # The original enemy inventory is capped across the saved run. Keep those
    # assignments intact rather than rolling another inventory for extra maps.
    return upgraded, added
