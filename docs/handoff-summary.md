Latest status: shortcut request/reporting corrections are implemented; **43 automated tests PASS**. Requested `CTRL+SHIFT+s`, observed assignment Ctrl+Alt+S. Host app-grid identity and physical acceptance remain unverified. See the final shortcut update below.

# Current handoff — Phase 1, 2026-11-14

Phase 1 implementation is ready for review on `fix/phase-01-app-lifecycle`; physical acceptance is still pending. Phase 2 has not started. The Phase 0 handoff below is preserved verbatim, including its pre-existing uncommitted note.

- Canonical `main.py`, portable generated desktop entry and actual user launcher migration; quiet hidden controller; shared shortcut/tray route; duplicate process guard; overlay cleanup; interruptible portal registration/waits; cancellable subprocess boundary around the unchanged OCR engine.
- Qt widgets/pixmaps/clipboard stay on the main thread. Existing capture modules, crop/save algorithms, OCR engine and clipboard helpers remain unchanged. No AI/dependency/PDF/Freeform additions.
- Fixed observed GNOME startup abort using a conditional Qt generic-theme fallback for the missing XSettings `antialiasing` key; explicit theme preferences remain respected.
- PASS: 20 new lifecycle tests, syntax/import checks, existing smoke/cancel, offscreen clipboard/OCR probe, desktop validation and whitespace. Native Wayland check: hidden controller/no overlay at startup, tray reported available, real portal registration completes, heartbeat and Quit clean up thread.
- NOT RUN: physical Ctrl+Shift+S, visual ghost-window/task-switcher inspection, external paste, physical tray clicks, interactive screenshot portal denial/delay. No screenshot request was issued by the live probe. Full Phase 1 exit gate is not signed off.
- Remaining: host Registry warning despite successful shortcut registration; clipboard anchor requires real paste acceptance; existing pip/model-download/accuracy/punctuation/filename/geometry issues are not fixed here. Legacy selected-area test route now directs users to the production overlay.
- Initial HEAD `24d741c`; existing handoff and Phase 0 log modifications preserved. External commits appeared during the task. This agent performed no stage/commit/merge/push/reset/unstage action. Recheck HEAD/status before further work.
- Exact commands/results: [phase-01-command-log.txt](phase-01-command-log.txt). Acceptance steps: [test-matrix.md](test-matrix.md). Implementation findings: [baseline-audit.md](baseline-audit.md).

Phase 1 authored files:
`main.py`, `com.dulmina.aisnippingtool.desktop`, `shortcuts/global_shortcut.py`, `ui/capture_menu.py`, `utils/async_jobs.py`, `utils/desktop_entry.py`, `utils/ocr_job.py`, `utils/ocr_process.py`, `test_capture_menu.py`, `test_global_shortcut.py`, `tests/test_phase01.py`, `docs/baseline-audit.md`, `docs/test-matrix.md`, `docs/handoff-summary.md`, `docs/phase-01-command-log.txt`.

Outside checkout: migrated `~/.local/share/applications/com.dulmina.aisnippingtool.desktop` using the authorized installer. Pre-existing `docs/phase-00-command-log.txt` edits were preserved, not authored in Phase 1.

---

# Phase 0 handoff — 2026-11-14

Phase 0 audit recorded; Phase 1 not implemented. Read [baseline-audit.md](baseline-audit.md), [test-matrix.md](test-matrix.md), and [phase-00-command-log.txt](phase-00-command-log.txt).

- Working branch: `chore/phase-00-baseline-audit`. Started at requested baseline `ee0c132`; pre-existing production changes were preserved.
- HEAD advanced externally during the audit to `29e61f5` via `aaf6cab`. This agent executed no commit/push/merge/delete command. Recheck status/HEAD before continuing.
- Agent-authored files: updated audit and matrix; new handoff, isolated probe `docs/phase-00-checks.py`, command log. No production code changed by this agent. The probe was included in a concurrent commit; do not amend/reset it without instruction.
- PASS: syntax/imports, offscreen mocked cancellation, PNG MIME and Unicode/ZWJ round-trip, local Sinhala model loading, one synthetic English OCR sample (0 CER/WER).
- FAIL: existing pip consistency; fresh offline install without supplied wheels; stale AI test; same-second output uniqueness; punctuation retention; hidden-controller assertion (visible 1x1).
- NOT RUN: real capture/tray/shortcut, compositor cancellation, external paste, multi-monitor, Sinhala/mixed accuracy, PDF/import/release journeys. Clean online installation also unverified. Physical results are needed before claiming these work.
- Next **one proposed task**: canonical `main.py` production launcher (including generated desktop entry) and controller visibility lifecycle; acceptance tests are numbered in the matrix. Review these documents and explicitly request that bounded Phase 1 slice before implementation.
- No AI integration/API keys/dependencies added. Complete offline Sinhala/English/mixed OCR and image/PDF workflows and the non-AI release before Ask AI.

Final index observation: documentation was staged by an external actor during the audit (this agent ran no `git add`). `git diff --cached --check` reports an extra blank line at EOF in the staged command-log snapshot. The current worktree command log has subsequent content and `git diff --check` passes. Preserve/review the external index before any approved commit; do not claim staged whitespace validation passed.

## Latest acceptance follow-up — 2026-11-14

**Phase 1 cannot close; Phase 2 must not begin.** Read [phase-01-acceptance.md](phase-01-acceptance.md), which supersedes earlier assumptions about the successful registration message.

Read-only Git inspection started at `f9858ca` on `fix/phase-01-app-lifecycle`, with no staged files and the same two prior unstaged edits (`docs/phase-01-command-log.txt`, `test_global_shortcut.py`). Both preserved byte-for-byte. Historical commits' initiating process remains unidentified; metadata alone is not provenance. No Git mutation or production-source edits performed in this verification.

Fresh result: 20 automated tests PASS. Canonical main and installed GIO launcher run on Wayland; hidden controller/no startup overlay in Qt state, one actual launcher process, duplicate rejection and cleanup confirmed. Physical key/Esc/tray/visual/capture/paste checks remain NOT RUN.

New confirmed issues: portal returned **Ctrl+Alt+S**, while app reports **Ctrl+Shift+S**; preference also uses non-XDG syntax. Registry specifically rejects `io.snapcraft` callers, consistent with inherited Snap VS Code scope. Successful binding does not prove intended app identity. Genuine GNOME app-grid launch outside this context is still required. No binding/settings changes or portal bypass attempted. Fix these Phase 1 issues and finish manual acceptance before advancing.

## Current shortcut implementation update — 2026-11-14

Phase 1 only. **43 automated tests PASS; Phase 1 closure still pending physical acceptance and genuine app-grid host identity. Phase 2 must not begin.** Detailed updated procedure/results: [phase-01-acceptance.md](phase-01-acceptance.md), final update section. Exact commands/live results: [phase-01-shortcut-log.txt](phase-01-shortcut-log.txt).

- Request now `CTRL+SHIFT+s`; stable ID `open_capture_menu`. Actual local assignment is still **Press <Control><Alt>s**. It is now shown truthfully in tray Capture, tooltip and status, with a mismatch warning. Existing remembered choices are preserved, not overwritten.
- BindShortcuts descriptions, ListShortcuts verification and ShortcutsChanged drive actual state. Localized descriptions are displayed without guessing; missing/unbound/stale responses do not claim the preferred shortcut is active.
- Explicit tray Configure Shortcut action detects the actual method/signature, including this installed version-1 interface advertising the method. It never opens automatically or resets bindings. It is disabled when Registry identity fails, to avoid configuring the inherited editor identity. Live dialog remains NOT RUN.
- Registry runs first on the same connection using `com.dulmina.aisnippingtool`; detailed `io.snapcraft` rejection is preserved/displayed. No bypass/spoofing attempted. True GNOME app-grid host launch is still NOT RUN; agent-side GIO launches inherit the same editor context.
- Live bounded native Wayland check: requested/actual display correct, version=1, ConfigureShortcuts advertised but blocked by identity, hidden controller, no startup overlay, duplicate instance rejected, clean Quit/thread stop. Physical keys/Esc/tray/paste still NOT RUN.
- Started clean on `fix/phase-01-app-lifecycle` at external `79a7fd9`. External `9755ff4` appeared during implementation and was preserved. This agent ran no stage, commit, reset, clean, branch switch, merge or push commands; recheck HEAD/status before resuming.
- Files authored/updated: `shortcuts/global_shortcut.py`, new `shortcuts/assignment.py`, `main.py`, new `ui/shortcut_status.py`, `test_global_shortcut.py`, `tests/test_phase01.py`, new `tests/test_shortcut_assignment.py`, `docs/phase-01-acceptance.md`, `docs/handoff-summary.md`, `docs/test-matrix.md`, `docs/baseline-audit.md`, new `docs/phase-01-shortcut-log.txt`. No capture/clipboard/OCR/PDF/AI implementation changes or dependencies.
