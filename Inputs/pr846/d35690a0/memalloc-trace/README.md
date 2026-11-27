# Memalloc trace of #846's cell 1 (Windows-pr846-d35690a0, PC, Nov 27 2026)

**Run (`args.txt`):** cell 1's recipe (stationary Galveston, `-SailingTideStepEvery=20`, 4K Ultra) for 10.5 min, plus
`-trace=memalloc,callstack,module`, `-llm -llmcsv`, and at 120 s and 600 s `memreport -full`, `rhi.DumpMemory` and
`rhi.DumpResourceMemory`. The trace is 10.1 GB, kept on the PC
(`D:\dev\ss-fix\Artifacts\bench\memtrace846\memtrace846.utrace`; D: had 142 GB free after). Insights analysed it in
8 min. Private bytes went from 15,465 MB at minute 2 to 17,574 at minute 10 (`memory.csv`). Bean's Saved restored (7B5CA7BE).

## Result: three new 32 MB `FD3D12MemoryPool`s tagged GPUScene at every tide step, none released

`MemoryInsights.ExportAllocs -Rule=AaBf -TimeA=140 -TimeB=622` (allocated between the two memreports, still live at the
end; the times are trace seconds from the log stamps): 33,323 allocations, 2,672 MB (`aabf-top15.txt`).

- **2,272 MB of it (85%) is 71 allocations of exactly 32 MB, tag `GPUScene`, all from `FD3D12MemoryPool::Init`.** They
  come three at every forced tide step: two within the same 0.1 s, about 2.5 s after the log's "Tide step" line, and a
  third 1 to 2 s later. 24 steps in the window, 24 groups (one group had 2). That is **96 MB a step**, the whole climb.
  They're allocated from 12 different threads (the render and RHI workers).
- **The rest is small:** 90 MB of untagged `VmAlloc`, 78 MB of untagged `Malloc`, then `Stats`, `MemStack`,
  `SceneRender` and `EngineMisc` at 6 to 32 MB each.

**The RHI's own view doesn't see it as resources** (`rhi-dumps.txt`):
- `rhi.DumpMemory` total 17,235 to 17,247 MB (+12).
- `rhi.DumpResourceMemory` tracked total 20,789 to 20,795 MB (+6). Its top-50 list is the same apart from one more
  `Lumen.ScreenProbeGather.RoughSpecularIndirect`. The command lists only the top 50, so the full list can't be diffed by
  name; no named buffer multiplies in it.
- **`memreport -full` (`memreport-heads.txt`):** process virtual 15,712 to 17,514 MB (+1,802), physical 4,249 to 4,468
  (+219), FMalloc's total from the OS 1,994 to 1,950 (down).

**So:** each tide step's GPU-scene update (the instance data for the moved components) gets uploaded through D3D12
memory pools, and three 32 MB pools are created for it. They're kept afterwards, mostly unused (LLM's
`D3D12AllocatorUnused`), and committed but not resident (virtual +1.8 GB, physical +0.2 GB). That fits the cells:
- **Batch 0 with recreate** (one big remove-and-add on the step frame) grows far less.
- **#846's kept classes** still push every moved instance through `GPUScene`'s upload, so they don't help.

What I can't name from this export is the caller above `FD3D12MemoryPool::Init`: this build's ExportAllocs writes the
function but no callstack id. The `.utrace` on the PC has the full callstacks for anyone who opens it in Insights
(Memory, then the GPUScene tag).
