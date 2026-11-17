# Blow sea (feedback #27)

The report (sailing-feedback #27, build 40226d1c, Ultra, J/22, Ray Hubbard north of Rush Creek below the SH-66
causeway): a thunderstorm at 26 kn gusting 36 from about 158 deg, and the sea "small, grey and bland", not matching how
hard the boat was slamming. The tester has sailed the lake in 20 kn+ gusts and saw bigger, more defined waves.

## What the sea was

Standalone (SailingPhysics, `RayHubbard.height`), at the report's spot (north 8917 m, east 240 m), 26 kn from 157.5 deg:

| | fetch | Hs | peak period |
|---|---|---|---|
| game before (SWAN-fitted laws over Saville's effective fetch) | 1.76 km | 0.43 m (1.4 ft) | 2.27 s |
| SWAN bake at the nearest point, 28 kn (no 26 kn case) | | 0.47 m | 2.45 s |
| the game's own law over the straight-line fetch | 2.68 km | 0.53 m (1.7 ft) | |
| textbook formulas over the straight-line fetch (QA's check): CEM 2002 / SPM 1984 with U_A | 2.68 km | 0.36 / 0.46 m | |
| game now | 1.76 km | 0.53 m (1.7 ft) | 2.47 s |

The sea already followed the SWAN bake of the lake within 10% (`SailingSim.Physics.WaveGrowthSwan`), and it was already
as steep as young chop gets (Hs over the peak wavelength 0.054). The textbook formulas don't call for a bigger sea
either. So this is a look and feel choice, tuned to what sailors report seeing on the lake in a blow, for Bean to judge
on stills, not a correction the wave models ask for. The fitted laws stay as they are; the game builds the sea in a
stronger wind once it blows.

## The change

`FWaveField::BlowSeaKnots(mean knots, lift)`: below 20 kn the wind itself; from 20 kn it rises by the lift (0.15) over
8 kn on a smoothstep and holds it. `ASailingGameMode::UpdateWeather` hands the lifted wind to `FWaveField::SetWind` and the
sea map, and keeps the air's own wind beside it (`FWaveParams::AirKnots`). Offshore (the Gulf, the prologue's gale) nothing is
lifted: the FFT ocean is the sea there; the lift fades out across the ocean mask's 0.3 to 0.7 band at the boat, so a
harbour mouth has no step.

What follows the sea's (lifted) wind: the long waves' height and period (the boat floats on the same field the renderer
draws, so her motion, added resistance, the HUD's and the logbook's wave height and the visible sea grow together; AI
boats slow a little more above 20 kn), the short waves (`FWaveDetail`), the whitecap target (Monahan, U^3.41: x1.5 at
26 kn) and the far cap sprites (their cover from the wind maps times the same ratio).

What keeps the air's wind (`AirWindKnots`): `WindParams.z`, against which the water materials read the wind maps' gusts
(the cap gain, the chop's calm and the dark puff patches; lifting it would have cancelled the extra caps and paled the
gusts), and the gale spray's onsets (torn crests 22, gale spray 24, spindrift 33 kn, as the storm look, #703, tuned them).

Left as is: `M_WaterV4`'s far roughness term (Cox-Munk slopes standing in for the waves the mesh can't draw) reads
`WindParams.z`, the air's wind, while the near short waves are built in the sea's: past the near detail the glint is
about 10% smoother than the near water's at 26 kn. Changing it is a `make_materials.py` edit.

At the report's spot, 26 kn from 157.5 deg (standalone; `SailingSim.Physics.BlowSea` holds the 26 kn row):

| wind (kn) | sea built in (kn) | Hs before -> now (m) | Tp (s) | Hs / peak wavelength | cap target |
|---|---|---|---|---|---|
| 20 | 20.0 | 0.28 -> 0.28 | 1.89 | 0.050 | x1.00 |
| 22 | 22.5 | 0.33 -> 0.34 | 2.02 -> 2.05 | 0.052 | x1.08 |
| 24 | 25.8 | 0.38 -> 0.43 | 2.15 -> 2.26 | 0.053 -> 0.054 | x1.28 |
| 26 | 29.3 | 0.43 -> 0.53 | 2.27 -> 2.47 | 0.054 -> 0.055 | x1.50 |
| 28 | 32.2 | 0.49 -> 0.62 | 2.39 -> 2.64 | 0.055 -> 0.057 | x1.61 |
| 30 | 34.5 | 0.55 -> 0.69 | 2.51 -> 2.77 | 0.056 -> 0.058 | x1.61 |
| 35 | 40.2 | 0.71 -> 0.89 | 2.80 -> 3.09 | 0.058 -> 0.060 | x1.61 |

At 28 kn the lake's sea is now about 30% over the SWAN bake there. Why a stronger wind rather than a bigger height: the
sea stays the sea of some real wind (height, period and caps agree; by Toba's law a little steeper, as a harder blow's
chop is), and nothing the polars, reference checks, sea trials or SWAN tests use changes (they never call it).

On the 20-28 kn ramp a change in the real wind moves the sea's wind up to 1.76 times as much, so the sea map (rebuilt at a
5% change, on a worker) rebuilds up to about 1.6 times as often behind a gust front; no game-thread cost.

## Comparing

`-SailingClassicBlowSea` (or `-SailingBlowSea=0`) is the old sea; `-SailingBlowSea=<lift>` tries another (0 to 0.5).
Repro: `-SailingWorld=ray-hubbard -SailingBoat=J22 "-SailingStartAt=8917,240,137" -SailingWeather=Thunderstorm
-SailingWind=26 -SailingWindFrom=158`.

Test: `SailingSim.Physics.BlowSea`.

## Not in this pass

- The storm grade (#677), the cap look (#703) and the spray onsets are as Bean approved them; this pass changes how big
  the sea is and, through Monahan's law, how many caps it carries.
- The boat already floats on the long waves the renderer draws (the same `FWaveField`); the drawn surface's Gerstner
  shift (choppiness 1.5) and the FFT short waves are not in her hull's sampling, as before.
