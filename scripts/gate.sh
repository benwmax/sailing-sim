#!/usr/bin/env bash
# Bench-fast (docs/bench-fast): the Mac gate for a change, scoped to what it can affect.
#   scripts/gate.sh --scope clouds|water|boats|crew|world|ui|night|all [--seconds 12] [--label name] [--baseline csv]
#                   [--tests <filter>|--no-tests] [--force] [--merge <ref> ...]
# --merge gates several PRs as one batch: a local branch gate-<n> from origin/main with each ref merged in (fetched
# first; a conflict stops the gate), so one build, one test run, one package and one bench cover them all.
# Builds, tests, packages and benches only when their inputs changed since the last pass (hashes in Artifacts/gate/;
# a docs-only change gates in seconds), then benches the scope's views (bench-visual.sh, one launch per view) and checks
# the gates (Medium 60 fps, High 45 fps). Scoped gates run High, where the margin is under 1 fps on the storm view and
# a few fps on the sentinels, plus Medium for the storm view alone (its margin is 7-9 fps; every other Medium view has
# 13 fps or more). `all` is the full sweep (every view, Low Medium High): run it at least daily and before every blind
# round. --baseline compares each view with an earlier bench-visual CSV.
# bash reads a script as it runs it, and --merge checks out another tree: run from a copy.
if [[ -z "${GATE_COPY:-}" ]]; then
	COPY="$(mktemp -t gate).sh"; cp "$0" "$COPY"
	GATE_COPY=1 GATE_SCRIPTS="$(cd "$(dirname "$0")" && pwd)" exec bash "$COPY" "$@"
fi
source "$GATE_SCRIPTS/env.sh"
SCOPE=all; SECONDS_PER_RUN=12; LABEL=""; BASELINE=""; TESTS=SailingSim; FORCE=0; MERGE=()
while [[ $# -gt 0 ]]; do
	case "$1" in
		--scope) SCOPE="$2"; shift 2 ;;
		--seconds) SECONDS_PER_RUN="$2"; shift 2 ;;
		--label) LABEL="$2"; shift 2 ;;
		--baseline) BASELINE="$2"; shift 2 ;;
		--tests) TESTS="$2"; shift 2 ;;
		--no-tests) TESTS=""; shift ;;
		--force) FORCE=1; shift ;;
		--merge) shift; while [[ $# -gt 0 && "$1" != --* ]]; do MERGE+=("$1"); shift; done ;;
		*) echo "Unknown argument $1" >&2; exit 2 ;;
	esac
done
# The tightest High view, helm-eye (about 1 fps over 45 after W2), runs in every scope; the next two, slip (the
# marina with the player's boat) and coast-day (the bay shore), only in the scopes that touch what they show.
TIERS=(High)
case "$SCOPE" in
	clouds|sky) VIEWS="beam8,beat15,storm,gulf-sea,bridge,helm-eye" ;;
	water) VIEWS="beam8,beat15,storm,marina,gulf-sea,bridge,helm-eye,coast-day" ;;
	boats) VIEWS="beam8,beat15,marina,crew,helm-eye,slip" ;;
	crew) VIEWS="beat15,crew,helm-eye,slip" ;;
	world) VIEWS="marina,bridge,coast-night,marina-night,helm-eye,slip,coast-day" ;;
	night) VIEWS="coast-night,marina-night,helm-eye" ;;
	ui) VIEWS="beam8,helm-eye" ;;
	all) VIEWS=""; TIERS=(Low Medium High) ;;
	*) echo "Unknown scope $SCOPE" >&2; exit 2 ;;
esac
# Medium's one tight view: the storm (67-69 fps against 60 in every sweep since bench-fast).
MEDIUM_VIEWS=""; [[ ",$VIEWS," == *",storm,"* ]] && MEDIUM_VIEWS="storm"
LABEL="${LABEL:-gate-$SCOPE}"
STATE="$ARTIFACTS/gate"; mkdir -p "$STATE"
cd "$REPO_ROOT"
if [[ ${#MERGE[@]} -gt 0 ]]; then
	[[ -z "$(git status --porcelain --untracked-files=no)" ]] || { echo "Uncommitted changes: commit or stash before --merge" >&2; exit 1; }
	git fetch -q origin main "${MERGE[@]}"
	BRANCH="gate-$(date +%m%d-%H%M)"
	git checkout -q -B "$BRANCH" origin/main
	for REF in "${MERGE[@]}"; do
		git merge -q --no-edit "origin/$REF" 2>/dev/null || git merge -q --no-edit "$REF" \
			|| { echo "Merging $REF into $BRANCH conflicts: resolve it, commit, then run the gate without --merge" >&2; exit 1; }
	done
	echo "[gate] $BRANCH: origin/main + ${MERGE[*]}"
fi

# inputs_hash (env.sh): what a step reads, by content.
CODE_HASH="$(inputs_hash Source SailingSim.uproject Config Plugins)"
PACKAGE_HASH="$(inputs_hash Source SailingSim.uproject Config Plugins Content)"
# What the packaged game is made of: everything but the tests module (editor only, never packaged), so a change to the
# tests alone neither repackages nor benches.
GAME_HASH="$(inputs_hash Source ':(exclude)Source/SailingSimTests' SailingSim.uproject Config Plugins Content)"
T0=$(date +%s)
step() { echo "[gate $(( $(date +%s) - T0 )) s] $*"; }

if [[ $FORCE == 1 || "$(cat "$STATE/build.hash" 2>/dev/null)" != "$CODE_HASH" ]]; then
	step "build"
	"$GATE_SCRIPTS/build.sh" > /dev/null || { echo "Build failed: Artifacts/build.log" >&2; exit 1; }
	echo "$CODE_HASH" > "$STATE/build.hash"
else
	step "build: nothing changed since the last build"
fi
# The heavy tests (scripts/gate-heavy-tests.txt) read only the physics, the tests and the terrain bake (and the few
# game files the test sources include): when none of those changed since they last passed, the rest run alone.
# The heavy tests live in these five test files: an edit to any other test file leaves them be.
HEAVY_INPUTS=(Source/SailingPhysics Source/SailingSimTests/SailingSimTests.Build.cs Source/SailingSimTests/Private/OceanTests.cpp
	Source/SailingSimTests/Private/FleetTests.cpp Source/SailingSimTests/Private/ReferenceTests.cpp
	Source/SailingSimTests/Private/PhysicsTests.cpp Source/SailingSimTests/Private/TrafficTests.cpp Content/TerrainData Source/SailingSim/Public/LakeData.h
	Source/SailingSim/Private/LakeData.cpp Source/SailingSim/Public/Chart.h Source/SailingSim/Private/Chart.cpp
	Source/SailingSim/Public/Navigation.h Source/SailingSim/Private/Navigation.cpp Source/SailingSim/Public/ReferenceCapture.h
	Source/SailingSim/Private/ReferenceCapture.cpp)
HEAVY_HASH="$(inputs_hash "${HEAVY_INPUTS[@]}")"
run_tests() {
	if ! "$GATE_SCRIPTS/test.sh" "$1" > "$STATE/test.out"; then
		grep -E "^Fail|!" "$STATE/test.out" >&2 || true
		echo "Tests failed: Artifacts/gate/test.out" >&2; exit 1
	fi
	tail -1 "$STATE/test.out"
}
if [[ -n "$TESTS" ]]; then
	# Content is in the tests' inputs too (maps, materials, terrain data).
	if [[ $FORCE == 0 && "$(cat "$STATE/tests.hash" 2>/dev/null)" == "$PACKAGE_HASH $TESTS" ]]; then
		step "tests: passed on these inputs already"
	elif [[ $FORCE == 0 && "$TESTS" == SailingSim && -f "$STATE/tests-all.txt" && "$(cat "$STATE/heavy.hash" 2>/dev/null)" == "$HEAVY_HASH" ]]; then
		LIGHT="$(python3 - "$STATE/tests-all.txt" "$GATE_SCRIPTS/gate-heavy-tests.txt" <<'PY'
import sys
heavy = [l.strip() for l in open(sys.argv[2]) if l.strip() and not l.startswith('#')]
names = [l.strip() for l in open(sys.argv[1]) if l.strip()]
print('+'.join(n for n in names if not any(n.startswith(h) for h in heavy)))
PY
)"
		step "tests: the heavy set passed on these physics inputs; $(echo "$LIGHT" | tr '+' '\n' | wc -l | tr -d ' ') others"
		run_tests "$LIGHT"
		# New tests (not in the last full run's list) are picked up by the next full run.
		echo "$PACKAGE_HASH $TESTS" > "$STATE/tests.hash"
	else
		step "tests ($TESTS)"
		run_tests "$TESTS"
		echo "$PACKAGE_HASH $TESTS" > "$STATE/tests.hash"
		if [[ "$TESTS" == SailingSim ]]; then
			echo "$HEAVY_HASH" > "$STATE/heavy.hash"
			python3 -c "import json,sys; [print(t['fullTestPath']) for t in json.load(open(sys.argv[1], encoding='utf-8-sig'))['tests']]" "$ARTIFACTS/TestReport/index.json" > "$STATE/tests-all.txt"
		fi
	fi
fi
if [[ $FORCE == 1 || ! -d "$REPO_ROOT/Packaged/Mac/SailingSim.app" || "$(cat "$STATE/package.hash" 2>/dev/null)" != "$GAME_HASH" ]]; then
	step "package"
	"$GATE_SCRIPTS/package-mac.sh" Development > /dev/null || { echo "Package failed: Artifacts/package.log" >&2; exit 1; }
	echo "$GAME_HASH" > "$STATE/package.hash"
else
	step "package: the packaged game is already this tree"
fi
# The bench reads only the packaged game: when that is the tree the scope last passed on, the result stands.
BENCH_KEY="$GAME_HASH $SCOPE $SECONDS_PER_RUN"
if [[ $FORCE == 0 && -z "$BASELINE" && "$(cat "$STATE/bench-$SCOPE.hash" 2>/dev/null)" == "$BENCH_KEY" && -f "$STATE/bench-$SCOPE.csv" ]]; then
	step "bench: this scope passed on this packaged game already (--force reruns it)"
	cp "$STATE/bench-$SCOPE.csv" "$ARTIFACTS/visual-bench-$LABEL.csv"
else
	rm -f "$STATE/bench-$SCOPE.hash"
	step "bench ${VIEWS:-every view} on ${TIERS[*]}${MEDIUM_VIEWS:+, $MEDIUM_VIEWS on Medium}"
	ONLY="$VIEWS" "$GATE_SCRIPTS/bench-visual.sh" "$SECONDS_PER_RUN" "$LABEL" "${TIERS[@]}" > /dev/null
	if [[ -n "$MEDIUM_VIEWS" ]]; then
		ONLY="$MEDIUM_VIEWS" "$GATE_SCRIPTS/bench-visual.sh" "$SECONDS_PER_RUN" "$LABEL-medium" Medium > /dev/null
		tail -n +2 "$ARTIFACTS/visual-bench-$LABEL-medium.csv" >> "$ARTIFACTS/visual-bench-$LABEL.csv"
	fi
fi
step "done"
GATE_OK=0
python3 - "$ARTIFACTS/visual-bench-$LABEL.csv" "$BASELINE" <<'PY' && GATE_OK=1
import csv, sys
rows = list(csv.DictReader(open(sys.argv[1])))
base = {}
if sys.argv[2]:
    for r in csv.DictReader(open(sys.argv[2])):
        base[(r['view'], r['quality'])] = r
GATE = {'Medium': 60.0, 'High': 45.0}
fail = 0
print(f"{'view':14} {'tier':7} {'fps':>6} {'p99 ms':>7} {'gpu ms':>7}" + (f" {'base fps':>9} {'delta':>6}" if base else '') + "  gate")
for r in rows:
    try:
        fps = float(r['avg_fps'])
    except ValueError:
        print(f"{r['view']:14} {r['quality']:7}  error"); fail += 1; continue
    gate = GATE.get(r['quality'])
    ok = gate is None or fps >= gate
    fail += not ok
    line = f"{r['view']:14} {r['quality']:7} {fps:6.1f} {r['p99_ms']:>7} {r['gpu_ms']:>7}"
    b = base.get((r['view'], r['quality']))
    if base:
        line += f" {b['avg_fps']:>9} {fps - float(b['avg_fps']):+6.1f}" if b and b['avg_fps'] not in ('', 'error') else f" {'':>9} {'':>6}"
    print(line + ("  ok" if ok else f"  UNDER {gate:.0f}"))
print("gate: " + ("pass" if not fail else f"{fail} view(s) under the gate or lost"))
sys.exit(1 if fail else 0)
PY
if [[ $GATE_OK == 1 ]]; then
	echo "$BENCH_KEY" > "$STATE/bench-$SCOPE.hash"
	cp "$ARTIFACTS/visual-bench-$LABEL.csv" "$STATE/bench-$SCOPE.csv"
	exit 0
fi
exit 1
