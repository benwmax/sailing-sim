# Bean's play build: main 40226d1c (Win64 Shipping)

**For Bean to play on this PC; not a tester zip to share.** main 40226d1c has #707 (crest spray) and #708 (friday.ps1's
scoped kill).

- **Exe:** `D:\dev\ss-fix\Packaged\Shipping-40226d1c\Windows\SailingSim.exe`
- **Zip:** `D:\dev\ss-fix\Packaged\ReadyAbout-40226d1c-Win64.zip`, 4,446,444,779 bytes, SHA-256
  `37E1A08560B19617BE16027B77E3E24A35C949657F0D6007A4ABC32B40F900A0`
- **How it was built:** the merged `scripts\windows\friday.ps1 -NoCheckout` run as-is on a clean detached checkout, after
  `git lfs pull`. Full-cook Shipping, 9 min. Sentry key staged (quoted). Symbols were skipped (no auth token on the PC).
  No earlier folder or zip was overwritten.
- **Saved:** the script held Bean's Saved aside for its smokes and put it back. Afterwards his real Saved was in place
  (profile F6458EAB) with no `.friday-hold` folder left; the smokes' own copy is `Saved.friday-40226d1c`. My own smokes
  below held and restored it the same way.

## Smokes

| check | result |
|---|---|
| friday.ps1: Title > Gallery | ok, 202 thumbnails, exit 0 |
| friday.ps1: Ultra Lake, 1920x1080 windowed, 30 s | 76.8 then **77.3 fps**, p99 20.0 ms, GPU 8.5 ms |
| Warm-up, Ultra Lake 3840x2160 fullscreen (`-SailingShippingSmoke`) | 55.1 fps |
| **Ultra Lake 3840x2160 fullscreen, 30 s** | **56.0 fps**, p99 20.4 ms, max 26.6 ms, GPU 17.2 ms, game thread 10.0 ms |
| Plain start to the title (UI script Wait x8, Quit) | started cleanly, quit by itself, exit 0 |

Every log: 0 ensures, 0 default material, 0 SkipPackage, 0 crash folders, and
`Sound: sample pack, 17 loops and 23 one-shots`.

The plain start used `-SailingShippingSmoke`, because a Shipping build reads its UI script only with that switch. It ran
no bench; it only waited at the title and quit.

## One thing off

**friday.ps1's 1080p Ultra bench is about 12 fps lower than the 75ed143f dry run's.** It ran 77.3 fps (p99 20.0 ms)
against 89.7 fps (p99 16.8 ms) a few hours earlier, at the same GPU time (8.5 ms). So it is CPU or game-thread time, not
the GPU.

At 4K, where the GPU is the limit, the two builds are the same: 56.0 against 56.1 fps. Between them, main gained #707
(crest spray: game code in `WaterSurface.cpp`) and #708 (script only). Either #707's spray costs game-thread time when
the GPU has headroom, or it is run-to-run noise in the windowed 1080p bench. A traced A/B of the two Shipping packages at
1080p would tell.
