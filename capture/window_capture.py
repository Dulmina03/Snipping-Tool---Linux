import asyncio
import shutil
import time
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

from dbus_next.aio import MessageBus
from dbus_next import Message, MessageType, Variant
from dbus_next.constants import BusType

from utils.clipboard import copy_image_to_clipboard
from capture.screenshot_portal_request import request_screenshot, ScreenshotPortalError


PORTAL_BUS_NAME = "org.freedesktop.portal.Desktop"
PORTAL_OBJECT_PATH = "/org/freedesktop/portal/desktop"

SCREENSHOT_INTERFACE = "org.freedesktop.portal.Screenshot"
REQUEST_INTERFACE = "org.freedesktop.portal.Request"

OUTPUT_DIR = Path.home() / "Pictures" / "Screenshots"
RESPONSE_TIMEOUT_SECONDS = 180


async def call_method(
    bus,
    destination,
    path,
    interface,
    member,
    signature,
    body
):
    message = Message(
        destination=destination,
        path=path,
        interface=interface,
        member=member,
        signature=signature,
        body=body
    )

    reply = await bus.call(message)

    if reply.message_type == MessageType.ERROR:
        raise RuntimeError(
            f"D-Bus error: {reply.error_name}: {reply.body}"
        )

    return reply


def uri_to_path(uri):
    """
    Convert a portal file:// URI into a real filesystem path.

    Portal URIs are percent-encoded, for example:

        file:///home/user/Pictures/Screenshots/Screenshot%20From%202026-08-22%2011-10-51.png

    That must become:

        /home/user/Pictures/Screenshots/Screenshot From 2026-08-22 11-10-51.png
    """

    if not isinstance(uri, str):
        raise RuntimeError(
            "Screenshot URI is not a string."
        )

    parsed = urlparse(uri)

    if parsed.scheme != "file":
        raise RuntimeError(
            f"Screenshot URI is not a local file: {uri}"
        )

    decoded_path = unquote(parsed.path)

    if not decoded_path:
        raise RuntimeError(
            f"Screenshot URI has no path: {uri}"
        )

    return Path(decoded_path)


def unique_destination():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    destination = OUTPUT_DIR / f"Screenshot_{timestamp}.png"

    if destination.exists():
        destination = (
            OUTPUT_DIR
            / f"Screenshot_{timestamp}_{uuid.uuid4().hex[:8]}.png"
        )

    return destination


async def take_screenshot():
    try:
        source_path = await request_screenshot(interactive=True)
    except ScreenshotPortalError as error:
        if error.kind == 'cancelled':
            return None
        raise

    if not source_path.exists():
        print()
        print("ERROR: Screenshot file does not exist.")
        print()
        print("Expected path:")
        print(source_path)
        return None

    destination = unique_destination()

    shutil.copy2(source_path, destination)

    print()
    print("Screenshot saved:")
    print(destination)

    try:
        copy_image_to_clipboard(destination)
        print("Copied to clipboard.")
    except Exception as error:
        print("WARNING: Screenshot saved, but clipboard copy failed:")
        print(error)

    if source_path.resolve() != destination.resolve():
        try:
            source_path.unlink()
            print()
            print("Temporary screenshot removed.")
        except OSError as error:
            print()
            print(
                "Could not remove temporary screenshot:",
                error
            )

    return destination


async def main():

    try:
        result = await take_screenshot()

        if result:
            print()
            print("================================")
            print(" WINDOW CAPTURE SUCCESS!")
            print("================================")
            print()
            print("Final screenshot:")
            print(result)
            print()

    except KeyboardInterrupt:
        print()
        print("Cancelled by user.")

    except Exception as error:
        print()
        print("================================")
        print(" WINDOW CAPTURE FAILED")
        print("================================")
        print()
        print(type(error).__name__, ":", error)
        print()


if __name__ == "__main__":
    asyncio.run(main())
