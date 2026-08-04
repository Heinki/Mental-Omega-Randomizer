"""Validate that displayed unit buffs produced real generated INI changes."""

from randomizer.maps.buff_values import _active_direct_buff_counts
from randomizer.maps.ini import all_section_value_maps
from randomizer.rewards.catalogue import (
    BUFF_TARGETS,
    canonical_rewards,
    effective_buff_count,
    linked_buff_variant_ids,
)
from randomizer.rewards.rules import buffs_with_unlocked_access


_UNIT_BUFF_FIELDS = {
    'health': ('Strength',),
    'armor': ('Strength',),
    'sight': ('Sight',),
    'ammo': ('Ammo',),
    'passenger_capacity': ('Passengers',),
    'open_topped': ('OpenTopped',),
    'self_healing': ('SelfHealing', 'SelfHealing.Amount'),
    'cloak': ('Cloakable', 'Cloakable.Stages', 'CloakingSpeed'),
    'sensors': ('Sensors', 'SensorsSight'),
    'production': ('BuildTimeMultiplier',),
    'cost': ('Cost',),
    'speed': ('Speed',),
    'build_limit': ('BuildLimit',),
    'building_limit': ('BuildLimit',),
}
_WEAPON_BUFF_FIELDS = {
    'damage': 'Damage',
    'range': 'Range',
    'reload': 'ROF',
}


def _lower_values(values):
    return {
        str(key).lower(): value
        for key, value in (values or {}).items()
    }


def _numeric(value):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _unit_fields_are_effective(
    buff_type,
    values,
    target,
    base_values=None,
    allow_existing=False,
):
    lowered = _lower_values(values)
    base_values = _lower_values(base_values)
    required = _UNIT_BUFF_FIELDS.get(buff_type, ())
    if not required or any(key.lower() not in lowered for key in required):
        return False
    if buff_type in {'open_topped', 'self_healing', 'cloak', 'sensors'}:
        base_enabled = (
            str(base_values.get(required[0].lower(), 'no')).strip().lower()
            == 'yes'
        )
        return (
            str(lowered[required[0].lower()]).strip().lower() == 'yes'
            and (allow_existing or not base_enabled)
        )
    actual = _numeric(lowered[required[0].lower()])
    if actual is None:
        return False
    base_field = {
        'health': 'strength',
        'armor': 'strength',
        'sight': 'sight',
        'ammo': 'ammo',
        'passenger_capacity': 'passengers',
        'cost': 'cost',
        'speed': 'speed',
        'build_limit': 'build_limit',
        'building_limit': 'build_limit',
    }.get(buff_type)
    if buff_type == 'production':
        base = _numeric(base_values.get('buildtimemultiplier', 1))
        return base is not None and 0 < actual < base
    base_key = required[0].lower()
    base = _numeric(base_values.get(base_key))
    if base is None:
        base = _numeric(target.get(base_field)) if base_field else None
    if base is None:
        return False
    if buff_type == 'cost':
        return actual < base
    return actual > base


def _weapon_field_is_effective(
    buff_type,
    unit_id,
    details,
    sections,
):
    field = _WEAPON_BUFF_FIELDS[buff_type]
    targets = BUFF_TARGETS.get(unit_id, {}).get('weapons', {})
    target_names = {
        str(weapon_id).upper(): stats
        for weapon_id, stats in targets.items()
    }
    for source_weapon, clone_weapon in (
        details.get('weapon_clone_ids', {}) or {}
    ).items():
        stats = target_names.get(str(source_weapon).upper(), {})
        base_field = 'rof' if buff_type == 'reload' else buff_type
        base = _numeric(stats.get(base_field))
        actual = _numeric(
            _lower_values(sections.get(str(clone_weapon), {})).get(
                field.lower()
            )
        )
        if base is None or actual is None:
            continue
        if buff_type == 'reload' and actual < base:
            return True
        if buff_type != 'reload' and actual > base:
            return True
    return False


def _veteran_clone_is_registered(unit_id, clone_handled, sections):
    candidate_ids = linked_buff_variant_ids(unit_id) or {unit_id}
    clone_ids = {
        str(clone_handled.get(candidate, {}).get('clone_id') or '').upper()
        for candidate in candidate_ids
    } - {''}
    if not clone_ids:
        return False
    category = BUFF_TARGETS.get(unit_id, {}).get('category')
    field = {
        'infantry': 'veteraninfantry',
        'units': 'veteranunits',
        'aircraft': 'veteranaircraft',
        'defenses': 'veteranbuildings',
    }.get(category)
    if not field:
        return False
    for values in sections.values():
        raw = _lower_values(values).get(field)
        if raw is None:
            continue
        entries = {
            item.strip().upper()
            for item in str(raw).split(',')
            if item.strip()
        }
        if clone_ids.intersection(entries):
            return True
    return False


def validate_generated_unit_buff_changes(
    lines,
    rewards,
    clone_handled,
    *,
    require_unlocked_access=True,
    additional_unlocked_tech_ids=(),
    share_basic_equivalent_buffs=False,
    unit_specific_mode=False,
    global_production_unit_ids=(),
    excluded_unit_ids=(),
):
    """Compare active requested stacks with final clone/weapon INI sections."""
    sections = all_section_value_maps(lines)
    counts_by_unit = _active_direct_buff_counts(
        rewards,
        require_unlocked_access=require_unlocked_access,
        additional_unlocked_tech_ids=additional_unlocked_tech_ids,
        share_basic_equivalent_buffs=share_basic_equivalent_buffs,
        unit_specific_mode=unit_specific_mode,
        global_production_unit_ids=global_production_unit_ids,
    )
    excluded = {
        str(unit_id).upper() for unit_id in excluded_unit_ids
    }
    for unit_id in excluded:
        counts_by_unit.pop(unit_id, None)

    applied = []
    skipped = []
    for unit_id, counts in sorted(counts_by_unit.items()):
        target = BUFF_TARGETS.get(unit_id, {})
        peers = linked_buff_variant_ids(unit_id) or {unit_id}
        for buff_type, count in sorted(counts.items()):
            if buff_type in _WEAPON_BUFF_FIELDS:
                valid = False
                for peer_id in peers:
                    details = clone_handled.get(peer_id, {})
                    if buff_type not in set(
                        details.get('clone_weapon_buff_types', ())
                    ):
                        continue
                    if _weapon_field_is_effective(
                        buff_type,
                        peer_id,
                        details,
                        sections,
                    ):
                        valid = True
                        break
            else:
                details = clone_handled.get(unit_id, {})
                clone_id = str(details.get('clone_id') or '')
                valid = bool(
                    clone_id
                    and buff_type in set(
                        details.get('clone_unit_buff_types', ())
                    )
                    and _unit_fields_are_effective(
                        buff_type,
                        sections.get(clone_id, {}),
                        target,
                        details.get('clone_base_values', {}),
                        allow_existing=bool(
                            target.get('linked_buff_source')
                        ),
                    )
                )
            entry = {
                'unit': unit_id,
                'buff_type': buff_type,
                'stacks': int(count),
            }
            if valid:
                applied.append(entry)
            else:
                entry['reason'] = (
                    'no changed private weapon field'
                    if buff_type in _WEAPON_BUFF_FIELDS
                    else 'no changed player-clone field'
                )
                skipped.append(entry)

    active = buffs_with_unlocked_access(
        rewards,
        require_unlocked_access=require_unlocked_access,
        additional_unlocked_tech_ids=additional_unlocked_tech_ids,
        share_basic_equivalent_buffs=share_basic_equivalent_buffs,
    )
    veteran_counts = {}
    for reward in canonical_rewards(active):
        if reward.get('kind') != 'buff' or reward.get('buff_type') != 'veteran':
            continue
        unit_id = str(reward.get('unit') or '').upper()
        veteran_counts[unit_id] = veteran_counts.get(unit_id, 0) + 1
        veteran_counts[unit_id] = effective_buff_count(
            reward,
            veteran_counts[unit_id],
        )
    for unit_id, count in sorted(veteran_counts.items()):
        entry = {'unit': unit_id, 'buff_type': 'veteran', 'stacks': count}
        if _veteran_clone_is_registered(unit_id, clone_handled, sections):
            applied.append(entry)
        else:
            entry['reason'] = 'player clone absent from VeteranTypes list'
            skipped.append(entry)

    return {
        'requested_effects': len(applied) + len(skipped),
        'requested_stacks': sum(
            entry['stacks'] for entry in applied + skipped
        ),
        'applied_effects': len(applied),
        'applied_stacks': sum(entry['stacks'] for entry in applied),
        'applied': applied,
        'skipped': skipped,
    }
