"""Resolve native challenge modes and option controls into map/spawn values."""

from __future__ import annotations

from pathlib import Path

from randomizer.challenges.catalogue import CHALLENGE_MODES, catalogue_sections
from randomizer.coop.compatibility import resolve_path
from randomizer.maps.ini import all_section_value_maps_preserve, merge_ini_section_values


_DIFFICULTIES = {'easy': 0, 'normal': 1, 'hard': 2}
_TRUE = {'true', 'yes', '1'}
_FALSE = {'false', 'no', '0'}


def mode_name(difficulty: str | int) -> str:
    if isinstance(difficulty, str):
        difficulty = _DIFFICULTIES.get(difficulty.casefold(), -1)
    if type(difficulty) is not int or difficulty not in range(3):
        raise ValueError('Challenge difficulty must be easy, normal, hard, or 0–2.')
    return CHALLENGE_MODES[difficulty]


def _boolean(value: str, label: str) -> bool:
    text = str(value).strip().casefold()
    if text not in _TRUE | _FALSE:
        raise ValueError(f'Invalid native challenge boolean for {label}.')
    return text in _TRUE


def _sections(path: Path):
    # Preserve actual engine key spelling when applying map code.
    return all_section_value_maps_preserve(path.read_bytes().decode('latin-1').splitlines())


def _controls(game_root: Path) -> dict:
    return {
        section.casefold(): {key.casefold(): value.split(';', 1)[0].strip()
                             for key, value in values.items()
                             if not key.lstrip().startswith(';')}
        for section, values in _sections(resolve_path(game_root, 'Resources/GameOptions.ini')).items()
    }


def _code_path(game_root: Path, value: str) -> Path:
    path = resolve_path(game_root, value)
    if not path.is_file():
        # The native mode catalogue retains INI\Challenge *.ini while the
        # shipped files live in INI\Map Code. Match the client's mode layout.
        name = str(value).replace('\\', '/').rsplit('/', 1)[-1]
        path = resolve_path(game_root, f'INI/Map Code/{name}')
    if not path.is_file():
        raise FileNotFoundError(f'Missing native challenge rule file: {value}')
    return path


def _resolved_options(game_root: Path, metadata: dict, difficulty):
    sections = catalogue_sections(game_root)
    name = mode_name(difficulty)
    mode = sections.get(name.casefold())
    if not mode or not mode.get('custominipath'):
        raise ValueError(f'Installed client has no native {name} rules.')
    controls = _controls(game_root)
    lobby = controls.get('multiplayergamelobby', {})
    names = [value.strip().casefold() for key in ('checkboxes', 'dropdowns')
             for value in lobby.get(key, '').split(',') if value.strip()]
    choices = {}
    for control_name in names:
        control = controls.get(control_name)
        if control is None:
            raise ValueError(f'Missing native game-option control: {control_name}.')
        if control_name.startswith('chk'):
            choices[control_name] = control.get('checked', 'false')
        else:
            choices[control_name] = control.get('defaultindex', '0')
    # The map is allowed to override a game-mode restriction, exactly as in
    # the native lobby (e.g. Freedom forces the Naval Combat map code on).
    for owner in (mode, metadata):
        forced = owner.get('forcedoptions', '')
        if forced:
            values = sections.get(forced.casefold())
            if values is None:
                raise ValueError(f'Missing native forced-options section: {forced}.')
            choices.update(values)
    return sections, name, mode, controls, choices


def spawn_settings(game_root: Path, metadata: dict, difficulty) -> dict[str, str]:
    """Translate UI control values, including dropdown indexes, to spawn.ini."""
    sections, name, mode, controls, choices = _resolved_options(game_root, metadata, difficulty)
    result = {'UIGameMode': name}
    for control_name, selection in choices.items():
        control = controls.get(control_name, {})
        option = control.get('spawninioption')
        if not option:
            continue
        if control_name.startswith('chk'):
            value = _boolean(selection, control_name)
            if _boolean(control.get('reversed', 'false'), control_name):
                value = not value
            result[option] = 'Yes' if value else 'No'
        else:
            try:
                index = int(selection)
                items = control.get('items', '').split(',')
                if not 0 <= index < len(items):
                    raise ValueError
            except (TypeError, ValueError) as exc:
                raise ValueError(f'Invalid native challenge dropdown: {control_name}.') from exc
            write_mode = control.get('datawritemode', 'index').casefold()
            if write_mode == 'string':
                result[option] = items[index].strip()
            elif write_mode == 'index':
                result[option] = str(index)
    # Controls always define these in the installed client. Add no speculative
    # engine defaults: malformed metadata must be reported instead.
    result.update({key: value for key, value in _sections(
        resolve_path(game_root, 'Resources/GameOptions.ini')
    ).get('ForcedSpawnIniOptions', {}).items()})
    for section_name in (name + 'ForcedSpawnIniOptions', mode.get('forcedspawninioptions', ''),
                         metadata.get('forcedspawninioptions', '')):
        if section_name:
            for key, value in sections.get(section_name.casefold(), {}).items():
                # Reuse the control's spelling where one exists.
                spelling = next((existing for existing in result if existing.casefold() == key), key)
                result[spelling] = value
    if 'unitcount' in metadata:
        result['UnitCount'] = metadata['unitcount']
    return result


def apply_mode_rules(game_root: Path, source_bytes: bytes, metadata: dict, difficulty) -> bytes:
    """Merge difficulty first, then enabled native option map-code files."""
    _sections_by_name, _name, mode, controls, choices = _resolved_options(
        game_root, metadata, difficulty
    )
    paths = [_code_path(game_root, mode['custominipath'])]
    if metadata.get('custominipath'):
        paths.append(_code_path(game_root, metadata['custominipath']))
    for control_name, selection in choices.items():
        control = controls.get(control_name, {})
        if control_name.startswith('chk'):
            if control.get('custominipath') and _boolean(selection, control_name):
                paths.append(_code_path(game_root, control['custominipath']))
        elif control.get('datawritemode', '').casefold() == 'mapcode':
            try:
                items = control.get('items', '').split(',')
                index = int(selection)
                if not 0 <= index < len(items):
                    raise ValueError
            except (ValueError, TypeError) as exc:
                raise ValueError(f'Invalid native challenge map-code dropdown: {control_name}.') from exc
            paths.append(_code_path(game_root, items[index].strip()))
    lines = source_bytes.decode('latin-1').splitlines()
    for path in paths:
        merge_ini_section_values(lines, _sections(path))
    return ('\r\n'.join(lines) + '\r\n').encode('latin-1')
