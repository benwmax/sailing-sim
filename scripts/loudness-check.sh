#!/usr/bin/env bash
# Loudness and clipping check of the game's master mix (the sound plan's slice item 6).
# Usage: scripts/loudness-check.sh [seconds] [scene ...]      scenes: breeze storm race dusk (default: all four)
# Each scene runs the game uncooked (scripts/run-game.sh, autopilot tacking) with -SailingRecordAudio=<seconds>, which
# records the master mix after the 3 s warm-up to Saved/Bench/loud-<scene>.audio.wav; then scripts/loudness_check.py
# measures each file (integrated LUFS, loudness range, true peak, clipping) against -18 LUFS +-3 and -1 dBTP
# (LOUD_ARGS="--target -16 --tolerance 2" to change) and writes Artifacts/loudness.csv. Exit 1 when a scene fails.
# The recording is what the Mac's output device gets (stereo here; 5.1/7.1 when the Mac sends that).
source "$(dirname "$0")/env.sh"
REC="${1:-30}"; shift || true
SCENES=("$@"); [[ ${#SCENES[@]} -gt 0 ]] || SCENES=(breeze storm race dusk)
args_for() {
  case "$1" in
    breeze) echo "-SailingWind=8 -SailingTWA=90" ;;
    storm) echo "-SailingWeather=Thunderstorm -SailingWeatherTime=120" ;;
    race) echo "-SailingTraffic=1 -SailingRace=20" ;;
    dusk) echo "-SailingHour=20.5 -SailingWind=3 -SailingKeepStart" ;;
    *) echo "unknown scene $1 (breeze storm race dusk)" >&2; return 1 ;;
  esac
}
FILES=()
for S in "${SCENES[@]}"; do
  A=$(args_for "$S")
  OUT="$REPO_ROOT/Saved/Bench/loud-$S.audio.wav"
  rm -f "$OUT" "$REPO_ROOT/Saved/BouncedWavFiles/loud-$S.audio.wav"
  echo "== $S: $A"
  # shellcheck disable=SC2086
  "$REPO_ROOT/scripts/run-game.sh" $((REC + 8)) $A -SailingShot="loud-$S" -SailingRecordAudio="$REC" -SailingNoGpuSlices >/dev/null
  [[ -f "$OUT" ]] || OUT="$REPO_ROOT/Saved/BouncedWavFiles/loud-$S.audio.wav"
  if [[ -f "$OUT" ]]; then FILES+=("$OUT"); else echo "$S: no recording (see the game log for 'Sound: recording')" >&2; fi
done
[[ ${#FILES[@]} -gt 0 ]] || { echo "no recordings" >&2; exit 1; }
PY="$REPO_ROOT/Tools/venv/bin/python"; [[ -x "$PY" ]] || PY=python3
mkdir -p "$REPO_ROOT/Artifacts"
# shellcheck disable=SC2086
"$PY" -I "$REPO_ROOT/scripts/loudness_check.py" "${FILES[@]}" --csv "$REPO_ROOT/Artifacts/loudness.csv" ${LOUD_ARGS:-}
