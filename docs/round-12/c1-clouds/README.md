# C1: cloud shape and size (round 12, `Inputs/clouds-trees/plan.md`)

The first item of the clouds and trees plan. The material keeps the same march steps; what changes is the shape of the
fair-weather cumulus and how much of the sky they cover. The grain at the edges is C2's job, the sky cache, and it is
unchanged here.

## What changed

**Bases from the dew point** (`Weather.cpp`, `WindClimate.cpp`). Every cumulus base on a day now sits at one height, the
lifting condensation level: 125 m per degree C of spread between the air and its dew point. `ClimateDewC` holds the DFW
and Galveston monthly dew-point normals, and `FWeatherState::DewC` carries them; real days take the HRRR dew point. With
the weather's default month (June) the lake's bases are 0.84 km at 10:00 and 1.72 km at 15:30, and the humid coast's
are lower. Before, every preset used 1.2 to 1.5 km.

**Smaller, fewer fair-weather cells** (`CloudSky.cpp`, `FCloudSky::CuCellScale`):
- On a fair day the four W5a size classes shrink together to 0.6. The largest cells are about 1.5 km in radius; most are
  200 m to 1 km.
- A building or stormy day keeps the full sizes (scale 1): the thunderstorm preset, and real days with CAPE.
- The afternoon breeze's cumulus peaks at about a fifth of the sky (0.04 + 0.18 x the afternoon), down from a third. At
  a third, the towers' sides filled the low sky into a deck as seen from the water.
- Fair-weather cumulus are 0.4 to 1.1 km deep, down from 0.6 to 1.5 km, so they are about as deep as they are wide.

**The shape** (`CLOUD_CODE`, `make_materials.py`):
- **The pancakes and contour lines are gone.** Two things caused them. The shape noise was squeezed 2.4 times vertically,
  which stacked its own layers into plates through every tower; it is now squeezed 2 times (at 1.4 the towers stood as
  columns). The billow remap clipped into flat plateaus whose rims read as contour lines; it is now a little gentler
  (1.75, against 1.9; at 1.5 the billows went smooth as balloons).
- **Domes, not cones.** A cell's top rose linearly with its presence in the weather map, and presence falls off toward
  a cell's edge, so every cell came out as a cone. The top now follows presence to the power 0.3, which keeps the sides
  steep and the top round. The density fades over the top quarter of the cell, not over 70% of its height.
- **A Nubis height profile.** Coverage is full over the base and up the sides and narrows only near the top.
- **Billows that build upward.** Almost nothing is eroded from the base, so every cell keeps one flat base. Above the
  base the erosion is wispy, then billowed (inverted Worley) higher up.
- **Edges.** The ramp from edge to body steepens with height, from 2.5 to 6, so tops are crisper and bases softer. The
  fuzz that remains is the march's grain.

The cloud material's own rain term was already removed in W5a (M_RainCurtain draws the rain); there was nothing left to
drop.

## Stills (packaged, the PC)

These are the saved round 12 cameras (`docs/round-12/game/scenes.csv`) at High and at Ultra, before (main) and after.
Each JPEG puts the two side by side, before on the left: `<scene>-high.jpg` and `<scene>-ultra.jpg`.

- **lake-towers.** Separate clouds with flat bases at one height and blue sky between them, in place of a deck of
  stacked plates.
- **galv-kemah.** Smaller puffs over the far shore.
- **galv-texascity.** Rounder, billowed cells on one base line.
- **lake-north-shore.** The thin morning cells are flat and smooth; this is the weakest of the five.
- **storm-shelf.** Unchanged. The storm has its own shaping, which C1 doesn't touch.

The real photos to compare against (real-03, real-05, real-08 and real-10, from the G5 blind pack) are only on the Mac,
so they are not placed beside these stills yet.

## Cost (lake-towers, 1440x1080, three ProfileGPU frames)

| | High before | High after | Ultra before | Ultra after |
|---|---|---|---|---|
| clouds + fog, ms | 0.58 | 0.57 | 2.39 | 2.53 |
| GPU frame, ms | 5.05 | 4.98 | 8.42 | 8.50 |
| fps (20 s) | 81.8 | 80.7 | 73.5 | 75.5 |

About 0 ms. The Ultra slice moved by 0.1 to 0.35 ms between runs, which is the noise of three profiled frames; less cover
means longer rays through clear air between the cells. The Mac measures its own High (5.0 ms at lake-towers before C1, on the M5 Pro).

## Tests

- `SailingSim.Visual.CloudLayers` now checks:
  - the dew-point bases (0.7 to 1.3 km in the morning, 1.5 to 2.3 km in the afternoon);
  - that the coast's bases are lower than the lake's;
  - an afternoon coverage above 0.18 and a morning coverage below 0.1.
- `SailingSim.Visual.CloudNoise` checks that a fair afternoon's largest cloud is under 15 km^2. It measured 12 km^2:
  single cells are 7 km^2 at most, and two that touch make 12.
- `SailingSim.Visual`: 33/33 passed.
