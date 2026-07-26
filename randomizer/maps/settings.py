"""Launch-time map appearance settings."""

import hashlib

from randomizer.core.collections import unique_in_order
from randomizer.maps.ini import (
    action_group_tokens,
    append_section_entry,
    find_section_bounds,
    parse_action_groups,
)
from randomizer.maps.hooks import unique_section_key
from randomizer.maps.houses import (
    map_house_records,
    player_controlled_houses,
    player_house_from_map,
)


BUILTIN_EVA_ACTION_INDEXES = {
    'allied': 0,
    'russian': 1,
    'yuri': 2,
}


def mission_house_color_rules(
    lines,
    player_color='Default',
    rainbowizer=False,
    rainbow_colors=(),
    random_key='',
):
    """Return deterministic per-House color overrides for one launch."""
    records = map_house_records(lines)
    player_houses = set(player_controlled_houses(lines, records=records))
    if not player_houses:
        player_house = player_house_from_map(lines, records=records)
        if player_house:
            player_houses.add(player_house)

    rules = {}
    selected_color = str(player_color or '').strip()
    if selected_color and selected_color.lower() != 'default':
        for house in player_houses:
            rules[house] = {'Color': selected_color}

    if not rainbowizer:
        return rules

    colors = unique_in_order(
        str(color or '').strip()
        for color in rainbow_colors
        if str(color or '').strip()
        and str(color).strip().lower() != selected_color.lower()
    )
    if not colors:
        return rules

    def is_neutral_house(name, record):
        side = str(record.get('side') or '').strip().lower()
        identities = {
            str(name or '').removesuffix(' House').strip().lower(),
            str(record.get('country') or '').strip().lower(),
            str(record.get('parent_country') or '').strip().lower(),
        }
        return (
            side in {'civilian', 'mutant'}
            or bool(identities.intersection({'neutral', 'special', 'civilian'}))
        )

    ai_houses = [
        name
        for name, record in records.items()
        if name not in player_houses and not is_neutral_house(name, record)
    ]
    key = str(random_key or '')
    ai_houses.sort(
        key=lambda name: hashlib.sha256(
            f'{key}|house|{name.lower()}'.encode('utf-8')
        ).digest()
    )
    colors.sort(
        key=lambda color: hashlib.sha256(
            f'{key}|color|{color.lower()}'.encode('utf-8')
        ).digest()
    )
    for index, house in enumerate(ai_houses):
        rules[house] = {'Color': colors[index % len(colors)]}
    return rules


def mission_eva_voice_rules(selection, voice_tags, random_key=''):
    """Return Side overrides, selected label, and Ares action-148 index."""
    selection = str(selection or '').strip()
    tags = {
        str(label): str(tag)
        for label, tag in (voice_tags or {}).items()
        if str(label).strip() and str(tag).strip()
    }
    if selection.lower() in {'', 'mission default'}:
        return {}, 'Mission default', None
    if selection.lower() == 'random':
        labels = sorted(
            tags,
            key=lambda label: hashlib.sha256(
                f'{random_key}|eva|{label.lower()}'.encode('utf-8')
            ).digest(),
        )
        if not labels:
            return {}, 'Mission default', None
        selection = labels[0]
    tag = tags.get(selection)
    if not tag:
        return {}, 'Mission default', None
    tag_lower = tag.lower()
    action_index = BUILTIN_EVA_ACTION_INDEXES.get(tag_lower)
    if action_index is None:
        custom_tags = unique_in_order(
            configured_tag
            for configured_tag in tags.values()
            if configured_tag.lower() not in BUILTIN_EVA_ACTION_INDEXES
        )
        action_index = 3 + next(
            (
                index
                for index, configured_tag in enumerate(custom_tags)
                if configured_tag.lower() == tag_lower
            ),
            0,
        )
    return (
        {
            side: {'EVA.Tag': tag}
            for side in ('GDI', 'Nod', 'ThirdSide', 'FourthSide')
        },
        selection,
        action_index,
    )


def apply_mission_eva_voice(lines, house, action_index):
    """Force the selected EVA at map start and after native re-enable actions.

    Map-local Side fields are retained as rules documentation/fallback, but
    Mental Omega campaign launches do not reliably apply them to the already
    created human player. Ares action 148 changes the live player's EVA.
    Native ``-1`` actions still silence EVA for authored cinematics.
    """
    if action_index is None:
        return '', 0
    action_index = int(action_index)
    if action_index < 0:
        return '', 0

    rewritten = 0
    start, end = find_section_bounds(lines, 'Actions')
    if start is not None:
        for line_index in range(start + 1, end):
            line = lines[line_index]
            if '=' not in line:
                continue
            key, value = line.split('=', 1)
            declared_count, groups = parse_action_groups(value)
            if declared_count != len(groups):
                continue
            changed = False
            for group in groups:
                if (
                    len(group) == 8
                    and group[0] == '148'
                    and group[2] != '-1'
                    and group[2] != str(action_index)
                ):
                    group[2] = str(action_index)
                    changed = True
                    rewritten += 1
            if changed:
                lines[line_index] = (
                    f'{key}={declared_count},'
                    f'{",".join(action_group_tokens(groups))}'
                )

    house = str(house or '').strip()
    if not house:
        return '', rewritten
    trigger_id = unique_section_key(
        lines,
        ('Events', 'Actions', 'Triggers'),
        'RNGEV',
    )
    tag_id = unique_section_key(lines, ('Tags',), 'RNEVT')
    name = 'MOR Selected EVA'
    append_section_entry(lines, 'Events', trigger_id, '1,13,0,0')
    append_section_entry(
        lines,
        'Actions',
        trigger_id,
        f'1,148,0,{action_index},0,0,0,0,A',
    )
    append_section_entry(
        lines,
        'Triggers',
        trigger_id,
        f'{house},<none>,{name},0,1,1,1,0',
    )
    append_section_entry(lines, 'Tags', tag_id, f'0,{name} 1,{trigger_id}')
    return trigger_id, rewritten
