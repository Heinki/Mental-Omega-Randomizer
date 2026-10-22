"""Reviewed special production access, isolated from installed enemy types."""

from copy import deepcopy


FACTORIES = {'GDI': 'ALLWEAP', 'Nod': 'SOVWEAP',
             'ThirdSide': 'YURWEAP', 'FourthSide': 'FOEWEAP'}


def reviewed_rules(rules, access):
    """Use the same portable models as campaign rewards without MORP leakage."""
    if not access:
        return rules, set()
    from randomizer.rewards.roster import randomizer_unit_roster, installed_rules_template_overlay

    _, clone_ids, templates = randomizer_unit_roster()
    templates, _ = installed_rules_template_overlay(templates, rules)
    inverse = {alias: source for source, alias in clone_ids.items()}
    reviewed = dict(rules)
    forms = set()

    def include(original):
        if original in forms:
            return
        if original not in rules:
            raise ValueError(f'Special unit {original} is not installed.')
        forms.add(original)
        row = deepcopy(templates.get(original, rules[original]))
        for field in ('Convert.Deploy', 'Convert.Land', 'Convert.Water', 'UnloadingClass'):
            if field in row:
                row[field] = inverse.get(row[field], row[field])
                if row[field].lower() not in ('none', ''):
                    include(row[field])
        reviewed[original] = row

    for original in access:
        if original not in templates:
            raise ValueError(f'Special access requires a reviewed reward model: {original}.')
        include(original)
    return reviewed, forms


def production_access(row, friends, country, rules):
    """Replace mission/stolen-tech gates with the faction's ordinary factory."""
    for field in tuple(row):
        if field.startswith(('Prerequisite', 'FactoryOwners')):
            del row[field]
    row.update(TechLevel='1', Owner=','.join(friends), RequiredHouses=','.join(friends),
               ForbiddenHouses='', Prerequisite=FACTORIES[rules[country]['Side']])
