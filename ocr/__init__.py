"""OCR support for AI Snipping Tool."""

from .ocr_engine import extract_text, tesseract_version

__all__ = ["extract_text", "tesseract_version"]
