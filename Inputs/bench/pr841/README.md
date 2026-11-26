# PR #841 at 9552ab69: forced tide steps swing 3 cm (PC, Nov 26 2026)

**Build and package:**
- New worktree `D:\dev\ss-fix-wt\pr841`, one commit on main 412440c8. MSVC build succeeded, 0 project warnings.
- **`SailingSim.Coast`:** 23 tests, 0 failed (19 succeeded, 4 with warnings), including `TideStep` and
  `TideStepBatched` (`test-coast.json`).
- Development package in the new `Packaged\Windows-pr841-9552ab69`.

**Run:**
- The same Galveston forced-step run as `../pr836/0d2ac23a-forced/`: Ultra 4K, demo, clock 15:00,
  `-SailingTideStepEvery=20`, 120 s.
- **No date pin:** this is Nov 26's tide, the one where 412440c8's 2 cm swing stepped only once.
- One untraced warm-up launch came first.

| Run | Steps after the start | Followers | fps | p99 | Max | Peak render ms in each 20 s window | Frames > 50 ms |
|---|---|---|---|---|---|---|---|
| **forced-ultra (warm)** | **6** | -22, -26, -22, -26, -24, -26, -24 cm | **51.2** | **26.5** | **56.0** | 28 / 55 / 56 / 58 / 56 / 53 / 55 | **7** |
| forced-ultra-warmup (first launch, cold) | 6 | the same | 38.9 | 58.1 | 91.5 | 39 / 73 / 87 / 85 / 92 / 85 / 74 | 96 |
| main 412440c8, warm, pinned to Nov 25 (`../pr836/0d2ac23a-forced/`) | 6 | -36 / -38 in turn | 51.2 | 26.9 | 55.7 | 29 / 56 / 53 / 55 / 56 / 52 / 51 | 7 |
| main 412440c8, warm, Nov 26 (2 cm swing) | 1 | -22, -24 | 51.5 | 24.2 | 54.1 | 25 / 54 / 25 / 25 / 25 / 24 | 3 |

**Findings:**
- **#841 does what it says:** 6 steps in 120 s on the day the 2 cm swing was swallowed, with no date pin. The warm
  numbers match the pinned main run: each step is one frame of 53-58 ms, 7 frames over 50 ms.
- **Some forced steps move 4 cm** (-22 to -26). The 3 cm swing can carry the tide across two 2 cm boundaries at once;
  others move 2 cm (-26 to -24).
  - It's only the forcing; a real tide moves far slower than 3 cm in a frame.
  - A 4 cm step costs the same frame as a 2 cm one here (55-58 ms against 53-56).
- **The cold first launch** (96 frames over 50 ms, steps 73-92 ms) is the first-run effect again.
- **What the step frames spend:** that's in `../pr836/0d2ac23a-forced/README.md`. Mainly `UpdatePrimitive` +10.7 ms,
  `ExecuteCommandList` +7.7, distance fields +4.0, the virtual shadow cache +3.0, and primitives removed and re-added
  (+5.7).

Bean's Saved was held aside and restored for both launches (7B5CA7BE).
