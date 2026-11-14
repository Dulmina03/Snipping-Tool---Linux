# Paste this task into Codex Desktop / Codex Work

**Project:** `Dulmina03/Snipping-Tool---Linux`  
**Suggested local directory:** `~/Projects/ai-snipping-tool` (verify — do not assume).

```text
I want to resume and finish my existing Linux Snipping Tool, not start again.
Repo: https://github.com/Dulmina03/Snipping-Tool---Linux

FIRST, read AGENTS.md, AI_Snipping_Tool_Codex_Build_Plan.md, docs/baseline-audit.md and docs/test-matrix.md in this checkout. If any of them are missing, tell me before proceeding and use the instructions in this message.

Start with Phase 0 — baseline audit — ONLY. Treat September 3, 2026 commit ee0c132ece526748b876167c76f434886627f84d as the GitHub baseline to compare against, not an assumption that my local checkout is identical.

1. Inspect `pwd`, `git status --short`, `git branch -vv`, `git log -5 --oneline`, remote URL and any local uncommitted work. Do not discard or overwrite local modifications. Create `chore/phase-00-baseline-audit` from the appropriate base only if it will not conflict with existing work.
2. Inspect the actual main.py, ui/capture_menu.py, ui/overlay.py, capture/*, shortcuts/global_shortcut.py, ocr/ocr_engine.py, utils/clipboard.py, requirements.txt, desktop entry and tests.
3. Check Ubuntu/GNOME/Wayland runtime, Python/PySide6 versions, portal support, and Tesseract trained language packs `eng` and `sin`.
4. Run safe syntax checks and relevant available tests. When tests need physical GUI interaction, guide me to exercise them and report NOT RUN until observed.
5. Fill in docs/baseline-audit.md and docs/test-matrix.md with the REAL observed results; distinguish confirmed bugs from risks.
6. Identify old/disconnected code and stale tests. Preserve working capture, OCR and clipboard code; do not remove PipeWire experiments without reviewing references.
7. End with the ONE smallest implementation task for Phase 1: reconcile the canonical production entry point and desktop launcher, and prevent a blank controller window from appearing on shortcut activation. Do not implement Phase 1 in this first run; give me exact acceptance tests so I can approve it.

Non-negotiable: Sinhala + English + mixed-language offline OCR and PDF/images must be completed before AI integration; Ask AI is the FINAL phase. Do not implement AI or API key handling now. Avoid hidden network uploads or telemetry.
Do not commit, push, merge, delete user files, or rewrite the project without my permission. Report all commands, changed files and test outcomes accurately.
```

After Codex finishes Phase 0, review its `docs/baseline-audit.md` and `docs/test-matrix.md`. Then ask it to implement **only Phase 1** and test the launcher/window-lifecycle fixes. Do not skip the acceptance gate.
