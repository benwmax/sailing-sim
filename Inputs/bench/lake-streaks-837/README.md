# #837 lake streaks at 48c61014 (the Mac's asset commit), PC, Nov 26 2026

**Worktree:** `D:\dev\ss-fix-wt\pr837` at **48c61014**, which rebuilt M_Water and M_WaterV4 on 773f28dd. The LFS content
was pulled, and M_WaterV4 is the real asset. **Package:** Development `Packaged\Windows-pr837-48c61014`.

## Build and tests

- **MSVC build:** succeeded, 0 errors, 0 warnings in the project's `Source/`.
- **`SailingSim.Visual`: 109 tests, 0 failed** (106 clean, 3 with warnings; `test-visual-48c61014.json`).
  **WindrowFrames passes**, and so does every test in `WaterTests.cpp`: WakeGrid, CapillaryWaves, WaveMatch, Whitecaps*,
  WaterBodyTransmission, FarWaterCurvature, FarCap*, CapRepeat, GaleSpray, SprayQuad, WaterRingOverlap and WakeGridShip.

## Clips and stills, main d8f2a3dc against 48c61014

**Files:** `clips/<build>-<place>-<kn>-<view>.mp4` (10 s, 30 fps, 720p, H.264 crf 28) and a `.webp` still beside each,
from the middle frame at 1920.

**How they were shot:** 1080p film takes at Ultra, the demo at TWA 60, an afternoon breeze at 14:00, crew off.
- **Places:**
  - `club`: launch 1, Off Rush Creek, about 0.8 km from the yacht club.
  - `3km`: `-SailingStartAt=3000,-550,0`, mid-lake about 3 km north.
- **Views:**
  - `helm`: `-SailingCapture=HelmEye`.
  - `up30`: a shot file in her frame, 20 m astern and 30 m up, pitched 50 deg down, fov 60.
- **Winds:** 8 and 12 kn.
- **A/B on the branch, 12 kn, 3 km, up30:**
  - `pr837-3km-12kn-up30-nowindrows`: `-SailingNoWindrows`.
  - `pr837-3km-12kn-up30-classicwindmap`: `-SailingClassicWindMap`.

All 18 takes wrote 300 of 300 frames.

**First look at the stills:**
- From 30 m up and from the helm, main and the branch are very close at this size. Both show faint diagonal streaks on
  the water.
- The windrows' change in frame and in time is easier to judge in the clips than in stills: compare
  `main-3km-12kn-up30.mp4` with `pr837-3km-12kn-up30.mp4` and with its `-nowindrows` and `-classicwindmap` twins.

## Frame pacing

See `stutter/README.md`.

Bean's Saved was held aside and restored for every run (7B5CA7BE).
