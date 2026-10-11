#!/usr/bin/env bash
# Regenerates Content/Maps/Lake.umap from scripts/make_lake_map.py (run after scripts/build.sh).
source "$(dirname "$0")/env.sh"
"$EDITOR_CMD" "$PROJECT" -run=pythonscript -script="$REPO_ROOT/scripts/make_lake_map.py" \
	-unattended -nosplash -nosound -NoP4 -stdout -FullStdOutLogOutput 2>&1 | tee "$ARTIFACTS/make-map.log" \
	| grep -E "Lake map saved|Error|Traceback" || true
test -f "$REPO_ROOT/Content/Maps/Lake.umap"
