"""Clipboard support backed by PySide6/Qt for Wayland and X11."""

import sys
from pathlib import Path

from PySide6.QtCore import QMimeData
from PySide6.QtGui import QClipboard, QGuiApplication, QImage
from PySide6.QtWidgets import QApplication


_owned_application: QGuiApplication | None = None


def _application():
    """Return the current Qt application, creating one when necessary."""
    global _owned_application

    application = QGuiApplication.instance()

    if application is None:
        _owned_application = QApplication(sys.argv)
        application = _owned_application

    return application


def copy_image_to_clipboard(image_path: str | Path) -> None:
    """Load a PNG image from *image_path* and copy it to the system clipboard."""
    path = Path(image_path).expanduser()

    if not path.is_file():
        raise FileNotFoundError(f"Screenshot file does not exist: {path}")

    image = QImage(str(path))

    if image.isNull():
        raise RuntimeError(f"Could not load image for clipboard: {path}")

    application = _application()
    clipboard = application.clipboard()

    mime = QMimeData()
    mime.setImageData(image)
    clipboard.setMimeData(mime, QClipboard.Mode.Clipboard)

    if clipboard.supportsSelection():
        mime_sel = QMimeData()
        mime_sel.setImageData(image)
        clipboard.setMimeData(mime_sel, QClipboard.Mode.Selection)

    application.processEvents()


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
    mime.setData("UTF8_STRING", raw_bytes)
    clipboard.setMimeData(mime, QClipboard.Mode.Clipboard)

    if clipboard.supportsSelection():
        mime_sel = QMimeData()
        mime_sel.setText(text)
        mime_sel.setData("text/plain;charset=utf-8", raw_bytes)
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
