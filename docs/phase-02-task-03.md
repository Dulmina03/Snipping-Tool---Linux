# Phase 2 Task 3 — Capture performance and long-run stability

## Baseline recorded before production changes — 2026-11-14

User confirms Phase 1 accepted, Task 1 all six physical tests PASS and Task 2 all seven physical tests PASS on one monitor at 100%. Mixed-monitor and actual fractional-scaling acceptance remains pending. Only Task 3 is authorized here.

Started clean at `b9d5995` on `main`: reflog showed an external fast-forward from the Phase 2 branch. Safely returned to existing `fix/phase-02-capture-reliability`, which pointed to the identical commit. No history or index changes.

Baseline command: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v`: **132 PASS, 8.628s, exit 0**. Benchmark command: `QT_QPA_PLATFORM=offscreen .venv/bin/python tests/capture_performance_probe.py /tmp/snipping-task03-before.json`. Raw aggregate observations are preserved in [phase-02-task-03-before.json](phase-02-task-03-before.json).

Public seeded-noise 1600×900 PNG, Rectangle 1200×700, three warmups then 50 alternating Rectangle/Full Screen operations using the actual controller and clipboard helpers, isolated offscreen QApplication. No screenshot contents or extracted text logged. Monotonic timings, nearest-rank p95; 25 samples per save mode, 50 for delivery. Toast rendering excluded; portal is a controlled asynchronous fixture, not GNOME performance or permission timing.

- Activation to overlay show returned: median 54.378 ms, p95 113.332 ms. This does not measure a physical global key or compositor presentation.
- Fixture portal wait: median 28.125 ms, p95 33.964 ms (requested delay 10 ms plus Qt/async scheduling and fixture copy).
- Rectangle decode/crop/save combined: median 250.928 ms, p95 279.198 ms. Nested PNG save: median 197.856 ms, p95 221.581 ms. Do not sum overlapping measurements.
- Full Screen encoded-file copy: median 2.846 ms, p95 3.510 ms.
- Clipboard publishing, including image decode and PNG MIME encoding: median 235.342 ms, p95 323.975 ms.
- Selection to delivery: median 370.255 ms, p95 464.674 ms.
- Overlay close: median 0.151 ms, p95 0.177 ms; this times close scheduling, not compositor presentation/deferred deletion.
- Real existing English OCR subprocess, public fixture, three samples: median 2140.262 ms, max 2210.164 ms. Sample count insufficient for meaningful tail latency; no OCR algorithm change planned.
- Qt 1 ms heartbeat maximum gap: **514.882 ms**. Confirmed synchronous decode/crop/PNG save blocks the GUI, followed by GUI clipboard encoding. Portal wait and OCR are already asynchronous.
- RSS after warmup/10/50 captures: 114312/104792/104988 KiB; nine file descriptors throughout, two threads. No monotonic leak demonstrated. After shutdown six descriptors, two threads; allocator RSS is not equivalent to live-object ownership.

Targeted plan supported by these measurements: move only Pillow/file work to a bounded off-GUI job, retain GUI mapping snapshots and all Qt pixmap/clipboard operations on the GUI thread. Drain a cancelled file operation before allowing another capture or closing its executor; never publish its late result. Preserve saved files, atomic filename publication and real focused overlay through clipboard delivery. Do not rewrite clipboard/OCR/portal/toolbar/shortcut components to chase arbitrary speed targets.

Verification and after measurements will follow below.

## Confirmed problems and focused changes

1. Rectangle PNG decoding/cropping/encoding blocked the GUI for about 251 ms median, before clipboard work. Production Rectangle and Full Screen saves now use `AsyncJobs.run_file`, backed by one lazily started file thread. The controller freezes Qt geometry/mapping and plain coordinates on the GUI thread first. No QWidget, QPixmap or clipboard API is passed to that worker. Pillow crop buffers are explicitly closed.
2. Saved PNGs were decoded and encoded again solely for clipboard MIME publication. `copy_image_to_clipboard` now reads one byte snapshot, validates it with QImage on the GUI thread, and reuses the original PNG bytes for `image/png` and `image/x-png`. Qt image data, standard Clipboard mode, focus checks and persistent QApplication ownership remain intact. Other file formats and in-memory images retain PNG encoding. Invalid inputs do not replace existing clipboard data. No OCR recognition algorithm changed.
3. An explicit controller operation guard rejects duplicate mode callbacks as well as repeated activation. The legacy entry now rejects busy work before clearing current results or disabling controls.
4. Cancelling a file job closes the overlay promptly, but the controller remains busy until the single running write drains. Its late result never reaches OCR or the clipboard. Source cleanup waits for the worker; retries cannot read/delete a source still in use. Shutdown joins the worker. If atomic publication already completed when cancelled, the valid saved screenshot is preserved, not deleted. OS disk operations cannot be forcibly interrupted safely; shutdown can still wait for slow storage.
5. Opt-in `SNIPPING_DIAGNOSTICS=1` emits monotonic duration records for portal requests, overlay preparation, decode/crop/save, PNG encode/publication, clipboard delivery, OCR and overlay-close scheduling. Records contain operation names and durations, not pixels or recognized text. Existing opt-in source/path diagnostics remain local. Portal totals explicitly include registration and any user dialog: they are not CPU time. The portal does not expose a separate duration for human consent, so that portion has not been independently measured. Async preparation timing begins when its coroutine runs, not at physical key depression or compositor presentation.

The first executor implementation using cross-thread asyncio future completion stalled in the new active-shutdown test. A standalone executor diagnostic also stalled on this environment. That implementation was replaced by a 10 ms cooperative check of a single concurrent future; cancellation drains it and consumes errors before returning. Final shutdown tests pass. This is an observed compatibility failure, not a claimed diagnosis of Python/Qt internals or a reason to change runtimes.

No leak was demonstrated in the original 50-capture baseline, so no cache purge or normal clipboard clearing was introduced. Window's existing asynchronous portal request/GUI restoration and OCR's cancellable process group remain unchanged. Its small synchronous encoded-file copy was measured but not rewritten. Toolbar, shortcut, tray, filename collision algorithm, default directory and display-mapping algorithms are preserved.

## Before and after — repeatable public fixtures

Final command: `QT_QPA_PLATFORM=offscreen .venv/bin/python tests/capture_performance_probe.py /tmp/snipping-task03-after-png-reuse.json`, **PASS, exit 0**. Same fixture/workload and three warmups as baseline; 50 captures, 25 per mode. [Final aggregates](phase-02-task-03-after.json). These are single-run observations on this machine, not guaranteed latency targets.

Median / nearest-rank p95, milliseconds, before → after:

- Activation to overlay show returned: **54.378 / 113.332 → 55.125 / 112.336**. No meaningful startup improvement claimed.
- Controlled fixture portal wait: **28.125 / 33.964 → 32.665 / 34.006**. Synthetic delay and event-loop scheduling only; native GNOME/permission latency NOT RUN.
- Rectangle decode/crop/save: **250.928 / 279.198 → 248.359 / 261.921**, now on the file worker. CPU cost is essentially unchanged; GUI responsiveness is the benefit. Nested PNG encode/save: **197.856 / 221.581 → 191.926 / 200.950**. Do not add nested totals.
- Full Screen encoded-file copy: **2.846 / 3.510 → 6.175 / 6.953**. The new worker scheduling also adds latency not included in the function's copy duration; this is not a copy-speed improvement.
- GUI clipboard publishing: **235.342 / 323.975 → 47.110 / 67.090**. PNG reuse removes redundant encoding; validation and publishing still run on the GUI thread.
- Alternating selection to clipboard delivery: **370.255 / 464.674 → 190.597 / 315.705**. Mixed-mode median reflects both Full Screen and Rectangle; it is not the median for either mode individually.
- Overlay close scheduling: **0.151 / 0.177 → 0.221 / 0.281**. Deferred deletion is explicitly drained during each test cycle; native compositor frame disappearance is not measured.
- Qt heartbeat maximum gap: **514.882 → 76.901 ms**; normal heartbeat median **1.143 → 1.144 ms**. Controlled slow-worker regression independently confirms Qt events and cancellation continue during saving. QPixmap/QImage decode and clipboard publication still have GUI costs; larger images may take longer.
- Real English OCR, three public-fixture executions: median **2140.262 → 1900.179 ms**, maximum **2210.164 → 1950.592 ms**. Too few samples for a meaningful tail percentile. No engine change or causal OCR speedup is claimed; Sinhala recognition accuracy is not measured here.

An intermediate worker-only isolated run had selection/delivery median **419.910 ms**, maximum heartbeat **522.951 ms**: moving saving alone did not solve expensive GUI clipboard encoding. Preserved in [worker-only observations](phase-02-task-03-worker-only.json). An earlier run overlapped regressions and was excluded from the final comparison; no cherry-picked claim is made from that loaded run.

## Resource observations

Final warmup / 10 / 50 captures: RSS **122976 / 128836 / 126588 KiB**; file descriptors **14 / 14 / 14**; native threads **8 / 8 / 8**. Python threads were exactly MainThread plus one `snipping-file_0`. After close, MainThread only remained among Python threads; the owned worker joined, three loop descriptors closed. Qt's QDBusConnection and five native pooled threads remained until process exit. The benchmark process exited normally. Increased allocator/Qt-pool RSS versus baseline is acknowledged; no unbounded growth over this 50-capture interval was demonstrated. This is not an hours-long or arbitrary-resolution leak proof.

Each completed run preserved 53 distinct valid PNGs (three warmups +50 measured captures), zero staging files and no outstanding asyncio tasks. Existing 100-operation pixel/clipboard regression also passes. Tests clear only their own offscreen clipboard at teardown to avoid the previously documented Qt plugin teardown defect; production cleanup does not clear the clipboard.

## Verification outcomes

- **PASS — 145 automated regressions, 17.455s, exit 0**, using `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v`. All previous 132 retained; 11 new stability tests and two clipboard byte-snapshot/fallback tests. Existing delivery/mapping/lifecycle tests now await asynchronous saves and assert that clipboard publication precedes surface teardown. An obsolete assertion that expected the reverse was corrected.
- **PASS — simulated production long runs:** 100 consecutive screenshots; ten Unicode OCR callbacks; 50 rapid launch/cancel cycles; 20 Window backend success/cancel cycles; repeated failed/timeout portal responses, repeated activation and duplicate mode requests; failure/retry; worker cancellation including repeated cancel and late worker failure; idle and active shutdown. Actual small PNG pixels/Qt MIME readback are checked; no mocked-result-only success claim.
- **PASS — real OCR subprocess control:** public English fixture recognized; existing error/cancellation/process-group reaping regressions pass. Controlled Unicode delivery contains Sinhala combining marks, punctuation and ZWJ. That tests transfer, not Sinhala recognition accuracy.
- **PASS — syntax/import:** `.venv/bin/python -m compileall -q main.py ui capture utils shortcuts tests`; `QT_QPA_PLATFORM=offscreen .venv/bin/python -c 'import ui.capture_menu, capture.screenshot_portal_request, utils.async_jobs, utils.screenshot_files, utils.clipboard'`.
- **PASS — whitespace:** `git diff --check` and `git diff --cached --check`.
- **PASS — read-only native session inventory:** GNOME Shell **50.1**, Screenshot portal **v2**. Agent inherits Snap VS Code scope; no identity spoofing or settings change. One existing user `main.py` process observed (PID 30510), left untouched. This does not prove it is executing the changed source loaded after restart.
- **NOT RUN — fresh native/global-key timing, actual portal interaction/permission latency, newly changed-path external cross-process image/text retrieval, physical Alt+Shift+S/Escape/tray, physical Window picker or multi-monitor/fractional-scale checks.** Offscreen clipboard equality is not external paste. Prior user acceptance remains valid for its tested version/configuration, not automatic sign-off on this change.

Development failures recorded: the initial asynchronous-save run had four failures/two errors from synchronous assertions; the retained tests were updated to wait inside their mocks. The first new active-worker shutdown test hung and was stopped; a timed stack diagnostic reproduced it. A subsequent diagnostic wrapper itself errored when scheduling a timer on an already closed loop during teardown. Those temporary diagnostics are not production fixes or final PASS results. Final regression and benchmark processes exit 0.

## Minimum physical acceptance — pending

1. Quit the existing instance through the tray, then relaunch **AI Snipping Tool from GNOME's app grid**. Focus another app, press the actually assigned Alt+Shift+S and verify one overlay. Select a public rectangle (also reverse-drag from a corner), paste into another app immediately and after switching focus. Repeat Full Screen.
2. Alternate Screenshot and Extract Text on public English content, externally paste each fresh result. Escape during selection and during OCR, then capture again. Verify no stale clipboard replacement from cancelled work and no freeze. Include one completed Window capture and one cancelled GNOME picker.
3. Across **20–50 total operations**, include rapid repeated shortcut activation while busy. Expect one capture session, distinct preserved files, usable controls and no accumulating windows. Quit both idle and once during an active operation, then relaunch; expect no remaining app/OCR/file worker. Do not intentionally corrupt or fill the real screenshot directory.

Record capture mode, resolution/scale and outcome. Mixed-monitor and actual GNOME fractional-scaling acceptance remains pending from Task 2; do not claim it here. Task 3 is implemented/automated-tested, **not physically accepted**. No Freeform, further task or AI work is authorized by this report.

## Modified files and provenance

Production files:

- `ui/capture_menu.py`: GUI geometry snapshots, async file jobs, duplicate-operation guard, busy-safe legacy entry, source lifetime and duration hooks.
- `utils/async_jobs.py`: single-worker execution, cancellation drain and joined shutdown.
- `utils/clipboard.py`: validate one file snapshot, reuse complete PNG MIME bytes; same GUI ownership and other-input fallback.
- `utils/capture_diagnostics.py`: reusable opt-in monotonic timing decorator.
- `utils/screenshot_files.py`: PNG publication duration hook only; atomic collision handling unchanged.
- `capture/screenshot_portal_request.py`: inclusive request duration hook only; identity/options/security/lifecycle unchanged.

Tests: `tests/capture_performance_probe.py`, `tests/test_capture_stability.py`, `tests/test_clipboard.py`, `tests/test_capture_delivery.py`, `tests/test_display_mapping.py`, `tests/test_phase01.py`.

Documentation: this report, `docs/phase-02-task-03-before.json`, `docs/phase-02-task-03-worker-only.json`, `docs/phase-02-task-03-after.json`, `docs/handoff-summary.md`, `docs/test-matrix.md`, and the new single-monitor acceptance note in `docs/phase-02-task-02.md`.

External commits **50359dd**, **5dd0de0** and **88848d5** appeared during work and contain the baseline, initial implementation, and subsequent stability/PNG changes. Final observed HEAD is `88848d5`; remaining edits are documentation/evidence only and the index is empty. They were preserved. The agent switched only from clean main to the existing identical Phase 2 branch; it did not stage, commit, merge, reset, clean or push. Recheck HEAD/index before further work because external updates have occurred repeatedly.
