"""Close private reward-unit transform graphs without editing native actors."""

from __future__ import annotations

from dataclasses import dataclass

from randomizer.rewards.catalogue import BUFF_TARGETS
from randomizer.rewards.definitions import LINKED_BUFF_VARIANTS, MCV_UNIT_IDS


TRANSFORM_REFERENCE_KEYS = frozenset({
    'deploysinto', 'undeploysinto', 'convert.deploy',
    'convert.deploy.reversedas', 'convert.land', 'convert.water', 'reversedas',
})
_TYPE_LISTS = ('InfantryTypes', 'VehicleTypes', 'AircraftTypes', 'BuildingTypes')


def _merge(*sections):
    values = {}
    for section in sections:
        for key, value in section.items():
            previous = next((existing for existing in values
                             if str(existing).lower() == str(key).lower()), None)
            if previous is not None:
                values.pop(previous)
            if value is not None:
                values[key] = value
    return values


@dataclass(slots=True)
class UnitClonePlan:
    source_id: str
    root_id: str
    clone_id: str
    type_list: str
    template: dict
    buildable: bool


def unit_transform_plan(access_ids, templates, clone_ids, installed, map_sections,
                        scope='', *, building_access_ids=()) -> list[UnitClonePlan]:
    """Resolve deploy/land/water forms into the same human clone namespace.

    Reviewed roster templates can name MORP identities before those identities
    are registered. Native transform forms often have no static reward roster
    entry at all. Resolve both kinds, retaining native AI/script definitions.
    Construction Yards are the campaign pipeline's deliberate exception:
    reward MCVs deploy into their real Yard to retain its complete sidebar.
    """
    installed = {str(name).upper(): values for name, values in installed.items()}
    local = {str(name).upper(): values for name, values in map_sections.items()}
    roots = tuple(dict.fromkeys(str(item).upper()
                               for item in (*access_ids, *building_access_ids)))
    root_set = set(roots)
    source_by_clone = {str(clone).upper(): source for source, clone in clone_ids.items()}
    source_by_clone.update({f'MORP{source}': source for source in templates})
    categories = {}
    for type_list in _TYPE_LISTS:
        for sections in (installed, local):
            for type_id in sections.get(type_list.upper(), {}).values():
                categories[str(type_id).upper()] = type_list
    for source, target in BUFF_TARGETS.items():
        categories.setdefault(source, {
            'infantry': 'InfantryTypes', 'units': 'VehicleTypes',
            'aircraft': 'AircraftTypes', 'defenses': 'BuildingTypes',
            'special_buildings': 'BuildingTypes',
        }.get(target.get('category')))

    plans = {}
    pending = [(source, source) for source in roots]
    for source, root in pending:
        if source in plans:
            continue
        native = _merge(installed.get(source, {}), local.get(source, {}))
        template = dict(templates.get(source) or native)
        # Challenge-specific deploy/convert rules remain authoritative, even
        # when a reviewed static template wires the stock pair through MORP.
        # A local "none" (or removed value) must not resurrect that stock link.
        for key, value in local.get(source, {}).items():
            if str(key).lower() not in TRANSFORM_REFERENCE_KEYS:
                continue
            for existing in list(template):
                if str(existing).lower() == str(key).lower():
                    template.pop(existing)
            template[key] = value
        type_list = categories.get(source)
        if not template or not type_list:
            raise ValueError(f'Missing co-op transform definition/category: {source}')
        template.setdefault('Image', source)
        clone_id = (f'MOR{scope}{source}' if scope
                    else clone_ids.get(source, f'MORP{source}'))
        plans[source] = UnitClonePlan(
            source, root, clone_id, type_list, template, source in root_set,
        )
        # Nanofiber mutation is a superweapon/warhead conversion rather than
        # a TechnoType Convert.* field. Its reviewed hidden forms still need
        # the same private identity and earned unit/weapon stacks.
        for related, metadata in LINKED_BUFF_VARIANTS.get(source, {}).items():
            if metadata.get('nanofiber_stage') and related not in plans:
                pending.append((related, root))
        for key, value in template.items():
            lowered = str(key).lower()
            if lowered not in TRANSFORM_REFERENCE_KEYS:
                continue
            if source in MCV_UNIT_IDS and lowered == 'deploysinto':
                continue
            for token in str(value or '').split(','):
                token = token.strip().upper()
                if token in {'', 'NONE', '<NONE>'}:
                    continue
                related = source_by_clone.get(token, token)
                if related not in plans:
                    pending.append((related, root))

    replacements = {}
    for source, plan in plans.items():
        replacements[source] = plan.clone_id
        replacements[f'MORP{source}'] = plan.clone_id
        if source in clone_ids:
            replacements[str(clone_ids[source]).upper()] = plan.clone_id
    for source, plan in plans.items():
        for key, value in list(plan.template.items()):
            lowered = str(key).lower()
            if lowered not in TRANSFORM_REFERENCE_KEYS:
                continue
            if source in MCV_UNIT_IDS and lowered == 'deploysinto':
                continue
            if value is None:
                continue
            plan.template[key] = ','.join(
                replacements.get(token.strip().upper(), token.strip())
                for token in str(value or '').split(',')
            )
    return list(plans.values())
