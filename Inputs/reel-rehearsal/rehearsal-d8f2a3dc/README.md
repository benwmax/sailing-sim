# Saturday capture rehearsal on main d8f2a3dc, at 4K (PC, Nov 25 2026)

**Package:** Development `Packaged\Windows-d8f2a3dc`, packaged with `package-win.ps1 -Config Development -Full`. The cook
carries `r.ForceDebugViewModes=1` (#829), and #828's `-SailingViewMode` is on main.

**Command:**

```
reel-saturday.ps1 -Package Windows-d8f2a3dc -Res 4k -ViewModeArg
```

- **Setup:** 3840x2160 Ultra, crew off. Bean's Saved was held aside and restored for every take (7B5CA7BE).
- **Where the frames are:** about 82 GB of PNG on the PC, in `D:\dev\reel\saturday-Windows-d8f2a3dc\<take>\rec`, plus
  `P2-storm-full.mp4` (218 MB) and `P2-storm-scrub.webp` (20 MB).
- **Here:** one preview per take in `previews/`, and the run's status lines in `status-log.txt`.

## Per take

| Take | Frames | Time (s) | Notes |
|---|---|---|---|
| P1-final | 720 / 720 | 875 | Pass 1 was **cut at 474** by rec.ps1's 600 s default timeout; re-run with the 4K timeout |
| P1-lightingonly | 720 / 720 | 828 | Pass 1 was **cut at 527**, the same way; re-run |
| P1-wireframe | 720 / 720 | 217 | With `-SailingViewMode` the sails now draw in wireframe; the sky is still black |
| P2-storm | 800 / 800 | 1654 | Wrote `P2-storm-full.mp4` and the 300-frame `P2-storm-scrub.webp` |
| P3-realday | 300 / 300 | 1226 | |
| P4-topdown | 1 / 1 | 35 | A still, by design |
| P5-then-now | 1 / 1 | 69 | A still, by design |
| R01-dawn-marina | 360 / 360 | 457 | |
| R05-tack-orbit | 420 / 420 | 529 | |
| R06-helm-eye | 360 / 360 | 470 | |
| R09-polar-chase | 480 / 480 | 600 | All frames, but **ran into the 600 s timeout** (the game was stopped at its exit) |
| R10-gust | 420 / 420 | 489 | |
| R12-sunfish | 480 / 480 | 603 | All frames; **ran into the 600 s timeout**, the same way as R09 |
| R13-jibclew | 180 / 180 | 247 | |
| R14-c22-dolly | 420 / 420 | 523 | |
| R21-golden | 420 / 420 | 529 | |
| R22-night | 420 / 420 | 458 | |
| H02-reach | 360 / 360 | 439 | |
| R03-briefing | 240 / 240 | 272 | |
| R08-career | 240 / 240 | 278 | |
| R08b-checkride | 960 / 960 | 1056 | Pass 1 was **cut at 821** by its own 900 s timeout; see below |
| R23-worldmap | 240 / 240 | 291 | |

**Total time:**

| Pass | Takes | Minutes |
|---|---|---|
| Pass 1 | All 22 | 217 |
| Pass 2 | The three cut takes | 46 |
| R08b re-run | One | 18 |

A clean run with the fixed script would be about **4.5 h at 4K**.

## What the rehearsal found, and what changed

1. **4K is about 3x slower per recorded frame than 1080p**: about 1.1-1.3 s of real time a frame, against about 0.35 s.
   - rec.ps1's 600 s default cut P1-final and P1-lightingonly, and only just held R09 and R12.
   - **Fix:** `reel-saturday.ps1` now gives every 4K take 3600 s, unless the take sets its own.
2. **R08b's hold depends on that same rate.** The UI script's `Wait` is 2.6 s of real time.
   - At 4K the 26-Wait hold gave only about 2.5 s of score and certificate (frames 30-90).
   - **Fix:** the hold is now 75 Waits at 4K (26 at 1080p), and R08b's timeout is 2400 s at 4K.
   - **Re-test at 4K:** the score and certificate hold from frame 60 to about 270, **about 7 s**. Then the Logbook comes
     up, with the seeded clean book: 29.9 miles, 8.0 hours, 5 sails.
3. **Takes that had no problems:** P2's MP4 and WebP, the P4 and P5 stills, the menu takes (R03, R08, R23) and every
   R- and H-take wrote all their frames. No crash.

The fixed `reel-saturday.ps1` is in `../saturday-script/`.
