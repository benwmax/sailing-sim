#!/usr/bin/env bash
# Blind-test round stills: scripts/capture-round.sh <round> [seconds] [scene ...] shoots docs/round-<round>/game/scenes.csv
# with capture-scenes.sh into Artifacts/round-<round>/ (git-ignored; OUT=docs/round-<round>/game once the round is final).
R="${1:?round number}"; shift; ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCENES="$ROOT/docs/round-$R/game/scenes.csv" OUT="${OUT:-$ROOT/Artifacts/round-$R}" exec "$ROOT/scripts/capture-scenes.sh" "${@:-14}"
