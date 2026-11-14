# Phase 2 Task 3 — Capture performance and long-run stability

## Baseline recorded before production changes — 2026-11-14

User confirms Phase 1 accepted, Task 1 all six physical tests PASS and Task 2 all seven physical tests PASS on one monitor at 100%. Mixed-monitor and actual fractional-scaling acceptance remains pending. Only Task 3 is authorized here.

Started clean at `b9d5995` on `main`: reflog showed an external fast-forward from the Phase 2 branch. Safely returned to existing `fix/phase-02-capture-reliability`, which pointed to the identical commit. No history or index changes.

Baseline command: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v`: **132 PASS, 8.628s, exit 0**. Benchmark command: `QT_QPA_PLATFORM=offscreen .venv/bin/python tests/capture_performance_probe.py /tmp/snipping-task03-before.json`. Raw aggregate observations are preserved in [phase-02-task-03-before.json](phase-02-task-03-before.json).

Public seeded-noise 1600×900 PNG, Rectangle 1200×700, three warmups then 50 alternating Rectangle/Full Screen operations using the actual controller and clipboard helpers, isolated offscreen QApplication. No screenshot contents or extracted text logged. Monotonic timings, nearest-rank p95; 25 samples per save mode, 50 for delivery. Toast rendering excluded; portal is a controlled asynchronous fixture, not GNOME performance or permission timing.

- Activation to overlay show returned: median 54.378 ms, p95 113.332 ms. This does not measure a physical global key or compositor presentation.
- Fixture portal wait: median 28.125 ms, p95 33.964 ms (requested delay 10 ms plus Qt/async scheduling and fixture copy).
- Rectangle decode/crop/save combined: median 250.928 ms, p95 279.198 ms. Nested PNG save: median 197.856 ms, p95 221.581 ms. Do not sum overlapping measurements.
- Full Screen encoded-file copy: median 2.846 ms, p95 3.510 ms.
- Clipboard publishing, including image decode and PNG MIME encoding: median 235.342 ms, p95 323.975 ms.
- Selection to delivery: median 370.255 ms, p95 464.674 ms.
- Overlay close: median 0.151 ms, p95 0.177 ms; this times close scheduling, not compositor presentation/deferred deletion.
- Real existing English OCR subprocess, public fixture, three samples: median 2140.262 ms, max 2210.164 ms. Sample count insufficient for meaningful tail latency; no OCR algorithm change planned.
- Qt 1 ms heartbeat maximum gap: **514.882 ms**. Confirmed synchronous decode/crop/PNG save blocks the GUI, followed by GUI clipboard encoding. Portal wait and OCR are already asynchronous.
- RSS after warmup/10/50 captures: 114312/104792/104988 KiB; nine file descriptors throughout, two threads. No monotonic leak demonstrated. After shutdown six descriptors, two threads; allocator RSS is not equivalent to live-object ownership.

Targeted plan supported by these measurements: move only Pillow/file work to a bounded off-GUI job, retain GUI mapping snapshots and all Qt pixmap/clipboard operations on the GUI thread. Drain a cancelled file operation before allowing another capture or closing its executor; never publish its late result. Preserve saved files, atomic filename publication and real focused overlay through clipboard delivery. Do not rewrite clipboard/OCR/portal/toolbar/shortcut components to chase arbitrary speed targets.

Verification and after measurements will follow below.
