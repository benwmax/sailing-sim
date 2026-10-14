#!/bin/sh
# Galveston Gulf front: build the GalvestonGulf G2 region (29.20 N to 1 km past the bay grid's south edge) and the
# Gulf-front pack from it. Downloads: USGS 3DEP (prd-tnm, usgs-lidar-public), TxGIO NAIP 2022 and NOAA C-CAP
# (tnris-data-warehouse), Overture buildings (overturemaps-us-west-2). About 2.5 h on 4 cores, mostly tile.py.
# Env: G2_OUT = output root (the sailing-sim-g2 folder), SIM_REPO = sailing-sim checkout, G2_WORK / G2_SRC = scratch
#      (default /tmp/g2/work and /tmp/g2/src), GULF_DEST = pack folder (default $G2_OUT/GalvestonBay/gulf-front).
# Needs in G2_SRC first (see README "Rebuild"): naipidx/ (NAIP 2022 index shapefile, no .cpg), naip/*.jp2 (from
# naip_list.py's list), dem_TX_CoastalRegion_2018_A18.txt (S3 key list), empty bldg/ and ept/.
set -e
cd "$(dirname "$0")/.."
export G2_REGIONS=GalvestonGulf
python3 masks.py GalvestonGulf
python3 naip_list.py
python3 overture.py
python3 prep.py GalvestonGulf
python3 runall.py GalvestonGulf 4
python3 ortho.py GalvestonGulf
python3 merge.py GalvestonGulf
python3 beachfix.py && python3 beachfix2.py
SEAWALL_SAND_MIN=0.15 sh piers/run.sh GalvestonGulf 4     # narrow beach in front of the western Seawall
python3 -I gulf/build.py
python3 -I gulf/package.py "$@"                              # add --rasters to copy the dem/dsm/cover/ortho tiles too
python3 -I gulf/preview.py "${GULF_DEST:-$G2_OUT/GalvestonBay/gulf-front}/preview_gulf_front.png"
