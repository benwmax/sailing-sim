# Sourced by package-mac.sh (docs/xcode27-stdin/). Xcode 27 fails to launch a scheme's pre-action ("Failed to launch
# task /bin/sh: Bad file descriptor", seen only in the .xcactivitylog) when xcodebuild has no stdin, and UnrealBuildTool's
# app finalization (ApplePostBuildSync) runs it that way: every package failed with "Run custom shell script 'Touch UBT
# generated tiles'". UBT finds xcodebuild through `xcode-select -p`, which honours DEVELOPER_DIR. So this points it at a
# mirror of the selected Xcode's Developer folder (symlinks; Contents' other entries beside it for the version files),
# whose usr/bin/xcodebuild runs the real one with stdin from /dev/null. Nothing else changes: every other tool is the
# real one through its link. The mirror lives in Artifacts/ (git-ignored; the main-tree baseline gets its own under its
# SAILING_ROOT) and is rebuilt when the selected Xcode or its build changes. The real Xcode is never written to. Only
# Xcode 27 takes it, so it drops away with the next major; SAILING_NO_XCODE_SHIM=1 skips it (to check a fix).
xcode_stdin_shim() {
	[[ "${SAILING_NO_XCODE_SHIM:-0}" == 1 ]] && return 0
	local Real Version Major Shim Stamp E N
	# A DEVELOPER_DIR that is already a mirror (an inherited environment) is not the Xcode to mirror.
	[[ "${DEVELOPER_DIR:-}" == */xcode-shim/Xcode.app/Contents/Developer ]] && unset DEVELOPER_DIR
	Real="$(xcode-select -p 2>/dev/null)" || return 0
	Version="$(xcodebuild -version 2>/dev/null | tr '\n' ' ')"
	Major="$(awk '{split($2, V, "."); print V[1]; exit}' <<< "$Version")"
	[[ "$Major" == 27 ]] || return 0
	Shim="$ARTIFACTS/xcode-shim/Xcode.app/Contents"
	Stamp="$ARTIFACTS/xcode-shim/stamp"
	if [[ "$(cat "$Stamp" 2>/dev/null)" == "$Real $Version" && -x "$Shim/Developer/usr/bin/xcodebuild" ]]; then
		export DEVELOPER_DIR="$Shim/Developer"
		return 0
	fi
	rm -rf "$ARTIFACTS/xcode-shim"
	mkdir -p "$Shim/Developer/usr/bin"
	for E in "$Real/.."/*; do N="$(basename "$E")"; [[ "$N" == Developer ]] || ln -s "$(cd "$Real/.." && pwd)/$N" "$Shim/$N"; done
	for E in "$Real"/*; do N="$(basename "$E")"; [[ "$N" == usr ]] || ln -s "$E" "$Shim/Developer/$N"; done
	for E in "$Real/usr"/*; do N="$(basename "$E")"; [[ "$N" == bin ]] || ln -s "$E" "$Shim/Developer/usr/$N"; done
	for E in "$Real/usr/bin"/*; do N="$(basename "$E")"; [[ "$N" == xcodebuild ]] || ln -s "$E" "$Shim/Developer/usr/bin/$N"; done
	printf '#!/bin/sh\nDEVELOPER_DIR="%s" exec "%s/usr/bin/xcodebuild" "$@" < /dev/null\n' "$Real" "$Real" > "$Shim/Developer/usr/bin/xcodebuild"
	chmod +x "$Shim/Developer/usr/bin/xcodebuild"
	echo "$Real $Version" > "$Stamp"
	export DEVELOPER_DIR="$Shim/Developer"
	echo "Xcode $Major: xcodebuild runs with stdin from /dev/null (scripts/xcode-stdin-shim.sh)"
}
