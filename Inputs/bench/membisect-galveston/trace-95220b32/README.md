# Memory trace of one step, stationary Galveston run on Windows-95220b32 (PC, Nov 27 2026)

**Run:** `../still-95220b32/`'s arguments with `-llm -llmcsv -trace=memalloc,callstack,module,memtag` (`args.txt`), from
07:11 local. The supervisor noted a +149 MB private-bytes step at minute 19 and stopped the game at minute 20, as asked.
The 18.5 GB `.utrace` stays on the PC (`D:\dev\ss-fix\Artifacts\bench\memtrace\`). Bean's Saved restored (7B5CA7BE).

**Files:** `memory.csv` (private and working set per minute), the two LLM CSVs (`LLM_*` default tags, `LLMPlatform_*` platform
level, one row about every second, MB), `tide-steps.txt` (the game log's tide steps).

## Result: the step is the D3D12 allocator growing at a tide step, render side, not the game thread

**At the step** (LLM rows 1060 to 1125, 13:29:00 to 13:30:05 UTC):
- **Platform level:** `D3D12AllocatorUnused` +95 MB (461 to 555 MB, and it stays), `Total` +49. It jumps +197, -151,
  +48, +48, -47 over rows 1096 to 1100: a burst of D3D12 allocations, then most of it freed into the pool, which keeps the
  new heap space as unused.
- **Default tags:** `Untracked` +101 MB, the same D3D12 heap. Game tags hardly move: `SceneCulling`, `SceneRender`,
  `MemStack`, `Stats` all under 2 MB. `Untagged` makes a +52/-52 MB FMalloc round trip around it, which nets to nothing.
- **When:** row 1096 was written at 13:30:18.6 UTC. The game logged `Tide step: the followers stand at -14 cm` at
  13:30:19.95.
- **The earlier tide step** (-12 cm at 13:19:10) made the same burst (rows 436 to 440: +205, -152, +79, -79), with no
  net growth that time.

**The same thing across the stationary run** (`../still-95220b32/`, launched 11:52:34 local, tide steps in its log):

| Tide step (local) | Minute from launch | Private-bytes step |
|---|---|---|
| 06:00:00 (-12 cm) | 7.4 | none (like the trace's first) |
| 06:11:23 (-14 cm) | 18.8 | +84 at minute 19 |
| 06:22:09 (-16 cm) | 29.6 | +102 at 30 |
| 06:33:14 (-18 cm) | 40.7 | +91 at 41 |
| 06:45:36 (-20 cm) | 53.0 | +95 at 53 |

Only its +54 at minute 46 has no tide step. The 95220b32 Galveston soak's six steps (minutes 29, 33, 36, 41, 46, 52)
also each fall within about a minute of a tide step (29.8, 33.6, 37.2, 42.4, 47.3, 53.2 min).

**So:** each 2 cm tide step moves the coast's followers. CLAUDE.md's re-centre note says that makes every instanced mesh
resend its instances to the distance-field and Lumen scenes. On the render side, D3D12 grabs about 100 MB of new heap
for it and keeps it in its pool as unused. That fits:
- the lake staying flat (no tide);
- the staircase following time, not distance (the tide follows the clock);
- the start minute varying with the clock hour at launch.

The Gulf soak's 7 tide steps stayed flat, maybe because offshore there are few instanced meshes to resend.

**Not done:** callstacks. The D3D12 heap growth is untracked by FMalloc, so the trace's memalloc callstacks won't hold
it directly. Unreal Insights' memory views have no command-line export that I know of; the `.utrace` is on the PC for
anyone to open. A quicker check would be `-SailingTideStep` or freezing the tide, if the game has one, to see whether
the steps vanish.
