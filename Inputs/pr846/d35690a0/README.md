# PR #846 at d35690a0 on the PC (Nov 27 2026)

**Head:** d35690a0 (the branch tip at the start; the asked head). Its own worktree `D:\dev\ss-fix-wt\pr846-d35690a0`,
Development package `Packaged\Windows-pr846-d35690a0` (warmed once). Nothing pushed to the PR branch.

## Build and tests

| Step | Result |
|---|---|
| MSVC editor build | Succeeded, 0 project warnings, 0 errors |
| `SailingSim.Coast` | 24 tests, 24 passed (5 with warnings), 0 failed |
| `SailingSim.Smoke` | 38 tests, 38 passed (1 with warnings), 0 failed |
| `SailingSim.Coast.KeptKeepsProxy` with a renderer | Success, no warnings (the editor without `-nullrhi`: D3D12, SM6) |

Warnings: four Coast tests can't find `<World>.detail` (`GalvestonBay`, `GulfPassage`, `Marseille`); `KeptKeepsProxy`
under `-nullrhi` notes its skipped proxy checks; Smoke's `AsyncPhysicsMatchesSync` misses the optional
`/Game/Audio/Samples/S_*`.

## The merge gate: the climb doesn't stop

Stationary Galveston (`../../../bench/membisect-galveston/still-95220b32/`'s arguments), `-SailingTideStepEvery=20` (52
forced 2 cm steps), 4K Ultra, 17 min a cell, `-llm -llmcsv -SailingBenchTrace` (`mem-*/`: `memory.csv`, `args.txt`,
`d3d12-unused-per-minute.csv`).

| Cell | switches | private MB/min (minute 3 to 17) | D3D12AllocatorUnused MB/min |
|---|---|---|---|
| 1 | #846 as is | **243.0** | 282 |
| 2 | `-SailingTideBatch=0` | 181.9 | 183 |
| 3 | `-SailingTideRecreate` | 234.5 | 286 |
| 4 | `-SailingTideRecreate -SailingTideBatch=0` | 40.7 | 74 |

95220b32 for comparison (`../../../bench/tide-mem-95220b32/`): baseline 233.5, `-SailingTideBatch=0` 27.5.

- **Cell 1 isn't near flat:** the kept classes leave the climb where it was (cell 1 against cell 3).
- **They also take away most of what `-SailingTideBatch=0` buys:** 182 with them, 41 with the engine's recreate path
  (cells 2 and 4). So the pool growth isn't from recreating proxies; it comes with the batched instance moves, and keeping
  the proxy through a move doesn't avoid it. (The memalloc trace of cell 1 runs next: `memalloc-trace/`.)

## The step hitch

From each cell's frame trace, the longest frame within 1 s of each tide step (51 steps; the median frame is about 20 ms):

| Cell | median peak frame ms | max | median peak render ms | max |
|---|---|---|---|---|
| 1 kept | 81.5 | 175.9 | 19.0 | 52.2 |
| 2 kept, batch 0 | 99.7 | 163.0 | 102.8 | 120.8 |
| 3 recreate | 79.0 | 169.6 | 77.6 | 95.5 |
| 4 recreate, batch 0 | 238.9 | 435.6 | 238.3 | 437.5 |

The kept classes move the step's cost off the render thread (render peak 19 against 78 ms) but the frame still peaks near
80 ms on the game thread. Times are matched by the log's tide-step stamps against the trace's clock, so treat them as
about ±1 s.

## Look check, a 1 m step

`-SailingTideStepEvery=30 -SailingTideStepSize=1` (the log: followers at 10 cm, then -90 cm at 30 s), the still at 45 s.
The camera is fixed at the Kemah channel spot (-310, 1100), 3 m up, looking 215 deg at the Kemah shore and docks about
600 m off, fov 20 (a 1 m offset would be about 18 px at 4K). Files in `look/`; `args.txt` has each line.

- **Day and dusk:** #846 and `-SailingTideRecreate` look the same. `day-shore-diff-x8.webp` is the shore band and their
  difference times 8. Only the foliage's sway and the water's glints differ; no house, dock, pile, shadow or reflection
  edge is offset.
- **The ray-tracing debug view (instances)** drew only the near water bands and black above, the same in both, so it
  can't show the shore either way.
