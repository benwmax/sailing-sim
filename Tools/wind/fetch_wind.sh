#!/usr/bin/env bash
# W1: fetches the free station data the wind field is calibrated against, into Data/Wind/raw (git-ignored).
#   NCEI ASOS one-minute data, page 1 (TD-6405: 2-minute mean wind and the highest 5-second wind each minute) for
#   Dallas Love Field (KDAL), Terrell (KTRL) and Dallas Executive (KRBD) over a year. Mesquite (KHQZ) is not in the
#   one-minute archive. Over land: an upper bound for the lake, converted to water roughness by fit_gusts.py.
#   NOAA CO-OPS (TCOON) Galveston Bay meteorological stations, 6-minute wind (speed, direction, gust) over the same year:
#   8771341 Galveston Bay Entrance North Jetty, 8771013 Eagle Point, 8770613 Morgans Point.
# Then: Tools/venv/bin/python Tools/wind/fit_gusts.py
set -euo pipefail
cd "$(dirname "$0")/../.."
YEAR="${YEAR:-2024}"
OUT=Data/Wind/raw
mkdir -p "$OUT/asos" "$OUT/coops"
for ST in KDAL KTRL KRBD; do
  for M in 01 02 03 04 05 06 07 08 09 10 11 12; do
    F="$OUT/asos/asos-1min-pg1-$ST-$YEAR$M.dat"
    [ -s "$F" ] && continue
    curl -sSf -m 120 --retry 3 -o "$F" \
      "https://www.ncei.noaa.gov/data/automated-surface-observing-system-one-minute-pg1/access/$YEAR/$M/asos-1min-pg1-$ST-$YEAR$M.dat" || { echo "missing $F"; rm -f "$F"; }
  done
done
for ST in 8771341 8771013 8770613; do
  for M in 01 02 03 04 05 06 07 08 09 10 11 12; do
    F="$OUT/coops/wind-$ST-$YEAR$M.csv"
    [ -s "$F" ] && continue
    END=$(python3 -c "import calendar; print(calendar.monthrange($YEAR, int('$M'))[1])")
    curl -sSf -m 120 --retry 3 -o "$F" \
      "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=wind&station=$ST&begin_date=$YEAR${M}01&end_date=$YEAR$M$END&time_zone=lst&units=metric&format=csv&application=sailing-sim" || { echo "missing $F"; rm -f "$F"; }
  done
done
du -sh "$OUT"/*
