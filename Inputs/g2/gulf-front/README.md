# Galveston Gulf front (G2 add-on, Oct 14 2026)

The Gulf side of Galveston Island south of the bay grid's edge (29.295 N, sim_north −27,600): the Seawall end to end,
the Pleasure Pier and the fishing piers, the groins, the beach every 50 m, plus both entrance jetties carried out to
their charted heads. Built in the cloud from the `GalvestonGulf` G2 region (2018 USGS lidar, 2022 NAIP, Overture
buildings) with the scripts in `scripts/gulf/`.

Conventions are the G2 pack's (`../../README.md`) and the piers pack's (`../piers/README.md`): GeoJSON in EPSG:4326,
rasters in UTM 15N (EPSG:26915) on the same 1 km tile grid, heights in NAVD88 metres, **sim Z = NAVD88 + 0.094**
(metres above MLLW), directions in degrees from true north, `sim_north` / `sim_east` in the sim's Galveston map frame
(+X north, +Y east). Everything here is south of the bay grid, so **the sim's Galveston grid has to grow south** (to
about sim_north −38,200) before any of it shows; the jetties are the exception and sit inside the current grid.

> **In the repo** (`Inputs/g2/gulf-front`): the big layers are `.geojson.gz` (`gunzip -k`), the 0.5 m cover tiles are
> `shore/cover.tar.gz`, and the PNGs and the `dem/ dsm/ ortho/` tiles are left out (about 820 MB; PNGs would go to LFS).
> The full pack with the rasters and the preview is in the project's shared folder at
> `sailing-sim-g2/GalvestonBay/gulf-front/`; on the Mac, rebuild the rasters with `scripts/gulf/run.sh`.

## Files

| file | what | count |
|---|---|---|
| `landmarks.geojson` | **start here**: Seawall, North and South Jetty (to the head lights), the two jetty-head lights, three named piers | 8 |
| `gulf_piers.geojson` | over-water structures standing in the open Gulf (pier polygons from the lidar) | 3 |
| `groins.geojson` | rock groins off the Seawall, as centrelines (lidar) | 15 |
| `charted_structures.geojson` | NOAA chart piers and groins on the Gulf front: a cross-check, and it has the low ones the lidar misses | 51 |
| `beach_profiles.geojson` | one cross-shore line every 50 m from the waterline to the back of the beach (or the dune crest) | 398 |
| `gulf_summary.json` | counts and medians | |
| `gulf_water10.png` | 10 m mask of open Gulf water used to tell the Gulf side from the bay side (white = Gulf) | |
| `shore/` | the G2 layers for the region, clipped south of the seam: `buildings`, `trees`, `shore_armour` GeoJSON, `tiles.json`, and the `dem/ dsm/ cover/ ortho/` tiles | 13,883 buildings, 57,556 trees, 323 tiles |
| `piers/` | the piers-pack layers for the region (same fields as `../piers/`), clipped south of the seam | 4,780 over-water pieces, 456 narrow, 1,513 boats, 26 marinas |

### landmarks.geojson
| name | size | heights (NAVD88) | how |
|---|---|---|---|
| Galveston Seawall | 10,959 m from −94.869 (its west end) to the bay grid's edge at −94.777; lidar saw 8,241 m of it | top edge +4.63 m; faces about 145° | lidar step edge (2018). Six gaps where groins, piers or stairs break the step, the longest 1,678 m between −94.803 and −94.789, just west of the Pleasure Pier; listed in `gaps` and bridged with straight lines |
| Galveston North Jetty | 5,980 m: the bay pack's 5,109 m trace plus 871 m to the head | crest +1.34 m (p75) where traced; the last 871 m is assumed the same | head = North Jetty Light 6A on the NOAA chart (ENC US5TXTED), light 9.1 m above MHW |
| Galveston South Jetty | 3,552 m: the bay pack's trace plus 81 m | crest +1.13 m | head = South Jetty Light 5A |
| Galveston Island Historic Pleasure Pier (25th St) | 239 × 56 m | deck +9.96 m, rides to +31.8 m | lidar over water; the ride deck stands 10 m above the water |
| Galveston Fishing Pier (90th St) | 209 × 18 m | deck +5.12 m, roof +13.4 m | lidar |
| 61st Street Fishing Pier | 86 × 38 m (the lidar caught the high end of the pier; the low walkway to shore is missing) | deck +4.70 m | lidar |

The two light points carry the chart's light characteristics (`light`: flash group, period, colour, range, height)
and daymark. The jetty heads are outside both the 2018 lidar and the NAIP 2022 imagery, and the 2024 HGAC lidar
DEM there is hydro-flattened, so no crest height is measured past the traced part.

### gulf_piers.geojson
The piers-pack polygon fields (`kind`, `length_m`, `width_m`, `deck_z_navd88`, `top_z_navd88`, `deck_above_water_m`,
`sim_deck_z`, ...) plus `setting: "gulf"` and `name`. Only decks 1.5 m or more above the water are kept: the run
also found 2,636 "decks" 0.4 m above the water just off the beach, which are breaking waves on the sand bars
(`dropped_as_surf` in the summary). The two high piers were classed `bridge` by the bay rules and are relabelled `pier`
(`kind_note`).

### groins.geojson
The narrow-structure centrelines whose polygons touch the open Gulf: 15 rock groins, 61 to 138 m long (median 77 m),
crest about +1.4 m, 6 to 25 m wide. Fields as `../piers/narrow_structures.geojson`.

### charted_structures.geojson
NOAA ENC shoreline constructions on the Gulf front, taken from the sim's own `Content/TerrainData/GulfPassage.chart.json`
(so it matches the chart view): 32 groin or breakwater lines and 19 pier outlines (`chart_kind` `breakwater` or `pier`).
Use it to place groins that are awash or too low for the lidar, and the T-headed structure near −94.801.

### beach_profiles.geojson
LineString from the waterline landward (to the back of the beach, or to the dune crest when there is one), one every
50 m along the open-Gulf shore from about −94.95 to the bay grid. Profiles are cut on the 1 m DEM and the 0.5 m cover.

| property | meaning |
|---|---|
| `beach_width_m` | waterline to the back of the beach |
| `faces_deg` | seaward direction of the profile |
| `water_z_navd88` | the lidar-time water surface (about −0.58 m; the Gulf was flown near low water) |
| `foreshore_slope` | rise over run of the first 25 m above the water (median 0.03, about 1 in 33) |
| `berm_z_navd88` | median height of the upper half of the beach (median +1.33 m) |
| `back_z_navd88` | height where the beach stops |
| `backed_by` | `seawall`, `dune`, `road_or_parking`, `buildings`, `vegetation`, `scarp_or_bank` (a steep dune face or bulkhead away from the Seawall), `riprap`, `pavement`, `sand`, `bare_ground` |
| `dune_crest_z_navd88`, `dune_dist_m` | dune top and its distance from the waterline, when `backed_by` is `dune` |
| `behind` | main cover class in the 60 m behind the beach |
| `sand_frac` | share of the beach in the `sand` cover class |

Along the Seawall (209 profiles): beach 31 to 86 m wide (median 59 m), 144 backed by the wall itself. West of the
Seawall (189): 51 to 70 m wide (median 61 m), 120 backed by dunes with crests near +2.9 m, the rest by roads and houses.
The back of the beach is where 3 m in a row are vegetation, pavement or buildings, or where the ground steps up 1.5 m
within 4 m. NAIP-bright dry sand often falls in the `concrete` cover class, so concrete below +2.0 m counts as beach.

## Limits
- The jetty heads have no measured height (see above). Model them as a rock mound about 12 m wide at the waterline with the
  listed crest, and put the light structure on the end.
- The Seawall's curved face and stairs are not modelled; the line is its top edge. Groins and piers break the lidar step,
  so `gaps` are real data gaps, not breaks in the wall.
- The 61st Street pier walkway is missing from `gulf_piers` (low over the water); `charted_structures` has its outline.
- Beach profiles stop about 2 km short of the region's south-west corner, and East Beach (north of 29.295) is not profiled;
  it is in the bay tiles' `shore_armour` as `beach`.
- Data age: lidar 2018 (any beach nourishment since then is not in it), imagery 2022, chart current to the sim's
  last chart fetch.

## Rebuild
Everything here comes from `scripts/gulf/run.sh`, which runs the G2 pipeline for `GalvestonGulf` and then
`gulf/build.py` (piers, groins, profiles, landmarks), `gulf/package.py` (clip south of the seam; `--rasters` copies the
tiles) and `gulf/preview.py`. Python 3 with numpy, scipy, rasterio, pyproj, shapely, laspy[lazrs], scikit-image, pyarrow,
pyshp and Pillow; the `piers/` and `gulf/` steps need numpy and Pillow only.

Before the first step, fill `G2_SRC` (default `/tmp/g2/src`):
- `naipidx/`: the NAIP 2022 index (`.shp .shx .dbf .prj` from
  `tnris-data-warehouse/LCD/collection/naip-2022-nccir-60cm/assets/index/`; leave out the `.cpg`, whose
  "ANSI 1252" name pyshp cannot read).
- `naip/`: the `.jp2` and `.j2w` files that `naip_list.py` lists (11 quarter quads, 360 MB), from `.../items/nccir/`.
- `dem_TX_CoastalRegion_2018_A18.txt`: the S3 key list of
  `prd-tnm/StagedProducts/Elevation/1m/Projects/TX_CoastalRegion_2018_A18/TIFF/`.
- empty `bldg/` and `ept/`.

`overture.py` now goes through an HTTPS proxy when `HTTPS_PROXY` is set (virtual-host addressing on
`overturemaps-us-west-2.s3.amazonaws.com`; set `AWS_CA_BUNDLE` to the proxy's CA). On the Mac, with no proxy, it reads
S3 directly as before. `piers/seawall.py` takes `SEAWALL_SAND_MIN` (default 0.3, so the bay pack is unchanged;
`run.sh` uses 0.15 for the Gulf). Run time in the cloud: about 2 h for the 323 tiles on 4 cores, a minute for the rest.

## Sources and credits
See `CREDITS.md`. In short: USGS 3DEP lidar and DEM, USDA NAIP 2022, NOAA C-CAP 2020 and NOAA ENC charts (all public
domain), and Overture Maps buildings (ODbL; credit "Overture Maps Foundation, OpenStreetMap contributors").
