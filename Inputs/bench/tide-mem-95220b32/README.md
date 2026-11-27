# Tide-step memory checks on Windows-95220b32 (PC, Nov 27 2026)

**Runs:** stationary Galveston, `../membisect-galveston/still-95220b32/`'s arguments plus `-SailingTideStepEvery=20` (a
forced 2 cm step every 20 s: 52 steps in each run) and `-llm -llmcsv`, 17 min each, 4K Ultra. One switch added per run
(`args.txt`). The baseline ran at 07:57 local, a at 11:16, b and c after the freeze build. Bean's Saved held and
restored each time (7B5CA7BE).

**Files per run:** `memory.csv` (private bytes and working set every minute), `d3d12-unused-per-minute.csv` (LLM platform
`D3D12AllocatorUnused`, one sample a minute), `LLMPlatform_*.csv` (every second).

| Run | switch | private MB, minute 3 to 17 | private MB/min | D3D12AllocatorUnused MB, minute 3 to end | per min |
|---|---|---|---|---|---|
| `0-baseline` | none | 16,115 to 19,384 | **233.5** | 1,447 to 4,905 | 266 |
| `a-lumenhw0` | `-SailingLumenHW=0` | 16,524 to 19,306 | 198.8 | 1,214 to 4,380 | 244 |
| `b-tidebatch0` | `-SailingTideBatch=0` | 15,564 to 15,949 | **27.5** | 664 to 1,658 | 76 |
| `c-classictrees` | `-SailingClassicTrees` | 15,466 to 19,263 | 271.2 | 1,391 to 4,975 | 276 |

## Which one removes the growth

- **`-SailingTideBatch=0` takes away about 88% of it** (233.5 to 27.5 MB/min of private bytes). Moving everything
  at once on the step frame, instead of a budget of instances a frame over several frames, leaves the D3D12 pool far less
  unused heap: 76 MB/min, against 266. So batching is involved: spread over frames, each batch looks to grow the pool
  afresh. It doesn't stop the growth entirely; the D3D12 pool still grows about 30 MB a step.
- **Ray tracing (`-SailingLumenHW=0`) is a small part:** 15% less.
- **The crown tiles (`-SailingClassicTrees`) are not it:** slightly more, not less.

So per step on this route: about 75 MB with batching, about 9 MB of private bytes without it. Each run is a single
17 min sample; run-to-run noise on the baseline isn't measured here.
