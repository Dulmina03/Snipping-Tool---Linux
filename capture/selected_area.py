import asyncio
import os
import time
import tkinter as tk
from pathlib import Path
from urllib.parse import unquote

from dbus_next import Message, MessageType, Variant
from dbus_next.aio import MessageBus

from utils.clipboard import copy_image_to_clipboard


# ============================================================
# CONFIGURATION
# ============================================================

SCREENSHOTS_DIR = (
    Path.home()
    / "Pictures"
    / "Screenshots"
)


# ============================================================
# SELECTED AREA
# ============================================================

class SelectedAreaSelector:

    def __init__(self):

        self.root = None
        self.canvas = None

        self.start_x = 0
        self.start_y = 0

        self.end_x = 0
        self.end_y = 0

        self.selection_finished = False
        self.cancelled = False

        self.rectangle = None

    def select(self):
        """
        Create the fullscreen selection window.

        IMPORTANT:
        This function runs entirely on the main thread.
        We do NOT use asyncio.to_thread().
        """

        self.root = tk.Tk()

        self.root.title(
            "Select Area"
        )

        # Fullscreen
        self.root.attributes(
            "-fullscreen",
            True
        )

        # Keep overlay above other windows
        self.root.attributes(
            "-topmost",
            True
        )

        # Remove normal window decorations
        self.root.overrideredirect(
            True
        )

        # Crosshair cursor
        self.root.config(
            cursor="crosshair"
        )

        # Try to make the overlay transparent
        try:

            self.root.attributes(
                "-alpha",
                0.25
            )

        except tk.TclError:

            pass

        self.canvas = tk.Canvas(
            self.root,
            bg="black",
            highlightthickness=0,
            cursor="crosshair"
        )

        self.canvas.pack(
            fill=tk.BOTH,
            expand=True
        )

        # Mouse events
        self.canvas.bind(
            "<ButtonPress-1>",
            self.mouse_down
        )

        self.canvas.bind(
            "<B1-Motion>",
            self.mouse_drag
        )

        self.canvas.bind(
            "<ButtonRelease-1>",
            self.mouse_up
        )

        # ESC = cancel
        self.root.bind(
            "<Escape>",
            self.cancel
        )

        print(
            "Selection overlay opened."
        )

        print(
            "Drag with LEFT mouse button."
        )

        print(
            "Press ESC to cancel."
        )

        # Start Tk event loop
        self.root.mainloop()

        # Tk has now completely finished.
        # We are back on the same main thread.

        if self.cancelled:

            return None

        if not self.selection_finished:

            return None

        x = min(
            self.start_x,
            self.end_x
        )

        y = min(
            self.start_y,
            self.end_y
        )

        width = abs(
            self.end_x - self.start_x
        )

        height = abs(
            self.end_y - self.start_y
        )

        if width < 2 or height < 2:

            return None

        return (
            x,
            y,
            width,
            height
        )

    # --------------------------------------------------------
    # Mouse pressed
    # --------------------------------------------------------

    def mouse_down(
        self,
        event
    ):

        self.start_x = event.x
        self.start_y = event.y

        self.end_x = event.x
        self.end_y = event.y

        if self.rectangle is not None:

            self.canvas.delete(
                self.rectangle
            )

            self.rectangle = None

    # --------------------------------------------------------
    # Mouse dragging
    # --------------------------------------------------------

    def mouse_drag(
        self,
        event
    ):

        self.end_x = event.x
        self.end_y = event.y

        if self.rectangle is not None:

            self.canvas.delete(
                self.rectangle
            )

        x1 = min(
            self.start_x,
            self.end_x
        )

        y1 = min(
            self.start_y,
            self.end_y
        )

        x2 = max(
            self.start_x,
            self.end_x
        )

        y2 = max(
            self.start_y,
            self.end_y
        )

        self.rectangle = (
            self.canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                outline="white",
                width=2
            )
        )

    # --------------------------------------------------------
    # Mouse released
    # --------------------------------------------------------

    def mouse_up(
        self,
        event
    ):

        self.end_x = event.x
        self.end_y = event.y

        self.selection_finished = True

        # Destroy Tk window on the SAME thread
        self.root.destroy()

    # --------------------------------------------------------
    # ESC
    # --------------------------------------------------------

    def cancel(
        self,
        event=None
    ):

        self.cancelled = True

        if self.root is not None:

            self.root.destroy()


# ============================================================
# SCREENSHOT PORTAL
# ============================================================

async def take_portal_screenshot():

    print()

    print(
        "Connecting to Screenshot portal..."
    )

    bus = await MessageBus().connect()

    print(
        "Connected to portal."
    )

    print()

    # Unique token for this request
    request_token = (
        "ai_snipping_tool_"
        + str(os.getpid())
        + "_"
        + str(
            int(
                time.time() * 1000
            )
        )
    )

    options = {

        "handle_token": Variant(
            "s",
            request_token
        ),

        "interactive": Variant(
            "b",
            False
        )
    }

    # --------------------------------------------------------
    # Screenshot() D-Bus method call
    # --------------------------------------------------------

    message = Message(

        destination=(
            "org.freedesktop.portal.Desktop"
        ),

        path=(
            "/org/freedesktop/portal/desktop"
        ),

        interface=(
            "org.freedesktop.portal.Screenshot"
        ),

        member="Screenshot",

        signature="sa{sv}",

        body=[
            "",
            options
        ]
    )

    print(
        "Creating screenshot request..."
    )

    reply = await bus.call(
        message
    )

    if reply.message_type == MessageType.ERROR:

        bus.disconnect()

        raise RuntimeError(
            "Screenshot request failed: "
            + str(reply.error_name)
        )

    if not reply.body:

        bus.disconnect()

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

    print()

    # --------------------------------------------------------
    # Wait for Response signal
    # --------------------------------------------------------

    loop = asyncio.get_running_loop()

    response_future = loop.create_future()

    def message_handler(
        msg
    ):

        if (
            msg.message_type
            == MessageType.SIGNAL
            and
            msg.interface
            == "org.freedesktop.portal.Request"
            and
            msg.member
            == "Response"
            and
            msg.path
            == request_path
        ):

            if not response_future.done():

                response_future.set_result(
                    msg.body
                )

    bus.add_message_handler(
        message_handler
    )

    print(
        "Waiting for screenshot..."
    )

    try:

        response = await response_future

    finally:

        # IMPORTANT:
        # disconnect() is NOT awaited.
        bus.disconnect()

    # --------------------------------------------------------
    # Process response
    # --------------------------------------------------------

    if not response:

        raise RuntimeError(
            "Screenshot portal returned "
            "an empty response."
        )

    response_code = response[0]

    results = {}

    if len(response) > 1:

        results = response[1]

    print()

    print(
        "Screenshot portal responded."
    )

    print(
        f"Response code: {response_code}"
    )

    # 0 = success
    if response_code != 0:

        raise RuntimeError(
            "Screenshot was cancelled "
            "or failed."
        )

    uri_variant = results.get(
        "uri"
    )

    if uri_variant is None:

        raise RuntimeError(
            "Screenshot portal did not "
            "return a URI."
        )

    uri = uri_variant.value

    print()

    print(
        "Screenshot URI:"
    )

    print(
        uri
    )

    return uri


# ============================================================
# URI -> PATH
# ============================================================

def uri_to_path(
    uri
):

    if not uri.startswith(
        "file://"
    ):

        raise RuntimeError(
            "Portal returned an unsupported URI: "
            + uri
        )

    path = uri[7:]

    return Path(
        unquote(path)
    )


# ============================================================
# SCREEN SIZE
# ============================================================

def get_screen_size():

    """
    Get the logical screen size using Tk.

    This function is called on the main thread,
    after the selection overlay has finished.
    """

    root = tk.Tk()

    root.withdraw()

    width = root.winfo_screenwidth()

    height = root.winfo_screenheight()

    root.destroy()

    return (
        width,
        height
    )


# ============================================================
# CROP SCREENSHOT
# ============================================================

def crop_screenshot(
    source_path,
    x,
    y,
    width,
    height
):

    try:

        from PIL import Image

    except ImportError:

        raise RuntimeError(
            "Pillow is not installed.\n"
            "Run:\n"
            "pip install Pillow"
        )

    SCREENSHOTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    filename = (
        "Screenshot_"
        + time.strftime(
            "%Y-%m-%d_%H-%M-%S"
        )
        + ".png"
    )

    output_path = (
        SCREENSHOTS_DIR
        / filename
    )

    # --------------------------------------------------------
    # Open full screenshot
    # --------------------------------------------------------

    with Image.open(
        source_path
    ) as image:

        print()

        print(
            "Full screenshot size:"
        )

        print(
            f"{image.width} x "
            f"{image.height}"
        )

        # ----------------------------------------------------
        # Get actual logical screen size
        # ----------------------------------------------------

        screen_width, screen_height = (
            get_screen_size()
        )

        print(
            "Logical screen size:"
        )

        print(
            f"{screen_width} x "
            f"{screen_height}"
        )

        # ----------------------------------------------------
        # Calculate scaling
        # ----------------------------------------------------

        scale_x = (
            image.width
            / screen_width
        )

        scale_y = (
            image.height
            / screen_height
        )

        print(
            "Scale:"
        )

        print(
            f"X = {scale_x:.3f}"
        )

        print(
            f"Y = {scale_y:.3f}"
        )

        # ----------------------------------------------------
        # Convert selected coordinates
        # ----------------------------------------------------

        crop_x = round(
            x * scale_x
        )

        crop_y = round(
            y * scale_y
        )

        crop_width = round(
            width * scale_x
        )

        crop_height = round(
            height * scale_y
        )

        left = max(
            0,
            crop_x
        )

        top = max(
            0,
            crop_y
        )

        right = min(
            image.width,
            crop_x + crop_width
        )

        bottom = min(
            image.height,
            crop_y + crop_height
        )

        print()

        print(
            "Final crop:"
        )

        print(
            f"({left}, {top}) -> "
            f"({right}, {bottom})"
        )

        if (
            right <= left
            or
            bottom <= top
        ):

            raise RuntimeError(
                "Invalid crop coordinates."
            )

        # ----------------------------------------------------
        # Crop
        # ----------------------------------------------------

        cropped = image.crop(
            (
                left,
                top,
                right,
                bottom
            )
        )

        # ----------------------------------------------------
        # Save
        # ----------------------------------------------------

        cropped.save(
            output_path,
            "PNG"
        )

    return output_path


# ============================================================
# MAIN
# ============================================================

async def main():

    print()

    print(
        "==================================="
    )

    print(
        "       SELECTED AREA CAPTURE"
    )

    print(
        "==================================="
    )

    print()

    print(
        "Drag over the area you want "
        "to capture."
    )

    print(
        "Press ESC to cancel."
    )

    print()

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Tkinter selection happens BEFORE
    # any asyncio work.
    #
    # This prevents the Tcl_AsyncDelete
    # wrong-thread crash.
    # --------------------------------------------------------

    selector = SelectedAreaSelector()

    area = selector.select()

    if area is None:

        print()

        print(
            "Selection cancelled."
        )

        return

    x, y, width, height = area

    print()

    print(
        "========== SELECTED AREA =========="
    )

    print(
        f"X: {x}"
    )

    print(
        f"Y: {y}"
    )

    print(
        f"Width: {width}"
    )

    print(
        f"Height: {height}"
    )

    print(
        "==================================="
    )

    # --------------------------------------------------------
    # Take full screenshot using portal
    # --------------------------------------------------------

    try:

        uri = await take_portal_screenshot()

        source_path = uri_to_path(
            uri
        )

        if not source_path.exists():

            raise RuntimeError(
                "Portal screenshot file "
                "does not exist:\n"
                + str(source_path)
            )

        print()

        print(
            "Cropping selected area..."
        )

        # ----------------------------------------------------
        # Crop
        # ----------------------------------------------------

        output_path = crop_screenshot(

            source_path,

            x,
            y,

            width,
            height
        )

        try:
            copy_image_to_clipboard(output_path)
            print("Copied to clipboard.")
        except Exception as clipboard_error:
            print(
                "WARNING: Screenshot saved, but "
                "clipboard copy failed:"
            )
            print(clipboard_error)

        print()

        print(
            "================================"
        )

        print(
            "SELECTED AREA SCREENSHOT SUCCESS!"
        )

        print(
            "================================"
        )

        print()

        print(
            "Saved to:"
        )

        print(
            output_path
        )

        # ----------------------------------------------------
        # Remove temporary full screenshot
        # ----------------------------------------------------

        try:

            source_path.unlink()

            print()

            print(
                "Temporary full screenshot "
                "removed."
            )

        except OSError:

            pass

        return output_path

    except Exception as error:

        print()

        print(
            "Screenshot failed:"
        )

        print(
            error
        )

        return None


# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":

    asyncio.run(
        main()
    )
