# Boat fidelity, phase 1: shared boat materials

Phase 1 of the Boat Fidelity Plan (phase 0's gap check and budgets: `docs/boat-fidelity-0`). It adds one material
library that every boat model uses, so the hero models to come (phase 3 onward, from Bean's reference photos) start
with real surfaces. The J/22 shows the change today.

## What changed

**M_BoatSurface / M_BoatMast** (`scripts/make_materials.py`, `BOAT_CODE`)

- **Surface kinds.** A `Surface` parameter tells the material what each slot is made of:
  1. gelcoat
  2. non-skid
  3. 316 stainless
  4. anodised aluminium
  5. painted aluminium
  6. varnished wood
  7. bare wood
  8. rubber or soft PVC
  9. rope
  10. sailcloth
  11. canvas

  0 means no kind: crew, plastics, glass and antifouling get no detail map and no extra weathering. `BOAT_SURFACE` sets the
  kind for each `MI_Boat_*` slot. `import_j22_hero.py`'s `HERO_SURFACE` does the same for the hero's flat slots.
- **New library entries.** `PaintedAluminium`, `Rubber` and `Sailcloth` join the existing entries. Gelcoat already covered
  new to chalky through its oxidation, and now age drives that too. Wood is the varnished kind and Teak the bare kind.
- **Weathering from Age and Care.** The age and care values are the existing E1 seed: per-instance custom data 10 and 11
  on berthed boats, or the `Age` and `Care` parameters on a boat. No new slots. They give `ageK`, from 0 (new) to 1 (worn
  out), which weathers each surface:
  - Gelcoat chalks.
  - Stainless tea-stains in its pits, worse on salt water.
  - Anodising fades to chalky grey.
  - Paint chips to bare metal.
  - Varnish yellows, then fails in patches.
  - Bare teak goes silver.
  - Rubber blooms grey.
  - Rope and cloth go dingy, and a neglected boat's cloth gets mildew specks.

  With `Age` unset (-1, as on the player's and AI boats), the livery's oxidation channel stands in, so those boats look as before.
- **Detail maps.** Tiling detail normals and masks, box-projected in the boat's frame, fading out between 1.5 and 6 m.
  The maps come from `Tools/boats/make_detail_textures.py`, built with numpy. Nothing was downloaded and there are no photos.
  - Existing maps: gelcoat, non-skid, weathered teak, canvas.
  - New maps: brushed metal, varnished wood, rubber, rope braid, sailcloth.
  - U runs along the part; masts set `GrainUp`.
  - `Surface` is a uniform parameter, so each pixel samples one map pair, three times (one per box face).
- **Wet.** Standing water darkens a surface's cavities first: non-skid grooves, teak checks, wood pores. Up-facing is
  now judged on the side the camera sees. The material is two-sided and the J/22's cockpit sole is wound facing down,
  so its deck never got wet or grimy before. The shading normal is unchanged.

**M_J22HeroSurface** (`scripts/import_j22_hero.py`). The J/22's textured groups (hull, deck mould, rudder, teak) get
the same treatment:

- Wear: the pawn's per-boat `Wear`, plus `Age` and `Care`. The baked textures already carry the club boat's wear, so
  the livery stands in at half weight.
- Chalking on the smooth gelcoat, grime in the non-skid where feet go, teak greying.
- The splash line and the deck wetness from `MPC_Boat`, with porosity per surface (gelcoat 0.1, non-skid 0.5, teak 0.6)
  and water standing in the non-skid's grooves.

`HERO_MATERIALS_ONLY=1` rebuilds just these materials. It reimports no meshes or textures.

**Tiers.** `MPC_Boat.Detail` switches the detail maps. The pawn sets it to 1 on High and Ultra, and to 0 on Medium and
Low, which is the cheaper path. Weathering and wetness are a few ALU operations on every tier.

**Measuring args** (development builds only):

| Arg | Effect |
| --- | --- |
| `-SailingNoBoatDetail` | Turns the detail maps off. |
| `-SailingBoatAge=<years>[,<care>]` | Ages the player's hull slots as E1 ages a berthed boat. |
| `-SailingDeckWet=<0..1>` | Starts the deck that wet. It dries over about five minutes. |

## Pipeline (Windows; the Mac's make-content.sh runs the same scripts)

```
python Tools/boats/make_detail_textures.py                 # writes the new maps to Inputs/boat-detail
scripts\windows\run-python.ps1 import_boat_detail.py         # DETAIL_NEW_ONLY=1 skips the rope and the maps already imported
scripts\windows\run-python.ps1 make_materials.py -Only build_boat_library
HERO_MATERIALS_ONLY=1 scripts\windows\run-python.ps1 import_j22_hero.py
```

`make_materials.py` falls back to engine textures, with a warning, when the detail maps aren't imported yet. Run
`build_boat_library` again after `import_boat_detail.py`.

Rerunning `make_detail_textures.py` on the PC's numpy produced slightly different bytes for the four existing maps. I
kept the committed ones; only the five new maps are added.

## Stills (Ultra, uncooked, 1600x900)

`j22-before-after-aged.jpg`: mast base and jib winch.
- Main (the phase 0 stills).
- This branch, as the club boat.
- This branch, aged 16 years with care 0.1.

The aged boat's deck goes chalkier and greyer, with grime in the non-skid. The hardware weathers (stainless, the
anodised track) but stays subtle at this distance.

`j22-dry-wet.jpg`: the cockpit sole and deck, dry and at `-SailingDeckWet=1`. The wet non-skid darkens and greys,
deepest in the grooves.

The J/22's large surfaces are its baked hero textures, so on the current boat the visible change is mostly wear and
wetness. The detail maps mainly reach its flat-material hardware. The library pays off on the hero models of phase 3+.

## Cost (Ultra, packaged Development, RTX 4090, 1920x1080, the J/22 alone, two runs each)

| View | Detail on | Detail off | Render thread | GPU base pass |
| --- | --- | --- | --- | --- |
| Chase (9 m) | 78.2 / 78.2 fps | 79.5 / 71.7 fps | 12.8 vs 12.6–13.9 ms | 2.6–2.8 ms both |
| Close-up (jib winch, 1.3 m) | 64.2 / 64.4 fps | 65.1 / 61.9 fps | 15.5 vs 15.4–16.1 ms | 3.8 vs 4.0 ms |

The difference is inside run-to-run noise. On Ultra the frame is bound by the render thread, and the boat's pixels are a
small share of the GPU's 6–8 ms. Phase 0 measured 76.9 fps on main for the same chase view. Texture memory is unchanged
(3256 MB chase). The Mac gate (Medium 60, High 45) still has to be run on the Mac. Medium samples no detail maps.

## Test

`SailingSim.Visual.BoatLibrary` checks three things:
- Each `MI_Boat_*` slot's kind.
- `MPC_Boat.Detail` exists.
- The hero J/22's textured groups take `Age`, `Care` and `Wear`.
