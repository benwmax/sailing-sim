# Session weather: honest gusts, a held wind, the storm day's label (Nov 11 2026)

From the physics and weather review of Nov 11 2026 (findings 1, 4 and 5). Bean's calls: gusts "you choose", the July
storm day "reword", the wind drift "fix to hold".

## Gusts match the label

A session's "10 gusting 13" was read as the weather stations' gust factor (a minute's 5-second peak over the 2-minute
mean), and the puffs were scaled up to 3 times on top. A sailor reads it as the strongest gust they will meet. Measured
that way (the highest 3-second wind in each ten minutes over that ten minutes' mean, near the shore where the open
water does not ease the gusts), the days delivered far more than their labels.

The label now means the top of the usual gusts, as a forecast's gust does: nine ten-minute stretches in ten top out at
or under it, the average stretch a little under it, and the rare strongest about 10 % past it.
`Sailing::SailorGustScale` (`WindClimate.h`) scales the day's calibrated gustiness (fine turbulence and puffs together,
so a day keeps its own mix of quick gusts and slow puffs) to hit that; `ASailingGameMode` computes the scale once when
the weather is set (`GustLabelScale`, next to `WindScale`). Easy still halves the variability after it.

| Day | Label | Before: usual strongest / worst | Now: average / 9 in 10 / worst | Easy now (9 in 10 / worst) |
|---|---|---|---|---|
| Lesson day | 10 gusting 13 | 20 / 25 kn | 12.2 / 13.0 / 14.2 kn | 11.5 / 12.1 |
| Fair breeze | 15 gusting 20 | 27 / 34 kn | 18.9 / 20.4 / 22.1 kn | 17.7 / 18.6 |
| Blue norther | 20 gusting 28 | 39 / 50-54 kn | 26.1 / 28.7 / 32.0 kn | 24.4 / 26.1 |
| July afternoon (before the storm) | 12 gusting 20 | | 17.7 / 19.5 / 22.1 kn | 15.8 / 17.1 |

"Before" is the review's measurement (it includes the wind drift below). `scripts/gust-check.sh` builds the physics
standalone and prints this table for six days (needs the real `Content/TerrainData/Wind.mann`, not its LFS stub);
`SailingSim.Physics.WindSailorGusts` holds two of them. The command line's `-SailingGust=` (reference captures) and the
prologue's stand-in keep the stations' meaning (`GustIntensityForFactor`), as do real days (their own analysis).

The peak constant (`kSailorPeak` 3.55 combined standard deviations for the 9-in-10 gust) was fitted over Fair in April,
July and November, the July afternoon, Overcast in November and January and Rain, at 0.6 to 1.6 times the calibrated
gustiness: 3.2 to 3.9. A storm's gust front has its own outflow gusts and is not scaled.

Known limits (QA, Nov 11): the scale is set once at the start, so as the clock moves the day's calibrated gustiness
drifts it a little (the norther's 9-in-10 gust 27.8 to 29.7 kn over three hours, the lesson 12.9 to 13.5). Light air
reads under its label (the glassy morning's "2 gusting 4" tops out near 3.2; it was 5.7), outside the fit. On the July
storm day the label holds until the front; behind it the gentler 7 kn outflow is gustier by nature (about 18 kn, it was
22.6). `SailingSim.Physics.WindSailorGusts` tests the mapping, not the game mode's wiring of it.

## The chosen wind holds

The calm-morning and afternoon-breeze presets multiply the wind by the lake's daily cycle (`Diurnal` in `Weather.cpp`);
the session scaled the start to the chosen wind and then let it build: a 10 kn lesson at 10:00 was 13.9 kn at 11:00 and
18.5 by noon, a "Live from today" session at 7 am up to 2.86 times the chosen wind. `FWeatherSystem::SetHoldWind` keeps
the start hour's breeze; the game holds it whenever the wind is chosen (every front-end session and `-SailingWind=`).
Clouds, air temperature and the gusts' calibration still follow the clock. Real days keep their own hourly wind.

## The July storm day says what it does

"Typical July afternoon, storms after 4 pm" started at 14:30 and met the storm's gust front 150 s in
(`FWeatherSystem::kFrontArrives`), gone by about ten minutes. The timing stays; the preset is now "July afternoon storm,
12 kn SSE · storm arriving in minutes", and the Conditions screen's "What to expect" says the storm arrives within
minutes with 40 kn or more and clears in about ten (a real day's storm still says it comes when it did that day).
