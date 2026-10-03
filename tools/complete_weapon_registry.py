"""Complete weapon-only gunner entries in the committed stock weapon snapshot.

The original extractor followed Primary/Secondary mounts and their payloads.
WeaponCount units without those mounts must instead use WeaponN/EliteWeaponN.
Keep the existing payload graph and standard-mount reward scope unchanged.
Run against stock RULESMO.INI, never a submodded registry.
"""

import argparse
import ast
import base64
import json
from pathlib import Path
import re
import sys
import textwrap
import zlib


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from randomizer.maps.ini import all_section_value_maps_preserve
from randomizer.rewards.roster import randomizer_unit_template_values


def complete(data, sections, roster_ids, curated_ids=()):
    sections = {
        str(section).upper(): {str(k).lower(): v for k, v in values.items()}
        for section, values in sections.items()
    }
    numbered_by_unit = {}
    for unit_id, values in sections.items():
        weapons = tuple(dict.fromkeys(
            str(value).split(';', 1)[0].strip().upper()
            for key, value in values.items()
            if re.fullmatch(r'(?:elite)?weapon\d+', key)
        ))
        if weapons:
            numbered_by_unit[unit_id] = weapons
    added = []
    for unit_id in sorted(roster_ids):
        if data['direct'].get(unit_id) or unit_id in curated_ids:
            continue
        values = sections.get(unit_id, {})
        if str(values.get('gunner', 'no')).lower() != 'yes':
            continue
        if any(
            str(values.get(key, '')).lower() not in {'', 'none', '<none>'}
            for key in ('primary', 'secondary', 'eliteprimary', 'elitesecondary')
        ):
            continue
        weapons = [w for w in numbered_by_unit.get(unit_id, ()) if w in sections]
        if not weapons:
            continue
        data['direct'][unit_id] = weapons
        damage_weapons = []
        for weapon_id in weapons:
            values = sections[weapon_id]
            stats = [
                float(values[field]) if field in values else None
                for field in ('damage', 'rof', 'range')
            ]
            data['stats'][weapon_id] = stats
            if stats[0] is not None and stats[0] > 1:
                damage_weapons.append(weapon_id)
            users = set(data['users'].get(weapon_id, ()))
            users.update(
                source for source, mounts in numbered_by_unit.items()
                if weapon_id in mounts
            )
            data['users'][weapon_id] = sorted(users)
        data['damage'][unit_id] = damage_weapons
        added.append(unit_id)
    return added


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rules', type=Path, default=(
        ROOT.parent / 'RandomizerLauncherData/cameo_cache/rulesmo.ini'
    ))
    args = parser.parse_args()
    path = ROOT / 'randomizer/rewards/weapon_stats_data.py'
    source = path.read_text(encoding='utf-8')
    tree = ast.parse(source)
    encoded = next(
        ast.literal_eval(node.value) for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == '_ENCODED' for t in node.targets)
    )
    data = json.loads(zlib.decompress(base64.b85decode(encoded)))
    unit_data = json.loads((ROOT / 'configs/rewards/unit_data.json').read_text())['sections']
    curated_ids = {
        unit_id for unit_id, target in unit_data['buff_targets'].items()
        if target.get('weapons')
    }
    added = complete(
        data, all_section_value_maps_preserve(args.rules.read_text().splitlines()),
        randomizer_unit_template_values(), curated_ids,
    )
    if added:
        packed = base64.b85encode(zlib.compress(
            json.dumps(data, separators=(',', ':')).encode('utf-8'), 9
        )).decode('ascii')
        payload = '_ENCODED = (\n' + ''.join(
            f'    {line!r}\n' for line in textwrap.wrap(
                packed, 100, break_on_hyphens=False
            )
        ) + ')\n'
        start = source.index('_ENCODED = (')
        end = source.index('_DATA = ', start)
        path.write_text(source[:start] + payload + source[end:], encoding='utf-8')
    print('Completed numbered weapon mounts: ' + ', '.join(added or ['none']))


if __name__ == '__main__':
    main()
