# Bluebonnet deck at #764's 1d28db92 (PC)

**Short version:**

- The re-export with the laid deck's v written as 1 - v is imported and committed as **48028ddc** on `claude/project-thread-yo30mi`. That is a fast-forward on 1d28db92, with only the 5 `Content/Boats/Bluebonnet` uassets.
- **The planks now draw near the camera:** narrow boards with dark seams and staggered butts. There were none at 63c2b4cc.
- **Further off, the deck still reads as the old fine woven texture.**
- **`SailingSim.Visual.JClassMaterials` fails** on the read-back: min YM **-0.354**.

## Run

- **Worktree:** the kept `pr764` worktree at **1d28db92**, with the crew linked.
- **LFS:** `T_MaskGrey` and `MI_Boat_LaidTeak` are real files.
- **Editor build:** MSVC clean. The C4456 at ec92c9ec is gone.
- **Export:** `make-boat-models.ps1 -Parts bluebonnet`.
  - `build_jclass.py`'s inputs are unchanged, so `jclass.blend` was reused.
  - `export_game.py` ran fresh: `SM_Bluebonnet_Hull.fbx` was rewritten at 10:35, 18,151,964 B.
  - Numbers unchanged: LOA 39.929, beam 6.556, draft 4.521, hull 507,238 tris, 24 sockets.
- **Import:** all five meshes, 0 errors. The 7 warnings are the same as before: the editor's Sentry DSN note, the reference-gathering note, and the importer's 5 "Error opening file" lines while replacing the old assets.
- **Tests:**
  - `SailingSim.Visual.JClassMaterials`: **FAIL**, verbatim: `Expected 'the laid deck's YM is never negative (min -0.354: a negative one is the import's V flip)' to be true.`
  - `SailingSim.Visual.FleetMesh`: 1/1 pass.
  - `SailingSim.Visual.RigClearance`: pass, with only the standing missing `S_*` sound-sample warnings.
- **Stills:** uncooked through `run-game.ps1 -Seconds 10 -ResX 1920 -ResY 1080 -NoDemo`, Ultra 1920x1080, Bolivar Roads. The framings are the same as `deck-a9b6c330`. Bean's Saved was held aside and restored (B57AA3AF).
  - **Common args:** `-SailingBoat=Bluebonnet -SailingWorld=1 -SailingNoHud -SailingQuality=Ultra -SailingNoGpuSlices -ForceRes`
  - `bluebonnet-helm.png`: `-SailingCamTarget=-10.85,1.1,2.6 -SailingCamDist=7 -SailingCamYaw=60 -SailingCamPitch=-15`
  - `bluebonnet-deck.png`: `-SailingCamTarget=-8,0,2.4 -SailingCamDist=6 -SailingCamYaw=150 -SailingCamPitch=-35`
  - **1:1 crops:** `bluebonnet-helm-deck-1to1.png` is x 1000-1720, y 760-1080 of the helm still. `bluebonnet-deck-1to1.png` is x 1080-1480, y 180-620 of the deck still.
- **Game logs:** no default-material lines and no failed asset loads. No grey checker anywhere.

## What I saw at 1:1

- **Helm crop (deck close to the camera, by the skylight hatch):**
  - Laid planks, a few cm wide on screen, run fore and aft.
  - Each has a thin dark seam, with butt joints staggered from plank to plank. They read as a laid deck.
  - Compared with `deck-a9b6c330`, where this was a uniform woven texture, the fix works here.
- **Deck crop (the after deck, from higher up, looking toward the counter):**
  - Still the fine woven or knit texture, with no planks or seams.
  - In the full still, the planks draw only in the nearest few metres: bottom right, and along the starboard side under the boom.
  - Around the wheel box and aft toward the counter, it is the woven texture again.
  - The helm still shows the same: planks in the foreground, woven texture by the doghouse further forward.
- **What I can't tell from these stills:** whether the far deck is the material's distance fade ("far off the seams fade to their share") starting only a few metres out, or the faces with negative YM that JClassMaterials reports. A still from the same spot with the camera moved over the after deck would separate the two.

I made no other changes.
