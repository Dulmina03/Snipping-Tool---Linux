# Background service Stage 2 — Automatic GNOME login startup

2026-11-14. **Configured and enabled; real logout/login/reboot acceptance is NOT RUN.** No logout or reboot was automated. Stage 1 is now physically accepted by the user: all six shortcut, Escape, Rectangle/paste, English OCR/paste, Window/paste and tray/Quit tests PASS.

## Initial configuration and Git safety

Stayed on the current `feat/background-service` branch throughout, starting at `a46732d` with clean tree and empty index. The existing installed unit was `/home/dulmina/.config/systemd/user/com.dulmina.aisnippingtool.service`, static/manual-only, running PID 79946. No matching XDG autostart entry or second persistent app service was found; the normal application-grid `.desktop` launcher was preserved.

Read-only native inspection confirmed GNOME 50.1, systemd 259.9, Wayland, both `gnome-session.target` and `graphical-session.target` active, and Linger=no. The user-manager environment already contained wayland-0, /run/user/1000, its session D-Bus socket, XDG_SESSION_TYPE=wayland and ubuntu:GNOME. No environment import was needed or performed.

## Session architecture

The same service has two explicitly generated profiles. The unchanged `systemd/com.dulmina.aisnippingtool.service.in` remains the Stage 1/manual template. `utils.user_service.service_unit(login_startup=True)` derives the login profile with these relationships:

```ini
[Unit]
Requisite=gnome-session.target
After=gnome-session.target
PartOf=graphical-session.target

[Install]
WantedBy=graphical-session.target
```

Installed GNOME target files establish `gnome-session.target` after `gnome-session-initialized.target` and before `graphical-session.target`, with BindsTo=graphical-session.target. The new ordering is GNOME readiness → app execution → graphical-session target, rather than retaining the manual profile's wait on the target now pulling the app in. Both a private prospective-enabled unit search tree and the actual enabled configuration passed systemd verification with no ordering-cycle diagnostic.

Requisite refuses a manual start when GNOME is not running without starting GNOME itself. PartOf propagates graphical-session stop. The user-manager target dependencies—not default.target, a terminal or a second autostart script—provide login startup. See [session target guidance](https://www.freedesktop.org/software/systemd/man/latest/systemd.special.html), [unit dependency/install semantics](https://www.freedesktop.org/software/systemd/man/latest/systemd.unit.html) and [target ordering rules](https://www.freedesktop.org/software/systemd/man/257/systemd.target.html).

All other Stage 1 settings remain: existing venv/main.py, hidden background application, owned session/runtime sockets checked by ExecCondition, QT_QPA_PLATFORM=wayland, stable desktop app ID, one-instance QLockFile, on-failure restart after 3s with three starts per minute, SIGTERM cleanup, mixed cgroup termination and 30s stop timeout. No root service or lingering. Type=exec reports process execution, not portal-registration readiness; inspect the tray/journal after asynchronous registration settles.

The installer still never enables/starts/reloads anything itself. `--login-startup` selects a profile; `--replace-known` explicitly permits migration only when the existing file exactly matches the other generated profile for this checkout. Differing custom units/symlinks are refused, even with a managed marker. Content is rechecked before atomic profile replacement. Tests cover an edit during preparation and cleanup of its own staging file. The manual profile remains available for rollback without removing Stage 1.

## Exact installation and activation commands

The following sequence was performed as the desktop user, without sudo. Manual lifecycle/dependency/registration checks passed before the first enable command:

```bash
cd /home/dulmina/Projects/ai-snipping-tool
.venv/bin/python -m utils.user_service --print --login-startup
.venv/bin/python -m utils.user_service --install --login-startup --replace-known
systemctl --user daemon-reload
systemd-analyze --user verify "$HOME/.config/systemd/user/com.dulmina.aisnippingtool.service"
systemctl --user is-enabled com.dulmina.aisnippingtool.service
systemctl --user stop com.dulmina.aisnippingtool.service
systemctl --user start com.dulmina.aisnippingtool.service
systemctl --user status com.dulmina.aisnippingtool.service --no-pager
```

At that checkpoint UnitFileState was **disabled**, not enabled. Repeated starts, actual portal registration/capture, clean stop and crash recovery were then verified. Only afterward:

```bash
systemctl --user enable com.dulmina.aisnippingtool.service
```

This created exactly the app's link:

`~/.config/systemd/user/graphical-session.target.wants/com.dulmina.aisnippingtool.service`

pointing to the existing installed unit. No `default.target.wants`, XDG autostart file, service alias or additional persistent service was created. No unrelated startup entries needed removal.

## User commands

Status and logs:

```bash
systemctl --user status com.dulmina.aisnippingtool.service --no-pager
systemctl --user is-enabled com.dulmina.aisnippingtool.service
systemctl --user show com.dulmina.aisnippingtool.service -p MainPID -p NRestarts -p Result -p WantedBy
journalctl --user -u com.dulmina.aisnippingtool.service -n 50 --no-pager
```

Enable startup (without starting now), disable startup (without stopping now), and explicit current-session controls:

```bash
systemctl --user enable com.dulmina.aisnippingtool.service
systemctl --user disable com.dulmina.aisnippingtool.service
systemctl --user start com.dulmina.aisnippingtool.service
systemctl --user stop com.dulmina.aisnippingtool.service
systemctl --user restart com.dulmina.aisnippingtool.service
```

`disable --now` both disables later-login startup and stops now; `enable --now` enables and starts now. Tray Quit and `stop` leave the enabled preference intact but do not relaunch in the current session. An explicit restart closes the old process/session before starting the replacement. If the configured failure limit is reached, inspect the cause before using `systemctl --user reset-failed com.dulmina.aisnippingtool.service` and starting again. No rate-limit reset was needed during this task.

## Tested rollback — preserves Stage 1

These commands were actually exercised while the app was inactive, then Stage 2 restored. They remove only the login link and restore the original manual profile, not the application or unit:

```bash
cd /home/dulmina/Projects/ai-snipping-tool
systemctl --user stop com.dulmina.aisnippingtool.service
systemctl --user disable com.dulmina.aisnippingtool.service
.venv/bin/python -m utils.user_service --install --replace-known
systemctl --user daemon-reload
systemctl --user is-enabled com.dulmina.aisnippingtool.service
```

The rollback returned **static**, Requisite/After=graphical-session.target, PartOf=graphical-session.target. The Stage 1 service could still be started manually. The subsequent Stage 2 restore used `--install --login-startup --replace-known`, daemon-reload, enable and start. It returned enabled with the GNOME session relationships above. For merely disabling login startup, no profile rollback is required.

## Verification results

**PASS — automated:** 164 tests, **18.286s**, exit 0:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
```

Authorized host execution is needed for the temporary Unix sockets/real systemd parser used by Stage 1 tests. All previous 158 retained; six added tests cover login relationships, explicit migration and rollback, preserving user customization/concurrent preparation edits, prospective enabled dependency verification and CLI/profile option validation. Focused service suite: 19 tests, 0.651s, exit 0. These tests do not enable host units or simulate a real login.

**PASS — syntax/whitespace:** compileall of `utils/user_service.py` and `tests/test_user_service.py`; staged/unstaged `git diff --check`. Host `systemd-analyze --user verify` accepted the installed enabled unit. The pre-existing unrelated `spice-vdagent.service` [Install]/StandardError warning remains; no edit was made to that unit.

**PASS — actual user-manager/service lifecycle, before enablement:**

- Upgraded the known installed Stage 1 profile without enabling; stopped original PID 79946 cleanly.
- Manual start PID **103043**; two repeated start commands retained the same PID and NRestarts=0, UnitFileState=disabled.
- `gio launch ~/.local/share/applications/com.dulmina.aisnippingtool.desktop` exited 0 with the existing-instance message; service PID unchanged, one main.py process. This uses the real normal launcher programmatically, not a physical app-grid click.
- PID-verified tray inspection: Application identity Registered, requested ALT+SHIFT+s, actual **Press <Control><Alt>s**, from ListShortcuts/ShortcutsChanged. No shortcut setting changed.
- PID-verified tray Capture protocol invoked the real Screenshot request. Connection **:1.2131** registered the correct app ID, read Screenshot v2, sent parent `''`, interactive=False/modal=True, and received response **0**. Existing permission worked; no Allow/Deny or permission reset was automated. No screenshot contents were collected.
- Stopped during that capture session; aboutToQuit, capture/shortcut cleanup and Shutdown complete logged. Still inactive/MainPID=0/Result=success after 3.5s, with startup disabled.
- Controlled unexpected SIGKILL of PID **103916** recovered as PID **103994** in **3.301s**, NRestarts=1, one process. This is an injected crash, not a claim of spontaneous failure. Registry/actual assignment remained correct afterward.

**PASS — activation, disable and rollback:**

- Enabled only after those checks; real manager reported WantedBy=graphical-session.target and the sole app-specific enabling link.
- Invoked the enabled service PID 103994's tray Quit through PID/app-ID-verified DBusMenu protocol. After 3.5s: **inactive, MainPID=0, Result=success, UnitFileState=enabled**. The live graphical target did not resurrect it. This is protocol activation, not a physical click.
- Disabled it: link removed, UnitFileState=disabled. Restored Stage 1: static. Restored Stage 2: disabled before re-enabling. No unit/app file was removed and no unrelated service altered.
- Final re-enable/start PID **106899**; explicit `systemctl --user restart` cleanly replaced it with **107521**, active/enabled, NRestarts=0, exactly one main.py. Portal identity and actual assignment were verified again.
- One tray diagnostic immediately after restart encountered a stale old SNI name (`NameHasNoOwner`); retry after asynchronous unregister/register settled succeeded. This was a test-helper query race, not an app restart failure. No production code changed for it.

**PASS — native Qt Wayland public-fixture production workflow:** reused the existing collected transient test unit `snipping-stage01-workflow-probe.service`, with After/Requisite=gnome-session.target and PartOf=graphical-session.target. The installed application unit was inactive during the test, so no duplicate normal instance. No second persistent startup unit was installed.

Invocation **52df3703810546338300d69785cc2b73**, exit 0, **27.452s**:

- Rectangle and repeated Rectangle: saved 1181×301 PNG pixel integrity, exact cross-process PNG equality and successful editor paste in two separate readers before/after focus change.
- Full Screen: same checks at 1920×1080.
- Existing real English OCR: expected public reference, exact UTF-8 retrieval and actual editor paste in both reader processes.
- Supplied Sinhala/English punctuation/ZWJ: exact UTF-8 and paste in both processes. Transfer compatibility, not Sinhala recognition accuracy.
- GUI heartbeat, complete shutdown and stopped shortcut thread PASS. Test readers/probe exited and transient unit was collected.

The backdrop and mouse input are fixtures/QTest; the English OCR and native Wayland transfer are real. These are not physical capture/global-key tests or a real Window picker. Mocked Window success/cancellation, mapping, repeated saves, clipboard lifetime and worker cleanup remain covered by the full regression suite. Stage 1's six physical passes are user-reported acceptance for its version; they are not silently relabeled as Stage 2/login observations.

## Final enablement and environment

Last verified installed service: **enabled, active/running, PID 107521, Result=success, NRestarts=0**, one main.py. No probe app remained. Linger=no. Actual service environment: WAYLAND_DISPLAY=wayland-0, XDG_RUNTIME_DIR=/run/user/1000, session bus=unix:path=/run/user/1000/bus, XDG_SESSION_TYPE=wayland, XDG_CURRENT_DESKTOP=ubuntu:GNOME, QT_QPA_PLATFORM=wayland, SNAP absent. Genuine service cgroup remains `app.slice/com.dulmina.aisnippingtool.service`; editor Snap scope was not spoofed or imported.

**Requested Alt+Shift+S; actual Ctrl+Alt+S.** The tray reports the effective assignment. Stage 2 did not change the user's binding; do not assume Alt+Shift+S works. No ConfigureShortcuts call, binding reset or permission edit.

## NOT RUN — physical session acceptance

No logout/reboot or real login event was synthesized or performed. Unit-graph validation and manual starts are not real login verification.

At the user's next planned logout/login:

1. With startup enabled, log out normally and log back in without opening a terminal or clicking the app launcher. Expect a quiet background app/tray, no controller/overlay/status popup and one instance. Use the actual assigned key (currently Ctrl+Alt+S) → Escape; then Rectangle/image paste, Window picker/image paste and English OCR/text paste in another app.
2. Physically choose tray Quit. Expect it to stay stopped for the rest of that session. On a later planned login, expect it to start again because enablement persists.
3. To test disabling, run `systemctl --user disable --now com.dulmina.aisnippingtool.service` before another planned logout. Next login should have no app instance until manually launched. Restore with `systemctl --user enable --now com.dulmina.aisnippingtool.service` when desired.
4. Optional future reboot check: at the user's convenience, verify the same enabled login behavior. No reboot is necessary solely to complete today's implementation.

Record PASS/FAIL for quiet automatic login startup, clean logout, next login after Quit, disabled next login, physical shortcut/Escape/tray and real Rectangle/Window/OCR external paste. These remain NOT RUN for Stage 2 until observed. First-use portal consent, deliberate rate-limit exhaustion, multiple simultaneous graphical sessions and long-run physical mixed-monitor checks also remain outside today's verified results.

Known limitations: development checkout/venv absolute paths must remain available; moving the checkout requires reviewed regeneration (installer refuses an unknown old/custom profile). User-manager environment is shared for one UID, so multiple simultaneous desktop sessions are unsupported. Missing/stale GNOME environment causes a clean ExecCondition skip, not guessed display settings or automatic editor-environment imports. Restart rate limiting can require investigation/manual recovery after repeated failures. No hours-long/real-login reliability claim is made from these bounded checks.

## Files modified and scope

- `utils/user_service.py`: opt-in login profile, explicit exact-profile replacement/rollback, CLI validation; installer still does not enable anything itself.
- `tests/test_user_service.py`: six new Stage 2 cases, prior 13 retained.
- `docs/background-service-stage-02.md`, `docs/background-service-stage-02-evidence.txt`: new report/evidence.
- `docs/background-service-stage-01.md`: latest user physical acceptance note; older observations retained.
- `docs/handoff-summary.md`, `docs/test-matrix.md`: latest configuration, acceptance and verification status.
- Outside Git: updated the existing `~/.config/systemd/user/com.dulmina.aisnippingtool.service` and created its single graphical-session enabling link. No other persistent startup unit/autostart entry or normal launcher was modified.

Main, capture/coordinate algorithms, toolbar, OCR, clipboard, shortcut/tray implementations and manual service template are unchanged. Stayed on the user's current branch; no staging, commit, merge, reset, push or branch switch. Stage 2 only. Freeform remains postponed; no AI or packaging.

Final Git provenance check: an external commit **4136879** (`Implement Background Service Stage 2 with GNOME login profile support`) appeared during final verification and was preserved. The agent did not create that commit or stage files. Branch remained `feat/background-service`; final observed service state remained enabled/active, PID 107521, NRestarts=0, Linger=no.
