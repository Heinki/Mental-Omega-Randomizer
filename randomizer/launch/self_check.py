"""Regression checks for the process boundary, also runnable inside the EXE."""

import io
import json
import os
from pathlib import Path, PureWindowsPath
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from randomizer.application import launch_controller as launch
from randomizer.maps.nanofiber import (
    nanofiber_clone_rules,
    player_can_use_nanofiber,
)


FLAGS = ['-SPAWN', '-CD', '-SPEEDCONTROL', '-LOG']


class LaunchCommandTests(unittest.TestCase):
    def controller(self):
        controller = launch.LaunchController()
        controller.state = None
        for name in (
            'append_log', 'after', 'poll_hook_log', 'cleanup_generated_root_maps',
            'disable_generated_rules_for_client', 'finish_progression_launch_context',
        ):
            setattr(controller, name, Mock())
        controller.archipelago_run_active = lambda: False
        return controller

    def start(self, controller):
        controller.start_mission_process(
            {'code': 'TEST', 'scenario': 'TEST.MAP'}, None, 1, 3,
        )

    def test_windows_process_receives_required_quotes(self):
        for root in (r'C:\Games\MO', r'C:\Games\Mental Omega', r'C:\遊戲\MO & Mods'):
            for host in ('gamemd.exe', root + r'\gamemd.exe'):
                with self.subTest(root=root, host=host):
                    controller = self.controller()
                    argv = [root + r'\Syringe.exe', host, *FLAGS]
                    controller.build_command = lambda: argv
                    expected = (
                        subprocess.list2cmdline(argv[:1])
                        + ' "' + host + '" ' + ' '.join(FLAGS)
                    )
                    with (
                        patch.object(launch.sys, 'platform', 'win32'),
                        patch.object(launch, 'GAME_ROOT', root),
                        patch.object(launch.subprocess, 'Popen') as popen,
                        patch.object(launch, 'log_event') as event,
                    ):
                        self.start(controller)
                    popen.assert_called_once_with(
                        expected, cwd=root, executable=argv[0],
                    )
                    self.assertIs(controller.active_game_process, popen.return_value)
                    self.assertEqual(event.call_args.kwargs['command'], expected)
                    controller.after.assert_called_once()
                    controller.cleanup_generated_root_maps.assert_not_called()

    def test_windows_build_command_uses_game_executable(self):
        root = PureWindowsPath(r'C:\Games\MO')
        with (
            patch.object(launch.sys, 'platform', 'win32'),
            patch.object(launch, 'GAME_LAUNCHER_EXE', root / 'Syringe.exe'),
            patch.object(launch, 'GAME_EXE', root / 'gamemd.exe'),
        ):
            self.assertEqual(
                self.controller().build_command(),
                [str(root / 'Syringe.exe'), 'gamemd.exe', *FLAGS],
            )

    def test_linux_keeps_argv_environment_and_process_group(self):
        for overrides, expected in (
            ('', 'ddraw=n,b'),
            ('d3d9=n', 'd3d9=n;ddraw=n,b'),
            ('ddraw=b', 'ddraw=b'),
        ):
            with self.subTest(overrides=overrides):
                controller = self.controller()
                argv = ['/usr/bin/wine', '/games/Mental Omega/Syringe.exe',
                        r'Z:\games\Mental Omega\gamemd.exe', *FLAGS]
                controller.build_command = lambda: argv
                with (
                    patch.object(launch.sys, 'platform', 'linux'),
                    patch.dict(os.environ, {'WINEDLLOVERRIDES': overrides}),
                    patch.object(launch.subprocess, 'Popen') as popen,
                    patch.object(launch, 'log_event'),
                ):
                    self.start(controller)
                self.assertIs(popen.call_args.args[0], argv)
                options = popen.call_args.kwargs
                self.assertEqual(options['env']['WINEDLLOVERRIDES'], expected)
                self.assertTrue(options['start_new_session'])
                self.assertNotIn('executable', options)
                self.assertNotIn('shell', options)

    def test_linux_resolves_host_with_winepath(self):
        with (
            patch.object(launch.sys, 'platform', 'linux'),
            patch.object(launch.shutil, 'which', side_effect=lambda name: '/usr/bin/' + name),
            patch.object(launch.subprocess, 'run') as run,
        ):
            run.return_value.stdout = 'Z:\\games\\Mental Omega\\gamemd.exe\n'
            argv = self.controller().build_command()
        self.assertEqual(argv, [
            '/usr/bin/wine', str(launch.GAME_LAUNCHER_EXE),
            r'Z:\games\Mental Omega\gamemd.exe', *FLAGS,
        ])
        self.assertEqual(run.call_args.args[0], [
            '/usr/bin/winepath', '-w', str(launch.GAME_EXE),
        ])
        self.assertTrue(run.call_args.kwargs['check'])

    def test_command_preparation_failure_cleans_up(self):
        controller = self.controller()
        controller.build_command = Mock(side_effect=FileNotFoundError('Wine is missing'))
        with (
            patch.object(launch.subprocess, 'Popen') as popen,
            patch.object(launch, 'log_event'),
            patch.object(launch.messagebox, 'showerror') as error,
        ):
            self.start(controller)
        popen.assert_not_called()
        controller.cleanup_generated_root_maps.assert_called_once()
        controller.disable_generated_rules_for_client.assert_called_once()
        controller.finish_progression_launch_context.assert_called_once()
        error.assert_called_once()

    def test_quote_windows_argument(self):
        for argument, expected in (
            ('', '""'),
            ('gamemd.exe', '"gamemd.exe"'),
            ('has space', '"has space"'),
            ('end\\', '"end\\\\"'),
            ('has space\\', '"has space\\\\"'),
            ('say"hi', '"say\\"hi"'),
        ):
            with self.subTest(argument=argument):
                self.assertEqual(launch.quote_windows_argument(argument), expected)

    def test_nanofiber_asset_failure_degrades_without_blocking_launch(self):
        controller = self.controller()
        controller.mission_required_launch_rules = Mock(return_value={})
        controller.write_spawn_ini = Mock()
        controller.write_launch_options = Mock()
        with tempfile.TemporaryDirectory() as temporary:
            map_path = Path(temporary) / 'TEST.MAP'
            map_path.write_text(
                '[MORNanofiberAnimations]\n'
                'MORNano1A=NANODEATH1\n\n'
                '[Nanofiber7P]\n'
                'Airburst=yes\n'
                'AirburstWeapon=MORNano1W\n',
                encoding='utf-8',
            )
            controller.prepare_hooked_map = Mock(return_value={
                'root_map': map_path,
                'markers': {},
            })
            with (
                patch.object(launch, 'claim_runtime_asset_lease'),
                patch.object(
                    launch,
                    'deploy_generated_unit_art',
                    side_effect=[OSError('asset denied'), (map_path, {})],
                ) as deploy,
                patch.object(launch, 'log_event'),
            ):
                hook = controller.prepare_mission_launch_files(
                    {'code': 'TEST', 'scenario': 'TEST.MAP'}, {}, 1, 3,
                )

            self.assertEqual(hook['root_map'], map_path)
            self.assertIn('Airburst=no', map_path.read_text(encoding='utf-8'))
            self.assertEqual(deploy.call_count, 2)
            self.assertEqual(
                deploy.call_args_list[1].kwargs,
                {'include_nanofiber': False},
            )
            controller.write_spawn_ini.assert_called_once()
            controller.write_launch_options.assert_called_once()

    def test_nanofiber_assets_only_required_when_power_is_usable(self):
        self.assertFalse(player_can_use_nanofiber((), 'Allies'))
        self.assertTrue(player_can_use_nanofiber((), 'Foehn'))
        self.assertTrue(player_can_use_nanofiber(
            ('NANOFIBERSYNCSPECIAL',), 'Soviets'
        ))

    def test_nanofiber_mutation_uses_fixed_lethal_damage(self):
        lines = [
            '[General]', 'AnimToInfantry=BRUTE,KINGS', '',
            '[MORPKNIGHT]', 'Armor=n_knight', 'Strength=999999', '',
            '[MORPKINGS]', 'Armor=n_plate', 'Strength=100', '',
            '[WeaponTypes]', '0=Nanofiber1Weapon', '',
            '[Projectiles]', '0=Nanofiber7P', '',
            '[Warheads]', '0=Nanofiber1WH', '',
            '[Animations]', '0=NANODEATH1',
        ]
        installed = {
            'General': {'AnimToInfantry': 'BRUTE,KINGS'},
            'Nanofiber7P': {'Image': 'none', 'Inviso': 'yes'},
            'Nanofiber1Weapon': {
                'Damage': '2000',
                'Warhead': 'Nanofiber1WH',
                'Projectile': 'Nanofiber7P',
            },
            'Nanofiber1WH': {
                'Verses': ','.join(['0%'] * 11),
                'Versus.n_knight': '200%',
                'InfDeathAnim': 'NANODEATH1',
            },
            'ArmorTypes': {'0': 'none'},
            'WeaponTypes': {'0': 'Nanofiber1Weapon'},
            'Projectiles': {'0': 'Nanofiber7P'},
            'Warheads': {'0': 'Nanofiber1WH'},
            'Animations': {'0': 'NANODEATH1'},
        }
        rules = nanofiber_clone_rules(lines, installed, {
            'KNIGHT': {'clone_id': 'MORPKNIGHT'},
            'KINGS': {'clone_id': 'MORPKINGS'},
        })
        self.assertEqual(rules['MORNano1W']['Damage'], '15999984')
        self.assertNotIn('RelativeDamage', rules['MORNano1WH'])
        self.assertNotIn('RelativeDamage.Infantry', rules['MORNano1WH'])
        self.assertEqual(
            rules['MORNano1WH']['Versus.MORNanoArmor1'], '100%'
        )
        self.assertEqual(rules['MORNano1WH']['AffectsAllies'], 'yes')
        self.assertEqual(rules['MORNano1WH']['AffectsEnemies'], 'yes')
        self.assertEqual(rules['MORNano1WH']['AffectsOwner'], 'yes')

    @unittest.skipUnless(sys.platform == 'win32' and not getattr(sys, 'frozen', False),
                         'Requires a Windows Python interpreter')
    def test_real_windows_process_command_line(self):
        # Observe GetCommandLineW in a real child, not just Python's argv parser.
        script = (
            'import ctypes,json,sys; '
            'ctypes.windll.kernel32.GetCommandLineW.restype=ctypes.c_wchar_p; '
            'print(json.dumps([ctypes.windll.kernel32.GetCommandLineW(),sys.argv[1:]]))'
        )
        for host in ('gamemd.exe', r'C:\Games\MO\gamemd.exe', r'C:\Mental Omega\gamemd.exe'):
            with self.subTest(host=host):
                tail = launch.windows_syringe_command_line(['Syringe.exe', host, *FLAGS])
                tail = tail.removeprefix('Syringe.exe ')
                command = subprocess.list2cmdline([sys.executable, '-c', script]) + ' ' + tail
                result = subprocess.run(command, executable=sys.executable, check=True,
                                        capture_output=True, text=True)
                raw, argv = json.loads(result.stdout)
                self.assertTrue(raw.endswith(' "' + host + '" ' + ' '.join(FLAGS)))
                self.assertEqual(argv, [host, *FLAGS])


def validate_launch_contract():
    """Raise on regression even in optimized, windowed PyInstaller builds."""
    output = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(LaunchCommandTests)
    result = unittest.TextTestRunner(stream=output).run(suite)
    if not result.wasSuccessful():
        raise RuntimeError(output.getvalue())
    return {'passed': True, 'tests': result.testsRun, 'skipped': len(result.skipped)}
