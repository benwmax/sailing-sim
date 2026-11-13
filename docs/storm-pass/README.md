# Storm pass (feedback #21, #24)

Two in-game reports from the Nov 13 2026 playtest on a Thunderstorm day: the sea looked too smooth for a storm, and the
storm's colour and effects felt dull.

## The sea follows the storm's own wind (#21)

What the report showed: it was sent 91 s into the session, with the gust front due at the start at 150 s
(`FWeatherSystem::kFrontArrives`). The wind at the boat was the 12 kn breeze ahead of the storm, so the sea was a 12 kn
sea. That part is how a lake behaves: the outflow's waves travel at their group speed (2 to 4 m/s for the lake's 3 to 5 s
chop), far slower than the front (11 m/s), so they cannot run ahead of it.

What was wrong behind the front: `ASailingGameMode::UpdateWeather` switched the sea to the bare outflow (26 kn) once the
front had passed and back to the breeze the moment the outflow began to decay (a step from 26 to 10 kn at 420 s), and it
never saw the microburst. Now `FGustFront::SeaWindAt` gives the sea the mean 10 m wind the boat is in: the breeze ahead,
blended into the outflow plus the burst across the leading edge (`Behind`), and eased back out over the decay. On the
preset storm at the start (standalone run, seed 11):

| weather time (s) | 100 | 150 | 175 | 200 | 250 | 300 | 350 | 400 | 450 | 500 | 550 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| breeze (kn) | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 | 9.6 | 8.2 | 7.0 |
| sea wind before (kn) | 10.0 | ~10-26 | 26.2 | 26.2 | 26.2 | 26.2 | 26.2 | 26.2 | 9.6 | 8.2 | 7.0 |
| sea wind now (kn) | 10.0 | 14.4 | 34.2 | 35.2 | 30.2 | 24.2 | 18.5 | 16.4 | 18.3 | 12.5 | 7.0 |

The peak of 35 kn just behind the front is the burst's ring passing; its far side blows back against the outflow, so
the sea wind dips a little before the decay. The sea grows to it over `FWaveField::GrowthSeconds` as before. The gale
spray and spindrift (`AWaterSurface::GaleSprayFor`) read the same wind, so in the burst they now start.

Bean's choice (Nov 13 2026, "real sea, storm arrives sooner"): a played storm day now starts 30 s before the front
reaches the boat (`FWeatherSystem::kSessionStormLead`, `SessionStartTime`: weather time 120 instead of 0), with the shelf
337 m off and the gloom already in. The game applies it when no `-SailingWeatherTime` is given, on the preset's own storm
(not a real day, a scene, or `-SailingStormDelay`); every bench, capture and loudness view passes `-SailingWeatherTime`,
so their timing is unchanged. Strikes before the start are skipped as before (`ASailingEnvironment::BeginPlay`).

Test: `SailingSim.Weather.StormSeaFollowsTheStormWind` (the sea wind and the session start).

## The storm grade (#24)

Under a storm deck the grade was saturation 0.3 and the cinematic LUT faded to 0.4, nothing else: grey and flat. The
Phase 8 blind test's reason for the grey stands (the light under the deck is not blue), so the scene stays grey, but
`StormGradeFor` (`VisualPipeline.h`) now keeps more of the colour (0.4), steepens the middle (contrast 1.18), puts a
slate cast in the shadows (`ColorGainShadows` 0.91, 1.0, 1.07) and, gentler, the middle (`ColorGainMidtones` 0.95, 0.99,
1.04), so whites stay white, and darkens the frame's edges (vignette 0.6). Lightning's flash light is 22 (was 14).

Round 2 (Bean, Nov 13 2026, on the first stills in `inputs:storm-grade-677/`: "too sepia"): the first grade kept the
cinematic LUT at 0.65 under the deck, and its warm highlights turned the lake's brown water sepia. The LUT now fades to
0.4 as before, the white balance is 450 K cooler under a day deck (`WhiteTempOffset`), and the slate cast reaches the
midtones.

`-SailingClassicStormGrade` gives the old grade and flash for compared stills. Test: `SailingSim.Visual.StormGrade`.

## Not in this pass

- The near whitecaps in the 30 kn report read as flat, crackled plates (the foam texture in `M_WaterV4`): a
  `make_materials.py` change with a Mac rebuild, left for a follow-up.
- The long-wave FFT storm sea (branch `long-wave-fft-2`) stays after the slice.
