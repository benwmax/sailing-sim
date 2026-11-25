# Main baseline at fa51d3a6 on the PC, Nov 25 2026

**Main:** **fa51d3a6** ("Merge pull request #833"). It has #822, #824, #825, #829 and #833 over 9291fbf6. Built in a
fresh worktree, which I removed afterwards; I only unlinked the crew link, and all 541 crew files are still there.

- **MSVC build:** Succeeded, 0 errors.
- **All tests (`SailingSim`):** **463 tests, 0 failed**, 37 with warnings, in 152 min. Every group passed (Physics 96,
  Visual 108, UI 46, Smoke 36, and the rest); `test-all.json` has the details.
- **Package:** Development `Packaged\Windows-fa51d3a6`; the cook had 0 errors and 1 warning. It's kept, and the soak runs
  on it.

## 16-view Ultra bench (1080p, 100%, single runs)

The mean is **69.6 fps**, against 9291fbf6's 71.4 and 8a768667's 70.4. `vs-9291fbf6-8a768667.csv` has every view with
its GPU slices.

| View | 8a768667 | 9291fbf6 | fa51d3a6 | fps vs 9291 | GPU ms 9291 to fa51 |
|---|---|---|---|---|---|
| beam8 | 69.4 | 72.8 | 71.4 | -1.4 | 6.73 to 6.69 |
| beat15 | 65.3 | 67.5 | 66.6 | -0.9 | 7.69 to 6.92 |
| storm | 69.1 | 68.6 | 67.0 | -1.6 | 7.57 to 7.54 |
| marina | 67.0 | 66.4 | 69.7 | +3.3 | 7.67 to 7.13 |
| coast-day | 69.4 | 65.4 | **60.9** | **-4.5** | 7.92 to 7.45 |
| coast-night | 67.1 | 71.9 | 72.8 | +0.9 | 7.16 to **7.45** |
| gulf-sea | 69.5 | 72.8 | 76.4 | +3.6 | 6.46 to 6.14 |
| helm-eye | 73.3 | 74.7 | 75.1 | +0.4 | 7.53 to 7.12 |
| slip | 76.9 | 77.9 | 77.8 | -0.1 | 8.03 to 7.56 |
| bridge | 71.1 | 74.0 | 72.2 | -1.8 | 6.83 to 6.62 |
| crew | 59.0 | 60.6 | 59.5 | -1.1 | 9.16 to 8.81 |
| marina-night | 90.1 | 85.0 | **79.2** | **-5.8** | 7.07 to 6.94 |
| far-coast | 66.5 | 66.2 | **62.6** | **-3.6** | 6.92 to 6.65 |
| far-coast-night | 75.0 | 75.6 | **68.2** | **-7.4** | 5.57 to 5.45 |
| marseille-port | 70.7 | 75.3 | **66.2** | **-9.1** | 7.64 to 6.85 |
| stream-run | 66.4 | 68.0 | 68.0 | 0.0 | 8.45 to 8.09 |

**Spread flag: five views dropped more than 2 fps with the GPU unchanged or lower.** They are coast-day, marina-night,
far-coast, far-coast-night and marseille-port.
- In all five, the **game and render threads are 1.0 to 1.8 ms heavier** than on 9291fbf6:

  | View | game ms | render ms |
  |---|---|---|
  | coast-day | 12.65 vs 11.59 | 16.41 vs 15.27 |
  | far-coast-night | 12.00 vs 10.82 | 14.63 vs 13.20 |
  | marseille-port | 11.69 vs 10.32 | 15.07 vs 13.27 |

- The other views' CPU times moved both ways by less than 0.6 ms.
- These are single runs, and the far-shore views have swung this much between single runs before (marseille-port spanned
  62-73 at 91c8c80d).
- But all four far-coast views moving the same way in game and render points to CPU work on the far shore. A 3x
  interleaved repeat of those five views against 9291fbf6 would settle it.

**GPU-time rise flag:** only **coast-night, +0.29 ms** (base +0.16, Lumen +0.12). Every other view's GPU frame is the
same or lower, by up to 0.79 ms (marseille-port).

**crew, repeated 3 times:** 59.6 / 59.5 / 60.1 fps (GPU 11.1 ms). That's borderline at the 60 line, as before.

**Frigate stills** (wide, deck, gun deck): all three load, with 244 outside parts, 87 rig parts and 0 missing. The stills
are in this folder. Bean's Saved was held aside and restored (7B5CA7BE).
