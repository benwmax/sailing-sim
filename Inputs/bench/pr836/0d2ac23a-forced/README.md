# #836 at 0d2ac23a (tide-step dead band): forced steps and a parked boundary run, for the record (PC, Nov 26 2026)

**#836 is merged** (main 412440c8). These runs are on its last head, 0d2ac23a, in the Development package
`Windows-pr836-0d2ac23a`.

**Setup:** Galveston, from the soak's Bolivar Roads start, 4K windowed. Each run writes a `*-tide-steps.txt` with its
"Tide step" lines.

| Run | Settings | fps | p99 | Max | Peak render ms in each 20 s window | Frames > 50 ms |
|---|---|---|---|---|---|---|
| forced-ultra | Ultra, demo, clock 15:00, `-SailingTideStepEvery=20`, 120 s | 41.1 | 54.8 | 83.9 | 84 / 78 / 90 / 73 / 70 / 62 | 85 |
| forced-medium | Medium, the same | 78.9 | 27.8 | 53.8 | 49 / 48 / 50 / 49 / 51 / 56 | 4 |
| parked-boundary | Ultra, no autopilot, `-SailingKeepStart`, clock 15:30, 300 s | 53.0 | 23.1 | 53.5 | 24-26 in every window except the step's: 53 | 3 |

## The dead band: no flapping

- **Parked across a step boundary:** in 5 minutes she drifted from the start while the tide moved through a boundary. The
  followers stepped **exactly once**, from -42 to -44 cm at frame 11,372 (about 3.6 min in), and never back.
  - That step's frame peaked at 53 ms of render thread; every other window stayed at 24-26 ms.
  - In the 45-min soak on d5be42d, without the dead band, the followers went -40/-38/-40/-38 within 1-3 frames at a
    boundary.
- **Forced steps:** each run has exactly one "Tide step" line per forced step (7 in 120 s), alternating -36 and -38 cm,
  with no extra flips between them.

## The worst frames around steps

- **Medium:** each forced step peaks at 48-56 ms of render thread. Only 4 frames in 2 min go over 50 ms. That matches
  d5be42d's Medium run (45-52 ms).
- **Ultra:** steps peak at 62-90 ms, with 85 frames over 50 ms. **Read this with care: this run was the package's first
  launch.**
  - The package was built at 22:17 and never run before, and `../../gt-regression-823/` shows that a fresh package's
    first run is heavier on this PC (game thread +6 ms, everything slower).
  - d5be42d's warm Ultra pairs had steps of 48-60 ms.
  - A second Ultra run of this package would give the fair number. I can add it in a free slot.

Bean's Saved was held aside and restored for every run (7B5CA7BE).
