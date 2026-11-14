**Physical acceptance update — 2026-11-14:** The user confirms all six Phase 2 Task 1 physical acceptance tests PASS and has explicitly authorized Task 2. The earlier NOT RUN statements below record the status before that confirmation. Task 1 is accepted.

# Phase 2 Task 1 — Unique filenames and repeated captures

Date: 2026-11-14. **Implementation and automated verification PASS; physical GNOME acceptance NOT RUN.** The user explicitly authorized this bounded Phase 2 task. Older Phase 1 shortcut/physical acceptance notes remain historical evidence; this task does not imply that those gates were signed off. No Phase 2 geometry, multi-monitor, Freeform or AI work was started.

## Observed problems

Six independent paths generated screenshot filenames:

1. `ui/capture_menu.py::_crop_and_save`: production Rectangle, including images saved for Extract Text.
2. `ui/capture_menu.py::_save_full`: production Full Screen, including images saved for Extract Text.
3. `capture/window_capture.py::take_screenshot`: production Window and standalone compatibility route.
4. `capture/screenshot.py::ScreenshotCapture.capture`: older full-screen/window/area engine and compatibility helpers.
5. `capture/selected_area.py::crop_screenshot`: older selected-area path.
6. `capture/portal_screenshot.py::PortalScreenshot.screenshot`: older portal wrapper.

All used second-resolution names. Five wrote/copied to the chosen path directly. Window used an `exists()` check and short random suffix, which still left a check/write race. Same-second captures could replace earlier PNGs. The Phase 0 B01 failure is now resolved by the new tests.

The production controller retained `last_capture_path` / `last_extracted_text` from a previous operation when a new capture was cancelled or failed before obtaining a result. The compatibility capture method also changed state before rejecting a busy request. Source cleanup could delete an already-saved image if the portal/source path was within the screenshot directory. These are separate state/cleanup defects; no OCR recognition or clipboard encoding defect is claimed here.

## Implementation

All six save paths now use `utils/screenshot_files.py`. The default remains **`~/Pictures/Screenshots/`**.

- Write into an exclusively created, private `.capture-*.tmp` file in the destination directory. Pillow PNG encoding/crop coordinates are unchanged; full/window image copies preserve the encoded bytes exactly.
- Finish and close that file before exposing a screenshot name.
- Atomically publish using `os.link(staging, candidate)`. This operation refuses to replace an existing file, directory or symlink, including a dangling symlink. It also handles other processes winning the same filename after the candidate was selected.
- Try `Screenshot_YYYY-MM-DD_HH-MM-SS.png`, then `_001.png`, `_002.png`, and so on until publication succeeds. The clock alone is never the uniqueness guarantee. There is no replacing rename or exists-then-write sequence.
- Remove only the helper's own staging file on success or failure. Encode/copy/publication errors propagate into existing controller failure handling, with no partial public PNG and no replacement of previous files. Window cleanup now also runs on a save failure.
- Source cleanup protects both the lexical and resolved screenshot directory, including saved symlink entries. Existing saved screenshots remain intact when reused as a source or when cancelling. Other source cleanup retains the pre-existing portal-temporary behavior.
- On a newly accepted controller capture, reset prior path/text/pending-result state. Requests coalesced during a busy operation do not reset that operation. Existing overlay retention, GUI-thread clipboard delivery, OCR cancellation/process boundary and capture algorithms are preserved.

The publication mechanism requires filesystem hard-link support. An unsupported filesystem returns a save error and cleans staging rather than falling back to an unsafe overwrite or a partially visible destination. The actual default directory is on **ext4**, the same device as this checkout. An additional fixture check on that device passed without writing into the user's screenshot directory. Power-loss durability is not a claim of this task.

No changes to `ui/overlay.py`, toolbar design, `utils/clipboard.py`, OCR algorithms, shortcut configuration or system tray logic. Legacy capture paths were updated only for safe saving/cleanup; their older portal/geometry limitations were not expanded or redesigned. PipeWire experiments were not changed or removed.

## Automated verification

**PASS — 107 tests, 9.835 seconds, process exit 0.** All 86 existing regressions plus 21 new cases pass.

`tests/test_screenshot_files.py` has 14 cases covering:

- 100 captures with the timestamp frozen to the same second; every file distinct and previous bytes unchanged.
- Existing filename, directory and dangling-symlink collisions, and a deliberately injected publication race.
- 40 concurrent thread writers with distinct PNG pixels, plus four real separate processes making 32 copies under the same timestamp; all children reaped and no overwritten output.
- No public file during a partial write; incomplete encoding, denied publication, missing source and invalid output-directory errors; clean retry and no abandoned staging files.
- Pixel/byte integrity through production Rectangle/Full Screen and compatibility engine/selected-area/portal save routes.
- Window success, cancellation, write failure, exactly the existing clipboard delivery route, and preservation of a source already in the saved directory.

`tests/test_repeated_capture.py` has seven production-controller cases covering:

- 100 consecutive alternating Rectangle/Full Screen operations, repeat-activation coalescing, one visible overlay, fresh PNG pixels and actual offscreen Qt clipboard MIME bytes after each capture, all earlier files unchanged, a continuing Qt heartbeat, and no remaining asyncio jobs.
- Ten asynchronous OCR-result callbacks with distinct English/Sinhala/ZWJ text, fresh state and exact offscreen Qt text retrieval. OCR replies are fixtures: **this is not Sinhala recognition accuracy or a new OCR engine test**.
- Cancellation before selection, during delayed portal work and during OCR, followed by another successful capture; no late stale text and no orphan job.
- Save failure after an earlier success: overlay closes, no success/clipboard replacement, previous screenshot preserved, staging removed, next capture succeeds.
- Cancelling a saved image reused as the portal source does not delete that image.

These are controlled portal/OCR fixtures and programmatic Qt interactions, not real global-keyboard, native GNOME picker or cross-process paste acceptance. Existing cross-process and physical results are historical; none is newly claimed from same-process MIME checks.

The first isolated repeated-capture runs completed assertions but exited with a Qt offscreen clipboard-owner shutdown segmentation fault. A minimal QApplication + QMimeData text owner reproduced the same exit failure, without the application pipeline. The new test teardown now clears its own offscreen clipboard and drains deferred widget deletion, matching the existing clipboard test discipline. The isolated seven-case run and final full suite both exit 0. Production clipboard behavior was not changed to mask that harness issue.

## Commands and evidence

Read-only initial Git checks: `pwd`, `git status --short`, `git branch --show-current`, `git log -5 --oneline`, `git diff --stat`, `git diff --cached --stat`. Read AGENTS/startup/build plan/handoff and actual save/controller/job/test modules. `rg` inventory now finds screenshot output-name generation only in the shared utility; other remaining time tokens are portal request tokens, not saved filenames.

Created the dedicated branch with `git switch -c fix/phase-02-capture-reliability` from clean `main` at `a451bc3`. No stage, commit, merge, reset or push command was executed by the agent.

Verification commands:

- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v` — 86 previous tests PASS after initial save changes; final 107 tests PASS, 9.835s, exit 0. Output retained at `/tmp/snipping-phase02-regressions.log`.
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -p test_screenshot_files.py -v` — 14 PASS, exit 0; `/tmp/snipping-phase02-files.log`.
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -p test_repeated_capture.py -v` — final seven PASS, exit 0; `/tmp/snipping-phase02-repeat.log`. Earlier shutdown-fault evidence: `/tmp/snipping-phase02-repeat-fault.log`.
- `.venv/bin/python -m compileall -q capture ui/capture_menu.py utils/screenshot_files.py tests/test_screenshot_files.py tests/test_repeated_capture.py` — PASS.
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -c 'import capture.screenshot, capture.selected_area, capture.window_capture, capture.portal_screenshot, ui.capture_menu, utils.screenshot_files'` — PASS.
- `git diff --check` and `git diff --cached --check` — PASS.
- `findmnt -T /home/dulmina/Pictures/Screenshots -n -o FSTYPE` — `ext4`; screenshot directory/checkout device both 66309. `/tmp` test device 48. Additional `TemporaryDirectory(dir=Path.cwd())` fixture publication: four same-second PNGs, four names, exact colors, zero staging files, own fixture directory cleaned.

An external commit **`7a88a0c`** appeared during work and contains the initial saving refactor. Later the Window/helper refinements and two test files were externally staged. The agent did not perform those operations; both the commit and index were preserved. Recheck current HEAD/index before continuing; do not unstage or overwrite external work.

Files authored/modified for this task: the six production files listed above including the new shared utility, `tests/test_screenshot_files.py`, `tests/test_repeated_capture.py`, this document, `docs/handoff-summary.md`, `docs/test-matrix.md`, and `docs/baseline-audit.md`.

## Remaining physical acceptance — NOT RUN

1. Launch through GNOME, use the actually assigned shortcut, and take at least ten rapid Rectangle/Full Screen captures with visibly different public content. Confirm distinct PNG names in `~/Pictures/Screenshots/`, correct images, and no earlier image modified.
2. Alternate capture → Escape → capture, including cancellation of GNOME's Window picker. Complete a Window capture afterward. Expect no stuck/duplicate overlay or process.
3. Repeat Screenshot → external image paste and Extract Text → external English paste, including a capture immediately after cancelling OCR. Confirm fresh results and no stale text/clipboard replacement on cancellation or save failure.
4. Quit through the tray after the series. Confirm clean exit and no remaining app/OCR process. Do not induce disk-full/permission errors in the real screenshots directory; those paths have deterministic fixture tests.

Task 1 implementation is ready for physical acceptance. Phase 2 overall remains open; do not continue to Task 2, Freeform, multi-monitor changes or AI without the next instruction.
