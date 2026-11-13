"""Independent Ares country bonuses and private weapon/utility upgrades."""

from copy import deepcopy
from math import ceil, floor
import re

from .buff_links import linked_types, rewrite_type_links
from randomizer.final_fortress.player_perks import register_building_equivalent
from randomizer.final_fortress.utilities import utility_updates
from .profile import GAME, NATIVE_COUNTRIES
from .catalogue import FACTORY_TRAINING_PERCENT, PERKS
from .teams import HOUSE_ALIASES

TYPE_LISTS = ('InfantryTypes', 'VehicleTypes', 'AircraftTypes', 'BuildingTypes')


def items(value):
    return [v.strip() for v in str(value or '').split(',') if v.strip()]


def eligible(kind, row, country):
    if GAME == 'reloaded':
        from randomizer.final_fortress.catalogue import eligible as reviewed
        return reviewed(kind, country, row)
    required = items(row.get('RequiredHouses'))
    return (country in items(row.get('Owner')) and
            (not required or country in required) and country not in items(row.get('ForbiddenHouses')))


def weapon_fields(row):
    return [field for field in row if field in ('Primary', 'Secondary', 'Elite', 'ElitePrimary', 'EliteSecondary')
            or re.fullmatch(r'(?:Elite)?Weapon\d+', field)]


def combat_weapon(rules, name):
    row = rules.get(name, {})
    warhead = rules.get(row.get('Warhead'), {})
    if any(warhead.get(field, 'no').lower() == 'yes' for field in ('MindControl', 'Temporal', 'Parasite', 'BombDisarm')):
        return False
    try:
        return (float(row.get('Damage', 0)) > 0 and float(row.get('Range', 0)) > 0
                and row.get('Suicide', 'no').lower() != 'yes')
    except ValueError:
        return False


def infrastructure(row):
    return float(row.get('Strength', 0)) > 1 and row.get('IsBaseDefense', 'no').lower() != 'yes' and (
        bool(row.get('Factory')) or row.get('Refinery', 'no').lower() == 'yes'
        or float(row.get('Power', 0)) > 0 or float(row.get('ProduceCashAmount', 0)) > 0
        or row.get('FreeUnit', 'none').lower() != 'none')


def factory_training_updates(row, rules, country, rank):
    """Use exact native academy lists for barracks and land vehicle factories."""
    factory = row.get('Factory', '').lower()
    if not rank or factory not in ('infantrytype', 'unittype') or row.get('Naval', 'no').lower() == 'yes':
        return {}
    category = 'InfantryTypes' if factory == 'infantrytype' else 'VehicleTypes'
    types = [kind for kind in rules[category].values() if kind in rules
             and eligible(kind, rules[kind], country)
             and rules[kind].get('Trainable', 'yes').lower() != 'no'
             and rules[kind].get('Naval', 'no').lower() != 'yes'
             and 0 <= int(rules[kind].get('TechLevel', '-1')) <= 10]
    if not types:
        # An empty Academy.Types list would train every type instead.
        return {}
    types = sorted(set(types) | {kind for kind in items(row.get('Academy.Types'))
                                if kind.lower() not in ('none', '<none>')})
    value = FACTORY_TRAINING_PERCENT[rank] / 100
    # Organic and ConsideredAircraft vehicle types use different Ares academy
    # categories. Exact IDs keep naval and airfield aircraft out of all three.
    updates = {'Academy.' + category + 'Veterancy':
               f'{max(value, float(row.get("Academy." + category + "Veterancy", 0))):g}'
               for category in ('Infantry', 'Vehicle', 'Aircraft')}
    return {**updates, 'Academy.Types': ','.join(types)}


def perk_utility_updates(kind, row, perks, *, building=False, field_repairs=False):
    """Extend reviewed Fortress utility policies without changing their targets."""
    defense = building and row.get('IsBaseDefense', 'no').lower() == 'yes'
    effective = row
    if defense and perks.get('fortified_emplacements') and float(row.get('Strength', 0)) > 1:
        effective = {**row, 'Strength': str(int(row['Strength']) *
                     (100 + 15 * perks['fortified_emplacements']) // 100)}
    updates = utility_updates(kind, effective, {
        'healing_stacks': 1 if field_repairs else 0,
        'unique_limit_stacks': perks.get('unique_unit_capacity', 0),
        'special_building_limit_stacks': perks.get('special_building_limit', 0),
        'generator_power_percent': 25 * perks.get('generator_efficiency', 0),
        'transport_capacity_stacks': perks.get('transport_capacity', 0),
        'open_topped': bool(perks.get('open_topped_transports')),
    }, building=building, defense=defense)
    if effective is not row:
        # Healing is calculated against the upgraded defense health too.
        updates['Strength'] = effective['Strength']
    return updates


def apply_effects(writer, members, difficulty):
    rules = writer.rules
    categories = {kind: category for category in TYPE_LISTS for kind in rules[category].values()}
    all_aliases = {}
    for member in members:
        loadout, actor = member['loadout'], HOUSE_ALIASES[member['slot']]
        country = NATIVE_COUNTRIES[loadout['country']]
        stats, perks = loadout['stats'], loadout['perks']
        row = deepcopy(rules[country])
        # Explicit gates below preserve native technology while each seat owns
        # independent multipliers, including mirrors and AI allies.
        row.update(Name=actor, ParentCountry=actor, Multiplay='no')
        row.pop('ListIndex', None)
        for suffix in ('Infantry', 'Units', 'Aircraft', 'Buildings', 'Defenses'):
            factors = {'Armor': (1 + stats['health'] / 100) * (1 + stats['armor'] / 100),
                       'BuildTime': 1 - perks.get('production', 0) * .1,
                       'Cost': 1 - perks.get('discount', 0) * .1}
            if suffix in ('Infantry', 'Units', 'Aircraft'):
                factors['Speed'] = 1 + stats['speed'] / 100
            for prefix, factor in factors.items():
                field = prefix + suffix + 'Mult'
                row[field] = f'{float(row.get(field, 1)) * factor:.8g}'
        writer.sections[actor] = row
        writer.register('Countries', actor)
        writer.put('CQCountryOrigins', actor, country)
        allowed = {kind for kind, category in categories.items() if eligible(kind, rules[kind], country)}
        # Scripted escorts are faction grants, including heroes normally
        # unlocked by a late tech branch. Their build gates remain native.
        delivered = set(loadout['force']['units']) | set(loadout['force']['structures'])
        candidates = allowed | delivered
        aliases = all_aliases[member['slot']] = {}
        utilities = {}
        for kind in sorted(candidates):
            row, category = rules[kind], categories[kind]
            building = category == 'BuildingTypes'
            combat = any(combat_weapon(rules, row.get(f)) for f in weapon_fields(row))
            defense = building and row.get('IsBaseDefense', 'no').lower() == 'yes'
            updates = perk_utility_updates(kind, row, perks, building=building,
                                           field_repairs=loadout.get('field_repairs', False))
            if building:
                updates.update(factory_training_updates(row, rules, country, perks.get('factory_training', 0)))
            if defense and perks.get('veteran_defenses'):
                updates.update(Trainable='yes',
                    VeteranAbilities=row.get('VeteranAbilities', 'STRONGER'),
                    EliteAbilities=row.get('EliteAbilities', 'STRONGER,FIREPOWER,ROF'))
            if building and infrastructure(row) and perks.get('hardened_infrastructure'):
                updates['Strength'] = str(max(1, floor(float(row['Strength']) * (1 + perks['hardened_infrastructure'] * .1))))
            utilities[kind] = updates
            if updates or combat and (stats['damage'] or stats['reload'] or perks.get('extended_arsenal')
                                      or difficulty == 'Impossible' and member['controller'] == 'ai'):
                aliases[kind] = writer.key()
        pending = list(aliases)
        while pending:
            kind = pending.pop()
            for _, target in linked_types(rules[kind], categories):
                if target not in aliases:
                    aliases[target] = writer.key()
                    pending.append(target)
        # Free collectors, MCVs and deployment chains must stay within their
        # commander's private production/docking graph.
        changed = True
        while changed:
            changed = False
            for kind in sorted(allowed):
                if kind in aliases:
                    continue
                row = rules[kind]
                if any(value in aliases for field in ('FreeUnit', 'DeploysInto', 'UndeploysInto', 'PowersUpBuilding') for value in items(row.get(field))):
                    aliases[kind] = writer.key()
                    changed = True
        weapons = {}
        for kind, alias in aliases.items():
            original = rules[kind]
            row = deepcopy(original)
            row.update(Image=original.get('Image', kind), Owner=actor,
                       RequiredHouses=actor if kind in allowed else 'Neutral', ForbiddenHouses='')
            row.update(utilities.get(kind, {}))
            rewrite_type_links(row, aliases)
            for field in weapon_fields(original):
                name = original[field]
                if not combat_weapon(rules, name):
                    continue
                if name not in weapons:
                    weapon = deepcopy(rules[name])
                    damage = (1 + stats['damage'] / 100) * (1.25 if difficulty == 'Impossible' and member['controller'] == 'ai' else 1)
                    weapon['Damage'] = str(max(1, floor(float(weapon['Damage']) * damage)))
                    if float(weapon.get('ROF', 0)) > 0:
                        weapon['ROF'] = str(max(1, ceil(float(weapon['ROF']) / (1 + stats['reload'] / 100))))
                    rank = perks.get('extended_arsenal', 0)
                    weapon['Range'] = f'{float(weapon["Range"]) + rank:g}'
                    if rank and float(weapon.get('ProjectileRange', 0)) > 0:
                        weapon['ProjectileRange'] = f'{float(weapon["ProjectileRange"]) + rank:g}'
                    weapons[name] = writer.key()
                    writer.sections[weapons[name]] = weapon
                    writer.register('WeaponTypes', weapons[name])
                row[field] = weapons[name]
            writer.sections[alias] = row
            writer.register(categories[kind], alias)
        # Every native type, including unmodified engineers and factories,
        # needs concrete masks for the new country indices.
        registered_countries = set(rules['Countries'].values())
        for kind, category in categories.items():
            original = rules[kind]
            if category != 'BuildingTypes':
                # Owner alone is not a native production gate after a country
                # is cloned. Reproduce the concrete native masks, as Fortress
                # does, so subfaction tanks/engineers cannot leak across seats.
                native = set(items(original.get('Owner'))) & registered_countries
                required = set(items(original.get('RequiredHouses')))
                if required:
                    native &= required
                native -= set(items(original.get('ForbiddenHouses')))
                previous = set(items(writer.sections.get(kind, {}).get('RequiredHouses'))) & set(HOUSE_ALIASES)
                if kind in allowed and kind not in aliases:
                    previous.add(actor)
                writer.put(kind, 'RequiredHouses', ','.join(sorted(native | previous)) or 'Neutral')
            for field in ('Owner', 'RequiredHouses', 'ForbiddenHouses'):
                if field == 'RequiredHouses' and category != 'BuildingTypes':
                    continue
                current = items(writer.sections.get(kind, {}).get(field, original.get(field)))
                if kind in allowed and kind not in aliases and field in ('Owner', 'RequiredHouses'):
                    if field == 'RequiredHouses' and not items(original.get(field)):
                        continue
                    current.append(actor)
                if field == 'ForbiddenHouses' and (kind in aliases or country in items(original.get(field))):
                    current.append(actor)
                if current:
                    writer.put(kind, field, ','.join(dict.fromkeys(current)))
        # Update global base/factory selectors without removing native types.
        for section in ('General', 'AI'):
            for field, value in rules.get(section, {}).items():
                if not (field.startswith(('Build', 'Prerequisite')) or field in ('BaseUnit', 'HarvesterUnit', 'PadAircraft')):
                    continue
                additions = [aliases[v] for v in items(value) if v in aliases]
                if additions:
                    current = items(writer.sections.get(section, {}).get(field, value))
                    writer.put(section, field, ','.join(dict.fromkeys([*current, *additions])))
        for field in ('AI.PowerPlants', 'ParaDrop.Types', 'VeteranInfantry', 'VeteranUnits', 'VeteranAircraft', 'VeteranBuildings'):
            if field in writer.sections[actor]:
                writer.sections[actor][field] = ','.join(aliases.get(v, v) for v in items(writer.sections[actor][field]))
        if perks.get('veteran_defenses'):
            defenses = [aliases[kind] for kind in sorted(candidates)
                        if categories[kind] == 'BuildingTypes'
                        and rules[kind].get('IsBaseDefense', 'no').lower() == 'yes']
            native = items(writer.sections[actor].get('VeteranBuildings'))
            writer.put(actor, 'VeteranBuildings', ','.join(dict.fromkeys([*native, *defenses])))
            # Granted buildings are constructed Neutral before their start-
            # location ownership transfer. Only this seat's private types train.
            native = items(writer.sections.get('Neutral', {}).get('VeteranBuildings',
                           rules.get('Neutral', {}).get('VeteranBuildings')))
            granted = [aliases[kind] for kind in sorted(loadout['force']['structures'])
                       if rules[kind].get('IsBaseDefense', 'no').lower() == 'yes']
            # Future factory-built defenses use the actor's list. Keep only
            # granted types on Neutral to stay within native INI list limits.
            writer.put('Neutral', 'VeteranBuildings', ','.join(dict.fromkeys([*native, *granted])))
        for kind, alias in aliases.items():
            if categories[kind] == 'BuildingTypes':
                register_building_equivalent(writer, rules, kind, alias, aliases, preserve_native=True)
    from .technology import repair_technology
    repair_technology(writer, members, all_aliases)
    return all_aliases


def perk_inventory(rules):
    """Inventory actual installed native targets; never unlock missing technology."""
    result = {}
    keys = ('veteran_defenses', 'unique_unit_capacity', 'special_building_limit',
            'factory_training', 'fortified_emplacements', 'generator_efficiency',
            'transport_capacity', 'open_topped_transports')
    for label, country in NATIVE_COUNTRIES.items():
        targets = {key: [] for key in keys if key in PERKS}
        for category in TYPE_LISTS:
            building = category == 'BuildingTypes'
            for kind in rules[category].values():
                if kind not in rules or not eligible(kind, rules[kind], country):
                    continue
                row = rules[kind]
                if int(row.get('TechLevel', '-1')) < 0:
                    continue
                defense = building and row.get('IsBaseDefense', 'no').lower() == 'yes'
                if defense:
                    targets['veteran_defenses'].append(kind)
                if building and factory_training_updates(row, rules, country, 1):
                    targets['factory_training'].append(kind)
                for key, field in (('unique_unit_capacity', 'BuildLimit'),
                                   ('special_building_limit', 'BuildLimit'),
                                   ('fortified_emplacements', 'Strength'),
                                   ('generator_efficiency', 'Power'),
                                   ('transport_capacity', 'Passengers'),
                                   ('open_topped_transports', 'OpenTopped')):
                    if key in targets and field in perk_utility_updates(kind, row, {key: 1}, building=building):
                        targets[key].append(kind)
        result[label] = {key: sorted(values) for key, values in targets.items()}
    return result
