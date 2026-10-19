#!/usr/bin/env bash
# Visual phases: a representative set of views (lake beam reach, lake beat with tacking, storm, marina, Galveston day
# and night, Gulf sea, the helm eye; since V6 also Bean's slip at Rush Creek, the I-30 bridge and the marina at night; since G3 the crew close up) on each quality tier of the packaged build, with GPU time per budget slice.
# Writes Artifacts/visual-bench-<label>.csv; with DOCS=<dir> also copies each screenshot there as <view>-<tier>.png.
# Usage: scripts/bench-visual.sh [seconds] [label] [tiers...]   e.g. scripts/bench-visual.sh 12 before Medium High
# Bench-fast (docs/bench-fast): ONLY=storm,helm-eye runs just those views (scripts/gate.sh picks them by scope);
# BENCH_EXTRA="..." adds arguments to every view. One launch per view, as before (measured the most reliable and,
# at 3 s of launch per view, barely slower); FAST=1 runs CHUNK views per launch in-process instead (bench-mac.sh LIST=).
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
	"slip|-SailingWorld=Lake -SailingDrill=LeavetheDock -SailingWeather=AfternoonBreeze -SailingHour=10 -SailingWind=6 -SailingCamYaw=160 -SailingCamPitch=-14 -SailingCamDist=26"
	"bridge|-SailingWorld=Lake -SailingStartAt=7060,880,183 -SailingKeepStart -SailingWeather=AfternoonBreeze -SailingHour=11 -SailingWind=8 -SailingCamYaw=180 -SailingCamPitch=-4 -SailingCamDist=20"
	"crew|-SailingWorld=Lake -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingHour=15 -SailingWind=10 -SailingTWA=60 -SailingHoldTWA=60 -SailingCamYaw=250 -SailingCamPitch=-6 -SailingCamDist=2.6 -SailingCamTarget=-1.6,0.8,0.9"
	"marina-night|-SailingWorld=Lake -SailingDrill=LeavetheDock -SailingWeather=AfternoonBreeze -SailingHour=21.5 -SailingWind=4 -SailingCamYaw=200 -SailingCamPitch=-10 -SailingCamDist=40"
	# Wide World Rendering PR 1 (docs/world-far): Bolivar Roads looking northwest, the far coast ring past 8 km.
	"far-coast|-SailingWorld=1 -SailingStartAt=-21700,26000,315 -SailingKeepStart -SailingWeather=AfternoonBreeze -SailingWind=10 -SailingTWA=60 -SailingHoldTWA=60 -SailingHour=11 -SailingCamYaw=0 -SailingCamPitch=-3 -SailingCamDist=14"
	"far-coast-night|-SailingWorld=1 -SailingStartAt=-21700,26000,315 -SailingKeepStart -SailingWeather=AfternoonBreeze -SailingWind=10 -SailingTWA=60 -SailingHoldTWA=60 -SailingHour=21 -SailingCamYaw=0 -SailingCamPitch=-3 -SailingCamDist=14"
	"marseille-port|-SailingWorld=Marseille -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingTWA=60 -SailingHoldTWA=60 -SailingHour=14 -SailingCamYaw=120 -SailingCamPitch=-8 -SailingCamDist=30"
)
if [[ -n "${ONLY:-}" ]]; then
	KEPT=()
	for V in "${VIEWS[@]}"; do [[ ",$ONLY," == *",${V%%|*},"* ]] && KEPT+=("$V"); done
	VIEWS=("${KEPT[@]}")
fi
echo "view,quality,avg_fps,p99_ms,gpu_ms,base_ms,lumen_ms,water_ms,clouds_fog_ms,niagara_ms,post_ms,other_ms,cloth_cpu_ms,water_cpu_ms,game_ms,game_p99_ms,render_ms,rhi_ms,gpu_frame_ms" > "$OUT"
# Perf 1: the game thread's named slices (PerfScopes.h), ms per frame, one row per run.
GT_OUT="${OUT%.csv}-gt.csv"; rm -f "$GT_OUT"
lower() { echo "$1" | tr '[:upper:]' '[:lower:]'; }
# One launch for one view (the old way, FAST=0; also the retry for a view a list run lost).
run_single() {
	local NAME="$1" EXTRA="$2" Q="$3" SHOT
	SHOT="$NAME-$(lower "$Q")"
	for TRY in 1 2; do
		rm -f "$ARTIFACTS/bench.json"
		DEMO=1 SHOT="$SHOT" ARGS="$EXTRA -SailingQuality=$Q" "$(dirname "$0")/bench-mac.sh" "$SECONDS_PER_RUN" > /dev/null || true
		[[ -f "$ARTIFACTS/bench.json" ]] && { cp "$ARTIFACTS/bench.json" "$ARTIFACTS/$SHOT.bench.json"; break; }
	done
	# A view lost twice is an error row in the CSV, not the end of the sweep (env.sh sets -e).
	return 0
}
for V in "${VIEWS[@]}"; do for Q in "${TIERS[@]}"; do rm -f "$ARTIFACTS/${V%%|*}-$(lower "$Q").bench.json"{,.slowed}; done; done
if [[ "${FAST:-0}" == "1" ]]; then
	# Bench-fast: one launch runs CHUNK views in turn (bench-mac.sh LIST=). Within a launch the render and RHI threads
	# can slow down from one view to the next (docs/bench-fast: 1.8 ms of RHI time grew to 6-20 ms on some runs, not
	# others, with the GPU's own time unchanged), so a view counts only if its RHI time is within 1.5x (+0.5 ms) of the
	# launch's first view, which starts as fresh as a single run; any other is run again on its own.
	CHUNK="${CHUNK:-4}"
	for Q in "${TIERS[@]}"; do
		for ((S0 = 0; S0 < ${#VIEWS[@]}; S0 += CHUNK)); do
			LISTFILE="$ARTIFACTS/bench-list-$(lower "$Q").txt"; : > "$LISTFILE"
			NAMES=()
			for V in "${VIEWS[@]:S0:CHUNK}"; do
				echo "${V%%|*}-$(lower "$Q")|${V#*|} ${BENCH_EXTRA:-}" >> "$LISTFILE"
				NAMES+=("$ARTIFACTS/${V%%|*}-$(lower "$Q").bench.json")
			done
			DEMO=1 LIST="$LISTFILE" ARGS="-SailingQuality=$Q" "$(dirname "$0")/bench-mac.sh" "$SECONDS_PER_RUN" > /dev/null || true
			python3 - "${NAMES[@]}" <<'PY'
import json, os, sys
first = None
for path in sys.argv[1:]:
    try:
        b = json.load(open(path))
    except Exception:
        continue
    rhi = float(b.get('rhi_ms', 0) or 0)
    if first is None:
        first = rhi
    bad = first is not None and rhi > 1.5 * first + 0.5
    if bad:
        os.rename(path, path + '.slowed')
        print(f"{os.path.basename(path)}: RHI {rhi:.1f} ms against the launch's first {first:.1f} ms; run again on its own", file=sys.stderr)
PY
			for V in "${VIEWS[@]:S0:CHUNK}"; do
				[[ -f "$ARTIFACTS/${V%%|*}-$(lower "$Q").bench.json" ]] && continue
				echo "${V%%|*} $Q: lost or slowed in the list run; once more on its own" >&2
				run_single "${V%%|*}" "${V#*|} ${BENCH_EXTRA:-}" "$Q"
			done
		done
	done
else
	for V in "${VIEWS[@]}"; do for Q in "${TIERS[@]}"; do run_single "${V%%|*}" "${V#*|} ${BENCH_EXTRA:-}" "$Q"; done; done
fi
for V in "${VIEWS[@]}"; do
	NAME="${V%%|*}"
	for Q in "${TIERS[@]}"; do
		SHOT="$NAME-$(lower "$Q")"
		python3 - "$ARTIFACTS/$SHOT.bench.json" "$NAME" "$Q" "$GT_OUT" >> "$OUT" <<'PY'
import json, sys
import os
G = ('total_ms', 'base_ms', 'lumen_ms', 'water_ms', 'clouds_fog_ms', 'niagara_ms', 'post_ms', 'other_ms')
T = ('game_ms', 'game_p99_ms', 'render_ms', 'rhi_ms', 'gpu_frame_ms')
try:
    b = json.load(open(sys.argv[1]))
    print(f"{sys.argv[2]},{sys.argv[3]},{b['avg_fps']},{b['p99_ms']}" + ''.join(',' + str(b.get('gpu', {}).get(k, '')) for k in G) + f",{b.get('cloth_cpu_ms', '')},{b.get('water_cpu_ms', '')}" + ''.join(',' + str(b.get(k, '')) for k in T))
    gt = b.get('gt', {})
    if gt:
        path = sys.argv[4]
        new = not os.path.exists(path)
        with open(path, 'a') as f:
            if new: f.write('view,quality,game_ms,' + ','.join(gt) + '\n')
            f.write(f"{sys.argv[2]},{sys.argv[3]},{b.get('game_ms', '')}," + ','.join(str(v) for v in gt.values()) + '\n')
except Exception:
    print(f"{sys.argv[2]},{sys.argv[3]},error,,,,,,,,,,,,,,,,")
PY
		[[ -n "${DOCS:-}" && -f "$ARTIFACTS/$SHOT.png" ]] && { mkdir -p "$DOCS"; cp "$ARTIFACTS/$SHOT.png" "$DOCS/$SHOT.png"; }
	done
done
column -s, -t < "$OUT"
