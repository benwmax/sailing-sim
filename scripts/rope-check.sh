#!/usr/bin/env bash
# docs/rope-lay/: builds the rope lay's checks standalone with clang (no Unreal) and runs them in about a second.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO_ROOT/Source/SailingPhysics"
OUT="$REPO_ROOT/Artifacts/rope-check"
mkdir -p "$REPO_ROOT/Artifacts"
clang++ -std=c++17 -O2 -ffp-contract=off -Wall -Wextra -Werror -Wshadow -I"$SRC/Public" "$SRC/Private/RopeLayChecks.cpp" \
  "$REPO_ROOT/Tools/RopeLayCheck/main.cpp" -o "$OUT"
"$OUT"
