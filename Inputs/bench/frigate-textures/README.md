# Why the frigate's interior reads as flat colour (PC, Nov 24 2026)

**Package:** `Packaged\Windows-pr823-d7188785` (#823's head, with a5670d9b's materials), Ultra 1920x1080. The walker
stands at about 1-2 m from the parts.

## Stills (`contact.png`; the args are in `args.csv`)

| Still | What it shows |
|---|---|
| `tx-guns` (`-SailingWalkAt=Gun,-19,3.2,90`) | a deck beam and carriage overhead about 1-1.5 m away, the hull side, a barrel's breech, a breeching rope |
| `tx-pillar` (`Gun,-19,0,0`) | the pillar 1.5 m ahead, the beams and knees, two rows of guns and carriages |
| `tx-berth-table` (`Berth,-8,1.5,90`) | berth-deck beams and planking, a hammock hook and its clews, a mess table's edge |
| `tx-guns-nodetail`, `tx-pillar-nodetail` | the same two with `-SailingNoBoatDetail` |
| `tx-guns-classic` | the same with `-SailingClassicFrigate` (the decks below still load) |

Every wood part (beams, knees, pillar, carriage sides, berth deck) is **one flat colour per face**, with only
lighting and AO on it. The barrels are smooth black, with no cast-iron skin.

## What the parts are made of

1. **The export carries no textures.** `D:\dev\frigate\out` has no image files, and `Frigate_materials.json` gives each
   of the 48 slots only `base_colour_linear`, `roughness`, a `surface`, sometimes a `kind`, and wear levels.
   - `MI_Frigate_Oak` (beams, knees, pillars): oak, wood surface, colour [0.30, 0.20, 0.11], roughness 0.7.
   - `MI_Frigate_Iron` and `MI_Frigate_Blacking` (barrel): iron, colour about 0.04-0.05.
   - `MI_Frigate_Carriage`: paint, red [0.33, 0.11, 0.055].
   - The below-decks woods (`Ceiling`, `Deal`, `Ash`) have **no kind**, only `surface: below_decks`.
   - The gun deck mesh (`SM_Frigate_GunDeck`) uses 20 slots: Deck, GunDeckPlanks, Oak, Iron, and others.
2. **The MIs set only scalars and a colour.** `import_frigate.py` makes `MI_Frigate_*` over `M_BoatSurface` with
   `Color`, roughness, `Metallic`, `IsHull`, `Surface` and `Grain`. There is no texture parameter, and
   `import_textures` is off. Everything visible has to come from M_BoatSurface's procedural code by `Surface` kind.
3. **Grain is 0 on all her wood.** In the committed materials (a5670d9b, built by 366ffb3d's `import_frigate.py`),
   `BY_SURFACE` has `"wood": (6, 0.0, 0.0)` and `"below_decks": (6, 0.0, 0.0)`, and `BY_NAME` has `"Deck": (6, 0.0, 0.0)`.
   That's the round-2 fix for the wavy bands. In M_BoatSurface the wood's figure is `col = lerp(col, col * ...ring..., Grain)`
   and the roughness the same, so **with Grain 0 the wood's whole figure is off**. Only the decks' planks (GunDeckPlanks,
   BerthDeckPlanks, kind 7) keep Grain 1.
4. **The detail maps are on but carry almost nothing at this scale.** `MPC_Boat.Detail` is 1 on High and Ultra
   (`BoatModelVisuals.cpp`, the player's boat), and the frigate's MIs are M_BoatSurface, so they get it. They're
   box-projected in the boat's frame and fade out between 1.5 and 7.5 m.
   - Detail on against `-SailingNoBoatDetail` differs by 0.69 grey levels on the guns still and 1.45 on the pillar still.
   - At 1:1 (`crops-1to1-detail-vs-nodetail.png`) the only change is a faint fine speckle on the beam's face.
   - They were made for small-boat close-ups (3.4 mm grain on a tiller); on a 25 cm beam at 1.5 m they don't read.
5. **Not the light twins.** Every run logs "Ship outside Commonwealth: 244 parts to load (heroes)" on Ultra. The decks
   below are `Decks/SM_Frigate_<Deck>` heroes from ShipWalkVisuals, and the guns come from the gun table's hero meshes.
   The guns still and the pillar still are on hero meshes.
6. **`-SailingClassicFrigate`** changes only the outside, the stand-in hull and rig. The decks below are the same import,
   so the guns still looks the same, with the open port and sea now visible.

## Conclusion

**Grain set to 0 (the round-2 fix) on top of an export that never had textures.** It's neither textures missing from
the import nor textures unbound in the MIs: there were never any. Nor is it the light or interior tier.

## Likely fix

- **Turn the figure back on with the axis fixed:** the wiring thread's 511434b2 ("wood grain along each timber",
  `export.py paint_grain` writing a Grain colour attribute per timber, M_BoatSurface reading it, Grain 1 again).
  - It **isn't in the branch's current history** (the tip is d7188785).
  - It needs the export regenerated on the PC, the materials re-imported, and M_BoatSurface rebuilt
    (`MATERIALS_ONLY=build_boat_library`).
  - I can do the regeneration and re-import here once it's on the branch: the frigate recipe runs about 2.5 h,
    6 shards at a time.
- **Give the below-decks woods (Ceiling, Deal, Ash) a wood kind** so they get oak/deal treatment, not the default.
- **Scale the figure and detail for a ship.** The wood figure's rings are about 1 cm apart, which only works close up.
  The frigate's timbers are 20-40 cm, so they want broader figure and plank or timber edges, worked by boat size. The
  same goes for iron: a cast skin or pitting on the barrels (kind 5 gives smooth paint).
- **Paint wear:** `Frigate_materials.json` carries wear levels L0-L4 per slot. Passing Age and Care to the MIs (the
  game's Age/Care terms) would add chalk, scrape and tar and break up the flat paint and carriages.

Bean's Saved was held aside and restored (7B5CA7BE).
