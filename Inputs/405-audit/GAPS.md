# #405 gap audit: the Sunfish and the club docks up close

Main 4317b6ec, uncooked editor build on Bean's PC (RTX 4090), Ultra, 1920x1080, Nov 11 2026. No code or asset changes.
Stills in `stills/` (JPEG; camera.json beside each), contact sheets `sheet-sunfish.jpg` and `sheet-j22-docks.jpg`.
The standard is the hero J/22 (`j22-*` stills): baked deck and non-skid, kit hardware, live coiled tails, seamed sails.

Ordered by what a new player sees in the first hour: the lessons start and end at the J/22's home slip (LeavetheDock), so
the docks come first; the Sunfish is Club Racer's first boat, later in the career.

| # | What, where | How it looks vs the hero standard | Proposed fix (tool) | Needs Bean? |
|---|---|---|---|---|
| 1 | Gangway plate where dock B meets the shore walkway (`dock-walkway-junction`) | A flat, overbright white slab between two thin rails: no tread, no hinge or transition plate, no edge; it glows in the sun next to weathered planks | A gangway part with a tread pattern and hinge plate in the Metal look, darker and rougher (`MarinaActor` row roots, `M_WorldSurface` pattern; `make_materials.py` WORLD_LIBRARY) | No: free now |
| 2 | Shore at the ramp pier's landward end (`dock-ramp`) | Flat tan sand in large flat-shaded triangles meeting the water with no wet band, beside detailed decking and rails; a few rocks and grass tufts sit on it | Shore detail around the club: the terrain material's sand gets a texture and a wet band at the waterline; more of the club shore dressing (Poly Haven set already in `Content/World/Shore`, `AMarinaActor::BuildShore`) | No: free now |
| 3 | Sunfish deck from above (`sunfish-cockpit`, `sunfish-tiller`) | The deck's wear reads as blocky grey pixel blotches (scum and scuff noise at too coarse a scale for a 4 m boat); the J/22's deck has baked texture, non-skid and fine wear | Give the Sunfish's slots the boat-detail kinds (non-skid deck, smooth gelcoat) and scale `M_BoatSurface` wear by hull length (`build_fleet.py` SPECS slot kinds, `BOAT_SURFACE` in `make_materials.py`) | No: free now |
| 4 | Sunfish sail (`sunfish-clew`, `sunfish-mast-goose`, `sunfish-side`) | Flat colour bands with no seams, tabling, corner patches or insignia; it reads as thin plastic and the light shows through strongly; the J/22's sails carry `Detail` seams, stitching and numbers | `M_SailCloth` `Detail` on for the lateen layout, seam lines along the colour bands, a made-up insignia and the sail number (`Layout`/`Marks` for the Sunfish; less backlit transmission for a dacron sail) | No: free now (photos of a Sunfish sail would help match the band widths) |
| 5 | Sunfish rudder head and tiller (`sunfish-tiller`, `sunfish-tiller-crew`) | The rudder head is a plain black block on the transom: no casting shape, gudgeon/pintle, spring or kick-up pivot; the tiller and its stowed extension are fine | A dinghy rudder-head kit part (cast head, pintles, return spring) placed by the boat kit layout (`Tools/boatkit/layouts/sunfish.json`, `bk_parts`) | Photos of a real Sunfish rudder head (Bean's club) would make it right; a generic one is free now |
| 6 | Sunfish hull side (`sunfish-side`) | White hull with a black rub rail only: no coloured stripe or deck colour, where real Sunfish carry a coloured deck or hull stripe | A Sunfish livery scheme with a deck/hull stripe in the boat catalogue (`Inputs/g3/boat-catalogue.json` -> `Tools/fleet/make_liveries.py`) | No: free now |
| 7 | Dock box and the red box on a pole by the home slip (`dock-bow-end`) | The dock box is a plain white block (no lid seam, hinge or latch); the red box on a post has no readable purpose (fire point? phone?) and no label | A dock-box part with a lid, hinges and a hasp; a labelled fire-extinguisher cabinet or life-ring post instead of the bare red box (`MarinaActor` finger roots / `build_props.py`) | No: free now |
| 8 | Sunfish daggerboard trunk (`sunfish-dagger`) | Not captured: on this reach the sail fills the frame; the cockpit still shows the board's wooden handle in its slot ahead of the well, which looks right | Retake from the windward side (camera yaw -60) before judging | No |

Not gaps, noted for the next pass:
- `sunfish-mast-goose` has lens water drops: the stills ran outside the capture mode (High/Ultra lens water). Retakes should use `-SailingCapture` or turn the lens water off.
- `dock-port` and `dock-starboard` put the camera over the neighbours' decks (the slip is tighter than the offsets assumed); `dock-bow-end` and `dock-stern-end` cover the finger, cleats, lines, fenders and pilings: they hold up to the hero well (planks, capped pilings, cleats with the lines made off, fenders).
- The hero J/22 pairs (`j22-bow`, `j22-cockpit[-crew]`, `j22-tiller`, `j22-side`) are the reference; nothing new there.
