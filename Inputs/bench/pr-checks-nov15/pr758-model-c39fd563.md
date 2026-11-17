# #758 J-Class step 3 on the PC: the Bluebonnet imported, commit c39fd563

## The model

- **Build:** `build_jclass.py` ran at 3ac08534 (about 50 min), producing `Artifacts/jclass-build/jclass.blend` (256 MB). The only warnings were the known "collapse ... more than 3 input faces" on `_light_tmp`.
- **Export and import:** the worktree then moved to 67b7636b, keeping that build. `make-boat-models.ps1 -Parts bluebonnet` (no `-RebuildJClass`) exported her and imported `/Game/Boats/Bluebonnet`.
- **How Blender was started:** Blender 4.2.2 through a one-line launcher, `"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe" --python-use-system-env %*`, set as `$env:BLENDER`, with `PYTHONPATH=%APPDATA%\Python\Python311\site-packages`. That user site holds scipy 1.15.3, matplotlib 3.10.9 and Pillow 13.0.0, installed with Bean's OK with numpy held at Blender's own 1.24.3. Without the flag, Blender ignores PYTHONPATH.
- **Commit:** `Content/Boats/Bluebonnet` only (5 LFS objects, 17 MB), committed and plain-pushed to `claude/project-thread-bnso1y` as **c39fd563** on top of 67b7636b. The Mac has since added 59c099e0 (rebuilt `M_WaterV4`) on top.

Export line, verbatim:

```
Bluebonnet: LOA 39.929 beam 6.556 draft 4.521 (physics 39.929, 6.556, 4.521); canoe 153.446 m^3 at (-0.678, -1.030) (physics 153.513 at (-0.678, -1.030)); tris {'SM_Bluebonnet_Hull': 507238, 'SM_Bluebonnet_Mast': 94828, 'SM_Bluebonnet_Boom': 15380, 'SM_Bluebonnet_Rudder': 7246, 'SM_Bluebonnet_Wheel': 3520}; 24 sockets
```

It matches the cloud's Blender 4.2 canary exactly: five parts, 24 sockets, hull 507,238, mast 94,828, boom 15,380, rudder 7,246, wheel 3,520 triangles, canoe 153.446 m^3.

The editor import exited 0 ("0 error(s), 1 warning(s)"); every part is Nanite.

**MSVC build at c39fd563:** Succeeded. 0 errors, 0 warnings in our Source. 67b7636b also built clean; fc04271a had stopped on `BoatModelVisuals.cpp(2185,18): error C4458: declaration of 'HelmSide' hides class member`, fixed in 67b7636b.

## Tests at c39fd563

59c099e0 changes only a material, so the code is the same.

The crew was linked from the main checkout (541 files) for these runs. Only the link was removed afterwards.

| Filter | Passed | Failed | With warnings |
| --- | --- | --- | --- |
| SailingSim.Visual.BluebonnetMesh | 1 | 0 | 0 |
| SailingSim.Physics.BluebonnetUpwind | 1 | 0 | 0 |
| SailingSim.Visual.BluebonnetHelmReach | 1 | 0 | 0 |
| SailingSim.Fleet | 17 | 0 | 7 |
| SailingSim.Physics.Bluebonnet | 3 | 0 | 1 |
| SailingSim.Physics.PolarGate | 1 | 0 | 0 |
| SailingSim.UI.DeepKeelStarts | 1 | 0 | 0 |
| SailingSim.Career | 15 | 0 | 0 |
| SailingSim.Skin | 9 | 0 | 0 |
| SailingSim.Visual.BoatBudget | 1 | 0 | 0 |
| SailingSim.Visual | 98 | 0 | 3 |
| SailingSim.UI | 44 | 0 | 1 |

**Nothing failed.**

The tests the brief named: SailingSim.Fleet.Polar.Bluebonnet Success, SailingSim.Physics.BluebonnetHull Success, SailingSim.Physics.BluebonnetRoll Success, SailingSim.Physics.BluebonnetUpwind Success, SailingSim.Physics.PolarGate Success, SailingSim.UI.DeepKeelStarts Success, SailingSim.Visual.BluebonnetHelmReach Success, SailingSim.Visual.BluebonnetMesh Success, SailingSim.Visual.HullClip Success, SailingSim.Visual.SailShrouds Success, SailingSim.Visual.SheetClearance Success, SailingSim.Visual.SpinnakerClew Success, SailingSim.Visual.SpinnakerHead Success.

The standing warnings are normal: the missing `S_*` sound samples, J22HeroMesh's tolerance notes, `GalvestonBay.detail`, Feedback.Jpeg's deliberate missing.png, and the engine's online-check HTTP timeout.

## Stills at 59c099e0 (`Inputs/bench/jclass-14/`)

Uncooked through `run-game.ps1`, Ultra, 1920x1080, Bolivar Roads. Bean's Saved was held aside and restored (profile hash B57AA3AF).

- `bluebonnet-side.jpg`: `-SailingBoat=Bluebonnet -SailingWorld=1 -SailingCamYaw=90 -SailingCamPitch=-8 -SailingNoHud -SailingQuality=Ultra -SailingNoGpuSlices -ForceRes`
- `bluebonnet-quarter.jpg`: the same with `-SailingCamYaw=135`
- `bluebonnet-helm.jpg`: `-SailingCamTarget=-10.85,1.1,2.6 -SailingCamDist=7 -SailingCamYaw=60 -SailingCamPitch=-15` (the wheel at x -10.85, 1.1 m off the centreline). `bluebonnet-helm-crop-1to1.jpg` is a 1:1 crop of the wheel and cockpit well.

What I saw at 1:1:

- **Side:** her dark blue hull, the deck furniture, mast, genoa and main all draw. The genoa and main overlap as on a close reach, with a bow wave and wake at the waterline. Nothing is missing. At the default chase distance her 48 m rig fills the frame and the hull sits low in it.
- **Quarter:** at the default distance the camera is close enough that the genoa covers most of the hull; only the stern shows under the sails. A longer `-SailingCamDist` would show her better.
- **Helm:** the wheel, its pedestal and binnacle, the cockpit well, winches, cleats, the doghouse with its portlights, the skylight and the running rigging along the deck all draw, with no gaps or floating parts.
- **Deck surface:** at 1:1 it reads as a fine woven or knit pattern, not teak planking. Her deck slot probably doesn't have its final material yet (the Mac rebuilds the boat materials), so I didn't touch it.
- **No crew figures:** none are drawn in any still, the helm included. This is expected: Settings > Show crew is off by default and these runs don't pass `-SailingShowCrew=1`. Her 12 crew figures are covered by the tests.

Nothing from Bean's Saved went into the repo. No package was made.
