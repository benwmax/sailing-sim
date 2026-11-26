# PR #839 (bow wave phase 2) on the PC, Nov 25 2026

**Shas:** the tests ran on **33bc3df**, and the build, package and stills on **fc9a8be**. The head moved mid-run; fc9a8be
adds only the release switch `sailing.BowWave2`.

## Build and tests

- **MSVC build, editor target:**
  - 33bc3df: succeeded, 0 errors, 0 warnings in the project's `Source/` (all 53 are in engine headers).
  - fc9a8be: succeeded, 0 errors, 0 warnings in the project's `Source/`.
- **`SailingSim.Visual` on 33bc3df: 109 tests, 0 failed** (106 clean, 3 with warnings; 15 min).
  - **BowCrest, HullClip, WakeGrid and WakeGridShip all pass** (`test-visual-33bc3df.json`).
- **Development package:** `Windows-pr839-fc9a8be`.

## Ultra stills, new against `-SailingClassicBowWave`

**Setup:** every scene in `docs/bow-wave/bow-scenes.csv` except the two `-classic` rows, with `-SailingQuality=High`
swapped for `Ultra`. A 12 s bench at 1920x1080 with crew off, one still each way (`stills/<scene>-new.webp`,
`stills/<scene>-classic.webp`): 28 stills.

**How they were shot:** by my own runner, not `capture-scenes-win.ps1`. That script's `bench-win.ps1` ends every
`SailingSim*` process by name; my runner holds Bean's Saved aside and stops only its own package.

**Side by side, new on the left:** `compare-bow-6kn-quarter-windward.webp`, `compare-bow-6kn-drone.webp`,
`compare-bow-7kn-drone.webp` and `compare-bow-6kn-quarter.webp`.

### What the stills show

- **Most Chase framings don't show the bow on the PC.**
  - With the Chase preset, `-SailingCaptureBearing=-10` ("ahead"), `-30` ("bow quarter, leeward") and `-90` ("abeam")
    shoot her from astern or the stern quarter.
  - `-150` ("stern quarter") shows the stern quarter too.
  - Only **`+30` (`bow-6kn-quarter-windward`)** and the **Drone** views have the bow and its wave in frame.
  - The bearing convention in the CSV doesn't match the capture camera here. Worth a check against the Mac's stills: if
    the Mac frames these bows, the difference is in the capture code; if not, the CSV's bearings need flipping.
- **Where the bow shows, new and classic are very close at 1080p.**
  - `+30` at 6 kn: a small white roll at the stem in both. The new one is a touch longer along the side.
  - Drone at 6 and 7 kn: the white trail along her lee side and the wedge look about the same from 60 m up.
  - I can't see a clear win either way at this size.
- **Lighting:** sky and water are identical between the pairs, as expected; only the bow-wave code differs.

**Suggested next step:** re-shoot the 5, 6 and 7 kn bow views from bearings that frame the bow (+10, +30, +90 on this
build), and closer, for example `-SailingCamDist` or the drone lower. Then the curl and side foam would be large enough
to judge. I can do that in the next free slot.
