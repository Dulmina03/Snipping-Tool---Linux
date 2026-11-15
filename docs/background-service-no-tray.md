# Background service — application indicator removed

2026-11-15. Bounded follow-up on `feat/background-service`, initial HEAD `67789bd`, clean working tree and index. The user switched from main before implementation. No branch changes, staging, commits, resets, merges or pushes by this agent.

The GNOME top-bar application indicator was `QSystemTrayIcon` created and shown by `main.configure_application()`. Its context menu and tray-triggered `ShortcutStatus` object are no longer constructed. This removes only this application's StatusNotifierItem. GNOME screenshot/screen-sharing privacy indicators and other applications' indicators are untouched.

`QApplication.setQuitOnLastWindowClosed(False)` stays explicit. The hidden CaptureMenu, shortcut manager, owned jobs and Qt event loop stay alive without a window or tray. The global Activated signal still calls the same overlay route. Identity and registration failures now also reach the application journal; the portal manager continues logging requested versus actual assignment. There is no replacement startup popup or notification. Registration failure has no tray fallback: inspect the journal and correct the desktop/portal problem before retrying the service.

SIGTERM still invokes QApplication.quit; aboutToQuit cancels capture work, and final cleanup drains jobs, closes the portal session, stops its thread and unlocks the single-instance lock. Restart=on-failure, session dependencies and enablement are unchanged. Intentional service stop exits normally; a later login starts it again while enabled. No desktop permissions or shortcut bindings were changed. Capture algorithms, toolbar, image/text clipboard and OCR code are unchanged. The existing Debian artifact has not been rebuilt or installed and still contains the old tray behavior.

## Control without a tray

Run in a terminal in the logged-in GNOME session, without sudo:

```bash
systemctl --user start com.dulmina.aisnippingtool.service
systemctl --user status com.dulmina.aisnippingtool.service --no-pager
systemctl --user restart com.dulmina.aisnippingtool.service
systemctl --user stop com.dulmina.aisnippingtool.service
journalctl --user -u com.dulmina.aisnippingtool.service -n 60 --no-pager
# Stop now and disable future login startup (only if desired):
systemctl --user disable --now com.dulmina.aisnippingtool.service
# Restore login startup and start now (only if desired):
systemctl --user enable --now com.dulmina.aisnippingtool.service
```

Only start/stop/restart were exercised by this task; enablement was preserved, not toggled. Do not use the historical tray Quit instructions below older service reports. Check the journal's `Shortcut requested=…; actual=…` record for the desktop-assigned key, rather than assuming the requested Alt+Shift+S was granted. To roll back this source change, review/revert only its diff with explicit Git authorization; do not reset unrelated changes or reinstall the older .deb over this development service.

## Changed files

- `main.py`: remove icon renderer, QSystemTrayIcon, menu and status presenter creation, tray cleanup; keep two owned runtime objects and journal reporting.
- `tests/test_phase01.py`: trayless routing/quiet startup assertions, no tray child/status presenter, new real Qt event-loop child process proving last-window close does not exit; existing real main.py SIGTERM/duplicate/restart coverage retained.
- `tests/test_screenshot_permission.py`: replace obsolete tray Quit-action test with pending-capture cancellation/worker cleanup through the trayless controller.
- `tests/test_shortcut_assignment.py`: retain all assignment/formatting/error/UI tests; construct legacy presentation explicitly with a mocked tray, outside production. `ui/shortcut_status.py` is preserved but unused by main.py; no application tray or dialog is created by those tests' setup.
- `tests/production_clipboard_probe.py`: actual production initializer now returns controller/manager only; the native probe shuts down through QApplication.quit rather than an obsolete tray action.
- `test_global_shortcut.py`: manual physical-key harness updated for the two-object initializer and service-based control.
- This report, `docs/background-service-no-tray-evidence.txt`, Stage 1/2 report pointers, handoff and test matrix.

## Verification results

- **PASS — full regression:** `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v`: **192 tests in 21.786s**, including quiet startup, routing, cancellation, mapping/pixel output, saving, OCR/clipboard, duplicates, real main.py SIGTERM/restart and new last-window lifetime regression. No screenshot/lifecycle coverage was dropped to accommodate tray removal. Intermediate host run before the added lifetime test passed 191 in 20.504s.
- **FAIL — restricted sandbox run:** 191 tests ran with four local socket permission errors and two systemd parser permission failures. The same suite passed with authorized host access; these were environmental failures, not hidden passes.
- **PASS — native GNOME protocol:** old PID88627 owned `:1.2482@/StatusNotifierItem`; updated PIDs121445/121573 owned no registered StatusNotifierItem. Four unrelated notifier items remained unchanged. This establishes removal at the desktop protocol level, not physical visual confirmation.
- **PASS — native identity/shortcuts:** same desktop application ID successfully registered; CreateSession, BindShortcuts and ListShortcuts responses code0. Requested **Alt+Shift+S**, actual **Ctrl+Alt+S**, unchanged. No unsupported ConfigureShortcuts call or settings/permission reset.
- **PASS — native service lifecycle:** start and repeated start keep one PID; one deliberate SIGKILL recovered automatically after RestartSec (PID121445→121550, NRestarts1). Explicit restart exited the updated process cleanly, logged aboutToQuit, jobs/session cleanup and Shutdown complete, then registered PID121573. Normal stop also remained inactive past RestartSec, with enablement preserved. Final explicit start restored PID122672, enabled/active, Result=success/NRestarts0; updated-source stop stayed inactive with Result=success for four seconds before that start. No persistent unit/environment/autostart changes.
- **PASS — native programmatic production workflows:** Rectangle, Full Screen, repeated Rectangle, actual English Tesseract OCR, and supplied Sinhala/ZWJ transfer all passed saved PNG integrity and two separate clipboard readers/paste across focus changes. Actual GUI event loop stayed alive; native probe exited0, shortcut thread stopped. Supplied Sinhala transfer is not a Sinhala OCR accuracy test. These are production-handler/QTest/public-fixture checks, not physical keyboard input or real Window selection.
- **PASS — syntax/imports and whitespace:** changed Python modules compiled; full suite imports passed; `git diff --check` clean. Existing `.deb` SHA256 remains `39a189ad278921cd68cd68b9caf86f027b64659dca609f1b7193c433e1c2e2eb`.
- **NOT RUN — new-version physical acceptance:** actual shortcut activation, visual top-bar/quiet-start check, physical Escape, Rectangle/Window/paste/OCR, clean logout and reboot. Existing automated Window success/cancel and synthetic Escape regressions passed; physical equivalents are separate.

[Command/results and native protocol evidence](background-service-no-tray-evidence.txt). Native probes used the existing service and a temporary genuine user unit; no root service, package installation or GNOME security bypass.

## Remaining physical acceptance

No physical keypress, GNOME top-bar visual inspection, Window picker, logout or reboot is claimed from programmatic tests. On the running service:

1. Confirm the AI Snipping Tool application icon is absent and startup produces no window/notification. GNOME's own permission/privacy indicators remain legitimate.
2. Focus another app. Press the actual journal-reported shortcut (currently Ctrl+Alt+S); confirm toolbar, Escape, rapid reopen and repeated Rectangle capture/paste. Test Window picker/cancel and image paste; English Extract Text and external text paste.
3. Use service stop; confirm no spontaneous relaunch. Start/restart and repeat the key/overlay check.
4. At the next convenient normal logout/login and reboot, confirm quiet automatic startup, no application icon and working capture. No automated logout/reboot is performed by this task.

Record these as NOT RUN until observed. Earlier accepted versions' physical results do not establish acceptance of this change. No AI, Freeform or packaging work is included.
