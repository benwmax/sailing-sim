# Mac High soak 2: what grows (Oct 17 2026)

The follow-up to `mac-soak-high-2026-10-16.md`, whose "Next" asked which allocations make up the 1.4 GB/h. This run had
the same setup with Unreal's low-level memory tracker on. It took `memreport -full` and `DumpLLM` at 10 and 50 min, and
`heap` (macOS's malloc census by class) at the same two points.

Packaged Development build of main `65536c69` plus the new `-SailingExecAt` arg (branch `mac-soak-2`), on Bean's Mac
(Apple M5 Pro, 48 GB, macOS 26.6.2). High, the J/22 at the lake with the autopilot tacking, afternoon breeze, draw
events off. Window visible, display kept awake with `caffeinate`. Started 01:29 CDT.

    DEMO=1 SHOT=soak-high2 ARGS="-SailingQuality=High -SailingBenchTrace -ExecCmds=ToggleDrawEvents -LLM -LLMCSV \
      -SailingExecAt=600:memreport+-full;600:DumpLLM;3000:memreport+-full;3000:DumpLLM" scripts/bench-mac.sh 3600
    # RSS every 60 s (ps -o rss=), footprint -p every 10 min, heap <pid> at about 10 and 50 min

`-SailingExecAt=<s>:<cmd>[;<s>:<cmd>...]` runs console commands at those seconds of the bench clock. A `+` stands for a
space, because `bench-mac.sh` splits `ARGS` on whitespace.

## Answer

The growth is the same as on Oct 16 (footprint: Unreal's heap +0.86 GB/h then, +0.90 GB/h now; system malloc +0.52 then,
+0.51 now). Here is what it is made of, as linear rates from 10 to 60 min:

| where | what | rate |
|---|---|---|
| Unreal's heap (FMalloc, LLM) | **`RHIMisc/CommandList/ExecuteAndDestruct`** 74 to 398 MB | **+387 MB/h**, a straight line from the first minute |
| | **`SceneRender`** 141 to 353 MB | **+253 MB/h**, straight |
| | `EngineMisc` 281 to 390 MB | +130 MB/h, flattening: +8 MB in the last 20 min |
| | `FMallocUnused` (the allocator's slack) | +48 MB/h |
| | everything else (UObject, Meshes, Textures, Lumen, Nanite, Physics, Audio...) | flat |
| system malloc (`heap`, 10 to 50 min) | **Metal ray-tracing acceleration-structure builds**: 385,735 more each of `AGXG17XFamilyRayTracingGPUBuilder` (+ its `_impl`), `AGXG17XFamilyComputeContext` and `MTLInstanceAccelerationStructureDescriptor` | +296 MB in 40 min, about **+440 MB/h**; 160 a second, about 3 a frame |
| | **`CAMetalDrawable`**: 128,578 more | +29 MB in 40 min; one a frame (53 fps x 2405 s) |
| | `NSMutableArray`, 257,162 more (two per builder), autorelease pool contents | +22 MB |
| UObjects (memreport) | object count flat at 43,868; **`ProceduralMeshComponent`** (4452 of them) 252 to 265 MB | +58 MB in 40 min, about +87 MB/h |
| GPU | flat: graphics unmapped 5529 MB throughout, IOAccelerator 1244 to 1259 MB | 0 |

Both big pieces are tied to the frame rate and leak a fixed amount every frame:

- **System malloc is Metal objects that are created every frame and never released.** About three instance
  acceleration-structure builds a frame on High (Lumen hardware ray tracing: the TLAS rebuild), and every frame's
  drawable. Each builder, compute context, descriptor and drawable is still alive 40 minutes later. This is the same
  pattern the Medium soak found for the draw-event labels: objects autoreleased on a thread whose autorelease pool never
  drains. Turning draw events off removed the labels but not these. Only High enables ray tracing, so Medium should
  leak only the drawables. Not checked yet.
- **Unreal's heap grows inside RHI command-list execution** (`ExecuteAndDestruct`: memory allocated while the RHI
  thread replays a command list and never freed) **and in `SceneRender`**. They grow in step with each other and with
  the Metal objects. A likely common cause is Metal RHI wrappers (or their ray-tracing scene data) held alive by the
  same undrained pool. That is a hypothesis: LLM names the tag, not the call site.
- `ProceduralMeshComponent` memory grows while the count stays fixed, so some procedural meshes keep growing their
  arrays. The rig lines, sails and terrain chunks are procedural meshes. This one is ours, not the engine's.

Adding up: 387 + 253 + 130 + 48 = 818 MB/h of the LLM's 857 MB/h FMalloc growth (TrackedTotal), and Metal objects make
up nearly all of the system malloc growth. The leak doesn't depend on the game logic: it scales with frames, not with
time sailed.

## Numbers

| | value |
|---|---|
| Whole run (bench.json) | 53.4 fps, p99 22.24 ms, 192,587 frames over 3606 s; GPU 18.20 ms, game 3.13 ms |
| fps by 10 min | 54.8, 55.8, 53.4, 52.9, 52.1, 51.9 (Oct 16: 55.1, 57.3, 55.3, 55.1, 54.0, 53.5) |
| Mean frame time after warm-up | 18.00 ms at 10-20 min to 19.34 ms at 50-60 min, **+2.0 ms/h** (Oct 16: 17.45 to 18.69, +1.9 ms/h) |
| p99 drift (`soak_stats.py`, per-minute p99) | +9.0 ms/h over the whole run. The median 1 s p99 goes 19.85 to 21.90 ms from 10-20 to 50-60 min, **+3.1 ms/h** (Oct 16: 19.35 to 20.55, +1.8 ms/h) |
| Memory, `footprint` (10 to 50 min) | Unreal's heap (`app-specific tag 2`) 1780 to 2382 MB, **+901 MB/h**; system malloc (`MALLOC_SMALL`) 324 to 662 MB, **+507 MB/h** |
| GPU memory | flat |
| RSS growth (`soak_stats.py`, after 5 min) | +1561 MB/h, 2319 to 4104 MB (RSS leaves out compressed pages; footprint is the figure to use) |
| LLM's own overhead | 77 to 244 MB (it grows with the number of live allocations) |
| Frames over 33.3 ms after warm-up | 472. The worst, 3.3 s, came at about 50 min, during the second `heap` census, which suspends the process |

No crash and no hang. The game finished the run and quit normally.

Measurement costs: the tracker and the two `heap` censuses cost a little speed (the first and last 10 min are 0.3 and
1.6 fps under Oct 16) and add the long frames at 10 and 50 min. Use the Oct 16 run for frame-time numbers and this one
for what grows. The mean frame time fades at the same rate as on Oct 16 (+2.0 against +1.9 ms/h), so the fade isn't the tracker's.
It fits a cost that grows with the number of live Metal objects. The p99 fades faster here (+3.1 against +1.8 ms/h),
which may be LLM's bookkeeping on top.

## Next

1. Confirm the autorelease cause: a Medium soak (ray tracing off) with `heap` at 10 and 50 min should show the
   drawables and none of the ray-tracing builders. If so, look at whether the Metal RHI thread's per-frame
   `@autoreleasepool` is drained in this engine build (`MetalRHI`, the RHI thread's frame loop and
   `FMetalRayTracingScene` builds). A Shipping soak tells whether the player's build carries it.
2. `ProceduralMeshComponent`: dump `obj list class=ProceduralMeshComponent -resourcesizesort` at 10 and 50 min (add it to
   `-SailingExecAt`) to name the component, then reuse its section arrays instead of growing them.
3. If the RHI side stays unexplained, a short run with `-trace=memalloc` (Unreal Insights) gives call stacks for
   `ExecuteAndDestruct` and `SceneRender`.

## Files (`docs/budget/soak/`)

- `mac-high-2026-10-17.mem.csv`: seconds since process start, RSS MB, every 60 s
- `mac-high-2026-10-17.footprint.csv`: `footprint` total and the four biggest categories, every 10 min
- `mac-high-2026-10-17.llm-1min.csv`: LLM tags (MB) once a minute: TrackedTotal and the ones that grow, plus some flat
  ones for contrast
- `mac-high-2026-10-17.heap-diff.txt`: the `heap` classes that grew between 10 and 50 min
- `mac-high-2026-10-17.frames-1hz.csv`: the frame trace cut to one row a second
- `mac-high-2026-10-17.bench.json`, `mac-high-2026-10-17.ledger.csv` (`soak_to_ledger.py`)

The full memreports, LLM CSVs and heap dumps (about 10 MB) stay in the game's sandbox
(`~/Library/Containers/com.benwmax.SailingSim/Data/Library/Application Support/Epic/SailingSim/Saved/Profiling/`).
