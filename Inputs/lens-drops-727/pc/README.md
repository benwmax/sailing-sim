# #727 lens drops (feedback #28), on the PC

- **Branch:** `claude/project-thread-pz8kri` head **ea7120ec**. It already contains main 0da7d6ea, so I used it as is. Package `Windows-ea7120ec-727`. M_LensWater compiled with no shader errors.
- **Main side:** main **40226d1c**, package `Windows-40226d1c`. Caveat: this is an older main than the branch's base 0da7d6ea, so anything outside the lens can differ too. The cloud/fog GPU numbers below show it.
- **Build:** MSVC clean.
- **`test.ps1 -Filter SailingSim.Visual`:** 76 passed, 2 failed, 14 with warnings.
  - **LensDrops:** Success.
  - **The two failures:** RigClearance (Catalina 22's lazy jib sheet through crew 0's spine, 2.4 cm) and SheetClearance (Catalina 22's mainsheet tail at 4.9 cm, the Maxi 100's lazy jib sheet at 4.7 cm). Bare main 0da7d6ea fails both identically, so the branch didn't cause them.
- **Runs:** 3840x2160 fullscreen, Ultra, packaged Development builds, RTX 4090. Bean's Saved was held aside and restored after each set (profile hash checked).
- **Repro:** `-SailingWorld=ray-hubbard -SailingBoat=J22 "-SailingStartAt=8759,152,-124" -SailingWind=27 -SailingTWA=67 -SailingWeather=Thunderstorm`

## Two sets

1. **The repro as given** (`stills-*`, `moving-*`, `gpu-*`). At the repro's start the storm has no rain over the boat yet, so **neither build draws lens drops** in these stills.
2. **The same plus `-SailingWeatherTime=200`** (`rain-*`): the boat is in the rain core. Every lens-drop observation below comes from this set.

Stills are three frames 2 s apart in one run (`-SailingRecord=6 -SailingRecordInterval=2`): `frame_0000..0002.png`. `end.png` is the bench's end shot. The moving-camera runs (`*-moving-*`) use `-SailingDemo` (the autopilot tacking): `end.png` plus bench.json.

## Post slice (bench.json `gpu.post_ms`; three ProfileGPU frames after a 20 s window), A/B/A back to back

| set | main A1 | branch B | main A2 |
|---|---|---|---|
| repro (no rain) | 2.45 | 2.61 | 2.45 |
| rain core (WeatherTime 200) | 2.69 | 2.70 | 2.47 |

- **In rain**, the branch's post (2.70 ms) sits inside main's own spread (2.47 to 2.69 ms): no cost I can measure.
- **Dry**, post is +0.16 ms on the branch.
- **Whole-frame GPU** is lower on the branch in both sets (rain 23.25 / 20.46 / 22.95 ms; dry 20.52 / 18.52 / 20.44 ms). That comes from the different main base (clouds_fog: main 6.01 against branch 4.43 ms dry), not from the lens.

## What I saw (1:1 crops, `crop-*-1to1.png`)

**Main** (`rain-stills-main/crop-sky-1to1.png` and `crop-mid-1to1.png`) has dozens of drops (roughly 60 in a 1200x800 crop). Every drop is the same rounded teardrop, tilted the same way, with the same small specular highlight in the same place. They come in a few size classes, so the lens reads as a repeated stamp.

**Branch** (`rain-stills-branch/crop-*-1to1.png`) has far fewer drops (about 10 in the same crop). Their outlines are irregular and differ from drop to drop. Their refraction is subtler: a darker rim and a lightly bent interior. Two things to look at:

- Some outlines are visibly faceted, polygonal with five or six straight sides, rather than smooth curves. At 1:1 that reads as a low-segment shape, not as water.
- The highlight is mostly gone, so on the dark sea the drops read as outlines more than as beads.

The branch's `frame_0002` shows drops at new places as they come and go. The boat has turned between frames (the start heading drifts), so the background moves too.

## Files

`<run>/bench.json`, `end.png`, `frame_*.png` (the stills runs), and the crops. Runs: `warm-*` (one warm-up per package), `stills-*`, `moving-*`, `gpu-a1-main`, `gpu-b-branch`, `gpu-a2-main`, and the `rain-` versions of each.
