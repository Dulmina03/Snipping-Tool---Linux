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
