# G2 shore datasets: Lake Ray Hubbard and Galveston Bay

These are derived products for phase G2 "shore", made in the cloud from public lidar and imagery. Their formats follow the sim thread's spec: georeferenced GeoTIFFs in UTM, GeoJSON in EPSG:4326, and the real extent always in the file tags. No raw downloads are kept here.

```
sailing-sim-g2/
  README.md
  RayHubbard/            UTM 14N (EPSG:26914)
  GalvestonBay/          UTM 15N (EPSG:26915)
    tiles.json             tile list, per-tile lidar point count, water level, grid convergence
    dem/<tile>.tif         float32 bare earth, 1 m
    dsm/<tile>.tif         float32 first-return surface, 1 m        (tiles with land only)
    cover/<tile>.tif       uint8 ground cover, 0.5 m                (tiles with land only)
    ortho/<tile>.tif       NAIP 2022 RGB, native 0.6 m              (tiles with land only)
    buildings.geojson      footprints with lidar heights, roof type, ridge direction, roof colour
    trees.geojson          one point per lidar tree crown
    shore_armour.geojson   riprap, bulkhead and beach lines along the waterline
  previews/              quick-look mosaics
  scripts/               the Python that made all of it (re-runnable)
```

## Grids and coverage
- **Tiles:** 1 km × 1 km on the UTM kilometre grid. The name is `<zone>_<E km>_<N km>` of the south-west corner, so `14_0734_3634` covers E 734000 to 735000 and N 3634000 to 3635000. Rush Creek Yacht Club is in `RayHubbard/14_0734_3634`. Always read the extent from each file's geotransform.
- **Band:** land within 1 km of the shoreline, plus water within 1 km of land.
  - Lake: the whole of Lake Ray Hubbard. The band is cut at the sim's existing lake grid, which already holds the full lake.
  - Coast: everything inside the sim's Galveston Bay grid (latitude 29.295 to 29.625). That covers Kemah, Clear Lake, Seabrook, La Porte and Morgan's Point, the Houston Ship Channel edge inside the grid, Texas City and the dike, Galveston Island, Pelican Island, Bolivar, Smith Point and the east bay. The grid's south edge cuts Galveston Island, so most of the Seawall Boulevard Gulf front is outside it.
  - Outside the band, rasters hold nodata.
- **Shoreline:** the main water body only. On the lake that is the 3DEP hydro-flattened surface at lidar time (132.43 m NAVD88). On the coast it is NOAA C-CAP 2020 open water and aquatic bed. Inland ponds are not shoreline, but they are shown as water in `cover`.
- **Vertical datum:** every height is NAVD88 metres (GEOID12B). Each GeoTIFF carries the tags `VERTICAL_DATUM`, `SIM_Z_OFFSET_M` and `SIM_Z_NOTE`. Sim Z = NAVD88 + offset:
  - Ray Hubbard: offset is −132.7407. That is the 435.5 ft pool, subtracted exactly as `Tools/terrain/build_rayhubbard.py` does (no NGVD29 shift).
  - Galveston: offset is +0.094, which gives metres above MLLW. This is the `navd88_to_mllw_m` value used by `Tools/coast/build_galveston.py`.
- **Directions:** all directions in the GeoJSON (`ridge_dir_deg`, `long_axis_dir_deg`) are degrees clockwise from true north, 0 to 180. UTM grid north differs from true north by the convergence in `tiles.json`: +1.36° on the lake, and the coast value is in its own `tiles.json`.

## Files

### dem/*.tif
- float32, 1 m, nodata −9999.
- Bare earth from the USGS 3DEP 1 m DEM, bilinear onto the tile grid. It is the same UTM zone as the source, so there is no reprojection.
- Water areas hold the hydro-flattened surface at lidar time:
  - Lake: about 132.43 m NAVD88, roughly 0.3 m below pool.
  - Coast: about −0.5 m NAVD88; the coast was flown near low water.
- Use the DEM over water only to blend the waterline. The sim's lake level, tide and bathymetry still win.
- Water-only tiles have a DEM but no other rasters.

### dsm/*.tif
- float32, 1 m, nodata −9999.
- Each cell holds the highest lidar return (all returns except noise classes 7 and 18). In practice that is the first-return canopy and roof surface.
- Cells with no return (about 3% of land cells at Rush Creek, and most of the water) are filled from the DEM.
- Canopy height model = DSM − DEM.

### cover/*.tif
- uint8, 0.5 m, nodata 255.

| value | class | how it's decided |
|---|---|---|
| 0 | water | the main lake or bay, plus ponds and canals from lidar water returns (class 9) |
| 1 | grass | green in NAIP and under 0.6 m, or bare but not clay-coloured (dormant grass). Coastal marsh is also mapped here |
| 2 | scrub | green, 0.6 to 2.5 m tall |
| 3 | bare_clay | no green, reddish or brown, NDVI under 0.04 |
| 4 | sand | coast: C-CAP unconsolidated shore; both shores: flat, bare and bright next to the water |
| 5 | riprap_rock | between the waterline and the crest of a riprap run (see shore_armour) |
| 6 | concrete | grey, not green, NAIP brightness 135 or more. Also the 1 m strip behind a bulkhead |
| 7 | asphalt | grey, not green, NAIP brightness under 135 |
| 8 | tree_canopy | green, 2.5 m or taller |
| 9 | building | Overture footprint |

- Imagery cues (green, colour, brightness) come from NAIP resampled to 0.5 m.
- Height cues (scrub and tree) and the riprap and bulkhead strips come from the 1 m lidar grid, repeated 2 × 2. So class edges driven by height are 1 m steps, not 0.5 m.
- The NAIP was flown in summer 2022, a drought year. Some dormant pasture falls in bare_clay and some bare dirt falls in grass.
- Concrete versus asphalt is decided by brightness only. A dark, weathered concrete drive can read as asphalt.

### ortho/*.tif
- NAIP 2022 natural colour (RGB) at its native 0.6 m grid, cut to the tile. The pixels are copied, not resampled.
- JPEG-compressed GeoTIFF (YCbCr, quality 85).
- Flight dates:
  - Ray Hubbard: July 2022.
  - Galveston: September 2022.
- Each file's extent snaps outward to the 0.6 m grid, so it is a fraction of a metre bigger than the tile.

### buildings.geojson
- One Polygon per building, in EPSG:4326.
- It holds every Overture footprint (OSM, Microsoft ML Buildings, Esri) whose centroid is on land within 1 km of the shoreline.

| property | meaning |
|---|---|
| `id` | Overture id |
| `osm_id` | OSM way id (`w…`) when OSM holds this footprint, else null |
| `source` | footprint source: `osm`, `microsoft`, `esri` or `other`. `footprint_sources` lists all of them |
| `height_m` | top of roof above `ground_z_navd88` |
| `height_source` | `lidar` (fitted to 2018 lidar returns on the roof), `overture` (an OSM or Overture height tag) or `none` (no height; use a default) |
| `eave_m` | eave height above ground, from the roof fit |
| `roof_type` | `flat`, `gable`, `hip` or `complex`; null when lidar is missing |
| `roof_detail` | the same, plus `shed`. Single-pitch roofs are `complex` in `roof_type` |
| `roof_fallback` | for `complex`: the closest simple shape |
| `ridge_dir_deg` | ridge direction for gable or hip, degrees from true north (0 to 180) |
| `pitch_deg`, `fit_rms_m` | roof fit |
| `roof_colour` | median NAIP colour inside the footprint shrunk 1 m, `#rrggbb` |
| `dist_to_water_m` | to the shoreline, on a 10 m grid |
| `detail` | `full` within 400 m of the water (Bean's rule), `reduced` beyond |
| `ground_z_navd88` | median bare earth under the footprint |
| `area_m2`, `length_m`, `width_m`, `long_axis_dir_deg` | minimum rotated rectangle |
| `lidar_points` | roof returns used |
| `sim_north`, `sim_east` | centroid in the sim's map frame (+X north, +Y east) |
| `sim_index` | index into `buildings` in the sim's `RayHubbard.json` or `GalvestonBay.json` when one of its boxes is centred within 6 m, else null |
| `ov_class`, `ov_floors`, `ov_roof_shape` | Overture tags, when present |
| `roof_grid` | the measured roof surface (below); null when lidar is missing |

- **roof_grid:** use it to model complex roofs exactly.
  - Fields: `cols_u` × `rows_v` cells of 1 m, and `b64` = base64 of uint8 values. Each value is the roof height above ground in decimetres; 0 means outside the footprint.
  - Axes: u runs along the long axis and v is 90° counter-clockwise from u. Both are in UTM grid coordinates (`centre_utm` = [E, N]).
  - Cell (row j, col i) has its centre at u = −length/2 + i + 0.5 and v = −width/2 + j + 0.5.
  - In the world, with α = `long_axis_dir_deg` − convergence (the grid azimuth): E = cE + u·sin α − v·cos α and N = cN + u·cos α + v·sin α.
- **Roof fit:** the fit tries flat, shed, gable along the long or short axis, and hip.
  - It is `complex` when the best fit is off by more than max(0.35 m, 22% of the roof's rise). This covers many Texas houses with cross gables.
- **Lidar date:** lidar is from 2018. Buildings put up since then have `height_source` `overture` or `none`.

### trees.geojson
One Point per crown, found on the lidar canopy height model (outside footprints, green in NAIP) by local maxima and watershed crowns. Crowns under 3 m are left to the scrub class.

| property | meaning |
|---|---|
| `height_m` | canopy top above ground |
| `crown_radius_m` | equal-area radius of the crown, capped at 14 m |
| `species_guess` | `eastern_red_cedar` or `unknown` (see below) |
| `ground_z_navd88` | ground under the crown |
| `ndvi` | NAIP greenness at the crown |
| `dist_to_water_m` | to the shoreline |
| `sim_north`, `sim_east` | position in the sim's map frame |

**Species guess:** only `eastern_red_cedar` and `unknown` are produced, and red cedar only on the lake. A red cedar is a narrow crown (radius under 0.28 × height), under 14 m and dark in the imagery. Single-date summer NAIP plus 2.5 points per m² of lidar can't separate live oak, cedar elm, hackberry, pecan, mesquite or bald cypress. A useful guess for those needs leaf-off imagery or field samples, so treat `unknown` as "pick by the local mix". The sim's existing Texas species mix is a fair default.

### shore_armour.geojson
Each LineString in EPSG:4326 follows the waterline. Points are about every 2 m, and each run is at least 8 m.

| property | meaning |
|---|---|
| `type` | `riprap`: rock revetment or breakwater face. `bulkhead`: vertical seawall or hard concrete edge. `beach`: flat bare shore, which can be sand, shell or a mud flat (on the coast most of it is bay mud and shell flats) |
| `detection` | `lidar_profile`, or `flat_grey_edge` for a low grey edge with pavement or buildings right behind it in `cover` (boardwalks, seawall caps, marina edges), relabelled from beach to bulkhead |
| `length_m` | length of the run |
| `water_z_navd88` | the lidar-time water surface |
| `crest_z_navd88` | top of the bank |
| `width_m` | waterline to crest |
| `roughness_m` | slope-corrected scatter of lidar ground returns on 2 m cells, a proxy for rock size |
| `mean_rock_size_m` | always null: not measurable from this data (see Limits) |

How each type is detected:
- **bulkhead:** at least 0.55 m of rise within 2 m of the water, flat behind it, and a straight run (chord at least 0.85 of the length). Wiggly vertical edges are eroded clay banks and are left out.
- **riprap:** a slope of 0.15 to 1.5, not green, and grey (limestone) or rough in the lidar.
- **beach:** flat, bare and bright.
- **flat grey edge:** each beach run was then re-checked against the ortho and the cover raster. A run that is grey and backed by pavement or buildings becomes `bulkhead`.

Natural shoreline is not listed; everything not in the file is natural. The sim already draws charted and OSM breakwaters and the hand-placed Rush Creek breakwater. This file adds the private revetments and bulkheads between them.

## Sources, dates and licences

| File | Source | Date | Licence |
|---|---|---|---|
| dem | USGS 3DEP 1 m DEM. Lake: project `TX_Pecos_Dallas_2018_D19`. Coast: `TX_CoastalRegion_2018_A18`. https://prd-tnm.s3.amazonaws.com/index.html?prefix=StagedProducts/Elevation/1m/Projects/ | lidar 2018 | Public domain (USGS) |
| dsm, building heights, roofs, trees, shore lines | USGS 3DEP lidar point clouds (Entwine). Lake: `TX_Pecos_Dallas_B3_2018`. Coast: `TX_Coastal_B3_2018`, then `TX_Coastal_B1_2018` where B3 is thin. https://usgs-lidar-public.s3.amazonaws.com/TX_Pecos_Dallas_B3_2018/ept.json (and so on). Classes are ground, water, noise and unclassified only | 2018 | Public domain (USGS) |
| ortho, cover, roof colours, tree greenness | USDA NAIP 2022, 60 cm, 4-band, from the TxGIO data hub bucket: https://tnris-data-warehouse.s3.us-east-1.amazonaws.com/LCD/collection/naip-2022-nccir-60cm/ | Jul 2022 (lake), Sep 2022 (coast) | Public domain (USDA FSA) |
| cover (coast: water, sand, marsh, impervious) | NOAA C-CAP 2020 1 m high-resolution land cover: https://tnris-data-warehouse.s3.us-east-1.amazonaws.com/LCD/collection/noaa-2020-ccap-landcover-1m/ | 2020 | Public domain (NOAA) |
| building footprints | Overture Maps Foundation, release 2026-09-23.1, buildings theme (s3://overturemaps-us-west-2/release/2026-09-23.1/theme=buildings/) | 2026 | ODbL 1.0. Add "Overture Maps Foundation, OpenStreetMap contributors" to CREDITS.md; the sim already credits OSM under ODbL |
| shore band masks | USGS 3DEP 1/3 arc-second DEM | current | Public domain |

Google 3D tiles were not used anywhere.

**Hosts blocked from the cloud:** the TNM API, the National Map image services, Planetary Computer, Overpass, Geofabrik, NOAA Digital Coast and data.geographic.texas.gov. The same data came from the S3 buckets above.

**Checked but not used:**
- StratMap 2026 building footprints: they don't cover Dallas, Rockwall or Galveston counties.
- NAIP 2024: county MrSID only, and there is no MrSID reader here.
- HGAC 2024 35 cm lidar (`usgs-2024-35cm-hgac`, same bucket): this is a possible later upgrade for Galveston, because it would pick up houses built since 2018.

## What was produced

| | Ray Hubbard | Galveston Bay |
|---|---|---|
| Tiles (with land) | 271 (238) | 812 (636) |
| Buildings | 35,310 (13,534 within 400 m) | 47,890 (23,657 within 400 m) |
| Lidar roof height | 31,551 | 43,685 |
| Roof type: gable / hip / flat / complex / none | 7,949 / 8,843 / 988 / 13,771 / 3,759 | 13,549 / 7,915 / 4,936 / 17,285 / 4,205 |
| Sim buildings matched (`sim_index`) | 11,519 of 11,719 | 9,076 of 9,652 |
| Trees | 412,058 (9,911 red cedar) | 665,350 |
| Shore: riprap / bulkhead / beach (km) | 6.7 / 14.6 / 37.3 | 157.6 / 88.5 / 413.2 |

**Sizes:**
- Ray Hubbard: dem 262 MB, dsm 358 MB, cover 46 MB, ortho 118 MB, buildings 46 MB, trees 104 MB.
- Galveston: dem 879 MB, dsm 1.1 GB, cover 116 MB, ortho 277 MB, buildings 61 MB, trees 167 MB.
- About 3.5 GB in all.
- That is too big for the repo's LFS quota. Bake from this folder on the Mac and commit only the baked game assets, not these tiles.

## Limits
- **`mean_rock_size_m` is null everywhere.** Rocks are 0.3 to 1 m across and the lidar has about 2.5 points per m², so single rocks can't be resolved. `roughness_m` is a relative proxy. As a rough guide, riprap with roughness 0.07 to 0.15 m usually means 0.3 to 0.6 m stone, but that conversion is an assumption, not a measurement.
- **Species:** see trees.geojson above.
- **Data age:** lidar is from 2018 and imagery from 2022. Houses built since then have imagery and a footprint but no lidar height, and new clearings may still show old trees.
- **Water level:** the DEM's water level is a single lidar-time snapshot, not pool or tide.
- **Rule-based classes:** cover and shore types follow simple rules, and their misses are noted in each section above.

## Re-running
The scripts are in `scripts/` and run in order:
1. `masks.py <Region>`
2. `naip_list.py`
3. `prep.py <Region>`
4. `runall.py <Region> 4`
5. `ortho.py <Region>`
6. `merge.py <Region>`
7. `preview.py`
8. `beachfix.py`
9. `beachfix2.py`

They need Python 3 with numpy, scipy, rasterio, pyproj, shapely, laspy[lazrs], scikit-image, pyarrow, pyshp and pillow. The paths are at the top of `common.py`.
