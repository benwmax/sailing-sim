# Opening splash and licences

Plan and decisions: the Claude Doc "Opening splash and licences plan" and the mockup page in the project thread.
Bean approved the plan on Nov 24 2026: keep DLSS in the tester build; show the splash every launch; any click or key
skips it; fade in and out.

## What this page's PR does (code only, no label needed)

- `SSailSplash` (`Source/SailingSim/Private/UI/SailSplash.cpp`): a dark backdrop, then the name and "Sailing" (no water
  animation: Bean found the waves cheap, Nov 24), "Made with Unreal Engine" bottom left, and in a build that contains NVIDIA's DLSS plugin an NVIDIA DLSS
  block bottom right. It fades in over 0.6 s, holds 3 s, fades out over 0.6 s. Any key, click or pad button skips it
  (a 0.25 s fade). It is added by `ASailingHUD::OpenSplash` above the front end, once per process (`SailSplash::Wanted`),
  so the cast-off map reload never shows it again. Off for measuring runs, `-SailingFrontEnd=`, `-SailingUIScript=` and
  `-SailingNoSplash`.
- Still hook: `-SailingFrontEnd=Splash` shows the splash alone, held at full opacity (input is
  ignored, it never finishes), and `SailSplash::Wanted()` lets that one case through although stills run with
  `-SailingBench`. Example: `scripts/run-game.sh 8 -SailingFrontEnd=Splash -SailingShot=splash`; copy the shot to
  `docs/splash/`. Any other `-SailingFrontEnd=` value or `-SailingUIScript=` still skips the splash.
- The Credits screen's first notice is now Epic's wording from the EULA (section 7a) with the current year, and a DLSS
  attribution line follows it in a build with the plugin.
- Tests: `SailingSim.UI.Splash.Timeline`, `SailingSim.UI.Splash.Widget`, and the updated `SailingSim.UI.Credits`.

## Not in this PR (needs Bean's `bean-approved` label, or NVIDIA)

- `CREDITS.md` still has the older line "Made with Unreal Engine. Unreal is a trademark..." under Art and content; it can
  go once the new notice is seen on the Credits screen.
- A Licences page (MIT for Sentry, Apache 2.0 for Crashpad, SIL OFL, CC BY links, ODbL): the texts need staging into the
  pak from `SailingSim.Build.cs`.
- NVIDIA's mark: the splash shows plain words in a box. It loads `/Game/UI/Splash/T_NvidiaDLSS` if that texture exists
  (git-ignored, installed on the PC like the plugin). It goes in only after NVIDIA approves a sample in writing
  (RTX SDKs licence, supplement 7.2c: sample at least 2 weeks ahead, silence for 10 business days counts as no).
- The release notice to NVIDIA before any commercial release: https://developer.nvidia.com/sw-notification
  (company, publisher, SDK, app name, platform, ship date, link).
