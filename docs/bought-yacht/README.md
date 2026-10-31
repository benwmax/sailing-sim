# Bought-model test (pc/bought-yacht)

A one-off test, not a slice item: a purchased, quality sailboat model standing in for one of our classes, so Bean can
judge in a Windows build how a bought model holds up against our script-built ones (and the new Sunfish). The model is
visual only: the class's physics, sails (`FSailCloth`), rig lines and crew are ours, unchanged.

## How it fits in

- **Which class:** the bought hull stands in for the class nearest it in size. For a 30 ft cruiser that's the
  Catalina 30 (9.14 m LOA, 3.35 m beam, a masthead sloop with a wheel). A bigger boat (10-17 m) still goes on the
  Catalina 30, scaled down to its length, unless we add a class for it, which would be a physics change and isn't part
  of this test.
- **The code:** `ASailboatPawn::ModelMeshesFor` (and `ModelAssetPaths`, for the showroom's async load) first looks for
  `/Game/Boats/Bought/<Tag>/SM_<Tag>B_{Hull,Mast,Boom,Rudder}`.
  - When all four load, they stand in for the class's model on the player's boat and on the gallery's display.
  - AI boats, the ghost and berthed neighbours keep our model.
  - With no bought set, which means every checkout but the PC that imported one, nothing changes.
  - `-SailingNoBoughtModel` compares (dev builds; a Shipping build has no switches, so a test build carries the bought
    model whenever it is imported).
- **Physics against looks:** our models' hulls are the physics hull below the waterline (`SailingSim.Visual.FleetMesh`).
  A bought hull isn't, so it rides the class's physics: it can sit a little high or low, and its keel and rudder aren't
  the physics foils. Judging that is part of the test.
  - FleetMesh keeps checking the shipped fleet models only.
  - The new `SailingSim.Visual.BoughtModel` holds a bought set to its class's length (3%) and the rig's sockets, and
    passes with a note when none is imported.
- **The asset gallery:** unknown folders go under Other (`docs/gallery-core`), so `/Game/Boats/Bought/<Tag>` shows there
  with its stats card (triangles, materials, size) beside our own models.

## Import steps

1. **Save the purchase** to `Data/Reference/raw/boats/<name>/` (git-ignored). Unzip any archive into its own new folder.
   Nothing in it is run.
2. **Build our class's model once,** so its spec and sockets exist:
   `scripts\windows\make-boat-models.ps1 -Parts fleet -Fleet Catalina30 -NoImport`. That writes
   `Artifacts\models\catalina30.json` and `Catalina30_sockets.json`.
3. **Look at the file** in headless Blender: a read-only object list, sizes and materials (as done for the Sunfish
   references). Then write a mapping file naming its parts by object-name substrings:
   ```json
   {"Hull": ["hull", "deck", "cockpit", "keel", "stanchion"], "Mast": ["mast", "spreader"], "Boom": ["boom"],
    "Rudder": ["rudder", "wheel"], "drop": ["sail", "rope", "sheet"], "bow": "auto",
    "anchors": {"Boom": "snap"}}
   ```
4. **Fit it:**
   `blender -b --disable-autoexec --factory-startup -P Tools/blender/prep_bought.py -- <source> Catalina30 <mapping.json>`.
   This writes `Artifacts\models\bought\SM_Catalina30B_*.fbx` and `Catalina30B_sockets.json`, with the textures embedded.
   - The hull is turned bow forward and scaled to the class's LOA.
   - Its bow goes to the physics bow, and its keel's lowest point to the class's draft.
   - The sails and ropes are dropped (the game draws its own).
   - Each part keeps its place on the model's hull. The boom's forward end goes to our gooseneck, because the game swings
     it about that point.
   - The class's sockets are copied, so shrouds, stays, sheets and sails meet the model at the physics points.
5. **Import it:** `scripts\windows\run-python.ps1 import_boats.py -ScriptArgs "bought Catalina30"`. It goes to
   `/Game/Boats/Bought/Catalina30`, with Nanite on all but the mast (which bends in our material), keeping its own PBR
   materials and textures.
6. **Check it:** `scripts\windows\test.ps1 -Filter SailingSim.Visual.BoughtModel`, and stills with `run-game.ps1`.
7. **Sail it:** in a dev build, `-SailingBoat=Catalina30` (with `-SailingNoBoughtModel` to compare); in the game, pick the
   Catalina 30 in Free Sail. For Bean's test build, `scripts\windows\friday.ps1` packages it along with the Sunfish.

**Materials:** the first pass keeps the model's own textures, imported with it, which is the quickest honest test.
- If they come out wrong (specular-gloss maps, 3ds Max-only materials), the next step is a small `M_BoughtPBR` in
  `make_materials.py`: base colour, normal, and ORM inputs, our wetness and wear from `MPC_Boat`. Its instances get
  pointed at the model's textures.
- Our `MI_Boat_*` library is the other choice, by slot name, at the cost of the model's own look.

**Dry run, Oct 31:** `prep_bought.py` was run on the TurboSquid Sunfish reference (already on the PC), fitted to our
Sunfish, with `"anchors": {"Boom": "keep"}` because its boom group holds the lateen yard.
- It found the bow by itself, scaled the hull ×0.990 to 4.19 m and dropped 12 sail, rope and foil objects.
- It wrote the four parts: hull 93k triangles, boom 38k, rudder 16k, mast 3k.
- Placed at our origins they sat right: the splash rail, the cockpit, the rudder and tiller on the transom, the spars at
  the mast.
- That model is reference-only, so it wasn't imported into Unreal; the outputs were deleted.

## Licence and git

Bought files never go in git. The repository is public, and every licence below forbids handing out the model's source
files. That includes our `.uasset`s made from them, which anyone could extract from a public repo. So:

- The purchase stays in `Data/Reference/raw` (git-ignored), and its fitted FBX in `Artifacts` (git-ignored).
- `/Game/Boats/Bought/` is git-ignored (`.gitignore`), like the MetaHuman crew. It exists only on the PC that imported
  it, and reaches players only cooked inside the packaged game.
- In git: only our code, the scripts, these docs and the test.

What the licences allow, from what I know (Bean confirms on each page before buying):

| Store and licence | In a game we sell | The model's files in our repo |
| --- | --- | --- |
| CGTrader Royalty Free | yes, built into the product | no |
| TurboSquid Standard | yes, built into a game; the model can't be extractable as a standalone asset | no |
| Fab Standard | yes, in a project or game | no; and Fab files never in git here |
| Superhive (Blender Market) Royalty Free | yes | no |
| Any "Editorial" licence | **no**: news and illustration only | no |

A brand name in the title (Bavaria, Beneteau, Catalina, a class logo) is the model's description, not a licence from the
builder. The class's logos and lettering are never shown: textures carrying them get painted out, and our own insignia
goes on (`M_SailCloth` draws our sails anyway). Check the page's licence tag for any branded listing before buying it;
the "Bavaria Cruiser 37" on the shortlist is one.

Credit goes in `CREDITS.md` and `docs/licences/assets.csv` when a bought model ships, in the form "<model> by <author>,
<store> (<licence>)". The `assets.csv` row marks it git-ignored and cooked only.

## Test plan for Bean

1. Free Sail on the lake in the Catalina 30 (the bought model), then in the Sunfish (our new hero), at High and Ultra.
2. Look at close range: the helm, the cockpit, the deck hardware, the rig at the masthead. Check the waterline in a
   breeze and running.
3. Note how smooth it feels and how long it takes to load. The bench numbers (fps, GPU, triangles) come from me.
4. Verdict: is a bought model worth buying for the other classes, and at what quality and price?
