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
from randomizer.coop.access import clone_production_owners, standard_coop_access_rules
from randomizer.coop.native_buildings import (
    apply_building_reward_buffs, preserve_native_building_abilities,
)
from randomizer.coop.native_units import TRANSFORM_REFERENCE_KEYS, unit_transform_plan
from randomizer.maps.powers import (
    append_static_startup_buildings, append_superweapon_grant_trigger,
)
from randomizer.missions.access import CHAOS_PRIMARY_PRODUCTION
from randomizer.rewards.arsenal import arsenal_unit_type
from randomizer.rewards.catalogue import BUFF_TARGETS, canonical_reward
from randomizer.rewards.definitions import LIMITED_HERO_UNIT_IDS
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
_WEAPON_BUFFS = {'damage', 'range', 'reload', 'mind_control'}
_BUFF_ORDER = (
    'health', 'armor', 'sight', 'ammo', 'storage', 'income',
    'passenger_capacity', 'initial_passenger', 'open_topped', 'self_healing',
    'self_healing_cap', 'self_healing_rate', 'cloak',
    'sensors', 'production', 'cost', 'speed',
)


def _weapon_key(key: str) -> bool:
    return key.lower() in _DIRECT_WEAPON_KEYS or bool(_WEAPON_KEY.fullmatch(key))


def _lookup(sections: dict, section: str) -> dict:
    name = next((key for key in sections if key.lower() == section.lower()), None)
    return dict(sections[name]) if name is not None else {}


def _remove_building_cap(values: dict) -> None:
    """Remove concurrent/lifetime caps while retaining explicit build locks.

    A missing BuildLimit uses the engine's unlimited default. Zero instead
    blocks production, and may protect hidden implementation types, so it
    must never be treated as an unlimited setting.
    """
    for key in list(values):
        if str(key).lower() != 'buildlimit':
            continue
        try:
            limited = int(str(values[key]).strip()) != 0
        except (TypeError, ValueError):
            continue
        if limited:
            values.pop(key)


def apply_coop_rewards(lines: list[str], manifest: dict, family: str, *,
                       country: str | None = None, access_ids=None,
                       buff_counts=None, clone_scope: str = '',
                       production_restrictions=(), building_ids=(),
                       shop_settings=None) -> None:
    """Add shared clones or one country's isolated Shop/challenge roster.

    Native map objects and AI TaskForces keep their original IDs. Shop uses
    separate countries and clone IDs for the two human slots. Challenges do
    the same when players choose different countries, sharing one clone set
    when their country matches. Shop production restrictions only
    disable the affected player's unit clones.
    """
    if clone_scope not in ('', 'H', 'G'):
        raise ValueError('Invalid co-op clone scope.')
    country = country or manifest['player_country']
    access_ids = (manifest.get('access_ids', [manifest['unit_id']])
                  if access_ids is None else access_ids)
    counts = (manifest.get('buff_counts') or {}
              if buff_counts is None else buff_counts)
    unlimited_buildings = manifest.get('unlimited_buildings', False)
    building_roots = {str(item).upper() for item in building_ids}
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
    unit_plans = unit_transform_plan(
        access_ids, templates, clone_ids, installed, map_sections, clone_scope,
        building_access_ids=building_ids,
    )
    unlimited_building_forms = set()
    if unlimited_buildings:
        unlimited_building_forms.update(
            plan.clone_id for plan in unit_plans if plan.type_list == 'BuildingTypes'
        )
        # Follow earned building roots explicitly: if SMIN also has its own
        # unit access, its plan can be rooted at SMIN rather than War Rig.
        # Removing only the deployed building's cap would leave that mobile
        # half enforcing the same shared deploy-pair count.
        by_clone = {plan.clone_id.upper(): plan for plan in unit_plans}
        pending = [plan for plan in unit_plans if plan.source_id in building_roots]
        visited = set()
        for plan in pending:
            if plan.clone_id in visited:
                continue
            visited.add(plan.clone_id)
            unlimited_building_forms.add(plan.clone_id)
            for key, value in plan.template.items():
                if str(key).lower() not in TRANSFORM_REFERENCE_KEYS:
                    continue
                for token in str(value or '').split(','):
                    related = by_clone.get(token.strip().upper())
                    if related is not None and related.clone_id not in visited:
                        pending.append(related)
    for plan in unit_plans:
        # War Rig access starts as a building and undeploys into a mobile
        # form. Its visible building is processed by the building loop once;
        # its private mobile form follows the same hidden-unit path as Grumble.
        if plan.buildable and plan.type_list == 'BuildingTypes':
            continue
        source_id = plan.source_id
        target = BUFF_TARGETS.get(source_id) or BUFF_TARGETS.get(plan.root_id)
        unit_type = arsenal_unit_type(source_id, target)
        if not target or (plan.buildable and unit_type not in _TYPE_LIST):
            raise ValueError(f'Unsupported co-op unit reward: {source_id}')
        clone_id = plan.clone_id
        template = plan.template
        factory = (CHAOS_PRIMARY_PRODUCTION[family].get(_FACTORY_CATEGORY[unit_type])
                   if plan.buildable else None)
        if plan.buildable and not factory:
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
        # Portable access replaces the source's campaign/factory gates. For
        # example, Stardust's installed stolen-tech flag otherwise silently
        # survives its earned unlock and keeps the reward unbuildable.
        for key in list(values):
            lowered = str(key).lower()
            if (lowered.startswith('prerequisite')
                    or lowered in {'factoryowners', 'factoryowners.forbidden', 'builtat'}):
                values.pop(key)
        values.update({
            'TechLevel': '1' if plan.buildable else '-1',
            'Owner': clone_production_owners(source_values, country),
            'RequiredHouses': country,
            'ForbiddenHouses': 'none', 'Prerequisite': factory,
            'PrerequisiteOverride': None, 'Prerequisite.List0': None,
            'Prerequisite.Lists': None, 'Prerequisite.Negative': None,
            'AllowedToStartInMultiplayer': 'no',
        })
        if plan.buildable and manifest.get('reward_mode') == 'Standard':
            # Rejuvenator is a portable Neutral reward, with no Standard
            # faction/access-catalog factory. Its earned clone uses the
            # selected human faction's vehicle factory already set above.
            if source_id != 'REJU':
                values.update(standard_coop_access_rules(source_id))
        # Mode switches keep the earned root's stacks; hidden forms are never
        # independent unlocks or a route around a production restriction.
        unit_counts = counts.get(source_id, counts.get(plan.root_id, {}))
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
        if (manifest.get('unlimited_hero_units')
                and plan.root_id in LIMITED_HERO_UNIT_IDS):
            # Match the campaign clone policy: an absent BuildLimit removes
            # the simultaneous-unit cap, whereas zero would block production.
            # Change only earned player clones, after capacity buffs, so the
            # native AI/script identities retain their authored limits. Shared
            # country clones work for both humans; the engine counts per House.
            for key in list(values):
                if key.lower() == 'buildlimit':
                    values.pop(key)
        if plan.clone_id in unlimited_building_forms:
            # Include hidden deployed structures and War Rig's mobile form:
            # Ares counts both sides of a deploy pair against either cap.
            # Mobile hero roots remain governed by their separate setting.
            _remove_building_cap(values)
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
                        mind_control = weapon_key in target.get('mind_control_weapons', {})
                        if ((buff_type == 'mind_control' and not mind_control)
                                or (buff_type == 'damage' and mind_control)):
                            continue
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
        if unit_counts.get('veteran') and plan.type_list != 'BuildingTypes':
            category = {
                'infantry': 'Infantry', 'vehicles': 'Units',
                'naval': 'Units', 'aircraft': 'Aircraft',
            }[unit_type]
            veteran[category].append(clone_id)
        changes[clone_id] = values
        handled[source_id] = {'clone_id': clone_id}
        source_rules[source_id] = source_values
        register(plan.type_list, clone_id)
    plans_by_source = {plan.source_id: plan for plan in unit_plans}
    for plan in unit_plans:
        root = plans_by_source[plan.root_id]
        handled.setdefault(plan.root_id, {'clone_id': root.clone_id})
        handled[plan.root_id].setdefault('clone_ids', []).append(plan.clone_id)
    # Exact AircraftType registration also determines airfield capacity. Use
    # the campaign rule builder so reward planes cannot bypass or stall pads.
    from randomizer.maps.player_clones import player_clone_pad_aircraft_rules
    pad_rules, _pad_ids = player_clone_pad_aircraft_rules(lines, installed, handled)
    for section, values in pad_rules.items():
        changes.setdefault(section, {}).update(values)
    if production_restrictions:
        apply_shop_clone_restrictions(
            changes, handled, source_rules,
            {'shop_production_restrictions': production_restrictions},
        )
    # Deployed unit forms can provide native powers too (FABOID). They are
    # earned through their root unit rather than independent building access.
    building_clones = {plan.source_id: plan.clone_id for plan in unit_plans
                       if plan.type_list == 'BuildingTypes'}
    planned_buildings = {plan.source_id: plan.template for plan in unit_plans
                         if plan.type_list == 'BuildingTypes' and plan.buildable}
    for source_id in building_ids:
        source_id = str(source_id).upper()
        if BUFF_TARGETS.get(source_id, {}).get('category') not in {
            'defenses', 'special_buildings',
        }:
            raise ValueError(f'Unsupported co-op building reward: {source_id}')
        native = _lookup(installed, source_id)
        native.update(_lookup(map_sections, source_id))
        template = planned_buildings.get(source_id, templates.get(source_id))
        if not native and not template:
            raise ValueError(f'No source definition for co-op building: {source_id}')
        clone_id = f'MOR{clone_scope or "P"}{source_id}'
        # Some reward buildings (for example NACLONS) exist only in the
        # packaged player roster. Use that complete reviewed template when
        # the installed rules have no native section.
        values = dict(template or native)
        # Challenge armor/power tuning belongs to the authored native map,
        # while the reviewed clone policy still controls independent powers
        # and production access (for example the Industrial Plant's Gear Change).
        for key, value in _lookup(map_sections, source_id).items():
            if key.lower() in {
                'strength', 'armor', 'power', 'powered', 'cost', 'sight',
                'ammo', 'storage', 'producecashamount', 'producecashdelay',
                'primary', 'secondary', 'eliteprimary', 'elitesecondary',
            } or _weapon_key(key):
                for previous in list(values):
                    if previous.lower() == key.lower():
                        values.pop(previous)
                values[key] = value
        values.update({
            'Image': native.get('Image') or source_id,
            'TechLevel': '1', 'Owner': clone_production_owners(native, country),
            'RequiredHouses': country,
            'ForbiddenHouses': 'none',
            'Prerequisite': CHAOS_PRIMARY_PRODUCTION[family]['base'],
            'PrerequisiteOverride': None, 'Prerequisite.List0': None,
            'Prerequisite.Lists': None, 'Prerequisite.Negative': None,
            'AllowedToStartInMultiplayer': 'no',
        })
        if manifest.get('reward_mode') == 'Standard':
            values.update(standard_coop_access_rules(source_id))
        building_counts = counts.get(source_id, {})
        apply_building_reward_buffs(
            changes, source_id, values, BUFF_TARGETS[source_id], building_counts,
            installed, map_sections, clone_scope, register,
        )
        if unlimited_buildings:
            _remove_building_cap(values)
        if building_counts.get('veteran') and BUFF_TARGETS[source_id].get('trainable'):
            veteran.setdefault('Buildings', []).append(clone_id)
        changes[clone_id] = values
        register('BuildingTypes', clone_id)
        building_clones[source_id] = clone_id
        handled[source_id] = {'clone_id': clone_id}
    preserve_native_building_abilities(
        changes, building_clones, installed, map_sections,
        country, clone_scope, register,
        techno_clones={plan.source_id: plan.clone_id for plan in unit_plans},
    )
    _register_initial_payloads(
        changes, templates, clone_ids, installed, map_sections,
        country, clone_scope, register,
    )
    if shop_settings:
        from randomizer.coop.shop_modifiers import apply_personal_shop_modifiers
        apply_personal_shop_modifiers(
            changes, handled, installed, map_sections, shop_settings,
            clone_scope, register,
        )
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


def _register_initial_payloads(changes, templates, clone_ids, installed,
                               map_sections, country, scope, register):
    """Give sealed carriers complete private payloads without production access.

    A payload cannot reuse a buildable reward clone: its production restriction
    or unearned prerequisite could prevent InitialPayload creation. Separate
    locked identities also preserve Shop's private host/guest loadouts.
    """
    sources = {str(clone).upper(): source for source, clone in clone_ids.items()}
    pending = list(changes)
    payloads = {}
    for carrier_id in pending:
        values = changes[carrier_id]
        payload_key = next((key for key in values
                            if key.lower() == 'initialpayload.types'), None)
        if payload_key is None or not values[payload_key]:
            continue
        replacements = {}
        for payload in str(values[payload_key]).split(','):
            payload = payload.strip()
            source = sources.get(payload.upper(), payload.upper())
            if source not in payloads:
                native = _lookup(installed, source)
                native.update(_lookup(map_sections, source))
                definition = dict(templates.get(source) or native)
                if not definition:
                    raise ValueError(f'Missing co-op initial payload: {source}')
                identity = f'{scope}|{source}'
                suffix = hashlib.sha1(identity.encode('ascii')).hexdigest()[:12].upper()
                clone = f'MOR{scope}CP{suffix}'
                definition.setdefault('Image', source)
                for key in list(definition):
                    if (key.lower().startswith('prerequisite')
                            or key.lower() in {'factoryowners', 'factoryowners.forbidden',
                                               'buildlimit'}):
                        definition[key] = None
                definition.update({
                    'TechLevel': '-1', 'Owner': clone_production_owners(native, country),
                    'RequiredHouses': country, 'ForbiddenHouses': 'none',
                    'AllowedToStartInMultiplayer': 'no',
                })
                target = BUFF_TARGETS.get(source)
                unit_type = arsenal_unit_type(source, target)
                type_list = _TYPE_LIST.get(unit_type)
                if type_list is None:
                    # Implementation-only payloads (e.g. SALA_1) need not be
                    # reward targets. Resolve their reviewed installed registry.
                    type_list = next((category for category in (
                        'InfantryTypes', 'VehicleTypes', 'AircraftTypes',
                    ) if source in {
                        str(item).upper() for sections in (installed, map_sections)
                        for item in _lookup(sections, category).values()
                    }), None)
                if type_list is None:
                    raise ValueError(f'Unknown co-op initial payload category: {source}')
                changes[clone] = definition
                register(type_list, clone)
                payloads[source] = clone
                pending.append(clone)
            replacements[payload.upper()] = payloads[source]
        values[payload_key] = ','.join(
            replacements[item.strip().upper()]
            for item in str(values[payload_key]).split(',')
        )
        for key in values:
            if key.lower() != 'passengers.allowed' or not values[key]:
                continue
            values[key] = ','.join(
                replacements.get(item.strip().upper(), item.strip())
                for item in str(values[key]).split(',')
            )


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
        'Image': 'GALITE', 'TechLevel': '-1', 'Owner': country,
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
                                 installed_types, installed, *,
                                 label='Shared Grid Powers', human_slots=(0, 1)):
    """Give human slots providers using native Player @ A/B transfers.

    Trigger owners resolve a country to its first house. Both Grid players
    may use the same country, so action 34 and country-owned static providers only
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
            'Name': 'Randomizer shared Grid power provider', 'Image': 'GALITE',
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
    # Every entry here is an implementation object, including providers
    # returned by the shared power planner and the original-production gate.
    # Retain their real House ownership/powers without consuming a build cell.
    for provider in providers:
        rules.setdefault(provider, {}).update({
            'Image': 'GALITE', 'InvisibleInGame': 'yes', 'IsPassable': 'yes',
        })
    merge_ini_section_values(lines, rules)
    if not providers:
        return
    for human_slot in human_slots:
        if type(human_slot) is not int or human_slot not in (0, 1):
            raise ValueError('Invalid human slot for multiplayer reward providers.')
        slot, house_index = human_slot + 1, 4475 + human_slot
        trigger = unique_section_key(lines, ('Events', 'Actions', 'Triggers'), 'RNGGP')
        tag = unique_section_key(lines, ('Tags',), 'RNGGT')
        name = f'MOR {label} P{slot}'
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
                             reward_ids: list[str], *, shared_grid=False,
                             human_slots=(0, 1), countries=(),
                             support_recharge=1.0) -> None:
    """Grant earned powers to private Shop or shared Grid/challenge humans."""
    if not reward_ids:
        return
    rewards = [canonical_reward({'name': name}) for name in reward_ids]
    player_countries = list(dict.fromkeys(countries or (country,)))
    installed_types, installed = installed_rules_registry(synchronous=True)
    rewards = apply_power_buffs_to_unlock_rewards(rewards, installed)
    if support_recharge != 1.0:
        rewards = [
            {**reward, 'superweapon_recharge_multiplier': float(
                reward.get('superweapon_recharge_multiplier', 1.0)
            ) * support_recharge}
            if reward.get('kind') == 'superweapon' and reward.get('power_category') == 'aid'
            else reward
            for reward in rewards
        ]
    if any(reward.get('superweapon_sidebar_image') for reward in rewards):
        from randomizer.maps.assets import deploy_superweapon_sidebar_assets
        deploy_superweapon_sidebar_assets(rewards)
    rules, actions, _names, startup, static, missing = cloned_superweapon_plan(
        lines, rewards, installed_types, installed,
        superweapon_required_houses=player_countries, force_required_houses=True,
    )
    if missing:
        raise ValueError('Co-op power source rules are missing: ' + ', '.join(missing))
    if not rules:
        raise ValueError('Co-op power rewards produced no map rules.')
    from randomizer.coop.native_powers import close_reward_power_references
    close_reward_power_references(lines, rules, installed, player_countries)
    merge_ini_section_values(lines, rules)
    if shared_grid:
        _append_grid_power_providers(
            lines, ','.join(player_countries), actions, [*startup, *static], installed_types, installed,
            human_slots=human_slots,
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
