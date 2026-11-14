# Codex Working Instructions — AI Snipping Tool for Linux

This repository is an existing Python/PySide6 screenshot utility. **Continue its code; do not rebuild from scratch.** The main source of truth for the development sequence is `AI_Snipping_Tool_Codex_Build_Plan.md`.

## Mission and implementation order

1. Establish the current baseline, verify existing behavior, and document findings.
2. Stabilize application lifecycle and system integration.
3. Make screenshot capture reliable, including multi-monitor and mixed-DPI setups.
4. Complete freeform capture.
5. Support local text extraction from images and documents (PDF, PNG, JPEG, WebP, BMP, TIFF).
6. Deliver accurately benchmarked **English, Sinhala, and mixed Sinhala+English** OCR, with editable results and exports.
7. Finish screenshot annotation, capture history, settings, accessibility, tests, packaging, and offline release.
8. **Implement Ask AI LAST**, only after all non-AI release criteria pass. Do not add AI APIs, dependencies, provider code, or API keys during earlier phases.

## Existing stack to preserve

Python, PySide6, dbus-next, XDG Desktop Portal, Pillow, Tesseract. Target Ubuntu 26.04/GNOME/Wayland first; account for other desktops where feasible. Video recording/PipeWire streaming is out of scope. Screenshots and documents should stay local by default.

## Mandatory engineering rules

- Check `git status --short`, current branch, and HEAD before edits. Never overwrite unrelated uncommitted work.
- Work in a purpose-named branch per bounded task. Never modify `main` directly.
- Do not commit, push, merge, or delete files unless the user explicitly approves.
- Do not rewrite previously working features when a focused fix is sufficient.
- Never call QWidget/QPixmap or Qt clipboard APIs from worker threads; keep long-running OCR, PDF tasks and portal waits from blocking the GUI thread.
- Follow Wayland XDG Desktop Portal permissions and maintain proper application identity. No X11-only keyboard interception.
- No private document uploads, telemetry, secrets in Git, or logging raw document contents.
- Treat OCR accuracy as a measured property. Check availability of Tesseract `eng` and `sin` model data; add reproducible labeled samples and report CER/WER for Sinhala, English and mixed text. Preserve Unicode correctly.
- PDFs with a real text layer should use direct extraction first; scanned PDF pages use OCR. Do not claim that all file formats are OCR images or that accuracy is perfect.
- Each change must include relevant automated tests and clear manual-test instructions. A unit test that emits a shortcut signal is not proof of a real global keyboard shortcut.
- Report actual commands and results: PASS, FAIL, or NOT RUN. Do not claim graphical confirmation unless observed on the user's computer.
- At phase completion, update `docs/baseline-audit.md`, `docs/test-matrix.md`, and the handoff summary. Stop before starting the next phase unless asked.

## Startup instructions

Read `CODEX_START.md` for the first task, and inspect the actual working tree before relying on the source-review notes in `docs/baseline-audit.md`.
