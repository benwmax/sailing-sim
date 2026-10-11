#!/usr/bin/env bash
# Builds, cooks, stages and archives a standalone Mac app with RunUAT BuildCookRun.
# Usage: scripts/package-mac.sh [Development|Shipping]
#   Output: Packaged/Mac/SailingSim.app
source "$(dirname "$0")/env.sh"
CONFIG="${1:-Development}"
OUT="$REPO_ROOT/Packaged"

"$RUNUAT" BuildCookRun \
	-project="$PROJECT" -noP4 -utf8output -unattended \
	-platform=Mac -clientconfig="$CONFIG" \
	-build -cook -stage -pak -iostore -package -archive -archivedirectory="$OUT" \
	2>&1 | tee "$ARTIFACTS/package.log"
STATUS=${PIPESTATUS[0]}
if [[ $STATUS -eq 0 ]]; then
	echo "Packaged app(s):"
	find "$OUT" -maxdepth 3 -name "*.app" -print
fi
exit $STATUS
