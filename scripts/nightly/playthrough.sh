#!/bin/bash
# #404: the first hour's scripted playthrough on the packaged game, once on keys and once on the pad's buttons. A fresh
# save: the first launch, Skip to the menu (the title), Career, Day Sailor's first lesson (its loading screen, the lesson
# ended by the UI script's Finish:clean through the drill's own finish), its medal screen, the pause menu, Quit to title. Each screen the
# flow reaches is checked (Expect:<screen>) and shot (Shot:<name>, the window with its UI). Fails naming the first screen
# that did not appear.
# Usage: scripts/nightly/playthrough.sh <SailingSim.app> <out dir>    (or --self-test: the log check on stand-in logs)
#   PLAYTHROUGH_FLOWS="keys" runs one input only (dry runs).
set -u
# One lesson from its loading screen: the lesson ended by Finish:<outcome>, its medal screen, the quiz answered right
# (Answer:all, through the quiz's own buttons), the score, then Enter on the score's first way (the next lesson).
lesson() {   # <stage label> <outcome>
	echo "Stage:$1,Wait,Wait,Expect:Loading,Wait,Wait,Wait,Wait,Wait,Wait,Wait,Wait,Wait,Wait,Wait,ENTER,Wait,Wait,ENTER,Wait,Wait"
	echo "Expect:Hud,Shot:$1-lesson,Finish:$2,Wait,Wait"
	echo "Expect:Quiz,Shot:$1-medal,Answer:all,Wait"
	echo "Expect:Quiz,Shot:$1-score"
}
FLOW_STEPS=(
	"Stage:start,Wait,Wait,Expect:FirstLaunch,Shot:01-first-launch"
	"DOWN,ENTER,Wait,Expect:Title,Shot:02-title"
	"DOWN,ENTER,Wait,Expect:Career,Shot:03-career"
	"DOWN,RIGHT,Wait,Shot:04-lesson-1,ENTER"
	$(lesson ds1 clean) "ENTER"
	$(lesson ds2 done) "ENTER"
	$(lesson ds3 done) "ENTER"
	$(lesson ds4 proper) "ENTER"
	$(lesson ds5 proper) "ENTER"
	$(lesson ds6 gentle)
	"Stage:to-career,DOWN,ENTER,Wait,Wait,Expect:Hud,MENU,Wait,Expect:Pause"
	"DOWN,DOWN,DOWN,DOWN,DOWN,DOWN,DOWN,DOWN,DOWN,DOWN,DOWN,DOWN,ENTER,Wait,Expect:Confirm,LEFT,ENTER,Wait,Wait,Wait,Wait,Wait"
	"Expect:Title,Shot:20-title-returning,ENTER,Wait,Expect:Career,Shot:21-career"
	"Stage:explore,DOWN,Shot:e1,DOWN,Shot:e2,DOWN,Shot:e3,DOWN,Shot:e4,DOWN,Shot:e5,DOWN,Shot:e6,DOWN,Shot:e7,DOWN,Shot:e8,ENTER,Wait,Wait,Log,Shot:e9-enter,Quit"
)
flow() {   # <keys|pad>: the script with that input's keys
	local Down=Down Right=Right Left=Left Enter=Enter Back=Escape Menu=Escape S
	[[ "$1" == pad ]] && { Down=Gamepad_DPad_Down; Right=Gamepad_DPad_Right; Left=Gamepad_DPad_Left; Enter=Gamepad_FaceButton_Bottom; Back=Gamepad_FaceButton_Right; Menu=Gamepad_Special_Right; }
	S=$(IFS=,; echo "${FLOW_STEPS[*]}")
	S=${S//DOWN/$Down}; S=${S//RIGHT/$Right}; S=${S//LEFT/$Left}; S=${S//ENTER/$Enter}; S=${S//BACK/$Back}; S=${S//MENU/$Menu}; S=${S//Shot:/Shot:pt-$1-}
	echo "$S"
}
# check <log>: prints PASS, or FAIL with the first screen that did not appear (and the screen that was up instead).
check() {
	local Log=$1 Miss Want
	Want=$(grep -c "UI script: expect " "$Log" 2>/dev/null); Want=${Want:-0}
	if [[ "$Want" == 0 ]]; then echo "FAIL the script never ran (no screen checks in the log)"; return 1; fi
	Miss=$(grep -m1 "UI script: expect .*: MISSING" "$Log" | sed -E 's/.*UI script: expect ([A-Za-z]+): MISSING \(on ([A-Za-z?]+)\).*/\1 (on \2)/')
	if [[ -n "$Miss" ]]; then
		local At; At=$(grep -E "UI script: (stage |expect .*: MISSING)" "$Log" | sed -n '/MISSING/q;p' | tail -1 | sed -E 's/.*UI script: stage //')
		echo "FAIL $Miss${At:+ in $At}"; return 1
	fi
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
	{ echo "UI script: stage start"; echo "UI script: expect FirstLaunch: ok"; echo "UI script: stage ds3"; echo "UI script: expect Quiz: MISSING (on Hud)"; echo "UI script: stage ds4"; } > "$T/miss.log"
	ok "a missing screen is named with its lesson" "$(check "$T/miss.log")" "FAIL Quiz (on Hud) in ds3"
	echo "LogInit: nothing" > "$T/none.log"
	ok "no checks at all fails" "$(check "$T/none.log")" "FAIL the script never ran"
	{ for ((i = 0; i < N; i++)); do echo "UI script: expect X: ok"; done; echo "UI script: finish clean: no drill running"; } > "$T/fin.log"
	ok "an unfinished lesson fails" "$(check "$T/fin.log")" "FAIL the lesson could not be finished"
	echo "UI script: expect FirstLaunch: ok" > "$T/short.log"
	ok "a script cut short fails" "$(check "$T/short.log")" "FAIL the script stopped"
	ok "the pad flow uses the pad's buttons" "$(flow pad | grep -o 'Gamepad_FaceButton_Bottom' | head -1)" "Gamepad_FaceButton_Bottom"
	ok "the keys flow has no pad keys" "$(flow keys | grep -c Gamepad)" "0"
	ok "every lesson is finished and its quiz answered" "$(flow keys | grep -o 'Finish:' | wc -l | tr -d ' ')/$(flow keys | grep -o 'Answer:all' | wc -l | tr -d ' ')" "6/6"
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
# Two minutes a stage (a lesson's loading, sailing and quiz take about one), plus a minute to start.
STAGES=$(echo "${FLOW_STEPS[*]}" | grep -o "Stage:" | wc -l | tr -d ' ')
LIMIT=$(( 60 + 120 * STAGES ))
for F in ${PLAYTHROUGH_FLOWS:-keys pad}; do
	rm -rf "$SV/Config" "$SV/SaveGames" "$SV/Bench/pt-$F-"*.png; mkdir -p "$SV/SaveGames"
	open -n -a "$APP" --args -windowed -ResX=1920 -ResY=1080 -ForceRes -SailingNoGpuSlices -SailingSlice=1 \
		-SailingSave=SaveGames/playthrough.json "-SailingUIScript=$(flow $F)"
	sleep 5
	for ((i = 0; i < LIMIT; i++)); do pgrep -qf "SailingSim.app/Contents/MacOS/SailingSim" || break; sleep 1; done
	if pgrep -qf "SailingSim.app/Contents/MacOS/SailingSim"; then osascript -e 'quit app "SailingSim"' 2>/dev/null; sleep 8; fi
	cp "$SV/Bench/pt-$F-"*.png "$OUT/" 2>/dev/null; cp "$LOGF" "$OUT/$F.log" 2>/dev/null
	R=$(check "$OUT/$F.log") || RC=1
	echo "$F: $R"
	restore
done
exit $RC
