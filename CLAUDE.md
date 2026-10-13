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
  picks a class's meshes (only the J/22 so far); the rig lines, traveler car, mast bend and wet line are in
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
  (`fleet`, `berthed` args) imports. `SailingSim.Visual.FleetMesh` holds each to its physics hulls (the Hobie, Corsair
  and Lagoon configs' published beam/LOA disagree with their own hull shapes: reported, open). The rig is drawn only
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
  Medium 60 and High 45; Ultra is only checked to run on the Mac. Windows: package with `RunUAT BuildCookRun -platform=Win64`
  (not scripted yet).
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
- Water in the cockpit: `M_WaterV4` drops its surface 2 m inside the player's hull plan (`HullClipA/B/C`, set by
  `AWaterSurface::UpdateHullClip`; off for catamarans), so low-freeboard cockpits don't fill with the drawn sea.
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
