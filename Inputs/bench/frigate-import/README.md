# Frigate Commonwealth import on the PC, Nov 23 2026

**Branch** `claude/project-thread-xkunbh`:

- `76b24417`: the import script.
- `612aba11`: ShipOutside, the outside model in game.
- **`60e6af5f`**: my Content commit, pushed normally on 612aba11.
- `c6c18b37` and **`5911d01c`**: the wiring thread's two MSVC fixes to `ShipOutsideTests.cpp`.

All checks below are at **5911d01c**, in the worktree `D:\dev\ss-fix-wt\frigate` (kept).

## Import (`scripts\windows\run-python.ps1 import_frigate.py -ScriptArgs "D:\dev\frigate\out"`, 32 min)

- "Built 48 MI_Frigate_* instances in /Game/Boats/Frigate/Materials".
- **"Imported 959 meshes (0 parts skipped by only=)"**.
- Both json files copied to `Content/TerrainData/Ships/Commonwealth.{sockets,materials}.json`.
- **0 slot warnings, 0 Python errors.** "Success - 0 error(s), 2 warning(s)": the Sentry DSN, and an Interchange console
  performance note.
- **Content:** `Content/Boats/Frigate/**` is 1,007 uassets (959 meshes and 48 instances), 279 MB through LFS. The commit
  60e6af5f has those plus the two json files, 1,009 files in all; LFS upload 293 MB. No other asset was re-saved.
- The import's per-material lines are in `import-summary.txt`.

## Build and tests at 5911d01c

| | |
|---|---|
| MSVC build | Succeeded, 0 errors. At 60e6af5f and c6c18b37 it had failed in `ShipOutsideTests.cpp`: a raw string inside `TEXT()`, then a `)"` in the sample JSON. Both are fixed now. |
| SailingSim.ShipWalk | 7/7 |
| SailingSim.ShipRig | 3/3 (Motion, Pose, Table) |
| SailingSim.ShipFrames | 5/5 (Doors, Helm, Pose, Ropes, Table) |
| SailingSim.ShipOutside | 3/3 (Commonwealth, Groups, Table) |
| SailingSim.Visual | 106/106 (3 standing warnings) |
| SailingSim.Smoke | 32/32 (1 standing warning) |
| Dev package `Windows-frigate-5911d01c` | exit 0, 4 min; cook 0 errors, 1 warning. It starts. |

## Stills (Ultra 1920x1080; `args.csv`, the log lines in `*.lines.txt`)

**Settings:** `-SailingBoat=Comm -SailingWorld=Gulf -SailingLaunch=2 -SailingWind=12`.

- **frigate-import-deck** (`-SailingCamDist=60`). The log:
  - `Ship outside Commonwealth: 244 parts to load (heroes)`
  - `Ship outside Commonwealth: 244 parts on the boat, 0 did not load`: **N = 244, M = 0**
  - `Ship rig Commonwealth: 0 parts on the model, 0 to load, 87 not in the project`
  - `Ship frames Commonwealth: 0 parts on the model, 12 to load, 0 not in the project`
  - No "Deck mesh ... did not load".
- **frigate-import-gundeck.** The brief's `-SailingWalkAt=GunDeck,-19,0,0` is refused: "want <deck>,<x>,<y>[,<yaw>] with
  a deck of Commonwealth's map". Her map names the decks Spar, Gun, Berth, Orlop and Hold (`walk.py`).
  Retaken with **`-SailingWalkAt=Gun,-19,0,0`**: "-SailingWalkAt: walking on Gun at (-19.00, 0.00) facing 0". The gun
  deck loads: the battery on its carriages with breechings and tackles, the beams and knees, the pillars.
- **frigate-classic-deck** (`-SailingClassicFrigate`, for comparison): the config stand-in with the full rig, and
  `Ship rig Commonwealth: 0 parts on the model, 87 to load, 0 not in the project`.

## What looks wrong

1. **The rig doesn't bind with the outside model.** With ShipOutside on, the rig binder reports "0 to load, **87 not in
   the project**". With `-SailingClassicFrigate` the same build reports "87 to load". So with the outside model in
   place, the yards and sails aren't found or placed. The deck still shows only two sails, one lying almost flat across
   the deck, and no yards on the masts.
2. **The decks are white.** `MI_Frigate_DeckPlanks`, `GunDeckPlanks`, `BerthDeckPlanks`, `FloorCloth`, `Sailcloth` and
   `SailclothFA` all have the colour [0.8, 0.8, 0.8], which looks like a default rather than a real undressed colour.
   The spar deck from above is a flat white slab, and the gun deck's floor is white.
3. **Wood shows a wavy ripple pattern:** pillars, beams and the deckhead (gun-deck still). `surface 6` (wood) on
   Oak/Deal/Ceiling and others looks like a detail map at the wrong scale, or a UV problem on these meshes.
4. **Material kinds to check:**
   - `GunDeckPlanks` and `BerthDeckPlanks` are surface 6 (wood), while `DeckPlanks` is 7 (deck).
   - `MI_Frigate_Deck` is surface 1 (paint).
   - `Brick`, `Horn` and `CompassCard` are paint (1).
   - Carriages are paint (1): red, which looks right.

The material table and kinds are in `import-summary.txt`. Bean's Saved was held aside and restored (7B5CA7BE).
