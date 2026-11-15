# Background service Stage 3.1 — Ubuntu Debian packaging

2026-11-15 (Asia/Colombo). **Local candidate built and inspected; NOT installed on this host. Clean Ubuntu installation/removal and packaged physical GNOME acceptance are NOT RUN.** The user confirms all nine Stage 2 physical tests PASS, including login registration/activation, captures/paste, OCR, Escape, Quit and reboot. This supersedes the older pending gate; it does not establish acceptance of the new package.

## Candidate

Final artifact: `dist/stage-03.1-final/ai-snipping-tool_0.3.1~stage3.1-1_amd64.deb` (**52,832 bytes**).

SHA-256: `39a189ad278921cd68cd68b9caf86f027b64659dca609f1b7193c433e1c2e2eb`.

Two independent builds produced identical bytes. Earlier private iterations under other dist directories are not the final candidate and must not be distributed/installed. Build outputs are Git-ignored, not staged. This is a rootless `dpkg-deb` binary-package workflow, not a Debian archive-ready source package or public release. No host installation, removal, accepted service restart/stop/enable/disable or permission change was performed.

## Inspection and architecture

Initial checkout was clean on **main at6811b8e**, contrary to the attachment's branch assumption. Existing `feat/background-service` pointed to the same commit. After the explicit branch-authorization question and user's “ok”, switched to that existing branch; no new branch, merge, reset or commit. The accepted service remains `/home/dulmina/.config/systemd/user/com.dulmina.aisnippingtool.service`, enabled/running PID9096, NRestarts0; its source checkout and venv remain intact.

Installation layout:

- `/usr/bin/ai-snipping-tool`: executable Python launcher; uses `/usr/bin/python3`, resolves the private application directory relative to the installed prefix, rejects root GUI launches, supports `--version` and lightweight `--check-session`.
- `/usr/lib/ai-snipping-tool/`: runtime Python modules plus a private, hash-pinned pytesseract package and `.packaged-install` resource marker. No global pip/site-packages writes.
- `/usr/share/applications/com.dulmina.aisnippingtool.desktop`: installed launcher, stable desktop app ID, no terminal or development paths.
- `/usr/share/icons/hicolor/scalable/apps/com.dulmina.aisnippingtool.svg`: vector rendering of the existing fallback camera icon; toolbar/tray implementation unchanged.
- `/usr/lib/systemd/user/com.dulmina.aisnippingtool.service`: same accepted GNOME session lifecycle with installed executable paths. Not enabled by package installation.
- `/usr/share/doc/ai-snipping-tool/`: installation/upgrade/removal notes, copyright status, full pytesseract license and changelog.

No tests, Git metadata, build logs, secrets, screenshots, trained-data copies, developer service installer, PipeWire experiments/binaries or virtual environments are installed. Original PipeWire source files remain in the checkout; they are not referenced by the production main capture path. Generic `/home/user/...` examples remain in the existing URI-decoding function docstrings, but no executable home-path literal or developer `/home/dulmina` path occurs in the payload. Archive validator distinguishes AST docstrings from runtime strings.

Development installation blockers addressed:

1. Checkout launcher generation used sys.executable/main.py and could rewrite a managed per-user desktop entry. Packaged startup now verifies/uses the installed desktop resource and never generates/replaces a user launcher. Development behavior is unchanged.
2. OCR formerly stored/downloaded/link-created models beside its module. Packaged startup reads Ubuntu-installed `eng`/`sin` data and fails clearly if missing, with no download or write into `/usr`. The existing Sinhala/mixed recognition branch now consults that active model directory. Preprocessing, OCR passes, scoring and text processing are unchanged. Development local-model behavior is preserved.
3. The developer user-service generator assumes a project `.venv`. It is excluded from the payload. Its exact existing session guard is extracted/re-exported through `utils.session_environment` and shared by both service launchers; development generator tests still pass.
4. OCR children use the system interpreter and private application working directory. The private pytesseract module is therefore importable by parent and OCR child without the development venv or a PYTHONPATH dependency.

Screenshots stay `~/Pictures/Screenshots`; runtime lock stays in the current user's runtime directory. No new settings/history or data format is introduced. Installed code/models are read-only; user-created files and application logs remain under user/session control. No hidden uploads, telemetry, pip, API keys or network use is added.

## Dependency and license strategy

Observed Ubuntu26.04.1 amd64 has Python3.14.4, PySide6 **6.10.2**, Pillow **12.1.1** and packaging26.0. The development venv has PySide6 **6.11.2** and Pillow12.3.0. Both stacks pass the full regressions. Package deliberately targets Python3.14 and amd64; portability to another Ubuntu/Python release is not claimed.

Declared dependencies: python3(>=3.14,<<3.15), python3-pyside6.qtcore/qtgui/qtwidgets(>=6.10), python3-pil(>=12), python3-dbus-next(>=0.2.3), python3-packaging, tesseract-ocr, tesseract-ocr-eng, tesseract-ocr-sin, xdg-desktop-portal(>=1.18), xdg-desktop-portal-gnome, qt6-wayland, libglib2.0-bin and systemd. Recommends the GNOME AppIndicator extension; Ubuntu GNOME's tray support must actually be enabled/available for tray acceptance. No PySide6 Addons wheel is needed by current imports.

The local Ubuntu package index provides dbus-next0.2.3-6 but no python3-pytesseract (tesserocr is a different binding and is not substituted). Bundle only the small pure-Python **pytesseract0.3.13** runtime from its SHA-256-pinned wheel in the app-private directory, plus its full Apache-2.0 license; use Ubuntu-managed PySide6/Pillow/dbus-next/packaging. [Official wheel metadata and hash provenance](https://pypi.org/pypi/pytesseract/0.3.13/json). All exact metadata lives in `debian/pytesseract-wheel.json`; the builder refuses unverified inputs. The Ubuntu runtime package licenses remain in their own `/usr/share/doc/<package>/copyright` files. [Debian binary-package metadata conventions](https://www.debian.org/doc/debian-policy/ch-binary.html).

No project LICENSE exists. User explicitly chose **keep local prototype status**, so copyright metadata records “upstream license unspecified; no redistribution grant”; no new license is imposed. Maintainer contact follows the existing Git author identity. This is a blocker for public redistribution, not an invented open-source license. Sinhala apt language data may differ from the development tessdata_best file: no new recognition accuracy/benchmark claim is made.

## Build and inspection — no root or system pip

From the checkout, using system Python:

```bash
# Explicit network acquisition of a BUILD INPUT only; may also supply it offline.
/usr/bin/python3 debian/build_deb.py --fetch-wheel /tmp/snipping-build-inputs
# Everything below is offline. Use a fresh output directory on repeated builds.
/usr/bin/python3 debian/build_deb.py \
  --wheel /tmp/snipping-build-inputs/pytesseract-0.3.13-py3-none-any.whl \
  --output dist/candidate-next
/usr/bin/python3 debian/verify_deb.py \
  dist/candidate-next/ai-snipping-tool_0.3.1~stage3.1-1_amd64.deb
dpkg-deb -I dist/candidate-next/ai-snipping-tool_0.3.1~stage3.1-1_amd64.deb
dpkg-deb -c dist/candidate-next/ai-snipping-tool_0.3.1~stage3.1-1_amd64.deb
```

Build tools: Python standard library and dpkg/dpkg-deb; desktop-file-utils for validator. No debhelper, root, compilation of Qt, pip install or venv is required. Offline builds take an already acquired wheel. Reproducible timestamps use SOURCE_DATE_EPOCH or the package changelog date, fixed modes/root ownership and no bytecode. Existing artifacts are preserved rather than overwritten. Package version is pinned for this prototype; before a future release update control/changelog/launcher version and build under a new version.

## Installation and explicit per-user activation — NOT EXECUTED

Use a disposable Ubuntu26.04 GNOME VM or a separate test machine first. A separate account on this host would still share the new system package and is not as isolated as a VM. Prepare/cache **all declared and transitive Ubuntu dependencies** beforehand; a clean GNOME installation may need many more than this host's two missing packages. The small .deb is not an offline mirror of Ubuntu/Qt. Nothing in package installation downloads dependencies or runs pip.

```bash
# On the disposable test system only, after preparing dependencies offline:
sudo apt --no-download install ./ai-snipping-tool_0.3.1~stage3.1-1_amd64.deb
ai-snipping-tool --version
systemctl --user daemon-reload
systemctl --user show com.dulmina.aisnippingtool.service -p FragmentPath
systemctl --user cat com.dulmina.aisnippingtool.service
```

Proceed only if FragmentPath is `/usr/lib/systemd/user/com.dulmina.aisnippingtool.service`, no user override/drop-in redirects it to a checkout, and the session is genuine GNOME Wayland. Then, as that logged-in user:

```bash
systemctl --user enable --now com.dulmina.aisnippingtool.service
systemctl --user status com.dulmina.aisnippingtool.service --no-pager
```

There are **no maintainer scripts**, global enablement/presets, lingering, root GUI or XDG autostart entry. Every account opts in separately. Service Requisite/After=gnome-session.target, PartOf=graphical-session.target, Restart=on-failure/3s, rate limit3/60s and clean signal/Quit behavior are retained. `Type=exec` does not mean portal registration is complete: wait for actual identity/assignment status. Stage2's bounded nonblocking recovery stays in place. Single-instance runtime lock and shortcut/session IDs are unchanged.

Stable identity `com.dulmina.aisnippingtool` and shortcut `open_capture_menu` preserve existing permissions/bindings where the backend supports it. No permission database migration/reset is performed. GNOME may ask for consent for the installed launch; the user must confirm it. Requested key remains Alt+Shift+S; inspect actual portal/tray assignment rather than assuming it changed. No ConfigureShortcuts v1 call is added.

### Existing accepted development setup — future migration requires review

The current `~/.config/systemd/user` unit **shadows** the packaged unit. Existing `~/.local/share/applications` launcher can similarly shadow the installed app-grid entry. Installation deliberately does not overwrite, remove, disable or migrate either. Starting the packaged command alongside the accepted instance will be rejected by the existing lock; that alone is not packaged acceptance.

Do not perform the following migration until the user approves replacing the accepted development setup:

1. Record the accepted unit, enabling links, drop-ins, launcher and environment; create a unique backup directory. Review exact file contents and ownership, including XDG_CONFIG_HOME/XDG_DATA_HOME overrides.
2. Intentionally stop/disable the development service in that account. Back up/move only the reviewed app-specific user unit/managed launcher and app-specific drop-ins; preserve unrelated/custom files. Do not reset permissions or any GNOME shortcuts.
3. Install the candidate with prepared dependencies, reload, confirm FragmentPath is the packaged unit and the app-grid entry resolves `/usr/bin/ai-snipping-tool`, then explicitly enable/start the packaged service.
4. Perform the complete physical acceptance below before removing any backup or development checkout.

No such migration was executed today. The installed package and development app must not be given separate competing startup mechanisms.

## Upgrade, removal and rollback

Package upgrades replace only dpkg-owned `/usr` files; they do not automatically stop running per-user processes. Before upgrade/removal, **each opted-in logged-in account** must `systemctl --user disable --now com.dulmina.aisnippingtool.service`. On the test machine, perform the reviewed offline upgrade, then reload and explicitly enable/start again. Do not uninstall while another user's instance is running. This manual prototype lifecycle is a known limitation, not an assertion of automatic multi-user coordination.

For removal on the test machine after stopping every instance: `sudo apt remove ai-snipping-tool`, then `systemctl --user daemon-reload` in affected accounts. No uninstall script deletes screenshots, user settings/units/launchers, permissions or backups. Purge does not clear user data either. Disable before removal to avoid stale enabling links.

Rollback by offline reinstalling a retained, previously tested package and explicitly reactivating. To restore development instead, stop/disable the packaged service and restore the reviewed original app-specific backups without overwriting any newer custom edits; reload, inspect FragmentPath/desktop entry and explicitly re-enable the old service if desired. No rollback/migration was executed against the working development setup.

## Actual tests and limitations

- **PASS:** required pre-change baseline173 regressions, 19.447s.
- **PASS:** final full182 tests on development venv, 18.510s; full182 on Ubuntu-managed Python/PySide6/Pillow, 18.746s. Nine new packaging tests cover offline stage/allowlist/licensing/modes, hash refusal, desktop-user-file preservation, missing resource failure, system model lookup/no download, Sinhala/mixed routing and shared session guard. Subsequent staging-root permissions assertion passed in all9 focused tests, 0.081s.
- **PASS:** versioned amd64 binary, matching independent rebuild hash; dpkg structure, MD5 manifest, root ownership, modes, source exclusions, home-path/syntax scan, installed launcher version, SVG parsing and desktop-file-validate. Validator initially caught staging root mode0775 under the host umask; fixed to0755 and retested. Generic existing URI docstrings are exempted from runtime-path validation.
- **PASS:** real systemd parser/prospective enabled graph with executable/WorkingDirectory prefix mapped to the extracted tree. It reports only an unrelated pre-existing spice-vdagent `[Install] StandardError` warning. This is staged-path validation, not actual installed-service launch.
- **PASS:** normal no-install APT resolver simulation resolves ai-snipping-tool + python3-dbus-next + tesseract-ocr-sin; no upgrades/removals required on this host.
- **FAIL/expected prerequisite check:** `apt-get -s --no-download install ...` refuses because those two dependencies are not installed/cached in APT. They were downloaded/extracted privately into /tmp for tests, not installed. Offline install needs a prepared dependency bundle/cache; no claim of self-contained OS dependencies.
- **PASS:** bubblewrap source-hidden, read-only/no-network isolated smoke with extracted payload, system Python, extracted Ubuntu dbus-next and Ubuntu language models mounted read-only in that namespace. Actual production PNG save yields matching pixels/default screenshot directory, Qt image clipboard; actual OCR child returns English, GUI text clipboard matches. Original recognition algorithms run unchanged. This is offscreen public-fixture testing, **not physical GNOME capture, external Wayland paste or a clean-machine dpkg installation**. Namespace mounts do not alter host models or identity.
- **PASS:** syntax/import coverage and `git diff --check`. Accepted development service still enabled/active PID9096/NRestarts0 with its original user FragmentPath. Candidate absent from host dpkg database.
- **NOT RUN:** installing/upgrading/removing the .deb on a clean Ubuntu VM; actual package activation/login/logout/reboot; installed GNOME portal identity/consent, real shortcut/Escape, Rectangle/Window external image paste, English OCR external text paste, physical tray Quit. No native/package success is inferred from the user's accepted development version or mocked Window tests.
- **NOT RUN:** lintian/source-package/archive checks; lintian is not installed. This is not a public-release or Debian Policy compliance claim. Multiple simultaneous graphical sessions remain unsupported, as before.

Full selected commands/results: [evidence](background-service-stage-03-packaging-evidence.txt).

## Physical package gate

On the disposable Ubuntu GNOME test system, install offline prerequisites and the candidate, activate the user service explicitly and verify **one** instance. Test quiet login, actual assigned shortcut opening only the overlay, Escape cancellation, Rectangle → external image paste, Window picker → external image paste, English OCR → external text paste across focus changes, tray Quit staying stopped, and startup/registration after reboot. Confirm consent normally if GNOME prompts; never automate approval. Test upgrade/stop/remove/rollback separately and verify screenshot files remain intact. Record each PASS/FAIL/NOT RUN.

Stage3.1 has produced the requested inspectable candidate; packaging acceptance remains open. No further stage, public release, Freeform or AI work is authorized.

## Files modified

- `.gitignore`: excludes local dist artifacts/build inputs.
- `utils/desktop_entry.py`: packaged desktop-resource lookup; development launcher generation preserved.
- `utils/session_environment.py`: extracted unchanged session guard.
- `utils/user_service.py`: re-exports shared guard; accepted service generator preserved.
- `ocr/ocr_engine.py`: installed read-only model lookup and matching language branch; no algorithm rewrite.
- `tests/test_debian_packaging.py`: nine isolated regressions; never installs/starts a service.
- `debian/control`, `debian/changelog`, `debian/copyright`, `debian/README.install`, `debian/pytesseract-wheel.json`, `debian/build_deb.py`, `debian/verify_deb.py`: metadata, licensing status, explicit build input, rootless offline build and artifact validation.
- `debian/assets/ai-snipping-tool`, `debian/assets/com.dulmina.aisnippingtool.desktop`, `debian/assets/com.dulmina.aisnippingtool.service`, `debian/assets/com.dulmina.aisnippingtool.svg`: installed executable, desktop identity, session service, icon.
- This report/evidence, `docs/baseline-audit.md`, `docs/handoff-summary.md`, `docs/test-matrix.md`: accepted Stage2 baseline, Stage3.1 results and outstanding gate.

No stage/commit/merge/reset/push, system package installation or accepted startup modification. Existing external commit6811b8e and all repository history preserved.
