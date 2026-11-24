# Film mode: recording the demo reel from the game

Dev-only tools for the portfolio demo reel (plan: the reel plan doc; capture test: `Inputs/reel-test/README.md` on the
inputs branch). Nothing a player sees changes: every piece is a launch switch read through `SailingArgs::Dev()`, which is
empty in Shipping, so record from a Development package. Code: `FilmMode.h`, `ReferenceCapture.h` (the `Tripod` and
`Path` presets), the capture in `SailboatPawn.cpp`, the recording loop in `SailingGameMode.cpp`. Tests:
`SailingSim.Smoke.FilmMode.*`.

## What it adds

| Switch | What it does | Why (the capture test) |
|---|---|---|
| fixed step (`-benchmark -fps=60`, or `-UseFixedTimeStep`) | `-SailingRecord=<s>` and `-SailingRecordInterval=<s>` are counted in frames (`FFilmFrameClock`): exactly round(record / interval) frames, one every round(interval / step) frames, numbered `frame_0000.png` on. The bench runs on until the last one is written. | The timed loop wrote 481 frames for 480. |
| `-SailingMotionBlur=<amount>` | Capture mode keeps that much motion blur (0.5 is a 180 degree shutter). `-SailingFilm` alone gives 0.5. Without either, capture mode stays at 0, as the reference stills need. | Capture mode set `MotionBlurAmount` to 0. |
| `-SailingEV=<EV100>` | Locks the exposure outside capture mode too (the chase rig, any view). | It was read only in capture mode. |
| `-SailingCapture=Tripod -SailingTripod=<distance m>,<height m>[,<hfov deg>[,<aim>]]` | A tripod set up off the boat's bearing (`-SailingCaptureBearing`, or to leeward; `-SailingCaptureAbsolute` for a compass bearing). Once it is set up it stays put and pans to follow her live, aimed at `aim` times her masthead height. Defaults are 40 m, 1.6 m, 26 deg and 0.45, which hold the whole J/22 from waterline to masthead in 16:9. | ShoreTele is fixed at 200 m, 3 m up and 15 deg. |
| `-SailingCapture=Path -SailingShotFile=<file>` | A keyframed camera move (below). A relative path is read from `Saved/`. If the file doesn't load, the log says why and the chase camera films instead. | |
| `-SailingFilm` | The offline quality boost: clouds traced with up to 512 samples and rebuilt over frames (`r.VolumetricRenderTarget.Mode 0`: the full-resolution mode 3 left dark stipple in the shaded cloud bases, PC on #818), the water's and Lumen's reflections at full resolution, a 200% TSR history, and on the capture camera Lumen reflection and final gather quality 2 with hit lighting. Costly, and meant only for frames written to disk. `-SailingCloudMode` and `-SailingCloudSamples` still override it. | Blocky cloud edges at 4K, and dithered stripes in the reflection under the boat. |
| `-SailingViewMode=wireframe\|lightingonly\|unlit` | A layer pass of the shot. In a package cooked with debug view modes (`r.ForceDebugViewModes=1` in the config at cook time, which needs Bean's label), the engine's own view mode. Without them, lighting only falls back to `ShowFlag.LightingOnlyOverride`, with the sails' insignia, number and colour taken off; wireframe and unlit log why not and stay lit. The cvar is never forced at run time: in a package cooked without the shaders that crashed on the first frame (PC on #828). The log says `Film view mode: ...`. | A cooked game refused `viewmode wireframe` (logged as set, every frame lit). |

`-SailingExecAt=<s>:<cmd>` now runs its commands through the player's console, so viewport commands (`viewmode`, `show`)
reach the viewport.

For a camera just above the water beside the hull, try `-SailingNoHullClip`: the water's drop inside the hull is worked
out per vertex, half a metre apart near the camera, so from 20 cm up the lee waterline showed a strip of hull below it.
The hull hides the water inside it from outside (it also turns off the waterline foam).

`camera.json` now records the real lens, `motion_blur` and `film_quality`.

## Shot files

A shot is one JSON file. Key times are seconds from the first recorded frame (under a fixed step this time is counted in
frames, so every run of a shot is the same). Before the first key the camera holds on it, and after the last key it holds there.

```json
{
  "frame": "boat",
  "path": "linear",
  "fov": 35,
  "keys": [
    { "t": 0, "orbit": [-100, 22, 1.8] },
    { "t": 6, "orbit": [-20, 24, 3], "fov": 32, "ease": "inout" }
  ]
}
```

- **`frame`** sets what the camera is placed against.
  - `boat` is metres forward, right and up from her, level, turning with her heading.
  - `world` is metres north, east and up from her start, with compass angles.
  - `mount` is metres forward, right and up in the hull's own frame, so the camera heels and pitches with her (a locked mount).
  - Heights in `boat` and `world` are above the still water.
- **Place:** `"pos": [x, y, z]` in that frame, or `"orbit": [bearing deg, distance m, height m]` round the boat. The orbit's bearing is off her bow in `boat` and a compass bearing in `world`. A mount can't orbit.
- **Look:** `"look": "boat"` (the default) aims at her, `"aim_up": <m>` high (a third of the masthead by default), and `"aim_offset": [pitch, yaw, roll]` frames her off centre. `"look": [pitch, yaw, roll]` is fixed in the frame.
- **Lens:** `"fov"` is the horizontal field of view, per key or once for the whole shot (40 by default).
- **Ease:** `"ease"` is `linear`, `in`, `out` or `inout` (the default), and applies to the move from that key to the next.
- **Path:** `"path": "smooth"` runs a Catmull-Rom curve through every key. The default moves in a straight line, except that two orbits go round her.

The moves the reel needs:

- **Orbit:** two `orbit` keys.
- **Dolly or crane:** two `pos` keys, closer or higher.
- **Pan:** one `pos` twice, with two `look` angles (`world` frame for a stand on the shore).
- **Locked mount:** `frame: mount` with one key.

## A run

From the PC (Development package, Ultra, 4K):

```
SailingSim.exe -benchmark -fps=60 -SailingBench=20 -SailingBenchWarmup=10 -SailingRecord=8 -SailingRecordInterval=0.0166667 -SailingFilm -SailingCapture=Path -SailingShotFile=reel/orbit-hero.json -SailingShot=orbit-hero -SailingNoGpuSlices -SailingShowCrew=0 -SailingTraffic=0 -SailingSeed=7 -SailingCinematic=1 ...
```

The frames land in `Saved/Bench/rec/` (`frame_0000.png` to `frame_0479.png`), and the log says `SailingRecord: 480 of
480 frames recorded`. Capture mode keeps the look neutral unless `-SailingCinematic=1` is given.
