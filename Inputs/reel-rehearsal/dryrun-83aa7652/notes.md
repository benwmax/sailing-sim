# Saturday capture dry run on main 83aa7652 (PC, Nov 25 2026)

## Setup

- **Package:** Development `Packaged\Windows-83aa7652`, a fresh package of main 83aa7652 (#827 merged). Its cook runs
  with `-DPCVars=r.ForceDebugViewModes=1` (#829).
- **Tests on that line:** the full suite ran on fa51d3a6, two merges earlier: 463 tests, 0 failed
  (`Inputs/bench/main-fa51d3a6`). I didn't rerun the 2.5 h suite on 83aa7652.
- **Takes:** every take ran once at 1920x1080, with frames on `D:\dev\reel\dryrun\<take>`.
  - Each take's exact command line is in `previews/<take>-args.txt`, and its middle frame in `previews/`.
  - Shot files are from `Inputs/reel-rehearsal/shots/`.
- **Common args:** `-benchmark -fps=60 -SailingQuality=Ultra -ForceRes -windowed -SailingFilm -SailingCinematic=1
  -SailingNoHud -SailingNoGpuSlices -SailingShowCrew=0 -SailingTraffic=0 -SailingSeed=7 -SailingBenchWarmup=10
  -SailingRecordInterval=0.0166667`. The HUD takes drop `-SailingNoHud`.
- **Results:** all 17 takes wrote every frame ("N of N frames recorded"). No crash, and no sailor in any frame.

## P1: wireframe

#828's `-SailingViewMode` isn't on main yet, so I used `-DPCVars=r.ForceDebugViewModes=1 "-ExecCmds=viewmode wireframe"`.

- **It works:** 120 frames of true wireframe on the hull, rig, water and shore.
- **Same gap as the test cook:** the sails don't draw in wireframe, and the sky is black.

## P2: storm time-lapse (`P2-storm-preview-1080p.mp4`)

`-SailingWeather=Thunderstorm -SailingStormDelay=60 -SailingHour=16 -SailingDemo -SailingTWA=60 -SailingHoldTWA=60
-SailingCapture=Tripod "-SailingTripod=60,2.5,40,0.4" -SailingRecord=600 -SailingRecordInterval=2`

- 300 frames, 10 min of game time, taking 10 min of wall time at 1080p.
- **Game clock:** first frame 16:00:10, front passage about 16:03:25, last frame 16:10:09.
- **The front hits at about 205 s of game time, 195 s into the recording: 32% in, as planned.**
  - Before it, the true wind is about 9-10 kn from 180.
  - After it, 43.6 kn from 292, easing to 28 kn by 4 min after and to 7 kn by 9 min.
  - The J/22 heels to 40 deg at the hit.
- **The rule for Saturday:** the front passes at about (150 + `StormDelay`) s of game time. A warm-up of W s and a
  third-way front need `StormDelay = W + 200 - 150`, which is 60 for a 10 s warm-up.

## P3: real day 2023-06-11 (`P3-realday-preview-1080p.mp4`)

`-SailingDay=2023-06-11 -SailingHour=18.892`, same tripod and record as P2.

- The baked day's storm is due at **18.950 local** (`storm arrival 18.950`). The file's own start is 18.908.
- **Game clock:** first frame 18:53:41, front passage about 18:56:55, last frame 19:03:40.
- **The front passes at about 205 s of game time, 32% into the recording.**
  - Before it: 2-8 kn from 85-105 deg. The wind drops to about 2 kn, so the demo boat **stalls**: 0 kn from 76 s on,
    lying head to wind.
  - After it: 28-37 kn from 281. She lies **knocked down at 20-30 deg of heel without way** for about 3 min, then the
    wind dies to 1-2 kn by the end.
- For Saturday, either accept a drifting boat (it reads as caught out) or start with more way on. One way is
  `-SailingTWA=90 -SailingHoldTWA=90`, so she reaches across the light air.

## R-shots (1080p, 1 take each)

| Take | Framing | Notes |
|---|---|---|
| R01 dawn marina crane | Works: the crane down over the marina rows | **Too dark:** at 07:00 the sun is 1.8 deg *below* the horizon (EV -5). Use **`-SailingHour=7.4`** for first light, or 7.6 for the sun on the water. |
| R05 tack orbit | Works | **Tack timing:** the demo pilot tacks at **12.6 s and 24.6 s** of game time (TWA crosses 0). With warm-up 25 the tack falls just before the record. **Use `-SailingBenchWarmup=11.5`** to start the record 1.1 s before the first tack. It's the same every run (seed 7, fixed step). |
| R06 helm eye | Works: the mount at the helm looking forward, heeling with her | `-SailingUiMode=natural` with the HUD on shows **no HUD elements** in these frames; natural mode shows nothing in this situation. If a HUD is wanted, use `helpful`. |
| R09 polar chase | Works | |
| R10 gust (C22, tripod 120 m) | Boat small in the frame | At 120 m and 18 deg she's a small subject. |
| R12 Sunfish bow mount | Works: looking aft from the bow, mast and boom in frame | She tacks at **14.2 s**, about 4 s into the 8 s record. |
| R13 jib clew macro | **Doesn't work** | At the dock (`-SailingDrill=LeavetheDock`) the jib is stowed, so there's **no clew** to frame; the shot shows the deck and a neighbour's cabin. It needs the boat under sail (open water, light air), or a drill state with sails up. |
| R14 C22 dolly | Works | |
| R21 golden orbit | Works | **Golden hour:** at `-SailingHour=16.85` the sun is at 4.9 deg (EV -3.5), with warm side light. Sunset on the date is about 17:20, so 16.85 is about 30 min before. |
| R22 night chase | Very dark | The boat is a silhouette against faint shore lights at 21:00, with the natural HUD showing nothing. It may want `-SailingEV` lifted, or the moon. |
| H02 hero reach track | Works | |

## Menus (8 s at 30 fps, HUD on)

| Take | Result |
|---|---|
| R03 briefing (`-SailingDrill=LeavetheDock -SailingFrontEnd=Briefing`) | **Reachable:** the "Leave the dock" briefing card opens about 4 s in. |
| R08 certificate (`-SailingFrontEnd=Career`) | The Career screen ("Learn to sail", tiers and lessons) is reachable. **No certificate shows**: a fresh profile has none earned. A certificate needs a save with a finished tier, or a dev switch. |
| R23 world map (`-SailingFrontEnd=World`) | **Reachable:** "Choose a world" with the four worlds. |

`-SailingFrontEnd` works in a Development package during a recording. I didn't need `-SailingUIScript` for these three.

## Saturday args per take

Add these to the common args (4K: `-ResX=3840 -ResY=2160`).

| Take | Args |
|---|---|
| P1 | `-SailingWorld=Lake -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingHour=16 -SailingDemo -SailingTWA=60 -SailingHoldTWA=60 -SailingCapture=Path -SailingShotFile=reel/p1-layer-peel-orbit.json -SailingRecord=12 -DPCVars=r.ForceDebugViewModes=1`, plus `-SailingViewMode=wireframe` or `lightingonly` once #828 is merged (or `"-ExecCmds=viewmode wireframe"` now) |
| P2 | `-SailingWorld=Lake -SailingWeather=Thunderstorm -SailingStormDelay=60 -SailingHour=16 -SailingDemo -SailingTWA=60 -SailingHoldTWA=60 -SailingCapture=Tripod "-SailingTripod=60,2.5,40,0.4" -SailingRecord=600 -SailingRecordInterval=2` |
| P3 | `-SailingWorld=Lake -SailingDay=2023-06-11 -SailingHour=18.892 -SailingDemo -SailingTWA=90 -SailingHoldTWA=90 -SailingCapture=Tripod "-SailingTripod=60,2.5,40,0.4" -SailingRecord=600 -SailingRecordInterval=2` |
| R01 | `-SailingWorld=Lake -SailingDrill=LeavetheDock -SailingWeather=CalmMorning -SailingHour=7.4 -SailingCapture=Path -SailingShotFile=reel/s01-dawn-marina.json -SailingRecord=6` |
| R05 | `-SailingWorld=Lake -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingHour=15 -SailingDemo -SailingTWA=45 -SailingBenchWarmup=11.5 -SailingCapture=Path -SailingShotFile=reel/s05-tack-orbit.json -SailingRecord=7` |
| R06 | `-SailingWorld=Lake -SailingLaunch=1 -SailingUiMode=helpful -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingHour=15 -SailingDemo -SailingTWA=45 -SailingHoldTWA=45 -SailingCapture=Path -SailingShotFile=reel/s06-helm-eye.json -SailingRecord=6`, without `-SailingNoHud` |
| R09 | `-SailingWorld=Lake -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingWind=15 -SailingHour=14 -SailingDemo -SailingTWA=90 -SailingHoldTWA=90 -SailingCapture=Path -SailingShotFile=reel/s09-polar-chase.json -SailingRecord=8` |
| R10 | `-SailingWorld=Lake -SailingLaunch=1 "-SailingBoat=Catalina 22" -SailingWeather=AfternoonBreeze -SailingWind=14 -SailingHour=14 -SailingDemo -SailingTWA=60 -SailingHoldTWA=60 -SailingCapture=Tripod "-SailingTripod=120,3,18,0.4" -SailingRecord=7` |
| R12 | `-SailingWorld=Lake -SailingLaunch=0 -SailingBoat=Sunfish -SailingWeather=AfternoonBreeze -SailingWind=6 -SailingHour=14 -SailingDemo -SailingTWA=50 -SailingCapture=Path -SailingShotFile=reel/s12-sunfish-bow.json -SailingRecord=8` |
| R13 | Not ready: the jib is stowed at the dock (see above) |
| R14 | `-SailingWorld=Lake -SailingLaunch=1 "-SailingBoat=Catalina 22" -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingHour=14 -SailingDemo -SailingTWA=90 -SailingHoldTWA=90 -SailingCapture=Path -SailingShotFile=reel/s14-c22-dolly.json -SailingRecord=7` |
| R21 | `-SailingWorld=Lake -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingWind=6 -SailingHour=16.85 -SailingDemo -SailingTWA=70 -SailingHoldTWA=70 -SailingCapture=Path -SailingShotFile=reel/s21-golden-orbit.json -SailingRecord=7`. Check the hour against the capture date's sunset (`camera.json` sun elevation about 5 deg). |
| R22 | `-SailingWorld=Lake -SailingLaunch=1 -SailingUiMode=natural -SailingWeather=CalmMorning -SailingWind=4 -SailingHour=21 -SailingDemo -SailingTWA=80 -SailingHoldTWA=80 -SailingCapture=Path -SailingShotFile=reel/s22-night-chase.json -SailingRecord=7` (dark: see above) |
| H02 | `-SailingWorld=Lake -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingWind=10 -SailingHour=14 -SailingDemo -SailingTWA=90 -SailingHoldTWA=90 -SailingCapture=Path -SailingShotFile=reel/h02-j22-reach-track.json -SailingRecord=6` |
| R03 | `-SailingWorld=Lake -SailingDrill=LeavetheDock -SailingFrontEnd=Briefing -SailingRecord=8 -SailingRecordInterval=0.0333333`, without `-SailingNoHud` |
| R08 | `-SailingWorld=Lake -SailingFrontEnd=Career -SailingRecord=8 -SailingRecordInterval=0.0333333` (no certificate on a fresh profile) |
| R23 | `-SailingWorld=Lake -SailingFrontEnd=World -SailingRecord=8 -SailingRecordInterval=0.0333333` |

Each needs `-SailingShot=<id>` too. Run each from a Development package with Bean's Saved held aside. Bean's Saved was
held aside for every dry-run take and restored (7B5CA7BE).
