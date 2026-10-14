#!/usr/bin/env bash
# Graphics G3: the crew cloth scans, CC0 from ambientCG (https://ambientcg.com, no attribution required): Fabric070
# (sportswear knit), Fabric048 (polyester vest), Fabric036 (smooth woven), 2K JPG, about 85 MB, into Data/Fabrics/raw
# (git-ignored). scripts/make-content.sh imports them (make_materials.py, build_crew_fabric).
set -euo pipefail
cd "$(dirname "$0")/../.."
mkdir -p Data/Fabrics/raw
cd Data/Fabrics/raw
for a in Fabric070 Fabric048 Fabric036; do
	[ -d "$a" ] && continue
	curl -sS -L -m 600 -o "$a.zip" "https://ambientcg.com/get?file=${a}_2K-JPG.zip"
	mkdir -p "$a" && unzip -oq "$a.zip" -d "$a"
done
