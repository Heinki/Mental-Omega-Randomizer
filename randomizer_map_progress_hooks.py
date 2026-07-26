"""Plan and inject objective/victory progress markers."""

from randomizer_collections import unique_in_order
from randomizer_map_hooks import (
    action_has_code,
    action_has_objective_complete,
    action_line_ids,
    append_action_to_action_id,
    append_hook_team,
    append_parallel_global_hook,
    hook_marker_name,
    insert_actions_before_codes,
    trigger_action_ids_by_name,
)


def pending_check_hook_plan(lines, checks):
    """Pair stored checks with map actions before filtering completed checks.

    Pairing first preserves Objective 2 to Action 2 after Objective 1 was
    already completed in an earlier launch.
    """
    objective_action_ids = action_line_ids(
        lines,
        lambda groups: (
            action_has_objective_complete(groups)
            and not action_has_code(groups, 1)
            and not action_has_code(groups, 67)
        ),
    )
    victory_action_ids = unique_in_order(
        action_line_ids(lines, lambda groups: action_has_code(groups, 1))
        + action_line_ids(lines, lambda groups: action_has_code(groups, 67))
        + trigger_action_ids_by_name(
            lines,
            ['[win]', '/win', 'mission victory', 'mission successful'],
        )
    )

    plan = []
    objective_checks = [
        check for check in checks if check.get('id') != 'victory'
    ]
    for check, action_id in zip(objective_checks, objective_action_ids):
        if not check.get('unlocked'):
            plan.append((check, action_id))

    victory_check = next(
        (check for check in checks if check.get('id') == 'victory'),
        None,
    )
    missing_victory = False
    if victory_check and not victory_check.get('unlocked'):
        if victory_action_ids:
            plan.append((victory_check, victory_action_ids[0]))
        else:
            missing_victory = True
    return plan, missing_victory


def inject_check_markers(lines, mission_code, plan, house):
    """Inject bounded marker actions and return marker map plus failures."""
    markers = {}
    failures = []
    for index, (check, action_id) in enumerate(plan, start=1):
        marker = hook_marker_name(
            mission_code,
            check.get('id', f'check_{index}'),
        )
        team_id = f'RND{index:05d}'
        taskforce_id = f'RNT{index:05d}'
        script_id = f'RNS{index:05d}'
        marker_action = ['4', '1', team_id, '0', '0', '0', '0', 'A']

        if check.get('id') == 'victory':
            patched = insert_actions_before_codes(
                lines,
                action_id,
                [marker_action],
                before_codes=('1', '67', '69'),
            )
            if not patched:
                patched = append_action_to_action_id(
                    lines,
                    action_id,
                    marker_action,
                )
        else:
            patched = append_action_to_action_id(
                lines,
                action_id,
                marker_action,
            )
            if not patched:
                patched = append_parallel_global_hook(
                    lines,
                    action_id,
                    marker_action,
                    marker,
                )

        if not patched:
            failures.append((check, action_id))
            continue
        append_hook_team(
            lines,
            team_id,
            taskforce_id,
            script_id,
            marker,
            house,
        )
        markers[marker] = check.get('id')
    return markers, failures
