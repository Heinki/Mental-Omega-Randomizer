"""Preserve exact native building gates when player buildings are cloned."""

from itertools import product

from randomizer.core.collections import comma_items, unique_in_order
from randomizer.maps.ini import all_section_value_maps


def expand_prerequisite_paths(values, replacements):
    """Add full AND paths, retaining every factory/support requirement."""
    paths = [comma_items(values.get('prerequisite.list0', values.get('prerequisite', '')))]
    extra_lists = int(values.get('prerequisite.lists', '0'))
    paths.extend(
        comma_items(values.get(f'prerequisite.list{index}', ''))
        for index in range(1, extra_lists + 1)
    )
    # An empty active path already permits production. Do not replace it with
    # a restrictive List0 or activate an authored but disabled extra list.
    if any(not path for path in paths):
        return {}
    seen = {tuple(item.upper() for item in path) for path in paths}
    rules = {}
    next_index = extra_lists + 1
    for path in paths:
        choices = [(item, *replacements.get(item.upper(), ())) for item in path]
        for alternate in product(*choices):
            identity = tuple(item.upper() for item in alternate)
            if identity in seen:
                continue
            seen.add(identity)
            # Keep authored list indices and their exact type references.
            rules[f'Prerequisite.List{next_index}'] = ','.join(alternate)
            next_index += 1
    if rules:
        rules['Prerequisite.Lists'] = str(next_index - 1)
    return rules


def player_building_prerequisite_rules(lines, installed_sections, clone_handled):
    """Let private buildings satisfy their native production gates.

    Ordinary campaign structures retain native identities and therefore are
    absent from the player clone list. Include every registered TechnoType,
    reading final map overrides after refinery and mission-access preparation.
    """
    sections = all_section_value_maps(lines)
    # Power plants, tech centers and defense/support buildings are also exact
    # prerequisite identities. Restricting this to yards and refineries leaves
    # an upgraded NODAPWR unable to satisfy POWER, blocking the whole tech tree.
    building_sources = {
        str(identifier).upper()
        for source_sections in (installed_sections, sections)
        for name, values in source_sections.items()
        if str(name).casefold() == 'buildingtypes'
        for identifier in values.values()
    }

    replacements = {
        source: unique_in_order(
            str(details[key])
            for key in ('clone_id', 'reference_clone_id')
            if details.get(key) and str(details[key]).upper() != source
        )
        for source in building_sources
        if (details := clone_handled.get(source))
    }
    replacements = {source: clones for source, clones in replacements.items() if clones}
    if not replacements:
        return {}

    effective = {}
    for source_sections in (installed_sections, sections):
        for name, values in source_sections.items():
            effective.setdefault(str(name).upper(), {}).update({
                str(key).lower(): (key, value) for key, value in values.items()
            })

    def expand_members(value):
        originals = comma_items(value)
        return unique_in_order([
            *originals,
            *(clone for item in originals for clone in replacements.get(item.upper(), ())),
        ])

    rules = {}
    for key, value in effective.get('GENERICPREREQUISITES', {}).values():
        expanded = expand_members(value)
        if expanded != comma_items(value):
            rules.setdefault('GenericPrerequisites', {})[key] = ','.join(expanded)
    for field in ('Power', 'Factory', 'Barracks', 'Radar', 'Tech', 'Proc'):
        key = 'Prerequisite' + field
        value = effective.get('GENERAL', {}).get(key.lower(), (key, ''))[1]
        expanded = expand_members(value)
        if expanded != comma_items(value):
            rules.setdefault('General', {})[key] = ','.join(expanded)

    techno_ids = {
        str(identifier)
        for registry in ('INFANTRYTYPES', 'VEHICLETYPES', 'AIRCRAFTTYPES', 'BUILDINGTYPES')
        for _key, identifier in effective.get(registry, {}).values()
    }
    for identifier in sorted(techno_ids):
        values = {
            key: value for key, (_spelling, value) in effective.get(identifier.upper(), {}).items()
        }
        additions = expand_prerequisite_paths(values, replacements)
        override = values.get('prerequisiteoverride', '')
        expanded_override = expand_members(override)
        if expanded_override != comma_items(override):
            additions['PrerequisiteOverride'] = ','.join(expanded_override)
        if additions:
            rules[identifier] = additions
    return rules
