"""Shared Grid units and private Shop unit rules for co-op maps."""

from __future__ import annotations

import hashlib
import re

from randomizer.maps.buff_values import apply_unit_buff_value, apply_weapon_buff_value
from randomizer.maps.base import cloned_superweapon_plan
from randomizer.maps.power_buffs import apply_power_buffs_to_unlock_rewards
from randomizer.maps._shared import (
    STANDALONE_UNIT_RULE_TEMPLATES, STANDALONE_WEAPON_TEMPLATES,
    append_section_entry, next_numeric_section_index, unique_section_key,
)
from randomizer.maps.clone_references import _target_with_effective_unit_stats
from randomizer.maps.base import parse_float
from randomizer.maps.ini import (
    all_section_value_maps_preserve, merge_ini_section_values,
    section_value_map_preserve,
)
from randomizer.maps.shop_modifiers import apply_shop_clone_restrictions
from randomizer.maps.powers import (
    append_static_startup_buildings, append_superweapon_grant_trigger,
)
from randomizer.missions.access import CHAOS_PRIMARY_PRODUCTION
from randomizer.rewards.arsenal import arsenal_unit_type
from randomizer.rewards.catalogue import BUFF_TARGETS, canonical_reward
from randomizer.rewards.roster import (
    installed_rules_template_overlay, randomizer_unit_roster,
)
from randomizer.ui.cameos import installed_rules_registry


_WEAPON_KEY = re.compile(r'(?:elite)?weapon\d+\Z', re.I)
_DIRECT_WEAPON_KEYS = {
    'primary', 'secondary', 'eliteprimary', 'elitesecondary',
    'prismforwarding.supportweapon', 'prismforwarding.elitesupportweapon',
}
_TYPE_LIST = {
    'infantry': 'InfantryTypes', 'vehicles': 'VehicleTypes',
    'naval': 'VehicleTypes', 'aircraft': 'AircraftTypes',
}
_FACTORY_CATEGORY = {
    'infantry': 'infantry', 'vehicles': 'vehicles',
    'naval': 'naval', 'aircraft': 'air',
}
_WEAPON_BUFFS = {'damage', 'range', 'reload'}
_BUFF_ORDER = (
    'health', 'armor', 'sight', 'ammo', 'storage', 'income',
    'passenger_capacity', 'open_topped', 'self_healing', 'cloak',
    'sensors', 'production', 'cost', 'speed',
)


def _weapon_key(key: str) -> bool:
    return key.lower() in _DIRECT_WEAPON_KEYS or bool(_WEAPON_KEY.fullmatch(key))


def _lookup(sections: dict, section: str) -> dict:
    name = next((key for key in sections if key.lower() == section.lower()), None)
    return dict(sections[name]) if name is not None else {}


def apply_coop_rewards(lines: list[str], manifest: dict, family: str, *,
                       country: str | None = None, access_ids=None,
                       buff_counts=None, clone_scope: str = '',
                       production_restrictions=(), building_ids=()) -> None:
    """Add shared Grid clones or one country's private Shop clones.

    Native map objects and AI TaskForces keep their original IDs. Shop uses
    separate countries and clone IDs for the two human slots; Grid keeps the
    original shared country and clone IDs. Shop production restrictions only
    disable the affected player's unit clones.
    """
    if clone_scope not in ('', 'H', 'G'):
        raise ValueError('Invalid co-op clone scope.')
    country = country or manifest['player_country']
    access_ids = (manifest.get('access_ids') or [manifest['unit_id']]
                  if access_ids is None else access_ids)
    counts = (manifest.get('buff_counts') or {}
              if buff_counts is None else buff_counts)
    _, clone_ids, templates = randomizer_unit_roster()
    _, installed = installed_rules_registry(synchronous=True)
    templates, _ = installed_rules_template_overlay(templates, installed)
    map_sections = all_section_value_maps_preserve(lines)
    changes = {}
    registered = {
        key: {str(value).upper() for value in _lookup(installed, key).values()}
        | {str(value).upper() for value in _lookup(map_sections, key).values()}
        for key in ('InfantryTypes', 'VehicleTypes', 'AircraftTypes', 'WeaponTypes')
    }
    next_key = {
        key: 310000 + index * 10000
        for index, key in enumerate(registered)
    }
    occupied_keys = {
        key: set(_lookup(installed, key)) | set(_lookup(map_sections, key))
        for key in registered
    }

    def register(type_list: str, type_id: str) -> None:
        if type_list not in registered:
            registered[type_list] = {
                str(value).upper() for value in _lookup(installed, type_list).values()
            } | {
                str(value).upper() for value in _lookup(map_sections, type_list).values()
            }
            occupied_keys[type_list] = (
                set(_lookup(installed, type_list))
                | set(_lookup(map_sections, type_list))
            )
            next_key[type_list] = 310000 + len(registered) * 10000
        if type_id.upper() in registered[type_list]:
            return
        while str(next_key[type_list]) in occupied_keys[type_list]:
            next_key[type_list] += 1
        key = str(next_key[type_list])
        changes.setdefault(type_list, {})[key] = type_id
        occupied_keys[type_list].add(key)
        registered[type_list].add(type_id.upper())
        next_key[type_list] += 1

    veteran = {'Infantry': [], 'Units': [], 'Aircraft': []}
    handled = {}
    source_rules = {}
    for source_id in access_ids:
        source_id = str(source_id).upper()
        target = BUFF_TARGETS.get(source_id)
        unit_type = arsenal_unit_type(source_id, target)
        if not target or unit_type not in _TYPE_LIST:
            raise ValueError(f'Unsupported co-op unit reward: {source_id}')
        clone_id = (f'MOR{clone_scope}{source_id}' if clone_scope
                    else clone_ids.get(source_id))
        template = templates.get(source_id)
        if not clone_id or not template:
            native = _lookup(installed, source_id)
            native.update(_lookup(map_sections, source_id))
            if not native:
                raise ValueError(f'No source definition for co-op unit: {source_id}')
            clone_id = f'MOR{clone_scope or "P"}{source_id}'
            template = dict(native)
            template.setdefault('Image', source_id)
        factory = CHAOS_PRIMARY_PRODUCTION[family].get(_FACTORY_CATEGORY[unit_type])
        if not factory:
            raise ValueError(f'No co-op factory for {source_id}')
        for type_list, definitions in STANDALONE_UNIT_RULE_TEMPLATES.get(
            source_id, {},
        ).items():
            for type_id, definition in definitions.items():
                if not _lookup(installed, type_id) and not _lookup(map_sections, type_id):
                    changes[type_id] = dict(definition)
                register(type_list, type_id)
        source_values = _lookup(installed, source_id)
        source_values.update(_lookup(map_sections, source_id))
        values = dict(template)
        # Keep installed/map weapon and core stat changes that the ordinary
        # single-player clone path would inherit.
        for key, value in source_values.items():
            if key.lower() in {
                'strength', 'cost', 'speed', 'sight', 'ammo', 'primary',
                'secondary', 'eliteprimary', 'elitesecondary',
            } or _weapon_key(key):
                values[key] = value
        values.update({
            'TechLevel': '1', 'Owner': country, 'RequiredHouses': country,
            'ForbiddenHouses': 'none', 'Prerequisite': factory,
            'PrerequisiteOverride': None, 'Prerequisite.List0': None,
            'Prerequisite.Lists': None, 'Prerequisite.Negative': None,
            'AllowedToStartInMultiplayer': 'no',
        })
        unit_counts = counts.get(source_id, {})
        effective_target = _target_with_effective_unit_stats(target, values)
        for buff_type in _BUFF_ORDER:
            if buff_type not in unit_counts:
                continue
            amount = unit_counts[buff_type]
            if not apply_unit_buff_value(values, effective_target, buff_type, amount):
                raise ValueError(f'Cannot apply {buff_type} to {source_id}')
        for buff_type in sorted(set(unit_counts) - set(_BUFF_ORDER)):
            amount = unit_counts[buff_type]
            if buff_type in {'build_limit', 'building_limit'}:
                base_limit = int(str(values.get('BuildLimit') or target.get('build_limit') or '1'))
                values['BuildLimit'] = str(max(1, base_limit) + amount)
            elif buff_type != 'veteran' and buff_type not in _WEAPON_BUFFS:
                raise ValueError(f'Unsupported co-op buff: {source_id} {buff_type}')
        weapon_counts = {
            key: value for key, value in unit_counts.items() if key in _WEAPON_BUFFS
        }
        if weapon_counts:
            weapon_targets = {
                str(key).upper(): stats
                for key, stats in target.get('weapons', {}).items()
            }
            seen_weapons = {}
            for field, weapon_id in list(values.items()):
                if not _weapon_key(field) or not weapon_id or str(weapon_id).lower() == 'none':
                    continue
                native_weapon = str(weapon_id)
                weapon_key = native_weapon.upper()
                if weapon_key not in seen_weapons:
                    weapon_values = _lookup(installed, native_weapon)
                    weapon_values.update(_lookup(map_sections, native_weapon))
                    if not weapon_values:
                        weapon_values = dict(
                            STANDALONE_WEAPON_TEMPLATES.get(weapon_key, {})
                        )
                    if not weapon_values:
                        raise ValueError(f'Missing weapon {native_weapon} for {source_id}')
                    defaults = weapon_targets.get(weapon_key, {})
                    base_stats = {
                        key: parse_float(
                            next((value for field_name, value in weapon_values.items()
                                  if field_name.lower() == field.lower()), None),
                            defaults.get(key, 0),
                        )
                        for key, field in (
                            ('damage', 'Damage'), ('range', 'Range'), ('rof', 'ROF'),
                        )
                    }
                    changed = False
                    for buff_type, amount in sorted(weapon_counts.items()):
                        changed |= apply_weapon_buff_value(
                            weapon_values, base_stats, buff_type, amount,
                        )
                    if changed:
                        identity = (f'{clone_scope}|{source_id}|{weapon_key}'
                                    if clone_scope else f'{source_id}|{weapon_key}')
                        suffix = hashlib.sha1(identity.encode('ascii')).hexdigest()[:12].upper()
                        new_weapon = f'MOR{clone_scope}CW{suffix}'
                        changes[new_weapon] = weapon_values
                        register('WeaponTypes', new_weapon)
                        seen_weapons[weapon_key] = new_weapon
                    else:
                        seen_weapons[weapon_key] = native_weapon
                values[field] = seen_weapons[weapon_key]
        if unit_counts.get('veteran'):
            category = {
                'infantry': 'Infantry', 'vehicles': 'Units',
                'naval': 'Units', 'aircraft': 'Aircraft',
            }[unit_type]
            veteran[category].append(clone_id)
        changes[clone_id] = values
        handled[source_id] = {'clone_id': clone_id}
        source_rules[source_id] = source_values
        type_list = _TYPE_LIST[unit_type]
        register(type_list, clone_id)
    if production_restrictions:
        apply_shop_clone_restrictions(
            changes, handled, source_rules,
            {'shop_production_restrictions': production_restrictions},
        )
    for source_id in building_ids:
        source_id = str(source_id).upper()
        if BUFF_TARGETS.get(source_id, {}).get('category') not in {
            'defenses', 'special_buildings',
        }:
            raise ValueError(f'Unsupported co-op building reward: {source_id}')
        native = _lookup(installed, source_id)
        native.update(_lookup(map_sections, source_id))
        template = templates.get(source_id)
        if not native and not template:
            raise ValueError(f'No source definition for co-op building: {source_id}')
        clone_id = f'MOR{clone_scope or "P"}{source_id}'
        # Some reward buildings (for example NACLONS) exist only in the
        # packaged player roster. Use that complete reviewed template when
        # the installed rules have no native section.
        values = dict(template or native)
        values.update({
            'Image': native.get('Image') or source_id,
            'TechLevel': '1', 'Owner': country, 'RequiredHouses': country,
            'ForbiddenHouses': 'none',
            'Prerequisite': CHAOS_PRIMARY_PRODUCTION[family]['base'],
            'PrerequisiteOverride': None, 'Prerequisite.List0': None,
            'Prerequisite.Lists': None, 'Prerequisite.Negative': None,
            'AllowedToStartInMultiplayer': 'no',
        })
        changes[clone_id] = values
        register('BuildingTypes', clone_id)
    factory_categories = {
        'infantry': 'infantry', 'vehicles': 'vehicles',
        'aircraft': 'air', 'naval': 'naval',
    }
    for category in production_restrictions:
        factory = CHAOS_PRIMARY_PRODUCTION[family][factory_categories[category]]
        current = _lookup(installed, factory)
        current.update(_lookup(map_sections, factory))
        blocked = [
            item.strip() for item in str(current.get('ForbiddenHouses') or '').split(',')
            if item.strip().lower() not in {'', 'none', '<none>'}
        ]
        if country not in blocked:
            blocked.append(country)
        changes.setdefault(factory, {})['ForbiddenHouses'] = ','.join(blocked)
    country_values = {}
    for category, ids in veteran.items():
        if ids:
            key = f'Veteran{category}'
            existing = str(_lookup(map_sections, country).get(key, ''))
            country_values[key] = ','.join(filter(None, [existing, *ids]))
    if country_values:
        changes[country] = country_values
    merge_ini_section_values(lines, changes)


def apply_shop_credit_bonus(lines: list[str], country: str, scope: str,
                            amount: int) -> None:
    """Grant one player's credit delta through a private map-start cash building."""
    if not amount:
        return
    if scope not in {'H', 'G'}:
        raise ValueError('Invalid co-op credit scope.')
    _powers, installed = installed_rules_registry(synchronous=True)
    source = _lookup(installed, 'CASHGIVE')
    if not source:
        raise ValueError('Installed cash grant building is missing.')
    type_id = f'MOR{scope}CASH'
    values = dict(source)
    values.update({
        'Image': 'CASHGIVE', 'TechLevel': '-1', 'Owner': country,
        'RequiredHouses': country, 'ForbiddenHouses': 'none',
        'ProduceCashStartup': str(amount), 'ProduceCashAmount': '0',
        'ProduceCashDelay': '0', 'Capturable': 'no', 'Selectable': 'no',
        'Insignificant': 'yes', 'InvisibleInGame': 'yes',
        'IsPassable': 'yes', 'LegalTarget': 'no', 'Unsellable': 'yes',
    })
    registered = {
        str(item).upper() for item in _lookup(installed, 'BuildingTypes').values()
    } | {
        str(item).upper() for item in section_value_map_preserve(
            lines, 'BuildingTypes'
        ).values()
    }
    changes = {type_id: values}
    if type_id not in registered:
        occupied = set(section_value_map_preserve(lines, 'BuildingTypes'))
        key = 390000
        while str(key) in occupied:
            key += 1
        changes['BuildingTypes'] = {str(key): type_id}
    merge_ini_section_values(lines, changes)
    if not append_superweapon_grant_trigger(
        lines, [country], [], startup_buildings=[type_id],
    ):
        raise ValueError(f'Could not place private starting credits for {country}.')


def _append_grid_power_providers(lines, country, actions, buildings,
                                 installed_types, installed):
    """Give both human slots providers using native Player @ A/B transfers.

    Trigger owners resolve a country to its first house. Both Grid players
    use the same country, so action 34 and country-owned static providers only
    grant powers to one player. Neutral hidden buildings with separate tags
    use action 14's explicit multiplayer house indices, as authored co-op
    maps do when assigning their starting units and cash buildings.
    """
    runtime_types = list(installed_types)
    known = {type_id.lower() for type_id in runtime_types}
    for type_id in section_value_map_preserve(lines, 'SuperWeaponTypes').values():
        if type_id.lower() not in known:
            known.add(type_id.lower())
            runtime_types.append(type_id)
    dummy = _lookup(installed, 'DUMMYDUMMY')
    if not dummy and actions:
        raise ValueError('Installed Grid power provider building is missing.')
    reserved = {name.upper() for name in installed}
    reserved.update(name.upper() for name in all_section_value_maps_preserve(lines))
    providers = list(buildings)
    provided_powers = {
        power.strip().lower()
        for building in providers
        for key, value in section_value_map_preserve(lines, building).items()
        if key.lower() in {'superweapon', 'superweapon2', 'superweapons'}
        for power in str(value).split(',') if power.strip()
    }
    rules = {}
    type_keys = set(_lookup(installed, 'BuildingTypes'))
    type_keys.update(section_value_map_preserve(lines, 'BuildingTypes'))
    next_type_key = max(390000, next_numeric_section_index(lines, 'BuildingTypes'))
    for action in actions:
        if action[0] != '34':
            raise ValueError('Unsupported shared Grid power grant action.')
        power_id = runtime_types[int(action[2])]
        if power_id.lower() in provided_powers:
            continue
        provided_powers.add(power_id.lower())
        provider = f'MORGridPower{action[2]}'
        suffix = 1
        while provider.upper() in reserved:
            provider = f'MORGridPower{action[2]}_{suffix}'
            suffix += 1
        reserved.add(provider.upper())
        values = dict(dummy)
        values.update({
            'Name': 'Randomizer shared Grid power provider', 'Image': 'DUMMYDUMMY',
            'SuperWeapon': power_id, 'SuperWeapon2': None, 'SuperWeapons': None,
            'TechLevel': '-1', 'BuildLimit': '0', 'Owner': country,
            'RequiredHouses': country, 'ForbiddenHouses': 'none',
            'Power': '0', 'Powered': 'false', 'AIBuildThis': 'no',
            'Capturable': 'no', 'Selectable': 'no', 'Unsellable': 'yes',
            'Insignificant': 'yes', 'InvisibleInGame': 'yes', 'IsPassable': 'yes',
            'LegalTarget': 'no', 'KeepAlive': 'no', 'DontScore': 'yes',
            'ImmuneToEMP': 'yes', 'BaseNormal': 'no', 'AIBaseNormal': 'no',
            'IsBaseDefense': 'no', 'Firestorm.Wall': 'no', 'Sight': '0',
        })
        rules[provider] = values
        while str(next_type_key) in type_keys:
            next_type_key += 1
        rules.setdefault('BuildingTypes', {})[str(next_type_key)] = provider
        type_keys.add(str(next_type_key))
        next_type_key += 1
        providers.append(provider)
    merge_ini_section_values(lines, rules)
    if not providers:
        return
    for slot, house_index in enumerate((4475, 4476), 1):
        trigger = unique_section_key(lines, ('Events', 'Actions', 'Triggers'), 'RNGGP')
        tag = unique_section_key(lines, ('Tags',), 'RNGGT')
        name = f'MOR Shared Grid Powers P{slot}'
        append_section_entry(lines, 'Events', trigger, '1,13,0,1')
        append_section_entry(lines, 'Actions', trigger, f'1,14,0,{house_index},0,0,0,0,A')
        append_section_entry(lines, 'Triggers', trigger, f'Neutral,<none>,{name},0,1,1,1,0')
        append_section_entry(lines, 'Tags', tag, f'0,{name},{trigger}')
        previous = set(section_value_map_preserve(lines, 'Structures'))
        placed = append_static_startup_buildings(lines, ['Neutral'], providers)
        if len(placed) != len(providers):
            raise ValueError(f'Could not place shared Grid powers for player {slot}.')
        changes = {}
        for key, value in section_value_map_preserve(lines, 'Structures').items():
            if key not in previous:
                tokens = value.split(',')
                tokens[6] = tag
                changes[key] = ','.join(tokens)
        merge_ini_section_values(lines, {'Structures': changes})


def apply_coop_power_rewards(lines: list[str], country: str,
                             reward_ids: list[str], *, shared_grid=False) -> None:
    """Grant earned powers to a private Shop country or both shared Grid slots."""
    if not reward_ids:
        return
    rewards = [canonical_reward({'name': name}) for name in reward_ids]
    installed_types, installed = installed_rules_registry(synchronous=True)
    rewards = apply_power_buffs_to_unlock_rewards(rewards, installed)
    rules, actions, _names, startup, static, missing = cloned_superweapon_plan(
        lines, rewards, installed_types, installed,
        superweapon_required_houses=[country], force_required_houses=True,
    )
    if missing:
        raise ValueError('Co-op power source rules are missing: ' + ', '.join(missing))
    if not rules:
        raise ValueError('Co-op power rewards produced no map rules.')
    merge_ini_section_values(lines, rules)
    if shared_grid:
        _append_grid_power_providers(
            lines, country, actions, [*startup, *static], installed_types, installed,
        )
        return
    if static:
        placed = append_static_startup_buildings(lines, [country], static)
        if len(placed) != len(static):
            raise ValueError(f'Could not place static power providers for {country}.')
    if (actions or startup) and not append_superweapon_grant_trigger(
        lines, [country], actions, startup_buildings=startup,
    ):
        raise ValueError(f'Could not grant earned powers to {country}.')
