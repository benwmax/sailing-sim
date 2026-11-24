# Saturday capture dry run on main adb0e90e: PAUSED (Bean, 23:32 UTC Nov 24)

## Done

- **Worktree:** a clean one at `D:\dev\ss-fix-wt\dryrun`, on main **adb0e90e** (includes #829). I kept it for the resume;
  the crew is still linked.
- **MSVC build:** Succeeded, 0 errors (16:54 local).
- **Shot files:** committed to `Inputs/reel-rehearsal/shots/` (88f5917e): the R-shots, H02, P1, P4 and P5.
- **Storm timing for P2, worked out from the source (not run yet):**
  - With `-SailingStormDelay=D` and no `-SailingWeatherTime`, the weather clock runs on the game clock.
  - The gust front reaches the start at about 150 s + D (`FWeatherSystem::kFrontArrives` = 150).
  - With a 10 s warm-up and `-SailingRecordInterval=2` over 300 frames (600 s), a third of the way in is 200 s into
    the recording, so D ≈ 60. This needs checking against the log.

## Stopped

The full test suite (`test.ps1 -Filter SailingSim`) had been running about 38 minutes and wasn't close to done. I
stopped my own job; its editor process had already ended with it. No game was running, and Bean's Saved wasn't held
(profile 7B5CA7BE, unchanged).

## Left for the resume

1. The full test suite, then the FULL Development package.
2. P1 wireframe check.
3. P2 storm time-lapse timing.
4. P3 real day 2023-06-11.
5. The R-shots and the three menus.
6. The main baseline (16 views, frigate, Galveston) against 9291fbf6.
7. The local Saturday capture script.
