# PR #812 at 23312223 on the PC (name placement moved)

**Build:**

- Head `23312223`, confirmed with `gh pr view 812`. It contains main `91c8c80d`, so it was used as is.
- Fresh worktree, `git lfs pull`, crew linked. MSVC build: **Succeeded, 0 errors**.
- The worktree was removed afterwards.

**Test:** `SailingSim.Skin`: 9 passed, **1 failed**:

```
SailingSim.Skin.Lettering | Expected 'Bluebonnet: letters a reader can see' to be true.
```

## Stills: all three boats legible

Uncooked Ultra 1080p, the UI thread's args: `-SailingHullName="Bluebonnet" -SailingNoHud -SailingWind=6 -SailingCamPitch=-2`, camera square abeam to starboard (`-SailingCamYaw=90`), aimed with `-SailingCamTarget` (`args.csv`). Bean's Saved was held aside and restored.

| Boat | Camera | Verdict |
|---|---|---|
| Bluebonnet | `"-SailingCamTarget=-10.79,2.94,0.95"`, 10 m | **legible:** white serif "Bluebonnet" on her navy topside aft, well clear of the water (`crop-bluebonnet.png`) |
| Catalina 22 | `"-SailingCamTarget=-2.85,0.94,0.44"`, 4 m | **legible:** dark serif on the white quarter (`crop-catalina22.png`) |
| Corsair 880 | `"-SailingCamTarget=-3.84,0.76,0.58"`, 6 m | **legible:** on the main hull's starboard quarter, seen between the main hull and the float (`crop-corsair880.png`) |
| Corsair 880, wide | `"-SailingCamTarget=-3.0,2.5,0.5"`, 14 m | the starboard float's outer side has **no name** (`abeam-corsair880-wide.png`) |

**Mismatch:** `Skin.Lettering` fails for the Bluebonnet even though her name reads clearly in-game. The test's notion of "letters a reader can see" disagrees with the render.

**Logged positions:** only the last run's game log survived, the Corsair's (`hull-name-log.txt`):

```
Hull name: "Bluebonnet" 604 x 161 px in 628 x 185, read 116180 px, 18317 lit
Hull name "Bluebonnet": 628 x 185 px at aft -416.6, low 48.4, 64.9 x 19.1 cm on SM_Corsair880_Hull
```

The Bluebonnet (expected aft about -1161, low about 71) and C22 (low about 37) lines were in their own runs' logs, which weren't kept. A rerun with per-run log copies would give them.
