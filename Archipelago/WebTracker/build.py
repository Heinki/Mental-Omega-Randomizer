"""Export launcher presentation data and cameos for an Archipelago WebHost."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import shutil
import sys

SOURCE = Path(__file__).resolve().parent
PROJECT = SOURCE.parents[1]


def build(output: Path, *, images=True):
    sys.path.insert(0, str(PROJECT))
    from randomizer.rewards.catalogue import (
        ALWAYS_AVAILABLE_TECH_IDS, BUFF_TARGETS, REWARD_BY_NAME,
        buff_effect_lines, buff_stack_limit, house_wide_buff_scope,
        reward_display_name, reward_rule_summary,
    )
    from randomizer.rewards.rules import tech_ids_for_rewards
    from randomizer.config.tuning import stacking_multiplier

    catalogue = json.loads((PROJECT / 'Archipelago/APWorld/mental_omega/catalogue.json').read_text())
    output = output.resolve()
    if output == SOURCE or SOURCE in output.parents:
        raise ValueError('Choose an output directory outside WebTracker sources.')
    webhost = output / 'WebHostLib'
    for path in (SOURCE / 'WebHostLib').rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts:
            target = webhost / path.relative_to(SOURCE / 'WebHostLib')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)

    entities = {}
    items = {}
    categories = {'infantry': 'Infantry', 'units': 'Vehicles / Naval',
                  'aircraft': 'Aircraft', 'defenses': 'Defenses',
                  'buildings': 'Buildings', 'special_buildings': 'Special Buildings'}
    image_sources = {}
    powers = {reward['superweapon']: reward for reward in REWARD_BY_NAME.values()
              if reward.get('kind') == 'superweapon' and reward.get('superweapon')}
    for item in catalogue['items']:
        reward = REWARD_BY_NAME[item['name']]
        buff = reward.get('kind') == 'buff'
        power = reward.get('superweapon')
        power_reward = powers.get(power, reward)
        unit = reward.get('unit')
        if reward.get('enemy_reward') or house_wide_buff_scope(reward) or reward.get('buff_type') == 'starting_credits':
            keys = [f"global:{item['id']}"]
        elif power:
            keys = [f'power:{power}']
        elif buff and unit:
            keys = [f'unit:{unit}']
        else:
            keys = [f'unit:{tech}' for tech in sorted(tech_ids_for_rewards([reward]))]
            keys = keys or [f"global:{item['id']}"]
        maximum = buff_stack_limit(reward) if buff else 1
        items[str(item['id'])] = {
            'name': item['name'], 'label': reward_display_name(reward),
            'description': reward.get('description', ''),
            'buff': buff, 'buff_type': reward.get('buff_type') or reward.get('power_buff_type'),
            'maximum': maximum, 'entities': keys,
            'effects': [buff_effect_lines(reward, count=count) for count in range(maximum + 1)]
                       if buff else [[], reward_rule_summary(reward)],
        }
        for key in keys:
            target = BUFF_TARGETS.get(key.split(':', 1)[1], {}) if key.startswith('unit:') else {}
            factions = target.get('factions') or reward.get('factions') or ['Global']
            entity = entities.setdefault(key, {
                'label': target.get('label') or (reward_display_name(power_reward) if power else reward_display_name(reward)),
                'faction': factions[0] if len(factions) == 1 else 'Global',
                'category': 'Special' if target.get('special_reward') else categories.get(target.get('category'), 'Powers' if power else 'Bonuses'),
                'items': [], 'image': None,
                'always_available': key.startswith('unit:') and key[5:] in ALWAYS_AVAILABLE_TECH_IDS,
                'base_stats': [],
            })
            entity['items'].append(item['id'])
            if target and not entity['base_stats']:
                entity['base_stats'] = [f'{label}: {target[field]:g}{suffix}'
                    for field, label, suffix in [('cost', 'Cost', ' credits'), ('strength', 'Health', ' HP'),
                                                ('speed', 'Speed', ''), ('sight', 'Vision', ' cells')]
                    if isinstance(target.get(field), (int, float))]
                for weapon, stats in target.get('weapons', {}).items():
                    entity['base_stats'].append(f"{weapon}: " + ', '.join(
                        f'{label} {stats[field]:g}' for field, label in [('damage', 'damage'), ('range', 'range'), ('rof', 'reload frames')]
                        if isinstance(stats.get(field), (int, float))))
                entity['strength'] = target.get('strength')
            if key.startswith('unit:'):
                image_sources[key] = ('unit', key[5:])
            elif key.startswith('power:'):
                image_sources[key] = ('asset', power_reward['superweapon_sidebar_image']) if power_reward.get('superweapon_sidebar_image') else ('power', str(power_reward.get('cameo_superweapon') or power).upper())

    missing = []
    if images:
        from randomizer.ui.cameos import ensure_unit_cameos, ensure_superweapon_cameos
        from randomizer.maps.assets import custom_sidebar_preview
        sources = defaultdict(set)
        for kind, identity in image_sources.values():
            sources[kind].add(identity)
        paths = {('unit', key): path for key, path in ensure_unit_cameos(sources['unit'], synchronous=True).items()}
        overrides = {str(reward.get('cameo_superweapon') or identity).upper():
                     (reward.get('superweapon_rules') or {}).get('SidebarPCX', '')
                     for identity, reward in powers.items()}
        paths.update({('power', key): path for key, path in ensure_superweapon_cameos(sources['power'], overrides, synchronous=True).items()})
        paths.update({('asset', key): custom_sidebar_preview(key) for key in sources['asset']})
        image_dir = webhost / 'static/assets/mentalOmegaTracker'
        image_dir.mkdir(parents=True, exist_ok=True)
        for key, source in sorted(image_sources.items()):
            path = paths.get(source)
            if path and path.is_file():
                filename = key.replace(':', '-') + '.png'
                shutil.copy2(path, image_dir / filename)
                entities[key]['image'] = filename
            else:
                missing.append(key)
    data = {'schema_version': 1, 'catalogue_checksum': catalogue['catalogue_checksum'],
            'items': items, 'entities': entities,
            'health_multipliers': [stacking_multiplier('health', count) for count in range(101)],
            'armor_multipliers': [stacking_multiplier('armor', count) for count in range(101)]}
    (webhost / 'mental_omega_tracker_data.json').write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    (output / 'missing-cameos.json').write_text(json.dumps(missing, indent=2) + '\n')
    shutil.copy2(SOURCE / 'install.py', output / 'install.py')
    shutil.copy2(SOURCE / 'preview.py', output / 'preview.py')
    shutil.copy2(SOURCE / 'README.md', output / 'README.md')
    print(f'{output}: {len(items)} rewards, {len(entities)} cards, {sum(bool(e["image"]) for e in entities.values())} cameos, {len(missing)} missing cameos')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=PROJECT / 'build/mental-omega-webtracker')
    parser.add_argument('--no-images', action='store_true', help='Build metadata and placeholders without an installed game.')
    args = parser.parse_args()
    build(args.output, images=not args.no_images)


if __name__ == '__main__':
    main()
