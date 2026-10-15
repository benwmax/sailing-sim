# W5b: storms with measured numbers, rain curtains, real weather days

The weather half of W5 (the PC does the cloud half). The thunderstorm's wind, cold and rain now come from published
models and measured numbers. The rain falls as its own curtains, with a rain foot over the water. A real day can replace
a preset: its timeline comes from NOAA's HRRR model analyses, and a storm on it is replayed from MRMS radar and the
stations' reports.

![The gust front closing in: the shelf cloud, rain curtains behind it](gustfront.png)

## The storm (`Storm.h`, `Wind.h` `FGustFront`, `Weather.cpp`)

**Microburst.** `FMicroburst` is Vicroy's analytic axisymmetric model (NASA TM-104053, 1991). It refines Oseguera and
Bowles (NASA TM-100632, 1988) and is what flight simulators use for wind shear:

- u_r = λ r / 2 · [e^(c1 z/zm) − e^(c2 z/zm)] · e^((2 − (r/rp)^2α) / 2α)
- w = −λ {zm/c1 [e^(c1 z/zm) − 1] − zm/c2 [e^(c2 z/zm) − 1]} · [1 − (r/rp)^2α / 2] · e^(...)
- c1 = −0.22, c2 = −2.75 (z*/ε = 12.5), α = 2, and λ is chosen so the outflow peaks at um on the ring r = rp at height zm.

It conserves mass, and an updraft ring sits beyond rp·2^(1/2α). It rides in the rain core on the storm's axis, 1.5 km
behind the front, and bursts as the front nears the start. The preset's is a moderate wet microburst: 10 m/s at 50 m on
a ring 1.2 km across, about 5 m/s at 10 m.

**Cold pool and gust front.** The outflow is a density current (Benjamin 1968; Charba 1974; Wakimoto 1982):

- **Front speed:** c = 0.75 √(g h ΔT/T) + 0.6 × the ambient wind along the track. The preset's 6 °C, 1.4 km deep pool
  under a 33 °C afternoon, against a 10 kn southerly, gives 11.25 m/s (it was a fixed 12).
- **Wind behind the head:** 1.2 × the front's speed, plus gusts. They peak near 1.5 × the front, which is what Goff
  (1976) measured.
- **Temperature drop:** the pool's ΔT, which lingers after the outflow eases. The stability over the water uses it.
- **What stayed the same:** `FGustFront::DistanceAhead` keeps its meaning, so the shelf cloud, rain core and anvil (the
  cloud material, `FStormShape`) follow the front as before.

At the start, the 10 m wind goes from 5 m/s ahead of the front to 21 m/s behind it (a jump of 16 m/s), and the air
drops 6 °C. The mean outflow is 26 kn, with gusts to 47 kn.

**Rain.** `FStormRain` is the rate in mm/h along the front's track:

- It hangs from the core 700 m behind the front aloft.
- Near the water the outflow sweeps it forward into a rain foot, so the curtain's edge slants forward toward the
  surface: 300 m e^(−z/180 m).
- It is heaviest just inside the edge: 80 mm/h, the core of a strong Texas storm.
- It tapers into trailing rain and ends at the storm's lateral extent (the weather map's storm channel).
- The rain reaches the start about half a minute after the front.

The weather's `Rain`, the visibility, the water's rain rings, the deck and the sound are now the boat's local rain, not
a global value.

## Rain curtains (`ASailingEnvironment::UpdateRainCurtains`, `M_RainCurtain`)

The storm's rain seen from afar is its own geometry, not a density in the cloud march:

- **Placement:** twice a second, the rain field (the storm's, or a real day's radar) is sampled on a world grid of 2 km
  cells within 26 km of the camera. The rainiest, nearest cells get a curtain (32; 16 on Low). The cells stay put in the
  world, so the curtains don't swim as the camera moves.
- **Curtains:** each is a lit translucent card facing the camera (forward-shaded, so the sun and sky light it by day and
  night). It runs from the core's base (750 m) to the water: veils a few hundred metres apart with finer striations,
  slanted a little by the shear, denser toward the water, and on the earth's curvature.
- **Rain foot:** a low, wide card of spray and mist on the water, set 300 m ahead toward where the storm is going. It
  shows in heavy rain.
- **Near the boat:** within 2.5 km the curtains fade, and the existing rain cylinders and lens drops follow the rain at
  the camera.

| Without curtains (the cloud material's rain only) | With them |
|---|---|
| ![](curtains-off.png) | ![](curtains-on.png) |

![Rain curtains from the boat 2 minutes before the front](curtains.png)

The cloud material's own rain term (`dRain` in `CLOUD_CODE`, owned by the PC) is still drawn. The PC can drop it now:
`FrontB.z` drives the storm's core and anvil as well, so it can't be switched off from C++ alone.

## Real days (`WeatherDay.h`, `Tools/weather`)

```
Tools/venv/bin/pip install -r Tools/weather/requirements.txt
Tools/venv/bin/python Tools/weather/fetch_day.py 2023-06-11 --storm 16:30-20:30
Tools/venv/bin/python Tools/weather/bake_day.py 2023-06-11 "Summer afternoon thunderstorm (11 June 2023)"
Tools/venv/bin/python Tools/weather/plot_days.py
```

- **Fetch** (free, anonymous; the raw data goes to `Data/Weather/raw/<date>`, git-ignored, about 1 MB a day):
  - HRRR analyses from AWS (`noaa-hrrr-bdp-pds`), every hour of the local day. Only the needed GRIB messages are read,
    by byte ranges from each file's `.idx`: 10 and 80 m wind, gust, 2 m temperature and dew point, boundary-layer
    height, CAPE, low, middle and high cloud, cloud base, rain rate, visibility. They are decoded with eccodes and
    cropped to 60 km round the lake.
  - MRMS precipitation rate from AWS (`noaa-mrms-pds`), every 4 minutes over the storm window, cropped to 128 km.
  - ASOS reports from Iowa Environmental Mesonet (Mesquite, Love Field, Terrell).
- **Bake** (`Content/TerrainData/Weather/<date>.wxday`, staged with TerrainData):
  - **Hourly timeline:** the mean of the HRRR points within 5 km of the map origin. HRRR's 3 km grid doesn't resolve
    the lake's surface, so the water temperature is W1's monthly normal.
  - **Storm fit:**
    - motion: the shift that best maps each radar frame onto the next, median over the storm;
    - arrival: when the rain's edge reaches the origin, less the front's lead over it;
    - cold pool: the largest temperature drop at a station, and its depth from the density current's speed;
    - microburst: what the cold pool's flow leaves of the peak gust;
    - peak rain, and how long it rained hard (the preset's timeline after the front is stretched to match).
  - **Radar:** rain rate on 64 × 64 cells of 2 km, frame by frame.
- **In the game:**
  - The hour drives the wind speed and direction, the gustiness (W1's station calibration scaled by HRRR's own gust
    ratio), the stability (air over the water), the mixed layer, clouds by layer, haze from the dew point, rain and
    visibility.
  - A storm runs the preset's storm with its own fitted front, cold pool and burst. It reaches the start when it reached
    the lake (the replay is anchored at the start, as the preset is), and it rains where the radar saw rain.
  - The front end's Conditions screen has a Real day row (Lake Ray Hubbard only). `-SailingDay=YYYY-MM-DD` loads one
    (its suggested start hour unless `-SailingHour` is given).

| Day | What it is | Fitted |
|---|---|---|
| 2023-06-11 | Summer afternoon thunderstorm: a band of cells growing south-west of the lake crossed it at 18:57 | toward 103° at 6.7 m/s; 6.1 °C cold pool (Love Field, 11 °F in under 45 minutes), 567 m deep; peak gust 41 kn; burst 17 m/s; 52 mm/h (122 mm/h peak frame); hard rain about 1 h |
| 2023-11-20 | Fall norther | south 5–10 kn in the morning, veering through west to 342° at 15 kn gusting 27 by evening; 7 °C colder |
| 2025-09-16 | Calm late-summer day | 1–4 kn, clear, a 2 km mixed layer by late afternoon |

![The three days' timelines](timeline.png)

![The storm's radar replay](radar.png)

![The real storm arriving, 18:48 on 11 June 2023](realday.png)

![The Conditions screen's Real day row](conditions.png)

## Tests

- `SailingSim.Physics.MicroburstVicroy`: peak um at (rp, zm) found by search, z*/ε = 12.5, continuity to 2·10⁻⁴ of
  um/rp (the finite difference's error), the downdraft and the updraft ring.
- `SailingSim.Physics.GustFrontColdPool`: front speed 8 to 16 m/s and rising with the pool's coldness and depth; a wind
  jump of 10 to 20 m/s (16); a temperature drop of 3 to 8 °C (6); the burst blowing out of the core; `DistanceAhead`
  unchanged.
- `SailingSim.Physics.RainFootAheadOfCore`: the edge 300 m further forward at the water than at the cloud base; rain
  under the foot, none aloft there; 50 to 100 mm/h; none ahead of the front or beyond the storm; at the start the rain
  comes half a minute after the front.
- `SailingSim.Weather.RealDays`: the three days load and drive the wind, the mixed layer and the cirrus. The norther
  veers and cools. The storm's front reaches a moved start at the real arrival, the radar rains there within the hour,
  the sky darkens and lightning strikes.
- `SailingSim.Weather.StormDeterminism`: the preset storm and the real day give the same wind, rain, temperature and
  lightning, evaluated in any order and from a fresh load.
- `SailingSim.Weather.ThunderstormSequence` changed: gusts 30 to 50 kn (were 25 to 40: the microburst and the measured
  outflow), and rain 15 s or more after the front (was 30: the rain foot).

## Cost

**The storm view against main.** `scripts/bench-mac.sh 12` with bench-visual's storm view (inside the rain, 50 s after
the front), packaged Development, main 59f1d50 and this branch the same evening, two runs each:

| Tier | main fps | main GPU ms | W5b fps | W5b GPU ms |
|---|---|---|---|---|
| Medium | 67.8, 69.4 | 15.37, 14.28 | 68.7, 68.5 | 14.08, 14.35 |
| High | 47.9, 49.0 | 18.76, 19.64 | 49.2, 50.1 | 18.66, 18.55 |

The GPU time is no higher than main's. Looking at the storm from outside it with the curtains up (`run-game.sh`, High,
uncooked), 22.48 ms with them against 22.88 without: within the noise. There are at most 64 cards, forward-lit, and
cheap per pixel.

**All views.** `scripts/bench-visual.sh 12 w5b Medium High` (`visual-bench-w5b.csv`, with the GPU slices). Gate: Medium
60 and High 45. Every view passes. The tightest is the slip on High at 45.6 (47.0 on the W1 bench); it uses no weather
code changed here.

| View | Tier | fps | p99 ms | GPU ms |
|---|---|---|---|---|
| beam8 | Medium | 92.5 | 11.54 | 10.7 |
| beam8 | High | 56.8 | 19.57 | 15.53 |
| beat15 | Medium | 90.0 | 12.12 | 10.72 |
| beat15 | High | 53.6 | 22.41 | 18.38 |
| storm | Medium | 68.5 | 16.52 | 14.62 |
| storm | High | 48.7 | 23.7 | 19.82 |
| marina | Medium | 88.4 | 12.48 | 11.49 |
| marina | High | 51.5 | 21.51 | 17.9 |
| coast-day | Medium | 86.6 | 12.24 | 11.37 |
| coast-day | High | 50.3 | 21.12 | 16.04 |
| coast-night | Medium | 99.2 | 11.07 | 9.3 |
| coast-night | High | 51.6 | 21.05 | 13.98 |
| gulf-sea | Medium | 107.3 | 9.86 | 9.24 |
| gulf-sea | High | 58.8 | 18.23 | 14.26 |
| helm-eye | Medium | 89.7 | 12.2 | 11.17 |
| helm-eye | High | 52.6 | 20.89 | 18.11 |
| slip | Medium | 70.6 | 16.24 | 14.01 |
| slip | High | 45.6 | 24.81 | 22.54 |
| bridge | Medium | 95.0 | 11.23 | 10.01 |
| bridge | High | 54.3 | 19.86 | 15.28 |
| crew | Medium | 118.6 | 8.53 | 7.73 |
| crew | High | 66.7 | 16.09 | 13.16 |
| marina-night | Medium | 88.9 | 12.95 | 11.42 |
| marina-night | High | 58.0 | 19.4 | 16.45 |

## Skipped or changed, and why

- **Rain term in the cloud material:** the rain curtains replace the cloud's rain as the storm's rain from afar, but its
  `dRain` term is still drawn. CLOUD_CODE is the PC's to change.
- **Lake water temperature:** taken from W1's monthly normals. HRRR doesn't resolve the lake.
- **ASOS:** added to HRRR and MRMS for the storm's arrival, temperature drop and peak gust, which hourly analyses smear.
- **The front is a straight line** that keeps the cloud material's frame, so a real storm's front is fitted (direction,
  speed, arrival) rather than traced from the radar. Its rain is the radar's.
- **Real days are for Lake Ray Hubbard only.** Galveston would need its own bake.
- **Thunderstorm preset microburst:** 10 m/s rather than a severe 20+, which would put gusts past 50 kn.
- **Data formats:** HRRR's 3 km grid gives the lake's wind as the mean of the points round it. MRMS frames are kept at
  2 km (a few hundred KB a day) rather than 1 km.
