"""Map object/team ownership analysis used by buff isolation."""

from randomizer.core.collections import unique_in_order
from randomizer.maps.ini import (
    all_section_value_maps,
    parse_action_groups,
    section_lines,
)
from randomizer.maps.houses import (
    canonical_house_name,
    country_inherits_from,
    is_buffable_helper_house,
    map_house_records,
    player_controlled_houses,
)


def ai_trigger_team_usage_houses(lines):
    """Return runtime owner overrides for TeamTypes used by AI triggers."""
    team_houses = {}
    for line in section_lines(lines, 'AITriggerTypes'):
        if '=' not in line:
            continue
        _, value = line.split('=', 1)
        tokens = [token.strip() for token in value.split(',')]
        if len(tokens) < 3:
            continue
        team_id = tokens[1]
        house = tokens[2]
        if not team_id or team_id.lower() in {'<none>', 'none'}:
            continue
        if not house or house.lower() in {'<none>', 'none'}:
            continue
        team_houses.setdefault(team_id.lower(), set()).add(house)
    return team_houses


def directly_created_team_ids(lines):
    """Return TeamTypes created directly by map actions."""
    team_ids = set()
    for line in section_lines(lines, 'Actions'):
        if '=' not in line:
            continue
        _, value = line.split('=', 1)
        _, groups = parse_action_groups(value)
        for group in groups:
            # Action 4 is Create Team; parameter 3 contains TeamType ID.
            if group[0] == '4' and group[2]:
                team_ids.add(group[2].lower())
    return team_ids


def taskforce_usage_houses(lines, sections=None):
    """Resolve each TaskForce to houses that can own it at runtime."""
    sections = sections or all_section_value_maps(lines)
    ai_team_houses = ai_trigger_team_usage_houses(lines)
    directly_created = directly_created_team_ids(lines)
    taskforce_to_houses = {}
    placeholder_houses = {'neutral', 'neutral house', '<none>', 'none'}
    for section_name, values in sections.items():
        taskforce = values.get('taskforce')
        house = values.get('house')
        if not taskforce or not house:
            continue

        section_key = section_name.lower()
        runtime_houses = ai_team_houses.get(section_key, set())
        houses = taskforce_to_houses.setdefault(taskforce.lower(), set())
        houses.update(runtime_houses)

        # Neutral can be an AITrigger template, not a live Neutral consumer.
        if (
            house.lower() not in placeholder_houses
            or not runtime_houses
            or section_key in directly_created
        ):
            houses.add(house)
    return taskforce_to_houses


def taskforce_unit_usage_houses(lines, unit_id):
    """Return runtime houses using one type through TaskForces."""
    unit_upper = (unit_id or '').upper()
    sections = all_section_value_maps(lines)
    sections_by_lower = {name.lower(): values for name, values in sections.items()}
    taskforce_to_houses = taskforce_usage_houses(lines, sections=sections)

    usage_houses = set()
    for taskforce_id, houses in taskforce_to_houses.items():
        for value in sections_by_lower.get(taskforce_id, {}).values():
            tokens = [token.strip() for token in value.split(',')]
            if len(tokens) >= 2 and tokens[1].upper() == unit_upper:
                usage_houses.update(houses)
    return usage_houses


def placed_unit_usage_houses(lines, unit_id):
    """Return houses owning placed instances of one type."""
    unit_upper = (unit_id or '').upper()
    usage_houses = set()
    for section in ('Infantry', 'Units', 'Aircraft', 'Structures'):
        for line in section_lines(lines, section):
            if '=' not in line:
                continue
            _, value = line.split('=', 1)
            tokens = [token.strip() for token in value.split(',')]
            if len(tokens) >= 2 and tokens[1].upper() == unit_upper:
                usage_houses.add(tokens[0])
    return usage_houses


def build_unit_usage_index(lines):
    """Index placed and scripted type ownership with one map parse."""
    usage = {}
    sections = all_section_value_maps(lines)
    sections_by_lower = {name.lower(): values for name, values in sections.items()}
    for section in ('Infantry', 'Units', 'Aircraft', 'Structures'):
        for value in sections_by_lower.get(section.lower(), {}).values():
            tokens = [token.strip() for token in value.split(',')]
            if len(tokens) >= 2:
                usage.setdefault(tokens[1].upper(), set()).add(tokens[0])

    for taskforce_id, houses in taskforce_usage_houses(
        lines,
        sections=sections,
    ).items():
        for value in sections_by_lower.get(taskforce_id, {}).values():
            tokens = [token.strip() for token in value.split(',')]
            if len(tokens) >= 2:
                usage.setdefault(tokens[1].upper(), set()).update(houses)
    return usage


def unit_usage_houses(lines, unit_id, usage_index=None):
    """Return placed/scripted houses using one TechnoType."""
    if usage_index is not None:
        return set(usage_index.get(str(unit_id or '').upper(), set()))
    return (
        placed_unit_usage_houses(lines, unit_id)
        | taskforce_unit_usage_houses(lines, unit_id)
    )


def scripted_enemy_house_pairs(lines, records=None):
    """Return house pairs that Action 38 can make hostile."""
    records = records if records is not None else map_house_records(lines)
    house_by_index = {}
    for line in section_lines(lines, 'Houses'):
        if '=' not in line:
            continue
        index, value = line.split('=', 1)
        house = canonical_house_name(records, value)
        if house:
            house_by_index[index.strip()] = house

    enemy_targets_by_action = {}
    for line in section_lines(lines, 'Actions'):
        if '=' not in line:
            continue
        action_id, value = line.split('=', 1)
        _, groups = parse_action_groups(value)
        targets = {
            house_by_index.get(group[2].strip(), '')
            for group in groups
            if len(group) >= 3 and group[0] == '38'
        } - {''}
        if targets:
            enemy_targets_by_action[action_id.strip().lower()] = targets

    pairs = set()
    for line in section_lines(lines, 'Triggers'):
        if '=' not in line:
            continue
        trigger_id, value = line.split('=', 1)
        targets = enemy_targets_by_action.get(trigger_id.strip().lower())
        if not targets:
            continue
        tokens = [token.strip() for token in value.split(',')]
        if len(tokens) >= 3 and 'debug' in tokens[2].lower():
            continue
        owner = canonical_house_name(records, tokens[0] if tokens else '')
        if not owner:
            continue
        for target in targets:
            if owner.lower() != target.lower():
                pairs.add(frozenset((owner.lower(), target.lower())))
    return pairs


def player_transfer_houses(lines, records=None, scripted_enemies=None):
    """Return houses whose complete forces safely join player coalition."""
    records = records if records is not None else map_house_records(lines)
    player_houses = player_controlled_houses(lines, records=records)
    if not player_houses:
        return []

    player_indexes = set()
    wanted_players = {house.lower() for house in player_houses}
    for line in section_lines(lines, 'Houses'):
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        if value.strip().lower() in wanted_players:
            player_indexes.add(key.strip())
    if not player_indexes:
        return []

    transfer_actions = set()
    for line in section_lines(lines, 'Actions'):
        if '=' not in line:
            continue
        action_id, value = line.split('=', 1)
        _, groups = parse_action_groups(value)
        if any(
            group[0] == '36' and group[2] in player_indexes
            for group in groups
        ):
            transfer_actions.add(action_id.strip().lower())

    houses = []
    for line in section_lines(lines, 'Triggers'):
        if '=' not in line:
            continue
        trigger_id, value = line.split('=', 1)
        if trigger_id.strip().lower() not in transfer_actions:
            continue
        parts = [part.strip() for part in value.split(',')]
        if len(parts) < 3 or 'debug' in parts[2].lower():
            continue
        owner = parts[0]
        if owner and owner.lower() not in {'<none>', 'neutral'}:
            houses.append(owner)
    canonical_houses = unique_in_order(
        canonical_house_name(records, house) or house
        for house in unique_in_order(houses)
    )

    coalition_names = list(player_houses)
    for player in player_houses:
        coalition_names.extend(records.get(player, {}).get('allies', []))
    coalition = {
        canonical.lower()
        for house in coalition_names
        if (canonical := canonical_house_name(records, house))
    }
    scripted_enemies = (
        scripted_enemy_house_pairs(lines, records=records)
        if scripted_enemies is None
        else scripted_enemies
    )
    return [
        house
        for house in canonical_houses
        if not any(
            frozenset((house.lower(), coalition_house)) in scripted_enemies
            for coalition_house in coalition
            if coalition_house != house.lower()
        )
    ]


def unsafe_country_houses(
    lines,
    country,
    allowed_house_names,
    records=None,
    sections=None,
    usage_index=None,
    scripted_enemies=None,
):
    """Return active denied houses inheriting one buff-target country."""
    allowed = {name.lower() for name in allowed_house_names}
    sections = sections if sections is not None else all_section_value_maps(lines)
    records = (
        records
        if records is not None
        else map_house_records(lines, sections=sections)
    )
    usage_index = (
        build_unit_usage_index(lines)
        if usage_index is None
        else usage_index
    )
    scripted_enemies = (
        scripted_enemy_house_pairs(lines, records=records)
        if scripted_enemies is None
        else scripted_enemies
    )
    used_houses = set()
    for owners in usage_index.values():
        for owner in owners:
            canonical = canonical_house_name(records, owner)
            used_houses.add((canonical or owner).lower())

    unsafe = []
    for name, record in records.items():
        if not country_inherits_from(
            lines,
            record.get('country'),
            country,
            sections=sections,
        ):
            continue
        name_lower = name.lower()
        if name_lower in allowed:
            continue

        record_allies = {
            canonical.lower()
            for ally in record.get('allies', [])
            if (canonical := canonical_house_name(records, ally))
        }
        allied_to_allowed = bool(record_allies.intersection(allowed)) or any(
            name_lower in {
                canonical.lower()
                for ally in records.get(allowed_house, {}).get('allies', [])
                if (canonical := canonical_house_name(records, ally))
            }
            for allowed_house in allowed_house_names
        )
        hostile_to_allowed = any(
            frozenset((name_lower, allowed_house)) in scripted_enemies
            for allowed_house in allowed
            if allowed_house != name_lower
        )
        harmless_placeholder = (
            not is_buffable_helper_house(record)
            and name_lower not in used_houses
            and allied_to_allowed
            and not hostile_to_allowed
        )
        if not harmless_placeholder:
            unsafe.append(name)
    return unsafe
