"""Close earned-power payloads and exact-type lookups over multiplayer clones."""

from __future__ import annotations

import hashlib
import re

from randomizer.coop.native_units import TRANSFORM_REFERENCE_KEYS, unit_transform_plan
from randomizer.maps.ini import all_section_value_maps_preserve, merge_ini_section_values
from randomizer.rewards.roster import randomizer_unit_roster


_TECHNO_LISTS = ('InfantryTypes', 'VehicleTypes', 'AircraftTypes', 'BuildingTypes')
_OWNED_LOOKUPS = {
    'academy.types', 'auxbuilding', 'sw.auxbuildings', 'sw.negbuildings',
    'sw.designators', 'sw.inhibitors', 'sw.launchsites', 'empulse.cannons',
    'hunterseeker.buildings', 'battery.overpower',
}
_POWER_LINKS = {'sw.postdependent', 'sw.next'}
_BUILDING_POWERS = {'superweapon', 'superweapon2', 'superweapons'}
_PAYLOAD_FIELDS = {'deliver.types', 'droppod.types', 'initialpayload.types', 'freeunit'}
_EMPTY = {'', 'none', '<none>'}


def _lookup(sections, name):
    wanted = str(name).upper()
    return next((dict(values) for section, values in sections.items()
                 if str(section).upper() == wanted), {})


def _merge(*sections):
    result = {}
    for values in sections:
        for key, value in values.items():
            for previous in list(result):
                if str(previous).lower() == str(key).lower():
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


def _unique(items):
    return list(dict.fromkeys(items))


def _payload_field(field):
    return field in _PAYLOAD_FIELDS or bool(re.fullmatch(r'paradrop(?:\.[^.]+)?\.types', field))


def close_reward_power_references(lines, rules, installed, countries):
    """Retain native actors while making every earned power's actors usable.

    Power delivery is an entitlement of the power, independent of whether its
    payload has also been earned as a buildable unit. A separate, unbuildable
    namespace avoids changing either player's purchased unit clone. Static
    helper actors also require real multiplayer owners: MORPLAYER belongs to
    the campaign pipeline and is not a native multiplayer country.

    Rocket ``Spawns``, airstrike aircraft, survivor crews and visual art IDs
    deliberately retain their native identities. They are valid installed
    actors; several rocket behaviours use exact IDs in RocketData. Only actual
    delivery/payload/transform edges are redirected to private player actors.
    """
    countries = _unique(str(country).strip() for country in countries if str(country).strip())
    if not countries:
        raise ValueError('Earned multiplayer powers require a player country.')
    owners = ','.join(countries)
    local = all_section_value_maps_preserve(lines)
    native_names = {str(name).upper() for registry in (installed, local) for name in registry}
    _, roster_ids, templates = randomizer_unit_roster()
    reserved = {str(name).upper() for registry in (installed, local, rules)
                for name in registry}
    registered = {}
    for category in (*_TECHNO_LISTS, 'SuperWeaponTypes'):
        for registry in (installed, local, rules):
            for type_id in _lookup(registry, category).values():
                registered[str(type_id).upper()] = category

    def effective(name):
        return _merge(_lookup(installed, name), _lookup(local, name), _lookup(rules, name))

    def generated(name):
        return str(name).upper() not in native_names

    def register(category, type_id):
        if str(type_id).upper() in registered:
            return
        occupied = {str(key) for registry in (installed, local, rules)
                    for key in _lookup(registry, category)}
        index = 390000
        while str(index) in occupied:
            index += 1
        rules.setdefault(category, {})[str(index)] = type_id
        registered[str(type_id).upper()] = category

    def allocate(kind, identity):
        suffix = hashlib.sha1(f'{owners}|{kind}|{identity}'.encode('utf-8')).hexdigest()[:14].upper()
        type_id = f'MORRP{kind}{suffix}'
        if type_id.upper() in reserved:
            raise ValueError(f'Earned power helper identity is already in use: {type_id}')
        reserved.add(type_id.upper())
        return type_id

    # Map only identities that really exist in this map. Static campaign MORP
    # references are not sufficient when the players use separate H/G rosters.
    runtime = {}
    sources = {source for source in registered if not source.startswith('MOR')}
    sources.update(str(source).upper() for source in templates)
    aliases = {str(clone).upper(): str(source).upper() for source, clone in roster_ids.items()}
    for source in sources:
        aliases[f'MORP{source}'] = source
        candidates = [roster_ids.get(source, ''), f'MORP{source}', f'MORH{source}', f'MORG{source}']
        runtime[source] = [candidate for candidate in _unique(candidates)
                           if candidate and candidate.upper() in registered]

    payloads = {}
    private_powers = {}
    power_providers = {}
    queued = []
    processed = set()

    def own_actor(values):
        for field, value in {
            'Owner': owners, 'RequiredHouses': owners, 'ForbiddenHouses': 'none',
            'TechLevel': '-1', 'BuildLimit': None, 'Prerequisite': None,
            'PrerequisiteOverride': None, 'Prerequisite.Negative': None,
            'FactoryOwners': None, 'FactoryOwners.Forbidden': None,
            'AllowedToStartInMultiplayer': 'no',
        }.items():
            _set(values, field, value)
        for key in list(values):
            if str(key).lower().startswith('prerequisite.'):
                values[key] = None

    def payload(token):
        source = aliases.get(str(token).upper(), str(token).upper())
        existing = next((name for name in rules if str(name).upper() == str(token).upper()), None)
        if (existing and generated(existing)
                and registered.get(str(existing).upper()) in _TECHNO_LISTS):
            queued.append(existing)
            return existing
        if source in payloads:
            return payloads[source]
        if registered.get(source) not in _TECHNO_LISTS:
            raise ValueError(f'Earned power payload is not a registered TechnoType: {token}')
        # The existing transform resolver preserves MCV -> native Yard, and
        # respects map-local disabled forms. Native definitions are the source
        # here; campaign-only buildable-roster identities are not required.
        plans = unit_transform_plan([source], {}, {}, installed, local, scope='RP')
        remap = {}
        for plan in plans:
            if plan.source_id not in payloads:
                payloads[plan.source_id] = allocate('T', plan.source_id)
                runtime.setdefault(plan.source_id, []).append(payloads[plan.source_id])
            remap[plan.clone_id.upper()] = payloads[plan.source_id]
        for plan in plans:
            clone = payloads[plan.source_id]
            if clone in rules:
                continue
            values = dict(plan.template)
            own_actor(values)
            for field, raw in list(values.items()):
                if str(field).lower() in TRANSFORM_REFERENCE_KEYS and raw is not None:
                    values[field] = ','.join(remap.get(item.upper(), item) for item in _items(raw)) or raw
            rules[clone] = values
            register(plan.type_list, clone)
            queued.append(clone)
        return payloads[source]

    def private_power(source, provider):
        identity = (str(source).upper(), str(provider).upper())
        if identity in private_powers:
            return private_powers[identity]
        existing = next((name for name in rules if str(name).upper() == str(source).upper()), None)
        if (existing and generated(existing)
                and registered.get(str(existing).upper()) == 'SuperWeaponTypes'):
            return existing
        values = effective(source)
        if not values or registered.get(str(source).upper()) != 'SuperWeaponTypes':
            raise ValueError(f'Earned power actor references a missing native power: {source}')
        clone = allocate('S', '|'.join(identity))
        private_powers[identity] = clone
        power_providers[clone] = provider
        _set(values, 'SW.RequiredHouses', owners)
        _set(values, 'SW.ForbiddenHouses', 'none')
        _set(values, 'SW.AllowAI', 'no')
        if str(_value(values, 'Type')).lower() == 'empulse' and not _items(_value(values, 'EMPulse.Cannons')):
            _set(values, 'EMPulse.Cannons', provider)
        rules[clone] = values
        register('SuperWeaponTypes', clone)
        queued.append(clone)
        return clone

    for section in list(rules):
        category = registered.get(str(section).upper())
        if generated(section) and (category in _TECHNO_LISTS or category == 'SuperWeaponTypes'):
            queued.append(section)
    for section in queued:
        if section in processed:
            continue
        processed.add(section)
        values = rules[section]
        category = registered.get(str(section).upper())
        if category in _TECHNO_LISTS:
            own_actor(values)
        elif category == 'SuperWeaponTypes':
            _set(values, 'SW.RequiredHouses', owners)
            _set(values, 'SW.ForbiddenHouses', 'none')
            _set(values, 'SW.AllowAI', 'no')
        for field, raw in list(values.items()):
            lowered = str(field).lower()
            if not _items(raw):
                continue
            if _payload_field(lowered):
                values[field] = ','.join(payload(item) for item in _items(raw))
            elif lowered in _BUILDING_POWERS:
                values[field] = ','.join(private_power(item, section) for item in _items(raw))
            elif lowered in _POWER_LINKS:
                provider = power_providers.get(section, section)
                values[field] = ','.join(private_power(item, provider) for item in _items(raw))
            elif lowered == 'passengers.allowed':
                # InitialPayload has already allocated these actors by the
                # time the final lookup pass runs below.
                continue

    for section, values in list(rules.items()):
        for field, raw in list(values.items()):
            lowered = str(field).lower()
            if lowered not in _OWNED_LOOKUPS and lowered != 'passengers.allowed':
                continue
            expanded = []
            for token in _items(raw):
                source = aliases.get(token.upper(), token.upper())
                actual = runtime.get(source, [])
                if lowered == 'passengers.allowed' and source in payloads:
                    expanded.append(payloads[source])
                else:
                    if token.upper() in registered:
                        expanded.append(token)
                    elif not token.upper().startswith('MORP'):
                        expanded.append(token)
                    expanded.extend(actual)
            if _items(raw):
                values[field] = ','.join(_unique(expanded)) or None

    if payloads:
        rules.setdefault('MORPowerPayloadSources', {}).update({
            clone: source for source, clone in payloads.items()
        })
    return {'payload_types': len(payloads), 'dependent_powers': len(private_powers)}


def apply_coop_payload_support(lines):
    """Bind delivered miners/inhibitors after all player and power clones exist."""
    from randomizer.maps.base import resolved_native_designator_clone_rules
    from randomizer.maps.special_buildings import refinery_miner_dock_rules
    from randomizer.ui.cameos import installed_rules_registry

    sections = all_section_value_maps_preserve(lines)
    metadata = _lookup(sections, 'MORPowerPayloadSources')
    if not metadata:
        return
    _powers, installed = installed_rules_registry(synchronous=True)
    groups = {}
    miner = False
    for clone, source in metadata.items():
        values = _lookup(sections, clone)
        if not values:
            raise ValueError(f'Earned power payload definition is missing: {clone}')
        owner = str(_value(values, 'Owner'))
        groups.setdefault(owner, {})[str(source).upper()] = {'clone_id': clone}
        miner = miner or str(_value(values, 'Harvester')).lower() in {'yes', 'true', '1'}
    for handled in groups.values():
        # Preserve native enemies and already-added H/G identities, then append
        # the additional delivered actors rather than replacing a shared list.
        updates = resolved_native_designator_clone_rules(
            installed, all_section_value_maps_preserve(lines), handled,
        )
        merge_ini_section_values(lines, updates)
    if miner:
        updates, report = refinery_miner_dock_rules(lines, installed)
        if report['issues']:
            raise ValueError('Earned power miner docking could not be resolved: '
                             + '; '.join(report['issues']))
        merge_ini_section_values(lines, updates)
