"""Build shared, map-local co-op unit rewards for a private LAN test.

The prototype deliberately edits a new copy of an installed co-op map. The
original map and official MIX files remain untouched. Both players install
the same generated map and lobby entry before opening the LAN client.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from randomizer.coop.compatibility import FINGERPRINT_POLICY, resolve_path, text_hash
from randomizer.maps.ini import (
    IniLines, all_section_value_maps, find_section_bounds,
    merge_ini_section_values,
)
from randomizer.missions.access import CHAOS_PRIMARY_PRODUCTION
from randomizer.coop.reward_map import (
    apply_coop_power_rewards, apply_coop_rewards, apply_shop_credit_bonus,
)
from randomizer.coop.enemy_rewards import apply_coop_enemy_rewards
from randomizer.coop.access import apply_coop_native_production_gate, coop_starting_rewards
from randomizer.coop.archipelago import received_rewards
from randomizer.coop.victory import inject_victory_markers
from randomizer.maps.buff_values import _active_direct_buff_counts
from randomizer.rewards.arsenal import ARSENAL_MODE, arsenal_launch_rewards, arsenal_unit_type
from randomizer.rewards.catalogue import BUFF_TARGETS, buff_stack_limit, canonical_reward, check_rewards
from randomizer.rewards.display import starting_credit_bonus
from randomizer.rewards.enemy_scaling import (
    configured_enemy_reward, normalize_enemy_scaling_settings,
)
from randomizer.rewards.rules import tech_ids_for_rewards
from randomizer.rewards.roster import randomizer_unit_roster
from randomizer.shop.modifiers import (
    PRODUCTION_RESTRICTIONS, modifier_effects, stage_production_restrictions,
)
from randomizer.shop.config import SHOP_CONFIG
from randomizer.shop.mission_modifiers import shop_enemy_scaling_entries
from randomizer.ui.cameos import installed_rules_registry


PROTOTYPE_MARKER = 'MOR_COOP_PROTOTYPE_V10'
SHOP_MARKER = 'MOR_COOP_SHOP_V4'
SUPPORTED_PROGRESSION = {'Classic', 'Grid Mode', 'Mission List'}
SIDE_COUNTRIES = (
    'UnitedStates', 'Europeans', 'Pacific',
    'USSR', 'Latin', 'Chinese',
    'PsiCorps', 'ScorpionCell', 'Headquaters',
    'Guild1', 'Guild2', 'Guild3',
)
SIDE_FAMILIES = ('allies',) * 3 + ('soviets',) * 3 + ('epsilon',) * 3 + ('foehn',) * 3


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _text(path: Path) -> str:
    # Map files can contain legacy 8-bit text. Latin-1 round-trips every byte.
    return path.read_bytes().decode('latin-1')


def _section(lines: list[str], name: str) -> list[str]:
    start, end = find_section_bounds(lines, name)
    if start is None:
        raise ValueError(f'Missing [{name}] section.')
    return list(lines[start + 1:end])


def _values(lines: list[str], name: str) -> dict[str, str]:
    return {
        key.strip().lower(): value.strip().split(';', 1)[0].strip()
        for line in _section(lines, name)
        if '=' in line
        for key, value in [line.split('=', 1)]
    }


def _map_config(game_root: Path, coop_name: str):
    if not re.fullmatch(r'coop_[a-z0-9_]+', coop_name, re.I):
        raise ValueError('Co-op map must be an installed coop_*.map name.')
    source = resolve_path(game_root, f'MapsMO/Cooperative/{coop_name.lower()}.map')
    if not source.is_file():
        raise FileNotFoundError(source)
    catalogue = resolve_path(game_root, 'INI/MentalOmegaMaps.ini')
    lines = _text(catalogue).splitlines()
    source_key = f'MapsMO\\Cooperative\\{coop_name.lower()}'
    metadata = _values(lines, source_key)
    if metadata.get('iscoopmission', '').lower() != 'true':
        raise ValueError('Selected map is not registered as a co-op mission.')
    if metadata.get('minplayers') != '2' or metadata.get('maxplayers') != '2':
        raise ValueError('Prototype requires a registered two-player co-op map.')
    denied = {
        int(value.strip())
        for value in metadata.get('disallowedplayersides', '').split(',')
        if value.strip().isdigit()
    }
    available = sorted(set(range(9)) - denied)
    if len(available) != 1:
        raise ValueError('Prototype requires one fixed Allied, Soviet, or Epsilon player side.')
    side = available[0]
    if any(
        value.split(',', 1)[0].strip() == str(side)
        for key, value in metadata.items()
        if key.startswith('enemyhouse')
    ):
        raise ValueError('Enemy uses player country; shared native rule could change enemy production.')
    return source, source_key, metadata, SIDE_COUNTRIES[side], SIDE_FAMILIES[side]


def _earned_rewards(state: dict) -> list[dict]:
    received = received_rewards(state)
    if received is not None:
        return [reward for reward in received if not reward.get('enemy_reward')]
    earned = list(state.get('starting_rewards') or [])
    checks_by_code = state.get('mission_checks') or {}
    for code in state.get('mission_order') or []:
        for check in checks_by_code.get(code, ()):
            if check.get('unlocked') or check.get('released'):
                earned.extend(check_rewards(check))
    return [
        canonical_reward(reward)
        for reward in earned
        if isinstance(reward, dict) and not reward.get('enemy_reward')
    ]


def _access_candidates(state: dict, source_mission: str = '',
                       country: str = '') -> list[tuple[str, dict]]:
    rewards = _launch_rewards(state, source_mission, country)
    candidates = []
    for reward in rewards:
        if reward.get('kind') in {'buff', 'superweapon', 'message', 'retired'}:
            continue
        for unit_id in sorted(tech_ids_for_rewards([reward])):
            if arsenal_unit_type(unit_id, BUFF_TARGETS.get(unit_id)):
                candidates.append((unit_id, reward))
    return candidates


def _building_ids(rewards: list[dict]) -> list[str]:
    return sorted({
        unit_id
        for reward in rewards
        if reward.get('kind') not in {'buff', 'superweapon', 'message', 'retired'}
        for unit_id in tech_ids_for_rewards([reward])
        if BUFF_TARGETS.get(unit_id, {}).get('category') in {
            'defenses', 'special_buildings',
        }
    })


def _power_reward_ids(rewards: list[dict]) -> list[str]:
    return sorted(
        str(reward['name'])
        for reward in rewards
        if reward.get('name') and (
            reward.get('kind') == 'superweapon'
            or reward.get('kind') == 'buff' and reward.get('power_buff_type')
        )
    )


def _enemy_countries(metadata: dict) -> list[str]:
    return sorted({
        SIDE_COUNTRIES[int(value.split(',', 1)[0].strip())]
        for key, value in metadata.items() if key.startswith('enemyhouse')
    })


def _grid_enemy_reward_ids(state: dict) -> list[str]:
    received = received_rewards(state)
    checks = {
        (str(code), str(check.get('id'))): check
        for code in state.get('mission_order', ())
        for check in (state.get('mission_checks') or {}).get(code, ())
        if isinstance(check, dict) and check.get('id')
    }
    settings = normalize_enemy_scaling_settings(
        (state.get('reward_settings') or {}).get('enemy_scaling')
    )
    rewards = []
    counts = Counter()
    entries = (state.get('enemy_reward_plan', ()) if received is None else
               [{'reward': reward} for reward in received if reward.get('enemy_reward')])
    for entry in entries:
        if len(rewards) >= settings['maximum_total_buffs']:
            break
        if not isinstance(entry, dict):
            continue
        check = checks.get((str(entry.get('mission')), str(entry.get('check_id'))))
        if received is None and (not check or not (check.get('unlocked') or check.get('released'))):
            continue
        reward = configured_enemy_reward(
            canonical_reward(entry.get('reward') or {}), settings or {}
        )
        if reward and reward.get('enemy_reward'):
            effect_id = str(reward.get('enemy_effect_id') or '')
            if counts[effect_id] >= int(reward.get('enemy_maximum', 1)):
                continue
            counts[effect_id] += 1
            rewards.append(str(reward['name']))
    return sorted(rewards)


def _shared_shop_enemy_reward_ids(loadouts: dict) -> list[str]:
    counts = Counter()
    for loadout in loadouts.values():
        counts |= Counter(loadout.get('enemy_reward_ids', ()))
    return sorted(name for name, count in counts.items() for _ in range(count))


def _launch_rewards(state: dict, source_mission: str = '', country: str = '') -> list[dict]:
    earned = _earned_rewards(state)
    if state.get('reward_mode') == ARSENAL_MODE:
        if not source_mission:
            raise ValueError('Randomizer Arsenal requires --source-mission CODE.')
        arsenal = (state.get('mission_arsenals') or {}).get(source_mission.upper())
        if not arsenal:
            raise ValueError(f'No saved arsenal for {source_mission.upper()}.')
        return arsenal_launch_rewards(arsenal, earned)
    return earned + coop_starting_rewards(state, country)


def _buff_counts(rewards: list[dict], access_ids: list[str],
                 building_ids=()) -> dict:
    earned_ids = sorted(set(access_ids) | set(building_ids))
    counts = _active_direct_buff_counts(
        rewards, additional_unlocked_tech_ids=earned_ids,
        unit_specific_mode=True, global_production_unit_ids=earned_ids,
    )
    selected = {unit_id: dict(counts.get(unit_id, {})) for unit_id in earned_ids}
    for reward in rewards:
        if reward.get('kind') != 'buff' or reward.get('buff_type') != 'veteran':
            continue
        unit_id = str(reward.get('unit') or '').upper()
        if unit_id not in selected:
            continue
        buff = selected[unit_id]
        buff['veteran'] = buff.get('veteran', 0) + 1
        limit = buff_stack_limit(reward)
        if limit is not None:
            buff['veteran'] = min(buff['veteran'], limit)
    return {unit_id: values for unit_id, values in selected.items() if values}


def _selected_reward(state: dict, source_mission: str, unit_id: str,
                     allow_test_unit: bool = False, country: str = ''):
    candidates = _access_candidates(state, source_mission, country)
    if unit_id:
        selected = next((entry for entry in candidates if entry[0] == unit_id.upper()), None)
        if selected is None:
            if not allow_test_unit:
                raise ValueError(f'{unit_id.upper()} is not available from saved run rewards or arsenal.')
            return unit_id.upper(), {'name': f'{unit_id.upper()} test access'}, True
        return *selected, False
    if not candidates:
        if allow_test_unit:
            return 'FV', {'name': 'FV test access'}, True
        return '', {'name': 'No unit production access'}, False
    return *candidates[0], False


def _registered_unit_types(source: Path) -> frozenset[str]:
    """Index this installed map once per launch/replay, rather than per reward."""
    _powers, installed = installed_rules_registry(synchronous=True)
    map_sections = all_section_value_maps(_text(source).splitlines())
    registered = set()
    for sections in (installed, map_sections):
        names = {str(name).lower(): name for name in sections}
        registered.update(
            str(value).upper()
            for category in ('InfantryTypes', 'VehicleTypes', 'AircraftTypes')
            for value in sections.get(names.get(category.lower()), {}).values()
            if str(value).lower() in names
        )
    _, clone_ids, templates = randomizer_unit_roster()
    registered.update(unit_id for unit_id in clone_ids if templates.get(unit_id))
    return frozenset(registered)


def _require_registered_type(source: Path, unit_id: str, registered_types=None) -> None:
    """Reject map-only rewards absent from this co-op map's type registry."""
    if registered_types is None:
        registered_types = _registered_unit_types(source)
    if unit_id.upper() in registered_types:
        return
    raise ValueError(
        f'{unit_id} is absent from installed and co-op map type lists; '
        'choose another unit for the prototype.'
    )


def available_units(state: dict, source_mission: str = '') -> list[tuple[str, str]]:
    """Show access candidates available from a saved run or mission arsenal."""
    unique = {}
    for unit_id, reward in _access_candidates(state, source_mission):
        unique.setdefault(unit_id, reward.get('name', unit_id))
    return sorted(unique.items())


def _apply_enemy_powerhouse_waves(lines, source, manifest, metadata):
    """Resolve authored multiplayer enemy slots before expanding their waves."""
    rewards = [canonical_reward({'name': name})
               for name in manifest.get('enemy_reward_ids', ())]
    if not any(reward.get('enemy_effect') == 'powerhouse' for reward in rewards):
        return
    from randomizer.coop.catalogue import COOP_BUILD_CLASSIFICATIONS
    from randomizer.maps.enemy_powerhouses import enemy_powerhouse_rules
    from randomizer.maps.houses import map_house_records

    if (manifest.get('mission_category') != 'challenge'
            and COOP_BUILD_CLASSIFICATIONS.get(source.stem.upper()) != 'base_build'):
        return
    players = {manifest['player_country'], manifest.get('guest_country', '')}
    ai_teammate = manifest.get('ai_teammate')
    if ai_teammate:
        players.add(ai_teammate['country'])
    enemies = set(manifest.get('enemy_countries', ()))
    records = map_house_records(lines)
    hostile_houses = []
    countries = (manifest['player_country'],
                 manifest.get('guest_country', manifest['player_country']))
    if manifest.get('player_count', 2) == 2 and 'player_colors' in manifest:
        countries = tuple(country for _color, country in sorted(zip(
            manifest['player_colors'], countries,
        )))
    for slot, country in enumerate(countries[:manifest.get('player_count', 2)]):
        house = f'<Player @ {chr(ord("A") + slot)}>'
        records[house] = {'name': house, 'country': country, 'player': True}
        records[country] = {'name': country, 'country': country, 'player': True}
    if ai_teammate:
        house = '<Player @ B>'
        country = ai_teammate['country']
        records[house] = {'name': house, 'country': country, 'player': True}
        records[country] = {'name': country, 'country': country, 'player': True}
    for key, value in metadata.items():
        if not key.startswith('enemyhouse'):
            continue
        country_index, _color, slot = map(int, value.split(','))
        country = SIDE_COUNTRIES[country_index]
        if slot < 2 or slot > 7 or country in players or country not in enemies:
            continue
        house = f'<Player @ {chr(ord("A") + slot)}>'
        records[house] = {'name': house, 'country': country}
        records[country] = {'name': country, 'country': country}
        hostile_houses.extend((house, country))
    _types, installed = installed_rules_registry(synchronous=True)
    rules, _applications, _skips = enemy_powerhouse_rules(
        lines, hostile_houses, rewards, installed, house_records=records,
        stage=manifest.get('shop_stage', 1), difficulty=manifest.get('difficulty', 1),
        seed=manifest['seed'],
        player_countries=sorted(players - {''}),
    )
    if rules:
        merge_ini_section_values(lines, rules)


def _map_bytes(source: Path, source_key: str, manifest: dict, family: str,
               metadata: dict) -> bytes:
    raw = source.read_bytes()
    policy = manifest.get('fingerprint_policy')
    if policy not in (None, FINGERPRINT_POLICY):
        raise ValueError('Co-op map compatibility check differs. Update both launchers.')
    source_hash = text_hash(raw) if policy else _digest(raw)
    if source_hash != manifest['source_sha256']:
        raise ValueError('Installed source map differs from host source map.')
    lines = IniLines(raw.decode('latin-1').splitlines())
    basic = _values(lines, 'Basic')
    if basic.get('multiplayeronly') not in {'1', 'yes', 'true'}:
        raise ValueError('Source map is not multiplayer-only.')
    merge_ini_section_values(lines, {
        'Basic': {'Name': f"{basic.get('name', source.stem)} - Randomizer"},
        # DrawBehind creates a BEHIND animation according to local visibility.
        # A hidden reward provider produced an extra animation on the guest
        # in the paired Panzer Ace SYNC logs (frame 259). That shifted subsequent
        # object IDs and caused different CRCs despite identical rules and RNG.
        # The native renderer supports a null Behind type without creating an
        # animation object. Disable this cosmetic marker for co-op maps only.
        'General': {'Behind': 'none'},
    })
    _apply_enemy_powerhouse_waves(lines, source, manifest, metadata)
    apply_coop_native_production_gate(lines, manifest)
    if manifest['schema'] == 5 or (manifest['schema'] in (7, 8)
            and manifest.get('guest_country', manifest['player_country'])
            != manifest['player_country']):
        for role, scope, country in (
            ('host', 'H', manifest['player_country']),
            ('guest', 'G', manifest['guest_country']),
        ):
            loadout = manifest['player_loadouts'][role]
            apply_coop_rewards(
                lines, manifest, SIDE_FAMILIES[SIDE_COUNTRIES.index(country)], country=country,
                access_ids=loadout['access_ids'],
                buff_counts=loadout['buff_counts'], clone_scope=scope,
                production_restrictions=loadout.get('production_restrictions', ()),
                building_ids=loadout.get('building_ids', ()),
            )
            if manifest['schema'] == 5:
                apply_shop_credit_bonus(
                    lines, country, scope, loadout.get('starting_credit_bonus', 0),
                )
                apply_coop_power_rewards(
                    lines, country, loadout.get('power_reward_ids', []),
                )
        if manifest['schema'] in (7, 8):
            apply_coop_power_rewards(
                lines, manifest['player_country'], manifest.get('power_reward_ids', []),
                shared_grid=True, countries=(manifest['player_country'], manifest['guest_country']),
                human_slots=range(manifest['player_count']),
            )
    else:
        apply_coop_rewards(
            lines, manifest, family,
            building_ids=manifest.get('building_ids', ()),
        )
        apply_coop_power_rewards(
            lines, manifest['player_country'], manifest.get('power_reward_ids', []),
            shared_grid=True, human_slots=range(manifest.get('player_count', 2)),
        )
    player_countries = {manifest['player_country']}
    if manifest['schema'] in (5, 7) and manifest.get('guest_country'):
        player_countries.add(manifest['guest_country'])
    if manifest.get('ai_teammate'):
        # Keep all allied native armies out of enemy reward overrides, even
        # when a shared native unit belongs to several different countries.
        player_countries.add(manifest['ai_teammate']['country'])
        # Settings/Credits is global to human and AI houses. Apply the earned
        # delta to the human house instead so the AI retains native finances.
        apply_shop_credit_bonus(
            lines, manifest['player_country'], 'H',
            manifest.get('starting_credit_bonus', 0),
        )
    apply_coop_enemy_rewards(
        lines, manifest.get('enemy_countries', []), player_countries,
        manifest.get('enemy_reward_ids', []),
    )
    from randomizer.coop.native_powers import apply_coop_payload_support
    apply_coop_payload_support(lines)
    from randomizer.coop.native_mutations import apply_coop_native_mutations
    apply_coop_native_mutations(lines, manifest)
    if manifest.get('ai_teammate'):
        # Native unit TaskForces use authored IDs, but the AI base planner
        # scans BuildingTypes. Exclude earned copies from that scan when an
        # allied AI uses the same country as the human; its original buildings
        # are still available because the production gate belongs only to A.
        building_clones = {
            str(value) for value in _values(lines, 'BuildingTypes').values()
            if str(value).upper().startswith(('MORP', 'MORH', 'MORG'))
        }
        merge_ini_section_values(lines, {
            clone: {'AIBuildThis': 'no'} for clone in sorted(building_clones)
        })
    from randomizer.coop.native_veterancy import compact_coop_veteran_ids
    compact_coop_veteran_ids(lines, player_countries)
    if manifest.get('mission_category') != 'challenge':
        inject_victory_markers(
            lines, source.stem.lower(), manifest['player_country'],
        )
    lines.insert(0, f'; {manifest["marker"]} {source_key} {manifest["seed"]}')
    return ('\r\n'.join(lines) + '\r\n').encode('latin-1')


def _validate_difficulty(difficulty):
    if type(difficulty) is not int or difficulty not in {0, 1, 2}:
        raise ValueError('Co-op difficulty must be 0 (Casual), 1 (Normal), or 2 (Mental).')
    return difficulty


def build_manifest(game_root: Path, state: dict, coop_name: str, *,
                   source_mission: str = '', unit_id: str = '',
                   allow_test_unit: bool = False, difficulty: int = 1,
                   country: str = '', player_count: int = 2,
                   mission_category: str = '', game_speed: int = 2,
                   guest_country: str = '', player_colors=None,
                   ai_teammate: dict | None = None) -> tuple[dict, bytes]:
    _validate_difficulty(difficulty)
    if state.get('progression_mode') not in SUPPORTED_PROGRESSION:
        raise ValueError('Prototype supports Classic, Grid Mode, and Mission List; Shop Mode is excluded.')
    if not state.get('seed'):
        raise ValueError('Generate or load a seed first.')
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,96}', str(state['seed'])):
        raise ValueError('Seed contains characters unsafe for a map marker.')
    coop_name = coop_name.lower()
    category = mission_category or state.get('mission_category') or (
        'challenge' if coop_name.startswith('c_') else 'coop')
    context = {}
    if category == 'challenge':
        from randomizer.coop.challenge import challenge_context
        config, context = challenge_context(
            game_root, coop_name, country, player_count, difficulty, game_speed,
            ai_teammate=ai_teammate,
            **({'guest_country': (guest_country or country or '') if player_count == 2 else guest_country,
                'player_colors': player_colors}
               if player_count == 2 or player_colors is not None else {}),
        )
        source, source_key, metadata, country, family = config
    elif category == 'coop':
        if ai_teammate is not None:
            raise ValueError('AI teammates are available only in local challenges.')
        if player_count != 2:
            raise ValueError('Co-op requires two human players.')
        source, source_key, metadata, country, family = _map_config(game_root, coop_name)
    else:
        raise ValueError('Multiplayer manifest needs a co-op or challenge mission.')
    selected_id, reward, test_override = _selected_reward(
        state, source_mission, unit_id, allow_test_unit, country)
    if selected_id and not re.fullmatch(r'[A-Z0-9_]{2,24}', selected_id):
        raise ValueError('Invalid unit ID for co-op prototype.')
    access_ids = sorted({entry[0] for entry in _access_candidates(state, source_mission, country)}
                        | ({selected_id} if selected_id else set()))
    registered_types = _registered_unit_types(source)
    for candidate_id in access_ids:
        _require_registered_type(source, candidate_id, registered_types)
    launch_rewards = _launch_rewards(state, source_mission, country)
    building_ids = _building_ids(launch_rewards)
    buff_counts = _buff_counts(launch_rewards, access_ids, building_ids)
    power_reward_ids = _power_reward_ids(launch_rewards)
    enemy_reward_ids = _grid_enemy_reward_ids(state)
    enemy_countries = _enemy_countries(metadata)
    credit_bonus = starting_credit_bonus(launch_rewards)
    if 'player_colors' in context:
        context['player_loadouts'] = {
            'host': {'access_ids': access_ids, 'buff_counts': buff_counts,
                     'building_ids': building_ids},
        }
        if player_count == 2:
            guest = context['guest_country']
            guest_rewards = _launch_rewards(state, source_mission, guest)
            guest_ids = sorted({entry[0] for entry in _access_candidates(
                state, source_mission, guest)} | ({selected_id} if test_override else set()))
            for candidate_id in guest_ids:
                _require_registered_type(source, candidate_id, registered_types)
            guest_buildings = _building_ids(guest_rewards)
            context['player_loadouts']['guest'] = {
                'access_ids': guest_ids,
                'buff_counts': _buff_counts(guest_rewards, guest_ids, guest_buildings),
                'building_ids': guest_buildings,
            }
    production_type = arsenal_unit_type(selected_id, BUFF_TARGETS.get(selected_id))
    source_hash = text_hash(source.read_bytes())
    unlimited_hero_units = bool(
        (state.get('reward_settings') or {}).get('unlimited_hero_units', False)
    )
    unlimited_buildings = bool(
        (state.get('reward_settings') or {}).get('unlimited_buildings', False)
    )
    from randomizer.coop.challenge import CHALLENGE_MARKER, destination, identity_fields
    marker = CHALLENGE_MARKER if context else PROTOTYPE_MARKER
    identity = _digest(json.dumps(
        [marker, source_hash, str(state['seed']), access_ids,
         buff_counts, building_ids, power_reward_ids, enemy_reward_ids,
         enemy_countries, credit_bonus, country, state.get('reward_mode', '')]
        + (identity_fields(context, difficulty) if context else
           [difficulty] if difficulty != 1 else [])
        + ([{'unlimited_hero_units': True}] if unlimited_hero_units else [])
        + ([{'unlimited_buildings': True}] if unlimited_buildings else []),
        sort_keys=True, separators=(',', ':'),
    ).encode('utf-8'))[:10]
    stem = f'morcp_{coop_name.removeprefix("coop_").lower()}_{identity}'
    map_key = f'MapsMO\\Cooperative\\{stem}'
    if context:
        stem, map_key = destination(coop_name, identity)
    manifest = {
        'schema': ((8 if 'ai_teammate' in context else
                    7 if 'player_colors' in context else 6) if context else 4),
        'fingerprint_policy': FINGERPRINT_POLICY,
        'marker': marker,
        'source_key': source_key,
        'source_sha256': source_hash,
        'seed': str(state['seed']),
        'progression_mode': state['progression_mode'],
        'reward_mode': state.get('reward_mode', ''),
        'source_mission': source_mission.upper(),
        'unit_id': selected_id,
        'access_ids': access_ids,
        'buff_counts': buff_counts,
        'building_ids': building_ids,
        'power_reward_ids': power_reward_ids,
        'enemy_reward_ids': enemy_reward_ids,
        'enemy_countries': enemy_countries,
        'starting_credit_bonus': credit_bonus,
        'test_override': test_override,
        'reward_name': reward.get('name', selected_id),
        'production_type': production_type,
        'player_country': country,
        'map_key': map_key,
        'map_file': f'{stem}.map',
        'description': metadata.get('description', source.stem.lower()) + ' - Randomizer',
        **context,
    }
    if unlimited_hero_units:
        manifest['unlimited_hero_units'] = True
    if unlimited_buildings:
        manifest['unlimited_buildings'] = True
    if difficulty != 1:
        manifest['difficulty'] = difficulty
    map_data = _map_bytes(source, source_key, manifest, family, metadata)
    manifest['map_sha256'] = _digest(map_data)
    return manifest, map_data


def shop_guest_country(metadata: dict, host_country: str) -> str:
    """Pick an unused sibling country so each player can own private clones."""
    host_index = SIDE_COUNTRIES.index(host_country)
    family_start = (host_index // 3) * 3
    enemies = {
        int(value.split(',', 1)[0].strip())
        for key, value in metadata.items() if key.startswith('enemyhouse')
    }
    candidates = [
        index for index in range(family_start, family_start + 3)
        if index != host_index and index not in enemies
    ]
    if not candidates:
        raise ValueError('Co-op map has no free sibling country for guest Shop loadout.')
    return SIDE_COUNTRIES[candidates[0]]


def _validate_shop_loadout(source: Path, loadout: dict, *, allow_empty=False,
                            registered_types=None) -> dict:
    if (not isinstance(loadout, dict)
            or not {'access_ids', 'buff_counts'} <= set(loadout)
            or set(loadout) - {
                'access_ids', 'buff_counts', 'production_restrictions',
                'building_ids', 'starting_credit_bonus', 'power_reward_ids',
                'enemy_reward_ids',
            }):
        raise ValueError('Shop loadout needs access_ids and buff_counts.')
    access_ids = loadout['access_ids']
    buff_counts = loadout['buff_counts']
    if (not isinstance(access_ids, list) or (not access_ids and not allow_empty)
            or len(access_ids) > (2048 if allow_empty else 100)
            or any(not isinstance(item, str) or not re.fullmatch(r'[A-Z0-9_]{2,24}', item)
                   for item in access_ids)
            or access_ids != sorted(set(access_ids))
            or not isinstance(buff_counts, dict)
            or any(not isinstance(counts, dict) for counts in buff_counts.values())):
        raise ValueError('Invalid co-op Shop unit access or buff loadout.')
    if registered_types is None:
        registered_types = _registered_unit_types(source)
    for unit_id in access_ids:
        _require_registered_type(source, unit_id, registered_types)
        if not arsenal_unit_type(unit_id, BUFF_TARGETS.get(unit_id)):
            raise ValueError(f'Unsupported co-op Shop unit: {unit_id}')
    for unit_id, counts in buff_counts.items():
        if any(not isinstance(buff_type, str) or not isinstance(amount, int)
               or isinstance(amount, bool) or not 1 <= amount <= 100
               for buff_type, amount in counts.items()):
            raise ValueError(f'Invalid co-op Shop buffs for {unit_id}.')
    restrictions = loadout.get('production_restrictions', [])
    if (not isinstance(restrictions, list)
            or any(not isinstance(item, str)
                   or item not in PRODUCTION_RESTRICTIONS for item in restrictions)
            or restrictions != sorted(set(restrictions))
            ):
        raise ValueError('Invalid co-op Shop production restrictions.')
    building_ids = loadout.get('building_ids', [])
    if (not isinstance(building_ids, list)
            or len(building_ids) > (2048 if allow_empty else 100)
            or any(not isinstance(item, str)
                   or not re.fullmatch(r'[A-Z0-9_]{2,24}', item)
                   or BUFF_TARGETS.get(item, {}).get('category') not in {
                       'defenses', 'special_buildings',
                   } for item in building_ids)
            or building_ids != sorted(set(building_ids))):
        raise ValueError('Invalid co-op Shop building access.')
    if set(buff_counts) - (set(access_ids) | set(building_ids)):
        raise ValueError('Co-op buffs require earned unit or building access.')
    credit_bonus = loadout.get('starting_credit_bonus', 0)
    if type(credit_bonus) is not int or not -10000 <= credit_bonus <= 50000:
        raise ValueError('Invalid co-op Shop starting credit bonus.')
    power_reward_ids = loadout.get('power_reward_ids', [])
    if (not isinstance(power_reward_ids, list) or len(power_reward_ids) > 150
            or any(not isinstance(item, str) or len(item) > 120
                   or canonical_reward({'name': item}).get('kind') not in {
                       'superweapon', 'buff',
                   }
                   or canonical_reward({'name': item}).get('kind') == 'buff'
                   and not canonical_reward({'name': item}).get('power_buff_type')
                   for item in power_reward_ids)
            or power_reward_ids != sorted(power_reward_ids)):
        raise ValueError('Invalid co-op Shop power rewards.')
    enemy_reward_ids = loadout.get('enemy_reward_ids', [])
    if (not isinstance(enemy_reward_ids, list) or len(enemy_reward_ids) > 150
            or any(not isinstance(item, str) or len(item) > 120
                   or not canonical_reward({'name': item}).get('enemy_reward')
                   for item in enemy_reward_ids)
            or enemy_reward_ids != sorted(enemy_reward_ids)):
        raise ValueError('Invalid co-op Shop enemy rewards.')
    result = {'access_ids': list(access_ids),
              'buff_counts': {unit_id: dict(counts) for unit_id, counts in buff_counts.items()}}
    if 'production_restrictions' in loadout:
        result['production_restrictions'] = list(restrictions)
    if 'building_ids' in loadout:
        result['building_ids'] = list(building_ids)
    if 'starting_credit_bonus' in loadout:
        result['starting_credit_bonus'] = credit_bonus
    if 'power_reward_ids' in loadout:
        result['power_reward_ids'] = list(power_reward_ids)
    if 'enemy_reward_ids' in loadout:
        result['enemy_reward_ids'] = list(enemy_reward_ids)
    return result


def shop_unit_loadout(run, profile=None, *, state=None) -> dict:
    """Project one player's Shop rewards and stage effects for the map."""
    from randomizer.shop.active import (
        active_shop_rewards, active_shop_starter_defense_ids,
        active_shop_starter_unit_ids,
    )
    from randomizer.shop.catalogue import canonical_reward_for_id
    from randomizer.shop.mission_modifiers import active_mission_modifier

    rewards = list(active_shop_rewards(run))
    challenge_definition = SHOP_CONFIG.permanent_upgrades['permanent_challenge_slots']
    challenge_slots = (
        profile.upgrade_level('permanent_challenge_slots')
        * int(challenge_definition.effects['slots_per_level'])
        if profile else 0
    )
    mission_modifier = active_mission_modifier(run, challenge_slots=challenge_slots)
    if mission_modifier:
        rewards.extend(
            canonical_reward_for_id(reward_id)
            for reward_id in mission_modifier.player_reward_ids
        )
    access_ids = {str(unit_id).upper() for unit_id in active_shop_starter_unit_ids(run)}
    for reward in rewards:
        if reward.get('kind') in {'buff', 'superweapon', 'message', 'retired'}:
            continue
        for unit_id in tech_ids_for_rewards([reward]):
            if arsenal_unit_type(unit_id, BUFF_TARGETS.get(unit_id)):
                access_ids.add(unit_id)
    access_ids = sorted(access_ids)
    if not access_ids:
        raise ValueError('Co-op Shop player has no supported unit access.')
    veteran_targets = set()
    if profile and profile.upgrade_level('veteran_academy'):
        for reward_id in run.selected_permanent_units:
            veteran_targets.update(
                unit_id for unit_id in tech_ids_for_rewards([
                    canonical_reward_for_id(reward_id)
                ]) if unit_id in access_ids
            )
    if modifier_effects(run.modifiers)['starter_veteran']:
        veteran_targets.update(active_shop_starter_unit_ids(run))
    for unit_id in sorted(veteran_targets):
        target = BUFF_TARGETS.get(unit_id, {})
        reward_name = f'{target.get("label", unit_id)} Veteran Training I'
        reward = canonical_reward_for_id(reward_name)
        if reward.get('buff_type') == 'veteran':
            rewards.append(reward)
    building_ids = sorted(set(_building_ids(rewards))
                          | set(active_shop_starter_defense_ids(run)))
    loadout = {'access_ids': access_ids,
               'buff_counts': _buff_counts(rewards, access_ids, building_ids)}
    if building_ids:
        loadout['building_ids'] = building_ids
    power_reward_ids = _power_reward_ids(rewards)
    if power_reward_ids:
        loadout['power_reward_ids'] = power_reward_ids
    offer = next((
        item for item in run.mission_offers
        if item.mission_code == run.selected_mission_code
    ), None)
    if offer is not None:
        entries = shop_enemy_scaling_entries(
            run, offer, {'no_build': False, 'true_no_build': False,
                         'no_build_production': False},
            challenge_slots=challenge_slots,
        )
        enemy_reward_ids = sorted(str(entry['reward']['name']) for entry in entries)
        if enemy_reward_ids:
            loadout['enemy_reward_ids'] = enemy_reward_ids
    if state is not None and received_rewards(state) is not None:
        traps = _grid_enemy_reward_ids(state)
        if traps:
            loadout['enemy_reward_ids'] = sorted([
                *loadout.get('enemy_reward_ids', ()), *traps,
            ])
    credit_level = profile.upgrade_level('mission_starting_credits') if profile else 0
    credits_per_level = int(SHOP_CONFIG.permanent_upgrades[
        'mission_starting_credits'
    ].effects['credits_per_level'])
    credit_bonus = (
        starting_credit_bonus(rewards)
        + credit_level * credits_per_level
        + int(modifier_effects(run.modifiers)['mission_starting_credits_flat'])
    )
    if credit_bonus:
        loadout['starting_credit_bonus'] = credit_bonus
    restrictions = stage_production_restrictions(run)
    if restrictions:
        loadout['production_restrictions'] = sorted(restrictions)
    return loadout


def build_shop_manifest(game_root: Path, seed: str, coop_name: str,
                        host_loadout: dict, guest_loadout: dict, *,
                        stage: int = 1, difficulty: int = 1,
                        _fingerprint_policy=FINGERPRINT_POLICY) -> tuple[dict, bytes]:
    """Build one identical map with two country-gated purchased unit rosters."""
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,96}', str(seed)):
        raise ValueError('Shop seed contains characters unsafe for a map marker.')
    if not isinstance(stage, int) or isinstance(stage, bool) or not 1 <= stage <= 10000:
        raise ValueError('Co-op Shop stage must be between 1 and 10000.')
    _validate_difficulty(difficulty)
    coop_name = coop_name.lower()
    source, source_key, metadata, country, family = _map_config(game_root, coop_name)
    guest_country = shop_guest_country(metadata, country)
    enemy_countries = _enemy_countries(metadata)
    registered_types = _registered_unit_types(source)
    loadouts = {
        'host': _validate_shop_loadout(source, host_loadout, registered_types=registered_types),
        'guest': _validate_shop_loadout(source, guest_loadout, registered_types=registered_types),
    }
    source_hash = (text_hash if _fingerprint_policy else _digest)(source.read_bytes())
    identity = _digest(json.dumps(
        [SHOP_MARKER, source_hash, str(seed), stage, country, guest_country,
         enemy_countries, loadouts] + ([difficulty] if difficulty != 1 else []),
        sort_keys=True, separators=(',', ':'),
    ).encode('utf-8'))[:10]
    stem = f'morcs_{coop_name.removeprefix("coop_")}_{identity}'
    manifest = {
        'schema': 5, 'marker': SHOP_MARKER,
        'source_key': source_key, 'source_sha256': source_hash,
        'seed': str(seed), 'shop_stage': stage, 'progression_mode': 'Shop Mode',
        'player_country': country, 'guest_country': guest_country,
        'enemy_countries': enemy_countries,
        'player_loadouts': loadouts,
        'enemy_reward_ids': _shared_shop_enemy_reward_ids(loadouts),
        'map_key': f'MapsMO\\Cooperative\\{stem}',
        'map_file': f'{stem}.map',
        'description': metadata.get('description', source.stem.lower()) + ' - Randomizer Shop',
    }
    if _fingerprint_policy:
        manifest['fingerprint_policy'] = _fingerprint_policy
    if difficulty != 1:
        manifest['difficulty'] = difficulty
    data = _map_bytes(source, source_key, manifest, family, metadata)
    manifest['map_sha256'] = _digest(data)
    return manifest, data


def rebuild_from_manifest(game_root: Path, manifest: dict) -> bytes:
    if manifest.get('schema') == 5:
        source_key = str(manifest.get('source_key', ''))
        coop_name = source_key.rsplit('\\', 1)[-1]
        loadouts = manifest.get('player_loadouts')
        if not isinstance(loadouts, dict):
            raise ValueError('Co-op Shop manifest has no player loadouts.')
        expected, data = build_shop_manifest(
            game_root, manifest.get('seed', ''), coop_name,
            loadouts.get('host'), loadouts.get('guest'),
            stage=manifest.get('shop_stage'),
            difficulty=manifest.get('difficulty', 1),
            _fingerprint_policy=manifest.get('fingerprint_policy'),
        )
        if manifest != expected:
            raise ValueError('Co-op Shop manifest differs from installed map or loadouts.')
        return data
    context = {}
    if manifest.get('schema') in (6, 7, 8):
        from randomizer.coop.challenge import identity_fields, validate_context
        config, context = validate_context(game_root, manifest)
    elif manifest.get('schema') != 4 or manifest.get('marker') != PROTOTYPE_MARKER:
        raise ValueError('Unsupported co-op prototype manifest.')
    elif (manifest.get('mission_category', 'coop') != 'coop'
          or manifest.get('player_count', 2) != 2):
        raise ValueError('Legacy co-op manifest cannot select challenge settings.')
    elif 'ai_teammate' in manifest:
        raise ValueError('Legacy co-op manifests cannot select an AI teammate.')
    source_key = str(manifest.get('source_key', ''))
    coop_name = source_key.rsplit('\\', 1)[-1]
    source, actual_key, _metadata, country, family = (
        config if context else _map_config(game_root, coop_name))
    if source_key != actual_key or country != manifest.get('player_country'):
        raise ValueError('Manifest map or player side differs from installed Mental Omega.')
    unit_id = str(manifest.get('unit_id', '')).upper()
    if unit_id and not re.fullmatch(r'[A-Z0-9_]{2,24}', unit_id):
        raise ValueError('Invalid unit ID in manifest.')
    if arsenal_unit_type(unit_id, BUFF_TARGETS.get(unit_id)) != manifest.get('production_type'):
        raise ValueError('Manifest unit category differs from launcher catalogue.')
    registered_types = _registered_unit_types(source)
    if unit_id:
        _require_registered_type(source, unit_id, registered_types)
    seed = str(manifest.get('seed', ''))
    difficulty = _validate_difficulty(manifest.get('difficulty', 1))
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,96}', seed):
        raise ValueError('Manifest seed is invalid.')
    access_ids = manifest.get('access_ids')
    buff_counts = manifest.get('buff_counts')
    building_ids = manifest.get('building_ids')
    power_reward_ids = manifest.get('power_reward_ids')
    enemy_reward_ids = manifest.get('enemy_reward_ids')
    enemy_countries = manifest.get('enemy_countries')
    credit_bonus = manifest.get('starting_credit_bonus')
    unlimited_hero_units = manifest.get('unlimited_hero_units', False)
    if type(unlimited_hero_units) is not bool:
        raise ValueError('Invalid unlimited hero unit setting in manifest.')
    unlimited_buildings = manifest.get('unlimited_buildings', False)
    if type(unlimited_buildings) is not bool:
        raise ValueError('Invalid unlimited building setting in manifest.')
    if (type(credit_bonus) is not int or not 0 <= credit_bonus <= 20000):
        raise ValueError('Invalid co-op starting credit bonus.')
    if (not isinstance(access_ids, list) or
            not all(isinstance(item, str) and re.fullmatch(r'[A-Z0-9_]{2,24}', item)
                    for item in access_ids) or
            access_ids != sorted(set(access_ids)) or
            bool(unit_id) != bool(access_ids) or
            (unit_id and unit_id not in access_ids) or not isinstance(buff_counts, dict)):
        raise ValueError('Invalid co-op access or buff manifest.')
    if (not isinstance(building_ids, list)
            or building_ids != sorted(set(building_ids))
            or any(BUFF_TARGETS.get(item, {}).get('category') not in {
                'defenses', 'special_buildings',
            } for item in building_ids)):
        raise ValueError('Invalid co-op building access manifest.')
    if (not isinstance(power_reward_ids, list)
            or power_reward_ids != sorted(power_reward_ids)
            or any(not isinstance(item, str)
                   or canonical_reward({'name': item}).get('kind') not in {
                       'superweapon', 'buff',
                   } for item in power_reward_ids)):
        raise ValueError('Invalid co-op power reward manifest.')
    if (not isinstance(enemy_reward_ids, list)
            or enemy_reward_ids != sorted(enemy_reward_ids)
            or any(not isinstance(item, str)
                   or not canonical_reward({'name': item}).get('enemy_reward')
                   for item in enemy_reward_ids)
            or enemy_countries != _enemy_countries(_metadata)):
        raise ValueError('Invalid co-op enemy reward manifest.')
    for candidate_id in access_ids:
        _require_registered_type(source, candidate_id, registered_types)
    for candidate_id, counts in buff_counts.items():
        if (candidate_id not in set(access_ids) | set(building_ids)
                or not isinstance(counts, dict)):
            raise ValueError('Invalid co-op buff target.')
        if any(not isinstance(buff_type, str) or type(value) is not int
               or not 1 <= value <= 100 for buff_type, value in counts.items()):
            raise ValueError('Invalid co-op buff count.')
    if manifest.get('schema') in (7, 8):
        loadouts = manifest.get('player_loadouts')
        roles = {'host', 'guest'} if manifest['player_count'] == 2 else {'host'}
        if not isinstance(loadouts, dict) or set(loadouts) != roles:
            raise ValueError('Challenge player reward loadouts are missing.')
        for role in roles:
            if (not isinstance(loadouts[role], dict)
                    or set(loadouts[role]) != {'access_ids', 'buff_counts', 'building_ids'}):
                raise ValueError('Invalid challenge player reward loadout.')
            _validate_shop_loadout(
                source, loadouts[role], allow_empty=True,
                registered_types=registered_types,
            )
        if loadouts['host'] != {'access_ids': access_ids, 'buff_counts': buff_counts,
                               'building_ids': building_ids}:
            raise ValueError('Host challenge rewards differ from shared run rewards.')
        if (manifest.get('guest_country') == country
                and loadouts['guest'] != loadouts['host']):
            raise ValueError('Players using the same house must share one reward roster.')
        context['player_loadouts'] = loadouts
    expected_identity = _digest(json.dumps(
        [manifest['marker'], manifest['source_sha256'], seed, access_ids,
         buff_counts, building_ids, power_reward_ids, enemy_reward_ids,
         enemy_countries, credit_bonus, country, manifest.get('reward_mode', '')]
        + (identity_fields(context, difficulty) if context else
           [difficulty] if difficulty != 1 else [])
        + ([{'unlimited_hero_units': True}] if unlimited_hero_units else [])
        + ([{'unlimited_buildings': True}] if unlimited_buildings else []),
        sort_keys=True, separators=(',', ':'),
    ).encode('utf-8'))[:10]
    expected_stem = f'morcp_{coop_name.removeprefix("coop_")}_{expected_identity}'
    expected_key = f'MapsMO\\Cooperative\\{expected_stem}'
    if context:
        from randomizer.coop.challenge import destination
        expected_stem, expected_key = destination(coop_name, expected_identity)
    if manifest.get('map_key') != expected_key or manifest.get('map_file') != f'{expected_stem}.map':
        raise ValueError('Manifest destination does not match its source and seed.')
    if manifest.get('description') != _metadata.get('description', source.stem.lower()) + ' - Randomizer':
        raise ValueError('Manifest map description differs from installed map metadata.')
    data = _map_bytes(source, actual_key, manifest, family, _metadata)
    if _digest(data) != manifest.get('map_sha256'):
        raise ValueError('Generated map hash differs from host manifest.')
    return data


def write_bundle(output_dir: Path, manifest: dict, map_data: bytes) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / (Path(manifest['map_file']).stem + '.json')
    map_path = output_dir / manifest['map_file']
    for path, data in (
        (map_path, map_data),
        (manifest_path, (json.dumps(manifest, indent=2) + '\n').encode('utf-8')),
    ):
        if path.exists() and path.read_bytes() != data:
            raise FileExistsError(f'Refusing to replace different prototype output: {path}')
        path.write_bytes(data)
    return manifest_path, map_path


def _remove_catalogue_entry(lines: list[str], manifest: dict) -> list[str]:
    marker = f'; {manifest["marker"]} {manifest["map_key"]}'
    output = list(lines)
    start, end = find_section_bounds(output, manifest['map_key'])
    if start is not None:
        if start == 0 or output[start - 1] != marker:
            raise ValueError('Existing map entry lacks prototype ownership marker.')
        # Our generated section is appended after one separator line. Remove
        # that separator too so uninstall restores a byte-identical INI.
        first = start - 2 if start >= 2 and output[start - 2] == '' else start - 1
        del output[first:end]
    start, end = find_section_bounds(output, 'MultiMaps')
    for index in range(end - 1, start, -1):
        if output[index] != marker:
            continue
        if index + 1 >= end or output[index + 1].split('=', 1)[-1].strip() != manifest['map_key']:
            raise ValueError('Prototype list marker has unexpected value.')
        del output[index:index + 2]
        break
    return output


def _catalogue_bytes(game_root: Path, manifest: dict, *, add: bool) -> bytes:
    catalogue = resolve_path(game_root, 'INI/MentalOmegaMaps.ini')
    original = _text(catalogue)
    newline = '\r\n' if '\r\n' in original else '\n'
    ends_with_newline = original.endswith(('\n', '\r'))
    lines = _remove_catalogue_entry(original.splitlines(), manifest)
    if add:
        source_lines = _section(lines, manifest['source_key'])
        while source_lines and not source_lines[-1].strip():
            source_lines.pop()
        updated = []
        for line in source_lines:
            if line.lower().startswith('description='):
                updated.append(f'Description={manifest["description"]}')
            else:
                updated.append(line)
        start, end = find_section_bounds(lines, 'MultiMaps')
        keys = [
            int(line.split('=', 1)[0].strip())
            for line in lines[start + 1:end]
            if '=' in line and line.split('=', 1)[0].strip().isdigit()
        ]
        marker = f'; {manifest["marker"]} {manifest["map_key"]}'
        lines[end:end] = [marker, f'{max(keys, default=-1) + 1}={manifest["map_key"]}']
        lines.extend(['', marker, f'[{manifest["map_key"]}]', *updated])
    result = newline.join(lines)
    if ends_with_newline:
        result += newline
    return result.encode('latin-1')


def install(game_root: Path, manifest: dict, map_data: bytes) -> Path:
    expected_data = rebuild_from_manifest(game_root, manifest)
    if expected_data != map_data:
        raise ValueError('Map data does not match local source and manifest.')
    if _digest(map_data) != manifest.get('map_sha256'):
        raise ValueError('Map data does not match manifest hash.')
    if not map_data.startswith(f'; {manifest["marker"]} '.encode('ascii')):
        raise ValueError('Map lacks prototype ownership marker.')
    folder = 'Challenge' if manifest.get('mission_category') == 'challenge' else 'Cooperative'
    destination = game_root / 'MapsMO' / folder / manifest['map_file']
    if destination.exists() and destination.read_bytes() != map_data:
        raise FileExistsError(f'Refusing to replace different map: {destination}')
    catalogue = resolve_path(game_root, 'INI/MentalOmegaMaps.ini')
    updated = _catalogue_bytes(game_root, manifest, add=True)
    if not destination.exists():
        destination.write_bytes(map_data)
    if catalogue.read_bytes() != updated:
        backup = catalogue.with_name('MentalOmegaMaps.ini.mor-coop-backup')
        if not backup.exists():
            backup.write_bytes(catalogue.read_bytes())
        catalogue.write_bytes(updated)
    return destination


def remove(game_root: Path, manifest: dict) -> None:
    rebuild_from_manifest(game_root, manifest)
    folder = 'Challenge' if manifest.get('mission_category') == 'challenge' else 'Cooperative'
    destination = game_root / 'MapsMO' / folder / manifest['map_file']
    if destination.exists() and _digest(destination.read_bytes()) != manifest.get('map_sha256'):
        raise ValueError('Installed map changed; refusing to remove it.')
    catalogue = resolve_path(game_root, 'INI/MentalOmegaMaps.ini')
    updated = _catalogue_bytes(game_root, manifest, add=False)
    if updated != catalogue.read_bytes():
        catalogue.write_bytes(updated)
    if destination.exists():
        destination.unlink()
