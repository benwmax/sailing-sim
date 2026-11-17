# #765 at dea6dbb: cannon smoke round 3, on the PC

- **Version tested:** head dea6dbb5, merged locally with main 687f777c (not pushed). MSVC build clean, with 0 errors and 0 warnings in our Source.
- **Smoke material:** `M_CannonSmoke` was rebuilt in the worktree with `CANNON_FX_ONLY=smoke` through `scripts\windows\run-python.ps1 import_cannon_fx.py` (editor exit 0), and not committed.
- **Crew:** linked from the main checkout. Only the link was removed afterwards.
- **Runs:** uncooked through `run-game.ps1 -Seconds 12 -NoDemo`, Ultra, 1440x1080 (the script's default size). Bean's Saved was held aside and restored (profile hash B57AA3AF).
- **Tuning applied:** the flash run logged "Cannon fx: 1 from the command line".

| Still | `-GameArgs` |
| --- | --- |
| `pr765-dea6dbb-cfx3-near.jpg` | `-SailingCannonStage=10,40,0 -SailingBroadside=6,port -SailingCamYaw=90 -SailingCamPitch=-5 -SailingNoHud -SailingQuality=Ultra -SailingNoGpuSlices -SailingShot=cfx3-near` |
| `pr765-dea6dbb-cfx3-far.jpg` | the same with `-SailingCannonStage=10,90,0 -SailingShot=cfx3-far` |
| `pr765-dea6dbb-cfx3-flash.jpg` | `-SailingCannonStage=10,40,0 -SailingBroadside=2,port,ripple "-SailingCannonFx=FlashS=0.3" -SailingNoCameraShake -SailingCamYaw=90 -SailingCamPitch=-5 -SailingNoHud -SailingQuality=Ultra -SailingNoGpuSlices -SailingShot=cfx3-flash` |

The crops are:

- `pr765-dea6dbb-cfx3-near-edge-crop-1to1.jpg`: near, the smoke's foot along the water.
- `pr765-dea6dbb-cfx3-far-edge-crop-1to1.jpg`: far, the bank's foot.
- `pr765-dea6dbb-cfx3-flash-guns-2x.jpg`: flash, the gun line at 2x, shown twice side by side.

## What I saw at 1:1

- **near (40 m): the flat cutoff is gone.**
  - **The foot:** where round 2 had a hard straight line just above the water, the smoke's foot now fades into the water. On the left it thins into low, ragged wisps lying on the water in front of the guns. On the right it's a soft gradient band. There's no single edge line.
  - **Heights:** the puffs sit at visibly different heights: low wisps by the water, a mid veil around the guns, and the big billows above. The upper part still merges into the sky's cumulus.
  - **Lit side:** the lit tops and right-hand faces match the sky clouds' lighting.
  - **Grain:** none, and no banding.
- **far (90 m): the cutoff is much reduced, but still reads as a line at this range.**
  - **The foot:** the bank's foot meets the water along a nearly straight horizontal edge, slightly softened and darker. A 3 m fade at 90 m is only a few pixels, so the bank still looks like it sits on a ruler-straight line.
  - **Top and lighting:** the top is lumpy, and the lit faces match the sun.
  - **Grain:** none, and no banding.
- **flash (ripple from 2 s, flash 0.3 s, no camera shake): no flame caught.**
  - **What it shows:** the ripple's smoke rolls low across the water towards the camera, around the J/22 and past her stern. It's soft and wispy at the water, with puffs at several heights. It reads the most like gun smoke of all the rounds.
  - **The guns:** at 2x, the near guns on the left are clear, the rest fade into the smoke, and none shows an orange or bright flame at its muzzle. The guns firing at that moment may be inside the smoke, or between flashes. Without camera shake the frame is sharp.

**Verdict:** round 3 fixes the near cutoff, and the ripple shot looks the most like real gun smoke so far. At 90 m the foot still reads as a straight line; a wider fade, or a ragged foot, would hide it. No flame has been caught yet. A shot with the camera on the near end of the gun line, or a longer `FlashS`, would help.

No package, bench or other game launch.
