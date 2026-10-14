#!/usr/bin/env bash
# Phase 8: reproduces each reference scene in docs/phase-8/reference-scenes.csv with the reference capture mode
# (-SailingCapture) and saves the still, its camera settings and telemetry to docs/phase-8/captures/.
# Usage: scripts/capture-scenes.sh [seconds] [scene ...]   Uncooked (run-game.sh), about 40 s a scene.
# SCENES=<csv> OUT=<dir> pick another scene list (the blind test uses docs/phase-8/blind-test/scenes.csv).
source "$(dirname "$0")/env.sh"
SECONDS_PER_RUN="${1:-12}"; shift || true
SCENES="${SCENES:-$REPO_ROOT/docs/phase-8/reference-scenes.csv}"
OUT="${OUT:-$REPO_ROOT/docs/phase-8/captures}"
mkdir -p "$OUT"
LIST="$(mktemp -t scenes)"
python3 - "$SCENES" "$@" <<'PY' > "$LIST"
import csv, sys
only = set(sys.argv[2:])
for r in csv.DictReader(open(sys.argv[1])):
    if only and r["scene"] not in only: continue
    print(r["scene"] + "|" + r["preset"] + "|" + r["args"])
PY
# Read the whole list first: the game runs must not share the loop's stdin, and another run must not rewrite it.
SCENE_LINES=()
while IFS= read -r L; do SCENE_LINES+=("$L"); done < "$LIST"
rm -f "$LIST"
for L in "${SCENE_LINES[@]}"; do
	IFS='|' read -r SCENE PRESET ARGS <<< "$L"
	read -r -a ARGV <<< "$ARGS"
	"$(dirname "$0")/run-game.sh" "$SECONDS_PER_RUN" ${ARGV[@]+"${ARGV[@]}"} -SailingCapture="$PRESET" -SailingShot="$SCENE" < /dev/null > /dev/null 2>&1 || true
	for EXT in png camera.json telemetry.csv; do
		[[ -f "$REPO_ROOT/Saved/Bench/$SCENE.$EXT" ]] && cp "$REPO_ROOT/Saved/Bench/$SCENE.$EXT" "$OUT/$SCENE.$EXT"
	done
	echo "$SCENE: $([[ -f "$OUT/$SCENE.png" ]] && echo ok || echo FAILED)"
done
