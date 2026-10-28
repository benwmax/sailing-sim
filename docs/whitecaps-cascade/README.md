# Whitecaps after the jitter and the cascades: the solve's sample and a fold refit

`SailingSim.Visual.WhitecapsSeen` went red on main after #377 (chop cascades) landed on top of #374 (jittered long
trains): at 14 kn the threshold solved on one stretch of sea capped 0.177 % elsewhere, against a 0.129 % target (1.37x,
the band is 35 %). #377's own gate tree lacked #374 and passed.

## Why 14 kn failed

The renderer solves the cap threshold each detail frame from the drawn fold (`FWaveDetail::CapThreshold`). It samples
the long trains over a patch about 170 m wide (every other chop texel, 1.31 m apart). `SailingSim.Visual.WhitecapSolveSpread`
(new) solves on one stretch and reads the cover on eight others: four later times, 0.9 and 2.7 km off. With the 170 m
patch, 14 kn's solve stretch is a quiet one. **Every** other stretch caps more (1.15-1.69x, mean 1.37x), so the
failure was a biased solve, not noise. A 170 m patch holds only a few of the jittered trains' wave groups.

| Wind | 170 m patch: cover elsewhere / target, mean (range) | 1.7 km: mean (range) |
|---|---|---|
| 12 kn | 1.09 (0.83-1.23) | 0.99 (0.77-1.36) |
| 14 kn | **1.37 (1.15-1.69)** | 1.07 (0.90-1.26) |
| 16 kn | 1.11 (0.87-1.33) | 1.03 (0.89-1.16) |
| 20 kn | 0.92 (0.81-1.08) | 1.02 (0.85-1.15) |
| 25 kn | 1.05 (0.91-1.17) | 1.06 (0.97-1.18) |

## The fix

- **The solve's sample.** The long trains are sampled over about 1.7 km (13.1 m between samples, the same count: no
  extra cost). The chop is still read at its own texel. The three CPU copies in `WaterTests.cpp` follow it.
  `WhitecapSolveSpread` holds each wind's mean within 15 % at 1.7 km.
- **The drawn fold, refit by the capshape-mac method** (`docs/water-8/capshape-mac/`). On screen the cover had drifted
  from its CPU copy since that fit: main drew 1.6-2.0x the target at every wind. With the fair solve it still drew
  1.4-2.1x. The excess over each wind's logged solve slope (`-SailingDebugCaps`: 0.023 at 12 kn, 0.0245 at 14, 0.0215 at
  16, 0.030 at 20) gives the scale that lands it: 0.997 at 12 kn, 0.948 at 14, 0.938 at 16, 0.910 at 20.
  `DrawnFoldScaleAt` is now 0.97 - 0.0075 (U - 12 kn) (was 0.94 - ...). That is the same slope, 0.03 higher, within
  0.007 of 14-20 kn. 12 kn's 29 caps asked for more. It is held at 0.97 below 12 kn and never under 0.85. The likely
  cause, not isolated: the cascades' long chop folds deeper on screen than in the CPU's sample.

## Cover, 10-80 m, open water (crests only, no AA, four headings, the capshape-mac views)

| Wind | Lake target | Main (ca2bfb4e) | 1.7 km solve | + fold refit | Refit / target |
|---|---|---|---|---|---|
| 12 kn | 0.076 % | 0.127 % (1.67x) | 0.163 % (2.1x) | 0.113 % | 1.49x (22 caps) |
| 14 kn | 0.129 % | 0.251 % (1.95x) | 0.175 % (1.36x) | 0.130 % | 1.01x |
| 16 kn | 0.203 % | 0.372 % (1.83x) | 0.314 % (1.55x) | 0.235 % | 1.16x |
| 20 kn | 0.435 % | 0.723 % (1.66x) | 0.631 % (1.45x) | 0.512 % | 1.18x |

As in capshape-mac, 12 kn's four stills hold only about 22-29 caps, so a run swings by up to 2x there. 14-20 kn are
back where that fit left them (1.07-1.16x). Cap size is unchanged (area-weighted length 1.6-1.8 m at 12-16 kn, 2.5 m at 20).

## The CPU checks after

`WhitecapsSeen`, the solved threshold on other water: 12 kn 0.069 % (0.91x), 14 kn 0.144 % (1.12x), 16 kn 0.189 %
(0.93x), 20 kn 0.462 % (1.06x), 25 kn 0.938 % (1.01x). No test's band changed.

## Files

`cap{12,14,16,20}-open300-crest-{before,after2}.png` (+ `.camera.json`): main and the fix, one heading each. `scenes.csv`:
every run (`-before` main, `-after` the 1.7 km solve alone, `-after2` the fix). Counts: `../water-8/capshape-mac/count_caps.py`.

## Gate (`scripts/gate.sh --scope water`, packaged, the Mac)

Pass: 264 tests, every view over Medium 60 and High 45 (`gate-water.csv`): beam8 58.7, beat15 54.3, storm 46.8,
marina 56.0, coast-day 52.7, gulf-sea 62.4, helm-eye 59.7, bridge 59.2 on High; storm 68.4 on Medium.
