# Phase 0 — Observed test matrix

Date: **2026-11-14, Asia/Colombo**. Environment and code ownership: [baseline-audit.md](baseline-audit.md). Exact executable check commands, output and exit codes: [phase-00-command-log.txt](phase-00-command-log.txt). PASS below applies only to the stated check. No physical GUI acceptance was observed.

## Automated and environment results

| ID | Check | Result | Evidence and limit |
|---|---|---|---|
| E01 | Installed requirements/versions | PASS | Existing environment versions match requirements; Qt 6.11.2/Python 3.14.4 |
| E02 | Dependency consistency | FAIL | `pip check`: missing charset-normalizer and shiboken6-generator version conflict |
| E03 | Compile source and all test scripts | PASS | `compileall`, exit 0; does not execute GUI code |
| E04 | Target desktop environment | PASS | Ubuntu 26.04.1, GNOME 50.1, Wayland environment variables; not visual confirmation |
| E05 | Portal interfaces advertised | PASS | Authorized read-only introspection: Screenshot v2, GlobalShortcuts v1, Registry v1; no capture/registration requested |
| E06 | System OCR language availability | FAIL | `eng, osd`; `sin` missing and apt package absent |
| E07 | Local OCR language availability | PASS | `--tessdata-dir ocr/tessdata`: eng/osd/sin; ignored local sin model loads |
| E08 | Clean environment creation | PASS | `python3 -m venv /tmp/snipping-phase00-clean-venv` |
| E09 | Fresh offline dependency install | FAIL | `pip install --no-index -r requirements.txt`: no distributions supplied; online install NOT RUN |
| E10 | Desktop-file syntax | PASS | `desktop-file-validate`, exit 0; multi-category hint; entry point still wrong |
| E11 | Whitespace check | PASS | `git diff --check`, exit 0 |
| A01 | Existing menu `--smoke` | PASS | offscreen, temporary HOME, exit 0; no tray or launch verification |
| A02 | Existing menu `--cancel` | PASS | offscreen, mocked `_capture=lambda: None`, exit 0; no real portal denial |
| A03 | Existing menu `--ai` | FAIL | obsolete placeholder expectation, exit 1; no AI implementation attempted |
| A04 | Production-module imports | PASS | 12 modules imported by phase-00-checks.py; entry points not invoked |
| A05 | Synthetic rectangle signal | PASS | expected selection rectangle received; no mouse drag/compositor involved |
| A06 | Image clipboard MIME | PASS | PNG signature and Qt hasImage offscreen; no cross-app paste |
| A07 | Sinhala/English/ZWJ clipboard | PASS | exact UTF-8 MIME and same-process text equality offscreen |
| A08 | Synthetic English OCR | PASS | one 900x160 DejaVuSans 36px fixture, CER=0/WER=0, raw string Levenshtein; no normalization; not representative |
| A09 | Sinhala recognition accuracy | NOT RUN | local model loading only; no human-verified Sinhala corpus |
| A10 | Mixed recognition accuracy | NOT RUN | no human-verified mixed corpus |
| B01 | Unique same-second full-save path | FAIL | isolated `_save_full` probe returns same filename twice; writes only in temp HOME |
| B02 | Preserve OCR punctuation | FAIL | isolated cleanup turns `- item` into `item` |
| B03 | Hidden controller state | FAIL | baseline offscreen isVisible=True, size 1x1; physical blank window remains unverified |

Qt scripts print a Settings.ReadAll D-Bus disconnection warning in this sandbox even when checks pass. Offscreen deliberately does not use the real Wayland display. The probe blocks model setup/download calls and does not read private screenshots.

## Existing test harness limitations

- `test_screenshot.py`: interactive portal and same-process clipboard presence, not an image-content assertion or paste check.
- `test_area.py`, `test_window.py`: interactive. Cancellation/failure returning None can still result in process exit 0; do not interpret that as successful capture.
- `test_overlay.py`: launches a GUI event loop at module scope. **Do not blindly collect/import all test_*.py with pytest/unittest discovery.** Compatibility alias remains valid; script requires a person to exercise selection.
- `test_capture_menu.py`: smoke/cancel run above. `--run MODE ACTION` exercises hidden compatibility controls and legacy backend, not normal toolbar orchestration. Default script shows the controller and has stale manual instructions. `--ai` expects an obsolete placeholder; retain as evidence, not a reason to add AI.
- `test_global_shortcut.py`: registers then emits `shortcut_activated` itself and checks controller visibility. It can call a real screenshot request, but cannot prove a physical keypress and conflicts with the desired hidden controller. NOT RUN.
- `test_clipboard.py`: uses newest personal screenshot by default and exits quickly; script success is not persistent cross-process ownership. NOT RUN on the actual desktop. Synthetic MIME coverage is in the isolated probe.
- `test_ocr.py`: prints extracted document contents and declares PASS even for empty text; no ground truth/CER/WER. NOT RUN on private screenshots. Use only an explicit public/synthetic fixture in later manual work.

## Physical and later-feature checks — all NOT RUN

Run on the user's real session with `.venv/bin/python main.py`; authorize portal prompts normally. Record the actual outcome and display setup. Do not run two app entry points simultaneously. No graphical confirmation is claimed here.

| ID | Journey / command | Required observation | Status |
|---|---|---|---|
| C01 | Full Screen via toolbar; optional `test_screenshot.py` | correct whole-screen pixels, no overlay in output | NOT RUN |
| C02 | Rectangle drag; optional `test_area.py` | selected pixels and dimensions exactly match saved PNG | NOT RUN |
| C03 | Window via toolbar; optional `test_window.py` | choose Window in portal, verify exact target window | NOT RUN |
| C04 | Physical Ctrl+Shift+S with another app focused | portal-approved shortcut opens exactly one overlay | NOT RUN |
| C05 | Capture then paste in two other GUI apps | actual image, correct dimensions; retry after toast/overlay closes | NOT RUN |
| C06 | Public English image OCR | compare text to reference and paste externally | NOT RUN |
| C07 | Labeled Sinhala and mixed images | CER/WER per script; preserve ZWJ/combining marks on paste | NOT RUN |
| C08 | Tray and Quit | capture action, no ghost window, process exits and shortcut session closes | NOT RUN |
| C09 | Esc, toolbar X, portal Cancel/denial | no saved output, stuck overlay or orphan process; retry works | NOT RUN |
| C10 | Two monitors/mixed scale/negative origins/rotation | map each selection to exact expected pixels; record actual hardware/DPR | NOT RUN |
| C11 | Repeated shortcut/captures in one second | no extra controller/duplicate requests or overwritten outputs | NOT RUN |
| D01 | Digital PDF | direct text extraction, page order, source unchanged; absent feature | NOT RUN |
| D02 | Scanned/mixed PDF | OCR only required pages, progress/cancel/export; absent feature | NOT RUN |
| D03 | PNG/JPEG/WebP/BMP/TIFF | EXIF/alpha/multipage/corrupt-input handling; no production importer | NOT RUN |
| R01 | Fresh-account installation and offline use | dependencies/models/launcher/shortcut/paste/quit; no installer yet | NOT RUN |

## Exact acceptance tests for the proposed first Phase 1 task

These are **future tests**, not results. Task: canonical production launcher plus hidden controller on shortcut activation. Do not implement before user review.

1. **Automated launcher contract:** inspect both repository launcher and generated desktop file in temporary HOME. Exec resolves to the same installed production command/`main.py`, never `ui/capture_menu.py`; no developer home path; stable `com.dulmina.aisnippingtool` identity. Validate both files using `desktop-file-validate`. Generate from an install path containing spaces and verify correct quoting. Exercise stale launcher migration without overwriting unrelated custom entries.
2. **Automated startup contract:** construct app/controller without opening portal/network requests. Assert controller hidden at startup and after capture cancel/completion; do not use a 1x1 visible controller to satisfy old tests. Assert shortcut/tray wiring targets the canonical workflow. Use mocked capture only for wiring assertions; it is not a real shortcut test.
3. **Real launcher:** quit the existing instance, launch from GNOME app grid using the installed desktop entry. Expect background utility/tray where supported, no immediate overlay and no blank controller/task-switcher item. Record absent GNOME tray support explicitly; do not treat an offscreen test as proof.
4. **Real shortcut and repeat:** focus a different app, physically press the portal-assigned Ctrl+Shift+S, complete a rectangle and externally paste it. Repeat ten times, alternating Esc, toolbar X and completion. Expect one overlay at a time, no blank window, no focus theft after completion and continued ability to capture.
5. **Clipboard regression:** externally paste PNG immediately and after the overlay/toast closes (wait five seconds). OCR a public fixture containing `ශ්‍රී English 123` and paste into a text editor, checking combining marks/ZWJ against a human-verified reference. Do not remove any anchor workaround until these pass on real Wayland. Clipboard preservation is a release requirement independent of same-process equality.
6. **Quit/restart:** Quit via the supported production control. Check the launched PID exits within five seconds and its shortcut session stops; restart from app grid and repeat shortcut/capture/paste. No screenshot or source document may be deleted or altered by testing cleanup.
7. **Regression check:** rerun compileall, isolated menu cancellation and updated lifecycle tests; report every command/exit code. Do not carry forward the old `menu.isVisible()` shortcut success criterion or add an AI placeholder implementation.

The full Phase 1 gate also requires responsive denied/delayed portal requests, safe worker/main-thread boundaries, cancellation/shutdown and duplicate-instance prevention. Those remain separate work after this smallest slice. Passing these launcher tests alone does not complete Phase 1.
