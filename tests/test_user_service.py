"""Manual/login service profiles and fail-closed session checks; no host changes."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from utils.user_service import UNIT_NAME, install_service, service_unit, session_problem, unit_quote


class UserServiceTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='snipping-service-')
        self.root = Path(self.scratch.name)
        self.checkout = self.root / 'checkout with spaces % and $'
        (self.checkout / '.venv/bin').mkdir(parents=True)
        (self.checkout / '.venv/bin/python').symlink_to(sys.executable)
        (self.checkout / 'main.py').write_text('# public test fixture\n')
        self.units = self.root / 'units'

    def tearDown(self):
        self.scratch.cleanup()

    def test_manual_only_graphical_session_lifetime_and_failure_restart_contract(self):
        unit = service_unit(self.checkout)
        for line in ('Requisite=graphical-session.target', 'After=graphical-session.target',
                     'PartOf=graphical-session.target', 'Restart=on-failure', 'RestartSec=3',
                     'StartLimitIntervalSec=60', 'StartLimitBurst=3', 'KillMode=mixed',
                     'TimeoutStopSec=30', 'Environment=XDG_RUNTIME_DIR=%t',
                     'Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=%t/bus',
                     'Environment=QT_QPA_PLATFORM=wayland', 'Type=exec'):
            self.assertIn(line+'\n', unit)
        self.assertNotIn('\n[Install]', unit)
        self.assertNotIn('\nWantedBy=', unit)
        self.assertNotIn('\nUser=root', unit)
        self.assertIn('--check-session', unit)
        self.assertNotIn('capture_menu.py', unit)
        self.assertIn('/.venv/bin/python', unit)
        self.assertNotIn('import-environment', unit)

    def test_install_is_idempotent_and_does_not_enable_or_run_commands(self):
        with patch('subprocess.run') as run:
            first = install_service(self.checkout, self.units)
            before = first.stat().st_ino
            self.assertEqual(install_service(self.checkout, self.units), first)
            self.assertEqual(first.stat().st_ino, before)
            run.assert_not_called()
        self.assertEqual(list(self.units.iterdir()), [first])
        self.assertEqual(first.stat().st_mode & 0o777, 0o644)

    def test_existing_custom_unit_and_symlink_are_preserved(self):
        self.units.mkdir()
        target = self.units / UNIT_NAME
        target.write_text('custom configuration')
        with self.assertRaisesRegex(RuntimeError, 'preserved'):
            install_service(self.checkout, self.units)
        self.assertEqual(target.read_text(), 'custom configuration')
        target.unlink()  # This test's own temporary fixture only.
        original = self.root / 'custom.service'
        original.write_text('keep')
        target.symlink_to(original)
        with self.assertRaisesRegex(RuntimeError, 'symlink preserved'):
            install_service(self.checkout, self.units)
        self.assertEqual(original.read_text(), 'keep')
        self.assertTrue(target.is_symlink())

    def test_publish_race_never_overwrites_or_leaves_staging(self):
        real_link = os.link
        def race(source, target):
            Path(target).write_text('external user unit')
            return real_link(source, target)
        with patch('utils.user_service.os.link', side_effect=race):
            with self.assertRaisesRegex(RuntimeError, 'preserved'):
                install_service(self.checkout, self.units)
        self.assertEqual((self.units / UNIT_NAME).read_text(), 'external user unit')
        self.assertEqual(len(list(self.units.iterdir())), 1)

    def test_failed_publication_cleans_only_its_staging_file(self):
        with patch('utils.user_service.os.link', side_effect=PermissionError('controlled')):
            with self.assertRaises(PermissionError):
                install_service(self.checkout, self.units)
        self.assertFalse(list(self.units.iterdir()))

    def test_systemd_quoting_is_not_shell_or_desktop_escaping(self):
        self.assertEqual(unit_quote('/tmp/a"b\\c% $'), '"/tmp/a\\"b\\\\c%% $"')
        self.assertEqual(unit_quote('/tmp/$HOME%u', command=True), '"/tmp/$$HOME%%u"')
        for value in ('newline\npath', 'tab\tpath', 'null\x00', 'delete\x7f'):
            with self.assertRaises(ValueError):
                unit_quote(value)

    def test_missing_checkout_or_venv_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'executable .venv'):
            service_unit(self.root / 'missing')

    def test_real_systemd_parser_accepts_generated_unit_and_paths(self):
        target = self.root / UNIT_NAME
        target.write_text(service_unit(self.checkout))
        result = subprocess.run(['systemd-analyze', '--user', 'verify', str(target)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cli_print_uses_checkout_virtualenv_without_installing(self):
        result = subprocess.run([sys.executable, '-m', 'utils.user_service', '--print'],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('ExecStart=', result.stdout)
        self.assertNotIn('[Install]\n', result.stdout)

    def test_login_profile_waits_for_gnome_and_is_wanted_by_graphical_session(self):
        unit = service_unit(self.checkout, login_startup=True)
        for line in ('Requisite=gnome-session.target', 'After=gnome-session.target',
                     'PartOf=graphical-session.target', 'WantedBy=graphical-session.target',
                     'Restart=on-failure', 'ExecCondition='):
            self.assertIn(line, unit)
        self.assertNotIn('After=graphical-session.target', unit)
        self.assertNotIn('Requisite=graphical-session.target', unit)
        self.assertNotIn('default.target', unit)
        self.assertEqual(unit.count('ExecStart='), 1)

    def test_profile_migration_and_rollback_require_explicit_exact_match(self):
        target = install_service(self.checkout, self.units)
        manual = target.read_text()
        with self.assertRaisesRegex(RuntimeError, 'preserved'):
            install_service(self.checkout, self.units, login_startup=True)
        self.assertEqual(target.read_text(), manual)
        with patch('subprocess.run') as run:
            install_service(self.checkout, self.units, login_startup=True, replace_known=True)
            self.assertEqual(target.read_text(), service_unit(self.checkout, login_startup=True))
            install_service(self.checkout, self.units, replace_known=True)
            run.assert_not_called()
        self.assertEqual(target.read_text(), manual)
        self.assertEqual(list(self.units.iterdir()), [target])

    def test_replace_known_preserves_customized_unit_even_with_managed_marker(self):
        target = install_service(self.checkout, self.units)
        content = target.read_text() + '\n# User customization must survive\n'
        target.write_text(content)
        with self.assertRaisesRegex(RuntimeError, 'preserved'):
            install_service(self.checkout, self.units, login_startup=True, replace_known=True)
        self.assertEqual(target.read_text(), content)

    def test_profile_change_during_preparation_is_preserved(self):
        target = install_service(self.checkout, self.units)
        original = Path.chmod
        def concurrent_edit(path, mode):
            target.write_text('concurrent custom unit')
            original(path, mode)
        with patch.object(Path, 'chmod', concurrent_edit):
            with self.assertRaisesRegex(RuntimeError, 'changed while preparing'):
                install_service(self.checkout, self.units, login_startup=True, replace_known=True)
        self.assertEqual(target.read_text(), 'concurrent custom unit')
        self.assertEqual(list(self.units.iterdir()), [target])

    def test_prospective_enabled_graph_passes_real_systemd_verification(self):
        target = self.root / UNIT_NAME
        target.write_text(service_unit(self.checkout, login_startup=True))
        wants = self.root / 'graphical-session.target.wants'
        wants.mkdir()
        (wants / UNIT_NAME).symlink_to(target)
        # Private unit search tree models enablement; no live manager calls,
        # no GNOME target restart and no symlink in the real user's directory.
        env = dict(os.environ, SYSTEMD_UNIT_PATH=str(self.root)+':')
        result = subprocess.run(['systemd-analyze', '--user', 'verify', str(target)],
                                env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('ordering cycle', result.stderr.lower())

    def test_cli_login_print_does_not_enable_and_invalid_option_combinations_fail(self):
        result = subprocess.run([sys.executable, '-m', 'utils.user_service', '--print', '--login-startup'],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('WantedBy=graphical-session.target', result.stdout)
        for args in (['--check-session', '--login-startup'], ['--print', '--replace-known']):
            result = subprocess.run([sys.executable, '-m', 'utils.user_service', *args],
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 2)


class SessionConditionTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='snip-session-')
        self.root = Path(self.scratch.name)
        self.sockets = []
        for name in ('wayland-test', 'bus'):
            sock = socket.socket(socket.AF_UNIX)
            sock.bind(str(self.root / name))
            self.sockets.append(sock)
        self.env = {'XDG_SESSION_TYPE': 'wayland', 'XDG_CURRENT_DESKTOP': 'ubuntu:GNOME',
                    'XDG_RUNTIME_DIR': str(self.root), 'WAYLAND_DISPLAY': 'wayland-test',
                    'DBUS_SESSION_BUS_ADDRESS': f'unix:path={self.root}/bus'}

    def tearDown(self):
        for sock in self.sockets: sock.close()
        self.scratch.cleanup()

    def test_owned_live_wayland_and_session_bus_sockets_pass(self):
        self.assertIsNone(session_problem(self.env))
        self.env['WAYLAND_DISPLAY'] = str(self.root / 'wayland-test')
        self.assertIsNone(session_problem(self.env))

    def test_non_graphical_missing_or_stale_environment_fails_closed(self):
        for key, value in [('XDG_SESSION_TYPE', 'tty'), ('XDG_CURRENT_DESKTOP', 'KDE'),
                           ('XDG_RUNTIME_DIR', ''), ('XDG_RUNTIME_DIR', 'relative'),
                           ('WAYLAND_DISPLAY', ''), ('WAYLAND_DISPLAY', 'stale-display'),
                           ('DBUS_SESSION_BUS_ADDRESS', 'unix:path=/different/bus')]:
            with self.subTest(key=key, value=value):
                self.assertIsNotNone(session_problem(dict(self.env, **{key: value})))

    def test_root_other_owner_and_regular_files_are_rejected(self):
        self.assertIsNotNone(session_problem(self.env, uid=0))
        self.assertIsNotNone(session_problem(self.env, uid=os.getuid()+1))
        file = self.root / 'regular'
        file.write_text('not a Wayland socket')
        self.assertIsNotNone(session_problem(dict(self.env, WAYLAND_DISPLAY=str(file))))

    def test_exec_condition_returns_skip_not_restart_failure(self):
        with patch.dict(os.environ, {'XDG_SESSION_TYPE': 'tty'}):
            result = subprocess.run([sys.executable, '-m', 'utils.user_service', '--check-session'],
                                    capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 1)
        self.assertIn('service skipped', result.stderr)
