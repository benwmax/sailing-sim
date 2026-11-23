# PR #817 (film mode) on the PC at cc8e91cb, Nov 23 2026

Branch `claude/project-thread-q73bv9` at **cc8e91cb** ("Film mode: count frames under -benchmark; tripod frames the
whole boat"), on e961e382. It ran in a new worktree (removed afterwards) with nothing committed or pushed. The
frigate regeneration's light shards were running alongside (3 of them), so the timings may be a little slow. Free RAM
never fell below 36 GB.

- **Build:** `scripts\windows\build.ps1` Succeeded, 0 errors.
- **Tests:** `SailingSim.Smoke.FilmMode` 4/4 (FrameClock, ShotMoves, ShotParse, Switches).
- **Package:** Development `Packaged\Windows-pr817-cc8e91cb` (kept), 5 min; cook 0 errors, 1 warning.

**Settings** (as e961e382 and the reel test): Ultra 3840x2160, `-SailingFilm`, J/22, Lake launch 1, AfternoonBreeze 12
kn, 16:00, seed 7, `-SailingShowCrew=0 -SailingTraffic=0 -SailingDemo -SailingTWA=60 -SailingHoldTWA=60
-SailingCinematic=1 -SailingNoHud`, `-benchmark -fps=60 -SailingBenchWarmup=10 -SailingRecordInterval=0.0166667`.
Frames are on the PC in `D:\dev\reel-test\pr817-cc8e91cb\`.

## 1. The fix: 480 frames, with the log lines

| Run | Frames | Log | s/frame | Motion blur |
|---|---|---|---|---|
| Tripod (defaults: 26 deg, aim 0.45), `-SailingRecord=8` | **480** (frame_0000 to frame_0479) | "SailingRecord: fixed step 0.01667 s, 480 frames from frame 600, one every 1" and "SailingRecord: 480 of 480 frames recorded" | 1.32 | 0.50 |
| Path (the README's orbit, now ending at 24 m and 32 deg), `-SailingRecord=8` | **480** | the same two lines; "Film shot: .../Saved/reel/orbit-hero.json, 2 keys over 6.00 s" | 1.29 | 0.50 |
| Cloud A: tripod, `-SailingMotionBlur=0`, `-SailingRecord=2` | **120** | "120 frames from frame 600, one every 1"; "120 of 120 frames recorded" | 1.31 | 0.00 |
| Cloud B: as A plus `-SailingCloudMode=1` | **120** | the same | 1.31 | 0.00 |

The logs show no errors beyond the standing frame-0 engine ensures and their RHI breadcrumb lines.

**Framing** (`tripod-` and `path-frame0000/0240/0479-1080p.jpg`):

- **Tripod:** at 26 deg the whole boat is in frame with sky above. She still drifts from left of centre to right of
  centre over the 8 s, but stays well inside the frame.
- **Path:** the orbit now keeps the whole hull in frame at 4 s and at the end, with the masthead just cut at the top.

## 2. Cloud A/B (`clouds-1to1-blur-vs-noblur-vs-mode1.png`)

Frame 60 of each tripod run, at two 800x450 crops, 1:1 at 4K:

- **Without motion blur (A)** the clouds show a regular **blocky grid of square tiles, about 8 px**, along the edges
  and through the thin parts: the stair-steps. This is the same structure as the reel test's "frosting", now sharp.
- **The blurred run** smears the same tiles horizontally into streaks with the pan. It hides the grid but does not
  remove it; the dark blocky patch inside the cloud is the same tiles.
- **`-SailingCloudMode=1` (B) changed nothing visible.** A and B differ by 0.38 grey levels on average (0.33 in the
  sky band), which is noise. Either mode 1 renders the same as the film's mode 3 at this setting, or the switch isn't
  reaching the cloud render target under `-SailingFilm`. The README says it should override. The log has no line
  naming the cloud mode in use, so I can't tell which; a log line, or a cvar dump at start, would settle it.
- So the stair-steps aren't motion blur and aren't (visibly) the render-target mode. The ~8 px tiling looks like a
  tile-based cloud step (the tracing tile or the weather-map texel) rather than reconstruction.

Files: `tripod-`/`path-frame*-1080p.jpg`, `clouds-1to1-blur-vs-noblur-vs-mode1.png`, both `camera.json`, `status.txt`.
Bean's Saved was held aside and restored (7B5CA7BE). The worktree was removed: crew link unlinked first, 541 crew files
intact.
