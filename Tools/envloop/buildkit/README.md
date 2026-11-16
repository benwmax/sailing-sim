# Building parts kit (Track E, parts half)

The shore plan's Track E (Nov 16 2026, plan "Shore, Grass and Buildings", approved by Bean): standard house features as
reusable parts at real size, one shared trim sheet, six house styles, and a test house builder that judges the kit
outside the game. Today `HouseKit.cpp` draws one window and one door design for the whole lake, as flat rectangles with
painted frames; after the Nov 21 slice ships, the integration step swaps those rectangles for these parts on the same
openings, and re-bakes the 553 house tiles from them for the mid band.

The materials half (wall and roof textures, wear, the fake-interior window glass) is its own thread and folder
(`Tools/envloop/buildmat/`). `slots.json` is the contract between the two halves.

Nothing here is loaded by the game yet. Everything runs in Blender's Python (the `bpy` module, `pip install bpy`, or
`blender -b --factory-startup -P <script> -- <args>`), plus numpy and Pillow.

| File | What it does |
| --- | --- |
| `slots.json` | Material slots (Trim, Glass, Wall, Roof), UV rules, vertex colour channels, paint roles, wall and roof finish ids: shared with the materials thread |
| `sizes.json` | Interim size card for every part (US catalogue sizes, IRC stair and guard rules) until Track 0's shared card lands |
| `make_trim_sheet.py` | The shared trim sheet: 2048 x 2048 at 4 px/cm, 15 surface bands and 6 cells, colour, normal and mask maps, all procedural |
| `trim.json` | The sheet's layout (bands and cells in pixels and UV), written by `make_trim_sheet.py` |
| `hk_core.py` | Face marks (`trim`, `cell`, `wall`, `roof`, `pane`) and the finish pass that writes UV0, UV1 and the colour attribute to the contract |
| `hk_parts.py` | The kit: 53 parts (8 windows, 5 doors, 5 garage doors, 3 shutters, gutters and downspouts, 4 roof vents, ridge cap, 3 chimneys, 2 dormers, 4 columns and posts, rails, steps, 2 foundations, 3 lights, 2 AC units, 2 meters, casings, sills, corner boards, fascia) |
| `build_kit.py` | Builds every part, checks it against its size-card row and triangle budget, exports `SM_HouseKit_<Part>.fbx` with sockets and `kit.json`; `--render` makes the catalogue sheet |
| `packs/<region>/` | Region packs: data, not code. `north-texas-lake` holds `pack.json` and `styles/*.json`, six house styles: 1970s brick ranch, 1990s two-storey brick, stone and metal-roof farmhouse, lake cottage, modern, plain commercial. Each picks parts, finishes, roof, porch, palettes by a seed. The tools take `--pack <region>` (default `north-texas-lake`); another region copies the folder and adds parts only where its houses need a shape the kit lacks |
| `test_house.py` | Builds a whole house from a style and a seed and renders the loop's standard views; `--row` renders three seeds side by side (the no-repeat check) |
| `hk_preview.py` | Preview materials and the three lights for the review renders. Wall and roof previews are stand-in patterns at the true course sizes; the real ones are the materials thread's |

## Run

    python3 Tools/envloop/buildkit/make_trim_sheet.py                       # -> Artifacts/buildkit/trim
    python3 Tools/envloop/buildkit/build_kit.py Artifacts/buildkit/kit --render
    python3 Tools/envloop/buildkit/test_house.py ranch1970 1 Artifacts/buildkit/houses --render
    python3 Tools/envloop/buildkit/test_house.py ranch1970 1 Artifacts/buildkit/houses --render --row
    python3 Tools/envloop/buildkit/test_house.py ranch1970 1 Artifacts/buildkit/houses --pack north-texas-lake

`HK_SAMPLES=<n>` sets the Cycles samples (default 48); `HK_ONLY=15m_midday,03m` renders some views only. A house takes
about 3 to 5 minutes for all seven views on four CPU cores.

## Other regions

The kit is parts plus recipes. The parts, the trim sheet and the builder are shared; everything specific to North Texas
(house styles, roof shapes and pitches, wall and roof finishes, palettes) is in `packs/north-texas-lake/`. Wall and roof
finish names are the materials thread's pack list (`Tools/envloop/buildmat/packs/north-texas-lake.json`) on the ids in
`slots.json`; a region's pack puts its own finishes on the same ids. Seeds are stable (crc32 of style and seed), so a
house is the same on every run. The layout moves to Track 0's shared pack format when it lands.

## Rules for parts

- Metres, Z up. An opening's origin is the bottom centre of the opening on the wall plane; the frame's face sits on
  y = 0 and the part runs back into -Y, so the house sets it back by its reveal (brick 100 mm, siding 30 mm).
  Wall-mounted parts mount at their back face, +Y out. Roof parts stand plumb on their base centre.
- Every face is marked before the join: `K.trim(ob, band, paint_role)`, `K.cell(ob, cell)`, `K.wall(ob, finish)`,
  `K.roof(ob, finish)` or `K.pane(ob, seed, obscure, door)`. `K.part` joins, writes UVs and colours and adds sockets.
- Trim faces land on their band of the sheet at true scale (4 px/cm, tiling along U and within the band's 32 cm).
  Bands with a paint mask take the house's colour for the paint role (trim, door, shutter, sash, garage, metal);
  galvanised, black iron, bronze, cedar, concrete, cast stone, rubber, screen and coil guard keep their own colour.
- Glass is one pane per light with UV0 0..1 across it and UV1 the pane's size in metres, for the fake interior.
  Muntins are Trim bars 6 mm in front of the glass.
- Generic shapes only: no maker's logo or a copied product.
- No light copies: the near band (30 to 150 m) uses the full parts and past 150 m houses are the re-baked tiles.

## The environment loop for this track

Card (`sizes.json` row and budget in `hk_parts.register`), reference pack (catalogue sizes now; Bean's lake-house photos
when he takes them, kept in git-ignored `Data/Reference/raw/houses/`), size card, scripted build, standard renders (3 m,
15 m in midday, low sun and overcast, 15 m and 40 m from the lake side, 60 m), six checks (sizes within 5 percent and
budgets: `build_kit.py`; colour against a grey card: waits for photos; no repeat in a 40 m frame: `--row`; variety
counts: 8 windows, 5 doors, 5 garage doors, 6 styles; blind review; budget per house), in-game still at Track 0's
stations (after Nov 21), Bean's look at the styles.

Results and review sheets: `docs/envloop/buildkit/README.md`.
