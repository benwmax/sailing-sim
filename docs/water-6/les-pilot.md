# Water W6: LES pilot on the PC

A first large-eddy simulation of the air the game's sailors sail in: a North Texas summer afternoon's convective boundary
layer. The aim is a check on the game's wind field, `FWindField`: its gust intensity, gust patch spacing and shifts.

## Setup

- **Code:** MicroHH (github.com/microhh/microhh at 736a2f5), built with CUDA 12.8 for the RTX 4090 (sm_89) under WSL2
  (Ubuntu 24.04). Case: `Tools/les/ntxcbl.ini` and `ntxcbl_input.py`; `Tools/les/run_pilot.sh` runs it and
  `Tools/les/analyse_pilot.py` analyses it.
- **Domain:** a periodic tile, 10 x 10 x 3 km at 25 m (400 x 400 x 120 cells), Smagorinsky subgrid, second-order
  advection, a sponge from 2.4 km up.
- **Forcing:** 250 W/m2 of surface sensible heat flux (0.218 K m/s), roughness 0.05 m (the land round the lake).
  Geostrophic wind 13 kn from the south, f for 32.8 deg N.
- **Start:** a mixed layer to 1.5 km at 306 K under a 1.5 K inversion, 4 K/km above.
- **Run:** 3 h, with the first 2 h as spin-up and the last hour saved (cross-sections at 12.5, 62.5 and 212.5 m every
  60 s, profiles every 5 min). 6,065 steps, about 15 min on the 4090. The large outputs stay in WSL
  (`/root/les-runs/ntxcbl`) and are not in git.

## What it gives

From the last hour (61 frames, 2-3 h), at 12.5 m (`les-pilot.json`):

| Quantity | LES | The game (`FWindField`) |
|---|---|---|
| Mean wind at 12.5 m | 9.0 kn under a 13 kn geostrophic wind | the set speed is the 10 m wind |
| Gust intensity, std/mean at a point over the hour | 0.29 | `GustIntensity` 0.15-0.3 on a typical lake day |
| Gust factor, 99th percentile/mean at a point | 1.64 | |
| Direction, std at a point | 19 deg | `ShiftDegrees` |
| Speed correlation length (e-folding) | 300 m | `GustLengthMeters` 250 m (patch spacing) |
| Thermals at 225 m, correlation length | 200 m | |
| Shift period at a point | about 30 min (from 60 s samples: shorter shifts aren't resolved) | `ShiftPeriodSeconds` 90 s |
| Mixed layer at 3 h | 1.9 km | |

![Wind speed at 12.5 m](speed-12m.png)

![Vertical wind at 225 m](w-225m.png)

![Spectrum](spectrum.png)

## What it means for the game

1. **Gust strength is about right for a hot afternoon.** 0.29 is the top of the game's range. A convective
   afternoon should sit there, not mid-range, and the gusts reach 1.6 times the mean.
2. **Most of the gust energy is at kilometres, not 250 m.** The speed spectrum along the wind keeps rising to 2-5 km
   wavelengths: lulls and puffs the size of the convective cells (one to two mixed-layer depths). The 250-500 m
   streaks sit on top of them. The map shows it: dark lulls a kilometre across, edged with bright gust streaks. The
   game's single 250 m scale gives the streaks but not the big patches a sailor reads from far off and sails toward. A
   second, kilometre-scale octave in `FWindField`, slower and carrying about two thirds of the variance, would match.
3. **Shifts are large and slow on this scale.** 19 deg of direction spread is more than a typical `ShiftDegrees`. At a
   point the direction mostly changes as a cell drifts over, on the order of 10-30 min. The game's 90 s oscillation
   is the fast part, which this sampling can't see. A cross-section every 5-10 s over a shorter window would measure it.
4. **What the pilot doesn't cover:** the lake itself. Over the water the heat flux is near zero and the roughness is
   much smaller, so the surface layer adjusts within a few hundred metres downwind of the shore. A tile with the lake's
   outline as a surface patch (flux and z0 maps) is the next run. The land's flux pattern (fields, town) and the
   lake breeze also aren't modelled.

## Follow-up: the same afternoon over Lake Ray Hubbard

`Tools/les/ntxlake.ini` and `ntxlake_input.py` take the surface from the game's own height grid: a 10 x 10 km window
round Rush Creek (north -4.7 to +5.3 km, east -5 to +5 km), averaged to 25 m. The lake has no sensible heat flux and
water's roughness (z0m 2e-4 m), the land 250 W/m2 and 0.05 m. The lake covers 33% of the tile, so the domain-mean flux
is 167 W/m2. The atmosphere and wind are the pilot's (`les-pilot-lake.json`).

| Quantity at 12.5 m | Uniform land (pilot) | With the lake: all | over the water | over the land |
|---|---|---|---|---|
| Mean wind | 9.0 kn | 10.7 kn | 11.4 kn | 10.3 kn |
| Gust intensity (std/mean at a point) | 0.29 | 0.16 | 0.13 | 0.18 |
| Direction std at a point | 19 deg | 10 deg | | |
| Speed correlation length | 300 m | 175 m | | |
| Mixed layer at 3 h | 1.9 km | 1.86 km | | |

Downwind of the shore the wind crosses first (from the south), over the water:

| Distance over water | Speed / land mean | Gust intensity |
|---|---|---|
| 0-250 m | 1.07 | 0.15 |
| 250-500 m | 1.11 | 0.15 |
| 0.5-1 km | 1.13 | 0.15 |
| 1-2 km | 1.13 | 0.14 |
| 2-4 km | 1.11 | 0.13 |
| 4-10 km | 1.06 | 0.11 |

![Wind speed at 12.5 m over the lake](speed-12m-lake.png)

What it adds for the game:

1. **Over the water the wind is steadier than over the land round it.** Gust intensity is 0.13 over the lake (0.18
   over the land, 0.29 with all land). It falls from 0.15 near the upwind shore to 0.11 after 4 km of open water. The
   game's lake days should sit at the low end of `GustIntensity` (0.15) and ease with distance from the upwind shore.
   The game already marches that fetch for the waves (`FLakeTerrain::FetchToward`), so the same distance could scale
   the gusts.
2. **The wind picks up over the water.** It is 7% stronger within 250 m of the shore and 13% stronger by 1-2 km, as the
   smoother surface lets the air speed up. The game's wind is uniform in strength across land and water. A fetch-based
   factor, rising from 1 at the shore to about 1.1 over 1 km, matches this.
3. **The kilometre-scale lulls weaken over the lake.** Without heating from below the water damps the convective
   cells, so their patches don't reach the surface as strongly (correlation 175 m, against 300 m over land). Most of
   the gust structure over the water arrives from the upwind land. So the kilometre octave proposed above belongs over
   land and near the upwind shore, fading out over open water.
4. **Caveats.** The tile is periodic, so the lake's outline wraps at the tile edges and the land north of the window
   feeds the south shore. The lake is a uniform cool patch (in summer the water is warm and the real flux is a little
   above zero). There is no lake breeze: its pressure-driven circulation needs a larger domain and more time.

## Reproducing it

```
# WSL2 Ubuntu 24.04 with cuda-toolkit-12-8, libnetcdf-dev, libfftw3-dev, libboost-dev, python3-netcdf4
git clone --depth 1 https://github.com/microhh/microhh /opt/les/microhh && cd /opt/les/microhh && git submodule update --init --recursive
# config/wsl4090.cmake: config/ubuntu_20lts.cmake with CMAKE_CUDA_ARCHITECTURES 89
mkdir build && cd build && cmake .. -DSYST=wsl4090 -DUSECUDA=TRUE && make -j6
Tools/les/run_pilot.sh /root/les-runs/ntxcbl
python3 Tools/les/analyse_pilot.py /root/les-runs/ntxcbl
```
