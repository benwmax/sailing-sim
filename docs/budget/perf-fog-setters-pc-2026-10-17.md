# Perf 4 on the PC: the fog setters on D3D12 (Oct 17 2026)

Main 0059ea12 (#116 fog steps and #111 merged), packaged as Development on Bean's PC (i9-9900K, RTX 4090, D3D12,
1920x1080). The setup matches the PC's #110 soak: Ultra, slip view, 30 min, parked with the clock running, no demo, one
run, window visible:

    scripts\windows\soak-win.ps1 -Minutes 30 -Quality Ultra -View slip -NoDemo -Extra '-SailingKeepStart -csvCaptureFrames=150000'

Per-thread times came from a local logging patch (not committed): the mean `GGameThreadTime`, `GRenderThreadTime`,
`GRHIThreadTime` and GPU frame time over each minute. Slopes are least-squares fits after the first 5 min
(`budget-ledger.py`'s `slope_per_hour`).

## Results

| Drift after 5 min | #110 run (main with #110) | main 0059ea12 |
|---|---|---|
| game thread | +0.64 ms/h | **+0.05 ms/h** |
| render thread | +1.66 ms/h | **+0.50 ms/h** |
| RHI thread | +1.04 ms/h | **+0.82 ms/h** |
| GPU | | -0.03 ms/h (flat) |
| p99 drift (`from_soak`) | 0.79 ms/h | 0.81 ms/h |

Over the whole 1800 s run, 0059ea12 averaged 77.3 fps, with p99 at 17.46 ms, GPU at 8.57 ms, game thread 6.83 ms,
render thread 12.91 ms and RHI thread 7.23 ms.

| 10-minute window | fps | p99 ms | RAM MB | VRAM MB |
|---|---|---|---|---|
| 0-10 min | 76.2 | 17.7 | 8673 | 7324 |
| 10-20 min | 78.0 | 16.87 | 8354 | 7325 |
| 20-30 min | 77.7 | 16.9 | 8396 | 7325 |

These CSV profile counters (139,397 frames, nine equal bins) were flat:

- `RHI/PrimitivesDrawn`: about 1.106 M.
- `DrawCall/ShadowDepths`: 79-81.
- `RHI/DrawCalls`: 690-695.
- `Ticks/Total`: 64.

The ledger's straight-line fit gives RAM growth of 128 MB/h. The windows don't climb steadily, though: the first is the
highest. VRAM peaked at 7325 MB and stayed there.

## Conclusion

#116 helped on D3D12. The render thread's residual drift fell from +1.66 to +0.50 ms/h, and the game thread's from
+0.64 to +0.05 ms/h. On the Mac it changed nothing measurable (`perf-sun-setters-2026-10-17.md`, Perf 4), because there
the fog proxy is cheap to rebuild.

What remains (RHI +0.8, render +0.5 ms/h, p99 0.8 ms/h) is under 1 ms an hour on any one thread, against a 12.9 ms frame. It is parked,
with no dumpticks or memreport pass planned for now.
