"""Reviewed special production access, isolated from installed enemy types."""

from copy import deepcopy


FACTORIES = {'GDI': 'ALLWEAP', 'Nod': 'SOVWEAP',
             'ThirdSide': 'YURWEAP', 'FourthSide': 'FOEWEAP'}
BARRACKS = {'GDI': 'GAPILE', 'Nod': 'NAHAND',
            'ThirdSide': 'YABRCK', 'FourthSide': 'FABARR'}
AIRFIELDS = {'GDI': 'GAAIRC', 'Nod': 'NAAIR', 'ThirdSide': 'YAAIRF'}
CONVERSION_FIELDS = ('Convert.Deploy', 'Convert.Land', 'Convert.Water', 'UnloadingClass',
                     'DeploysInto', 'UndeploysInto')
PAYLOAD_FIELDS = ('InitialPayload.Types', 'Passengers.Allowed')
TYPE_REFERENCE_FIELDS = (*CONVERSION_FIELDS, *PAYLOAD_FIELDS, 'ReversedAs')


def production_factory(original, country, rules):
    """Select the native production category, including airport-bound planes."""
    side = rules[country]['Side']
    if original in rules['InfantryTypes'].values():
        return BARRACKS[side]
    if original in rules['AircraftTypes'].values():
        return AIRFIELDS[side]
    return FACTORIES[side]


def replace_references(row, aliases):
    return {field: ','.join(aliases.get(part.strip(), part.strip()) for part in value.split(','))
            for field, value in row.items() if value is not None}


def reviewed_rules(rules, access):
    """Use the same portable models as campaign rewards without MORP leakage."""
    if not access:
        return rules, set()
    from randomizer.rewards.roster import (
        ROSTER_CATEGORIES, randomizer_unit_roster, installed_rules_template_overlay,
    )
    from randomizer.rewards.catalogue import (
        BUFF_TARGETS, SPECIAL_REWARD_UNIT_IDS, STANDALONE_UNIT_RULE_TEMPLATES,
    )
    from randomizer.rewards.template_policy import build_template_values

    _, clone_ids, templates = randomizer_unit_roster()
    templates, _ = installed_rules_template_overlay(templates, rules)
    inverse = {alias: source for source, alias in clone_ids.items()}
    inverse.update({'MORP' + source: source for source in BUFF_TARGETS})
    reviewed = dict(rules)
    forms = set()

    def include(original):
        if original in forms:
            return
        category = ROSTER_CATEGORIES.get(BUFF_TARGETS.get(original, {}).get('category'))
        if not category or original not in templates and original not in rules:
            raise ValueError(f'Special unit {original} has no reviewed model.')
        forms.add(original)
        if (original not in access and original not in SPECIAL_REWARD_UNIT_IDS
                and not BUFF_TARGETS[original].get('linked_buff_source')):
            # Ordinary soldiers carried by Super Thor remain ordinary
            # production units; randomizer templates use locked TechLevel 11.
            row = deepcopy(rules[original])
        elif original in templates:
            row = deepcopy(templates[original])
        else:
            row = build_template_values(
                original, rules[original], category=BUFF_TARGETS[original]['category'],
                special_reward=True, description='NOSTR:* Granted by Randomizer')
        row = replace_references(row, inverse)
        registry = reviewed[category]
        if original not in registry.values():
            registry = reviewed[category] = dict(registry)
            registry[str(max(int(key) for key in registry) + 1)] = original
        reviewed[original] = row
        for field in (*CONVERSION_FIELDS, *PAYLOAD_FIELDS):
            for target in row.get(field, '').split(','):
                if target and target.lower() != 'none':
                    include(target)
        for entries in STANDALONE_UNIT_RULE_TEMPLATES.get(original, {}).values():
            for section, values in entries.items():
                reviewed[section] = deepcopy(values)

    for original in sorted(access):
        if original not in templates:
            raise ValueError(f'Special access requires a reviewed reward model: {original}.')
        include(original)
    return reviewed, forms


def special_dependencies(writer, rules, access):
    """Give map-only weapons, projectiles and warheads private identities."""
    from randomizer.maps.buff_values import _register_map_type
    from randomizer.rewards.catalogue import STANDALONE_UNIT_RULE_TEMPLATES

    definitions = {section: category for original in sorted(access)
                   for category, entries in STANDALONE_UNIT_RULE_TEMPLATES.get(original, {}).items()
                   for section in entries}
    aliases = {section: writer.key() for section in definitions}
    for original, category in definitions.items():
        alias = aliases[original]
        writer.sections[alias] = replace_references(rules[original], aliases)
        _register_map_type(writer.sections, writer.lines, rules, category, alias)
    return aliases


def reserve_special_limits(writer, plan, rules):
    """Keep capped specials inside the engine's 512-entry ownership counters."""
    from randomizer.maps.buff_values import _register_map_type

    access = plan['effects'].get('special_access', [])
    reviewed, _ = reviewed_rules(rules, access)
    categories = {kind: category for category in ('InfantryTypes', 'VehicleTypes', 'AircraftTypes')
                  for kind in reviewed[category].values()}
    aliases = {}
    for original in sorted(access):
        if int(reviewed[original].get('BuildLimit', '0')) > 0:
            alias = aliases[original] = writer.key()
            _register_map_type(writer.sections, writer.lines, rules, categories[original], alias)
    return aliases


def production_access(row, friends, country, rules, original):
    """Replace mission/stolen-tech gates with the faction's matching factory."""
    for field in tuple(row):
        if field.startswith(('Prerequisite', 'FactoryOwners')) or field == 'BuiltAt':
            del row[field]
    row.update(TechLevel='1', Owner=','.join(friends), RequiredHouses=','.join(friends),
               ForbiddenHouses='', Prerequisite=production_factory(original, country, rules))
