# Recording the five loops on the PC

The footage is recorded on the Windows 4090 PC. It has the better graphics: the Ultra tier, hair strands, crew falls
and the FFT bloom. Renders on the Mac are smoke tests of the pipeline only. How the pipeline works and why it is
offline: [README.md](README.md).

Run everything in PowerShell from the repo root (`D:\dev\sailing-sim` or wherever the PC's checkout is).

## Once

1. **Get the code:** `git pull`, then `git lfs pull`.
2. **Build:**

   ```powershell
   scripts\windows\build.ps1
   ```

   `build-windows.bat` does this too, along with the crew zip.
3. **Python with numpy and Pillow:**

   ```powershell
   py -m pip install numpy pillow
   ```

   If several Pythons are installed, point the script at one: `$env:PYTHON = 'C:\...\python.exe'`.
4. **ffmpeg:**

   ```powershell
   winget install Gyan.FFmpeg
   ```

   Then open a new PowerShell so it's on the PATH.
5. **Check:**

   ```powershell
   scripts\windows\capture-reel.ps1 -Preflight
   ```

   It should say `Ready.`. A warning about the MetaHuman crew means the boats will sail with the stand-in crew: unzip
   the crew zip first (`build-windows.bat` does).

## Each shot: a draft, then the master

For every shot, the same three steps:

1. **Draft:** `scripts\windows\capture-reel.ps1 -Shot <shot> -Quality draft`
   - 1080p, Ultra, 2 samples a frame: a quick look at the framing.
   - Watch `Artifacts\reel\<shot>\draft\<shot>.mp4`.
2. **Adjust** the shot's args in `Tools\reel\shots.json` until the draft looks right (the knobs for each shot are below).
   Drafts are cheap: run as many as it takes.
3. **Master:** `scripts\windows\capture-reel.ps1 -Shot <shot>`
   - 4K, Ultra, 4 × 4 samples (the storm uses 4 × 1).
   - The result goes to `Artifacts\reel\<shot>\master\`.

A render opens a game window and closes it at the end; leave the PC alone while it runs. The first render after a
build compiles shaders and can take several extra minutes. Render times on the 4090 haven't been measured yet;
`meta.json` records them.

### 1. `wireframe`: the J/22 on the gallery stage

```powershell
scripts\windows\capture-reel.ps1 -Shot wireframe -Quality draft
```

```powershell
scripts\windows\capture-reel.ps1 -Shot wireframe
```

- **Three passes:** wire, litwire and lit, the same motion each time. They are wiped together at 2.5 s and 5.5 s.
- **What to check:**
  - The masthead stays in frame.
  - The wipe crosses the boat, not empty floor.
  - The light is golden by the end.
- **Knobs:**
  - `-SailingGalleryOrbit=<pitch>,<zoom>`: -8, 1.25 now.
  - `-SailingGallerySpin=<deg/s>`: 8.
  - `-SailingGalleryWarm=<from s>,<to s>`: 3, 10.
  - `-SailingReelFstop`: 5.6.
  - `compose.at`: the wipe times.
  - `-SailingGalleryWireGlow`: 12; the wire's brightness.
- **Known gap:** the crew stay grey in the wire pass.

### 2. `fleet`: all eight boats

```powershell
scripts\windows\capture-reel.ps1 -Shot fleet -Quality draft
```

```powershell
scripts\windows\capture-reel.ps1 -Shot fleet
```

- **Eight passes**, one boat each, cut together at 1.1 s with a short crossfade.
- **What to check:** each boat is framed alike.
- **Knobs:**
  - `-SailingGalleryLight`: `GoldenHour` now, on the lake, where the camera follows each boat's heading. `Studio`
    gives identical framing for every boat.
  - `-SailingGalleryOrbit`.
  - `compose.each_s`.

### 3. `physics`: a tack, with real telemetry

```powershell
scripts\windows\capture-reel.ps1 -Shot physics -Quality draft
```

```powershell
scripts\windows\capture-reel.ps1 -Shot physics
```

- **The shot:** capture mode's chase camera on the J/22 tacking (`-SailingDemo`) in 14 kn. The heel, speed and wind
  numbers are drawn from that run's own `telemetry.csv`.
- **What to check:** the tack happens inside the 10 s, and the overlay is readable.
- **Knobs:**
  - `start_s`: when the loop starts. 20 s now; move it so the tack lands mid-loop.
  - `-SailingCaptureBearing`, `-SailingWind`, `-SailingTWA`, `-SailingHour`.
  - For the Hobie flying a hull: `-SailingBoat=Hobie16` and about 16 kn on a reach (`-SailingTWA=100`), without
    `-SailingDemo` tacking. Try it in a draft.

### 4. `storm`: the gust front, time-lapsed

```powershell
scripts\windows\capture-reel.ps1 -Shot storm -Quality draft
```

```powershell
scripts\windows\capture-reel.ps1 -Shot storm
```

- **The shot:** the thunderstorm preset on seed 7, seen from the shore tripod. The world runs at 3× and every 8th frame
  is kept: 24×. It renders 2640 frames to keep 330, so it's the longest render.
- **What to check:**
  - The front, the whitecaps and the rain all happen within the loop.
  - The near bank across the bottom of the frame: currently in shot, probably unwanted.
- **Knobs:**
  - `-SailingWeatherTime`: how far into the storm the loop starts.
  - `start_s`.
  - `-SailingCaptureBearing=<deg>`, or `-SailingCapture=Drone` for a different angle.
  - `decimate`: 8 now; higher is a faster time-lapse.
  - `-SailingNoLightning`: leave it off; the lightning is part of the shot.

### 5. `night`: Galveston's ship channel

```powershell
scripts\windows\capture-reel.ps1 -Shot night -Quality draft
```

```powershell
scripts\windows\capture-reel.ps1 -Shot night
```

- **The shot:** Galveston Bay with heavy traffic close by, the drone framing the nearest big ship
  (`-SailingCamVessel=3,140,60`: kind, distance in m, bearing from her bow).
- **What to check:** the buoys' flashes show, and the ship passes through the frame.
- **Knobs:**
  - `-SailingHour`: 20.6 is still dusk in June. Try 21.5 for full dark, or keep dusk for colour.
  - `-SailingCamVessel`.
  - `-SailingLightsOn`.

### All five at once

When the drafts are approved:

```powershell
scripts\windows\capture-reel.ps1 -Shot all
```

## What comes out

`Artifacts\reel\<shot>\master\` holds:

| File | What it is | Where it goes |
|---|---|---|
| `master.mov` | ProRes 422 HQ, 4K | Keep for the longer reel |
| `<shot>.mp4`, `<shot>.webm`, `<shot>.jpg` | 1280 wide, 30 fps, no audio, plus the poster | The portfolio's `public/sim/` |
| `meta.json` | Args, commit, render times, `"render": "offline"`, `"footage": true` | Kept with the clip |
| `loop\`, `passes\<pass>\` | The frames; each pass also has `game.log` | Delete when done: a 4K shot is several GB |

In the portfolio's `src/content/sim-reel.ts`, set `render: "offline"` for every clip.

## If something goes wrong

- **`Pass <name> failed: n/N frames`:** read `Artifacts\reel\<shot>\<quality>\passes\<name>\game.log`. Rerun only
  that pass with `-Passes <name>`; the others are kept and the loop is composed again.
- **A render hangs:** the script stops it after its timeout (15 min plus about a second a sample-frame). Close any
  `UnrealEditor` left running in Task Manager before the next one.
- **Changed only the composition** (wipe times, crossfade): `-ComposeOnly` re-joins and re-encodes without
  rendering.
- **See the exact game command:** `-DryRun` prints it, and you can paste it to run that pass by hand.

## Before publishing

- **Bean's motion capture:** as of this commit, the game never plays the crew-2 capture clips (nothing loads
  `/Game/Crew/Capture`). The crew move procedurally, plus CMU idles. If that changes, ask Bean before a clip with the
  crew goes public.
- **Reference clips:** no YouTube reference clips anywhere public. Use your own photos or credited Commons stills
  only.
