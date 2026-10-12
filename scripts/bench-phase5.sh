#!/usr/bin/env bash
# Phase 5 coast: Galveston Bay on the packaged build at the default (Medium) tier. Sails each view with the
# autopilot and records fps and p99 frame time, copying each screenshot to docs/phase-5/<view>.png.
# Writes Artifacts/phase5-bench.csv. Leave the windows visible: macOS throttles hidden ones.
source "$(dirname "$0")/env.sh"
SECONDS_PER_RUN="${1:-12}"
OUT="$ARTIFACTS/phase5-bench.csv"
mkdir -p "$REPO_ROOT/docs/phase-5"
COMMON="-SailingWorld=1 -SailingQuality=Medium -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingTWA=60 -SailingHoldTWA=60"
VIEWS=(
	"coast-day|-SailingLaunch=1 -SailingHour=11 -SailingCamYaw=250 -SailingCamPitch=-10"
	"coast-bay|-SailingLaunch=2 -SailingHour=15 -SailingCamYaw=200 -SailingCamPitch=-8 -SailingCamDist=30"
	"coast-night|-SailingLaunch=1 -SailingHour=21 -SailingCamYaw=150 -SailingCamPitch=-6 -SailingCamDist=14"
	"coast-dusk|-SailingLaunch=4 -SailingHour=18.9 -SailingCamYaw=180 -SailingCamPitch=-5"
	"chart|-SailingLaunch=1 -SailingHour=11 -SailingChart=4 -SailingPlotFix"
	"chart-bay|-SailingLaunch=2 -SailingHour=11 -SailingChart=25"
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
	[[ -z "${NO_DOCS:-}" && -f "$ARTIFACTS/$SHOT.png" ]] && cp "$ARTIFACTS/$SHOT.png" "$REPO_ROOT/docs/phase-5/$SHOT.png" || true
done
cat "$OUT"
