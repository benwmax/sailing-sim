# G2 shore data (prepared off the Mac, Oct 13 2026)

Read `DATA-README.md` (the data thread's full description: grids, datums, classes, limits) before using any of this.

What is here (per world; RayHubbard = EPSG:26914, GalvestonBay = EPSG:26915):
- `buildings.geojson.gz`, `trees.geojson.gz`, `shore_armour.geojson.gz`: gzip of the GeoJSON described in DATA-README.md
  (`gunzip -k` to expand). Buildings carry `sim_index`, `height_m`, `roof_type`, `ridge_dir_deg`, `roof_colour`,
  `dist_to_water_m` and a 1 m `roof_grid`.
- `tiles.json`: the 1 km tile list with lidar point counts, water level and grid convergence.
- `cover.tar.gz` (lake) and `cover.tar.gz.part00` + `part01` (coast; rejoin with
  `cat cover.tar.gz.part0* > cover.tar.gz`): the 0.5 m uint8 cover-class tiles. These are deflate GeoTIFFs already, so the
  tar is plain git, not LFS, and the parts keep each file under GitHub's 100 MB limit.
- `scripts/`: the Python that made everything (re-runnable; `runall.py` is the entry point, `tile.py` does the work).
- `piers/` (Galveston, added Oct 14 2026): piers, docks, bridges, moored boats (2018), marinas, jetties, groins, the Texas
  City Dike and the Seawall run inside the bay grid. Start with `piers/landmarks.geojson` and `piers/README.md`; the big
  layers are `.geojson.gz`. Made from the G2 tiles by `scripts/piers/run.sh` (numpy and Pillow only), so the Mac can
  rebuild it once it has rebuilt the dem/dsm/cover/ortho tiles. The scripts also gained a `GalvestonGulf` region for the
  Gulf front south of the bay grid (Seawall, Pleasure Pier, fishing piers); it has not been built yet (see piers/README.md).

Not here, because they are 3.2 GB and the Mac already downloads the same sources after Bean's approval: the 1 m `dem/`
and `dsm/` float32 tiles and the NAIP 2022 `ortho/` tiles. Rebuild them on the Mac from USGS 3DEP and NAIP with
`scripts/tile.py` (same tile grid as `tiles.json`) so the cover classes and buildings line up exactly.

Generator inputs only; nothing here is loaded by the game. Bake assets on the Mac and commit only the baked output.
