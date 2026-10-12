#!/usr/bin/env bash
# Downloads the public data that Tools/terrain/build_rayhubbard.py bakes into Content/TerrainData.
# Everything lands in Data/RayHubbard/raw (git-ignored). Takes a few minutes; Overpass may rate-limit (retries built in).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RAW="$ROOT/Data/RayHubbard/raw"
OVERPASS="$ROOT/Tools/terrain/overpass.sh"
UA="SailingSim/0.1 (github.com/benwmax/sailing-sim)"
B="32.78,-96.62,33.025,-96.445"   # south, west, north, east
mkdir -p "$RAW" && cd "$RAW"

# USGS 3DEP 1/3 arc-second DEM through the National Map export service. The service widens the box to keep
# square pixels; the bake reads the real extent from the GeoTIFF tags.
curl -sS -m 600 -o dem_3dep.tif "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage?bbox=-96.62,32.78,-96.445,33.025&bboxSR=4326&imageSR=4326&size=1640,2720&format=tiff&pixelType=F32&noDataInterpretation=esriNoDataMatchAny&interpolation=RSP_BilinearInterpolation&f=image"

# TWDB 2015 volumetric survey (interpolated bottom points) and the daily level record.
curl -sS -m 600 -o twdb_shapefiles.zip "https://www.twdb.texas.gov/hydro_survey/RayHubbard/2015-08/Shapefiles.zip"
mkdir -p twdb && (cd twdb && unzip -o -q ../twdb_shapefiles.zip)
curl -sS -m 60 -A "$UA" -o level.csv "https://waterdatafortexas.org/reservoirs/individual/ray-hubbard.csv"

# OpenStreetMap (ODbL): the lake multipolygon, then docks, bridges, land use and buildings.
"$OVERPASS" "[out:json][timeout:200];relation(952396);out geom;" lake_osm.json; sleep 10
"$OVERPASS" "[out:json][timeout:100];way[\"man_made\"~\"pier|breakwater\"](around:900,32.8233,-96.5);out geom tags;" club_osm.json; sleep 10
"$OVERPASS" "[out:json][timeout:200];(way[\"bridge\"][\"highway\"]($B);way[\"bridge\"][\"railway\"]($B);way[\"highway\"~\"motorway|trunk|primary\"][\"embankment\"]($B););out geom tags;" bridges_osm.json; sleep 10
"$OVERPASS" "[out:json][timeout:250];(way[\"landuse\"=\"forest\"]($B);way[\"natural\"=\"wood\"]($B);relation[\"natural\"=\"wood\"]($B);relation[\"landuse\"=\"forest\"]($B);way[\"leisure\"~\"park|nature_reserve\"]($B);way[\"landuse\"~\"residential|commercial|industrial|grass|meadow|farmland\"]($B););out geom tags;" landuse_osm.json; sleep 10
"$OVERPASS" "[out:json][timeout:280];way[\"building\"]($B);out geom;" buildings_osm.json; sleep 10
"$OVERPASS" "[out:json][timeout:200];(nwr[\"leisure\"~\"marina|slipway\"]($B);nwr[\"man_made\"~\"pier|breakwater\"]($B);nwr[\"name\"~\"Robertson|Harry Myers|Rockwall Harbor|Chandlers|Sapphire|Lakeside Village\",i]($B););out geom tags;" marinas_osm.json
ls -la "$RAW"
