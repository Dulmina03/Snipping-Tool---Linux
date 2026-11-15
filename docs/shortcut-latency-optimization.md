# Shortcut-to-capture latency optimization

2026-11-15, Ubuntu26.04 GNOME Wayland. **Implemented and measured; physical keyboard/visual acceptance remains NOT RUN for this change.** Stage2's user-accepted startup/capture baseline remains recorded. Stage3.1 clean-install testing is postponed by user request; the existing .deb was neither rebuilt nor installed.

## Result — native, serialized production-path comparison

Final comparison uses the same production controller, mapping, Screenshot portal and Qt overlays, with the same Qt application/desktop identity as main.py. A programmatically injected valid local shortcut-manager signal starts each capture; **no physical keypress is claimed**. The Screenshot requests and Wayland surfaces are genuine. Every activation obtains a fresh screenshot; no cached desktop, continuous pre-capture or early visible overlay.

Warm samples:20 per version, after recording one separate first activation in each process. Durations are from injected Activated-handler entry to the named checkpoint, in milliseconds; median / nearest-rank p95:

- Callback dispatched: **0.348 /0.540 → 0.305 /0.517**. Shortcut routing was already fast.
- Toolbar Show event: **910.143 /921.455 → 672.385 /712.960**.
- Toolbar's first Qt paint fully processed: **951.031 /978.102 → 716.659 /756.614**. Median improves **234.372ms (24.6%)**; observed p95 improves221.488ms (22.6%). This is the primary comparison, available for every sample.
- Focused, enabled controls after paint: **979.419 /1015.129 → 744.127 /781.604**, **19/20 samples per version**. One programmatic activation per version did not establish focus within the observation window; interactive timing for those samples is NOT RUN, not silently inferred from visibility. This subset does not prove physical keyboard usability.

First activation in fresh GUI processes, five independently launched processes per version:

- Toolbar Show: **958.179 /972.866 → 695.675 /724.453**.
- Paint processed: **1009.914 /1017.116 → 740.336 /771.617** (median269.578ms/26.7% sooner).
- Focused readiness was observed in4/5 baseline and5/5 optimized processes; conditional medians1037.164→779.682ms. Do not infer focus reliability from this small programmatic sample.

With only five cold observations, nearest-rank p95 is the maximum; it is a coarse observed tail, not a statistically stable percentile estimate. “Cold” means the first capture in a new application process while the desktop portals are already available. It is not cold boot/login, nor an actual user's first keypress after the normal service starts. Those physical checks remain pending.

Public-fixture/offscreen serialized comparison,40 warm samples per version: paint processed **75.403 /102.781 → 62.055 /80.492ms**; focused readiness **75.443 /102.830 → 62.087 /80.540ms**. This synthetic workload uses a1920×1080 public PNG and a controlled5ms async portal stand-in. It does not model GNOME permissions/backend time and is not compared numerically with older Phase2 Task3's different fixtures.

Raw data: [native before](shortcut-latency-delivery-before-native.json), [native after](shortcut-latency-delivery-after-native.json), [fresh-process cold samples](shortcut-latency-cold-native.json), [fixture before](shortcut-latency-controlled-before-fixture.json), [fixture after](shortcut-latency-controlled-after-fixture.json).

## Confirmed bottleneck and practical portal limit

`AsyncJobs` previously advanced asyncio only once per10ms Qt timer tick. D-Bus authentication, identity registration, method calls and wait_for/future completions contain multiple short await boundaries. Their continuations repeatedly waited for the next timer tick. This multiplied latency even when responses were immediately available. It affected both mandatory display-layout reads and per-connection Screenshot setup.

Per-sample stage durations, native median /p95 before→after (do not sum medians of overlapping intervals):

- First GNOME layout read: **100.052 /110.576 → 24.691 /31.422ms**.
- Screenshot connection/Registry/version setup before the actual Screenshot method: **100.087 /100.398 → 14.762 /18.458ms**.
- Actual Screenshot method to its D-Bus Response signal: **540.456 /550.559 → 542.713 /575.890ms**. No backend speedup is claimed.
- Complete Screenshot helper, including that setup/response: **650.406 /660.483 → 558.607 /592.924ms**.
- PNG→QPixmap load: **39.910 /53.088 → 57.390 /72.266ms**. Image decoding was not optimized; the observed increase is retained. Native screenshot pixels/compression and desktop load vary across runs.
- Second layout read after image load: **91.796 /91.982 → 13.957 /16.881ms**.
- Overlay widget construction after verified mapping: **11.301 /14.078 → 11.597 /17.491ms**. No widget-construction improvement is claimed.

The tested portal stage still waits approximately0.54s. That includes GNOME's capture/encoding/portal processing and transport; it is not a pure CPU measurement or a universal fixed lower bound. Permission dialogs can add arbitrary human response time. Preserving the supported portal path means this optimization cannot make capture instantaneous. Both layout reads and fresh per-connection app identity remain intact. Widget reuse, display caching and persistent screenshot connections were unnecessary for the demonstrated gain and would add lifecycle/invalidation work.

## Changes

`utils/async_jobs.py` uses a precise1ms Qt timer while owned asynchronous jobs are active and a coarse100ms checkpoint when idle. It retains the existing single file worker and non-reentrant tick guard. Qt GUI/clipboard operations remain on the Qt GUI thread; file/OCR worker behavior is unchanged. Higher active timer frequency is a tradeoff; no battery/total-CPU improvement is claimed. Idle callback frequency is reduced from configured100Hz to10Hz, retaining Python signal processing.

Two regressions were caught during development and fixed before final verification:

1. The first attempt stopped the timer completely when idle. Python can remain inside Qt's C++ exec loop with no Python callbacks, leaving a Python SIGTERM handler pending. The real-process shutdown test timed out. The100ms idle checkpoint restores signal delivery without the old100Hz idle pump.
2. During close, a completed root's callback could restart the idle timer. A closing guard now rejects new work and prevents timer restart while cancellation/worker/subprocess cleanup drains. The new active-close test caught this before delivery.

`utils/capture_latency.py` adds opt-in monotonic timestamps and a toolbar-parented event observer. It records show, first paint, processing after the paint event, and focused/enabled readiness. Its timers die with the toolbar. Event filters never consume input; no new window or startup popup is created. Diagnostics are disabled by default and contain capture IDs, stage names and elapsed/absolute monotonic times only, with no image paths, pixels or OCR text.

`shortcuts/global_shortcut.py` records the incoming Activated signal when latency diagnostics are enabled; its activation signal, registration, stable IDs, requested/assigned shortcuts and routing remain unchanged. `ui/capture_menu.py` records callback/preparation/portal/image/mapping/widget/show stages, including failure/cancellation. `capture/screenshot_portal_request.py` records connect/Registry/actual Screenshot method/Response points. A ContextVar associates nested portal tasks with the accepted capture and is reset in finally. The ordinary path still makes one screenshot request; the existing consent-window retry intentionally discards a permission capture and recaptures after that window closes.

No overlay/style, capture algorithms, source pixels, mapping conversion, clipboard implementation, atomic filename/save behavior, OCR algorithm, tray implementation, startup configuration or desktop binding changed. No screenshot or geometry cache was introduced.

## Measurement boundaries and reproducibility

Qt's Show event does not establish that a user can see the toolbar. The primary endpoint is the callback after the first toolbar paint has run. It does **not** measure the compositor's physical scanout/photons. Focused readiness additionally requires an active capture window and enabled/visible toolbar. Actual global keyboard input, pointer interaction and perceived responsiveness require human observation.

Incoming physical Activated events can be recorded with `SNIPPING_LATENCY_DIAGNOSTICS=1` on a legitimate host launch. The existing route remains GlobalShortcuts.Activated → Qt queued signal → CaptureMenu.launch_overlay. Capture IDs start at accepted callbacks; repeated activations while busy are still coalesced. The new flag does not enable the older image/path diagnostic decoder. Avoid enabling broader diagnostics while comparing timings because existing image diagnostics can add extra decoding.

Before/after use the same instrumented path and backend. Baseline active scheduling comes from a read-only snapshot of the original class, loaded only into the benchmark process; no checkout/reset or production fallback was used:

```bash
git show a0428d3:utils/async_jobs.py > /tmp/snipping-latency-original-jobs.py
QT_QPA_PLATFORM=offscreen .venv/bin/python tests/shortcut_latency_probe.py \
  /tmp/before.json --count 41 --scheduler-source /tmp/snipping-latency-original-jobs.py
QT_QPA_PLATFORM=offscreen .venv/bin/python tests/shortcut_latency_probe.py \
  /tmp/after.json --count 41
```

Original class SHA256 `ee91091ca256978a22f3ce3bf858ce8df87080171dd2aaea46e568dfd1abe70f`. The final baseline uses10ms active/idle pumping; optimized code uses1ms active/100ms idle. Counts include the first separate sample, so41 means40 warm observations and21 means20 warm. `--count 1` measures a first activation in a fresh process.

Native equivalent, executed only while the normal app is deliberately inactive to prevent duplicates:

```bash
systemd-run --user --wait --pipe --collect --unit=snipping-latency-probe \
  --property=WorkingDirectory=/home/dulmina/Projects/ai-snipping-tool \
  --setenv=QT_QPA_PLATFORM=wayland \
  /home/dulmina/Projects/ai-snipping-tool/.venv/bin/python \
  tests/shortcut_latency_probe.py /tmp/native-after.json --native --count 21
```

The baseline adds `--scheduler-source /tmp/snipping-latency-original-jobs.py`. Final warm batches were serialized, and the five cold pairs were interleaved before/after. No regressions or clipboard probe ran concurrently with final timed batches. Genuine user-manager launches/Registry identity were used, without inheriting/spoofing the editor's Snap scope. The probe matches main.py's Qt ApplicationName/DesktopFileName. Its local test Activated message is not sent to GNOME and does not create/change a global shortcut binding. Screenshot methods use the real host portal with normal consent.

Early exploratory batches overlapped a fixture run or used the default Qt window identity in the harness; they are not the published primary comparison. The harness identity was corrected before the final warm/cold data. Some programmatic windows still lacked focus; no activation token or security bypass was synthesized. The final native fixture workflow confirms one monitor at100% scaling; no physical fractional/multiple-monitor performance claim is made.

## Regression, native verification and remaining acceptance

- **PASS:** all191 regressions,18.844s, after both shutdown fixes. Nine focused tests cover low-rate idle/active scheduling, multiple roots, chained jobs, Qt heartbeat/non-reentrancy, cancellation during close, ordered readiness/fresh PNG pixels, observer cleanup,15 rapid synthetic Escape cycles and disabled instrumentation. Existing tests include100 consecutive saves, Window success/cancel, display/mixed-DPI fixtures, failed writes, OCR/clipboard and subprocess/worker cleanup.
- **PASS:** Python syntax/import coverage and git diff --check.
- **PASS:** final native public-fixture Rectangle/Full Screen/repeat PNG integrity, cross-process PNG pixel equality/paste in two separate readers, real English OCR/text paste and supplied Sinhala/ZWJ transfer across focus changes. Final probe exited0 with shortcut thread stopped. This is programmatic native Qt/Wayland transfer, not physical Ctrl+V or Sinhala recognition accuracy.
- **PASS:** native repeated opening/closing and controller cancellation across measured batches; fresh screenshot requests, both mapping snapshots and all primary first-paint checkpoints. No orphan probe worker process or duplicate normal app is left running.
- **PASS:** protocol-activated, PID-verified tray Quit and corrected service stop/start. Final test driver observed clean stop0.020s before measurements, then restored the same enabled normal unit. Separate restart reached registered status in1.258s and logged Shutdown complete for the old invocation; repeated start retained the PID. Last read-only check after all probes: **one PID88627**, enabled/active/NRestarts0, identity Registered, actual Ctrl+Alt+S, original user-unit FragmentPath.
- **PASS, bounded resource observations:** final before/after warm runs start with18 FDs, end with58 before explicit GC, and20 after GC in both; Python threads MainThread only after shutdown, pending owned tasks0. Cyclic dbus-next/Qt object cleanup depends on collection, as in the baseline; no new FD growth difference is demonstrated. This is not an hours-long leak proof or an eager-resource-release claim.
- **NOT RUN:** an additional actual-portal public-color pixel/previous-toolbar-exclusion fixture could not establish its baseline (scene focus/presentation or color conversion did not match raw PNG samples). It stopped conservatively, logged no raw pixels and restored the app. No pixel or toolbar-exclusion pass is inferred from that attempt; `tests/native_capture_freshness_probe.py` retains the opt-in check for a suitable focused scene.
- **NOT RUN:** physical assigned-key-to-photon/interaction timing, real new Window picker/cancellation, physical Escape/tray controls or user application paste for this exact change. Mocked Window and native public-fixture paste are explicitly separate from those checks.

Observed development failures are retained: initial full191 run had one SIGTERM timeout from stopped idle polling; the next191 run exposed the close callback restarting the timer; final191 passes both. A temporary tray test helper initially misparsed GNOME's `name@path` format and failed to find the app; it was corrected without a production tray change. Native cross-process verification remained successful. Full commands, logs, source hashes and service observations are in [evidence](shortcut-latency-evidence.txt).

Minimal physical check on the currently restored service: optionally restart it from a genuine GNOME terminal with `systemctl --user restart com.dulmina.aisnippingtool.service` and wait for registered status, then focus another app, press the **actual shortcut shown in the tray** (last observed Ctrl+Alt+S; requested Alt+Shift+S is unchanged), assess first and repeated activation, then Escape several times. Verify Rectangle→external image paste, Window→external image paste/cancel, English Extract Text→external text paste, and tray Quit staying stopped. Record PASS/FAIL; do not assume the requested shortcut equals the assigned one. Startup/login/reboot acceptance from Stage2 remains historical; this task did not change startup configuration or perform logout/reboot.

## Files and Git provenance

Production: `utils/async_jobs.py`, new `utils/capture_latency.py`, `ui/capture_menu.py`, `capture/screenshot_portal_request.py`, `shortcuts/global_shortcut.py`.

Tests: new `tests/shortcut_latency_probe.py`, new `tests/test_capture_latency.py`, new opt-in `tests/native_capture_freshness_probe.py`.

Documentation: this report; `docs/shortcut-latency-evidence.txt`; five linked measurement JSON files; `docs/handoff-summary.md`; `docs/test-matrix.md`.

Started clean at95b81bf on main, with feat/background-service at the identical commit. Used the user's standing authorization to return to that existing feature branch; automatic permission review initially timed out and the permitted retry succeeded. No files were edited on main. External commits **a0428d3**, **a3fa2d2**, **161ec8e** and **4bb819b** appeared during implementation, containing task work; they were preserved. The agent did not stage, commit, reset, merge, push or rewrite them. Final Git state is recorded separately.

The Stage3.1 artifact remains byte-identical: `dist/stage-03.1-final/ai-snipping-tool_0.3.1~stage3.1-1_amd64.deb`, SHA256 `39a189ad278921cd68cd68b9caf86f027b64659dca609f1b7193c433e1c2e2eb`. It predates this latency fix. A future package rebuild/clean install needs a separate reviewed follow-up; no candidate replacement happened here. No Freeform, AI, packaging installation or subsequent stage began.
