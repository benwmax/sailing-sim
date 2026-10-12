#!/usr/bin/env bash
# Overpass query with retries (the public server rate-limits). Usage: overpass.sh <query> <out.json>
set -euo pipefail
for TRY in 1 2 3 4 5 6; do
	curl -s -m 300 -A "SailingSim/0.1 (ben@benjaminwmaxwell.com)" --data-urlencode "data=$1" https://overpass-api.de/api/interpreter -o "$2" || true
	if head -c 1 "$2" 2>/dev/null | grep -q '{'; then exit 0; fi
	sleep $((TRY * 15))
done
echo "Overpass failed" >&2; exit 1
