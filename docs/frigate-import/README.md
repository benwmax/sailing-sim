# Frigate Commonwealth: the import

The model export (`Tools/shipkit/frigate/export.py`, [docs/shipkit-17](../shipkit-17/README.md); regenerated on the PC
from main, 484 FBX, 252 MB, `Inputs/bench/frigate-regen/`) goes into the game with `scripts/import_frigate.py`.

## What it does

- Every mesh in `Frigate_sockets.json`'s `meshes` at its `asset` path: `/Game/Boats/Frigate/Outside/SM_Frigate_<Part>`
  (246: hull, decks, fittings, spars, rigging, sails in each set, boats), `Decks/` (20: the merged gun, berth, orlop and
  hold decks, the tiller's parts, the cabin doors, the gun-deck capstan, the berth deck's instanced copies) and `Guns/`
  (218: the battery's shared and per-gun meshes). Nanite on all of them; the parts over 100k triangles (the decks, the
  skin, the figurehead) take a 6% Nanite fallback as the maxi's hull does.
- Each light twin (slice 16, `docs/shipkit-16`) beside its hero as `SM_Frigate_<Part>_Light` (475 of them; the lower
  three decks and the berth deck's copies have none). The game picks the hero or the twin by tier and distance
  (`ShipRigGame::ObjectOfMesh` reads both); a commandlet has no LOD subsystem, so the twin is not LOD 1.
- `MI_Frigate_<Material>` (48) in `/Game/Boats/Frigate/Materials` over `M_BoatSurface`, from `Frigate_materials.json`:
  the undressed colour and roughness, the Surface kind by the table's `surface`, `kind` and name (`surface_for`: wood 6,
  deck 7, paint 1, blacked iron 5, bright bronze and gilt 16, copper and lead 3, rope 9, sailcloth 10, canvas and
  tarpaulin 11, netting 14, glass 15), `IsHull` on the three hull paints and the copper. The wear levels are left to
  the game's Age/Care. Assigned by slot name; a slot the table lacks fails the import.
- `Frigate_sockets.json` and `Frigate_materials.json` copied to `Content/TerrainData/Ships/Commonwealth.sockets.json` and
  `Commonwealth.materials.json` (staged loose with the walk map) for the game's lanterns (`lights`) and placed copies.
- No mesh sockets: every frame the game moves is in the physics tables (`CommonwealthRigData.inl`,
  `CommonwealthFramesData.inl`, `FrigateGunData.inl`), generated from the same json.

## Running it

PC: `scripts\windows\run-python.ps1 import_frigate.py -ScriptArgs "D:\dev\frigate\out"` after `make_materials.py`
(M_BoatSurface). Args `only=Hull,Wheel` (parts by prefix), `materials` (instances only), `nolight`. The script ends by
returning. Then commit `Content/Boats/Frigate/**` (LFS) and the two json files; the PR needs Bean's label (Content).

## What the game does with it

- `ASailboatPawn::BindShipRig` / `BindShipFrames` (docs/ship-rig, docs/ship-frames) load the yards, sails, tiller, ropes,
  wheel and doors from `Outside/` and `Decks/` by name and move them.
- `ShipWalkVisuals` streams `Decks/SM_Frigate_<GunDeck|BerthDeck|Orlop|Hold>` by the walk map's deck under the walker.
- `ACannonBattery` places the `Guns/` meshes from the gun table.
- The outside model itself (the hull and everything static in `Outside/`, by her state: underway, action, clewed,
  anchored) is drawn by the wiring thread's next PR; until it lands she is drawn from her config.
