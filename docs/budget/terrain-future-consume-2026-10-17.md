# Terrain: take each chunk's mesh out of its future (Mac, Oct 17 2026)

Soak 3 (`mac-soak-parked-2026-10-17.md`, Next 3) noticed that `ALakeTerrainActor::Tick` took a finished chunk with
`Ch.Future.Get()`. That copies the `FChunkMesh` out of the future's shared state, and the future keeps the original
until the chunk is next rebuilt. Now the tick uses `Consume()`, which moves the mesh out and invalidates the future.
`EndPlay` only waits on chunks still building, so it is unaffected.

The copy was held for **every** chunk, not only the 1 m shore ones: the lake has 4421 chunks, and each kept its last
build's vertices, normals, colours and indices next to the procedural mesh.

## Measured

Packaged Development, Medium, 10 min sailing with the autopilot (`DEMO=1`), the same arguments as soak 3 task B (draw
events off, `-LLM -LLMCSV`, `obj list class=ProceduralMeshComponent` and `memreport -full` at 60 and 540 s). main cb80cc34
first, then this branch, back to back on Bean's Mac (Apple M5 Pro):

| | main | Consume | change |
|---|---|---|---|
| LLM `Untagged`, 60 s / 540 s | 142.7 / 141.2 MB | **43.5 / 43.5 MB** | **-98 MB** |
| LLM TrackedTotal, 60 s / 540 s | 1650 / 1710 MB | 1556 / 1616 MB | -94 MB |
| RSS, first sample (15 s) / last (585 s) | 2433 / 2570 MB | 2339 / 2487 MB | -94 / -83 MB |
| RSS growth after 5 min | +748 MB/h | +709 MB/h | same within noise (soak 3's Metal leak) |
| fps, p99 | 86.3, 12.71 ms | 86.5, 12.68 ms | same |
| `ProceduralMeshComponent`, 60 s / 540 s (obj list) | 196.5 / 194.7 MB | 196.3 / 194.7 MB | same (the futures live outside the UObject) |

The future copies were the lake's `Untagged` memory: about 98 MB, held for the whole run. With `Consume()` the tag stays
at 43.5 MB for all 10 min. On main it sits at 141 MB, with one step to 165 MB at 420 s.

This run never came near the lidar shore: the largest terrain chunk was 0.8 MB at both points in both builds, and no 1 m
chunk (15 to 16 MB in soak 3) was built. Near a wooded shore each of those chunks also held a second copy of about 10 MB
in `FChunkMesh` form (vertices, normals, colours, indices), and that copy is gone too.

`scripts/test.sh SailingSim.Lake`: 14/14.

## Files (`soak/`)

`terrain-future-{main,fix}-2026-10-17.mem.csv` (RSS every 30 s), `.frames-1hz.csv`, and `terrain-future-2026-10-17.llm-1min.csv`
(the LLM tags that differ or grow, once a minute, both builds side by side).
