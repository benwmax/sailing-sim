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

## B) P4 top-down lake still: the whole lake fits, but distant land doesn't render

**Weather:** noon, clear: `-SailingWeather=ClearMistral -SailingWind=10 -SailingHour=12`.
- The lake has no "clear" weather preset; Clear mistral is the cloudless one.
- The camera record says sun elevation 36.7 deg and azimuth 176 deg (Nov 24), EV100 0.57.
- One frame per run (`-SailingRecord=0.0166667`).

| Try | Shot | Result |
|---|---|---|
| 1 | Start values: `pos [0,0,6000]`, `look [-90,0,0]`, boat at the default launch (Rush Creek) | Only the south lake. The frame is 8.4 x 4.7 km |
| 2 | `pos [6500,-1750,24000]`, `look [-90,0,0]` | Lake in frame, but most of the land is missing (square holes) |
| 4 | `pos [6500,-1750,10000]`, `look [-90,90,0]` | Lake's long axis across the frame. Land holes at the edges |
| 5 | Boat started mid-lake (`-SailingStartAt=6500,-1750,0`), `pos [0,0,12000]` | Same holes, so they don't follow the boat |
| **6 (final)** | **mid-lake start, `pos [0,0,16000]`, `look [-90,90,0]`, fov 70** | **Every arm of the lake is in frame** (`B-p4-topdown-4k.png`, `B-p4-topdown-1080p.jpg`) |

`B-tries-1080p.jpg` shows tries 1, 2, 4 and 5.

**Final values** (`p4-topdown.json` in this folder; the boat starts at `-SailingStartAt=6500,-1750,0`):
- `{"frame":"world","fov":70,"keys":[{"t":0,"pos":[0,0,16000],"look":[-90,90,0]}]}`
- That puts the camera at map 6500 N, -1750 E (from Rush Creek), 16 km up.
- Yaw 90 turns east to the top of the frame, so the lake's north-south length runs across it.
- At 16 km and 70 deg HFOV the frame covers about 22.4 x 12.6 km.

**Distant land doesn't render from these heights (flag).**
- From about 6 km out from the point under the camera, the terrain drops out in square chunks.
- The water plane shows through, with houses, trees and roads floating on it.
- This shows at 10, 12, 16 and 24 km. At 24 km most of the land is gone.
- It doesn't depend on where the boat is (tries 4 and 5).
- The chunk count stays 4,247 to 4,420 with none dropped, so the missing land is probably chunks that aren't drawn at that
  range, or the far ring not covering the grid's own area. I didn't dig further; it's game-side.
- **For Saturday's P4 this needs a fix, or a different shot.** Two options: a lower pass that pans along the lake, or a
  setting that keeps the whole lake grid's land drawn from altitude.

**Other notes:**
- Haze softens the frame toward the far edges. One small cumulus shows at 6 km (try 1).
- No sailor is visible, and the boat is too small to see at these heights.
