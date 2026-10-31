# Building on the Windows PC

Status (Oct 14 2026, first run on Bean's RTX 4090 PC): the editor build, the automation tests, the Win64 package and
the Ultra benchmark have all run. Fixes that run needed are in this branch (MSVC shadowing errors, the MetaHuman test
skipping when the crew is absent).

Nothing in the game is Mac-only: the physics in `Source/SailingPhysics` is standard C++, the rendering has two
`PLATFORM_MAC` switches (hair cards and the hair voxelization), and the content is committed through Git LFS.

## 1. Install (once)

| What | Notes |
| --- | --- |
| Windows 11, current NVIDIA driver | The game needs DirectX 12 (SM6). The RTX 4090 runs the Ultra tier. |
| Visual Studio 2022 (latest 17.x) or Visual Studio 2026 | Whichever the Unreal 5.8 release notes list as supported. Community edition is fine. In the installer pick the **Game development with C++** workload, and on its right-hand panel keep **MSVC (latest) C++ build tools**, a **Windows 11 SDK**, and **Unreal Engine installer** ticked. |
| Epic Games Launcher, then **Unreal Engine 5.8.3** | Library > Engine Versions > + > 5.8.3. Default folder `C:\Program Files\Epic Games\UE_5.8` (if you pick another, set `UE_ROOT`, below). In the engine's Options keep the **Windows** target platform; also tick **MetaHuman** content if you bring the crew over (step 3), as on the Mac. |
| Git for Windows | Its installer also sets up Git Credential Manager, which signs in to GitHub the first time. |
| Git LFS | Comes with Git for Windows; run `git lfs install` once in a terminal. |

Optional, for speed: add the repo folder and `C:\Program Files\Epic Games` to Windows Security's exclusions
(Virus & threat protection > Exclusions). Defender scanning every intermediate file makes builds much slower.

## 2. Clone with LFS

Use a short path. Unreal's intermediate paths are long, and Windows still trips over 260 characters in places.

```bat
git config --global core.longpaths true
git lfs install
git clone https://github.com/benwmax/sailing-sim D:\dev\sailing-sim
cd D:\dev\sailing-sim
git lfs pull
```

`git lfs pull` is harmless if the clone already fetched everything. If `Content\Maps\Lake.umap` is a few hundred bytes
of text starting with `version https://git-lfs`, LFS did not run; the one-command script checks this and stops.

If Unreal is not in the default folder: `setx UE_ROOT "D:\Epic Games\UE_5.8"` (then open a new terminal).

## 3. The MetaHuman crew (optional, recommended)

`Content/Crew/MetaHumans` is git-ignored (about 0.5 GB, and the MetaHuman licence covers use, not redistribution), and
building it needs an Epic sign-in for the cloud auto-rig. Bring the Mac's copy over instead:

1. On the Mac: `scripts/pack-metahumans.sh` writes `Artifacts/MetaHumans-for-PC.zip`.
2. Copy the zip to the PC by USB drive or a private cloud folder (never commit or publish it). Put it in the repo root
   or in `Downloads`, and the script finds it; anywhere else, pass `-MetaHumansZip <path>`.

Without it the game uses the Blender crew (`SK_Sailor`) on every tier, and the packaging log shows warnings about the
missing `/Game/Crew/MetaHumans/...` folders; it should still package. With it, High and Ultra draw the crew's hair as
strands (the Mac can only draw cards).

## 3b. NVIDIA DLSS (optional, NVIDIA GPUs)

`Plugins/DLSS` and `Plugins/StreamlineNGXCommon` are git-ignored: NVIDIA's RTX SDK licence allows them only inside the
shipped game (never in git or on their own), and they are about 4 GB. The `.uproject` lists both as optional, Win64
only, and the game finds DLSS by its console variable (`r.NGX.DLSS.Enable`), never by linking to it: the Mac and a fresh
clone build and run without them, and keep TSR.

1. Download "UE 5.8 DLSS Plugin" from https://developer.nvidia.com/rtx/dlss (no sign-in; v8.9.0 was used, 1.17 GB).
2. Unzip it outside the repo, then copy its `Plugins/DLSS` and `Plugins/StreamlineNGXCommon` folders into the repo's
   `Plugins/`. Build as usual (`scripts\windows\build.ps1`, then package).
3. In the game, Settings > Graphics > Anti-aliasing gains DLAA, DLSS Quality, Balanced and Performance on an NVIDIA GPU.
   DLSS sets its own render scale (DLAA native, Quality 67%, Balanced 58%, Performance 50%); benches ignore it.

Before a commercial release (`docs/licences/assets.csv`, the DLSS row): notify NVIDIA
(https://developer.nvidia.com/sw-notification), and show the DLSS attribution and NVIDIA's marks on the splash screen,
the about box and the credits, each use approved by NVIDIA in writing (send a sample at least two weeks ahead). The
game's own EULA must protect NVIDIA's parts at least as well as NVIDIA's licence. No NVIDIA logos are in the game yet.

## 4. One command

Double-click `build-windows.bat` in the repo root, or from a terminal in the repo:

```bat
build-windows.bat
```

In PowerShell (the default terminal on Windows 11) type `.\build-windows.bat`: PowerShell does not run files from
the current folder without the `.\`.

It runs `scripts\windows\all.ps1`, which:

1. checks Git LFS, Visual Studio's C++ game workload, Unreal and the GPU;
2. runs `git lfs pull` and checks the map is real;
3. unpacks the MetaHuman zip if it finds one;
4. builds the editor (`SailingSimEditor Win64 Development`);
5. runs every automation test headless (`SailingSim.*`; the Mac passes 92);
6. packages the game to `Packaged\Windows\SailingSim.exe`;
7. launches it once to warm the GPU's pipeline cache, then runs a 20 s Ultra benchmark with the autopilot tacking and
   prints the frame rate (the screenshot goes to `Artifacts\ultra.png`).

Leave the PC awake and the game window in front while it benches. Options (after the .bat or the .ps1):

| Option | Effect |
| --- | --- |
| `-Visual` | Also runs the twelve-view bench on High and Ultra (`Artifacts\visual-bench-pc.csv`, about half an hour) |
| `-ResX 3840 -ResY 2160` | Bench at 4K instead of 1080p |
| `-Config Shipping` | Package a Shipping build |
| `-SkipTests`, `-SkipPackage`, `-SkipBench` | Leave a step out |
| `-MetaHumansZip <path>` | Where the crew zip is |

The first run takes a long time: the engine compiles its shaders for DirectX 12 SM6 once (the Derived Data Cache keeps
them), and the first launch of the packaged game builds the GPU's pipeline cache.

## 5. The steps on their own

Each mirrors a Mac script and writes the same logs to `Artifacts\`. Run from the repo root in PowerShell (or
`powershell -ExecutionPolicy Bypass -File scripts\windows\<script>.ps1 ...` from cmd).

| Windows | Mac twin | What it does |
| --- | --- | --- |
| `scripts\windows\build.ps1 [-Config DebugGame]` | `scripts/build.sh` | Compiles the editor target. Log `Artifacts\build.log` |
| `scripts\windows\test.ps1 [-Filter SailingSim.Physics]` | `scripts/test.sh` | Automation tests headless; report `Artifacts\TestReport\index.json`, log `Artifacts\test.log`. Build first |
| `scripts\windows\package-win.ps1 [-Config Shipping] [-Full]` | `scripts/package-mac.sh` | BuildCookRun `-platform=Win64` to `Packaged\Windows\`, cooking incrementally (`-Full` cooks everything). Log `Artifacts\package.log` |
| `scripts\windows\gate.ps1 -Scope clouds\|water\|boats\|crew\|world\|night\|ui\|all [-Baseline csv] [-Merge a,b]` | `scripts/gate.sh` | The gate: build, tests and package only when their inputs changed (`Artifacts\gate\`), then the scope's views on High and Ultra |
| `scripts\windows\prescreen-stills.ps1 -Label x [-View storm,beam8] [-Compare main]` | `scripts/run-game.sh` | Stills of the bench views from the uncooked editor binary, no package; `-Compare` puts another label's still beside each |
| `scripts\windows\run-python.ps1 make_materials.py [-Full]` | `scripts/make-content.sh` | Rebuilds only the materials whose code changed since its last run here; `-Full` all of them |
| `scripts\windows\make-crew-clothes.ps1 [-SkipExport] [-ExportOnly]` (`$env:PIECES=Vest`) | `scripts/make-crew-clothes.sh` | Exports the MetaHuman bodies (full editor, `QUIT_EDITOR` after the script), tailors polo, shoes and vest in Blender, imports them (`PIECES` filters the import) and tunes the skin. Needs the MetaHumans and Blender; logs `Artifacts\crew-*.log` |
| `scripts\windows\bench-win.ps1 [-Seconds 20] [-Quality Ultra] [-Demo] [-GameArgs "..."]` | `scripts/bench-mac.sh` | Runs the packaged game, prints fps and GPU slices, copies `bench.json` and the screenshot to `Artifacts\` |
| `scripts\windows\bench-visual-win.ps1 [-Tiers High,Ultra]` | `scripts/bench-visual.sh` | The twelve visual views per tier, CSV in `Artifacts\` |

The game arguments in `CLAUDE.md` (`-SailingWeather=Thunderstorm`, `-SailingWorld=1`, `-SailingCapture=HelmEye`, ...)
work the same way through `-GameArgs`. To play, run `Packaged\Windows\SailingSim.exe`.

The other `scripts/*.sh` (content generation, Blender models, MetaHumans, phase benches) stay Mac-only; the content
they make is already committed. `polar.sh` and `traffic.sh` can run under Git Bash with LLVM's clang on the path.

## Shipping builds and the release smoke

In a Shipping build every `-Sailing` switch is inert (`SailingArgs::Dev()` returns an empty command line), so the bench,
capture and tuning switches and `-SailingExecAt`'s console commands can't change a shipped game. The one exception is
the release smoke: with `-SailingShippingSmoke`, only `-SailingUIScript`, `-SailingWorld`, `-SailingLaunch`,
`-SailingShot` and `-SailingBench` (at most 60 s) pass (`SailingArgs::ShippingSmokeArgs`, tested by
`SailingSim.Smoke.ShippingSmokeArgs`). Package and load each world:

```
scripts\windows\package-win.ps1 -Config Shipping
Packaged\Windows\SailingSim.exe -windowed -SailingShippingSmoke -SailingWorld=0 -SailingLaunch=1 -SailingShot=ship-lake -SailingBench=20
Packaged\Windows\SailingSim.exe -windowed -SailingShippingSmoke -SailingWorld=1 -SailingLaunch=1 -SailingShot=ship-bay -SailingBench=20
Packaged\Windows\SailingSim.exe -windowed -SailingShippingSmoke -SailingWorld=Gulf -SailingLaunch=1 -SailingShot=ship-gulf -SailingBench=20
```

A Shipping build saves to `%LOCALAPPDATA%\SailingSim\Saved`, not beside the executable: the screenshots and
`bench.json` are in its `Bench` folder. Shipping writes no log. The package includes CrashReportClient, with no upload
endpoint (`[CrashReportClient] DataRouterUrl=""` in `DefaultEngine.ini`), so crash reports stay in `Saved\Crashes`.

`[/Script/AndroidFileServerEditor.AndroidFileServerRuntimeSettings] SecurityToken` in `DefaultEngine.ini` is a random
per-project value that the editor regenerates on start, not a credential to any service. The AndroidFileServer plugin's
runtime module is built into the Windows game, but all of its code is under `PLATFORM_ANDROID`, so on Windows it does
nothing and the token is unused (it stays in the staged config like every other `DefaultEngine.ini` value).

Never drive the game by sending keys or mouse clicks to the desktop: the window may not be in front, and the input lands
in other apps. Use `-SailingUIScript`, which delivers keys through Slate inside the game.

## The Friday tester build

One command takes main to a zip for Bean and the testers (slice issue #406):

```
scripts\windows\friday.ps1                  # origin/main, fetched and checked out detached
scripts\windows\friday.ps1 -Commit 29ecd2b6 # a given commit
scripts\windows\friday.ps1 -NoCheckout      # what's checked out (a dry run of a branch)
```

It refuses a tree with tracked changes, and a commit that already has a `Packaged\Shipping-<commit>` folder: a build is
never packaged over another. Then, in about 15 minutes on the 4090:

1. `build.ps1`, then `package-win.ps1 -Config Shipping -Full -Into Shipping-<commit>` (a full cook, into a new folder).
   For the package only, it writes `Content\BuildStamp\version.txt` ("<commit>, <date>", git-ignored, staged by
   `DefaultGame.ini`), which the title screen shows small in its bottom corner (`SailCatalog::BuildStamp`); it's removed
   afterwards. A build without the file shows no stamp.
2. Smoke checks, by launch arguments and `-SailingUIScript` only (`-SailingShippingSmoke`, `-NoCrashReporter`):
   - Title > Gallery opens and renders its thumbnails (more than 100 in `Saved\GalleryThumbs`);
   - two Ultra Lake benches of 30 s (`-BenchSeconds`), the second reported: the first after a full cook runs slow.
3. `Packaged\Shipping-<commit>\BUILD.md`: the commit, date, fps, the checks, where crash logs go, and what merged since
   the last Friday build (the newest other `Packaged\Shipping-*\BUILD.md`'s commit, by `git log --first-parent`).
4. `Packaged\SailingSim-<commit>-Win64.zip`: the `Windows` folder with `BUILD.md` and
   [TESTER-GUIDE.md](TESTER-GUIDE.md) (install, the first-launch shader wait, controls, reporting, crash logs). Windows'
   own `tar.exe` writes it: the .ucas is over 2 GB, past PowerShell 5's `Compress-Archive`.

The result line is in `Artifacts\friday-<commit>.txt`. The gamepad and settings checks are done by hand.

**Crash reports (Sentry).** The DSN lives on the PC only, in `Artifacts\sentry\dsn.txt` (or `$env:SENTRY_DSN`; the file
wins), and is never committed: `Artifacts/` is git-ignored. For the cook, friday.ps1 appends a
`[/Script/Sentry.SentrySettings]` section (`Dsn`, `Release=sailing-sim@<commit>`, `Environment=tester`) to
`Config\Windows\WindowsEngine.ini` and puts the file back byte for byte afterwards, even when packaging fails, then warns
loudly if anything under `Config` or `Content` is left changed. The section does nothing until the game has the Sentry
plugin. After packaging it uploads the Shipping symbols with `sentry-cli debug-files upload --include-sources` when
sentry-cli, `Artifacts\sentry\auth.token` (a Sentry auth token with `project:releases` and `project:write`) and
`Artifacts\sentry\project.txt` (`<org>/<project>`) are all there; otherwise it skips with one line and the build goes on.
sentry-cli is installed on the PC (3.8.0, Oct 30: `winget install Sentry.sentry-cli`, which names the command `sentry`; friday.ps1 takes `sentry-cli` or `sentry`).

## Build times

Measured on the PC (i9-9900K, RTX 4090, D:\ NVMe, Unreal's DDC on `D:\UnrealDDC`) on Oct 15 2026, after main 7149d537,
one run each (a second run of the same step came within 5%). Before = the scripts as they were; after = build-fast.

| Step | Before | After | What changed |
| --- | --- | --- | --- |
| Package, nothing changed | 186 s (cook 80, stage 62) | 62-66 s (cook 26-29, stage 29) | incremental cook: the Zen store keeps the last cook (`-cookincremental`) |
| Package, full cook (`-Full`) | 186 s (cook 80) | 126-129 s (cook 59) | no SM5 shaders (6,033 of them: 1,365 material, 4,668 global) |
| One water material changed, shaders compiled: materials + package | 30 s + 186 s = 216 s | 12 s + 68 s = 80 s | `make_materials.py` rebuilt 1 builder of 23 (`build_water_v4`) instead of resaving 116 assets; the cook cooked 2 packages of 4,149 instead of 3,037 |
| Gate on an unchanged tree: build and package before the bench | 4 s + 186 s every time (no gate on the PC) | 0 s | `gate.ps1` skips both by content hash, as `gate.sh` does; the `ui` scope's bench (4 views x 2 tiers) is 202 s |
| A visual pre-screen after a material change (one view, High and Ultra) | package 68 s + two bench runs 50 s = 118 s | 97 s (185 s the first time: the editor compiles its Ultra shaders once) | `prescreen-stills.ps1`: uncooked stills, no package; most useful when the change would recook a lot |
| SWAN wave bake (WSL) | one case at a time on one core (20-50 min a case; 15 of 16 threads idle) | four cases at once | `Tools/water/swan_bake.py run --jobs N` (w3 branch); numbers in `docs/water-3/swan-bake.md` |

The first package on a new checkout is still long: 2,199 s on `D:\dev\sailing-sim` (cook 2,072 s), almost all of it
derived data (Nanite meshes, distance fields, mesh cards) built once into the DDC; the next full cook was 186 s.

Checked: the incremental and the full package of the same tree bench the same (GPU ms per frame on beam8, storm and
helm-eye, High and Ultra, within 0.4 ms; the fps moved more between runs, because the PC is held by its render thread,
about 15-18 ms a frame, not the 4090: compare GPU ms on this PC, fps on the Mac).

How to use it:

- `scripts\windows\gate.ps1 -Scope water -Baseline Artifacts\visual-bench-gate-water-main.csv` before a PR (the Mac's
  scopes; on the PC its tiers are High and Ultra). `-Merge a,b` gates a batch of branches in one build and package.
- `scripts\windows\prescreen-stills.ps1 -Label main -View storm` on main, then `-Label mine -Compare main` on the branch:
  stills side by side in a minute or two, before any package.
- `scripts\windows\run-python.ps1 make_materials.py` rebuilds what changed; `-Full` after changing a fabric scan or the
  cloud noise (inputs outside the script), or when in doubt. It rebuilds everything by itself when the material assets
  changed some other way (a git checkout or merge) since its last run.

The Mac once saw its incremental package hang at "Reading oplog from Zen" (the cook's own Zen server exited before
staging) and now starts a persistent Zen server first. None of about a dozen Windows packages on Oct 15 2026, incremental
or full, hung there, so `package-win.ps1` has no such guard. Add one (start `zenserver` before RunUAT, stop it after) if
it ever does.

What a studio does that doesn't apply here: a build farm or distributed shader compiling (one PC; UBA already uses its
16 threads); a shared cloud DDC with the Mac (the Mac's Metal shaders and the PC's DX12 ones share nothing, and the
meshes' derived data is per platform too); `-snapshot` cooks from a build server (there is none to publish them).

## Settings that differ on Windows

- Graphics: DirectX 12 with the SM6 shader platform only (`Config/DefaultEngine.ini`, WindowsTargetSettings). There is
  no DirectX 11 fallback, and since build-fast no SM5 shaders are cooked either (`Config/Windows/WindowsEngine.ini`
  removes the engine's default D3D11 entry, which had kept a whole SM5 set in every cook).
- Quality: the packaged PC game starts on **Ultra** (TSR at native, half-resolution clouds with the most samples,
  Epic scalability, no resolution governor). A tier picked in Settings is saved and wins. The editor and the tests keep
  Medium, as on the Mac (`USailingSettings` constructor).
- Hair: strands on High and Ultra with hair voxelization on (`Config/Windows/WindowsEngine.ini`); the Mac uses cards.
- Hardware ray tracing (Lumen on High and Ultra) turns on only where the GPU reports it, as on the Mac.
- Saved files (logbook, photos, bench output) should be in `Packaged\Windows\SailingSim\Saved\` for Development
  builds; the scripts also look in `%LOCALAPPDATA%\SailingSim\Saved\`.

## If something fails

- **Compile errors that the Mac never showed**: MSVC warns about different things than clang (for example C4244,
  double to float). Fix them in the code rather than turning warnings off; the fix must still build on the Mac.
- **"Unreal Engine not found"**: set `UE_ROOT` to the folder that holds `Engine\`.
- **Build says no Visual Studio or no toolchain**: re-run the Visual Studio Installer and add the
  "Game development with C++" workload with the latest MSVC and a Windows 11 SDK.
- **The bench prints "No bench result"**: look at `Artifacts\bench.log`. A locked or sleeping screen stalls the game;
  the first launch can run past the time limit while it builds the pipeline cache (run `bench-win.ps1` again).
- **Scripts refuse to run** ("running scripts is disabled"): use `build-windows.bat`, which bypasses the policy for
  this run only, or `powershell -ExecutionPolicy Bypass -File ...`.
- Frame rates have only been measured on the M5 Pro; the Ultra tier has only been checked to run there.

## What has been run, and what has not

Run on the PC (Windows 11, RTX 4090, Visual Studio Community, Unreal 5.8.3, then `C:\dev\sailing-sim`; the checkouts moved to `D:\dev` on Oct 15 2026):

- Editor build (after renaming locals that MSVC rejects as shadowing, C4458/C4459).
- Automation tests: 91 of 92 passed; the one failure was `SailingSim.Visual.MetaHumanCrew` because the crew is
  git-ignored and not on the PC. That test now skips with a warning when `Content\Crew\MetaHumans` is missing.
- Win64 cook and package to `Packaged\Windows\SailingSim.exe`.
- Ultra benchmark (1080p, autopilot tacking): about 72 fps average, p99 22.6 ms, with the GPU at 7.3 ms of a 13.9 ms
  frame. The frame is CPU-bound, so a CPU profile comes before any GPU tuning.

Not yet run: the full test pass after the crew-test change, the twelve-view `-Visual` bench, a Shipping package, the
MetaHuman zip round trip (strand hair has not been seen on the NVIDIA GPU), and 4K.

## Editor scripts that hang on exit (the "zombie" UnrealEditor-Cmd)

Seen three times on Oct 14-15 2026, each after an editor Python import run through `scripts\windows\run-python.ps1`.
Each script ran to completion (its last log line printed), and the editor then crashed while exiting, with a
callstack through `python311.dll` and `UnrealEditor-PythonScriptPlugin.dll` and `CrashReportClientEditor` opening.
Stopping `UnrealEditor-Cmd` while the crash reporter was up (`Stop-Process -Force` or `taskkill /F /T`) left it in the
process list with one thread and about 1,300 handles, and `taskkill` then reported "no running instance of the task".
Those processes kept their files open until a reboot:

- `Content\Materials\M_CloudLayers.uasset` and `Content\Boats\Materials\M_BoatSurface.uasset` (a `git merge` couldn't
  replace them: "unable to unlink ... Invalid argument");
- `Content\Boats\J22Hero\M_BoatHero.uasset` (a reimport couldn't delete it: error 32);
- `Binaries\Win64\UnrealEditor-SailingPhysics.dll` and `UnrealEditor-SailingSimTests.dll` (the editor build failed to
  link: LNK1104).

The commands, from `run-python.ps1` (all with the project path and `-run=pythonscript`):

| Script | Ends with | Extra flags | Result |
|---|---|---|---|
| `import_boats.py gearonly` | `os._exit(0)` | `-unattended -nosplash -nosound -NoP4 -stdout -FullStdOutLogOutput` | crashed on exit; the crash reporter waited until it was killed |
| `import_boats.py fleet` | `os._exit(0)` | the same plus `-nocrashreports` | crashed on exit; the crash reporter still opened (the flag didn't stop it); a zombie |
| `import_j22_hero.py` (first version) | `os._exit(0)` | the same | crashed on exit; zombie after `Stop-Process` |
| `import_j22_hero.py` (later) | `os._exit(0)` | the same, crash reporter closed within 3 s by a loop | crashed on exit; the editor then hung, and stopping it left a zombie |
| `import_j22_hero.py` (Oct 15, called directly) | nothing (returns) | `-unattended -NoCrashReporter -nosplash -nosound -NoP4 -stdout -FullStdOutLogOutput` | **exited cleanly**, code 0 in 45 s, no crash reporter |

So on this PC `os._exit(0)` itself is what crashes the editor on the way out (on the Mac it exists to dodge a Python
shutdown crash after big bakes). Without it, and with `-NoCrashReporter`, the hero import exited cleanly. Whether the
big imports (`import_boats.py`, `import_world.py`) also exit cleanly without `os._exit` on Windows is still to be
tried. What to try, in order:

1. No `os._exit` (let `-run=pythonscript` return), and compare.
2. `-NoCrashReporter` in place of `-nocrashreports`, to keep `CrashReportClientEditor` from opening at all.
3. If an editor still hangs, don't kill it while the crash reporter is up. Close the crash reporter first, wait for the
   editor to end, and record the exact command and log tail here.

Oct 15 2026 again, after the move to `D:\dev`: a short probe ending in `os._exit(0)` (with `-nocrashreports`) hung in an
ensure at shutdown (`LocalizableMessageProcessor.h`, `Registrations.Num() == 0`); `Stop-Process` after ten minutes left
a fourth zombie holding `D:\dev\sailing-sim\Binaries\Win64\UnrealEditor-Sailing*.dll`. Since then `run-python.ps1`
passes `-NoCrashReporter`, and every script that returns normally (`capture_clips.py`, `make_test_footage.py stage`,
`solve_clips.py`, a dozen probes) exited cleanly.

Oct 30 2026: a one-off marina bake script (UWorldKitLibrary::BakeMarina through `run-python.ps1`, `-NoCrashReporter`)
ended with `os._exit(0)` as `import_world.py` does after its bakes. The bake saved, then the editor hit the same
`LocalizableMessageProcessor.h` ensure on the way out, and stopping it left a fifth zombie. So `os._exit` crashes the
exit on this PC with `-NoCrashReporter` too: scripts run here should return normally.

If a zombie does appear, only a restart frees its files. Work that doesn't build or import (docs, the WSL jobs) can go
on meanwhile. A zombie's module DLLs can still be renamed out of the way (a mapped image allows a rename), and the build
then links new ones:

```powershell
Get-ChildItem Binaries\Win64\UnrealEditor-Sailing*.dll, Binaries\Win64\UnrealEditor-Sailing*.pdb | ForEach-Object { Rename-Item $_.FullName "$($_.Name).zombie" }
```

Delete the `.zombie` files after the restart. A moved or copied checkout needs its UBT makefiles deleted
(`Intermediate\Build\Win64\x64\SailingSim*\Development\Makefile.bin`): the copy from `C:\dev` kept the old paths and its
first build tried to link into `C:\dev\sailing-sim\Binaries`.

## Editor scripts that need the full editor

`-ExecutePythonScript="<script> <args>"` on `UnrealEditor.exe` runs a script in a full editor (GPU, PIE, Movie Render
Queue) and quits on the next tick after it returns. A script that waits on something (an MRQ render) calls
`unreal.EditorPythonScripting.set_keep_python_script_alive(True)` and sets it back to `False` when done
(`make_test_footage.py render`). The MetaHuman body solve needs this route too (`solve_clips.py`): a commandlet has no
RHI, so the performance won't start.
