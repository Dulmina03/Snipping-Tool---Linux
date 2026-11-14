"""Wayland and X11 global-shortcut registration through XDG Desktop Portal and D-Bus."""

import asyncio
import logging
import threading
from typing import Optional
import uuid

from dbus_next import Message, MessageType, Variant
from dbus_next.aio import MessageBus
from dbus_next.constants import BusType
from PySide6.QtCore import QObject, Signal


from utils.desktop_entry import APP_ID, ensure_desktop_entry


logger = logging.getLogger(__name__)

PORTAL_BUS_NAME = "org.freedesktop.portal.Desktop"
PORTAL_OBJECT_PATH = "/org/freedesktop/portal/desktop"
REGISTRY_INTERFACE = "org.freedesktop.host.portal.Registry"
GLOBAL_SHORTCUTS_INTERFACE = "org.freedesktop.portal.GlobalShortcuts"
REQUEST_INTERFACE = "org.freedesktop.portal.Request"
SESSION_INTERFACE = "org.freedesktop.portal.Session"

SHORTCUT_ID = "open_capture_menu"
PREFERRED_TRIGGER = "<Ctrl><Shift>S"
REQUEST_TIMEOUT_SECONDS = 60


class GlobalShortcutManager(QObject):
    """Register global hotkey via XDG Desktop Portal and relay activation into Qt UI."""

    registration_succeeded = Signal(str)
    registration_failed = Signal(str)
    shortcut_activated = Signal()

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
        self._stop_event: Optional[asyncio.Event] = None
        self._request_futures: dict[str, asyncio.Future] = {}
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

    def start(self) -> bool:
        """Start registration in a background D-Bus event loop.

        Returns False if this manager is already running, preventing duplicate
        registration attempts for the same application session.
        """
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False

            self._registered = False
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
        self._stop_event = asyncio.Event()

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
                    self._stop_event = None

    async def _wait_for_stop(self):
        # Bounded polling also works when a confined runtime cannot wake the
        # asyncio self-pipe from another thread. No GUI API is touched here.
        while not self._shutdown_requested.is_set():
            await asyncio.sleep(0.05)

    async def _run_session(self):
        if self._shutdown_requested.is_set():
            return
        registration = asyncio.create_task(asyncio.wait_for(self._register(), REQUEST_TIMEOUT_SECONDS))
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
                logger.warning("Shortcut registration failed: %s", type(error).__name__)
                self.registration_failed.emit(str(error))
                return
            self._ready.set()
            await stopping
        finally:
            for task in (registration, stopping):
                if not task.done():
                    task.cancel()
            await asyncio.gather(registration, stopping, return_exceptions=True)

    async def _register(self) -> None:
        ensure_desktop_entry()

        try:
            self._bus = await MessageBus(bus_type=BusType.SESSION).connect()
        except Exception as bus_error:
            raise RuntimeError(f"Could not connect to D-Bus session bus: {bus_error}") from bus_error

        self._bus.add_message_handler(self._message_handler)

        # Establish application identity through the host portal Registry
        try:
            await self._register_identity()
        except Exception as ident_error:
            logger.warning("Application identity registration warning: %s", ident_error)

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

        shortcuts = [
            [
                self.shortcut_id,
                {
                    "description": Variant("s", self.shortcut_description),
                    "preferred_trigger": Variant("s", self.preferred_trigger),
                },
            ]
        ]

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
        bound_ids = {shortcut[0] for shortcut in bound_shortcuts}

        if self.shortcut_id not in bound_ids:
            raise RuntimeError(
                f"{self.preferred_trigger} was not registered. It may have been cancelled "
                "or rejected by the desktop portal."
            )

        with self._lock:
            self._registered = True

        self.registration_succeeded.emit(self.preferred_trigger)

    async def _register_identity(self) -> None:
        """Register application identity via org.freedesktop.host.portal.Registry."""
        reply = await self._bus.call(
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
                f"Portal Registry registration failed: {reply.error_name}"
            )

    async def _portal_request(self, member: str, signature: str, body: list) -> dict:
        reply = await self._bus.call(
            Message(
                destination=PORTAL_BUS_NAME,
                path=PORTAL_OBJECT_PATH,
                interface=GLOBAL_SHORTCUTS_INTERFACE,
                member=member,
                signature=signature,
                body=body,
            )
        )

        if reply.message_type == MessageType.ERROR:
            raise RuntimeError(
                f"GlobalShortcuts {member} failed: {reply.error_name}"
            )

        if not reply.body:
            raise RuntimeError(f"GlobalShortcuts {member} returned no request handle.")

        request_path = reply.body[0]
        response_future = asyncio.get_running_loop().create_future()
        self._request_futures[request_path] = response_future

        try:
            response_code, results = await asyncio.wait_for(
                response_future,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError as error:
            raise RuntimeError(
                f"Timed out waiting for GlobalShortcuts {member}."
            ) from error
        finally:
            self._request_futures.pop(request_path, None)

        if response_code != 0:
            raise RuntimeError(
                f"GlobalShortcuts {member} was cancelled or denied "
                f"(response code {response_code})."
            )

        return results

    def _message_handler(self, message) -> None:
        if message.message_type != MessageType.SIGNAL:
            return

        if message.interface == REQUEST_INTERFACE and message.member == "Response":
            response_future = self._request_futures.get(message.path)

            if response_future is not None and not response_future.done():
                response_future.set_result(message.body)

            return

        if (
            message.interface == GLOBAL_SHORTCUTS_INTERFACE
            and message.member == "Activated"
            and len(message.body) >= 2
        ):
            session_handle, shortcut_id = message.body[:2]

            if session_handle == self.session_handle and shortcut_id == self.shortcut_id:
                print(f"[SHORTCUT ACTIVATED] Real keypress detected: {shortcut_id}", flush=True)
                self.shortcut_activated.emit()

    @staticmethod
    def _variant_value(value):
        return value.value if isinstance(value, Variant) else value

    async def _close_session(self) -> None:
        if self._bus is None:
            return

        try:
            if self._session_handle:
                reply = await self._bus.call(
                    Message(
                        destination=PORTAL_BUS_NAME,
                        path=self._session_handle,
                        interface=SESSION_INTERFACE,
                        member="Close",
                    )
                )

                if reply.message_type == MessageType.ERROR:
                    logger.debug("Global shortcut session close notice: %s", reply.error_name)
        finally:
            self._bus.disconnect()
