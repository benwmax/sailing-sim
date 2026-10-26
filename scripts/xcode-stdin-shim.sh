# Sourced by package-mac.sh (docs/xcode27-stdin/). Xcode 27 fails to launch a scheme's pre-action ("Failed to launch
# task /bin/sh: Bad file descriptor", seen only in the .xcactivitylog) when xcodebuild has no stdin, and UnrealBuildTool's
# app finalization (ApplePostBuildSync) runs it that way: every package failed with "Run custom shell script 'Touch UBT
# generated tiles'". UBT finds xcodebuild through `xcode-select -p`, which honours DEVELOPER_DIR. So this points it at a
# mirror of the selected Xcode's Developer folder (symlinks; Contents' other entries beside it for the version files),
# whose usr/bin/xcodebuild runs the real one with stdin from /dev/null. Nothing else changes: every other tool is the
# real one through its link. Xcode 26 and earlier, or SAILING_NO_XCODE_SHIM=1, skip it.
xcode_stdin_shim() {
	[[ "${SAILING_NO_XCODE_SHIM:-0}" == 1 ]] && return 0
	local Real Major Shim E N
	Real="$(xcode-select -p 2>/dev/null)" || return 0
	Major="$(xcodebuild -version 2>/dev/null | awk '/^Xcode/ {split($2, V, "."); print V[1]}')"
	[[ -n "$Major" && "$Major" -ge 27 ]] || return 0
	Shim="$ARTIFACTS/xcode-shim/Xcode.app/Contents"
	rm -rf "$ARTIFACTS/xcode-shim"
	mkdir -p "$Shim/Developer/usr/bin"
	for E in "$Real/.."/*; do N="$(basename "$E")"; [[ "$N" == Developer ]] || ln -s "$(cd "$Real/.." && pwd)/$N" "$Shim/$N"; done
	for E in "$Real"/*; do N="$(basename "$E")"; [[ "$N" == usr ]] || ln -s "$E" "$Shim/Developer/$N"; done
	for E in "$Real/usr"/*; do N="$(basename "$E")"; [[ "$N" == bin ]] || ln -s "$E" "$Shim/Developer/usr/$N"; done
	for E in "$Real/usr/bin"/*; do N="$(basename "$E")"; [[ "$N" == xcodebuild ]] || ln -s "$E" "$Shim/Developer/usr/bin/$N"; done
	printf '#!/bin/sh\nDEVELOPER_DIR="%s" exec "%s/usr/bin/xcodebuild" "$@" < /dev/null\n' "$Real" "$Real" > "$Shim/Developer/usr/bin/xcodebuild"
	chmod +x "$Shim/Developer/usr/bin/xcodebuild"
	export DEVELOPER_DIR="$Shim/Developer"
	echo "Xcode $Major: xcodebuild runs with stdin from /dev/null (scripts/xcode-stdin-shim.sh)"
}
