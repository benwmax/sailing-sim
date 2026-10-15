#!/usr/bin/env bash
# Licence audit (docs/licences): fails when a file under Content/ or Audio/ has no row in docs/licences/assets.csv.
# Every tracked file, every new untracked one and the git-ignored local builds there (MetaHumans, capture) must match a
# row's `path` glob (fnmatch: * also crosses folders). Also fails on a row whose commercial column is "no".
# Usage: scripts/licence-check.sh   (exit 0 = every file covered)
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
{
	git ls-files -- Content Audio
	git ls-files --others --exclude-standard -- Content Audio
	git ls-files --others --ignored --exclude-standard --directory -- Content Audio
} | python3 -c '
import csv, fnmatch, sys
rows = list(csv.DictReader(open("docs/licences/assets.csv", newline="", encoding="utf-8")))
globs = [r["path"] for r in rows if r["path"].startswith(("Content/", "Audio/"))]
bad = [r["path"] for r in rows if r["commercial"].strip().lower() == "no"]
missing = []
for line in sys.stdin:
    p = line.rstrip("\n").rstrip("/")
    if not p:
        continue
    # A directory listed whole (git-ignored) is covered by a row for it or for its files.
    if not any(fnmatch.fnmatch(p, g) or fnmatch.fnmatch(p + "/x", g) for g in globs):
        missing.append(p)
for p in sorted(set(missing))[:50]:
    print("no licence row:", p)
for p in bad:
    print("not for commercial use:", p)
if missing:
    print(f"{len(set(missing))} file(s) under Content/ or Audio/ without a row in docs/licences/assets.csv")
if missing or bad:
    sys.exit(1)
print(f"licence check: every file under Content/ and Audio/ has a row ({len(rows)} rows)")
'
