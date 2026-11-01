#!/bin/bash
# The nightly Mac bench (#401): scripts/gate.sh --scope all --force on origin/main, in its own worktree
# Artifacts/wt-nightly, under the Mac lock. Writes Artifacts/nightly/<date>.csv (the sweep), <date>.log and a one-line
# <date>.txt, copied to latest.txt. Run by ~/Library/LaunchAgents/com.benwmax.sailing-nightly.plist at 03:00 Dallas time.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
ROOT=/Users/ben/myProjects/sailing-sim
N=$ROOT/Artifacts/nightly; W=$ROOT/Artifacts/wt-nightly
DAY=$(date -u +%F); LOG=$N/$DAY.log; SUM=$N/$DAY.txt
summary() { echo "$DAY $(date -u +%H:%MZ) $*" > "$SUM"; cp "$SUM" "$N/latest.txt"; }
exec > "$LOG" 2>&1
echo "nightly $DAY start $(date -u +%T)"
# A locked screen: the game can't open its window, and even the headless test editor stalled for hours on Nov 1 2026
# until the screen was unlocked. Skip the night instead (keep the Mac unlocked overnight: Lock Screen settings).
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
bash scripts/gate.sh --scope all --force > "$N/$DAY.gate.txt" 2>&1
RC=$?
cp Artifacts/visual-bench-gate-all.csv "$N/$DAY.csv" 2>/dev/null
RESULT=$(grep -E "^gate: " "$N/$DAY.gate.txt" | tail -1)
UNDER=$(grep -E "UNDER|lost" "$N/$DAY.gate.txt" | tr -s ' ' | head -6 | paste -sd ';' -)
# #404: a test failure names the tests (the gate's test.out), so the morning line says what broke.
FAILED=$(grep -E "^Fail" Artifacts/gate/test.out 2>/dev/null | awk '{print $2}' | head -8 | paste -sd ',' -)
if [[ -n "$FAILED" ]]; then summary "TESTS FAILED main $SHA: $FAILED ($N/$DAY.gate.txt)"
elif [[ $RC == 0 ]]; then summary "PASS main $SHA: ${RESULT:-gate: pass} ($N/$DAY.csv)"
elif [[ -z "$RESULT" ]]; then summary "ERROR main $SHA: the gate stopped before the bench (exit $RC): $(grep -vE '^\[gate' "$N/$DAY.gate.txt" | tail -1)"
else summary "FLOOR BREAK main $SHA: $RESULT ${UNDER:+[$UNDER]} ($N/$DAY.csv)"; fi
echo "nightly done $(date -u +%T) rc=$RC"
