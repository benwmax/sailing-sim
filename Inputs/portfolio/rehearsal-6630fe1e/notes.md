# Portfolio capture rehearsal on main 6630fe1e (PC, Nov 24 2026)

A rehearsal for the Sat Nov 28 capture, run on today's main. The final takes run on the Nov 27 freeze sha. No game code
was changed.

## Setup

- **Main:** origin/main at **6630fe1e** ("Merge pull request #821 from benwmax/claude/project-thread-xkunbh").
- **Worktree:** a clean detached worktree, `D:\dev\ss-fix-wt\rehearsal` (smudge-skipped checkout, then `git lfs pull`,
  with the crew linked).
- **MSVC build:** Succeeded, 0 errors.
- **Package:** Development, `Packaged\Windows-6630fe1e`. The cook had 0 errors and 1 warning, and took 5 min.
- **Frames:** they stay on `D:\dev\reel\rehearsal-6630fe1e\<run>\`. Only previews and the B and C stills come here.

## Common args

```
-benchmark -fps=60 -SailingQuality=Ultra -ResX=3840 -ResY=2160 -ForceRes -windowed -SailingFilm -SailingCinematic=1
-SailingNoHud -SailingNoGpuSlices -SailingShowCrew=0 -SailingTraffic=0 -SailingSeed=7 -SailingBenchWarmup=10
-SailingRecordInterval=0.0166667 -SailingBench=3 -SailingCapture=Path -SailingShotFile=reel/<shot>.json
-SailingRecord=<s>
```

- I added `-SailingBench=3`, `-ForceRes` and `-windowed` to the brief's set.
- Each run's exact command line is in its `args.txt` on the PC.
- Bean's Saved was held aside for every run and restored (7B5CA7BE).

## A) P1 view-mode check: view modes do NOT work through `viewmode`

**Setup:**
- Lake, J/22, `-SailingWeather=AfternoonBreeze -SailingWind=12 -SailingHour=16 -SailingDemo -SailingTWA=60 -SailingHoldTWA=60`.
- Shot `p1-layer-peel-orbit.json` (in this folder), `-SailingRecord=2`.
- Every run wrote 120 frames in 158 to 195 s of wall time ("SailingRecord: 120 of 120 frames recorded").

| Run | Result |
|---|---|
| final | Normal Ultra film frames (`A-final-f060-1080p.jpg`) |
| `-ExecCmds="viewmode wireframe"` | The log says "Set new viewmode: Wireframe", but **every frame is lit, the same as final** (`A-viewmode-wireframe-f060-1080p.jpg`) |
| `-ExecCmds="viewmode lightingonly"` | Same: lit frames, no effect |
| `-SailingExecAt=5:viewmode+wireframe` / `+lightingonly` | No effect. This route goes through the game mode's exec and never reaches the viewport ("Set new viewmode" isn't logged) |
| `-ExecCmds="ShowFlag.Wireframe 1"` | **Partly works** (`A-showflag-wireframe-f060-1080p.jpg`) |
| `-ExecCmds="ShowFlag.LightingOnlyOverride 1"` | **Partly works** (`A-showflag-lightingonly-f060-1080p.jpg`) |

**`ShowFlag.Wireframe 1`, frame by frame:**
- The hull, deck gear and the far shore draw as magenta and cyan wireframe.
- The sails, sky and clouds stay fully lit.
- The water goes flat and dark.

**`ShowFlag.LightingOnlyOverride 1`:**
- The hull, deck and water go grey and lighting-only.
- The sails keep their cloth, marks and number, and the sky and clouds are unchanged.

**Whether view modes work in Development:** not as used here. `viewmode wireframe` and `viewmode lightingonly` are
accepted but render lit. The engine only allows debug view modes when it has the debug view-mode shaders
(`AllowDebugViewmodes()`), and a cooked package doesn't have them by default (`r.ForceDebugViewModes` is 0). The show
flags render through the normal shaders, so they work, but only on some of the scene.

**For P1 on Saturday, one of these is needed:**
- a cook with `r.ForceDebugViewModes=1`, which is a Config change and needs Bean's approval;
- a game-side switch that sets the view mode on the capture view;
- or accepting the show-flag look, with the sails and sky left lit.

**Does `-SailingFilm` fight them?** I saw no sign of it. The film log line shows only its own cvars, and the show flags
took effect with `-SailingFilm` on. I didn't do a run without `-SailingFilm` to rule it out.

**Do the runs line up frame for frame?** Yes.
- The telemetry is identical in every row (842 of 842 rows the same as final, in all six runs).
- The lit frames differ from final by only 0.4 to 0.7 of 255 in mean luminance, which is TSR and cloud noise.

**Crew:** no sailor is visible in any frame (`-SailingShowCrew=0`).
