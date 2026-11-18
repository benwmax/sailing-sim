# Bluebonnet at #764's bb833f4c, the PackTrim pack (PC)

**Short version:** the hull is now at **8 material slots**, and the commit is **46b5abbc** on `claude/project-thread-yo30mi`.

- **Head:** bb833f4c, which is main 32810779 merged plus the Mac's library rebuild with `MI_Boat_PackTrim`.
- **The commit:** only the 5 `Content/Boats/Bluebonnet` uassets, a plain push on top of bb833f4c.
- **Tests:** JClassMaterials, FleetMesh, RigClearance and BluebonnetMesh all pass.
- **Look:** at 1:1 her varnish, bronze, lenses and laid deck look the same as `deck-f491dab6`.

## Run (kept `pr764` worktree)

- **LFS:** real files: T_MaskGrey 10,381 B, MI_Boat_LaidTeak 9,687 B, and **MI_Boat_PackTrim**, a real asset, not a pointer.
- **Editor build:** MSVC clean.
- **Export and import:** `make-boat-models.ps1 -Parts bluebonnet`, 51 min. The J-Class build was redone, because the merged head's shipkit sources are newer.
  - Numbers unchanged: LOA 39.929, beam 6.556, draft 4.521, canoe 153.446 m^3, hull 507,238 tris, 24 sockets.
  - No slot-cap stop and no SystemExit in the export log.
  - The import has 0 errors; the 7 warnings are the usual editor ones.
- **Tests:**
  - `SailingSim.Visual.JClassMaterials`: 1/1
  - `SailingSim.Visual.FleetMesh`: 1/1
  - `SailingSim.Visual.RigClearance`: pass (only the standing `S_*` sound warnings)
  - `SailingSim.Visual.BluebonnetMesh`: 1/1. It logged no per-part messages.
- **Material slots per part:** counted as the distinct `MI_Boat_*` each imported asset references. Two slots sharing one material would count once.

| Part | Slots | Materials |
| --- | --- | --- |
| SM_Bluebonnet_Hull | **8** | CastBronze, LaidTeak, Manila, PackCanoe, PackCanvas, PackDeck, PackFit, PackTrim |
| SM_Bluebonnet_Mast | 4 | CastBronze, Manila, MastAluminium, PackFit |
| SM_Bluebonnet_Boom | 2 | CastBronze, PackFit |
| SM_Bluebonnet_Rudder | 2 | CastBronze, PackCanoe |
| SM_Bluebonnet_Wheel | 2 | CastBronze, PackTrim |

- **Stills:** uncooked through `run-game.ps1 -Seconds 10 -ResX 1920 -ResY 1080 -NoDemo`, Ultra, Bolivar Roads, with the same framings as `deck-f491dab6`. Bean's Saved was held aside and restored (B57AA3AF).
  - **Common args:** `-SailingBoat=Bluebonnet -SailingWorld=1 -SailingNoHud -SailingQuality=Ultra -SailingNoGpuSlices -ForceRes`.
  - `bluebonnet-helm.png`: `-SailingCamTarget=-10.85,1.1,2.6 -SailingCamDist=7 -SailingCamYaw=60 -SailingCamPitch=-15`. Crop `bluebonnet-helm-deck-1to1.png`, x 1000-1720, y 760-1080.
  - `bluebonnet-deck.png`: `-SailingCamTarget=-8,0,2.4 -SailingCamDist=6 -SailingCamYaw=150 -SailingCamPitch=-35`. Crop `bluebonnet-deck-1to1.png`, x 1080-1480, y 180-620.

## Against deck-f491dab6 at 1:1

- **Varnish:** the doghouse, skylight and wheel box have the same glossy reddish-brown varnish.
- **Bronze:** the winches, bollards, cleats and fairleads are the same cast bronze.
- **Lenses:** the binnacle's compass glass reads the same blue-grey. The lens and gilt parts now in PackTrim draw as before.
- **Laid deck:** the planks with seams, butts and straight grain are unchanged, near and far.
- **Checker:** none. The game logs have no default-material lines or failed loads.
