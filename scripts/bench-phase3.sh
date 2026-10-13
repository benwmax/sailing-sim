#!/usr/bin/env bash
# Phase 3 frame budget and reference screenshots on Lake Ray Hubbard, packaged build:
#   marina  : at the Rush Creek Yacht Club docks, all three quality tiers
#   bridge  : 340 m south of the I-30 main-channel bridge, looking north at it (Medium)
#   wide    : open water off Rush Creek with a high camera, so far terrain and trees stream in (Medium)
#   sailing : the autopilot sailing and tacking across the south lake while chunks stream (Medium)
# Writes Artifacts/phase3-bench.csv and copies the screenshots to docs/phase-3/.
source "$(dirname "$0")/env.sh"
SECONDS_PER_RUN="${1:-15}"
OUT="$ARTIFACTS/phase3-bench.csv"
mkdir -p "$REPO_ROOT/docs/phase-3"
echo "view,quality,avg_fps,p99_ms,resolution,gpu_ms,base_ms,lumen_ms,water_ms,clouds_fog_ms,niagara_ms,post_ms" > "$OUT"

run() # name quality demo args
{
	local NAME="$1" Q="$2" DEMO_FLAG="$3"; shift 3
	local SHOT_NAME="$NAME-$(echo "$Q" | tr "[:upper:]" "[:lower:]")"
	rm -f "$ARTIFACTS/bench.json"
	DEMO="$DEMO_FLAG" SHOT="$SHOT_NAME" ARGS="$* -SailingQuality=$Q" "$(dirname "$0")/bench-mac.sh" "$SECONDS_PER_RUN" > /dev/null || true
	python3 - "$ARTIFACTS/bench.json" "$NAME" "$Q" >> "$OUT" <<'PY'
import json, sys
G = ('total_ms', 'base_ms', 'lumen_ms', 'water_ms', 'clouds_fog_ms', 'niagara_ms', 'post_ms')
gpu = lambda b: ''.join(',' + str(b.get('gpu', {}).get(k, '')) for k in G)
try:
    b = json.load(open(sys.argv[1]))
    print(f"{sys.argv[2]},{sys.argv[3]},{b['avg_fps']},{b['p99_ms']},{b['resolution']}" + gpu(b))
except Exception:
    print(f"{sys.argv[2]},{sys.argv[3]},error,,,,,,,,,")
PY
	[[ -z "${NO_DOCS:-}" && -f "$ARTIFACTS/$SHOT_NAME.png" ]] && cp "$ARTIFACTS/$SHOT_NAME.png" "$REPO_ROOT/docs/phase-3/$SHOT_NAME.png" || true
}

COMMON="-SailingWeather=AfternoonBreeze -SailingHour=11 -SailingWind=10 -SailingKeepStart"
for Q in Low Medium High; do
	run marina "$Q" 0 "$COMMON -SailingLaunch=0 -SailingDrill=LeavetheDock -SailingCamYaw=60 -SailingCamPitch=-18 -SailingCamDist=40"
done
run bridge Medium 0 "$COMMON -SailingStartAt=7060,880,183 -SailingCamYaw=180 -SailingCamPitch=-4 -SailingCamDist=20"
run wide Medium 0 "$COMMON -SailingLaunch=1 -SailingCamYaw=135 -SailingCamPitch=-25 -SailingCamDist=250"
run sailing Medium 1 "-SailingWeather=AfternoonBreeze -SailingHour=15 -SailingWind=14 -SailingLaunch=2 -SailingTWA=60"
cat "$OUT"
