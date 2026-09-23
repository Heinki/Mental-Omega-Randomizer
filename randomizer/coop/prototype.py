"""Build shared, map-local co-op unit rewards for a private LAN test.

The prototype deliberately edits a new copy of an installed co-op map. The
original map and official MIX files remain untouched. Both players install
the same generated map and lobby entry before opening the LAN client.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from randomizer.maps.ini import (
    IniLines, all_section_value_maps, find_section_bounds,
    merge_ini_section_values,
)
from randomizer.missions.access import CHAOS_PRIMARY_PRODUCTION
from randomizer.coop.reward_map import apply_coop_rewards
from randomizer.maps.buff_values import _active_direct_buff_counts
from randomizer.rewards.arsenal import ARSENAL_MODE, arsenal_launch_rewards, arsenal_unit_type
from randomizer.rewards.catalogue import BUFF_TARGETS, buff_stack_limit, canonical_reward, check_rewards
from randomizer.rewards.rules import tech_ids_for_rewards
from randomizer.rewards.roster import randomizer_unit_roster
from randomizer.ui.cameos import installed_rules_registry


PROTOTYPE_MARKER = 'MOR_COOP_PROTOTYPE_V4'
SUPPORTED_PROGRESSION = {'Classic', 'Grid Mode', 'Mission List'}
SIDE_COUNTRIES = (
    'UnitedStates', 'Europeans', 'Pacific',
    'USSR', 'Latin', 'Chinese',
    'PsiCorps', 'ScorpionCell', 'Headquaters',
)
SIDE_FAMILIES = ('allies',) * 3 + ('soviets',) * 3 + ('epsilon',) * 3


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
    source = game_root / 'MapsMO' / 'Cooperative' / f'{coop_name.lower()}.map'
    if not source.is_file():
        raise FileNotFoundError(source)
    catalogue = game_root / 'INI' / 'MentalOmegaMaps.ini'
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
    available = sorted(set(range(len(SIDE_COUNTRIES))) - denied)
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


def _access_candidates(state: dict, source_mission: str = '') -> list[tuple[str, dict]]:
    rewards = _launch_rewards(state, source_mission)
    candidates = []
    for reward in rewards:
        if reward.get('kind') in {'buff', 'superweapon', 'message', 'retired'}:
            continue
        for unit_id in sorted(tech_ids_for_rewards([reward])):
            if arsenal_unit_type(unit_id, BUFF_TARGETS.get(unit_id)):
                candidates.append((unit_id, reward))
    return candidates


def _launch_rewards(state: dict, source_mission: str = '') -> list[dict]:
    earned = _earned_rewards(state)
    if state.get('reward_mode') == ARSENAL_MODE:
        if not source_mission:
            raise ValueError('Randomizer Arsenal requires --source-mission CODE.')
        arsenal = (state.get('mission_arsenals') or {}).get(source_mission.upper())
        if not arsenal:
            raise ValueError(f'No saved arsenal for {source_mission.upper()}.')
        return arsenal_launch_rewards(arsenal, earned)
    return earned


def _buff_counts(rewards: list[dict], access_ids: list[str]) -> dict:
    counts = _active_direct_buff_counts(
        rewards, additional_unlocked_tech_ids=access_ids,
        unit_specific_mode=True, global_production_unit_ids=access_ids,
    )
    selected = {unit_id: dict(counts.get(unit_id, {})) for unit_id in access_ids}
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
                     allow_test_unit: bool = False):
    candidates = _access_candidates(state, source_mission)
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
        raise ValueError('Saved run has no supported infantry, vehicle, aircraft, or naval access.')
    return *candidates[0], False


def _require_registered_type(source: Path, unit_id: str) -> None:
    """Reject map-only rewards absent from this co-op map's type registry."""
    _powers, installed = installed_rules_registry(synchronous=True)
    map_sections = all_section_value_maps(_text(source).splitlines())
    for sections in (installed, map_sections):
        names = {str(name).lower(): name for name in sections}
        type_section = names.get(unit_id.lower())
        if not type_section:
            continue
        if any(
            unit_id.upper() in {
                str(value).upper() for value in sections.get(names.get(category.lower()), {}).values()
            }
            for category in ('InfantryTypes', 'VehicleTypes', 'AircraftTypes')
            if names.get(category.lower())
        ):
            return
    _, clone_ids, templates = randomizer_unit_roster()
    if unit_id in clone_ids and templates.get(unit_id):
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


def _map_bytes(source: Path, source_key: str, manifest: dict, family: str) -> bytes:
    raw = source.read_bytes()
    if _digest(raw) != manifest['source_sha256']:
        raise ValueError('Installed source map differs from host source map.')
    lines = IniLines(raw.decode('latin-1').splitlines())
    basic = _values(lines, 'Basic')
    if basic.get('multiplayeronly') not in {'1', 'yes', 'true'}:
        raise ValueError('Source map is not multiplayer-only.')
    merge_ini_section_values(lines, {
        'Basic': {'Name': f"{basic.get('name', source.stem)} - Randomizer"},
    })
    apply_coop_rewards(lines, manifest, family)
    lines.insert(0, f'; {PROTOTYPE_MARKER} {source_key} {manifest["seed"]}')
    return ('\r\n'.join(lines) + '\r\n').encode('latin-1')


def build_manifest(game_root: Path, state: dict, coop_name: str, *,
                   source_mission: str = '', unit_id: str = '',
                   allow_test_unit: bool = False) -> tuple[dict, bytes]:
    if state.get('progression_mode') not in SUPPORTED_PROGRESSION:
        raise ValueError('Prototype supports Classic, Grid Mode, and Mission List; Shop Mode is excluded.')
    if not state.get('seed'):
        raise ValueError('Generate or load a seed first.')
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,96}', str(state['seed'])):
        raise ValueError('Seed contains characters unsafe for a map marker.')
    coop_name = coop_name.lower()
    source, source_key, metadata, country, family = _map_config(game_root, coop_name)
    selected_id, reward, test_override = _selected_reward(
        state, source_mission, unit_id, allow_test_unit)
    if not re.fullmatch(r'[A-Z0-9_]{2,24}', selected_id):
        raise ValueError('Invalid unit ID for co-op prototype.')
    access_ids = sorted({entry[0] for entry in _access_candidates(state, source_mission)}
                        | {selected_id})
    for candidate_id in access_ids:
        _require_registered_type(source, candidate_id)
    buff_counts = _buff_counts(_launch_rewards(state, source_mission), access_ids)
    production_type = arsenal_unit_type(selected_id, BUFF_TARGETS.get(selected_id))
    source_hash = _digest(source.read_bytes())
    identity = _digest(json.dumps(
        [PROTOTYPE_MARKER, source_hash, str(state['seed']), access_ids, buff_counts, country],
        sort_keys=True, separators=(',', ':'),
    ).encode('utf-8'))[:10]
    stem = f'morcp_{coop_name.removeprefix("coop_").lower()}_{identity}'
    map_key = f'MapsMO\\Cooperative\\{stem}'
    manifest = {
        'schema': 3,
        'marker': PROTOTYPE_MARKER,
        'source_key': source_key,
        'source_sha256': source_hash,
        'seed': str(state['seed']),
        'progression_mode': state['progression_mode'],
        'reward_mode': state.get('reward_mode', ''),
        'source_mission': source_mission.upper(),
        'unit_id': selected_id,
        'access_ids': access_ids,
        'buff_counts': buff_counts,
        'test_override': test_override,
        'reward_name': reward.get('name', selected_id),
        'production_type': production_type,
        'player_country': country,
        'map_key': map_key,
        'map_file': f'{stem}.map',
        'description': metadata.get('description', source.stem) + ' - Randomizer',
    }
    map_data = _map_bytes(source, source_key, manifest, family)
    manifest['map_sha256'] = _digest(map_data)
    return manifest, map_data


def rebuild_from_manifest(game_root: Path, manifest: dict) -> bytes:
    if manifest.get('schema') != 3 or manifest.get('marker') != PROTOTYPE_MARKER:
        raise ValueError('Unsupported co-op prototype manifest.')
    source_key = str(manifest.get('source_key', ''))
    coop_name = source_key.rsplit('\\', 1)[-1]
    source, actual_key, _metadata, country, family = _map_config(game_root, coop_name)
    if source_key != actual_key or country != manifest.get('player_country'):
        raise ValueError('Manifest map or player side differs from installed Mental Omega.')
    unit_id = str(manifest.get('unit_id', '')).upper()
    if not re.fullmatch(r'[A-Z0-9_]{2,24}', unit_id):
        raise ValueError('Invalid unit ID in manifest.')
    if arsenal_unit_type(unit_id, BUFF_TARGETS.get(unit_id)) != manifest.get('production_type'):
        raise ValueError('Manifest unit category differs from launcher catalogue.')
    _require_registered_type(source, unit_id)
    seed = str(manifest.get('seed', ''))
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,96}', seed):
        raise ValueError('Manifest seed is invalid.')
    access_ids = manifest.get('access_ids')
    buff_counts = manifest.get('buff_counts')
    if (not isinstance(access_ids, list) or not access_ids or
            not all(isinstance(item, str) and re.fullmatch(r'[A-Z0-9_]{2,24}', item)
                    for item in access_ids) or
            access_ids != sorted(set(access_ids)) or
            unit_id not in access_ids or not isinstance(buff_counts, dict)):
        raise ValueError('Invalid co-op access or buff manifest.')
    for candidate_id in access_ids:
        _require_registered_type(source, candidate_id)
    for candidate_id, counts in buff_counts.items():
        if candidate_id not in access_ids or not isinstance(counts, dict):
            raise ValueError('Invalid co-op buff target.')
        if any(not isinstance(value, int) or not 1 <= value <= 100
               for value in counts.values()):
            raise ValueError('Invalid co-op buff count.')
    expected_identity = _digest(json.dumps(
        [PROTOTYPE_MARKER, manifest['source_sha256'], seed, access_ids, buff_counts, country],
        sort_keys=True, separators=(',', ':'),
    ).encode('utf-8'))[:10]
    expected_stem = f'morcp_{coop_name.removeprefix("coop_")}_{expected_identity}'
    expected_key = f'MapsMO\\Cooperative\\{expected_stem}'
    if manifest.get('map_key') != expected_key or manifest.get('map_file') != f'{expected_stem}.map':
        raise ValueError('Manifest destination does not match its source and seed.')
    if manifest.get('description') != _metadata.get('description', source.stem) + ' - Randomizer':
        raise ValueError('Manifest map description differs from installed map metadata.')
    data = _map_bytes(source, actual_key, manifest, family)
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
    marker = f'; {PROTOTYPE_MARKER} {manifest["map_key"]}'
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
    catalogue = game_root / 'INI' / 'MentalOmegaMaps.ini'
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
        marker = f'; {PROTOTYPE_MARKER} {manifest["map_key"]}'
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
    if not map_data.startswith(f'; {PROTOTYPE_MARKER} '.encode('ascii')):
        raise ValueError('Map lacks prototype ownership marker.')
    destination = game_root / 'MapsMO' / 'Cooperative' / manifest['map_file']
    if destination.exists() and destination.read_bytes() != map_data:
        raise FileExistsError(f'Refusing to replace different map: {destination}')
    catalogue = game_root / 'INI' / 'MentalOmegaMaps.ini'
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
    destination = game_root / 'MapsMO' / 'Cooperative' / manifest['map_file']
    if destination.exists() and _digest(destination.read_bytes()) != manifest.get('map_sha256'):
        raise ValueError('Installed map changed; refusing to remove it.')
    catalogue = game_root / 'INI' / 'MentalOmegaMaps.ini'
    updated = _catalogue_bytes(game_root, manifest, add=False)
    if updated != catalogue.read_bytes():
        catalogue.write_bytes(updated)
    if destination.exists():
        destination.unlink()
