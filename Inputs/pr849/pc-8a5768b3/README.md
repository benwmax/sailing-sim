# PR #849 at 8a5768b3 on the PC (Nov 27 2026)

**Head:** 8a5768b3 "Long-sail memory test: a memory row a minute and a flat/growing verdict in bench.json", parent main
2479e9cf. A reused worktree (`D:\dev\ss-fix-wt\pr852-30b9ea2f`, detached at 8a5768b3), Development package
`Packaged\Windows-pr849-8a5768b3`, warmed once. Nothing pushed to the PR branch. Bean's Saved restored (7B5CA7BE).

| Step | Result |
|---|---|
| MSVC editor build | Succeeded, 0 project warnings, 0 errors |
| `SailingSim.Smoke.SoakMemory` | 1 test, passed |
| `SailingSim.Smoke` | 39 tests: 38 passed, 1 with warnings (`AsyncPhysicsMatchesSync`: the optional `/Game/Audio/Samples/S_*`), 0 failed |

## The 20-minute lake run

`-SailingBench=1200 -SailingBenchTrace`, 4K Ultra, the lake from launch 1, demo, 15:00, crew off (`args.txt`). Exit 0, 1,224 s.

**`pr849-lake20.mem.csv`:** 21 rows, one a minute from 0 to 1,200 s (`t_s`, position, `travelled_m`, `used_mb`, `peak_mb`,
`tex_mb`, `uobjects`, tiles, chunks, re-centres).
- `used_mb` goes 4,126 at 0 s, 4,181 at 60 s, then down: 4,052 at 420 s, 3,590 at 480 s, 3,640 at 600 s, 3,559 at
  1,200 s. `peak_mb` holds 4,577 from 60 s.
- `uobjects` 52,300 to 52,500 after the first minute; 2.0 km sailed.

**`soak_mem` in `bench.json`:**
```
{"rows":11,"mb_per_hour":-227.4,"mb_per_100km":-3451.4,"first_mb":3640,"last_mb":3559,"peak_mb":3646,
 "travelled_km":2.0,"budget_mb_per_hour":50,"verdict":"flat"}
```
It fits the last 11 rows (600 to 1,200 s). **Verdict: flat.** The process's private bytes, sampled from outside every minute
(`memory.csv`), agree: 14,884 MB at minute 1, 14,312 at 10, 14,191 at 20, falling as `used_mb` does (including the
~470 MB drop at minute 8).

The PR's check compares the verdict with a Mac `footprint` column. The PC's rows have no such column; the outside
private-bytes curve is the PC's equivalent here.
