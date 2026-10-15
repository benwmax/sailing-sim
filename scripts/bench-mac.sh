#!/usr/bin/env bash
# Runs the packaged Mac build for a fixed time, prints the measured frame rate and copies
# the screenshot it takes into Artifacts/.
# Usage: scripts/bench-mac.sh [seconds] [width] [height]   (default 20 s at 1920x1080, windowed)
# Environment: DEMO=1 lets the autopilot sail and tack (-SailingDemo); RECORD=<s> also saves frames and
# builds Artifacts/recording.gif (needs python3 with Pillow); RECORD_INTERVAL=<s> between frames (0.1);
# ARGS="..." passes extra game arguments (weather, hour, wind, TWA, quality); SHOT=<name> names the screenshot.
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
SHOT="${SHOT:-screenshot}"
rm -rf "$LOG" "$BENCH_DIR/bench.json" "$BENCH_DIR/$SHOT.png" "$BENCH_DIR/$SHOT.camera.json" "$BENCH_DIR/$SHOT.telemetry.csv" "$BENCH_DIR/rec"
EXTRA=(-SailingShot="$SHOT")
[[ -n "${ARGS:-}" ]] && read -r -a ARGV <<< "$ARGS" && EXTRA+=("${ARGV[@]}")
# The J/22 at the lake unless the run says otherwise (the game also ignores the player's saved boat and world here).
[[ " ${EXTRA[*]} " == *" -SailingBoat="* ]] || EXTRA+=(-SailingBoat=J22)
[[ " ${EXTRA[*]} " == *" -SailingWorld="* ]] || EXTRA+=(-SailingWorld=Lake)
[[ -n "${RECORD_INTERVAL:-}" ]] && EXTRA+=(-SailingRecordInterval="$RECORD_INTERVAL")
[[ "${DEMO:-0}" == "1" ]] && EXTRA+=(-SailingDemo)
[[ -n "${RECORD:-}" ]] && EXTRA+=(-SailingRecord="$RECORD")

open -n -W -a "$APP" --args -SailingBench="$SECONDS_TO_MEASURE" -windowed -ResX="$RES_X" -ResY="$RES_Y" "${EXTRA[@]}" &
OPEN_PID=$!
# Warm-up + measurement + generous startup allowance; kill the game if it hangs.
DEADLINE=$((SECONDS_TO_MEASURE + ${RECORD:-0} + 120))
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
cp "$BENCH_DIR/$SHOT.png" "$ARTIFACTS/$SHOT.png" 2>/dev/null || true
# Reference captures (-SailingCapture) also leave the camera settings and the telemetry.
for EXT in camera.json telemetry.csv; do
	[[ -f "$BENCH_DIR/$SHOT.$EXT" ]] && cp "$BENCH_DIR/$SHOT.$EXT" "$ARTIFACTS/$SHOT.$EXT"
done
echo "Bench: $(cat "$ARTIFACTS/bench.json")"
echo "Screenshot: $ARTIFACTS/$SHOT.png"
# Visual V1: GPU time per budget slice (bench.json "gpu", averaged over three ProfileGPU frames after the window).
python3 - "$ARTIFACTS/bench.json" <<'PY'
import json, sys
g = json.load(open(sys.argv[1])).get("gpu")
if g:
    print("GPU ms: total {total_ms}  base {base_ms}  lumen {lumen_ms}  water {water_ms}  clouds+fog {clouds_fog_ms}  niagara {niagara_ms}  post {post_ms}  other {other_ms}".format(**g))
PY
if [[ -d "$BENCH_DIR/rec" ]]; then
	python3 - "$BENCH_DIR/rec" "$ARTIFACTS/recording.gif" <<'PY'
import glob, sys
from PIL import Image
frames = [Image.open(p).convert("RGB") for p in sorted(glob.glob(sys.argv[1] + "/frame_*.png"))[::int(__import__("os").environ.get("GIF_STEP", "2"))]]
frames = [f.resize((640, int(640 * f.height / f.width))) for f in frames]
frames = [f.quantize(colors=96, method=Image.Quantize.MEDIANCUT) for f in frames]
frames[0].save(sys.argv[2], save_all=True, append_images=frames[1:], duration=200, loop=0, optimize=True)
print(f"Recording: {sys.argv[2]} ({len(frames)} frames)")
PY
fi
