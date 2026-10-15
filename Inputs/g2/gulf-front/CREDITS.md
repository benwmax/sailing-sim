# Credits: Galveston Gulf front

| what | source | date | licence |
|---|---|---|---|
| bare earth (dem), beach profiles, Seawall, groin crests | USGS 3DEP 1 m DEM, project `TX_CoastalRegion_2018_A18` (prd-tnm.s3.amazonaws.com) | lidar 2018 | public domain (USGS) |
| surface (dsm), building heights and roofs, trees, pier decks | USGS 3DEP lidar point clouds `TX_Coastal_B3_2018`, `TX_Coastal_B1_2018` (usgs-lidar-public.s3.amazonaws.com, Entwine) | 2018 | public domain (USGS) |
| ortho, cover classes, roof colours | USDA NAIP 2022 60 cm, via the TxGIO data hub (tnris-data-warehouse, `naip-2022-nccir-60cm`) | Sep 2022 | public domain (USDA FSA) |
| cover (water, sand, marsh) | NOAA C-CAP 2020 1 m land cover (tnris-data-warehouse, `noaa-2020-ccap-landcover-1m`) | 2020 | public domain (NOAA) |
| building footprints | Overture Maps Foundation release 2026-09-23.1, buildings theme (OpenStreetMap, Microsoft, Esri footprints) | 2026 | ODbL 1.0 |
| jetty-head lights, charted piers and groins | NOAA Electronic Navigational Charts (US5TXTED and the Gulf passage cells), as already baked into the sim's `Content/TerrainData` | current at the sim's chart fetch | public domain (NOAA) |

Checked but not used: the 2024 HGAC 50 cm lidar DEM (`usgs-2024-35cm-hgac`, public domain), which is hydro-flattened at the
jetty heads and has no point cloud for Galveston in the bucket; the 2023 lower Galveston Bay sonar bathymetry
(`stratmap-2023-lower-galveston-bay-bathy`), which is underwater only.

For the game's CREDITS.md: "Overture Maps Foundation, OpenStreetMap contributors (ODbL)" is the only line this pack needs
beyond the USGS, USDA and NOAA lines G2 already carries. Google tiles were not used.
