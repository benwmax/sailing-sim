# Reel capture test (PC, Nov 20 2026): in-game recording against Movie Render Queue

The same 8 s shot made three ways, on main `76a41ea4`. There were no code or repo changes. Frames are kept on the PC in
`D:\dev\reel-test\` (13 GB, all 4K PNG).

**Shot:** J/22, Lake, `-SailingWeather=AfternoonBreeze -SailingWind=12 -SailingHour=16 -SailingSeed=7 -SailingShowCrew=0
-SailingTraffic=0 -SailingDemo -SailingTWA=60 -SailingHoldTWA=60`, launch 1, Ultra, `-SailingCinematic=1`,
`-SailingNoHud`, 10 s settle. No crew is visible in any run.

| | A1: in-game tripod | A2: in-game chase rig | B: Movie Render Queue |
|---|---|---|---|
| How | Dev package `Windows-76a41ea4`, `-benchmark -fps=60 -SailingBench=20 -SailingBenchWarmup=10 -SailingRecord=8 -SailingRecordInterval=0.0166667`, `-SailingCapture=ShoreTele` | the same, without capture mode: `-SailingCamYaw=90 -SailingCamDist=40 -SailingCamPitch=-3` | editor PIE through MRQ (`D:\dev\reel-test\reelB.py`, outside the repo), the game's own mode, the same game args on the editor command line |
| Camera | tripod 200 m off to leeward, 3 m up, 15 deg HFOV, panning (`reelA1.camera.json`) | the chase camera 40 m abeam, following | a cine camera on A1's tripod (15 deg), panning along A1's path integrated from its 60 Hz telemetry |
| Exposure | locked: auto exposure frozen at 2.5 s | the game's own (not locked) | locked at A1's meter, EV100 -2.10 (the game's scene scale) |
| Motion blur | **off** (capture mode sets MotionBlurAmount 0) | on (cinematic look) | on (8 temporal samples) |
| Frames | **481** (480 expected: the 1/60 s interval lands one extra) | **481** | **480** |
| Doubled / skipped | **0 doubled, 0 skipped** (consecutive-frame difference 0.75 to 1.49, median 1.07) | **0 doubled.** Two large steps at frames 476 and 478, near the end. | not checked (MRQ renders each frame) |
| Seconds per frame | **1.14** (548.6 s for 480 frames) | **1.24** (596.8 s) | **0.54** (256 s for the frames; 381 s with 600 engine and 32 render warm-up frames) |
| Run time | 9.9 min | 10.6 min | 6.9 min (editor start to quit) |
| Size | 4.26 GB | 5.04 GB | 3.85 GB |

## Arguments: brief against code

Every argument in the brief exists in the source: `-SailingCinematic`, `-SailingRecord`, `-SailingRecordInterval`,
`-SailingBenchWarmup`, `-SailingSeed`, `-SailingEV`, `-SailingHoldTWA`, `-SailingShowCrew` and `-SailingTraffic`. Three
gaps:

- **No 40 m tripod.** The only panning tripod is ShoreTele, fixed at 200 m, 3 m up and 15 deg HFOV (`ReferenceCapture.cpp`).
  The 40 m abeam framing exists only as the chase rig (A2), which follows the boat rather than panning.
- **`-SailingEV` is read only in capture mode.** I didn't guess a number: A1 locks by freezing auto exposure at 2.5 s,
  the capture's own default. A2's exposure is the game's.
- **Capture mode turns motion blur off,** so A2 is the rerun with the chase rig, motion blur on.

## Movie Render Queue: what it needed

- MRQ puts its own `MoviePipelineGameMode` into PIE by default, so the lake and boat are never built. The first
  two tries rendered only sky and water; they are kept on the PC as `B-mrq-try1-no-game` and `B-mrq-try2-no-game`.
  The old `game_mode_override` is deprecated and ignored. Setting **`soft_game_mode_override`** to `SailingGameMode` on
  `MoviePipelineGameOverrideSetting` works: the log reads "Game class is 'SailingGameMode'".
- With the sequence's tick resolution set to 60 fps, the 8 temporal samples had no sub-frame ticks ("Too many temporal
  samples", "zero delta time"). The default 24000 tick resolution works.
- **B's boat drifts off-centre.** The PIE run with MRQ's sub-stepped ticks doesn't follow A1's track exactly, so the
  pan, keyed to A1's path, has the boat right of centre by the middle of the shot. A tripod that tracks the pawn live
  would need a game-side hook.

## Look

All crops are 1:1 from frame 240 (`crops/`; each sheet is A1, A2, B left to right).

- **Rigging against the sky:** A1 and A2 are crisp, with the backstay and shrouds a pixel wide. **B is visibly softer**:
  the sail number, battens and stays are blurred, and so are the far shore and the water. B is also brighter and
  flatter: EV -2.10 sits about half a stop over A1's frozen meter. Likely causes are the cine camera's own
  post-process (the game's cinematic camera settings don't reach it) or MRQ's anti-aliasing with no spatial samples.
  It needs a second pass with `MoviePipelineAntiAliasingSetting.override_anti_aliasing` and a sharpened, matched exposure.
- **Water and wake:** A1's reflection under the boat shows a combed, dithered pattern (Lumen and TSR noise, horizontal
  stripes). **B's temporal samples clean it out:** the reflection is smooth. A2 is busy chop with motion blur; no shimmer
  between frames in the steps measured.
- **Far shore:** A1 is sharp, with trees and houses legible through the haze. A2 at 40 m is small. B is soft.
- **Clouds:** all three runs show the cumulus with **blocky, stair-stepped edges**: A1 and B top right, and A2 all
  over. This is the half-resolution cloud tracing at 4K. It is the most visible flaw for a reel, and the same in
  game and MRQ.
- **Lumen noise:** the dithered reflection in A1 is the only noise I saw. B has none.

## Files

- `reel-test-side-by-side-1080p.mp4` (14 MB, 1920x1080, 60 fps, 480 frames, H.264 CRF 18, made with ffmpeg):
  A1 top left, B top right, A2 bottom left.
- `crops/rigging.png`, `crops/water-wake.png`, `crops/far-shore.png`, plus each crop alone.
- `reelA1.camera.json`: A1's tripod.
- `B-editor-command.txt`: B's editor command line.

The 4K frames stay on the PC: `D:\dev\reel-test\A1-tripod\frames`, `A2-chase\frames` and `B-mrq\frames`, plus the
two empty-world MRQ tries. Bean's Saved was held aside for every run and restored (7B5CA7BE). ffmpeg was installed
with `winget install Gyan.FFmpeg` on Bean's typed OK, and nothing else was installed.
