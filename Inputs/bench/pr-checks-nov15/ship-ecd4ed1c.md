# Shipping candidate of main ecd4ed1c (Friday Nov 20), on the PC

**Not cleared to share.** The zip is kept on the PC only.

## Build

- **Commit:** main **ecd4ed1c** (Merge pull request #766). Built in a fresh worktree at ecd4ed1c; the main checkout stays at 40226d1c, clean.
- **Method:** ecd4ed1c's own `scripts\windows\friday.ps1 -NoCheckout`, with the crew linked from the main checkout (541 files; only the link was removed afterwards).
- **Package:** full-cook Shipping, slice build, 11 min, exit 0, MSVC 0 errors.
- **Output:** the new folder `Packaged/Shipping-ecd4ed1c` and the zip `Packaged/ReadyAbout-ecd4ed1c-Win64.zip`.
- **Zip size:** **4,412,378,380 bytes (4.11 GB)**. It holds TESTER-GUIDE.md and BUILD.md.
- **Sentry:**
  - The key was staged from the PC's own file. It was passed to the script through an environment variable, never written to a file, and never printed or logged; the staged line reads back quoted and https.
  - Release `sailing-sim@ecd4ed1c`, environment `tester`.
  - `Config\Windows\WindowsEngine.ini` was restored, with nothing left under Config or Content.
  - Symbols were skipped, as there is no Sentry auth token on the PC.

## Startup smoke

The smoke used friday.ps1's own steps, with `-SailingShippingSmoke` and no synthetic input.

- **Title > Gallery:** opens, 211 thumbnails rendered, game exit 0. Friday 40226d1c rendered 202.
- **Lake (Ultra, 1920x1080, 30 s):** two runs. Both reached the lake, wrote `bench.json` and quit.
  - **108.1 fps** (second run), p99 13.08 ms, GPU 8.47 ms, game thread 7.14 ms. The first run gave 106.7 fps.
  - Friday 40226d1c's same smoke gave 77.3 fps, p99 20 ms, game thread 11.53 ms.
- **Crashes:** none. The smokes' Saved has no Crashes folder entries and no fatal errors in its logs.
- **Bean's Saved:** held by friday.ps1 and put back, with the profile hash checked before and after (B57AA3AF both). The smokes' own Saved is kept as `Saved.friday-ecd4ed1c`.
- **Not checked:** the gamepad and settings checks are Bean's, by hand, as always.

## One thing to fix before it ships

BUILD.md, in the folder and inside the zip, lists "the last 20 on main (no earlier Friday build on this PC)" instead of what merged since Friday 40226d1c (61 first-parent merges).

- **Why:** friday.ps1 looks for the previous BUILD.md under the worktree's own empty `Packaged`, not the main checkout's.
- **Fix:** if this becomes the tester build, the BUILD.md and zip need regenerating with the 61-merge list. Or friday.ps1 needs a way to take the earlier build from another `Packaged`.
- **For now:** the zip is untouched.
