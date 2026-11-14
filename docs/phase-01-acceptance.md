## Production clipboard delivery fix and Window investigation — 2026-11-14

**Phase 1 remains OPEN. Do not start Phase 2.** Latest user-confirmed physical results supersede earlier entries: GNOME grid startup, Ctrl+Shift+S overlay, Escape and real tray Quit **PASS**. Rectangle paste, English OCR paste, OCR after focus switching and Window capture **FAIL before this change**. Full post-change physical confirmation is pending. No claim of Sinhala OCR recognition accuracy is made.

### Image and OCR delivery root cause

The saved PNG and returned OCR text were not automatically evidence of desktop clipboard delivery. The actual controller closed/unmapped its only real capture surface before `copy_image_to_clipboard`, or before asynchronous OCR returned and `copy_text_to_clipboard` ran. Earlier native protocol evidence showed compositor focus leaving before set_selection, then selection cancellation/old data returned to another process, even while Qt sometimes reported ownsClipboard=true. The same helper worked with a focused persistent surface. That identifies a production lifetime/focus-ordering defect, not broken PNG MIME encoding or a Tesseract algorithm failure. The invisible 1px anchor and nested processEvents did not establish authorized focus or delivery and were not a substitute for the real capture surface.

The fix publishes while the existing capture overlay is still alive and focused, then closes it; QApplication stays alive to serve the MIME data to external clients. OCR keeps the same overlay through its async result, with mode/action inputs disabled during processing and Escape/cancel available. If the user switches to another application before OCR completes, the result is retained without claiming a successful background write. Return to the overlay and click or press Enter to publish from a real focused input event. No invisible focus window, forged serial or desktop security bypass is used. Layout/design of the overlay is unchanged.

The native production-handler probe now passes exact external PNG and UTF-8 retrieval, twice per result with focus changing to separate reader processes. This validates the ordering fix in automation. It does not replace the user's required physical confirmation or establish that no desktop-specific issues remain.

### Production changes and diagnostics

- `ui/capture_menu.py`: preserves the capture surface through save/copy or OCR completion; queues deferred result delivery when unfocused, permits an explicit retry, cancels pending OCR on Escape, avoids false success after a copy exception, and resets stale previous OCR state. Window results return through this same delivery path.
- `ui/overlay.py`: removes the premature fullscreen hide and guards rectangular auto-close while processing; preserves existing layout, allows Escape/cancel, prevents another selection during OCR and permits click/Enter delivery after focus returns. Freeform remains disabled.
- `utils/clipboard.py`: retains valid image/png, image/x-png, Qt image data, and exact UTF-8 text MIME handling; enforces the Qt GUI thread. Removes the invisible anchor and nested processEvents. Standard Copy writes **QClipboard.Clipboard only**, without modifying primary Selection. QApplication/QClipboard own and serve the data after the overlay closes. Invalid image/PNG encoding produces an error rather than a success notice.
- `capture/window_capture.py`: controller can request save-only (`copy_to_clipboard=False`) so the backend no longer copies once without focus and then copies a second time in the controller. Existing standalone default, file save and crop/OCR algorithms preserved. Controller restores its existing surface after the picker result, then publishes while focused or retains the result for a real click/Enter.
- `utils/capture_diagnostics.py`, `main.py`, `capture/screenshot_portal_request.py`: **opt-in temporary local diagnostics**, enabled by `SNIPPING_DIAGNOSTICS=1`. Records action/mode, source/saved path, existence/valid PNG, dimensions/file size, post-handler execution, clipboard invocation/thread/MIME/Qt ownership, OCR character count and event-loop heartbeat. Never logs pixels or extracted text. Default launch leaves these detailed diagnostics off. Portal D-Bus errors retain existing diagnostic logging.

### Window capture: confirmed stages and limits

Installed Screenshot frontend and GNOME backend are version **2**, not v3. Version 2 supports `interactive`; it does not provide v3 `target=2` / AvailableTargets to force Window selection. The app's Window button successfully reaches the real interactive GNOME picker. Native accessibility exposed Window, Screen, Selection and Take Screenshot controls; they had no usable AT-SPI Action interface. Heartbeats continued while the portal request was pending. No unsupported target option or alternate capture backend was added.

The picker still requires **Window → select a thumbnail/window → Capture**. We did not execute a real selected-window completion through an authorized automated control. The diagnostic request was cancelled/closed after waiting; no visible picker remained afterward (AT-SPI SHOWING=false). GNOME logged `InteractiveScreenshot didn't return a file` for that incomplete request, not evidence of PNG save corruption. Its exact relationship to the user's earlier Window failure is **unconfirmed**. Do not claim a confirmed picker/root cause from an intentionally incomplete interaction.

A confirmed window-path problem was duplicate clipboard publication after losing the capture surface. That is corrected independently. Unit integration verifies returned PNG save bytes, one controller copy while the surface is visible, and cleanup without copy on cancellation. Real Window completion, returned-image integrity and physical paste remain **NOT RUN after the change**, pending the user test. The user's earlier Window FAIL remains an unresolved acceptance blocker.

### Tests and evidence

- **PASS — 74 regression tests**, all previous 66 plus 8 focused delivery tests. Cover real production area/OCR handlers, copy-before-teardown, async surface retention, deferral on lost focus, cancellation/no late delivery, copy-failure messaging, worker-thread rejection, and window result/cancel handling. Existing tests retained; a window mock now accepts the production save-only keyword.
- **PASS — native two-process production-handler integration:** rectangle, fullscreen, repeated rectangle, **real existing English OCR subprocess**, and supplied mixed Sinhala/English/ZWJ/punctuation text. Each validates the saved PNG against expected source pixels and uses two new native reader processes to decode exact PNG pixels or compare exact UTF-8 bytes and actual pasted editor contents, including after overlay close/focus switching. Every case PASS; event loop remained active; canonical main exited with no shortcut thread left.
- The native integration uses public deterministic **portal backdrop fixtures**, not real user desktop selection. It executes the actual production overlay/result/save/OCR/clipboard handlers. The mixed-language case supplies a known recognizer string only to test transfer; it does not test Sinhala recognition. The English case invokes the unchanged local OCR worker. No model/engine change or network OCR.
- **PASS — real Window request/picker stage**, responsive Qt loop and cleanup; selected-window completion **NOT RUN**. Mocked success/cancel tests do not override this limit.
- **PASS — syntax/import checks and staged/unstaged whitespace checks.** Initial new-test discovery found a root/tests `test_clipboard` module-name collision caused by a probe prepending the checkout to sys.path; fixed by preserving path order. One new crop-size assertion initially used native-size assumptions in the headless screen; fixed to use an explicit fixture virtual size. Final full suite exits 0; failed exploratory runs are not counted as passing.
- **Physical after change: NOT RUN / pending user report** for image paste, English OCR paste (including focus switches), and Window completion/paste. Already-confirmed physical startup/shortcut/Escape/tray PASS is retained. **Phase 1 cannot close until the user confirms all three delivery requirements.**

The final native public-fixture records and test output are retained in [phase-01-delivery-evidence.txt](phase-01-delivery-evidence.txt). Reproduction: `.venv/bin/python tests/production_clipboard_probe.py` in a genuine GNOME terminal (overwrites clipboard with public data). Headless suite: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v`. A diagnostic copy of the updated canonical app is running for the pending user retest; its local log is `/tmp/snipping-physical-delivery-session.log`. It is an intentional background app, not an orphan. No further GUI probe should steal focus during that retest.

### Git and authored files

Started clean on `fix/phase-01-app-lifecycle`, HEAD `f62fc02`; index empty. Existing external commits retained. This agent ran no stage, commit, reset, clean, unstage, checkout, merge or push. Recheck current status before further work.

Task changes: `main.py`, `capture/screenshot_portal_request.py`, `capture/window_capture.py`, `ui/capture_menu.py`, `ui/overlay.py`, `utils/clipboard.py`; new `utils/capture_diagnostics.py`, `tests/production_clipboard_probe.py`, `tests/test_capture_delivery.py`; small compatibility fixes in `tests/test_phase01.py`, `tests/clipboard_native_probe.py`; acceptance, handoff, matrix, baseline and new delivery evidence. Legacy capture/PipeWire experiments, shortcut registration/assignment, OCR algorithm, AI/PDF/Phase 2 are untouched.

Minimum user test (already requested asynchronously): physically capture a rectangle and paste into an image-capable application; Extract Text from public English and paste, including after switching focus; Window → Window in GNOME's picker → select → Capture → external paste. If OCR finishes unfocused, return to the existing overlay and click/Enter to copy. Report the exact stopping stage/status for any failure. Do not mark these PASS from the scripted probes.

References: [Screenshot v2 interactive versus v3 target contract](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.Screenshot.html), [GNOME backend interactive request implementation](https://raw.githubusercontent.com/GNOME/xdg-desktop-portal-gnome/main/src/screenshot.c). Earlier native selection-serial traces remain in [clipboard evidence](phase-01-clipboard-evidence.txt).

---

## Physical failure diagnosis and first-use permission fix — 2026-11-14

**Phase 1 remains OPEN. Phase 2 is not authorized.** This supersedes older acceptance assumptions. User physical results before this fix: app-grid launch PASS; shortcut capture, Escape, rectangle/paste, English OCR/paste, window capture and tray Quit FAIL. The shortcut signal itself did reach the app; the first screenshot failed before an overlay existed.

### Confirmed screenshot root cause

At 08:36:08, 08:36:16, 08:36:38 and 08:37:07 +0530 the genuine app-grid process PID 134609 logged `Portal Activated signal for open_capture_menu`. Immediately afterward GNOME logged `Failed to associate portal window with parent window` and portal AccessDenied: **`Only the focused app is allowed to show a system access dialog`**. The old controller replaced the underlying failure with a generic cancelled/denied message. There was no evidence that the user cancelled.

A controlled background request with **com.dulmina.aisnippingtool explicitly registered on the screenshot connection** reproduced method return with a request handle, then **Response `[2, {}]`**. Correct identity alone does not give a background app permission to show GNOME's first-use access dialog. A focused real Qt window, with the same app/desktop ID and registration, instead exposed GNOME's **Allow AI Snipping Tool to Take Screenshots?** dialog and Allow/Deny buttons through accessibility. The user subsequently confirmed **“Yes, I clicked Allow.”** The permission entry changed from only anonymous `'' → yes` to additionally `com.dulmina.aisnippingtool → yes`. No agent tool chose Allow/Deny, reset permissions or edited the permission store. After that explicit consent, properly registered background screenshot requests succeed with response 0.

The earlier automated environment was not equivalent to the physical app-grid path: screenshot connections were unregistered even when the separate shortcut connection was registered, and the anonymous permission entry was already yes. The exact identity of each historical screenshot connection was not recorded; do not treat those earlier screenshots as proof of first-use named-app consent.

### Actual request and identity evidence

- GNOME Shell 50.1-0ubuntu1.5; xdg-desktop-portal 1.21.1+ds-1ubuntu3.1; xdg-desktop-portal-gnome 50.0-0ubuntu1. Screenshot frontend **version 2**, GNOME backend **version 2**. GNOME portal routing prefers gnome then gtk; GNOME advertises Screenshot and Access.
- Actual flow: `GlobalShortcuts.Activated(open_capture_menu)` → Qt `CaptureMenu.launch_overlay` → AsyncJobs on Qt GUI thread → first noninteractive Screenshot request. Stable shortcut and working Ctrl+Shift+S assignment unchanged.
- New shared production request layer connects its own session bus, performs `org.freedesktop.host.portal.Registry.Register(APP_ID,{})` **before any portal method on that same connection**, then queries Screenshot version and calls `org.freedesktop.portal.Screenshot.Screenshot`, signature `sa{sv}`. Failed identity registration is reported; no anonymous fallback or Snap impersonation.
- Backdrop: `parent_window=''`, options `handle_token=<unique token>`, `interactive=false`, `modal=true`. Window route: same identified helper with `interactive=true`. Request handle and response code/payload shape logged; local URI value redacted in persistent logs. Controlled failure connection `:1.2704` returned the predicted request handle and response 2, empty payload. Final recovery connections `:1.2878` and `:1.2879` both registered the correct app ID and returned response 0 with a local screenshot URI.
- Empty parent is a **valid optional parent**, not an exported Wayland surface. No wl_surface pointer was fabricated as an xdg_foreign handle. PySide6 here exposes no QWindow Wayland export-handle binding. GNOME's AccessDialog implementation checks focused app identity independently of parent_window. The same empty parent succeeds for a focused consent request, and after consent for background requests. Parent-association warnings remain possible; they were not the fatal focus rejection. This is a documented limitation, not a claim that an exported parent was supplied.

### Small supported changes

1. `capture/screenshot_portal_request.py`: shared identified request transaction, unique handles, subscription before method call, early/changed-handle response handling, bounded waits, Request.Close on cancellation/timeout, handler removal/disconnect. Distinct error kinds: portal cancellation, permission error, identity failure, unavailable backend/method, timeout, unexpected/malformed response. Response 2 is never labeled user cancellation. Response 1 explicitly admits that the portal may also mean permission declined; that ambiguity cannot be resolved from the code alone. Detailed errors preserved in status/logs.
2. `ui/capture_menu.py`: on a direct permission error or response 2, show a small real **Screenshot permission** recovery dialog, with explicit Continue and Cancel. Only Continue requests again from that real focused window; no automatic consent. Startup/controller remain hidden. A successful consent-time screenshot is discarded, the recovery window closes, and a fresh backdrop is requested before the existing overlay opens, so the permission window is not in the selected image. Escape/cancel closes the recovery dialog and cancels pending request. Other failures keep specific diagnostics rather than a blanket cancellation claim.
3. `capture/window_capture.py`: only the request transaction is replaced with the same identified helper; existing destination naming, file copy, clipboard and cleanup behavior retained. A response-2 error is propagated rather than silently treated as cancellation. Legacy/disconnected capture/PipeWire experiments retained.
4. `main.py`: tray Quit logs receipt and queues QApplication.quit for the next Qt turn; aboutToQuit and cleanup stages log separately. This adds evidence and avoids exiting inside native menu dispatch; it is not claimed to have fixed the unobserved physical tray failure.

### Independent tray Quit result

The original live tray item `:1.2532` exposed enabled Quit id 1, with correct app ID. A normal DBusMenu Event(`clicked`) on that exact item returned success; PID 134609 exited within **0.1s**. This demonstrates that the app-side action/shutdown path worked under protocol activation, not that the user's physical click worked. No stale/duplicate-app explanation is assumed.

The updated canonical native probe also used a PID-verified real DBusMenu Quit event. Logs show `Tray Quit action received` → `QApplication aboutToQuit emitted` → capture-job cleanup → shortcut session cleanup → `Shutdown complete`; main exit 0 and shortcut thread stopped. No test app interpreter remained afterward. **Physical tray Quit after the update is NOT RUN**. If it fails again, check whether the new action-received line exists; absence points to delivery before the app handler, while later stage logs locate an app shutdown stall. Neither is assumed without evidence.

### Test and acceptance results

- **PASS — 66 automated tests** (50 previous +16 new), 3.210s, exit 0. Coverage includes raw response 2 focus failure, cancellation/permission ambiguity, AccessDenied/missing backend/unexpected errors, independent Registry ordering/failure, changed-handle early response, timeout/cancel cleanup, explicit permission retry without silent consent, clean backdrop recapture, pending-dialog cancellation, unchanged window file-copy/clipboard route and queued Quit. Compile/import and both whitespace checks PASS.
- **PASS — native diagnosis:** identified background request fails with response 2 before consent; focused Qt request exposes actual GNOME consent dialog. User clicking Allow is confirmed user interaction, not automated consent.
- **PASS — native post-consent:** three real portal returns and screenshot saving again work; existing overlay/controller state and main shutdown pass. Existing local English fixture OCR still returns exact reference. These toolbar/selection events are synthetic, not physical input. Native text retrieval in that repeated synthetic workflow still FAILS with an active reader. A valid image-paste check is NOT RUN because the final image receiver lacked focus (the raw harness labels it FAIL); prior clipboard handoff concerns are not declared fixed.
- **PASS — final native recovery flow:** actual implemented recovery QDialog active; simulated Continue click; two real identified screenshot returns; dialog closed; hidden controller; existing overlay visible. Synthetic Qt Escape closes it. This verifies the implementation with the user's now-granted permission; first-use Allow was observed in the separate focused-window probe. Permissions were not reset to rerun first use.
- **PASS — native tray transport/cleanup:** original exact PID exits in 0.1s; updated canonical main receives real DBusMenu Event and logs all shutdown stages. **NOT RUN — physical menu click delivery after fix.**
- **FAIL — user's original physical capture/Escape/rectangle/OCR/window/tray acceptance** remains the pre-fix observed result. **NOT RUN — full post-fix physical retest**. Background permission failure is addressed and verified natively, but screenshots/paste, real Escape/window selection and physical tray actions must be confirmed again. Phase 1 cannot close on unit results alone.

### Git provenance and preserved work

Start: branch `fix/phase-01-app-lifecycle`, HEAD `68e48a6`, six pre-existing staged changes (baseline, handoff, acceptance, clipboard evidence, matrix, native clipboard probe), no unstaged changes. These were preserved. External commits `4a1a7c2` (those existing changes), `a5b6d11` (part of this task's implementation) and `1f6a461` (restored experiment/new module and regressions) appeared during work; further external staging occurred. HEAD at final documentation check is `1f6a461`; index empty, documentation edits unstaged/untracked. Agent executed no stage, unstage, commit, reset, clean, checkout, merge or push. Do not infer actor from author metadata; provenance remains external/unidentified.

A naming mistake initially replaced the standalone `capture/portal_screenshot.py` experiment and was included by an external commit. It was corrected: original file restored byte-for-byte from task-start HEAD; new helper uses separate `capture/screenshot_portal_request.py`. References were reviewed; no legacy experiment was removed. History was not rewritten. Some authored changes are already in an external commit/index; final Git status must be reviewed as-is.

Task-authored files: `main.py`, `ui/capture_menu.py`, `capture/window_capture.py`, new `capture/screenshot_portal_request.py`, `tests/test_phase01.py`, new `tests/test_screenshot_permission.py`; restoration of `capture/portal_screenshot.py`; acceptance, handoff, baseline, matrix and [new evidence log](phase-01-physical-failure-evidence.txt). Existing overlay, clipboard helper, OCR engine and shortcut manager algorithms unchanged. No AI/PDF/Phase 2 work.

### Minimum remaining physical verification

1. Open the updated app from GNOME's app grid. Focus another app, Ctrl+Shift+S, then Escape. Since you already clicked Allow, expect the overlay directly. If another legitimate permission dialog appears, use its explicit Continue/Allow/Deny controls and report the exact status; no permission reset needed.
2. Repeat for a rectangle and full screen; paste into an image-capable app. Capture public English text in Extract Text mode and paste externally. Also select a real Window in GNOME's picker. Check whether real input resolves the separately recorded clipboard handoff failure.
3. Click real tray Quit. Confirm icon/process exit. If not, preserve the journal lines containing `Tray Quit`, `aboutToQuit` and `Shutdown`; they now distinguish event delivery from cleanup failure.

Sources: [GNOME AccessDialog focused-app check](https://raw.githubusercontent.com/GNOME/gnome-shell/main/js/ui/accessDialog.js), [portal window identifiers (empty allowed)](https://flatpak.github.io/xdg-desktop-portal/docs/window-identifiers.html), [Screenshot portal contract](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.Screenshot.html), [Registry connection identity](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.host.portal.Registry.html).

---

## Clipboard investigation and shortcut capability correction — 2026-11-14

**Current decision: Phase 1 OPEN. Do not start Phase 2.** This section supersedes earlier current-status statements. Production capture, clipboard and OCR algorithms are unchanged. The only production behavior change is conservative ConfigureShortcuts capability gating and its explanation.

### Findings and limits

The delivery failure is at the native Wayland selection handoff, not a demonstrated PNG/Unicode encoding failure, worker-thread write, destroyed QApplication or stopped event loop. The synthetic test also had a confirmed receiver flaw: plain QTextEdit accepts text/rich text, not standalone PNG paste by default. The replacement reader explicitly supports image insertion. This alone does not explain all failures: the corrected canonical workflow still fails cross-process image/text retrieval.

A persistent, focused native Qt owner successfully transferred fresh PNG pixels and exact English/Sinhala/ZWJ UTF-8 text to a different native process, which actually decoded and pasted them. The final traced run's focused image and text cases both PASS. Unmapping the owner before copying, delaying the copy and using the controller's result handlers then FAIL in that run despite live event loops and GUI-thread writes. An earlier untraced run passed these same unmapped/delayed/controller cases; this variability is evidence of a compositor focus/selection timing dependency, not reliable acceptance. Neither an image-shaped MIME offer nor local ownsClipboard() proves delivery.

Protocol evidence: background calls sent `wl_data_device.set_selection(..., 0)`. Focused controls used real compositor pointer-enter serials and succeeded. After an owner was unmapped, keyboard/pointer leave preceded set_selection and data_source.cancelled followed; the reader got previous/different data. The canonical workflow similarly sets image data after its overlay closes; its first fullscreen source was cancelled, and the corrected reader did not retrieve the expected image. Later OCR reused the previous input serial. A cancelled source alone is not proof of rejection (clipboard managers can replace sources); the retrieval failure is the decisive observation. Synthetic Qt clicks do not produce trusted compositor key/button serials. Actual input may differ, and physical copy/paste remains NOT RUN. Thus a focus/selection race is established in automation, but its exact compositor validation path and effect on physical use remain unresolved. It would be inaccurate to declare either an application-wide clipboard fix or a harmless test-only failure.

No clipboard behavior change was justified without choosing and validating a supported focus/user-action strategy, especially for OCR finishing after another app gains focus. We did not force focus, invent serials, keep a new blank controller visible, switch to X11 or bypass desktop security. Persistent ownership/event-loop and MIME hypotheses were tested rather than rewriting those helpers. The existing helper's invisible anchor is not proof of compositor acceptance; its docstring should not be treated as such.

### Pipeline and ownership trace

- A single QApplication in canonical main owns the controller, native overlays, clipboard and event loop. `_on_fullscreen` / `_on_area_selected` close the overlay, save/crop the existing backdrop, then call `_handle_capture_result` → `copy_image_to_clipboard`. The helper loads QImage, attaches Qt image data plus encoded `image/png` / `image/x-png`, then transfers QMimeData ownership to QClipboard. It may also publish primary selection. The persistent application and helper anchor remain alive after overlay disposal.
- OCR: `_handle_capture_result` → `AsyncJobs.submit(_recognize)` → `extract_text_async` spawns `python -m utils.ocr_job`. Only recognition runs in that child; it returns local JSON text. Qt's timer advances the parent asyncio loop on the GUI thread. `_recognize` resumes there and calls `copy_text_to_clipboard`, publishing text/plain, UTF-8 charset data and UTF8_STRING. No Qt GUI/clipboard call occurs in the OCR child.
- Native instrumentation recorded actual image and OCR helper calls on QApplication.thread(). The owner and reader both serviced their event loops. Tests verified overlay/controller cancellation does not itself clear Qt's locally stored MIME, and shutdown cancels pending OCR before any late clipboard write. Application exit is not promised to preserve clipboard without a desktop clipboard manager.

### Results (automated unless explicitly physical)

1. **PASS:** all 43 previous suite tests retained (version-1 capability expectation corrected to specification); 7 added regressions; **50 tests total**, final run 2.998s, exit 0. PNG decode/pixel equality, exact Sinhala/English/ZWJ MIME bytes, image-capable reader, main-thread image/async-OCR callbacks, local lifetime and no late write after shutdown covered. These headless tests are not desktop paste acceptance.
2. **PASS:** focused native two-process PNG transfer: raw PNG decode and Qt image exactly match fresh per-transfer pixels, then image inserts into reader document. Fresh nonce-derived pixels prevent stale clipboard false positives.
3. **PASS:** focused native two-process UTF-8 transfer: charset bytes, QClipboard.text and actual pasted editor contents exactly match fresh English/Sinhala/ZWJ reference. This is clipboard Unicode coverage, not Sinhala OCR accuracy.
4. **FAIL:** final traced native unmapped/delayed/controller-result cases, both image and text. Prior untraced successes are not used to override these failures. Owner heartbeat continues; local ownsClipboard is sometimes true and sometimes lost. The controller OCR case uses a public mocked recognition result to isolate delivery, clearly separate from actual OCR.
5. **FAIL:** background text retrieval with serial 0; **NOT RUN:** final background-image reader could not obtain focus (raw earlier harness labeled it FAIL; final script now correctly classifies missing reader focus as NOT RUN). These are negative controls, not physical acceptance.
6. **PASS:** canonical native main still registers host `com.dulmina.aisnippingtool`, reports actual `Press <Shift><Control>s`, starts quietly and keeps controller hidden. Three real portal screenshots, fullscreen file equality, rectangle 301×201, local English OCR exact fixture and clean exit/thread cleanup pass again. **FAIL:** corrected separate-reader fullscreen image and OCR-text paste in this synthetic workflow. Overlay selection and Escape were synthetic; physical shortcut/Escape/paste/window selection/tray clicks remain **NOT RUN**. AT-SPI Escape still ineffective; no change attempted.
7. **PASS:** frontend and GNOME backend read-only introspection: both version **1**, both advertise CreateSession, BindShortcuts, ListShortcuts, ConfigureShortcuts. Advertisement is insufficient: official ConfigureShortcuts contract starts at version 2; earlier host UnknownMethod remains evidence of unavailable implementation. Updated manager requires version >=2 and the correct signature, disables the action otherwise, and explains backend support in status/tooltip. A version-2 UnknownMethod/NotImplemented disables further calls in that session. Tests prove unsupported version-1 and repeat calls are not sent. Working shortcut registration and stable shortcut ID unchanged; no live configuration request or GNOME settings change made.
8. **PASS:** source compile/import and staged/unstaged whitespace checks. Initial 49-test experiment printed OK but segfaulted during interpreter teardown with uncleared test MIME; test teardown now explicitly clears its own Clipboard/Selection data before Qt/Python destruction. Subsequent full suites exited 0. This is recorded as a resolved test-harness failure, not omitted or treated as a successful run.

### Git and changed files

Start: clean `fix/phase-01-app-lifecycle`, HEAD `2504a3b`, containing prior `ccdfb6b`. During work an external actor staged source/tests, then created `68e48a6` at 08:27:49 +0530 (`enhance global shortcut configuration support and add clipboard tests`). This agent ran no stage, unstage, commit, reset, clean, checkout, merge or push. Initiating actor remains unidentified. Existing commits/index left intact; working-tree improvements made after that external snapshot remain separate. Recheck status/index before any future action.

Authored this task: `shortcuts/global_shortcut.py`, `ui/shortcut_status.py` (version/capability messages); `tests/test_shortcut_assignment.py` (v1 advertisement/unsupported repeat coverage); `tests/test_clipboard.py` (six MIME/thread/lifetime regressions); `tests/clipboard_native_probe.py` (opt-in two-process public-fixture harness); this acceptance document, handoff, matrix, baseline, and new [clipboard evidence log](phase-01-clipboard-evidence.txt). Some changes were included in the external commit, not committed by this agent. No screenshot, crop, OCR engine, async engine or clipboard helper behavior changed.

### Reproduce and remaining gate

Run the opt-in native probe from a genuine host GNOME terminal: `.venv/bin/python tests/clipboard_native_probe.py`. It opens public test windows, overwrites the session clipboard, uses separate native processes and returns failure for failed positive cases or code 2 for incomplete/focus-unavailable cases. It remaps a maximized test owner to allow ordinary compositor focus/pointer-enter events; this is not a physical key/mouse test or a guarantee of a fresh authorized input serial. The `never_focused` label means its explicit fixture window was never shown, not that the helper anchor cannot receive desktop events. Headless suite: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v`.

Minimum physical test: launch through GNOME's application grid; focus another app; Ctrl+Shift+S → rectangle capture → Ctrl+V in an image-capable app, immediately and after five seconds. Repeat with real Full Screen and an actual selected Window. Capture public English text using Extract Text, focus another app while OCR runs and paste the result; repeat while waiting for OCR before changing focus. Also check real Escape and tray Capture/Quit. Record exactly which workflow fails, whether stale data is pasted, and whether focus timing changes it. No shortcut reconfiguration is needed.

**Phase 1 cannot close.** The confirmed automation delivery race and pending physical acceptance remain blockers; the portal configuration limitation is now handled safely. Do not start Phase 2, AI, PDF or OCR enhancements.

Sources: [Qt QClipboard ownership contract](https://doc.qt.io/qt-6/qclipboard.html), [QTextEdit image MIME support and paste](https://doc.qt.io/qt-6/qtextedit.html), [Qt Wayland selection serial handling](https://raw.githubusercontent.com/qt/qtbase/dev/src/plugins/platforms/wayland/qwaylanddatadevice.cpp), [GlobalShortcuts version-2 ConfigureShortcuts contract](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.GlobalShortcuts.html).

---

## Latest verification — genuine GNOME session, 2026-11-14

This section supersedes earlier current-status statements below. **Phase 1 remains OPEN; Phase 2 must not begin.** Verification only: no production/test source or GNOME settings changed. Native session access was possible through normal D-Bus interfaces, improving on the earlier environment assessment. Physical input was not performed.

### Git safety

Started and rechecked clean on `fix/phase-01-app-lifecycle`, HEAD `ccdfb6b` (`Implement shortcut correction and logging enhancements`). No staged files or pre-existing unstaged changes. Read status, branch, latest eight commits, last twelve reflog entries and both diff stats before documentation edits. Commits `79a7fd9`, `9755ff4`, `ccdfb6b` appeared after the earlier reported `f9858ca`; reflog records commits at 07:34:34, 07:41:23 and 07:49:43 +0530. This agent did not create them; their initiating process remains unidentified. No reset, clean, checkout, unstage, stage, commit, merge or push. Existing history/index preserved.

### Session, identity and automation boundary

- PASS: genuine GNOME Shell 50.1 / Wayland session and session/a11y buses reachable with authorized host access. Agent itself inherits `snap.code.code-7eb1f933-73f2-44ce-84c5-bd8b232bea75.scope`. A direct launch from that scope is not evidence of unsandboxed identity.
- PASS: independently discovered existing canonical app PID 75703 in `app-gnome-com.dulmina.aisnippingtool-75703.scope`; tray reports `Host identity registered: com.dulmina.aisnippingtool`. This establishes genuine GNOME app-launch context, but an actual icon click was not observed.
- PASS: ordinary D-Bus-activated GNOME Terminal Factory0/Terminal0 launch produces children under `app-org.gnome.Terminal.slice/vte-spawn-….scope`, not the Snap scope. Instrumented canonical `main.main()` there successfully registers the same desktop app ID. No cgroup movement, sandbox impersonation or desktop security bypass. Direct `gnome-terminal` CLI initially aborted on missing XSettings `antialiasing`; its normal service interface worked. No settings changed.
- PASS: requested `CTRL+SHIFT+s`; actual portal description **`Press <Shift><Control>s`**, matching Ctrl+Shift+S. Confirmed from live `ShortcutsChanged`, `ListShortcuts` and tray labels. Earlier Ctrl+Alt+S observations remain historical. No shortcut configuration action was invoked in this run and no mapping was reset.
- FAIL — installed backend capability: portal advertises ConfigureShortcuts, but the existing genuine-host app's tooltip records backend `org.freedesktop.DBus.Error.UnknownMethod`: `Method ConfigureShortcuts is not implemented on interface org.freedesktop.portal.GlobalShortcuts`. Host identity no longer blocks that launch, but configuration UI is unavailable in this backend. This was inspected existing state, not a new configuration attempt.
- PASS — accessibility discovery: system GI/Atspi available and Shell tray labels readable. `org.a11y.Status` IsEnabled/ScreenReaderEnabled false, left unchanged. Tray items expose no actionable AT-SPI Action interface. Shell Introspect.GetWindows returns AccessDenied, respected.
- FAIL — AT-SPI synthetic input: generate_keyboard_event(Escape) returned True but the live overlay remained open. API success is not interaction success. Qt QTest synthetic Escape worked. Neither is a physical keypress. No working supported cross-application key/mouse injector was established; no unsafe Shell Eval, X11 interception, uinput or security-setting changes used.

### Acceptance outcomes

Each PASS below names its evidence level; no programmatic event is physical acceptance.

1. **PASS — quiet native startup:** canonical main produced hidden controller and no initial overlay. Visual task-switcher/desktop inspection **NOT RUN**.
2. **PASS — no blank controller in Qt state:** live overlay visible on native Wayland while controller remained hidden. Visual ghost-window inspection **NOT RUN**.
3. **PASS — single-instance guard:** host main probe rejected while the discovered app was running. After normal tray Quit, harness acquired the lock; final test processes exited. Not a long-duration race/stress test.
4. **PASS — portal registration and assigned shortcut:** correct host app ID and actual Ctrl+Shift+S description, rather than preference-only reporting.
5. **NOT RUN — physical Ctrl+Shift+S with another app focused:** no real hardware/compositor shortcut activation observed. Signal/QAction tests do not prove this.
6. **PASS — synthetic native Qt Escape cancellation; NOT RUN — physical Escape.** AT-SPI Escape attempt separately **FAIL**, overlay unchanged until Qt event.
7. **PASS — bounded native repeated workflow:** three real screenshot portal returns (1920×1080), cancellation/fullscreen/rectangle completed without orphan overlay or visible controller. Longer/repeated physical workflow **NOT RUN**.
8. **PASS — programmatic tray protocols/actions:** real StatusNotifier DBusMenu Capture/Quit Events accepted; discovered app exited, later lock acquired. Instrumented main's tray QAction capture and Quit also succeeded. Physical tray clicks **NOT RUN**. Initial DBusMenu Capture reply alone was not treated as proof of image completion.
9. **PASS — fullscreen/rectangle saving with synthetic UI input:** fullscreen PNG bytes match real portal source; rectangle 301×201 saved after Qt synthetic drag. Window Screenshot request **PASS**; actual selected-window capture **NOT RUN**. Same-connection Request.Close returned METHOD_RETURN; waiting coroutine remained pending until shutdown, as Close emits no Response by contract. Shutdown canceled it cleanly; not a user-cancel-response test.
10. **FAIL — automated native cross-process screenshot paste:** active second native Qt app received no matching image through clipboard/read/paste after capture. Physical Ctrl+V **NOT RUN**. Synthetic producer interaction may affect compositor focus/selection; root cause not established.
11. **PASS — existing local English OCR fixture:** exact `Offline English screenshot test 123.` from generated public image via existing OCR subprocess, with local trained data, no new download/engine. **FAIL — automated native cross-process OCR text paste.** Physical text paste **NOT RUN**. Control diagnostic using the unchanged helper from a focused visible producer **PASS**, including cross-process native text paste. Concurrent/inactive producer diagnostic failed first; repeated alone with producer/consumer active passed. This narrows, but does not prove, an application lifecycle/focus defect. One English fixture is not a Sinhala/mixed accuracy benchmark.
12. **PASS — installed entry point/context:** existing genuine GNOME app process executes checkout `.venv/bin/python .../main.py` under correct desktop app scope. Physical app-grid icon click **NOT RUN**; no launcher/settings edits made.
13. **PASS — host identity; FAIL — Snap-inherited launch compatibility:** genuine host registration succeeds. Earlier Registry `io.snapcraft` rejection remains valid for Snap scope; do not label it harmless or spoof identity. Backend ConfigureShortcuts incompatibility remains separately reported above.
14. **PASS — clean shutdown:** canonical instrumented main exit 0, shortcut thread stopped (21.26 seconds total workflow). Separate pending-window-request shutdown also exit 0/thread stopped. Final process query found no matching test-app interpreter process. Physical tray-Quit click **NOT RUN**.
15. **PASS — regression suite:** 43 tests in 2.814s. Source compileall and staged/unstaged whitespace checks exit 0. Offscreen warnings in retained output do not establish native regressions.

### Evidence, limitations and next acceptance gate

[Retained command/result evidence](phase-01-gnome-evidence.txt) contains live ledger, logs, focused clipboard diagnostic, window-request cancellation and regression output. Temporary instrumentation invoked canonical main and wrapped functions in memory only; Qt widgets/clipboard stayed on its GUI thread. Capture output redirected in memory to `/tmp/snipping-native-output/`; native desktop screenshots remain local there and were not copied into Git or uploaded. Temporary scripts are under `/tmp/snipping-*.py` and are ephemeral. Clipboard was exercised with images/public English text; previous clipboard contents were not preserved. Normal tray Quit stopped the discovered app; no test app was left running.

Supported-interface references: [GNOME Terminal D-Bus API](https://raw.githubusercontent.com/GNOME/gnome-terminal/master/src/org.gnome.Terminal.xml), [AT-SPI device-controller Wayland limitations](https://gnome.pages.gitlab.gnome.org/at-spi2-core/devel-docs/de-controller.html), [Request.Close contract: no Response emitted](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.Request.html).

Minimum remaining manual check (no configuration changes):

1. Press Super, search **AI Snipping Tool**, open its app-grid icon. Confirm no blank window; read assigned Ctrl+Shift+S and registered host identity in its tray menu.
2. Focus another app, physically press **Ctrl+Shift+S**, then **Esc**. Repeat once; confirm only the overlay appears and closes. Use real tray Capture once.
3. Capture a rectangle, paste with **Ctrl+V** into another image-capable app immediately and after five seconds. Also test Full Screen and choose a real Window in GNOME's picker. Record image presence/dimensions.
4. Display the public English line above, capture it in Extract Text mode, paste into an external editor and compare. Click real tray Quit; verify exit within five seconds.

Do not mark these physical steps PASS until observed/reported. Clipboard workflow failures and pending physical activation/paste/window/tray acceptance block Phase 1 closure. Configuration UI incompatibility remains a known host issue. Investigate clipboard focus/selection with genuine input before deciding on a production fix. No Phase 2, AI, OCR improvement or PDF work started.

---

Latest status: shortcut request/reporting corrections are implemented; **43 automated tests PASS**. Requested `CTRL+SHIFT+s`, observed assignment Ctrl+Alt+S. Host app-grid identity and physical acceptance remain unverified. See the final shortcut update below.

# Phase 1 acceptance verification — 2026-11-14

**Decision: Phase 1 cannot close; Phase 2 must not begin.** Verification only; no production/test source changed in this run. Real keyboard, mouse/tray and cross-application paste require user interaction. This session has no native desktop controls; no synthetic keypress or tray action was counted as physical acceptance.

## Git safety and provenance

Initial and pre-documentation state:

- Branch `fix/phase-01-app-lifecycle`; HEAD `f9858cae5ed95bb22a2310edadc858ec3c4eba34`.
- Two unstaged files: `docs/phase-01-command-log.txt` (five appended lines), `test_global_shortcut.py` (import/call to `prepare_qt_environment`). Both match the prior turn's final additions and are preserved byte-for-byte.
- No staged files. Unstaged diff: 7 insertions, 1 deletion. No initial untracked files.
- Seven Phase 1 commits since `24d741c`: `eb6b625`, `072d0bd`, `a739762`, `89387d5`, `236bf76`, `1e9ca1b`, `f9858ca`. Reflog records normal commits from 07:14:47 to 07:27:46 on November 14, 2026, Asia/Colombo. No new HEAD movement occurred during the verification before documentation.
- HEAD author/committer metadata names the repository owner; this is not proof of the person/process that created a commit. Prior agent tool history contains no commit/stage commands for these commits. The initiating process remains **unidentified**.
- `core.hooksPath` has no configured value; `.git/hooks` contains only sample hooks. These checks do not identify an automatic committer. No global hooks/configuration changed.
- Executed no reset, clean, checkout/switch, unstage, stage, commit, merge or push command. No branch created. Existing index left untouched.

Required read-only commands executed: `git status --short`, `git branch --show-current`, `git log -8 --oneline --decorate`, `git reflog -12 --date=iso`, `git diff --stat`, `git diff --cached --stat`. Also read the exact two-file diff, HEAD metadata and relevant source/docs. Before writing documentation, `git diff --check` and `git diff --cached --check` passed.

Preserved starting-file SHA-256:

- `docs/phase-01-command-log.txt`: `cfc0fa519cbfb0f0dbccd4b690a4f8b015d80f505d68358573228b921f40523e`
- `test_global_shortcut.py`: `ba2bf16b7ca518fa50d5d551174251b839e819b797444013d4b7f5e781aeb78e`

## Acceptance results

| User test | Result | Evidence and limits |
|---|---|---|
| 1. Quiet main.py startup | PASS — runtime state | Native `main.main()` on Qt Wayland: no visible top-level widgets, hidden controller, no startup overlay. Visual inspection NOT RUN. |
| 2. No unwanted blank controller window | NOT RUN — visual | Qt reports `CONTROLLER_VISIBLE=False` and no visible top-level widget. No native screen/task-switcher observation available. |
| 3. Exactly one background instance | PASS — bounded live check | Before launcher test: zero. During GIO desktop launch: exactly one actual `.venv/bin/python .../main.py` process. A second launch in canonical main probe rejected by lock. After own-process SIGTERM: zero. |
| 4. Global shortcut registration | PASS — registration only | Actual BindShortcuts response returned `open_capture_menu`. Assigned description is **Press <Control><Alt>s**, not the requested Ctrl+Shift+S. Correct assignment therefore FAIL. |
| 5. Physical Ctrl+Shift+S while another app focused | NOT RUN | No physical key input. Returned assignment mismatch is independently confirmed; app success signal misleadingly reports preferred Ctrl+Shift+S. |
| 6. Physical Escape closes overlay | NOT RUN | No real overlay opened in this verification. Synthetic lifecycle test remains separate automated evidence. |
| 7. Repeated real captures without freeze/orphans | NOT RUN | Automated repeat-activation/heartbeat/cleanup checks pass; no real captures made. |
| 8. Tray Capture and Quit by physical clicks | NOT RUN | Qt reports tray available. Programmatic Quit QAction in live probe exits main cleanly and joins shortcut thread; no physical tray click. |
| 9. Fullscreen/rectangle/window captures | NOT RUN | No screenshot portal request or real mouse selection issued. Existing automated lifecycle tests are not capture-image proof. |
| 10. Screenshot paste into another app | NOT RUN | Desktop clipboard untouched by live probes. Headless tests use isolated clipboard only. |
| 11. English OCR paste into another app | NOT RUN | No actual cross-application paste. Existing backend/isolated results do not prove ownership on Wayland. |
| 12. Desktop launcher targets main.py | PASS — GIO execution | Installed entry validates; actual GIO launch starts the exact checkout `.venv/bin/python` and `main.py`. Physical GNOME app-grid activation NOT RUN. |
| 13. Registry warning harmless? | FAIL — compatibility/identity in tested context | Detailed reply rejects manual host registration because portal classifies caller as `io.snapcraft`. Both diagnostic and GIO-launched process inherit Snap VS Code scope. Not harmless for host identity; registration success alone does not establish correct app attribution. |

## Live evidence and Registry diagnosis

The instrumentation patched methods **in memory only**, then invoked canonical `main.main()` for ten seconds. It logged the Registry reply and real BindShortcuts result, counted GUI heartbeats and programmatically triggered the existing Quit QAction. It requested no capture, changed no clipboard contents, and touched no pre-existing user process.

```text
PROBE_PID: 55836
PLATFORM: wayland
CONTROLLER_VISIBLE: False
STARTUP_OVERLAY: False
VISIBLE_TOP_LEVEL_TYPES: []
TRAY_AVAILABLE: True
SECOND_INSTANCE_EXIT: 0 AI Snipping Tool is already running, or its runtime lock is unavailable.
REGISTRY_REPLY: ERROR org.freedesktop.portal.Error.Failed ["Could not register app ID: Can't manually register a io.snapcraft application"]
BOUND_SHORTCUTS: [('open_capture_menu', {'description': 'Open AI Snipping Tool capture menu', 'trigger_description': 'Press <Control><Alt>s'})]
REGISTRATION_PASS: <Ctrl><Shift>S
MAIN_EXIT: 0
HEARTBEATS: 98
SHORTCUT_THREAD_ALIVE: False
```

Caller cgroup: `/user.slice/user-1000.slice/user@1000.service/app.slice/snap.code.code-7eb1f933-73f2-44ce-84c5-bd8b232bea75.scope`.

A separate installed-launcher test ran `gio launch ~/.local/share/applications/com.dulmina.aisnippingtool.desktop`, observed PID 56767 with exactly the expected interpreter/main.py arguments, waited three seconds, then sent SIGTERM **only to that newly launched test instance**. GIO exited 0; process count was zero/one/zero before/during/after. It inherited the same Snap scope and emitted the same Registry warning. This GIO invocation is not evidence of a genuine GNOME app-grid launch in an independent host context.

The [official Registry contract](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.host.portal.Registry.html) excludes callers identified as sandboxed. That matches the detailed live rejection. The tested environment cannot establish `com.dulmina.aisnippingtool` through the host Registry call. Whether a normal app-grid launch outside the Snap editor context resolves this is **NOT RUN**, not a claimed fix. Do not bypass the portal's sandbox classification or suppress the warning as harmless.

The [GlobalShortcuts contract](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.GlobalShortcuts.html) distinguishes the optional preferred trigger from returned `trigger_description`, which the client should present. Source currently emits `self.preferred_trigger` after checking only the shortcut ID and uses a hardcoded tray tooltip. This explains the false success label; it does not explain why the portal chose Ctrl+Alt+S.

Also, `PREFERRED_TRIGGER='<Ctrl><Shift>S'` does not follow the referenced [XDG shortcuts syntax](https://specifications.freedesktop.org/shortcuts/latest/), which uses forms such as `CTRL+SHIFT+s`. This is a source-level compatibility defect to address in Phase 1. It is not proven to be the cause of the current assignment; a remembered user choice or desktop handling could also matter. No bindings/settings were changed by this verification.

## Automated regression evidence

Command: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v`.

Result: **PASS, 20 tests in 2.662 seconds**. Full current output saved temporarily at `/tmp/snipping-phase01-acceptance-tests.txt`. This includes simulated denial/delay, lifecycle routing, duplicate process startup, worker shutdown and main-thread delivery checks, not physical acceptance. No new source changes were made or needed for this run.

Live commands: `.venv/bin/python /tmp/snipping-phase01-verify.py` and `.venv/bin/python /tmp/snipping-launcher-verify.py`, each with authorized session-bus/Wayland access. Temporary probe scripts contain instrumentation/process checks only and were not added to the repository. `desktop-file-validate ~/.local/share/applications/com.dulmina.aisnippingtool.desktop` passed. No screenshots or private documents were inspected/uploaded.

## Manual instructions and closure gate

1. Start from GNOME's application grid, **not the embedded Snap VS Code terminal**. Use the installed AI Snipping Tool entry; do not reinstall or edit it for this test. Confirm no initial overlay or blank controller/task-switcher entry and one background instance. This independent launch context must still be verified.
2. With another app focused, physically press **Ctrl+Shift+S**. Record whether the overlay opens. Current diagnostic portal assignment was Ctrl+Alt+S; optionally test that only as a diagnostic and record it separately, never as a pass for Ctrl+Shift+S. Follow any portal permission/configuration dialog; do not bypass it.
3. If activation succeeds, press **Esc** and verify clean cancellation; repeat ten times, alternating Esc and completed rectangle captures. Inspect task-switcher/windows and responsiveness for each repetition.
4. From the real tray, click Capture. Use Rectangle, Full Screen, then Window; choose a window through the compositor portal. Compare saved PNG contents to selections. Do not delete or overwrite existing screenshots during testing; the known same-second naming defect remains.
5. Paste an image into another GUI app using Ctrl+V immediately and again after five seconds. Confirm real image pixels/dimensions. Choose Extract Text on a public English fixture (for example `Offline English screenshot test 123.`), then paste the text into a text editor and compare to the reference.
6. Click tray Quit. Confirm app process exits within five seconds; restart via the app grid and repeat. Report each outcome; all physical rows above remain NOT RUN until observed or user-confirmed.

Before closure: resolve truthful assigned-trigger reporting and preference syntax; verify correct identity in the real launch context or handle unsupported Registry registration appropriately; complete the physical acceptance rows. Existing OCR quality/offline model-download/dependency risks and filename/geometry bugs remain documented, not fixed here. No Phase 2, AI or unrelated work is authorized by this report.

## Shortcut correction update — 2026-11-14

This update supersedes the earlier **code defects** in preference syntax and truthful assignment reporting. The historical physical-acceptance rows above remain NOT RUN. **Phase 1 is still not ready to close; Phase 2 has not started.**

### Git and scope

Started on `fix/phase-01-app-lifecycle` at `79a7fd9`, an external commit after the previously reported `f9858ca`. The starting index/worktree were clean. External `9755ff4` appeared while implementing this change; it was preserved. No branch switch, reset/clean, stage/unstage, commit, merge or push command was performed by this agent. Recheck Git before further work; commit metadata does not identify the external initiating process.

Only shortcut protocol/presentation/tests/docs changed. Capture, clipboard, OCR recognition, PDF, Freeform and AI code were not modified. No dependencies added.

### Implemented behavior

- Preferred request is **`CTRL+SHIFT+s`**, using the specification's uppercase modifier names and lowercase base keysym `s`; stable shortcut ID remains **`open_capture_menu`**. See the [XDG shortcuts specification](https://specifications.freedesktop.org/shortcuts/latest/).
- Read remembered shortcuts with ListShortcuts before binding. If the stable shortcut already exists, omit a preferred-trigger replacement; do not override the user's remembered choice. Bind once for the session, read the returned `trigger_description`, and verify with ListShortcuts afterwards.
- Emit the **actual desktop description** on successful registration. Tray Capture label, tray tooltip and status text show requested and assigned values separately. Recognizable different assignments produce an understandable warning. Localized/unrecognized descriptions remain verbatim, with an explicit comparison/verification cue rather than a guessed match.
- Subscribe to ShortcutsChanged, scope updates to the current session, update display/state immediately and refresh with ListShortcuts. Ignore stale List responses when a newer change signal has arrived. Missing descriptions never fall back to the requested key; unbound state removes the activation claim.
- Log requested/actual values separately. Canonical startup enables INFO diagnostics, without logging screenshots/documents/OCR results. Presentation uses QObject slots on Qt's main thread.
- Offer **Configure Shortcut…** in the tray only when the exact ConfigureShortcuts method/signature is advertised **and host identity was registered successfully**. It runs only after an explicit user click. No startup configuration dialog, resets or repeated rebinds. Changes are read back through ListShortcuts/ShortcutsChanged. Unsupported/error responses remain visible and UnknownMethod/NotImplemented disables the action.
- Installed portal reports **GlobalShortcuts version 1** yet advertises `ConfigureShortcuts(osa{sv})`. Capability detection therefore uses the method/signature, not only a version-number assumption. Official docs introduce this method in version 2; live dialog behavior on this installation remains unverified. See the [GlobalShortcuts contract](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.GlobalShortcuts.html).
- dbus-next 0.2.3 failed while parsing an unrelated `power-saver-enabled` property in the full portal introspection. Inspecting just the needed method in raw Introspect XML fixes capability detection without changing that dependency.
- Registry Register uses `com.dulmina.aisnippingtool` and remains the first portal operation on the same D-Bus connection subsequently used for GlobalShortcuts. Errors retain the detailed portal reply and are shown with launch-context guidance. Failed identity blocks configuration of an uncertain application. No Snap identity bypass, spoofing, cgroup manipulation or environment sanitization was attempted. The installed desktop entry still targets canonical main.py; no launcher change was necessary here.

### Current observed result

**Requested:** `CTRL+SHIFT+s` (Ctrl+Shift+S).

**Assigned on this session:** `Press <Control><Alt>s` (Ctrl+Alt+S), preserved as the existing choice. Both BindShortcuts and the ListShortcuts-backed state agree. The tray displays **Capture (Press <Control><Alt>s)** and a different-assignment warning. Correct display is PASS; the desired Ctrl+Shift+S assignment/physical behavior is **not** declared PASS.

**Identity:** Registry still rejects this Snap VS Code-inherited process with `Can't manually register a io.snapcraft application`. The application displays this error accurately and disables configuration even though the method is advertised. Genuine unsandboxed host registration has not been observed. The [Registry contract](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.host.portal.Registry.html) excludes callers identified as sandboxed.

**Live Wayland smoke:** hidden controller, no startup overlay, duplicate launch rejected, 104 GUI heartbeats, clean programmatic Quit, no remaining shortcut thread. No screenshots, physical keys or configuration changes were performed.

**Automated:** **PASS — 43 tests**, including all 20 previous Phase 1 regressions. Syntax/import compilation, existing menu smoke/cancellation and both whitespace checks PASS. New cases cover syntax/ID, Bind/List parsing, actual GUI display/mismatch, localized/missing descriptions, ShortcutsChanged/session filtering/stale responses, remembered choices, Registry ordering/errors, portal version/backport/signature compatibility, explicit configuration/errors and clean cancellation/shutdown. Exact outputs: [phase-01-shortcut-log.txt](phase-01-shortcut-log.txt).

**Manual:** genuine GNOME application-grid identity, physical Ctrl+Shift+S/Esc, repeated captures, tray clicks, ConfigureShortcuts dialog/confirmation and external image/English-text paste are **NOT RUN** unless a subsequent user report confirms them.

### Exact manual acceptance procedure for the updated app

1. Quit any existing instance using its tray **Quit**. Press **Super** to open GNOME Activities, open **Show Apps** if necessary, search **AI Snipping Tool**, and click its application icon. Do not start it from VS Code's integrated terminal, and do not count `gio launch` invoked there as an independent host launch.
2. Open the app's tray menu and read both the shortcut and identity status. Expect `Host identity registered: com.dulmina.aisnippingtool` for a verified host connection. If identity remains unregistered, copy the exact error and stop shortcut-configuration acceptance; do not bypass the sandbox or reset GNOME settings. Confirm no blank controller/task-switcher window.
3. Read the **assigned** key. If it differs from Ctrl+Shift+S and **Configure Shortcut…** is enabled, explicitly click that action. In the GNOME dialog, select the capture action, choose Ctrl+Shift+S and confirm it. Resolve any conflict through the dialog or cancel. Existing settings must remain untouched unless you confirm a change. Confirm the app's displayed assignment updates. If unavailable or rejected, record the status/error; the configuration test remains NOT RUN/FAIL as appropriate.
4. Focus a different GUI application. Physically press **Ctrl+Shift+S**. Only the selection overlay should appear. If a different key is still assigned, record that difference; testing Ctrl+Alt+S is only a separate diagnostic, never a pass for the requested key. Press **Esc**; verify no error or blank window. Repeat ten times, alternating cancellation and completed rectangle captures.
5. Use real tray **Capture**; test Rectangle, Full Screen and Window through the toolbar/portal. Paste each image into another GUI app with **Ctrl+V**, immediately and after waiting five seconds. Compare actual pixels/dimensions. Keep captures at least two seconds apart while the previously documented filename collision remains unresolved.
6. Capture a public English line, e.g. `Offline English screenshot test 123.`, with **Extract Text** selected. Paste into another text editor and compare with that exact reference. Do not send private screenshots/text to logs or chat.
7. Click tray **Quit**. Confirm the launched process exits within five seconds, then reopen through the application grid and repeat activation. Record PASS/FAIL for every step and the requested/assigned/identity text. Until reported/observed, physical rows stay NOT RUN.

Remaining Phase 1 blockers: independent host identity verification, any portal/backend limitation discovered in the explicit configuration dialog, desired assignment confirmation and all outstanding physical acceptance. No Phase 2 work is authorized by this update.
