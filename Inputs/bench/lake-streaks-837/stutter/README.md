# Frame pacing on the lake: traced reruns (PC, Nov 26 2026)

**Setup:** every run is the same 60 s lake chase as `stutter-main/followup/`: 4K Ultra, windowed, `r.VSync 0`, the demo at
TWA 60, 12 kn, crew off, `-trace=cpu,frame,gpu -statnamedevents`. Slow and fast frames are taken from 40-46 s of each
trace (slow over 22.5 ms, fast under 19 ms).

## #839 at f186aa47 (the wake FFT's columns in contiguous blocks)

**Build:** MSVC succeeded with 0 project warnings. Package `Windows-pr839-f186aa47`. f186aa47 contains main 8e5cbfce.

| Traced run | p50 | p95 | p99 | Frames > 2 ms off median | Frame-to-frame change > 2 ms | Game p50 | Render thread waiting on visibility (slow minus fast) |
|---|---|---|---|---|---|---|---|
| `followup/`, main d8f2a3dc | 20.59 | 22.85 | 24.10 | 14.4% | 29.4% (mean 2.24 ms) | 10.1 | +3.3 ms |
| `stutter-main/scopes/`, main 8e5cbfce + scopes | 22.21 | 27.19 | 33.93 | 39.2% | 57.0% (mean 4.44 ms) | 16.2 | +0.5 ms |
| **#839 f186aa47** | **22.20** | **26.31** | **29.85** | **31.0%** | **48.2%** (mean 3.51 ms) | 16.3 | +0.4 ms |

**Background worker time per render frame** (`f186aa47-workers.txt`):

| Scope | Slow | Fast |
|---|---|---|
| All background `ParallelFor Task` | **17.0 ms** | **24.7 ms** |
| (the scopes trace on 8e5cbfce) | 39.3 | 46.0 |
| of which the wake FFT's columns, `Sailing_PF_WakeFftCols` in the scopes trace | 27.6 | 32.5 |

- **The column fix took about 22 ms of worker time per frame off the background `ParallelFor` load:** 39-46 ms became
  17-25 ms. That's about what the columns cost before, so they now cost a fraction of it.
- **No per-body names on #839:** its branch doesn't carry #837's names (`Sailing_WakeGridRows`, ...), so the remaining
  `ParallelFor` time isn't split by body here. #837's trace will give that.
- **Against the same base, the 8e5cbfce scopes trace:**
  - p99 falls from 33.9 to **29.9 ms**;
  - frames changing by more than 2 ms fall from 57% to **48%**;
  - the mean frame-to-frame change falls from 4.4 to **3.5 ms**.
- **Against `followup/` on d8f2a3dc it's still rougher, but that isn't the FFT.** Both 8e5cbfce-based traces run the game
  thread at about 16 ms against 10 ms. The only merge between those mains is #823 (frigate decks). Worth a look on its
  own: something there made the lake's game thread about 6 ms heavier.
- **The visibility wait** that drove the slow frames in `followup/` is small in both newer traces (+0.4-0.5 ms). Their
  slow frames follow the heavier game thread and general render-thread work instead (`f186aa47-render-thread.txt`).

## #837 (773f28dd or newer: background priority and named scopes)

Not yet run. It waits for the Mac's asset commit and goes with #837's stills. It will add the per-body names, including
`Sailing_WakeGridRows`.

Bean's Saved was held aside and restored for every run (7B5CA7BE).
