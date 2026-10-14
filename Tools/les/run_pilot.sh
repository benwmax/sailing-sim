#!/usr/bin/env bash
# Water W6 LES pilot: sets up and runs ntxcbl on the GPU (MicroHH built with CUDA in /opt/les/microhh/build).
# Usage (WSL): Tools/les/run_pilot.sh [work dir, default /root/les-runs/ntxcbl]
# Restartable: MicroHH writes restart files every savetime (1 h); rerunning picks up from the last one.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${1:-/root/les-runs/ntxcbl}"
MHH=/opt/les/microhh
export PATH=/usr/local/cuda/bin:/usr/bin:/bin
mkdir -p "$WORK"
cd "$WORK"
cp "$HERE/ntxcbl.ini" "$HERE/ntxcbl_input.py" .
python3 ntxcbl_input.py
LAST=$(ls -1 time.* 2>/dev/null | sort | tail -1 | sed 's/time\.//' || true)
if [[ -z "$LAST" ]]; then
	"$MHH/build/microhh" init ntxcbl > init.log 2>&1
	START=0
else
	START=$((10#$LAST))
	sed -i "s/^starttime=.*/starttime=$START/" ntxcbl.ini
fi
echo "starting at t = $START s"
"$MHH/build/microhh" run ntxcbl > "run-$START.log" 2>&1
echo "done: $(tail -1 "run-$START.log")"
