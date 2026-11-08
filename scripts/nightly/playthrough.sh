#!/bin/bash
# #404: the first hour's scripted playthrough on the packaged game, once on keys and once on the pad's buttons. A fresh
# save: the first launch, Skip to the menu, Career, Day Sailor's first lesson (briefing, loading, the lesson ended by the
# UI script's Finish:clean through the drill's own finish), its medal screen and quiz, back to the title. Each screen the
# flow reaches is checked (Expect:<screen>) and shot (Shot:<name>, the window with its UI). Fails naming the first screen
# that did not appear.
# Usage: scripts/nightly/playthrough.sh <SailingSim.app> <out dir>    (or --self-test: the log check on stand-in logs)
set -u
FLOW_STEPS=(
	"Wait,Wait,Expect:FirstLaunch,Shot:01-first-launch"
	"DOWN,ENTER,Wait,Expect:Title,Shot:02-title"
	"DOWN,ENTER,Wait,Expect:Career,Shot:03-career"
	"DOWN,RIGHT,Wait,Shot:04-lesson-1,ENTER,Wait,Wait,Expect:Loading,Shot:05-loading"
	"Wait,Wait,Wait,Wait,Wait,Wait,Wait,Wait,Wait,Wait,Wait,Wait,ENTER,Wait,Wait,ENTER,Wait,Wait,Log,Shot:06-after-loading"
	"Expect:Briefing,Shot:07-briefing,ENTER,Wait,Wait"
	"Expect:Hud,Shot:08-lesson,Finish:clean,Wait,Wait"
	"Expect:Quiz,Shot:09-medal,BACK,Wait,Wait"
	"Expect:Hud,BACK,Wait,Expect:Pause,Shot:10-pause"
	"DOWN,DOWN,DOWN,DOWN,DOWN,DOWN,DOWN,DOWN,DOWN,DOWN,DOWN,DOWN,Shot:11-pause-bottom,ENTER,Wait,Wait,Log,Shot:12-quit,ENTER,Wait,Wait,Wait"
	"Expect:Title,Shot:13-title,Log,Quit"
)
flow() {   # <keys|pad>: the script with that input's keys
	local Down=Down Right=Right Enter=Enter Back=Escape S
	[[ "$1" == pad ]] && { Down=Gamepad_DPad_Down; Right=Gamepad_DPad_Right; Enter=Gamepad_FaceButton_Bottom; Back=Gamepad_FaceButton_Right; }
	S=$(IFS=,; echo "${FLOW_STEPS[*]}")
	S=${S//DOWN/$Down}; S=${S//RIGHT/$Right}; S=${S//ENTER/$Enter}; S=${S//BACK/$Back}; S=${S//Shot:/Shot:pt-$1-}
	echo "$S"
}
# check <log>: prints PASS, or FAIL with the first screen that did not appear (and the screen that was up instead).
check() {
	local Log=$1 Miss Want
	Want=$(grep -c "UI script: expect " "$Log" 2>/dev/null); Want=${Want:-0}
	if [[ "$Want" == 0 ]]; then echo "FAIL the script never ran (no screen checks in the log)"; return 1; fi
	Miss=$(grep -m1 "UI script: expect .*: MISSING" "$Log" | sed -E 's/.*UI script: expect ([A-Za-z]+): MISSING \(on ([A-Za-z?]+)\).*/\1 (on \2)/')
	if [[ -n "$Miss" ]]; then echo "FAIL $Miss"; return 1; fi
	if grep -q "UI script: finish .*: no drill running\|UI script: finish .*: not in this build" "$Log"; then echo "FAIL the lesson could not be finished ($(grep -m1 'UI script: finish' "$Log" | sed 's/.*UI script: //'))"; return 1; fi
	local Need; Need=$(echo "${FLOW_STEPS[*]}" | grep -o "Expect:" | wc -l | tr -d ' ')
	if [[ "$Want" -lt "$Need" ]]; then echo "FAIL the script stopped after $Want of $Need screen checks"; return 1; fi
	echo "PASS $Want screens"
}
if [[ "${1:-}" == "--self-test" ]]; then
	T=$(mktemp -d); F=0
	ok() { if [[ "$2" == "$3"* ]]; then echo "ok   $1"; else echo "FAIL $1 (got '$2')"; F=$((F + 1)); fi; }
	N=$(echo "${FLOW_STEPS[*]}" | grep -o "Expect:" | wc -l | tr -d ' ')
	for ((i = 0; i < N; i++)); do echo "LogSailing: Display: UI script: expect X: ok"; done > "$T/pass.log"
	ok "every screen up passes" "$(check "$T/pass.log")" "PASS"
	{ echo "UI script: expect FirstLaunch: ok"; echo "UI script: expect Career: MISSING (on Title)"; } > "$T/miss.log"
	ok "a missing screen is named" "$(check "$T/miss.log")" "FAIL Career (on Title)"
	echo "LogInit: nothing" > "$T/none.log"
	ok "no checks at all fails" "$(check "$T/none.log")" "FAIL the script never ran"
	{ echo "UI script: expect Hud: ok"; echo "UI script: finish clean: no drill running"; } > "$T/fin.log"
	ok "an unfinished lesson fails" "$(check "$T/fin.log")" "FAIL the lesson could not be finished"
	echo "UI script: expect FirstLaunch: ok" > "$T/short.log"
	ok "a script cut short fails" "$(check "$T/short.log")" "FAIL the script stopped"
	ok "the pad flow uses the pad's buttons" "$(flow pad | grep -o 'Gamepad_FaceButton_Bottom' | head -1)" "Gamepad_FaceButton_Bottom"
	ok "the keys flow has no pad keys" "$(flow keys | grep -c Gamepad)" "0"
	rm -rf "$T"; echo "self-test: $F failure(s)"; exit $(( F > 0 ))
fi
APP=$1; OUT=$2; mkdir -p "$OUT"
C="$HOME/Library/Containers/com.benwmax.SailingSim/Data/Library"
SV="$C/Application Support/Epic/SailingSim/Saved"; LOGF="$C/Logs/SailingSim/SailingSim.log"
# A fresh profile for each run (no settings, no saves: the title's last session lives in the settings), and the
# player's own settings and saves put back after it.
B=$(mktemp -d); mkdir -p "$SV/Config" "$SV/SaveGames"; cp -Rp "$SV/Config" "$B/Config"; cp -Rp "$SV/SaveGames" "$B/SaveGames"
restore() { rm -rf "$SV/Config" "$SV/SaveGames"; cp -Rp "$B/Config" "$SV/Config"; cp -Rp "$B/SaveGames" "$SV/SaveGames"; }
trap 'restore; rm -rf "$B"' EXIT
RC=0
for F in keys pad; do
	rm -rf "$SV/Config" "$SV/SaveGames" "$SV/Bench/pt-$F-"*.png; mkdir -p "$SV/SaveGames"
	open -n -a "$APP" --args -windowed -ResX=1920 -ResY=1080 -ForceRes -SailingNoGpuSlices -SailingSlice=1 \
		-SailingSave=SaveGames/playthrough.json "-SailingUIScript=$(flow $F)"
	sleep 5
	for ((i = 0; i < 300; i++)); do pgrep -qf "SailingSim.app/Contents/MacOS/SailingSim" || break; sleep 1; done
	if pgrep -qf "SailingSim.app/Contents/MacOS/SailingSim"; then osascript -e 'quit app "SailingSim"' 2>/dev/null; sleep 8; fi
	cp "$SV/Bench/pt-$F-"*.png "$OUT/" 2>/dev/null; cp "$LOGF" "$OUT/$F.log" 2>/dev/null
	R=$(check "$OUT/$F.log") || RC=1
	echo "$F: $R"
	restore
done
exit $RC
