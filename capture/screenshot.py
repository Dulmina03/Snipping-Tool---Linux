"""Screen capture utilities via XDG Desktop Portal and PySide6."""

import asyncio
from datetime import datetime
from pathlib import Path
import shutil
from urllib.parse import unquote, urlparse
import uuid

from dbus_next import Message, MessageType, Variant
from dbus_next.aio import MessageBus
from PIL import Image
from PySide6.QtGui import QPixmap

from utils.clipboard import copy_image_to_clipboard


PORTAL_BUS = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"

SCREENSHOT_INTERFACE = "org.freedesktop.portal.Screenshot"
REQUEST_INTERFACE = "org.freedesktop.portal.Request"


class ScreenshotCapture:
    """Full-screen, window, and area screenshot capture engine."""

    def __init__(self):
        self.screenshot_folder = (
            Path.home()
            / "Pictures"
            / "Screenshots"
        )

        self.screenshot_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

    async def _request(self, options):
        bus = await MessageBus().connect()

        token = "snippingtool_" + uuid.uuid4().hex

        options["handle_token"] = Variant(
            "s",
            token,
        )

        message = Message(
            destination=PORTAL_BUS,
            path=PORTAL_PATH,
            interface=SCREENSHOT_INTERFACE,
            member="Screenshot",
            signature="sa{sv}",
            body=[
                "",
                options,
            ],
        )

        reply = await bus.call(message)

        if reply.message_type == MessageType.ERROR:
            bus.disconnect()
            raise RuntimeError(
                f"Screenshot request failed: {reply.error_name}"
            )

        request_path = reply.body[0]

        future = asyncio.get_running_loop().create_future()

        def response_handler(message):
            if message.message_type != MessageType.SIGNAL:
                return

            if message.interface != REQUEST_INTERFACE:
                return

            if message.member != "Response":
                return

            if message.path != request_path:
                return

            if not future.done():
                future.set_result(message.body)

        self.bus_add_handler = response_handler
        bus.add_message_handler(response_handler)

        try:
            response, results = await asyncio.wait_for(
                future,
                timeout=120,
            )
        finally:
            bus.remove_message_handler(response_handler)
            bus.disconnect()

        if response != 0:
            raise RuntimeError("Screenshot was cancelled.")

        return results

    async def capture(
        self,
        mode="screen",
    ):
        if mode == "screen":
            options = {
                "interactive": Variant(
                    "b",
                    False,
                ),
            }
        elif mode == "window":
            options = {
                "interactive": Variant(
                    "b",
                    True,
                ),
            }
        elif mode == "area":
            options = {
                "interactive": Variant(
                    "b",
                    True,
                ),
            }
        else:
            raise ValueError(f"Unknown capture mode: {mode}")

        results = await self._request(options)
        uri = results["uri"].value

        destination = self._create_filename()
        self._copy_screenshot(uri, destination)

        try:
            copy_image_to_clipboard(destination)
            print("Copied to clipboard.")
        except Exception as error:
            print("WARNING: Screenshot saved, but clipboard copy failed:")
            print(error)

        return destination

    async def capture_full_screen(self):
        """Capture the full screen to a file and copy to clipboard."""
        return await self.capture("screen")

    async def capture_window(self):
        """Capture a selected window."""
        return await self.capture("window")

    async def capture_area(self):
        """Capture a selected screen area."""
        return await self.capture("area")

    async def capture_full_screen_pixmap(self) -> QPixmap:
        """Capture full screen and return as QPixmap."""
        path = await self.capture_full_screen()
        return QPixmap(str(path))

    async def capture_full_screen_pil(self) -> Image.Image:
        """Capture full screen and return as PIL Image."""
        path = await self.capture_full_screen()
        return Image.open(str(path))

    def _create_filename(self):
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return self.screenshot_folder / f"Screenshot_{timestamp}.png"

    @staticmethod
    def _copy_screenshot(uri, destination):
        if not uri.startswith("file://"):
            raise RuntimeError(f"Unsupported screenshot URI: {uri}")

        parsed_uri = urlparse(uri)
        source = unquote(parsed_uri.path)
        shutil.copy2(source, destination)


def capture_screen_pixmap() -> QPixmap:
    """Synchronous helper to capture full screen as a QPixmap."""
    capture_engine = ScreenshotCapture()
    path = asyncio.run(capture_engine.capture_full_screen())
    return QPixmap(str(path))


def capture_screen_pil() -> Image.Image:
    """Synchronous helper to capture full screen as a PIL Image."""
    capture_engine = ScreenshotCapture()
    path = asyncio.run(capture_engine.capture_full_screen())
    return Image.open(str(path))
