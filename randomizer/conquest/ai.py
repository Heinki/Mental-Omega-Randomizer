"""Route installed native AI recipes to each independently upgraded army."""

from copy import deepcopy
from .profile import GAME, NATIVE_COUNTRIES
from .teams import HOUSE_ALIASES

def route_ai(writer, members, ai_rules, private):
    """Copy native AI recipes per country, retaining their native conditions.

    Helpers must request their own buffed types rather than the private enemy
    copies. Country-scoped trigger copies also handle matching factions on
    opposing teams without opening either side's production gates.
    """
    rules = writer.rules
    ai_sections = {}
    section_ids = {key.casefold(): key for key in ai_rules}
    if GAME == 'reloaded':
        from randomizer.content.inventory import is_cabal_content

    def supported_team(original):
        if original.lower() in ('<none>', 'none', '0', ''):
            return True
        row = ai_rules.get(section_ids.get(original.casefold()), {})
        force = ai_rules.get(section_ids.get(row.get('TaskForce', '').casefold()), {})
        return all(not is_cabal_content(unit.strip(), rules.get(unit.strip(), {}))
                   for field, value in force.items() if field.isdigit()
                   for _, sep, unit in [value.partition(',')] if sep)
    actors = [(HOUSE_ALIASES[m['slot']], NATIVE_COUNTRIES[m['loadout']['country']], private[m['slot']])
              for m in members if m['controller'] == 'ai']
    sides = list(rules['Sides'])
    for country_alias, country, aliases in actors:
        copies = {}

        def team_copy(original):
            if original.lower() in ('<none>', 'none', '0', ''):
                return original
            if original in copies:
                return copies[original]
            source = section_ids.get(original.casefold())
            if source is None:
                raise ValueError(f'Missing native AI team: {original}.')
            alias = writer.key()
            copies[original] = alias
            row = deepcopy(ai_rules[source])
            force = row.get('TaskForce')
            if force:
                force = section_ids[force.casefold()]
                force_alias = writer.key()
                force_row = deepcopy(ai_rules[force])
                for field, value in tuple(force_row.items()):
                    if field.isdigit():
                        count, sep, unit = value.partition(',')
                        if sep:
                            force_row[field] = count + ',' + aliases.get(unit.strip(), unit.strip())
                ai_sections[force_alias] = force_row
                ai_sections.setdefault('TaskForces', {})[str(20000 + len(ai_sections['TaskForces']) if 'TaskForces' in ai_sections else 20000)] = force_alias
                row['TaskForce'] = force_alias
            row['House'] = country_alias
            ai_sections[alias] = row
            ai_sections.setdefault('TeamTypes', {})[str(20000 + len(ai_sections['TeamTypes']) if 'TeamTypes' in ai_sections else 20000)] = alias
            return alias

        side_index = sides.index(rules[country]['Side']) + 1
        for original, value in ai_rules['AITriggerTypes'].items():
            fields = value.split(',')
            if len(fields) != 18:
                raise ValueError(f'Unexpected native AI trigger format: {original}.')
            if fields[2] not in ('<all>', country) or int(fields[12]) not in (0, side_index):
                continue
            # The installed AIMO contains an orphaned Last Bastion Condor
            # recipe. Native loading ignores unresolved teams; do the same.
            if any(fields[index].lower() not in ('<none>', 'none', '0', '')
                   and fields[index].casefold() not in section_ids for index in (1, 14)):
                continue
            if GAME == 'reloaded' and not all(supported_team(fields[index]) for index in (1, 14)):
                continue
            fields[0] = 'Conquest ' + fields[0]
            fields[1], fields[14] = team_copy(fields[1]), team_copy(fields[14])
            fields[2] = country_alias
            # Native condition 1 counts this AI's objects; condition 0
            # counts its enemy. Never substitute this actor's private types
            # into an enemy-owned condition.
            if fields[4] == '1':
                fields[5] = aliases.get(fields[5], fields[5])
            ai_sections.setdefault('AITriggerTypes', {})[writer.key()] = ','.join(fields)
    # The Fortress preload replaces the global trigger registry. Retaining
    # thousands of disabled campaign recipes still makes native house/team
    # selection inspect them; only the active AI actors need recipes.
    ai_sections['AITriggerTypesEnable'] = {key: 'yes' for key in ai_sections.get('AITriggerTypes', {})}
    # Only the preload carries complete AI list additions. Map-local list keys
    # are also registered for native map validation and saved runtime review.
    for section, values in ai_sections.items():
        writer.sections.setdefault(section, {}).update(values)
    return ai_sections

