"""Regression checks for the process boundary, also runnable inside the EXE."""

import io
import json
import os
from pathlib import PureWindowsPath
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

from randomizer.application import launch_controller as launch


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
