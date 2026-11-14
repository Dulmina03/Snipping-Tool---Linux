# AI Snipping Tool for Linux — Complete Build Plan

**Project:** AI Snipping Tool for Linux  
**Repository:** https://github.com/Dulmina03/Snipping-Tool---Linux  
**Planning date:** 2026-11-11  
**Development assistant:** Codex  
**Primary target:** Ubuntu 26.04 / GNOME / Wayland; keep architecture adaptable to other Linux desktops  
**Stack to retain:** Python, PySide6 (Qt), `dbus-next`, XDG Desktop Portal, Pillow, Tesseract OCR  
**Core rule:** **AI integration is the FINAL implementation phase. Complete, test, and release all non-AI features first.**

---

## 1. Product vision

Build a polished, reliable, **offline-first Linux snipping and document-text extraction tool** with the everyday simplicity of Windows Snipping Tool and native GNOME/Wayland compatibility.

The product should:

- Open immediately from the global **Alt+Shift+S** shortcut or a tray/menu entry.
- Capture a rectangle, freeform area, selected window, or complete screen.
- Copy screenshots or extracted text to the system clipboard and optionally save files.
- **Accurately extract printed Sinhala, English, and mixed Sinhala+English text** from screen captures, images, and PDFs; also handle documents with an existing text layer without unnecessarily running OCR.
- Offer a readable text-results editor, confidence/review cues, page navigation, and flexible export.
- Offer built-in annotation, history, settings, and an easy-to-install desktop package.
- Keep all screenshot/OCR/document functions local by default. **No cloud dependency or AI service is required for the non-AI release.**
- Introduce **Ask AI only after all the above is complete and verified**.

### Explicit non-goals for the first stable release

- Video recording or streaming via PipeWire.
- Cloud OCR, mandatory accounts, analytics, or hidden background uploads.
- Claiming perfect text recognition on every image or file. Handwriting, highly stylized text, low-resolution scans, damaged PDFs, equations, and complex layouts require clear limitations and user review.
- Supporting every possible proprietary document format from day one. Implement a documented compatibility matrix instead.

---

## 2. Current GitHub baseline — what already exists

The following is based on a source review of the repository's **`main` branch** on 2026-11-11. **Code presence is not proof that behavior works today on the developer's current computer.** Codex must verify it locally.

| Area | Existing code | Baseline assessment |
|---|---|---|
| Application daemon/tray | `main.py` | Implemented, verify startup/lifecycle |
| Shortcut | `shortcuts/global_shortcut.py` | XDG GlobalShortcuts + app identity registration exists; physical keypress needs real-device test |
| Screenshot portal | `capture/screenshot.py` | Implemented; duplicate portal logic exists elsewhere |
| Window selection | `capture/window_capture.py` | Interactive portal capture exists |
| Region selector/overlay | `ui/overlay.py`, `capture/selected_area.py` | Rectangle implemented; coordinate/scaling behavior needs tests |
| Freeform selector | `ui/overlay.py` | Button explicitly disabled (`coming soon`) |
| Action toolbar | `ui/overlay.py` | Screenshot / Extract Text; no functional Ask AI action |
| UI orchestration | `ui/capture_menu.py` | Existing workflow; blocking `asyncio.run()` on UI path |
| OCR | `ocr/ocr_engine.py` | Tesseract + 3 OCR passes; currently no explicit Sinhala+English OCR language selection |
| Clipboard | `utils/clipboard.py` | Qt clipboard, image/text MIME support |
| Screenshot storage | `~/Pictures/Screenshots/` | Exists; some filename paths can collide in the same second |
| Standalone tests | `test_*.py` | Mostly interactive or old UI compatibility tests; little automated regression coverage |
| Desktop launcher | `com.dulmina.aisnippingtool.desktop` | Hard-coded machine-specific Python/project paths; wrong default entry point |
| Legacy/experimental capture | `capture/screen_capture.py`, `capture/native/`, `capture/portal_screenshot.py` | Audit usage; preserve before deciding what to archive/delete |
| Docs/install/CI | repository root | README, standard installer, workflow, license and release documentation not yet established |

### Confirmed or high-confidence issues to track

1. **P0 — Main-thread blocking:** screenshot portal waits and Tesseract runs occur synchronously in Qt UI code. Refactor to a safe asynchronous design without calling QWidget/QPixmap from worker threads.
2. **P0 — Launcher mismatch:** `.desktop` entry points at `ui/capture_menu.py` while `main.py` is the background-tray app. Establish `main.py` or a package entry point as the sole production launch target.
3. **P0 — Multi-monitor mapping:** existing screenshot crop assumes a uniform scale between virtual desktop and screenshot image; this is unreliable for mixed-scale displays, negative monitor origins, and differing display arrangements.
4. **P1 — Controller visibility:** `show_from_global_shortcut()` calls `self.show()` to satisfy an old test and may leave an empty controller window present.
5. **P1 — Result names:** several paths use second-level timestamps without collision protection.
6. **P1 — OCR model/language:** `pytesseract.image_to_string(...)` currently lacks explicit `lang='sin+eng'` and trained-model validation.
7. **P1 — OCR quality selection:** choosing the longest of 3 passes can select extra hallucinated characters or noise; preprocessing uses an unbounded upscaling factor for extremely narrow images.
8. **P1 — Incomplete Freeform:** visible but disabled.
9. **P1 — Outdated tests:** shortcut integration test emits the Qt activation signal itself; some capture tests depend on invisible compatibility controls.
10. **P2 — Installation and docs:** source checkout is not equivalent to an installable application.

Codex must **confirm each issue against the local checkout before changing code** and record any discrepancy between local files and GitHub `main`.

---

## 3. Feature specification — non-AI release

### 3.1 Screenshot acquisition

**Modes (all must work):**

- **Rectangular:** drag to select; display dimensions; Esc cancels; no unwanted background overlay in output.
- **Freeform:** draw a closed lasso; pixels outside path transparent in PNG; handle tiny/invalid shapes and cancel.
- **Window:** select a real window through the desktop's portal UI; do not bypass Wayland permissions.
- **Full screen:** select whole desktop or monitor where supported by the portal; avoid promising unsupported compositor-specific options.

**General behavior:**

- `Alt+Shift+S` from an unfocused app, repeatable without ghost windows.
- Tray Capture/Open, Settings, Recent Captures, About, Quit.
- Optional save-to-file, copy-to-clipboard, or both (user preference).
- Clear result feedback; never claim clipboard success unless it was verified appropriately.
- Save to `~/Pictures/Screenshots` by default (user-configurable).
- Timestamp + collision-safe naming; avoid accidental overwrite.
- Handle user cancellation, denied permission, portal timeout, display changes, and session shutdown safely.
- Cross-display test matrix: single monitor, dual monitor, different resolutions, different scales, monitors left/above primary, and rotated monitors where available.

### 3.2 Text extraction — language support

**Mandatory modes:** `English`, `Sinhala`, `Sinhala + English`, and `Auto / Recommended` (auto mode may use quality-tested heuristics; do not pretend detection is perfect).

**Primary local OCR engine:** Tesseract LSTM with installed `eng` and `sin` language models. Provide a setup/health check and guidance when `sin.traineddata` is missing. Compare installed models with optional `tessdata_best` only after benchmarking accuracy and performance; do not change system-wide models silently.

**Text types to test:**

- Common English and Sinhala fonts, including Unicode Sinhala glyph shaping.
- Sinhala + English mixed in one line, headings, labels, paragraphs and UI text.
- Numbers, punctuation, Sinhala combining marks, ZWJ-containing words, diacritics, and line breaks.
- Black-on-white, white-on-black, colored UI, PDFs, scanned pages, photos taken by phone.
- Tables, columns, headings, bullet lists and form fields where feasible.

**Output expectations:**

- Editable, selectable extracted text; copy all / copy selection.
- Preserve Unicode correctly in memory, editor, saved TXT and clipboard.
- Preserve meaningful spaces, line breaks and paragraph order when possible.
- Do not strip or rewrite Sinhala **zero-width joiners** or other meaningful combining characters without explicit user instruction.
- Expose low-confidence sections for review where confidence information is available.
- Provide a layout-aware or plain-text mode; exporting a table as plain text cannot guarantee the original structure.

**Accuracy policy:** Measure with a curated dataset. Never use character count as a substitute for accuracy. Report at least CER (character error rate), WER (word error rate), language, source type, and processing time. Prefer human review for low-confidence content. Define release thresholds after recording a baseline, for example initial acceptance goals for high-quality printed source images: English CER **≤5%**, Sinhala CER **≤10%**, mixed-language CER **≤12%**; these are **project targets to validate, not guaranteed capabilities**. Segregate difficult phone scans and complex layouts in independent benchmark sets.

**Important distinction:** OCR recognizes rasterized text; it is not a universal document parser. Digitally generated PDFs and text-based documents should use direct extraction where possible.

### 3.3 Supported import/export formats

**Required in v1.0:**

| Input | Approach | Notes |
|---|---|---|
| Screen capture | Existing portal + capture pipeline | PNG screenshot as source |
| `.png` | Pillow/Tesseract | Including transparency, grayscale |
| `.jpg`, `.jpeg` | Pillow/Tesseract | Handle EXIF orientation and image compression |
| `.webp`, `.bmp` | Pillow/Tesseract | As supported by Pillow build |
| `.tif`, `.tiff` | Pillow/Tesseract | Support multi-page TIFF deliberately |
| `.pdf` — digital | Extract embedded text first | Prefer original text layer; avoid OCR degradation |
| `.pdf` — scanned | Render pages → Tesseract OCR | DPI option, progress, page selection |
| `.pdf` — mixed | Decide per page/region where practical | Avoid missing image-only pages |
| `.txt`, `.md` | Direct UTF-8/text import | Not OCR; offer editing/copy/export |

**Stretch formats, before AI only if needed:** `.gif` (static frames), `.heic`/`.avif` via optional supported decoders, `.docx` via direct parsing (not OCR), `.odt` where feasible. Explicitly report unsupported types or missing optional codecs. Do not silently discard pages or animation frames.

**Required exports:** UTF-8 `.txt`, clipboard, searchable PDF from scanned PDF or images (clearly marked OCR-derived), plus extracted text preview. **Optional:** Markdown `.md`, JSON with per-page text/confidence and bounding boxes, image export PNG/JPEG/WebP, batch ZIP.

**PDF workflow:**

1. Import PDF and check encryption/password/page count/size limits.
2. Inspect each page for a reliable text layer.
3. Extract digital text directly where reliable.
4. Render scanned/image-only pages at a selected DPI (e.g., benchmark 200/300/400 DPI) with a maintained PDF renderer such as `pypdfium2`.
5. Process only selected pages, using cancellation, progress, timeouts and bounded concurrency.
6. Merge results in page order; show per-page output and source preview.
7. Offer TXT, clipboard, and searchable-PDF export.
8. Never alter or overwrite the input PDF.
9. Avoid unnecessary rendering or OCR of digitally born text; check language-specific encoding and extraction quality.

### 3.4 Screenshot editor and annotation

Required before AI:

- Preview captured image before/after saving (configurable, with fast direct copy mode).
- Crop, resize and rotate.
- Arrow, rectangle, ellipse, line, freehand pen, highlighter, text labels.
- Blur or solid redaction tool; **redaction output must actually remove pixels**, not just draw a removable overlay.
- Undo/redo, reset, save as, copy edited image, export PNG/JPEG/WebP.
- Maintain original immutable image; keep edit operations reversible until export.
- Clear unsaved-changes handling and shortcuts; verify edited image rather than original reaches clipboard.

### 3.5 History and file management

- Recent captures with thumbnail, timestamp, type, source, OCR status.
- Search across filenames and saved OCR text locally.
- Reopen/annotate, recopy, rename, reveal in file manager, delete with confirmation.
- Configurable retention policy and storage management.
- Option not to record private captures in history; delete associated thumbnails and metadata on removal.
- SQLite is reasonable if metadata/search become nontrivial; do not put raw full-size images in database.

### 3.6 Settings, usability, system integration

- Dark/light/system themes; polished compact capture toolbar and consistent icons.
- Keyboard shortcut preference (portal capabilities vary; show actual assigned trigger, conflicts and permission status).
- Default action: screenshot or extract text; saved location; format; auto-save; copy preference.
- OCR language choice (`eng`, `sin`, `sin+eng`), speed/accuracy preset, PDF DPI, page range.
- Start at login (opt-in), tray behavior, clear Quit, single application instance, restart after error.
- Explicit settings reset and export/import where appropriate.
- Correct accessibility: keyboard navigation, Esc, labels, focus, contrast, scalable UI, readable Sinhala font fallback (e.g., Noto Sans Sinhala).
- Don't hijack other applications' shortcuts. Follow compositor/portal approval.
- Diagnostics panel: platform, Qt, portal versions, installed OCR models, paths and self-tests.
- Help/About page with version, licenses, logs location, privacy statement.

---

## 4. Architectural target

Keep the proven Qt/portal/Tesseract foundation but separate responsibilities.

```text
src/snipping_tool/
  app/                  # Application bootstrap, single-instance, tray, lifecycle
  ui/                   # Overlay, toolbar, editor, OCR viewer, history, settings
  capture/              # Portal adapter, mode orchestration, screen-coordinate model
  documents/            # Input detection, PDF text extraction/rendering, import pipeline
  ocr/                  # Tesseract adapter, languages, preprocessing, evaluation
  clipboard/            # Qt clipboard adapter (main-thread only)
  storage/              # Screenshot files, naming, thumbnails, history database
  config/               # Persistent settings, defaults, migration
  jobs/                 # Worker execution, progress, cancellation, structured errors
  diagnostics/          # Health checks, safe logging
  ai/                   # RESERVED ONLY: create/implement in FINAL AI phase
assets/                  # Icons, fonts only if redistribution permits, desktop entry
packaging/               # Desktop launcher templates, install/release scripts
scripts/                 # Development and release helpers
tests/
  unit/
  integration/
  fixtures/
  e2e_manual/
  ocr_benchmarks/
docs/
  architecture.md
  development.md
  privacy.md
  supported-formats.md
  test-matrix.md
  releases.md
```

This is a **target organization**, not a demand to move everything at once. Refactor in small PRs while preserving a runnable product.

### Engineering invariants

- Only the **Qt main thread** may create/manipulate QWidget, QPixmap, and QClipboard.
- Worker threads/processes handle OCR, PDF rendering/parsing, and blocking I/O; hand results back by Qt signals. Carefully integrate asynchronous portal requests without nested event-loop deadlocks.
- D-Bus Request responses must be subscribed reliably; handle cancellation/timeout, unregister handlers, release resources, and ensure only the intended screenshot is used.
- Wayland: use XDG portals; no X11-specific hacks or direct compositor bypass.
- A screenshot/document and its extracted text remain local unless a user later explicitly invokes AI upload.
- Never store API keys, access tokens, or user documents in Git; AI credentials will be designed in the final phase.
- Never overwrite source images, PDFs or existing screenshots; use atomic writes and unique paths.
- Treat external PDF/image inputs as untrusted; enforce limits on pages, decoded pixels, time, and memory.
- Every bug fix includes a focused regression test whenever feasible.

---

## 5. Development phases — execute in this order

**Rule:** Each phase has a hard exit gate. Do not advance solely because Codex says the code compiles. Require actual test output plus any manual checks marked below.

### PHASE 0 — Re-establish repository and baseline
**Branch:** `chore/phase-00-baseline-audit`  
**Goal:** Establish the exact current state before edits.

**Tasks**
- Clone/open repo in Codex; confirm branch, HEAD, uncommitted changes, Python and virtualenv.
- Inventory active vs legacy modules and run paths (`main.py`, `.desktop`, UI standalone).
- Create a clean Python environment from `requirements.txt`; document necessary apt system dependencies (`tesseract-ocr`, `tesseract-ocr-eng`, `tesseract-ocr-sin`, XDG portal implementations).
- Run static compilation/import checks and existing tests; distinguish automated, interactive and obsolete tests.
- Manually test full screen, window, region, shortcut, OCR, clipboard, tray, cancel, quit.
- Create `docs/baseline-audit.md`, `docs/test-matrix.md`, and an ordered issue list.

**Exit gate:** reproducible installation instructions + explicit pass/fail matrix + no undocumented claims about working features. No refactor yet.

### PHASE 1 — Entry point, app lifecycle, safe execution
**Branch:** `fix/phase-01-app-lifecycle`  
**Goal:** A stable background utility that launches and exits correctly.

**Tasks**
- Single canonical production entry point (`main.py` or installed `snipping-tool` console script).
- Fix desktop launcher to use it; remove hard-coded home paths through install-time generation/portable command.
- Prevent duplicate instances and duplicate portal shortcut registrations.
- Remove empty controller window shown for old tests; adjust tests instead of keeping invisible workarounds.
- Prevent UI freezes using signals/workers/async integration; ensure safe cancellation and shutdown.
- Surface useful errors via non-blocking UI and logs; make successful action notifications truthful.

**Exit gate:** background launch/tray/quit stable; real shortcut works while app unfocused; no frozen UI during denied or delayed portal requests.

### PHASE 2 — Reliable capture engine and monitor geometry
**Branch:** `fix/phase-02-capture-correctness`  
**Goal:** Make existing screenshot modes reliable before adding new modes.

**Tasks**
- Consolidate screenshot portal request handling behind one tested adapter.
- Normalize screen-space/virtual-space coordinates, per-monitor DPR, origin offsets and image pixel-space mapping.
- Fix same-second filename collisions, temporary files, file URI parsing, atomic save behavior.
- Confirm screenshot, window, rectangle, cancel, clipboard, save behavior and race conditions.
- Avoid misleading fallback screens when portal denies permission; show actionable error.
- Keep portal compliance and user permissions.

**Exit gate:** complete display matrix; region matches selected pixels on at least tested single- and multi-monitor setups; no unintended saved file on cancel.

### PHASE 3 — Complete Freeform capture
**Branch:** `feat/phase-03-freeform-capture`  
**Goal:** Make the disabled Freeform toolbar item real.

**Tasks**
- Capture closed polygon/path with pen/mouse; smooth lasso selection.
- Produce proper alpha mask and tight crop around path.
- Handle invalid paths, out-of-bounds strokes and Esc.
- Save alpha-preserving PNG and copy to clipboard; avoid unsupported JPEG transparency silently.
- Add automated mask tests using synthetic pixel fixtures.

**Exit gate:** Freeform enabled and usable; outside-of-selection pixels transparent; clipboard/export consistent.

### PHASE 4 — Build the document import and export foundation
**Branch:** `feat/phase-04-document-inputs`  
**Goal:** Accept common file formats before OCR tuning.

**Tasks**
- Implement Open File / drag-and-drop / paste-image workflow with type detection.
- Import PNG/JPEG/WebP/BMP/TIFF and multi-page TIFF; honor EXIF rotation.
- Implement digital PDF text extraction and scanned-PDF page rendering via a maintained library.
- Implement per-page import, pages/size limits, password-protected PDFs and corrupt-file handling.
- Add TXT/MD as direct-text inputs, not OCR.
- Document supported/unsupported formats; determine optional HEIC/AVIF/DOCX/ODT separately.
- Implement UTF-8 TXT export and clipboard as foundation.

**Exit gate:** fixture-based import/export for all required formats; PDF page count/order correct; original files unchanged.

### PHASE 5 — Sinhala + English OCR engine and quality program
**Branch:** `feat/phase-05-sinhala-english-ocr`  
**Goal:** Make bilingual accuracy a first-class verified feature.

**Tasks**
- Install/check `eng` and `sin` Tesseract language data; clear diagnostics if absent.
- Support explicitly chosen `eng`, `sin`, `sin+eng`; compare alternate language order only if measured.
- Benchmark `tessdata_fast` vs `tessdata_best` and appropriate OEM/PSM options (LSTM-only models use OEM 1).
- Remove unlimited upscaling; test adaptive preprocessing (deskew, orientation, contrast, denoise, threshold) against **untouched** images.
- Compare multiple candidate results using recognized confidence and layout consistency, **not just longest text**.
- Preserve Unicode (especially Sinhala combining forms and ZWJ) and avoid destructive cleanup.
- Build a reproducible OCR corpus covering clean prints, mixed scripts, screenshots, dark UI, PDFs, images, tables, and photos.
- Compute CER/WER per language and fixture group, plus latency/memory. Store baseline results and failures, not just a pass label.
- Keep OCR off GUI thread; support cancellation, progress and failure recovery.
- If measured Sinhala accuracy is inadequate, evaluate non-cloud OCR alternatives or fine-tuning only with evidence; do not promise accuracy by switching engines blindly.

**Exit gate:** benchmark report; agreed accuracy thresholds met on the *clean printed* test set, honest limitations on difficult documents, no UI freezes, correct Unicode clipboard.

### PHASE 6 — Full PDF/document OCR and batch processing
**Branch:** `feat/phase-06-pdf-batch-ocr`  
**Goal:** Finish the PDF/JPEG/PNG/etc. promise across real documents.

**Tasks**
- Hybrid PDF processing: direct extraction on reliable text pages; OCR scanned pages.
- Configurable page range, DPI, orientation, task progress, per-page preview, stop/cancel/retry.
- Batch processing of image/PDF files with bounded concurrency and batch-summary results.
- Export per document: TXT, optional JSON, searchable PDF (choose maintained local method and audit licenses).
- Preserve logical reading order as far as possible; report complex table/multicolumn limitations.
- Add large-document safeguards and malformed/encrypted PDF handling.

**Exit gate:** scanned and digital PDFs work; mixed PDF doesn't drop pages; cancel leaves no broken partial outputs; batch progress and errors are correct.

### PHASE 7 — OCR results interface
**Branch:** `feat/phase-07-text-results-ui`  
**Goal:** Make extracted Sinhala/English text usable.

**Tasks**
- Side-by-side source preview and editable Unicode text panel.
- Language indicator, page selector, copy all / copy selection, save text, search, line wrap.
- Clear low-confidence/unreadable sections and let users correct them manually.
- Font fallback for Sinhala; correct clipboard Unicode output.
- Optional layout mode; do not imply perfect table reconstruction.
- Keyboard accessibility and undo/redo for text edits.

**Exit gate:** users can review/correct/export multi-page Sinhala+English without text corruption or UI lag.

### PHASE 8 — Screenshot annotation and editor
**Branch:** `feat/phase-08-image-editor`  
**Goal:** Finish core non-AI image editing.

**Tasks**
- Image preview, crop/resize/rotate, shapes, arrows, pen, highlight, text, blur/redact.
- Undo/redo and save-as flow; copy edited image vs original correctly.
- Real destructive-on-export redaction; verify flattened output cannot recover original obscured pixels.
- Export PNG/JPEG/WebP with clear handling of transparency and quality.

**Exit gate:** all editing tools work from screenshot and imported image; keyboard operations, clipboard and export tested.

### PHASE 9 — Capture/document history and storage
**Branch:** `feat/phase-09-history-storage`  
**Goal:** Reuse earlier captures and OCR results safely.

**Tasks**
- Persist metadata locally with thumbnails, source path, mode, time, optional OCR text.
- Search recent captures and local extracted text.
- Reopen, edit, recopy, reveal, rename, delete, clean thumbnails and metadata.
- Retention/clear history/private mode; default not to duplicate sensitive inputs unnecessarily.
- Handle missing files/renamed folders and database corruption/migration.

**Exit gate:** history survives restart, deletes correctly, obeys privacy controls and never loses a saved original unexpectedly.

### PHASE 10 — Settings, themes, system behavior
**Branch:** `feat/phase-10-settings-and-polish`  
**Goal:** Finalize all user-configurable non-AI options.

**Tasks**
- Settings: save path, auto-save, clipboard policy, image format/quality, capture default, OCR language/model preset, PDF DPI and page range.
- Dark/light/system themes; responsive compact toolbar across resolutions/scaling.
- Shortcut status/permission/conflict UI and configurable shortcut where supported.
- Opt-in autostart, tray controls, single-instance behavior and restart-safe settings.
- Accessibility: keyboard-only flow, readable contrast, Sinhala font fallback, zoom/large text.
- About, Help, diagnostics, privacy and troubleshooting pages.

**Exit gate:** every setting persists through restart, defaults are sensible, no missing/disabled placeholders remain without an explicit explanation.

### PHASE 11 — Tests, security, performance, maintenance
**Branch:** `test/phase-11-quality-hardening`  
**Goal:** Make the entire non-AI application dependable.

**Tasks**
- Replace obsolete UI tests with proper unit/integration suites; keep manual GNOME/Wayland checks where emulation is insufficient.
- Test errors: portal denied/timeouts, shortcut conflict, app exit during work, clipboard ownership, file permission errors, malformed images/PDFs.
- Stress tests: 100 repeated captures, large PDFs, multi-page TIFF, long OCR batches, cancellation, rapid shortcut presses, RAM and temp files.
- Accessibility tests; smoke tests for screenshot + OCR + editor + history.
- CI: static checks, formatting/linting, unit tests, package build; avoid GUI tests that require unavailable portals in headless CI.
- Audit third-party license obligations, document safety limits, and verify no secrets or private screenshots are committed.

**Exit gate:** all automated tests passing; documented manual test matrix signed off; reproducible benchmark results; no open P0/P1 defects.

### PHASE 12 — Packaging, documentation and NON-AI release
**Branch:** `release/phase-12-offline-v1`  
**Goal:** Ship a usable, self-contained **non-AI** release first.

**Tasks**
- Choose distribution strategy: first supported Ubuntu `.deb` and/or well-documented user install script; Flatpak evaluation can follow if portal behavior requires adaptation.
- Create portable desktop file + icon, correct Exec command, install/uninstall path, no hard-coded home directory.
- Document dependencies and Sinhala/English Tesseract trained models; include install-time/first-run checks.
- README with screenshots, feature list, install/run/uninstall, troubleshooting, limitations, supported formats.
- LICENSE, CHANGELOG, privacy policy, third-party attributions; verify installer/binary license compliance.
- CI release workflow/build checks; version/tag `v1.0.0` when ready; clean clone smoke test on supported Ubuntu GNOME Wayland environment.
- Validate startup-from-app-grid, shortcut, capture, copy, OCR, PDF import, history, settings, edit, quit after packaged install.

**NON-AI RELEASE GATE — mandatory before AI:**
- [ ] All screenshot modes including Freeform pass real-device checks.
- [ ] No UI freezes, ghost windows, duplicate instances, or same-name overwrite.
- [ ] Multi-monitor/scaling behavior tested and documented.
- [ ] Sinhala, English and mixed-script OCR meet agreed clean-document benchmarks.
- [ ] PNG/JPEG/WebP/BMP/TIFF, scanned/digital/mixed PDF and TXT/MD workflows pass.
- [ ] Results editor, annotation, history and settings are finished and tested.
- [ ] Clipboard and UTF-8 export preserve Sinhala Unicode correctly.
- [ ] Tests/CI green, no unresolved P0 or P1 issues.
- [ ] Fresh installation and uninstallation are documented and work.
- [ ] Non-AI app can be used completely offline.
- [ ] A tagged non-AI release exists; architecture and user docs are current.

### PHASE 13 — LAST PHASE: Ask AI integration
**Branch:** `feat/phase-13-ask-ai`  
**Start only once Phase 12 release gate has been satisfied.**

**Tasks**
- Add provider-neutral, opt-in AI service architecture with configurable model/provider.
- Add **Ask AI** to capture action list / document viewer only after the non-AI system is feature complete.
- Support user question + image attachment or explicitly selected OCR text, with clear preview of outgoing content.
- Provide explicit consent before screenshot/documents leave the device; default to local-only and never upload silently.
- Store credentials securely using system keyring/appropriate secret service; never log or save raw keys.
- Handle provider limits, network failures, costs, cancellation, response copy/export, and reasonable file limits.
- Add a clean, accessible conversation/answer panel, with explicit labeling that AI answers may be wrong.
- Test with mocked provider calls; avoid expensive/unnecessary live requests in CI.
- Document privacy, model availability, pricing dependence and optional nature of AI integration.

**Exit gate:** Ask AI is optional and does not break or slow the non-AI workflow; no screenshot is sent externally without user action and consent.

---

## 6. Recommended GitHub issue / branch / PR sequence

Use **one focused issue → one branch → one PR**. Keep a protected, releasable `main` branch. Never mix unrelated feature changes in one PR.

| Order | Issue theme | Proposed branch | Evidence required |
|---|---|---|---|
| 00 | Baseline and reproducibility | `chore/phase-00-baseline-audit` | Audit + first pass/fail report |
| 01 | Startup/shortcut/Qt lifecycle | `fix/phase-01-app-lifecycle` | Runtime smoke tests |
| 02 | Portals/crop/scaling | `fix/phase-02-capture-correctness` | Golden-image + real-monitor tests |
| 03 | Freeform mask | `feat/phase-03-freeform-capture` | Transparency + UI tests |
| 04 | Importer/PDF base | `feat/phase-04-document-inputs` | File-format fixtures |
| 05 | Sinhala/English engine | `feat/phase-05-sinhala-english-ocr` | CER/WER benchmark report |
| 06 | PDF and batch OCR | `feat/phase-06-pdf-batch-ocr` | Scanned/mixed-PDF results |
| 07 | Text editor | `feat/phase-07-text-results-ui` | Sinhala Unicode manual test |
| 08 | Image editor | `feat/phase-08-image-editor` | Undo/export/redaction tests |
| 09 | Recent history | `feat/phase-09-history-storage` | Restart/delete/data tests |
| 10 | Settings/UI/accessibility | `feat/phase-10-settings-and-polish` | Preferences + accessibility checks |
| 11 | QA/security/CI | `test/phase-11-quality-hardening` | Regression suite, security checklist |
| 12 | Offline release | `release/phase-12-offline-v1` | Installable release/tag |
| 13 | **AI (last)** | `feat/phase-13-ask-ai` | Privacy/security + integration tests |

**Practical advice:** A phase can contain multiple small PRs if it becomes large; use `issue-<number>` branch suffixes when convenient. Always rebase/update a new phase branch from the latest tested `main` after the previous phase merges.

### Standard development loop

```bash
# Only once, if needed
 git clone https://github.com/Dulmina03/Snipping-Tool---Linux.git
 cd Snipping-Tool---Linux

# At the start of each phase (ensure your worktree is clean first)
 git switch main
 git pull --ff-only
 git switch -c chore/phase-00-baseline-audit

# After Codex changes files: review + test; commit after verification
 git status --short
 git diff --check
 git diff --stat
 # Run phase-specific tests here
 git add -A
 git commit -m "chore: document current snipping tool baseline"
 git push -u origin chore/phase-00-baseline-audit

# Open/review/merge a PR through GitHub or gh CLI
```

*Commit/merge commands are examples, not permission for Codex to perform them automatically.*

---

## 7. Codex working instructions — paste once at the start of the project

Use this as the initial context in Codex, or save it in a repository `AGENTS.md` after reviewing it. **AGENTS.md must remain consistent with this plan** and can point here rather than duplicating every phase.

```text
You are continuing an existing Linux AI Snipping Tool application.
Repository: https://github.com/Dulmina03/Snipping-Tool---Linux
Read AI_Snipping_Tool_Codex_Build_Plan.md before proposing or changing code.

Non-negotiable constraints:
1. Do NOT rebuild from scratch; inspect current source and preserve working behavior.
2. AI integration MUST be the final development phase (Phase 13). Do not create provider code, request keys, or connect any AI service until all Phase 12 release criteria pass.
3. First-class offline OCR for Sinhala, English and mixed Sinhala+English is mandatory. Benchmark accuracy with labeled fixtures; do not claim perfect OCR.
4. Support both scanned and digitally born PDF appropriately, plus PNG/JPEG/WebP/BMP/TIFF and common direct-text formats.
5. Keep Python + PySide6 + XDG Portal + Tesseract unless evidence justifies a deliberate change.
6. On Wayland, respect portal permissions. Never use X11 hacks or capture the screen without the authorized portal.
7. Never run Qt widget/pixmap/clipboard operations in background worker threads. Keep UI responsive for OCR, PDFs and portal waits.
8. Protect user data: no unintended uploads, no overwriting source files, no logging private document contents, and no credentials in Git.
9. One bounded task per change. Add tests, document decisions, and list exact files changed.
10. Do not commit, push, merge, or delete user data without my explicit permission.
11. Run relevant checks and report exact passes/failures. If physical GUI testing is impossible, clearly label it NOT VERIFIED; do not pretend to press keys or visually confirm output.
12. Prefer complete working code changes in the repository, not fragmented suggestions. Avoid unnecessary refactors and regressions.
13. At each phase end, update checklist, docs and concise handoff note. Wait for my instruction before starting the next phase.
```

### Prompt template for EACH phase

```text
Implement ONLY Phase [NUMBER] — [TITLE] from AI_Snipping_Tool_Codex_Build_Plan.md.

Before editing:
- Inspect the relevant existing code, tests and git status.
- State observed problems, a minimal implementation plan and acceptance tests.
- Identify required dependencies and any potential regressions.

Then:
- Implement scoped changes in the existing repository.
- Add/update automated tests and docs.
- Run exact relevant tests and summarize results.
- List changed files, architectural decisions, remaining risks and manual steps.
- Do not start the next phase or AI work.
- Do not commit, push, merge or delete files without approval.

Acceptance gate: [COPY THE PHASE EXIT GATE HERE].
```

### First Codex prompt — ready to paste

```text
We are resuming my older Linux snipping tool in Codex.
Repository: https://github.com/Dulmina03/Snipping-Tool---Linux
Read AI_Snipping_Tool_Codex_Build_Plan.md and follow its order.

Start with PHASE 0 ONLY: repository baseline, reproducible environment, code inventory and regression verification. Do not alter working capture or OCR behavior yet.

Please:
1. Check current branch/HEAD, uncommitted changes, package requirements and Ubuntu/GNOME/Wayland environment.
2. Read the actual startup flow, portal capture code, overlay, shortcut, OCR and clipboard code.
3. Run available tests and mark every check PASS / FAIL / NOT RUN with reasons.
4. Flag stale test harnesses and unsafe/duplicated code. Do not silently delete files.
5. Record available Tesseract language models; in particular check 'eng' and 'sin'.
6. Write docs/baseline-audit.md and docs/test-matrix.md with results and necessary manual checks.
7. Report the smallest actionable Phase 1 task, but do not implement Phase 1 until I approve.
8. Do not add AI integration, AI packages or API keys.
9. Do not commit or push without permission.
```

---

## 8. OCR test corpus and quality scoring specification

**Build the test corpus before changing preprocessing or models.** Treat labeled samples as ground truth; manually verify transcriptions. Keep personal documents out of Git unless explicit permission and redaction.

### Minimum benchmark groups

| Group | Example cases | Main checks |
|---|---|---|
| A — English clean text | 10+ screenshots/scans | CER/WER, punctuation |
| B — Sinhala clean print | 20+ samples across multiple Sinhala fonts and glyph combinations | Sinhala Unicode, CER/WER |
| C — Mixed Sinhala + English | 20+ mixed paragraphs and UI screenshots | Script switching, numerals, spacing |
| D — Sinhala dark UI | 10+ screenshots | Contrast, small text |
| E — PDF digital | 10+ varied documents/pages | Direct extraction correctness |
| F — PDF scanned | 10+ documents/pages | Rendering DPI, OCR accuracy |
| G — Complex layout | 10+ forms/tables/columns | Reading order, loss detection |
| H — Challenging images | 10+ blurry/skewed/phone photos | Honest degraded performance |
| I — Edge cases | Unicode ZWJ, thin fonts, empty images, extreme aspect ratio, corrupt input | Stability and preservation |

Counts above are **suggested starting minimums**, not proof of statistical representativeness. Increase as real errors are discovered; version the corpus and baseline outputs.

### Benchmark log schema

```text
sample_id,language,source_type,font_or_context,image_size,engine_version,
traineddata,psm,preprocess_profile,expected_chars,actual_chars,CER,WER,
processing_ms,peak_memory_mb,notes
```

**Quality evaluation rules:**

1. Compare against human-verified ground truth; record source image and expected UTF-8 text.
2. Keep raw output intact. For scoring, define normalization rules in advance; be careful with Sinhala ZWJ/combining marks.
3. Separate recognition accuracy from layout/reading-order fidelity and from speed.
4. Track low-confidence segments using Tesseract `image_to_data()` or equivalent when practical.
5. Treat original vs preprocessed as independent candidates; no preprocessing is uniformly best.
6. Avoid claiming multilingual accuracy based only on English samples or a single `OCR TEST PASS` message.
7. Test output through the **real GUI editor and clipboard** after backend benchmarks pass.

---

## 9. Complete end-to-end test journeys

Run these manually on a supported GNOME/Wayland machine and automate parts where possible:

**Journey A — screenshot:** From another application press Alt+Shift+S → rectangle → copy image → paste into browser/editor → save correct PNG → capture again within one second → distinct names.

**Journey B — window/full-screen/freeform:** Capture each mode, verify exact pixels/alpha, cancellation, and repeat activation without extra blank windows.

**Journey C — Sinhala OCR:** Capture Sinhala printed page → choose Sinhala → extract → edit a word with combining mark/ZWJ → copy to another text editor → save UTF-8 → reopen without corruption.

**Journey D — mixed language:** Capture mixed Sinhala+English heading, paragraph, punctuation and numbers → select mixed OCR → review predicted errors and CER/WER against benchmark.

**Journey E — scanned PDF:** Import 30-page scanned PDF → select 2–6 → OCR → progress updates → cancel mid-job → retry → per-page preview → TXT/searchable PDF export without altering original.

**Journey F — digital PDF:** Import digital text PDF → direct extract preserves exact text where encoding allows → no unnecessary expensive OCR → copy/export.

**Journey G — photo/document:** Import a JPEG with EXIF rotation, an RGBA PNG, multi-page TIFF, WebP, corrupted file → verify handling and clear failures.

**Journey H — annotation:** Capture → arrow/blur/redaction → undo/redo → copy edited image → verify redacted pixels are not recoverable from output → save as new file.

**Journey I — lifecycle:** Start from desktop app launcher → tray/shortcut → capture → settings → auto-start preference → close windows → reopen overlay → Quit → no orphan background process.

**Journey J — installation:** Fresh non-developer Ubuntu account → install package → verify dependencies, `sin` and `eng` OCR models, launcher, shortcut, clipboard, uninstall/cleanup instructions.

---

## 10. Definition of Done (applies to every PR)

- [ ] Scope matches one issue and phase; no unrelated redesign.
- [ ] New behavior documented, and accessible through actual UI where appropriate.
- [ ] Normal path plus error/cancel/retry/timeout cases covered.
- [ ] Relevant unit/integration tests pass locally; manual Wayland tests recorded as pass/fail/not verified.
- [ ] Source images/PDFs remain untouched; no hidden network transfer.
- [ ] Performance and memory effects considered.
- [ ] Sinhala text round-trips correctly wherever the change affects text.
- [ ] Dependencies are justified, pinned appropriately and license-reviewed.
- [ ] `git diff --check` clean; no private samples, credentials, generated builds or temporary files staged.
- [ ] User reviews changes; merge only after approval.
- [ ] Phase checklist and next-action note updated.

---

## 11. Risk register and priorities

| Risk | Likelihood / impact | Mitigation |
|---|---|---|
| Wayland portal implementation differences | High / High | Feature detection, specific GNOME validation, actionable fallbacks |
| Wrong region coordinates with mixed DPI | High / High | Per-monitor geometry model, golden images and actual dual-display testing |
| Sinhala font/model OCR inaccuracy | High / High | `sin` models, real Sinhala labeled corpus, CER/WER and measured tuning |
| Complex Sinhala ZWJ normalization | Medium / High | Preserve raw Unicode, targeted corpus, don't strip shaping characters |
| Scanned multi-page PDF memory spikes | Medium / High | Per-page worker pipeline, bounded DPI/concurrency, cancel and limits |
| Unsafe or very large PDF/image inputs | Medium / High | Content limits, library updates, corruption tests, resource guards |
| Qt threading/clipboard race conditions | High / High | Main-thread UI work and controlled signals |
| Screenshot capture permissions denied | Medium / High | User-facing portal permission recovery; never bypass Wayland |
| Inaccurate OCR presented as authoritative | Medium / Medium | Editable text, confidence cues, explain limitations |
| Packaging and dependency incompatibility | High / Medium | Clean Ubuntu smoke tests, automated build, trained-model health check |
| Scope creep before AI | High / Medium | Phase gates, defer nonessential optional formats, maintain changelog |

**Recommended priority:** correctness and bilingual OCR > packaging and reliable workflows > visual flourish > optional format expansion > AI.

---

## 12. Reference documentation used for architecture decisions

These references inform the plan; Codex should re-check installation details and library versions when implementing:

- Tesseract supported image formats and PDF limitation: https://tesseract-ocr.github.io/tessdoc/InputFormats.html
- Tesseract official language data, including `sin` / `eng` and `tessdata_best`: https://tesseract-ocr.github.io/tessdoc/Data-Files
- Tesseract model speed vs accuracy tradeoffs: https://tesseract-ocr.github.io/tessdoc/Data-Files-in-tessdata_best.html
- pypdf guide explaining why digital PDFs should not be OCR'd indiscriminately: https://github.com/py-pdf/pypdf/blob/main/docs/user/extract-text.md
- pypdfium2 PDF rendering/package documentation: https://pypdfium2-team.github.io/pypdfium2/readme.html
- GitHub source of truth: https://github.com/Dulmina03/Snipping-Tool---Linux

---

## 13. Final delivery milestones

**Milestone A — Solid desktop capture:** Phase 0–3. Portal integration, shortcut, overlay and all capture modes stable.

**Milestone B — Accurate bilingual document extraction:** Phase 4–7. Sinhala/English OCR backed by benchmark data, common image formats, scanned/digital PDFs, batch processing, review/export UI.

**Milestone C — Complete screenshot utility:** Phase 8–10. Editor, history, preferences, accessibility, system integration.

**Milestone D — Finished offline application:** Phase 11–12. Tested, packaged, documented **v1.0.0 without AI**.

**Milestone E — AI capability (last):** Phase 13. Optional, privacy-conscious Ask AI for screenshots and extracted text.

> **Progress rule:** Finish Milestone D before doing any implementation work for Milestone E. If an early phase uncovers additional required non-AI work, add it before Phase 13 rather than silently skipping it.
