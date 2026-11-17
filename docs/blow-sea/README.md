# Blow sea (feedback #27)

The report (sailing-feedback #27, build 40226d1c, Ultra, J/22, Ray Hubbard north of Rush Creek below the SH-66
causeway): a thunderstorm at 26 kn gusting 36 from about 158 deg, and the sea "small, grey and bland", not matching how
hard the boat was slamming. The tester has sailed the lake in 20 kn+ gusts and saw bigger, more defined waves.

## What the sea was

Standalone (SailingPhysics, `RayHubbard.height`), at the report's spot (north 8917 m, east 240 m), 26 kn from 157.5 deg:

| | fetch | Hs | biggest of ~600 waves | peak period |
|---|---|---|---|---|
| game before (SWAN-fitted laws, Saville's effective fetch) | 1.76 km | 0.43 m (1.4 ft) | 0.72 m | 2.27 s |
| SWAN bake at the nearest point (28 kn, 157.5 deg) | | 0.47 m | | 2.45 s |
| CEM straight-line fetch (the reference checks' method) | 2.68 km | 0.53 m (1.7 ft) | | |
| game now | 1.76 km | 0.53 m (1.7 ft) | 0.82 m | 2.47 s |

The sea already followed the SWAN bake of the lake within 10% (`SailingSim.Physics.WaveGrowthSwan`), and it was
already as steep as young chop gets (Hs over the peak wavelength 0.054). So the fitted laws stay as they are; the game
builds the sea in a stronger wind once it blows.

## The change

`FWaveField::BlowSeaKnots(mean knots, lift)`: below 20 kn the wind itself; from 20 kn it rises by the lift (0.15) over
8 kn on a smoothstep and holds it. `ASailingGameMode::UpdateWeather` hands the lifted wind to `FWaveField::SetWind` and the
sea map (after the Gulf's FFT ocean, which keeps its own wind). Everything that reads the sea's wind follows from that
one number: the long waves' height and period (the boat floats on the same field the renderer draws, so her motion and
the visible sea grow together), the short waves (`FWaveDetail`), the whitecap target (Monahan, U^3.41), the far cap
sprites and the gale spray.

At the report's spot, 26 kn from 157.5 deg (standalone; `SailingSim.Physics.BlowSea` holds the 26 kn row):

| wind (kn) | sea built in (kn) | Hs before -> now (m) | Tp (s) | Hs / peak wavelength | caps | CEM straight (m) |
|---|---|---|---|---|---|---|
| 20 | 20.0 | 0.28 -> 0.28 | 1.89 | 0.050 | x1.00 | 0.35 |
| 22 | 22.5 | 0.33 -> 0.34 | 2.02 -> 2.05 | 0.052 | x1.08 | 0.40 |
| 24 | 25.8 | 0.38 -> 0.43 | 2.15 -> 2.26 | 0.053 -> 0.054 | x1.28 | 0.47 |
| 26 | 29.3 | 0.43 -> 0.53 | 2.27 -> 2.47 | 0.054 -> 0.055 | x1.50 | 0.53 |
| 28 | 32.2 | 0.49 -> 0.62 | 2.39 -> 2.64 | 0.055 -> 0.057 | x1.61 | 0.60 |
| 30 | 34.5 | 0.55 -> 0.69 | 2.51 -> 2.77 | 0.056 -> 0.058 | x1.61 | 0.68 |
| 35 | 40.2 | 0.71 -> 0.89 | 2.80 -> 3.09 | 0.058 -> 0.060 | x1.61 | 0.87 |

From 26 kn up the sea at that spot now stands where the CEM's straight-line fetch puts it; below 24 kn it stays under it.

Why a stronger wind rather than a bigger height: the sea stays the sea of some real wind (height, period and caps
agree, by Toba's law a little steeper as a harder blow's chop is), and nothing the polars, reference checks, sea trials or
SWAN tests use changes (they never call it). The reasons it is fair: a gusty blow's sea answers the wind's stress (U^2),
which its gusts raise past the mean's; and the bake ran a steady wind over Saville's fetch, which on a narrow lake is the
shorter of the two textbook methods. It is still a choice for the look and feel, tuned to sailors' reports, and Bean's
call.

## Comparing

`-SailingClassicBlowSea` (or `-SailingBlowSea=0`) is the old sea; `-SailingBlowSea=<lift>` tries another (0 to 0.5).
Repro: `-SailingWorld=ray-hubbard -SailingBoat=J22 "-SailingStartAt=8917,240,137" -SailingWeather=Thunderstorm
-SailingWind=26 -SailingWindFrom=158`.

Test: `SailingSim.Physics.BlowSea`.

## Not in this pass

- The storm grade (#677) and the cap look (#703) are as Bean approved them; this pass only changes how big the sea is.
- The boat already floats on the long waves the renderer draws (the same `FWaveField`); the drawn surface's Gerstner
  shift (choppiness 1.5) and the FFT short waves are not in her hull's sampling, as before.
