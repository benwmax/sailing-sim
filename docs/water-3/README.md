# Water W3: sea state by direction

Before W3 the lake had one sea. Its height and period came from the growth laws on the effective fetch at the boat
(W3 prep: Saville's mean over +/-45 deg of the wind), and every point of the water drew that same sea. The boat on
open water and the chop in a cove behind a point were the same.

W3 gives every point its own sea, in physics and on screen alike:

- **The fetch map** (`FSeaFetch`, `SeaState.h`). At load it computes Saville's effective fetch for 16 wave directions
  at every cell of a 50 m grid (Ray Hubbard; 100 m on Galveston Bay, 200 m on the Gulf passage), plus the water's depth.
  Each direction is marched semi-Lagrangian at half the cell: a cell's fetch is the fetch one step upwind plus the step.
  32 rays every 11.25 deg are combined nine at a time with Saville's cos^2 weights. A 3 x 3 mean over the water (two
  passes) softens the knife-edged shadows the rays cast behind points. This takes 40-60 ms.
- **The sea map** (`FSeaMap`). For the mean wind, it holds a ratio for each of the 24 long wave trains at every cell:
  the amplitude the growth laws' JONSWAP spectrum gives that train's band at the cell's fetch for its direction,
  divided by the amplitude at the 15 km reference fetch, times the square root of the TMA depth factor
  (Kitaigorodskii) at the cell's depth. One more channel scales the short waves (the other 24 trains and the FFT
  detail): their energy-weighted ratio. The game mode rebuilds it on a worker when the mean wind's speed changes by 5%
  or its direction by 11.25 deg (about 25 ms).
- **The field** (`FWaveField`). With a map, its components grow toward the 15 km reference sea, and `Height`, `Sample`,
  `SignificantHeightAt` and `BandsAt` scale each one by the map's ratio at the point. Every boat's added resistance
  reads `BandsAt` at its own position, AI boats included. Without a map (polars, reference checks, `-SailingNoSeaMap`)
  nothing changes: `SailingSim.Physics.PolarGate` is unchanged.
- **Shallow-water dispersion.** The components keep their frequencies, but their wavenumbers follow
  omega^2 = g k tanh(k h) at the world's median depth: Ray Hubbard 6.4 m, Galveston Bay 2.5 m, the Gulf passage
  16.7 m. In Galveston Bay's 2.5 m a 2.5 s wave now travels 6% slower than in deep water, a 3 s wave 14% and a 4 s
  wave 29%. Before W3 they all moved at deep-water speed.
- **The shaders.** `AWaterSurface` uploads the map as one atlas of seven RGBA half-float tiles. Tile t, channel c
  scales component 4t + c, and tile 6's R channel is the short scale. M_WaterV4's vertex code multiplies the 24 long
  trains by it (four taps a vertex, plus one for the FFT detail). The pixel code scales the chop's slopes, its
  variance and its fold by the short channel (the ripples stay with the local wind). M_Water (Low) scales all 48
  components the same way. The sampling mirrors `FSeaMap::Sample`: bilinear between cell centres, clamped at the
  edge, never across a tile.

## Against SWAN

`scripts/wave-check.sh --map` runs the lake's sea against the PC's SWAN bake of Ray Hubbard (`swan-bake.md` on
w3-swan-bake: 16 directions x 7 speeds, 50 m). It reports the lake-wide median the bake used (per direction, the median
over the water every 250 m, then the median over directions), and the ten spectrum points in every case
(`sea-map-points.csv`).

| Wind | SWAN Hs | Sea map Hs | Error |
|---|---|---|---|
| 5 kn | 0.048 m | 0.047 m | -2% |
| 8 kn | 0.085 m | 0.087 m | +2% |
| 11 kn | 0.125 m | 0.129 m | +3% |
| 14 kn | 0.167 m | 0.170 m | +1% |
| 18 kn | 0.238 m | 0.231 m | -3% |
| 22 kn | 0.335 m | 0.311 m | -7% |
| 28 kn | 0.493 m | 0.465 m | -6% |

The table below covers the ten points in all 112 cases (1,050 with SWAN Hs above 5 mm). "Before W3" is the effective
fetch at the point; the "bake's ray" is the single straight-upwind fetch in the 10 m wind, before W3 prep.

| | Median abs. log error, Hs | Median abs. log error, Tp |
|---|---|---|
| Sea map | 0.08 | 0.12 |
| Before W3 (effective fetch at the point) | 0.08 | 0.08 |
| The bake's ray in U | 0.25 | 0.16 |

| Point | Sea map / SWAN | Before W3 / SWAN |
|---|---|---|
| Rush Creek Yacht Club | 1.11 | 1.16 |
| Off Rush Creek, open water | 1.03 | 1.02 |
| South lake, near the dam | 1.04 | 1.02 |
| Chandlers Landing | 0.98 | 1.03 |
| North lake, below SH-66 | 1.37 | 1.52 |
| Harry Myers Park | 0.99 | 1.04 |
| open water (three points) | 0.89-1.03 | 0.92-1.03 |

So at a point the sea map is as good as the boat's effective fetch was, and the shallow north arm is better, from
+52% to +37% (TMA). The gain is that this now holds everywhere at once: the water in the lee of the I-30 and SH-66
causeways, the coves and the far shore each show their own sea, and so do the AI boats' motion and resistance.

![Hs over Ray Hubbard at 14 kn from the north and from the south](sea-map-14kn.png)

### What I tried first

- **Each component along its own direction.** The plan read each wave train's fetch along the direction it travels.
  The field has three components per band, 120 deg apart with a seeded offset, standing in for the whole cos^2 spread.
  Read along their own directions, a band's fetch came from up to 60 deg off the wind, almost at random, and the points
  scattered twice as far from SWAN (0.14). Pulling the direction 75% of the way toward the wind
  (`kSeaTowardWind`) matches the effective fetch at the points (0.08). A component well off the wind still sees the
  shore on its own side, which is what makes cross-chop behind a point.

### Known gaps

- **Peak period at short fetch.** The 24 short trains share one scale, so below about 8 kn, where the whole sea is
  short waves, the drawn spectrum keeps the reference sea's shape. The peak period at the points is 0.3 s long at 5 kn
  (SWAN 0.99 s, the map 1.31 s). Heights are right. A per-component ratio for the short trains would fix it in
  physics, but M_Water and the FFT detail would then need 12 more taps.
- **Galveston Bay** has no SWAN results yet (the bake is still running on the PC, on the pre-Galveston 2 grid). The
  bay gets the same map at 100 m, TMA in its 2.5 m median and the shallow-water speed. The comparison follows when
  the bake finishes.
- **The open sea** (Galveston's Gulf side, the Gulf passage) keeps a 200 m chop under the FFT ocean where its mask is
  over half, as before. The mask is copied when the sea map is built; a swell change that moves the mask waits for the
  next wind change.

## Tests

- `SailingSim.Physics.SeaFetch`: the march in a basin (straight and diagonal) and its cap. Over Ray Hubbard, the map
  against `FLakeTerrain::EffectiveFetch`'s rays: median within 10%, half within 25%, and built in under 2 s.
- `SailingSim.Physics.SeaDepth`: the TMA factor (deep, shallow limit, continuity, dry) and the dispersion in 3 m (same
  frequency and direction, slower). Without a map the field is unchanged.
- `SailingSim.Lake.SeaStateSwan`: the lake medians within 10% of SWAN at 5, 11, 18 and 28 kn. Five points at 14 kn
  within 30% of SWAN, with the club's lee shore under three quarters of the dam's sea in a northerly. `BandsAt` carries
  `SignificantHeightAt`, and land has no sea.

## Cost

PENDING: bench (gate --scope water, then --scope all).
