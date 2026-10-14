"""Render an explicitly labeled offline design preview of the exported tracker."""

import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


def preview(bundle):
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    webhost = bundle / 'WebHostLib'
    spec = importlib.util.spec_from_file_location('mental_omega_preview', webhost / 'mental_omega_tracker.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = json.loads((webhost / 'mental_omega_tracker_data.json').read_text(encoding='utf-8'))
    inventory = Counter()
    # Design sample: access, combined buffs, capped stacks, locked cards and powers.
    for key in ['unit:E1', 'unit:E2', 'power:NukeSpecial']:
        entity = data['entities'].get(key, {})
        for identity in entity.get('items', []):
            row = data['items'][str(identity)]
            if not row['buff']:
                inventory[identity] = 1
            elif row['buff_type'] in {'health', 'armor', 'damage'}:
                inventory[identity] = min(3, row['maximum'])
    guardian = data['entities'].get('unit:GGI', {})
    for identity in guardian.get('items', []):
        if data['items'][str(identity)]['buff_type'] == 'health':
            inventory[identity] = 2
    slot = {'progression_mode': 'Campaign', 'locations': {'ALL01': {'victory': [1, 2]}},
            'mission_order': ['ALL01']}
    view = module.tracker_view(slot, inventory, {1: (), 2: ()}, {1}, {},
                               {1: 'Allied 01: RED DAWN RISING - Mission Complete - Reward 1',
                                2: 'Allied 01: RED DAWN RISING - Mission Complete - Reward 2'}, data)
    environment = Environment(loader=FileSystemLoader(webhost / 'templates'), autoescape=select_autoescape(['html']))

    def url_for(endpoint, **arguments):
        if endpoint == 'static':
            return 'WebHostLib/static/' + arguments['filename']
        return '#offline-preview'

    html = environment.get_template('tracker__MentalOmega.html').render(
        **view, url_for=url_for, room=SimpleNamespace(tracker='offline-preview'), team=0,
        player=1, player_name='Offline design preview (sample inventory)',
        saving_second=0, game_finished=False, progression_mode='Preview: sample inventory')
    # Offline preview has no room to poll. Keep all filtering interactions active.
    html = html.replace('id="omega-tracker"', 'id="omega-tracker" data-offline="true"')
    output = bundle / 'preview.html'
    output.write_text(html, encoding='utf-8')
    print(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    preview(args.bundle.resolve())
