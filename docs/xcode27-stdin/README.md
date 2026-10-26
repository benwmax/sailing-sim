# Packaging with Xcode 27 (Oct 26 2026)

After the macOS 27.0.1 / Xcode 27.1 update every `scripts/package-mac.sh` failed in UnrealBuildTool's app finalization
(`ApplePostBuildSync`, exit 65). The log shows only:

    The following build commands failed:
        Run custom shell script 'Touch UBT generated tiles'

The cause is in the build's `.xcactivitylog` (`~/Library/Developer/Xcode/DerivedData/SailingSim_Mac_SailingSim-*/Logs/Build`):

    Failed to launch task /bin/sh: The operation couldn't be completed. Bad file descriptor

Xcode 27 can't launch a scheme pre-action when xcodebuild has no stdin. UBT runs the finalization's xcodebuild that
way (deep inside its action executor), so it failed every time. The same xcodebuild command run by hand, detached
or with an empty pipe on stdin succeeds; with `0<&-` it fails. Running Xcode's first-launch install
(`xcodebuild -runFirstLaunch`, which cleared the "CoreSimulator is out of date" warnings) did not change it.

`scripts/xcode-stdin-shim.sh` (sourced by `package-mac.sh`) works around it without touching the engine. UBT finds
xcodebuild through `xcode-select -p`, which honours `DEVELOPER_DIR`. So the shim points that at a mirror of the
selected Xcode's Developer folder in `Artifacts/xcode-shim`. It is all symlinks, except `usr/bin/xcodebuild`, which
runs the real xcodebuild with stdin from `/dev/null`. Every other tool is the real one through its link, and the real
Xcode is never written to. The mirror is rebuilt when the selected Xcode or its build changes (`stamp`). The gate's main
baseline (`Artifacts/main-tree`, `SAILING_ROOT`) runs the same `package-mac.sh` and gets its own mirror. Only Xcode 27
uses it, so it drops away with the next major; `SAILING_NO_XCODE_SHIM=1` turns it off, to check whether an update
fixed it.
