# Mac Medium soak, 2 h (Oct 16 2026)

Packaged Development build of main `8d5320cb` on Bean's Mac (Apple M5 Pro, 48 GB, macOS 26.6.2), windowed 1920x1080
(1440x1080 render), Medium, the J/22 at the lake with the autopilot tacking, afternoon breeze. Window visible, display
kept awake with `caffeinate`.

    DEMO=1 SHOT=soak-medium ARGS="-SailingQuality=Medium -SailingBenchTrace" scripts/bench-mac.sh 7200
    # RSS of the game process every 60 s: ps -o rss= -p <pid>
    python3 docs/budget/soak_stats.py <frames.csv> soak/mac-medium-2026-10-16.mem.csv

## Numbers

| | value |
|---|---|
| Whole run (bench.json) | 79.7 fps, p99 14.16 ms, 574,617 frames over 7210 s |
| First 10 min | **84.6 fps, p99 13.10 ms** |
| Last 10 min | **77.1 fps, p99 14.55 ms** |
| p99 drift (linear fit of the per-minute p99) | **+1.00 ms/h** |
| RSS growth (linear fit after 5 min) | **+3133 MB/h** |
| Peak RSS | **8752 MB** (2449 MB at 85 s) |
| Physical footprint (`footprint`, graphics included) | 8180 MB at 21 min, 13312 MB at 111 min |
| Frames over 33.3 ms after warm-up | 2: the `heap` probe at 1902 s (10.5 s pause, mine) and the exit frame (186 ms) |

No crash and no hang. The game finished the run and quit normally.

## The memory growth is a Development-build leak

`footprint` every 10 min (`soak/mac-medium-2026-10-16.footprint.csv`) puts the growth in `MALLOC_SMALL` (system malloc,
+44 MB/min). The GPU's memory stays flat (graphics unmapped 3509 to 3621 MB, IOAccelerator 1225 to 1233 MB), and so,
nearly, does Unreal's own allocator (`app-specific tag 2`, +6.5 MB/min). `heap -s` at 32 min:

    COUNT      BYTES       CLASS_NAME
    7165715    720794208   CFData
    7190023    645198384   CFString
      28618    117219328   @autoreleasepool content
     157261     35226464   CAMetalDrawable      (one per frame since launch)

The autorelease pool is never drained. A short run with `MallocStackLogging=lite` shows the pool pages filled on
task-graph worker threads translating RHI command lists in parallel:
`FRHICommandListExecutor::FTranslateState::Translate_ExecuteCommandList` -> `FMetalRHICommandContext::RHIBeginRenderPass`
-> `FMetalCommandEncoder::BeginRenderCommandEncoding` -> `__CFStringCreateImmutableFunnel3`. That function labels every
render encoder (`"RenderEncoder: <debug group>"`) when `GetEmitDrawEvents()` is true. In Debug and Development builds
`MetalRHI.cpp` turns draw events on at startup (`SetEmitDrawEvents(GetEmitDrawEvents() | ENABLE_METAL_GPUEVENTS)`), and
nothing drains a pool around that code on the workers. Test and Shipping builds don't enable draw events.

A/B, 3 min each on the same package (`soak/mac-medium-2026-10-16.drawevents-ab.csv`), RSS from 40 s to 180 s:

- draw events on (default): +126 MB, **54 MB/min** (the soak's rate)
- `-ExecCmds=ToggleDrawEvents` (log: "Draw events are now DISABLED"): +24 MB, **10 MB/min**, and only 5 MB in the last
  30 s

So the 3.1 GB/h is a Development-only artefact. A player's Shipping build should grow far less. What remains with draw
events off is Unreal's own heap at about 0.4 GB/h, which still wants its own soak. The fps fade (84.6 to 77.1) may be
partly the leak too (the allocator and the pool both get bigger), so the p99 drift is an upper bound until a soak runs
without draw events.

## What a player's build would grow

Shipping and Test builds don't enable Metal draw events (only Debug and Development turn them on at startup), so the
3.1 GB/h of this soak is a Development-only artefact. With draw events off, growth doesn't stop. The 1 h High soak with
`-ExecCmds=ToggleDrawEvents` (`mac-soak-high-2026-10-16.md`) still grows **about 1.4 GB/h** (`footprint`: Unreal's heap
+0.86 GB/h, system malloc +0.52 GB/h; RSS fit +1.46 GB/h; GPU memory flat), and its p99 doesn't drift (-1.0 ms/h). That
remaining growth has no known Development-only cause, so expect it in Shipping too, and it is far over the 100 MB/h cap.

## Files (`docs/budget/soak/`)

- `mac-medium-2026-10-16.mem.csv`: seconds since process start, RSS MB, every 60 s
- `mac-medium-2026-10-16.footprint.csv`: `footprint` total and the four biggest categories, every 10 min
- `mac-medium-2026-10-16.frames-1hz.csv`: the 575,036-frame trace (9.7 MB) cut to one row a second: frames, mean, p99,
  max ms
- `mac-medium-2026-10-16.bench.json`: the bench result
- `mac-medium-2026-10-16.drawevents-ab.csv`: the A/B above

## Next

- Done for High (`mac-soak-high-2026-10-16.md`): 1 h with draw events off. Next is naming the remaining heap growth.
- In the game, Development runs that don't profile could turn draw events off at startup (benches that read
  `ProfileGPU` slices would turn them back on around the capture), or wrap our RHI work in a pool. The engine fix is an
  autorelease pool in the parallel translate task on Apple platforms.
