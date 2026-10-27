# Near-shore audit, phase 1: residential shore

Follow-up to `docs/near-shore-audit/` (items 1 to 4: house kit, shore edge, lot dressing). Everything is procedural in
`HouseKit.cpp` and baked into the existing `SM_Houses_<World>_*` tiles; no new assets.

## What changed

- House kit: gutters and downspouts on full-detail houses; the garage position is kept for the lot.
- Lot dressing on full-detail, non-commercial houses (not on decks or towers): a driveway; a back patio on 85% (60% of them
  covered, with posts, a shed roof and a glass slider; the rest a raised timber deck with rails).
- Lakefront lots (water within 70 m behind the house): side fences on 70% (board or iron, following the ground), a
  concrete path to the water on 60%, and the bank by its slope: a bulkhead with a cap where it is steep, stepped riprap
  where it is moderate, natural otherwise. A boathouse on 35% where no charted dock is within 30 m and the water is 0.7 m
  deep 10 m out (decking, piles, gable roof, a lift with a covered boat).
- No cattails or rushes on mown lawns (`ALakeTerrainActor::PlaceReeds`: 25 m cells around full-detail houses); bank grass
  near houses only at the waterline.
- Lawn variation in `M_Terrain` (`make_materials.py`, `build_terrain`): 2.5 m mowing stripes turned per 40 m block, and dry
  patches, on grass above the bank only.
- All new parts reuse the house's own looks (wall, roof, trim, concrete, metal: wood and iron are wall paint codes), so a
  tile has no more material sections than on main.

## Cost

The first version added five looks to every tile and measured about 4 ms of game thread on Ultra. Folding them into the
existing looks did not change that, because the cost wasn't the geometry: every uncooked run was rebuilding the new tiles'
distance fields and Lumen cards on the worker threads and abandoning them at shutdown (the bake exited before they
reached the DDC). `UWorldKitLibrary::FinishMeshBuilds` now waits for them; `bake_houses.py` calls it, and
`scripts/warm_house_tiles.py` warms existing tiles (8 minutes for Ray Hubbard's 553). Cooked builds always carried them.

Alternating main/branch (house tiles and `M_Terrain` swapped), RTX 4090, 1920x1080, uncooked, two rounds averaged:

| View | Tier | main fps | branch fps | game ms | render ms | GPU ms |
|---|---|---|---|---|---|---|
| Helm eye | Ultra | 57.3 | 59.2 | 15.41 → 15.16 | 7.35 → 7.09 | 7.72 → 7.71 |
| Helm eye | High | 58.5 | 60.6 | 14.77 → 14.10 | 7.21 → 6.93 | 5.55 → 5.49 |
| Residential, raised | Ultra | 73.2 | 72.3 | 10.93 → 11.43 | 5.56 → 5.61 | 6.57 → 6.64 |
| Residential, raised | High | 74.7 | 77.5 | 10.45 → 10.23 | 5.42 → 5.22 | 4.75 → 4.83 |

All within run-to-run noise. Ray Hubbard: 35,165 houses, 4.60 M quads in 553 tiles.

## Stills (Ultra, audit camera spots)

- `residential-noon.jpg`: raised camera, 12:30.
- `residential-eye-noon.jpg`: eye height, 12:30.
- `shore-band-noon.jpg`: the shore band of the raised still at full resolution.
- `houses-15h.jpg`: 15:00, the audit's before against the raised camera.

The marina, bridge and wooded spots are unchanged.

## Not done

- Galveston Bay's house tiles are not rebaked (`HOUSES_WORLDS=GalvestonBay` with `scripts/bake_houses.py`); until then
  they are main's.
- Boathouses are skipped wherever OSM already charts a dock nearby, which includes the audit's residential spot.
