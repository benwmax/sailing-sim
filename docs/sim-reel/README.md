# Sim reel: offline renders of the showcase loops

The portfolio's `sim-reel` widget (benwmax/bmax-portfolio, `docs/side-projects/sim-reel.md`) plays five 6–10 s loops of
the sim: `wireframe`, `fleet`, `physics`, `storm`, `night`. This folder is how they're made, so every loop can be rendered
again from a command.

## Does Movie Render Queue step the sim correctly?

Yes. Movie Render Queue (MRQ) renders at a fixed frame rate: it ticks the engine with fixed deltas, one tick per
temporal sample. Everything the sim draws runs on those deltas.

**Physics.** Every boat steps at a fixed 120 Hz. Frame time goes into an accumulator (`FFixedStepper`), and whole steps
come out. The world clock (`FWorldClock`, owned by the game mode) runs the same way, and each boat steps until it reaches
that clock. So the boat behaves the same at any frame rate. The physics never reads the wall clock.

**Weather, wind, waves, traffic.** These all run on the sim clock. Their randomness is seeded and portable
(`FPortableRandom`, cell hashes in `Wind.cpp`). `-SailingSeed` is the weather seed, and the same seed always gives the
same storm.

**Materials and effects.** These read the game time (`GetWorld()->GetTimeSeconds()`): lightning flicker, stars, far
whitecaps' lives. Under MRQ, game time is exactly the sum of its fixed deltas.

**Workers.** Off-thread workers (the wave detail FFT, wake, weather map, sea and shelter maps, terrain chunks) are polled
when they finish. At MRQ's speeds (well under real time) they always finish within the frame, so a render sees each
result on the first frame it could arrive. A real-time run can see them a frame or two later. The wave detail is
evaluated at sim times and blended, and it waits when it falls behind.

**The wall clock** appears only in:
- profiling and log timers;
- the gallery's list debounce and compare timer (UI, not used by the reel);
- `OrderReaders`' once-a-second tick-order check (`BoatPhysicsTask.cpp`: it changes the tick order, not the results);
- the session date and time zone.

That last one matters: without `-SailingDate`, the date is today (sun, moon, tide), and the UTC offset is always the
machine's current one. The reel passes `-SailingDate=2026-06-20`. Render on a machine set to US Central time, which
both of Bean's machines are.

Three caveats:

1. **Temporal samples and the 120 Hz step.**
   - The boat moves in 1/120 s steps and isn't interpolated between them. At 30 fps with a 180° shutter, the shutter is
     open for 1/60 s: two physics steps. More temporal samples than that don't add positions for the boat.
   - The camera, water, clouds and particles are continuous, so extra temporal samples still smooth them.
   - At 4 temporal samples, the boat's blur is two images 1/120 s apart. That's about 2.5 cm at 6 kn, which you can't
     see at reel framing.
   - The engine's own motion blur (`ApplyReelLens`, 0.5 = 180°) covers the rest.
2. **Time-lapse is capped.** One tick may run at most 12 physics steps (0.1 s). Past that, the clock drops time, like a
   hitch. The world's dilation divided by the fps must stay at or under 0.1, which is 3× at 30 fps. Faster time-lapses
   render more frames and keep every n-th (`decimate` in `shots.json`). The storm loop runs at 3× and keeps every 8th
   frame: 24×.
   Under dilation the level sequence plays faster too, so the executor asks MRQ for frames × dilation sequence frames.
   That gives the right number of output frames.
3. **Before the render starts**, the game runs from launch at a fixed step (`-UseFixedTimeStep -FPS=<fps>`). The
   executor starts MRQ when the game clock reaches the shot's `start_s`, so every run starts from the same sim state.
   Asset loads still finish on the wall clock. A pass whose subject isn't loaded by `start_s` shows it popping in, so
   give a shot enough `start_s`.

Not everything visual is seeded:
- **AI boats' liveries** come from their object ids (`GetUniqueID`), which change from run to run. That includes the
  gallery's display boat: the first wireframe render had a different sail number in each pass. The gallery shots pin
  them with `-SailingLiverySeed=0`. In traffic shots, the AI boats' colours can change between runs, but their courses
  don't.
- **Film grain** (the cinematic look) is random per frame.

**MRQ's own game overrides.** MRQ adds them by default, and they switch scalability to Cinematic, which overrides the
tier's tuned settings (Lumen, clouds, water). The executor turns that off. The tier comes from the quality instead:
High for `check` and `preview`, Ultra for `master`.

Checked by rendering the same shot twice: see "Proof" below.

**So the approach is offline.** The game renders itself through MRQ, run from the editor binary (`-game`, uncooked
content: no packaging, no cook). A shot is just the game's own launch args, the same ones the benches and capture mode
use. No Take Recorder or Sequencer tracks are needed, and nothing is replayed: the run is deterministic, so
"re-recording" is simply running it again. `FReplay` (10 Hz, interpolated) would be coarser than the sim itself.

## How a shot is rendered

```bash
scripts/capture-reel.sh wireframe                    # preview: 1280x720, 1 spatial x 2 temporal samples, High, Mac
```

```bash
scripts/capture-reel.sh physics --quality check      # 640x360, 1 sample: a quick look, about 1.5 min a pass
```

```bash
scripts/capture-reel.sh wireframe --quality master   # 4K, 4 x 4 samples, Ultra: the PC
```

```powershell
scripts\windows\capture-reel.ps1 wireframe            # master by default on the PC
```

For each pass of the shot (`Tools/reel/shots.json`), `Tools/reel/capture_reel.py`:
1. Writes a job file and starts the game with:
   - the shot's args;
   - `-SailingReel -SailingCinematic=1 -SailingNoHud -SailingSeed=7 -SailingDate=2026-06-20`;
   - the reel executor.
2. The executor (`Content/Python/sailing_reel_executor.py`, a `MoviePipelinePythonHostExecutor` registered by
   `Content/Python/init_unreal.py`) builds the MRQ job in memory: frame range and rate, resolution, samples, warm-up,
   and a PNG sequence. Its only asset is the empty `/Game/Reel/LS_Reel` (`scripts/make_reel_sequence.py`; MRQ needs a
   sequence to time the render, and the camera is the game's).
3. Frames land in `Artifacts/reel/<shot>/<quality>/passes/<pass>/`, with `job.json`, `done.json`, the game's log and,
   for capture shots, the run's `telemetry.csv`.

Then `Tools/reel/compose.py` joins the passes into the loop (`loop/`):
- **wipe**: Wireframe, Lit+Wire, then Lit, each wiping over the last along a slanted edge with a wire-blue line.
- **cuts**: one boat after another.
- **single**: one pass, with the `physics` loop's overlay drawn from that run's own telemetry. No faked HUD.

It then dissolves the extra `tail` seconds over the head, so the last frame flows into the first.

ffmpeg writes:

| File | What |
|---|---|
| `master.mov` | ProRes 422 HQ at full resolution: the longer reel cuts from these |
| `<shot>.mp4`, `<shot>.webm`, `<shot>.jpg` | The portfolio's own encode settings (1280 wide, 30 fps, no audio) |
| `meta.json` | Args, commit, machine, render times, `"render": "offline"` |

Other options:
- `--passes a,b` re-renders some passes and keeps the rest.
- `--compose-only` recomposes and re-encodes without rendering.
- `--dry-run` prints the game commands.

The script holds the Mac lock (`scripts/mac-lock.sh`) while it renders.

### The reel's look (`-SailingReel`)

This is the opposite of capture mode's reference settings, which are untouched without `-SailingReel`.

| Setting | Where |
|---|---|
| The cinematic grade: `T_CinematicLUT`, tone curve, bloom, vignette, grain | `-SailingCinematic=1` (docs/graphics-8/cinematic) |
| Depth of field focused on the subject, f/4 or `-SailingReelFstop`, full-frame sensor | `ApplyReelLens` (`VisualPipeline.h`) |
| Motion blur at a 180° shutter | `ApplyReelLens` |

It's applied every frame in capture mode (focus on the boat) and on the gallery stage (focus on the asset). Capture
mode's exposure lock stays: no exposure pumping in a loop.

The brief also named `MI_World_Trailer`. That's the paint on the world kit's road trailer (`build_props.py`), not part of
any look, so the reel leaves it out.

### Gallery additions for the reel

These only apply with `-SailingReel`:
- `-SailingGallerySpin=<deg/s>` spins from the first frame (no 4 s idle wait or ease).
- `-SailingGalleryOrbit=<pitch deg>,<zoom>` sets the hero angle (zoom 2 is twice as close).
- `-SailingGalleryWarm=<from>,<to>` warms the studio over those game seconds after the stage opens: the key light drops
  from 35° to 12° and goes from 6500 K to 3200 K, the fill cools to 9500 K, the rim burns at 2900 K.
- Wireframe on a whole boat is the wire alone. Outside the reel it stays an overlay, as before. The view is re-applied
  each tick, because the sails, rig lines and crew take their materials after the boat appears. The boat's own materials
  come back for the other views.
- The wire glows (`-SailingGalleryWireGlow=<x>`, 12): at the material's own emissive of 1, it read black against the
  studio's metered exposure.
- The stage fills the screen (no panel offset).

## The five shots

| Shot | Command | Passes | Notes |
|---|---|---|---|
| `wireframe` | `scripts/capture-reel.sh wireframe` | wire, litwire, lit | J/22 on the studio stage, 8°/s, pitch -8°, zoom 1.25, warming 3–10 s, wipes at 2.5 s and 5.5 s |
| `fleet` | `scripts/capture-reel.sh fleet` | the 8 boats (`Boat:0`–`Boat:7`) | Gallery whole-boat view at golden hour on the lake, 1.1 s each |
| `physics` | `scripts/capture-reel.sh physics` | chase | J/22 tacking (`-SailingDemo`) in 14 kn, capture mode Chase, telemetry overlay |
| `storm` | `scripts/capture-reel.sh storm` | front | Thunderstorm, seed 7, ShoreTele, 3× dilation keeping every 8th frame (24×) |
| `night` | `scripts/capture-reel.sh night` | channel | Galveston at 20:36, traffic 2 and near, drone framing the nearest tanker (`-SailingCamVessel=3,...`) |

Add `--quality master` for the 4K masters on the PC.

The camera angles, times and conditions in `shots.json` are first guesses, not chosen hero angles. Try a framing
quickly with `scripts/run-game.sh 10 <the shot's args>`, then set it in `shots.json`.

## Mac or PC

| Step | Where |
|---|---|
| Building the pipeline, previews (720p), checking a framing | Mac |
| 4K masters (`--quality master`: 4 × 4 samples, 16 renders a frame) | Windows 4090 PC. On the Mac, a 10 s 4K loop would take hours a pass. |
| Grooms as strands, Ultra-only effects (crew falls, FFT bloom) | PC only: the Mac draws hair cards |

The PC needs the commit, `scripts\windows\build.ps1`, ffmpeg (`winget install ffmpeg`), and a venv with numpy and
Pillow (`Tools\venv`).

## Proof

All on Bean's Mac (M5 Pro), Oct 30 2026, main at 16a0835b plus this branch.

**Repeatable physics.** `scripts/capture-reel.sh physics --quality check` ran twice:
- The run covered a 20 s pre-roll, then 315 frames of a J/22 tacking in 14 kn (heading 130° to 236°, heel up to 15.5°).
- Both runs wrote byte-identical `telemetry.csv` files: every row, time column included, 931 rows.
- Pixels differed by 0.5/255 on average (at most 1.1/255 in a frame): the film grain and Lumen's noise.

**The test shot: `wireframe` at preview quality** (1280×720, High, 1 spatial × 2 temporal samples, 9 s loop + 1 s
tail).
- Three passes of 300 frames each: 50, 58 and 56 s, including the editor's start-up (about 25 s). That's about 0.1 s a
  frame of rendering.
- Composing and encoding added 45 s, for **210 s in all**.
- The master lands at `Artifacts/reel/wireframe/preview/master.mov` (ProRes 422 HQ, 125 MB), beside `wireframe.mp4`
  (0.55 MB), `wireframe.webm`, `wireframe.jpg` and `meta.json`. The frames are in `loop/` and `passes/<pass>/`.

**Every other shot ran at `check` quality:**
- `physics`: 315 frames, 1.5 min.
- `storm`: 2640 frames rendered for 330 kept, 2.2 min. The burst knocks the J/22 flat.
- `night`: 330 frames, 1.3 min.
- `fleet`: 8 × 273 frames, 13 min. One pass took 7.8 min compiling the ILCA's shaders the first time.

**A master estimate.** The 4K master is 16 renders a frame at 9× the pixels, on Ultra. At the Mac's preview rate that's
over an hour a pass, hence the PC. On the 4090, expect a few seconds a frame: 10–20 minutes a pass. That's not measured
yet.

## Still open

- Hero angles, times and conditions for each shot (Ben). The `shots.json` values are first guesses:
  - the fleet's lake framing follows each boat's heading;
  - night at 20:36 in June is still dusk;
  - the storm's shore tripod has the near bank across the bottom of the frame.
- The MetaHuman crew stay grey in the wire-only pass: the wire material doesn't take on the skinned bodies and grooms.
- The PC masters: `scripts\windows\capture-reel.ps1 <shot>`. It needs ffmpeg and the venv with numpy and Pillow.
- Bean's OK before any of Bean's motion capture appears. The idles are CMU clips, but crew-2's capture solves are
  Bean's.
- Label each clip honestly in the portfolio (`render: "offline"`, as `meta.json` says).
