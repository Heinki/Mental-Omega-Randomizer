"""Map-local hostile AI rewards for registered two-player co-op maps."""

from collections import Counter
import hashlib
import re

from randomizer.maps.base import cloned_superweapon_plan, format_multiplier, parse_float
from randomizer.maps.buff_values import apply_unit_buff_value, apply_weapon_buff_value
from randomizer.maps.clone_references import _target_with_effective_unit_stats
from randomizer.maps.enemy_scaling import (
    _authored_tech_tier, enemy_existing_power_grant_plan,
    enemy_existing_power_rule_overrides,
    enemy_power_launch_rewards, enemy_weapon_supports_direct_buff,
)
from randomizer.maps.ini import (
    all_section_value_maps_preserve, merge_ini_section_values,
    section_value_map_preserve,
)
from randomizer.maps.powers import (
    append_static_startup_buildings, append_superweapon_grant_trigger,
)
from randomizer.rewards.catalogue import BUFF_TARGETS, canonical_reward
from randomizer.rewards.enemy_scaling import enemy_effect_values
from randomizer.ui.cameos import installed_rules_registry


def _get(values, key, default=None):
    return next((value for name, value in values.items()
                 if str(name).lower() == key.lower()), default)


def _csv(value):
    return {item.strip().upper() for item in str(value or '').split(',') if item.strip()}


def _safe_enemy_unit_buffs(lines, enemies, players, counts, rewards, installed):
    """Buff native types only when no human or neutral map object uses them."""
    effects = {
        (int(reward.get('tier', 0)), reward.get('unit_buff_type')): count
        for effect_id, count in counts.items()
        for reward in (rewards[effect_id],)
        if count and reward.get('enemy_effect') == 'unit'
    }
    if not effects:
        return ()
    map_sections = all_section_value_maps_preserve(lines)
    map_by_lower = {key.lower(): value for key, value in map_sections.items()}
    installed_by_lower = {key.lower(): value for key, value in installed.items()}
    map_owners = {}
    for section in ('Units', 'Infantry', 'Aircraft', 'Structures'):
        for raw in section_value_map_preserve(lines, section).values():
            parts = str(raw).split(',')
            if len(parts) >= 2:
                map_owners.setdefault(parts[1].strip().upper(), set()).add(
                    parts[0].strip().upper()
                )
    enemies_upper = {country.upper() for country in enemies}
    players_upper = {country.upper() for country in players}
    occupied_weapons = {
        str(value).upper() for value in installed.get('WeaponTypes', {}).values()
    } | {
        str(value).upper() for value in section_value_map_preserve(
            lines, 'WeaponTypes'
        ).values()
    }
    weapon_keys = set(section_value_map_preserve(lines, 'WeaponTypes'))
    next_weapon_key = 380000
    changes = {}
    affected = []
    for unit_id, target in sorted(BUFF_TARGETS.items()):
        unit_id = str(unit_id).upper()
        if target.get('category') not in {'infantry', 'units', 'aircraft'}:
            continue
        values = dict(installed_by_lower.get(unit_id.lower(), {}))
        values.update(map_by_lower.get(unit_id.lower(), {}))
        owners = _csv(_get(values, 'Owner'))
        if (not owners.intersection(enemies_upper)
                or owners.intersection(players_upper)
                or map_owners.get(unit_id, set()) - enemies_upper):
            continue
        tier = _authored_tech_tier(values)
        if not any(effect_tier == tier for effect_tier, _ in effects):
            continue
        updated = dict(values)
        effective_target = _target_with_effective_unit_stats(target, values)
        for buff_type in (
            'health', 'armor', 'sight', 'ammo', 'self_healing',
            'cloak', 'sensors', 'speed',
        ):
            amount = effects.get((tier, buff_type), 0)
            if amount:
                apply_unit_buff_value(updated, effective_target, buff_type, amount)
        weapon_counts = {
            buff_type: effects[(tier, buff_type)]
            for buff_type in ('damage', 'range', 'reload')
            if (tier, buff_type) in effects
        }
        if weapon_counts:
            cloned_weapons = {}
            for field, weapon_id in list(updated.items()):
                if not re.fullmatch(r'(?:elite)?weapon\d*|primary|secondary|eliteprimary|elitesecondary',
                                    field, re.I):
                    continue
                weapon_id = str(weapon_id or '').strip()
                if not weapon_id or weapon_id.lower() == 'none':
                    continue
                weapon_key = weapon_id.upper()
                if weapon_key in cloned_weapons:
                    updated[field] = cloned_weapons[weapon_key]
                    continue
                weapon = dict(installed_by_lower.get(weapon_id.lower(), {}))
                weapon.update(map_by_lower.get(weapon_id.lower(), {}))
                if not weapon or not enemy_weapon_supports_direct_buff(weapon):
                    continue
                defaults = {
                    str(name).upper(): stats
                    for name, stats in target.get('weapons', {}).items()
                }.get(weapon_key, {})
                base = {
                    key: parse_float(_get(weapon, field_name), defaults.get(key, 0))
                    for key, field_name in (
                        ('damage', 'Damage'), ('range', 'Range'), ('rof', 'ROF'),
                    )
                }
                clone_values = dict(weapon)
                changed = False
                for buff_type, amount in sorted(weapon_counts.items()):
                    changed |= apply_weapon_buff_value(
                        clone_values, base, buff_type, amount,
                    )
                if not changed:
                    continue
                suffix = hashlib.sha1(f'{unit_id}:{weapon_key}'.encode()).hexdigest()[:12].upper()
                clone_id = f'MORCEW{suffix}'
                changes[clone_id] = clone_values
                if clone_id not in occupied_weapons:
                    while str(next_weapon_key) in weapon_keys:
                        next_weapon_key += 1
                    changes.setdefault('WeaponTypes', {})[str(next_weapon_key)] = clone_id
                    weapon_keys.add(str(next_weapon_key))
                    occupied_weapons.add(clone_id)
                    next_weapon_key += 1
                cloned_weapons[weapon_key] = clone_id
                updated[field] = clone_id
        delta = {key: value for key, value in updated.items()
                 if str(_get(values, key, '')) != str(value)}
        if delta:
            changes[unit_id] = delta
            affected.append(unit_id)
    if changes:
        merge_ini_section_values(lines, changes)
    return tuple(affected)


def apply_coop_enemy_rewards(lines, enemy_countries, player_countries, reward_ids):
    """Apply country bonuses and AI powers without touching player countries."""
    if not reward_ids:
        return ()
    enemies = sorted(set(enemy_countries))
    if not enemies or set(enemies).intersection(player_countries):
        raise ValueError('Co-op enemy rewards overlap a player country.')
    installed_types, installed = installed_rules_registry(synchronous=True)
    counts = Counter()
    rewards = {}
    for name in reward_ids:
        reward = canonical_reward({'name': name})
        if not reward.get('enemy_reward'):
            raise ValueError(f'Invalid co-op enemy reward: {name}')
        effect_id = str(reward['enemy_effect_id'])
        counts[effect_id] += 1
        rewards[effect_id] = reward
    for effect_id, count in counts.items():
        counts[effect_id] = min(count, int(rewards[effect_id]['enemy_maximum']))

    changes = {}
    for country in enemies:
        native = dict(installed.get(country, {}))
        native.update(section_value_map_preserve(lines, country))
        for effect_id, count in counts.items():
            reward = rewards[effect_id]
            effect = reward.get('enemy_effect')
            if effect not in {'armor', 'production'}:
                continue
            prefix = 'Armor' if effect == 'armor' else 'BuildTime'
            key = f'{prefix}{reward["enemy_country_suffix"]}Mult'
            base = parse_float(_get(native, key), 1.0)
            result = enemy_effect_values(reward, count, base)
            changes.setdefault(country, {})[key] = format_multiplier(
                result['final_engine_value']
            )
    if changes:
        merge_ini_section_values(lines, changes)
    affected_units = _safe_enemy_unit_buffs(
        lines, enemies, player_countries, counts, rewards, installed,
    )

    power_rewards = [
        rewards[effect_id] for effect_id, count in counts.items()
        if count and rewards[effect_id].get('enemy_effect') == 'power'
    ]
    if power_rewards:
        actions, granted_names, missing = enemy_existing_power_grant_plan(
            lines, power_rewards, installed_types,
        )
        if missing:
            raise ValueError('Co-op enemy power sources are missing: ' + ', '.join(missing))
        existing_rules = enemy_existing_power_rule_overrides(
            power_rewards, granted_names,
        )
        if existing_rules:
            merge_ini_section_values(lines, existing_rules)
        clones = enemy_power_launch_rewards(power_rewards)
        startup = []
        if clones:
            rules, cloned_actions, _names, startup, static, missing = (
                cloned_superweapon_plan(
                    lines, clones, installed_types, installed,
                    superweapon_required_houses=enemies,
                    allow_player=False, allow_ai=True,
                    force_required_houses=True,
                )
            )
            if missing:
                raise ValueError('Co-op enemy power rules are missing: ' + ', '.join(missing))
            merge_ini_section_values(lines, rules)
            actions.extend(cloned_actions)
            if static:
                for country in enemies:
                    placed = append_static_startup_buildings(lines, [country], static)
                    if len(placed) != len(static):
                        raise ValueError(f'Could not place AI power providers for {country}.')
        if actions or startup:
            for country in enemies:
                if not append_superweapon_grant_trigger(
                    lines, [country], actions, startup_buildings=startup,
                ):
                    raise ValueError(f'Could not grant AI powers to {country}.')
    return affected_units
