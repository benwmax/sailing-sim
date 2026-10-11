# SailingSim: notes for Claude sessions

Unreal Engine 5.8.3 C++ project. Builds run on Bean's Mac (Apple M5 Pro, Xcode 27) at
`/Users/ben/myProjects/sailing-sim`. Engine at `/Users/Shared/Epic Games/UE_5.8` (override with `UE_ROOT`).

## The loop (run from the repo root)

1. `scripts/build.sh` compiles the editor target (all three modules). About 20 s incremental. Log: `Artifacts/build.log`.
2. `scripts/test.sh [Filter]` runs automation tests headless (`-nullrhi`), default filter `SailingSim`.
   Prints one line per test and exits non-zero on any failure. Report: `Artifacts/TestReport/index.json`; log `Artifacts/test.log`.
   Always rebuild first: the editor loads the dylibs in `Binaries/Mac`, it does not compile.
3. `scripts/make-map.sh` regenerates `Content/Maps/Lake.umap` from `scripts/make_lake_map.py`. Edit the Python, not the map.
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
7. `DEMO=1 RECORD=15 scripts/bench-mac.sh 17` runs the packaged game with the autopilot tacking (`-SailingDemo`) and
   writes `Artifacts/recording.gif`. Recording drops the frame rate; measure fps without RECORD.

## Conventions

- Physics lives in `Source/SailingPhysics`: plain standard C++ (no Unreal headers, so it builds standalone) in
  namespace `Sailing`, SI units (meters, kg, seconds, radians), stepped at a fixed 120 Hz through `FFixedStepper`.
  `FBoatModel` is the J/22 (config in `FBoatConfig`), `FWindField` the wind, `FAutoTrim`/`FAutopilot` the crew helpers.
  `Quat` uses FQuat's algebra, so copy X/Y/Z/W straight across. Positive heel = starboard side up (heeled to port);
  positive yaw/rudder/tiller = bow to starboard; TWA/AWA positive = wind from starboard.
- Calibration knobs, if the polar drifts: residuary table and `ChopResistance` (hull), sail `InducedAspectRatio`,
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
