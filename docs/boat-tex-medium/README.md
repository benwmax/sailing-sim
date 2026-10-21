# Boat texture budget on Medium (Oct 21 2026)

The Mac gate after #195 found the hero J/22's textures at +20 to 31 MB on Medium, over that tier's 24 MB budget. They
were +17 to 29 MB on High, inside its 48 MB budget.

**Fix.** The hero's baked maps (`/Game/Boats/J22Hero/Textures`) and the boats' close-up detail maps
(`/Game/Boats/Detail`) now live in the Vehicle texture groups: `TEXTUREGROUP_VehicleNormalMap` for normal maps,
`TEXTUREGROUP_Vehicle` for the rest. Nothing else uses those groups.

`ASailingGameMode::ApplyQualitySettings` gives the groups a LOD bias of one mip on Medium and Low and none on High and
Ultra (`ApplyBoatTextureBias`). The bias goes on the active device profile's LOD settings, and only the textures in the
two groups are refreshed, once per change of tier. Dropping the top mip quarters each texture.

| Piece | Path |
| --- | --- |
| Fresh imports | `scripts/import_j22_hero.py`, `scripts/import_boat_detail.py` set the groups |
| Already-imported textures | `scripts/set_boat_texture_groups.py` sets them without reimporting (34 textures, no pixel changes) |
| Measuring | `-SailingBoatTexBias=<n>` overrides the bias |

## Measured (PC, uncooked, J/22 alone at 9 m, resident sizes from `ListTextures`)

| Tier | Hero maps | Detail maps | Hero + detail | With rope and sail marks |
| --- | --- | --- | --- | --- |
| Medium, before | 25.6 MB | 5.3 MB | 30.9 MB | 35.6 MB |
| Medium, after | 9.3 MB | 1.6 MB | **10.9 MB** | 15.6 MB (budget 24) |
| High (unchanged) | 25.6 MB | 5.3 MB | 30.9 MB | 35.6 MB (budget 48) |

Low takes the same bias as Medium. Ultra keeps everything (budget 96).

## Test

`SailingSim.Visual.BoatTextureBudget` checks that every texture in the two folders is in a Vehicle group, with normal
maps in the normal-map group.
