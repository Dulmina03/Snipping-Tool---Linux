# Stage 3.3 — clean GNOME installation acceptance

2026-11-15. **Physical acceptance NOT RUN: no ready disposable Ubuntu GNOME Wayland guest was found. Not ready for external beta distribution.** This stage prepares the exact test procedure; it does not turn Stage3.2's headless passes into graphical acceptance.

## Environment and actions actually observed

- Checkout stayed on `feat/background-service`, initial HEAD6096a74, clean working tree/index. No branch creation/switch, stage, commit, merge, reset or push by this agent.
- Host is the accepted Ubuntu26.04 development desktop, **not** the clean-install target. Its service remained enabled/active PID138240, invocation7664161b8879476e94e3f1e85f40ebe6, user FragmentPath `/home/dulmina/.config/systemd/user/com.dulmina.aisnippingtool.service`. Unit SHA2565212c21af2e8ac203bf51d352bd3b7d50bcdcafca783090a6e2bafe9682e06ce and desktop SHA256f7d6857517d07e3df9e7abf8ea49507cc6d6f08bd914321b2b6258a873417ce5 match Stage3.2. No host service/package/permission/binding changes.
- QEMU executable exists, but `/dev/kvm` is absent. No ready guest process, ISO or virtual disk was found in the checked Downloads, VirtualBox, Boxes and libvirt locations. Docker's configured desktop-linux daemon socket is absent. No virt-manager/virsh/Boxes/VirtualBox manager was found in PATH. This inventory is scoped, not proof that every storage location lacks a VM. Software emulation could be prepared later; it is not an existing graphical acceptance environment.
- No native GNOME keyboard/tray/window-control interface is available for conducting physical guest interaction here. No synthetic key/clipboard event was labeled physical.
- **PASS this stage:** original artifact SHA and archive validator (metadata/launcher version, ownership/modes, MD5, no development paths, source exclusions, desktop/SVG/syntax). **NOT RUN this stage:** install/APT, guest runtime, physical checks below. No production code changed, so the prior198-test suites were not rerun merely for documentation. Their Stage3.2 results remain historical:198 development/198 Ubuntu system stack PASS; isolated clone install/upgrade/remove/purge PASS, not clean GNOME.

## Candidate and files to transfer

Use only:

`dist/stage-03.2-validated/ai-snipping-tool_0.3.2~stage3.2-1_amd64.deb`

Version0.3.2~stage3.2-1; amd64;54,072bytes; SHA256 **fe18304aa2108689661ed4a67a76417eb1f03d4bb9c090a22b2d889742d69005**.

Do not use similarly named earlier Stage3.2 iteration directories. Do not share/mount the checkout, `.venv`, developer HOME, session D-Bus socket or runtime directory with the guest. Disable shared host/guest clipboard for these tests; clipboard success must be between guest applications.

Optional upgrade-only input: retained `dist/stage-03.1-final/ai-snipping-tool_0.3.1~stage3.1-1_amd64.deb`, SHA25639a189ad278921cd68cd68b9caf86f027b64659dca609f1b7193c433e1c2e2eb. Keep it out of the initial new-user path.

## Prepare a disposable desktop guest — instructions only

Use a dedicated VM host with an already configured hypervisor (or another test machine), not a second user account on the accepted development host. No hypervisor installation, disk creation, ISO download or VM boot was performed by this task.

1. Download the **Ubuntu26.04.1 Desktop AMD64** image and matching SHA256SUMS/signature from the [official26.04 release directory](https://releases.ubuntu.com/26.04/). It lists `ubuntu-26.04.1-desktop-amd64.iso`; use Desktop, not Server/WSL. Authenticate the checksum file following [Ubuntu's verification guide](https://ubuntu.com/tutorials/how-to-verify-ubuntu). Do not ignore signature/checksum failures.
2. Create a fresh VM named `ai-snipping-stage33`, with4 virtual CPUs,8GiB RAM,40GiB virtual disk, NAT networking and a graphical console. These are proposed test allocations, not claimed official minima. Use a virtual GPU supported by that hypervisor's GNOME Wayland guest; graphics acceleration if supported. Do not pass through a physical system disk.
3. Boot the ISO, install only onto the disposable virtual disk, create a normal user `sniptest`, complete installation, detach ISO and boot the installed desktop. Use GNOME's standard Wayland session. Do not configure X11 as a fallback acceptance target.
4. In the **guest's graphical Terminal**, record:

```bash
cat /etc/os-release
dpkg --print-architecture
printf 'Session=%s Desktop=%s\n' "$XDG_SESSION_TYPE" "$XDG_CURRENT_DESKTOP"
loginctl show-session "$XDG_SESSION_ID" -p Type -p Desktop
python3 --version
gnome-shell --version
```

Proceed only with Ubuntu26.04/amd64 and a genuine GNOME **wayland** session. If the hypervisor cannot provide that, record the environment blocker; do not report an X11/container/nested mock pass. Snapshot the VM as `clean-gnome-before-snipping` before installing the application.

### Package transfer — no source access

Use the hypervisor's file-transfer facility for **only the selected .deb**, or copy it via removable media to `~/Downloads` in the guest. Avoid a shared source folder or shared clipboard. Verify its SHA inside the guest before installation.

For QEMU's default user-mode NAT specifically, a temporary localhost-only transfer server is an alternative. These are **unexecuted instructions**; the server serves only a new package-only directory and is stopped with Ctrl+C. If the VM is on another machine, first copy the one .deb to that VM host using a removable medium/file transfer; substitute that local file in `cp`.

On the machine actually running the QEMU guest:

```bash
mkdir -p /tmp/ai-stage33-package-transfer
cp --no-clobber /home/dulmina/Projects/ai-snipping-tool/dist/stage-03.2-validated/ai-snipping-tool_0.3.2~stage3.2-1_amd64.deb /tmp/ai-stage33-package-transfer/
sha256sum /tmp/ai-stage33-package-transfer/*.deb
python3 -m http.server 8765 --bind 127.0.0.1 --directory /tmp/ai-stage33-package-transfer
```

In the QEMU guest, [default user-mode networking](https://www.qemu.org/docs/master/system/devices/net.html) provides the virtual host at10.0.2.2; default SLIRP host-loopback access permits this localhost transfer. Other hypervisors use different addresses; do not assume this for them.

```bash
cd "$HOME/Downloads"
wget http://10.0.2.2:8765/ai-snipping-tool_0.3.2~stage3.2-1_amd64.deb
printf '%s  %s\n' fe18304aa2108689661ed4a67a76417eb1f03d4bb9c090a22b2d889742d69005 ai-snipping-tool_0.3.2~stage3.2-1_amd64.deb | sha256sum -c -
```

Use a fresh Downloads directory/filename; do not install a suffixed stale download. Stop the server after transfer. No server or transfer was started by this task. No screenshots/documents are uploaded.

## Installation through APT — guest only, NOT RUN

Use networked APT in the disposable guest to validate the dependency resolver/download/configuration, unlike the prior offline namespace test:

```bash
cd "$HOME/Downloads"
sudo apt update
apt-cache policy python3 python3-pyside6.qtcore python3-pyside6.qtgui python3-pyside6.qtwidgets python3-pil python3-dbus-next python3-packaging tesseract-ocr tesseract-ocr-eng tesseract-ocr-sin xdg-desktop-portal xdg-desktop-portal-gnome qt6-wayland libglib2.0-bin systemd
sudo apt install ./ai-snipping-tool_0.3.2~stage3.2-1_amd64.deb
```

If Universe is not enabled and candidates are missing, enable Universe **inside the VM only**, then apt update and inspect policy again. Record locally missing versus unavailable packages separately. Do not use pip, `--force-depends`, or mix another Ubuntu release's archives. Offline alternative requires a complete pre-supplied dependency bundle; see Stage3.2. Normal APT dependency installation on a clean guest is still NOT RUN.

As `sniptest` (never sudo for the GUI), inspect:

```bash
ai-snipping-tool --version
command -v ai-snipping-tool
head -n 1 /usr/bin/ai-snipping-tool
dpkg --verify ai-snipping-tool
dpkg --audit
python3 --version
python3 -c 'from PySide6 import __version__; import PIL, dbus_next; print("PySide6", __version__, "Pillow", PIL.__version__)'
tesseract --version
tesseract --list-langs
cat /usr/share/applications/com.dulmina.aisnippingtool.desktop
cat /usr/lib/systemd/user/com.dulmina.aisnippingtool.service
test -f /usr/share/icons/hicolor/scalable/apps/com.dulmina.aisnippingtool.svg
test ! -w /usr/lib/ai-snipping-tool/main.py
grep -R -nF /home/dulmina /usr/lib/ai-snipping-tool /usr/bin/ai-snipping-tool /usr/lib/systemd/user/com.dulmina.aisnippingtool.service /usr/share/applications/com.dulmina.aisnippingtool.desktop
```

Expected: installed command `/usr/bin/ai-snipping-tool`, `/usr/bin/python3` shebang, Python3.14, Qt>=6.10, Pillow>=12, `eng` and `sin` listed, no dpkg integrity/audit errors, no developer path matches (grep exit1 for no matches). The service/desktop/app identity is `com.dulmina.aisnippingtool`; installed Exec/WorkingDirectory refer only to `/usr`, no `.venv` or source checkout. Models come from Ubuntu resources; no recognition-accuracy claim follows from listing Sinhala data. Record actual versions rather than substituting the development host's versions.

## First run and explicit per-user activation

**Confirmed from package contents, not physically executed:** installation installs files but neither starts nor enables the app. There are no package activation scripts, global presets or XDG autostart entry. Each account must opt in explicitly. Opening the app-grid entry alone runs a quiet manual instance; it does not enable login startup.

For the clean-user acceptance path, **activate the service before launching from the grid**, so the hidden process has a clear stop/restart owner and the grid test exercises duplicate prevention. In the guest's genuine GNOME Terminal:

```bash
systemctl --user daemon-reload
systemctl --user show com.dulmina.aisnippingtool.service -p FragmentPath -p DropInPaths
ai-snipping-tool --check-session
```

Require FragmentPath `/usr/lib/systemd/user/com.dulmina.aisnippingtool.service`, no unexpected drop-ins, and a successful session check. If a development/user override is present, stop this procedure and investigate the VM setup; do not remove another installation. Then:

```bash
systemctl --user enable --now com.dulmina.aisnippingtool.service
systemctl --user status com.dulmina.aisnippingtool.service --no-pager
systemctl --user show com.dulmina.aisnippingtool.service -p MainPID -p ActiveState -p UnitFileState -p Result -p NRestarts
journalctl --user -b -u com.dulmina.aisnippingtool.service -n 100 --no-pager
```

Enable affects only `sniptest`. Wait for successful host Registry identity and actual shortcut assignment from Bind/List, not just service active. Bounded startup recovery can take up to roughly3minutes if the portal is recovering; failure is a diagnostic result, not a reason to loop registration or reset GNOME settings. If the user manager's session environment is missing, inspect its five relevant variables and GNOME logs; log out/in normally instead of guessing/importing editor environment.

**Prototype usability limitation:** activation/control requires these explicit terminal commands; there is no tray and no graphical onboarding/service-enable action. If the grid was already launched before activation, do not start competing instances or use indiscriminate pkill. In this clean VM, log out/in with startup still disabled, verify no old instance remains, then activate as above. Evaluate this documented setup with the new user; no new onboarding feature was added in this task.

Use service `stop`/`start`/`restart` without sudo for control. `disable --now` stops now and disables future login startup for this user. A normal stop stays stopped for the session, but an enabled service is expected to start at a later login.

## Permissions and shortcut behavior — observed fields pending

App IDcom.dulmina.aisnippingtool; action IDopen_capture_menu; requested **Alt+Shift+S**. **New user's actual binding: NOT RUN/unknown**. The development host's Ctrl+Alt+S assignment is not a prediction for a fresh account. Read the real assigned trigger in the guest journal. A different key is a recorded mismatch; never silently edit/reset it or report the requested key as active.

If GNOME offers a binding/permission dialog, the tester must interact with it normally. ConfigureShortcuts is unsupported on the previously observed v1 portal; do not invoke unsupported methods. Only use GNOME's binding UI if it is actually available and the test user explicitly chooses a change. Report a conflict or missing configuration path as such.

On first capture, GNOME may need the app focused to show screenshot consent. If the app opens **Screenshot permission — AI Snipping Tool**, click **Continue**, then physically choose **Allow** in GNOME if desired. This deliberate recovery UI is distinct from an unwanted permanent controller window. Record whether a dialog appeared, exact response/error, and whether capture succeeds afterward. No dialog does not automatically mean a failure. Do not reinterpret every error/response2 as explicit cancellation or change permissions with a database tool.

Ensure physical shortcut input reaches the **guest**, not a host shortcut handler. Use the hypervisor's supported keyboard capture; if the host intercepts the key, record NOT RUN/input limitation. Do not disable the accepted host shortcut or replace the key with a synthetic portal signal.

## Physical acceptance ledger — all NOT RUN

Use guest-only external receiver apps, e.g. LibreOffice Draw for image paste and Writer for text. If absent, `sudo apt install libreoffice-draw libreoffice-writer` **in the VM only**, recorded as test tools, not application dependencies. Keep host/guest clipboard sharing off. Use public text such as “Offline English screenshot test 123.” in large black type on white; save no private desktop screenshots to shared evidence.

1. **NOT RUN — GNOME app-grid launch.** With service active, press Super, search AI Snipping Tool and launch it. Expect no persistent window/icon/menu, correct installed launcher, same service MainPID and no second lasting instance. This verifies service-owned launch/duplicate handling; an independent grid-owned daemon start is not claimed.
2. **NOT RUN — screenshot permission.** First physical capture, observe GNOME consent/recovery as above, explicitly grant if presented and record outcome. No automated Allow/Deny.
3. **NOT RUN — physical global key.** Focus another guest app, press actual assigned key; observe only selection overlay/toolbar, correlate with guest activity and record requested/assigned values and conflicts.
4. **NOT RUN — Rectangle/paste.** Capture a distinctive public rectangle, paste into guest Draw with physical Ctrl+V. Confirm correct pixels/area and saved PNG in `~/Pictures/Screenshots`. Repeat with visibly different content to rule out stale clipboard.
5. **NOT RUN — Window/paste.** Click Window, choose a guest window using GNOME's interactive picker, finish capture and paste into guest Draw. Record success and cancellation separately; no mocked returned PNG.
6. **NOT RUN — Full Screen.** Click Full Screen and verify saved/pasted image represents the guest desktop, without old overlays/toolbars.
7. **NOT RUN — English OCR/paste.** Select Extract Text, capture the public English text, wait for result and physically paste into guest Writer after switching focus. Record actual text correctness locally; language-pack listing is not this check. If delivery asks to return/click the capture surface, follow that real focus handoff and record it.
8. **NOT RUN — Escape.** Physically cancel selection; rapidly reopen/cancel and verify no frozen/extra overlays, errors or lost next capture.
9. **NOT RUN — segmented controls.** Screenshot default; both labeled/icon segments readable, exclusive and one-click; changing action alone does not capture. Rectangle/Window/Full Screen/Close present, no Freeform or dropdown.
10. **NOT RUN — no application tray.** Inspect GNOME top bar before/after capture; no AI Snipping Tool indicator/menu or permanent controller. GNOME's own screenshot/privacy indicators must remain intact.
11. **NOT RUN — normal logout/login.** Leave user service enabled, log out via guest GNOME menu and back in. Without a terminal/manual app launch, verify quiet automatic startup, identified shortcut registration, physical key/Escape and one PID.
12. **NOT RUN — guest reboot.** Reboot **the VM only**, log in and repeat quiet startup/registration/key plus one capture/paste. Record the new boot/session, not the host's earlier acceptance.
13. **NOT RUN — service stop/restart.** Use commands below in the guest. Stop yields inactive/MainPID0, no unrequested relaunch beyond3s; start/restart yields one registered instance, no icon. Check normal shutdown/session cleanup and physical key afterward.
14. **NOT RUN — graphical upgrade/removal.** Follow the separate snapshot procedure below, with all opted-in users stopped first; preserve captures, no leftover active process/service/enabling link after removal. Previous headless dpkg passes do not satisfy this line.

For each result collect actual guest OS/session/package/runtime versions, UTC time/boot ID, expected versus observed, consent/binding state, relevant local journal/error excerpts, and PASS/FAIL/NOT RUN. Do not upload private content. Distinguish denied/cancelled/timeout/backend errors.

## Service control, upgrade and removal — guest only

```bash
systemctl --user stop com.dulmina.aisnippingtool.service
# Wait more than RestartSec=3 seconds, then inspect (inactive is expected):
systemctl --user show com.dulmina.aisnippingtool.service -p MainPID -p ActiveState -p Result
systemctl --user start com.dulmina.aisnippingtool.service
systemctl --user restart com.dulmina.aisnippingtool.service
journalctl --user -b -u com.dulmina.aisnippingtool.service -n 60 --no-pager
```

For the upgrade test, restore/clone `clean-gnome-before-snipping` rather than downgrading a running accepted candidate. Transfer/checksum the retained Stage3.1 input separately. Install it through guest APT with dependencies, explicitly activate its user service, then **stop/disable each opted-in guest user** before upgrading:

```bash
# In each affected guest user's terminal; never the development host:
systemctl --user disable --now com.dulmina.aisnippingtool.service
# Guest administrator, current candidate in Downloads:
cd "$HOME/Downloads"
sudo apt install ./ai-snipping-tool_0.3.2~stage3.2-1_amd64.deb
# Opted-in guest user again:
systemctl --user daemon-reload
ai-snipping-tool --version
systemctl --user enable --now com.dulmina.aisnippingtool.service
```

Confirm version, preserved actual binding/permissions, no tray, new segments and capture/paste. Existing screenshots must remain untouched. Package upgrade does not automatically stop/restart another user's running process; explicit coordination is a prototype constraint.

Before removal, record a saved public screenshot's hash and stop/disable every opted-in guest account. Then:

```bash
systemctl --user disable --now com.dulmina.aisnippingtool.service
sudo apt remove ai-snipping-tool
systemctl --user daemon-reload
systemctl --user is-active com.dulmina.aisnippingtool.service
systemctl --user is-enabled com.dulmina.aisnippingtool.service
command -v ai-snipping-tool
pgrep -af '/usr/bin/ai-snipping-tool|/usr/lib/ai-snipping-tool/main.py'
```

Expected inactive/not-found, no installed command/lasting process and no user startup link; nonzero statuses can be the expected absence. Inspect any remaining app-specific user override rather than deleting it blindly. Confirm screenshot hashes/user data unchanged, optionally purge in the VM, then log in again to check no unexpected service. No uninstall script should delete screenshots, GNOME permissions, user settings or unrelated files. Preserve the VM snapshot for rollback; do not substitute these steps for migration of the development installation.

## Release decision and changed files

**Not ready for external beta distribution:** clean guest APT/dependency/first-run verification and all14 actual GNOME acceptance checks remain unresolved; no public redistribution license has been selected (local unpublished prototype status remains). Explicit per-user setup/removal coordination also needs evaluation by a new user. Stage3.2's package/headless results remain useful prerequisites, not a completed gate.

Only documentation changed: this file, `docs/handoff-summary.md`, `docs/test-matrix.md`. No rebuild, dependency installation, VM creation, desktop setting/permission change, host service operation or production code change. Next authorized action is to prepare the disposable guest and execute/record this ledger. Do not proceed to release, Freeform or AI on the basis of these instructions alone.
