#!/usr/bin/env bash
# Water W6 LES: sets up and runs a case (ntxcbl: the uniform pilot; ntxlake: over Lake Ray Hubbard's outline) on the GPU
# (MicroHH built with CUDA in /opt/les/microhh/build).
# Usage (WSL): Tools/les/run_pilot.sh [case, default ntxcbl] [work dir, default /root/les-runs/<case>]
# Restartable: MicroHH writes restart files every savetime (1 h); rerunning picks up from the last one.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
CASE="${1:-ntxcbl}"
WORK="${2:-/root/les-runs/$CASE}"
MHH=/opt/les/microhh
export PATH=/usr/local/cuda/bin:/usr/bin:/bin
mkdir -p "$WORK"
cd "$WORK"
cp "$HERE/$CASE.ini" "$HERE/ntxcbl_input.py" .
[[ -f "$HERE/${CASE}_input.py" ]] && cp "$HERE/${CASE}_input.py" .
[[ -f "$HERE/ntxcbl.ini" ]] && cp "$HERE/ntxcbl.ini" .   # ntxlake's input script reads the pilot's profile code
python3 "${CASE}_input.py"
LAST=$(ls -1 time.* 2>/dev/null | sort | tail -1 | sed 's/time\.//' || true)
if [[ -z "$LAST" ]]; then
	"$MHH/build/microhh" init "$CASE" > init.log 2>&1
	START=0
else
	START=$((10#$LAST))
	sed -i "s/^starttime=.*/starttime=$START/" "$CASE.ini"
fi
echo "starting $CASE at t = $START s"
"$MHH/build/microhh" run "$CASE" > "run-$START.log" 2>&1
echo "done: $(tail -1 "run-$START.log")"
