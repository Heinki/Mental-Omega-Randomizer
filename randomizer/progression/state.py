"""Pure normalization helpers for persisted launcher state."""

from randomizer.config.tuning import mission_assistance_stack_count


def normalize_completed_checks(state):
    """Synchronize completed missions and their check flags in place."""
    changed = False
    completed = state.setdefault('completed_missions', [])
    for code, checks in state.get('mission_checks', {}).items():
        victory_unlocked = any(
            check.get('id') == 'victory' and check.get('unlocked')
            for check in checks
        )
        if not victory_unlocked and code not in completed:
            continue
        if code not in completed:
            completed.append(code)
            changed = True
        for check in checks:
            if not check.get('unlocked'):
                check['unlocked'] = True
                changed = True
            if check.pop('released', None) is not None:
                changed = True
    return changed


def normalize_failure_stacks(state):
    """Keep positive failure counts only for unfinished seed missions."""
    raw_stacks = state.get('mission_failure_stacks', {})
    if not isinstance(raw_stacks, dict):
        raw_stacks = {}
    valid_codes = set(state.get('mission_order', []))
    completed = set(state.get('completed_missions', []))
    normalized = {}
    for code, value in raw_stacks.items():
        try:
            count = mission_assistance_stack_count(value)
        except (TypeError, ValueError):
            count = 0
        if code in valid_codes and code not in completed and count:
            normalized[code] = count
    if state.get('mission_failure_stacks') == normalized:
        return False
    state['mission_failure_stacks'] = normalized
    return True


def normalize_assistance_units(state, buff_targets):
    """Keep supported combat-unit IDs for unfinished seed missions."""
    raw_units = state.get('mission_assistance_units', {})
    if not isinstance(raw_units, dict):
        raw_units = {}
    valid_codes = set(state.get('mission_order', []))
    completed = set(state.get('completed_missions', []))
    normalized_by_mission = {}
    for code, unit_ids in raw_units.items():
        if (
            code not in valid_codes
            or code in completed
            or not isinstance(unit_ids, list)
        ):
            continue
        normalized = sorted({
            str(unit_id).upper()
            for unit_id in unit_ids
            if buff_targets.get(str(unit_id).upper(), {}).get('category')
            in {'infantry', 'units', 'aircraft'}
        })
        if normalized:
            normalized_by_mission[code] = normalized
    if state.get('mission_assistance_units') == normalized_by_mission:
        return False
    state['mission_assistance_units'] = normalized_by_mission
    return True
