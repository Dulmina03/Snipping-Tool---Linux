"""Selected area capture implementation using PySide6 Overlay and XDG Desktop Portal."""

import asyncio
import os
from pathlib import Path
import sys
import time
from urllib.parse import unquote

from dbus_next import Message, MessageType, Variant
from dbus_next.aio import MessageBus
from PIL import Image
from PySide6.QtCore import QEventLoop, QRect
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from ui.overlay import Overlay
from utils.clipboard import copy_image_to_clipboard


SCREENSHOTS_DIR = Path.home() / "Pictures" / "Screenshots"


class SelectedAreaSelector:
    """Fullscreen rectangular selection overlay powered by PySide6 Overlay."""

    def __init__(self):
        self.selected_area = None

    def select(self):
        """Display the PySide6 fullscreen selection overlay."""
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        overlay = Overlay()
        virtual_geom = overlay._get_virtual_geometry()
        print(
            f"[OVERLAY LAUNCH] Class: {overlay.__class__.__name__}, "
            f"Screen Geometry: {virtual_geom}"
        )

        overlay.showFullScreenOverlay()
        print(
            f"[OVERLAY SHOWN] Class: {overlay.__class__.__name__}, "
            f"Active Geometry: {overlay.geometry()}"
        )

        loop = QEventLoop()
        overlay.area_selected.connect(lambda rect: loop.quit())
        overlay.cancelled.connect(lambda: loop.quit())
        loop.exec()

        if overlay.selected_rect is not None:
            r = overlay.selected_rect
            print(f"[OVERLAY SELECTION] Selected: X={r.x()}, Y={r.y()}, Width={r.width()}, Height={r.height()}")
            return (r.x(), r.y(), r.width(), r.height())

        print("[OVERLAY CANCELLED] Selection was cancelled.")
        return None


async def take_portal_screenshot() -> str:
    """Request a non-interactive full screen screenshot from XDG Desktop Portal."""
    print("Connecting to Screenshot portal...")
    bus = await MessageBus().connect()

    token = f"ai_snipping_tool_{os.getpid()}_{int(time.time() * 1000)}"

    options = {
        "handle_token": Variant("s", token),
        "interactive": Variant("b", False),
    }

    message = Message(
        destination="org.freedesktop.portal.Desktop",
        path="/org/freedesktop/portal/desktop",
        interface="org.freedesktop.portal.Screenshot",
        member="Screenshot",
        signature="sa{sv}",
        body=["", options],
    )

    reply = await bus.call(message)

    if reply.message_type == MessageType.ERROR:
        bus.disconnect()
        raise RuntimeError(f"Portal screenshot request error: {reply.error_name}")

    request_handle = reply.body[0]
    print("Screenshot request created:", request_handle)

    future = asyncio.get_running_loop().create_future()

    def on_signal(msg):
        if (
            msg.message_type == MessageType.SIGNAL
            and msg.interface == "org.freedesktop.portal.Request"
            and msg.member == "Response"
            and msg.path == request_handle
        ):
            if not future.done():
                future.set_result(msg.body)

    bus.add_message_handler(on_signal)

    try:
        response_code, results = await asyncio.wait_for(future, timeout=120)
    finally:
        bus.remove_message_handler(on_signal)
        bus.disconnect()

    if response_code != 0:
        raise RuntimeError(f"Screenshot cancelled or denied (code {response_code}).")

    return results["uri"].value


def uri_to_path(uri: str) -> Path:
    if not uri.startswith("file://"):
        raise RuntimeError(f"Portal returned an unsupported URI: {uri}")
    return Path(unquote(uri[7:]))


def get_screen_size() -> tuple[int, int]:
    """Get the virtual desktop size across all connected screens."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    total_rect = QRect()
    for screen in QGuiApplication.screens():
        total_rect = total_rect.united(screen.geometry())

    if total_rect.isEmpty():
        primary = QGuiApplication.primaryScreen()
        total_rect = primary.geometry() if primary else QRect(0, 0, 1920, 1080)

    return (total_rect.width(), total_rect.height())


def crop_screenshot(source_path: Path, x: int, y: int, width: int, height: int) -> Path:
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"Screenshot_{time.strftime('%Y-%m-%d_%H-%M-%S')}.png"
    output_path = SCREENSHOTS_DIR / filename

    with Image.open(source_path) as image:
        screen_width, screen_height = get_screen_size()
        scale_x = image.width / screen_width
        scale_y = image.height / screen_height

        print(f"Full screenshot size: {image.width} x {image.height}")
        print(f"Logical screen size: {screen_width} x {screen_height}")
        print(f"Scale: X = {scale_x:.3f}, Y = {scale_y:.3f}")

        crop_x = round(x * scale_x)
        crop_y = round(y * scale_y)
        crop_width = round(width * scale_x)
        crop_height = round(height * scale_y)

        left = max(0, crop_x)
        top = max(0, crop_y)
        right = min(image.width, crop_x + crop_width)
        bottom = min(image.height, crop_y + crop_height)

        print(f"Final crop: ({left}, {top}) -> ({right}, {bottom})")

        if right <= left or bottom <= top:
            raise RuntimeError("Invalid crop coordinates.")

        cropped = image.crop((left, top, right, bottom))
        cropped.save(output_path, "PNG")

    return output_path


async def main() -> Path | None:
    print("===================================")
    print("       SELECTED AREA CAPTURE       ")
    print("===================================")

    selector = SelectedAreaSelector()
    area = selector.select()

    if area is None:
        print("Selection cancelled.")
        return None

    x, y, width, height = area

    try:
        uri = await take_portal_screenshot()
        source_path = uri_to_path(uri)

        if not source_path.exists():
            raise RuntimeError(f"Portal screenshot file does not exist: {source_path}")

        print("Cropping selected area...")
        output_path = crop_screenshot(source_path, x, y, width, height)

        try:
            copy_image_to_clipboard(output_path)
            print("Copied to clipboard.")
        except Exception as clipboard_error:
            print("WARNING: Screenshot saved, but clipboard copy failed:", clipboard_error)

        print("================================")
        print("SELECTED AREA SCREENSHOT SUCCESS!")
        print("================================")
        print("Saved to:", output_path)

        try:
            source_path.unlink()
            print("Temporary full screenshot removed.")
        except OSError:
            pass

        return output_path

    except Exception as error:
        print("Screenshot failed:", error)
        return None


if __name__ == "__main__":
    asyncio.run(main())
