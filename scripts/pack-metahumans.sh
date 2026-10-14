#!/usr/bin/env bash
# Graphics G8: packs the built MetaHuman crew (git-ignored: /Game/Crew/MetaHumans, the helm, trimmer and bow with their
# grooms, polo, vest and shoes) into one zip for the Windows PC, which cannot build them headless (no Epic cloud rig there).
# Unzip it over the PC's checkout root: it holds Content/Crew/MetaHumans/... and a MANIFEST.txt.
#   scripts/pack-metahumans.sh [--sources]     --sources adds Content/Crew/MetaHumanSources (the editable characters)
# Writes Artifacts/MetaHumanCrew-<date>-<commit>.zip. The licence covers use on Bean's own machines, not redistribution:
# never commit or publish the zip.
source "$(dirname "$0")/env.sh"
cd "$REPO_ROOT"
DIRS=(Content/Crew/MetaHumans)
[[ "${1:-}" == "--sources" ]] && DIRS+=(Content/Crew/MetaHumanSources)
for d in "${DIRS[@]}"; do
	[[ -d "$d" ]] || { echo "pack-metahumans: $d is missing (scripts/make-metahumans.sh, then scripts/make-crew-clothes.sh)"; exit 1; }
done
for role in Helm Trimmer Bow; do
	for piece in Polo Shoes Vest; do
		[[ -f "Content/Crew/MetaHumans/$role/Clothing/SKM_${role}_${piece}.uasset" ]] || echo "pack-metahumans: warning, no SKM_${role}_${piece}"
	done
done
COMMIT=$(git rev-parse --short HEAD)
ZIP="$ARTIFACTS/MetaHumanCrew-$(date +%Y%m%d)-$COMMIT.zip"
MANIFEST="$ARTIFACTS/MANIFEST.txt"
{
	echo "SailingSim MetaHuman crew, packed $(date -u +%Y-%m-%dT%H:%MZ) from $(git rev-parse --abbrev-ref HEAD) @ $COMMIT"
	echo "Unzip over the checkout root (it replaces Content/Crew/MetaHumans). Needs the engine's MetaHuman and HairStrands plugins."
	echo "The crew fabric (/Game/Crew/Fabric) and gear (/Game/Crew/Gear) are in git: pull the same commit."
	echo
	find "${DIRS[@]}" -name '*.uasset' -o -name '*.ubulk' -o -name '*.uexp' | sort | while read -r f; do echo "$(stat -f %z "$f") $f"; done
} > "$MANIFEST"
rm -f "$ZIP"
zip -qr -1 "$ZIP" "${DIRS[@]}" -x '*.DS_Store'
(cd "$ARTIFACTS" && zip -q "$ZIP" MANIFEST.txt)
echo "pack-metahumans: $ZIP ($(du -h "$ZIP" | cut -f1), $(grep -c '^[0-9]' "$MANIFEST") files)"
