"""GNOME first-use permission failure and request/shutdown regressions."""
import asyncio
from pathlib import Path
from types import SimpleNamespace as NS
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from dbus_next import MessageType, Variant
from PIL import Image
from test_phase01 import app, spin_until
from capture.screenshot_portal_request import request_screenshot, ScreenshotPortalError
from ui.capture_menu import CaptureMenu
from utils.desktop_entry import APP_ID


class Bus:
    unique_name = ':1.800'
    def __init__(self, code=0, method_error=None, registry_error=None, delayed=False, changed_path=False):
        self.code, self.method_error, self.registry_error = code, method_error, registry_error
        self.delayed, self.changed_path = delayed, changed_path
        self.calls = []
        self.handler = None
        self.closed = self.started = False
        self.uri = 'file:///tmp/public%20fixture.png'
    async def connect(self):
        return self
    def disconnect(self):
        self.closed = True
    def add_message_handler(self, handler):
        self.handler = handler
    def remove_message_handler(self, handler):
        self.handler = None
    async def call(self, message):
        self.calls.append(message)
        if message.member == 'Register':
            if self.registry_error:
                return NS(message_type=MessageType.ERROR,error_name=self.registry_error,body=['identity rejected'])
            return NS(message_type=MessageType.METHOD_RETURN,body=[])
        if message.member == 'Get':
            return NS(message_type=MessageType.METHOD_RETURN,body=[Variant('u',2)])
        if message.member == 'Close':
            return NS(message_type=MessageType.METHOD_RETURN,body=[])
        self.started = True
        if self.method_error:
            return NS(message_type=MessageType.ERROR,error_name=self.method_error,body=['test portal detail'])
        token = message.body[1]['handle_token'].value
        path = '/org/freedesktop/portal/desktop/request/1_800/' + token
        if self.changed_path:
            path += '_returned'
        if not self.delayed:
            self.handler(NS(message_type=MessageType.SIGNAL,interface='org.freedesktop.portal.Request',
                member='Response',path=path,body=[self.code, {'uri':Variant('s',self.uri)} if self.code==0 else {}]))
        return NS(message_type=MessageType.METHOD_RETURN,body=[path])


class RequestTests(unittest.TestCase):
    def request(self,bus):
        with patch('capture.screenshot_portal_request.MessageBus',return_value=bus):
            return asyncio.run(request_screenshot())

    def test_independent_connection_registers_before_screenshot(self):
        bus=Bus()
        self.assertEqual(self.request(bus),Path('/tmp/public fixture.png'))
        self.assertEqual([m.member for m in bus.calls][:3],['Register','Get','Screenshot'])
        self.assertEqual(bus.calls[0].body,[APP_ID,{}])
        screenshot=bus.calls[2]
        self.assertEqual(screenshot.body[0],'')  # Valid optional parent, not a fake wl_surface id.
        self.assertFalse(screenshot.body[1]['interactive'].value)
        self.assertTrue(bus.closed)
        self.assertIsNone(bus.handler)

    def test_background_focus_rejection_response_two_is_not_user_cancel(self):
        bus=Bus(code=2)
        with self.assertRaises(ScreenshotPortalError) as caught:
            self.request(bus)
        self.assertEqual(caught.exception.kind,'unexpected')
        self.assertEqual(caught.exception.response_code,2)
        self.assertIn('does not establish user cancellation',str(caught.exception))

    def test_response_one_reports_portal_cancellation_with_permission_ambiguity(self):
        with self.assertRaises(ScreenshotPortalError) as caught:
            self.request(Bus(code=1))
        self.assertEqual(caught.exception.kind,'cancelled')
        self.assertIn('permission was declined',str(caught.exception))

    def test_permission_missing_backend_and_other_method_errors_keep_details(self):
        for name,kind in [('AccessDenied','permission'),('ServiceUnknown','unavailable'),
                          ('UnknownMethod','unavailable'),('Failed','unexpected')]:
            with self.subTest(name=name),self.assertRaises(ScreenshotPortalError) as caught:
                self.request(Bus(method_error='org.freedesktop.DBus.Error.'+name))
            self.assertEqual(caught.exception.kind,kind)
            self.assertIn(name,str(caught.exception))
            self.assertIn('test portal detail',str(caught.exception))

    def test_rejected_registry_never_falls_back_to_anonymous_request(self):
        bus=Bus(registry_error='org.freedesktop.portal.Error.Failed')
        with self.assertRaises(ScreenshotPortalError) as caught:
            self.request(bus)
        self.assertEqual(caught.exception.kind,'identity')
        self.assertFalse(bus.started)
        self.assertTrue(bus.closed)

    def test_response_before_reply_on_changed_handle(self):
        self.assertEqual(self.request(Bus(changed_path=True)),Path('/tmp/public fixture.png'))

    def test_unsupported_uri_is_unexpected_error(self):
        bus=Bus();bus.uri='https://example.invalid/image.png'
        with self.assertRaises(ScreenshotPortalError) as caught:
            self.request(bus)
        self.assertEqual(caught.exception.kind,'unexpected')

    def test_cancel_closes_pending_request_and_disconnects(self):
        bus=Bus(delayed=True)
        async def scenario():
            with patch('capture.screenshot_portal_request.MessageBus',return_value=bus):
                task=asyncio.create_task(request_screenshot())
                while not bus.started:
                    await asyncio.sleep(0)
                task.cancel()
                await asyncio.gather(task,return_exceptions=True)
                self.assertTrue(task.cancelled())
        asyncio.run(scenario())
        self.assertTrue(any(m.member=='Close' for m in bus.calls))
        self.assertTrue(bus.closed)
        self.assertIsNone(bus.handler)

    def test_timeout_keeps_distinct_error_and_disconnects(self):
        bus=Bus()
        original=bus.call
        async def call(message):
            if message.member=='Screenshot':
                raise asyncio.TimeoutError()
            return await original(message)
        bus.call=call
        with self.assertRaises(ScreenshotPortalError) as caught:
            self.request(bus)
        self.assertEqual(caught.exception.kind,'timeout')
        self.assertTrue(bus.closed)


class PermissionWindowTests(unittest.TestCase):
    def setUp(self):
        self.menu=CaptureMenu()
        self.menu._show_toast=lambda _:None
    def tearDown(self):
        self.menu.shutdown();self.menu.jobs.close();app.processEvents()

    def test_focus_failure_offers_real_window_without_showing_controller(self):
        with patch('ui.capture_menu._portal_screenshot',new=AsyncMock(side_effect=ScreenshotPortalError('unexpected','response 2',2))) as portal:
            self.menu.launch_overlay();spin_until(lambda:not self.menu.busy)
            self.assertEqual(portal.await_count,1)  # No silent retry/consent.
            self.assertTrue(self.menu._permission_prompt.isVisible())
            self.assertFalse(self.menu.isVisible())
            self.assertIsNone(self.menu._overlay)
            self.menu._permission_prompt.reject()
            self.assertIsNone(self.menu._permission_prompt)

    def test_cancelled_portal_does_not_auto_retry_or_open_permission_window(self):
        with patch('ui.capture_menu._portal_screenshot',new=AsyncMock(side_effect=ScreenshotPortalError('cancelled','cancelled',1))) as portal:
            self.menu.launch_overlay();spin_until(lambda:not self.menu.busy)
            self.assertIsNone(self.menu._permission_prompt)
            self.assertEqual(portal.await_count,1)

    def test_explicit_continue_discards_permission_window_capture_and_recaptures(self):
        with tempfile.TemporaryDirectory() as folder:
            consent=Path(folder)/'consent.png';clean=Path(folder)/'clean.png'
            for path in (consent,clean):Image.new('RGB',(80,60),'white').save(path)
            with patch('ui.capture_menu._portal_screenshot',new=AsyncMock(side_effect=[
                    ScreenshotPortalError('unexpected','response 2',2),consent,clean])) as portal:
                self.menu.launch_overlay();spin_until(lambda:not self.menu.busy)
                self.menu._permission_prompt.continue_button.click()
                spin_until(lambda:not self.menu.busy)
                self.assertEqual(portal.await_count,3)
                self.assertFalse(consent.exists())
                self.assertEqual(self.menu._src_path,clean)
                self.assertIsNone(self.menu._permission_prompt)
                self.assertIsNotNone(self.menu._overlay)
                self.assertFalse(self.menu.isVisible())

    def test_escape_closing_permission_window_cancels_pending_request(self):
        started=[]
        async def waiting(**kwargs):
            started.append(True)
            await asyncio.sleep(60)
        self.menu._show_permission_prompt()
        with patch('ui.capture_menu._portal_screenshot',waiting):
            self.menu._permission_prompt.continue_button.click()
            task=self.menu._pending
            spin_until(lambda:bool(started))
            self.menu._permission_prompt.reject()
            spin_until(task.done)
            self.assertTrue(task.cancelled())
            self.assertIsNone(self.menu._permission_prompt)


class WindowAndQuitTests(unittest.TestCase):
    def test_window_capture_uses_identified_request_and_existing_save_copy(self):
        import capture.window_capture as window
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'portal-public.png'
            Image.new('RGB',(19,13),'blue').save(source)
            expected=source.read_bytes()
            with patch.object(window,'request_screenshot',new=AsyncMock(return_value=source)) as request, \
                 patch.object(window,'OUTPUT_DIR',Path(folder)/'saved'), \
                 patch.object(window,'copy_image_to_clipboard') as copy:
                result=asyncio.run(window.take_screenshot())
            request.assert_awaited_once_with(interactive=True)
            self.assertEqual(result.read_bytes(),expected)
            self.assertFalse(source.exists())
            copy.assert_called_once_with(result)

    def test_window_response_two_is_not_silently_returned_as_cancel(self):
        import capture.window_capture as window
        error=ScreenshotPortalError('unexpected','failure response 2',2)
        with patch.object(window,'request_screenshot',new=AsyncMock(side_effect=error)):
            with self.assertRaises(ScreenshotPortalError):
                asyncio.run(window.take_screenshot())

    def test_background_shutdown_cancels_pending_capture_without_tray(self):
        import main
        from test_phase01 import FakeShortcuts
        with patch.object(main, 'GlobalShortcutManager', FakeShortcuts):
            menu, manager = main.configure_application(app)
        try:
            entered = []
            async def pending(**kwargs):
                entered.append(True)
                await asyncio.sleep(60)
            with patch('ui.capture_menu._portal_screenshot', pending):
                manager.shortcut_activated.emit()
                spin_until(lambda: bool(entered))
                menu.shutdown()
                menu.jobs.close()
                self.assertFalse(menu.jobs.tasks)
                self.assertIsNone(menu._overlay)
                self.assertFalse(menu.isVisible())
        finally:
            menu.shutdown(); menu.jobs.close()
            app.aboutToQuit.disconnect(menu.shutdown)
