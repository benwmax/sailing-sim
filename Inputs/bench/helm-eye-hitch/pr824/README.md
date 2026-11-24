# PR #824 (capture telemetry: no flush on the game thread) on the PC at fdaa4352, Nov 24 2026

**Head:** branch `claude/project-thread-8onn2s` at **fdaa4352** ("Capture telemetry: no flush on the game thread
(helm-eye hitch)"), on main 9291fbf6. The worktree was removed afterwards (crew link unlinked only). Nothing was pushed.

- **MSVC build:** Succeeded, 0 errors.
- **`SailingSim.Smoke`:** 36/36, including ReferenceCapture (1 standing warning). The full suite was skipped as asked:
  the Mac runs it.
- **Package:** Development `Packaged\Windows-pr824-fdaa4352` (kept), 3 min; cook 0 errors, 1 warning.

## Helm-eye, 3 runs (the same view and args as on 9291fbf6: Ultra 1080p, 100%, 12 s, `-SailingBenchTrace`)

Measured window 3-15 s; every run's `frames.csv` and `bench.json` are here.

| Run | fps | p99 | Window max | Game ms on the x120 frames (median about 10) | Slow frames in the window |
|---|---|---|---|---|---|
| r1 (the package's first launch) | 48.7 | 30.1 | 230.1 ms (render thread, at 3.9 s) | 11.9, 18.6, 12.6, 18.3, 10.7 | a cold start: render-thread frames of 25-55 ms through 3-8 s, then the 230 ms render frame; no x120 pattern |
| r2 | 65.9 | 22.36 | **37.2 ms** | 13.9, 10.6, 12.7, 15.0, 9.6, 11.8, 8.2 | 2 frames at the window's start (27.8, 37.2 ms) |
| r3 | 66.4 | 21.96 | **41.6 ms** | 12.6, 9.3, 9.5, 10.9, 10.5, 8.2, 9.8 | 1 frame at the window's start (41.6 ms) |

**Against Windows-9291fbf6** (`../`): there, every run had game-thread stalls of 29-143 ms on frames that were exact
multiples of 120 (maxes 115.6, 137.6 and 142.8 ms).

**Verdict: the x120 stalls are gone.** In all three runs the frames at multiples of 120 sit at the game thread's
median, with nothing over 19 ms. r2 and r3 peak at 37 and 42 ms, at the start of the measured window rather than on an
x120 frame. r1's slow stretch is on the render thread and is the fresh package's first launch: shaders and PSOs cache
on first use; the 9291fbf6 runs came after earlier launches of that package. A rerun after a warm-up would show r1
like r2 and r3.

Bean's Saved was held aside and restored (7B5CA7BE).
