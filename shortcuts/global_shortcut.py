"""Wayland and X11 global-shortcut registration through XDG Desktop Portal and D-Bus."""

import asyncio
import logging
from pathlib import Path
import queue
import threading
from typing import Optional
import uuid
import xml.etree.ElementTree as ET

from dbus_next import Message, MessageType, MessageFlag, Variant
from dbus_next.aio import MessageBus
from dbus_next.constants import BusType
from PySide6.QtCore import QObject, Signal


from utils.desktop_entry import APP_ID, ensure_desktop_entry
from shortcuts.assignment import comparison
from utils.capture_latency import signal_received


logger = logging.getLogger(__name__)

PORTAL_BUS_NAME = "org.freedesktop.portal.Desktop"
PORTAL_OBJECT_PATH = "/org/freedesktop/portal/desktop"
REGISTRY_INTERFACE = "org.freedesktop.host.portal.Registry"
GLOBAL_SHORTCUTS_INTERFACE = "org.freedesktop.portal.GlobalShortcuts"
REQUEST_INTERFACE = "org.freedesktop.portal.Request"
SESSION_INTERFACE = "org.freedesktop.portal.Session"

SHORTCUT_ID = "open_capture_menu"
PREFERRED_TRIGGER = "ALT+SHIFT+s"
REQUEST_TIMEOUT_SECONDS = 60
STARTUP_ATTEMPTS = 3
STARTUP_RETRY_SECONDS = 1
TRANSIENT_DBUS_ERRORS = {
    'org.freedesktop.DBus.Error.NoReply',
    'org.freedesktop.DBus.Error.TimedOut',
    'org.freedesktop.DBus.Error.Timeout',
    'org.freedesktop.DBus.Error.ServiceUnknown',
    'org.freedesktop.DBus.Error.NameHasNoOwner',
    'org.freedesktop.DBus.Error.Disconnected',
}


class PortalStartupError(RuntimeError):
    """A transient transport/startup failure, never a permission refusal."""



class GlobalShortcutManager(QObject):
    """Register global hotkey via XDG Desktop Portal and relay activation into Qt UI."""

    registration_succeeded = Signal(str)
    registration_failed = Signal(str)
    shortcut_activated = Signal()
    assignment_changed = Signal(str, str, str)  # requested, portal description, comparison
    identity_changed = Signal(str)
    configuration_available_changed = Signal(bool)
    configuration_message = Signal(str)

    def __init__(
        self,
        preferred_trigger: str = PREFERRED_TRIGGER,
        description: str = "Open AI Snipping Tool capture menu",
        shortcut_id: str = SHORTCUT_ID,
    ):
        super().__init__()

        self.preferred_trigger = preferred_trigger
        self.shortcut_description = description
        self.shortcut_id = shortcut_id

        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._bus: Optional[MessageBus] = None
        self._session_handle: Optional[str] = None
        self._request_futures: dict[str, asyncio.Future] = {}
        self._assigned_trigger = ""
        self._assignment_revision = 0
        self._portal_version = None
        self._configure_supported = False
        self._identity_blocked = False
        self._identity_status = "Identity not checked"
        self._registration_operation = "Not started"
        self._commands = queue.Queue()
        self._action_tasks = set()
        self._configuring = False
        self._registered = False
        self._error: Optional[str] = None
        self._ready = threading.Event()
        self._shutdown_requested = threading.Event()
        self._lock = threading.Lock()

    @property
    def is_registered(self) -> bool:
        with self._lock:
            return self._registered

    @property
    def error(self) -> str | None:
        with self._lock:
            return self._error

    @property
    def session_handle(self) -> str | None:
        with self._lock:
            return self._session_handle

    @property
    def assigned_trigger(self):
        with self._lock:
            return self._assigned_trigger

    @property
    def identity_status(self):
        with self._lock:
            return self._identity_status

    @property
    def portal_version(self):
        with self._lock:
            return self._portal_version

    @property
    def can_configure(self):
        with self._lock:
            return bool(self._configure_supported and self._session_handle
                        and not self._identity_blocked and not self._shutdown_requested.is_set())

    def request_configuration(self):
        """Queue an explicit tray action; never open configuration on startup."""
        if not self.can_configure:
            self.configuration_message.emit("Shortcut configuration unavailable; check portal support and application identity.")
            return False
        with self._lock:
            if self._configuring:
                return False
            self._configuring = True
        self._commands.put('configure')
        return True

    def start(self) -> bool:
        """Start registration in a background D-Bus event loop.

        Returns False if this manager is already running, preventing duplicate
        registration attempts for the same application session.
        """
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False

            self._registered = False
            self._assigned_trigger = ""
            self._assignment_revision = 0
            self._configure_supported = False
            self._portal_version = None
            self._identity_blocked = False
            self._identity_status = "Identity not checked"
            self._registration_operation = "Not started"
            self._configuring = False
            self._commands = queue.Queue()
            self._error = None
            self._session_handle = None
            self._ready.clear()
            self._shutdown_requested.clear()
            self._thread = threading.Thread(
                target=self._thread_main,
                name="global-shortcut-portal",
                daemon=True,
            )
            self._thread.start()

        return True

    def wait_until_ready(self, timeout: float = REQUEST_TIMEOUT_SECONDS) -> bool:
        """Wait until registration succeeds or fails."""
        self._ready.wait(timeout)
        return self.is_registered

    def stop(self) -> None:
        """Close the portal session and stop the D-Bus event loop."""
        with self._lock:
            thread = self._thread

        self._shutdown_requested.set()

        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=5)

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop

        try:
            loop.run_until_complete(self._run_session())
        finally:
            try:
                loop.run_until_complete(asyncio.wait_for(self._close_session(), 2))
            except Exception as error:
                logger.warning("Shortcut cleanup failed: %s", type(error).__name__)
            finally:
                if self._bus is not None:
                    self._bus.disconnect()
                loop.close()
                self._ready.set()
                with self._lock:
                    self._registered = False
                    self._session_handle = None
                    self._bus = None
                    self._loop = None

    async def _wait_for_stop(self):
        # Bounded polling also works when a confined runtime cannot wake the
        # asyncio self-pipe from another thread. No GUI API is touched here.
        while not self._shutdown_requested.is_set():
            try:
                command = self._commands.get_nowait()
            except queue.Empty:
                pass
            else:
                self._start_action(self._configure_shortcuts() if command == 'configure'
                                   else self._refresh_assignment())
            await asyncio.sleep(0.05)

    async def _run_session(self):
        if self._shutdown_requested.is_set():
            return
        registration = asyncio.create_task(self._register_at_startup())
        stopping = asyncio.create_task(self._wait_for_stop())
        try:
            done, _ = await asyncio.wait((registration, stopping), return_when=asyncio.FIRST_COMPLETED)
            if stopping in done:
                return
            try:
                registration.result()
            except Exception as error:
                with self._lock:
                    self._error = str(error)
                logger.warning("Shortcut registration failed at %s: %s: %s",
                               self._registration_operation, type(error).__name__, error)
                self.registration_failed.emit(str(error))
                return
            self._ready.set()
            await stopping
        finally:
            for task in (registration, stopping):
                if not task.done():
                    task.cancel()
            await asyncio.gather(registration, stopping, return_exceptions=True)
            for task in tuple(self._action_tasks):
                task.cancel()
            if self._action_tasks:
                await asyncio.gather(*tuple(self._action_tasks), return_exceptions=True)
            self.configuration_available_changed.emit(False)

    def _identity_unavailable(self, detail):
        # Cancellation is a BaseException; the Registry exception handler alone
        # cannot update this state when the outer registration timeout expires.
        if not self.identity_status.startswith('Host identity registered:'):
            status = f'Identity not registered: {detail}'
            with self._lock:
                self._identity_status = status
            self.identity_changed.emit(status)

    async def _register_at_startup(self):
        """At most three startup attempts; never rebind an existing session.

        The portal can still be restarting after logout when GNOME starts us.
        Registry.Register on a fresh connection is the readiness/identity check.
        Only a transport failure before CreateSession may be retried. Consent,
        backend errors and configured bindings are never reset or retried.
        """
        for attempt in range(1, STARTUP_ATTEMPTS + 1):
            started = asyncio.get_running_loop().time()
            with self._lock:
                self._identity_status = f'Waiting for desktop portal (startup attempt {attempt}/{STARTUP_ATTEMPTS})'
                self._identity_blocked = False
            self.identity_changed.emit(self.identity_status)
            try:
                await asyncio.wait_for(self._register(), REQUEST_TIMEOUT_SECONDS)
                with self._lock:
                    self._error = None
                return
            except asyncio.CancelledError:
                self._identity_unavailable('Registration stopped before identity was confirmed.')
                raise
            except (TimeoutError, PortalStartupError, ConnectionError, EOFError) as error:
                detail = (f'{self._registration_operation}: {type(error).__name__}: {error} '
                          f'(startup attempt {attempt}/{STARTUP_ATTEMPTS})')
                self._identity_unavailable(detail)
                logger.warning('%s; elapsed=%.3fs', detail,
                               asyncio.get_running_loop().time() - started)
                if self.session_handle or attempt == STARTUP_ATTEMPTS:
                    raise RuntimeError(detail) from error
                # A new connection must register its own identity. Close the old
                # transport before retrying; no sessions/bindings are discarded.
                await self._close_session()
                self._bus = None
                self._request_futures.clear()
                # Short, cancellable backoff for immediate ServiceUnknown errors;
                # no GUI blocking, unbounded polling or post-startup retry loop.
                await asyncio.sleep(STARTUP_RETRY_SECONDS)
            except Exception as error:
                self._identity_unavailable(str(error))
                raise

    async def _call(self, message):
        operation = f'{message.interface}.{message.member}'
        self._registration_operation = operation
        started = asyncio.get_running_loop().time()
        logger.info('Portal operation=%s connection=%s app_id=%s started',
                    operation, self._bus.unique_name, APP_ID)
        try:
            reply = await self._bus.call(message)
        except BaseException as error:
            logger.warning('Portal operation=%s elapsed=%.3fs exception=%s: %s',
                           operation, asyncio.get_running_loop().time() - started,
                           type(error).__name__, error)
            raise
        logger.info('Portal operation=%s elapsed=%.3fs error=%s', operation,
                    asyncio.get_running_loop().time() - started,
                    reply.error_name if reply.message_type == MessageType.ERROR else 'none')
        if reply.message_type == MessageType.ERROR and reply.error_name in TRANSIENT_DBUS_ERRORS:
            raise PortalStartupError(f'{operation}: {reply.error_name}: {reply.body}')
        return reply

    async def _register(self) -> None:
        self._registration_operation = 'Session D-Bus connect'
        ensure_desktop_entry()

        try:
            self._bus = await MessageBus(bus_type=BusType.SESSION).connect()
        except Exception as bus_error:
            raise RuntimeError(f"Could not connect to D-Bus session bus: {bus_error}") from bus_error

        self._bus.add_message_handler(self._message_handler)

        # Establish application identity through the host portal Registry
        try:
            await self._register_identity()
        except PortalStartupError:
            raise
        except Exception as ident_error:
            detail = str(ident_error)
            # Never configure another portal-detected identity when our app ID
            # could not be confirmed (including an inherited editor sandbox).
            blocked = True
            context = ""
            try:
                if 'snap.' in Path('/proc/self/cgroup').read_text():
                    context = " Inherited Snap scope detected (possibly Snap VS Code)."
            except OSError:
                pass
            status = (f"Identity not registered for {APP_ID}: {detail}.{context} "
                      "Launch from GNOME's application grid to verify host identity.")
            with self._lock:
                self._identity_status = status
                self._identity_blocked = blocked
            logger.warning("%s", status)
            self.identity_changed.emit(status)
        else:
            status = f"Host identity registered: {APP_ID}"
            with self._lock:
                self._identity_status = status
            self.identity_changed.emit(status)

        # Subscribe explicitly: raw message handlers alone do not request
        # broadcast GlobalShortcuts signals from the session bus.
        match_reply = await self._call(Message(
            destination='org.freedesktop.DBus', path='/org/freedesktop/DBus',
            interface='org.freedesktop.DBus', member='AddMatch', signature='s',
            body=["type='signal',sender='org.freedesktop.portal.Desktop',interface='org.freedesktop.portal.GlobalShortcuts'"]))
        if match_reply.message_type == MessageType.ERROR:
            raise RuntimeError('Could not subscribe to desktop shortcut changes.')
        await self._inspect_capabilities()

        session_token = f"ai_snipping_{uuid.uuid4().hex}"
        create_results = await self._portal_request(
            member="CreateSession",
            signature="a{sv}",
            body=[
                {
                    "handle_token": Variant("s", f"request_{uuid.uuid4().hex}"),
                    "session_handle_token": Variant("s", session_token),
                }
            ],
        )

        session_handle = self._variant_value(create_results.get("session_handle"))

        if not isinstance(session_handle, str) or not session_handle:
            raise RuntimeError("GlobalShortcuts portal returned no session handle.")

        with self._lock:
            self._session_handle = session_handle

        # Read remembered choices; a preferred trigger is only a suggestion for
        # a new binding, never a request to replace a configured user shortcut.
        previous = await self._list_shortcuts()
        remembered = any(entry[0] == self.shortcut_id for entry in previous)
        shortcut_options = {"description": Variant("s", self.shortcut_description)}
        if not remembered:
            shortcut_options["preferred_trigger"] = Variant("s", self.preferred_trigger)
        logger.info("Shortcut requested=%s; remembered binding=%s", self.preferred_trigger, remembered)
        shortcuts = [
            [
                self.shortcut_id,
                shortcut_options,
            ]
        ]

        revision_before_bind = self._assignment_revision
        bind_results = await self._portal_request(
            member="BindShortcuts",
            signature="oa(sa{sv})sa{sv}",
            body=[
                session_handle,
                shortcuts,
                "",
                {"handle_token": Variant("s", f"request_{uuid.uuid4().hex}")},
            ],
        )

        bound_shortcuts = self._variant_value(bind_results.get("shortcuts", []))
        if not any(entry[0] == self.shortcut_id for entry in bound_shortcuts):
            raise RuntimeError("Desktop did not bind the capture shortcut; it may have been cancelled or denied.")
        if revision_before_bind == self._assignment_revision:
            self._apply_assignment(bound_shortcuts, 'BindShortcuts')
        await self._refresh_assignment()
        if self.is_registered:
            self.registration_succeeded.emit(self.assigned_trigger or 'Assigned key not supplied by desktop')
        self.configuration_available_changed.emit(self.can_configure)

    async def _inspect_capabilities(self):
        # Introspection may advertise unimplemented generated methods. Version 2
        # is the contract that adds ConfigureShortcuts; require both checks.
        version, supported = None, False
        try:
            reply = await self._call(Message(
                destination=PORTAL_BUS_NAME, path=PORTAL_OBJECT_PATH,
                interface='org.freedesktop.DBus.Properties', member='Get',
                signature='ss', body=[GLOBAL_SHORTCUTS_INTERFACE, 'version']))
            if reply.message_type != MessageType.ERROR:
                version = self._variant_value(reply.body[0])
        except Exception as error:
            logger.warning('Shortcut version unavailable: %s', type(error).__name__)
        try:
            reply = await self._call(Message(
                destination=PORTAL_BUS_NAME, path=PORTAL_OBJECT_PATH,
                interface='org.freedesktop.DBus.Introspectable', member='Introspect'))
            if reply.message_type != MessageType.ERROR:
                # dbus-next 0.2.3 cannot parse this machine's unrelated
                # power-saver-enabled property. Inspect only the needed method.
                root = ET.fromstring(reply.body[0])
                for interface in root.findall('interface'):
                    if interface.get('name') != GLOBAL_SHORTCUTS_INTERFACE:
                        continue
                    for method in interface.findall('method'):
                        signature = ''.join(arg.get('type', '') for arg in method.findall('arg')
                                            if arg.get('direction', 'in') == 'in')
                        if method.get('name') == 'ConfigureShortcuts' and signature == 'osa{sv}':
                            supported = True
        except Exception as error:
            logger.warning('Shortcut capability inspection unavailable: %s', type(error).__name__)
        with self._lock:
            self._portal_version = version
            self._configure_supported = bool(isinstance(version, int) and version >= 2 and supported)
        if not self._configure_supported:
            self.configuration_message.emit(
                'Shortcut configuration unavailable: this desktop backend does not support '
                'the required GlobalShortcuts version 2 method. The assigned shortcut remains active.')

    async def _list_shortcuts(self):
        results = await self._portal_request(member='ListShortcuts', signature='oa{sv}', body=[
            self.session_handle, {'handle_token': Variant('s', 'list_' + uuid.uuid4().hex)}])
        return self._variant_value(results.get('shortcuts', []))

    async def _refresh_assignment(self):
        revision = self._assignment_revision
        try:
            entries = await self._list_shortcuts()
        except Exception as error:
            logger.warning('Active shortcut verification failed: %s', type(error).__name__)
            self.configuration_message.emit('Could not verify active assignment; showing the last portal-reported value.')
            return
        if revision == self._assignment_revision:
            self._apply_assignment(entries, 'ListShortcuts')

    def _apply_assignment(self, entries, source):
        description, found = '', False
        for shortcut_id, info in self._variant_value(entries):
            if shortcut_id == self.shortcut_id:
                found = True
                candidate = self._variant_value(info.get('trigger_description', ''))
                description = candidate if isinstance(candidate, str) else ''
                break
        with self._lock:
            self._assigned_trigger = description
            self._registered = found
            self._assignment_revision += 1
        state = comparison(self.preferred_trigger, description) if found else 'unbound'
        actual = description or ('Assigned key not supplied by desktop' if found else 'Not assigned')
        logger.info('Shortcut requested=%s; actual=%s; source=%s', self.preferred_trigger, actual, source)
        if state == 'different':
            logger.warning('Desktop assigned a different capture shortcut: requested=%s; actual=%s',
                           self.preferred_trigger, actual)
        self.assignment_changed.emit(self.preferred_trigger, actual, state)

    def _start_action(self, coroutine):
        task = asyncio.create_task(coroutine)
        self._action_tasks.add(task)
        def finished(task):
            self._action_tasks.discard(task)
            if not task.cancelled() and task.exception() is not None:
                logger.warning('Shortcut action failed: %s', type(task.exception()).__name__)
        task.add_done_callback(finished)

    async def _configure_shortcuts(self):
        try:
            if not self.can_configure:
                raise RuntimeError('Configuration unavailable for this application identity or portal.')
            reply = await asyncio.wait_for(self._call(Message(
                destination=PORTAL_BUS_NAME, path=PORTAL_OBJECT_PATH,
                interface=GLOBAL_SHORTCUTS_INTERFACE, member='ConfigureShortcuts',
                signature='osa{sv}', body=[self.session_handle, '', {}])), REQUEST_TIMEOUT_SECONDS)
            if reply.message_type == MessageType.ERROR:
                if reply.error_name in ('org.freedesktop.DBus.Error.UnknownMethod',
                                        'org.freedesktop.portal.Error.NotImplemented'):
                    with self._lock:
                        self._configure_supported = False
                    self.configuration_available_changed.emit(False)
                    raise RuntimeError(
                        'Desktop backend does not support shortcut configuration; action disabled. '
                        f'The assigned shortcut remains active. ({reply.error_name})')
                raise RuntimeError(f'{reply.error_name}: {reply.body}')
            self.configuration_message.emit('Desktop shortcut configuration requested. Changes appear after confirmation.')
            await self._refresh_assignment()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.configuration_message.emit(f'Cannot open shortcut configuration: {error}')
        finally:
            with self._lock:
                self._configuring = False

    async def _register_identity(self) -> None:
        """Register application identity via org.freedesktop.host.portal.Registry."""
        reply = await self._call(
            Message(
                destination=PORTAL_BUS_NAME,
                path=PORTAL_OBJECT_PATH,
                interface=REGISTRY_INTERFACE,
                member="Register",
                signature="sa{sv}",
                body=[APP_ID, {}],
            )
        )

        if reply.message_type == MessageType.ERROR:
            raise RuntimeError(
                f"Portal Registry registration failed: {reply.error_name}: {reply.body}"
            )

    async def _portal_request(self, member: str, signature: str, body: list) -> dict:
        token = self._variant_value(body[-1]['handle_token'])
        sender = self._bus.unique_name[1:].replace('.', '_')
        path = f'/org/freedesktop/portal/desktop/request/{sender}/{token}'
        future = asyncio.get_running_loop().create_future()
        self._request_futures[path] = future
        actual_path = path
        try:
            reply = await asyncio.wait_for(self._call(Message(
                destination=PORTAL_BUS_NAME, path=PORTAL_OBJECT_PATH,
                interface=GLOBAL_SHORTCUTS_INTERFACE, member=member,
                signature=signature, body=body)), REQUEST_TIMEOUT_SECONDS)
            if reply.message_type == MessageType.ERROR:
                raise RuntimeError(f'GlobalShortcuts {member} failed: {reply.error_name}: {reply.body}')
            if not reply.body:
                raise RuntimeError(f'GlobalShortcuts {member} returned no request handle.')
            actual_path = reply.body[0]
            if actual_path != path:
                self._request_futures[actual_path] = future
            self._registration_operation = f'GlobalShortcuts.{member} Response'
            response_code, results = await asyncio.wait_for(future, REQUEST_TIMEOUT_SECONDS)
            logger.info('Portal response operation=%s code=%s', member, response_code)
            if response_code != 0:
                raise RuntimeError(f'GlobalShortcuts {member} cancelled or denied (response code {response_code}).')
            return results
        except asyncio.TimeoutError as error:
            raise RuntimeError(f'Timed out waiting for GlobalShortcuts {member}.') from error
        finally:
            self._request_futures.pop(path, None)
            self._request_futures.pop(actual_path, None)

    def _message_handler(self, message) -> None:
        if message.message_type != MessageType.SIGNAL:
            return

        if message.interface == REQUEST_INTERFACE and message.member == "Response":
            response_future = self._request_futures.get(message.path)

            if response_future is not None and not response_future.done():
                response_future.set_result(message.body)

            return

        if (message.interface == GLOBAL_SHORTCUTS_INTERFACE
                and message.member == 'ShortcutsChanged' and len(message.body) >= 2
                and message.body[0] == self.session_handle):
            entries = self._variant_value(message.body[1])
            if not entries or any(entry[0] == self.shortcut_id for entry in entries):
                self._apply_assignment(entries, 'ShortcutsChanged')
            self._commands.put('refresh')
            return

        if (
            message.interface == GLOBAL_SHORTCUTS_INTERFACE
            and message.member == "Activated"
            and len(message.body) >= 2
        ):
            session_handle, shortcut_id = message.body[:2]

            if session_handle == self.session_handle and shortcut_id == self.shortcut_id:
                signal_received()
                logger.info("Portal Activated signal for %s", shortcut_id)
                self.shortcut_activated.emit()

    @staticmethod
    def _variant_value(value):
        return value.value if isinstance(value, Variant) else value

    async def _close_session(self) -> None:
        if self._bus is None:
            return

        try:
            if self._session_handle:
                reply = await self._call(
                    Message(
                        destination=PORTAL_BUS_NAME,
                        path=self._session_handle,
                        interface=SESSION_INTERFACE,
                        member="Close",
                        flags=MessageFlag.NO_AUTOSTART,
                    )
                )

                if reply.message_type == MessageType.ERROR:
                    logger.debug("Global shortcut session close notice: %s", reply.error_name)
        finally:
            self._bus.disconnect()
