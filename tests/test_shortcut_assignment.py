"""Portal protocol and GUI state tests; no real keypress or GNOME settings changes."""
import asyncio
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
import threading
from unittest.mock import AsyncMock, patch

from dbus_next import MessageType, Variant
from PySide6.QtCore import QThread, QRect, Qt

# Reuse the isolated QApplication/environment from the original Phase 1 suite.
from test_phase01 import app, spin_until
from main import configure_application
from shortcuts.assignment import comparison, display_shortcut
from shortcuts.global_shortcut import (GlobalShortcutManager, GLOBAL_SHORTCUTS_INTERFACE,
    REGISTRY_INTERFACE, PREFERRED_TRIGGER, SHORTCUT_ID, APP_ID, PORTAL_OBJECT_PATH)


def entries(description='Press <Control><Alt>s', key=SHORTCUT_ID):
    return [[key, {'trigger_description': Variant('s', description)}]]


def xml(config=True):
    method = '<method name="ConfigureShortcuts"><arg type="o" direction="in"/><arg type="s" direction="in"/><arg type="a{sv}" direction="in"/></method>' if config else ''
    return f'<node><interface name="{GLOBAL_SHORTCUTS_INTERFACE}">{method}</interface></node>'


class FakeBus:
    unique_name = ':1.999'
    def __init__(self, version=2, configure=True, identity_error=None, remembered=None):
        self.version, self.configure, self.identity_error = version, configure, identity_error
        self.remembered = remembered or []
        self.calls = []
        self.handler = None
        self.disconnected = False
        self.actual = entries()
        self.bound = False
        self.configure_error = None
        self.xml_override = None

    async def connect(self):
        return self

    def add_message_handler(self, handler):
        self.handler = handler

    def disconnect(self):
        self.disconnected = True

    async def call(self, message):
        self.calls.append(message)
        if message.member == 'Register':
            if self.identity_error:
                return NS(message_type=MessageType.ERROR, error_name='org.freedesktop.portal.Error.Failed',
                          body=[self.identity_error])
            return NS(message_type=MessageType.METHOD_RETURN, body=[])
        if message.member == 'Introspect':
            return NS(message_type=MessageType.METHOD_RETURN, body=[self.xml_override or xml(self.configure)])
        if message.member == 'Get':
            return NS(message_type=MessageType.METHOD_RETURN, body=[Variant('u', self.version)])
        if message.member == 'ConfigureShortcuts':
            if self.configure_error:
                return NS(message_type=MessageType.ERROR, error_name=self.configure_error, body=['unsupported'])
            return NS(message_type=MessageType.METHOD_RETURN, body=[])
        if message.member in ('AddMatch', 'Close'):
            return NS(message_type=MessageType.METHOD_RETURN, body=[])
        token = message.body[-1]['handle_token'].value
        path = '/org/freedesktop/portal/desktop/request/1_999/' + token
        if message.member == 'CreateSession':
            result = {'session_handle': Variant('s', '/session/capture')}
        elif message.member == 'ListShortcuts':
            result = {'shortcuts': Variant('a(sa{sv})', self.actual if self.bound else self.remembered)}
        elif message.member == 'BindShortcuts':
            self.bound = True
            result = {'shortcuts': Variant('a(sa{sv})', self.actual)}
        else:
            raise AssertionError(message.member)
        # Response before method return exercises the subscription race.
        self.handler(NS(message_type=MessageType.SIGNAL, interface='org.freedesktop.portal.Request',
                        member='Response', path=path, body=[0, result]))
        return NS(message_type=MessageType.METHOD_RETURN, body=[path])


class AssignmentTests(unittest.TestCase):
    def setUp(self):
        self.manager = GlobalShortcutManager()
        self.assignments = []
        self.successes = []
        self.manager.assignment_changed.connect(lambda *args: self.assignments.append(args))
        self.manager.registration_succeeded.connect(self.successes.append)

    def register(self, bus):
        with patch('shortcuts.global_shortcut.MessageBus', return_value=bus), \
             patch('shortcuts.global_shortcut.ensure_desktop_entry'):
            asyncio.run(self.manager._register())

    def test_xdg_base_keysym_and_stable_id(self):
        self.assertEqual(PREFERRED_TRIGGER, 'ALT+SHIFT+s')
        self.assertEqual(SHORTCUT_ID, 'open_capture_menu')
        self.assertEqual(comparison(PREFERRED_TRIGGER, 'Press <Alt><Shift>s'), 'match')
        self.assertEqual(comparison(PREFERRED_TRIGGER, 'Alt+Shift+S'), 'match')

    def test_new_binding_request_and_actual_response(self):
        bus = FakeBus()
        with self.assertLogs('shortcuts.global_shortcut', level='INFO') as logs:
            self.register(bus)
        request = next(msg for msg in bus.calls if msg.member == 'BindShortcuts')
        self.assertEqual(request.body[1][0][0], SHORTCUT_ID)
        self.assertEqual(request.body[1][0][1]['preferred_trigger'].value, PREFERRED_TRIGGER)
        self.assertEqual(self.successes, ['Press <Control><Alt>s'])
        self.assertEqual(self.manager.assigned_trigger, 'Press <Control><Alt>s')
        self.assertEqual(self.assignments[-1], (PREFERRED_TRIGGER, 'Press <Control><Alt>s', 'different'))
        self.assertTrue(any('requested=ALT+SHIFT+s; actual=Press <Control><Alt>s' in line for line in logs.output))
        self.assertEqual([m.member for m in bus.calls].count('ListShortcuts'), 2)

    def test_remembered_choice_not_replaced_by_preference(self):
        bus = FakeBus(remembered=entries())
        self.register(bus)
        request = next(msg for msg in bus.calls if msg.member == 'BindShortcuts')
        self.assertNotIn('preferred_trigger', request.body[1][0][1])

    def test_previous_control_shift_assignment_remains_truthful_on_v1(self):
        old = entries('Press <Shift><Control>s')
        bus = FakeBus(version=1, remembered=old)
        bus.actual = old
        self.register(bus)
        request = next(msg for msg in bus.calls if msg.member == 'BindShortcuts')
        self.assertEqual(request.body[1][0][0], SHORTCUT_ID)
        self.assertNotIn('preferred_trigger', request.body[1][0][1])
        self.assertEqual(self.assignments[-1],
                         ('ALT+SHIFT+s', 'Press <Shift><Control>s', 'different'))
        self.assertFalse(self.manager.can_configure)
        self.assertFalse(any(m.member == 'ConfigureShortcuts' for m in bus.calls))

    def test_alt_shift_assignment_verified_by_list(self):
        bus = FakeBus(version=1)
        bus.actual = entries('Press <Shift><Alt>s')
        self.register(bus)
        self.assertEqual(self.assignments[-1],
                         ('ALT+SHIFT+s', 'Press <Shift><Alt>s', 'match'))
        self.assertEqual(self.successes, ['Press <Shift><Alt>s'])
        self.assertEqual([m.member for m in bus.calls].count('ListShortcuts'), 2)

    def test_missing_description_never_substitutes_requested_key(self):
        self.manager._apply_assignment([[SHORTCUT_ID, {}]], 'test')
        self.assertEqual(self.manager.assigned_trigger, '')
        self.assertIn('not supplied', self.assignments[-1][1])
        self.assertEqual(self.assignments[-1][2], 'unknown')
        self.assertNotEqual(self.assignments[-1][1], PREFERRED_TRIGGER)

    def test_localized_description_preserved_without_guessing(self):
        self.manager._apply_assignment(entries('Drücken Sie Strg+Alt+S'), 'test')
        self.assertEqual(self.assignments[-1][1], 'Drücken Sie Strg+Alt+S')
        self.assertEqual(self.assignments[-1][2], 'unknown')

    def test_shortcuts_changed_updates_and_filters_session(self):
        self.manager._session_handle = '/session/capture'
        msg = NS(message_type=MessageType.SIGNAL, interface=GLOBAL_SHORTCUTS_INTERFACE,
                 member='ShortcutsChanged', body=['/other', entries('Alt+Shift+S')])
        self.manager._message_handler(msg)
        self.assertFalse(self.assignments)
        msg.body[0] = '/session/capture'
        self.manager._message_handler(msg)
        self.assertEqual(self.assignments[-1][2], 'match')
        self.assertEqual(self.manager._commands.get_nowait(), 'refresh')
        msg.body[1] = []
        self.manager._message_handler(msg)
        self.assertFalse(self.manager.is_registered)
        self.assertEqual(self.assignments[-1][2], 'unbound')

    def test_stale_list_does_not_overwrite_new_signal(self):
        async def list_result():
            self.manager._apply_assignment(entries('Alt+Shift+S'), 'ShortcutsChanged')
            return entries('Ctrl+Alt+S')
        with patch.object(self.manager, '_list_shortcuts', list_result):
            asyncio.run(self.manager._refresh_assignment())
        self.assertEqual(self.manager.assigned_trigger, 'Alt+Shift+S')

    def test_failed_list_retains_last_reported_assignment(self):
        self.manager._apply_assignment(entries(), 'BindShortcuts')
        with patch.object(self.manager, '_list_shortcuts', new=AsyncMock(side_effect=RuntimeError('denied'))):
            asyncio.run(self.manager._refresh_assignment())
        self.assertEqual(self.manager.assigned_trigger, 'Press <Control><Alt>s')

    def test_identity_first_same_connection_and_exact_app_id(self):
        bus = FakeBus()
        self.register(bus)
        self.assertEqual(bus.calls[0].interface, REGISTRY_INTERFACE)
        self.assertEqual(bus.calls[0].body, [APP_ID, {}])
        self.assertIn('Host identity registered', self.manager.identity_status)
        self.assertTrue(any(m.member == 'AddMatch' for m in bus.calls))

    def test_snap_identity_error_kept_and_configuration_blocked(self):
        bus = FakeBus(identity_error="Could not register app ID: Can't manually register a io.snapcraft application")
        self.register(bus)
        self.assertIn('io.snapcraft', self.manager.identity_status)
        self.assertIn('not registered', self.manager.identity_status)
        self.assertFalse(self.manager.can_configure)
        self.assertFalse(self.manager.request_configuration())
        self.assertFalse(any(m.member == 'ConfigureShortcuts' for m in bus.calls))

    def test_host_registry_failure_is_not_treated_as_confirmed_identity(self):
        bus = FakeBus(identity_error='Desktop application ID not found')
        self.register(bus)
        self.assertIn('Desktop application ID not found', self.manager.identity_status)
        self.assertFalse(self.manager.can_configure)

    def test_registration_failure_signal_keeps_error(self):
        errors = []
        self.manager.registration_failed.connect(errors.append)
        with patch.object(self.manager, '_register', new=AsyncMock(side_effect=RuntimeError('portal denied'))):
            asyncio.run(self.manager._run_session())
        self.assertEqual(errors, ['portal denied'])
        self.assertEqual(self.manager.error, 'portal denied')

    def test_close_session_closes_exact_handle_and_disconnects(self):
        bus = FakeBus()
        self.manager._bus = bus
        self.manager._session_handle = '/session/capture'
        asyncio.run(self.manager._close_session())
        self.assertEqual(bus.calls[-1].member, 'Close')
        self.assertEqual(bus.calls[-1].path, '/session/capture')
        self.assertTrue(bus.disconnected)

    def test_v1_advertised_stub_v2_and_signature(self):
        for version, method, expected in ((1, False, False), (1, True, False), (2, True, True), (2, False, False)):
            with self.subTest(version=version, method=method):
                manager = GlobalShortcutManager()
                manager._bus = FakeBus(version=version, configure=method)
                manager._session_handle = '/session/capture'
                asyncio.run(manager._inspect_capabilities())
                self.assertEqual(manager.can_configure, expected)
                self.assertEqual(manager.portal_version, version)
        self.manager._bus = FakeBus()
        self.manager._bus.xml_override = f'<node><interface name="{GLOBAL_SHORTCUTS_INTERFACE}"><method name="ConfigureShortcuts"/></interface></node>'
        asyncio.run(self.manager._inspect_capabilities())
        self.assertFalse(self.manager._configure_supported)

    def test_unrelated_nonstandard_property_does_not_break_capabilities(self):
        self.manager._bus = FakeBus()
        self.manager._bus.xml_override = xml().replace('</node>',
            '<interface name="org.freedesktop.portal.PowerProfileMonitor">'
            '<property name="power-saver-enabled" type="b" access="read"/>'
            '</interface></node>')
        asyncio.run(self.manager._inspect_capabilities())
        self.assertTrue(self.manager._configure_supported)
        self.assertEqual(self.manager.portal_version, 2)

    def test_configuration_explicit_only_and_refreshes_list(self):
        bus = FakeBus()
        self.register(bus)
        self.assertFalse(any(m.member == 'ConfigureShortcuts' for m in bus.calls))
        self.assertTrue(self.manager.request_configuration())
        self.assertFalse(self.manager.request_configuration())
        self.assertEqual(self.manager._commands.get_nowait(), 'configure')
        asyncio.run(self.manager._configure_shortcuts())
        calls = [m for m in bus.calls if m.member == 'ConfigureShortcuts']
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].signature, 'osa{sv}')
        self.assertEqual(calls[0].body, ['/session/capture', '', {}])
        self.assertEqual(bus.calls[-1].member, 'ListShortcuts')
        self.assertFalse(self.manager._configuring)

    def test_configuration_unknown_method_disables_action(self):
        bus = FakeBus()
        self.register(bus)
        bus.configure_error = 'org.freedesktop.DBus.Error.UnknownMethod'
        messages = []
        self.manager.configuration_message.connect(messages.append)
        asyncio.run(self.manager._configure_shortcuts())
        self.assertFalse(self.manager.can_configure)
        self.assertIn('UnknownMethod', messages[-1])
        self.assertFalse(self.manager.request_configuration())
        asyncio.run(self.manager._configure_shortcuts())
        self.assertEqual(sum(m.member == 'ConfigureShortcuts' for m in bus.calls), 1)

    def test_v1_advertised_stub_never_called_and_explained(self):
        bus = FakeBus(version=1)
        messages = []
        self.manager.configuration_message.connect(messages.append)
        self.register(bus)
        self.assertFalse(self.manager.can_configure)
        self.assertFalse(self.manager.request_configuration())
        self.assertFalse(any(m.member == 'ConfigureShortcuts' for m in bus.calls))
        self.assertTrue(any('backend does not support' in message for message in messages))

    def test_denied_binding_reports_registration_error(self):
        async def rejected(**kwargs):
            if kwargs['member'] == 'CreateSession':
                return {'session_handle': Variant('s', '/session/capture')}
            if kwargs['member'] == 'ListShortcuts':
                return {'shortcuts': []}
            return {'shortcuts': []}
        with patch.object(self.manager, '_portal_request', rejected):
            with self.assertRaisesRegex(RuntimeError, 'did not bind'):
                self.register(FakeBus())
        self.assertFalse(self.successes)

    def test_shutdown_cancels_pending_configuration(self):
        entered = []
        cancelled = []
        async def configure():
            entered.append(True)
            try:
                await asyncio.sleep(60)
            finally:
                cancelled.append(True)
        async def register():
            self.manager._session_handle = '/session/capture'
        async def scenario():
            self.manager._commands.put('configure')
            with patch.object(self.manager, '_register', register), \
                 patch.object(self.manager, '_configure_shortcuts', configure):
                task = asyncio.create_task(self.manager._run_session())
                while not entered:
                    await asyncio.sleep(.01)
                self.manager._shutdown_requested.set()
                await task
        asyncio.run(scenario())
        self.assertEqual(cancelled, [True])
        self.assertFalse(self.manager._action_tasks)


class PresentationTests(unittest.TestCase):
    def test_identity_timeout_is_not_stuck_checking(self):
        self.manager.identity_changed.emit('Identity not registered: Registry.Register timed out')
        self.manager.registration_failed.emit('Registry.Register: TimeoutError (startup attempt 3/3)')
        self.assertEqual(self.status.identity_text, 'Not registered')
        self.assertIn('TimeoutError', self.status.error_detail)


    def setUp(self):
        self.menu, self.manager, self.tray, self.tray_menu = configure_application(app)
        self.status = self.menu.shortcut_status
    def tearDown(self):
        self.status.dialog.close()
        self.menu.shutdown()
        self.menu.jobs.close()
        self.tray.hide()
        app.aboutToQuit.disconnect(self.menu.shutdown)

    def test_actual_assignment_in_action_tooltip_status_and_mismatch_warning(self):
        self.manager._apply_assignment(entries(), 'test')
        self.assertIn('Ctrl+Alt+S', self.tray_menu.actions()[0].text())
        self.assertIn('Assigned shortcut: Ctrl+Alt+S', self.tray.toolTip())
        self.assertIn('different shortcut', self.menu.status_label.text())
        self.assertIn('Requested shortcut: Alt+Shift+S', self.menu.status_label.text())
        detail = self.status.dialog.details.toPlainText()
        self.assertIn('Permissions → Global Shortcuts', detail)
        self.assertIn('Set Shortcut', detail)
        self.assertNotIn('Settings', self.status.status_action.text())
        self.assertFalse(self.menu.isVisible())
        self.assertFalse(self.status.dialog.isVisible())

    def test_worker_assignment_is_delivered_to_gui_thread(self):
        threads = []
        original_render = self.status._render
        def render():
            threads.append(QThread.currentThread())
            original_render()
        with patch.object(self.status, '_render', render):
            worker = threading.Thread(target=lambda: self.manager.assignment_changed.emit(
                PREFERRED_TRIGGER, 'Alt+Shift+S', 'match'))
            worker.start()
            worker.join()
            spin_until(lambda: bool(threads))
        self.assertEqual(threads, [app.thread()])
        self.assertIn('Alt+Shift+S', self.tray_menu.actions()[0].text())

    def test_configuration_action_is_explicit_and_capability_gated(self):
        action = self.status.configure_action
        self.assertFalse(action.isEnabled())
        self.manager.configuration_available_changed.emit(True)
        self.assertTrue(action.isEnabled())
        with patch.object(self.manager, 'request_configuration') as request:
            action.trigger()
            request.assert_called_once()
        self.manager.configuration_available_changed.emit(False)
        self.assertFalse(action.isEnabled())

    def test_registration_error_removes_stale_assignment(self):
        self.manager._apply_assignment(entries(), 'test')
        self.manager.registration_failed.emit('Portal denied registration')
        self.assertEqual(self.tray_menu.actions()[0].text(), 'Capture')
        self.assertIn('Registration failed', self.menu.status_label.text())
        self.assertIn('Portal denied registration', self.status.dialog.details.toPlainText())
        self.assertNotIn('Portal denied registration', self.tray.toolTip())
        self.assertNotIn('registered: ALT+SHIFT+s', self.tray.toolTip())

    def test_dialog_opens_only_on_explicit_status_action(self):
        self.manager._apply_assignment(entries(), 'ListShortcuts')
        self.manager.identity_changed.emit('Host identity registered: test.app')
        self.manager.configuration_message.emit('Details ' * 100)
        self.assertFalse(self.status.dialog.isVisible())
        self.status.status_action.trigger()
        self.assertTrue(self.status.dialog.isVisible())
        self.assertFalse(self.menu.isVisible())
        self.assertFalse(self.status.dialog.details.isVisible())
        self.status.dialog.details_button.click()
        self.assertTrue(self.status.dialog.details.isVisible())
        self.assertIn('Details', self.status.dialog.details.toPlainText())

    def test_dialog_wraps_and_fits_narrow_logical_screen(self):
        self.manager._apply_assignment(entries('localized description ' * 100), 'test')
        dialog = self.status.dialog
        dialog.fit_to_screen(QRect(0, 0, 320, 480))
        dialog.show()
        app.processEvents()
        self.assertLessEqual(dialog.width(), 288)
        self.assertLessEqual(dialog.height(), 432)
        self.assertTrue(dialog.summary.wordWrap())
        self.assertEqual(dialog.summary.textFormat(), Qt.PlainText)
        self.assertEqual(dialog.summary.alignment(), Qt.AlignLeft | Qt.AlignTop)
        self.assertGreater(dialog.summary.heightForWidth(200), dialog.summary.fontMetrics().height())
        self.assertLessEqual(dialog.summary.geometry().right(), dialog.summary.parentWidget().width())
        self.assertTrue(dialog.details_button.isVisible())
        self.assertLessEqual(len(self.status.status_action.text()), 100)

    def test_long_errors_and_identity_do_not_expand_tray(self):
        error = 'verylongtechnicaltoken' * 100
        self.manager.registration_failed.emit(error)
        self.manager.identity_changed.emit('Identity not registered: ' + error)
        self.assertNotIn(error, self.status.status_action.text())
        self.assertNotIn(error, self.status.identity_action.text())
        self.assertIn(error, self.status.dialog.details.toPlainText())
        self.assertIn('Not registered', self.status.dialog.summary.text())
        self.assertFalse(self.status.dialog.isVisible())
        self.assertIs(self.menu.status_label.parentWidget(), self.menu)


class DisplayShortcutTests(unittest.TestCase):
    def test_readable_requested_and_portal_descriptions(self):
        for raw, expected in [('ALT+SHIFT+s', 'Alt+Shift+S'),
                ('Press <Shift><Alt>s', 'Alt+Shift+S'),
                ('Press <Control><Alt>s', 'Ctrl+Alt+S'),
                ('CTRL+SHIFT+s', 'Ctrl+Shift+S')]:
            self.assertEqual(display_shortcut(raw), expected)

    def test_unknown_or_localized_descriptions_preserved(self):
        for raw in ['Drücken Sie Strg+Alt+S', 'Not assigned', '<unknown>thing', '']:
            self.assertEqual(display_shortcut(raw), raw)
