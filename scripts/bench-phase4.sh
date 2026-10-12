#!/usr/bin/env bash
# Phase 4 fleet: every boat on the packaged build at the default (Medium) tier, close reaching in 12 kn off Rush
# Creek with the autopilot, camera abeam. Records fps, p99 frame time and how long the boat took to build, and
# copies each screenshot to docs/phase-4/<boat>.png. Writes Artifacts/phase4-bench.csv.
source "$(dirname "$0")/env.sh"
SECONDS_PER_RUN="${1:-12}"
OUT="$ARTIFACTS/phase4-bench.csv"
APP="$REPO_ROOT/Packaged/Mac/SailingSim.app"
BUNDLE_ID="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$APP/Contents/Info.plist")"
LOG="$HOME/Library/Containers/$BUNDLE_ID/Data/Library/Logs/SailingSim/SailingSim.log"
mkdir -p "$REPO_ROOT/docs/phase-4"
echo "boat,avg_fps,p99_ms,build_ms" > "$OUT"
for BOAT in J22 Sunfish ILCA Catalina22 Catalina30 Hobie Corsair Lagoon; do
	SHOT="fleet-$(echo "$BOAT" | tr '[:upper:]' '[:lower:]')"
	for TRY in 1 2; do # a launch occasionally fails to report; try once more
		rm -f "$ARTIFACTS/bench.json"
		DEMO=1 SHOT="$SHOT" ARGS="-SailingBoat=$BOAT -SailingQuality=Medium -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingHour=11 -SailingWind=12 -SailingTWA=60 -SailingHoldTWA=60 -SailingCamYaw=250 -SailingCamPitch=-10" \
			"$(dirname "$0")/bench-mac.sh" "$SECONDS_PER_RUN" > /dev/null || true
		[[ -f "$ARTIFACTS/bench.json" ]] && break
	done
	BUILD_MS="$(grep -o 'Boat ready: .* in [0-9.]* ms' "$LOG" 2>/dev/null | tail -1 | sed 's/.* in \([0-9.]*\) ms/\1/')"
	python3 - "$ARTIFACTS/bench.json" "$BOAT" "${BUILD_MS:-}" >> "$OUT" <<'PY'
import json, sys
try:
    b = json.load(open(sys.argv[1])); print(f"{sys.argv[2]},{b['avg_fps']},{b['p99_ms']},{sys.argv[3]}")
except Exception:
    print(f"{sys.argv[2]},error,,{sys.argv[3]}")
PY
	[[ -f "$ARTIFACTS/$SHOT.png" ]] && cp "$ARTIFACTS/$SHOT.png" "$REPO_ROOT/docs/phase-4/$SHOT.png"
done
cat "$OUT"
