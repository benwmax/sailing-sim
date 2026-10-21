# Boat texture budget on Medium (Oct 21 2026; corrected after the packaged measurements)

The Mac gate after #195 found the hero J/22's textures at +20 to 31 MB on Medium, over that tier's 24 MB budget. They
were +17 to 29 MB on High, inside its 48 MB budget.

## What holds

**The change.** The hero's baked maps (`/Game/Boats/J22Hero/Textures`) and the boats' close-up detail maps
(`/Game/Boats/Detail`) live in the Vehicle texture groups: `TEXTUREGROUP_VehicleNormalMap` for normal maps,
`TEXTUREGROUP_Vehicle` for the rest. Nothing else uses those groups.

| Piece | Path |
| --- | --- |
| Fresh imports | `scripts/import_j22_hero.py`, `scripts/import_boat_detail.py` set the groups |
| Already-imported textures | `scripts/set_boat_texture_groups.py` sets them without reimporting (34 textures, no pixel changes) |

**The saving.** It comes from the groups' own device-profile settings.

| Mac, packaged chase view, hero + detail (34 textures) | main before #200 | with the Vehicle groups |
| --- | --- | --- |
| Medium | 30.4 MB | **22.4 MB** (budget 24) |
| High | 27.9 MB | **38.8 MB** (budget 48) |

High grew by 10.9 MB. The old World groups held these textures smaller on High than the Vehicle groups do. It is still
inside High's budget, and it's kept: the J/22 is the camera's subject on High.

## What didn't work, and is removed

#200 also gave the two groups a one-mip LOD bias at runtime on Medium and Low (`ApplyBoatTextureBias` in
`ASailingGameMode::ApplyQualitySettings`). In the editor it worked: hero + detail went from 30.9 to 10.9 MB on Medium.
That was the "15.6 MB" this README first reported.

In a cooked build it does nothing:
- The Mac's packaged Medium measured 22.4 MB both with and without it (`-SailingBoatTexBias=0`).
- The PC's packaged Medium measured 30.9 vs 31.3 MB.
- A logged check on the PC's packaged build showed the textures' computed LOD bias still 0 after the group's bias was set
  to 1, so a cooked build doesn't take a device-profile group bias changed at runtime.
- Unregistering and re-registering the textures with the streamer didn't help either. Adding one back as well asserts:
  `UpdateResource` re-registers it already.

So the runtime bias is removed (boat-tex-bias), rather than left in as something that looks like it works.

Two other approaches were rejected:
- A bias in the device-profile ini would apply to every tier: High and Ultra would lose the hero's detail too.
- `r.Streaming.MipBias` would shrink every texture in the game.

The PC's own packaged Medium (Windows device profile) stays at about 31 MB. The PC runs Ultra; Medium and Low are the
Mac's tiers, and there the hero is inside budget.

## Test

`SailingSim.Visual.BoatTextureBudget` checks that every texture in the two folders is in a Vehicle group, with normal
maps in the normal-map group.
