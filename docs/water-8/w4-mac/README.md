# W4 (PR #89) on the Mac

Branch `water-4-foam`, with main e5d87f68 (#91) merged. Packaged Development build, Apple M5 Pro.

## Gate: pass

`scripts/gate.sh --scope water`: 149/149 tests, and every view is over Medium 60 and High 45.

| View | Medium fps | High fps |
|---|---|---|
| beam8 | 86.5 | 57.7 |
| beat15 | 82.2 | 50.8 |
| storm | 68.7 | 46.3 |
| marina | 90.6 | 59.1 |
| coast-day | 80.0 | 53.0 |
| gulf-sea | 101.4 | 66.6 |
| helm-eye | 82.4 | 52.0 |
| slip | 77.6 | 50.5 |
| bridge | 95.0 | 60.7 |

## Same-session A/B against main (e5d87f68)

I benched the branch (`ab-branch`), packaged and benched main (`ab-main`), then packaged and benched the branch again
(`ab-branch2`). The first branch pass ran straight after the gate's hour of tests and benches. It came out 1-3 fps under
main on Medium and 1-4.6 fps under on High, all of it on the render thread. Repeated right after main, the branch is level
with main. So the first gap came from the order of the runs, not from W4.

| View | Main Medium | W4 Medium (rerun) | Main High | W4 High (rerun) | W4 High, first pass |
|---|---|---|---|---|---|
| beam8 | 89.4 | 89.1 | 60.0 | 59.6 | 57.6 |
| beat15 | 84.6 | 84.4 | 55.4 | 54.9 | 50.8 |
| bridge | 98.7 | 98.9 | 63.6 | 63.2 | 61.7 |

From the first pass against main (High): marina 59.2 against 61.1, helm-eye 52.9 against 54.6, slip 51.0 against 52.0.
These are inside the same order effect as the rerun rows above. The water GPU slice is within ±0.3 ms on every view.

## The slip's foam grid (the PC's +0.2 ms on High)

Not reproduced here. Packaged, High, slip view, two runs each, alternated:

| | fps | GPU ms | water slice ms | water CPU ms |
|---|---|---|---|---|
| grid on | 51.5, 51.2 | 17.99, 17.98 | 2.43, 2.33 | 0.22, 0.22 |
| `-SailingNoFoamGrid` | 51.2, 51.4 | 17.98, 17.69 | 2.48, 2.37 | 0.19, 0.19 |

On beam8, beat15 and bridge, grid on against off is within 0.5 fps and 0.3 ms GPU (`ab-branch2` and `ab-branch2-nogrid`).
The grid costs about 0.03 ms of water CPU.

## The slip at 6 kn and the shoal ramp at 14 kn

The bench's slip view (LeavetheDock, 10:00, camera yaw 160), uncooked, High:

- `w4-slip6` / `w4-slip14` are beauty frames.
- `-crest` stills use `-SailingDebugFoam=2 -SailingAA=0`.
- `w4-slip14-grid` uses `-SailingDebugFoam=4`.

- **6 kn: clean.** The crest mask has no caps at the docks, only the debug view's isolated-pixel floor (0.26 % of the
  screen, see `capshape-mac`). Blobs of 6 px or more ringed by water: 8, totalling 75 px, all salt.
- **14 kn: the shoal ramp.** Caps fold beside the hulls and pilings in the shallow slips: 21 blobs, 2,151 px. This is
  `ShoalFoldScale` at 14 kn, about 0.8 of the full shoal fold.

![6 kn left, 14 kn right: crests only, the slips' near corner](slip-6-vs-14kn-crest-crop.jpg)

![6 kn (top) and 14 kn (bottom): beauty and crests](slip-6-14kn-beauty-crest.jpg)

## Open-water caps at 12, 16 and 20 kn: unchanged from #85

These are #85's scenes, the free camera 6 m over open water at four headings, counted by `../capshape-mac/count_caps.py`
(10-80 m, crests only, no AA):

| Wind | Cover (W4) | Cover (#85, runs 1 / 2) | Caps (W4) | Caps (#85) | Area-weighted length (W4 / #85) |
|---|---|---|---|---|---|
| 12 kn | 0.059 % | 0.058 / 0.117 % | 32 | 27 | 1.32 / 1.41 m |
| 16 kn | 0.219 % | 0.221 / 0.212 % | 57 | 57 | 2.15 / 2.20 m |
| 20 kn | 0.493 % | 0.501 / 0.497 % | 74 | 76 | 3.10 / 3.26 m |

At 12 kn the four stills hold about 30 caps, so a run swings by 2x, as #85 found. The mask is W8/#85's, as the PR says.

## Files

- `scenes.csv`: every run's arguments.
- `cap{12,16,20}-open{300,30,120,210}-crest-w4.png` plus `.camera.json`: the counted masks.
- `cap20-open300-w4.jpg` (beauty) and `cap20-open300-grid-w4.jpg` (the foam grid alone, 20 kn).
- The slip stills.
