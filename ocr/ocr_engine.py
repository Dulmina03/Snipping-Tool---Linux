"""Tesseract OCR helpers with preprocessing for UI screenshot text."""

from pathlib import Path

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, UnidentifiedImageError


# ── Tesseract PSM/OEM config ──────────────────────────────────────────────────
# --psm 3  = fully automatic page segmentation (default, good for mixed layouts)
# --psm 6  = single uniform block of text (better for small/cropped UI text)
# --oem 3  = use LSTM + legacy engine (best accuracy on modern Tesseract ≥ 4)
_CONFIG_FULL = "--oem 3 --psm 3"
_CONFIG_BLOCK = "--oem 3 --psm 6"
_CONFIG_SPARSE = "--oem 3 --psm 11"   # sparse text, no structure assumed


def tesseract_version() -> str:
    """Return the installed Tesseract version string, or raise a clear error."""
    try:
        return str(pytesseract.get_tesseract_version())
    except pytesseract.TesseractNotFoundError as error:
        raise RuntimeError(
            "Tesseract OCR is not installed or not on PATH.\n"
            "Install it with:  sudo apt install tesseract-ocr\n"
            "Then verify with: tesseract --version"
        ) from error


def _preprocess(image: Image.Image) -> Image.Image:
    """
    Apply preprocessing steps that consistently improve OCR accuracy on
    screenshots of UI text (menus, dialogs, window content, etc.).

    Pipeline:
      1. Convert to RGB to normalise any RGBA/P-mode input.
      2. Convert to greyscale (L).
      3. Scale up 2× with Lanczos if smaller than 1 000 px on either side
         — Tesseract struggles on sub-100dpi source material.
      4. Enhance contrast (factor 2.0) to help binarise light-grey-on-white
         or dark-on-dark text typical in modern dark-mode UIs.
      5. Apply a mild sharpening filter to crisp blurry edges.
      6. Binarise with Otsu-style threshold via point() for clean B/W input.
    """
    # Step 1 — normalise colour mode
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    # Step 2 — greyscale
    grey = image.convert("L")

    # Step 3 — upscale low-resolution crops
    min_side = min(grey.width, grey.height)
    if min_side < 600:
        scale = max(2, round(600 / min_side))
        grey = grey.resize(
            (grey.width * scale, grey.height * scale),
            Image.Resampling.LANCZOS,
        )

    # Step 4 — contrast enhancement
    grey = ImageEnhance.Contrast(grey).enhance(2.0)

    # Step 5 — sharpen
    grey = grey.filter(ImageFilter.SHARPEN)

    # Step 6 — simple threshold binarisation (128 split)
    grey = grey.point(lambda p: 255 if p > 128 else 0)

    return grey


def extract_text(image_source: "str | Path | Image.Image") -> str:
    """
    Extract text from a screenshot image using Tesseract OCR.

    Args:
        image_source: A file path (str or Path) **or** an already-opened
                      PIL ``Image`` object.

    Returns:
        The extracted text as a stripped string.  Empty string if nothing
        was found.

    Raises:
        FileNotFoundError: If *image_source* is a path that does not exist.
        RuntimeError:      If Tesseract is not installed, or OCR fails.
    """
    # ── 1. Load image ─────────────────────────────────────────────────────────
    if isinstance(image_source, (str, Path)):
        path = Path(image_source).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Image file does not exist: {path}")
        try:
            image = Image.open(path)
            image.load()
        except UnidentifiedImageError as error:
            raise RuntimeError(
                f"Image file is invalid or unsupported: {path}"
            ) from error
    elif isinstance(image_source, Image.Image):
        image = image_source
    else:
        raise TypeError(
            f"image_source must be a file path or PIL Image, got {type(image_source)}"
        )

    # ── 2. Run OCR ────────────────────────────────────────────────────────────
    try:
        # First pass — raw image with automatic page segmentation
        text = pytesseract.image_to_string(image, config=_CONFIG_FULL).strip()

        # Second pass — preprocessed image using block layout (often better for UI)
        processed = _preprocess(image)
        text_preprocessed = pytesseract.image_to_string(
            processed, config=_CONFIG_BLOCK
        ).strip()

        # Third pass — sparse mode on preprocessed (catches isolated labels/buttons)
        text_sparse = pytesseract.image_to_string(
            processed, config=_CONFIG_SPARSE
        ).strip()

        # Use whichever pass returned the most content
        best = max(
            (text, text_preprocessed, text_sparse),
            key=lambda t: len(t),
        )
        return best

    except pytesseract.TesseractNotFoundError as error:
        raise RuntimeError(
            "Tesseract OCR is not installed or not on PATH.\n"
            "Install it with:  sudo apt install tesseract-ocr\n"
            "Then verify with: tesseract --version"
        ) from error
    except pytesseract.TesseractError as error:
        raise RuntimeError(f"Tesseract OCR engine failed: {error}") from error
    finally:
        # Only close if we opened it ourselves from a path
        if isinstance(image_source, (str, Path)):
            image.close()
