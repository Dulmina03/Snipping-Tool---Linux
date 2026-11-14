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

## Phase 1 results — 2026-11-14

This section supersedes the Phase 0 expectations where code changed; preceding results remain historical. Full output: [phase-01-command-log.txt](phase-01-command-log.txt). Run only `unittest discover -s tests` for the automated suite; root `test_overlay.py` still launches an interactive GUI on import.

| ID | Check | Result | Evidence / limit |
|---|---|---|---|
| P01 | Lifecycle suite | PASS | `.venv/bin/python -m unittest discover -s tests -v`: 20 tests |
| P02 | Compile/import checks | PASS | compileall across production/tests; isolated Phase 0 probe imports 12 modules |
| P03 | Existing menu smoke | PASS | offscreen `test_capture_menu.py --smoke`, now asserts quiet hidden-controller startup |
| P04 | Existing mocked cancellation | PASS | offscreen `test_capture_menu.py --cancel`; hidden controller remains hidden |
| P05 | Obsolete AI placeholder | NOT RUN | `--ai` explicitly prints NOT RUN and exits without capture/AI; no placeholder implementation added |
| P06 | Launcher generation/migration | PASS | quoted paths with spaces; legacy migration, custom preservation, desktop-file validation |
| P07 | Installed desktop launcher | PASS | actual `main.py --install-desktop` and validation, Exec now targets main.py with current .venv Python |
| P08 | Canonical startup/legacy delegation | PASS | alternate controller entry delegates; no overlay or shown controller at construction |
| P09 | Single instance/process restart | PASS | actual headless main.py subprocess rejects second launch; SIGTERM exits, releases lock; repeat startup passes |
| P10 | Shortcut/tray activation routing | PASS | synthetic signal and QAction route to same async workflow; not a physical shortcut check |
| P11 | Overlay lifecycle | PASS | repeat activation coalesced; cancel, rectangle and fullscreen dispose overlay; controller hidden |
| P12 | Delayed/denied portal responsiveness | PASS | simulated delay with continuing Qt heartbeat; denial/retry; no fallback overlay |
| P13 | Portal cleanup | PASS | early-response handling; cancellation during connection/method disconnects, removes handler, closes Request |
| P14 | Thread boundaries | PASS | window backend and image/text clipboard deliveries observed on app.thread(); OCR behind process boundary |
| P15 | OCR shutdown | PASS | real worker error protocol; long-lived real process killed/reaped by jobs.close; no late text clipboard delivery |
| P16 | Shortcut startup/shutdown | PASS | duplicate manager.start rejected; quitting during simulated registration cancels worker and joins thread |
| P17 | Existing clipboard/OCR smoke | PASS | unchanged isolated PNG MIME/UTF-8/ZWJ checks; synthetic English CER/WER remain zero; no new accuracy claim |
| P18 | GNOME default theme startup | FAIL → PASS | initially aborts on missing XSettings key; conditional generic fallback passes automated test and live startup |
| P19 | Real Wayland startup/heartbeat/Quit action | PASS | native Qt state: controller hidden, no startup overlay, tray reported available; 84 heartbeats/8.42s; shortcut thread stops |
| P20 | Real portal registration | PASS | final live run completes BindShortcuts for requested Ctrl+Shift+S; not physical key verification |
| P21 | Whitespace | PASS | git diff --check and git diff --cached --check, exit 0 |
| P22 | Physical Ctrl+Shift+S opens only overlay | NOT RUN | no native keyboard/visual-control tool in this session; unit signal emission is not proof |
| P23 | Visual blank-window/task-switcher check | NOT RUN | Qt hidden state confirmed, but desktop appearance not visually inspected |
| P24 | Cross-app clipboard after overlay closes | NOT RUN | existing clipboard helper/anchor preserved; real Wayland paste needed |
| P25 | Physical tray Capture/Quit clicks | NOT RUN | native tray availability and QAction shutdown tested, not a human click |
| P26 | Interactive portal Cancel/denial/delay | NOT RUN | automated simulations only; no live screenshot request made |

Known remaining problems: host Registry emits `org.freedesktop.portal.Error.Failed` in live test even though shortcut registration succeeds; exact desktop attribution/physical trigger need acceptance. Existing dependency conflicts, output filename collisions, OCR punctuation/accuracy/model-download risks remain recorded in Phase 0. No crop/clipboard engine changes or AI/PDF/Freeform implementation were made. The old `--run selected_area` compatibility harness is now rejected explicitly; test rectangles through the production toolbar. This removes the obsolete nested-loop test route without removing the production feature.

### Physical acceptance steps still required

1. Quit any existing instance. Run `.venv/bin/python main.py` or the installed GNOME launcher. Expect background startup, no blank controller or immediate overlay. Use `.venv/bin/python main.py --install-desktop` after moving this checkout/interpreter; do not copy the template directly.
2. Authorize the portal shortcut, focus another app and physically press its assigned Ctrl+Shift+S. Only the intended selection overlay should appear. Repeat ten times, alternating rectangle completion, Esc and toolbar X. Check Alt+Tab/task-switcher for a blank controller.
3. Paste screenshots into another GUI application immediately and five seconds after overlay/toast closure. Verify exact pixels/dimensions. Repeat Extract Text with a public fixture and compare Sinhala/English/ZWJ output against reference. No private document output should be logged/shared.
4. Exercise portal cancellation/denial/delay and use tray Quit while waiting. Check no stuck UI, orphan process or late clipboard delivery. Restart from the launcher and repeat capture.
5. Verify tray Capture and Quit by actual clicks. Confirm the launched PID exits within five seconds and another launch registers normally.

The user asked the agent to perform checks independently; a bounded real Wayland smoke was run. Physical-key/visual/paste checks remain explicitly NOT RUN because this session has no native desktop controls. **Phase 1 implementation is ready for review; the full phase exit gate is pending those manual checks. Do not proceed to Phase 2.**

## Phase 1 acceptance follow-up — 2026-11-14

Latest detailed results for **all 13 user acceptance tests**: [phase-01-acceptance.md](phase-01-acceptance.md). This supersedes any inference that the earlier registration PASS proves Ctrl+Shift+S is bound.

- PASS: 20 automated regressions; quiet native main runtime state; single-instance rejection; exactly one actual GIO-launched main.py process; installed launcher execution; bounded programmatic Quit/SIGTERM cleanup.
- FAIL: intended shortcut assignment/truthful reporting. Portal returns `Press <Control><Alt>s`; app emits preferred `<Ctrl><Shift>S`. Preferred string also differs from the portal's specified XDG syntax.
- FAIL in this launch context: host Registry identity. Detailed response identifies caller as `io.snapcraft`; both tests inherit the Snap VS Code cgroup. Do not classify this as harmless or assume successful host app identity.
- NOT RUN: visual blank-window check, actual physical key/Esc/tray clicks, repeated real captures, all three capture modes, cross-app image/OCR paste, independent genuine GNOME app-grid context.

**Phase 1 cannot close and Phase 2 must not begin.** No production source or user shortcut settings changed during this verification. Existing dirty command log/manual harness additions preserved; no Git mutation commands executed.

## Shortcut correction results — 2026-11-14

Latest [acceptance update and manual procedure](phase-01-acceptance.md) supersede the earlier preference-syntax/false-reporting code failures. **43 automated tests PASS**, including all original 20. Syntax, existing smoke/cancel and whitespace PASS. The new suite covers assigned-description display, mismatch/localized/missing values, remembered user choices, Bind/List/ShortcutsChanged, Registry ordering/errors, real method detection across versions/backports, explicit configuration and shutdown. [Exact output](phase-01-shortcut-log.txt).

Live reporting PASS: requested `CTRL+SHIFT+s`; actual `Press <Control><Alt>s`; tray agrees. Existing choice preserved. Installed portal version=1 advertises ConfigureShortcuts, but configuration is disabled for the observed `io.snapcraft` identity rejection. No live configuration dialog invoked or settings altered. Genuine app-grid identity, desired assignment, physical shortcut/Esc/tray and external image/text paste remain **NOT RUN**. Full Phase 1 gate remains open; Phase 2 has not started.


## Native GNOME verification follow-up — 2026-11-14

Supersedes older environment/assignment/identity statements above: genuine host identity **PASS**, actual assigned Ctrl+Shift+S **PASS**, 43 regressions **PASS**. Real portal/fullscreen/rectangle saving, bounded repeat workflow, local English fixture OCR, synthetic Qt cancellation and shutdown **PASS**. App-workflow native cross-process image/text paste **FAIL** with synthetic producer input; focused public-text control **PASS**, root cause unresolved. AT-SPI Escape synthesis **FAIL** despite API True; real keyboard/tray clicks/window selection/paste **NOT RUN**. Backend ConfigureShortcuts UnknownMethod remains. No GNOME settings/source changes. **Phase 1 cannot close; Phase 2 must not begin.** All individual acceptance outcomes, physical steps and retained evidence: [phase-01-acceptance.md](phase-01-acceptance.md).


## Clipboard reliability follow-up — 2026-11-14

50 regressions PASS; focused native two-process exact PNG and Sinhala/English/ZWJ text transfer/paste PASS. Final traced unmapped/delayed/controller delivery and canonical synthetic-workflow image/text paste FAIL, with active event loops and GUI-thread writes. Zero/stale selection serials/focus loss and a prior text-only image receiver explain testing limitations; physical behavior remains NOT RUN, not cleared. ConfigureShortcuts v1 advertisement is now rejected by the v2 capability gate; shortcut binding unchanged. No clipboard/capture/OCR behavior rewritten. Phase 1 OPEN; Phase 2 blocked. [Latest acceptance, pipeline, provenance, reproduction and manual gate](phase-01-acceptance.md); [raw evidence](phase-01-clipboard-evidence.txt).


## Physical failure and permission fix — 2026-11-14

User reported physical app-grid PASS; capture/Esc/rectangle/OCR/window/tray FAIL. Journal confirms background GNOME access-dialog focus rejection, not observed user cancellation. Identified background probe returned `[2, {}]`; focused Qt probe exposed GNOME consent dialog. User confirmed Allow. New shared screenshot connection registration, typed errors, explicit focused recovery/clean recapture and request cleanup implemented. Post-consent native capture/recovery and programmatic tray Quit PASS; 66 regressions PASS. Physical post-fix keyboard/window/tray/paste NOT RUN; clipboard handoff remains unresolved. Phase 1 OPEN, Phase 2 blocked. Legacy screenshot experiment restored exactly; no overlay/clipboard/OCR algorithm changes. [Latest acceptance and provenance](phase-01-acceptance.md), [evidence](phase-01-physical-failure-evidence.txt).


## Capture-to-clipboard integration fix — 2026-11-14

Physical startup, Ctrl+Shift+S overlay, Escape and tray Quit now user-confirmed PASS. Image/OCR paste and Window remain pre-fix FAIL. Fixed publication after overlay teardown; OCR retains surface/result, defers unfocused delivery to click/Enter, GUI-thread guard, standard Clipboard only, no fake anchor/nested event pump. Native production handlers + two separate readers PASS for rectangle/fullscreen/repeat, real English OCR and supplied Sinhala/English/ZWJ punctuation. 74 tests PASS. Real Window picker opens (Screenshot v2); selected-window completion and all post-fix physical paste acceptance NOT RUN/pending user. Window success/cancel mocks are separate; no claim of complete Window root cause. Phase 1 OPEN; no Phase 2. [Details](phase-01-acceptance.md), [evidence](phase-01-delivery-evidence.txt).


## Alt+Shift+S final shortcut change — 2026-11-14

- PASS: 76 automated tests; requested `ALT+SHIFT+s`, stable app/action IDs, old remembered binding preserved, new Alt assignment parsing, actual display, mismatch, ShortcutsChanged, v1 configuration gate, capture/OCR/clipboard lifecycle regressions. Syntax/import and both diff whitespace checks PASS.
- PASS: genuine host installed-desktop-entry execution, Registry identity, one main.py instance, actual assignment retrieved by List and displayed truthfully. Prior process quit through PID-verified tray protocol; no physical click simulated as PASS.
- FAIL / pending migration: desired Alt+Shift+S is not yet assigned. GNOME still returns `Press <Shift><Control>s`, and read-only stored settings agree. No Alt conflict has been established. User must edit this app's action in Settings → Apps → AI Snipping Tool → Global Shortcuts and confirm; cancel any conflict. No settings were silently changed; ConfigureShortcuts v1 was not called.
- PASS (user report before this shortcut change): grid startup, rectangle screenshot/paste, English OCR/paste, Window screenshot/paste, Escape, tray Quit. This supersedes earlier physical delivery failures.
- NOT RUN after this change: physical Alt+Shift+S, Escape, rectangle/OCR/Window external paste, physical tray Quit, persistence across restart. Automated routing does not prove these. Phase 1 remains OPEN until the user confirms the new binding and no regressions. Phase 2 has not started.

Detailed evidence and minimum acceptance: [phase-01-acceptance.md](phase-01-acceptance.md), [phase-01-alt-shortcut-evidence.txt](phase-01-alt-shortcut-evidence.txt).

Final native cleanup PASS: PID-verified DBusMenu Quit on updated PID 200574 logged aboutToQuit, capture-job/session cleanup and Shutdown complete; PID no longer exists. Own terminal test harness stopped. A real Activated signal + screenshot response 0 appeared late in the session, but without key/source attribution or user visual confirmation; physical Alt+Shift+S remains NOT RUN.


## Compact status layout / current binding — 2026-11-14

- PASS: 81 regression tests; readable XDG/portal key display; unknown/localized text preserved; compact tray actions; requested/actual/registration/identity separated; errors and instructions in collapsed details; explicit-only status opening; narrow 320×480 logical geometry, wrapping, plaintext and left alignment; existing capture/clipboard/OCR/window/Escape/Quit automation retained.
- PASS: 31 shortcut/presentation cases at QT_SCALE_FACTOR=2; compile/import and both whitespace checks. Generated 288×340 narrow offscreen render visually inspected with Close/details visible.
- PASS: native host registered identity and actual ListShortcuts/ShortcutsChanged **Ctrl+Alt+S**, while request is **Alt+Shift+S**; truthful compact tray labels. One main.py instance observed. Portal v1 configuration remains disabled; no settings mutation.
- NOT RUN: native visual/scaling confirmation (AT-SPI could not expose dialog), physical Alt+Shift+S and post-layout rectangle/OCR/Window paste, Escape, tray interactions. Prior user-confirmed physical passes remain historical evidence. Programmatic tray status activation is not a physical click.
- PENDING: explicit GNOME Settings → Apps → AI Snipping Tool → Permissions → Global Shortcuts → capture action → Set Shortcut confirmation. Cancel conflicts; no binding reset/replacement automated. Phase 1 open; no Phase 2.

[Current detailed acceptance](phase-01-acceptance.md), [evidence](phase-01-status-ui-evidence.txt).


## Phase 2 Task 1 — Filename and repetition reliability (2026-11-14)

- PASS: full suite **107 tests**, 9.835s, exit 0; all 86 previous regressions retained. Syntax/import and staged/unstaged whitespace PASS.
- PASS: 100 frozen-second copies; existing file/directory/dangling-symlink and publication-race preservation; 40 concurrent thread PNGs; four real separate processes/32 same-second copies; byte/pixel integrity; incomplete encode/missing source/write failure/no public partial; no staging leaks; all six save routes tested.
- PASS: 100 consecutive real production-controller screenshot operations with fixture portal replies, Qt heartbeat and actual offscreen clipboard pixels; ten asynchronous fixture OCR returns including English/Sinhala/ZWJ; repeat activation coalesces; one overlay; no stale path/text; cancel/failure/retry; no late OCR text or pending tasks; saved-source cleanup protection.
- PASS: actual default directory on ext4; additional same-filesystem isolated PNG publication check, no user screenshot writes. Unsupported hard-link filesystems fail cleanly, no unsafe fallback.
- NOT RUN: new physical GNOME rapid captures, Window picker cancellation/completion, external image/text paste, and physical Quit after the series. Offscreen MIME retrieval is not cross-process/native paste; fixture OCR is not recognition-accuracy evidence.
- Earlier isolated repetition test had offscreen Qt MIME-owner teardown exit 139 despite completed assertions; minimal plain Qt text-owner reproduced it. Test-owned MIME/deferred-widget cleanup fixed harness teardown; final tests exit 0. No production clipboard change.

User explicitly authorized this bounded Phase 2 task; no implied Phase 1 physical sign-off or Phase 2 overall completion. [Full inventory, evidence and minimum manual steps](phase-02-task-01.md).


## Phase 2 Task 2 — Display mapping (2026-11-14)

Phase 2 Task 1 is now **physically accepted**: user reports all six acceptance tests PASS. Earlier NOT RUN records are historical.

- PASS: 132-test full regression suite, 8.563s, exit 0; all prior 107 retained. Compile/import and both whitespace checks PASS.
- PASS: 25 new geometry/provider/session/controller cases; standard 100% and separate Qt 125/150/175/200% runs all PASS. Simulated compositor scales include all five factors; different resolutions/scales, left/right/above/below and negative origins, forward/reverse boundary drags, edges, invalid/gap areas, saved/copy PNG pixel accuracy, configuration changes, cancellation and fallback Full Screen tested.
- PASS: per-output source painting without global stretching; subpixel coordinates preserved; correct physical PNG dimensions in badge; origin/reverse QRect defects fixed. Toolbar classes/QSS byte-identical; protected clipboard/OCR/shortcut/tray/filename modules unchanged.
- PASS: native GNOME 50.1 Screenshot portal real dimensions/metadata and before/after geometry on one eDP-1 1920×1080 at GNOME 100%; correct output/fullscreen viewport and pixel box. Programmatic cancellation exits cleanly. Native Qt scale 125/150/175/200% changes viewport but preserves PNG dimensions and maps expected boxes once.
- NOT RUN: physical multiple monitors, actual GNOME fractional-scale changes, cross-output mouse dragging, newly repeated external screenshot/OCR paste, physical Escape/tray tests for Task 2. Native Qt scale probes are not OS fractional-scale acceptance. Current mode does not offer GNOME 175%; no settings changed or scale forced.
- Explicit limits: Rectangle requires verified GNOME 50 packing/metadata, logical-layout mode, matched outputs; cloned/overlapping/unknown layouts and native negative GNOME stage origins are refused. Negative Qt origins work by connector mapping. Layout-gap selections save nothing. Full Screen may retain genuine compositor gaps; source image and save behavior are preserved.

[Detailed strategy, file list, evidence and minimum physical gate](phase-02-task-02.md). No Task 3/Freeform/AI.


## Phase 2 Task 3 — Performance and long-run stability (2026-11-14)

User confirms Phase 1 accepted; Task 1 all six physical tests PASS; Task 2 all seven physical tests PASS on single-monitor 100%. Mixed-monitor/fractional physical checks remain pending.

- PASS: baseline 132 tests, 8.628s; final **145 tests, 17.455s, exit 0**. Syntax/import and staged/unstaged whitespace checks PASS.
- PASS: 50 alternating production Rectangle/Full Screen benchmark operations after three warmups; all distinct saved PNGs, no staging/orphan asyncio jobs. Public offscreen fixture only: selection-to-delivery median/p95 370.255/464.674 → 190.597/315.705 ms; clipboard 235.342/323.975 → 47.110/67.090 ms; maximum Qt heartbeat gap 514.882 → 76.901 ms. Portal fixture delay is not native latency; no OCR algorithm speedup claimed.
- PASS: one worker, GUI-thread geometry/clipboard; cancellation drains in-flight writes, rejects overlap and discards late clipboard/OCR results. Active/idle shutdown, late worker failure and retry tested. Initial worker shutdown hang detected and fixed; final tests exit normally.
- PASS: existing 100 screenshot/ten Unicode OCR callback series plus 50 launch/cancel cycles, 20 Window backend success/cancel cycles, failed/timeout portal fixtures and repeated activation. Saved pixel/Qt MIME integrity, original PNG byte reuse/source-deletion lifetime, non-PNG fallback, Sinhala/English punctuation/ZWJ transfer retained. These are simulated workflows, not physical keys, native picker acceptance or Sinhala recognition accuracy.
- PASS: real existing English OCR subprocess benchmark and process cancellation/error regressions. RSS 122976/128836/126588 KiB at warmup/10/50, FD counts 14/14/14 and native threads 8/8/8; exactly one Python file worker, joined at close. Qt native pool remains until process exit; no unbounded leak over 50 captures observed, no hours-long claim.
- PASS: read-only GNOME Shell 50.1 and Screenshot v2 inventory; one existing user app left untouched. No GNOME shortcut/permission/settings edits.
- NOT RUN: new physical Alt+Shift+S/Escape, native portal/permission timing, fresh cross-process external screenshot/OCR paste, actual Window picker, extended user capture series and physical Quit/restart on changed implementation. Previously accepted physical behavior is not silently re-signed off.

[Task report, full file list, exact commands, baseline/final measurements and minimum physical steps](phase-02-task-03.md). Task 3 awaits physical acceptance; no subsequent task, Freeform or AI begun.


## Background Service Stage 1 — manual user-session prototype (2026-11-14)

- PASS: 158 regressions, 18.400s, exit 0 (previous 145 +13 service tests); real systemd parser/special-character paths, session/environment/socket ownership checks, no-overwrite installation, manual-only/no-enable configuration, syntax/whitespace.
- PASS native: genuine user-manager start, existing manual-instance lock conflict with no duplicate/restart loop, repeated start same PID, stop during capture with complete cleanup, inactive beyond restart delay; injected SIGKILL recovery to a new PID in 3.296s/NRestarts=1; PID-verified tray protocol Quit remained inactive.
- PASS native: service under its own genuine app.slice cgroup, correct Wayland/runtime/session D-Bus environment, SNAP absent. Screenshot connection independently registered APP_ID and portal v2 returned response 0 using existing permission; no consent or settings automated.
- PASS native public-fixture probe in a separate transient user service: production Rectangle/Full Screen/repeat pixels and actual editor paste in two reader processes across focus changes; real English OCR and supplied Sinhala/ZWJ UTF-8 transfer; clean worker/session exit. Qt input is programmatic and backdrop is a fixture. First Unicode probe failed due to fixture patch lifetime, corrected and full rerun exit 0.
- Requested Alt+Shift+S preserved; actual GNOME Ctrl+Alt+S confirmed before/after via tray/ListShortcuts/ShortcutsChanged. Existing mismatch, no binding reset/change. Desired-key physical activation remains unverified.
- NOT RUN: physical key/Escape/tray, installed-service Rectangle/Window/OCR external paste, actual Window picker completion, logout/login, first-use consent and rate-limit exhaustion. Dependency/rate configuration tested; no physical or logout PASS inferred.
- Installed unit is static, not enabled. No XDG autostart/root service/lingering change. One service manually started for pending physical checks (last PID 79946); intentional Quit should leave it stopped. No further stage, Freeform or AI.

[Full report, modified files, commands, raw observations and rollback](background-service-stage-01.md).
