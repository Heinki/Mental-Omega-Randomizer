"""Static player-owned TechnoType roster loading and validation."""

from __future__ import annotations

import shutil
from functools import lru_cache
from pathlib import Path

from randomizer_paths import APP_DIR, FROZEN, SOURCE_DIR


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


@lru_cache(maxsize=1)
def randomizer_unit_roster():
    from randomizer_rewards import BUFF_TARGETS

    paths = _active_roster_paths()
    sections_by_path = {}
    missing_files = []
    for path in paths:
        if not path.is_file():
            missing_files.append(str(path))
            continue
        sections_by_path[path] = _read_sections(path)
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
