# Phase 2 Task 2 — Display mapping

Work in progress, 2026-11-14. Phase 2 Task 1 is physically accepted by the user (all six acceptance tests PASS). Task 2 only; no Freeform or AI work.

## Confirmed limitations before changes

- Production Rectangle uses only the union width/height of Qt screens, then independently scales X/Y by screenshot dimensions. It loses the virtual origin and freezes neither layout nor image mapping. The compatibility selected-area helper does a similar conversion with different edge rounding.
- Overlay stretches the entire screenshot into one virtual-desktop-sized QWidget. Wayland fullscreen targets an output; requested global positioning/spanning is not reliable. Mixed-DPI monitor layout cannot be inferred from this window or a PNG size alone.
- Screenshot portal v2 returns a file URI, no per-monitor pixel rectangles. Multiplying by QScreen DPR after converting image pixels would risk applying scale twice.
- `(0,0)` is treated as an absent start/end point, preventing a valid corner selection. Out-of-bounds/empty selections are not consistently rejected before Pillow crop.
- This host has one physical eDP-1 1920×1080 display at GNOME scale 1.0, logical layout mode. Physical multi-monitor and other GNOME scale settings are NOT RUN; no settings have been changed.

Implementation and verification results will be added below. Existing Phase 2 branch/history and working state are preserved.
