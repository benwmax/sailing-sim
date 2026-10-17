# Mac High soak, 1 h, draw events off (Oct 16 2026)

Packaged Development build of main `d63ab44b` on Bean's Mac (Apple M5 Pro, 48 GB, macOS 26.6.2), windowed 1920x1080,
High, the J/22 at the lake with the autopilot tacking, afternoon breeze. Window visible, display kept awake with
`caffeinate`. Started 23:08 CDT.

    DEMO=1 SHOT=soak-high ARGS="-SailingQuality=High -SailingBenchTrace -ExecCmds=ToggleDrawEvents" scripts/bench-mac.sh 3600
    # RSS every 60 s (ps -o rss=), footprint -p every 10 min
    python3 docs/budget/soak_stats.py <frames.csv> soak/mac-high-2026-10-16.mem.csv

**Draw events were off** (`-ExecCmds=ToggleDrawEvents`; the log shows "Draw events are now DISABLED" in the first frame).
A Development build turns Metal draw events on at startup, and with them on, every render encoder gets a label string
that a never-drained autorelease pool keeps: 3.1 GB/h of `CFString`/`CFData` in the Medium soak
(`mac-soak-medium-2026-10-16.md`). Shipping and Test builds never turn them on, so this soak measures what a player's
build would do. The GPU slices in bench.json still come from `ProfileGPU` after the run.

## Numbers

| | value |
|---|---|
| Whole run (bench.json) | 55.1 fps, p99 21.28 ms, 198,251 frames over 3601 s; GPU 18.62 ms, game 2.44 ms |
| First 10 min | **55.1 fps, p99 23.41 ms** |
| Last 10 min | **53.5 fps, p99 21.40 ms** |
| p99 drift after the 10 min warm-up | **+2.0 ms/h** (ledger: per-minute samples, `soak_to_ledger.py`); +3.0 ms/h on the raw per-minute p99 (19.5 ms at 10-15 min, 21.7 ms in the last 5). Over the whole run the fit reads -1.0 ms/h only because the first 5 min hold the hitches |
| Memory growth, `footprint` (10 to 60 min) | **+1385 MB/h**: Unreal's heap (`app-specific tag 2`) 1796 to 2516 MB, +864 MB/h; system malloc (`MALLOC_SMALL`) 322 to 756 MB, +521 MB/h |
| GPU memory | flat: graphics unmapped 5529 MB throughout, IOAccelerator 1260 to 1267 MB |
| RSS growth (linear fit after 10 min) | +1455 MB/h (1124 MB at 5 min to 2589 MB at 59 min) |
| Engine peak (bench.json `mem_peak_mb`) | 10649 MB |
| Frames over 33.3 ms after warm-up | 311: 284 in the first 5 min (a 1.0 s frame at 223 s among them), then 0 to 7 per 5 min |

No crash and no hang. The game finished the run and quit normally.

RSS isn't a clean measure here. At about 230 s it fell from 2528 to 936 MB, in the same second as the 1 s frame (macOS
compressing the process's pages, which RSS leaves out), and then climbed steadily. `footprint` counts compressed pages,
so its categories are the figure to use. Above 10 GB it prints its total only in whole GB (10240 MB from 40 min on), so
the growth above sums the two categories that move.

## Against the Medium soak (draw events on)

| per hour | Medium, draw events on | High, draw events off |
|---|---|---|
| system malloc (`MALLOC_SMALL`) | +2.7 GB/h (`CFString`/`CFData` from the encoder labels) | **+0.52 GB/h** |
| Unreal's heap (`app-specific tag 2`) | +0.38 GB/h | **+0.86 GB/h** |
| GPU memory | flat | flat |
| p99 drift after warm-up | +0.7 ms/h (ledger) | **+2.0 ms/h** (ledger) |

Turning draw events off removes most of the malloc growth. The p99 drift doesn't go away: High still slows by about
2 ms/h after warm-up, over the 1 ms/h cap, so the fps fade isn't the encoder labels' doing either. What remains is about 1.4 GB/h with no known Development-only cause, so expect it in Shipping until a
Shipping soak says otherwise. Unreal's heap grows about twice as fast on High as on
Medium, and system malloc still grows half a gigabyte an hour. Both are well over the ledger's 100 MB/h cap. Next:
`memreport -full` (or `stat memory` with LLM tags) at 10 and 50 min on a High run to name the heap's tags, and
`heap -s` on the malloc side.
Done in `mac-soak-high-2-2026-10-17.md`: Metal ray-tracing builders and drawables kept alive every frame (malloc), and
RHI command-list execution plus `SceneRender` (Unreal's heap).

## Files (`docs/budget/soak/`)

- `mac-high-2026-10-16.mem.csv`: seconds since process start, RSS MB, every 60 s
- `mac-high-2026-10-16.footprint.csv`: `footprint` total and the four biggest categories, every 10 min
- `mac-high-2026-10-16.frames-1hz.csv`: the 198,522-frame trace cut to one row a second: frames, mean, p99, max ms
- `mac-high-2026-10-16.bench.json`: the bench result
- `mac-high-2026-10-16.ledger.csv`: the soak in the ledger's format (`t_s,ram_mb,vram_mb,fps,p99_ms`, one row a minute;
  `docs/budget/soak_to_ledger.py`)
