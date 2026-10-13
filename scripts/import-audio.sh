#!/usr/bin/env bash
# Visual V7: imports Audio/Samples/*.wav as the sample layer (scripts/import_audio.py). Then repackage.
source "$(dirname "$0")/env.sh"
set -euo pipefail
"$EDITOR_CMD" "$PROJECT" -run=pythonscript -script="$REPO_ROOT/scripts/import_audio.py" -unattended -nosplash -nosound -NoP4 -stdout -FullStdOutLogOutput > "$ARTIFACTS/import-audio.log" 2>&1 || true
grep -E "LogPython: (Imported|Warning|Error)" "$ARTIFACTS/import-audio.log" || echo "No samples imported (Audio/Samples is empty)."
