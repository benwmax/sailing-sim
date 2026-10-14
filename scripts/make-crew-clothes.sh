#!/usr/bin/env bash
# Graphics G3: the crew's free, scripted clothing. Exports each MetaHuman body (scripts/export_crew_bodies.py), tailors
# the polo (from the T-shirt) and the deck shoes (from the feet) in Blender (Tools/blender/build_polo.py: the garment around the body, skinned from it), and imports
# it to /Game/Crew/MetaHumans/<Role>/Clothing/SKM_<Role>_Polo on the body's skeleton (scripts/import_crew_clothes.py).
# Needs the MetaHumans (scripts/make-metahumans.sh) and Blender. Logs in Artifacts/crew-*.log.
source "$(dirname "$0")/env.sh"
BLENDER="${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}"
CREW="$ARTIFACTS/crew"
mkdir -p "$CREW"
APP="$UE_ROOT/Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor"
if [[ "${SKIP_EXPORT:-0}" != 1 ]]; then
	"$APP" "$PROJECT" -EnablePlugins=MetaHumanCharacter -ExecCmds="py $REPO_ROOT/scripts/export_crew_bodies.py" -nosplash -NoP4 -stdout \
		-unattended > "$ARTIFACTS/crew-export.log" 2>&1 || true
	grep "Crew bodies" "$ARTIFACTS/crew-export.log" | sed 's/.*LogPython: //'
fi
[[ "${EXPORT_ONLY:-0}" == 1 ]] && exit 0
for role in Helm Trimmer Bow; do
	"$BLENDER" -b --factory-startup -noaudio -P "$REPO_ROOT/Tools/blender/build_polo.py" -- "$CREW/${role}_Outfit.fbx" "$CREW/${role}_Polo.fbx" \
		> "$ARTIFACTS/crew-blender-$role.log" 2>&1 || { tail -30 "$ARTIFACTS/crew-blender-$role.log"; exit 1; }
	grep -E "^Polo:" "$ARTIFACTS/crew-blender-$role.log" || true
	"$BLENDER" -b --factory-startup -noaudio -P "$REPO_ROOT/Tools/blender/build_shoes.py" -- "$CREW/${role}_Body.fbx" "$CREW/${role}_Shoes.fbx" \
		> "$ARTIFACTS/crew-shoes-$role.log" 2>&1 || { tail -30 "$ARTIFACTS/crew-shoes-$role.log"; exit 1; }
	grep -E "^Shoes:" "$ARTIFACTS/crew-shoes-$role.log" || true
done
"$EDITOR_CMD" "$PROJECT" -run=pythonscript -script="$REPO_ROOT/scripts/import_crew_clothes.py" -unattended -nosplash -nosound -NoP4 -stdout -FullStdOutLogOutput > "$ARTIFACTS/crew-import.log" 2>&1 || true
grep "Crew clothes" "$ARTIFACTS/crew-import.log" | sed 's/.*LogPython: //'
