# Portfolio data exports

Data only, exported from the game's build inputs and physics on Bean's Mac (no game code, no Content). Helpers: `Artifacts/claude-6e6e/portfolio/` on that Mac (not in the repo).

## j22-polar.csv

One row per point of the J/22 reference polar (`Source/SailingPhysics/Private/PolarReference.cpp`) beside the game's steady speed at the same true wind speed and angle (`SailSteady`: autopilot and auto-trim, best trim searched, lake chop for a 5 km fetch, main and jib only).

- `reference_kn`: ORC VPP polar for the J/22 one-design (median of 13 ORC certificates as tabulated by keelindex.com, cross-checked against the ORC 2021 J/22 One Design certificate). The beat points are beat VMG / cos(beat angle); 15 kn is interpolated between the 14 and 20 kn columns; 110 deg and deeper are an approximate non-spinnaker polar (ORC x 0.84 / 0.89 / 0.91). `reference_source` says which.
- `game_kn`, `heel_deg`, `leeway_deg`: the game's physics. `tolerance_pct` is the band the game's PolarGate test holds each point to.

## Lake Ray Hubbard layers (north up, same extent and grid)

Grid in `lake-grid.json`: 15 m pixels (every third cell of the game's 5 m bake), transverse Mercator centred on the map origin (NAD83). The map origin is Rush Creek Yacht Club, 32.8233 N, 96.5000 W.

| File | Layer | Source and licence |
|---|---|---|
| `lake-hillshade-usgs3dep.png` | Land hillshade (sun from the NW at 45 deg), water flat grey | USGS 3D Elevation Program, 1/3 arc-second DEM: public domain (credit "USGS") |
| `lake-bathymetry-twdb.png` | Depth below the 435.5 ft conservation pool, light to dark blue; land transparent | Texas Water Development Board, 2015 Volumetric Survey of Lake Ray Hubbard: public data (credit "TWDB") |
| `lake-osm.png` | Shoreline (the lake relation), docks and piers, bridges, buildings; transparent | © OpenStreetMap contributors, ODbL 1.0 (openstreetmap.org/copyright) |
| `lake-origin.png` | The map origin marker; transparent | this project |
| `lake-composite.jpg` | All four layers stacked | as above |

## storm-2023-06-11/

NOAA MRMS surface precipitation rate (PrecipRate, 2-minute product sampled every 4 minutes), 2023-06-11 21:30 UTC to 2023-06-12 01:30 UTC, cropped to the lake with its shoreline drawn over it; one PNG per frame, named `mrms-<YYYYMMDDTHHMM>Z.png` in UTC. Log colour scale, 0.1 to 200 mm/h; blank where the rate is under 0.1 mm/h. The red cross is the map origin. Source: NOAA/NSSL Multi-Radar Multi-Sensor, public domain (credit "NOAA MRMS"). Shoreline © OpenStreetMap contributors, ODbL 1.0.
