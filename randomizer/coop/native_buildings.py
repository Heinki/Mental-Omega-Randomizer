"""Native engine identities required by earned multiplayer building clones."""

from __future__ import annotations

import hashlib
import re

from randomizer.maps.base import parse_float, resolved_native_designator_clone_rules
from randomizer.maps.buff_values import apply_unit_buff_value, apply_weapon_buff_value
from randomizer.maps.clone_references import (
    _target_with_effective_unit_stats, prism_forwarding_clone_rules,
)
from randomizer.maps.special_buildings import refinery_miner_dock_rules


_BUILDING_POWERS = {'superweapon', 'superweapon2', 'superweapons'}
_POWER_LINKS = {'sw.postdependent', 'sw.next'}
_OWNED_BUILDING_LINKS = {
    'auxbuilding', 'sw.auxbuildings', 'sw.negbuildings', 'sw.designators',
}
_EMPTY = {'', 'none', '<none>'}
_BUFF_ORDER = (
    'health', 'armor', 'sight', 'ammo', 'storage', 'income',
    'passenger_capacity', 'open_topped', 'self_healing', 'cloak',
    'sensors', 'production', 'cost', 'speed',
)
_WEAPON_BUFFS = {'damage', 'range', 'reload', 'mind_control'}
_WEAPON_FIELDS = {
    'primary', 'secondary', 'eliteprimary', 'elitesecondary',
    'prismforwarding.supportweapon', 'prismforwarding.elitesupportweapon',
}


def _lookup(registry, name):
    wanted = str(name).lower()
    return next((dict(values) for section, values in registry.items()
                 if str(section).lower() == wanted), {})


def _merge(*sections):
    result = {}
    for section in sections:
        for key, value in section.items():
            previous = next((item for item in result
                             if str(item).lower() == str(key).lower()), None)
            if previous is not None:
                result.pop(previous)
            if value is not None:
                result[key] = value
    return result


def _value(values, field, default=''):
    return next((value for key, value in values.items()
                 if str(key).lower() == field.lower()), default)


def _set(values, field, value):
    for key in list(values):
        if str(key).lower() == field.lower():
            values.pop(key)
    values[field] = value


def _items(value):
    return [item.strip() for item in str(value or '').split(',')
            if item.strip().lower() not in _EMPTY]


def apply_building_reward_buffs(changes, source, values, target, counts,
                               installed, map_sections, scope, register):
    """Apply the same earned stacks to an exact building and its weapons."""
    effective_target = _target_with_effective_unit_stats(target, values)
    for buff in _BUFF_ORDER:
        if buff in counts and not apply_unit_buff_value(
            values, effective_target, buff, counts[buff],
        ):
            raise ValueError(f'Cannot apply building buff: {source} {buff}')
    for buff in set(counts) - set(_BUFF_ORDER):
        if buff in {'build_limit', 'building_limit'}:
            limit = int(str(_value(values, 'BuildLimit') or target.get('build_limit') or 1))
            _set(values, 'BuildLimit', str(max(1, limit) + counts[buff]))
        elif buff != 'veteran' and buff not in _WEAPON_BUFFS:
            raise ValueError(f'Unsupported co-op building buff: {source} {buff}')

    weapon_counts = {buff: count for buff, count in counts.items()
                     if buff in _WEAPON_BUFFS}
    if not weapon_counts:
        return
    targets = {str(name).upper(): stats
               for name, stats in target.get('weapons', {}).items()}
    mind_control = {str(name).upper()
                    for name in target.get('mind_control_weapons', {})}
    replacements = {}
    for field, weapon in list(values.items()):
        lowered = str(field).lower()
        if (lowered not in _WEAPON_FIELDS
                and not re.fullmatch(r'(?:elite)?weapon\d+', lowered)):
            continue
        if not _items(weapon):
            continue
        key = str(weapon).upper()
        if key not in replacements:
            definition = _merge(_lookup(installed, weapon), _lookup(map_sections, weapon))
            if not definition:
                raise ValueError(f'Missing building weapon: {source} {weapon}')
            defaults = targets.get(key, {})
            stats = {name: parse_float(_value(definition, native), defaults.get(name, 0))
                     for name, native in (
                         ('damage', 'Damage'), ('range', 'Range'), ('rof', 'ROF'),
                     )}
            changed = False
            for buff, count in sorted(weapon_counts.items()):
                if ((buff == 'mind_control' and key not in mind_control)
                        or (buff == 'damage' and key in mind_control)):
                    continue
                changed |= apply_weapon_buff_value(definition, stats, buff, count)
            if changed:
                suffix = hashlib.sha1(
                    f'{scope}|{source}|{key}'.encode('utf-8')
                ).hexdigest()[:12].upper()
                clone = f'MOR{scope or "P"}BW{suffix}'
                if any(_lookup(registry, clone) for registry in (installed, map_sections, changes)):
                    raise ValueError(f'Building weapon identity is already in use: {clone}')
                changes[clone] = definition
                register('WeaponTypes', clone)
                replacements[key] = clone
            else:
                replacements[key] = weapon
        values[field] = replacements[key]


def preserve_native_building_abilities(changes, building_clones, installed,
                                      map_sections, country, scope, register,
                                      *, techno_clones=None):
    """Attach private native powers and register exact bounty enablers.

    Copying a BuildingType does not copy the engine's exact-type references:
    BountyEnablers still names FAREPR and IronGuardSpecial's cannon list still
    names NAIRDM. Country/slot-specific powers prevent a foreign or unearned
    cannon from being used, without changing native ability strength or costs.
    The provider building continues to control availability and power supply;
    nothing is granted through startup objects or trigger actions.
    """
    techno_clones = dict(techno_clones or {})
    techno_clones.update(building_clones)
    if not techno_clones:
        return

    def effective(name):
        return _merge(_lookup(installed, name), _lookup(map_sections, name),
                      _lookup(changes, name))

    building_ids = {str(source).upper(): clone
                    for source, clone in building_clones.items()}
    reserved = {str(name).upper() for registry in (installed, map_sections, changes)
                for name in registry}
    power_ids = {}

    def private_power(source, provider):
        identity = (str(provider).upper(), str(source).upper())
        if identity in power_ids:
            return power_ids[identity]
        native = effective(source)
        if not native:
            raise ValueError(f'Missing native building power: {provider} {source}')
        suffix = hashlib.sha1(
            f'{scope}|{country}|{identity[0]}|{identity[1]}'.encode('utf-8')
        ).hexdigest()[:12].upper()
        clone = f'MOR{scope or "P"}BP{suffix}'
        if clone.upper() in reserved:
            raise ValueError(f'Building power identity is already in use: {clone}')
        reserved.add(clone.upper())
        power_ids[identity] = clone
        values = dict(native)
        changes[clone] = values
        register('SuperWeaponTypes', clone)
        # Keep explicit native SW.AllowPlayer=no (the Reprocessor AI-only
        # cash fix), native power consumption, costs and recharge settings.
        _set(values, 'SW.RequiredHouses', country)
        _set(values, 'SW.ForbiddenHouses', 'none')
        _set(values, 'SW.AllowAI', 'no')
        for field, raw in list(values.items()):
            lowered = str(field).lower()
            if lowered in _POWER_LINKS:
                values[field] = ','.join(private_power(item, provider)
                                         for item in _items(raw)) or raw
            elif lowered in _OWNED_BUILDING_LINKS:
                values[field] = ','.join(building_ids.get(item.upper(), item)
                                         for item in _items(raw)) or raw
        if str(_value(values, 'Type')).lower() == 'empulse':
            cannons = _items(_value(values, 'EMPulse.Cannons'))
            # An empty native list accepts every EMPulseCannon building. The
            # player may now mix all factions' cannons, so restrict that case
            # to the actual provider instead of firing another earned weapon.
            _set(values, 'EMPulse.Cannons', ','.join(
                building_ids.get(item.upper(), item) for item in cannons
            ) if cannons else building_ids[provider])
        return clone

    for source, clone in building_ids.items():
        values = changes[clone]
        for field, raw in list(values.items()):
            if str(field).lower() in _BUILDING_POWERS and _items(raw):
                values[field] = ','.join(private_power(power, source)
                                         for power in _items(raw))

    reprocessor = building_ids.get('FAREPR')
    if reprocessor:
        general = effective('General')
        enablers = _items(_value(general, 'BountyEnablers'))
        # An empty effective list means bounty is already enabled globally.
        # Preserve that authored behavior rather than adding a new gate.
        if enablers and reprocessor.upper() not in {item.upper() for item in enablers}:
            changes.setdefault('General', {})['BountyEnablers'] = ','.join(
                [*enablers, reprocessor]
            )

    # These engine lists use exact type IDs even though the feature flags
    # themselves were copied. Reuse the campaign compatibility rules: a
    # cloned Prism Tower needs an explicit forwarding mode; ore miners must
    # recognize an earned Purifier/War Rig refinery; enemy powers must see a
    # player's actual Signal Inhibitor rather than just native FAINHI.
    registry = {}
    names = {}
    for source_registry in (installed, map_sections, changes):
        for name, values in source_registry.items():
            actual = names.setdefault(str(name).lower(), name)
            if str(name).lower() in {
                'infantrytypes', 'vehicletypes', 'aircrafttypes',
                'buildingtypes', 'weapontypes', 'superweapontypes',
            }:
                # Scenario type-list labels are independent of installed
                # labels: [VehicleTypes]0=X appends X, rather than deleting
                # the installed type numbered 0. Preserve both registries.
                registered = dict.fromkeys(
                    str(value).upper()
                    for value in [*registry.get(actual, {}).values(), *values.values()]
                )
                registry[actual] = {str(index): value
                                    for index, value in enumerate(registered)}
            else:
                registry[actual] = _merge(registry.get(actual, {}), values)
    handled = {source: {'clone_id': clone}
               for source, clone in techno_clones.items()}
    compatible_rules = [
        prism_forwarding_clone_rules([], registry, handled),
        resolved_native_designator_clone_rules(registry, {}, handled),
    ]
    if any(str(_value(changes[clone], 'Refinery')).lower() in {'yes', 'true', '1'}
           for clone in building_ids.values()):
        docks, _report = refinery_miner_dock_rules([], registry)
        compatible_rules.append(docks)
    for rules in compatible_rules:
        for name, values in rules.items():
            changes[name] = _merge(_lookup(changes, name), values)
