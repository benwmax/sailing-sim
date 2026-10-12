#!/usr/bin/env bash
# Runs the automation tests headless (no window, no GPU) and writes a report.
# Usage: scripts/test.sh [TestFilter]   default filter: SailingSim
#   Report: Artifacts/TestReport/index.json   Log: Artifacts/test.log
source "$(dirname "$0")/env.sh"
FILTER="${1:-SailingSim}"
REPORT_DIR="$ARTIFACTS/TestReport"
rm -rf "$REPORT_DIR"
mkdir -p "$REPORT_DIR"

set +e
"$EDITOR_CMD" "$PROJECT" \
	-ExecCmds="Automation RunTests $FILTER; Quit" \
	-TestExit="Automation Test Queue Empty" \
	-ReportExportPath="$REPORT_DIR" \
	-unattended -nullrhi -nosplash -nosound -NoP4 -stdout -FullStdOutLogOutput \
	> "$ARTIFACTS/test.log" 2>&1
EDITOR_EXIT=$?
set -e

python3 - "$REPORT_DIR/index.json" <<'PY'
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8-sig") as f:
        report = json.load(f)
except FileNotFoundError:
    print("No test report written; see Artifacts/test.log")
    sys.exit(2)
tests = report.get("tests", [])
for t in tests:
    print(f"{t.get('state','?'):8} {t.get('fullTestPath')}")
    for e in t.get("entries", []):
        ev = e.get("event", {})
        if ev.get("type") == "Error":
            print(f"         ! {ev.get('message')}")
# Warnings (for example the editor's own network probe timing out during a long test) do not fail a test.
passed = report.get("succeeded", 0) + report.get("succeededWithWarnings", 0)
failed = report.get("failed", 0)
print(f"\n{passed} passed, {failed} failed, {len(tests)} total")
sys.exit(1 if failed or not tests else 0)
PY
RESULT=$?
if [[ $RESULT -ne 0 || $EDITOR_EXIT -ne 0 ]]; then
	echo "Tests failed (report exit $RESULT, editor exit $EDITOR_EXIT). See Artifacts/test.log" >&2
	exit 1
fi
