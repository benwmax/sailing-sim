# Track F: docks, boathouses and covered slips (cloud half)

Shore plan of Nov 16 2026 (Claude artifact "Shore, Grass and Buildings Plan"), Track F: six private dock layouts, three
boathouses, covered marina sheds and the boats that sit in them, built by script and checked with the environment loop.
**Nothing here is loaded by the game yet.** Placing them is Track I's integration pull request after the Nov 21 slice
(one world gate on the Mac, booked through the main sim thread).

## What is built

| Mesh | What it is | Triangles |
| --- | --- | --- |
| `SM_ShoreDock_A` | straight pier 4 x 40 ft with an 8 x 24 ft T head, swim ladder, post lights, cleats, fenders | 29k |
| `SM_ShoreDock_B` | L pier, 10 x 12 ft side platform, a drive-on PWC port alongside | 16k |
| `SM_ShoreDock_C` | walk to an open 12 ft slip with fingers and a four-post lift (no roof) | 27k |
| `SM_ShoreDock_D` | fixed landing, aluminium gangway, floating 8 x 20 ft dock on two pilings with sliding hoops, kayak rack | 20k |
| `SM_ShoreDock_E` | sundeck pier: 16 x 16 ft deck with a rail, bench and bollard lights | 15k |
| `SM_ShoreDock_F` | short stub pier with two PWC ports | 18k |
| `SM_Boathouse_A` | one covered slip, ribbed steel gable roof (10 ft eave), knee braces, lift, lights | 21k |
| `SM_Boathouse_B` | two covered slips under one roof, two lifts, dock box, PWC port | 23k |
| `SM_Boathouse_C` | covered slip with a railed sundeck on its roof and a stair | 21k |
| `SM_MarinaShed_Bay`, `_End` | covered-slip shed module on floating docks, tiles every 4.58 m | 11k, 14k |
| `SM_ShorePWCPort` | drive-on PWC port, EZ Port 280 class (156 x 80 in) | 0.9k |
| `SM_ShoreBoat_RunaboutCovered`, `_RunaboutOpen`, `_Pontoon`, `_PWC` | 21 ft bowrider covered and open, 24 ft pontoon, three-seat PWC | 0.6-2.2k |

Every structure is real construction: 5/4x6 deck boards (140 mm, 6 mm gaps) laid one by one on 2x8 framing, 8 5/8 in
steel pipe pilings with caps, channel bents bolted to them, R-panel roofing with ribs every 305 mm on purlins and
rafters, 4x4 rails with pickets, the club kit's cleats, ladder, hoops and dock box dropped in from
`Tools/blender/build_docks.py` (so one better cleat improves every dock).

## How it fits the lake

- **Rockwall takeline rules** (searched; the city site is not reachable from the cloud, so from excerpts): a boathouse
  needs a seawall and a fixed pier, every boat stored under its roof, one boat lift or two PWC lifts inside. Builders say
  enclosed boathouses are not allowed, so all three are open-sided covered slips. Fixed piers stand on metal pilings
  (Heath's lake-edge ordinance).
- A search summary said Dallas bars boat lifts on its take line. That conflicts with Rockwall's own rule and with what the
  earlier residential pass found, so the lifts stay. **Bean's photo trip settles it** (docks from a boat, 10 to 20 wide
  shots).
- Deck tops at 1.0 m over the pool, as `HouseKit.cpp`'s boathouses today. Ray Hubbard runs 0.3 to 1.2 m low in a dry
  autumn, so most decks will stand 1.5 to 2 m over the water; floating dock D rides the level on its hoops.

## Conventions (for Track I)

- Origin on the bank's bulkhead line at the pool (Z 0 = 435.5 ft), +X out over the water, the walk on Y = 0. Place with
  `Water` as +X, exactly where `HouseKit.cpp` builds its boathouse now (`Sp`, `WaterYaw`).
- Sockets (in the build's `docks_manifest.json`): `boat_N`, `pwc_port_N`, `pwc_N`, `kayak_N`, `umbrella_0`, `chairs_0`,
  each a position and yaw in the mesh's frame. Boats on lifts sit at Z 0.62 (cradle raised); boats alongside at -0.3.
  Boats and dressing are separate meshes so a seed picks what stands there (and "a moored boat on some").
- Slots name `MI_World_*` looks. Six are new and need instances at integration: `MetalRoof` (Galvalume, barn red, forest
  green, charcoal, tan per instance), `Galv`, `Canvas`, `Plastic`, `Vinyl`, `Carpet`. `checks.py` lists them.
- Suggested rule: on a seawalled lot with deep water, Boathouse A/B/C at 2:1:1 where HouseKit builds one today, else a
  dock A to F by seed and depth; marina sheds along the commercial marinas' OSM piers. Mid band: baked into the house
  tiles' light copies with the rest of the shore.

## The loop (scripts in `Tools/envloop/`, cards in `Tools/envloop/docks/cards.json`)

```
python3 Tools/envloop/docks/build_shore_docks.py <out>/docks       # FBX + docks_manifest.json (bpy module or Blender)
python3 Tools/envloop/yard/build_yard_props.py <out>/yard          # the dressing (Track H)
python3 Tools/envloop/docks/checks.py <out>/docks/docks_manifest.json Tools/envloop/docks/cards.json \
        <out>/yard/yard_manifest.json Tools/envloop/yard/cards.json
python3 Tools/envloop/docks/render_envloop.py <out>/docks <out>/renders --dress <out>/yard   # 3/15/60 m x midday/low/overcast
python3 Tools/envloop/docks/make_sheet.py <out>/renders <out>/sheet.jpg --shots midday_15m
python3 Tools/envloop/docks/build_before.py <out>/before          # today's pier and boathouse, for blind rounds
```

In the cloud the `bpy` module (`pip install bpy==5.1.2 numpy pillow` in a Python 3.13 venv) runs all of it; the full
round of 480 renders takes about 15 minutes on 4 cores. The renders' looks are flat stand-ins: real materials come with
Track A/E's textures and the Mac.

## Results, round 1 and 2 (Nov 16 2026)

- **Checks:** sizes within 5% of every card, triangles under budget, sockets present, variety 6 docks / 3 boathouses /
  32 props: 0 failures.
- **Blind round 1** (new against today's, three fresh reviewers, pier and boathouse at 15 m in midday and low sun):
  new won **12 of 12**, confidence 4 to 5. Their notes on the new ones: pilings too clean and white, roof posts unbraced,
  lift beams not visibly fixed to their pilings, a boat lying on the dock with no fenders.
- **Round 2** added knee braces, saddle plates and straps on the lift pilings, and fenders on dock A: round 2 beat round 1
  **10 of 12**, the other 2 "same" (both the 3 m boathouse close-up, where the braces are out of frame). Round 2 is kept.
- **Left for later rounds:** waterline stain, rust and fading (materials, Track A/E and integration), wiring and lived-in
  clutter under the roofs, lift motor detail, the SUV-style glasshouse on the boats is simple, colour against grey-card
  photos (waits on Bean's photo trip).

Contact sheets and the blind pairs are in the project files (`envloop-docks-yard/`); images stay out of git because the
cloud can't push Git LFS.
