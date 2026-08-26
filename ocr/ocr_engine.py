"""Tesseract OCR helpers."""

from pathlib import Path

import pytesseract
from PIL import Image, UnidentifiedImageError


def tesseract_version() -> str:
    """Return the installed Tesseract version or raise a useful error."""
    try:
        return str(pytesseract.get_tesseract_version())
    except pytesseract.TesseractNotFoundError as error:
        raise RuntimeError(
            "Tesseract OCR is not installed or is not on PATH. "
            "Install it with: sudo apt install tesseract-ocr"
        ) from error


def extract_text(image_path: str | Path) -> str:
    """Extract text from an image path using the local Tesseract engine."""
    path = Path(image_path).expanduser()

    if not path.is_file():
        raise FileNotFoundError(f"Image file does not exist: {path}")

    try:
        with Image.open(path) as image:
            image.load()
            text = pytesseract.image_to_string(image)
    except UnidentifiedImageError as error:
        raise RuntimeError(f"Image file is invalid or unsupported: {path}") from error
    except pytesseract.TesseractNotFoundError as error:
        raise RuntimeError(
            "Tesseract OCR is not installed or is not on PATH. "
            "Install it with: sudo apt install tesseract-ocr"
        ) from error
    except pytesseract.TesseractError as error:
        raise RuntimeError(f"Tesseract OCR failed: {error}") from error

    return text.strip()
