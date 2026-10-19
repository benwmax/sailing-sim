#!/usr/bin/env bash
# World streaming (docs/world-streaming): the soak. The packaged game on the Texas coast with the world sliding under the
# boat (-SailingRun) back and forth over 40 km from Kemah down the bay, through Bolivar Roads and out past the jetties, for
# SECONDS (1800 by default): tiles, chunks, far tiles and trees come and go, the render origin moves every 20 km.
# Frame times by -SailingBenchTrace, the game's resident memory every 60 s (ps), then docs/budget/soak_stats.py.
# Usage: QUALITY=High scripts/soak-streaming.sh [seconds] [m/s]   (needs the unlocked desktop, as bench-mac.sh)
source "$(dirname "$0")/env.sh"
SECS="${1:-1800}"
SPEED="${2:-25}"
QUALITY="${QUALITY:-High}"
Q="$(echo "$QUALITY" | tr '[:upper:]' '[:lower:]')"
SHOT="stream-soak-$Q"
MEM="$ARTIFACTS/$SHOT.mem.csv"
APP="${APP:-$REPO_ROOT/Packaged/Mac/SailingSim.app}"
BUNDLE_ID="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$APP/Contents/Info.plist")"
BENCH_DIR="$HOME/Library/Containers/$BUNDLE_ID/Data/Library/Application Support/Epic/SailingSim/Saved/Bench"
# Kemah's channel, bearing down the bay to Bolivar Roads and on (131.8 deg), turning back every 40 km.
ARGS="-SailingQuality=$QUALITY -SailingBenchTrace -SailingWorld=TexasCoast -SailingStartAt=-310,1100,132 -SailingKeepStart \
-SailingRun=$SPEED,131.8,40000 -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingTWA=90 -SailingHoldTWA=90 -SailingHour=11 \
-SailingCamYaw=200 -SailingCamPitch=-8 -SailingCamDist=14" SHOT="$SHOT" "$(dirname "$0")/bench-mac.sh" "$SECS" &
BENCH_PID=$!
echo "seconds,rss_mb" > "$MEM"
T0=$(date +%s)
while kill -0 "$BENCH_PID" 2>/dev/null; do
	PID="$(pgrep -f "$APP/Contents/MacOS/" | head -1 || true)"
	if [[ -n "$PID" ]]; then
		RSS="$(ps -o rss= -p "$PID" 2>/dev/null | tr -d ' ' || true)"
		[[ -n "$RSS" ]] && echo "$(( $(date +%s) - T0 )),$(( RSS / 1024 ))" >> "$MEM"
	fi
	sleep 60
done
wait "$BENCH_PID" || true
cp "$BENCH_DIR/$SHOT.frames.csv" "$ARTIFACTS/$SHOT.frames.csv" 2>/dev/null || true
cp "$ARTIFACTS/bench.json" "$ARTIFACTS/$SHOT.bench.json" 2>/dev/null || true
python3 "$REPO_ROOT/docs/budget/soak_stats.py" "$ARTIFACTS/$SHOT.frames.csv" "$MEM"
