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

- `ShipOutside.h` / `ShipOutsideVisuals.cpp`: `ASailboatPawn::BindShipOutside` reads her table
  (`Content/TerrainData/Ships/Commonwealth.sockets.json`, `ShipOutside::ParseTable`: the `meshes` of group Outside in the
  ship's frame, 244 parts) and loads them under BoatRoot in her frame: the heroes on High and Ultra, the light twins on Low
  and Medium (`-SailingFrigateLight=0|1`). Once they are on her the rig and the frames bind again and find the yards and
  sails among them (neither loads its own copy of a part the outside model owns: `ShipOutsideOwns`). The stand-in hull,
  foils, spars and deck structure are not drawn when `bShipOutsideModel` (her table and `Outside/SM_Frigate_Skin` are in
  the project); `-SailingClassicFrigate` keeps the stand-in for compared stills.
- Her state shows the parts exported per state: the ship's is action while any gun is past loading on its way out or
  back (lid lanyards open), else underway; each rig group's running rigging and blocks (`Running_<Group>_<Set|Clewed|
  Furled>`, `Blocks_*`; `ShipOutside::GroupOf`, `GroupOfSail`) follow its sails: set while any is set, clewed while any
  is, else furled. The sails themselves are the rig's to show (`docs/ship-rig`).
- `BindShipRig` / `BindShipFrames` (docs/ship-rig, docs/ship-frames) move the yards, sails, tiller, ropes, wheel and doors;
  the wheel and the capstan, on their own pivots, are loaded by the frames from `Outside/`.
- `ShipWalkVisuals` streams `Decks/SM_Frigate_<GunDeck|BerthDeck|Orlop|Hold>` by the walk map's deck under the walker.
- `ACannonBattery` places the `Guns/` meshes from the gun table.
- Tests `SailingSim.ShipOutside.Table`, `.Groups` (plain) and `.Commonwealth` (her table once committed: 244 parts, every
  one with its twin, the skin among them, the wheel not).
- After the merge (code only): she is on the Boat screen and in the pause menu's boat row (the `kShipsListed` guard and the
  boat cycle's skip are gone; in Career she stays locked until `career.json` opens her, Free Sail shows her); the rig's
  and frames' bind log is quiet until the outside model has loaded and counts its parts apart ("with the outside model");
  the helmsman stands 1.65 m abaft the wheel's axle (`FWalkMap::HelmAbaftWheelAxle`: the walk bake's 0.7 m put his eye
  inside the after wheel; `walk.py`'s `HELM_BEHIND_WHEEL` should move with the next bake).
- Decks below (code only, after #821): `ShipOutside::ParseDecks` reads the export's `placed` copies owned by the ship in a
  deck's collection (the berth deck's 236 hammock hooks, 112 hammocks, 24 mess benches, 12 tables, 12 kids, 10 sea chests;
  the gun deck's framed parts are left to the frames) and its 29 `lights`; the pawn loads a deck's copy meshes with the
  deck (`DeckCopyPaths`), draws them as one instanced mesh per part (`SetDeckCopies`, off the distance field) and lights
  the deck's lanterns with the export's colour, lumens, reach and shadowing (`SetDeckLamps`), all gone when the deck
  unloads. `SailingSim.ShipOutside.Decks`.
  The deck over the walker's is shown with it (`FShipWalker::DecksOverhead`: a deck mesh carries its own planks and their
  underside, so the berth deck's overhead is the gun deck mesh; the berth deck's own has only the beams and ledges) but
  its lamps stay unlit (unshadowed, they would light down through the planks); its lamps are created when it becomes a
  walker's deck or a ladder's end and dropped after the unload delay, never shown and hidden (the PC's 4K GPU hang). The
  Mac's first berth deck stills (`Inputs/bench/frigate-import/mac-d7188785/`) saw the sky and the gun carriages through
  the bays between the beams.
- Wood grain by timber (Bean, Nov 24: "flat colours, no wood grain on the beams and cannons"): the first import turned
  `Grain` off on her wood (the figure ran along the ship's X on every part: wavy bands across beams and pillars). Now
  `export.py`'s `paint_grain` writes each connected timber's long axis into a `Grain` colour attribute (R 0: present;
  G 0 along the ship, 0.5 athwartships, 1 up; from the piece's bounds in the ship's frame, pieces found by label
  propagation over the mesh's edges), `M_BoatSurface` reads it (`VC` pin: the figure `gw` and the detail maps' U follow
  `gAxis`; a mesh without the attribute keeps the part's X or `GrainUp`), and `import_frigate.py` sets `Grain` 1 on wood
  again. It needs the export regenerated on the PC (REGENERATE.md) and `M_BoatSurface` rebuilt on the Mac
  (`MATERIALS_ONLY=build_boat_library`). The cannons' carriages are painted red (kind 1) by the export's table, as built. The decks (teak, kind 7) with the attribute take a near-straight figure per 10 in plank, as the laid
  deck does: one figure across the seams, foreshortened along the deck, drew a zigzag moire over the whole orlop floor at
  4K (`Inputs/bench/pr823-2fb7bc35/orlop/`). `GrainScale` 3 coarsens her figure for a ship's timbers; `Age` 2 and `Care`
  0.8 wear her paint.
- Not yet: the
  twin by distance rather than tier, and the boat card and boat cycle guards. The decks' planking (seams, butts, plugs,
  the nibbed margin) from the `Planking` and `Margin` UVs the export keeps, as Bluebonnet's laid deck (kind 18), and the
  sails' cloth texture: until then the importer gives those materials flat undressed colours (`COLOUR`), since the export's
  base colour under Blender's pattern is a 0.8 grey. The wood's figure (`Grain`) is off on her timbers: it runs along the
  part's X, and every part of hers sits in the ship's frame.
- The wake grid (`WakeGrid.cpp`) counts at most 2.3 m of a hull's draft as pressure on the surface (Bluebonnet's canoe,
  the deepest it was tuned on) and foams only where the kept surface moves: her 5.9 m pressed a 4 m head that held the
  sea beside her past the height clamp, a flat white sheet wider than her beam. `SailingSim.Visual.WakeGridShip`.
