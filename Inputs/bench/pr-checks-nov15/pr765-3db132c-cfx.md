# #765 at 3db132c: cannon smoke tuning set, on the PC

- **Version tested:** head 3db132c0, merged locally with main 687f777c (not pushed), MSVC build clean.
- **Smoke material:** `M_CannonSmoke` was rebuilt in the worktree with `CANNON_FX_ONLY=smoke` through `scripts\windows\run-python.ps1 import_cannon_fx.py` (editor exit 0), and not committed.
- **Crew:** linked from the main checkout. Only the link was removed afterwards.
- **Runs:** uncooked, Ultra, 1440x1080 (`run-game.ps1`'s default size). Bean's Saved was held aside and restored (profile hash B57AA3AF).
- **Timing:** each run was `run-game.ps1 -Seconds 9`, so the shot comes after the 3 s warm-up plus 9 s, the brief's 12 s. As D shows, the sim clock at the shot is not exactly 12 s (see below).
- **Tuning applied:** the game logged "Cannon fx: 5 from the command line" for B and D and "6" for C.

Base: `-SailingCannonStage=10,40,0 -SailingCamYaw=90 -SailingCamPitch=-5 -SailingNoHud -SailingQuality=Ultra -SailingNoGpuSlices`

| Still | Extra args |
| --- | --- |
| `pr765-3db132c-cfx-a.jpg` | `-SailingBroadside=6,port -SailingShot=cfx-a` (defaults) |
| `pr765-3db132c-cfx-b.jpg` | `-SailingBroadside=6,port "-SailingCannonFx=PuffsLong=6,PuffsCarronade=4,PuffsVent=1,SigmaStartM=1.2,SmokeEdgeSoftness=0.1" -SailingShot=cfx-b` |
| `pr765-3db132c-cfx-c.jpg` | B's `-SailingCannonFx` plus `,SmokeExtinction=250`, `-SailingShot=cfx-c` |
| `pr765-3db132c-cfx-flash.jpg` | `-SailingBroadside=11.85,port`, B's `-SailingCannonFx`, `-SailingShot=cfx-flash` |

`pr765-3db132c-cfx-guns-2x-flash-vs-c.jpg` shows the gun line at 2x: D on the left, C on the right.

## What I saw at 1:1

- **A (defaults):** the smoke fills the whole frame, the camera and the J/22 included. It's one even, pale veil from the water up into the sky: no separate puffs, no lumps and no edge anywhere. The guns can't be seen at all. There's no grain or banding, just a flat haze. At 40 m it reads as fog, not gun smoke.
- **B (more puffs, start 1.2 m, edge 0.1):** still one wall, but now it has an edge. The near water and the J/22 are clear, and a dense pale band starts at roughly the gun line, rising from the water to the sky. Its lower edge, along the water, is fairly sharp and even. No lumps or separate puffs read inside it, and the guns are hidden. There's no grain or banding.
- **C (B plus extinction 250):** the same wall shape as B, but the guns now show through it as faint grey shapes. The wall reads slightly thinner or more transparent than B, so the higher extinction doesn't make it look denser here. Still no separate puffs and no grain or banding.
- **D (B, broadside at 11.85 s):** **no muzzle flash and no smoke at all.** The guns had not fired by the shot. Both rows stand clear against the shore: carriages with barrels at different elevations, with no ship around them. So the sim clock at the shot was under 11.85 s, while A to C, firing at 6 s, show smoke. The bench's warm-up ran long while shaders compiled: the log shows the shot about 20 s after the bench started measuring. Catching the flash needs the fire time measured against the shot, for example a few runs at 8, 9, 10 and 11 s.

**Most like gun smoke:** none of the three yet. Each reads as a single wall or fog bank, not as banks of individual puffs drifting off the guns. B is the closest: a defined bank with clear air in front and an edge at the water. A is fog that swallows the camera. C's higher extinction made the bank more see-through rather than denser.

No package, bench or other game launch.
