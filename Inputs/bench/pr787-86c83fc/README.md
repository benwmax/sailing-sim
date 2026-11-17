# PR #787 (feedback #26 water stutter) at 86c83fc2, on the PC

**Build:**

- Head **86c83fc2**, merged locally with main **c0d81614** (not pushed; worktree at 3f4a7885). Main has since moved to 87bb95b1 and then e1561a60; this check stands on c0d81614.
- MSVC clean. All the targeted tests pass, and so does the full suite (388/388): `Inputs/bench/pr-checks-nov15/pr787-86c83fc.md`.

**Package:** Development, the new `Packaged/Windows-86c83fc`, 4 min, of that merged tree.

**All runs:** through the branch's own `bench-win.ps1` with the PID-only stop.

- **Saved:** Bean's Saved was held aside and restored each time (B57AA3AF).
- **Foreground:** 0 on every run; I don't move windows or send input.
- **Vsync:** off. While benching, the game skips the player's vsync setting (`USailingSettings::IsMeasuring`), so it runs on the engine default `r.VSync` 0.

## 1. The tester's repro: 4K Ultra, -SailingBenchTrace

- **Args:** `-SailingWorld=ray-hubbard -SailingBoat=J22 -SailingStartAt=8825,-367,163 -SailingWind=20 -SailingTWA=-160 -SailingScreenPct=100 -SailingBenchTrace`.
- **Runs:** as is, and with `-SailingClassicClock`; 3840x2160, `-Seconds 20`.
- **Files:** `repro/*.frames.csv`; command lines in `repro/args.csv`.

| Run | frames (3-23 s) | mean ms | p99 ms | max ms | stddev ms | fps |
| --- | --- | --- | --- | --- | --- | --- |
| as is (smooth render time) | 1026 | 19.50 | 23.93 | 26.88 | 1.36 | 51.3 |
| `-SailingClassicClock` | 1042 | 19.18 | 22.74 | 26.86 | 1.44 | 52.1 |

- **The distributions match**, within about 0.3 ms mean and 1 ms p99. That is what the fix should do: same frame times, smoother water.
- **The end-of-run frame:** each trace's final frame (t 23.4 s) is over a second, 1124 and 1167 ms. That is the bench's own screenshot and GPU-profile capture after the measured window, not gameplay, so the table stops at 23 s.
- **Counting from 3 s to the end** (that frame included): mean 20.51 against 20.24, stddev 33.9 against 35.0. The large stddev is that one frame.

**Capture:** bench-win has only `-Record`, which saves still PNGs at an interval: `-SailingRecord=4`, 10 frames 0.4 s apart. Both runs were recorded separately from the timed runs, because recording drops fps.

- **Recorded fps:** 29.7 as is, 30.3 classic.
- **What the frames can't show:** stills 0.4 s apart can't show judder between successive frames, and there is no video capture path in bench-win. So **the frames.csv tables above are the evidence**; whether the water looks smooth needs a live look.
- **Files:** the first recorded frame of each run is in `repro/repro-<run>-rec-frames/` for reference.

## 2. 16-view Ultra 1080p bench: Windows-86c83fc against Windows-ecd4ed1c

- **Order:** back to back, `bench-visual-win.ps1 -Tiers Ultra -Extra '-SailingScreenPct=100'`.
- **The main build:** ecd4ed1c is the newest main package on the PC. It is **not** the c0d81614 that #787 was merged with, so the gap below is #787 *plus* main's merges from ecd4ed1c to c0d81614.

| View | fps 86c83fc | fps ecd4ed1c | change | game ms (787 / main) | render ms (787 / main) | GPU ms (787 / main) |
| --- | --- | --- | --- | --- | --- | --- |
| beam8 | 71.2 | 70.6 | 0.6 | 9.81 / 9.88 | 14.03 / 14.16 | 6.82 / 7.19 |
| beat15 | 68.6 | 67.5 | 1.1 | 11 / 10.91 | 14.53 / 14.76 | 7.81 / 7.64 |
| storm | 62.5 | 72.3 | -9.8 | 13.99 / 11.93 | 15.93 / 13.79 | 7.56 / 7.52 |
| marina | 69.6 | 69.2 | 0.4 | 9.6 / 9.6 | 14.35 / 14.44 | 7.01 / 7.06 |
| coast-day | 65 | 69.7 | -4.7 | 11.48 / 10.63 | 15.37 / 14.33 | 7.65 / 7.46 |
| coast-night | 69.4 | 72.8 | -3.4 | 11.19 / 10.44 | 14.39 / 13.71 | 7.3 / 7.46 |
| gulf-sea | 71.1 | 75.3 | -4.2 | 11.28 / 10.15 | 14.03 / 13.27 | 6.33 / 6.52 |
| helm-eye | 66.1 | 74.2 | -8.1 | 10.58 / 9.29 | 14.76 / 13.35 | 7.34 / 7.05 |
| slip | 75.4 | 75.7 | -0.3 | 9.91 / 9.47 | 13.24 / 13.18 | 7.46 / 7.74 |
| bridge | 73.6 | 73.7 | -0.1 | 9.62 / 9.5 | 13.58 / 13.57 | 6.71 / 6.53 |
| crew | 60.3 | 61.6 | -1.3 | 10.98 / 10.78 | 16.57 / 16.22 | 9.01 / 8.87 |
| marina-night | 86.5 | 86.8 | -0.3 | 7.91 / 7.97 | 11.54 / 11.51 | 7.27 / 7.32 |
| far-coast | 67.8 | 66.7 | 1.1 | 11.29 / 11.51 | 14.74 / 14.98 | 7.03 / 6.71 |
| far-coast-night | 74.1 | 75.5 | -1.4 | 10.85 / 10.7 | 13.46 / 13.21 | 5.49 / 5.44 |
| marseille-port | 72.8 | 70.1 | 2.7 | 10.31 / 10.96 | 13.72 / 14.23 | 7.43 / 7.52 |
| stream-run | 67.8 | 68.5 | -0.7 | 11.22 / 11.19 | 14.74 / 14.58 | 7.84 / 8.35 |

- **Means:** 70.1 fps against 71.9.
- **Unchanged:** GPU time on every view.
- **Slower:** storm (-9.8 fps), helm-eye (-8.1), coast-day (-4.7), gulf-sea (-4.2) and coast-night (-3.4).
  - On those views the game thread is 1-2 ms slower, and on storm, helm-eye and coast-day the render thread too.
  - These are the views with a boat in the water. Views without (marina-night, slip, bridge, far-coast) match within about 1 fps.
- **Possible causes:** #787 drawing the water and boats at the render time between steps, or something merged into main between ecd4ed1c and c0d81614.
- **Not separated here:** splitting the two needs a c0d81614 (or e1561a60) main package benched beside this one.

## 3. Helm-eye through a tack, High and Ultra at 1080p (sim thread's ask)

- **Args:** `-SailingWorld=Lake -SailingLaunch=1 -SailingCapture=HelmEye -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingHour=15 -SailingTWA=45 -SailingDemo -SailingScreenPct=100`.
- **Traced runs:** `-SailingBenchTrace`, 20 s (`tack/*.frames.csv`).
- **Recorded runs:** separate, one frame a second for 21 s (`-SailingRecord=21 -SailingRecordInterval=1`), plus one Ultra chase-view run (no capture arg) for the boat-in-water check.
- **Command lines:** `tack/args.csv` (traces) and `tack/args-recordings.csv`.
- **The tack:** the demo turns at about 13-18 s of boat time, head to wind at 16 s (`tack/*.telemetry.csv`). The stills are frames 6, 13 and 18 (about 9, 16 and 21 s): before, during and after.
- **Retake:** my first recording ran only 12 s, so its frames all came before the turn. The `tack2` recordings replace it.

| Run | frames | mean ms | median ms | p99 ms | frames over 2x median | fps |
| --- | --- | --- | --- | --- | --- | --- |
| High | 1576 | 13.33 | 12.65 | 17.73 | 6 | 75.0 |
| Ultra | 1510 | 13.92 | 13.43 | 20.48 | 2 | 71.8 |

**Stutter:** yes, as game-thread hitches. Frames over 30 ms, apart from the end-of-run screenshot frame at about 23.3 s:

| Run | When (trace time) | Frame | Game thread | Render thread |
| --- | --- | --- | --- | --- |
| High | 4.2 s | 126 ms | 126 ms | 11 ms |
| High | 5.8 s | 68 ms | 68 ms | 10 ms |
| High | 8.9 s | 134 ms | 133 ms | 12 ms |
| High | 16.8 s | 126 ms | 125 ms | 12 ms |
| High | 21.5 s | 105 ms | 105 ms | 12 ms |
| Ultra | 9.45 s | 72 ms | 71 ms | 12 ms |

- **Where they are:** in the game thread only; render, RHI and GPU stay normal.
- **What I can't tell:** the trace clock and the boat-time telemetry aren't on the same base, so I can't say which hitch falls exactly at the tack.
- **Not checked:** these hitches weren't compared against `-SailingClassicClock` or main. That would be the next run if the fix thread wants their cause.

**Boat and water:** no offset seen.

- **Chase view at 1:1** (`tack/tack2-ultra-chase-waterline-*-1to1.png`, before, during and after): the hull sits in the water with its waterline, bow wave and wake attached. No gap under the hull, no hull sunk into the surface, no wake trailing off the stern.
- **Helm-eye stills** (`tack/tack2-*-helm-*.png`): the deck and water move together through the turn, with nothing visibly lagging.
- **Caveat:** one frame a second can't show a one-frame lag, so this rules out only a visible, steady offset.
