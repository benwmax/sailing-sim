# PR #852 at 30b9ea2f on the PC (Nov 27 2026)

**Head:** 30b9ea2f, the branch tip when the job started; f750dd4 changed only the ini comment. Worktree
`D:\dev\ss-fix-wt\pr852-30b9ea2f`; `Config/Windows/WindowsEngine.ini` there has `d3d12.UploadHeap.PoolAllocationStrategy=0`.
MSVC editor build succeeded (0 project warnings, 0 errors). Development package `Packaged\Windows-pr852-30b9ea2f`, warmed
once (the config is inside the pak). Nothing pushed to the PR branch. Bean's Saved restored (7B5CA7BE) after every run.

## The cvar comes from the ini, with no `-ini` argument

`cell-30b9ea2f/cvars.txt`, from the packaged run's log:
- `d3d12.UploadHeap.PoolAllocationStrategy = "0"  LastSetBy: SystemSettingsIni`
- `d3d12.UploadHeap.BigBlock.PoolSize = "33554432"  LastSetBy: Constructor`

The 95220b32 baseline (`baseline-95220b32/cvars.txt`) shows the default: strategy "1", LastSetBy Constructor.

## Cell 1, 10 min, against plain main 95220b32 on the same recipe

Stationary Galveston, `-SailingTideStepEvery=20` (30 steps), 4K Ultra, `-llm -llmcsv -SailingBenchTrace`, `memreport -full` at
595 s.

| Run | private MB/min (minute 3 to 10) | D3D12AllocatorUnused MB/min | step hitch median / max ms | render at the step, median / max | mean fps (after 30 s) | process virtual at 595 s |
|---|---|---|---|---|---|---|
| **#852 30b9ea2f** | **-73.0** (15,260 to 14,749) | -5.6 (378 to 345) | 77.2 / 174.0 | 31.0 / 83.9 | 43.4 | 14,484 MB |
| 95220b32 baseline | **+252.7** (15,567 to 17,336) | +277.0 (1,177 to 2,839) | 76.0 / 174.7 | 77.2 / 91.0 | 43.9 | 17,202 MB |

- **The climb is gone** with the ini alone: flat private bytes and a flat D3D12 pool over 30 steps.
- **fps** is 0.5 lower (43.4 against 43.9), within run-to-run noise for one 10-minute run each.
- **The step's frame peak is unchanged** (77 against 76 ms median; it's game-thread bound). The render thread's share of
  it drops (31 against 77 ms median).
- The hitch leaves out the bench's first 5 s and the `memreport` frames from 594 s on (1.7 s and 1.3 s long).

**Shipping:** not run. A Shipping build writes no engine log (no LastSetBy line). Its `SailingArgs::Dev()` passes only the
release smoke's switches, without `-SailingTideStepEvery`, `-SailingStartAt` or `-SailingRun`. A natural-tide-step
Shipping pair is queued as low-priority filler (`shipping/`, later).
