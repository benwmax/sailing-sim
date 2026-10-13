#!/usr/bin/env bash
# Phase 6 traffic and races on the packaged build at the default (Medium) tier: busy lake traffic, a race, the bay
# with ships, the bay at night (vessels' lights), the chart with AIS targets. Records fps and p99 frame time and copies
# each screenshot to docs/phase-6/<view>.png.
# Writes Artifacts/phase6-bench.csv. Leave the windows visible: macOS throttles hidden ones.
source "$(dirname "$0")/env.sh"
SECONDS_PER_RUN="${1:-12}"
OUT="$ARTIFACTS/phase6-bench.csv"
mkdir -p "$REPO_ROOT/docs/phase-6"
COMMON="-SailingQuality=Medium -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingTWA=60 -SailingHoldTWA=60"
VIEWS=(
	"lake-busy|-SailingWorld=0 -SailingLaunch=1 -SailingTraffic=2 -SailingHour=13 -SailingCamYaw=200 -SailingCamPitch=-12 -SailingCamDist=60"
	"lake-race|-SailingWorld=0 -SailingLaunch=1 -SailingTraffic=1 -SailingRace=8 -SailingHour=13 -SailingCamYaw=200 -SailingCamPitch=-14 -SailingCamDist=45"
	"bay-ships|-SailingWorld=1 -SailingLaunch=3 -SailingTraffic=2 -SailingTrafficNear -SailingHour=11 -SailingCamYaw=120 -SailingCamPitch=-8 -SailingCamDist=90"
	"bay-night-traffic|-SailingWorld=1 -SailingLaunch=3 -SailingTraffic=2 -SailingTrafficNear -SailingHour=21 -SailingCamYaw=120 -SailingCamPitch=-6 -SailingCamDist=40"
	"bay-chart-ais|-SailingWorld=1 -SailingLaunch=3 -SailingTraffic=2 -SailingTrafficNear -SailingHour=11 -SailingChart=10"
)
echo "view,avg_fps,p99_ms" > "$OUT"
for V in "${VIEWS[@]}"; do
	NAME="${V%%|*}"; EXTRA="${V#*|}"
	SHOT="$NAME"
	for TRY in 1 2; do # a launch occasionally fails to report; try once more
		rm -f "$ARTIFACTS/bench.json"
		DEMO=1 SHOT="$SHOT" ARGS="$COMMON $EXTRA" "$(dirname "$0")/bench-mac.sh" "$SECONDS_PER_RUN" > /dev/null || true
		[[ -f "$ARTIFACTS/bench.json" ]] && break
	done
	python3 - "$ARTIFACTS/bench.json" "$NAME" >> "$OUT" <<'PY'
import json, sys
try:
    b = json.load(open(sys.argv[1])); print(f"{sys.argv[2]},{b['avg_fps']},{b['p99_ms']}")
except Exception:
    print(f"{sys.argv[2]},error,")
PY
	[[ -z "${NO_DOCS:-}" && -f "$ARTIFACTS/$SHOT.png" ]] && cp "$ARTIFACTS/$SHOT.png" "$REPO_ROOT/docs/phase-6/$SHOT.png" || true
done
cat "$OUT"
