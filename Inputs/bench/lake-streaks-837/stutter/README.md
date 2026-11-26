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

## #837 at 48c61014 (background priority and named scopes, no column fix)

**The run:** the same 60 s VSync-off lake run, traced. **This package was warm**: the trace came after its 18 clips. See
`../../gt-regression-823/` for why that matters.

| Traced run | p50 | p95 | p99 | Frame-to-frame change > 2 ms | Game p50 | Slow (> 22.5 ms) / fast (< 19 ms) frames in 40-46 s |
|---|---|---|---|---|---|---|
| `followup/`, d8f2a3dc | 20.59 | 22.85 | 24.10 | 29.4% (mean 2.24 ms) | 10.1 | 37 / 22 of 287 |
| #839 f186aa47 (**first run of a fresh package**) | 22.20 | 26.31 | 29.85 | 48.2% | 16.3 | 94 / 23 of 275 |
| **#837 48c61014 (warm)** | **20.24** | **22.27** | **24.06** | **24.1%** (mean 2.18 ms) | 11.2 | **7 / 46 of 298** |

**Worker time per render frame by the branch's new scope names, slow against fast frames:**

| Scope | Slow | Fast |
|---|---|---|
| **`Sailing_WakeGridRows`** | **35.9 ms** | **10.2 ms** |
| `Sailing_WindMapRows` | 5.3 | 2.2 |
| `Sailing_WaterDetailBlend` | 7.4 | 6.9 |
| `Sailing_TrafficBoatStep` | 2.2 | 1.8 |
| `Sailing_WaterFoamGrid` | 2.6 | 2.8 |
| `Sailing_SailClothRender` | 0.6 | 0.6 |
| all background `ParallelFor Task` | 40.0 | 14.1 |

- **Slow frames are rarer:** 7 in 298, against 37 in 287 in `followup/`. p99 and the frame-to-frame spread are a little
  better than `followup/`.
- **The few slow frames that remain are the wake grid's bursts:** `Sailing_WakeGridRows` takes 35.9 ms of worker time in
  them against 10.2 ms in fast frames. With them, the render thread waits +2.7 ms on its visibility tasks.
- **This is the pass the column fix on #839 (f186aa47) targets.** With both changes, the bursts should shrink too.
- **The f186aa47 row isn't a fair comparison:** it was a fresh package's first run (game thread 16 ms), so it can't be
  set against this one directly. A warm rerun of f186aa47, or of a tree with both changes, would settle it.

## #839 at f186aa47, warm rerun (the column fix, no #837 priority)

**The run:** the same 60 s VSync-off 4K Ultra lake run, traced. One untraced warm-up launch ran first, so the package was
warm, like the 48c61014 run. bench.json: avg 20.04 ms, p99 23.91, game 10.7 ms.

**Method:** both rows below are computed the same way here (`f186aa47-warm.frames.csv`):
- p50/p95/p99 and the frame-to-frame change are over 3-69 s of the trace's frames.csv.
- Its mean jump leaves out the one load jump over 200 ms, so it reads lower than the 2.18 above.
- Slow and fast frames are counted in 40-46 s, as before.

| Traced run (warm) | p50 | p95 | p99 | Frame-to-frame change > 2 ms | Mean jump | Game p50 | Slow / fast frames in 40-46 s |
|---|---|---|---|---|---|---|---|
| #837 48c61014 (priority and names) | 20.24 | 22.27 | 24.05 | 24.1% | 1.44 ms | 11.2 | 7 / 46 of 298 |
| **#839 f186aa47 (column fix)** | **20.02** | **22.09** | **24.08** | **21.6%** | **1.36 ms** | 10.4 | 9 / 38 of 298 |

**Worker time per render frame, slow against fast** (`f186warm-workers.txt`):

| Scope | 48c61014 slow | 48c61014 fast | **f186aa47 slow** | **f186aa47 fast** |
|---|---|---|---|---|
| All background `ParallelFor Task` | 40.0 | 14.1 | **11.4** | **16.3** |
| `Sailing_WakeGridRows` (#837's name) | 35.9 | 10.2 | not named on this branch | not named on this branch |
| `Sailing_WaterDetailBlend` | 7.4 | 6.9 | 7.6 | 7.0 |
| `Sailing_WaterFoamGrid` | 2.6 | 2.8 | 4.8 | 3.5 |

**Findings:**
- **The column fix removes the wake bursts.** On 48c61014, slow frames carried about 26 ms more background
  `ParallelFor` time than fast ones; on f186aa47 they carry *less* (11.4 against 16.3). The wake grid no longer lines up
  with the slow frames.
- **Pacing is a little better than 48c61014's:**
  - frames changing by more than 2 ms: 21.6% against 24.1%;
  - p50 and p95 are slightly lower;
  - p99 is the same (24.1 ms).
- **The remaining slow frames (9 in 298) are general render-thread work,** not our workers:
  - scene render is +5.1 ms in slow frames;
  - of that, the wait on the engine's visibility tasks is +2.2 ms (`f186warm-render-thread.txt`);
  - background `ParallelFor` time is lower in those frames, so the wait isn't behind our tasks.
- **The earlier f186aa47 row was the first-run effect.** Warm, the game thread is 10.4 ms, not 16.3.
- **Both changes together** (#837's priority on top of the column fix) should be no worse than either alone. Not traced yet.

Bean's Saved was held aside and restored for both launches (7B5CA7BE).
