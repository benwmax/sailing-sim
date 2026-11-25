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
