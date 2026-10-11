#!/usr/bin/env bash
# Compiles the editor target (game + physics + tests modules) with UnrealBuildTool.
# Usage: scripts/build.sh [Development|DebugGame]
source "$(dirname "$0")/env.sh"
CONFIG="${1:-Development}"

"$UBT_BUILD" SailingSimEditor Mac "$CONFIG" -Project="$PROJECT" -WaitMutex -NoHotReload 2>&1 | tee "$ARTIFACTS/build.log"
exit "${PIPESTATUS[0]}"
