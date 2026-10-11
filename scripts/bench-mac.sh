#!/usr/bin/env bash
# Runs the packaged Mac build for a fixed time, prints the measured frame rate and copies
# the screenshot it takes into Artifacts/.
# Usage: scripts/bench-mac.sh [seconds] [width] [height]   (default 20 s at 1920x1080, windowed)
# Needs an unlocked, logged-in desktop: it opens a window. Launched through LaunchServices
# (`open`), because a game started straight from a non-GUI shell stalls at window creation.
source "$(dirname "$0")/env.sh"
SECONDS_TO_MEASURE="${1:-20}"
RES_X="${2:-1920}"
RES_Y="${3:-1080}"
APP="$REPO_ROOT/Packaged/Mac/SailingSim.app"
if [[ ! -d "$APP" ]]; then
	echo "No packaged app at $APP; run scripts/package-mac.sh first" >&2
	exit 1
fi

BUNDLE_ID="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$APP/Contents/Info.plist")"
CONTAINER="$HOME/Library/Containers/$BUNDLE_ID/Data/Library"
LOG="$CONTAINER/Logs/SailingSim/SailingSim.log"
BENCH_DIR="$CONTAINER/Application Support/Epic/SailingSim/Saved/Bench"
rm -f "$LOG" "$BENCH_DIR/bench.json" "$BENCH_DIR/screenshot.png"

open -n -W -a "$APP" --args -SailingBench="$SECONDS_TO_MEASURE" -windowed -ResX="$RES_X" -ResY="$RES_Y" &
OPEN_PID=$!
# Warm-up + measurement + generous startup allowance; kill the game if it hangs.
DEADLINE=$((SECONDS_TO_MEASURE + 90))
for ((i = 0; i < DEADLINE; i++)); do
	kill -0 "$OPEN_PID" 2>/dev/null || break
	sleep 1
done
if kill -0 "$OPEN_PID" 2>/dev/null; then
	echo "Game did not finish in ${DEADLINE}s; killing it (is the screen locked?)" >&2
	pkill -f "$APP/Contents/MacOS/" || true
fi
wait "$OPEN_PID" 2>/dev/null || true

[[ -f "$LOG" ]] && cp "$LOG" "$ARTIFACTS/bench.log"
if [[ ! -f "$BENCH_DIR/bench.json" ]]; then
	echo "No bench result; see $ARTIFACTS/bench.log" >&2
	exit 1
fi
cp "$BENCH_DIR/bench.json" "$ARTIFACTS/bench.json"
cp "$BENCH_DIR/screenshot.png" "$ARTIFACTS/packaged-screenshot.png" 2>/dev/null || true
echo "Bench: $(cat "$ARTIFACTS/bench.json")"
echo "Screenshot: $ARTIFACTS/packaged-screenshot.png"
