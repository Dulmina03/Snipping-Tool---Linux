"""Identified, cancellable Screenshot portal requests; no GUI or clipboard calls."""
import asyncio
import logging
from pathlib import Path
from urllib.parse import unquote, urlparse
import uuid

from dbus_next import Message, MessageType, Variant
from dbus_next.aio import MessageBus
from utils.desktop_entry import APP_ID
from utils.capture_latency import active_capture
from utils.capture_diagnostics import trace, timed

BUS_NAME = 'org.freedesktop.portal.Desktop'
OBJECT_PATH = '/org/freedesktop/portal/desktop'
INTERFACE = 'org.freedesktop.portal.Screenshot'
logger = logging.getLogger(__name__)


class ScreenshotPortalError(RuntimeError):
    def __init__(self, kind, detail, response_code=None):
        super().__init__(detail)
        self.kind = kind
        self.response_code = response_code


def method_error(reply, operation):
    name = reply.error_name or 'UnknownError'
    if name.endswith(('AccessDenied', 'NotAllowed')):
        kind = 'permission'
    elif name.endswith(('ServiceUnknown', 'NameHasNoOwner', 'UnknownInterface', 'UnknownMethod', 'NotFound')):
        kind = 'unavailable'
    else:
        kind = 'unexpected'
    return ScreenshotPortalError(kind, f'{operation}: {name}: {reply.body}')


@timed('portal_request_including_registration_and_user_dialog')
async def request_screenshot(interactive=False, parent_window=''):
    latency = active_capture.get()
    mark = latency.mark if latency is not None else lambda stage: None
    bus = MessageBus()
    handler = None
    request_started = False
    completed = False
    token = 'snip_' + uuid.uuid4().hex
    request_path = None
    try:
        await asyncio.wait_for(bus.connect(), 10)
        mark("portal_connected")
        # Registry attribution is per D-Bus connection, not per process. Never
        # rely on the separate GlobalShortcuts connection's registration.
        reply = await asyncio.wait_for(bus.call(Message(
            destination=BUS_NAME, path=OBJECT_PATH,
            interface='org.freedesktop.host.portal.Registry', member='Register',
            signature='sa{sv}', body=[APP_ID, {}])), 10)
        if reply.message_type == MessageType.ERROR:
            raise ScreenshotPortalError('identity',
                f'Screenshot identity registration failed: {reply.error_name}: {reply.body}')
        mark("portal_identity_registered")
        logger.info('Screenshot identity registered: app=%s connection=%s', APP_ID, bus.unique_name)
        version_reply = await asyncio.wait_for(bus.call(Message(
            destination=BUS_NAME, path=OBJECT_PATH,
            interface='org.freedesktop.DBus.Properties', member='Get',
            signature='ss', body=[INTERFACE, 'version'])), 10)
        if version_reply.message_type == MessageType.ERROR:
            raise method_error(version_reply, 'Screenshot portal version')
        logger.info('Screenshot portal version=%s', version_reply.body[0].value)
        request_path = '/org/freedesktop/portal/desktop/request/' + bus.unique_name[1:].replace('.', '_') + '/' + token
        future = asyncio.get_running_loop().create_future()
        early = {}

        def on_message(message):
            if (message.message_type == MessageType.SIGNAL
                    and message.interface == 'org.freedesktop.portal.Request'
                    and message.member == 'Response'):
                if message.path == request_path and not future.done():
                    mark("portal_response_signal")
                    future.set_result(message.body)
                elif not future.done():
                    early[message.path] = message.body

        handler = on_message
        bus.add_message_handler(handler)
        options = {'handle_token': Variant('s', token),
                   'interactive': Variant('b', interactive), 'modal': Variant('b', True)}
        logger.info('Screenshot request: connection=%s parent=%r interactive=%s modal=True token=%s',
                    bus.unique_name, parent_window, interactive, token)
        request_started = True
        mark("portal_method_call")
        reply = await asyncio.wait_for(bus.call(Message(
            destination=BUS_NAME, path=OBJECT_PATH, interface=INTERFACE,
            member='Screenshot', signature='sa{sv}', body=[parent_window, options])), 15)
        if reply.message_type == MessageType.ERROR:
            raise method_error(reply, 'Screenshot')
        if not reply.body or not isinstance(reply.body[0], str):
            raise ScreenshotPortalError('unexpected', 'Screenshot returned no request handle.')
        request_path = reply.body[0]
        logger.info('Screenshot request handle=%s', request_path)
        if request_path in early and not future.done():
            future.set_result(early[request_path])
        response = await asyncio.wait_for(future, 120)
        mark("portal_response_received")
        if len(response) != 2:
            raise ScreenshotPortalError('unexpected', 'Malformed Screenshot portal response.')
        code, results = response
        completed = True
        # Do not log screenshot bytes or the local filename/URI.
        logger.info('Screenshot response code=%s payload=%s', code,
                    {key: '<local screenshot URI>' if key == 'uri' else str(value)
                     for key, value in results.items()})
        if code == 1:
            raise ScreenshotPortalError('cancelled',
                'Portal reports cancellation (1); this may also mean permission was declined.', code)
        if code != 0:
            raise ScreenshotPortalError('unexpected',
                f'Screenshot portal failed (response {code}). This does not establish user cancellation.', code)
        uri = results.get('uri')
        uri = uri.value if isinstance(uri, Variant) else uri
        if not isinstance(uri, str):
            raise ScreenshotPortalError('unexpected', 'Screenshot response contains no file URI.')
        parsed = urlparse(uri)
        if parsed.scheme != 'file' or parsed.netloc not in ('', 'localhost') or not parsed.path:
            raise ScreenshotPortalError('unexpected', 'Screenshot returned an unsupported file URI.')
        source = Path(unquote(parsed.path))
        trace('portal_return', response=code, path=str(source), exists=source.is_file(),
              bytes=source.stat().st_size if source.is_file() else None, interactive=interactive)
        return source
    except asyncio.TimeoutError as error:
        raise ScreenshotPortalError('timeout', 'Timed out waiting for the Screenshot portal.') from error
    except (ScreenshotPortalError, asyncio.CancelledError):
        raise
    except Exception as error:
        raise ScreenshotPortalError('unexpected', f'Screenshot request failed: {type(error).__name__}: {error}') from error
    finally:
        if request_started and not completed and request_path:
            try:
                await asyncio.wait_for(bus.call(Message(destination=BUS_NAME,
                    path=request_path, interface='org.freedesktop.portal.Request', member='Close')), 1)
            except Exception:
                pass
        if handler is not None:
            bus.remove_message_handler(handler)
        bus.disconnect()
