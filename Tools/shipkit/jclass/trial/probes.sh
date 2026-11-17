#!/usr/bin/env bash
# Bluebonnet's knob probes (slice 13; docs/jclass-13's table "For the Mac's half"): a few TRIAL_SET knob sets, each
# sailed with --point (one run at the trimmer's default settings, its last 5 s sample), at the points that show them:
# the best beat VMG in 12 kn over TWA 32 to 40, 10 kn at 52, 16 kn at 90 (with the helm) and 6 kn at 90. Usage:
#   Tools/shipkit/jclass/trial/probes.sh <build dir>      (after trial.sh has built <build dir>/trial_sail; a minute)
set -euo pipefail
B="$(cd "$1" && pwd)/trial_sail"
cd "$(dirname "$0")/../../../.."
echo "# TRIAL_SET probes: one --point run each (the trimmer's default settings), the last 5 s sample"
echo "# knobs | 12 kn beat: best VMG over TWA 32-40 (speed at the TWA sailed, helm) | 10 kn 52 | 16 kn 90 (helm) | 6 kn 90"
for s in "" "residuary=0.8" "residuary=0.6" "residuary=0.6,keel_ar=1.3" "rudder_area=10"; do
  best=""; bv=0
  for a in 32 34 36 38 40; do
    r=$(TRIAL_SET="$s" "$B" /dev/null --point 12 "$a" 2>&1 | tail -1)
    v=$(echo "$r" | awk '{printf "%.2f", $3 * cos($6 * 3.14159265 / 180)}')
    if awk "BEGIN { exit !($v > $bv) }"; then
      bv=$v
      best=$(echo "$r" | awk '{printf "%.2f kn at %.1f, helm %.1f", $3, $6, -$14}')
    fi
  done
  p1=$(TRIAL_SET="$s" "$B" /dev/null --point 10 52 2>&1 | tail -1 | awk '{printf "%.2f", $3}')
  p2=$(TRIAL_SET="$s" "$B" /dev/null --point 16 90 2>&1 | tail -1 | awk '{printf "%.2f (helm %.1f)", $3, -$14}')
  p3=$(TRIAL_SET="$s" "$B" /dev/null --point 6 90 2>&1 | tail -1 | awk '{printf "%.2f", $3}')
  echo "${s:-as the sheet has them} | $bv ($best) | $p1 | $p2 | $p3"
done
