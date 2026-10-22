"""Wave growth, bounded composition sizing, and runtime admission decisions."""

import random

from .config import integer, validate_wave_multiplier


def spawn_side_count(config, seconds):
    """Read scheduled active fronts; older snapshots keep their three fronts."""
    integer(seconds, 'Scheduled wave time', 1)
    stages = config['wave_pressure'].get('spawn_sides')
    if stages is None:
        return 3
    return next(stage['count'] for stage in reversed(stages) if stage['from_seconds'] <= seconds)


def wave_growth(config, difficulty):
    """New balance grows by the opening amount; old fixed increments still work."""
    growth = config['wave_pressure']['growth_per_wave']
    if growth == 'starting_amount':
        return config['difficulties'][difficulty]['starting_wave_units']
    return integer(growth, 'Base unit growth per wave', 1)


def wave_size(config, *, difficulty, wave_index, wave_multiplier):
    """Keep the approved opening count, then grow to the configured unit ceiling.

    The ceiling is shared by all currently active spawn sides and is applied
    before multiplication. Each active side receives the same count, and xN
    still multiplies each chosen base unit by N. A too-small ceiling rejects
    the opening base count instead of reducing it.
    """
    integer(wave_index, 'Wave index')
    validate_wave_multiplier(wave_multiplier)
    start = config['difficulties'][difficulty]['starting_wave_units']
    pressure = config['wave_pressure']
    growth = wave_growth(config, difficulty)
    sides = spawn_side_count(config, (wave_index + 1) * config['settings']['wave_interval_seconds'])
    per_wave_limit = integer(config['settings']['max_wave_units'], 'Wave unit limit', 1)
    active_limit = integer(pressure['max_active_units'], 'Living wave unit limit', 1)
    maximum_base = min(per_wave_limit, active_limit) // (sides * wave_multiplier)
    if maximum_base < start:
        raise ValueError('Configured limits cannot admit the approved first-wave count.')
    requested = start + wave_index * growth
    base = min(requested, maximum_base)
    size = {
        'requested_base_units': requested,
        'base_units': base,
        'units_per_enemy': base * wave_multiplier,
        'total_units': base * wave_multiplier * sides,
        'capped': base < requested,
    }
    if 'spawn_sides' in pressure:
        size['spawn_sides'] = sides
    return size


def size_composition(units, *, base_units, seed, house, seconds):
    """Apportion the target count using template counts as relative proportions.

    Integer largest remainders preserve the exact target. A dedicated seeded
    tie order prevents low-count waves from always choosing the first listed
    types. Allocation happens before the separate player-selected multiplier.
    """
    integer(base_units, 'Base wave units', 1)
    if not units:
        raise ValueError('Wave composition has no units.')
    weights = [integer(unit['count'], 'Composition proportion', 1) for unit in units]
    total = sum(weights)
    allocated = [base_units * weight // total for weight in weights]
    order = list(range(len(units)))
    rng = random.Random(f'{seed}:final_fortress:wave_unit_distribution:{house}:{seconds}')
    rng.shuffle(order)
    order.sort(key=lambda index: base_units * weights[index] % total, reverse=True)
    for index in order[:base_units - sum(allocated)]:
        allocated[index] += 1
    return [{'type': unit['type'], 'count': count}
            for unit, count in zip(units, allocated) if count]


def wave_admission(plan, *, next_wave_index, elapsed_seconds, living_wave_units,
                   last_spawn_seconds=None):
    """Describe whether the next whole wave may spawn at the tracked population.

    Counts must track scripted-wave actors or conservatively reserve their
    capacity, excluding normal AI production. This function does not observe the engine. A
    delayed wave retains its place; the interval between actual admissions
    prevents accumulated waves from spawning together when capacity returns.
    The survival deadline always ends admission, including delayed waves.
    """
    integer(next_wave_index, 'Next wave index')
    integer(elapsed_seconds, 'Elapsed simulation seconds')
    integer(living_wave_units, 'Living scripted-wave units')
    if last_spawn_seconds is not None:
        integer(last_spawn_seconds, 'Last wave spawn time')
        if last_spawn_seconds > elapsed_seconds:
            raise ValueError('Last wave spawn cannot be in the future.')
    pressure = plan.get('wave_pressure')
    if not isinstance(pressure, dict) or pressure.get('overflow') != 'delay':
        raise ValueError('This run has no configured wave admission policy.')
    limit = integer(pressure['max_active_units'], 'Living wave unit limit', 1)
    schedule = plan['wave_schedule']
    if elapsed_seconds >= plan['survival_seconds'] or next_wave_index >= len(schedule):
        return 'finished'
    wave = schedule[next_wave_index]
    interval = plan['wave_interval_seconds']
    if elapsed_seconds < wave['seconds'] or (
        last_spawn_seconds is not None and elapsed_seconds - last_spawn_seconds < interval
    ):
        return 'wait_for_time'
    count = sum(unit['count'] for group in wave['groups'] for unit in group['units'])
    if count > limit:
        raise ValueError('This wave exceeds the total living scripted-wave unit limit.')
    if living_wave_units + count > limit:
        return 'wait_for_capacity'
    return 'spawn'
