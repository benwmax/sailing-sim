# Tide-step memory with D3D12 upload-heap pool settings, plain main 95220b32 (PC, Nov 27 2026)

**Runs:** Windows-95220b32 (no #846), cell 1's recipe: stationary Galveston, `-SailingTideStepEvery=20` (30 forced 2 cm
steps in the window), 4K Ultra, 10 min, `-llm -llmcsv -SailingBenchTrace`, `memreport -full` at 595 s. One `-ini:` switch
each (`args.txt`). Each log prints both cvars at 5-6 s (`cvars.txt`); both overrides took from the command line's ini
(`LastSetBy: SystemSettingsIni`), so no Engine.ini edit was used. Bean's Saved restored (7B5CA7BE).

| Cell | switch | private MB/min (minute 3 to 10) | D3D12AllocatorUnused MB/min | step hitch median / max ms | render at the step, median / max | mean fps (after 30 s) |
|---|---|---|---|---|---|---|
| A | `-ini:Engine:[SystemSettings]:d3d12.UploadHeap.PoolAllocationStrategy=0` | **-28.1** | -2.5 (359 to 344) | 72.9 / 166.7 | 73.5 / 84.8 | 44.7 |
| B | `-ini:Engine:[SystemSettings]:d3d12.UploadHeap.BigBlock.PoolSize=67108864` | **-80.2** | -5.9 (410 to 375) | 97.6 / 168.3 | 91.1 / 105.2 | 43.9 |
| baseline, same package and recipe | none (`../tide-mem-95220b32/0-baseline`, 17 min) | +233.5 | +266 | | | |

- **Both stop the climb.** Private bytes and the D3D12 pool's unused space stay flat or fall over 30 steps. The baseline
  grew about 75 MB a step, and the `#846` trace (`Inputs/pr846/d35690a0/memalloc-trace/`) showed that as three 32 MB
  `FD3D12MemoryPool`s tagged GPUScene kept per step.
- **memreport at 595 s (`memreport-head.txt`):** process virtual 14,504 MB (A) and 14,535 MB (B). The #846 trace's
  baseline run was at 17,514 MB by 600 s.
- **Strategy 0 (A) has the lower step hitch:** a median peak of 73 ms against 98 for B.
- The baseline cells weren't traced frame by frame, so the like-for-like fps and hitch baseline comes with the #852
  check, which runs a 95220b32 cell on the same recipe next to it.
