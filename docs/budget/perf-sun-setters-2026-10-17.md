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
