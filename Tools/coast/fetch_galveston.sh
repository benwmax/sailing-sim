#!/usr/bin/env bash
# Downloads the public data that Tools/coast/build_galveston.py bakes into Content/TerrainData (Galveston Bay).
# Everything lands in Data/GalvestonBay/raw (git-ignored). Takes several minutes; Overpass may rate-limit (retries
# built in). The tide and current reference predictions cover 12-26 October 2026: change the dates below to bake
# references for another fortnight (the tests compare the in-game predictor with whatever is baked).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RAW="$ROOT/Data/GalvestonBay/raw"
OVERPASS="$ROOT/Tools/terrain/overpass.sh"
B="29.29,-95.12,29.63,-94.66"   # south, west, north, east
API="https://api.tidesandcurrents.noaa.gov"
mkdir -p "$RAW/enc" "$RAW/tides" && cd "$RAW"

# NOAA ENC cells (S-57): harbor (US5) and approach (US4) scale, Clear Lake to Bolivar Roads.
curl -sS -m 120 -o ENCProdCat.xml https://charts.noaa.gov/ENCs/ENCProdCat.xml
for C in US4TX1MJ US4TX1MK US4TX1NJ US4TX1NK US5HOUAG US5HOUAH US5HOUAI US5HOUBF US5HOUBG US5HOUBH US5HOUBI \
		US5HOUCF US5HOUCI US5HOUDG US5HOUDH US5TX3GI US5TXTDA US5TXTDB US5TXTDC US5TXTDE US5TXTEA US5TXTEB US5TXTEC US5TXTED \
		US5HOUAJ US5HOUCG US5HOUCH US5TX3EE US5TXTDD US4TX1MI US4TX1NI; do
	curl -sS -m 120 -o "enc/$C.zip" "https://www.charts.noaa.gov/ENCs/$C.zip" && (cd enc && unzip -o -q "$C.zip")
done

# USGS 3DEP 1/3 arc-second DEM (NAVD88) through the National Map export service; the bake reads the real extent
# from the GeoTIFF tags.
curl -sS -m 900 -o dem_3dep.tif "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage?bbox=-95.12,29.29,-94.66,29.63&bboxSR=4326&imageSR=4326&size=3000,2220&format=tiff&pixelType=F32&noDataInterpretation=esriNoDataMatchAny&interpolation=RSP_BilinearInterpolation&f=image"

# NOAA CO-OPS: harmonic constituents, datums and station metadata for the five tide stations; NOAA's own
# predictions (high/low and 6-minute) as the test reference.
for ST in 8771450 8771341 8771013 8770613 8771486; do
	curl -sS -m 60 -o "tides/harcon_$ST.json" "$API/mdapi/prod/webapi/stations/$ST/harcon.json?units=metric"
	curl -sS -m 60 -o "tides/datums_$ST.json" "$API/mdapi/prod/webapi/stations/$ST/datums.json?units=metric"
	curl -sS -m 60 -o "tides/station_$ST.json" "$API/mdapi/prod/webapi/stations/$ST.json"
done
for ST in 8771450 8771013 8771341; do
	curl -sS -m 60 -o "tides/pred_hilo_$ST.json" "$API/api/prod/datagetter?product=predictions&station=$ST&begin_date=20261012&end_date=20261026&datum=MLLW&interval=hilo&units=metric&time_zone=gmt&format=json"
	curl -sS -m 60 -o "tides/pred_6min_$ST.json" "$API/api/prod/datagetter?product=predictions&station=$ST&begin_date=20261012&end_date=20261019&datum=MLLW&interval=6&units=metric&time_zone=gmt&format=json"
done
# Currents: Bolivar Roads (ACT8856, the reference) and a second station, harmonics (bin 2) and predictions.
curl -sS -m 60 -o tides/current_stations.json "$API/mdapi/prod/webapi/stations.json?type=currentpredictions&units=metric"
for S in ACT8856 ACT8851; do
	curl -sS -m 60 -o "tides/curharcon_$S.json" "$API/mdapi/prod/webapi/stations/$S/harcon.json?units=metric&bin=2"
	curl -sS -m 60 -o "tides/curpred_$S.json" "$API/api/prod/datagetter?product=currents_predictions&station=$S&bin=2&begin_date=20261012&end_date=20261019&interval=MAX_SLACK&units=english&time_zone=gmt&format=json"
done
curl -sS -m 60 -o tides/curpred6_ACT8856.json "$API/api/prod/datagetter?product=currents_predictions&station=ACT8856&bin=2&begin_date=20261012&end_date=20261015&interval=6&units=metric&time_zone=gmt&format=json"
curl -sS -m 60 -o tides/curpred6_ACT8856_month.json "$API/api/prod/datagetter?product=currents_predictions&station=ACT8856&bin=2&begin_date=20261001&end_date=20261031&interval=6&units=metric&time_zone=gmt&format=json"

# OpenStreetMap (ODbL): piers, breakwaters and marinas; land use and woods; buildings in four tiles (one query
# for the whole bay times out).
"$OVERPASS" "[out:json][timeout:250];(way[\"man_made\"~\"pier|breakwater|groyne\"]($B);nwr[\"leisure\"~\"marina|slipway\"]($B););out geom tags;" marinas_osm.json
sleep 10
"$OVERPASS" "[out:json][timeout:250];(way[\"landuse\"=\"forest\"]($B);way[\"natural\"~\"wood|wetland|scrub\"]($B);relation[\"natural\"=\"wood\"]($B);way[\"leisure\"~\"park|nature_reserve\"]($B);way[\"landuse\"~\"residential|commercial|industrial|grass|meadow|farmland\"]($B););out geom tags;" landuse_osm.json
I=0
for T in "29.29,-95.12,29.46,-94.89" "29.29,-94.89,29.46,-94.66" "29.46,-95.12,29.63,-94.89" "29.46,-94.89,29.63,-94.66"; do
	sleep 10
	"$OVERPASS" "[out:json][timeout:280];way[\"building\"]($T);out geom;" "buildings_osm_$I.json"
	I=$((I + 1))
done
echo "Fetched into $RAW"
