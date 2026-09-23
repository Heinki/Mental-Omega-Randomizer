"""Shared player production and unit buffs for a two-player co-op map."""

from __future__ import annotations

import hashlib
import re

from randomizer.maps.buff_values import apply_unit_buff_value, apply_weapon_buff_value
from randomizer.maps._shared import (
    STANDALONE_UNIT_RULE_TEMPLATES, STANDALONE_WEAPON_TEMPLATES,
)
from randomizer.maps.clone_references import _target_with_effective_unit_stats
from randomizer.maps.base import parse_float
from randomizer.maps.ini import (
    all_section_value_maps_preserve, merge_ini_section_values,
    section_value_map_preserve,
)
from randomizer.missions.access import CHAOS_PRIMARY_PRODUCTION
from randomizer.rewards.arsenal import arsenal_unit_type
from randomizer.rewards.catalogue import BUFF_TARGETS
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


def apply_coop_rewards(lines: list[str], manifest: dict, family: str) -> None:
    """Give both human slots the same player-owned TechnoTypes.

    Both slots use the co-op map's sole allowed country. Native map objects and
    AI TaskForces keep their original IDs. The production clones carry buffs.
    """
    country = manifest['player_country']
    access_ids = manifest.get('access_ids') or [manifest['unit_id']]
    counts = manifest.get('buff_counts') or {}
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
    for source_id in access_ids:
        source_id = str(source_id).upper()
        target = BUFF_TARGETS.get(source_id)
        unit_type = arsenal_unit_type(source_id, target)
        if not target or unit_type not in _TYPE_LIST:
            raise ValueError(f'Unsupported co-op unit reward: {source_id}')
        clone_id = clone_ids.get(source_id)
        template = templates.get(source_id)
        if not clone_id or not template:
            native = _lookup(installed, source_id)
            native.update(_lookup(map_sections, source_id))
            if not native:
                raise ValueError(f'No source definition for co-op unit: {source_id}')
            clone_id = f'MORP{source_id}'
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
                        suffix = hashlib.sha1(
                            f'{source_id}|{weapon_key}'.encode('ascii')
                        ).hexdigest()[:12].upper()
                        new_weapon = f'MORCW{suffix}'
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
        type_list = _TYPE_LIST[unit_type]
        register(type_list, clone_id)
    country_values = {}
    for category, ids in veteran.items():
        if ids:
            key = f'Veteran{category}'
            existing = str(_lookup(map_sections, country).get(key, ''))
            country_values[key] = ','.join(filter(None, [existing, *ids]))
    if country_values:
        changes[country] = country_values
    merge_ini_section_values(lines, changes)
