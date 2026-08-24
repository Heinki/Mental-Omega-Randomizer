"""Mission-safe enemy-house scaling and AI power reward preparation."""

import re

from randomizer.rewards.enemy_scaling import (
    enemy_effect_text,
    enemy_effect_values,
)

from ._shared import (
    all_section_value_maps,
    BUFF_TARGETS,
    build_unit_usage_index,
    canonical_house_name,
    map_house_records,
    player_controlled_houses,
    REWARD_POOL,
    scripted_enemy_house_pairs,
    section_value_map_preserve,
    techno_type_possible_houses,
    unique_in_order,
    unsafe_country_houses,
)
from .houses import country_family, is_buffable_helper_house
from .ownership import player_transfer_houses
from .base import (
    _collision_safe_type_id,
    _value_case_insensitive,
    format_multiplier,
    parse_float,
)
from .buff_values import (
    _register_map_type,
    apply_unit_buff_value,
    apply_weapon_buff_value,
)
from .clone_references import (
    _standalone_clone_values_from_maps,
    _target_with_effective_unit_stats,
)


def discover_hostile_ai_houses(lines, excluded_houses=()):
    """Find active military AI Houses outside the direct player coalition."""
    sections = all_section_value_maps(lines)
    records = map_house_records(lines, sections=sections)
    players = player_controlled_houses(lines, records=records)
    coalition = {house.lower() for house in players}

    # Alliance links are often one-sided, so inspect both directions. Do not
    # transitively close them: story/helper Houses can temporarily bridge the
    # player to an otherwise hostile coalition (Bad Apple does exactly this).
    direct_player_allies = set(coalition)
    for player in players:
        direct_player_allies.update(
            canonical.lower()
            for ally in records.get(player, {}).get('allies', ())
            if (canonical := canonical_house_name(records, ally))
        )
    for house, record in records.items():
        if any(
            canonical.lower() in coalition
            for ally in record.get('allies', ())
            if (canonical := canonical_house_name(records, ally))
        ):
            direct_player_allies.add(house.lower())
    coalition = direct_player_allies

    transfers = {
        house.lower()
        for house in player_transfer_houses(lines, records=records)
    }
    excluded = {
        str(house or '').strip().lower()
        for house in excluded_houses or ()
        if str(house or '').strip()
    }
    scripted_enemies = scripted_enemy_house_pairs(lines, records=records)
    player_lower = {house.lower() for house in players}
    usage_index = build_unit_usage_index(lines)
    used_houses = set()
    for owners in usage_index.values():
        for owner in owners:
            canonical = canonical_house_name(records, owner)
            if canonical:
                used_houses.add(canonical.lower())

    hostile = []
    skipped = {}
    for house, record in records.items():
        house_lower = house.lower()
        scripted_hostile = any(
            house_lower in pair and pair.intersection(player_lower)
            for pair in scripted_enemies
        )
        reason = ''
        if record.get('player'):
            reason = 'player-controlled House'
        elif house_lower in excluded:
            reason = 'reviewed player helper House'
        elif house_lower in coalition and not scripted_hostile:
            reason = 'player-controlled or allied coalition'
        elif house_lower in transfers:
            reason = 'scripted to transfer to player coalition'
        elif not is_buffable_helper_house(record) or not country_family(record):
            reason = 'neutral, civilian, special, or noncombat House'
        elif house_lower not in used_houses:
            reason = 'no placed or scripted military consumer'
        if reason:
            skipped[house] = reason
        else:
            hostile.append(house)
    return unique_in_order(hostile), skipped


def active_hostile_enemy_houses(lines, configured_enemy_houses):
    """Reject human-controlled or currently allied phase houses."""
    records = map_house_records(lines)
    players = set(player_controlled_houses(lines, records=records))
    player_lower = {house.lower() for house in players}
    transfers = {
        house.lower()
        for house in player_transfer_houses(lines, records=records)
    }
    scripted_enemies = scripted_enemy_house_pairs(lines, records=records)
    active = []
    skipped = []
    for house in configured_enemy_houses or ():
        record = records.get(house)
        house_lower = house.lower()
        if not record or record.get('player') or house_lower in transfers:
            skipped.append(house)
            continue
        scripted_hostile = any(
            house_lower in pair and pair.intersection(player_lower)
            for pair in scripted_enemies
        )
        allies = {
            canonical.lower()
            for ally in record.get('allies', ())
            if (canonical := canonical_house_name(records, ally))
        }
        player_allies = any(
            house.lower() in {
                canonical.lower()
                for ally in records.get(player, {}).get('allies', ())
                if (canonical := canonical_house_name(records, ally))
            }
            for player in players
        )
        if (
            not scripted_hostile
            and (allies.intersection(player_lower) or player_allies)
        ):
            skipped.append(house)
            continue
        active.append(house)
    return unique_in_order(active), unique_in_order(skipped)


def _effect_counts(rewards):
    raw_counts = {}
    maximums = {}
    definitions = {}
    for reward in rewards or ():
        if not reward.get('enemy_reward'):
            continue
        effect_id = str(reward.get('enemy_effect_id') or '')
        if not effect_id:
            continue
        maximum = max(1, int(reward.get('enemy_maximum', 1)))
        raw_counts[effect_id] = raw_counts.get(effect_id, 0) + 1
        if maximum >= maximums.get(effect_id, 0):
            maximums[effect_id] = maximum
            definitions[effect_id] = reward
    counts = {
        effect_id: min(count, maximums[effect_id])
        for effect_id, count in raw_counts.items()
    }
    return counts, definitions


def enemy_country_buff_rules(lines, enemy_houses, rewards):
    """Apply country multipliers only when no non-target house inherits them."""
    counts, definitions = _effect_counts(rewards)
    stat_effects = [
        (definitions[effect_id], count)
        for effect_id, count in counts.items()
        if definitions[effect_id].get('enemy_effect')
        in {'armor', 'production'}
    ]
    if not enemy_houses or not stat_effects:
        return {}, [], [], []
    sections = all_section_value_maps(lines)
    records = map_house_records(lines, sections=sections)
    usage_index = build_unit_usage_index(lines)
    scripted_enemies = scripted_enemy_house_pairs(lines, records=records)
    countries = unique_in_order(
        records.get(house, {}).get('country')
        or house.replace(' House', '')
        for house in enemy_houses
    )
    rules = {}
    applied = []
    skipped = []
    applications = []
    section_counts = {}
    for line in lines:
        stripped = str(line).strip()
        if stripped.startswith('[') and stripped.endswith(']'):
            section = stripped[1:-1].strip().lower()
            section_counts[section] = section_counts.get(section, 0) + 1
    for country in countries:
        if section_counts.get(country.lower(), 0) > 1:
            skipped.append((country, ['duplicate CountryType sections']))
            continue
        unsafe = unsafe_country_houses(
            lines,
            country,
            enemy_houses,
            records=records,
            sections=sections,
            usage_index=usage_index,
            scripted_enemies=scripted_enemies,
        )
        if unsafe:
            skipped.append((country, unsafe))
            continue
        base_values = section_value_map_preserve(lines, country)
        values = {}
        for reward, count in stat_effects:
            effect = reward['enemy_effect']
            suffix = reward['enemy_country_suffix']
            prefix = {
                'armor': 'Armor',
                'production': 'BuildTime',
            }[effect]
            key = f'{prefix}{suffix}Mult'
            existing_key = next(
                (name for name in base_values if name.lower() == key.lower()),
                key,
            )
            base = parse_float(base_values.get(existing_key), 1.0)
            effect_values = enemy_effect_values(reward, count, base)
            values[key] = format_multiplier(
                effect_values['final_engine_value']
            )
            applications.append({
                'effect_id': reward['enemy_effect_id'],
                'effect': effect,
                'category': reward.get('enemy_category', 'forces'),
                'country': country,
                'engine_field': existing_key,
                **effect_values,
            })
        if values:
            rules[country] = values
            applied.append(country)
    return rules, applied, skipped, applications


def _direct_weapon_reference_key(key):
    lowered = str(key).lower()
    return (
        lowered in {'primary', 'secondary', 'eliteprimary', 'elitesecondary'}
        or re.fullmatch(r'(?:elite)?weapon\d+', lowered) is not None
    )


def enemy_weapon_supports_direct_buff(weapon_values):
    """Reject spawn-manager control weapons from direct stat cloning."""
    return str(
        _value_case_insensitive(weapon_values, 'Spawner', 'no')
    ).strip().lower() not in {'yes', 'true', '1'}


def _authored_tech_tier(values):
    try:
        tech_level = int(float(str(
            _value_case_insensitive(values, 'TechLevel', -1)
        ).strip()))
    except (TypeError, ValueError):
        return 0
    if tech_level < 1:
        return 0
    if tech_level <= 2:
        return 1
    if tech_level <= 6:
        return 2
    return 3


def enemy_native_unit_buff_rules(
    lines,
    enemy_houses,
    rewards,
    installed_sections,
    authored_map_sections,
):
    """Buff native hostile T1/T2/T3 units; keep player clones separate."""
    counts, definitions = _effect_counts(rewards)
    unit_effects = {
        (int(definition.get('tier', 0)), definition.get('unit_buff_type')): (
            definition, count
        )
        for effect_id, count in counts.items()
        for definition in (definitions[effect_id],)
        if definition.get('enemy_effect') == 'unit'
    }
    if not enemy_houses or not unit_effects:
        return {}, [], [], []

    sections = all_section_value_maps(lines)
    sections_by_lower = {
        str(section).lower(): values for section, values in sections.items()
    }
    installed_by_lower = {
        str(section).lower(): values
        for section, values in (installed_sections or {}).items()
    }
    authored_by_lower = {
        str(section).lower(): values
        for section, values in (authored_map_sections or {}).items()
    }
    records = map_house_records(lines, sections=sections)
    usage_index = build_unit_usage_index(lines)
    hostile_aliases = set()
    hostile_canonical = set()
    for house in enemy_houses:
        record = records.get(house, {})
        hostile_canonical.add(str(house).lower())
        hostile_aliases.update({
            str(house).lower(),
            str(house).removesuffix(' House').lower(),
            str(record.get('country') or '').lower(),
            str(record.get('parent_country') or '').lower(),
        })
    hostile_aliases.discard('')

    def canonical_usage(owner):
        owner = str(owner or '').strip()
        canonical = canonical_house_name(records, owner)
        return str(canonical or owner).lower()

    player_buff_pairs = {
        (str(reward.get('unit') or '').upper(), reward.get('buff_type'))
        for reward in REWARD_POOL
        if reward.get('kind') == 'buff'
        and not reward.get('enemy_reward')
        and reward.get('unit')
    }
    reserved_ids = {
        str(section).lower() for section in sections
    }
    for list_section in (
        'WeaponTypes', 'InfantryTypes', 'VehicleTypes', 'AircraftTypes',
        'BuildingTypes', 'SuperWeaponTypes',
    ):
        reserved_ids.update(
            str(value).lower()
            for value in installed_sections.get(list_section, {}).values()
        )
        reserved_ids.update(
            str(value).lower()
            for value in sections.get(list_section, {}).values()
        )

    rules = {}
    applied_units = []
    skipped = []
    applications = []
    candidate_categories = {'infantry', 'units', 'aircraft'}
    unit_buff_order = (
        'health', 'armor', 'sight', 'ammo', 'self_healing', 'cloak',
        'sensors', 'speed',
    )
    weapon_buff_order = ('damage', 'range', 'reload')

    for unit_id, target in sorted(BUFF_TARGETS.items()):
        unit_id = str(unit_id).upper()
        if (
            target.get('category') not in candidate_categories
            or target.get('special_reward')
            or not target.get('trainable', True)
        ):
            continue
        authored_values = _standalone_clone_values_from_maps(
            installed_by_lower.get(unit_id.lower(), {}),
            authored_by_lower.get(unit_id.lower(), {}),
        )
        tier = _authored_tech_tier(authored_values)
        if not tier or not any(key[0] == tier for key in unit_effects):
            continue
        current_values = _standalone_clone_values_from_maps(
            installed_by_lower.get(unit_id.lower(), {}),
            sections_by_lower.get(unit_id.lower(), {}),
        )
        if not current_values:
            continue
        possible_houses = {
            canonical_usage(house)
            for house in techno_type_possible_houses(
                lines,
                current_values,
                records=records,
                sections=sections,
                sections_by_lower=sections_by_lower,
            )
        }
        relevant_houses = [
            house for house in enemy_houses
            if str(house).lower() in possible_houses
            or str(records.get(house, {}).get('country') or '').lower()
            in possible_houses
        ]
        actual_usage = {
            canonical_usage(owner)
            for owner in usage_index.get(unit_id, ())
        }
        unsafe_usage = sorted(
            owner for owner in actual_usage
            if owner not in hostile_canonical
            and owner not in hostile_aliases
        )
        if unsafe_usage:
            skipped.append(
                f'{unit_id} used by non-hostile House(s): '
                + ', '.join(unsafe_usage)
            )
            continue
        if not relevant_houses and not actual_usage.intersection(
            hostile_canonical | hostile_aliases
        ):
            continue
        if not relevant_houses:
            relevant_houses = list(enemy_houses)

        effective_target = _target_with_effective_unit_stats(
            target, current_values
        )
        unit_updates = {}
        unit_applied = False
        for buff_type in unit_buff_order:
            effect_entry = unit_effects.get((tier, buff_type))
            if not effect_entry or (unit_id, buff_type) not in player_buff_pairs:
                continue
            definition, count = effect_entry
            before_values = {**current_values, **unit_updates}
            candidate = dict(before_values)
            if not apply_unit_buff_value(
                candidate, effective_target, buff_type, count
            ):
                continue
            changed = {
                key: value for key, value in candidate.items()
                if str(_value_case_insensitive(before_values, key, ''))
                != str(value)
            }
            if not changed:
                continue
            unit_updates.update(changed)
            unit_applied = True
            primary_field = {
                'health': 'Strength', 'armor': 'Strength', 'sight': 'Sight',
                'ammo': 'Ammo', 'self_healing': 'SelfHealing.Amount',
                'cloak': 'Cloakable', 'sensors': 'Sensors', 'speed': 'Speed',
            }[buff_type]
            try:
                base_value = float(
                    _value_case_insensitive(before_values, primary_field, 0)
                )
                final_value = float(
                    _value_case_insensitive(candidate, primary_field, 1)
                )
            except (TypeError, ValueError):
                base_value, final_value = 0.0, 1.0
            for house in relevant_houses:
                applications.append({
                    **enemy_effect_values(definition, count),
                    'effect_id': definition['enemy_effect_id'],
                    'effect': enemy_effect_text(definition, count),
                    'category': definition.get('enemy_category', f'T{tier} Units'),
                    'house': house,
                    'country': str(records.get(house, {}).get('country') or ''),
                    'target': unit_id,
                    'engine_field': primary_field,
                    'base_engine_value': base_value,
                    'final_engine_value': final_value,
                })

        direct_weapons = {}
        for key, weapon_id in current_values.items():
            if not _direct_weapon_reference_key(key):
                continue
            weapon_id = str(weapon_id or '').strip()
            if weapon_id and weapon_id.lower() not in {'none', '<none>'}:
                direct_weapons.setdefault(weapon_id, []).append(key)
        for weapon_id, reference_keys in direct_weapons.items():
            active_weapon_effects = [
                (buff_type, unit_effects[(tier, buff_type)])
                for buff_type in weapon_buff_order
                if (tier, buff_type) in unit_effects
                and (unit_id, buff_type) in player_buff_pairs
            ]
            if not active_weapon_effects:
                continue
            weapon_values = _standalone_clone_values_from_maps(
                installed_by_lower.get(weapon_id.lower(), {}),
                sections_by_lower.get(weapon_id.lower(), {}),
            )
            if not weapon_values:
                skipped.append(f'{unit_id}/{weapon_id} source rules unavailable')
                continue
            if not enemy_weapon_supports_direct_buff(weapon_values):
                skipped.append(
                    f'{unit_id}/{weapon_id} spawn-manager weapon unchanged'
                )
                continue
            weapon_base = {
                'damage': parse_float(
                    _value_case_insensitive(weapon_values, 'Damage', 0), 0
                ),
                'range': parse_float(
                    _value_case_insensitive(weapon_values, 'Range', 0), 0
                ),
                'rof': parse_float(
                    _value_case_insensitive(weapon_values, 'ROF', 0), 0
                ),
            }
            updated_weapon = dict(weapon_values)
            weapon_applications = []
            for buff_type, (definition, count) in active_weapon_effects:
                before = dict(updated_weapon)
                if not apply_weapon_buff_value(
                    updated_weapon, weapon_base, buff_type, count
                ):
                    continue
                field = {
                    'damage': 'Damage', 'range': 'Range', 'reload': 'ROF',
                }[buff_type]
                if str(_value_case_insensitive(before, field, '')) == str(
                    _value_case_insensitive(updated_weapon, field, '')
                ):
                    continue
                weapon_applications.append((definition, count, field, before))
            if not weapon_applications:
                continue
            weapon_clone = _collision_safe_type_id(
                f'MORE{tier}{unit_id}{weapon_id}',
                f'enemy-weapon:{tier}:{unit_id}:{weapon_id}',
                reserved_ids,
            )
            _register_map_type(
                rules, lines, installed_sections, 'WeaponTypes', weapon_clone
            )
            rules[weapon_clone] = updated_weapon
            for key in reference_keys:
                unit_updates[key] = weapon_clone
            unit_applied = True
            for definition, count, field, before in weapon_applications:
                base_value = parse_float(
                    _value_case_insensitive(before, field, 0), 0
                )
                final_value = parse_float(
                    _value_case_insensitive(updated_weapon, field, 0), 0
                )
                for house in relevant_houses:
                    applications.append({
                        **enemy_effect_values(definition, count),
                        'effect_id': definition['enemy_effect_id'],
                        'effect': enemy_effect_text(definition, count),
                        'category': definition.get('enemy_category', f'T{tier} Units'),
                        'house': house,
                        'country': str(records.get(house, {}).get('country') or ''),
                        'target': f'{unit_id} / {weapon_id}',
                        'engine_field': field,
                        'base_engine_value': base_value,
                        'final_engine_value': final_value,
                    })
        if unit_updates:
            rules.setdefault(unit_id, {}).update(unit_updates)
        if unit_applied:
            applied_units.append(unit_id)
    return rules, unique_in_order(applied_units), unique_in_order(skipped), applications


def enemy_existing_power_grant_plan(lines, rewards, installed_types):
    """Grant reviewed native powers by runtime index; create no clone section."""
    runtime_types = list(installed_types or ())
    known = {str(type_id).lower() for type_id in runtime_types}
    for type_id in section_value_map_preserve(lines, 'SuperWeaponTypes').values():
        type_id = str(type_id or '').strip()
        if type_id and type_id.lower() not in known:
            known.add(type_id.lower())
            runtime_types.append(type_id)
    actions = []
    names = []
    missing = []
    granted = set()
    for reward in rewards or ():
        if not reward.get('enemy_use_existing_power'):
            continue
        power_id = str(reward.get('superweapon') or '').strip()
        runtime_index = next((
            index for index, candidate in enumerate(runtime_types)
            if str(candidate).lower() == power_id.lower()
        ), None)
        if runtime_index is None:
            missing.append(power_id)
            continue
        if runtime_index in granted:
            continue
        granted.add(runtime_index)
        actions.append(['34', '0', str(runtime_index), '0', '0', '0', '0', 'A'])
        names.append(power_id)
    return actions, names, missing


def enemy_existing_power_rule_overrides(rewards, granted_names):
    """Enable native Action-34 powers for automatic hostile-AI targeting."""
    granted = {
        str(name).strip().lower() for name in (granted_names or ())
    }
    rules = {}
    for reward in rewards or ():
        if not reward.get('enemy_use_existing_power'):
            continue
        power_id = str(reward.get('superweapon') or '').strip()
        targeting = str(reward.get('enemy_ai_targeting') or '').strip()
        if (
            not power_id
            or power_id.lower() not in granted
            or not targeting
            or targeting.lower() == 'none'
        ):
            continue
        values = {
            'SW.AllowAI': 'yes',
            'SW.AITargeting': targeting,
        }
        constraints = str(
            reward.get('enemy_ai_targeting_constraints') or ''
        ).strip()
        if constraints and constraints.lower() != 'none':
            values['SW.AITargeting.Constraints'] = constraints
        rules[power_id] = values
    return rules


def enemy_power_launch_rewards(rewards):
    """Convert earned enemy power entries into AI-only clone inputs."""
    launch = []
    seen = set()
    for reward in rewards or ():
        if (
            not reward.get('enemy_reward')
            or reward.get('enemy_effect') != 'power'
            or not reward.get('superweapon')
            or reward.get('enemy_use_existing_power')
        ):
            continue
        power_id = str(reward['superweapon']).upper()
        if power_id in seen:
            continue
        seen.add(power_id)
        converted = dict(reward)
        converted['kind'] = 'superweapon'
        # This is a transient map-build input, not a progression reward.
        # Bypass enemy-reward canonicalization or it restores kind=buff and
        # cloned_superweapon_plan silently ignores the power.
        converted['enemy_reward'] = False
        converted['superweapon_clone'] = reward['enemy_superweapon_clone']
        converted['superweapon_recharge_multiplier'] = 2
        values = dict(reward.get('superweapon_rules') or {})
        values.update({
            'IsPowered': 'false',
            'Money.Amount': '0',
            'SW.InitialReady': 'yes',
            'SW.AllowAI': 'yes',
            'SW.AllowPlayer': 'no',
            'SW.AITargeting': reward['enemy_ai_targeting'],
            'SW.AITargeting.Constraints': reward.get(
                'enemy_ai_targeting_constraints', 'none'
            ),
            'SW.ShowCameo': 'no',
            'SW.ManualFire': 'no',
            'SW.UseAITargeting': 'yes',
            'SW.FireIntoShroud': 'yes',
            'SW.RequiredHouses': '',
            'SW.ForbiddenHouses': '',
            'SW.AuxBuildings': '',
            'SW.NegBuildings': '',
            'SW.Designators': '',
            'SW.Inhibitors': '',
            'SW.AnyInhibitor': 'no',
            'SW.RangeMaximum': '-1',
            'SW.RangeMinimum': '-1',
        })
        converted['superweapon_rules'] = values
        converted['_runtime_canonical'] = True
        launch.append(converted)
    return launch
