# SailingSim: notes for Claude sessions

Unreal Engine 5.8.3 C++ project. Builds run on Bean's Mac (Apple M5 Pro, Xcode 27) at
`/Users/ben/myProjects/sailing-sim`. Engine at `/Users/Shared/Epic Games/UE_5.8` (override with `UE_ROOT`).

## The loop (run from the repo root)

1. `scripts/build.sh` compiles the editor target (all three modules). About 20 s incremental. Log: `Artifacts/build.log`.
2. `scripts/test.sh [Filter]` runs automation tests headless (`-nullrhi`), default filter `SailingSim`.
   Prints one line per test and exits non-zero on any failure. Report: `Artifacts/TestReport/index.json`; log `Artifacts/test.log`.
   Always rebuild first: the editor loads the dylibs in `Binaries/Mac`, it does not compile.
3. `scripts/make-content.sh` regenerates `/Game/Materials` (`scripts/make_materials.py`) and `Content/Maps/Lake.umap`
   (`scripts/make_lake_map.py`). Edit the Python, not the assets. Run after `scripts/build.sh` (the map uses C++ classes).
   M_Water's wave sum must match `FWaveField::Height` (same 48 components; amplitudes pushed each frame by AWaterSurface).
4. `scripts/package-mac.sh [Development|Shipping]` runs RunUAT BuildCookRun (`-build -cook -stage -pak -iostore -package -archive`)
   to `Packaged/Mac/SailingSim.app`. About 2 min. Log: `Artifacts/package.log`. Keep `-package`: on Mac it is the step that copies
   the cooked data into the .app; without it the app crashes at startup looking for the .uproject. Never archive into `Build/`:
   that is Unreal's own platform folder.
5. `scripts/bench-mac.sh [seconds]` launches the packaged app windowed via `open` with `-SailingBench=<s>`: 3 s warm-up,
   measures frame times, writes `bench.json` and a screenshot, quits; copies both to `Artifacts/`. Needs an unlocked desktop.
   Started directly from a shell (not `open`), or fullscreen while the display is asleep, the game hangs at window creation.
   The app is sandboxed: its log and Saved folder live in `~/Library/Containers/com.benwmax.SailingSim/Data/Library/`.

`Artifacts/`, `Packaged/`, `Build/`, `Binaries/`, `Intermediate/`, `Saved/`, `DerivedDataCache/` are git-ignored.

6. `scripts/polar.sh [--quick | --scenarios | --point <tws> <twa>]` builds `Source/SailingPhysics` standalone with clang
   (no Unreal) and sails the J/22 reference polar in about 2 s. Use it for any physics tuning, then confirm with
   `scripts/test.sh` (`SailingSim.Physics.PolarGate`). `--scenarios` prints tack and irons results; `--point` dumps
   per-strip sail state.
8. `scripts/run-game.sh <s> [args]` runs the game uncooked from the editor binary (about 30 s, no packaging) and saves
   `Saved/Bench/<shot>.png`: the fast loop for visual tuning. Game args: `-SailingWeather=Thunderstorm -SailingHour=16
   -SailingWeatherTime=120 -SailingWind=8 -SailingTWA=90 -SailingHoldTWA=90 -SailingCamYaw=0 -SailingCamPitch=-10
   -SailingQuality=High -SailingShot=name -SailingDebugGust=1|2 -SailingDumpGust -SailingProfileGPU`.
9. `scripts/bench-phase2.sh [seconds]` measures three reference conditions on each quality tier (packaged build) and
   copies the High screenshots to `docs/phase-2/`. Leave the windows visible: macOS throttles hidden ones.
7. `DEMO=1 RECORD=15 scripts/bench-mac.sh 17` runs the packaged game with the autopilot tacking (`-SailingDemo`) and
   writes `Artifacts/recording.gif`. Recording drops the frame rate; measure fps without RECORD.

10. `scripts/bench-phase3.sh [seconds]` measures the lake views (marina on each tier, the I-30 bridge, a wide view,
   sailing) on the packaged build and copies screenshots to `docs/phase-3/`. More game args: `-SailingLaunch=N`,
   `-SailingStartAt=<north m>,<east m>,<heading deg>`, `-SailingDrill=LeavetheDock` (drill name without spaces),
   `-SailingLakeLevel=gauge|pool`, `-SailingCamDist=<m>`, `-SailingKeepStart`, `-SailingMenu`. Camera args work without
   `-SailingDemo`; the camera yaw is relative to the boat.
11. `Tools/venv/bin/python Tools/terrain/build_rayhubbard.py` rebakes `Content/TerrainData` from `Data/RayHubbard/raw`
   (git-ignored; see README). Then `scripts/test.sh SailingSim.Lake` and repackage (the data is staged as loose files).

12. `scripts/bench-phase4.sh [seconds]` runs every boat on the packaged build (fps, p99, build time) and copies
   screenshots to `docs/phase-4/`. Fleet args: `-SailingBoat=<name prefix>`, `-SailingSpinnaker`. Standalone polar for
   any boat: `scripts/polar.sh --boat hobie [--quick | --point <tws> <twa> [spin]]`.

13. `scripts/bench-phase5.sh [seconds]` runs Galveston Bay on the packaged build (day, open bay, night lights, dusk,
   chart view near and far) and copies screenshots to `docs/phase-5/`. Coast args: `-SailingWorld=1`
   (`-SailingDate=YYYY-MM-DD`), `-SailingChart=<m per px>`, `-SailingPlotFix`, `-SailingNoGps`, `-SailingLightsOn`,
   `-SailingNoMoon`. Rebake the coast with `Tools/coast/fetch_galveston.sh` then
   `Tools/venv/bin/python Tools/coast/build_galveston.py`, then `scripts/test.sh SailingSim.Coast`.

14. `scripts/traffic.sh [index]` builds SailingPhysics standalone and runs the Navigation Rules scenarios (each with
   and without the rules) and an AI race in seconds; `98` runs 16 races, `99` one race with its signals. Tune traffic
   here, then `scripts/test.sh SailingSim.Traffic` and `SailingSim.Race`. `scripts/bench-phase6.sh [seconds]` runs the
   traffic and race views on the packaged build (`docs/phase-6/`). Args: `-SailingTraffic=0|1|2`,
   `-SailingRace=<seconds to the start>`, `-SailingTrafficNear` (ships start close by).

15. `scripts/bench-phase7.sh [seconds] [--regression]` measures the Gulf views (sea, swell, dusk, entrance, chart), the
   logbook and the ghost on the packaged build and copies screenshots to `docs/phase-7/`; `--regression` then reruns
   bench-phase2..6 with `NO_DOCS=1` (their screenshots are not overwritten). Phase 7 args: `-SailingWorld=Gulf|2`,
   `-SailingSwell=<Hs m>`, `-SailingLogOpen`, `-SailingKeys`, `-SailingGhostAt=<s>`, `-SailingWatchAt=<s>`.
   Rebake the Gulf with `Tools/coast/fetch_gulf.sh` then `Tools/venv/bin/python Tools/coast/build_galveston.py gulf`.

15. Phase 8 reference realism (`docs/phase-8/`, method in `reference-kit/method.md`): `scripts/reference-checks.sh
   [--quick] [--csv]` runs the physics checks against real numbers standalone (heel, tacking, roll, waves, capsize,
   top speed, Portsmouth); `SailingSim.Physics.ReferenceChecks` runs the quick set and lists the known gaps.
   `scripts/capture-scenes.sh [seconds] [scene...]` reproduces `reference-scenes.csv` (or `SCENES=<csv> OUT=<dir>`)
   with the capture mode: `-SailingCapture=HelmEye|ActionCam|Chase|Drone|ShoreTele` (`-SailingCaptureBearing=<deg>`,
   `-SailingEV=<ev100>` or auto exposure frozen at 2.5 s; no HUD, blur or depth of field) writes `<shot>.png`,
   `.camera.json` and `.telemetry.csv`. More args: `-SailingWindFrom=<deg>`, `-SailingGust=<0..1>`,
   `-SailingReef=<n>`, `-SailingCrewKg=<kg>`. `scripts/bench-phase8.sh [seconds] [--regression]` is the gate bench.

## Conventions

- Physics lives in `Source/SailingPhysics`: plain standard C++ (no Unreal headers, so it builds standalone) in
  namespace `Sailing`, SI units (meters, kg, seconds, radians), stepped at a fixed 120 Hz through `FFixedStepper`.
  `FBoatModel` is the J/22 (config in `FBoatConfig`), `FWindField` the wind, `FAutoTrim`/`FAutopilot` the crew helpers.
  `Quat` uses FQuat's algebra, so copy X/Y/Z/W straight across. Positive heel = starboard side up (heeled to port);
  positive yaw/rudder/tiller = bow to starboard; TWA/AWA positive = wind from starboard.
- World systems: `FWaveField` (lake chop), `FWindField` (+ `FGustFront`), `FWeatherSystem` (presets, storm timeline,
  lightning) live in SailingPhysics; `ASailingGameMode` owns them and the clock (= the boat's physics time).
  `AWaterSurface` renders the waves and fills the cat's-paw and wake maps; `ASailingEnvironment` does sun, clouds,
  haze, rain and lightning; `USailingSynthWave` synthesizes all sound.
- The fleet: `FBoatConfig::Make(EBoatType)` in `Source/SailingPhysics/Private/Fleet.cpp` builds each boat (hulls,
  foils, sails, engines, crew) and `FleetReferencePolar` holds its reference polar with per-point tolerance. The J/22
  is `FBoatConfig`'s default constructor and must keep passing `SailingSim.Physics.PolarGate` unchanged. Calibrate a boat
  with `scripts/polar.sh --boat <name>`; knobs are the residuary table, wetted-area coefficient, windage, sail aspect
  ratios and foil sizes, each justified in a comment. The pawn builds visuals from the config (`RebuildBoatVisuals`).
- The lake: `FLakeTerrain` (height grid, tree canopy, fetch) and `FShelterMap` live in SailingPhysics; `FLakeData`
  (`LakeData.h`) loads the bake and builds dock/bridge obstacles; `ALakeTerrainActor` streams chunks; drills are
  `FDrillRunner` (`Drills.h`), pure logic so tests can drive them. Map frame: +X north, +Y east, origin at Rush
  Creek Yacht Club (32.8233 N, 96.5000 W), Z = 0 at the 435.5 ft pool.
- The coast: `FTideModel` (`Tides.h`, harmonic prediction with V from mean longitudes and nodal f/u; `TideExtremes`,
  `CurrentEvents`) and `FLightCharacter` (`Lights.h`, S-57 LITCHR/SIGGRP/SIGPER to rhythm and label) live in
  SailingPhysics. `FChartData`/`SailingChart` (`Chart.h`: the vector chart and Chart No. 1 symbology), `SailingNav`
  (`Navigation.h`: bearings, `PlotFix`, DR, `FPlot`) and `ANavaidsActor` live in SailingSim. Heights on the coast are
  meters above MLLW; the game mode moves the terrain actor by -tide and sets the physics level to match. Reference
  times from CO-OPS are GMT. `ASailingEnvironment::SunPosition` takes the local clock hour (longitude, UTC offset and
  equation of time make solar time).
- Traffic: `Rules.h` (right of way, risk by CPA, signals), `Traffic.h` (`FTrafficSim`: AI helmsmen, power vessels,
  collisions with who had to keep clear, routes and the ship channel path), `Race.h` (`FRaceRunner`: sequence, OCS,
  rounding by swept angle, scoring, AI tactics), `RulesCoach.h` and `TrafficScenarios.h` live in SailingPhysics.
  `ATrafficManager` spawns and steps it on the game clock; AI sailboats are `ASailboatPawn`s with `bTrafficBoat` (the
  simulation borrows their `FBoatModel`); `APowerVesselActor` draws the rest with lights over their arcs. Roles in an
  encounter are decided once and kept until past (`LastGiveWay`); don't let sailboats luff to avoid (they stall).
- Bake gotchas: read the DEM's georeferencing from its GeoTIFF tags (the export widens the requested box); OSM
  shoreline cells get symmetric heights so the zero contour lands on the OSM line; `FParse::Value` stops at commas
  unless you pass `false`.
- The ocean: `FOcean` (`Ocean.h`) is a Tessendorf FFT (two 64x64 cascades, 480 m and 60 m tiles) evaluated at 30 Hz
  and blended; `FWaveField::SetOcean` adds it to the chop, and `Bands()` feeds the boat's spectral added resistance.
  Its mask (open sea 1, sheltered 0) comes from a fetch march toward the swell plus a depth limit. `AWaterSurface`
  uploads the same grids (float textures) so M_Water's ocean term matches the physics. Debrief: `FReplay`
  (`Replay.h`, 10 Hz), `FLogbook` (`Logbook.h`); the ghost is a traffic-mode pawn with `bGhost` and M_Ghost.
- Gotchas found the hard way: wire vector parameters into Custom nodes via their RGBA output; runtime textures fed to
  a Color sampler must be sRGB (values gamma-encoded on the CPU); never call UpdateResource per frame; volumetric
  cloud shadows on the sun cost 4+ ms on this Mac (left off); the clouds' shadow rays toward a sun near the horizon
  cost a third of the frame at night, so `r.VolumetricCloud.Shadow.ViewRaySampleMaxCount` drops with sun elevation; the gust front is easiest to see from a low camera.
- Weather helm: `FBoatConfig::HeelYawCoef` (J/22 only; `Make()` resets J/22-only knobs for the other boats) and
  `FAutopilot::HelmPerHeel`. Tests that hold a course with a fixed tiller must steer with the autopilot now.
- Capsize state is by `Quat::Tilt()` (0..180), not heel: a turtled boat reads heel near 0.
- Calibration knobs, if the polar drifts: residuary table and `AddedResistanceCoef` (hull), sail `InducedAspectRatio`,
  keel/rudder area and `Center`. Don't tune to make a single test pass; check `--scenarios` too.
- Avoid identifiers that collide with Unreal macros in physics code (`PI`, `check`, `verify`).
- Unreal code converts cm <-> m at the edge (`Sailing::CmPerMeter`). Axes match Unreal: X forward, Y right (starboard), Z up.
- Input actions and the mapping context are built in code from `USailingInputSettings` (rebindable in Input.ini).
- Every physics change gets an automation test in `Source/SailingSimTests` (`SailingSim.Physics.*`). Game/world checks go
  under `SailingSim.Smoke.*`. Tests that tick a world must `++GFrameCounter` each frame.
- Binary assets go through Git LFS (`.gitattributes`). Prefer generating content from scripts so diffs stay reviewable.
- Warnings are errors in this toolchain (for example `-Wunreachable-code-loop-increment`); `TestEqual` needs matching
  double/float argument types.

## Git

- `origin` is `github.com/benwmax/sailing-sim`. Push as the `benwmax` GitHub account (the Mac's gh CLI also has
  `Benrebelling` logged in, which only has read access).
- One branch and pull request per phase (`phase-0`, `phase-1`, ...). Do not touch `benwmax/sailing-study` (the web sim).
