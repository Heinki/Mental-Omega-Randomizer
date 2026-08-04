"""Deterministic per-mission rosters for Randomizer Arsenal mode."""

import random

from randomizer.rewards.catalogue import (
    BUFF_TARGETS,
    NAVAL_UNIT_IDS,
    REWARD_POOL,
    canonical_reward,
    linked_buff_variant_ids,
    unit_display_label,
    unit_role_equivalents,
)
from randomizer.rewards.rules import tech_ids_for_rewards


ARSENAL_MODE = 'Randomizer Arsenal'
ARSENAL_FACTIONS = ('Allies', 'Soviets', 'Epsilon', 'Foehn')
ARSENAL_TIERS = ('tier_1', 'tier_2', 'tier_3')
ARSENAL_UNIT_TYPES = ('infantry', 'vehicles', 'aircraft', 'naval')
ARSENAL_POWER_TYPES = ('offensive', 'secondary', 'aid')
ARSENAL_COUNT_MAXIMUM = 20

DEFAULT_ARSENAL_SETTINGS = {
    'factions': list(ARSENAL_FACTIONS),
    'roster_sizes': {
        'tier_1': {'infantry': 3, 'vehicles': 2, 'aircraft': 0, 'naval': 0},
        'tier_2': {'infantry': 3, 'vehicles': 3, 'aircraft': 1, 'naval': 1},
        'tier_3': {'infantry': 2, 'vehicles': 2, 'aircraft': 1, 'naval': 1},
    },
    'power_counts': {'offensive': 1, 'secondary': 0, 'aid': 1},
}


def _bounded_count(value, default=0):
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = default
    return max(0, min(ARSENAL_COUNT_MAXIMUM, value))


def normalize_arsenal_settings(value):
    """Return complete portable settings without retaining invalid values."""
    value = value if isinstance(value, dict) else {}
    raw_factions = value.get('factions')
    if not isinstance(raw_factions, list):
        raw_factions = DEFAULT_ARSENAL_SETTINGS['factions']
    factions = [
        faction for faction in ARSENAL_FACTIONS
        if faction in {str(item) for item in raw_factions}
    ]
    raw_sizes = value.get('roster_sizes')
    raw_sizes = raw_sizes if isinstance(raw_sizes, dict) else {}
    roster_sizes = {}
    for tier in ARSENAL_TIERS:
        raw_tier = raw_sizes.get(tier)
        raw_tier = raw_tier if isinstance(raw_tier, dict) else {}
        roster_sizes[tier] = {
            unit_type: _bounded_count(
                raw_tier.get(unit_type),
                DEFAULT_ARSENAL_SETTINGS['roster_sizes'][tier][unit_type],
            )
            for unit_type in ARSENAL_UNIT_TYPES
        }
    raw_powers = value.get('power_counts')
    raw_powers = raw_powers if isinstance(raw_powers, dict) else {}
    power_counts = {
        power_type: _bounded_count(
            raw_powers.get(power_type),
            DEFAULT_ARSENAL_SETTINGS['power_counts'][power_type],
        )
        for power_type in ARSENAL_POWER_TYPES
    }
    return {
        'factions': factions,
        'roster_sizes': roster_sizes,
        'power_counts': power_counts,
    }


def arsenal_tier_for_tech_level(tech_level):
    """Map installed TechLevel bands to three user-facing arsenal tiers."""
    try:
        tech_level = int(tech_level)
    except (TypeError, ValueError):
        tech_level = 1
    if tech_level <= 2:
        return 'tier_1'
    if tech_level <= 6:
        return 'tier_2'
    return 'tier_3'


def arsenal_unit_type(unit_id, target=None):
    target = target or BUFF_TARGETS.get(str(unit_id).upper(), {})
    category = target.get('category')
    if category == 'infantry':
        return 'infantry'
    if category == 'aircraft':
        return 'aircraft'
    if category == 'units':
        return 'naval' if str(unit_id).upper() in NAVAL_UNIT_IDS else 'vehicles'
    return ''


def _template_tech_levels():
    from randomizer.rewards.roster import randomizer_unit_roster

    _paths, _clone_ids, templates = randomizer_unit_roster()
    levels = {}
    for unit_id, values in templates.items():
        raw = next(
            (value for key, value in values.items() if str(key).lower() == 'techlevel'),
            1,
        )
        try:
            levels[unit_id.upper()] = max(1, int(raw))
        except (TypeError, ValueError):
            levels[unit_id.upper()] = 1
    return levels


def _root_unit_for_reward(reward, tech_ids):
    candidates = []
    for unit_id in tech_ids:
        target = BUFF_TARGETS.get(unit_id, {})
        if arsenal_unit_type(unit_id, target):
            candidates.append(unit_id)
    if not candidates:
        return ''
    return next(
        (
            unit_id for unit_id in candidates
            if not BUFF_TARGETS.get(unit_id, {}).get('linked_buff_source')
        ),
        candidates[0],
    )


def arsenal_unit_candidates(reward_settings, arsenal_settings):
    """Build stable supported access candidates before seeded shuffling."""
    settings = normalize_arsenal_settings(arsenal_settings)
    allowed_factions = set(settings['factions'])
    excluded_ids = {
        str(unit_id).upper()
        for unit_id in reward_settings.get('excluded_unit_access_ids', ())
    }
    include_special = bool(reward_settings.get('include_special_rewards', True))
    levels = _template_tech_levels()
    candidates = []
    seen_names = set()
    for source in REWARD_POOL:
        reward = canonical_reward(source)
        if reward.get('kind') in {'buff', 'superweapon', 'message', 'retired'}:
            continue
        name = str(reward.get('name') or '')
        if not name or name in seen_names:
            continue
        tech_ids = sorted(tech_ids_for_rewards([reward]))
        root_id = _root_unit_for_reward(reward, tech_ids)
        if not root_id:
            continue
        target = BUFF_TARGETS.get(root_id, {})
        factions = [
            str(faction) for faction in (target.get('factions') or reward.get('factions') or ())
            if str(faction) in ARSENAL_FACTIONS
        ]
        if not allowed_factions.intersection(factions):
            continue
        linked_ids = set(linked_buff_variant_ids(root_id)) | set(tech_ids)
        if linked_ids.intersection(excluded_ids):
            continue
        if not include_special and (
            reward.get('special_reward') or target.get('special_reward')
        ):
            continue
        tech_level = levels.get(root_id, 1)
        candidates.append({
            'unit_id': root_id,
            'tech_ids': tech_ids,
            'reward_name': name,
            'label': unit_display_label(root_id),
            'faction': next(
                (faction for faction in ARSENAL_FACTIONS if faction in factions),
                factions[0] if factions else 'Other',
            ),
            'production_type': arsenal_unit_type(root_id, target),
            'tech_level': tech_level,
            'tier': arsenal_tier_for_tech_level(tech_level),
            'equivalent_ids': sorted(
                set(unit_role_equivalents(root_id)) | linked_ids
            ),
        })
        seen_names.add(name)
    return candidates


def arsenal_power_candidates(reward_settings, arsenal_settings):
    settings = normalize_arsenal_settings(arsenal_settings)
    allowed_factions = set(settings['factions'])
    excluded = {
        str(power_id).upper()
        for power_id in reward_settings.get('excluded_superweapon_ids', ())
    }
    enabled_categories = {
        category for category, key in (
            ('offensive', 'include_superweapon_rewards'),
            ('secondary', 'include_secondary_superweapon_rewards'),
            ('aid', 'include_aid_power_rewards'),
        )
        if reward_settings.get(key, False)
    }
    include_special = bool(reward_settings.get('include_special_rewards', True))
    candidates = []
    seen = set()
    for source in REWARD_POOL:
        reward = canonical_reward(source)
        power_id = str(reward.get('superweapon') or '').upper()
        if reward.get('kind') != 'superweapon' or not power_id or power_id in seen:
            continue
        category = str(reward.get('power_category') or 'offensive')
        factions = {str(item) for item in reward.get('factions', ())}
        if (
            power_id in excluded
            or category not in enabled_categories
            or (not include_special and reward.get('special_reward'))
            or (
                factions
                and 'Neutral' not in factions
                and not allowed_factions.intersection(factions)
            )
        ):
            continue
        candidates.append({
            'power_id': power_id,
            'reward_name': reward.get('name', power_id),
            'label': reward.get('name', power_id),
            'faction': next(iter(factions), 'Neutral'),
            'power_type': category,
            'requires_any_tech_ids': [
                str(unit_id).upper()
                for unit_id in reward.get('requires_any_tech_ids', ())
                if str(unit_id).strip()
            ],
        })
        seen.add(power_id)
    return candidates


def _select_mixed_units(rng, candidates, count, used_equivalents, factions):
    by_faction = {faction: [] for faction in factions}
    for candidate in candidates:
        if candidate['faction'] in by_faction:
            by_faction[candidate['faction']].append(candidate)
    faction_order = list(factions)
    rng.shuffle(faction_order)
    for values in by_faction.values():
        rng.shuffle(values)
    selected = []
    while len(selected) < count:
        added = False
        for faction in faction_order:
            pool = by_faction[faction]
            while pool:
                candidate = pool.pop()
                equivalents = set(candidate['equivalent_ids'])
                if equivalents.intersection(used_equivalents):
                    continue
                selected.append(dict(candidate))
                used_equivalents.update(equivalents)
                added = True
                break
            if len(selected) >= count:
                break
        if not added:
            break
    return selected


def generate_mission_arsenals(seed, mission_codes, reward_settings, arsenal_settings):
    """Generate each mission independently so reopen/order changes cannot reroll it."""
    settings = normalize_arsenal_settings(arsenal_settings)
    unit_candidates = arsenal_unit_candidates(reward_settings, settings)
    power_candidates = arsenal_power_candidates(reward_settings, settings)
    arsenals = {}
    for code in mission_codes:
        rng = random.Random(f'{seed}:randomizer-arsenal:{str(code).upper()}')
        used_equivalents = set()
        units = []
        for tier in ARSENAL_TIERS:
            for unit_type in ARSENAL_UNIT_TYPES:
                count = settings['roster_sizes'][tier][unit_type]
                bucket = [
                    candidate for candidate in unit_candidates
                    if candidate['tier'] == tier
                    and candidate['production_type'] == unit_type
                ]
                units.extend(_select_mixed_units(
                    rng,
                    bucket,
                    count,
                    used_equivalents,
                    settings['factions'],
                ))
        powers = []
        selected_tech_ids = {
            str(unit_id).upper()
            for entry in units
            for unit_id in entry.get('tech_ids', ())
        }
        for power_type in ARSENAL_POWER_TYPES:
            bucket = [
                dict(candidate) for candidate in power_candidates
                if candidate['power_type'] == power_type
                and (
                    not candidate.get('requires_any_tech_ids')
                    or selected_tech_ids.intersection(
                        candidate['requires_any_tech_ids']
                    )
                )
            ]
            rng.shuffle(bucket)
            powers.extend(bucket[:settings['power_counts'][power_type]])
        arsenals[str(code).upper()] = {
            'seed_fixed': True,
            'units': units,
            'powers': powers,
        }
    return arsenals


def arsenal_unit_ids(arsenal):
    return {
        str(unit_id).upper()
        for entry in (arsenal or {}).get('units', ())
        for unit_id in entry.get('tech_ids', (entry.get('unit_id'),))
        if unit_id
    }


def arsenal_power_ids(arsenal):
    return {
        str(entry.get('power_id') or '').upper()
        for entry in (arsenal or {}).get('powers', ())
        if entry.get('power_id')
    }


def reward_matches_arsenal(reward, arsenal):
    """Accept only buffs that affect content present in one mission arsenal."""
    reward = canonical_reward(reward)
    if reward.get('enemy_reward'):
        return True
    if reward.get('kind') != 'buff':
        return False
    unit_id = str(reward.get('unit') or '').upper()
    power_id = str(reward.get('superweapon') or '').upper()
    if unit_id:
        selected = arsenal_unit_ids(arsenal)
        return bool(set(linked_buff_variant_ids(unit_id)).intersection(selected))
    if power_id:
        return power_id in arsenal_power_ids(arsenal)
    return bool(reward.get('global_buff') and arsenal_unit_ids(arsenal))


def arsenal_reward_pool(pool, arsenal):
    return [
        canonical_reward(reward)
        for reward in pool
        if reward_matches_arsenal(reward, arsenal)
        and (
            not reward.get('requires_any_tech_ids')
            or arsenal_unit_ids(arsenal).intersection(
                str(unit_id).upper()
                for unit_id in reward.get('requires_any_tech_ids', ())
            )
        )
    ]


def arsenal_launch_rewards(arsenal, earned_rewards):
    """Combine earned applicable buffs with temporary mission access."""
    reward_by_name = {
        canonical_reward(reward).get('name'): canonical_reward(reward)
        for reward in REWARD_POOL
    }
    rewards = [
        canonical_reward(reward)
        for reward in earned_rewards
        if reward_matches_arsenal(reward, arsenal)
    ]
    for entry in (arsenal or {}).get('units', ()):
        source = reward_by_name.get(entry.get('reward_name'))
        if not source:
            continue
        reward = dict(source)
        reward['rules'] = {
            section: dict(values)
            for section, values in source.get('rules', {}).items()
        }
        selected_ids = {str(item).upper() for item in entry.get('tech_ids', ())}
        for section, values in reward['rules'].items():
            if str(section).upper() in selected_ids:
                for key in list(values):
                    if str(key).lower() == 'techlevel':
                        values[key] = str(entry.get('tech_level', 1))
                        break
        reward['arsenal_temporary_access'] = True
        rewards.append(reward)
    for entry in (arsenal or {}).get('powers', ()):
        source = reward_by_name.get(entry.get('reward_name'))
        if source:
            reward = dict(source)
            reward['arsenal_temporary_access'] = True
            rewards.append(reward)
    return rewards
