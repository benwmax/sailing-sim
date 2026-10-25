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
	# The export ends the editor with os._exit, which can cut the log before its "Crew bodies" lines, so the FBX files
	# written after this stamp are the proof of the export (a missing grep match would end the script under pipefail).
	touch "$CREW/.export-start"
	"$APP" "$PROJECT" -EnablePlugins=MetaHumanCharacter -ExecCmds="py $REPO_ROOT/scripts/export_crew_bodies.py" -nosplash -NoP4 -stdout \
		-unattended > "$ARTIFACTS/crew-export.log" 2>&1 || true
	for role in Helm Trimmer Bow; do
		for part in Body Outfit; do
			fbx="$CREW/${role}_$part.fbx"
			[[ "$fbx" -nt "$CREW/.export-start" ]] || { echo "Crew bodies: $role $part not exported (see $ARTIFACTS/crew-export.log)"; exit 1; }
		done
	done
	echo "Crew bodies: 6 FBX exported to $CREW"
fi
[[ "${EXPORT_ONLY:-0}" == 1 ]] && exit 0
for role in Helm Trimmer Bow; do
	"$BLENDER" -b --factory-startup -noaudio -P "$REPO_ROOT/Tools/blender/build_polo.py" -- "$CREW/${role}_Outfit.fbx" "$CREW/${role}_Polo.fbx" \
		> "$ARTIFACTS/crew-blender-$role.log" 2>&1 || { tail -30 "$ARTIFACTS/crew-blender-$role.log"; exit 1; }
	grep -E "^Polo:" "$ARTIFACTS/crew-blender-$role.log" || true
	"$BLENDER" -b --factory-startup -noaudio -P "$REPO_ROOT/Tools/blender/build_shoes.py" -- "$CREW/${role}_Body.fbx" "$CREW/${role}_Shoes.fbx" \
		> "$ARTIFACTS/crew-shoes-$role.log" 2>&1 || { tail -30 "$ARTIFACTS/crew-shoes-$role.log"; exit 1; }
	grep -E "^Shoes:" "$ARTIFACTS/crew-shoes-$role.log" || true
	# Graphics G6: the life jacket tailored over the polo.
	# Graphics G8: and the polo with its torso under the vest cut away (imported as the polo).
	"$BLENDER" -b --factory-startup -noaudio -P "$REPO_ROOT/Tools/blender/build_vest.py" -- "$CREW/${role}_Polo.fbx" "$CREW/${role}_Vest.fbx" "$CREW/${role}_PoloOpen.fbx" \
		> "$ARTIFACTS/crew-vest-$role.log" 2>&1 || { tail -30 "$ARTIFACTS/crew-vest-$role.log"; exit 1; }
	grep -E "^Vest:" "$ARTIFACTS/crew-vest-$role.log" || true
	# Ultra audit item 7: the open polo's looseness (its hem and cuffs) as a vertex colour.
	"$BLENDER" -b --factory-startup -noaudio -P "$REPO_ROOT/Tools/blender/crew_looseness.py" -- "$CREW/${role}_PoloOpen.fbx" "$CREW/${role}_PoloLoose.fbx" \
		> "$ARTIFACTS/crew-loose-$role.log" 2>&1 || { tail -30 "$ARTIFACTS/crew-loose-$role.log"; exit 1; }
	grep -E "^Looseness:" "$ARTIFACTS/crew-loose-$role.log" || true
done
"$EDITOR_CMD" "$PROJECT" -run=pythonscript -script="$REPO_ROOT/scripts/import_crew_clothes.py" -unattended -nosplash -nosound -NoP4 -stdout -FullStdOutLogOutput > "$ARTIFACTS/crew-import.log" 2>&1 || true
grep "Crew clothes" "$ARTIFACTS/crew-import.log" | sed 's/.*LogPython: //'
# Graphics G8: the faces' micro skin detail and pores (the optimized build leaves them off).
"$EDITOR_CMD" "$PROJECT" -run=pythonscript -script="$REPO_ROOT/scripts/tune_crew_skin.py" -unattended -nosplash -nosound -NoP4 -stdout -FullStdOutLogOutput > "$ARTIFACTS/crew-skin.log" 2>&1 || true
grep "Crew skin" "$ARTIFACTS/crew-skin.log" | sed 's/.*LogPython: //' | tail -1
