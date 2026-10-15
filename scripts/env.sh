#!/usr/bin/env bash
# Shared paths for the build scripts. Override UE_ROOT if Unreal lives elsewhere.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT="$REPO_ROOT/SailingSim.uproject"
UE_ROOT="${UE_ROOT:-/Users/Shared/Epic Games/UE_5.8}"
UBT_BUILD="$UE_ROOT/Engine/Build/BatchFiles/Mac/Build.sh"
RUNUAT="$UE_ROOT/Engine/Build/BatchFiles/RunUAT.sh"
EDITOR_CMD="$UE_ROOT/Engine/Binaries/Mac/UnrealEditor-Cmd"
ARTIFACTS="$REPO_ROOT/Artifacts"

if [[ ! -x "$EDITOR_CMD" ]]; then
	echo "Unreal Engine not found at $UE_ROOT (set UE_ROOT)" >&2
	exit 1
fi
mkdir -p "$ARTIFACTS"

# Bench-fast: What a step reads, by content: each file's git blob id (uncommitted and new files hashed the same way), so a commit of
# the same files changes nothing.
inputs_hash() {
	python3 - "$@" <<'PY'
import hashlib, os, subprocess, sys
paths = sys.argv[1:]
git = lambda *a: subprocess.run(['git', *a, '--', *paths], capture_output=True, text=True, check=True).stdout
blobs = {}
for line in git('ls-files', '-s').splitlines():
    meta, path = line.split('\t', 1)
    blobs[path] = meta.split()[1]
changed = [p for p in git('ls-files', '-m', '-o', '--exclude-standard').splitlines() if p]
present = [p for p in changed if os.path.isfile(p)]
if present:
    ids = subprocess.run(['git', 'hash-object', '--stdin-paths'], input='\n'.join(present), capture_output=True, text=True, check=True).stdout.split()
    blobs.update(zip(present, ids))
for p in changed:
    if not os.path.isfile(p): blobs.pop(p, None)
h = hashlib.sha1()
for path in sorted(blobs): h.update(f'{blobs[path]} {path}\n'.encode())
print(h.hexdigest()[:16])
PY
}
