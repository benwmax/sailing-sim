#!/usr/bin/env bash
# Builds, cooks, stages and archives a standalone Mac app with RunUAT BuildCookRun.
# Usage: [FULL=1] scripts/package-mac.sh [Development|Shipping]
#   Output: Packaged/Mac/SailingSim.app
# The cook is incremental (docs/bench-fast): the cooked output in Saved/Cooked/Mac (a Zen store) is kept between runs and
# only packages whose dependencies changed (the package, its classes' schemas, referenced config and packages) are
# cooked again. FULL=1 deletes it and recooks everything, as every package did before.
source "$(dirname "$0")/env.sh"
CONFIG="${1:-Development}"
OUT="$REPO_ROOT/Packaged"
COOK=(-cookincremental)
# Without the flag the cook is full: Editor.ini CookIncrementalDefaultIncremental=false.
if [[ "${FULL:-0}" == 1 ]]; then COOK=(); fi

START=$(date +%s)
"$RUNUAT" BuildCookRun \
	-project="$PROJECT" -noP4 -utf8output -unattended \
	-platform=Mac -clientconfig="$CONFIG" \
	-build -cook ${COOK[@]+"${COOK[@]}"} -stage -pak -iostore -package -archive -archivedirectory="$OUT" \
	2>&1 | tee "$ARTIFACTS/package.log"
STATUS=${PIPESTATUS[0]}
if [[ $STATUS -eq 0 ]]; then
	echo "Packaged app(s) in $(( $(date +%s) - START )) s ($(grep -m1 -oE '(FULL|INCREMENTAL) COOK' "$ARTIFACTS/package.log" || echo 'cook mode not logged')):"
	find "$OUT" -maxdepth 3 -name "*.app" -print
fi
exit $STATUS
