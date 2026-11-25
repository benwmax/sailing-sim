# PR #836 (head d5be42d) on the PC, Nov 25 2026

**Worktree:** `D:\dev\ss-fix-wt\pr836` at d5be42d. **Package:** Development `Packaged\Windows-pr836-d5be42d`.

## Build and tests

- **MSVC build: succeeded, 0 errors.** All 53 warnings are in engine headers (Class.h, SoundWaveProcedural.h, Chaos);
  none come from the PR's files, and the new test compiles clean.
- **`SailingSim.Coast`: 23 tests, 0 failed** (19 clean, 4 with warnings; `test-coast.json`). `KeptStaticFollowsTide`,
  `TideStep` and the new `TideStepBatched` all pass.

## Forced steps

**Setup:** Galveston at 4K, the soak's route (Bolivar Roads, the demo, clock 15:00), `-SailingTideStepEvery=20` (6 steps).

| Run | Each step's peak render ms | Frames > 50 ms | fps | Render avg ms | DF instances |
|---|---|---|---|---|---|
| Ultra, d5be42d | 83 / 81 / 89 / 75 / 74 / 53 | 69 | 39.3 | 24.9 | 11,215 |
| Medium, d5be42d | 45 / 51 / 52 / 51 / 48 / 49 | 1 | 80.1 | 12.4 | 393,132 |
| Medium, `-SailingTideBatch=0` (no batching) | 374 / 271 / 273 / 275 / 273 / 273 | 13 | 78.2 | 12.7 | 393,092 |

- **Medium:** the batching alone takes each step from 270-370 ms to 45-52 ms. Medium keeps its distance fields (393k
  instances), as intended.
- **Ultra:** the steps are 74-89 ms. That's well under 7304f52's 400-810 ms (`Inputs/bench/tide-df-fix/`), but this run
  was slow all through.
  - The game thread was 18.6 ms and render 22 ms before the first forced step (3-18 s). The good runs had game 13.6 and
    render 19.8.
  - So this is the session, not the steps. The same thing showed on one of my three earlier batched runs of the local
    patch; the traced re-run of it was clean, with steps of 52-56 ms.
  - **Still to settle:** I'll run back-to-back Ultra pairs (patch, and `-SailingTideDF=1`) after the Saturday rehearsal,
    to tell PC noise from the patch.

## Quality switch while Galveston runs

**Setup:** Ultra, then Medium, then Ultra again, through Pause > Settings > Graphics > Quality by `-SailingUIScript`. These are Slate key events inside
the game, not OS input. It ran on a throwaway profile. The shots are `q0-ultra`, `q1-medium` and `q2-ultra`; the log is
`quality-switch-log.txt`.

| Switch | Result |
|---|---|
| Ultra -> High | No line: hardware Lumen both sides, nothing to change |
| **High -> Medium** | **"Tide followers: 2648 components in or out of the distance fields"** (back in) |
| **Medium -> High** | **"Tide followers: 2648 components ..."** (out again) |
| High -> Ultra | No line |

- **No crash; exit 0.**
- The run logged the usual PSO ensure at frame 0.
- **One thing to know:** the engine's matrix-precision ensure ("OriginX <= OriginMax ...", which every Galveston run
  logs at frame 0) fired this time at the switch to Medium instead. It's an ensure, not a crash. It looks like the
  existing coast precision issue showing at a render-state rebuild, and isn't the PR's.
- The switch frames cost up to 2.0 s, as a tier change always does.

Bean's Saved was held aside and restored for every run (7B5CA7BE).

## Update (evening): Ultra pairs, and the 45-min natural-tide soak

### Ultra, back to back on the d5be42d package (forced steps every 20 s)

| Run | Each step's peak render ms | Frames > 50 ms | fps | Before the first step: game / render ms |
|---|---|---|---|---|
| PR as is, run 1 | 60 / 52 / 51 / 48 / 50 / 55 | 5 | 51.4 | 13.3 / 19.8 |
| `-SailingTideDF=1` (batching only), run 1 | 59 / 61 / 56 / 61 / 59 / 62 | 8 | 51.1 | 13.5 / 19.9 |
| PR as is, run 2 | 50 / 52 / 51 / 55 / 49 / 54 | 6 | 52.0 | 14.1 / 20.0 |
| `-SailingTideDF=1`, run 2 | 59 / 65 / 61 / 64 / 55 / 57 | 8 | 50.6 | 14.2 / 20.0 |

- **The slow Ultra run above was PC noise.** All four runs are clean, with game 13-14 ms before any step.
- With the PR, **steps are 48-60 ms**. With batching alone they are 55-65 ms, so taking the followers out of the DF
  saves about 7 ms a step.

### 45 min, Galveston, natural tide, 4K Ultra

**Setup:** the soak's route (Bolivar Roads, the demo, clock 15:00), trace window 30-40 min.

**Result:** **exit 0, 53.1 fps, p99 23.2 ms.** Crash folders: the usual frame-0 ensure only.
- **No 380-520 ms stalls.** The longest render-thread frame was 88 ms (34.4 min). Only 4 frames went over 60 ms after
  the load:
  - 98 ms at 29.9 min: the trace starting, our own;
  - 84 ms at 34.4 min and 71 / 77 ms at 37.2 min: tide steps (below);
  - 1085 ms at 45.1 min: the bench writing its results at exit.
- **New finding: the tide step flaps** (`soak45-tide-steps.txt`).
  - **Where:** at 34 and 37 min the followers went -40, -38, -40, -38 cm within 1-3 frames. For example frames
    110006/110007/110009, and 119069/119070/119073.
  - **Why:** `TideHeight` is read at the boat's position, so as she sails it can sit on a 2 cm rounding boundary and
    round back and forth.
  - **Cost:** each flip starts the batched move again. With the PR that costs 70-90 ms frames instead of a single 55 ms
    one. Before the PR, each flip would have been a full stall.
  - **Suggested fix:** hysteresis in the follow step. Keep the shown step until the tide is more than about 1.5 cm from
    it (a dead band), or step only once the rounded value has held for about a second. That is the remaining source of
    tide hitches.
- **Memory:** flat to 30 min (working set 3.71-3.77 GB). From 30 min, when the trace window opened, it rose about
  400 MB (working set 4.18-4.20 GB, private 15.3 GB at 40 min). That's probably the trace's buffers. A soak without
  the trace would confirm it.
