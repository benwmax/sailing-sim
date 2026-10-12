#!/usr/bin/env bash
# Downloads the public data that Tools/coast/build_galveston.py bakes for the Gulf passage (Galveston to Freeport):
# NOAA ENC cells and CO-OPS tide stations, into Data/GulfPassage/raw (git-ignored). Run: Tools/coast/fetch_gulf.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RAW="$ROOT/Data/GulfPassage/raw"
API="https://api.tidesandcurrents.noaa.gov"
mkdir -p "$RAW/enc" "$RAW/tides" && cd "$RAW"

# Offshore (1:180,000) and approach (1:45,000-90,000) cells, the Freeport and Galveston entrance harbor cells.
for C in US3TX1DC US4TX1LI US4TX1LJ US4TX1LK US4TX1MI US4TX1MJ US4TX1MK US4TX1KI US4TX1KJ \
		US5FPOBB US5FPOBC US5FPOCA US5FPOCB US5FPOCC US5FPODA US5FPODB US5TXTDB US5TXTDC US5TXTDD US5TXTDE US5TXTDF \
		US5TXTEC US5TXTED US5TXTEE; do
	curl -sS -m 120 -o "enc/$C.zip" "https://www.charts.noaa.gov/ENCs/$C.zip" && (cd enc && unzip -o -q "$C.zip")
done
# Tide stations on the open coast: Galveston Pleasure Pier, North Jetty, San Luis Pass, Freeport.
for ST in 8771510 8771341 8771972 8772447; do
	curl -sS -m 60 -o "tides/harcon_$ST.json" "$API/mdapi/prod/webapi/stations/$ST/harcon.json?units=metric"
	curl -sS -m 60 -o "tides/datums_$ST.json" "$API/mdapi/prod/webapi/stations/$ST/datums.json?units=metric"
	curl -sS -m 60 -o "tides/station_$ST.json" "$API/mdapi/prod/webapi/stations/$ST.json"
done
echo "Fetched into $RAW"
