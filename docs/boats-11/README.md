# Boats 11: boat detail pass (rope, J/22 cabin, wear, fleet fittings)

Bean asked (Oct 15 2026) whether the boats could get much more detail from the reference photos: accurate textures,
wear and tear, sheets that look like rope, cabin interiors. This is the J/22 pass, built entirely by script in the
cloud from his lesson photos of TX 7295 EC. Nothing here has been run in Unreal yet.

## What was done

- **Rope that looks like rope.** `Tools/rope/make_rope_textures.py` draws a 2/2 twill double-braid cover (24 and 16
  carriers) and 1x19 wire, tileable over one lay length by one circumference: normal, height and a mask texture
  (R cavity, G fleck tracer, B spiral tracer, A mix). `colourways.json` and `T_RopeColourways` (16x4 LUT: base colour,
  tracer colour, pattern) hold eleven colourways, among them TX 7295 EC's red and green jib sheets with white flecks.
  Output: `Inputs/rope/` (`rope_swatches.png` shows them all).
  - In the hero stills every line is a mesh whose U is true arc length over 5 diameters (11 for wire), so the weave
    keeps its size round coils and knots (`Inputs/j22-hero/j22_rope.py`).
  - In the game the live lines (`FRigLine`, `BoatModelVisuals.cpp`) now carry UV0 with the same rule, a vertex colour
    whose red is the line's look (`RopeLook`: mainsheet, jib port, jib starboard, vang, plain) and tangents. Tubes
    went from 6 to 8 sides. `M_RigRope` and `M_RigWire` (`scripts/import_boat_detail.py`) draw them; the pawn picks
    them up at BeginPlay when they exist. `-SailingFlatRope` keeps the old flat materials.
- **Cabin interior** (`Inputs/j22-hero/j22_interior.py`, new game part `SM_J22H_Interior` plus `SM_J22H_Glass`).
  The trunk and deck are hollowed and the companionway opened, so the cabin shows from the cockpit. Inside: cream
  liner with dirt, water tracks under the chainplates and mildew; sole with a lift-out hatch over the keel sump,
  keel bolts with backing plates and a little bilge water; settee benches, V-berth with cushions, chainplate knees,
  compression post, companionway step, aft bulkhead with locker cut-outs; dark smoked portlights. TX 7295 EC carries
  the school's gear: sail bag, two spare vests, paddle, bucket, extinguisher and a Danforth with its rode
  (`interior` keys in `j22_style.py`; other styles get gear by seed).
- **Wear from the photos.** Rain streaks on the topsides now cluster and run hardest under the chainplates, jib
  tracks, stern cleats and scuppers, with a grey wash under the hull-deck joint (IMG_9224). TX 7295 EC's non-skid
  is grey-beige rather than tan. Halyard tails and cam cleats sit on the cabin top beside the hatch (in the proof of
  concept they were buried inside the trunk).
- **Close-up detail layer.** `Tools/boats/make_detail_textures.py` makes tileable true-scale normals and masks for
  moulded non-skid (2.5 mm pyramids), gelcoat orange peel and buffing scratches, weathered teak (eroded early wood,
  checks) and canvas (`Inputs/boat-detail/`). The bake now writes `T_J22H_<group>_X` (R non-skid, G teak, B gelcoat)
  and each group's metres per UV unit; `M_J22HeroSurface` lays the detail on within 1.5 to 6 m and fades it out.
- **The other seven boats** (`Tools/blender/build_fleet.py`, from class photos; every added part sits inside the hulls'
  plan, so `SailingSim.Visual.FleetMesh` is unchanged):
  - Sunfish and ILCA (`dinghy_detail`): the board standing in its trunk with a grip, bailer and drain in the well,
    traveler and ratchet blocks, bow handle, transom drain plug; the ILCA's control lines to three cam cleats a side and
    the hiking-strap shock cord; the Sunfish's V splash guard, halyard and horn cleat.
  - Catalina 22 and 30 (`keelboat_cockpit_detail`, also the Corsair): seat locker lids with hinge and hasp, cockpit
    drains, jib-sheet horn cleats, slide-hatch rails, anchor locker and bow roller, bicolour and stern lights, stanchion
    bases on every lifeline post; the C30's binnacle compass and stern ladder.
  - Hobie 16 (`hobie_detail`): trampoline lacing to both beams, dolphin striker and its wire, mast ball, traveler car
    and stops, jib cars on tracks, shroud adjusters, inspection ports, transom gudgeons and drain plugs.
  - Corsair 880 (`corsair_detail` plus the keelboat deck set): toe rail, halyards to clutches, aka fold hinges and float
    sockets, net lacing along hull and floats, float hatches and bow eyes.
  - Lagoon 42 (`lagoon_detail`): long hull windows, saloon mullions, the helm station (pod, wheel, instruments, seat),
    cockpit table, bimini solar panels, flush hatches, cleats, windlass and bow roller.
  Rebuild with `scripts/make-boat-models.sh` (or `build_fleet.py` alone, then `import_boats.py fleet`).

## To run (Mac or PC, in order)

1. Build the editor (C++ changed: `BoatModelVisuals.cpp`, `SailboatPawn.cpp/.h`).
2. `scripts/import_boat_detail.py` (rope, wire and detail textures, `M_RigRope`, `M_RigWire`).
3. `scripts/import_j22_hero.py` (hero parts, now with `Interior` and `Glass`, the detail masks and `M_J22HeroGlass`).
4. Look: `-SailingJ22Hero -SailingCockpit` at the slip, and a close sheet with `-SailingCamTarget`. Compare with
   `-SailingFlatRope`.
5. `scripts/make-boat-models.sh` for the fleet fittings (Blender), then look at each class with `-SailingBoat=<name>`.
6. Gate: `scripts/gate.sh --scope boats` (Medium 60, High 45). Expected costs: 8-sided rope tubes with a UV seam (about 50% more
   rope vertices), one extra texture fetch per rope pixel, the interior (Nanite, mostly hidden) and the glass
   (translucent, three small panes).

## Not done / next

- Untested in Unreal: the HLSL in `import_boat_detail.py` and `import_j22_hero.py` is syntax-checked only.
- The interior layout follows typical J/22 cabins, not a measurement of TX 7295 EC; a phone video of its cabin would
  settle berth heights, the sole and locker openings.
- Fleet interiors (Catalina 30, Corsair, Lagoon) and photo-matched wear for the other boats are not done; their live
  rope already gets the braid (FRigLine is shared). `build_berthed.py` (marina dress) is unchanged.

## Licences

All textures are generated by our own scripts (rows in `docs/licences/assets.csv` for `Content/Boats/Rope/*` and
`Content/Boats/Detail/*`). No photos are used as textures; the lesson photos were only looked at and stay out of the
repo.
