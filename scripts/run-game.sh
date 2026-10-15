#!/usr/bin/env bash
# Runs the game uncooked from the editor binary (no packaging), for quick visual checks.
# Usage: scripts/run-game.sh <seconds> [game args...]   e.g. scripts/run-game.sh 10 -SailingWeather=Thunderstorm
# Writes Saved/Bench/<shot>.png and bench.json like the packaged benchmark; frame rates here are not representative.
source "$(dirname "$0")/env.sh"
SECONDS_TO_RUN="${1:-10}"; shift || true
APP="$UE_ROOT/Engine/Binaries/Mac/UnrealEditor.app"
rm -f "$REPO_ROOT/Saved/Bench/bench.json"
# The J/22 at the lake unless the args say otherwise.
DEFAULTS=()
[[ " $* " == *" -SailingBoat="* ]] || DEFAULTS+=(-SailingBoat=J22)
[[ " $* " == *" -SailingWorld="* ]] || DEFAULTS+=(-SailingWorld=Lake)
open -n -W -a "$APP" --args "$PROJECT" -game -windowed -ResX="${RESX:-1440}" -ResY="${RESY:-1080}" -SailingBench="$SECONDS_TO_RUN" -SailingDemo ${DEFAULTS[@]+"${DEFAULTS[@]}"} "$@" &
PID=$!
for ((i = 0; i < SECONDS_TO_RUN + 240; i++)); do kill -0 "$PID" 2>/dev/null || break; sleep 1; done
kill -0 "$PID" 2>/dev/null && { echo "timed out (or crashed: see ~/Library/Logs/SailingSim)" >&2; pkill -9 -f "$PROJECT -game" || true; }
cat "$REPO_ROOT/Saved/Bench/bench.json" 2>/dev/null; echo
