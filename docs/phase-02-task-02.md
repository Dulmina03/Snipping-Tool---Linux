# Phase 2 Task 2 — Display mapping

Work in progress, 2026-11-14. Phase 2 Task 1 is physically accepted by the user (all six acceptance tests PASS). Task 2 only; no Freeform or AI work.

## Confirmed limitations before changes

- Production Rectangle uses only the union width/height of Qt screens, then independently scales X/Y by screenshot dimensions. It loses the virtual origin and freezes neither layout nor image mapping. The compatibility selected-area helper does a similar conversion with different edge rounding.
- Overlay stretches the entire screenshot into one virtual-desktop-sized QWidget. Wayland fullscreen targets an output; requested global positioning/spanning is not reliable. Mixed-DPI monitor layout cannot be inferred from this window or a PNG size alone.
- Screenshot portal v2 returns a file URI, no per-monitor pixel rectangles. Multiplying by QScreen DPR after converting image pixels would risk applying scale twice.
- `(0,0)` is treated as an absent start/end point, preventing a valid corner selection. Out-of-bounds/empty selections are not consistently rejected before Pillow crop.
- This host has one physical eDP-1 1920×1080 display at GNOME scale 1.0, logical layout mode. Physical multi-monitor and other GNOME scale settings are NOT RUN; no settings have been changed.

Implementation and verification results will be added below. Existing Phase 2 branch/history and working state are preserved.

## Result and coordinate strategy

**Implementation/automated verification PASS. Physical Task 2 multi-monitor acceptance remains NOT RUN.** All 132 regressions pass (107 previous +25 new). No Task 3, Freeform, AI or unrelated capture-system change.

1. `capture/display_mapping.py` provides immutable GNOME monitor bounds and a capture mapping. Read-only, bounded async D-Bus calls read ShellVersion and Mutter GetCurrentState before/after the portal capture. A changed serial/layout or changed Qt screen fingerprint invalidates Rectangle mapping. No display setting is applied.
2. Production mapping is constrained to the verified GNOME Shell 50 stage-capture contract, known `gnome-screenshot` PNG metadata, matching output connector names, logical layout mode and the expected PNG dimensions. GNOME's full-stage image uses a compositor capture scale (maximum stage-view scale), which may differ from an individual monitor's scale or Qt DPR. Fractional render buffers may use the next integer scale; image dimensions validate which contract applies. No extra Qt DPR multiplication is made during cropping.
3. Each logical monitor gets a separate Qt fullscreen surface through `QWindow.setScreen()`, sharing the same frozen PNG, selection, action/mode and lifecycle. Each surface paints only its own PNG source rectangle. No single Wayland window is asked to span/move across the virtual desktop. Negative **Qt** origins are handled by connector-based mapping and translating to a canvas rooted at the GNOME desktop bounds.
4. Surface-local floating-point pointer coordinates convert to canonical compositor coordinates using the actual surface viewport dimensions. Pointer-grab coordinates can extend beyond the originating surface for a boundary-crossing drag. Fractional edges remain floating point; the existing inclusive Qt selection unit is converted before rounding. Reverse drags construct explicit minimum/maximum edges, fixing QRect negative-size normalization and `(0,0)` corner handling.
5. Cropping computes a half-open PNG box: floor left/top, ceil right/bottom, clip to PNG bounds. Pillow slices the original pixels without resizing. The dimension badge uses the resulting PNG pixel size. Regions containing holes between unequal/offset monitors are rejected rather than filled with new black pixels. Full Screen still copies the server PNG unchanged, including any genuine unused desktop gaps already present in it.
6. All surfaces share cancellation/processing/clipboard-delivery signals. Any active app surface can hold focus for the existing clipboard handoff. Qt screen changes cancel the session; before selection completion, the frozen fingerprint and native target output are checked. Closing/cancelling disposes all surfaces and source files through existing controller cleanup.
7. If the mapping cannot be verified, Rectangle is disabled with an explicit reason and no stretched screenshot preview. Full Screen and Window remain available through the original backend/save routes. The older standalone selected-area helper uses the shared checked single-canvas crop math and refuses multiple Wayland outputs, directing users to `main.py`.

Primary implementation references: [Qt device-independent coordinates](https://doc.qt.io/qt-6/highdpi.html), [GNOME Shell 50.1 screenshot capture](https://github.com/GNOME/gnome-shell/blob/50.1/src/shell-screenshot.c), [Mutter 50.1 capture sizing](https://github.com/GNOME/mutter/blob/50.1/clutter/clutter/clutter-stage.c), [Mutter display-state interface](https://github.com/GNOME/mutter/blob/50.1/data/dbus-interfaces/org.gnome.Mutter.DisplayConfig.xml), [Screenshot portal API](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.Screenshot.html). The installed Screenshot portal is v2; the current online API page also describes newer features, which this implementation does not assume.

## Files modified

- `capture/display_mapping.py` — new model, coordinate validation, read-only GNOME discovery and backend guard.
- `ui/display_overlay.py` — new per-output surfaces and shared selection/lifecycle.
- `ui/capture_menu.py` — freezes/verifies layout around capture, uses the pixel mapping, and reports unsupported mapping safely.
- `ui/overlay.py` — source-region painting, correct corner/reverse selection, fractional rectangle support and accurate pixel-size badge. Toolbar classes/QSS are byte-identical to Task 1.
- `capture/selected_area.py` — checked compatibility crop math and explicit legacy Wayland multi-output limitation.
- `tests/test_display_mapping.py` — 25 model/provider/session/controller cases.
- `tests/production_clipboard_probe.py` — optional native helper now targets the session's QWidget surface, marks its synthetic PNG as a controlled GNOME-layout fixture, and explicitly skips layouts its fixed single-monitor/100% OCR reference cannot represent. Its public fixture is not a security/app-identity override. It was compiled but not run in this task because an existing user app instance was left undisturbed.
- This document, `docs/phase-02-task-02-evidence.txt`, `docs/handoff-summary.md`, `docs/test-matrix.md`, and the physical-acceptance update in `docs/phase-02-task-01.md`.

No edits to filename generation, screenshot directory, clipboard implementation, OCR algorithms, global shortcuts, tray logic, requirements or toolbar styling.

## Automated verification

- **PASS — full suite: 132 tests in 8.435s, exit 0.** Existing Task 1 repeated-capture, uniqueness, cleanup, clipboard/OCR lifecycle, toolbar and startup regressions remain green.
- **PASS — all 25 mapping tests at Qt scale factors 1.25, 1.5, 1.75 and 2.0**, each run in a separate offscreen process; standard 100% also covered. Controlled portal PNGs and simulated monitor configurations are used.
- The matrix covers 100/125/150/175/200% compositor scales, fractional ceil-render buffers, different resolutions, mixed scales, left/right/above/below arrangements, negative origins, cross-boundary forward/reverse drags, edges, gaps, zero/invalid selection, pixel-exact saved crops and real offscreen Qt PNG MIME contents. These MIME checks do not establish external paste.
- Tests verify per-output source-region painting, subpixel precision, dimension badges, one routed signal for Window/Full Screen/cancel, geometry-change cancellation, missing/unsupported metadata, unsupported backend versions and layout modes, provider errors/cancellation/disconnection, and fallback Full Screen preservation.
- An initial new reverse-drag assertion failed, exposing the QRect normalization defect; corrected and rerun. No final test failure remains.
- Compile/import and `git diff --check` / `git diff --cached --check` **PASS**. Toolbar-prefix comparison against starting HEAD is byte-identical; protected modules have no task diff.

## Native Wayland observations

**PASS — native geometry/portal probes on one physical display:** GNOME Shell 50.1, eDP-1, 1920×1080, GNOME scale 1.0, logical layout mode. The real portal returned a 1920×1080 PNG with `Software=gnome-screenshot`, matching the stable before/after layout. An actual fullscreen Qt surface targeted eDP-1 at 1920×1080; selection `(100,100)` through `(149,139)` mapped to PNG box `(100,100,150,140)`. Cancellation was programmatic and all diagnostic processes exited 0.

Additional native Wayland probes set **QT_SCALE_FACTOR**, leaving GNOME at 100%:

- 1.25: Qt viewport 1536×864, selected PNG box `(125,125,188,175)`.
- 1.5: viewport 1280×720, box `(150,150,225,210)`.
- 1.75: viewport 1097×617, box `(175,175,263,246)`.
- 2.0: viewport 960×540, box `(200,200,300,280)`.

Every box matched its independently calculated expectation; the portal PNG remained 1920×1080 and was not scaled twice. Native geometry used only dimensions/metadata from the real PNG; visible probe surfaces used public solid fixtures. No private screenshot pixels were exported, logged or included in evidence. No GNOME setting, shortcut binding or permission was changed. An existing running application was not stopped or replaced.

**These are not physical multi-monitor tests or physical GNOME fractional-scaling tests.** Only one physical display is attached. GNOME did not offer 175% for the current 1920×1080 mode; the fixture/model and Qt-scale checks cover 175%, but no unsupported OS scale was forced.

## Known constraints / explicit limits

- The portal's v2 response has a URI, not per-monitor packing metadata. Unrecognized PNG metadata/dimensions, backend versions outside GNOME 50, unavailable display information, physical-layout mode, cloned/overlapping outputs, mismatched Qt connector/proportions or unexpected output targeting are refused for Rectangle. Full Screen/Window remain available.
- Negative Qt screen origins are supported. A native GNOME stage origin other than `(0,0)` is explicitly unverified, since Shell's whole-stage request starts there; that discovery case is refused rather than guessing. Negative-origin arithmetic is separately covered by explicit fixtures.
- GNOME may resample lower-density outputs into its stage PNG. This app preserves the portal's source pixels; it cannot recover original panel pixels that the portal did not supply.
- Cross-output dragging is supported through surface-local pointer-grab coordinates, but physical compositor behavior across real mixed-DPI outputs still needs acceptance. A selection that spans unoccupied layout space is intentionally rejected.
- Full Screen preserves the returned PNG, so genuine gaps in the compositor's virtual desktop may remain black in that image. The app adds no crop padding or resizing.
- Large-PNG decode/crop/save performance and actual multi-monitor GPU/compositor behavior have not been benchmarked by the small controlled fixtures. Existing repeated-operation/heartbeat regressions passed; this is not a universal performance claim.

## Physical acceptance still required — NOT RUN

Quit/relaunch the user app from GNOME's application grid to load this code. Do not leave an older resident instance running while testing.

1. On the current screen, use the actual assigned shortcut. Capture a bordered public test pattern at center and every edge/corner; repeat reverse-direction drags. Compare PNG and external paste, dimensions and the pixel-size badge. Verify Escape, repeated captures, English OCR paste, Window and Full Screen.
2. Where GNOME offers them, repeat at 125/150/175/200%, starting a new capture after changing display settings. Do not force an unsupported factor. Record actual mode/scale and portal output dimensions.
3. With two actual displays, test same/different resolutions and mixed scales. Place secondary left, right, above and below. Verify one correctly aligned surface per output, captures wholly on each output and boundary-crossing selections both directions.
4. Check a selection into a true monitor-layout gap reports a limitation and saves nothing. Cancel while selecting, change/hotplug a monitor while selecting, then capture again; expect no stale source, frozen overlay or orphan windows. Confirm tray Quit afterward.

Task 2 implementation is ready for this acceptance gate; physical multi-monitor accuracy is not signed off. Do not start Task 3, Freeform or AI.

## Git provenance

Started clean on existing `fix/phase-02-capture-reliability`, HEAD `7b3d295`. External commits `4b7425f` and `1d9509c` appeared during implementation and were preserved. The agent did not stage, commit, merge, reset, checkout or push. Recheck the current index/history before continuing. Evidence and commands are recorded in [phase-02-task-02-evidence.txt](phase-02-task-02-evidence.txt).
