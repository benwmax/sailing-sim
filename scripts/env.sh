#!/usr/bin/env bash
# Shared paths for the build scripts. Override UE_ROOT if Unreal lives elsewhere.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT="$REPO_ROOT/SailingSim.uproject"
UE_ROOT="${UE_ROOT:-/Users/Shared/Epic Games/UE_5.8}"
UBT_BUILD="$UE_ROOT/Engine/Build/BatchFiles/Mac/Build.sh"
RUNUAT="$UE_ROOT/Engine/Build/BatchFiles/RunUAT.sh"
EDITOR_CMD="$UE_ROOT/Engine/Binaries/Mac/UnrealEditor-Cmd"
ARTIFACTS="$REPO_ROOT/Artifacts"

if [[ ! -x "$EDITOR_CMD" ]]; then
	echo "Unreal Engine not found at $UE_ROOT (set UE_ROOT)" >&2
	exit 1
fi
mkdir -p "$ARTIFACTS"
