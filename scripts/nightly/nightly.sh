#!/bin/bash
# The nightly Mac bench (#401): scripts/gate.sh --scope all --force on origin/main, in its own worktree
# Artifacts/wt-nightly, under the Mac lock. Writes Artifacts/nightly/<date>.csv (the sweep), <date>.log and a one-line
# <date>.txt, copied to latest.txt. Run by ~/Library/LaunchAgents/com.benwmax.sailing-nightly.plist at 03:00 Dallas time.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# The stall watchdog (Nov 6 2026): the gate is ended and the night written STALLED when its logs show no progress for
# NIGHTLY_STALL_S (20 min) or it runs past NIGHTLY_LIMIT_S (4 h; a whole night takes under 1 h). On Nov 1 and Nov 6 the
# test editor waited six hours on a macOS dialog (Documents folder access) while its timers kept writing to the log, so
# progress is the count of log lines other than that idle noise, summed over every log the gate writes.
STALL_S=${NIGHTLY_STALL_S:-1200}; LIMIT_S=${NIGHTLY_LIMIT_S:-14400}; POLL_S=${NIGHTLY_POLL_S:-60}
NOISE='idevice_id|Failed to launch Tool|Network path changed|Maintenance finished'
progress() { local t=0 f n; for f in "$@"; do [[ -f "$f" ]] || continue; n=$(grep -cvE "$NOISE" "$f" 2>/dev/null); t=$((t + ${n:-0})); done; echo "$t"; }
newest() { ls -t "$@" 2>/dev/null | head -1; }
killtree() { local c; for c in $(pgrep -P "$1"); do killtree "$c"; done; kill -TERM "$1" 2>/dev/null; }
# watch_job <pid> <log>...: 0 when the job ends by itself; 1 when it was ended for a stall (STALL_MSG says why).
watch_job() {
	local pid=$1 start=$SECONDS last=$SECONDS sig=-1 n; shift
	STALL_MSG=""; STALL_TAIL=""
	while kill -0 "$pid" 2>/dev/null; do
		sleep "$POLL_S"
		n=$(progress "$@")
		[[ "$n" != "$sig" ]] && { sig=$n; last=$SECONDS; }
		if (( SECONDS - last >= STALL_S )); then STALL_MSG="no progress for $(( (SECONDS - last) / 60 )) min"
		elif (( SECONDS - start >= LIMIT_S )); then STALL_MSG="past the $(( LIMIT_S / 60 )) min limit"; fi
		if [[ -n "$STALL_MSG" ]]; then
			local log; log=$(newest "$@")
			STALL_TAIL="$(basename "$log"): $(grep -vE "$NOISE" "$log" 2>/dev/null | tail -3 | cut -c1-160 | paste -sd '|' -)"
			killtree "$pid"; sleep 5; kill -KILL "$pid" 2>/dev/null
			return 1
		fi
	done
	return 0
}

if [[ "$1" == "--self-test" ]]; then
	# The watchdog on stand-in jobs, in seconds: no gate, no lock, no summary.
	T=$(mktemp -d); STALL_S=3; LIMIT_S=8; POLL_S=1; FAILS=0
	check() { if [[ "$2" == "$3" ]]; then echo "ok   $1"; else echo "FAIL $1 (got $2, want $3)"; FAILS=$((FAILS + 1)); fi; }
	( for i in 1 2 3; do echo "LogAutomation: test $i" >> "$T/a.log"; sleep 1; done ) & watch_job $! "$T/a.log"
	check "a job that finishes is left alone" "$?" 0
	( sleep 1000 & echo $! > "$T/child"; while :; do echo "LogHAL: Warning: idevice_id failed" >> "$T/b.log"; sleep 0.3; done ) 2>/dev/null & B=$!
	watch_job $B "$T/b.log" "$T/missing.log"; R=$?; sleep 1
	check "only idle noise is a stall" "$R" 1
	check "the reason" "${STALL_MSG%% for*}" "no progress"
	check "the job and its child are ended" "$(kill -0 $B 2>/dev/null && echo job)$(kill -0 "$(cat "$T/child")" 2>/dev/null && echo child)" ""
	( while :; do echo "LogAutomation: busy $RANDOM" >> "$T/c.log"; sleep 0.3; done ) 2>/dev/null & watch_job $! "$T/c.log"; R=$?
	check "a job past the limit is ended" "$R" 1
	check "the limit's reason" "${STALL_MSG%% min*}" "past the 0"
	check "the last lines are kept" "${STALL_TAIL%%:*}" "c.log"
	rm -rf "$T"; echo "self-test: $FAILS failure(s)"; exit $(( FAILS > 0 ))
fi
ROOT=/Users/ben/myProjects/sailing-sim
N=$ROOT/Artifacts/nightly; W=$ROOT/Artifacts/wt-nightly
DAY=$(date -u +%F); LOG=$N/$DAY.log; SUM=$N/$DAY.txt
summary() { echo "$DAY $(date -u +%H:%MZ) $*" > "$SUM"; cp "$SUM" "$N/latest.txt"; }
exec > "$LOG" 2>&1
echo "nightly $DAY start $(date -u +%T)"
# A locked screen: the game can't open its window. Skip the night instead (keep the Mac unlocked overnight: Lock Screen
# settings). (The test editor's six-hour waits on Nov 1 and Nov 6 2026 were a Documents-folder dialog, not the lock:
# scripts/test.sh turns off the editor's Home screen, which asked for it, and the watchdog above ends any other stall.)
if ioreg -n Root -d1 -a | plutil -extract IOConsoleUsers xml1 -o - - 2>/dev/null | grep -A1 CGSSessionScreenIsLocked | grep -q true; then
	summary "SKIPPED: the screen is locked (benches need the game window on screen)"; exit 0
fi
# The shader compiler: after an Xcode update the Metal toolchain must be downloaded again (xcrun -f finds the path anyway).
if ! xcrun metal -v > /dev/null 2>&1; then
	summary "SKIPPED: the Metal toolchain is missing (run: xcodebuild -downloadComponent MetalToolchain)"; exit 0
fi
cd "$ROOT" || exit 1
git fetch -q origin main || { summary "SKIPPED: git fetch failed"; exit 0; }
if [[ ! -d "$W" ]]; then git worktree add -q --detach "$W" origin/main || { summary "SKIPPED: no worktree"; exit 0; }; fi
cd "$W" || exit 1
git checkout -q --detach -f origin/main
git lfs pull > /dev/null 2>&1
for D in MetaHumans MetaHumanSources Capture; do
	[[ -d "$ROOT/Content/Crew/$D" && ! -e "Content/Crew/$D" ]] && ln -s "$ROOT/Content/Crew/$D" "Content/Crew/$D"
done
SHA=$(git rev-parse --short HEAD)
export MAC_LOCK_OWNER="nightly $DAY"
export MAC_LOCK_WAIT=10800
# Keep the display awake for the benches (a sleeping display hangs the game at window creation); the desktop must be
# unlocked. caffeinate ends with the gate.
caffeinate -dimsu -w $$ &
bash scripts/gate.sh --scope all --force > "$N/$DAY.gate.txt" 2>&1 &
GATE=$!
GAME_LOG="$HOME/Library/Containers/com.benwmax.SailingSim/Data/Library/Logs/SailingSim/SailingSim.log"
if ! watch_job $GATE "$N/$DAY.gate.txt" Artifacts/build.log Artifacts/test.log Artifacts/package.log Artifacts/gate/test.out "$GAME_LOG"; then
	pkill -f "$W/Packaged/" 2>/dev/null   # a bench's game is started by open, not by the gate
	bash scripts/mac-lock.sh drop
	summary "STALLED main $SHA: $STALL_MSG at $(date -u +%H:%MZ), ended [$STALL_TAIL] ($N/$DAY.gate.txt)"
	echo "nightly stalled $(date -u +%T): $STALL_MSG"; exit 0
fi
wait $GATE
RC=$?
cp Artifacts/visual-bench-gate-all.csv "$N/$DAY.csv" 2>/dev/null
RESULT=$(grep -E "^gate: " "$N/$DAY.gate.txt" | tail -1)
UNDER=$(grep -E "UNDER|lost" "$N/$DAY.gate.txt" | tr -s ' ' | head -6 | paste -sd ';' -)
# #404: a test failure names the tests (the gate's test.out), so the morning line says what broke.
FAILED=$(grep -E "^Fail" Artifacts/gate/test.out 2>/dev/null | awk '{print $2}' | head -8 | paste -sd ',' -)
# A view on its floor reads either side of it from run to run (storm High: 44.7 to 45.6 in one session on Nov 2 2026, the
# same before and after the merges suspected). Each view under its floor is benched once more, alone, in this run; the
# night breaks only when the rerun is under too, and a lost view (no reading) always breaks it.
FLAPS=(); BREAKS=()
if [[ -z "$FAILED" && $RC != 0 && -n "$RESULT" ]]; then
	while read -r VIEW Q FPS REST; do
		FLOOR=${REST##* }
		if ! MAC_LOCK_WAIT=3600 bash scripts/mac-lock.sh take; then BREAKS+=("$VIEW $Q $FPS, no rerun (lock)"); continue; fi
		PIN_HIGH=1 ONLY=$VIEW bash scripts/bench-visual.sh 12 nightly-rerun "$Q" > "$N/$DAY.rerun-$VIEW-$Q.txt" 2>&1
		bash scripts/mac-lock.sh drop
		AGAIN=$(awk -v v="$VIEW" -v q="$Q" '$1 == v && $2 == q { print $3 }' "$N/$DAY.rerun-$VIEW-$Q.txt" | tail -1)
		if [[ -n "$AGAIN" ]] && awk -v a="$AGAIN" -v f="$FLOOR" 'BEGIN { exit !(a >= f) }'; then FLAPS+=("$VIEW $Q: first $FPS, rerun $AGAIN")
		else BREAKS+=("$VIEW $Q: $FPS, rerun ${AGAIN:-none}, floor $FLOOR"); fi
	done < <(grep -E " UNDER [0-9.]+$" "$N/$DAY.gate.txt")
fi
# Every view the gate counted (under or lost) must be one rerun and passed for the night to pass.
COUNTED=$(echo "$RESULT" | grep -oE "[0-9]+ view" | grep -oE "[0-9]+")
if [[ -n "$FAILED" ]]; then summary "TESTS FAILED main $SHA: $FAILED ($N/$DAY.gate.txt)"
elif [[ $RC == 0 ]]; then summary "PASS main $SHA: ${RESULT:-gate: pass} ($N/$DAY.csv)"
elif [[ -z "$RESULT" ]]; then summary "ERROR main $SHA: the gate stopped before the bench (exit $RC): $(grep -vE '^\[gate' "$N/$DAY.gate.txt" | tail -1)"
elif [[ ${#BREAKS[@]} == 0 && ${#FLAPS[@]} -gt 0 && "${COUNTED:-0}" == "${#FLAPS[@]}" ]]; then
	summary "PASS main $SHA (flapping: $(IFS=';'; echo "${FLAPS[*]}")) ($N/$DAY.csv)"
else summary "FLOOR BREAK main $SHA: $RESULT ${UNDER:+[$UNDER]}${BREAKS:+ [reruns: $(IFS=';'; echo "${BREAKS[*]}")]} ($N/$DAY.csv)"; fi
echo "nightly done $(date -u +%T) rc=$RC"
