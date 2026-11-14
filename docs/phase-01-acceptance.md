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
