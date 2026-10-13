#!/usr/bin/env bash
# Phase 2 frame budget and reference screenshots: three conditions x three quality tiers on the packaged build.
#   beam8  : 8 kn beam reach at noon (afternoon breeze preset scaled to 8 kn)
#   beat15 : 15 kn beating in the afternoon, tacking
#   storm  : thunderstorm, just after the gust front, heavy rain coming
# Writes Artifacts/phase2-bench.csv and copies the High-tier screenshots to docs/phase-2/.
source "$(dirname "$0")/env.sh"
SECONDS_PER_RUN="${1:-15}"
OUT="$ARTIFACTS/phase2-bench.csv"
mkdir -p "$REPO_ROOT/docs/phase-2"
echo "condition,quality,avg_fps,p99_ms,resolution,gpu_ms,base_ms,lumen_ms,water_ms,clouds_fog_ms,niagara_ms,post_ms" > "$OUT"

declare -a NAMES=(beam8 beat15 storm)
declare -a CONDITIONS=(
	"-SailingWeather=AfternoonBreeze -SailingHour=12 -SailingWind=8 -SailingTWA=90 -SailingHoldTWA=90 -SailingCamYaw=200 -SailingCamPitch=-10"
	"-SailingWeather=AfternoonBreeze -SailingHour=16 -SailingWind=15 -SailingTWA=45"
	"-SailingWeather=Thunderstorm -SailingHour=16 -SailingWeatherTime=200 -SailingTWA=100 -SailingHoldTWA=100 -SailingCamYaw=200 -SailingCamPitch=-8"
)
for I in "${!NAMES[@]}"; do
	for Q in Low Medium High; do
		NAME="${NAMES[$I]}-$(echo "$Q" | tr "[:upper:]" "[:lower:]")"
		rm -f "$ARTIFACTS/bench.json"
		DEMO=1 SHOT="$NAME" ARGS="${CONDITIONS[$I]} -SailingQuality=$Q" "$(dirname "$0")/bench-mac.sh" "$SECONDS_PER_RUN" > /dev/null || true
		python3 - "$ARTIFACTS/bench.json" "${NAMES[$I]}" "$Q" >> "$OUT" <<'PY'
import json, sys
G = ('total_ms', 'base_ms', 'lumen_ms', 'water_ms', 'clouds_fog_ms', 'niagara_ms', 'post_ms')
gpu = lambda b: ''.join(',' + str(b.get('gpu', {}).get(k, '')) for k in G)
try:
    b = json.load(open(sys.argv[1]))
    print(f"{sys.argv[2]},{sys.argv[3]},{b['avg_fps']},{b['p99_ms']},{b['resolution']}" + gpu(b))
except Exception as e:
    print(f"{sys.argv[2]},{sys.argv[3]},error,,,,,,,,,")
PY
		[[ -z "${NO_DOCS:-}" && "$Q" == High && -f "$ARTIFACTS/$NAME.png" ]] && cp "$ARTIFACTS/$NAME.png" "$REPO_ROOT/docs/phase-2/${NAMES[$I]}.png" || true
	done
done
cat "$OUT"
