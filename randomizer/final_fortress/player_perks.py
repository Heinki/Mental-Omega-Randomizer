"""Native skirmish adapters for player perks and allied helper production."""

from copy import deepcopy
from math import ceil, floor
import re

from randomizer.maps.buff_values import _register_map_type
from randomizer.maps.enemy_scaling import _authored_tech_tier


def coalition(plan):
    return [('FFPLAYER', plan['player_country'], plan['map']['player_waypoint']),
            *[(f'FFALLY{i + 1}', country, waypoint) for i, (country, waypoint) in enumerate(
                zip(plan.get('allied_countries', []), plan.get('allied_waypoints', [])))]]


def human_actor(plan, actor):
    """Human guests occupy the first friendly start positions."""
    count = len(plan.get('coop_players', [])) or 1
    return actor in [entry[0] for entry in coalition(plan)[:count]]


def needs_countries(plan):
    effects = plan['effects']
    return bool(plan.get('plan_version', 1) >= 23 and plan['player_country'] in ('USSR', 'Latin', 'Chinese')
                or plan.get('allied_countries') or effects.get('production_percent')
                or effects.get('tier_buffs') or effects.get('defense_percent')
                or effects.get('defense_veterancy') or effects.get('support_powers')
                or effects.get('special_access') or effects.get('reinforcements')
                or effects.get('lab_reserve_units')
                or effects.get('generator_power_percent')
                or effects.get('construction_discount_percent') or effects.get('unit_discount_percent')
                or effects.get('special_building_limit_stacks')
                or any(plan.get('fundraising_ranks', []))
                or any(effects.get(field) for field in ('healing_stacks', 'recon_stacks',
                                                        'unique_limit_stacks', 'income_stacks')))


def _eligible(row, country):
    def parts(field):
        return {part.strip() for part in row.get(field, '').split(',') if part.strip()}
    return (country in parts('Owner') and (not parts('RequiredHouses') or country in parts('RequiredHouses'))
            and country not in parts('ForbiddenHouses'))


def register_building_equivalent(writer, rules, original, alias, aliases, *, preserve_native=False):
    """Keep refinery prerequisites and harvester docks valid for private copies."""
    for section in ('General', 'GenericPrerequisites'):
        for field, value in rules.get(section, {}).items():
            if (section == 'GenericPrerequisites' or field.startswith('Prerequisite')) and original in value.split(','):
                existing = writer.sections.get(section, {}).get(field, value)
                writer.put(section, field, ','.join(dict.fromkeys([*existing.split(','), alias])))
    for key, base in rules.items():
        if original in base.get('Dock', '').split(','):
            for target in {key, aliases.get(key, key)}:
                existing = writer.sections.get(target, {}).get('Dock', base['Dock'])
                writer.put(target, 'Dock', ','.join(dict.fromkeys([*existing.split(','), alias])))
        prerequisites = base.get('Prerequisite', '').split(',')
        if original in prerequisites:
            for target in {key, aliases.get(key, key)}:
                existing = writer.sections.get(target, {}).get('Prerequisite.Lists', base.get('Prerequisite.Lists', '0'))
                index = int(existing)
                writer.put(target, 'Prerequisite.Lists', index + 1)
                # List0 replaces the default prerequisites; extra lists start
                # at one. Writing List0 while declaring one extra list both
                # erased the normal build path and left an empty alternative.
                slot = index + 1 if preserve_native else index
                writer.put(target, f'Prerequisite.List{slot}', ','.join(alias if part == original else part for part in prerequisites))


def gate_prerequisite_overrides(writer, plan, rules):
    """Keep shortcut buildings without letting them bypass private house gates.

    Ares checks PrerequisiteOverride before Required/ForbiddenHouses (and even
    TechLevel). Alternative prerequisite lists retain the shortcut while still
    enforcing those gates. Apply after copying types so originals, production
    copies, gifts and enemy copies all receive the same safe interpretation.
    """
    if plan.get('plan_version', 1) < 14:
        return
    from randomizer.maps.ini import section_value_map
    for category in ('InfantryTypes', 'VehicleTypes', 'AircraftTypes', 'BuildingTypes'):
        types = dict.fromkeys([*rules[category].values(),
                               *section_value_map(writer.lines, category).values(),
                               *writer.sections.get(category, {}).values()])
        for kind in types:
            row = {**rules.get(kind, {}), **writer.sections.get(kind, {})}
            shortcuts = [value.strip() for value in row.get('PrerequisiteOverride', '').split(',')
                         if value.strip() and value.strip().lower() != 'none']
            if not shortcuts:
                continue
            count = int(row.get('Prerequisite.Lists', '0'))
            for value in shortcuts:
                count += 1
                writer.put(kind, f'Prerequisite.List{count}', value)
            writer.put(kind, 'Prerequisite.Lists', count)
            writer.put(kind, 'PrerequisiteOverride', 'none')


def apply_player_types(writer, plan, rules, *, reserved_aliases=None):
    """Isolate playable unit/defense copies from enemy and native country stats.

    Percentages describe a linear improvement from installed values, capped by
    the configuration contract. Healing and mind-control weapons retain their
    semantics; only positive, damaging weapons receive firepower bonuses.
    """
    private_player = needs_countries(plan)
    effects = plan['effects']
    from .utilities import supported_pairs, utility_updates
    from .arsenal import production_access, reviewed_rules
    from randomizer.rewards.catalogue import SPECIAL_REWARD_UNIT_IDS
    access = set(effects.get('special_access', []))
    special_deliveries = {unit['type'] for unit in (effects.get('reinforcements') or {}).get('units', [])
                          if unit['type'] in SPECIAL_REWARD_UNIT_IDS}
    native_drakuv = plan['player_country'] in ('USSR', 'Latin', 'Chinese') and private_player
    if native_drakuv:
        special_deliveries.add('RAVA')
    rules, special_forms = reviewed_rules(rules, access | special_deliveries)
    friends = coalition(plan) if private_player else []
    for alias, country, _ in friends:
        row = deepcopy(rules[country])
        row.update(Name=alias, ParentCountry=country, Multiplay='no')
        for suffix in ('Infantry', 'Units', 'Aircraft', 'Buildings', 'Defenses'):
            field = f'BuildTime{suffix}Mult'
            row[field] = str(float(row.get(field, '1')) * (1 - effects.get('production_percent', 0) / 100))
            discount = effects.get('construction_discount_percent' if suffix in ('Buildings', 'Defenses')
                                   else 'unit_discount_percent', 0)
            if discount:
                field = f'Cost{suffix}Mult'
                row[field] = str(float(row.get(field, '1')) * (1 - discount / 100))
        writer.sections[alias] = row
        indices = [int(key) for row in (rules['Countries'], writer.sections.get('Countries', {}))
                   for key in row if key.isdigit()]
        writer.put('Countries', max(indices) + 1, alias)

    # Required/forbidden country masks refer to concrete indices. Reproduce
    # native restrictions for every derivative, even on unmodified types
    # (engineers otherwise appear for all four factions).
    actors = [(name, country) for name, country, _ in friends]
    actors.extend((f'FFENEMY{i + 1}', country) for i, country in enumerate(plan['enemy_countries']))
    for category in ('InfantryTypes', 'VehicleTypes', 'AircraftTypes', 'BuildingTypes'):
        for original in rules[category].values():
            base = rules[original]
            if plan.get('plan_version', 1) >= 13 and category != 'BuildingTypes':
                owners = set(base.get('Owner', '').split(','))
                required = set(base.get('RequiredHouses', '').split(',')) - {''}
                forbidden = set(base.get('ForbiddenHouses', '').split(',')) - {''}
                allowed = owners - forbidden
                if required:
                    allowed &= required
                # Owner alone is insufficient once private prerequisite
                # equivalents exist. Gate native units to concrete countries.
                concrete = allowed | {name for name, country in actors if country in allowed}
                writer.put(original, 'RequiredHouses', ','.join(sorted(concrete)) or 'Neutral')
            for field in ('Owner', 'RequiredHouses', 'ForbiddenHouses'):
                if field == 'RequiredHouses' and plan.get('plan_version', 1) >= 13 and category != 'BuildingTypes':
                    continue
                native = {value.strip() for value in base.get(field, '').split(',') if value.strip()}
                if not native:
                    continue
                current = writer.sections.get(original, {}).get(field, base[field])
                additions = [name for name, country in actors if country in native]
                if additions:
                    writer.put(original, field, ','.join(dict.fromkeys([*current.split(','), *additions])))

    if not private_player:
        return {}

    categories = {key: category for category in ('InfantryTypes', 'VehicleTypes', 'AircraftTypes', 'BuildingTypes')
                  for key in rules[category].values()}
    delivered = {unit.strip() for power in effects.get('support_powers', [])
                 for field in ('Deliver.Types', 'ParaDrop.Types')
                 for unit in rules.get(power, {}).get(field, '').split(',') if unit.strip()}
    delivered.update(unit['type'] for unit in effects['starting_units'])
    delivered.update(effects.get('defense_types', []))
    delivered.update(unit['type'] for unit in effects['starting_defenses'])
    delivered.update(unit['type'] for unit in (effects.get('reinforcements') or {}).get('units', []))
    delivered.update(unit['type'] for unit in effects.get('lab_reserve_units', []))
    if native_drakuv:
        delivered.add('RAVA')
    aliases = {}
    for original, category in categories.items():
        row = rules.get(original, {})
        defense = category == 'BuildingTypes' and row.get('IsBaseDefense', 'no').lower() == 'yes'
        utilities = utility_updates(original, row, effects, building=category == 'BuildingTypes', defense=defense)
        prison = native_drakuv and original == 'NAPRIS'
        if category == 'BuildingTypes' and not defense and not utilities and not prison:
            continue
        eligible = [alias for alias, country, _ in friends if _eligible(row, country)]
        if original in delivered or original in special_forms:
            eligible = [alias for alias, _, _ in friends]
        tier = _authored_tech_tier(row)
        percent = effects.get('defense_percent', 0) if defense else effects.get('tier_buffs', {}).get(str(tier), 0)
        if not eligible or not (percent or utilities or original in special_forms or prison
                                 or (defense and effects.get('defense_veterancy'))):
            continue
        # Include conversion-only counterparts when reachable from a playable
        # source below; they may have TechLevel=-1 and no ownership declaration.
        aliases[original] = (reserved_aliases or {}).get(original) or writer.key()

    # A newly built refinery's FreeUnit must be the same buffed harvester that
    # the factory produces; enemy refineries retain their native free units.
    for original in rules['BuildingTypes'].values():
        row = rules[original]
        if row.get('FreeUnit') in aliases and any(_eligible(row, country) for _, country, _ in friends):
            aliases[original] = writer.key()

    mutation_targets = {}
    if plan.get('plan_version', 1) >= 10 and any(
            rules[country]['Side'] == 'FourthSide' for _, country, _ in friends):
        from randomizer.rewards.definitions import LINKED_BUFF_VARIANTS
        mutation_targets = {source: target for source, variants in LINKED_BUFF_VARIANTS.items()
                            for target, entry in variants.items() if entry.get('nanofiber_stage')}
    mutation_sources = {}
    capacity_pairs = supported_pairs() if effects.get('special_building_limit_stacks') else ()

    def conversion_fields(original):
        fields = ('Convert.Deploy', 'Convert.Land', 'Convert.Water', 'UnloadingClass')
        if (original, 'building_limit') in capacity_pairs:
            fields += ('DeploysInto', 'UndeploysInto')
        return fields

    def include_conversions(original):
        for field in conversion_fields(original):
            target = rules[original].get(field, '')
            if target in categories and target not in aliases:
                aliases[target] = writer.key()
                include_conversions(target)
        target = mutation_targets.get(original)
        if target:
            mutation_sources[target] = original
            if target not in aliases:
                aliases[target] = writer.key()
                include_conversions(target)
    for original in tuple(aliases):
        include_conversions(original)

    weapons = {}
    for original, alias in aliases.items():
        row = deepcopy(rules[original])
        category = categories[original]
        defense = category == 'BuildingTypes' and row.get('IsBaseDefense', 'no').lower() == 'yes'
        tier = _authored_tech_tier(rules[mutation_sources.get(original, original)])
        # Conversion forms inherit their playable counterpart's tier.
        if not tier:
            tier = next((_authored_tech_tier(rules[source]) for source in aliases
                         if original in [rules[source].get(field) for field in
                                         ('Convert.Deploy', 'Convert.Land', 'Convert.Water', 'UnloadingClass')]), 0)
        percent = effects.get('defense_percent', 0) if defense else effects.get('tier_buffs', {}).get(str(tier), 0)
        if category == 'BuildingTypes' and not defense and plan.get('plan_version', 1) >= 12:
            percent = 0
        factor = 1 + percent / 100
        native_eligible = [name for name, country, _ in friends if _eligible(row, country)]
        eligible = native_eligible[:]
        if original in delivered or original in special_forms:
            eligible = [name for name, _, _ in friends]
        if not eligible and (int(row.get('TechLevel', '-1')) < 0 or original in mutation_sources):
            eligible = [name for name, _, _ in friends]
        owners = {part.strip() for part in row.get('Owner', '').split(',') if part.strip()}
        forbidden = {part.strip() for part in writer.sections.get(original, {}).get(
            'ForbiddenHouses', row.get('ForbiddenHouses', '')).split(',') if part.strip()}
        row.update(Image=row.get('Image', original), Owner=','.join(sorted(owners | set(eligible))),
                   RequiredHouses=','.join(eligible) or 'Neutral', ForbiddenHouses='',
                   AllowedToStartInMultiplayer='no')
        if not native_eligible and original not in access and (
                original in delivered or original in mutation_sources):
            # A gift from a sister subfaction receives buffs without granting
            # access to that subfaction's regular production roster.
            row.update(TechLevel='-1', BuildLimit='0')
        if original in access:
            production_access(row, [name for name, _, _ in friends], plan['player_country'], rules)
        elif original in special_forms:
            row.update(TechLevel='-1', BuildLimit='0')
        if percent and not defense and float(row.get('Strength', '0')) > 1:
            row['Strength'] = str(floor(float(row['Strength']) * factor))
        row.update(utility_updates(original, row, effects, building=category == 'BuildingTypes', defense=defense))
        if defense and effects.get('defense_veterancy'):
            row['Trainable'] = 'yes'
            # Ares reads VeteranBuildings on the concrete country; native
            # initial ranks are also set explicitly on preplaced defenses.
            row.setdefault('VeteranAbilities', 'STRONGER')
            row.setdefault('EliteAbilities', 'STRONGER,FIREPOWER,ROF')
        for field, weapon in tuple(row.items()):
            if not re.fullmatch(r'(?:Elite)?(?:Primary|Secondary|Weapon\d+)', field) or weapon not in rules:
                continue
            base = rules[weapon]
            warhead = rules.get(base.get('Warhead', ''), {})
            if not percent or float(base.get('Damage', '0')) <= 0:
                continue
            # Missile carriers and spawners use separate child weapons; do not
            # multiply their launch-count pseudo damage.
            if base.get('Spawner', 'no').lower() == 'yes':
                continue
            weapon_key = (weapon, percent, defense)
            if weapon_key not in weapons:
                clone = writer.key()
                values = deepcopy(base)
                if warhead.get('MindControl', 'no').lower() != 'yes':
                    values['Damage'] = str(max(1, floor(float(base['Damage']) * factor)))
                if float(base.get('ROF', '0')) > 1:
                    values['ROF'] = str(max(1, ceil(float(base['ROF']) / factor)))
                if defense and float(base.get('Range', '0')) > 0:
                    values['Range'] = f'{float(base["Range"]) * factor:g}'
                writer.sections[clone] = values
                _register_map_type(writer.sections, writer.lines, rules, 'WeaponTypes', clone)
                weapons[weapon_key] = clone
            row[field] = weapons[weapon_key]
        for field in (*conversion_fields(original), 'FreeUnit', 'PowersUpBuilding'):
            if row.get(field) in aliases:
                row[field] = aliases[row[field]]
        writer.sections[alias] = row
        _register_map_type(writer.sections, writer.lines, rules, category, alias)
        writer.put(original, 'ForbiddenHouses', ','.join(sorted(forbidden | {name for name, _, _ in friends})))
    for original, alias in aliases.items():
        if categories[original] == 'BuildingTypes':
            register_building_equivalent(writer, rules, original, alias, aliases,
                                         preserve_native=plan.get('plan_version', 1) >= 14)
    if effects.get('defense_veterancy'):
        for name, country, _ in friends:
            defenses = [aliases.get(original, original) for original in rules['BuildingTypes'].values()
                        if rules[original].get('IsBaseDefense', 'no').lower() == 'yes' and _eligible(rules[original], country)]
            existing = rules[country].get('VeteranBuildings', '')
            writer.sections[name]['VeteranBuildings'] = ','.join(filter(None, [existing, *defenses]))
        # Preplaced objects are constructed Neutral before the start-location
        # ownership transfer. Only private player defenses receive this rank.
        private_defenses = [alias for original, alias in aliases.items()
                            if rules[original].get('IsBaseDefense', 'no').lower() == 'yes']
        writer.put('Neutral', 'VeteranBuildings', ','.join(filter(None, [rules['Neutral'].get('VeteranBuildings', ''), *private_defenses])))
    # Side-level AI defense lists are shared. Add private candidates alongside
    # native ones; their concrete-country gates select the appropriate copy.
    defaults = {'GDI': 'AlliedBaseDefenses', 'Nod': 'SovietBaseDefenses',
                'ThirdSide': 'ThirdBaseDefenses'}
    for side in {rules[country]['Side'] for _, country, _ in friends}:
        native = rules.get(side, {}).get('AI.BaseDefenses', rules['AI'].get(defaults.get(side, ''), ''))
        values = [value.strip() for value in native.split(',') if value.strip()]
        additions = [aliases[value] for value in values if value in aliases]
        if additions:
            current = writer.sections.get(side, {}).get('AI.BaseDefenses', ','.join(values))
            writer.put(side, 'AI.BaseDefenses', ','.join(dict.fromkeys([*current.split(','), *additions])))
    for field, value in rules['AI'].items():
        native = value.split(',')
        additions = [aliases[unit] for unit in native if unit in aliases]
        if additions:
            current = writer.sections.get('AI', {}).get(field, value)
            writer.put('AI', field, ','.join(dict.fromkeys([*current.split(','), *additions])))
    for field in ('BaseUnit', 'HarvesterUnit'):
        native = rules['General'].get(field, '').split(',')
        if any(unit in aliases for unit in native):
            current = writer.sections.get('General', {}).get(field, ','.join(native))
            writer.put('General', field, ','.join([current, *(aliases[unit] for unit in native if unit in aliases)]))
    for name, _, _ in friends:
        for field, value in tuple(writer.sections[name].items()):
            if field.startswith('Veteran') or field in ('ParaDrop.Types', 'AI.PowerPlants'):
                writer.sections[name][field] = ','.join(aliases.get(unit, unit) for unit in value.split(','))
    if mutation_sources:
        from randomizer.maps.ini import IniLines, merge_ini_section_values
        from randomizer.maps.nanofiber import nanofiber_clone_rules
        current = IniLines(list(writer.lines))
        merge_ini_section_values(current, writer.sections)
        linked = nanofiber_clone_rules(current, rules, {
            original: {'clone_id': alias} for original, alias in aliases.items()})
        for section, values in linked.items():
            writer.sections.setdefault(section, {}).update(values)
    for original in sorted(access):
        writer.put('FFSpecialAccess', original, aliases[original])
    if plan.get('plan_version', 1) >= 12:
        for original, alias in aliases.items():
            writer.put('FFPlayerTypes', original, alias)
    return aliases


def route_ai(writer, plan, rules, ai_rules, enemy_aliases, player_aliases):
    """Copy native AI recipes per country, retaining their native conditions.

    Helpers must request their own buffed types rather than the private enemy
    copies. Country-scoped trigger copies also handle matching factions on
    opposing teams without opening either side's production gates.
    """
    ai_sections = {}
    section_ids = {key.casefold(): key for key in ai_rules}
    actors = [(f'FFENEMY{i + 1}', country, enemy_aliases) for i, country in enumerate(plan['enemy_countries'])]
    actors.extend((name, country, player_aliases) for name, country, _ in coalition(plan)[1:]
                  if not human_actor(plan, name))
    sides = list(rules['Sides'])
    for original, value in ai_rules.get('AITriggerTypes', {}).items():
        fields = value.split(',')
        if len(fields) != 18:
            raise ValueError(f'Unexpected native AI trigger format: {original}.')
        disabled = fields[:]
        disabled[15:18] = ['0', '0', '0']
        ai_sections.setdefault('AITriggerTypes', {})[original] = ','.join(disabled)
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
            if plan.get('plan_version', 1) >= 16 and country_alias.startswith('FFALLY'):
                script = section_ids.get(row.get('Script', '').casefold())
                script_row = deepcopy(ai_rules.get(script, {}))
                changed = False
                for field, value in tuple(script_row.items()):
                    # Native assault recipes often insist on buildings or
                    # defenses. Protected starting yards and fixed turrets
                    # must not trap helpers in attacks against immortal targets.
                    if field.isdigit() and value in ('0,2', '0,6', '0,7'):
                        script_row[field] = '0,1'
                        changed = True
                if changed:
                    script_alias = writer.key()
                    ai_sections[script_alias] = script_row
                    ai_sections.setdefault('ScriptTypes', {})[str(20000 + len(ai_sections.get('ScriptTypes', {})))] = script_alias
                    row['Script'] = script_alias
            ai_sections[alias] = row
            ai_sections.setdefault('TeamTypes', {})[str(20000 + len(ai_sections['TeamTypes']) if 'TeamTypes' in ai_sections else 20000)] = alias
            return alias

        side_index = sides.index(rules[country]['Side']) + 1
        for original, value in ai_rules['AITriggerTypes'].items():
            fields = value.split(',')
            if fields[2] not in ('<all>', country) or int(fields[12]) not in (0, side_index):
                continue
            # The installed AIMO contains an orphaned Last Bastion Condor
            # recipe. Native loading ignores unresolved teams; do the same.
            if any(fields[index].lower() not in ('<none>', 'none', '0', '')
                   and fields[index].casefold() not in section_ids for index in (1, 14)):
                continue
            fields[0] = 'Final Fortress ' + fields[0]
            fields[1], fields[14] = team_copy(fields[1]), team_copy(fields[14])
            fields[2] = country_alias
            if fields[4] == '0':
                fields[5] = aliases.get(fields[5], fields[5])
            ai_sections.setdefault('AITriggerTypes', {})[writer.key()] = ','.join(fields)
    # Only the preload carries complete AI list additions. Map-local list keys
    # are also registered for native map validation and saved runtime review.
    for section, values in ai_sections.items():
        writer.sections.setdefault(section, {}).update(values)
    return ai_sections


def support_powers(writer, plan, rules, country_aliases):
    """Attach private, repeatable support powers to each coalition's lab proxy."""
    if plan.get('plan_version', 1) >= 9:
        from .powers import apply_powers
        return apply_powers(writer, plan, rules, country_aliases)
    from .engine import _action, _place, _transfer_tag
    from randomizer.maps.ini import section_value_map
    powers = plan['effects'].get('support_powers', [])
    if not powers and not (plan.get('allied_countries') and plan['effects']['starting_credits']):
        return
    for actor_index, (name, country, waypoint) in enumerate(coalition(plan)):
        if name == 'FFPLAYER' and not powers:
            continue
        clones = []
        for original in powers:
            if original not in rules.get('SuperWeaponTypes', {}).values():
                raise ValueError(f'Unknown support power: {original}.')
            alias = writer.key()
            row = deepcopy(rules[original])
            row['Name'] = 'Fortress ' + row.get('Name', original)
            # Preserve the installed localized name, avoiding NOSTR's short
            # literal-name limit for longer faction power names.
            # Independent perk powers do not require a second native provider.
            for field in ('SW.AuxBuildings', 'SW.NegBuildings', 'SW.RequiredHouses',
                          'SW.ForbiddenHouses', 'SW.Designators'):
                row.pop(field, None)
            row.update(IsPowered='no', DisableableFromShell='no')
            if original == 'AmericanParaDropSpecial':
                native = plan['effects']['starting_units']
                if native:
                    row['ParaDrop.Types'] = ','.join(country_aliases.get(unit['type'], unit['type']) for unit in native[:2])
                    row['ParaDrop.Num'] = '6,4' if len(native) > 1 else '10'
            for field in ('ParaDrop.Types', 'Deliver.Types'):
                if field in row:
                    row[field] = ','.join(country_aliases.get(unit.strip(), unit.strip()) for unit in row[field].split(','))
            writer.sections[alias] = row
            _register_map_type(writer.sections, writer.lines, rules, 'SuperWeaponTypes', alias)
            clones.append(alias)
        provider = writer.key()
        row = deepcopy(rules['CABHUT'])
        row.update(Image='CABHUT', Name='Final Fortress support powers', InvisibleInGame='yes',
                   IsPassable='yes', Immune='yes', LegalTarget='no', Selectable='no', Capturable='no',
                   Insignificant='no', DontScore='no', KeepAlive='no', RadarInvisible='yes',
                   Unsellable='yes', CanBeOccupied='no', BridgeRepairHut='no',
                   TechLevel='-1', BuildLimit='0',
                   ProduceCashStartup=str(plan['effects']['starting_credits'] if name != 'FFPLAYER' else 0),
                   ProduceCashAmount='0', ProduceCashDelay='0')
        if clones:
            row['SuperWeapon'] = clones[0]
        if len(clones) > 1:
            row['SuperWeapon2'] = clones[1]
        writer.sections[provider] = row
        _register_map_type(writer.sections, writer.lines, rules, 'BuildingTypes', provider)
        # Use a spare start, away from the helpers' building footprints. Keep
        # this row separate from the cash escrows on the start's center row.
        points = section_value_map(writer.lines, 'Waypoints')
        occupied_starts = {plan['map']['player_waypoint'], *plan['map']['enemy_waypoints'],
                           *plan.get('allied_waypoints', [])}
        unused = next(number for number in range(8) if number not in occupied_starts)
        cell = int(points[str(unused)])
        tag = _transfer_tag(writer, waypoint, 'Support power ownership ' + name)
        _place(writer, 'Structures', f'Neutral,{provider},256,{cell % 1000 + actor_index},'
               f'{cell // 1000 + 1},64,{tag},1,0,1,0,0,None,None,None,0,0')
        if clones:
            registered = list(dict.fromkeys([
                *rules['SuperWeaponTypes'].values(),
                *section_value_map(writer.lines, 'SuperWeaponTypes').values(),
                *writer.sections.get('SuperWeaponTypes', {}).values()]))
            # CABHUT-derived invisible providers are not sufficient to make
            # powers available after a skirmish ownership transfer. Use the
            # same native repeating-power action as earned Grid/Shop powers.
            writer.trigger('Fortress perk powers ' + name, [(13, 0, 2)],
                           [_action(34, registered.index(alias)) for alias in clones], owner=name)
