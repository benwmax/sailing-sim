# Perf 3: the sun's scattering and disc setters (Mac, Oct 17 2026)

PR #110 (`perf-sun-setters`, 9efbc9b3 on main cb80cc34): `SetVolumetricScatteringIntensity` and
`SetAtmosphereSunDiskColorScale` in `ASailingEnvironment::UpdateSun` now step by 0.04, the same way the Perf 2 scales do.
Both follow `CloudShade`, which moves every frame as the weather map drifts, and each change marks the light's render
state dirty.

Both builds packaged as Development on Bean's Mac (Apple M5 Pro). Parked on High with soak 3 task A's arguments on the
moving clock, 20 min each, one after the other, window visible, `caffeinate -d`:

    SHOT=soak-sun ARGS="-SailingQuality=High -SailingKeepStart -SailingMooring -SailingBenchTrace \
      -ExecCmds=ToggleDrawEvents -csvCategories=VSM -csvCaptureFrames=200000 -SailingExecAt=1195:CsvProfile+Stop" \
      scripts/bench-mac.sh 1200

Unlike soak 3 there is no `-LLM`, so these fps are not directly comparable with soak 3's 51.2. Main was rerun the same
way as the baseline. The CSV profile ran for the whole window. `-csvCategories=VSM` adds the virtual shadow map's
per-frame page counts.

## Results

> **Correction (Perf 4, below).** These two runs were not of the same scene. The #110 build (9efbc9b3) branched from
> a8ce8ed3, before #109 added `-SailingMooring`, so in its run the flag was ignored and the boat was not parked on the
> buoy, while main cb80cc34 was parked. Rerun like for like, #110 makes no measurable difference on the Mac, parked or
> not. The gain and the page counts below come from the scene. The PC's D3D12 result (below) was measured separately.

| | main cb80cc34 | #110 | change |
|---|---|---|---|
| fps (bench.json, 1200 s) | 54.9 | **59.3** | +4.4 (+8%) |
| p99 ms | 20.64 | **19.25** | -1.4 |
| first / last 10 min fps | 54.9 / 55.0 | 58.8 / 59.9 | |
| first / last 10 min p99 ms | 20.56 / 20.78 | 19.65 / 18.63 | |
| p99 drift (`soak_stats.py`) | **+2.8 ms/h** | **-2.0 ms/h** | |
| GPU ms (CSV `GPUTime`, mean) | 17.65 | 16.36 | -1.3 |
| game thread ms | 2.45 | 2.22 | |
| render thread ms (CSV) | 18.20 | 16.84 | = frame time, see below |
| RHI thread ms | 3.18 | 4.35 | +1.2 |
| VSM pages cleared and redrawn per frame (`NUM_PAGES_TO_CLEAR`) | **974**, flat (943 to 1012) | **238**: 518 in the first 2 min, 101 to 118 from 12 min on | -75%, -89% at the end |
| VSM static pages invalidated per frame | 0.85 | 0.22 | |
| VSM non-Nanite instances drawn into shadow pages | 93 | 80 (86 falling to 76) | |
| VSM dynamic pages invalidated / requested per frame | 1118 / 1173 | 1171 / 1235 | about the same |
| RSS growth after 5 min | +1285 MB/h | +1387 MB/h | soak 3's per-frame Metal leak, unchanged |
| frames over 33.3 ms after warm-up | 2 | 6 | the worst are the 3 s warm-up |

**What the fix changes.** On main the virtual shadow map clears and redraws about 970 pages every frame, at the same
rate for all 20 min: the cache restarts every frame. With #110 that falls to about 100 pages from minute 12 on. The GPU
saves 1.3 ms, fps rises 8%, and p99 no longer climbs (+2.8 ms/h on main against -2.0 with the fix). Over 20 min the
drift slopes are noisy, but the sign matches the brief.

**Still moving.** About 1170 dynamic pages a frame are still invalidated on both builds. These are the pages that moving
casters touch (the boat swinging on its mooring, sails, crew, water). That is what the dynamic layer is for, so it is not
this bug. The cleared pages still fall slowly over the first 12 min with the fix (518 to about 100). Some shade changes
early in the run are bigger than 0.04, so the light is still rebuilt now and then until the weather map settles.

**Draw counts.** `DrawCall/ShadowDepths` and `RHI/DrawCalls` are columns in the CSV, but they read 0 on Metal, with or
without draw events and with `r.GPUCsvStatsEnabled=1`. The Metal RHI doesn't feed the GPU profiler's draw stats in this
build. The VSM category's `NON_NANITE_INSTANCES_DRAWN` is the closest equivalent: 93 on main, 80 with the fix, flat
within each run, against about 1090 non-Nanite instances in the scene.

**Render thread.** On the Mac the CSV's `RenderThreadTime` equals the frame time on both builds, because it includes the
wait for the GPU (`RenderThreadIdle` doesn't count that wait here). So it can't show the PC's 4 ms of render-thread
work. GPU time and the page counts show the saving instead. The RHI thread does about 1.2 ms more per frame with the
fix. It submits 8% more frames a second, so part of that is per-frame work done more often.

## Stills (High, uncooked `run-game.sh`, main against #110)

`perf-sun-setters/helm-eye-main-vs-fix.jpg` (bench-visual's helm-eye row) and `perf-sun-setters/storm-main-vs-fix.jpg`
(Thunderstorm, `-SailingWeatherTime=120`, `-SailingNoLightning`), main on the left:

- helm-eye: mean luminance 125.7 against 125.9. The mean absolute difference, 2.1 of 255, is wave and cloud motion
  between runs. No visible change in the sun's haze or the disc.
- storm: mean luminance 62.9 against 63.0, mean difference 0.45 of 255. The deck's gloom and the dimmed scattering under
  it look the same. The 0.04 step doesn't show.

## Tests

`scripts/test.sh SailingSim.Visual` 32/32, `SailingSim.Smoke` 16/16 on #110.

## Next

The fog setters in `UpdateHaze` were the next suspect. With the cache no longer restarting, the drift is gone over these
20 min, so they matter less, but they still rebuild the fog proxy every frame and are worth stepping the same way. A
longer run, an hour or more, would pin the drift down better than 20 min can.

## Files (`soak/`)

`sun-setters-{main,fix}-2026-10-17.frames-1hz.csv` (1 Hz frames), `.mem.csv` (RSS every 60 s), `.csv-2min.txt` (CSV
profile means in ten 2-minute bins: frame, thread and GPU ms, VSM page and instance counts). The full CSV profiles (146
MB each) stay in the game's sandbox under `Saved/Profiling/CSV/`.

## The PC on D3D12 (main with #110)

The PC's parked soak confirmed #110 on D3D12: p99 drift 3.8 to 0.79 ms/h, Ultra fps 61 to 80, and `ShadowDepths` draws
119 and climbing to 80 and flat. A small residual drift is left on the render thread (+1.66 ms/h). That residual is why
Perf 4 looks at the fog.

## Perf 4: the fog setters (`perf-fog-setters`, Mac, Oct 17 2026)

`ASailingEnvironment::UpdateHaze` set every `UExponentialHeightFogComponent` value every frame. Each setter marks the
fog's render state dirty when its value changes, and the fog's scene proxy is then rebuilt. The inscattering colour
follows `HazeLight` (the metered light, new every frame) and the density follows the visibility, so the fog was rebuilt
every frame. Now density, height falloff, inscattering colour, max opacity, the cinematic glow colour, volumetric
extinction scale and volumetric distance move in steps of 3% of their value. They snap exactly to their lerp ends (dry,
full rain) and to zero. The constant setters (albedo, scattering distribution) were already no-ops after the first
frame.

Both builds are on main d6cf6476 (#110 and #113 merged; #114 is docs only), packaged as Development. Same arguments as
above, parked on the buoy, 20 min each, one after the other:

| | main d6cf6476 | fog steps | change |
|---|---|---|---|
| fps (bench.json, 1200 s) | 55.3 | 55.5 | +0.2, noise |
| p99 ms | 20.55 | 20.44 | -0.1 |
| first / last 10 min fps | 55.3 / 55.3 | 55.5 / 55.6 | |
| first / last 10 min p99 ms | 20.48 / 20.66 | 20.39 / 20.56 | |
| p99 drift (`soak_stats.py`) | +2.0 ms/h | +2.5 ms/h | both noise over 20 min |
| GPU ms (CSV mean) | 17.52 | 17.43 | -0.1 |
| game / render / RHI thread ms | 2.35 / 18.09 / 3.80 | 2.33 / 18.00 / 4.03 | |
| VSM pages cleared per frame | 973, flat | 973, flat | none |
| VSM non-Nanite instances drawn | 93 | 93 | |
| RSS growth after 5 min | +1317 MB/h | +1290 MB/h | soak 3's Metal leak |

**No gain on the Mac.** The fog steps change nothing measurable here. The fog proxy rebuild is cheap on Metal, and on
this parked scene the per-frame work is elsewhere. The change is still right in principle and costs nothing, so the
PC's render-thread residual is where it can show (D3D12 re-creates the proxy on the render thread).

**Why this run reads 973 pages and #110's read 100.** Main parked reads 973 pages cleared a frame, the same as the
pre-#110 parked baseline (974). Two 5-minute probes, unparked, with the #110 run's arguments minus `-SailingMooring`:

| unparked, 5 min | fps | p99 ms | GPU ms | VSM pages cleared per frame, by minute |
|---|---|---|---|---|
| main d6cf6476 | 58.3 | 20.02 | 16.58 | 698, 368, 247, 422, 429 |
| main with 9efbc9b3 reverted | 58.2 | 19.74 | 16.61 | 726, 369, 247, 422, 427 |

With and without the sun steps the unparked runs match frame for frame. So on Metal, #110 changes nothing either, and
its earlier "974 to 100" came from the scene. Parked on the buoy, the virtual shadow map clears about 970 pages every
frame and runs about 3 fps slower than unparked. Something about the parked boat (head to wind, sails up, the mooring line)
keeps the cache from settling. That is a separate lead, not this fix.

**Stills** (High, uncooked, `perf-fog-setters/`, main on the left): helm-eye mean luminance 129.9 against 127.1, mean
difference 6.5 of 255. That is a cloud shadow crossing the deck between runs: a second run of the fix differs from the
first by 7.9, and the horizon haze band reads 123.5 (main) against 119.8 and 124.2 (the two fix runs). Storm: 63.5
against 63.7, difference 0.7. The deck's gloom and haze look the same.

**Tests:** `SailingSim.Visual` 32/32, `SailingSim.Smoke` 16/16.

Files (`soak/`): `fog-setters-{main,fix}-2026-10-17.{frames-1hz.csv,mem.csv,csv-2min.txt}`, and the unparked probes'
CSV-profile means by minute, `unmoored-{main,pre110}-2026-10-17.csv-1min.txt`.

The PC's D3D12 soak of the fog steps (main 0059ea12): `perf-fog-setters-pc-2026-10-17.md` (render-thread drift +1.66 to +0.50 ms/h).

## The parked hour (Mac, main 0059ea12, Oct 17 2026)

One hour parked on the buoy on High, the build packaged at 08:06 from the fog-setters code (the same code as main
0059ea12), started straight after Perf 4. Same arguments as the 20-minute runs above, except `-csvCaptureFrames=400000`,
the profile stopped at 3595 s, and no `-ExecCmds=ToggleDrawEvents`:

    SHOT=soak-hour ARGS="-SailingQuality=High -SailingKeepStart -SailingMooring -SailingBenchTrace \
      -csvCategories=VSM -csvCaptureFrames=400000 -SailingExecAt=3595:CsvProfile+Stop" scripts/bench-mac.sh 3600

bench.json over 3600 s: 54.7 fps, p99 21.37 ms, GPU 17.72 ms, game thread 2.42 ms, RHI thread 3.55 ms.

| 10-min window | fps | p99 ms | GPU ms (CSV) | VSM pages cleared / frame | dynamic pages invalidated / frame | non-Nanite instances drawn |
|---|---|---|---|---|---|---|
| 0-10 | 54.7 | 20.59 | 17.73 | 989 | 1130 | 93 |
| 10-20 | 54.7 | 20.80 | 17.70 | 958 | 1107 | 93 |
| 20-30 | 54.4 | 22.34 | 17.82 | 990 | 1013 | 95 |
| 30-40 | 54.9 | 20.30 | 17.64 | 912 | 1063 | 93 |
| 40-50 | 54.5 | 22.68 | 17.78 | 928 | 974 | 95 |
| 50-60 | 54.9 | 20.40 | 17.67 | 868 | 991 | 94 |

- **No frame-time drift over the hour.** The per-minute p99 fits to +0.12 ms/h (61 minutes), against +2.0 to +2.8 ms/h
  read from the 20-minute runs: those were noise, as suspected. The two 22 ms windows are bumps, not a trend; the
  first and last 10 minutes read 20.59 and 20.40 ms. Only 2 frames over 33.3 ms after the warm-up: 59 ms at 3595 s, when the CSV
  profile stops, and the 190 ms worst at 3602 s, after the measured hour (the screenshot).
- **The parked cache never settles.** Parked, the virtual shadow map clears 941 pages a frame over the hour (989 in the
  first 10 minutes, 868 in the last), against 250 to 430 unparked after the first minute (the Perf 4 probes). The slow
  fall goes with the dynamic invalidations (1130 to 991). So the parked penalty (about 3 fps, about 1 ms of GPU) holds
  for the whole hour; it is not a warm-up effect. The caster is still to be named (item 2 of the brief).
- **RSS grew +3405 MB/h** after 5 min (2365 to 5776 MB), 57 MB a minute, steady. That is 2.6 times the +1290 to
  +1390 MB/h of every 20-minute parked run today. This run ran without `-ExecCmds=ToggleDrawEvents`, so the Development
  build's draw events were on, and those leak about 2 GB/h on Metal on their own (`mac-soak-medium-2026-10-16.md`: an
  encoder-label string autoreleased per encoder on the parallel RHI-translate workers, with no pool; Shipping and Test
  have draw events off). 1.3 GB/h of the known Metal growth plus 2 GB/h of draw events accounts for it; the longer CSV
  capture streams to disk (406 MB file, 2.1 KB a frame like the shorter runs) and is not suspected. Lesson repeated:
  every Development soak on the Mac takes `-ExecCmds=ToggleDrawEvents`.

Files (`soak/`): `parked-hour-2026-10-17.{bench.json,frames-1hz.csv,mem.csv,csv-10min.txt}`. The full CSV profile
(406 MB) stays in the sandbox (`Saved/Profiling/CSV/Profile(20261017_080655).csv`).

### Who keeps the parked cache busy (5-minute probes, High)

The Development package from the #115 gate run (main plus the Shipping guards, which change nothing in Development),
parked with the hour's arguments for 300 s, one run after another:

| parked, 5 min | fps | p99 ms | GPU ms | VSM pages cleared / frame, by minute | mean | dynamic invalidated |
|---|---|---|---|---|---|---|
| `-SailingMooring` | 54.8 | 20.53 | 17.67 | 1040, 976, 966, 994, 995 | 994 | 1146 |
| + `-SailingCrewStill` | 55.2 | 20.44 | 17.53 | 1045, 978, 966, 992, 997 | 996 | 1144 |
| + `-SailingNoCrewClips` | 55.4 | 20.34 | 17.48 | 1043, 978, 966, 994, 996 | 995 | 1144 |

**Not the crew.** Stilling the crew or dropping their idle clips leaves the cleared pages the same to within a few pages
in every minute. The per-minute pattern repeats from run to run, so whatever clears the pages is the deterministic
parked boat itself: the hull on its mooring and the sails. The 0.2 to 0.6 fps gains are crew CPU and GPU, not shadows.
There is no argument that lowers the sails (`-SailingMooring` parks head to wind with them up), so that probe was
skipped. Head to wind, the cloth flogs every frame (`FSailCloth` on High), and the sails are the largest moving casters
over the cockpit. That is the next suspect. A `-SailingSailsDown` switch (or parking at a TWA where the sails fill) would
settle it.

Files (`soak/`): `vsm-probe-{parked,crewstill,noclips}-2026-10-17.csv-1min.txt`.
