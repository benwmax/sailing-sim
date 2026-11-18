# Catalina 22 hero import on the PC, branch claude/c22-hero-import at 953dd6bd

**Setup:**

- Fresh worktree at origin/main `c7f1b59c` on a new branch `claude/c22-hero-import`, `git lfs pull`, crew linked, MSVC build: Succeeded, 0 errors.
- `scripts\windows\make-c22-hero.ps1` (no `-NoImport`): Blender build and export, then `import_boats.py c22hero` into `/Game/Boats/C22Hero`. Exit 0 in 5 minutes.
- **Import:** seven assets (`SM_C22Hero_Hull`, `Keel`, `Mast`, `Boom`, `Rudder`, `RudderBlade`, `Interior`), 80 sockets.
- **Blender's line:** `C22Hero: LOA 6.550 beam 2.338 draft 1.552; canoe 1.2382 m^3 at (-0.091, -0.092) (build's hull 1.2197 at (-0.093, -0.087))`.

## SailingSim.Visual.C22HeroMesh: PASS

- 1 passed, 0 failed (`test.txt`, `test-index.json`, `test.log`).
- **The test ran in full:** the report has no entries, so the "isn't imported ... Skipped" warning didn't fire and every check ran: draft 1.552, volume within 2% of 1.220 m³, centre of buoyancy within 2 cm, KeelPin radius, blade foot within 2 cm.

## Commit

The branch has one commit: `953dd6bd Import the Catalina 22 hero model`, adding only `Content/Boats/C22Hero/*.uasset` (7 files, LFS). It was pushed as a new branch (`git push -u origin claude/c22-hero-import`); no PR.

## Stills

Uncooked, Ultra 1920x1080, `-SailingBoat=Catalina`, args in `args.csv`:

- `c22hero-sailing.png`: launch 1 with the demo. The hero heeled on the wind: hull, cabin, lifelines, outboard, rig, sail number 1288.
- `c22hero-slip.png`:
  - **Not at the slip.** Without a launch or start argument the boat starts in open water, so this is a second open-water view from astern (stern ladder, outboard, cockpit, boom).
  - A true slip still needs the marina's start spot (e.g. `-SailingStartAt` at the home slip). Not taken.

Bean's Saved was held aside and restored (profile hash checked).
