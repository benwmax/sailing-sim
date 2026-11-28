# Florida to the Bahamas: free data sources and their licences

Survey for the big Florida-to-Bahamas map (plan: "Huge maps without memory growth", approved by Bean Nov 27 2026).
Bean may sell the game, so a source is usable only if its terms allow commercial use (CLAUDE.md rule 21). Each source
below says what it gives, how good it is here, its licence, and whether a cloud session could reach it on Nov 27 2026
(most of these hosts refuse cloud sessions; the Mac fetched Galveston's and Marseille's data from the same kind of
host, so the fetch runs there).

**The short version.** The Florida side is excellent: US government data is public domain and very detailed (1 m
lidar on land, surveyed depths in the bay, official charts, tide stations). The Bahamas side is thin: no free lidar, no
free official chart of its own, no NOAA tide station. For Bimini, NOAA's own US chart 11469 ("Fowey Rocks, Hillsboro
Inlet to Bimini Islands, Bahamas") reaches the islands, so stage 1 still has an official chart. Past Bimini (stage 2:
the Berry Islands and Nassau) the depths come from global grids and satellite estimates, and the reefs, cays and
harbours need hand work.

## Florida (Miami, Biscayne Bay, the Florida reef)

| Data | Source | Detail | Licence | Commercial | Cloud reach |
|---|---|---|---|---|---|
| Chart: depths, shoreline, buoys, lights, bridges | NOAA ENC (S-57), picked by box from NOAA's catalog | Harbour scale in the bay and Government Cut | US government work, public domain | Yes | No (charts.noaa.gov refused) |
| Land heights | USGS 3DEP 1/3 arc-second DEM (about 10 m) | Bare earth, NAVD88 | Public domain | Yes | Export service no; prd-tnm S3 yes |
| Shore detail | USGS 3DEP 1 m lidar DEM, project FL_MiamiDade_D23 (2023) | 1 m along the shore | Public domain | Yes | Yes (prd-tnm S3 lists it) |
| Shore and shallow-water heights together | NOAA NCEI CUDEM 1/9 arc-second topobathy tiles (about 3 m), and the NOAA NGS topobathy lidar (West Biscayne Bay 2018; Fort Lauderdale to Miami 2017) | Land and sea bed in one surface, bay and reef flats | Public domain (NOAA) | Yes | No (coast.noaa.gov, ncei.noaa.gov refused) |
| Bay depths | NOAA NOS Biscayne Bay estuarine bathymetry DEM (1/3 arc-second, MLLW) | Surveyed bay floor | Public domain | Yes | No |
| Tides | NOAA CO-OPS harmonic constituents and datums: Virginia Key 8723214 is the reference; the fetch lists every station in the box | Same predictor the Texas coast uses | Public domain | Yes | No (api.tidesandcurrents refused) |
| Lights | US Coast Guard Light List Vol. III (and the ENC's own lights) | Characters and ranges | Public domain | Yes | Not tried |
| Buildings | Overture Maps buildings (OpenStreetMap plus Microsoft and Google footprints) | Miami box: 235,768 footprints, 98% with a height or floor count (Miami-Dade's import into OSM) | ODbL 1.0 (OSM-derived); Microsoft footprints ODbL, Google Open Buildings CC BY 4.0 / ODbL in Overture | Yes, with credit | Yes (Overture S3) |
| Trees, land use | OpenStreetMap | Parks, mangroves, residential | ODbL 1.0 | Yes, with credit | Overpass no (Mac yes) |

## Across the Gulf Stream (the Florida Straits)

| Data | Source | Detail | Licence | Commercial | Cloud reach |
|---|---|---|---|---|---|
| Depths | NOAA ENC overview and approach cells (chart 11469, and 11013 at small scale) | Contours and soundings to about 900 m | Public domain | Yes | No |
| Depths, backup | GEBCO 2025 grid | 15 arc-seconds (about 450 m) | Public domain; credit asked | Yes | No (gebco.net refused) |
| Gulf Stream, monthly means | Copernicus Marine GLOBAL_MULTIYEAR_PHY_001_030 (reanalysis, 1/12 degree, uo/vo) | Monthly surface current, 1993 on | Copernicus Marine licence: free, commercial use allowed, credit "Source: E.U. Copernicus Marine Service Information" | Yes, with credit | No (needs a free account; the Mac runs `copernicusmarine subset`) |
| Gulf Stream, second source | HYCOM GOFS 3.1 reanalysis (water_u/water_v) | 1/12 degree | DoD Distribution A, public release, unlimited distribution; HYCOM says public domain (forum, not a formal licence) | Yes (treat as public domain, credit HYCOM) | No (hycom.org refused) |
| Gulf Stream strength by season | NOAA AOML Florida Current cable transport at 27 N (daily since 1982) | Mean about 32 Sv, highest in summer | Public domain | Yes | No |
| Winds | NOAA NDBC Fowey Rocks (FWYF1) and ERA5 (Copernicus Climate Change Service licence, commercial use allowed with credit) | Station and reanalysis climate | Public domain / Copernicus licence | Yes | Not tried |

## Bimini and the Great Bahama Bank (stage 1's far side)

| Data | Source | Detail | Licence | Commercial | Cloud reach |
|---|---|---|---|---|---|
| Chart | NOAA ENC cells behind chart 11469 (to the Bimini Islands) | Approach scale; harbour detail probably thin, from older foreign surveys | Public domain | Yes | No |
| Land heights | Copernicus DEM GLO-30 | 30 m surface model (roofs and trees included); islands are only a few metres high, so the bake uses flat low land | Free with attribution, commercial allowed | Yes, with credit | No (its S3 refused here; reachable from the Mac before) |
| Bank depths, backup | GEBCO 2025; ICESat-2 ATL24 near-shore bathymetry (NASA, public domain) where tracks cross | 450 m grid; spot tracks to about 20 m deep | Public domain | Yes | No |
| Reefs and sea-floor type | Allen Coral Atlas (geomorphic and benthic maps, 5 m) | Reef crests, sand, seagrass: what the water colour and the hand work need | v1 is CC BY 4.0; v2's terms not confirmed | **Check before use** | No |
| Buildings | Overture Maps | Bimini box: 1,530 footprints (1,208 OSM, 298 Google, 24 Microsoft), almost none with a height | ODbL / CC BY 4.0 | Yes, with credit | Yes |
| Tides | No NOAA station. FES2022 tide model (AVISO), already cleared for commercial use (ship baked constituents only) | Global model, fine for Bimini's open coast | AVISO licence, commercial OK | Yes | Not tried |
| Lights | NGA Pub 110 (Greenland, East Coasts of N. and S. America, West Indies), the ENC's lights | Characters and ranges | US public domain | Yes | No (msi.nga.mil refused) |

## Stage 2 preview: the Berry Islands and Nassau

No NOAA chart reaches them. Depths come from GEBCO plus satellite-derived estimates, reefs from the Allen Coral Atlas
(once its licence is confirmed), coastlines from OpenStreetMap, buildings from Overture (Berry Islands 1,711 footprints;
New Providence 100,728, 72,774 of them from OSM, almost none with heights). Excluded: the UKHO/Bahamas official charts
(not free), NGA DNC (restricted outside the US), Navionics and other commercial charts, EOX Sentinel-2 cloudless
(non-commercial).

## What was checked from the cloud on Nov 27 2026

Reachable: Overture S3 (building counts above, release 2026-11-18.0), USGS prd-tnm S3 (1 m projects
FL_MiamiDade_D23, FL_Southeast_B1/B2/TL_2018, FL_Peninsular_2018), usgs-lidar-public (FL_TopobathyFLKeysNOAA). Refused:
charts.noaa.gov, coast.noaa.gov, ncei.noaa.gov, api.tidesandcurrents.noaa.gov, the Copernicus DEM bucket, gebco.net,
Copernicus Marine, hycom.org, msi.nga.mil, allencoralatlas.org, Overpass, Geofabrik, AOML, NASA Earthdata. So the fetch
(`Tools/coast/fetch_miami_bimini.py`) runs on the Mac, after the Dec 11 release work frees it.

## Still to confirm

1. Allen Coral Atlas v2 terms (v1 was CC BY 4.0). Until then it is reference only, not baked into the game.
2. Which ENC cells cover Bimini and at what scale (the fetch prints the list; `--list` shows it without downloading).
3. HYCOM: written confirmation of public domain would be nice; Copernicus Marine alone is enough, so this is optional.
4. Licence texts saved to `Inputs/licences/` on the inputs branch, rows in `docs/licences/assets.csv` and lines in
   `CREDITS.md` with the first bake that ships (Copernicus Marine, Copernicus DEM, GEBCO, Overture/OSM, FES2022).

Sources: [NOAA chart 11469](https://www.amnautical.com/a/s/products/noaa-nautical-chart-11469-straits-of-florida-fowey-rocks-hillsboro-inlet-to-bimini-islands-bahamas),
[NCEI CUDEM 1/9 arc-second](https://catalog.data.gov/dataset/continuously-updated-digital-elevation-model-cudem-1-9-arc-second-resolution-bathymetric-t),
[Biscayne Bay bathymetric DEM](https://catalog.data.gov/dataset/biscayne-bay-s200-bathymetric-digital-elevation-model-noaa-nos-estuarine-bathymetry),
[2018 NGS topobathy lidar, West Biscayne Bay](https://www.fisheries.noaa.gov/inport/item/58261),
[Copernicus Marine service commitments and licence](https://marine.copernicus.eu/user-corner/service-commitments-and-licence),
[Copernicus Marine citation](https://help.marine.copernicus.eu/en/articles/4444611-how-to-cite-or-reference-copernicus-marine-products-and-services),
[HYCOM data acknowledgement](https://hycom.org/publications/acknowledgements/hycom-data),
[HYCOM forum on commercial use](https://groups.google.com/a/hycom.org/g/forum/c/Ry2SV_c6ODA),
[Allen Coral Atlas v1 (CC BY 4.0)](https://developers.google.com/earth-engine/datasets/catalog/ACA_reef_habitat_v1_0),
[Allen Coral Atlas v2](https://developers.google.com/earth-engine/datasets/catalog/ACA_reef_habitat_v2_0).
