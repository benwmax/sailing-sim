#!/usr/bin/env bash
# Phase 8 on the packaged build at the default (Medium) tier: the reference capture mode's cameras (helm eye, action
# cam with its lens distortion, drone, shore tele on a storm) and night under a full moon. Records fps and p99 and
# copies each screenshot to docs/phase-8/<view>.png. Writes Artifacts/phase8-bench.csv.
# Then the full regression: NO_DOCS=1 bench-phase2..7 (fps only; their published screenshots are left alone).
# Usage: scripts/bench-phase8.sh [seconds] [--regression]
source "$(dirname "$0")/env.sh"
SECONDS_PER_RUN="${1:-12}"
OUT="$ARTIFACTS/phase8-bench.csv"
mkdir -p "$REPO_ROOT/docs/phase-8"
COMMON="-SailingQuality=Medium -SailingWorld=Lake -SailingLaunch=1"
VIEWS=(
	"helm-eye|-SailingCapture=HelmEye -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingHour=15 -SailingTWA=45 -SailingHoldTWA=45"
	"action-cam|-SailingCapture=ActionCam -SailingWeather=AfternoonBreeze -SailingWind=9 -SailingHour=11 -SailingTWA=60 -SailingHoldTWA=60"
	"drone|-SailingCapture=Drone -SailingWeather=AfternoonBreeze -SailingWind=14 -SailingHour=13 -SailingTWA=90 -SailingHoldTWA=90"
	"storm-shore|-SailingCapture=ShoreTele -SailingWeather=Thunderstorm -SailingWeatherTime=150 -SailingHour=16 -SailingTWA=60 -SailingHoldTWA=60 -SailingCaptureBearing=150"
	"full-moon|-SailingCapture=Chase -SailingDate=2024-10-17 -SailingWeather=CalmMorning -SailingWind=6 -SailingHour=22.5 -SailingTWA=90 -SailingHoldTWA=90"
)
echo "view,avg_fps,p99_ms,gpu_ms,base_ms,lumen_ms,water_ms,clouds_fog_ms,niagara_ms,post_ms" > "$OUT"
for V in "${VIEWS[@]}"; do
	NAME="${V%%|*}"; EXTRA="${V#*|}"
	for TRY in 1 2; do
		rm -f "$ARTIFACTS/bench.json"
		SHOT="$NAME" ARGS="$COMMON $EXTRA" "$(dirname "$0")/bench-mac.sh" "$SECONDS_PER_RUN" > /dev/null || true
		[[ -f "$ARTIFACTS/bench.json" ]] && break
	done
	python3 - "$ARTIFACTS/bench.json" "$NAME" >> "$OUT" <<'PY'
import json, sys
G = ('total_ms', 'base_ms', 'lumen_ms', 'water_ms', 'clouds_fog_ms', 'niagara_ms', 'post_ms')
gpu = lambda b: ''.join(',' + str(b.get('gpu', {}).get(k, '')) for k in G)
try:
    b = json.load(open(sys.argv[1])); print(f"{sys.argv[2]},{b['avg_fps']},{b['p99_ms']}" + gpu(b))
except Exception:
    print(f"{sys.argv[2]},error,,,,,,,,")
PY
	[[ -z "${NO_DOCS:-}" && -f "$ARTIFACTS/$NAME.png" ]] && cp "$ARTIFACTS/$NAME.png" "$REPO_ROOT/docs/phase-8/$NAME.png" || true
done
cat "$OUT"
if [[ "${2:-}" == "--regression" ]]; then
	for P in 2 3 4 5 6 7; do
		echo "== phase $P"
		NO_DOCS=1 "$(dirname "$0")/bench-phase$P.sh" "$SECONDS_PER_RUN" | tail -12
	done
fi
