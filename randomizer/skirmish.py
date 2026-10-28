"""Disposable native Skirmish maps using existing progression reward adapters."""

from copy import deepcopy
import hashlib
from pathlib import Path
import random

from randomizer.core.storage import atomic_write_text
from randomizer.maps.ini import IniLines, all_section_value_maps_preserve, merge_ini_section_values

GAME = 'mo'


def multiplayer_colors(root):
    sections = all_section_value_maps_preserve((Path(root) / 'Resources/GameOptions.ini').read_bytes().decode('latin-1').splitlines())
    rows = next((values for name, values in sections.items() if name.lower() == 'mpcolors'), {})
    colors = {}
    for name, value in rows.items():
        raw = value.split(';', 1)[0].split(',')[-1].strip()
        if raw.isdigit() and 0 <= int(raw) < 64:
            colors[name] = int(raw)
    if not colors:
        raise ValueError('Installed multiplayer color catalogue is missing.')
    return colors


def playable_countries():
    if GAME == 'dta':
        from randomizer.final_fortress.catalogue import COUNTRY_LABELS
    elif GAME == 'reloaded':
        from randomizer.final_fortress.catalogue import COUNTRY_LABELS
    else:
        from randomizer.challenges.catalogue import COUNTRY_LABELS
    return {label: country for country, label in COUNTRY_LABELS.items()}


def discover_maps(root):
    """Offer unscripted maps only; authored campaigns keep their own adapters."""
    root = Path(root)
    result = {}
    for directory in ('Maps', 'MapsMO'):
        folder = root / directory
        if not folder.is_dir():
            continue
        for source in sorted(folder.rglob('*')):
            if source.suffix.lower() not in ('.map', '.mpr', '.yrm'):
                continue
            if any(part.casefold() in ('co-op', 'cooperative', 'coop', 'challenge', 'campaign') for part in source.relative_to(folder).parts[:-1]):
                continue
            rows = all_section_value_maps_preserve(source.read_bytes().decode('latin-1').splitlines())
            if any(rows.get(name) for name in ('Triggers', 'TeamTypes', 'AITriggerTypes', 'Houses')):
                continue
            starts = [i for i in range(8) if str(i) in rows.get('Waypoints', {})]
            if len(starts) < 2 or starts != list(range(len(starts))):
                continue
            label = str(source.relative_to(root))
            result[label] = {'path': str(source), 'name': rows.get('Basic', {}).get('Name', source.stem), 'starts': starts}
    return result


def _serialize(sections):
    return '\r\n'.join(line for section, values in sections.items()
                       for line in (f'[{section}]', *(f'{key}={value}' for key, value in values.items() if value is not None), ''))


def prepare_game(root, definition, rewards, settings, *, country, color, opponents,
                 difficulty, seed, game_speed, randomize_access):
    root = Path(root)
    source = Path(definition['path']).resolve()
    if root.resolve() not in source.parents:
        raise ValueError('Skirmish map must belong to this installation.')
    if country not in playable_countries().values() or color not in multiplayer_colors(root).values():
        raise ValueError('Choose an installed faction and color.')
    if type(opponents) is not int or opponents != 1:
        raise ValueError('Progression Skirmish requires exactly one enemy AI.')
    if len(definition['starts']) < 2:
        raise ValueError('Skirmish map requires two start positions.')
    rows = all_section_value_maps_preserve(source.read_bytes().decode('latin-1').splitlines())
    if any(rows.get(name) for name in ('Triggers', 'TeamTypes', 'AITriggerTypes', 'Houses')):
        raise ValueError('Progression Skirmish requires an unscripted multiplayer map.')
    if GAME == 'dta':
        from randomizer.coop.catalogue import inherited_sections
        rows = inherited_sections(root, source)
        rows.pop('INISystem', None)
        rows, side = _dta_rewards(root, rows, rewards, settings, country, randomize_access,
                                 str(source.relative_to(root.resolve())))
    else:
        rows, side = _ra2_rewards(rows, rewards, settings, country, randomize_access)
    rows.setdefault('Basic', {}).update(Name=definition['name'], MultiplayerOnly='yes', IgnoreGlobalAITriggers='no')
    rows['Basic'].pop('Player', None)
    data = _serialize(rows)
    game_id = random.SystemRandom().randrange(1, 2**31 - 1)
    rank = ('Easy', 'Normal', 'Hard').index(difficulty)
    values = {'Scenario': 'spawnmap.ini', 'Name': 'Commander', 'Host': 'Yes',
              'IsSinglePlayer': 'No', 'PlayerCount': '1', 'AIPlayers': str(opponents),
              'Side': str(side), 'Color': str(color), 'Seed': str(game_id), 'GameID': str(game_id),
              'GameSpeed': str(game_speed), 'ShortGame': 'No', 'AutoSurrender': 'No',
              'TechLevel': '7' if GAME == 'dta' else '10', 'Bases': 'Yes',
              'UnitCount': '0', 'Credits': '10000', 'Crates': 'No', 'MCVRedeploy': 'Yes',
              'FogOfWar': 'No', 'MultiEngineer': 'Yes', 'BuildOffAlly': 'No',
              'Protocol': '0' if GAME == 'dta' else '2',
              'FrameSendRate': '1' if GAME == 'dta' else '7',
              'UIGameMode': 'Progression Skirmish', 'UIMapName': definition['name'],
              'MapHash' if GAME == 'dta' else 'MapSHA1': hashlib.sha1(data.encode('latin-1')).hexdigest()}
    if GAME == 'dta':
        values.update(Firestorm='Yes', CoachMode='Yes', WriteStatistics='Yes', AIDifficulty=str(2 - rank), LoadSaveGame='No', AutoSaveGame='0')
    native_countries = tuple(playable_countries().values())
    rng = random.Random(f'{seed}:skirmish:{source.name}')
    palette = [value for value in multiplayer_colors(root).values() if value != color]
    if len(palette) < opponents:
        raise ValueError('Not enough distinct multiplayer colors.')
    spawn = {'Settings': values, 'SpawnLocations': {'Multi1': '0'}, 'HouseCountries': {}, 'HouseColors': {}, 'HouseHandicaps': {}}
    for index in range(opponents):
        house = f'Multi{index + 2}'
        enemy = rng.choice(native_countries)
        spawn['SpawnLocations'][house] = str(index + 1)
        indices = {value: index for index, value in enumerate(rows.get('Countries', {}).values())}
        spawn['HouseCountries'][house] = str(indices[enemy] if GAME != 'dta' else native_countries.index(enemy))
        spawn['HouseColors'][house] = str(palette[index])
        spawn['HouseHandicaps'][house] = str(2 - rank)
    atomic_write_text(root / 'spawnmap.ini', data, encoding='latin-1')
    atomic_write_text(root / 'spawn.ini', _serialize(spawn), encoding='latin-1')


def preload_player_country(root):
    """Register private multiplayer countries before the spawner creates houses."""
    from randomizer.core.paths import CAMEO_CACHE_DIR

    root = Path(root)
    rows = all_section_value_maps_preserve(
        (root / 'spawnmap.ini').read_bytes().decode('latin-1').splitlines())
    countries = rows.get('Countries', {})
    if 'RZPLAYER' not in countries.values() or 'RZPLAYER' not in rows:
        raise ValueError('Generated Skirmish has no private player country.')
    target = root / 'rulesmo.ini'
    marker = '; Generated by Mental Omega Randomizer Launcher'
    if target.exists() and not target.read_text(
            encoding='utf-8', errors='ignore').startswith(marker):
        raise ValueError('Cannot replace an existing custom rulesmo.ini for Skirmish.')
    source = target if target.is_file() else CAMEO_CACHE_DIR / 'rulesmo.ini'
    lines = IniLines(source.read_text(encoding='utf-8', errors='ignore').splitlines())
    changes = {'Countries': countries}
    changes.update({name: rows[name] for name in countries.values() if name in rows})
    merge_ini_section_values(lines, changes)
    atomic_write_text(target, marker + ' Skirmish country preload\r\n' +
                      '\r\n'.join(lines).encode('cp1252', errors='replace').decode('latin-1') + '\r\n',
                      encoding='latin-1')


def _dta_rewards(root, rows, rewards, settings, country, randomized, scenario):
    from randomizer.coop.production import player_production_rules
    from randomizer.dta.rules import PLAYABLE_FACTIONS, installed_effective_sections
    from randomizer.dta.powers import player_power_rules, ensure_power_runtime_types
    mission = {'code': '__SKIRMISH__', 'scenario': scenario, 'side': country,
               'coop_player_count': 1, 'coop_side': PLAYABLE_FACTIONS.index(country),
               'coop_allies': [], 'coop_enemies': [], 'required_addon': False}
    starter_access = set(settings.get('_skirmish_access', ()))
    if not starter_access:
        synthetic = deepcopy(rows)
        synthetic.update(Houses={'0': country}, **{country: {'PlayerControl': 'yes'}})
        synthetic.setdefault('Basic', {})['Player'] = country
        starter_access.update(_starter_rules(IniLines(_serialize(synthetic).splitlines()), settings))
    rewards = list(rewards) + [{'unit': unit, 'dta_production_access': True} for unit in sorted(starter_access)]
    # Existing adapter allocates an unused, engine-registered HouseType mask.
    sides, report = player_production_rules(root, mission, rows, [{
        'rewards': rewards, 'settings': settings, 'randomize_access': randomized, 'credit_bonus': 0}])
    installed = installed_effective_sections(False)
    house = installed['Houses'][str(sides[0])]
    context = {'player_house': 'Spawn1', 'production_house': house, 'acts_like': sides[0],
               'original_production_house': country, 'shared_hostile_houses': []}
    routes = {entry['unit']: entry['output_type'] for entry in report['applied']}
    rules, actions, power_report = player_power_rules(
        mission, rewards, reserved_rules=rows, production_context=context,
        scenario_sections=rows, installed_sections=installed, player_house_heap_id=0,
        paradrop_unit_routes=routes)
    for section, values in rules.items():
        rows.setdefault(section, {}).update(values)
    if power_report['skipped']:
        raise ValueError('Cannot apply Skirmish powers: ' + str(power_report['skipped']))
    if actions:
        _startup_trigger(rows, house, actions, 'RZPOWERS')
    from randomizer.dta.powers import ensure_power_action_types
    ensure_power_action_types()
    ensure_power_runtime_types(power_report.pop('_runtime_rules'), power_report.pop('_runtime_art'))
    from randomizer.rewards.display import starting_credit_bonus
    bonus = starting_credit_bonus(rewards) + int(settings.get('shop_mission_starting_credits_flat', 0))
    if bonus:
        _startup_trigger(rows, 'Neutral', [['106', '0', '50', str(max(-10000, bonus)), '0', '0', '0', 'A']], 'RZCREDITS')
    from randomizer.dta.maps import preserve_collateral_damage_coefficients
    from randomizer.coop.maps import validate_scripting
    lines = IniLines(_serialize(rows).splitlines())
    preserve_collateral_damage_coefficients(lines)
    validate_scripting(root, lines)
    return all_section_value_maps_preserve(lines), sides[0]


def _ra2_rewards(rows, rewards, settings, country, randomized):
    from randomizer.ui.cameos import installed_rules_registry
    from randomizer.maps.player_clones import player_unit_clone_rules, player_clone_pad_aircraft_rules
    from randomizer.maps.power_buffs import apply_power_buffs_to_unlock_rewards
    from randomizer.maps.base import cloned_superweapon_plan
    from randomizer.rewards.catalogue import BUFF_TARGETS, ALWAYS_AVAILABLE_TECH_IDS, canonical_rewards
    from randomizer.rewards.rules import unlocked_reward_tech_ids
    installed_types, installed = installed_rules_registry(synchronous=True)
    countries = dict(installed['Countries'])
    countries.update(rows.get('Countries', {}))
    if 'RZPLAYER' in countries.values():
        raise ValueError('Source map already reserves the progression player country.')
    side = len(dict.fromkeys(countries.values()))
    next_key = max((int(key) for key in countries if key.isdigit()), default=-1) + 1
    countries[str(next_key)] = 'RZPLAYER'
    rows['Countries'] = countries
    rows['RZPLAYER'] = dict(installed[country], Name='Progression Commander', ParentCountry=country, Multiplay='no')
    unlocked = set(unlocked_reward_tech_ids(rewards))
    unlocked.update(settings.get('_skirmish_access', ()))
    if not randomized:
        unlocked.update(unit for unit, target in BUFF_TARGETS.items()
                        if not target.get('power_payload_only') and not target.get('runtime_transform')
                        and _eligible(installed.get(unit, {}), country))
    unlocked.update(unit for unit in ALWAYS_AVAILABLE_TECH_IDS if _eligible(installed.get(unit, {}), country))
    # Native production remains available to AI, including enemies of the same faction.
    for category in ('InfantryTypes', 'VehicleTypes', 'AircraftTypes', 'BuildingTypes'):
        for unit in installed.get(category, {}).values():
            base = installed.get(unit, {})
            changes = rows.setdefault(unit, {})
            for key in ('Owner', 'RequiredHouses', 'ForbiddenHouses'):
                native = [part.strip() for part in base.get(key, '').split(',') if part.strip()]
                if country in native:
                    changes[key] = ','.join(dict.fromkeys([*native, 'RZPLAYER']))
            target = BUFF_TARGETS.get(unit, {})
            if target and unit not in ALWAYS_AVAILABLE_TECH_IDS and not target.get('power_payload_only'):
                forbidden = changes.get('ForbiddenHouses', base.get('ForbiddenHouses', ''))
                changes['ForbiddenHouses'] = ','.join(dict.fromkeys([*filter(None, forbidden.split(',')), 'RZPLAYER']))
    overlays = {}
    for reward in canonical_rewards(rewards):
        if reward.get('kind') == 'buff':
            continue
        for unit, values in reward.get('rules', {}).items():
            if unit in BUFF_TARGETS:
                overlays.setdefault(unit, {}).update(values)
    for unit in unlocked:
        overlays.setdefault(unit, {}).update(TechLevel='1', Owner='RZPLAYER', RequiredHouses='RZPLAYER', ForbiddenHouses='none')
    # Campaign clone code receives a temporary House record for ownership analysis.
    rows['Houses'] = {'0': 'RZPLAYER House'}
    rows['RZPLAYER House'] = {'Country': 'RZPLAYER', 'PlayerControl': 'yes'}
    rows.setdefault('Basic', {})['Player'] = 'RZPLAYER House'
    lines = IniLines(_serialize(rows).splitlines())
    from randomizer.missions.tier_one import chaos_earned_access_rules
    from randomizer.missions.access import mission_basic_unit_rules, CHAOS_PRIMARY_PRODUCTION
    chaos = settings.get('_skirmish_reward_mode') == 'Chaos'
    planning = all_section_value_maps_preserve(lines)
    planning = deepcopy(planning)
    planning['RZPLAYER']['ParentCountry'] = country
    virtual = planning.setdefault('Structures', {})
    next_structure = max((int(key) for key in virtual if key.isdigit()), default=-1) + 1
    for factories in CHAOS_PRIMARY_PRODUCTION.values():
        for factory in factories.values():
            if factory not in installed:
                continue
            virtual[str(next_structure)] = f'RZPLAYER House,{factory},256,1,1,64,None,1,0,1,0,0,None,None,None,0,0'
            next_structure += 1
    planning_lines = IniLines(_serialize(planning).splitlines())
    planned = (chaos_earned_access_rules(planning_lines, list(rewards)) if chaos
               else mission_basic_unit_rules(planning_lines, earned_access_ids=unlocked,
                                             translate_equivalents=False))
    starters = _starter_rules(planning_lines, settings)
    unlocked.update(starters)
    for unit in unlocked:
        overlays.setdefault(unit, {}).update(planned.get(unit, {}))
        overlays[unit].update(starters.get(unit, {}))
        overlays[unit].update(TechLevel='1', Owner='RZPLAYER', RequiredHouses='RZPLAYER', ForbiddenHouses='none')
    powers = apply_power_buffs_to_unlock_rewards(list(rewards), installed)
    payload = set()
    for reward in powers:
        if reward.get('kind') != 'superweapon':
            continue
        for key in ('Deliver.Types', 'ParaDrop.Types', 'DropPod.Types'):
            value = reward.get('superweapon_rules', {}).get(key, installed.get(reward.get('superweapon'), {}).get(key, ''))
            payload.update(part.strip().upper() for part in value.split(',') if part.strip().upper() in BUFF_TARGETS)
    if GAME == 'mo':
        from randomizer.maps.power_buffs import equivalent_payload_unit_buff_rewards
        from randomizer.challenges.catalogue import SIDE_COUNTRIES, SIDE_FAMILIES
        faction = {'allies': 'Allies', 'soviets': 'Soviets', 'epsilon': 'Epsilon', 'foehn': 'Foehn'}[SIDE_FAMILIES[SIDE_COUNTRIES.index(country)]]
        rewards = equivalent_payload_unit_buff_rewards(list(rewards),
            [r['superweapon'] for r in powers if r.get('kind') == 'superweapon'], unlocked, faction)
    from randomizer.rewards.rules import buffs_with_unlocked_access, expand_equivalent_role_buffs
    # Role sharing must stop at this launch's roster. Expanding inside the
    # clone builder also visits locked peers (for example a Magnetron's Scud
    # peer), creating unsupported missile clones for units the player lacks.
    rewards = buffs_with_unlocked_access(
        expand_equivalent_role_buffs(
            canonical_rewards(rewards),
            enabled=bool(settings.get('_skirmish_share_buffs', False)),
            allowed_unit_ids=unlocked | payload,
        ),
        additional_unlocked_tech_ids=unlocked | payload,
    )
    kwargs = {}
    if GAME == 'mo':
        from randomizer.rewards.roster import randomizer_unit_roster, installed_rules_template_overlay
        _, clone_ids, templates = randomizer_unit_roster()
        templates, _ = installed_rules_template_overlay(templates, installed)
        kwargs.update(owned_clone_ids=clone_ids, owned_clone_templates=templates)
    changes, _, handled, _, warnings = player_unit_clone_rules(
        lines, list(rewards), installed, require_unlocked_access=randomized,
        additional_unlocked_tech_ids=unlocked | payload, buildable_tech_ids=unlocked,
        build_owner_ids=('RZPLAYER',), forced_buildable_clone_ids=unlocked,
        forced_isolated_clone_ids=payload, forced_compact_clone_ids=payload,
        share_basic_equivalent_buffs=False,
        unit_specific_mode=True, owned_clone_rule_overlays=overlays, **kwargs)
    if warnings:
        raise ValueError('Cannot apply Skirmish rewards: ' + '; '.join(map(str, warnings)))
    from randomizer.maps.shop_modifiers import apply_shop_clone_modifiers, apply_shop_clone_restrictions
    apply_shop_clone_modifiers(changes, handled, settings)
    apply_shop_clone_restrictions(changes, handled, installed, settings)
    from randomizer.maps.shop_modifiers import apply_shop_global_modifiers
    apply_shop_global_modifiers(changes, lines, installed, settings)
    # Native starting-MCV and harvester selectors compare exact type IDs.
    # Include private player types before hiding the corresponding originals.
    for field in ('BaseUnit', 'HarvesterUnit'):
        native = [part.strip() for part in installed.get('General', {}).get(field, '').split(',') if part.strip()]
        additions = [handled[unit]['clone_id'] for unit in native
                     if handled.get(unit, {}).get('clone_id')]
        if additions:
            changes.setdefault('General', {})[field] = ','.join(dict.fromkeys([*native, *additions]))
    merge_ini_section_values(lines, changes)
    pad_rules, _ = player_clone_pad_aircraft_rules(lines, installed, handled)
    merge_ini_section_values(lines, pad_rules)
    if GAME == 'mo':
        from randomizer.coop.native_buildings import preserve_native_building_abilities
        from randomizer.maps.buff_values import _register_map_type
        native_changes = {}
        def register(category, alias):
            _register_map_type(native_changes, lines, installed, category, alias)
        current = all_section_value_maps_preserve(lines)
        buildings = {unit: alias for unit, alias in aliases_from_handled(handled).items()
                     if BUFF_TARGETS.get(unit, {}).get('category') in ('defenses', 'special_buildings')}
        # The native-power adapter edits each clone's existing definition.
        # Those definitions were already merged into the map above.
        native_changes.update({alias: dict(current[alias]) for alias in buildings.values()})
        preserve_native_building_abilities(native_changes, buildings, installed,
            current, 'RZPLAYER', 'SK', register, techno_clones=aliases_from_handled(handled))
        merge_ini_section_values(lines, native_changes)
        from randomizer.maps.special_buildings import reprocessor_bounty_rules
        bounty, _ = reprocessor_bounty_rules(lines, installed, handled, unlocked)
        merge_ini_section_values(lines, bounty)
    rules, actions, _, startup, static, missing = cloned_superweapon_plan(
        lines, powers, installed_types, installed,
        superweapon_required_houses=('RZPLAYER',), force_required_houses=True)
    if missing:
        raise ValueError('Missing Skirmish power definitions: ' + ', '.join(missing))
    merge_ini_section_values(lines, rules)
    # Point delivered troops at the same buffed clones used in production.
    aliases = {unit: detail['clone_id'] for unit, detail in handled.items() if detail.get('clone_id')}
    for section, values in rules.items():
        for key in ('Deliver.Types', 'ParaDrop.Types', 'DropPod.Types'):
            if key in values:
                merge_ini_section_values(lines, {section: {key: ','.join(aliases.get(part.strip().upper(), part.strip()) for part in values[key].split(','))}})
    providers = [*startup, *static]
    from randomizer.rewards.display import starting_credit_bonus
    bonus = starting_credit_bonus(list(rewards)) + int(settings.get('shop_mission_starting_credits_flat', 0))
    if bonus:
        merge_ini_section_values(lines, {
            'BuildingTypes': {'990001': 'RZCREDITS'},
            'RZCREDITS': dict(_hidden_provider(), ProduceCashStartup=str(max(-10000, bonus)))})
        providers.append('RZCREDITS')
    if actions or providers:
        _power_providers(lines, installed_types, installed, actions, providers)
    rows = all_section_value_maps_preserve(lines)
    rows.pop('Houses', None)
    rows.pop('RZPLAYER House', None)
    return rows, side


def _eligible(row, country):
    parts = lambda field: {part.strip() for part in row.get(field, '').split(',') if part.strip()}
    return country in parts('Owner') and (not parts('RequiredHouses') or country in parts('RequiredHouses')) and country not in parts('ForbiddenHouses')


def _power_providers(lines, installed_types, installed, actions, providers):
    """Reuse the same native player-at-location transfer used by Fortress."""
    from randomizer.maps.ini import section_value_map_preserve, append_section_entry
    from randomizer.maps.hooks import unique_section_key
    runtime = list(installed_types)
    runtime.extend(kind for kind in section_value_map_preserve(lines, 'SuperWeaponTypes').values() if kind not in runtime)
    changes = {}
    buildings = section_value_map_preserve(lines, 'BuildingTypes')
    index = max([int(key) for key in (*installed.get('BuildingTypes', {}), *buildings) if key.isdigit()], default=0) + 1
    for number, action in enumerate(actions):
        if str(action[0]) != '34':
            raise ValueError('Unsupported Skirmish power grant action.')
        alias = f'RZPOWER{number}'
        changes[alias] = dict(_hidden_provider(), SuperWeapon=runtime[int(action[2])])
        changes.setdefault('BuildingTypes', {})[str(index)] = alias
        index += 1
        providers.append(alias)
    merge_ini_section_values(lines, changes)
    trigger = unique_section_key(lines, ('Events', 'Actions', 'Triggers'), 'RZPOWER')
    tag = unique_section_key(lines, ('Tags',), 'RZPOWER')
    append_section_entry(lines, 'Events', trigger, '1,13,0,0')
    append_section_entry(lines, 'Actions', trigger, '1,14,0,4475,0,0,0,0,A')
    append_section_entry(lines, 'Triggers', trigger, 'Neutral,<none>,Progression powers,0,1,1,1,0')
    append_section_entry(lines, 'Tags', tag, f'0,Progression powers,{trigger}')
    cells = section_value_map_preserve(lines, 'Waypoints')
    cell = int(cells['0'])
    x, y = cell % 1000, cell // 1000
    existing = section_value_map_preserve(lines, 'Structures')
    index = max((int(key) for key in existing if key.isdigit()), default=-1) + 1
    for offset, provider in enumerate(dict.fromkeys(providers)):
        # Providers are invisible/passable; share the start cell without blocking MCV deployment.
        append_section_entry(lines, 'Structures', str(index + offset),
            f'Neutral,{provider},256,{x},{y},64,{tag},1,0,1,0,0,None,None,None,0,0')


def _hidden_provider():
    return {'Image': 'GALITE', 'Name': 'Progression provider',
            'Strength': '100', 'Armor': 'concrete', 'TechLevel': '-1', 'BuildLimit': '0',
            'Owner': 'RZPLAYER', 'Power': '0', 'Powered': 'no', 'Capturable': 'no',
            'Selectable': 'no', 'Unsellable': 'yes', 'Insignificant': 'yes',
            'InvisibleInGame': 'yes', 'IsPassable': 'yes', 'LegalTarget': 'no',
            'KeepAlive': 'no', 'DontScore': 'yes', 'Immune': 'yes'}


def _startup_trigger(rows, owner, actions, key):
    # Keep each native action record below the engine's fixed INI buffer.
    for offset in range(0, len(actions), 8):
        chunk = actions[offset:offset + 8]
        identity = f'{key}{offset // 8}'
        rows.setdefault('Events', {})[identity] = '1,13,0,0'
        rows.setdefault('Actions', {})[identity] = str(len(chunk)) + ',' + ','.join(str(value) for action in chunk for value in action)
        rows.setdefault('Triggers', {})[identity] = f'{owner},<none>,Progression startup,0,1,1,1,0'
        rows.setdefault('Tags', {})[identity] = f'0,Progression startup,{identity}'


def _starter_rules(lines, settings):
    from randomizer.missions.tier_one import starting_tier_one_rules, starting_tier_one_defense_rules
    result = {}
    for adapter, key in ((starting_tier_one_rules, '_skirmish_starter_units'),
                         (starting_tier_one_defense_rules, '_skirmish_starter_defenses')):
        for unit, values in adapter(lines, settings.get(key, ()),
                chaos_mode=settings.get('_skirmish_reward_mode') == 'Chaos',
                allow_player_family_fallback=True,
                excluded_unit_ids=settings.get('excluded_unit_access_ids', ())).items():
            if any(name.lower() == 'techlevel' and int(value) >= 0 for name, value in values.items()):
                result.setdefault(unit, {}).update(values)
    return result


def aliases_from_handled(handled):
    return {unit: details['clone_id'] for unit, details in handled.items() if details.get('clone_id')}
