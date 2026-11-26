# #836 at 0d2ac23a (tide-step dead band): forced steps and a parked boundary run, for the record (PC, Nov 26 2026)

**#836 is merged** (main 412440c8). These runs are on its last head, 0d2ac23a, in the Development package
`Windows-pr836-0d2ac23a`.

**Setup:** Galveston, from the soak's Bolivar Roads start, 4K windowed. Each run writes a `*-tide-steps.txt` with its
"Tide step" lines.

| Run | Settings | fps | p99 | Max | Peak render ms in each 20 s window | Frames > 50 ms |
|---|---|---|---|---|---|---|
| forced-ultra | Ultra, demo, clock 15:00, `-SailingTideStepEvery=20`, 120 s | 41.1 | 54.8 | 83.9 | 84 / 78 / 90 / 73 / 70 / 62 | 85 |
| forced-medium | Medium, the same | 78.9 | 27.8 | 53.8 | 49 / 48 / 50 / 49 / 51 / 56 | 4 |
| parked-boundary | Ultra, no autopilot, `-SailingKeepStart`, clock 15:30, 300 s | 53.0 | 23.1 | 53.5 | 24-26 in every window except the step's: 53 | 3 |

## The dead band: no flapping

- **Parked across a step boundary:** in 5 minutes she drifted from the start while the tide moved through a boundary. The
  followers stepped **exactly once**, from -42 to -44 cm at frame 11,372 (about 3.6 min in), and never back.
  - That step's frame peaked at 53 ms of render thread; every other window stayed at 24-26 ms.
  - In the 45-min soak on d5be42d, without the dead band, the followers went -40/-38/-40/-38 within 1-3 frames at a
    boundary.
- **Forced steps:** each run has exactly one "Tide step" line per forced step (7 in 120 s), alternating -36 and -38 cm,
  with no extra flips between them.

## The worst frames around steps

- **Medium:** each forced step peaks at 48-56 ms of render thread. Only 4 frames in 2 min go over 50 ms. That matches
  d5be42d's Medium run (45-52 ms).
- **Ultra:** steps peak at 62-90 ms, with 85 frames over 50 ms. **Read this with care: this run was the package's first
  launch.**
  - The package was built at 22:17 and never run before, and `../../gt-regression-823/` shows that a fresh package's
    first run is heavier on this PC (game thread +6 ms, everything slower).
  - d5be42d's warm Ultra pairs had steps of 48-60 ms.
  - A second Ultra run of this package would give the fair number. I can add it in a free slot.

Bean's Saved was held aside and restored for every run (7B5CA7BE).

## Warm Ultra rerun on main 412440c8 (#836 merged), Nov 26

**Package and setup:** Development package `Windows-412440c8`, which is kept for the Friday build. The same Galveston
forced-step run: Ultra, demo, clock 15:00, `-SailingTideStepEvery=20`, 120 s at 4K.
- **Run order:** a cold launch, then warm runs.
- **Pinned date:** the warm runs that show the steps are pinned to `-SailingDate=2026-11-25`, the local date of the
  0d2ac23a runs above (followers at -36/-38 cm).
- **Why the pin:** without it, on Nov 26's tide, the followers sit at -22/-24 cm and the forced steps stopped after the
  first one.
  - The 1.2 cm dead band is wider than half the forced 2 cm swing, so a tide near the middle of a band never leaves it.
  - This is a measuring problem only, and #841 makes the forced swing 3 cm.

| Run | Steps in 120 s | fps | p99 | Max | Peak render ms in each 20 s window | Frames > 50 ms |
|---|---|---|---|---|---|---|
| 0d2ac23a forced-ultra (above, **cold**) | 7 | 41.1 | 54.8 | 83.9 | 84 / 78 / 90 / 73 / 70 / 62 | 85 |
| main, cold, Nov 26 tide | 1 (then swallowed) | 40.5 | 53.8 | 72.0 | 38 / **72** / 36 / 37 / 36 / 34 | 60 |
| main, warm, Nov 26 tide | 1 (then swallowed) | 51.5 | 24.2 | 54.1 | 25 / **54** / 25 / 25 / 25 / 24 | 3 |
| **main, warm, pinned to Nov 25** | **7** (-36/-38 in turn) | **51.2** | **26.9** | **55.7** | 29 / 56 / 53 / 55 / 56 / 52 / 51 | **7** |

(Window peaks are max render-thread ms per 20 s of the frames.csv. Frames > 50 ms are frame_ms over the measured window.)

**Warm, each Ultra step costs one frame of 51-56 ms,** and there are 7 frames over 50 ms in 2 min, one per step:
- the cold 0d2ac23a run's 62-90 ms and 85 frames were the first-run effect;
- between steps the frames are 24-25 ms;
- Medium (above) was 48-56 ms.

**What the step frames spend (warm traced run):**
- **Method:** the same pinned run, `-trace=cpu,frame -statnamedevents`. The six step frames (7 frames over 45 ms) are
  compared with the 58 frames under 30 ms around them.
- **Files:** `main412-step-render-thread.txt`, `main412-step-game-thread.txt`.

**Render thread, slow minus fast (ms):**

| Scope | Slow | Fast | Diff |
|---|---|---|---|
| `SceneRender` | 40.4 | 15.7 | **+24.7** |
| `FTaskBase::WaitImpl_StateChangeEvent_WaitFor` | 14.9 | 3.2 | +11.8 |
| `UpdateAllPrimitiveSceneInfos` / `UpdatePrimitive` | 11.5 | 0.8 | **+10.7** |
| `ExecuteCommandList` | 8.1 | 0.4 | +7.7 |
| `InitViews` / `ProcessVisibilityTasks` | 7.4 | 2.6 | +4.8 |
| `PrepareDistanceFieldScene` (of which `UpdateDistanceFieldObjectBuffers` 3.8) | 4.7 | 0.8 | +4.0 |
| `AddPrimitiveCommand` | 3.2 | 0.0 | +3.1 |
| `FScene_VirtualShadowCacheUpdate` | 3.1 | 0.1 | +3.0 |
| `RemovePrimitive` | 2.7 | 0.1 | +2.6 |
| `SceneCulling_Update_FinalizeAndClear` | 5.7 | 3.6 | +2.0 |
| `UpdateLumenScene` | 2.2 | 0.4 | +1.9 |
| `UpdateTransformCommand` | 2.0 | 0.2 | +1.7 |

**Game thread:**
- It waits for the render thread: `Sync_RenderingThread` +23.5 ms.
- `TG_PostPhysics` ticks are +5.8 ms; the move itself is in the ticks, which aren't split by name in this trace.

**Reading:** the step cost is the render thread updating the moved primitives' scene info and transforms.
- The biggest parts:
  - `UpdatePrimitive` (+10.7 ms);
  - `ExecuteCommandList` (+7.7);
  - the distance-field object buffers (+4.0);
  - the virtual shadow cache (+3.0).
- Some primitives are **removed and re-added** (`AddPrimitiveCommand` +3.1, `RemovePrimitive` +2.6) instead of just
  moved, which is worth finding next: a component recreating its render state on the step.

Bean's Saved was held aside and restored for every run (7B5CA7BE).
