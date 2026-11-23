# PR #817 (film mode) on the PC at e961e382, Nov 23 2026

Branch `claude/project-thread-q73bv9` at **e961e382**: one commit on main 906c9034, code only. It ran in a new worktree
(removed afterwards) with nothing committed or pushed. The frigate regeneration's single-threaded Blender build was
running alongside the whole time, so the timings may be a little slow. Free RAM never fell below 36 GB.

## Build and tests

- **Build:** `scripts\windows\build.ps1` Succeeded, 0 errors.
- **Tests:**

| Filter | Tests | Failed | With warnings |
|---|---|---|---|
| SailingSim.Smoke.FilmMode | 4 (FrameClock, ShotMoves, ShotParse, Switches) | 0 | 0 |
| SailingSim.Smoke | 36 | 0 | 1 (the standing missing-sample warning) |
| SailingSim.UI | 44 | 0 | 1 |
| SailingSim.Visual | 106 | 0 | 3 (standing) |

- **Package:** Development `Packaged\Windows-pr817-e961e382` (kept), 5 min; cook "Success - 0 error(s), 1 warning(s)".

## Film runs

**Settings:** Ultra, 3840x2160, `-SailingFilm`, the same shot as the reel test: J/22, Lake launch 1, AfternoonBreeze 12
kn, 16:00, seed 7, `-SailingShowCrew=0 -SailingTraffic=0 -SailingDemo -SailingTWA=60 -SailingHoldTWA=60
-SailingCinematic=1 -SailingNoHud`, with `-benchmark -fps=60 -SailingBench=20 -SailingBenchWarmup=10 -SailingRecord=8
-SailingRecordInterval=0.0166667`. The shot file is the README's orbit, at `Saved/reel/orbit-hero.json` in the package.
Frames are on the PC in `D:\dev\reel-test\pr817-e961e382\{tripod,path}\frames`.

| | Tripod (`-SailingCapture=Tripod`, defaults 40 m, 1.6 m, 20 deg) | Path (`-SailingCapture=Path -SailingShotFile=reel/orbit-hero.json`) |
|---|---|---|
| Log | "Reference capture: Tripod, 20 deg, auto exposure frozen at 2.5 s, motion blur 0.50, film quality" | "Film shot: .../Saved/reel/orbit-hero.json, 2 keys over 6.00 s"; "Reference capture: Path, 35 deg, ... motion blur 0.50, film quality" |
| camera.json | `motion_blur` 0.50, `film_quality` true | `motion_blur` 0.50, `film_quality` true, `hfov_deg` 28 (the second key) |
| **Frames** | **481** (frame_0000 to frame_0480) | **481** |
| Doubled / skipped | 0 doubled, 0 large steps | 0 doubled. One large step, at frame 168 (the orbit's fastest move). |
| Seconds per frame | **1.25** (10.0 min of frames) | **1.24** |
| Size | 3.99 GB | 4.25 GB |
| Errors | only the two standing frame-0 engine ensures (PSOPrecache, DoubleFloat) and their stacks | the same |

## Finding: the frame-counted recording doesn't engage under `-benchmark -fps=60`

The runs wrote **481 frames, not 480**, and neither log has the PR's "SailingRecord: fixed step ..." line or
"SailingRecord: N of N frames recorded".

- `SailingGameMode.cpp` only builds `FFilmFrameClock` `if (FApp::UseFixedTimeStep())`.
- With `-benchmark -fps=60` the engine runs a fixed step (bench.json: every frame exactly 16.67 ms, 1,201 frames over
  20.02 s), but through `FApp::IsBenchmarking()`. `UseFixedTimeStep()` reads false, so the old timed loop ran.
- `SailingSim.Smoke.FilmMode.FrameClock` passes because it drives `FFilmFrameClock` directly.
- The likely fix is to check `FApp::IsBenchmarking() || FApp::UseFixedTimeStep()`, or to pass `-UseFixedTimeStep` too.
  I didn't try either (nothing pushed to the branch).

## Look

Three 1080p frames per run are attached (`tripod-frame0000/0240/0480`, `path-frame...`). A 1:1 cloud sheet compares the
reel test's A2 chase rig, the film tripod and the film path: `clouds-1to1-reelA2-vs-tripod-vs-path.png`.

- **Tripod:** the 40 m, 20 deg framing suits the J/22: the whole boat, the rig and some sky. It pans live, but she
  drifts from left of centre (frame 0) to right of centre (frame 480), so the pan trails her a little.
- **Path (the README's sample orbit):** the opening frame is good, at -100 deg and 22 m. At 4 s and after, the camera at
  16-18 m with a 28 deg lens is so close that the sails fill the frame and the hull is cut at the bottom. That is the
  sample shot's framing, not a bug.
- **Motion blur is on in both** (0.5). In the tripod the pan blurs the clouds behind her into horizontal streaks
  (1:1 crop, middle).
- **Cloud edges against the reel test:**
  - The film clouds lose the grainy, frosted speckle the reel test's clouds had (crop, left).
  - The path frame's cumulus outlines are smoother (crop, right), but small stair-steps still show along them at 1:1.
  - The tripod crop has one blocky dark rectangle inside a cloud, smeared by the pan blur.
  - Better than the reel test, but not clean at 1:1.
- **Water:** no dithered stripes under the boat at 1080p; the wake reads cleanly.

Bean's Saved was held aside for both runs and restored (7B5CA7BE). The worktree was removed: crew link unlinked first,
541 crew files intact.
