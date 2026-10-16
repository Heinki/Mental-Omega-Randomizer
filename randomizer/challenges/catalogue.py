"""The installed client's registered one- or two-human challenge catalogue."""

from __future__ import annotations

from pathlib import Path
import re

from randomizer.coop.compatibility import resolve_path
from randomizer.maps.ini import all_section_value_maps
from randomizer.missions.catalogue import BASE_BUILD, normalize_long_description


SIDE_COUNTRIES = (
    'UnitedStates', 'Europeans', 'Pacific', 'USSR', 'Latin', 'Chinese',
    'PsiCorps', 'ScorpionCell', 'Headquaters', 'Guild1', 'Guild2', 'Guild3',
)
SIDE_FAMILIES = ('allies',) * 3 + ('soviets',) * 3 + ('epsilon',) * 3 + ('foehn',) * 3
COUNTRY_LABELS = dict(zip(SIDE_COUNTRIES, (
    'United States', 'Euro Alliance', 'Pacific Front', 'Russia', 'Confederation',
    'China', 'PsiCorps', 'Scorpion Cell', 'Epsilon HQ', 'Haihead', 'Coronia',
    'Last Bastion',
)))
FAMILY_LABELS = {'allies': 'Allies', 'soviets': 'Soviets',
                 'epsilon': 'Epsilon', 'foehn': 'Foehn'}
CHALLENGE_MODES = ('Challenge Easy', 'Challenge Medium', 'Challenge Hard')
CATALOGUE_PATH = 'INI/MentalOmegaMaps.ini'
_REGISTERED = re.compile(r'MapsMO[\\/]Challenge[\\/](c_[a-z0-9_]+)\Z', re.I)


def catalogue_sections(game_root: Path) -> dict[str, dict[str, str]]:
    """Read native metadata without ConfigParser's duplicate/list rewriting."""
    path = resolve_path(game_root, CATALOGUE_PATH)
    return {
        name.casefold(): {
            key.casefold(): value.split(';', 1)[0].strip()
            for key, value in values.items() if not key.lstrip().startswith(';')
        }
        for name, values in all_section_value_maps(
            path.read_bytes().decode('latin-1').splitlines()
        ).items()
    }


def _integers(metadata: dict, key: str, maximum: int) -> set[int]:
    result = set()
    for token in str(metadata.get(key, '')).split(','):
        if not token.strip():
            continue
        try:
            value = int(token.strip())
        except ValueError as exc:
            raise ValueError(f'Invalid challenge {key}: {token!r}.') from exc
        if not 0 <= value <= maximum:
            raise ValueError(f'Challenge {key} is outside 0–{maximum}.')
        result.add(value)
    return result


def enemy_houses(metadata: dict) -> list[tuple[int, int, int]]:
    """Return country, color, and authored waypoint/house slot in native order."""
    result = []
    slots = set()
    keys = sorted((key for key in metadata if re.fullmatch(r'enemyhouse\d+', key)),
                  key=lambda key: int(key[len('enemyhouse'):]))
    for key in keys:
        try:
            country, color, slot = (int(token.strip()) for token in metadata[key].split(','))
        except (ValueError, TypeError) as exc:
            raise ValueError(f'Invalid challenge {key}.') from exc
        if not 0 <= country < len(SIDE_COUNTRIES) or not 0 <= color <= 12:
            raise ValueError(f'Invalid challenge country or color in {key}.')
        if not 2 <= slot <= 7 or slot in slots:
            raise ValueError(f'Invalid or repeated challenge enemy slot in {key}.')
        result.append((country, color, slot))
        slots.add(slot)
    if not result:
        raise ValueError('Challenge map has no registered enemy houses.')
    return result


def allowed_countries(metadata: dict) -> tuple[str, ...]:
    """Protect country-scoped rewards from also affecting an enemy army."""
    denied = _integers(metadata, 'disallowedplayersides', len(SIDE_COUNTRIES) - 1)
    denied.update(country for country, _color, _slot in enemy_houses(metadata))
    return tuple(country for index, country in enumerate(SIDE_COUNTRIES) if index not in denied)


def allowed_colors(metadata: dict) -> tuple[int, ...]:
    denied = _integers(metadata, 'disallowedplayercolors', 12)
    return tuple(index for index in range(13) if index not in denied)


def _validate_metadata(metadata: dict) -> None:
    if metadata.get('iscoopmission', '').casefold() not in {'true', 'yes', '1'}:
        raise ValueError('Selected map is not registered as a challenge mission.')
    if metadata.get('minplayers') != '1' or metadata.get('maxplayers') != '2':
        raise ValueError('Challenges require native one- or two-player registration.')
    modes = {value.strip().casefold() for value in metadata.get('gamemodes', '').split(',')}
    if any(mode.casefold() not in modes for mode in CHALLENGE_MODES):
        raise ValueError('Challenge map is missing a registered difficulty mode.')
    if metadata.get('unitcount', '0') != '0':
        raise ValueError('Challenge map must use its authored starting units.')
    if len(allowed_colors(metadata)) < 2 or not allowed_countries(metadata):
        raise ValueError('Challenge map has no safe player country or colors.')
    for waypoint in ('waypoint0', 'waypoint1'):
        if not metadata.get(waypoint, '').isdigit():
            raise ValueError(f'Challenge map is missing native {waypoint}.')


def _name(map_name: str) -> str:
    name = str(map_name)
    if name.casefold().endswith('.map'):
        name = name[:-4]
    if not re.fullmatch(r'c_[a-z0-9_]+', name, re.I):
        raise ValueError('Challenge map must be an installed c_*.map name.')
    return name.casefold()


def map_config(game_root: Path, map_name: str, player_country: str | None = None):
    """Return the same source/key/metadata/country/family tuple as co-op."""
    name = _name(map_name)
    source = resolve_path(game_root, f'MapsMO/Challenge/{name}.map')
    if not source.is_file():
        raise FileNotFoundError(source)
    source_key = f'MapsMO\\Challenge\\{name}'
    metadata = catalogue_sections(game_root).get(source_key.casefold())
    if metadata is None:
        raise ValueError(f'Challenge map {name} is not registered by the installed client.')
    _validate_metadata(metadata)
    available = allowed_countries(metadata)
    country = player_country or available[0]
    if country not in available:
        label = COUNTRY_LABELS.get(country, str(country))
        raise ValueError(f'{label} is restricted or used by an enemy in this challenge.')
    return source, source_key, metadata, country, SIDE_FAMILIES[SIDE_COUNTRIES.index(country)]


def discover_challenge_missions(game_root: Path, player_country: str | None = None, *,
                                country: str | None = None, player_count: int = 1) -> list[dict]:
    """Discover registered stock challenges, optionally for one selected country."""
    if player_count not in (1, 2):
        raise ValueError('Challenges support one or two human players.')
    selected = player_country or country
    if selected and selected not in SIDE_COUNTRIES:
        raise ValueError('Unknown challenge player country.')
    missions = []
    for section, metadata in catalogue_sections(game_root).items():
        match = _REGISTERED.fullmatch(section)
        if not match:
            continue
        name = match.group(1).casefold()
        source = resolve_path(game_root, f'MapsMO/Challenge/{name}.map')
        if not source.is_file():
            continue
        _validate_metadata(metadata)
        available = allowed_countries(metadata)
        if selected and selected not in available:
            continue
        chosen = selected or available[0]
        family = SIDE_FAMILIES[SIDE_COUNTRIES.index(chosen)]
        enemies = enemy_houses(metadata)
        missions.append({
            'index': len(missions) + 1,
            'code': name.upper(), 'challenge_name': name, 'coop_name': name,
            'mission_category': 'challenge', 'scenario': source.name,
            'title': metadata.get('description') or metadata.get('name') or name,
            'side': FAMILY_LABELS[family], 'player_country': chosen,
            'player_side': SIDE_COUNTRIES.index(chosen),
            'allowed_countries': list(available), 'reward_safe_countries': list(available),
            'allowed_colors': list(allowed_colors(metadata)),
            'enemy_houses': enemies, 'enemy_count': len(enemies),
            'min_players': 1, 'max_players': 2,
            'briefing': normalize_long_description(metadata.get('briefing', '')),
            'objectives': [], 'objective_count': 1,
            'build_classification': BASE_BUILD, 'no_build': False,
            'true_no_build': False, 'no_build_production': False,
            'operation': False, 'reward_class': 'act_1', 'reward_multiplier': 1,
        })
    return missions
