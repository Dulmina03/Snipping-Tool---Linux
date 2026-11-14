"""Tesseract OCR helpers with preprocessing for UI screenshot text and Sinhala/English support."""

import os
from pathlib import Path
import re
import shutil
import urllib.request

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, UnidentifiedImageError


# ── Tessdata setup (bundled / local directory for Sinhala + English) ───────────

TESSDATA_DIR = Path(__file__).resolve().parent / "tessdata"
SINHALA_TRAINEDDATA_URL = (
    "https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/main/sin.traineddata"
)

# Standard Linux system paths for tesseract traineddata
SYSTEM_TESSDATA_CANDIDATES = [
    Path("/usr/share/tesseract-ocr/5/tessdata"),
    Path("/usr/share/tesseract-ocr/4.00/tessdata"),
    Path("/usr/share/tesseract-ocr/tessdata"),
    Path("/usr/share/tessdata"),
]


def _setup_tessdata_dir() -> Path:
    """Ensure a local tessdata directory exists containing sin.traineddata and system data."""
    TESSDATA_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Check/Download Sinhala traineddata if not present
    sin_path = TESSDATA_DIR / "sin.traineddata"
    if not sin_path.is_file() or sin_path.stat().st_size < 100_000:
        # Check if system already has sin.traineddata
        found_system_sin = False
        for sys_dir in SYSTEM_TESSDATA_CANDIDATES:
            sys_sin = sys_dir / "sin.traineddata"
            if sys_sin.is_file():
                try:
                    os.symlink(sys_sin, sin_path)
                    found_system_sin = True
                    break
                except OSError:
                    pass

        if not found_system_sin:
            try:
                req = urllib.request.Request(
                    SINHALA_TRAINEDDATA_URL,
                    headers={"User-Agent": "ai-snipping-tool/1.0"},
                )
                with urllib.request.urlopen(req, timeout=20) as resp, open(sin_path, "wb") as f:
                    f.write(resp.read())
            except Exception as err:
                print(f"[OCR] Warning: Could not download Sinhala traineddata: {err}")

    # 2. Link or copy eng.traineddata & osd.traineddata into local tessdata if missing
    for name in ("eng.traineddata", "osd.traineddata"):
        target = TESSDATA_DIR / name
        if not target.exists():
            for sys_dir in SYSTEM_TESSDATA_CANDIDATES:
                src = sys_dir / name
                if src.is_file():
                    try:
                        os.symlink(src, target)
                        break
                    except OSError:
                        try:
                            shutil.copy2(src, target)
                            break
                        except Exception:
                            pass

    return TESSDATA_DIR


def get_default_languages() -> str:
    """Return 'sin+eng' if Sinhala traineddata is available, otherwise 'eng'."""
    tess_dir = _setup_tessdata_dir()
    if (tess_dir / "sin.traineddata").is_file():
        return "sin+eng"
    return "eng"


def _build_config(psm: int = 3, oem: int = 1) -> str:
    """Build Tesseract config string including custom tessdata directory if active."""
    tess_dir = _setup_tessdata_dir()
    if tess_dir.is_dir() and (tess_dir / "sin.traineddata").is_file():
        return f'--tessdata-dir "{tess_dir}" --oem {oem} --psm {psm}'
    return f"--oem {oem} --psm {psm}"


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
    """
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    grey = image.convert("L")

    min_side = min(grey.width, grey.height)
    if min_side < 600:
        scale = max(2, round(600 / min_side))
        grey = grey.resize(
            (grey.width * scale, grey.height * scale),
            Image.Resampling.LANCZOS,
        )

    grey = ImageEnhance.Contrast(grey).enhance(2.0)
    grey = grey.filter(ImageFilter.SHARPEN)
    grey = grey.point(lambda p: 255 if p > 128 else 0)

    return grey


def _score_ocr_candidate(text: str) -> float:
    """
    Score the quality of an OCR result based on language density and noise penalties.
    Avoids selecting passes that inflate length with hallucinated digits or noise symbols.
    """
    t = text.strip()
    if not t:
        return -1000.0

    sin_count = sum(1 for c in t if "\u0D80" <= c <= "\u0DFF")
    eng_count = sum(1 for c in t if c.isascii() and c.isalpha())
    digit_count = sum(1 for c in t if c.isdigit())
    noise_count = sum(1 for c in t if c in "?~^\\/|<>[]{}`_")

    score = sin_count * 2.0 + eng_count * 1.5 - noise_count * 4.0

    # Penalize digit hallucinations in predominantly Sinhala text
    # (e.g. Tesseract turning 'අනික' into '2625325' when multi-language eng is active)
    if sin_count > 5 and sin_count > eng_count:
        score -= digit_count * 5.0

    return score


def _post_process_text(text: str) -> str:
    """Clean up edge noise (leading/trailing underscores, stray quotes) from OCR lines."""
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        # Clean leading noise characters like _ or stray quote before words
        line = re.sub(r'^[_\-\"\':;|\^~]+\s*', "", line)
        line = re.sub(r'\s*[_\-\^~]+$', "", line)
        if line:
            lines.append(line)
    return "\n".join(lines)


def extract_text(
    image_source: "str | Path | Image.Image",
    lang: str | None = None,
) -> str:
    """
    Extract text (Sinhala and English) from a screenshot image using Tesseract OCR.

    Args:
        image_source: A file path (str or Path) **or** an already-opened
                      PIL ``Image`` object.
        lang:         Tesseract language code, defaults to auto-detected ('sin+eng' or 'eng').

    Returns:
        The extracted text as a stripped string. Empty string if nothing
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

    # Normalize image to RGB
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    has_sinhala = (TESSDATA_DIR / "sin.traineddata").is_file()

    # ── 2. Run multi-pass OCR ────────────────────────────────────────────────
    try:
        candidates = []
        cfg_block = _build_config(psm=6, oem=1)
        cfg_full = _build_config(psm=3, oem=1)

        # Pre-process image variations
        preprocessed = _preprocess(image)
        padded = ImageOps.expand(image, border=25, fill="black")

        if has_sinhala and (lang is None or "sin" in lang):
            # Pass 1: Raw image with pure Sinhala (avoids digit hallucinations on curves)
            c1 = pytesseract.image_to_string(image, lang="sin", config=cfg_block).strip()
            if c1:
                candidates.append(c1)

            # Pass 2: Raw image with Sinhala + English (for mixed lines)
            c2 = pytesseract.image_to_string(image, lang="sin+eng", config=cfg_block).strip()
            if c2:
                candidates.append(c2)

            # Pass 3: Edge-padded image (helps descenders like 'ෑ' not get clipped by borders)
            c3 = pytesseract.image_to_string(padded, lang="sin", config=cfg_block).strip()
            if c3:
                candidates.append(c3)

            # Pass 4: Preprocessed image with Sinhala
            c4 = pytesseract.image_to_string(preprocessed, lang="sin+eng", config=cfg_block).strip()
            if c4:
                candidates.append(c4)

            # Pass 5: Automatic page layout with Sinhala + English
            c5 = pytesseract.image_to_string(image, lang="sin+eng", config=cfg_full).strip()
            if c5:
                candidates.append(c5)
        else:
            target_lang = lang or "eng"
            c1 = pytesseract.image_to_string(image, lang=target_lang, config=cfg_full).strip()
            c2 = pytesseract.image_to_string(image, lang=target_lang, config=cfg_block).strip()
            c3 = pytesseract.image_to_string(preprocessed, lang=target_lang, config=cfg_block).strip()
            for c in (c1, c2, c3):
                if c:
                    candidates.append(c)

        if not candidates:
            return ""

        # Select the candidate with the highest script quality score
        best = max(candidates, key=_score_ocr_candidate)
        return _post_process_text(best)

    except pytesseract.TesseractNotFoundError as error:
        raise RuntimeError(
            "Tesseract OCR is not installed or not on PATH.\n"
            "Install it with:  sudo apt install tesseract-ocr\n"
            "Then verify with: tesseract --version"
        ) from error
    except pytesseract.TesseractError as error:
        raise RuntimeError(f"Tesseract OCR engine failed: {error}") from error
    finally:
        if isinstance(image_source, (str, Path)):
            image.close()
