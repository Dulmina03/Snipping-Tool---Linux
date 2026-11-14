"""Child-process boundary for the existing OCR engine; no Qt imports."""
import contextlib
import io
import json
import sys


def main():
    from ocr.ocr_engine import extract_text
    try:
        # Keep engine diagnostics separate from the result protocol and private text.
        with contextlib.redirect_stdout(io.StringIO()):
            text = extract_text(sys.argv[1])
        print(json.dumps({'text': text}, ensure_ascii=False))
        return 0
    except Exception:
        print(json.dumps({'error': 'Local OCR failed; check Tesseract and language data.'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
