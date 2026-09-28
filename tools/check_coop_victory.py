"""Check co-op win hooks and host log detection without winning a full map."""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from randomizer.application import coop_controller
from randomizer.coop.catalogue import discover_coop_missions
from randomizer.coop.prototype import build_manifest
from randomizer.coop.victory import victory_marker_name
from randomizer.core.paths import GAME_ROOT
from randomizer.maps.ini import parse_action_groups, section_value_map_preserve


def main():
    missions = discover_coop_missions(GAME_ROOT)
    for mission in missions:
        state = {
            'seed': 'COOP-WIN-CHECK', 'progression_mode': 'Grid Mode',
            'reward_mode': 'Chaos', 'coop_mode': True, 'starting_rewards': [],
            'mission_order': [mission['code']], 'mission_checks': {},
        }
        manifest, data = build_manifest(
            GAME_ROOT, state, mission['coop_name'], unit_id='FV', allow_test_unit=True,
        )
        assert manifest['schema'] == 4
        lines = data.decode('latin-1').splitlines()
        marker = victory_marker_name(mission['coop_name'])
        assert marker in data.decode('latin-1')
        win_actions = 0
        for value in section_value_map_preserve(lines, 'Actions').values():
            _, groups = parse_action_groups(value)
            codes = [group[0] for group in groups]
            if '2' in codes:
                assert '4' in codes[:codes.index('2')], mission['code']
                win_actions += 1
        assert win_actions >= 1, mission['code']

    class Watcher(coop_controller.CoopController):
        def __init__(self, marker, offset):
            self._coop_victory_watch = {
                'code': 'COOP_STHUNDER', 'marker': marker,
                'offset': offset, 'detected': False,
                'file_id': (log.stat().st_dev, log.stat().st_ino),
                'anchor': log.read_bytes()[max(0, offset - 64):offset],
            }
            self.completed = False
            self.unlocks = []

        def append_log(self, message, error=False):
            pass

        def is_mission_complete(self, code):
            return self.completed

        def unlock_mission_check(self, code, check_id, source):
            self.unlocks.append((code, check_id, source))
            self.completed = True

    with TemporaryDirectory() as temporary:
        log = Path(temporary) / 'debug.log'
        marker = victory_marker_name('coop_sthunder')
        log.write_text(f'old session {marker}\n', encoding='utf-8')
        original = coop_controller.DEBUG_LOG
        coop_controller.DEBUG_LOG = log
        try:
            watcher = Watcher(marker, log.stat().st_size)
            log.write_text(log.read_text() + 'Capture_Mouse()\n', encoding='utf-8')
            watcher._scan_coop_victory()
            assert not watcher.unlocks
            log.write_text(log.read_text() + f'TeamType Name={marker}\n', encoding='utf-8')
            watcher._scan_coop_victory()
            watcher._scan_coop_victory()
            assert watcher.unlocks == [
                ('COOP_STHUNDER', 'victory', 'Co-op in-game victory')
            ]
            # A new game may truncate and regrow debug.log before the next
            # watcher poll. Its old byte offset must not hide the new marker.
            log.write_text('previous game output\n' * 100, encoding='utf-8')
            rotated = Watcher(marker, log.stat().st_size)
            log.write_text('Capture_Mouse()\n'
                           f"Creating a new team named '{marker}'.\n",
                           encoding='utf-8')
            rotated._scan_coop_victory()
            assert rotated.unlocks == [
                ('COOP_STHUNDER', 'victory', 'Co-op in-game victory')
            ]
            # Even if the rewritten log regrows past old offset, its tail
            # anchor differs and the watcher scans from the beginning.
            log.write_text('previous game output\n' * 100, encoding='utf-8')
            regrown = Watcher(marker, log.stat().st_size)
            log.write_text('Capture_Mouse()\n'
                           f"Creating a new team named '{marker}'.\n"
                           + 'new game output\n' * 150, encoding='utf-8')
            regrown._scan_coop_victory()
            assert regrown.unlocks == [
                ('COOP_STHUNDER', 'victory', 'Co-op in-game victory')
            ]
        finally:
            coop_controller.DEBUG_LOG = original
    print(f'{len(missions)} win-marked maps; host log detection and deduplication passed')


if __name__ == '__main__':
    main()
