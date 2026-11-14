"""Login recovery regression fixtures; no physical keys or GNOME settings edits."""
import asyncio
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from dbus_next import MessageFlag, MessageType
from test_shortcut_assignment import FakeBus
from shortcuts.global_shortcut import GlobalShortcutManager, PortalStartupError


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.manager = GlobalShortcutManager()
        self.patches = [
            patch('shortcuts.global_shortcut.ensure_desktop_entry'),
            patch('shortcuts.global_shortcut.REQUEST_TIMEOUT_SECONDS', .025),
            patch('shortcuts.global_shortcut.STARTUP_RETRY_SECONDS', .001),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def test_login_registry_timeout_recovers_with_new_identified_connection(self):
        class StartingBus(FakeBus):
            async def call(self, message):
                if message.member == 'Register':
                    self.calls.append(message)
                    await asyncio.Future()  # Frontend stuck activating backend at login.
                return await super().call(message)
        first, ready = StartingBus(), FakeBus(version=1)
        states = []
        self.manager.identity_changed.connect(states.append)
        with patch('shortcuts.global_shortcut.MessageBus', side_effect=[first, ready]):
            asyncio.run(self.manager._register_at_startup())
        self.assertTrue(first.disconnected)
        self.assertFalse(any(m.member == 'CreateSession' for m in first.calls))
        self.assertEqual(ready.calls[0].member, 'Register')
        self.assertTrue(self.manager.is_registered)
        self.assertEqual(self.manager.assigned_trigger, 'Press <Control><Alt>s')
        self.assertTrue(any('not registered' in state for state in states))
        self.assertTrue(states[-1].startswith('Host identity registered:'))
        self.assertFalse(self.manager.can_configure)

    def test_no_reply_error_is_transient_and_attempts_are_bounded(self):
        class NoReply(FakeBus):
            async def call(self, message):
                self.calls.append(message)
                return NS(message_type=MessageType.ERROR,
                          error_name='org.freedesktop.DBus.Error.NoReply', body=['starting'])
        buses = [NoReply() for _ in range(3)]
        with patch('shortcuts.global_shortcut.MessageBus', side_effect=buses) as factory:
            with self.assertRaisesRegex(RuntimeError, 'NoReply.*3/3'):
                asyncio.run(self.manager._register_at_startup())
        self.assertEqual(factory.call_count, 3)
        self.assertTrue(all(bus.disconnected for bus in buses[:2]))
        self.assertIn('not registered', self.manager.identity_status)
        self.assertFalse(self.manager.is_registered)

    def test_binding_denial_is_not_retried(self):
        class Denied(FakeBus):
            async def call(self, message):
                if message.member == 'BindShortcuts':
                    raise RuntimeError('BindShortcuts denied (response code 2)')
                return await super().call(message)
        bus = Denied()
        with patch('shortcuts.global_shortcut.MessageBus', return_value=bus) as factory:
            with self.assertRaisesRegex(RuntimeError, 'response code 2'):
                asyncio.run(self.manager._register_at_startup())
        self.assertEqual(factory.call_count, 1)
        self.assertTrue(self.manager.identity_status.startswith('Host identity registered:'))

    def test_timeout_after_session_creation_does_not_duplicate_session(self):
        class SlowBinding(FakeBus):
            async def call(self, message):
                if message.member == 'BindShortcuts':
                    await asyncio.Future()
                return await super().call(message)
        with patch('shortcuts.global_shortcut.MessageBus', return_value=SlowBinding()) as factory:
            with self.assertRaisesRegex(RuntimeError, 'BindShortcuts'):
                asyncio.run(self.manager._register_at_startup())
        self.assertEqual(factory.call_count, 1)

    def test_cancelled_registry_updates_identity_and_leaves_no_async_tasks(self):
        async def waiting():
            self.manager._registration_operation = 'Registry.Register'
            await asyncio.Future()
        async def scenario():
            with patch.object(self.manager, '_register', waiting):
                task = asyncio.create_task(self.manager._run_session())
                await asyncio.sleep(.005)
                self.manager._shutdown_requested.set()
                await asyncio.wait_for(task, .5)
            self.assertFalse([task for task in asyncio.all_tasks()
                              if task is not asyncio.current_task() and not task.done()])
        asyncio.run(scenario())
        self.assertIn('not registered', self.manager.identity_status)

    def test_timeout_is_not_reported_as_empty_error_or_identity_checking(self):
        async def waiting():
            self.manager._registration_operation = 'Registry.Register'
            await asyncio.Future()
        with patch.object(self.manager, '_register', waiting):
            asyncio.run(self.manager._run_session())
        self.assertIn('Registry.Register', self.manager.error)
        self.assertIn('3/3', self.manager.error)
        self.assertIn('not registered', self.manager.identity_status)

    def test_shutdown_does_not_reactivate_portal_during_logout(self):
        bus = FakeBus()
        self.manager._bus = bus
        self.manager._session_handle = '/session/capture'
        asyncio.run(self.manager._close_session())
        self.assertTrue(bus.calls[-1].flags & MessageFlag.NO_AUTOSTART)
        self.assertTrue(bus.disconnected)

    def test_registry_refusal_is_not_a_transient_transport_failure(self):
        bus = FakeBus(identity_error='Desktop application ID not found')
        with patch('shortcuts.global_shortcut.MessageBus', return_value=bus) as factory:
            asyncio.run(self.manager._register_at_startup())
        self.assertEqual(factory.call_count, 1)
        self.assertIn('not registered', self.manager.identity_status)
        self.assertFalse(self.manager.can_configure)
