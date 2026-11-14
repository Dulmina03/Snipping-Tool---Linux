# Background service integration — Stage 1

2026-11-14, Ubuntu 26.04 / GNOME 50.1 / Wayland, systemd 259.9. **Prototype implemented; physical service acceptance pending. Login startup is NOT enabled.** Freeform is postponed; no AI work.

## Starting state and scope

Started with clean working tree and empty index on purpose-named branch `feat/background-service`, HEAD `8ca88fd`. Existing application-grid process PID 30510 was running in `app-gnome-com.dulmina.aisnippingtool-30510.scope`. No matching Snipping Tool XDG autostart entry or installed user service was found in the inspected user/system startup directories. The existing generated `.desktop` launcher is a manual `main.py` launcher, not an autostart mechanism.

Existing lifecycle was retained: hidden CaptureMenu, persistent QApplication/tray, QLockFile in XDG_RUNTIME_DIR, SIGTERM/SIGINT → QApplication.quit, capture-job/worker cleanup followed by shortcut-session shutdown and lock release. The GlobalShortcuts and Screenshot D-Bus connections register `com.dulmina.aisnippingtool` independently before portal methods. None of this production code was changed.

## Architecture

`systemd/com.dulmina.aisnippingtool.service.in` is generated for this checkout by `utils.user_service`. It uses the existing `.venv/bin/python -u main.py`, preserves the venv symlink path, quotes command arguments using systemd rules and sets the checkout WorkingDirectory. There is no shell wrapper, fork, root/system-wide service or packaging change.

- `Requisite=graphical-session.target` plus `After=` refuses a start outside the existing graphical session without pulling that target up. `PartOf=graphical-session.target` propagates session stop. This follows the [graphical-session guidance](https://www.freedesktop.org/software/systemd/man/latest/systemd.special.html) and [unit dependency semantics](https://www.freedesktop.org/software/systemd/man/latest/systemd.unit.html).
- `ExecCondition` checks GNOME/Wayland environment, non-root user, runtime ownership and live user-owned Wayland/session-bus sockets. Missing/stale environment skips with status 1. It does not create sockets, guess `wayland-0` or change permissions.
- The unit inherits WAYLAND_DISPLAY, XDG_SESSION_TYPE and XDG_CURRENT_DESKTOP from the GNOME user manager. It explicitly supplies XDG_RUNTIME_DIR=`%t`, DBUS_SESSION_BUS_ADDRESS=`unix:path=%t/bus` and QT_QPA_PLATFORM=`wayland`. No editor environment import, cgroup reassignment, sandbox spoofing or unrelated environment dump.
- `Restart=on-failure`, `RestartSec=3`, StartLimitBurst=3 within 60 seconds; clean exit does not restart, and explicit systemctl stop is not an automatic restart trigger. `KillMode=mixed` sends initial SIGTERM to main for orderly cleanup; remaining processes can be killed after TimeoutStopSec=30. [Service restart semantics](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html), [kill semantics](https://www.freedesktop.org/software/systemd/man/latest/systemd.kill.html).
- No `[Install]`, WantedBy, timer, socket activation or XDG autostart entry. The installed unit reports **static**. Stage 1 never runs `enable` or enables lingering. A future login-startup design needs separate authorization/acceptance.

Type=exec means the process executed, not that Qt/shortcut registration is already ready. Check journal/tray status too. If a manually launched instance already holds the lock, service startup exits 0 and becomes inactive; it does not adopt that existing PID or claim ownership. Starting an already-active service is idempotent. Manual app-grid startup remains unchanged and uses the same lock.

The installer only writes a unit. It is idempotent for identical content, rejects a differing existing unit or symlink, and publishes without replacing a racing/custom file. It never reloads, starts, enables or imports environment automatically. Generated installation paths stay out of the portable template.

## Installation and manual operation

Run as the logged-in desktop user, **without sudo**:

```bash
cd /home/dulmina/Projects/ai-snipping-tool
.venv/bin/python -m utils.user_service --print
.venv/bin/python -m utils.user_service --install
systemctl --user daemon-reload
systemd-analyze --user verify "$HOME/.config/systemd/user/com.dulmina.aisnippingtool.service"
```

The prototype has already been installed at `/home/dulmina/.config/systemd/user/com.dulmina.aisnippingtool.service`. If XDG_CONFIG_HOME is customized, installation uses its `systemd/user` directory; adjust the verification/rollback path accordingly. Quit an existing manually launched instance through the tray before transferring ownership:

```bash
systemctl --user start com.dulmina.aisnippingtool.service
systemctl --user status com.dulmina.aisnippingtool.service --no-pager
systemctl --user show com.dulmina.aisnippingtool.service -p MainPID -p NRestarts -p Result -p UnitFileState
journalctl --user -u com.dulmina.aisnippingtool.service -n 40 --no-pager
systemctl --user stop com.dulmina.aisnippingtool.service
```

No enable command is part of Stage 1. Tray Quit intentionally leaves the service stopped until a new explicit start.

If the condition skips for missing manager environment, first inspect from a **genuine GNOME Terminal**, not the VS Code integrated terminal:

```bash
systemctl --user show-environment | rg '^(WAYLAND_DISPLAY|DISPLAY|XDG_SESSION_TYPE|XDG_CURRENT_DESKTOP)='
```

Only if those values are missing/stale and the genuine terminal's values are correct:

```bash
systemctl --user import-environment WAYLAND_DISPLAY DISPLAY XDG_SESSION_TYPE XDG_CURRENT_DESKTOP
systemctl --user start com.dulmina.aisnippingtool.service
```

Never import the entire editor environment. No import was needed/performed on this host: manager environment already matched GNOME. This is a single-graphical-session prototype; multiple simultaneous graphical sessions for one UID are not supported by this manager-wide environment strategy.

## Observed verification

**PASS — 158 automated tests, 18.400s, exit 0:**

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
```

Run through the authorized host tool because the sandbox blocks temporary Unix socket binding/systemd parser operations. All prior 145 tests retained; 13 new cases cover unit/session/restart configuration, special-character paths with the actual systemd parser, venv selection, safe/idempotent installation, custom/symlink/racing-file preservation, failed publication cleanup, missing environment, stale sockets, root/foreign ownership, condition skip status and CLI print. These tests do not start host services or physically press keys.

**PASS — syntax/whitespace:** compileall of `utils/user_service.py`, `tests/test_user_service.py`, `tests/production_clipboard_probe.py`; `git diff --check` and `git diff --cached --check`. Host `systemd-analyze --user verify` accepts the installed unit. It warns about an unrelated pre-existing `spice-vdagent.service` StandardError key in [Install]; our unit verifies successfully.

**PASS — genuine user-manager lifecycle**, not physical tray/keyboard testing:

- Existing manual PID **30510** + manual service start: service child **73501** exited cleanly on QLockFile conflict, MainPID=0, NRestarts=0; original app remained. No duplicate persisted. Original instance then quit through its PID/app-ID-verified DBusMenu Quit action.
- Manual start: PID **74328**, active/running, static unit. Two more `systemctl --user start` calls retained PID 74328, NRestarts=0. Its genuine cgroup was `/user.slice/user-1000.slice/user@1000.service/app.slice/com.dulmina.aisnippingtool.service`.
- Actual service environment: WAYLAND_DISPLAY=wayland-0, runtime=/run/user/1000, session bus=unix:path=/run/user/1000/bus, XDG_SESSION_TYPE=wayland, desktop=ubuntu:GNOME, Qt=wayland; SNAP/SNAP_NAME absent. The agent itself remained in Snap VS Code's scope. The application was launched by the real user manager, not by changing or spoofing that scope.
- Tray Capture via PID-verified DBusMenu protocol invoked the real screenshot pipeline. Screenshot connection **:1.1481** registered the correct app ID, read Screenshot portal **v2**, called Screenshot with parent `''`, interactive=False, modal=True and received **response 0 with a local URI**. No permission was automatically granted/denied, no permissions reset, and no private screenshot content was collected. This tests existing granted permission compatibility, not first-use Allow/Deny or physical rectangle selection.
- `systemctl --user stop` during that capture session produced `aboutToQuit`, capture-job cleanup, shortcut portal cleanup and `Shutdown complete`. After 3.5s, inactive, MainPID=0, Result=success, NRestarts=0.
- Controlled unexpected crash: service PID **75868** received SIGKILL through `systemctl --user kill --kill-whom=main --signal=SIGKILL ...`; automatic recovery PID **75969** appeared in **3.296s**, NRestarts=1. Stale-lock recovery worked. This is an injected real process failure, not an observed spontaneous crash. Effective manager values confirm on-failure/3s/3-per-minute/30s-stop. The burst limit was inspected, not deliberately exhausted.
- Intentional Quit: PID 75969's tray Quit action activated through the verified protocol; full shutdown logged; after 3.5s inactive/MainPID=0/Result=success. No relaunch. Protocol activation is not a physical click.
- Normal startup is still hidden by existing regression contracts; no new main/status/capture window is requested by the service. Visual desktop inspection of idle startup is **NOT RUN**.

**PASS — native Qt Wayland public-fixture production workflow**, in a separate, collected transient user service, not the installed unit's unmodified runtime:

`tests/production_clipboard_probe.py` launches canonical main, actual per-output overlays, production post-capture handlers, worker/clipboard lifecycle and real English OCR. It substitutes a public backdrop and uses QTest mouse events; it is not physical input or the genuine portal selection journey. The probe unit inherits the same genuine user-manager GNOME environment; the installed unit was stopped so only one main instance owned the normal lock.

Final invocation `f339d2a7efd340128aae658b536fc443`, **exit 0**, 28.046s:

- Rectangle: valid **1181×301** PNG, exact pixels in two separate native reader processes, successful editor paste before/after focus change, live GUI heartbeat.
- Full Screen: **1920×1080**, identical checks PASS.
- Repeated Rectangle: fresh pixels and identical checks PASS.
- Real English OCR: correct public reference returned, exact UTF-8 retrieval and actual QTextEdit paste in two processes after focus changes PASS.
- Supplied Sinhala/English text with punctuation/ZWJ: exact UTF-8 and paste in both processes PASS. This is Unicode transfer, not Sinhala recognition accuracy.
- Quit/worker shutdown: PASS, global-shortcut thread no longer alive; probe and readers exited, transient unit collected.

An initial new-test run failed socket setup inside the sandbox; the host run exposed two real unit-generation quoting errors (WorkingDirectory quotes and dollar expansion in the executable word). Both were corrected and parser tests pass. The first native workflow run had Unicode FAIL because a helper adjustment restored the fixture patch before async saving reached OCR; the fixture scope was corrected, and the complete native probe passed on rerun. No production clipboard/OCR rewrite was used to hide that test failure. Evidence retains the distinction.

## Shortcut assignment and remaining blockers

**Requested remains Alt+Shift+S (`ALT+SHIFT+s`); actual GNOME assignment is Ctrl+Alt+S (`Press <Control><Alt>s`).** This mismatch existed on the original app-grid process before service testing and remained unchanged afterward. Native ListShortcuts and ShortcutsChanged both returned it; tray correctly displays it and identity Registered. No shortcut ID, registration code, binding settings or permissions were changed. ConfigureShortcuts remains disabled on portal v1.

- PASS: host registration, stable requested/actual reporting, existing real Screenshot permission.
- NOT RUN: physical Alt+Shift+S or current Ctrl+Alt+S activation, physical Escape/tray click, real Window picker completion, physical Rectangle/Window image paste and English text paste using the installed service.
- NOT RUN: genuine logout/login lifecycle. PartOf/Requisite semantics are configured and parser-tested; the user's GNOME session was not logged out for testing.
- NOT RUN: first-use permission Allow/Deny, deliberate rate-limit exhaustion, multiple simultaneous sessions, extended mixed-monitor/fractional acceptance. Existing capture/mapping tests pass; earlier physical acceptance is not silently re-applied to the service.

Do not claim the desired Alt+Shift+S binding is active. If the user wants to correct it, the previously verified GNOME route is **Settings → Apps → AI Snipping Tool → Permissions → Global Shortcuts → capture action → Set Shortcut**. The user must explicitly confirm the combination, and cancel/report any conflict; Stage 1 does not automate that change. Verify the new actual assignment through the tray/ListShortcuts before physically testing Alt+Shift+S.

Minimum physical gate: from another app, use the portal-assigned key → Escape; Rectangle → external image paste; Window picker → select a window → paste; Extract Text on public English → external paste; physical tray Quit. Confirm no duplicate/controller window and that service remains inactive after Quit. Then explicitly start it and repeat one capture. Actual logout acceptance can be performed on the user's next planned logout; do not log out merely to automate this task.

## Final runtime and rollback

After the native probe, the installed service was **manually started** with one main process, last observed PID **79946**, active/running, UnitFileState=static, NRestarts=0. No diagnostic service instance remains. If the user performs the pending Quit test, the expected final state changes to inactive; do not restart automatically to contradict intentional Quit.

Rollback only this prototype unit after reviewing that it is the generated Stage 1 file:

```bash
systemctl --user stop com.dulmina.aisnippingtool.service
cat "$HOME/.config/systemd/user/com.dulmina.aisnippingtool.service"
rm -- "$HOME/.config/systemd/user/com.dulmina.aisnippingtool.service"
systemctl --user daemon-reload
```

These rollback commands were documented, **not executed**. They do not remove the project, venv, screenshots, permissions, shortcut bindings or existing desktop launcher. Launch from GNOME's app grid afterward if desired. No disable command is needed because no enabling symlink was created.

## Files modified

- New `systemd/com.dulmina.aisnippingtool.service.in` — portable manual-only service template.
- New `utils/user_service.py` — generator, no-overwrite installer, stdlib-only session condition and CLI.
- New `tests/test_user_service.py` — 13 automated prototype tests.
- `tests/production_clipboard_probe.py` — wait for Full Screen asynchronous save, retaining the Unicode fixture through its async job.
- New `docs/background-service-stage-01.md` and `docs/background-service-stage-01-evidence.txt`; updated `docs/handoff-summary.md`, `docs/test-matrix.md`.
- Outside Git: generated `/home/dulmina/.config/systemd/user/com.dulmina.aisnippingtool.service`; daemon-reload/manual lifecycle operations only. Temporary PID-verified tray helper/logs in `/tmp`, no desktop/autostart changes.

Capture algorithms, main.py, approved toolbar, OCR engine, clipboard production code, shortcut registration and tray production code are unchanged. No staging, commit, merge, reset or push by the agent. Stage 1 only; do not enable startup, implement Freeform/AI or proceed to another stage without the next instruction.
