# Friday zip DRY RUN: main 75ed143f (not clear-to-share)

**DRY RUN, not clear-to-share.** The zip stays on the PC; nothing was shared.

## The build

I ran `scripts\windows\friday.ps1 -NoCheckout` on a clean detached checkout of main 75ed143f, from a copy
(`scripts\windows-fr`, deleted afterwards) with two lines changed:
- **The self-check** (the running script must equal the commit's own) is off, because the copy differs.
- **The end-of-smoke kill.** `Get-Process SailingSim-Win64-Shipping | Stop-Process -Force` became a stop of only the
  processes running from this build's `Shipping-75ed143f` folder. By name, it would also kill a tester zip Bean is
  playing. **friday.ps1 itself should get the same change.**

Results:
- **Time:** 9 min (build, full-cook Shipping, smokes, zip).
- **Sentry:** DSN staged from `Artifacts\sentry\dsn.txt`, "quoted: yes". `WindowsEngine.ini` was put back, and the tree
  was clean at 75ed143f afterwards. Symbols were skipped (no `auth.token` on the PC). The DSN is not in any file here.
- **friday.ps1's smokes:** Title > Gallery ok (202 thumbnails, exit 0). Ultra Lake bench at 1920x1080, 30 s: 91.1 fps,
  then **89.7 fps** on the reported second run (p99 16.8 ms, GPU 8.4 ms). It held and restored the PC's save itself.
- **Zip:** `Packaged\ReadyAbout-75ed143f-Win64.zip`, 4,446,454,749 bytes, SHA-256
  `7946CC41B41A37F2E8FDE3424EFD8C57D932F7C8028519A6D1B4D2339F2FDAC4`. That is **+232,867,431 bytes (+5.5%)** over the
  last clear-to-share zip, ReadyAbout-5e8233ef-Win64.zip (4,213,587,318).

Paks against Shipping-5e8233ef:

| file | 5e8233ef | 75ed143f |
|---|---|---|
| .ucas | 3,836,657,584 | 4,065,603,984 (+229 MB) |
| .utoc | 2,998,503 | 3,112,425 (+114 KB) |
| .pak | 123,548,511 | 126,555,159 (+3 MB) |

**Tests and licence.** friday.ps1 runs neither. The licence check passed on 75ed143f in my earlier runs, and the last
full suite on main (6f44708f) was 344/0/30.

## The smoke on the Shipping build (4K Ultra, fullscreen)

Bean's Saved was held aside and restored around these runs (F6458EAB).

**A Shipping build takes only six dev switches.** With `-SailingShippingSmoke` it reads `-SailingUIScript`,
`-SailingWorld`, `-SailingLaunch`, `-SailingShot`, `-SailingBench` and `-SailingSlice` (`BenchRunner.cpp`,
`ShippingSmokeArgs`). The storm's weather, wind, hour and camera args are dropped, so **a storm view cannot be set from
the command line on Shipping.** It would need a UI script through the Conditions screen.

My first attempt left out `-SailingShippingSmoke`. Those launches ignored every arg and sat at the menu; I stopped them
by PID and reran.

With the switch, the runs were the default lake afternoon (Afternoon breeze), Ultra, 3840x2160:

| run | fps | p99 ms | GPU ms |
|---|---|---|---|
| warm | 55.0 | 20.7 | 17.5 |
| 30 s | **56.1** | 20.3 | 17.2 |
| 20 s reach | 55.3 | 21.0 | 17.4 |

- In every log: no ensures, no default material, **no SkipPackage at all**, and no crash folders.
- **The sample pack loads in Shipping.** Every log has `Sound: sample pack, 17 loops and 23 one-shots` (at +3.0 s).
  Together with no SkipPackage for M_BowWave or Audio/Pack, that confirms #704's cook fix in the Shipping zip.

## The bow-wave curl

- **Shipping can't frame it.** The Shipping reach still (`shipping-reach-chase.png`) is the default chase camera from
  astern, broad reach at 5.8 kn.
- **Development package.** I took a low abeam still on `Windows-7bacf98e-704`, #704 on 6f44708f, which has the same cook
  fix (`dev704-bow-low-abeam.png`). After 20 s the boat had only 3.3 kn, so the bow throws no real wave and **the curl is
  not visible**.
- **What is established:** M_BowWave is in the package and loads, with no SkipPackage.
- **Not established:** that the curl draws. That needs a run held at speed (a reach of a minute or more in 18-20 kn) on
  the Development build.
