#!/usr/bin/env bash
# Shore Track C (docs/envloop/shore-edges): builds the kit shore edge pieces in Blender headless
# (Tools/envloop/shore-edges/export_edges.py -> Artifacts/models/edges/SM_Edge_*.fbx) and imports them with their material into
# /Game/World/Edges (scripts/import_shore_edges.py: M_ShoreEdge from edge_layer.py's HLSL, MPC_World's lake marks from the pack).
# Run scripts/make-content.sh first (MPC_World). Usage: scripts/make-shore-edges.sh [--no-import | --material-only] [--pack north-texas-lake]
# --material-only skips Blender and the FBX import: M_ShoreEdge and the marks are rebuilt and put on the pieces already imported.
source "$(dirname "$0")/env.sh"
set -euo pipefail
OUT="$ARTIFACTS/models/edges"
mkdir -p "$OUT"
PACK="north-texas-lake"
NOIMPORT=0
MATONLY=0
while [[ $# -gt 0 ]]; do
	case "$1" in
		--no-import) NOIMPORT=1 ;;
		--material-only) MATONLY=1 ;;
		--pack) PACK="$2"; shift ;;
	esac
	shift
done
BLENDER="${BLENDER:-$(command -v blender || echo /Applications/Blender.app/Contents/MacOS/Blender)}"
[[ "$MATONLY" == 1 ]] || "$BLENDER" -b --factory-startup -noaudio -P "$REPO_ROOT/Tools/envloop/shore-edges/export_edges.py" -- --out "$OUT" --pack "$PACK" > "$ARTIFACTS/blender-edges.log" 2>&1 \
	|| { tail -30 "$ARTIFACTS/blender-edges.log"; exit 1; }
grep -E "^Edges: " "$ARTIFACTS/blender-edges.log" || true
[[ "$NOIMPORT" == 1 ]] && exit 0
EDGE_PACK="$PACK" EDGE_MATERIAL_ONLY="$MATONLY" "$EDITOR_CMD" "$PROJECT" -run=pythonscript -script="$REPO_ROOT/scripts/import_shore_edges.py" -unattended -nosplash -nosound -NoP4 -stdout -FullStdOutLogOutput > "$ARTIFACTS/import-edges.log" 2>&1 \
	|| { tail -30 "$ARTIFACTS/import-edges.log"; exit 1; }
grep -E "LogPython: (Imported|Gave|Built|Error|Warning)" "$ARTIFACTS/import-edges.log" || true
