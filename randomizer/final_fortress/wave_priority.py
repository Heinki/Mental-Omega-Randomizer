"""Frozen late-wave proportions and capacity-delayed delivery upgrades."""

from copy import deepcopy

from .pressure import size_composition


def priority(kind, policy):
    return 2 if kind in policy['special_units'] else 1 if kind in policy['advanced_units'] else 0


def resize(units, count, *, seed, house, seconds, policy):
    """Keep exact capacity, preserve identities where possible, place heavies first."""
    if not units or not count:
        return []
    ordered = sorted(units, key=lambda u: -priority(u['type'], policy))
    chosen = ordered[:count]
    extras = size_composition(chosen, base_units=count - len(chosen), seed=seed,
                              house=house, seconds=seconds) if count > len(chosen) else []
    amounts = {u['type']: u['count'] for u in extras}
    return [{'type': u['type'], 'count': 1 + amounts.get(u['type'], 0)} for u in chosen]


def rebalance(units, count, *, seed, house, seconds, policy):
    stage = next((s for s in reversed(policy['stages']) if s['from_seconds'] <= seconds), None)
    if not stage:
        return resize(units, count, seed=seed, house=house, seconds=seconds, policy=policy)
    groups = [[u for u in units if priority(u['type'], policy) == rank] for rank in (0, 1, 2)]
    if count < len(units):
        return resize(units, count, seed=seed, house=house, seconds=seconds, policy=policy)
    high = groups[1] + groups[2]
    if not high:
        return resize(units, count, seed=seed, house=house, seconds=seconds, policy=policy)
    high_count = min(count - len(groups[0]), max(len(high),
        count * (stage['advanced_percent'] + stage['special_percent']) // 100))
    if not groups[0]:
        high_count = count
    special_count = (min(high_count - len(groups[1]), max(len(groups[2]),
        count * stage['special_percent'] // 100)) if groups[2] else 0)
    if not groups[1]:
        special_count = high_count
    counts = (count - high_count, high_count - special_count, special_count)
    result = []
    for group, amount in zip(groups, counts):
        result.extend(resize(group, amount, seed=seed, house=house, seconds=seconds, policy=policy))
    return sorted(result, key=lambda u: -priority(u['type'], policy))


def apply_priorities(plan, policy):
    """Rebalance only ground units; retain total counts and the planned air budget."""
    plan['wave_priorities'] = deepcopy(policy)
    for wave in plan['wave_schedule']:
        for group in wave['groups']:
            air = set(group.get('air_types', []))
            ground = [u for u in group['units'] if u['type'] not in air]
            flying = [u for u in group['units'] if u['type'] in air]
            group['units'] = rebalance(ground, sum(u['count'] for u in ground),
                seed=plan['seed'], house=group['house'], seconds=wave['seconds'], policy=policy) + flying


def late_delivery(plan, wave, group, units):
    """Upgrade a delayed old batch without adding units or using new pool identities."""
    policy = plan['wave_priorities']
    if wave['seconds'] >= policy['late_seconds']:
        return units
    later = next((w for w in plan['wave_schedule'] if w['seconds'] >= policy['late_seconds']),
                 plan['wave_schedule'][-1])
    source = next(g for g in later['groups'] if g['house'] == group['house'])
    flying = bool(set(group.get('air_types', [])) & {u['type'] for u in units})
    candidates = [u for u in source['units'] if (u['type'] in source.get('air_types', [])) == flying]
    return rebalance(candidates or units, sum(u['count'] for u in units), seed=plan['seed'],
                     house=group['house'], seconds=max(later['seconds'], policy['late_seconds']), policy=policy)
