"""Clipboard support backed by PySide6/Qt for Wayland and X11."""

import io
from pathlib import Path
import sys
from typing import Union

from PIL import Image
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QMimeData, Qt
from PySide6.QtGui import QClipboard, QGuiApplication, QImage, QPixmap
from PySide6.QtWidgets import QApplication, QWidget


_owned_application: QGuiApplication | None = None
_wayland_anchor: QWidget | None = None

ImageInputType = Union[str, Path, Image.Image, QPixmap, QImage]


def _application() -> QGuiApplication:
    """Return the current Qt application, creating one when necessary."""
    global _owned_application

    application = QGuiApplication.instance()

    if application is None:
        _owned_application = QApplication(sys.argv)
        application = _owned_application

    return application


def _ensure_clipboard_surface() -> None:
    """
    Ensure an invisible background surface exists on Wayland.
    Wayland compositors require an active client surface to maintain
    clipboard ownership (wl_data_source); without one, the compositor
    revokes the clipboard data as soon as all windows close.
    """
    global _wayland_anchor
    application = _application()

    if _wayland_anchor is None:
        try:
            anchor = QWidget()
            anchor.setWindowFlags(
                Qt.SubWindow
                | Qt.FramelessWindowHint
                | Qt.WindowDoesNotAcceptFocus
                | Qt.WindowTransparentForInput
            )
            anchor.setAttribute(Qt.WA_TranslucentBackground)
            anchor.setAttribute(Qt.WA_ShowWithoutActivating)
            anchor.setStyleSheet("background: transparent;")
            anchor.resize(1, 1)
            anchor.move(-10000, -10000)
            anchor.show()
            _wayland_anchor = anchor
            application.processEvents()
        except Exception:
            pass


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
    image = _to_qimage(image_input)

    application = _application()
    _ensure_clipboard_surface()

    # Encode raw PNG bytes for external clipboard consumers (browsers, editors, chat)
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    image.save(buf, "PNG")

    mime = QMimeData()
    mime.setImageData(image)
    mime.setData("image/png", ba)
    mime.setData("image/x-png", ba)

    clipboard = application.clipboard()
    clipboard.setMimeData(mime, QClipboard.Mode.Clipboard)

    if clipboard.supportsSelection():
        mime_sel = QMimeData()
        mime_sel.setImageData(image)
        mime_sel.setData("image/png", ba)
        mime_sel.setData("image/x-png", ba)
        clipboard.setMimeData(mime_sel, QClipboard.Mode.Selection)

    application.processEvents()


def copy_text_to_clipboard(text: str) -> None:
    """Copy extracted text to the system clipboard with full MIME type support."""
    if not isinstance(text, str):
        raise TypeError("Clipboard text must be a string.")

    application = _application()
    _ensure_clipboard_surface()

    clipboard = application.clipboard()

    raw_bytes = text.encode("utf-8")

    mime = QMimeData()
    mime.setText(text)
    mime.setData("text/plain;charset=utf-8", raw_bytes)
    mime.setData("text/plain", raw_bytes)
    mime.setData("UTF8_STRING", raw_bytes)
    clipboard.setMimeData(mime, QClipboard.Mode.Clipboard)

    if clipboard.supportsSelection():
        mime_sel = QMimeData()
        mime_sel.setText(text)
        mime_sel.setData("text/plain;charset=utf-8", raw_bytes)
        mime_sel.setData("text/plain", raw_bytes)
        mime_sel.setData("UTF8_STRING", raw_bytes)
        clipboard.setMimeData(mime_sel, QClipboard.Mode.Selection)

    application.processEvents()


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
