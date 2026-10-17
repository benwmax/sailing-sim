# Mac soak 3: parked on High, sailing on Medium (Oct 17 2026)

This follows `mac-soak-high-2-2026-10-17.md`. That run named what grows; this one asks two questions about it:

1. Does `ProceduralMeshComponent` memory (4452 of them, +87 MB/h while sailing) keep growing when the boat doesn't move?
   If it stops, the cause is the terrain chunks' level-of-detail churn. If it keeps growing, it's something rebuilt
   every frame (cloth, rig lines, telltales, water).
2. Are the Metal objects that pile up an undrained autorelease pool? On Medium there is no hardware ray tracing, so a
   heap census should show the drawables and none of the ray-tracing builders.

Packaged Development build of main `a8ce8ed3` plus two bench arguments (branch `mac-soak-3`), on Bean's Mac (Apple
M5 Pro, 48 GB, macOS 26.6.2). The J/22 at the lake in the afternoon breeze, draw events off, low-level memory tracker
on, window visible, display kept awake with `caffeinate`.

    # A: parked on High, 30 min (started 03:34 CDT)
    SHOT=soak-parked ARGS="-SailingQuality=High -SailingKeepStart -SailingMooring -SailingBenchTrace \
      -ExecCmds=ToggleDrawEvents -LLM -LLMCSV -SailingExecAt=60:obj+list+class=ProceduralMeshComponent+-resourcesizesort;\
    60:memreport+-full;1740:obj+list+class=ProceduralMeshComponent+-resourcesizesort;1740:memreport+-full" \
      scripts/bench-mac.sh 1800
    # B: sailing on Medium, 30 min (started 04:06 CDT): DEMO=1, -SailingQuality=Medium, otherwise the same
    # Both: RSS every 60 s, footprint every 10 min, heap (and footprint) at process 100 s and 1790 s (A), 615 s and 1515 s (B)

**New arguments.** Without the autopilot the boat doesn't sit still: it starts at 3 kn and sailed 200 m in the first two
minutes. `-SailingMooring` ties the player's bow to a buoy 12 m upwind of the start with its sails up. Over the whole run
it swung inside a circle about 25 m across (`position.csv`). With `-SailingBenchTrace`, the bench now also logs the
player's position once a minute (`SailingBench: at <s> s: boat at <n> N <e> E, <d> m since the last line`).

## Answers

**1. Procedural meshes: no leak. The growth follows the shore detail near the boat.**

| | 60 s | 1740 s | change |
|---|---|---|---|
| A, parked on High (memreport, all 4452) | 199.8 MB | 199.9 MB | **+0.15 MB** in 28 min |
| B, sailing on Medium (memreport, all 4452) | 201.2 MB | 258.7 MB | +57.5 MB in 28 min |
| B, the terrain's 4421 chunks (obj list) | 178.4 MB | 234.5 MB | +56.1 MB |
| B, water (6), the player's boat (24 components) | 16.1, 2.1 MB | 16.1, 2.1 MB | 0 |
| Soak 2, sailing on High (memreport, 10 to 50 min) | 252 MB | 265 MB (198.8 at 1 min) | +58 MB in 40 min |

Parked, the only procedural meshes that changed were six terrain chunks that changed level of detail as the boat
swung. Sails, rig lines, telltales and water are the same size at both points. So it isn't anything rebuilt every frame.

Sailing, the four chunks that grew most hold all of the growth. Each went from 0.05 to 0.19 MB to **15 to 16 MB**: these
are the Graphics G2 shore chunks, meshed from the lidar at 1 m (Step 0) once the camera is within 300 m. At the end of
B the boat was close to the shore at -2500 N (`position.csv`). A 64-cell chunk is 320 m square, so at 1 m it is about
100k vertices, around 16 MB in `FProcMeshVertex` and indices. 366 other chunks shrank in the same run. So the total
depends on how much lidar shore is near the camera, not on time. Soak 2's "+87 MB/h" is that working set, read at two
places on the course. The cost to keep in mind is 16 MB a chunk, and four to eight of them near a wooded shore.

`ALakeTerrainActor` keeps each chunk's `TFuture<FChunkMesh>` after the upload. `Get()` copies the mesh out and the
future keeps its own copy, so a Step 0 chunk may hold a second 16 MB. `obj list` doesn't count that copy (it lives
outside the UObject), so these numbers can't show it. Taking the result with `Consume()` and resetting the future would
free it. Not changed here.

The ten largest procedural meshes are the same at both points in A: `WaterRing0`-`4` (2.7 to 2.8 MB each) and
`FarPlane` (2.5 MB), then terrain chunks at 0.8 MB. In B the four 1 m shore chunks (15 to 16 MB) head the list at
1740 s (`pmc.csv` has owners, the ten largest at each point and the ten that grew most).

**2. The Metal objects: the ray-tracing builders are tied to ray tracing, and the drawables pile up on every tier.
Neither depends on the boat moving.**

`heap` census (counts that grew between the two points, all classes in `heap-diff.csv`):

| | A, parked, High (100 to 1790 s) | B, sailing, Medium (615 to 1515 s) |
|---|---|---|
| frames in the window (fps) | about 86,500 (51) | about 73,000 (81) |
| `AGXG17XFamilyRayTracingGPUBuilder` (+ `_impl`), `AGXG17XFamilyComputeContext`, `MTLInstanceAccelerationStructureDescriptor` | **+259,594 each**, 3 a frame, 199 MB = **+425 MB/h** | **0** (one builder alive in total) |
| `CAMetalDrawable` | +86,532, one a frame, +41 MB/h | **+73,001, one a frame**, +65 MB/h |
| `NSMutableArray` | +173,096 (two per drawable) | +146,015 (two per drawable) |
| `IOSurfaceSharedEvent` | +60,464 | +14,297 |

So on Medium, with no hardware ray tracing, the builders don't appear at all, and the drawables still leak one a frame.
Both fit objects autoreleased on a thread whose pool never drains. The drawable is acquired on every tier, and the
acceleration-structure builds happen only where Lumen uses hardware ray tracing. The "two `NSMutableArray`s per
builder" in soak 2's doc is wrong: they come two per drawable (257,162 = 2 x 128,578 there too).

Unreal's heap (LLM, MB/h from minute 2 to the end):

| tag | A, parked, High | soak 2, sailing, High | B, sailing, Medium |
|---|---|---|---|
| TrackedTotal | +726 | +857 | +665 |
| `RHIMisc/CommandList/ExecuteAndDestruct` | **+375** | +387 | **+45** |
| `SceneRender` | +223 | +253 | +249 |
| `EngineMisc` | +76 | +130 | +256 |
| `FMallocUnused` | +39 | +48 | +37 |
| `Untagged`, `GPUScene` | 0, +6 | flat | +60, +16 |
| UObject, Meshes, Textures, Lumen, Nanite, Physics, Audio | flat | flat | flat |

- **`ExecuteAndDestruct` goes with ray tracing**: +375 MB/h on High with the boat parked, +45 on Medium. It's the
  Unreal-side counterpart of the builders. It's memory allocated while the RHI thread replays the ray-tracing scene
  build and never freed, most likely Metal RHI wrappers held alive by the same undrained pool.
- **`SceneRender` doesn't care about ray tracing or motion**: +223 to +253 MB/h in all three runs, about 1 KB a frame
  (1.2 on High at 51 fps, 0.85 on Medium at 81 fps). This is the per-frame leak left once ray tracing is off.
- `EngineMisc` follows motion: +76 parked against +130 and +256 sailing, which is about the shore chunks' working set
  (B's procedural meshes alone were +120 MB/h, and the futures' copies would come on top).

`footprint` (MB/h between the two census points):

| | Unreal's heap (`app-specific tag 2`) | system malloc (`MALLOC_SMALL`) | GPU (graphics unmapped) |
|---|---|---|---|
| A, parked, High | 1673 to 2010, **+718** | 248 to 479, **+492** | flat (5529 when not being censused) |
| soak 2, sailing, High | +901 | +507 | flat |
| B, sailing, Medium | 1697 to 1907, **+840** | 237 to 263, **+104** | flat (3505 to 3621) |

Without ray tracing, system malloc grows a fifth as fast, and what's left is the drawables and their arrays (+93 of the
+104 MB/h). Unreal's heap still grows on Medium. That's `SceneRender`, plus `EngineMisc` from the shore chunks while
sailing.

## Frame rate

| | A, parked, High | B, sailing, Medium |
|---|---|---|
| Whole run (bench.json) | 51.2 fps, p99 22.67 ms, 92,359 frames over 1805 s | 81.4 fps, p99 13.85 ms, 146,840 frames over 1803 s |
| First / last 10 min | 50.6 / 51.9 fps, p99 22.19 / 23.48 ms | 83.5 / 78.7 fps, p99 13.32 / 14.11 ms |
| p99 drift (`soak_stats.py`) | +1.7 ms/h | +2.5 ms/h |
| RSS growth after 5 min | +1416 MB/h (2347 to 3193 MB) | +1213 MB/h (2371 to 2929 MB) |
| Frames over 33.3 ms after warm-up | 5 (the worst 3.2 s, during the last `heap` census) | 7 (the worst 1.5 s, a census) |

No crash and no hang: both runs finished and quit normally. The parked High run averaged 51.2 fps, against 53.4 for
soak 2 sailing (different view: the moored boat sits off the club). Medium fades
faster than High, which fits a cost per live Metal object that builds up per frame.

## Next

1. The Metal RHI's per-frame `@autoreleasepool`: both piles (drawables on every tier, ray-tracing builders on High)
   are autoreleased objects outliving the frame. Check where `MetalRHI` acquires the drawable (the viewport's
   `GetDrawable`/present) and where `FMetalRayTracingScene` builds the instance acceleration structure, and whether
   either runs on a thread (RHI thread, or the render thread with `r.RHIThread.Enable=0`) without a pool around its
   frame. A one-line `@autoreleasepool` around each frame's RHI work, in an engine patch, would be the test. A
   Shipping soak tells whether the player's build carries it.
2. `SceneRender` +1 KB a frame on every tier: a short run with `-trace=memalloc` (Unreal Insights) gives the call stacks.
3. Terrain: take the chunk mesh out of its future (`Consume()`, then reset `Future`) so a 1 m shore chunk isn't held
   twice. Consider a lower-detail shore level (2 m) beyond 150 m: 16 MB a chunk is a lot for the CPU copy.

## Files (`docs/budget/soak/`)

For each run, `mac-high-parked-2026-10-17.*` (A) and `mac-medium-2026-10-17.*` (B):

- `mem.csv`: seconds since process start, RSS MB, every 60 s
- `footprint.csv`: `footprint` total and the four biggest categories, every 10 min and at each census
- `llm-1min.csv`: LLM tags (MB) once a minute: TrackedTotal, the ones that grow, flat ones for contrast and Metal's own
  ray-tracing tags
- `heap-diff.csv`: the 15 `heap` classes that grew most between the two censuses
- `pmc.csv`: `ProceduralMeshComponent` sizes at 60 and 1740 s: per owner, the ten largest at each point, the ten that grew
- `position.csv`: the player's position once a minute (bench seconds, north and east in metres, metres moved)
- `frames-1hz.csv`, `bench.json`, `ledger.csv` (`soak_to_ledger.py`)

The full memreports, LLM CSVs, `obj list` output and heap dumps stay in the game's sandbox
(`~/Library/Containers/com.benwmax.SailingSim/Data/Library/Application Support/Epic/SailingSim/Saved/Profiling/`, and
the logs under `Logs/`).
