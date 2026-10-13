#!/usr/bin/env bash
# Visual phases: a representative set of views (lake beam reach, lake beat with tacking, storm, marina, Galveston day
# and night, Gulf sea, the helm eye) on each quality tier of the packaged build, with GPU time per budget slice.
# Writes Artifacts/visual-bench-<label>.csv; with DOCS=<dir> also copies each screenshot there as <view>-<tier>.png.
# Usage: scripts/bench-visual.sh [seconds] [label] [tiers...]   e.g. scripts/bench-visual.sh 12 before Medium High
source "$(dirname "$0")/env.sh"
SECONDS_PER_RUN="${1:-12}"; LABEL="${2:-run}"; shift 2 || true
TIERS=("$@"); [[ ${#TIERS[@]} -eq 0 ]] && TIERS=(Low Medium High)
OUT="$ARTIFACTS/visual-bench-$LABEL.csv"
VIEWS=(
	"beam8|-SailingWorld=Lake -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingHour=12 -SailingWind=8 -SailingTWA=90 -SailingHoldTWA=90 -SailingCamYaw=200 -SailingCamPitch=-10"
	"beat15|-SailingWorld=Lake -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingHour=16 -SailingWind=15 -SailingTWA=45"
	"storm|-SailingWorld=Lake -SailingLaunch=1 -SailingWeather=Thunderstorm -SailingHour=16 -SailingWeatherTime=200 -SailingTWA=100 -SailingHoldTWA=100 -SailingCamYaw=200 -SailingCamPitch=-8"
	"marina|-SailingWorld=Lake -SailingLaunch=0 -SailingWeather=AfternoonBreeze -SailingHour=10 -SailingWind=6 -SailingCamYaw=150 -SailingCamPitch=-12 -SailingCamDist=40"
	"coast-day|-SailingWorld=1 -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingTWA=60 -SailingHoldTWA=60 -SailingHour=11 -SailingCamYaw=250 -SailingCamPitch=-10"
	"coast-night|-SailingWorld=1 -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingTWA=60 -SailingHoldTWA=60 -SailingHour=21 -SailingCamYaw=150 -SailingCamPitch=-6 -SailingCamDist=14"
	"gulf-sea|-SailingWorld=Gulf -SailingLaunch=2 -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingTWA=60 -SailingHoldTWA=60 -SailingHour=11 -SailingCamYaw=200 -SailingCamPitch=-5 -SailingCamDist=22"
	"helm-eye|-SailingWorld=Lake -SailingLaunch=1 -SailingCapture=HelmEye -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingHour=15 -SailingTWA=45 -SailingHoldTWA=45"
)
echo "view,quality,avg_fps,p99_ms,gpu_ms,base_ms,lumen_ms,water_ms,clouds_fog_ms,niagara_ms,post_ms,other_ms" > "$OUT"
for V in "${VIEWS[@]}"; do
	NAME="${V%%|*}"; EXTRA="${V#*|}"
	for Q in "${TIERS[@]}"; do
		SHOT="$NAME-$(echo "$Q" | tr '[:upper:]' '[:lower:]')"
		for TRY in 1 2; do
			rm -f "$ARTIFACTS/bench.json"
			DEMO=1 SHOT="$SHOT" ARGS="$EXTRA -SailingQuality=$Q" "$(dirname "$0")/bench-mac.sh" "$SECONDS_PER_RUN" > /dev/null || true
			[[ -f "$ARTIFACTS/bench.json" ]] && break
		done
		python3 - "$ARTIFACTS/bench.json" "$NAME" "$Q" >> "$OUT" <<'PY'
import json, sys
G = ('total_ms', 'base_ms', 'lumen_ms', 'water_ms', 'clouds_fog_ms', 'niagara_ms', 'post_ms', 'other_ms')
try:
    b = json.load(open(sys.argv[1]))
    print(f"{sys.argv[2]},{sys.argv[3]},{b['avg_fps']},{b['p99_ms']}" + ''.join(',' + str(b.get('gpu', {}).get(k, '')) for k in G))
except Exception:
    print(f"{sys.argv[2]},{sys.argv[3]},error,,,,,,,,,")
PY
		[[ -n "${DOCS:-}" && -f "$ARTIFACTS/$SHOT.png" ]] && { mkdir -p "$DOCS"; cp "$ARTIFACTS/$SHOT.png" "$DOCS/$SHOT.png"; }
	done
done
column -s, -t < "$OUT"
