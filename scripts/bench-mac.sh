#!/usr/bin/env bash
# Runs the packaged Mac build for a fixed time, then prints the measured frame rate and
# copies the screenshot it takes into Artifacts/.
# Usage: scripts/bench-mac.sh [seconds]  (default 20; needs a logged-in desktop session)
source "$(dirname "$0")/env.sh"
SECONDS_TO_MEASURE="${1:-20}"
APP="$(find "$REPO_ROOT/Build/Mac" -maxdepth 3 -name "SailingSim*.app" | head -n 1)"
if [[ -z "$APP" ]]; then
	echo "No packaged app in Build/Mac; run scripts/package-mac.sh first" >&2
	exit 1
fi
BIN="$(find "$APP/Contents/MacOS" -type f -perm +111 | head -n 1)"

"$BIN" -SailingBench="$SECONDS_TO_MEASURE" -log -stdout -FullStdOutLogOutput > "$ARTIFACTS/bench.log" 2>&1 || true
grep "SailingBench result" "$ARTIFACTS/bench.log" || { echo "No bench result; see Artifacts/bench.log" >&2; exit 1; }

SAVED_DIR="$(grep -m1 -o 'SailingBench result' "$ARTIFACTS/bench.log" >/dev/null; find "$HOME/Library/Application Support/Epic/SailingSim" "$APP" -path '*Bench*' -name 'screenshot.png' 2>/dev/null | head -n 1)"
if [[ -n "$SAVED_DIR" ]]; then
	cp "$SAVED_DIR" "$ARTIFACTS/packaged-screenshot.png"
	cp "$(dirname "$SAVED_DIR")/bench.json" "$ARTIFACTS/bench.json" 2>/dev/null || true
	echo "Screenshot: $ARTIFACTS/packaged-screenshot.png"
fi
