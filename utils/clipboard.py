"""Standard Copy clipboard support backed by PySide6/Qt.

The caller publishes from its focused GUI surface and keeps QApplication's event
loop alive to serve other clients. A local write is not an external-paste test.
"""

import io
from pathlib import Path
import sys
import threading
from typing import Union
from utils.capture_diagnostics import trace

from PIL import Image
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QMimeData, QThread
from PySide6.QtGui import QClipboard, QGuiApplication, QImage, QPixmap
from PySide6.QtWidgets import QApplication


_owned_application: QGuiApplication | None = None

ImageInputType = Union[str, Path, Image.Image, QPixmap, QImage]


def _application() -> QGuiApplication:
    """Return the current Qt application, creating one when necessary."""
    global _owned_application

    application = QGuiApplication.instance()

    if application is None:
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError('Clipboard operations must run on the Qt GUI thread.')
        _owned_application = QApplication(sys.argv)
        application = _owned_application

    if QThread.currentThread() != application.thread():
        raise RuntimeError('Clipboard operations must run on the Qt GUI thread.')
    return application



def _to_qimage(image_input: ImageInputType) -> QImage:
    """Convert various image types (file path, PIL Image, QPixmap, QImage) to QImage."""
    if isinstance(image_input, QImage):
        image = image_input
    elif isinstance(image_input, QPixmap):
        image = image_input.toImage().convertToFormat(QImage.Format_ARGB32)
    elif isinstance(image_input, Image.Image):
        buf = io.BytesIO()
        image_input.save(buf, format="PNG")
        image = QImage()
        image.loadFromData(buf.getvalue())
    elif isinstance(image_input, (str, Path)):
        path = Path(image_input).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Screenshot file does not exist: {path}")
        image = QImage(str(path))
    else:
        raise TypeError(f"Unsupported image input type: {type(image_input)}")

    if image.isNull():
        raise RuntimeError(f"Could not load valid image for clipboard: {image_input}")

    if image.format() == QImage.Format_ARGB32_Premultiplied:
        image = image.convertToFormat(QImage.Format_ARGB32)

    return image


def copy_image_to_clipboard(image_input: ImageInputType) -> None:
    """
    Copy an image (file path, PIL Image, QPixmap, or QImage) to the system clipboard.
    Encodes standard image/png MIME data so external apps can paste without issue.
    """
    application = _application()
    encoded_png = None
    if isinstance(image_input, (str, Path)):
        # Saved screenshots are already complete immutable PNGs. Decode and
        # validate the same bytes that we publish, without encoding them again.
        path = Path(image_input).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Screenshot file does not exist: {path}")
        raw = path.read_bytes()
        image = _to_qimage(QImage.fromData(raw))
        if raw.startswith(b'\x89PNG\r\n\x1a\n'):
            encoded_png = QByteArray(raw)
    else:
        image = _to_qimage(image_input)

    # Encode raw PNG bytes for external clipboard consumers (browsers, editors, chat)
    ba = encoded_png
    if ba is None:
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.WriteOnly)
        if not image.save(buf, "PNG"):
            raise RuntimeError("Could not encode clipboard PNG.")
        buf.close()

    mime = QMimeData()
    mime.setImageData(image)
    mime.setData("image/png", ba)
    mime.setData("image/x-png", ba)

    clipboard = application.clipboard()
    clipboard.setMimeData(mime, QClipboard.Mode.Clipboard)

    trace('clipboard_write', kind='image', gui_thread=QThread.currentThread() == application.thread(),
          qt_owned=clipboard.ownsClipboard(), formats=clipboard.mimeData().formats(),
          application_alive=QGuiApplication.instance() is application)


def copy_text_to_clipboard(text: str) -> None:
    """Copy extracted text to the system clipboard with full MIME type support."""
    if not isinstance(text, str):
        raise TypeError("Clipboard text must be a string.")

    application = _application()

    clipboard = application.clipboard()

    raw_bytes = text.encode("utf-8")

    mime = QMimeData()
    mime.setText(text)
    mime.setData("text/plain;charset=utf-8", raw_bytes)
    mime.setData("text/plain", raw_bytes)
    mime.setData("UTF8_STRING", raw_bytes)
    clipboard.setMimeData(mime, QClipboard.Mode.Clipboard)

    trace('clipboard_write', kind='text', characters=len(text),
          gui_thread=QThread.currentThread() == application.thread(), qt_owned=clipboard.ownsClipboard(),
          formats=clipboard.mimeData().formats(), application_alive=QGuiApplication.instance() is application)


def clipboard_contains_image() -> bool:
    """Return whether the current system clipboard exposes a valid image."""
    application = _application()
    clipboard = application.clipboard()
    mime_data = clipboard.mimeData()

    if mime_data is None:
        return False

    return mime_data.hasImage() and not clipboard.image().isNull()


def clipboard_contains_text(expected_text: str | None = None) -> bool:
    """Return whether the clipboard contains text, optionally matching a value."""
    text = _application().clipboard().text()

    if expected_text is None:
        return bool(text)

    return text == expected_text
