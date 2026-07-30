"""Static player-owned TechnoType roster loading and validation."""

from __future__ import annotations

import shutil
from functools import lru_cache
from pathlib import Path

from randomizer.core.paths import APP_DIR, FROZEN, SOURCE_DIR


ROSTER_FILENAMES = (
    'RandomizerInfantry.ini',
    'RandomizerHeroes.ini',
    'RandomizerVehicles.ini',
    'RandomizerShips.ini',
    'RandomizerAircraft.ini',
    'RandomizerDefensesAndSpecialBuildings.ini',
)
ROSTER_CATEGORIES = {
    'infantry': 'InfantryTypes',
    'units': 'VehicleTypes',
    'aircraft': 'AircraftTypes',
    'defenses': 'BuildingTypes',
    'special_buildings': 'BuildingTypes',
}
MANDATORY_TEMPLATE_OVERRIDES = {
    # Old packaged editable roster files are preserved across upgrades. Keep
    # this EMPulse field generator uncloaked even when its visible file predates
    # the reviewed static-template correction.
    'NAIRDM': {
        'Cloakable.Allowed': 'no',
    },
}


def randomizer_unit_id(source_id):
    return f'MORP{str(source_id or "").strip().upper()}'


def _active_roster_paths():
    bundled_paths = tuple(SOURCE_DIR / 'configs' / name for name in ROSTER_FILENAMES)
    if not FROZEN:
        return bundled_paths
    visible_paths = tuple(APP_DIR / 'configs' / name for name in ROSTER_FILENAMES)
    for bundled_path, visible_path in zip(bundled_paths, visible_paths):
        if not visible_path.exists():
            visible_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bundled_path, visible_path)
    return visible_paths


def _read_sections(path: Path):
    sections = {}
    current = None
    for raw_line in path.read_text(encoding='utf-8-sig').splitlines():
        stripped = raw_line.strip()
        if stripped.startswith('[') and stripped.endswith(']'):
            current = stripped[1:-1].strip()
            sections[current] = {}
            continue
        if current is None or not stripped or stripped.startswith(';') or '=' not in raw_line:
            continue
        key, value = raw_line.split('=', 1)
        sections[current][key.strip()] = value.split(';', 1)[0].strip()
    return sections


@lru_cache(maxsize=None)
def randomizer_unit_ids_with_behavior(key, expected_value='yes'):
    """Return source IDs selected by an actual static-template behavior tag."""
    paths = _active_roster_paths()
    missing_files = [str(path) for path in paths if not path.is_file()]
    if missing_files:
        raise FileNotFoundError(
            'Randomizer unit roster file(s) missing: ' + ', '.join(missing_files)
        )

    sections = {}
    for path in paths:
        for section, values in _read_sections(path).items():
            sections[section.lower()] = (section, values)
    if FROZEN:
        # Preserved visible sections remain authoritative. Bundled sections
        # only supplement types absent from an older packaged roster.
        for name in ROSTER_FILENAMES:
            bundled_path = SOURCE_DIR / 'configs' / name
            if not bundled_path.is_file():
                continue
            for section, values in _read_sections(bundled_path).items():
                sections.setdefault(section.lower(), (section, values))

    normalized_key = str(key).strip().lower()
    normalized_value = str(expected_value).strip().lower()
    matches = set()
    for section, values in sections.values():
        if not section.upper().startswith('MORP'):
            continue
        value = next(
            (
                raw_value
                for raw_key, raw_value in values.items()
                if raw_key.strip().lower() == normalized_key
            ),
            None,
        )
        if value is not None and value.strip().lower() == normalized_value:
            matches.add(section[4:].upper())
    return frozenset(matches)


@lru_cache(maxsize=1)
def randomizer_unit_roster():
    from randomizer.rewards.catalogue import BUFF_TARGETS

    paths = _active_roster_paths()
    sections_by_path = {}
    bundled_fallback_sections = {}
    missing_files = []
    for path in paths:
        if not path.is_file():
            missing_files.append(str(path))
            continue
        sections_by_path[path] = _read_sections(path)
    if FROZEN:
        # Editable roster files intentionally survive packaged upgrades. New
        # mandatory clone templates must still work when an older visible
        # roster predates them, so use bundled registrations/templates only as
        # an in-memory fallback. Existing visible sections remain authoritative.
        for name in ROSTER_FILENAMES:
            bundled_path = SOURCE_DIR / 'configs' / name
            if bundled_path.is_file():
                bundled_fallback_sections[bundled_path] = _read_sections(
                    bundled_path
                )
    if missing_files:
        raise FileNotFoundError(
            'Randomizer unit roster file(s) missing: ' + ', '.join(missing_files)
        )

    template_sections = {}
    registered_by_list = {}
    for path, sections in sections_by_path.items():
        section_names = {name.lower(): name for name in sections}
        for list_name in set(ROSTER_CATEGORIES.values()):
            actual = section_names.get(list_name.lower())
            registered_by_list.setdefault(list_name, set()).update(
                value.upper()
                for value in sections.get(actual, {}).values()
                if value
            )
        for section, values in sections.items():
            lowered = section.lower()
            if lowered in {name.lower() for name in ROSTER_CATEGORIES.values()}:
                continue
            if lowered in template_sections:
                raise ValueError(
                    f'Duplicate randomizer unit section [{section}] in {path}.'
                )
            template_sections[lowered] = (section, values)
    for sections in bundled_fallback_sections.values():
        section_names = {name.lower(): name for name in sections}
        for list_name in set(ROSTER_CATEGORIES.values()):
            actual = section_names.get(list_name.lower())
            registered_by_list.setdefault(list_name, set()).update(
                value.upper()
                for value in sections.get(actual, {}).values()
                if value
            )
        for section, values in sections.items():
            lowered = section.lower()
            if lowered in {name.lower() for name in ROSTER_CATEGORIES.values()}:
                continue
            template_sections.setdefault(lowered, (section, values))

    missing = []
    templates = {}
    clone_ids = {}
    for source_id, target in BUFF_TARGETS.items():
        list_name = ROSTER_CATEGORIES.get(target.get('category'))
        if not list_name:
            continue
        clone_id = randomizer_unit_id(source_id)
        template = template_sections.get(clone_id.lower())
        if (
            clone_id not in registered_by_list.get(list_name, set())
            or template is None
            or not template[1]
        ):
            missing.append(f'{source_id}->{clone_id}/{list_name}')
            continue
        clone_ids[source_id.upper()] = clone_id
        templates[source_id.upper()] = dict(template[1])
        templates[source_id.upper()].update(
            MANDATORY_TEMPLATE_OVERRIDES.get(source_id.upper(), {})
        )
    if missing:
        raise ValueError(
            'Randomizer roster lacks required TechnoTypes: ' + ', '.join(missing)
        )
    return paths, clone_ids, templates


def validate_randomizer_unit_roster():
    paths, clone_ids, templates = randomizer_unit_roster()
    return {
        'paths': [str(path) for path in paths],
        'files': len(paths),
        'types': len(clone_ids),
        'templates': len(templates),
    }


def validate_transport_buff_eligibility():
    """Audit IFV/OpenTopped reward invariants used by every selection UI."""
    from randomizer.maps.buff_values import _active_direct_buff_counts
    from randomizer.rewards.display import canonical_reward
    from randomizer.rewards.definitions import (
        EXISTING_OPEN_TOPPED_IDS,
        TRANSPORT_GUNNER_IDS,
        TRANSPORT_OPEN_TOPPED_BLOCKED_IDS,
        UNIT_BUFF_REWARDS,
    )

    _paths, _clone_ids, templates = randomizer_unit_roster()
    template_gunners = randomizer_unit_ids_with_behavior('Gunner', 'yes')
    reward_pairs = {
        (str(reward.get('unit', '')).upper(), reward.get('buff_type'))
        for reward in UNIT_BUFF_REWARDS
    }
    forced_runtime_rewards = [
        {
            '_runtime_canonical': True,
            'name': f'Forced {unit_id} {buff_type}',
            'kind': 'buff',
            'unit': unit_id,
            'buff_type': buff_type,
        }
        for unit_id in template_gunners
        for buff_type in ('passenger_capacity', 'open_topped')
    ] + [{
        '_runtime_canonical': True,
        'name': 'Forced Stallion open_topped',
        'kind': 'buff',
        'unit': 'SHAD',
        'buff_type': 'open_topped',
    }]
    forced_counts = _active_direct_buff_counts(
        forced_runtime_rewards,
        require_unlocked_access=False,
    )
    errors = []
    if forced_counts:
        errors.append(
            f'mandatory transport exclusions reached map buffs: {forced_counts}'
        )
    if template_gunners != TRANSPORT_GUNNER_IDS:
        errors.append(
            'Gunner=yes templates differ from transport-gunner exclusions'
        )
    for unit_id in template_gunners:
        for buff_type in ('passenger_capacity', 'open_topped'):
            if (unit_id, buff_type) in reward_pairs:
                errors.append(f'{unit_id} still offers {buff_type}')
            legacy = canonical_reward({
                'name': f'Legacy {unit_id} {buff_type}',
                'kind': 'buff',
                'unit': unit_id,
                'buff_type': buff_type,
            })
            if legacy.get('kind') != 'retired':
                errors.append(f'{unit_id} legacy {buff_type} remains active')
    if ('SHAD', 'passenger_capacity') not in reward_pairs:
        errors.append('Stallion lost passenger_capacity')
    if ('SHAD', 'open_topped') in reward_pairs:
        errors.append('Stallion still offers broken open_topped')
    legacy_stallion_open_top = canonical_reward({
        'name': 'Legacy Stallion Passenger Firing I',
        'kind': 'buff',
        'unit': 'SHAD',
        'buff_type': 'open_topped',
    })
    if legacy_stallion_open_top.get('kind') != 'retired':
        errors.append('Stallion legacy open_topped remains active')
    if 'SHAD' not in TRANSPORT_OPEN_TOPPED_BLOCKED_IDS:
        errors.append('Stallion is absent from mandatory OpenTopped exclusions')
    for unit_id in EXISTING_OPEN_TOPPED_IDS:
        template = templates.get(unit_id, {})
        open_topped = next(
            (
                value
                for key, value in template.items()
                if key.strip().lower() == 'opentopped'
            ),
            '',
        )
        if str(open_topped).strip().lower() != 'yes':
            errors.append(f'{unit_id} native OpenTopped=yes was not preserved')
        if (unit_id, 'open_topped') in reward_pairs:
            errors.append(f'{unit_id} offers redundant open_topped')
    if errors:
        raise ValueError('Transport buff eligibility failed: ' + '; '.join(errors))
    return {
        'gunner_ids': sorted(template_gunners),
        'stallion_capacity_enabled': True,
        'stallion_open_topped_excluded': True,
        'native_open_topped_ids': sorted(EXISTING_OPEN_TOPPED_IDS),
    }
