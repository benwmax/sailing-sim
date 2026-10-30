#!/usr/bin/env bash
# The Mac's GPU and build lock, shared by every session on this machine: Artifacts/mac-build.lock in the main checkout.
#   scripts/mac-lock.sh take   waits for the lock and takes it atomically (noclobber); exits 1 after MAC_LOCK_WAIT
#                              seconds (default 3 h) without it
#   scripts/mac-lock.sh drop   removes the lock only if it is ours
#   scripts/mac-lock.sh held   exits 0 if the lock is ours
# MAC_LOCK_OWNER (required) names the holder, e.g. "storm-cost session 6e6e3d2b"; the lock is ours when its line starts
# with it. A wrapper that already holds the lock and runs gate.sh keeps the same MAC_LOCK_OWNER: the gate sees the lock
# is held by its owner and goes on without taking or dropping it. Never remove another owner's lock.
set -u
ROOT="$(git -C "$(dirname "$0")" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)"
ROOT="${MAC_LOCK_ROOT:-${ROOT%/.git}}"
LOCK="$ROOT/Artifacts/mac-build.lock"
OWNER="${MAC_LOCK_OWNER:-}"
if [[ -z "$OWNER" ]]; then
	echo "mac-lock: set MAC_LOCK_OWNER (who holds the lock, e.g. \"<job> session <id>\")" >&2
	exit 2
fi
ours() { [[ -f "$LOCK" ]] && [[ "$(head -c ${#OWNER} "$LOCK")" == "$OWNER" ]]; }
case "${1:-}" in
	take)
		ours && exit 0
		mkdir -p "$(dirname "$LOCK")"
		WAIT="${MAC_LOCK_WAIT:-10800}"; START=$(date +%s); SAID=0
		until ( set -o noclobber; echo "$OWNER $(date -u +%FT%TZ)" > "$LOCK" ) 2>/dev/null; do
			if (( $(date +%s) - START >= WAIT )); then
				echo "mac-lock: still held after ${WAIT} s by: $(cat "$LOCK" 2>/dev/null)" >&2
				exit 1
			fi
			if (( !SAID )); then echo "mac-lock: waiting for: $(cat "$LOCK" 2>/dev/null)" >&2; SAID=1; fi
			sleep 30
		done
		ours ;;
	drop)
		if ours; then rm -f "$LOCK"; fi ;;
	held)
		ours ;;
	*)
		echo "usage: mac-lock.sh take|drop|held" >&2; exit 2 ;;
esac
