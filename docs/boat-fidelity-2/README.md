# Boat fidelity, phase 2: the deck hardware kit

Phase 2 of the Boat Fidelity Plan. It turns the brand-free fittings kit in `Tools/boatkit` (boatkit phase 1, which had
never been imported) into game assets. Each part now has:
- catalogue sizes;
- a Nanite hero and a light version;
- UVs on one shared trim sheet;
- its sockets.

This PR adds only the kit, its import and a test. Fitting it to the J/22 waits for phase 3, which needs Bean's
reference photos. No socket in `J22H_sockets.json`, the crew attach points, `layouts/j22.json` or `dress_boat.py` moved.

## The parts (43)

These cover everything the plan asked for. The six new parts are marked *new*.

| Group | Parts |
| --- | --- |
| Winches | `Winch16`, `Winch70`, `WinchHandle`, `HandlePocket`, `GrinderPedestal` |
| Cleats and clutches | `CamCleat`, `CamRiser`, `HornCleat`, `Clutch` *(new)*, `ClutchBank` |
| Blocks and leads | `Block29`, `Block40`, `Ratchet57`, `FiddleCam`, `Fairlead` |
| Tracks and cars | `JibTrack`, `TrackCar` *(new)*, `Traveler`, `TravellerHeavy`, `GenoaTrackHeavy` |
| Lifelines | `Stanchion` *(new)*, `BowPulpit` *(new)*, `Pushpit` *(new)* |
| Rig | `Chainplate`, `Turnbuckle` *(new)*, `Stemhead`, `MastStep` |
| Fasteners | `ShackleD`, `Padeye` |
| Steering and outboard | `Tiller`, `TillerExtension`, `OutboardBracket`, `Outboard35`, `Gudgeon`, `SteeringWheel` |
| Hatches, trim, hull | `HatchFwd`, `Portlight`, `VentMushroom`, `DeckPlate`, `HandrailTeak`, `BowEye`, `Scupper`, `Fender` |

**Sizes.** `bk_parts.SIZES` records each size by the dimension the catalogues list:
- shackle pin 4–10 mm;
- block sheave 22–75 mm;
- winch size 8–40 (base diameter 102–175 mm);
- cam cleat 38–102 mm;
- stanchion height 457, 610 and 760 mm;
- pulpit and pushpit widths, track lengths, tiller extension lengths;
- wire size for chainplates and rigging screws;
- line size for clutches.

There are two kinds:
- *Scale* sizes are the default build scaled about its mount point. In the game that is a component scale on one mesh.
- *Option* sizes rebuild the part with the builder's own settings. They're used for tubes and tracks, where wall and
  diameter don't scale with length.

`kit.json` carries the table for phase 3.

**Maker's plates.** Blocks, winches and clutches carry an engraved plate from a made-up maker, TERNWAY, with size marks:
29, 40, 57 and "TERNWAY 16". There is no real maker's name or logo anywhere. The lettering is Saira (OFL), as in the UI.

## Trim sheet (`Tools/boatkit/make_trim_sheet.py`, `bk_trim.py`)

One 2048 x 1024 texture pair at 10 px/cm: `Inputs/boat-kit/T_KitTrim_N` (normal) and `_M` (R cavity, G roughness offset,
B paint fill).

- **Bands.** Eight bands of 11.2 cm, each tileable along U and within its own height. Each band is one surface kind from
  phase 1: brushed stainless, anodised aluminium, cast aluminium, knurl, rubber grip, textured plastic, smooth moulding,
  and carbon twill.
- **Plates.** A row of brand-plate cells holds the TERNWAY plates.
- **Projection.** Each face is box-projected in metres onto its slot's band. U runs along the part's long axis, so a
  tube's length runs along the band. A face is shifted within its band period, so neighbours line up.
- **Overrides.** Grips are marked onto the rubber band (winch handle, tiller extension). Badges are fitted whole into their cell.

## In the game (`scripts/import_hardware_kit.py`)

`/Game/Boats/Kit` holds the imported kit:

- `SM_Kit_<Part>`: the hero, Nanite.
- `SM_Kit_<Part>_Light`: about a quarter of the hero's triangles, at least 160, not Nanite. It is for the Mac's Medium and
  Low tiers.
- `M_BoatKit`: one lit, two-sided material over the trim sheet. The slot's colour is darkened in the sheet's cavities,
  paint-filled engravings are white, and the sheet nudges roughness and supplies the normal.
- `MI_Kit_<Slot>`: one instance per slot name, with that slot's colour, roughness and metalness from `BOAT_LIBRARY`.

Sockets come from the FBX's `SOCKET_*` empties. Blender's object names are global, so a part's `SOCKET_Head` used to come
out as `Head.001`; the build now exports every socket under its real name. Blender's +Y is Unreal's -Y, the same as the
J/22 hero.

`M_BoatKit` is built inside the import script, so phase 1's files (#195) stay untouched. Once #195 merges, the kit can
move onto `M_BoatSurface`'s surface kinds (weathering with Age and Care, wet) by giving each `MI_Kit_` a `Surface`.

**Budgets** (phase 0: a non-Nanite boat part within 40k triangles and 8 slots):

| | Triangles |
| --- | --- |
| All 43 heroes | 124,892 |
| All 43 light versions | 31,256 |
| Largest light part (`Winch70`) | 2,306 |
| A J/22 dressed with about 30 parts | about 15k |

Every part has 1 to 4 slots.

## Review sheets (Blender Cycles previews over the same trim sheet)

- `kit-catalogue.jpg`: every hero part, with hero and light triangle counts and its size in mm.
- `kit-sizes.jpg`: each sized part's catalogue sizes side by side, at true relative scale.

## Pipeline

```
scripts\windows\make-boatkit.ps1 -Render -Docs -Import      # PC: trim sheet, kit, review sheets, Unreal import
scripts/make-boatkit.sh --render                              # Mac: trim sheet, kit, review sheets (then import_hardware_kit.py)
```

It builds in about 7 s without renders (Blender 4.2). The import copies `kit.json` to `Inputs/boat-kit/kit.json`, which the
test reads.

## Test

`SailingSim.Visual.HardwareKit` checks every part in `kit.json`:
- the hero is Nanite and the light version is not;
- each light version is within 40k triangles and 8 slots;
- every slot has its `MI_Kit_` instance;
- every socket the kit names is on both meshes, within 1 mm of where the kit put it.
