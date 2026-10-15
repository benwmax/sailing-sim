#!/usr/bin/env bash
# Builds, cooks, stages and archives a standalone Mac app with RunUAT BuildCookRun.
# Usage: [FULL=1] scripts/package-mac.sh [Development|Shipping]
#   Output: Packaged/Mac/SailingSim.app
# The cook is incremental (docs/bench-fast): the cooked output in Saved/Cooked/Mac (a Zen store) is kept between runs and
# only packages whose dependencies changed (the package, its classes' schemas, referenced config and packages) are
# cooked again. FULL=1 deletes it and recooks everything, as every package did before.
# The game target is built only when the code changed since the last package (Source, Config, Plugins, the .uproject:
# Artifacts/package-code.hash): UnrealBuildTool rewrites its shared-PCH response files on every run with this installed
# engine and recompiles 32 files (about 30 s) even when nothing changed. FULL=1 builds too.
source "$(dirname "$0")/env.sh"
CONFIG="${1:-Development}"
OUT="$REPO_ROOT/Packaged"
COOK=(-cookincremental)
# Without the flag the cook is full: Editor.ini CookIncrementalDefaultIncremental=false.
if [[ "${FULL:-0}" == 1 ]]; then COOK=(); fi
CODE_HASH="$(cd "$REPO_ROOT" && inputs_hash Source SailingSim.uproject Config Plugins)-$CONFIG"
CODE_STAMP="$ARTIFACTS/package-code.hash"
BUILD=(-build)
if [[ "${FULL:-0}" != 1 && "$(cat "$CODE_STAMP" 2>/dev/null)" == "$CODE_HASH" && -d "$REPO_ROOT/Binaries/Mac/SailingSim.app" ]]; then
	BUILD=()
	echo "Code unchanged since the last package: skipping the build"
fi

START=$(date +%s)
# The stage step reads the cooked oplog from the Zen server. When none is running, the cooker starts one owned by
# itself (--owner-pid), which exits with the cook, and the stage then waits for it forever ("Reading oplog from Zen...").
# So start a server that outlives the cook first (the same install, port and data the engine uses).
ZEN_DIR="$HOME/Library/Application Support/Epic/UnrealEngine/Common/Zen"
if ! curl -s -m 3 -o /dev/null http://127.0.0.1:8558/health/ && [[ -x "$ZEN_DIR/Install/zenserver" ]]; then
	echo "Starting the Zen server for the cook and stage"
	(cd "$ZEN_DIR/Install" && ./zenserver --port 8558 --data-dir "$ZEN_DIR/Data" --http asio --quiet --detach > /dev/null 2>&1 &)
	for _ in $(seq 1 30); do curl -s -m 1 -o /dev/null http://127.0.0.1:8558/health/ && break; sleep 1; done
fi
"$RUNUAT" BuildCookRun \
	-project="$PROJECT" -noP4 -utf8output -unattended \
	-platform=Mac -clientconfig="$CONFIG" \
	${BUILD[@]+"${BUILD[@]}"} -cook ${COOK[@]+"${COOK[@]}"} -stage -pak -iostore -package -archive -archivedirectory="$OUT" \
	2>&1 | tee "$ARTIFACTS/package.log"
STATUS=${PIPESTATUS[0]}
if [[ $STATUS -eq 0 ]]; then
	echo "$CODE_HASH" > "$CODE_STAMP"
	echo "Packaged app(s) in $(( $(date +%s) - START )) s ($(grep -m1 -oE '(FULL|INCREMENTAL) COOK:' "$ARTIFACTS/package.log" || echo 'cook mode not logged')):"
	find "$OUT" -maxdepth 3 -name "*.app" -print
fi
exit $STATUS
