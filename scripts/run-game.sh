#!/usr/bin/env bash
# Runs the game uncooked from the editor binary (no packaging), for quick visual checks.
# Usage: scripts/run-game.sh <seconds> [game args...]   e.g. scripts/run-game.sh 10 -SailingWeather=Thunderstorm
# Writes Saved/Bench/<shot>.png and bench.json like the packaged benchmark; frame rates here are not representative.
source "$(dirname "$0")/env.sh"
SECONDS_TO_RUN="${1:-10}"; shift || true
APP="$UE_ROOT/Engine/Binaries/Mac/UnrealEditor.app"
rm -f "$REPO_ROOT/Saved/Bench/bench.json"
open -n -W -a "$APP" --args "$PROJECT" -game -windowed -ResX=1440 -ResY=1080 -SailingBench="$SECONDS_TO_RUN" -SailingDemo "$@" &
PID=$!
for ((i = 0; i < SECONDS_TO_RUN + 240; i++)); do kill -0 "$PID" 2>/dev/null || break; sleep 1; done
kill -0 "$PID" 2>/dev/null && { echo "timed out" >&2; pkill -f "UnrealEditor.app/Contents/MacOS/UnrealEditor $PROJECT" || true; }
cat "$REPO_ROOT/Saved/Bench/bench.json" 2>/dev/null; echo
