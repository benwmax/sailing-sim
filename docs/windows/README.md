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
| `scripts\windows\package-win.ps1 [-Config Shipping]` | `scripts/package-mac.sh` | BuildCookRun `-platform=Win64` to `Packaged\Windows\`. Log `Artifacts\package.log` |
| `scripts\windows\bench-win.ps1 [-Seconds 20] [-Quality Ultra] [-Demo] [-GameArgs "..."]` | `scripts/bench-mac.sh` | Runs the packaged game, prints fps and GPU slices, copies `bench.json` and the screenshot to `Artifacts\` |
| `scripts\windows\bench-visual-win.ps1 [-Tiers High,Ultra]` | `scripts/bench-visual.sh` | The twelve visual views per tier, CSV in `Artifacts\` |

The game arguments in `CLAUDE.md` (`-SailingWeather=Thunderstorm`, `-SailingWorld=1`, `-SailingCapture=HelmEye`, ...)
work the same way through `-GameArgs`. To play, run `Packaged\Windows\SailingSim.exe`.

The other `scripts/*.sh` (content generation, Blender models, MetaHumans, phase benches) stay Mac-only; the content
they make is already committed. `polar.sh` and `traffic.sh` can run under Git Bash with LLVM's clang on the path.

## Settings that differ on Windows

- Graphics: DirectX 12 with the SM6 shader platform only (`Config/DefaultEngine.ini`, WindowsTargetSettings; this
  was already set and is unchanged). There is no DirectX 11 fallback.
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
