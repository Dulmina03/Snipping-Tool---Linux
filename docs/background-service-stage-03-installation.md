# Stage 3.2 — refreshed Debian package and isolated validation

2026-11-15, Ubuntu26.04.1 LTS amd64. **Candidate ready for clean Ubuntu GNOME installation testing; packaged graphical acceptance and public release remain pending.**

The user physically accepted the development baseline: automatic login service, global shortcut, Rectangle/Window/Full Screen, English OCR/paste, latency improvement, no tray icon/menu, segmented actions/no Freeform button, Escape. Those passes supersede earlier source-version pending gates; they do not prove acceptance of the installed package.

## Final candidate — use this artifact

`dist/stage-03.2-validated/ai-snipping-tool_0.3.2~stage3.2-1_amd64.deb`

- Version: **0.3.2~stage3.2-1**, architectureamd64, size **54,072bytes**, Installed-Size226KiB.
- SHA256: **fe18304aa2108689661ed4a67a76417eb1f03d4bb9c090a22b2d889742d69005**.
- Independent build in `dist/stage-03.2-validated-repro/` has identical bytes/hash.
- Stage3.1 artifact remains unchanged at `dist/stage-03.1-final/ai-snipping-tool_0.3.1~stage3.1-1_amd64.deb`, SHA25639a189ad278921cd68cd68b9caf86f027b64659dca609f1b7193c433e1c2e2eb.
- Earlier Stage3.2 iterations in `dist/stage-03.2-final/` and `dist/stage-03.2-repro/` precede corrected offline instructions; they are preserved, **not the final candidate**. No artifact was overwritten or installed on the host.
- All dist artifacts are Git-ignored/local. Project license remains unspecified by the owner's earlier choice; no redistribution grant/public release.

## Inputs and focused packaging changes

Started clean on requested `feat/background-service` at7b1b5e0; no branch creation/switch. External commits6be6e3a and2ea28f3 appeared during work and were preserved. This agent did not stage, commit, merge, reset or push. [Build-input manifest](background-service-stage-03-build-inputs.json) records exact runtime/metadata hashes and the working-tree status at recording. Every packaged runtime file was compared byte-for-byte with its current filesystem source, not exported from Git HEAD; local uncommitted metadata changes were included. All recorded hashes still matched after external commits.

- `debian/control`, `debian/changelog`, `debian/assets/ai-snipping-tool`: new version, accepted source contents, remove obsolete AppIndicator recommendation. No runtime need for a tray extension remains.
- `debian/README.install`: trayless systemd control and journal status, no tray Quit, disposable-machine scope, dependency-checked local offline dpkg instructions and APT-cache caveat.
- `debian/verify_deb.py`: reject mismatch between launcher version and package control Version.
- `tests/test_debian_packaging.py`: add metadata consistency/no-tray-dependency and uncommitted-source-copy regressions; assert staged bytes equal every current runtime source. Existing196 tests preserved; total198.
- This report, build-input manifest, installation evidence, previous packaging report pointer, handoff and matrix document results.

No production screenshot/OCR/clipboard/toolbar/service/shortcut code changed in this task. The package copies accepted code: precise1ms active/coarse100ms idle job scheduler; trayless main.py with quit-on-last-window disabled; segmented Screenshot/Extract Text controls; only Rectangle/Window/Full Screen plus Close visible; unchanged capture saving, mapping, OCR and clipboard workflows.

## Package layout, integrity and identity — PASS

- `/usr/bin/ai-snipping-tool`: mode0755, system `/usr/bin/python3`, private app modules resolved relative to install prefix; version/session checks and root GUI refusal. No development venv or source checkout dependency.
- `/usr/lib/ai-snipping-tool/`: runtime modules, `.packaged-install`, private hash-pinned pytesseract0.3.13. No system pip or global site-packages writes. App/model resources are read-only during the runtime probe.
- `/usr/share/applications/com.dulmina.aisnippingtool.desktop`, matching hicolor SVG icon, `/usr/lib/systemd/user/com.dulmina.aisnippingtool.service`. Stable desktop/app IDcom.dulmina.aisnippingtool and shortcut IDopen_capture_menu retained. Exec/TryExec use the installed command; service uses installed executable/WorkingDirectory, same session/identity checks and restart policy.
- Root archive ownership, directory0755/file0644/executable0755; MD5 payload manifest, Python syntax, installed resource marker, desktop validation and SVG parse pass. No scripts, global enablement, XDG autostart, user-file migration, private screenshots, `.venv`, repository metadata, bytecode or bundled traineddata. Validator rejects `/home/dulmina`; only old generic URI-example docstrings contain `/home/user` examples, not executable paths.
- Actual installed-resource snapshot hashes/`dpkg --verify` pass. Screenshot saving still uses `~/Pictures/Screenshots`; saved fixture PNG bytes/pixels match, OCR child uses system Python and installed model resources without network.
- `systemd-analyze --user verify` passes with executable/WorkingDirectory mapped to the installed snapshot. Only warning is the unrelated existing spice-vdagent.service StandardError-in-Install entry. This is parser validation, not a running packaged user service.

## Dependency verification

Configured Ubuntu26.04 resolute/resolute-updates/security indexes provide every declared dependency (main/universe). No apt source or index changes were performed. Full APT simulation resolves the candidate plus only the two locally absent runtime packages, with **0 upgrades/0 removals**; unrelated packages reported as auto-removable were not touched.

- Python3 requires>=3.14,<3.15; installed metapackage3.14.3-0ubuntu2/interpreter3.14.4.
- Ubuntu PySide6 QtCore/QtGui/QtWidgets6.10.2-6ubuntu1; minimum6.10. Qt Wayland6.10.2-4. GUI/platform dependencies resolve transitively through Ubuntu packages.
- Pillow installed12.1.1-2ubuntu1.4, candidate12.1.1-2ubuntu1.5, satisfies>=12; python3-packaging26.0-1.
- **Locally missing, available in configured universe:** python3-dbus-next0.2.3-6; tesseract-ocr-sin1:4.1.0-2build1. Existing private Ubuntu archives match SHA256 metadata from the APT indexes; installed only in namespace layers, never on host.
- Tesseract5.5.0-1build1 and English data1:4.1.0-2build1; Sinhala data version as above. Model presence/English operation verified in isolation; no Sinhala recognition-accuracy claim.
- XDG Desktop Portal1.21.1+ds-1ubuntu3.1 (requires>=1.18), GNOME backend50.0-0ubuntu1, libglib2.0-bin2.88.0-1ubuntu0.1, systemd259.9-0ubuntu0.1, all installed/available.
- pytesseract0.3.13 is app-private from the existing SHA256-pinned wheel; configured indexes have no python3-pytesseract. Existing license/hash strategy retained, no API/provider dependencies.
- **Test-only:** QtTest Python bindings/library are absent locally, available as python3-pyside6.qttest6.10.2-6ubuntu1/libqt6test6. Downloaded261kB into /tmp and extracted privately for the system-stack full suite. Not a runtime dependency and not added to Depends; no system install.

**Offline distinction:** ordinary APT simulation PASS. `apt-get -s --no-download install candidate` refuses the host's absent/uncached dependencies; a namespace APT attempt with local archives also refused archive acquisition and logged rootless UID-mapping warnings; no APT installation pass is inferred. Offline operation needs a complete prepared dependency set, not just this54kB application package. The bundled instructions now use `dpkg --install` after prerequisites are supplied; no force flags or dependency bypass. Actual network-isolated dpkg dependency checks/configuration succeeded. No hidden runtime/install download or system pip.

## Actual isolated tests

There is no ready clean GNOME VM: Docker daemon socket is absent/not running, /dev/kvm absent; QEMU alone is not a prepared graphical Ubuntu guest. Testing used bubblewrap user/PID/network/IPC isolation with host `/` read-only, private writable overlay layers for `/usr`, `/etc`, `/var`, independent copied dpkg database/log, empty `/home`/`/run`, private inputs/output. The host session bus and source checkout were hidden. New private parent directories were needed because unmapped lower-layer root ownership is not writable by rootless namespace root. Host files and dependencies were not modified. **This is an isolated clone of the existing Ubuntu runtime, not a fresh minimal OS or live GNOME session.**

Results for the final exact artifact:

1. **PASS headless:** install Stage3.1 plus locally supplied Ubuntu dbus-next/Sinhala packages with normal dpkg dependency checks; verify old version.
2. **PASS headless:** upgrade to Stage3.2, verify version, `dpkg --verify`, clean `dpkg --audit` and copied installed resources. Namespace triggers for desktop/icon menus complete.
3. **PASS headless:** installed root-GUI guard refuses; session guard refuses absent genuine session rather than starting GNOME.
4. **PASS headless:** remove Stage3.2; executable/app directory/service unit gone, public screenshot preservation sentinel untouched. Reinstall current version, then purge; clean audit and sentinel preserved. No user-unit/permission cleanup script.
5. **PASS headless actual entry point:** two source-hidden, non-root/system-Python offscreen starts through installed executable, second invocation exits via runtime lock, SIGTERM exits0 with Shutdown complete/lock removal; second fresh start repeats. No development venv. Portal bus deliberately inaccessible, so this is not shortcut registration.
6. **PASS read-only runtime smoke:** main.configure_application creates quiet hidden controller/no QSystemTrayIcon, quit-on-last-window false; new action segments/defaults/modes and idle scheduling match accepted source. Actual production Full Screen fixture save yields matching PNG pixels/default path; real OCR child returns English; local Qt image/text clipboard matches. Not external Wayland paste or a live portal capture.
7. **PASS regressions:** all198 on development venv in19.261s; all198 on Ubuntu system Python/PySide6/Pillow in18.936s using privately supplied test-only QtTest and private pytesseract/dbus-next. No tests weakened or skipped. Syntax/import/whitespace checks pass.
8. **NOT RUN packaged GNOME:** service enable/start, genuine Registry/shortcut binding, physical shortcut, Rectangle/Window/Full Screen portal capture, external image/text paste, native visual quiet startup, actual login/reboot and installed service stop/logout. Static/session-guard/offscreen checks do not replace these tests.
9. **No unexpected activation in headless tests:** no live user manager/bus was exposed, package has no activation scripts, child processes reaped, payload removed in namespace. Real GNOME removal-after-enabled-service remains NOT RUN and must follow the explicit stop/disable procedure below.

**Recorded intermediate failures:** sandbox suite198/18.736s had4 socket permission errors/2 systemd parser failures; host rerun passed. First system run183/17.520s had2 missing QtTest-module import errors; custom wrapper discovery then collided with legacy root test_clipboard.py because capture_menu prepends ROOT when absent. Corrected test-only library/import-path setup passed all198 without changing production code. Namespace preparation initially failed overlay-root/mountpoint/ownership/lock permissions and APT cache; corrected private layers/databases enabled dpkg tests. First entry probe used a0775 runtime fixture; Qt selected its fallback runtime directory, invalidating the probe's assumed lock path. A separate0700 fixture passed both attempts. No production fix was inferred from these harness failures.

## Accepted development service — unchanged

Before/after: enabled/active **PID138240**, invocation7664161b8879476e94e3f1e85f40ebe6, user FragmentPath `/home/dulmina/.config/systemd/user/com.dulmina.aisnippingtool.service`. Unit SHA2565212c21af2e8ac203bf51d352bd3b7d50bcdcafca783090a6e2bafe9682e06ce; managed user desktop SHA256f7d6857517d07e3df9e7abf8ea49507cc6d6f08bd914321b2b6258a873417ce5. The host still has no ai-snipping-tool, python3-dbus-next or tesseract-ocr-sin installed. No host service stop/restart/disable/replace, package install/remove, permissions or shortcut edits. Package artifacts alone do not migrate the development installation.

## Clean-machine installation and rollback — not executed on host

**Only on a disposable Ubuntu26.04 GNOME Wayland VM/test machine. Do not run these on the accepted development host.** Preinstall/cache all declared/transitive Ubuntu dependencies or supply the complete offline Ubuntu archive bundle; the local application .deb is not that bundle. Do not use system pip or force dependency flags.

```bash
# Test machine only, after prerequisites have been supplied:
sudo dpkg --install ./ai-snipping-tool_0.3.2~stage3.2-1_amd64.deb
dpkg --verify ai-snipping-tool
dpkg --audit
ai-snipping-tool --version
systemctl --user daemon-reload
systemctl --user show com.dulmina.aisnippingtool.service -p FragmentPath
systemctl --user cat com.dulmina.aisnippingtool.service
```

Proceed only if FragmentPath resolves `/usr/lib/systemd/user/com.dulmina.aisnippingtool.service`, with no checkout/custom override/drop-in or user launcher shadowing the installed app-grid entry. If an override exists, STOP and review; these instructions do not authorize replacing it. In the genuine logged-in GNOME user session:

```bash
systemctl --user enable --now com.dulmina.aisnippingtool.service
systemctl --user status com.dulmina.aisnippingtool.service --no-pager
journalctl --user -u com.dulmina.aisnippingtool.service -n 60 --no-pager
# Intentional stop/control without a tray:
systemctl --user stop com.dulmina.aisnippingtool.service
systemctl --user start com.dulmina.aisnippingtool.service
systemctl --user restart com.dulmina.aisnippingtool.service
```

Confirm consent interactively if GNOME asks; never reset permissions or assume the requested Alt+Shift+S replaces a stored assignment. Inspect the actual assignment in the journal. Test app-grid launch/single instance, silent startup/no icon/menu/window, shortcut and Escape, Rectangle/Window/Full Screen → external image paste, Extract Text → English external text paste, repeated capture, stop staying stopped, then login/reboot startup. Record each physical PASS/FAIL. GNOME's own privacy indicators remain legitimate.

For upgrade/removal, **each opted-in account on the test machine** must stop/disable its packaged service first. No maintainer scripts coordinate running per-user processes automatically.

```bash
systemctl --user disable --now com.dulmina.aisnippingtool.service
# Upgrade: install newer candidate with prepared dependencies, reload, then opt in again.
# Removal (test machine only):
sudo dpkg --remove ai-snipping-tool
systemctl --user daemon-reload
systemctl --user is-active com.dulmina.aisnippingtool.service
# Optional package-metadata purge after removal:
sudo dpkg --purge ai-snipping-tool
```

Verify no remaining packaged process or stale enabling link; preserve screenshots/user files/permissions. Rollback on that VM by reinstalling a retained previously tested package with dependencies prepared, daemon-reload, inspect paths and explicitly activate. Stage3.1 is retained but lacks accepted new UI/lifecycle changes; it is not a recommendation to downgrade the development host. Host development migration/rollback is **not authorized or performed**. Multi-user stop coordination remains a prototype limitation.

[Commands, isolation details and results](background-service-stage-03-installation-evidence.txt). No clean graphical package sign-off, public release, AI, Freeform or next-stage work claimed.
