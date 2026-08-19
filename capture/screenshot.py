import asyncio
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

from dbus_next import Message, MessageType, Variant
from dbus_next.aio import MessageBus


PORTAL_BUS = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"

SCREENSHOT_INTERFACE = "org.freedesktop.portal.Screenshot"
REQUEST_INTERFACE = "org.freedesktop.portal.Request"


class ScreenshotCapture:

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

        token = (
            "snippingtool_"
            + uuid.uuid4().hex
        )

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
                f"Screenshot request failed: "
                f"{reply.error_name}"
            )

        request_path = reply.body[0]

        future = (
            asyncio.get_running_loop()
            .create_future()
        )

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
                future.set_result(
                    message.body
                )

        self.bus_add_handler = response_handler

        bus.add_message_handler(
            response_handler
        )

        try:
            response, results = (
                await asyncio.wait_for(
                    future,
                    timeout=120,
                )
            )

        finally:
            bus.remove_message_handler(
                response_handler
            )

            bus.disconnect()

        if response != 0:
            raise RuntimeError(
                "Screenshot was cancelled."
            )

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
            raise ValueError(
                f"Unknown capture mode: {mode}"
            )

        results = await self._request(
            options
        )

        uri = results["uri"].value

        destination = (
            self._create_filename()
        )

        self._copy_screenshot(
            uri,
            destination,
        )

        return destination

    async def capture_full_screen(self):

        return await self.capture(
            "screen"
        )

    async def capture_window(self):

        return await self.capture(
            "window"
        )

    async def capture_area(self):

        return await self.capture(
            "area"
        )

    def _create_filename(self):

        timestamp = datetime.now().strftime(
            "%Y-%m-%d_%H-%M-%S"
        )

        return (
            self.screenshot_folder
            / f"Screenshot_{timestamp}.png"
        )

    @staticmethod
    def _copy_screenshot(
        uri,
        destination,
    ):

        if not uri.startswith("file://"):
            raise RuntimeError(
                f"Unsupported screenshot URI: "
                f"{uri}"
            )

        parsed_uri = urlparse(uri)

        source = unquote(
            parsed_uri.path
        )

        shutil.copy2(
            source,
            destination,
        )