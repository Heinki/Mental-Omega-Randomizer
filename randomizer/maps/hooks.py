"""Objective/victory marker discovery and bounded map-action editing."""

import re

from randomizer.maps.ini import (
    action_group_tokens,
    append_section_entry,
    append_section_list_entry,
    find_section_bounds,
    parse_action_groups,
    section_lines,
    section_value_map_preserve,
)
from randomizer.config.static import static_config_section


_ENGINE_LIMITS = static_config_section(
    'map_rules.json',
    'engine_limits',
    dict,
)
MAX_MAP_ACTION_LINE_LENGTH = int(_ENGINE_LIMITS['max_map_action_line_length'])


def sanitize_marker_part(value, max_length=12):
    """Return uppercase alphanumeric marker component."""
    cleaned = re.sub(r'[^A-Za-z0-9]', '', value or '').upper()
    return (cleaned or 'UNK')[:max_length]


def action_has_code(groups, code):
    """Return whether parsed action groups contain action code."""
    return any(group and group[0] == str(code) for group in groups)


def action_has_objective_complete(groups):
    """Recognize supported Mental Omega objective-complete signatures."""
    for group in groups:
        if len(group) < 3:
            continue
        action_code = group[0]
        parameter = group[2].lower()
        if action_code == '19' and parameter == 'objectivecomplete':
            return True
        if action_code == '21' and parameter == 'eva_objectivecomplete':
            return True
        if action_code == '11' and parameter == 'mission:objc':
            return True
    return False


def action_line_ids(lines, predicate):
    """Return Action keys whose parsed groups satisfy predicate."""
    start, end = find_section_bounds(lines, 'Actions')
    if start is None:
        return []

    ids = []
    for line in lines[start + 1:end]:
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        count, groups = parse_action_groups(value)
        if count and predicate(groups):
            ids.append(key.strip())
    return ids


def trigger_action_ids_by_name(lines, patterns):
    """Return Action IDs whose same-key Trigger name contains one pattern."""
    start, end = find_section_bounds(lines, 'Triggers')
    if start is None:
        return []

    lowered_patterns = [pattern.lower() for pattern in patterns]
    action_start, _ = find_section_bounds(lines, 'Actions')
    if action_start is None:
        return []
    action_ids = {
        line.split('=', 1)[0].strip().lower()
        for line in section_lines(lines, 'Actions')
        if '=' in line
    }

    ids = []
    for line in lines[start + 1:end]:
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        if key.lower() not in action_ids:
            continue
        value_lower = value.lower()
        if any(pattern in value_lower for pattern in lowered_patterns):
            ids.append(key)
    return ids


def append_action_to_action_id(lines, action_id, action_tokens):
    """Append one eight-token action without crossing parser byte limit."""
    start, end = find_section_bounds(lines, 'Actions')
    if start is None:
        return False

    for index in range(start + 1, end):
        line = lines[index]
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        if key.strip().lower() != action_id.lower():
            continue
        tokens = [token.strip() for token in value.split(',')]
        try:
            tokens[0] = str(int(tokens[0]) + 1)
        except (ValueError, IndexError):
            return False
        tokens.extend(action_tokens)
        replacement = f'{key}={",".join(tokens)}'
        if len(replacement.encode('utf-8')) > MAX_MAP_ACTION_LINE_LENGTH:
            return False
        lines[index] = replacement
        return True
    return False


def insert_actions_before_codes(lines, action_id, action_tokens_list, before_codes):
    """Insert actions before first matching terminal action."""
    actions = [list(tokens) for tokens in action_tokens_list]
    if not actions or any(len(tokens) != 8 for tokens in actions):
        return False

    wanted_codes = {str(code) for code in before_codes}
    start, end = find_section_bounds(lines, 'Actions')
    if start is None:
        return False

    for index in range(start + 1, end):
        line = lines[index]
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        if key.strip().lower() != action_id.lower():
            continue

        tokens = [token.strip() for token in value.split(',')]
        try:
            declared_count = int(tokens[0])
        except (ValueError, IndexError):
            return False

        insert_group = None
        for group_index in range(min(declared_count, (len(tokens) - 1) // 8)):
            if tokens[1 + group_index * 8] in wanted_codes:
                insert_group = group_index
                break
        if insert_group is None:
            return False

        insert_at = 1 + insert_group * 8
        inserted_tokens = [token for action in actions for token in action]
        tokens[insert_at:insert_at] = inserted_tokens
        tokens[0] = str(declared_count + len(actions))
        replacement = f'{key}={",".join(tokens)}'
        if len(replacement.encode('utf-8')) > MAX_MAP_ACTION_LINE_LENGTH:
            return False
        lines[index] = replacement
        return True
    return False


def append_parallel_global_hook(lines, source_action_id, marker_action, marker_name):
    """Mirror global objective trigger when native action line is full."""
    events = section_value_map_preserve(lines, 'Events')
    triggers = section_value_map_preserve(lines, 'Triggers')
    source_event = events.get(source_action_id)
    source_trigger = triggers.get(source_action_id)
    if not source_event or not source_trigger or len(marker_action) != 8:
        return False

    event_tokens = [token.strip() for token in source_event.split(',')]
    if (
        len(event_tokens) < 2
        or event_tokens[0] != '1'
        or event_tokens[1] not in {'11', '61'}
    ):
        return False

    trigger_tokens = [token.strip() for token in source_trigger.split(',')]
    if len(trigger_tokens) != 8:
        return False

    hook_trigger_id = unique_section_key(
        lines,
        ('Events', 'Actions', 'Triggers'),
        'RNH00',
    )
    hook_tag_id = unique_section_key(lines, ('Tags',), 'RHT00')
    source_lower = source_action_id.lower()
    mirrored_lines = []
    mirrored_enable = False
    start, end = find_section_bounds(lines, 'Actions')
    if start is None:
        return False

    for index in range(start + 1, end):
        line = lines[index]
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        declared_count, groups = parse_action_groups(value)
        if declared_count != len(groups):
            continue

        expanded = []
        changed = False
        for group in groups:
            expanded.append(group)
            if group[0] not in {'53', '54'} or group[2].lower() != source_lower:
                continue
            mirrored = list(group)
            mirrored[2] = hook_trigger_id
            expanded.append(mirrored)
            changed = True
            if group[0] == '53':
                mirrored_enable = True
        if not changed:
            continue

        replacement = (
            f'{key}={len(expanded)},'
            f'{",".join(action_group_tokens(expanded))}'
        )
        if len(replacement.encode('utf-8')) > MAX_MAP_ACTION_LINE_LENGTH:
            return False
        mirrored_lines.append((index, replacement))

    source_starts_disabled = trigger_tokens[3] == '1'
    if source_starts_disabled and not mirrored_enable:
        return False

    for index, replacement in mirrored_lines:
        lines[index] = replacement

    trigger_tokens[2] = marker_name
    append_section_entry(lines, 'Events', hook_trigger_id, source_event)
    append_section_entry(
        lines,
        'Actions',
        hook_trigger_id,
        f'1,{",".join(marker_action)}',
    )
    append_section_entry(lines, 'Triggers', hook_trigger_id, ','.join(trigger_tokens))
    append_section_entry(lines, 'Tags', hook_tag_id, f'0,{marker_name} 1,{hook_trigger_id}')
    return True


def unique_section_key(lines, sections, prefix):
    """Allocate unused key across one or more map sections."""
    existing = set()
    for section in sections:
        for line in section_lines(lines, section):
            if '=' in line:
                existing.add(line.split('=', 1)[0].strip().lower())
    for index in range(1, 1000):
        candidate = f'{prefix}{index:03d}'
        if candidate.lower() not in existing:
            return candidate
    raise RuntimeError(f'Could not allocate a unique {prefix} map key.')


def append_hook_team(lines, team_id, taskforce_id, script_id, marker_name, house):
    """Append empty marker TaskForce, ScriptType, and TeamType."""
    append_section_list_entry(lines, 'TaskForces', taskforce_id)
    append_section_list_entry(lines, 'ScriptTypes', script_id)
    append_section_list_entry(lines, 'TeamTypes', team_id)

    lines.extend([
        '',
        f'[{taskforce_id}]',
        f'Name={marker_name} Empty',
        'Group=-1',
        '',
        f'[{script_id}]',
        '0=11,5',
        f'Name={marker_name} Guard',
        '',
        f'[{team_id}]',
        'Max=1',
        'Full=no',
        f'Name={marker_name}',
        'Group=-1',
        f'House={house}',
        f'Script={script_id}',
        'Whiner=no',
        'Droppod=no',
        'Suicide=no',
        'Loadable=no',
        'Prebuild=no',
        'Priority=1',
        'Waypoint=A',
        'Annoyance=no',
        'IonImmune=no',
        'Recruiter=yes',
        'Reinforce=no',
        f'TaskForce={taskforce_id}',
        'TechLevel=0',
        'Aggressive=no',
        'Autocreate=no',
        'GuardSlower=no',
        'OnTransOnly=no',
        'AvoidThreats=no',
        'LooseRecruit=no',
        'VeteranLevel=1',
        'IsBaseDefense=no',
        'UseTransportOrigin=no',
        'MindControlDecision=0',
        'OnlyTargetHouseEnemy=no',
        'TransportsReturnOnUnload=no',
        'AreTeamMembersRecruitable=no',
    ])


def hook_marker_name(mission_code, check_id):
    """Return stable debug-log marker name for one check."""
    if check_id == 'victory':
        suffix = 'VIC'
    else:
        suffix = sanitize_marker_part(check_id.replace('objective_', 'O'), 5)
    return f'MOR_{sanitize_marker_part(mission_code, 10)}_{suffix}'
