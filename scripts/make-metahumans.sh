#!/usr/bin/env bash
# Visual V7: builds the MetaHuman crew into /Game/Crew/MetaHumans (git-ignored) with scripts/make_metahumans.py, in the
# full editor (the texture bake needs a renderer). Needs the MetaHuman optional content for the engine (Epic Games
# Launcher) and an Epic sign-in for the cloud auto-rigging: the first run opens the device-code page in the browser.
# About 6 minutes. Log: Artifacts/metahumans.log. Then scripts/build.sh is not needed; repackage.
source "$(dirname "$0")/env.sh"
APP="$UE_ROOT/Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor"
"$APP" "$PROJECT" -EnablePlugins=MetaHumanCharacter -ExecCmds="py $REPO_ROOT/scripts/make_metahumans.py" -nosplash -NoP4 -stdout \
	-FullStdOutLogOutput > "$ARTIFACTS/metahumans.log" 2>&1
grep "MetaHumans:" "$ARTIFACTS/metahumans.log" | sed 's/.*LogPython: //'
grep -q "MetaHumans: done" "$ARTIFACTS/metahumans.log"
