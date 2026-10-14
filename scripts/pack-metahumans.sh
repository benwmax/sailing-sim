#!/usr/bin/env bash
# Zips the locally built MetaHuman crew (Content/Crew/MetaHumans: bodies, faces, outfits, grooms, the scripted polos and
# shoes) so the Windows PC can use it without rebuilding: the folder is git-ignored (size, and the MetaHuman licence
# covers use, not redistribution), and building it needs an Epic sign-in for the cloud auto-rig.
# Usage: scripts/pack-metahumans.sh     Output: Artifacts/MetaHumans-for-PC.zip (about 0.5 GB)
# Copy the zip to the PC by USB drive or a cloud folder (never commit or publish it), then on the PC:
#   scripts\windows\all.ps1 -MetaHumansZip <path to the zip>
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO_ROOT/Content/Crew/MetaHumans"
OUT="$REPO_ROOT/Artifacts/MetaHumans-for-PC.zip"
if [[ ! -d "$SRC" ]]; then
	echo "No MetaHuman crew at $SRC; build it with scripts/make-metahumans.sh first" >&2
	exit 1
fi
mkdir -p "$REPO_ROOT/Artifacts"
rm -f "$OUT"
# -X leaves out macOS extended attributes; the zip holds the MetaHumans folder itself.
(cd "$REPO_ROOT/Content/Crew" && zip -qr -X "$OUT" MetaHumans -x '*.DS_Store')
echo "Wrote $OUT ($(du -h "$OUT" | cut -f1))"
