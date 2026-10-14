"""Install the generated tracker bundle into an Archipelago source WebHost."""

import argparse
import ast
from pathlib import Path
import shutil

MARKER = '# Mental Omega cameo tracker integration'
REGISTRATION = '''

# Mental Omega cameo tracker integration
from .mental_omega_tracker import render_mental_omega_tracker
_player_trackers["Mental Omega"] = render_mental_omega_tracker
'''


def install(bundle: Path, archipelago: Path):
    source = bundle / 'WebHostLib'
    target = archipelago.resolve() / 'WebHostLib'
    tracker = target / 'tracker.py'
    if not (source / 'mental_omega_tracker_data.json').is_file():
        raise ValueError('Build the bundle first; run install.py from the generated output.')
    original = tracker.read_text(encoding='utf-8')
    if '_player_trackers' not in original or 'def get_player_tracker(' not in original:
        raise ValueError('Unsupported WebHost tracker API; expected Archipelago 0.6.8.')
    updated = original if MARKER in original else original.rstrip() + REGISTRATION
    ast.parse(updated)
    for path in source.rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts:
            destination = target / path.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
    if updated != original:
        backup = tracker.with_name('tracker.py.before-mental-omega')
        if not backup.exists():
            shutil.copy2(tracker, backup)
        tracker.write_text(updated, encoding='utf-8')
    print(f'Installed into {target}. Restart the WebHost to enable the tracker.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archipelago', type=Path, help='Archipelago source checkout used by the WebHost')
    args = parser.parse_args()
    install(Path(__file__).resolve().parent, args.archipelago)
