# Nightly Windows bench, Nov 17 2026 (PC)

- **Build:** main **687f777c** as a Development package, `Packaged/Windows-687f777c` (new; 4 min), warmed once.
- **Runs:** `scripts\windows\bench-visual-win.ps1 -Tiers Ultra -Package Windows-687f777c` on the standard views at 1920x1080, 12 s each with `-SailingDemo`. Two passes back to back, about 7 minutes each, and the shore-station stills ran just before.
- **The kill patch:** I used a temporary copy of `scripts\windows` whose `bench-win.ps1` stops its own game by PID, not by name. The copy was removed afterwards.
- **Saved:** Bean's Saved was held aside and restored (profile hash B57AA3AF).
- **Files:** the per-view `bench.json` and each pass's CSV are in `pass1/` and `pass2/`.

| View | fps p1 / p2 | p99 ms p1 / p2 | GPU ms p1 / p2 | base | lumen | water | clouds/fog | post | game ms | render ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| beam8 | 53.9 / 59.5 | 26.19 / 22.3 | 6.88 / 7.26 | 2.5 | 0.59 | 0.51 | 1.23 | 0.83 | 13.9 | 18.54 |
| beat15 | 51.4 / 56.5 | 26.22 / 23.64 | 7.44 / 7.54 | 2.98 | 0.57 | 0.54 | 1.1 | 0.81 | 15.57 | 19.42 |
| storm | 56 / 58.1 | 26.03 / 24.28 | 7.51 / 7.56 | 2.72 | 0.59 | 0.57 | 1.7 | 0.9 | 15.57 | 17.82 |
| marina | 54.2 / 55.4 | 24.8 / 22.94 | 7.49 / 7.33 | 2.77 | 0.64 | 0.54 | 1.49 | 0.77 | 13.05 | 18.45 |
| coast-day | 55.6 / 54.5 | 23.69 / 26.09 | 7.55 / 7.77 | 3.05 | 0.74 | 0.57 | 1.15 | 0.79 | 14.16 | 17.97 |
| coast-night | 58.5 / 59 | 25.37 / 25.97 | 7.32 / 7.48 | 3.06 | 0.88 | 0.45 | 1.03 | 0.76 | 13.63 | 17.07 |
| gulf-sea | 60.3 / 60.7 | 22.22 / 23.69 | 6.28 / 6.36 | 2.13 | 0.58 | 0.55 | 1.12 | 0.76 | 13.64 | 16.59 |
| helm-eye | 59.2 / 57.9 | 22.34 / 22.62 | 7.54 / 6.96 | 3 | 0.79 | 0.42 | 0.86 | 0.73 | 12.07 | 16.85 |
| slip | 65.1 / 65 | 20.79 / 20.74 | 7.65 / 7.56 | 3.37 | 0.72 | 0.43 | 1.04 | 0.79 | 12.2 | 15.35 |
| bridge | 59.1 / 59.1 | 22.61 / 22.04 | 6.8 / 6.84 | 2.52 | 0.6 | 0.46 | 1.08 | 0.76 | 12.31 | 16.9 |
| crew | 50.3 / 50.6 | 24.37 / 25.73 | 9.05 / 9.28 | 4.07 | 0.98 | 0.39 | 0.94 | 0.74 | 13.84 | 19.88 |
| marina-night | 68.7 / 69.7 | 19.49 / 19.35 | 7.07 / 7.07 | 3.08 | 0.84 | 0.53 | 0.77 | 0.81 | 11.64 | 14.56 |
| far-coast | 50.9 / 53.9 | 24.91 / 25.78 | 6.82 / 7.05 | 2.52 | 0.6 | 0.49 | 1.08 | 0.78 | 16.16 | 19.63 |
| far-coast-night | 55.5 / 58.7 | 25.21 / 25.02 | 5.65 / 5.46 | 1.76 | 0.56 | 0.45 | 0.83 | 0.79 | 15.91 | 18.01 |
| marseille-port | 56.8 / 59.4 | 23.86 / 23.26 | 7.07 / 7.43 | 2.65 | 0.64 | 0.53 | 1.24 | 0.78 | 14.86 | 17.59 |
| stream-run | 56.1 / 55.7 | 28.06 / 26.59 | 8.47 / 7.98 | 2.84 | 0.73 | 0.5 | 2.05 | 0.99 | 14.68 | 17.82 |

The slice, game and render columns are from pass 1.

**Summary:**

- **Frame rate:** 50 to 70 fps on every view in both passes. The passes agree within a few fps; beam8 (53.9 / 59.5) and beat15 (51.4 / 56.5) are the biggest moves.
- **Lowest:** crew, at 50.3 / 50.6 fps. It's also the heaviest GPU view, at about 9.1 to 9.3 ms, with base 4.1 ms.
- **Highest:** marina-night (68.7 / 69.7) and slip (65.1 / 65.0).
- **GPU:** total time is only 5.5 to 9.3 ms everywhere, and gpu_frame is 7 to 11 ms.
- **CPU-bound:** the frame is limited by the render thread (14.6 to 19.9 ms) and the game thread (11.6 to 16.2 ms), not the GPU, as in the Nov 16 station benches. So the fps numbers mostly measure CPU-side cost on this 4090.

**Caveat: the windows were not in front.** Every `bench.json` here says `foreground: 0`. The game windows were not the foreground window, probably because the desktop was idle or locked overnight. I don't move windows or send input. The Nov 16 station benches ran with `foreground: 1`. Windows doesn't throttle a background window the way macOS does, but treat small fps differences with care.

**Against Windows-00b43920:** no view matches. The Nov 16 runs on that package were the shore-station frame-cost views (`env-stations-nov16/cost/`), not the bench-visual set. The closest comparison is in magnitude: those ran 54 to 64 fps with GPU 6.9 to 7.7 ms, in the same CPU-bound regime as tonight's 50 to 70 fps.

No changes were made to the repo or its scripts.
