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
   M_WaterV4 (Medium and High) draws exactly the first 24 (`AWaterSurface::LongComponents`, under `SplitHz`, the edge of
   FWaveField's eighth band) and the rest from `FWaveDetail`; `SailingSim.Visual.WaveMatch` mirrors its vertex formula.
4. `scripts/package-mac.sh [Development|Shipping]` runs RunUAT BuildCookRun (`-build -cook -stage -pak -iostore -package -archive`)
   to `Packaged/Mac/SailingSim.app`. About 1.5 min (the cook is incremental and the game build is skipped when the code
   is unchanged; `FULL=1` recooks and rebuilds everything, 2.3 min: docs/bench-fast). Log: `Artifacts/package.log`. Keep `-package`: on Mac it is the step that copies
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

16. Visual phases (plan: the Claude Doc "Sailing Game: Visual Realism Plan"; `docs/visual-N/`). `scripts/bench-visual.sh
   [seconds] [label] [tiers...]` runs eight views on each tier of the packaged build with GPU time per budget slice
   (`DOCS=<dir>` keeps the screenshots). Every bench.json now has a `gpu` object (base, lumen, water, clouds_fog,
   niagara, post, other: three `ProfileGPU` frames after the measured window, parsed by `GpuSlices.h`; skip with
   `-SailingNoGpuSlices`) and the bench-phase CSVs carry those columns. Tier pipeline: `VisualPipeline.h`
   (`QualityCVars`, `CameraEV100`). Measuring args: `-SailingAA=<0|2 TAA|4 TSR|5 SMAA>`, `-SailingScreenPct=<n>`,
   `-SailingLumenHW=0|1`, `-SailingGI=<scalability level>`. `scripts/make_before_after_page.py <phase>` builds the
   before/after compare page from `docs/<phase>/compare/scores.csv`.

17. Boat models (Visual V2): `scripts/make-boat-models.sh` exports the physics geometry (`Tools/BoatExport`, standalone
   C++), builds the model in Blender headless (`Tools/blender/build_j22.py`; `brew install --cask blender`) and imports
   it into `/Game/Boats/J22` with Nanite, the `MI_Boat_*` materials and the rig sockets (`scripts/import_boats.py`).
   Run `scripts/make-content.sh` first (it builds `M_BoatSurface`, `M_BoatMast`, the `MI_Boat_*` library and
   `MPC_Boat`). Edit the Blender script, never the assets; `SailingSim.Visual.J22Mesh` holds the model to the physics
   (length, beam, draft, centre of buoyancy within 2 cm). The crew (`Tools/blender/build_crew.py`, `SK_Sailor`) is
   built and imported by the same script.

18. World kit (Visual V6): `scripts/make-world-models.sh` runs the Blender generators (`Tools/blender/build_trees.py`,
   `build_props.py` rocks and vehicles, `build_navaids.py`, `build_vessels.py`, `build_houses.py`, `build_landmarks.py`),
   imports them to `/Game/World/<Kind>` (`scripts/import_world.py`, slots to `MI_World_*` / `M_*` by name) and bakes the
   generated structures to Nanite tiles in `/Game/World/Baked` (`UWorldKitLibrary::BakeMarina/BakeBridges/BakeShore`).
   Rerun it after changing `WorldKit.cpp`, `MarinaActor::BuildGeometry` or `<Lake>.marina.json`; without a bake a tile
   falls back to a procedural mesh (fine on Medium, overflows VSM marking on High). Run `scripts/make-content.sh` first.

19. Windows (Bean's RTX 4090 PC; build, tests, package and Ultra bench run Oct 14 2026): `build-windows.bat` runs `scripts/windows/all.ps1` (checks, `git lfs pull`,
   MetaHuman zip, build, tests, package, warm-up and an Ultra bench). Single steps `scripts/windows/build.ps1`, `test.ps1`,
   `package-win.ps1` (to `Packaged/Windows/`), `bench-win.ps1`, `bench-visual-win.ps1` (keep its views in step with
   `bench-visual.sh`). `scripts/pack-metahumans.sh` zips the git-ignored crew on the Mac for the PC. Setup and what is
   untested: `docs/windows/README.md`. Keep new code MSVC-clean too, and run batch files through `cmd /s /c` (see
   `Invoke-Tool` in `scripts/windows/env.ps1`).
   Graphics G8 added the PC's own loop: `run-python.ps1 <script.py> [-Only fn,...]` (editor Python, e.g. make_materials.py),
   `run-game.ps1` (uncooked), `capture-scenes-win.ps1` (scene CSV on the packaged game). `M_WorldSurface` patterns 9
   (wood pilings) and 10 (dock boxes) are new and output a normal; keep `KitLook()` in step.
   Crew C2 on the PC: `capture-solve.ps1 [-TestClip tack_port]` runs the MetaHuman body solve (`Tools/capture/solve_clips.py`,
   full editor via `-ExecutePythonScript`) and `capture_clips.py`; see `docs/crew-2/README.md`. Editor scripts end by
   returning, never `os._exit` (it leaves zombie editors on Windows: `docs/windows/README.md`).

20. The gate (bench-fast, `docs/bench-fast/`): `scripts/gate.sh --scope clouds|water|boats|crew|world|night|ui|all
   [--baseline <csv>] [--merge <branch> ...]` builds, tests and packages only when their inputs' content hash changed
   (`Artifacts/gate/`), runs the heavy physics tests (`scripts/gate-heavy-tests.txt`) only when the physics, their five
   test files or the terrain changed (a change to the tests alone skips package and bench: `GAME_HASH`), then benches the scope's views on High (helm-eye always; slip and coast-day in the scopes that show
   them) plus the storm view on Medium, checks 60/45, and skips the bench when the packaged tree already passed that
   scope (`Artifacts/gate/bench-<scope>.hash`; `--force` reruns). A view under its floor in a scoped gate is benched again
   beside origin/main (`Artifacts/apps/main.app`, packaged in the worktree `Artifacts/main-tree` via `SAILING_ROOT` when
   main's game hash moved: `Artifacts/gate/main.hash`) and passes as flapping within 1 fps of main (`rerun_fps`,
   `main_fps` columns in `bench-<scope>.csv`; `--no-main-check` turns it off). `--scope all` is the full sweep, absolute:
   daily and before every blind round. `bench-visual.sh` takes `ONLY=a,b` and
   `BENCH_EXTRA=`; `FAST=1` runs several views per launch (`USailingBenchRunner`, `-SailingBenchList=<file in
   Saved/Bench>`), opt-in because the RHI thread can slow from view to view within one process (re-run alone
   by the guard). Args: `-SailingBenchTrace` (`<shot>.frames.csv`), `-SailingBenchWarmup=<s>` (keep 3 for gates).
   Command-line values cached in statics must use `SailingArgs::FCachedFlag`/`FOnce` (re-read when a list swaps it).

21. Licences (`docs/licences/`): Bean may sell the game, so only commercially usable assets, data and code (no NC/ND,
   no LAFAN1, Bandai or AMASS motion). Every file under `Content/` or `Audio/` needs a row in `docs/licences/assets.csv`
   (path glob, source, licence, commercial, conditions); `scripts/licence-check.sh` fails otherwise. Credit what the
   licence asks for in `CREDITS.md`. MetaHuman sources and exports are never redistributed outside the cooked game.

22. Boat kit (`Tools/boatkit/`, `docs/boatkit-1/`): shared hero fittings placed on each boat from
   `Tools/boatkit/layouts/<boat>.json`, plus per-boat character sheets (`characters/`, owner touches by seed).
   `scripts/make-boatkit.sh [--render]` builds the kit and dresses every boat (Blender or the `bpy` module, no Unreal).
   Photo match loop: `photomatch/solve_camera.py` solves a photo's camera from picked points, `dress_boat.py --camera
   --photo` renders from it and writes a compare image. Photos with people never enter the repo; only the picked
   pixel numbers do. Spread solve points in depth (`flatness` under 0.08 warns: points along the sheer leave the camera's
   height free); `photomatch/match_blend.py` renders any .blend from a solved camera. Phase 2 (`docs/boatkit-2/`): the
   hero builds kit parts with `kit_part` (`Winch16`, `JibTrack` on the cabin top; sockets kept as `sock_<Name>` props
   that `bake_j22_hero.py` reads), one chainplate a side, and the J/22's `MastX` is 0.65 (the class J, 8.8 ft) in the
   physics, the hero and `build_j22.py`: rerun `make-boat-models.sh` after it.
   Phase 3 (`docs/boatkit-3/`): the J/22's keel is the class template in both models (`keel_edges`; the physics keel
   `Center` stays a balance knob), the hero's aft freeboard is the ORC 0.568 m, its cabin face ends at 1.65.
   `photomatch/profile_match.py` lays the hero's outline over a broadside photo from two picked points (no camera solve).

23. Ports from a box and a name (`docs/world-marseille/`): `Tools/coast/worlds/<World>.json` defines a coast (box, origin,
   datum, harbours, spots, passage, climate, city glow, far ring); `build_coast.py <World>` bakes it (`build_galveston.py`
   is its old name). `"chart": "enc"` reads NOAA ENC (Galveston, Gulf: their rebakes are byte-identical); `"osm"` reads
   `fetch_world.py`'s downloads through `osm_chart.py` (OSM coastline and seamarks as S-57 rows, EMODnet depths, NGA Pub
   113 lights, Copernicus or IGN land). `build_piers.py <World>` and `build_houses.py <World>` fall back to OSM
   (`osm_harbour.py`: pontoons, breakwaters, boats stern-to) when there is no G2 pack. No SHOM products.

24. Far coast ring (Wide World Rendering PR 1, `docs/world-far/`): `scripts/make-far-ring.sh [World ...]` fetches the
   Copernicus GLO-90 tiles (`Tools/terrain/fetch_far_dem.sh` -> `Data/Far/raw`, or a world's own `Data/<World>/raw/far`),
   bakes `Content/TerrainData/<World>.far` (`Tools/terrain/build_far_ring.py`, bands in `Tools/terrain/far_ring.json` or a
   world bake's `far_ring.draw_km`) and its Nanite tiles in `/Game/World/Far` (`UWorldKitLibrary::BakeFarRing`). Rerun it
   after a world's grid changes (the ring takes the grid's heights inside it). `M_FarLand`'s WPO (`FAR_LAND_WPO`) is
   mirrored by `FarRing::OffsetZ`; `SailingSim.World.FarRing` holds both. `-SailingNoFarRing` compares.

25. Far lights (`docs/world-far-lights/`): `Tools/venv/bin/python -I Tools/terrain/build_far_lights.py [World ...]` writes
   `<World>.farlights.json` (lights from the world's navaids, neighbouring bakes and NGA Pub 113; lit-shore cells from
   the houses bake; city domes from the world json's `city_glow`; shipping lanes). `AFarLightsActor` draws lights past
   `NearPoolM` by `FFarLightMath` (Allard's law, geographic range, loom), the shore sprites and horizon ships (handed to
   `ATrafficManager::HandOffShip` at 8 km); `ANavaidsActor` keeps lights inside the near pool. `M_SkyDome` takes four
   domes (`GlowDomesA/B`). `-SailingNoFarLights` compares; `SailingSim.World.FarLights`.
26. World streaming (Wide World Rendering PR 2, `docs/world-streaming/`): a composed world (`Tools/coast/worlds/TexasCoast.json`,
   `"compose"`) is baked from other bakes by `Tools/coast/build_coast.py TexasCoast` (`compose_world.py`): `<World>.tiles`
   (6.4 km height tiles, `FTileIndex` in `WorldStream.h`), its own trees, json and chart; the frame member's houses, crowns,
   piers, current and kit tiles are read in place (`FLakeData::SourceFor`). `FWorldStreamer` (game) reads tiles on one
   worker around the boat; every world gets a tile index (whole grids: `FTileIndex::ForGrid`) and the terrain actor makes and
   drops its chunks by tile. Then `scripts/make-far-ring.sh TexasCoast`. Tests `SailingSim.World.Streaming.*`; bench view
   `stream-run` (`-SailingRun=<m/s>,<bearing>[,<turn after m>]` slides the world under the boat).
   Re-centre hitch (`docs/recentre-hitch/`): a world shift (and any move of an actor, like the tide's 2 cm steps) makes every
   instanced mesh recompute its bounds and resend all its instances to the distance-field and Lumen scenes. Big instanced
   sets on actors that move get `bAffectDistanceFieldLighting = false` where it doesn't show, `SetUseConservativeBounds(true)`
   and `SetCanEverAffectNavigation(false)`. Profile with `-trace=cpu,frame -statnamedevents -tracefile=<abs path>` and
   `UnrealInsights -NoUI -AutoQuit -ExecOnAnalysisCompleteCmd="@=<rsp>"` (`TimingInsights.ExportTimingEvents`).

25. Haze and far water (`docs/world-haze/`): `FHaze` (`Haze.h`: fog density for a visibility, clamped 0.5 to 80 km),
   `EWeatherPreset::ClearMistral` (60 km, cloudless NW), a world's `"haze"` (`fog_scale_height_m`, `far_plane_km`;
   `FLakeData::FogScaleHeightM`/`FarPlaneKm`). Band D: `Tools/venv/bin/python -I Tools/terrain/build_skyline.py
   Marseille` bakes `<World>.skyline` (500 m GLO-90); `FSkyline` marches it on a worker every 500 m into the sky dome's
   `Skyline` texture (`-SailingNoSkyline`). Tests `SailingSim.World.Haze`, `SailingSim.World.Skyline`.

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
- Rendering (Visual V1): Substrate is on project-wide; ray tracing is compiled in on demand (`r.RayTracing.Enable` is
  set per tier, only High uses it, for Lumen) and needs `r.SkinCache.CompileShaders=True` or the packaged game dies at
  startup. TSR is off (TAA at 67% on Medium, native TAA on High; this engine build has no MetalFX). High uses Lumen's
  High GI scalability, not Epic's (5.5 ms at native). Virtual shadow maps cost about 2 ms on Medium and 4 ms on High
  until the scene has Nanite meshes. Exposure on Medium and High follows the light (incident meter), not the frame;
  `kSceneEVOffset` in `VisualPipeline.cpp` ties real EV to the scene's 10-lux sun.
- Sails and crew (Visual V3): `FSailCloth` (`SailCloth.h`) builds each sail's grid from the physics strips (target shape)
  and runs a position-based cloth over it on Medium and High (flogging, leech flutter, luff wrinkles, spinnaker
  collapse); `M_SailCloth` draws seams, battens, insignia and number from its UVs (marks atlas from
  `scripts/make_sail_marks.py`). Telltale rules (`JibTelltaleState`, `LeechTelltaleState`) are shared with
  `SailingSim.Visual.Telltales`. The crew are `UPoseableMeshComponent`s posed by `CrewPose.h` (stances from the crew
  model, forward kinematics from the reference pose); their materials are set by slot name at runtime, and
  `M_BoatSurface` must keep `used_with_skeletal_mesh` or they fall back to the default material. MetaHuman Creator needs
  its optional content and Epic's cloud auto-rigging (not available headless here). `-SailingSpinnaker` survives the
  start resets; in shaders, clamp before `sqrt` (float `PI` times 1.0 is past pi).
- Water (Visual V4): Medium and High use `M_WaterV4` (Substrate Single Layer Water); Low keeps `M_Water`. The long
  waves' height, Gerstner displacement, slopes and Jacobian are computed per vertex in the WPO custom node (straight
  code, no branches: the vertex shader runs for every ring vertex) and interpolated to the pixels. `FWaveDetail`
  (`WaveDetail.h`, SailingPhysics) is the FFT of the same normalized JONSWAP for the short waves, evaluated off the
  game thread at 30 Hz, blended and uploaded as half-float mip-mapped textures (slopes plus squared slopes: LEAN
  roughness; sample with `Texture2DSample`, never `.Sample`, or the ray-tracing hit shaders fail). Foam where the
  Jacobian < `FoamThreshold` 0.6 (`SailingSim.Visual.Whitecaps` against Monahan). `FWakeGrid` (`WakeGrid.h`) solves the
  wave equation spectrally on a worker with each hull as a pressure patch (a truncated iWave kernel gives the wrong
  dispersion). Water bodies' albedo and extinction are in `WaterBodyFor`; the shore depth map is rebuilt on a worker;
  spray (High) is CPU droplets in an ISM. The terrain doesn't mesh the bed deeper than the water lets you see
  (`ALakeTerrainActor::HideBelow`): drawn behind SLW it cost 6 fps on High in shading and shadow pages.
  Measuring args: `-SailingClassicWater`, `-SailingWaterRings=N`; bench.json has `water_cpu_ms`.
- Sky (Visual V5): `FCloudSky` (`CloudSky.h`, in `FWeatherState::Sky`) holds the cloud layers per preset (cumulus,
  stratus, cirrus, storm), haze and the wind aloft; `FWeatherMap` paints them (plus the storm's lateral extent) around the
  camera in the clouds' drifting frame (world = field + Drift * T), on a worker every 2 s. `M_CloudLayers` (volumetric,
  Medium and High) reads it; `FStormShape` (shelf, rain core, anvil, distances from `FGustFront::DistanceAhead`) is
  mirrored in `make_materials.py` (`STORM`; `SailingSim.Visual.ShelfCloud`). The game mode keeps the front on the sim
  clock (pass sim time, not weather time) and the storm's timeline now starts at the boat's launch spot. Cirrus and the
  night sky are on `M_SkyDome` (an is-sky material: `SkyAtmosphereViewLuminance` plus the sun's limb-darkened disc,
  stars and the Milky Way rotated by sidereal time, the moon's phase); the moon light's own disc is off. The scene's sun
  follows `FWeatherMap::SunTransmittance` toward the sun; the clouds get the undimmed sun
  (`CloudScatteredLuminanceScale`). Volumetric fog thickens fast: its extinction scale is 0.12–0.3. Lens water is a
  post-process blendable on High outside the capture mode. Measuring: `-SailingClassicSky`, `-SailingCloudNoise=<path>`,
  `-SailingCamWorld=<n>,<e>,<up>,<heading>,<pitch>` (capture mode), `-SailingCaptureAbsolute` (compass bearing for the
  shore tripod).
- Boat models: below the waterline the J/22 model is the physics hull surface itself (`FHullShape` at the computed canoe
  depth), so a hull shape change in the physics means rerunning `make-boat-models.sh`. `ASailboatPawn::ModelMeshesFor`
  picks a class's meshes: the player's J/22 is the hero (`/Game/Boats/J22Hero`) since round 12, AI boats and the ghost
  keep `SM_J22_*` and their liveries (`-SailingClassicJ22` compares, `-SailingJ22Hero` puts the hero on AI boats too); a
  model that carries its own outboard sets `bOwnOutboard` (no stand-in box); the rig lines, traveler car, mast bend and wet line are in
  `BoatModelVisuals.cpp`. `MI_Boat_*` instances are updated in place, never deleted (the meshes reference them).
  `line` is a reserved word in HLSL custom nodes; Substrate's slab wants a tangent-space normal (the meshes carry
  box-projected UVs for their tangent frame).
- World (Visual V6): `FMarina` (`Marina.h`, `Content/TerrainData/RayHubbard.marina.json`: rows, slips, fingers, piers,
  breakwater, clubhouse; the home slip) is both physics obstacles and `AMarinaActor`; OSM docks and buildings inside it
  are dropped. `WorldKit.h`: generators write quads per look (`EKitLook`, which must match `WORLD_LIBRARY` in
  make_materials.py) plus light fixtures. `ABridgesActor` (bridges, shore riprap, a lake's piers, bridge traffic),
  `ALandmarksActor`, `ANightLightsActor` (pooled point lights; MegaLights on High via `r.MegaLights.EnableForProject`),
  house archetypes in `ALakeTerrainActor::PlaceHouseModels`. On a coast these follow the tide offset in 2 cm steps.
  Earth curvature: terrain and water materials offset by d^2/2R (R = 7/6 earth radius); trees and landmarks are placed
  with `CurvatureDrop`. Gotchas: `ObjectPositionWS` on instances is the bounds centre, not the pivot; `VertexNormalWS`
  was not world space on Nanite instances in a Custom node (use position derivatives); runtime-built components must be
  Static (or ShadowCacheInvalidationBehavior::Static) or VSM re-marks them every frame; the editor's Python crashes at
  shutdown after big bakes, so `import_world.py` ends with `os._exit(0)`; zsh does not word-split `$VAR` args.
- Fleet models (Visual V7): `Tools/blender/build_fleet.py` builds the other seven boats from `Tools/BoatExport` JSON (every
  hull, exactly the physics below the waterline; class decks, cabins, beams, nets, bridgedeck and rigs from `SPECS`),
  `build_berthed.py` the keelboats' in-slip dress for the marina; `make-boat-models.sh` runs them, `import_boats.py`
  (`fleet`, `berthed` args) imports. `SailingSim.Visual.FleetMesh` holds each to its physics hulls (and, since Graphics G3,
  each config's published LOA, less a fixed `Bowsprit`, and beam). The rig is drawn only
  where sockets exist; twin rudders use `RudderPivot_1`. Sail layouts per class are `Layout`/`BattenCount`/`FullBattens`
  on `M_SailCloth`. Marina neighbours are FMarina's `BoatType`/`Alongside` and are physics obstacles.
- Sound (Visual V7): `USailingSynthWave` layers (gust rumble, shelter hush, moored lapping and halyard slap, rain on
  deck and on water, squall hiss); `USailingWorldSynth` spatialised sources (`SailingSound::MakeWorldSound`: marina
  halyards, gulls, outboards, diesels); recorded samples in `Audio/Samples/<Cue>.wav` replace a synth voice
  (`scripts/import-audio.sh`, credits in `Audio/Samples/CREDITS.md`). Water below 2 kn goes glassy (`glass` in
  `M_WaterV4`). Cockpit view: `\` or `-SailingCockpit` (`UpdateCockpitCamera`); photo mode has depth of field and the
  V1 lens profile.
- MetaHuman crew (Visual V7): `scripts/make-metahumans.sh` builds the helm, trimmer and bow (presets Bruce, Ada, Omari)
  into `/Game/Crew/MetaHumans` in the full editor (git-ignored: about 0.5 GB, and the licence covers use, not
  redistribution). It needs the engine's MetaHuman optional content and an Epic sign-in for the cloud auto-rig (device
  code in the browser the first time); the editor has died on a Metal pipeline late in a run, so the script saves after
  each character and skips built ones. The player's boat uses them on Medium and High (`LoadMetaCrew`; SK_Sailor on Low,
  on AI boats and with `-SailingBlenderCrew`): `FCrewRig` (`CrewPose.h`) carries SK_Sailor's stance rotations to the
  MetaHuman skeleton (its +Y facing, A-pose turned to SK_Sailor's T-pose, spine/neck spread over its bones); face and
  outfit follow the body by leader pose; the life jacket and cap (`/Game/Crew/Gear`, `build_crew_gear.py`) are scaled
  from the skeleton. `SailingSim.Visual.MetaHumanCrew` checks every stance points each limb as SK_Sailor's does.
- Sky (Graphics G1): the cloud noise is ours (`Tools/clouds/make_cloud_noise.py` -> `/Game/Materials/Clouds`, imported by
  `scripts/import_cloud_noise.py`; `make-content.sh` bakes it when missing, `CLOUD_NOISE=1` rebakes). In `CLOUD_CODE`,
  nothing may vary faster than the march step (about 190 m: 80 samples over 15 km) or it aliases into grain: noise mips
  come from the sample footprint (floor 160 m), and the shelf has no altitude tiers. The weather map is 1024^2 (half
  floats). Cloud rendering per tier is in `QualityCVars` (upsampling mode 3 with clamped reprojection; Ultra traces at
  half resolution) and `ASailingEnvironment::BeginPlay` (sample scales, 4 km shadow rays). Measuring: `-SailingCloudScale=
  <view>,<shadow>`, `-SailingCloudShadowKm=<km>`, `-SailingCloudMode=<n>`, `-SailingCloudSamples=<n>`,
  `-SailingStormDelay=<s>` (the front reaches the start later), `SAILING_DEBUG_LAYERS=1 scripts/make-content.sh` (cloud
  layers tinted). CSV args with commas must be quoted.
- Ultra tier (Graphics G1): `ESailingQuality::Ultra`, for a desktop GPU (Bean's RTX 4090): everything High has plus Epic
  scalability, TSR at native, half-resolution clouds with the most samples, no resolution governor. The Mac gates stay
  Medium 60 and High 45; Ultra is only checked to run on the Mac, and the packaged Windows game starts on it
  (`USailingSettings` constructor).
- Boats and crew (Graphics G3): liveries come from `Inputs/g3/boat-catalogue.json` through `Tools/fleet/make_liveries.py`
  (generates `BoatLiveryData.inl`; edit the catalogue or the script, not the .inl). `SampleBoatLivery(type, seed)`: seed 0
  is the player's boat (commonest scheme, club wear, number 1288); AI boats seed from their unique id, marina neighbours
  from their slip; `-SailingLiverySeed=<n>` for stills. `M_BoatSurface` takes `Wear` (oxidation, scum, scuffs, rust) and
  `IsHull`, or per-instance custom data on the marina ISMs (0-3 wear, 4-6 hull colour). Sail numbers are composed in
  `M_SailCloth` from the digit strip in `T_SailMarks` (`SailNum`, `SailDigits`; `Marks` 1 insignia and number, 2 number).
  MetaHuman grooms (`LoadMetaHumanGrooms`, the HairStrands plugin) bind to the face: strands need `bSupportsHairStrandGeometry`,
  which on the Mac only METAL_SM6 has (this project is SM5), so the Mac draws cards; Windows High/Ultra get strands.
  `scripts/make-metahumans.sh` builds at High (`MH_QUALITY`); it reuses the source characters' cloud rig (`MH_RERIG=1` asks
  again; the request blocks on an Epic sign-in). `-SailingNoGrooms` measures without hair.
  Clothing is free and scripted (Bean's choice): the optimized MetaHuman body has no torso under the clothes, so
  `scripts/make-crew-clothes.sh` exports each outfit, tailors the polo from its T-shirt and deck shoes round its feet in Blender (`build_polo.py`, `build_shoes.py`: facings
  dropped, collar from a smooth neck ring, placket, buttons, rib cuffs, folds) and in Unreal copies the T-shirt's skin
  weights onto it with Geometry Script (`import_crew_clothes.py`, `SKM_<Role>_Polo`/`_Shoes`, git-ignored with the MetaHumans); shorts wear `MI_Crew_Shorts`.
  The pawn hides the outfit's shirt sections and adds the polo (`-SailingNoPolo` compares). `-SailingCamTarget=f,s,u`
  frames close stills; `-SailingNoHud` hides the HUD and engine messages outside the capture mode. Cloth: `M_CrewFabric` (`build_crew_fabric` in make_materials.py) puts the sailor's colour over CC0
  ambientCG scans (`Tools/fabrics/fetch_fabrics.sh` -> `Data/Fabrics/raw`, imported to `/Game/Crew/Fabric`): knit for
  the polo, polyester for the life jacket shell, woven cotton for the cap; normals fade past a few metres. Sampler types
  must match (`LINEAR_GRAYSCALE` for roughness) or the material falls back to the default checker.
- Shore (Graphics G2): `Tools/terrain/build_shore_detail.py` bakes the USGS 3DEP 1 m lidar DEM (`fetch_rayhubbard.sh` puts the
  2.6 GB of tiles in `Data/RayHubbard/raw/lidar`) into `RayHubbard.detail`: 64 m tiles of 1 m heights along the shore
  (land within 150 m of the water, water within 30 m), zlib-packed. The lidar is hydro-flattened on the water, so the bed
  there is the bathymetry under a shelf from the lidar shoreline; the band's edge fades into the 5 m grid. `FLakeTerrain::
  HeightAt` prefers the detail (physics and placement follow it); `ALakeTerrainActor` meshes shore chunks within 300 m at
  1 m (Step 0). Run it after `build_rayhubbard.py`; `-SailingNoShoreDetail` compares; `SailingSim.Lake.ShoreDetail` checks
  seams and agreement with the grid.
- Front end and HUD (Graphics G4): Slate in C++ (`Source/SailingSim/Private/UI/`), not Common UI assets. `SSailFrontEnd`
  (screen stack: Title, World, Launch, Boat, Conditions, Mode, Pause, ConditionsInGame, Settings, Controls, Confirm),
  `SSailLoading` (real readiness stages; waits for Enter unless Settings > Start when loaded), `SSailHud` (instruments,
  tips, drill/race panel, rules callout, coast navigation, minimap; text at 10 Hz), shared widgets `SailWidgets.h`, tokens
  and fonts `SailUIStyle.h`, data `SailCatalog.h` (spots and grids from the bakes, boats from the configs and polars).
  `USailSessionSubsystem` (`SailSession.h`) carries the choices over the map reload; the game mode applies them through
  the command-line override paths. Art: `Tools/ui/make_ui_art.py` (maps, label-free `T_MiniMap_<World>`, cards and
  loading stills from captures) then `scripts/import_ui_art.py` (`UI_ART_ONLY=<prefix>` reimports some). Args:
  `-SailingFrontEnd=<Screen|Loading>` (screenshots; Pause opens 4 s in), `-SailingUIScript=Down,Enter,Wait,...` (keys
  through Slate, survives the cast-off reload; `Log` prints the applied session), `-SailingNoHud`; `RESX`/`RESY` for
  `run-game.sh`. The front end is off for bench, capture, shot-only, demo, drill and automation runs; benches also ignore
  the player's resolution, frame cap and focus pause (`USailingSettings::IsMeasuring`). Pitfalls: no file-scope
  `using namespace` (unity build); `FSlateDrawElement::MakeBox` ignores the brush tint (multiply it in); never cache
  UObjects in statics (they dangle after the reload); keep brush textures alive with `SailUI::KeptTexture`; set focus
  from an active timer (not before layout). Test: `SailingSim.UI.SessionFlow`. The Credits screen parses CREDITS.md at
  runtime (`SailCatalog::Credits`; staged by `RuntimeDependencies` in `SailingSim.Build.cs`): edit CREDITS.md, not code.
- Save file (`docs/save/`): `FSailSave`/`SailSaveStore` (`SailSave.h`) keep the settings, last session and progress in
  `Saved/SaveGames/profile.json` (JSON, `version`, string ids only; the ini is version 0); new fields per the README; the mode is
  `settings.career.freeSail` and `lastSession.freeSail` (an older file's `openEverything` reads as it). UI stills at a size
  larger than the display's logical width need `-ForceRes` (`RESX=1920 RESY=1080 scripts/run-game.sh 6 -ForceRes ...`).
- Career (`docs/career/`): tiers, lessons, medal rules, checkrides and unlocks in `Content/Career/career.json` (`Tools/career/validate.py`); `Career.h`
  (plain) grades from `FDrillRunner` into the save's progress, `SailCareer::*` is the game's edge; locks are menu-only; `SailingSim.Career.*`.
  Two modes on the title (`docs/free-sail/`): Career, and Free Sail (`USailingSettings::bFreeSail`, `FSailSessionConfig::bFreeSail`,
  `-SailingFreeSail=0|1`): everything open, `FCareerProgress(..., bFreeSail)` records no medal, quiz or certificate; the logbook
  counts. It replaced Career 1's Open everything. The Sunfish is Club Racer's dinghy (its first boat; `SailingSim.Drills.SunfishLessons`).
- Geo anchor (`docs/geo-anchor/`): `FGeoAnchor` (`GeoAnchor.h`) is the bakes' tmerc exactly (pyproj to nanometres); persistent
  places go by id, then lat/lon (`ResolvePlacement`, the save's `launchSpotAt`); convert at the edge with `SailingNav::LatLonAt`/`MapAt`.
- Blind test and fixes (Graphics G5): `Tools/blindtest/fetch_commons.py search|pick <dir> <key> <query or Category:...>`
  fetches Commons photos (CC0/PD/BY/BY-SA only) with credits.json; `docs/graphics-5/blind/scenes.csv` holds the matched
  captures; `make_blind_pack.py` packs them; `make_g5_compare.py` builds the before/after page. The haze's inscattering
  follows the metered light (`HazeLight`, relative to a clear midday) and warms below 12 deg; exposure closes up to 2.5
  stops facing a sun under 20 deg; the fog's max opacity is 0.9 so the low sun shows (`-SailingClassicHaze` compares).
  Cirrus on `M_SkyDome` is stretched value noise, run only where the map has cirrus. `MATERIALS_ONLY=build_sky_dome,...`
  makes `make_materials.py` rebuild just those (otherwise every material is resaved). Two sessions sharing this checkout
  take turns on the GPU (builds, run-game, captures, benches) and stage explicit paths only.
- Fix round (Graphics G6, `docs/graphics-6/`): houses from the G2 footprints (`Tools/terrain/build_houses.py` ->
  `<World>.houses`, `HouseKit.cpp`, baked by `scripts/make-houses.sh` to `/Game/World/Baked/SM_Houses_*`); trees from the
  G2 lidar crowns (`Tools/terrain/build_crowns.py` -> `<World>.crowns`, `PlaceCrownTrees`) in three bands (leaf cards to
  250 m on High, shadowed opaque crowns to 1 km, unshadowed beyond: `-SailingNearTrees`, `-SailingMidTrees`,
  `-SailingFarTreeShadows=1`; `-SailingClassicTrees`/`-SailingClassicHouses` compare). A regroup moves only the trees crossing a band edge, and the mid and far crowns live in 4 km tile components (`TileComponent`, static, bounds scaled past `r.SceneCulling.MaxCellSize`): an ISM whose instance count changes is re-added whole to the distance-field and Lumen scenes, and a cullable tile costs scene culling every frame. Marina neighbours wear one of six
  `build_berthed.py` dresses (`SM_<Tag>_Berthed[_1..5]`); the player's keelboat wears dress 0 while tied up in her slip.
  The crew's vests are tailored over each polo (`Tools/blender/build_vest.py`, run by `make-crew-clothes.sh`; `PIECES=Vest`
  imports only them). `import_boats.py` takes `dress`, `gearonly`, `j22only`; `import_world.py` takes `ONLY=a,b`.
  Reference photos (faces, never commit): `Data/Reference/raw/j22-lessons`. Gotchas: a new BMesh face's normal is zero
  until `normal_update()`; Unreal's FBX import flips V; `env.sh` sets `-e` (a non-matching `grep` ends the script).
- Wiring (Graphics G7, `docs/graphics-7/`): learning content in `Content/Learning` (from `Inputs/drills`, staged loose;
  edit `Inputs/drills` and copy, then `python3 Inputs/drills/validate.py`): `FLearningContent`, `FLearningEvents` (the 63
  tip events), `FLearningCoach` (`Learning.h`); briefing and quiz are `ESailScreen::Briefing`/`Quiz`, opened by
  `ASailingHUD::WatchDrill` in learning mode (`-SailingDrill=<id> -SailingFrontEnd=Briefing|Quiz` for stills); a drill step
  change must keep `SailingSim.Drills.LearningContent` green. Sample pack: `scripts/import-audio.sh` imports
  `Inputs/audio/Samples` to `/Game/Audio/Pack` (`SailingSound::PackLoops`/`PackShots`, `USailingWorldSamples`). Coast piers:
  `Tools/venv/bin/python Tools/coast/build_piers.py` -> `GalvestonBay.piers` (`FLakeData::LoadPiers`: lidar decks, riprap,
  inferred `floating` walkways, `MooredBoats` drawn by `ACoastMarinasActor` via `SpawnBerthedBoats`), then
  `scripts/bake-shore.sh GalvestonBay`; `-SailingNoPiers`, `-SailingPiersSkip=decks,riprap,walkways,boats` compare.
  `FKitGeometry::SplitTiles` walks four vertices at a time: add triangles with `FKitSection::Tri` (a degenerate quad).
- Galveston 2 (`docs/galveston-2/`): the bay grid reaches 29.19 N (sim north -39,240) for the Gulf front pack
  (`Inputs/g2/gulf-front`), which `build_piers.py`, `build_houses.py` and `build_crowns.py` read beside the bay's. Moored
  boats need water deeper than their draft at MLLW (a marina basin: wet at MLLW); `SailingSim.Coast.MooredBoatsAfloat`.
- Crew (Graphics G8, `docs/graphics-8-crew/`): `FCrewHands` (`CrewPose.h`) puts the hands after the stance: Reach (two-bone
  IK from the shoulder, keeping the stance's elbow plane; the target is where the palm closes), Knee, and finger curl about
  axes from each rig's palm (`FCrewRig::CurlAxis`). `UpdateCrewFigures` gives the helm the tiller extension
  (`TillerEndCm`: the J/22's socket, or the config for the fleet's tillered boats) and the mainsheet, the trimmer the jib
  sheet's tail; the rig lines read `HelmGripCm`/`MainGripCm`/`JibGripCm` (keep every rig line drawn every frame: the mesh's
  vertex count is fixed). Grooms are held on their coarsest card LOD past 6 m (`UpdateCrewGroomLOD`: cards exist only at
  LODs 1 and 3, helmets at 5+ draw nothing). The vest is cut with bmesh bisect (`build_vest.py`), and the polo is imported
  with its torso under the vest cut away (`<Role>_PoloOpen.fbx`); keep closest-point weights for the vest (inpainting
  failed). `scripts/tune_crew_skin.py` turns on the faces' micro skin detail and pores (run by `make-crew-clothes.sh`
  after a MetaHuman rebuild). `scripts/pack-metahumans.sh` zips the git-ignored crew for the PC. Hide outfit sections by
  the asset's slot materials, never the component's (they are MIDs by then).
- Water W0 (`docs/w0/`): the cat's-paw map fades to `FWindField::MeanSurfaceRoughnessAt` over its outer 20% (no edge
  streaks); `WindParams` z is the sea's mean wind (puffs and caps read against it), w the water body's whitecap scale
  (`AWaterSurface::WhitecapScaleFor`: lake 0.4, bay 0.7, Gulf 1). M_WaterV4's cap threshold is mirrored by
  `AWaterSurface::WhitecapThreshold` (keep `CapSlope` in step with make_materials.py). `FWaveField::Update(Dt)` grows each
  band over `GrowthSeconds` (8 T^2, 5..300 s).
- Whitecaps (W8, `docs/water-8/whitecaps/`): caps fold on `FWaveDetail::JCap` (the chop's displacement blurred over
  `CapBlurMeters(wind)`: 0.36 m at 20 kn and up, U^0.85 below, so light-air caps are smaller; DetailA.a carries it), at
  a threshold the renderer solves each detail frame on the sea it draws (`FWaveDetail::CapThreshold`: long trains with
  the sea map at the camera and the mesh's fade at four vertex spacings, times the chop, `DrawnFoldScaleAt(wind)`: refit
  at 12, 16 and 20 kn in `docs/water-8/capshape-mac/`), to Monahan x `WhitecapScaleFor`; `FoamThresholdAt`/`CapSlopeAt`
  are the fallback and what `SailingSim.Visual.Whitecaps` holds. Far pixels read the fold table `DetailC` (mips average
  cover). `-SailingDebugFoam[=2|3]` draws the caps alone for counting; `-SailingDebugCaps` logs the solved thresholds.
- W3 prep (`docs/w3-prep/`): the growth laws take the adjusted wind U_A = 0.71 U^1.23 (`FWaveField::AdjustedWindSpeed`),
  steepened by (U / 18 kn)^0.43 above 18 kn to follow the SWAN bake (`GrowthStressWind`, `docs/physics-gaps/`);
  the lake's sea grows on `FLakeTerrain::EffectiveFetch` (Saville, nine rays over +/-45 deg; cached in the game mode).
  Polar, scenario and reference runs set `FWaveParams::bCalibrationSea` (the old law in U, the sea the fleet was
  calibrated in). `FShelterMap` builds the open-water speed-up and `GustAt` (gusts easing with fetch, W6's LES) from
  the same march; `FWindField::GustScaleAt` scales every fluctuation by it (1 without a map).
- Sea state by direction (W3, `docs/water-3/`): `FSeaFetch` (`SeaState.h`) is Saville's effective fetch for 16 wave
  directions on a 50 m grid (100 m bay, 200 m Gulf) plus depth, marched at load (~50 ms); `FSeaMap` holds, for the mean
  wind, a ratio per long component (its band's growth-law amplitude at its fetch / at the 15 km reference, times sqrt
  TMA) and one short-wave scale, rebuilt on a worker by the game mode (5% speed, 11.25 deg). A component's fetch is read
  along its direction pulled `kSeaTowardWind` (0.75) toward the wind. With a map, `FWaveField` grows toward the 15 km sea
  and `Height`/`Sample`/`SignificantHeightAt`/`BandsAt` scale by the map (boats' added resistance at their own position);
  without one (polars, references, `-SailingNoSeaMap`) nothing changes. `SetDepth` puts the components on omega^2 =
  g k tanh(kh) at the world's median depth before the renderer caches them. The atlas (`AWaterSurface::UpdateSeaMap`,
  packed on a worker) is seven RGBA half tiles: tile t channel c scales component 4t+c, tile 6 R the short waves;
  `SEA_ATLAS` in make_materials.py mirrors `FSeaMap::Sample` (keep them in step). `scripts/wave-check.sh --map` checks
  against SWAN (w3-swan-bake).
- Wind (W1, `docs/w1/`): `FWindField` is three seeded layers, each a function of place and time in a frame drifting with
  the air (`FDriftFrame`; `SetParamsAt` re-anchors at the boat when the wind turns): convective puffs (lattice along the
  surface wind, drifting with the wind aloft; since the W1 follow-up, kilometre cells from 12 seeded waves 2 to 5 km
  long carry `CellShare` of their variance and scale the streak puffs inside them), the Mann tile `Content/TerrainData/Wind.mann` (`Tools/wind/
  make_mann_slice.py`, loaded by the SailingPhysics module; standalone tools load it from the repo root), slow shifts.
  `WindClimate.h` holds the station calibration (`Tools/wind/fetch_wind.sh`, `fit_gusts.py`) and the stability inputs;
  the weather sets `GustIntensity` (fine, via `GustIntensityForFactor`) and `PuffIntensity` from it (`SetClimate`).
  `FShelterMap` = lee (terrain, canopy, houses, gone by 30 heights) x open-water build. AI reads `ReadableAt` (no fine
  turbulence) and tacks on headers. `Tools/wind/plot_field.sh` maps the field; `scripts/traffic.sh 98` races steady and
  shifty.
- Cloud fixes (W5a, `docs/w5a/`): cumulus are seeded cells in four size classes (power law, `FWeatherMap::Paint`;
  `Threshold` solves for the edge whose mean presence is the coverage); small cells take billows at twice the frequency.
  On Ultra `r.VolumetricCloud.DistanceToSampleMaxCount` is 3 km so near rays keep their samples (the per-step opacity cap
  is step-relative and stops binding); noise footprint floor 110 m (50 brought the frosting back). Cumulus are darkened
  by depth into the cell and its build, not altitude. The shelf face climbs in tiers (`FStormShape::TierX`, `ShelfTierM`,
  mirrored as `SHELF_TIER`). No rain density in `CLOUD_CODE`: `M_RainCurtain` draws it.
- Storm from the sunshine (W8, `docs/water-8/storm/`): the storm's gloom (`CloudDarkness`, `CloudCover`, visibility) is the
  boat's, from its distance ahead of the front (`FWeatherState::LocalizeStorm`, `FStormShape::Overhead`), not the clock;
  the anvil thins as the square of its reach and its ice dims the sun a third as much (`AnvilIceExtinction`); fair cumulus
  fade near the front (`CumulusFade`). The shelf's sloping face is lit by emission proportional to extinction (`SunLum`,
  `SunDir` from `UpdateSun`; the engine's cloud emission is luminance per metre) with its scattering cut: scattered light
  on a storm's skin is what the jittered march turns into grain. `-SailingNoLightning` for compared stills.
- Wind on the water (W2, `docs/water-2/`): `AWaterSurface` keeps two wrap-around wind maps (near 256^2 over 3.2 km,
  512^2 on Ultra; far 128^2 over 16 km; texel i at i mod Res, refreshed in strips): RGB = roughness, local direction
  (sRGB), A = slow wind (linear). `W2_WIND` in make_materials.py is the shared HLSL both water materials read (ripples
  turned to the local wind, glass, slicks, windrows); the trees bind the far map (`BindTreeWind`, `-SailingNoTreeWind`).
  Polarized glasses: `sailing.Polarized` or `-SailingPolarized`. bench.json has `windmap_cpu_ms`.
- Storms and real days (W5b, `docs/w5b/`): `Storm.h` holds `FMicroburst` (Vicroy 1991, NASA TM-104053), `FColdPool` (front
  speed 0.75 sqrt(g h dT/T) + 0.6 x the ambient wind along the track) and `FStormRain` (rain rate along the front's track,
  the rain foot slanting forward at the water). `FGustFront` carries the cold pool and burst; keep `DistanceAhead`'s
  meaning (the cloud material follows it). The game mode shifts `Front.StartTime`, `DecayStartTime`, `BurstStartTime` and
  `DayStartHour` onto the sim clock, and makes `WeatherState.Rain` the boat's local rain (`RainAt`). Rain curtains:
  `ASailingEnvironment::UpdateRainCurtains` + `M_RainCurtain` (`-SailingNoRainCurtains` compares). Real days:
  `FWeatherDay` (`WeatherDay.h`) loads `Content/TerrainData/Weather/<date>.wxday` (text header, then radar bytes);
  `FWeatherSystem::ConfigureDay` runs it, the preset's storm timeline shifted to the real arrival and stretched by
  `FStormSpec::TimeScale`. Bake with `Tools/weather/fetch_day.py <date> [--storm HH:MM-HH:MM]` then `bake_day.py`
  (`Tools/weather/requirements.txt`: eccodes); `plot_days.py` redraws the README's plots. `-SailingDay=YYYY-MM-DD` or the
  Conditions screen's Real day row (lake only). HRRR's grid doesn't resolve the lake: water temperature is W1's normal.
- Crew motion (C1, `docs/crew-1/`): each sailor is a `USkeletalMeshComponent` with `UCrewAnimInstance`, whose proxy runs
  `FAnimNode_CrewMotion` on the animation workers (`CrewAnimInstance.h`); the logic is `CrewMotion.h` (plain, for the tests):
  `CrewPlacement` (stance and place, shared with the tests; tacks timed to the boom: crossing low in the middle, facing
  forward), `FCrewBalance` (felt gravity `g - (a + alpha x r + omega x (omega x r))` at the seat after a 0.1-0.3 s lag,
  exact critically damped springs), `CrewMotionPose` (stance, trunk lean, breathing, slam give, brace, then the feet and
  hands IK from `CrewSolver.h`, then the head levelled and turned to the gaze). The physics exports `FBoatTelemetry::AccelBody`
  and `AngularAccelBody`. Attach points use the `J22H_sockets.json` names; without sockets `CrewDerivedAttachPoints` builds
  them from the geometry. AI crew tick at 15 Hz. The pawn hands each node `FCrewMotionInput` in `UpdateCrewFigures` (the
  mesh ticks after the pawn). Args: `-SailingCrewStill`, `-SailingDebugCrew`, `-SailingShotCrew=<name>`.
- Crew idles (C1b, `docs/crew-3/`): `CrewClips.h` plays CMU motion capture (`Tools/crew/clips.csv`, fetched by
  `Tools/crew/fetch_cmu.sh` into git-ignored `Data/CMU/raw`, baked by `Tools/venv/bin/python Tools/crew/bake_idles.py` into
  `CrewClipData.inl`: edit the CSV or the script, never the .inl) as joint motion about the stance, pre-multiplied before
  the reaction layer; head and neck become a gaze offset. Per-joint limits live in the bake (`JOINTS`) and are held by
  `SailingSim.Visual.CrewClipLimits`; the layer goes quiet for crossings, seat changes, bracing and ducking
  (`SailingSim.Visual.CrewClipTack`) and starts a clip's weight-shift onset against the heel's slow trend.
  `-SailingNoCrewClips` compares. CMU terms: in a sold product yes, resold as data no.
- Crew falls (C5, `docs/crew-5/`): `FCrewFalls` (`CrewFalls.h`, plain logic) throws the crew past 55 deg of heel,
  capsized or over 1 g, and brings them back once the boat is steady; `CrewFallsVisuals.cpp` makes the MetaHuman bodies
  active ragdolls with the Physics Control plugin (`CrewControl`; world-space controls relative to `CrewDeck`, a
  kinematic box under the sheer), with buoyancy from `FWaveField::Height`. Posed, their bodies have no collision and the
  controls don't tick (`SetCrewPhysicsActive`): keep it that way, it cost 1.6 ms otherwise. Ultra by default;
  `-SailingCrewFalls=0|1`, `-SailingKnockdownAt=<s>[,<deg>]`. Test: `SailingSim.Visual.CrewFalls`.
- Crew capture (C2, `docs/crew-2/`): MetaHuman Animator's markerless body solve (a Fab plugin, Windows) exports to
  `/Game/Crew/Capture/Solved/<clip>`; `Tools/capture/capture_clips.py` reads `Tools/capture/clips.csv` and saves
  `/Game/Crew/Capture/{Sailor,MetaHuman}/A_<label>` through `UCrewCaptureLibrary` (`CrewCapture.h`: each bone's
  component-space turn from the FCrewRig T-pose, carried between frames and onto the matching bones; the pelvis moves,
  the root stays). `CAPTURE_SYNTHETIC=1` makes stand-ins from the stances. `Content/Crew/Capture` is git-ignored.
  SK_Sailor's root bone is the armature ("Sailor") and carries the export scale: write each key's real scale.
- Gulf swell (`docs/gulf-swell/`): Galveston is an ocean world too (`"ocean": true`); `FOcean::BuildMask` is the share of
  the swell's +/-45 deg spread reaching a point in straight lines from the chart's deep (4 m+) edge, land on the 100 m grid
  from any 10 m node above water; the boat's added resistance and `SignificantHeightAt` follow the mask (mask^2 energy).
  `scripts/ocean-mask.sh [World]` maps it standalone; `-SailingNoOcean` compares; `SailingSim.Coast.GalvestonSwell`.
- Boat detail (boats 11, `docs/boats-11/`): the live rig lines carry UV0 (U = arc length over 5 diameters, 11 for wire;
  a seam column), tangents and a vertex colour whose red is the line's look (`RopeLook` in `BoatModelVisuals.cpp`, a
  column of `T_RopeColourways`, `Inputs/rope/colourways.json` order). `scripts/import_boat_detail.py` builds
  `M_RigRope`/`M_RigWire` and the close-up detail textures (`Tools/rope/make_rope_textures.py`,
  `Tools/boats/make_detail_textures.py`); run it before `import_j22_hero.py`. `-SailingFlatRope` keeps the old flat
  materials. The hero J/22 has a cabin (`SM_J22H_Interior`, player's boat only) and translucent `SM_J22H_Glass`.
  Boat fidelity 1 (`docs/boat-fidelity-1/`): `M_BoatSurface`'s `Surface` is each slot's kind in the shared library
  (`BOAT_SURFACE`; weathering by E1's Age/Care, box-projected detail maps on High/Ultra via `MPC_Boat.Detail`); `up` is
  judged on the side the camera sees (two-sided shells). Args `-SailingNoBoatDetail`, `-SailingBoatAge=<y>[,<care>]`,
  `-SailingDeckWet=<0..1>`; `HERO_MATERIALS_ONLY=1` rebuilds the hero's materials without reimporting.
- Water in the cockpit: `M_WaterV4` drops its surface to just under the player's hull bottom wherever it is inside
  a hull: `FHullClipMap` (`HullClip.h`) puts every hull's `FHullShape::BottomZ` (the maxi's sections too), sheer and
  deck-edge margins on a 256x128 grid in her frame, uploaded by `AWaterSurface::UpdateHullClip` once per boat and canoe
  depth (`HullClipMap`, `HullClipRect`; frame `HullClipA..D`), so catamarans, amas and the maxi are clipped and the water
  between hulls stays (`docs/water-hull-clip/`, `docs/boat-water-clip/`; `-SailingClassicHullClip` is V7's 2 m drop over
  the deck plan). Keep the shader's drop in step with `FHullClipMap::Drop` (`SailingSim.Visual.HullClip`).
- Dinghy handling: `DinghyEasePerHeelDeg`, `DinghySheetRate` and `CrewAftRange` (ILCA only so far) make `FAutoTrim` sail a
  dinghy flat with the sheet in the hand and sit back on the plane (`FBoatControls::CrewAft`); the dinghy sailor also eases
  on a puff itself (felt 0.4 s late, 20% over the last half minute's wind; physics-gaps), since hiked flat the heel hardly
  moves. Reference-check peaks are GPS-like one-second means.
- Easy mode (`docs/easy-mode/`): one switch (`USailingSettings::IsEasy`, `-SailingEasy=0|1`; off when measuring, capturing, in automation, traffic, ghost) applies `FEasyAssists` (`EasyAssists.h`: helm, heel cap, trim, no-go cue, `FEasyHelm` irons/bear-away on a copy of the controls); Realistic is the boat's own.
  Easy medals cap at career.json's `easy_max_medal` (`FCareerRun::bEasy`, save `medalEasy`); `scripts/polar.sh --easy`, `-SailingCrudeTackAt=<s>` (demo) for the gate runs.
- Prologue (`docs/prologue/`): scripted scenes are data (`Content/Prologue/prologue.json`, staged loose; `python3
  Tools/prologue/validate.py [--self-test]`) run by `Sailing::FScriptedScene` (`ScriptedScene.h`: triggers, captain calls,
  expected answers judged from telemetry and `FSceneInput`, repeats and crew takeover, never a hard fail; its own JSON
  reader). `-SailingPrologue=1` runs it on the stand-in (game mode `UpdateScene`, fed by the pawn; Space is the crew
  action, R restarts at the checkpoint); `SSailHud::RefreshScene` shows the caption; finished scenes go to the save's
  `progress.scenes`. SailingPhysics and SailingSimTests are `bUseUnity = false` (UBT unity-builds from 32 files).
  Crew stations (step 2): `FStationControls` (`CrewStation.h`) merges the player's station (helm = a wheel, jib trimmer
  = sheet and rate-limited grinder against the telemetry's sheet load, main trimmer = sheet, traveller, dump) with the
  crew's held controls each physics step (`FBoatStepJob::Stations`, `ASailboatPawn::UpdateStations`, only while a scene
  runs); steps name their `station`, expectations their `controls` (worked in order, `FSceneInput::Worked`). Grind,
  TravellerDump, Station and CrewAction are a key layer (`SailingBindings::SameLayer`) sharing buttons with boat
  commands the crew hold; `SailingSim.Prologue.Stations`.
- Prologue maxi (step 3, `docs/prologue/README.md`): `EBoatType::Maxi` is the PC's made-up 100 ft maxi; her hull is the
  exported sections (`FHullShape::Stations`, from `Tools/boats/maxi/sections.json` via `make_maxi_hull.py` ->
  `MaxiHullData.inl`; the formula's fields are only a stand-in fit for the water clip and BoatExport), fixed appendages
  float their own volume (`FBoatConfig::AppendageVolume`), reefs can change the jib (`ReefJibFraction`), a wheel has a
  rate (`WheelHardOverSeconds`). Estimated polar: `Tools/boats/maxi/estimate_polar.py`. `FSceneLimits` (EasyAssists.h)
  is the scene's cap and anti-broach, applied after Easy mode's while a scene runs. The prologue sails her on the
  Gulf's offshore spot (`setting.reefs`; `-SailingPrologueBoat=J22` is the stand-in); her hero model is
  `Tools/boats/maxi/build_maxi.py` (`import_boats.py maxi`, `/Game/Boats/Maxi`), on the Boat screen and the pause menu.
- Prologue gale (step 4, `docs/prologue/README.md`): `EWeatherPreset::Mistral` (32 kn gusting 40, 1.5 mm/h, a low fast
  deck, `FOceanParams::WindSeaHs`/`WindSeaTp` Hs 3.3 at 7 s on a 1.2 m sea with the wind: 3.5 m); its squall is an
  `FGustFront` with an `FSquallLine` (`FWeatherState::bSquall`: no storm layer, no lightning, no burst), cued by a step's
  `"weather"` (`squall` with `in_s`, `clearing`) through `FWeatherSystem::ApplySceneCue` on the sim clock; uncued it runs
  at `kSquallArrives`/`kSquallClears`. `setting.world_stand_in` turns the gale to the Gulf's open water
  (`SetPrevailingFrom`; from the northwest the ocean mask is shut). `-SailingPrologueStep=<id>` starts a scene partway.
  Known gaps: the maxi does not tack in that sea (`AddedResistanceCoef`) and nothing surfs (vertical buoyancy).
- Wave physics (`docs/wave-physics/`): added resistance is 2 m0 x R(lambda/LWL) (Jinkine & Ferdinande's fall past the
  peak) x Fn^1.5 to Fn 0.265; `AddedResistanceCoef` per boat (the J/22's 2.6 from her polar; the maxi's 0.47 and the
  Catalina 30's 1.57 from ORC's length scaling, VPP 2023 eq. 6.62). The waves' slope push (`WaveSlopeForceScale`) uses
  each column's immersion below her mean waterplane averaged over 8 s, so it stays first order (no drift from the chop at
  her ends). `FAutopilot` reverses the helm from 0.3 m/s of sternway. `SeaTrials.h` (`RunInSea`, `RunGaleTack`) and
  `scripts/polar.sh [--boat b] [--ar c] [--surf s] --sea [gale | checks | orc <hs> <tws> | at <tws> <twa>]` (loads
  `Wind.mann` as the module does). Telemetry: `CalmResistance`, `WaveResistance`, `WaveSlopeSurge`. Keels and rudders
  still meet still water (no orbital flow or wave inertia): a known gap.
- Weather helm: `FBoatConfig::HeelYawCoef` (the J/22's 0.06 and the maxi's 0.04; `Make()` resets the J/22's value for the other boats) and
  `FAutopilot::HelmPerHeel`. Tests that hold a course with a fixed tiller must steer with the autopilot now.
- Capsize state is by `Quat::Tilt()` (0..180), not heel: a turtled boat reads heel near 0.
- Calibration knobs, if the polar drifts: residuary table and `AddedResistanceCoef` (hull), sail `InducedAspectRatio`,
  keel/rudder area and `Center`. Don't tune to make a single test pass; check `--scenarios` too.
- Avoid identifiers that collide with Unreal macros in physics code (`PI`, `check`, `verify`).
- Unreal code converts cm <-> m at the edge (`Sailing::CmPerMeter`). Axes match Unreal: X forward, Y right (starboard), Z up.
- The render frame (world streaming, `SailingFrame.h`): the game mode moves the render origin (`UWorld::SetNewWorldOrigin`,
  on a 19.2 km lattice) when the boat is 20 km from it; the physics stays in the map frame. Map metres to Unreal and back
  only through `SailingFrame::ToWorld`/`ToMap`/`ToMapCm`/`FromMapCm`; world-space instance adds of map-frame transforms go
  through `ToWorldTransforms`; actors that build geometry in map coordinates spawn at `MapAnchor`. Materials see map-frame
  positions: `make_materials.py`'s `node()` adds `MPC_World.RenderOrigin` to every world, camera and object position.
  Workers read a copy of `FLakeTerrain` (it shares its heights), never `Lake->Terrain` (tiles are swapped under it).
- Input actions and the mapping context are built in code from `USailingInputSettings` (rebindable in Input.ini).
- Every physics change gets an automation test in `Source/SailingSimTests` (`SailingSim.Physics.*`). Game/world checks go
  under `SailingSim.Smoke.*`. Tests that tick a world must `++GFrameCounter` each frame.
- Binary assets go through Git LFS (`.gitattributes`). Prefer generating content from scripts so diffs stay reviewable.
- Warnings are errors in this toolchain (for example `-Wunreachable-code-loop-increment`); `TestEqual` needs matching
  double/float argument types.
- MSVC portability (the PC builds main on Windows): in a dllexport class declare one `static constexpr` per statement
  (`static constexpr double C1 = 1; static constexpr double C2 = 2;`, never comma-separated: C2487); no file-scope names
  that shadow engine template parameters (`Flags`); shadowing warnings C4458/C4459 are errors there.

## Git

- `origin` is `github.com/benwmax/sailing-sim`. Push as the `benwmax` GitHub account (the Mac's gh CLI also has
  `Benrebelling` logged in, which only has read access).
- One branch and pull request per phase (`phase-0`, `phase-1`, ...). Do not touch `benwmax/sailing-study` (the web sim).
