# Crash and bug reports (Sentry, #410)

Tester builds send crashes to Sentry once the player says yes. This is the first step of #410: the plugin and the
consent switch. The bug capture form (shots from the free camera, what happened, the last minute of boat state) builds on it.

## What is in the repo

- `Plugins/Sentry`: [sentry-unreal](https://github.com/getsentry/sentry-unreal) 1.25.0 for UE 5.8 (MIT, `LICENSE`
  beside it), trimmed to the Mac and Win64: their prebuilt SDKs under `Source/ThirdParty/{Mac,Win64}` (Git LFS). Left
  out: the other platforms, the bundled sentry-cli (the PC has its own), the optional external crash reporter apps and
  the plugin's editor Python (AI toolsets). To update, unzip the release's `-engine5.8` asset and copy the same parts.
- `SailingSim.uproject` enables it on Mac and Win64; `SailingSim.Build.cs` links it there and sets
  `WITH_SAILING_SENTRY`. The game's edge is `SailCrashReports` (`CrashReports.h`): consent, the place tags
  (`world`, `boat`, the save's ids), all no-ops without the plugin or a DSN.
- `Config/DefaultEngine.ini` `[/Script/Sentry.SentrySettings]`: no DSN; consent required and not given by default; no
  PII, screenshots, GPU dumps, tracing, metrics, session replay or symbol upload from the build. The log is attached.

## Where the DSN comes from

Never from the repo. `scripts/windows/friday.ps1` appends `Dsn`, `Release=sailing-sim@<commit>` and
`Environment=tester` to `Config/Windows/WindowsEngine.ini` for the cook and restores the file afterwards, then uploads
the Shipping symbols with sentry-cli (`docs/windows/README.md`, "Crash reports"). Mac builds carry no DSN, so the SDK
stays off there.

## The player's switch

Settings > Gameplay > Privacy > **Send crash reports** (Off by default): `USailingSettings::bSendCrashReports`, saved
as `settings.privacy.sendCrashReports` (`docs/save/README.md`), handed to the SDK at every session start and when it
changes (`ApplyCrashReports`: `GiveUserConsent` / `RevokeUserConsent`).

## Not checked yet

- A crash reaching Sentry from a Windows tester build (needs the PC and the DSN).
- Whether Unreal's own CrashReportClient (packaged in Shipping, `bIncludeCrashReporter`) and Sentry's Crashpad handler
  both want the crash on Windows; Sentry's docs suggest one handler. Check on the PC's first Friday build.
