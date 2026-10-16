#!/bin/zsh
# Crew C1b: fetches the CMU Graphics Lab motion capture trials the crew idles are baked from (Tools/crew/bake_idles.py)
# into Data/CMU/raw (git-ignored). Only the trials listed in Tools/crew/clips.csv, one request each: the site asks not
# to be crawled. Licence (mocap.cs.cmu.edu): free to use, may be included in commercially sold products, may not be
# resold directly, even converted. Credit in CREDITS.md and docs/licences/assets.csv.
set -e
cd "$(dirname "$0")/../.."
OUT=Data/CMU/raw
mkdir -p "$OUT"
typeset -A subjects
for trial in $(awk -F, 'NR > 1 && $1 !~ /^#/ { print $2 }' Tools/crew/clips.csv | sort -u); do
  s=${trial%%_*}
  subjects[$s]=1
  [[ -s "$OUT/$trial.amc" ]] || curl -sfL --max-time 120 -o "$OUT/$trial.amc" "http://mocap.cs.cmu.edu/subjects/$s/$trial.amc"
  echo "$trial.amc $(wc -c < "$OUT/$trial.amc") bytes"
done
for s in ${(k)subjects}; do
  [[ -s "$OUT/$s.asf" ]] || curl -sfL --max-time 60 -o "$OUT/$s.asf" "http://mocap.cs.cmu.edu/subjects/$s/$s.asf"
done
