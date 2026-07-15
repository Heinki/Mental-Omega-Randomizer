"""Small, case-insensitive INI helpers used by map and launcher patching.

Mental Omega maps are INI-like but may contain repeated numeric lists and must
retain their original ordering, so ConfigParser is not suitable here.
"""


def read_text(path):
    return path.read_text(encoding='utf-8', errors='ignore')


def set_ini_value_lines(text, section, key, value):
    lines = text.splitlines()
    output = []
    in_section = False
    section_found = False
    key_written = False
    for line in lines:
        stripped = line.strip()
        is_section = stripped.startswith('[') and stripped.endswith(']')
        if is_section:
            if in_section and not key_written:
                output.append(f'{key}={value}')
                key_written = True
            current = stripped[1:-1].strip()
            in_section = current.lower() == section.lower()
            section_found = section_found or in_section
        elif in_section and '=' in stripped:
            current_key = stripped.split('=', 1)[0].strip()
            if current_key.lower() == key.lower():
                output.append(f'{key}={value}')
                key_written = True
                continue
        output.append(line)
    if in_section and not key_written:
        output.append(f'{key}={value}')
    if not section_found:
        if output and output[-1].strip():
            output.append('')
        output.extend([f'[{section}]', f'{key}={value}'])
    return '\r\n'.join(output) + '\r\n'


def find_section_bounds(lines, section):
    wanted = section.lower()
    start = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('[') and stripped.endswith(']'):
            if start is not None:
                return (start, index)
            if stripped[1:-1].strip().lower() == wanted:
                start = index
    return (None, None) if start is None else (start, len(lines))


def section_lines(lines, section):
    start, end = find_section_bounds(lines, section)
    return [] if start is None else lines[start + 1:end]


def section_value_map(lines, section):
    values = {}
    for line in section_lines(lines, section):
        if '=' in line:
            key, value = line.split('=', 1)
            values[key.strip().lower()] = value.strip()
    return values


def section_value_map_preserve(lines, section):
    values = {}
    for line in section_lines(lines, section):
        if '=' in line:
            key, value = line.split('=', 1)
            values[key.strip()] = value.strip()
    return values


def all_section_value_maps(lines):
    sections = {}
    current_values = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('[') and stripped.endswith(']'):
            current_values = {}
            sections[stripped[1:-1].strip()] = current_values
        elif current_values is not None and '=' in line:
            key, value = line.split('=', 1)
            current_values[key.strip().lower()] = value.strip()
    return sections


def next_numeric_section_index(lines, section):
    highest = -1
    for line in section_lines(lines, section):
        if '=' in line:
            key = line.split('=', 1)[0].strip()
            if key.isdigit():
                highest = max(highest, int(key))
    return highest + 1


def append_section_list_entry(lines, section, value):
    start, end = find_section_bounds(lines, section)
    if start is None:
        if lines and lines[-1].strip():
            lines.append('')
        lines.extend([f'[{section}]', f'0={value}'])
        return
    lines.insert(end, f'{next_numeric_section_index(lines, section)}={value}')


def append_section_entry(lines, section, key, value):
    start, end = find_section_bounds(lines, section)
    if start is None:
        if lines and lines[-1].strip():
            lines.append('')
        lines.extend([f'[{section}]', f'{key}={value}'])
        return
    lines.insert(end, f'{key}={value}')


def parse_action_groups(value):
    tokens = [token.strip() for token in value.split(',')]
    if not tokens:
        return (0, [])
    try:
        count = int(tokens[0])
    except ValueError:
        return (0, [])
    groups = []
    cursor = 1
    while cursor + 7 < len(tokens):
        groups.append(tokens[cursor:cursor + 8])
        cursor += 8
    return (count, groups)


def action_group_tokens(groups):
    return [token for group in groups for token in group]


def merge_ini_section_values(lines, section_values):
    """Merge many sections in one pass instead of rescanning per key."""
    pending = {
        section.lower(): (
            section,
            {key.lower(): (key, value) for key, value in values.items()},
        )
        for section, values in section_values.items()
        if values
    }
    if not pending:
        return

    output = []
    active_values = None
    seen_keys = set()
    found_sections = set()

    def flush_missing_values():
        if active_values is not None:
            for key_lower in sorted(active_values, key=lambda item: active_values[item][0]):
                if key_lower not in seen_keys:
                    key, value = active_values[key_lower]
                    output.append(f'{key}={value}')

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('[') and stripped.endswith(']'):
            flush_missing_values()
            section_key = stripped[1:-1].strip().lower()
            active_key = section_key if section_key in pending and section_key not in found_sections else None
            if active_key is not None:
                found_sections.add(active_key)
                active_values = pending[active_key][1]
                seen_keys = set()
            else:
                active_values = None
                seen_keys = set()
            output.append(line)
            continue
        if active_values is not None and '=' in line:
            key_lower = line.split('=', 1)[0].strip().lower()
            replacement = active_values.get(key_lower)
            if replacement is not None:
                key, value = replacement
                output.append(f'{key}={value}')
                seen_keys.add(key_lower)
                continue
        output.append(line)

    flush_missing_values()
    for section_key, (section, values) in pending.items():
        if section_key in found_sections:
            continue
        if output and output[-1].strip():
            output.append('')
        output.append(f'[{section}]')
        for _, (key, value) in sorted(values.items(), key=lambda item: item[1][0]):
            output.append(f'{key}={value}')
    lines[:] = output
