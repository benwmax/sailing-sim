# #765 at ac672cf: cannon smoke round 2, on the PC

- **Version tested:** head ac672cf4, merged locally with main 687f777c (not pushed). MSVC build clean, with 0 errors and 0 warnings in our Source.
- **Smoke material:** `M_CannonSmoke` was rebuilt in the worktree with `CANNON_FX_ONLY=smoke` through `scripts\windows\run-python.ps1 import_cannon_fx.py` (editor exit 0), and not committed.
- **Crew:** linked from the main checkout. Only the link was removed afterwards.
- **Runs:** uncooked through `run-game.ps1 -Seconds 12 -NoDemo`, Ultra, 1440x1080 (the script's default size). Bean's Saved was held aside and restored (profile hash B57AA3AF).

| Still | `-GameArgs` |
| --- | --- |
| `pr765-ac672cf-cfx2-near.jpg` | `-SailingCannonStage=10,40,0 -SailingBroadside=6,port -SailingCamYaw=90 -SailingCamPitch=-5 -SailingNoHud -SailingQuality=Ultra -SailingNoGpuSlices -SailingShot=cfx2-near` |
| `pr765-ac672cf-cfx2-far.jpg` | the same with `-SailingCannonStage=10,90,0 -SailingShot=cfx2-far` |
| `pr765-ac672cf-cfx2-flash.jpg` | near's plus `-SailingBroadsideEvery=0.4 -SailingShot=cfx2-flash` |

The 1:1 crops are `pr765-ac672cf-cfx2-near-crop-1to1.jpg` (the left half, where the smoke meets the sky) and `pr765-ac672cf-cfx2-far-edge-crop-1to1.jpg` (the bank's lower edge).

## What I saw at 1:1

- **near (40 m):** a big improvement on round 1.
  - **Puffs:** the smoke now has real lumps. On the left and along the top there are large, rounded, billowing puffs with lit tops and darker undersides, and they read as solid volumes.
  - **Middle:** lower down and in the middle it still runs together into one pale veil, with the guns showing through as faint grey shapes.
  - **Bottom edge:** a hard, straight, horizontal line just above the water, running right across the frame. It looks like the smoke is cut off by a flat plane rather than lying on the water.
  - **Merging with the sky:** the smoke's upper left blends into the sky's cumulus, so it's hard to tell where the smoke ends.
  - **Grain:** none, and no banding.
- **far (90 m):**
  - **Shape:** the smoke sits to the right of the gun line as a separate bank, drifting downwind. The guns on the left stand clear. Its top is lumpy and bright, the cumulus look again.
  - **Lit side:** the brightest faces are the tops and the right-hand faces. In this frame the sky's own clouds are lit from the same side, so the smoke's lit side looks consistent with the scene's sun.
  - **Bottom edge:** perfectly straight and sharp at the waterline across the whole bank, the most obvious flaw at this range (see the edge crop).
  - **Grain:** none, and no banding.
- **flash:** no flames caught.
  - **Smoke:** firing every 0.4 s from 6 s onward fills the whole frame with smoke. The J/22 is barely visible as a ghost, and the near water is heavily motion-blurred (probably the camera shake from the firing). Nothing of the guns or their muzzles can be seen through it.
  - **To catch the flames:** a single broadside timed to the shot, or `-SailingBroadsideEvery` with fewer shots (e.g. starting at 10 s), or `-SailingNoCameraShake`.

**Verdict:** round 2's puffs read far more like smoke than round 1's wall. The main thing left is the hard, flat cutoff where the smoke meets the water. The lit side appears to match the scene's sun.

No package, bench or other game launch.
