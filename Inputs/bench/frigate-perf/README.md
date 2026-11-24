# Frigate performance on Windows-frigate-3946b08c (Dev), PC, Nov 24 2026 (UTC)

**Package:** `Packaged\Windows-frigate-3946b08c`, the frigate branch at 3946b08c: her 959 meshes imported (a5670d9b)
with the round 3 wake fix. Nothing pushed.

**Settings:** Ultra, 100% screen percentage, 20 s benches after a 3 s warm-up (one warm-up launch first), GPU slices
on, `-SailingBenchTrace`. All on Gulf launch 2 at 12 kn; the args are in `views/args.csv` and every bench.json is in
`views/`.

## Frigate (`-SailingBoat=Comm`) against the J/22 (`-SailingBoat=J22`), same package, same cameras

| View | fps | p99 ms | max ms | GPU ms | base | Lumen | water | clouds+fog | post | game ms | render ms | mem MB (peak) | textures MB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **1080p** | | | | | | | | | | | | | |
| frigate wide | 78.0 | 16.99 | 21.4 | 8.02 | 2.24 | 0.59 | 0.53 | 1.04 | 0.76 | 9.78 | 12.72 | 3,074 (3,778) | 3,328 |
| frigate deck | 75.9 | 17.44 | 21.1 | 8.13 | 2.56 | 0.65 | 0.52 | 0.87 | 0.74 | 9.44 | 13.11 | 3,096 (3,633) | 3,424 |
| frigate gun deck | 76.4 | 18.73 | 21.2 | 8.64 | 3.14 | 0.96 | 0.23 | 0.63 | 0.78 | 10.10 | 12.96 | 3,376 (4,233) | 3,439 |
| J/22 wide | 69.2 | 19.82 | 23.6 | 7.90 | 2.15 | 0.54 | 0.55 | 1.10 | 0.78 | 11.27 | 14.42 | 4,273 (4,659) | 3,569 |
| J/22 deck | 69.9 | 19.65 | 23.1 | 7.84 | 1.97 | 0.56 | 0.60 | 0.95 | 0.78 | 11.84 | 14.23 | 3,669 (4,202) | 3,569 |
| **4K (3840x2160)** | | | | | | | | | | | | | |
| frigate wide | 55.8 | 21.65 | 23.3 | 17.41 | 3.75 | 1.14 | 1.44 | 4.08 | 2.55 | 12.03 | 17.89 | 3,973 (4,424) | 6,145 |
| frigate deck | 56.5 | 21.20 | 22.5 | 17.22 | 3.77 | 1.36 | 1.37 | 3.36 | 2.42 | 11.95 | 17.69 | 3,178 (3,946) | 6,050 |
| frigate gun deck | 54.0 | 21.61 | 24.2 | 18.05 | 5.14 | 2.54 | 0.40 | 2.86 | 2.43 | 12.05 | 18.50 | 3,312 (3,648) | 6,065 |
| J/22 wide | 56.7 | 21.59 | 23.3 | 17.11 | 3.04 | 0.95 | 1.47 | 4.09 | 2.41 | 12.37 | 17.61 | 3,258 (3,760) | 6,434 |
| J/22 deck | 58.6 | 20.68 | 22.6 | 16.59 | 2.91 | 0.96 | 1.59 | 3.67 | 2.40 | 10.97 | 17.06 | 3,173 (3,564) | 6,434 |

The J/22 has no walk map, so there's no gun-deck baseline. The GPU memory figures are the bench's own `mem_used_mb`,
`mem_peak_mb` and `tex_mem_mb`.

- **The frigate costs the GPU little:**
  - At 1080p her GPU frame is 0.1-0.8 ms over the J/22's, at 4K 0.3-1.5 ms.
  - The base pass grows most, +0.6 to +1.2 ms at 1080p; on the gun deck it is +2.2 ms at 4K, with Lumen +1.6 ms.
- **She is CPU-cheaper than the J/22.** The frigate runs 6-9 fps faster at 1080p because her game and render threads
  are 1.5-2 ms lighter: the J/22 carries the MetaHuman crew, rope lay and sail cloth.
- **All within the limits:** every view is over 45 fps at 4K (54.0-58.6) and over 60 at 1080p (75.9-78.0).
- **No hitch:** the largest frame in any of these runs is 24.2 ms.

## The 16-view Ultra set on the same package (1080p, 100%), against main 906c9034's single run (Nov 20)

`visual16/` holds the csv, the 16 bench.json files and `vs-906c9034.csv`.

| View | 906c9034 | frigate branch | Change | GPU ms (906 / branch) |
|---|---|---|---|---|
| beam8 | 74.7 | 68.6 | -6.1 | 6.87 / 6.79 |
| beat15 | 69.6 | 66.6 | -3.0 | 7.65 / 7.36 |
| storm | 69.2 | 69.3 | +0.1 | 7.65 / 7.34 |
| marina | 70.7 | 68.1 | -2.6 | 7.17 / 7.00 |
| coast-day | 70.2 | 68.3 | -1.9 | 7.67 / 7.56 |
| coast-night | 70.8 | 72.6 | +1.8 | 7.48 / 7.28 |
| gulf-sea | 69.6 | 71.6 | +2.0 | 6.26 / 6.22 |
| helm-eye | 76.6 | 69.8 | -6.8 | 7.28 / 7.14 |
| slip | 78.2 | 74.2 | -4.0 | 7.66 / 7.53 |
| bridge | 74.6 | 70.6 | -4.0 | 6.58 / 6.69 |
| crew | 61.4 | **57.8** | -3.6 | 9.11 / 8.77 |
| marina-night | 86.9 | 87.5 | +0.6 | 7.11 / 7.02 |
| far-coast | 63.1 | 66.4 | +3.3 | 6.73 / 6.65 |
| far-coast-night | 68.3 | 73.4 | +5.1 | 5.52 / 5.43 |
| marseille-port | 66.6 | 71.5 | +4.9 | 7.64 / 6.84 |
| stream-run | 69.0 | 67.2 | -1.8 | 8.28 / 8.12 |
| **Mean** | **71.2** | **70.2** | **-1.0** | |

- **No GPU cost with no frigate in view.** GPU time is the same or lower on every view, by -0.8 to +0.11 ms.
- **The fps moves are on the CPU side and go both ways** (-6.8 to +5.1). That's the spread the Nov 20 repeat showed
  for single runs: 91c8c80d's own marseille-port spanned 62.0-73.2. The mean is 1.0 fps under 906c9034's single run.
  A 3x interleaved repeat would settle beam8 and helm-eye, the two largest drops, if wanted.

## Under the limits

- **Under 60 fps at 1080p:** only `crew` (57.8). It's the MetaHuman crew close-up, no frigate, and it was 59.9 at
  91c8c80d and 61.4 at 906c9034, so it's borderline and not new.
- **Under 45 fps at 4K:** none.
- **Hitches over 50 ms:** one, in `helm-eye` (max 52.2 ms) in the 16-view set. None in the frigate or J/22 runs.

Bean's Saved was held aside and restored (7B5CA7BE).
