#!/usr/bin/env bash
# Phase 7 on the packaged build at the default (Medium) tier: the Gulf passage (open sea with swell, a stormy sea,
# dusk, the Galveston entrance), the ship's log, a replay with the ghost, and photo mode. Records fps and p99 and
# copies each screenshot to docs/phase-7/<view>.png. Writes Artifacts/phase7-bench.csv.
# Then the full regression: NO_DOCS=1 bench-phase2..6 (fps only; their published screenshots are left alone).
# Usage: scripts/bench-phase7.sh [seconds] [--regression]
source "$(dirname "$0")/env.sh"
SECONDS_PER_RUN="${1:-12}"
OUT="$ARTIFACTS/phase7-bench.csv"
mkdir -p "$REPO_ROOT/docs/phase-7"
COMMON="-SailingQuality=Medium -SailingWind=12 -SailingTWA=60 -SailingHoldTWA=60 -SailingTraffic=1"
VIEWS=(
	"gulf-sea|-SailingWorld=Gulf -SailingLaunch=2 -SailingWeather=AfternoonBreeze -SailingHour=11 -SailingCamYaw=200 -SailingCamPitch=-5 -SailingCamDist=22"
	"gulf-swell|-SailingWorld=Gulf -SailingLaunch=2 -SailingWeather=Overcast -SailingSwell=1.8 -SailingWind=16 -SailingHour=14 -SailingCamYaw=100 -SailingCamPitch=-3 -SailingCamDist=18"
	"gulf-dusk|-SailingDate=2026-10-22 -SailingWorld=Gulf -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingHour=18.9 -SailingCamYaw=180 -SailingCamPitch=-5 -SailingCamDist=25"
	"gulf-entrance|-SailingWorld=Gulf -SailingLaunch=0 -SailingWeather=AfternoonBreeze -SailingHour=10 -SailingCamYaw=220 -SailingCamPitch=-12 -SailingCamDist=60"
	"gulf-chart|-SailingWorld=Gulf -SailingLaunch=0 -SailingWeather=AfternoonBreeze -SailingHour=10 -SailingChart=40"
	"logbook|-SailingWorld=Galveston -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingHour=10.45 -SailingPlotFix -SailingLogOpen"
	"ghost|-SailingWorld=Lake -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingHour=15 -SailingGhostAt=22 -SailingCamYaw=170 -SailingCamPitch=-20 -SailingCamDist=30"
)
echo "view,avg_fps,p99_ms,gpu_ms,base_ms,lumen_ms,water_ms,clouds_fog_ms,niagara_ms,post_ms" > "$OUT"
for V in "${VIEWS[@]}"; do
	NAME="${V%%|*}"; EXTRA="${V#*|}"
	RUN="$SECONDS_PER_RUN"
	[[ "$NAME" == ghost ]] && RUN=$((SECONDS_PER_RUN + 22)) # only a run over 20 s is kept for the ghost
	for TRY in 1 2; do
		rm -f "$ARTIFACTS/bench.json"
		DEMO=1 SHOT="$NAME" ARGS="$COMMON $EXTRA" "$(dirname "$0")/bench-mac.sh" "$RUN" > /dev/null || true
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
	[[ -z "${NO_DOCS:-}" && -f "$ARTIFACTS/$NAME.png" ]] && cp "$ARTIFACTS/$NAME.png" "$REPO_ROOT/docs/phase-7/$NAME.png" || true
done
cat "$OUT"
if [[ "${2:-}" == "--regression" ]]; then
	for P in 2 3 4 5 6; do
		echo "== phase $P"
		NO_DOCS=1 "$(dirname "$0")/bench-phase$P.sh" "$SECONDS_PER_RUN" | tail -12
	done
fi
