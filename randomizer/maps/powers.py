"""Startup structures and superweapon grant triggers."""

from ._shared import (
    MAX_MAP_ACTION_LINE_LENGTH,
    SUPERWEAPON_ACTIONS_PER_TRIGGER,
    action_group_tokens,
    append_section_entry,
    comma_items,
    map_house_records,
    next_numeric_section_index,
    player_controlled_houses,
    section_value_map_preserve,
    unique_in_order,
    unique_section_key,
)
from .base import (
    _value_case_insensitive,
)

def _waypoint_label(index):
    """Return FinalAlert's zero-based Excel-style waypoint label."""
    value = int(index) + 1
    label = ''
    while value > 0:
        value, remainder = divmod(value - 1, 26)
        label = chr(ord('A') + remainder) + label
    return label

def _startup_building_placements(
    lines,
    house,
    building_ids,
    reserved_cells=None,
):
    """Choose hidden support-building cells near proven friendly map objects."""
    building_ids = [str(item).strip() for item in building_ids if str(item).strip()]
    if not building_ids:
        return []

    records = map_house_records(lines)
    wanted = str(house or '').strip().lower()
    aliases = {wanted, wanted.replace(' house', '')}
    anchor_aliases = set(aliases)
    for house_name, record in records.items():
        record_aliases = {
            house_name.lower(),
            house_name.replace(' House', '').lower(),
            str(record.get('country') or '').lower(),
        }
        if wanted in record_aliases or aliases.intersection(record_aliases):
            aliases.update(record_aliases)
            # Some campaign missions begin with the human house owning no
            # object, then hand it an allied base. Hidden support buildings
            # still need a proven in-map anchor in those missions.
            for allied_house in record.get('allies') or ():
                allied_wanted = str(allied_house).strip().lower()
                anchor_aliases.update({
                    allied_wanted,
                    allied_wanted.replace(' house', ''),
                })
    anchor_aliases.update(aliases)
    aliases.discard('')

    occupied = set(reserved_cells or ())
    map_objects = []
    friendly_anchors = []
    fallback_anchors = []
    # Structures are stable, playable anchors and much less likely than map
    # edge reinforcement units to sit on an invalid or scripted staging cell.
    for section in ('Structures', 'Units', 'Infantry', 'Aircraft'):
        for value in section_value_map_preserve(lines, section).values():
            tokens = [token.strip() for token in str(value).split(',')]
            if len(tokens) < 5:
                continue
            try:
                cell = (int(tokens[3]), int(tokens[4]))
            except (TypeError, ValueError):
                continue
            occupied.add(cell)
            fallback_anchors.append(cell)
            owner = tokens[0].lower()
            if (
                owner in anchor_aliases
                or owner.replace(' house', '') in anchor_aliases
            ):
                friendly_anchors.append(cell)
            map_objects.append((owner, cell))

    anchors = list(dict.fromkeys(friendly_anchors))
    if not anchors:
        player_houses = {
            name.lower()
            for name in player_controlled_houses(lines, records=records)
        }
        anchors = list(dict.fromkeys(
            cell
            for owner, cell in map_objects
            if owner in player_houses
        ))
    if not anchors:
        anchors = list(dict.fromkeys(fallback_anchors))
    if not anchors:
        return []

    offsets = []
    for radius in range(4, 13):
        offsets.extend((
            (radius, 0), (-radius, 0), (0, radius), (0, -radius),
            (radius, radius), (-radius, radius),
            (radius, -radius), (-radius, -radius),
        ))

    map_size = comma_items(_value_case_insensitive(
        section_value_map_preserve(lines, 'Map'), 'Size', ''
    ))
    try:
        map_center = (
            int(map_size[0]) + (int(map_size[2]) + int(map_size[3])) / 2,
            int(map_size[1]) + (int(map_size[2]) + int(map_size[3])) / 2,
        )
    except (IndexError, TypeError, ValueError):
        map_center = (
            sum(cell[0] for cell in anchors) / len(anchors),
            sum(cell[1] for cell in anchors) / len(anchors),
        )

    startup_placements = []
    for building_number, building_id in enumerate(building_ids):
        chosen = None
        for anchor_number in range(len(anchors)):
            anchor = anchors[(building_number + anchor_number) % len(anchors)]
            inward_offsets = sorted(
                offsets,
                key=lambda offset: (
                    abs(anchor[0] + offset[0] - map_center[0])
                    + abs(anchor[1] + offset[1] - map_center[1]),
                    abs(offset[0]) + abs(offset[1]),
                    offset,
                ),
            )
            for dx, dy in inward_offsets:
                candidate = (anchor[0] + dx, anchor[1] + dy)
                if candidate[0] <= 0 or candidate[1] <= 0 or candidate in occupied:
                    continue
                chosen = candidate
                break
            if chosen:
                break
        if not chosen:
            continue
        occupied.add(chosen)
        if reserved_cells is not None:
            reserved_cells.add(chosen)
        startup_placements.append((building_id, chosen))
    return startup_placements

def _startup_building_actions(
    lines,
    house,
    building_ids,
    reserved_cells=None,
):
    """Create hidden support buildings through map-start actions."""
    placements = _startup_building_placements(
        lines,
        house,
        building_ids,
        reserved_cells=reserved_cells,
    )
    next_waypoint = next_numeric_section_index(lines, 'Waypoints')
    actions = []
    for building_id, chosen in placements:
        waypoint = _waypoint_label(next_waypoint)
        append_section_entry(
            lines,
            'Waypoints',
            str(next_waypoint),
            str(chosen[0] * 1000 + chosen[1]),
        )
        next_waypoint += 1
        actions.append([
            '125', '10', building_id, '0', '0', '0', '0', waypoint,
        ])
    return actions

def append_static_startup_buildings(lines, houses, building_ids=()):
    """Place exact-House support buildings before map-start triggers run."""
    if isinstance(houses, str):
        houses = [houses]
    houses = unique_in_order(
        str(house or '').strip()
        for house in (houses or ())
        if str(house or '').strip()
    )
    building_ids = [
        str(item).strip()
        for item in building_ids
        if str(item).strip()
    ]
    if not houses or not building_ids:
        return []

    next_structure = next_numeric_section_index(lines, 'Structures')
    reserved_cells = set()
    placed = []
    for house in houses:
        placements = _startup_building_placements(
            lines,
            house,
            building_ids,
            reserved_cells=reserved_cells,
        )
        for building_id, (cell_x, cell_y) in placements:
            append_section_entry(
                lines,
                'Structures',
                str(next_structure),
                (
                    f'{house},{building_id},256,{cell_x},{cell_y},64,None,'
                    '1,0,1,0,0,None,None,None,0,0'
                ),
            )
            next_structure += 1
            placed.append((house, building_id, cell_x, cell_y))
    return placed

def append_superweapon_grant_trigger(
    lines,
    houses,
    action_groups,
    startup_buildings=(),
):
    """Grant earned powers to every requested mission house safely.

    Mental Omega's installed campaign maps top out at 24 actions in one list.
    Large Chaos inventories previously wrote every power into a single list
    (35 in the reported crash), which corrupts the engine while processing the
    map-start trigger. Keep a conservative margin and stagger additional
    chunks by one second so every power is still granted exactly once.
    """
    actions = [list(group) for group in action_groups]
    if not actions or any(len(group) != 8 for group in actions):
        return ''

    if isinstance(houses, str):
        houses = [houses]
    houses = unique_in_order(
        str(house or '').strip()
        for house in (houses or ())
        if str(house or '').strip()
    )
    if not houses:
        return ''

    trigger_ids = []
    reserved_startup_cells = set()
    for house_number, house in enumerate(houses, 1):
        house_actions = _startup_building_actions(
            lines,
            house,
            startup_buildings,
            reserved_cells=reserved_startup_cells,
        ) + actions
        action_offset = 0
        chunk_number = 1
        while action_offset < len(house_actions):
            trigger_id = unique_section_key(lines, ('Events', 'Actions', 'Triggers'), 'RNGSW')
            chunk = []
            while (
                action_offset + len(chunk) < len(house_actions)
                and len(chunk) < SUPERWEAPON_ACTIONS_PER_TRIGGER
            ):
                candidate = chunk + [house_actions[action_offset + len(chunk)]]
                candidate_tokens = ','.join(action_group_tokens(candidate))
                candidate_line = f'{trigger_id}={len(candidate)},{candidate_tokens}'
                if (
                    chunk
                    and len(candidate_line.encode('utf-8'))
                    > MAX_MAP_ACTION_LINE_LENGTH
                ):
                    break
                chunk = candidate
            if not chunk:
                return ''
            tag_id = unique_section_key(lines, ('Tags',), 'RNGST')
            action_tokens = ','.join(action_group_tokens(chunk))
            name = f'MOR Earned Superweapons H{house_number} C{chunk_number}'
            append_section_entry(lines, 'Events', trigger_id, f'1,13,0,{chunk_number}')
            append_section_entry(lines, 'Actions', trigger_id, f'{len(chunk)},{action_tokens}')
            append_section_entry(lines, 'Triggers', trigger_id, f'{house},<none>,{name},0,1,1,1,0')
            append_section_entry(lines, 'Tags', tag_id, f'0,{name} 1,{trigger_id}')
            trigger_ids.append(trigger_id)
            action_offset += len(chunk)
            chunk_number += 1
    return trigger_ids[0]
