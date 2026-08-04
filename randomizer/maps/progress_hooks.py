"""Plan and inject objective/victory progress markers."""

from randomizer.core.collections import unique_in_order
from randomizer.maps.hooks import (
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

NEXT_OBJECTIVE_CHECK_ID = '__next_objective__'


def _action_has_real_objective_completion(groups):
    """Return whether Action 19 commits an objective completion."""
    return any(
        len(group) >= 3
        and group[0] == '19'
        and group[2].lower() == 'objectivecomplete'
        for group in groups
    )


def pending_check_hook_plan(lines, checks, configured_victory_action_ids=()):
    """Hook real completion events and the mission victory action."""
    objective_action_ids = action_line_ids(
        lines,
        lambda groups: (
            _action_has_real_objective_completion(groups)
            and not action_has_code(groups, 1)
            and not action_has_code(groups, 67)
        ),
    )
    # A few legacy maps only expose EVA/UI completion actions. Retain the
    # old signatures as a fallback, but never mix echoes with Action 19.
    if not objective_action_ids:
        objective_action_ids = action_line_ids(
            lines,
            lambda groups: (
                action_has_objective_complete(groups)
                and not action_has_code(groups, 1)
                and not action_has_code(groups, 67)
            ),
        )
    available_action_ids = set(action_line_ids(lines, lambda _groups: True))
    configured_victory_action_ids = [
        action_id
        for action_id in configured_victory_action_ids
        if action_id in available_action_ids
    ]
    victory_action_ids = unique_in_order(
        configured_victory_action_ids
        + action_line_ids(lines, lambda groups: action_has_code(groups, 1))
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
    completed_objectives = sum(
        1 for check in objective_checks if check.get('unlocked')
    )
    for index, action_id in enumerate(objective_action_ids, start=1):
        plan.append(({
            'id': NEXT_OBJECTIVE_CHECK_ID,
            'marker_id': f'E{index:04d}',
            'name': 'objective completion event',
        }, action_id))

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
    return plan, missing_victory, completed_objectives


def inject_check_markers(lines, mission_code, plan, house):
    """Inject bounded marker actions and return marker map plus failures."""
    markers = {}
    failures = []
    for index, (check, action_id) in enumerate(plan, start=1):
        marker = hook_marker_name(
            mission_code,
            check.get('marker_id', check.get('id', f'check_{index}')),
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
