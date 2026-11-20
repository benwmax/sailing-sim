# main 906c9034 (76a41ea4 + #810 Bluebonnet walkable) on the PC, Nov 20 2026

## Build and tests

The kept main worktree `D:\dev\ss-fix-wt\main` was moved to `906c9034` (smudge-skipped checkout, then `git lfs pull`);
`Decks/SM_Bluebonnet_Below` is 16,658,934 B, as committed.

- **MSVC build:** Succeeded, 0 errors, no C4xxx warnings in project code.
- **Tests:**

| Filter | Tests | Failed | With warnings |
|---|---|---|---|
| SailingSim.Skin | 10 | 0 | 0 |
| SailingSim.Visual | 106 | 0 | 3 |
| SailingSim.Lake | 19 | 0 | 1 |
| SailingSim.World | 8 | 0 | 7 |
| SailingSim.Smoke | 32 | 0 | 1 |
| SailingSim.ShipWalk | 7 | 0 | 0 |

All 182 pass. The warnings are the standing ones (`status.txt`): missing `S_Wind`/`S_GustRumble` samples, git-ignored
`.detail`/`.height` files not in a worktree, and J22HeroMesh's canoe volume note.

- **The merged pr810 worktree is removed.** Its crew junction was unlinked first (the link only; 541 crew files remain),
  and it had 0 tracked changes.

## 16-view Ultra bench

Development package `Packaged\Windows-906c9034` (new, kept), warmed once, then `bench-visual-win.ps1 -Tiers Ultra` at
1920x1080 with `-SailingScreenPct=100`, each view once. The per-view jsons and csv are in `bench/`; the comparison is
`bench/vs-91c8c80d.csv`.

| View | 91c8c80d fps | 906c9034 fps | Change | p99 ms (91c → 906) | GPU ms (91c → 906) |
|---|---|---|---|---|---|
| beam8 | 71.0 | 74.7 | +3.7 | 18.53 → 17.19 | 6.63 → 6.87 |
| beat15 | 66.0 | 69.6 | +3.6 | 21.36 → 20.81 | 6.96 → 7.65 |
| storm | 66.8 | 69.2 | +2.4 | 21.42 → 21.24 | 7.38 → 7.65 |
| marina | 68.2 | 70.7 | +2.5 | 18.69 → 18.46 | 7.14 → 7.17 |
| coast-day | 65.3 | 70.2 | +4.9 | 23.16 → 21.56 | 7.48 → 7.67 |
| coast-night | 72.2 | 70.8 | -1.4 | 19.85 → 21.48 | 7.32 → 7.48 |
| gulf-sea | 67.9 | 69.6 | +1.7 | 20.84 → 20.47 | 6.15 → 6.26 |
| helm-eye | 71.2 | 76.6 | +5.4 | 19.88 → 18.00 | 7.09 → 7.28 |
| slip | 77.7 | 78.2 | +0.5 | 17.03 → 18.27 | 7.64 → 7.66 |
| bridge | 73.0 | 74.6 | +1.6 | 17.63 → 17.59 | 6.58 → 6.58 |
| crew | 59.9 | 61.4 | +1.5 | 21.83 → 21.23 | 8.79 → 9.11 |
| marina-night | 86.6 | 86.9 | +0.3 | 15.15 → 15.67 | 7.08 → 7.11 |
| far-coast | 67.4 | 63.1 | **-4.3** | 21.75 → 23.04 | 6.63 → 6.73 |
| far-coast-night | 73.7 | 68.3 | **-5.4** | 21.84 → 21.55 | 5.42 → 5.52 |
| marseille-port | 71.4 | 66.6 | **-4.8** | 20.37 → 23.87 | 7.42 → 7.64 |
| stream-run | 63.9 | 69.0 | +5.1 | 24.51 → 26.46 | 8.06 → 8.28 |
| **Mean** | **70.1** | **71.2** | **+1.1** | | |

- **The set is 1.1 fps better on average.** GPU time is up 0.0-0.7 ms everywhere, at most beat15's +0.69 ms, so the
  frame rate follows the CPU side.
- **Three views are 4-5 fps down:** far-coast, far-coast-night and marseille-port. Their GPU time is within 0.2 ms of
  91c8c80d, so the loss is on the CPU threads, in the far-coast and Marseille views. Neither #815 nor #810 touches
  them. These are single 12 s benches, and earlier single runs of these views have moved by a few fps from run to run
  (the 70.1/70.4 pair), so they need a repeat before calling it a regression.
- There is no 16-view set for 76a41ea4: its Shipping smoke bench (Ultra Lake, 30 s) was 97.5 fps.

## Bluebonnet below decks on the package

Ultra 1920x1080, `-SailingBench=8`, about 7 s after the walk starts (`below/args.csv`). Every shot logged
"-SailingWalkAt: walking on Below at ...". No material failures.

| Still | Spot | Mean luma (bec7847b, uncooked) | fps | GPU ms | Game ms |
|---|---|---|---|---|---|
| `bb-below-saloon` | -2, 0, 0 | **81.8** (82.5) | 73.6 | 11.43 | 8.65 |
| `bb-below-galley` | 3, 0.8, **0** (as asked) | **87.6** (73.3 was at yaw -90, so not the same view) | 74.7 | 9.69 | 8.45 |
| `bb-below-focsle` | 5.3, 0, 0 | **110.9** (110.0) | 80.4 | 8.94 | 8.28 |

- **The cooked game matches the uncooked stills:** the saloon is 81.8 against 82.5 and the fo'c'sle 110.9 against
  110.0. The galley faces its forward bulkhead here (yaw 0), with the fo'c'sle through the door, so its 87.6 is a
  different view from bec7847b's.
- **Game thread:** in the package it is 8.3-8.7 ms below decks. The uncooked stills read 11.8-12.2 ms, so the +3 ms
  seen there was editor overhead, not the lamps.
- **The look is as at bec7847b:** a very orange saloon, two lamp hot spots, white panelling forward (`below/contact.png`).

Bean's Saved was held aside for the bench and the stills and restored both times; profile 7B5CA7BE. Kept:
`Packaged\Windows-906c9034` and the main worktree at 906c9034.
