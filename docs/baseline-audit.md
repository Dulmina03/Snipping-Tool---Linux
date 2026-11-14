# Phase 0 — Observed local baseline

Audit date: **2026-11-14 (Asia/Colombo)**. Scope: inspection, isolated checks and documentation only. No production behavior was edited by this audit. Phase 1 has **not** started. Real GNOME GUI acceptance and clean installation remain unverified; this report is not a release sign-off.

## Checkout and preservation

- Verified directory: `/home/dulmina/Projects/ai-snipping-tool`.
- Starting branch: `main`; starting HEAD and local `origin/main`: `ee0c132ece526748b876167c76f434886627f84d` (September 3, 2026). This matches the requested comparison commit. No fetch or remote freshness claim.
- Remote fetch/push: `git@github.com:Dulmina03/Snipping-Tool---Linux.git`.
- Initial tracked modifications: `.gitignore`, `main.py`, `ocr/ocr_engine.py`, `ui/capture_menu.py`, `ui/overlay.py`, `utils/clipboard.py` (280 insertions, 87 deletions). Initial untracked files: `AGENTS.md`, build plan, `CODEX_START.md`, `docs/`.
- Created `chore/phase-00-baseline-audit` at starting HEAD with all local work preserved. First attempt could not write `.git/refs`; the authorized sandbox retry succeeded. No main-branch edits by this audit.
- **Concurrent history change:** while auditing, HEAD advanced through `aaf6cab` to `29e61f5`. No commit command was executed by this agent. These commits contain the previously observed local changes and the new audit probe. They were preserved. The production diff against `ee0c132` matches the initially inspected modifications.
- All five required instruction/reference files existed and were read. Prior versions of these two audit documents were source-review notes, not local runtime results; observed results below supersede them.

## Differences from the September baseline

The local checkout already changes shortcut wiring in `main.py` to call `launch_overlay` directly. `show_from_global_shortcut` also no longer calls `show()` itself. However, `CaptureMenu.__init__` now **shows a transparent 1x1 controller anchor**, rather than hiding the controller. The isolated probe observes `isVisible=True`, size `1x1`; whether GNOME exposes a blank window, task-switcher item or focus disruption is **NOT RUN**.

Local clipboard code adds PNG MIME data, UTF-8 variants and another shown transparent QWidget anchor. These changes are preserved; their claimed Wayland benefits are not established by offscreen checks.

Local OCR is substantially newer than the source-review notes: it supports a language argument, local tessdata, up to five candidates, script-density scoring and line cleanup. It no longer simply chooses the longest text. These heuristics are **not benchmarked** for Sinhala/mixed accuracy. `_setup_tessdata_dir()` can automatically download `sin.traineddata` from GitHub if unavailable; this is pre-existing local code, not added in Phase 0. No document upload or telemetry path was found in the inspected Python sources, but the ordinary OCR path is not strictly offline when model data is missing. Probe calls replace setup and prohibit URL access.

## Observed environment

- Ubuntu **26.04.1 LTS**, GNOME Shell **50.1**, `XDG_SESSION_TYPE=wayland`, `XDG_CURRENT_DESKTOP=ubuntu:GNOME`, `DESKTOP_SESSION=ubuntu`, Wayland socket `wayland-0`, DISPLAY `:0`.
- System and existing `.venv` Python: **3.14.4**. `.venv/pyvenv.cfg` has `include-system-site-packages = true`.
- Existing installed versions match requirements: PySide6/Addons/Essentials/shiboken6 **6.11.2**, Qt **6.11.2**, Pillow **12.3.0**, pytesseract **0.3.13**, dbus-next **0.2.3**. pytest is not installed.
- `pip check`: **FAIL**, missing `charset-normalizer` required by `python-debian 1.0.1+ubuntu2`; system `shiboken6-generator 6.10.2` requires shiboken6 6.10.2 but the environment exposes 6.11.2. These are environment conflicts, not proven capture failures.
- Portal packages: xdg-desktop-portal **1.21.1+ds-1ubuntu3.1**, GNOME backend **50.0-0ubuntu1**, GTK backend **1.15.3-2ubuntu1**.
- Read-only session-bus introspection initially failed under the sandbox (`Operation not permitted`); authorized retry succeeded. Advertised interfaces include Screenshot **v2**, GlobalShortcuts **v1**, host Registry **v1**, ScreenCast **v5**. This establishes service/interface presence only, not permission, registration or successful capture.
- Tesseract **5.5.0**, Leptonica **1.86.0**. System models: **eng, osd**; system `sin` and apt package `tesseract-ocr-sin` absent.
- Ignored `ocr/tessdata/` already contains eng/osd system symlinks and an 8,282,713-byte `sin.traineddata`. Local list-langs: **eng, osd, sin**. Sinhala model SHA-256: `1d95b36e935c8c12cc890684fad15bd3ad8d904c3a6ffa2fccb81658eabd8454`. Its provenance/version was not independently verified. Tesseract successfully loaded it in an isolated call; this does not establish Sinhala recognition accuracy.

## Active and disconnected code inventory

- `main.py`: intended background QApplication/tray daemon; disables quit on last window; starts shortcut manager; tray and shortcut call controller overlay. No application-wide single-instance lock apparent.
- Repository desktop file **and existing installed user desktop file** launch `ui/capture_menu.py`, not `main.py`. Both hardcode this machine's paths. `ensure_desktop_entry()` in `shortcuts/global_shortcut.py` generates the same alternate entry point if missing and never updates an existing file. Desktop syntax validation passes with a multiple-main-category hint; semantic launch mismatch remains.
- `ui/capture_menu.py`: standalone alternate app, shortcut manager, immediate overlay after 200 ms, no tray. Production controller does backdrop portal, rectangle/fullscreen save, window request, OCR, clipboard and toast. Hidden action/mode groups and `_legacy_*` paths exist for old tests. `ScreenshotCapture` is instantiated but normal overlay capture uses its own portal helper.
- `ui/overlay.py`: rectangle selection; portal-window/fullscreen request signals; Screenshot/Extract Text actions; disabled Freeform. Local rectangle signal now fires before close, so synchronous result handling can keep the overlay present while OCR runs. This ordering was preserved.
- `capture/screenshot.py`: Screenshot portal adapter and clipboard, active through compatibility/test paths. `capture/window_capture.py`: interactive Screenshot portal used by production window mode; user still selects the desired mode in the compositor UI. It has a collision fallback, unlike other save paths.
- `capture/selected_area.py`: separate portal/crop/selector path used by the legacy controller and `test_area.py`; not the normal production rectangle handler.
- `ui/selection_overlay.py`: compatibility re-export; `SelectionOverlay = Overlay` is still valid and used by `test_overlay.py`.
- `capture/portal_screenshot.py`: standalone duplicate screenshot experiment; repository reference search found no external import. Response subscription follows introspection, URI is not percent-decoded, no response timeout. Retained.
- `capture/screen_capture.py`: standalone ScreenCast/PipeWire experiment. No production import found. It explicitly invokes `capture/native/pipewire_receiver`, passing portal FD and node ID. Native `.c` files and checked-in binaries were inventoried and frame/FD handling inspected; no external caller of `pipewire_capture` found. Not compiled, executed, removed or archived. Streaming remains out of scope.
- `ocr/ocr_engine.py`: Pillow import/Tesseract only; no PDF text layer or renderer pipeline. `test_ocr.py` can read an explicit image but there is no production document-import workflow, results editor or format/page validation matrix.
- `utils/clipboard.py`: Qt conversion, image/text MIME and clipboard helpers. Calls run on the main thread in these probes. No inference about cross-process Wayland ownership from them.
- No production history/settings/annotation/PDF pipeline or functional Ask AI implementation found. No AI packages/providers/keys added.

## Ordered findings: confirmed versus risks

1. **P0 — Confirmed source mismatch:** desktop file, generated desktop file and `main.py` disagree on production startup. Runtime launch/tray effects remain NOT RUN.
2. **P0 — Confirmed blocking code:** Qt UI callbacks invoke `asyncio.run()` for portal responses (120/180-second response waits) and synchronous Tesseract. A real UI freeze was not physically observed. Avoid moving Qt/clipboard APIs into workers when later fixing this.
3. **P1 — Confirmed shown controller:** isolated Qt reports a visible 1x1 controller; local shortcut change alone does not establish blank-window prevention. Second clipboard anchor also needs real Wayland validation before removal.
4. **P1 — Confirmed output collision:** two `_save_full` calls with fixed second return the same path and overwrite it. Rectangle/general/selected-area saves also use second-only names. Synthetic probe writes only to temporary HOME.
5. **P1 — Confirmed local offline gap:** missing-model OCR setup can download without a separate user action. No such download was run. Later design should validate installed data and provide explicit setup, preserving local documents.
6. **P1 — Confirmed destructive cleanup:** `_post_process_text('- item')` returns `'item'`; punctuation and blank lines can be lost. Candidate score favors scripts/length and penalizes some legitimate digits/symbols. Language argument is not strict: with Sinhala available, `lang='sin'` still runs mixed passes. Accuracy implications need labeled data.
7. **P1 — Confirmed missing capability:** Freeform disabled; system Sinhala model absent, though local model loads; no Sinhala/mixed CER/WER corpus. PDF/image import and editing/export journeys remain future work.
8. **Risk — Geometry:** unioned Qt screen size scaled against whole screenshot assumes uniform mapping; negative origins/mixed DPR/rotated and multiple monitors need real hardware and fixtures. No reproduced mixed-DPI failure claimed.
9. **Risk — Portal races/cleanup:** several paths attach handlers after method response; early responses may be missed. Response waits are bounded in active adapters, but initial bus calls lack explicit application timeouts. Permission fallback can display an unusable overlay after backdrop failure. Source cleanup deletes the returned portal file without ownership tracking. Not exercised against live screenshots.
10. **Risk — OCR resource cost:** minimum-side scaling remains unbounded for thin images; no OCR subprocess timeout/progress/cancel. Full recognition stays on GUI path. No memory stress test run.
11. **Test/packaging gaps:** obsolete visibility expectations, AI placeholder, no collected regression suite, inherited system dependencies and no installer/release docs. See test matrix for specific false-positive risks.

## Reproduction and installation instructions

Existing environment checks are recorded verbatim in [phase-00-command-log.txt](phase-00-command-log.txt). The isolated probe is [phase-00-checks.py](phase-00-checks.py). It uses synthetic content, temporary HOME, Qt offscreen and blocked model downloads; the actual desktop clipboard is untouched.

For a future clean GNOME/Wayland developer install, the proposed commands are below. **NOT RUN** here: apt installation, online pip installation, fresh-account desktop launch. Do not silently replace the current virtualenv or system model files.

```bash
sudo apt install python3-venv tesseract-ocr tesseract-ocr-eng tesseract-ocr-sin xdg-desktop-portal xdg-desktop-portal-gnome
python3 -m venv /tmp/snipping-clean-env
/tmp/snipping-clean-env/bin/python -m pip install -r requirements.txt
/tmp/snipping-clean-env/bin/python -m pip check
tesseract --list-langs
/tmp/snipping-clean-env/bin/python main.py
```

The GNOME session must provide its session bus and Wayland socket; do not force offscreen for physical acceptance. GTK portal backend is installed locally but not proven necessary for this app. A fresh isolated venv was created at `/tmp/snipping-phase00-clean-venv`; `pip install --no-index -r requirements.txt` **FAILS** because no offline distributions are supplied (first missing distribution: dbus-next==0.2.3). This is not evidence that the pins are unavailable online. A wheelhouse/model bundle is needed for reproducible offline installation. Clean installation is **not validated**.

## One next implementation task — proposed, not authorized yet

**Reconcile production startup with `main.py` and prevent the controller appearing as a blank window on activation.** On a future `fix/phase-01-app-lifecycle` branch, align the repository launcher and `ensure_desktop_entry()` generation/update with the same portable installed command and stable APP_ID. Keep the controller hidden in production; revise obsolete visibility tests and verify the existing clipboard workaround before changing it. Preserve capture/OCR behavior. No new runtime dependency is expected for this bounded task.

Exact automated and physical acceptance checks are in the final section of [test-matrix.md](test-matrix.md). This is the smallest Phase 1 slice, **not all of Phase 1**: single-instance control, nonblocking portal/OCR execution and shutdown safety remain required before the full phase exit gate can pass. Stop here for review.
