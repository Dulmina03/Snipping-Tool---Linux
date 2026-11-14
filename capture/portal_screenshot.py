import asyncio
import os
import shutil
import time
from pathlib import Path

from dbus_next import Message, Variant
from dbus_next.aio import MessageBus
from dbus_next.constants import MessageType


PORTAL_BUS = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"

SCREENSHOT_INTERFACE = (
    "org.freedesktop.portal.Screenshot"
)

REQUEST_INTERFACE = (
    "org.freedesktop.portal.Request"
)


class PortalScreenshot:

    def __init__(self):
        self.bus = None

    async def connect(self):

        print("Connecting to Screenshot portal...")

        self.bus = await MessageBus().connect()

        print("Connected to portal.")

    async def screenshot(self):

        if self.bus is None:
            await self.connect()

        # ---------------------------------------------------------
        # Create a unique request token.
        # ---------------------------------------------------------

        token = (
            "ai_snipping_tool_"
            + str(os.getpid())
            + "_"
            + str(int(time.time() * 1000))
        )

        print()
        print("Creating screenshot request...")

        # ---------------------------------------------------------
        # Portal Screenshot options.
        #
        # IMPORTANT:
        # D-Bus a{sv} values must be Variant objects.
        # ---------------------------------------------------------

        options = {
            "handle_token": Variant(
                "s",
                token
            )
        }

        # ---------------------------------------------------------
        # Create the D-Bus message.
        # ---------------------------------------------------------

        message = Message(
            destination=PORTAL_BUS,
            path=PORTAL_PATH,
            interface=SCREENSHOT_INTERFACE,
            member="Screenshot",
            signature="sa{sv}",
            body=[
                "",
                options
            ]
        )

        reply = await self.bus.call(
            message
        )

        # ---------------------------------------------------------
        # Check for D-Bus error.
        # ---------------------------------------------------------

        if reply.message_type == MessageType.ERROR:

            raise RuntimeError(
                f"Screenshot request failed: "
                f"{reply.error_name}: "
                f"{reply.body}"
            )

        if not reply.body:

            raise RuntimeError(
                "Screenshot portal returned "
                "no request path."
            )

        request_path = reply.body[0]

        print(
            "Screenshot request created:"
        )

        print(
            request_path
        )

        # ---------------------------------------------------------
        # Introspect the request object.
        # ---------------------------------------------------------

        introspection = (
            await self.bus.introspect(
                PORTAL_BUS,
                request_path
            )
        )

        proxy_object = (
            self.bus.get_proxy_object(
                PORTAL_BUS,
                request_path,
                introspection
            )
        )

        request_interface = (
            proxy_object.get_interface(
                REQUEST_INTERFACE
            )
        )

        # ---------------------------------------------------------
        # Future used to wait for the portal response.
        # ---------------------------------------------------------

        response_future = (
            asyncio.get_running_loop()
            .create_future()
        )

        def response_received(
            response,
            results
        ):

            if response_future.done():
                return

            response_future.set_result(
                (
                    response,
                    results
                )
            )

        request_interface.on_response(
            response_received
        )

        print()
        print(
            "Waiting for screenshot..."
        )

        # ---------------------------------------------------------
        # Wait for portal response.
        # ---------------------------------------------------------

        response, results = (
            await response_future
        )

        print()
        print(
            "Screenshot portal responded."
        )

        print(
            "Response code:",
            response
        )

        # ---------------------------------------------------------
        # Response code 0 means success.
        # ---------------------------------------------------------

        if response != 0:

            raise RuntimeError(
                "Screenshot was cancelled "
                "or failed. "
                f"Response code: {response}"
            )

        # ---------------------------------------------------------
        # Extract URI.
        # ---------------------------------------------------------

        uri_variant = results.get(
            "uri"
        )

        if uri_variant is None:

            raise RuntimeError(
                "Screenshot succeeded, "
                "but no URI was returned."
            )

        # dbus-next returns Variant objects
        # for a{sv} values.

        uri = uri_variant.value

        print()
        print(
            "Screenshot URI:"
        )

        print(
            uri
        )

        # ---------------------------------------------------------
        # Make sure this is a local file.
        # ---------------------------------------------------------

        if not uri.startswith(
            "file://"
        ):

            raise RuntimeError(
                f"Unexpected screenshot URI: "
                f"{uri}"
            )

        source_path = uri[
            len("file://"):
        ]

        # ---------------------------------------------------------
        # Create destination directory.
        # ---------------------------------------------------------

        screenshot_dir = (
            Path.home()
            / "Pictures"
            / "Screenshots"
        )

        screenshot_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        # ---------------------------------------------------------
        # Create filename.
        # ---------------------------------------------------------

        filename = (
            "Screenshot_"
            + time.strftime(
                "%Y-%m-%d_%H-%M-%S"
            )
            + ".png"
        )

        destination = (
            screenshot_dir
            / filename
        )

        # ---------------------------------------------------------
        # Copy screenshot.
        # ---------------------------------------------------------

        shutil.copy2(
            source_path,
            destination
        )

        print()
        print(
            "Screenshot saved:"
        )

        print(
            destination
        )

        return str(destination)

    async def close(self):

        if self.bus is not None:

            self.bus.disconnect()

            self.bus = None


async def main():

    screenshot = PortalScreenshot()

    try:

        await screenshot.connect()

        path = await screenshot.screenshot()

        print()
        print(
            "================================"
        )

        print(
            "SCREENSHOT SUCCESS!"
        )

        print(
            "================================"
        )

        print()
        print(
            "Final screenshot:"
        )

        print(
            path
        )

    except KeyboardInterrupt:

        print()
        print(
            "Screenshot cancelled."
        )

    except Exception as error:

        print()
        print(
            "Screenshot failed:"
        )

        print(
            error
        )

    finally:

        await screenshot.close()


if __name__ == "__main__":

    asyncio.run(main())