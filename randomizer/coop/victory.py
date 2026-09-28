"""Mark authored two-player win actions for host-side completion detection."""

from randomizer.maps.hooks import (
    action_has_code, action_line_ids, append_hook_team,
    hook_marker_name, insert_actions_before_codes,
)
from randomizer.maps.ini import section_value_map_preserve


def victory_marker_name(coop_name: str) -> str:
    return hook_marker_name(coop_name.upper(), 'victory')


def inject_victory_markers(lines: list[str], coop_name: str, player_country: str) -> str:
    """Create empty TeamTypes immediately before every map Action 2 (win)."""
    action_ids = action_line_ids(lines, lambda groups: action_has_code(groups, 2))
    if not action_ids:
        raise ValueError(f'{coop_name} has no supported co-op win action.')
    marker = victory_marker_name(coop_name)
    for index, action_id in enumerate(action_ids, start=1):
        team_id = f'RND{index:05d}'
        taskforce_id = f'RNT{index:05d}'
        script_id = f'RNS{index:05d}'
        for section, value in (
            ('TeamTypes', team_id),
            ('TaskForces', taskforce_id),
            ('ScriptTypes', script_id),
        ):
            if value in section_value_map_preserve(lines, section).values():
                raise ValueError(f'{coop_name} already uses marker ID {value}.')
        marker_action = ['4', '1', team_id, '0', '0', '0', '0', 'A']
        if not insert_actions_before_codes(
            lines, action_id, [marker_action], before_codes=('2',),
        ):
            raise ValueError(f'{coop_name} win action {action_id} cannot fit a progress marker.')
        append_hook_team(lines, team_id, taskforce_id, script_id, marker, player_country)
    return marker
