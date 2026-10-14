# Galveston piers, jetties, dikes, Seawall and marinas (G2 add-on, Oct 14 2026)

Over-water and in-water structures for the Galveston Bay level, made from the G2 shore tiles in `../dem`, `../dsm`,
`../cover` and `../ortho` (2018 USGS lidar, 2022 NAIP). Same conventions as `../../README.md`: GeoJSON in EPSG:4326,
heights in NAVD88 metres, **sim Z = NAVD88 + 0.094** (metres above MLLW), directions in degrees from true north,
`sim_north` / `sim_east` in the sim's Galveston map frame (+X north, +Y east). Nothing was downloaded for this pack.

## Files

| file | what | count |
|---|---|---|
| `landmarks.geojson` | the named big structures as clean centrelines: North Jetty, South Jetty, Texas City Dike, Seawall | 4 |
| `overwater_structures.geojson` | polygons of everything standing on hydro-flattened water: piers, docks, wharves, bridges, covered slips | 11,102 |
| `moored_boats_2018.geojson` | one point per boat in the 2018 lidar: length, beam, heading, height, mast seen | 8,241 (2,497 with a mast) |
| `marinas.geojson` | hull of each cluster of docks and boats with 10 or more boats | 128 |
| `narrow_structures.geojson` | polygons of narrow raised land in the water: jetties, groins, breakwaters, dikes, spoil ridges | 885 |
| `narrow_structures_centrelines.geojson` | the same, as LineStrings down the middle (10 m bins, 1 m simplified) | 885 |
| `seawall.geojson` | the Seawall run inside the bay grid (also in landmarks) | 1 |
| `summary.json` | counts by kind | |

All files together are about 17 MB. In the repo the four big layers are gzipped (`gunzip -k *.gz`).

### landmarks.geojson (use this first)
| name | length | crest NAVD88 | how |
|---|---|---|---|
| Galveston North Jetty | 5,109 m to the grid's east edge (the whole jetty is about 7.9 km) | +1.34 m (p75), dips to −0.4 m where waves wash over | lidar along its whole traced length |
| Galveston South Jetty | 3,471 m to the end of the imagery (the whole jetty is about 10.9 km) | +1.13 m | lidar for the first 18%; the rest traced in NAIP 2022, heights copied |
| Texas City Dike | 8,300 m, shore to tip | +2.48 m, 41 m wide (road on top) | one straight line fitted through the lidar pieces; gaps bridged and the ends found in the imagery |
| Galveston Seawall | 557 m (only its north-east end is inside the bay grid) | +4.54 m top edge, boulevard +5.3 m behind, beach +1.6 m in front | lidar step edge, faces 136° |

Jetty crest heights are low because the 2018 lidar mostly saw the rock tops between waves; give the sim a mound about
12 m wide at the waterline (`width_m_guess`) with a crest near the listed height.

### overwater_structures.geojson
A cell counts when the 3DEP DEM is hydro-flattened water there but the lidar surface stands at least 0.85 m above it.
Each Polygon (holes kept) carries:

| property | meaning |
|---|---|
| `kind` | `pier` (long, at least 12 m and 3 times longer than wide), `dock_complex` (300 m² or more of fingers and walkways), `platform_or_wharf`, `boats_in_slips` (a lumpy raft of boats, not a deck), `covered_slip_or_building` (top 2.8 m or more above water: boathouses, restaurants on piles), `bridge` (deck 5 m or more above water and 40 m or longer), `vessel_large` (ship or barge, not touching shore), `deck_small` (anything else: short docks, platforms, and some noise) |
| `attached_to_shore`, `shore_contact_frac` | touches land; share of its cells within 3 m of land |
| `length_m`, `width_m`, `long_axis_dir_deg`, `area_m2`, `fill` | oriented box of the cells; `fill` = area / box |
| `deck_z_navd88`, `top_z_navd88`, `sim_deck_z` | median and 99th percentile lidar surface |
| `water_z_navd88`, `deck_above_water_m` | lidar-time water surface (flattened DEM + 0.5 m, measured at Kemah) and deck height above it |
| `surface_roughness_m` | median step between neighbouring cells: about 0.05 m on a deck, 0.3 m or more on boats and trees |
| `name` | set only for anchors in `scripts/piers/anchors.json` |

### moored_boats_2018.geojson
Compact blobs 3.5 to 40 m long and 1.6 to 6.5 times longer than wide, at least 0.9 m above water. `heading_deg` is the
hull axis (0 to 180; bow direction is unknown). `mast_seen` is true when the top return is 6 m or more above water. This
is a 2018 snapshot, useful for how full each marina is and the real mix of sizes, not for which boat is where today.

### marinas.geojson
Docks and boats chained together within about 30 m; `boats_2018`, `dock_pieces`, `area_m2`. Kemah Boardwalk Marina is
named (74 boats, 5 ha).

### narrow_structures.geojson
Land strips narrower than 41 m (a morphological opening) at least 0.75 m above flattened water, 60 m or longer and 3.5
times longer than wide. Collinear pieces up to 250 m apart are joined (`pieces`, `above_water_length_m`).

| `kind` | rule |
|---|---|
| `jetty` / `groin` | 25% or more rock, concrete or asphalt cover, touching shore; jetty if 400 m or longer |
| `breakwater` | the same but standing free in the water |
| `dike_or_causeway` | 30% or more paved, 18 m or wider, 300 m or longer |
| `spoil_or_ridge` | soft but straight and at least +0.8 m: dredge-spoil banks and the containment levees round disposal areas |

Low, soft, wiggly strips (marsh edges) are dropped. Other properties: `crest_z_navd88` (p90 bare earth), `top_z_navd88`
(p95 surface), `mean_width_m`, `max_width_m`, `frac_rock_or_hard`, `frac_paved`, `frac_sand`, `frac_tree`, `straightness`.

## Limits
- **Floating docks are mostly missing.** They sit about 0.5 m above water, inside the lidar water noise. Marina docks show
  as boats in rows; draw the walkways between the rows of `moored_boats_2018` inside each `marinas` hull.
- **The lidar band stops 1 km from shore.** The outer jetties were traced in the imagery past it, but the imagery tiles
  also stop at the band edge, so both jetties end short of their real heads. The Pleasure Pier, 61st Street Pier and the
  rest of the Seawall are south of the bay grid (29.295 N); see the Gulf front below.
- `deck_small` is low confidence (8,189 of them, many under 30 m²). Filter by `area_m2` and `deck_above_water_m`.
- `bridge` includes a few tree crowns over bayous that passed the roughness check.
- Data age: lidar 2018, imagery 2022.

## Gulf front (not built yet)
The bay grid's south edge is 29.295 N, so most of the Seawall, the Pleasure Pier, the fishing piers and the groins are
outside every G2 tile. The G2 scripts now have a `GalvestonGulf` region (29.20 N to 1 km past the bay grid's edge, same
frame and sources) and write to `sailing-sim-g2/GalvestonGulf/`. It needs USGS (prd-tnm, usgs-lidar-public), the TxGIO
tnris bucket and Overture on S3, which this cloud session could not reach. To build it where those hosts are reachable:

```
cd sailing-sim-g2/scripts
export G2_REGIONS=GalvestonGulf G2_OUT=<sailing-sim-g2 folder> SIM_REPO=<sailing-sim checkout>
python3 masks.py GalvestonGulf && python3 naip_list.py && python3 overture.py && python3 prep.py GalvestonGulf
python3 runall.py GalvestonGulf 4 && python3 ortho.py GalvestonGulf && python3 merge.py GalvestonGulf
python3 beachfix.py && python3 beachfix2.py
sh piers/run.sh GalvestonGulf 4
```

The seam tiles at 29.295 N exist in both regions; keep the bay copy north of the seam. The sim grid itself also has to
grow south to show any of it.

## Rebuild this pack
`sh ../../scripts/piers/run.sh GalvestonBay 4` (numpy and Pillow only; about 12 minutes on 4 cores).

## Sources and credits
| what | source | licence |
|---|---|---|
| heights, decks, boats, narrow land | USGS 3DEP 1 m DEM (`TX_CoastalRegion_2018_A18`) and lidar (`TX_Coastal_B3_2018`, `TX_Coastal_B1_2018`), via the G2 tiles | public domain (USGS) |
| cover classes, jetty and dike tracing | USDA NAIP 2022 60 cm and NOAA C-CAP 2020 1 m, via the G2 tiles | public domain (USDA FSA, NOAA) |

No OpenStreetMap or Overture data is in this pack, so it adds nothing to CREDITS.md beyond the USGS, USDA and NOAA lines
G2 already needs.
