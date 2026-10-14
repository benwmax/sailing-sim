#!/usr/bin/env bash
# Graphics G7: rebakes the shore kit's Nanite tiles for the given worlds (default GalvestonBay): run after
# Tools/coast/build_piers.py or a change to BuildShoreGeometry. Run scripts/build.sh first.
source "$(dirname "$0")/env.sh"
set -euo pipefail
WORLDS="${*:-GalvestonBay}"
"$EDITOR_CMD" "$PROJECT" -run=pythonscript -script="$REPO_ROOT/scripts/bake_shore.py $WORLDS" -unattended -nosplash -nosound -NoP4 -stdout -FullStdOutLogOutput > "$ARTIFACTS/bake-shore.log" 2>&1 \
	|| { tail -30 "$ARTIFACTS/bake-shore.log"; exit 1; }
grep -E "Baked the|Removed stale|Error" "$ARTIFACTS/bake-shore.log" | grep -v "LogSailing: Display: Baked" || true
