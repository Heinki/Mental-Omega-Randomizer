"""Validated native challenge context shared by manifest build and replay."""

import hashlib
import json

from randomizer.challenges.catalogue import allowed_colors, map_config
from randomizer.challenges.native import apply_mode_rules, spawn_settings


CHALLENGE_MARKER = 'MOR_CHALLENGE_V1'


def challenge_context(game_root, name, country, player_count, difficulty, game_speed=2,
                      *, guest_country=None, player_colors=None, ai_teammate=None):
    """Bind humans, an optional local AI, speed, and native rules to identity."""
    if type(player_count) is not int or player_count not in (1, 2):
        raise ValueError('Challenges support one or two human players.')
    if type(game_speed) is not int or game_speed not in range(7):
        raise ValueError('Game speed must be between 0 and 6.')
    config = map_config(game_root, name, player_country=country or None)
    metadata = config[2]
    if ai_teammate is not None:
        if player_count != 1:
            raise ValueError('An AI teammate requires one local human player.')
        if (not isinstance(ai_teammate, dict)
                or set(ai_teammate) != {'country', 'color', 'difficulty'}
                or not isinstance(ai_teammate['country'], str)
                or not ai_teammate['country']
                or type(ai_teammate['color']) is not int
                or type(ai_teammate['difficulty']) is not int
                or ai_teammate['difficulty'] not in range(3)):
            raise ValueError('Choose an AI house, color, and difficulty (0–2).')
        # The native AI keeps its original army. It must still avoid enemy
        # countries: enemy reward overrides are scoped to those identities.
        map_config(game_root, name, player_country=ai_teammate['country'])
        if ai_teammate['color'] not in allowed_colors(metadata):
            raise ValueError('Choose an AI color allowed by this challenge.')
    participants = player_count + (ai_teammate is not None)
    if not int(metadata.get('minplayers', '1')) <= participants <= int(metadata.get('maxplayers', '2')):
        raise ValueError('This challenge requires a second human or an AI teammate.')
    settings = spawn_settings(game_root, metadata, difficulty)
    # The explicit launcher choice replaces the native lobby's speed cap.
    settings['GameSpeed'] = str(game_speed)
    # Resolve the same native patches independently on each machine. Their
    # effective INI rules participate in identity before either game starts.
    rules = apply_mode_rules(game_root, b'', metadata, difficulty)
    fields = {
        'mission_category': 'challenge', 'player_count': player_count,
        'game_speed': game_speed,
        'native_settings': settings,
        'native_rules_sha256': hashlib.sha256(rules).hexdigest(),
        'native_metadata_sha256': hashlib.sha256(json.dumps(
            metadata, sort_keys=True, separators=(',', ':'),
        ).encode('utf-8')).hexdigest(),
    }
    if guest_country is not None or player_colors is not None or ai_teammate is not None:
        if player_count == 1 and guest_country:
            raise ValueError('Solo challenges cannot select a guest country.')
        if player_count == 2:
            guest_country = guest_country or config[3]
            # Reuse the same catalogue validation, including enemy ownership.
            map_config(game_root, name, player_country=guest_country)
            fields['guest_country'] = guest_country
            settings['DisableGameSpeed'] = 'Yes'
        available = allowed_colors(metadata)
        default_colors = [color for color in available
                          if ai_teammate is None or color != ai_teammate['color']]
        colors = default_colors[:player_count] if player_colors is None else player_colors
        if (not isinstance(colors, (tuple, list)) or len(colors) != player_count
                or any(type(color) is not int or color not in available for color in colors)
                or len(set(colors)) != player_count):
            raise ValueError('Choose distinct player colors allowed by this challenge.')
        fields['player_colors'] = list(colors)
        if ai_teammate is not None:
            if ai_teammate['color'] in colors:
                raise ValueError('Choose distinct human and AI teammate colors.')
            fields['ai_teammate'] = dict(ai_teammate)
    return config, fields


def identity_fields(context, difficulty):
    fields = [context['mission_category'], context['player_count'],
            context['native_settings'], context['native_rules_sha256'],
            context['native_metadata_sha256'], difficulty]
    if 'player_colors' in context:
        fields.append({key: context[key] for key in (
            'guest_country', 'player_colors', 'player_loadouts', 'ai_teammate',
        ) if key in context})
    return fields


def destination(name, identity):
    stem = f'morch_{name.removeprefix("c_").lower()}_{identity}'
    return stem, f'MapsMO\\Challenge\\{stem}'


def validate_context(game_root, manifest):
    if manifest.get('schema') not in (6, 7, 8) or manifest.get('marker') != CHALLENGE_MARKER:
        raise ValueError('Unsupported challenge manifest. Update both launchers.')
    name = str(manifest.get('source_key', '')).rsplit('\\', 1)[-1]
    selections = {}
    if manifest['schema'] in (7, 8):
        if 'player_colors' not in manifest or (manifest.get('player_count') == 2
                and not manifest.get('guest_country')):
            raise ValueError('Challenge player houses or colors are missing.')
        selections = {'guest_country': manifest.get('guest_country', ''),
                      'player_colors': manifest['player_colors']}
    elif any(key in manifest for key in ('guest_country', 'player_colors', 'player_loadouts')):
        raise ValueError('Legacy challenge manifests cannot select separate player houses.')
    if manifest['schema'] == 8:
        if not isinstance(manifest.get('ai_teammate'), dict):
            raise ValueError('Local AI challenge settings are missing.')
        selections['ai_teammate'] = manifest['ai_teammate']
    elif 'ai_teammate' in manifest:
        raise ValueError('Legacy challenge manifests cannot select an AI teammate.')
    config, fields = challenge_context(
        game_root, name, manifest.get('player_country'),
        manifest.get('player_count'), manifest.get('difficulty', 1),
        manifest.get('game_speed', 2),
        **selections,
    )
    if 'game_speed' not in manifest:
        # Existing 1.43.1 manifests bind the native speed in their settings,
        # without a separate selected-speed field. Preserve their identity.
        fields.pop('game_speed')
        fields['native_settings'] = spawn_settings(
            game_root, config[2], manifest.get('difficulty', 1),
        )
    if any(manifest.get(key) != value for key, value in fields.items()):
        raise ValueError('Challenge players, game speed, or native rules differ from host settings.')
    return config, fields
