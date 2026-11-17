# Bluebonnet deck at #764's materials head a9b6c330 (PC)

**Short version:**

- The re-export and reimport **worked** and are committed as **63c2b4cc** on `claude/project-thread-yo30mi`. The commit has only `Content/Boats/Bluebonnet`.
- **No grey checker:** every part draws with its material.
- **But the laid deck's planking doesn't show.** The hull's deck slot is `MI_Boat_LaidTeak`, yet at 1:1 the deck still reads as the fine woven pattern: no 57 mm planks, no black seams, no king plank or covering boards.

## Run

- **Worktree:** the kept `pr764` worktree, checked out at **a9b6c330** (3ed2d4e6 materials + T_MaskGrey), with the crew linked.
- **LFS:** `T_MaskGrey.uasset` (10,381 B) and `MI_Boat_LaidTeak.uasset` (9,687 B) are real files, not pointers.
- **Editor build:** MSVC clean.
- **Export:** `make-boat-models.ps1 -Parts bluebonnet`.
  - Blender reused the J-Class build: no export input changed from 486beefe to a9b6c330 (`Tools`, `scripts` and `Source/SailingPhysics` have no diff).
  - Same numbers as stage A: LOA 39.929, beam 6.556, draft 4.521 (physics the same). Canoe 153.446 m^3 at (-0.678, -1.030), against the physics' 153.513.
  - Tris: Hull 507,238, Mast 94,828, Boom 15,380, Rudder 7,246, Wheel 3,520. 24 sockets.
- **Import:**
  - All five meshes imported: Hull 16 sockets, Mast 4, Boom 1, Rudder 2, Wheel 1. Nanite is on all but the Wheel; the import log doesn't print it for the Wheel.
  - The log ends "Success - 0 error(s), 7 warning(s)": Sentry has no DSN in the editor, an engine reference-gathering note, and five "Error opening file" lines from the importer replacing the old assets.
  - The hull asset grew from 13.0 MB to 15.3 MB.
  - It references MI_Boat_LaidTeak, VarnishedTeak, CastBronze, Manila, Brass, RedPlastic, WhitePlastic and the Pack* instances.
- **Tests:**
  - `SailingSim.Visual.FleetMesh`: 1/1 pass.
  - `SailingSim.Visual.RigClearance`: pass, with only the standing missing `S_*` sound-sample warnings.
- **Stills:** uncooked through `run-game.ps1 -Seconds 10 -ResX 1920 -ResY 1080 -NoDemo`, Ultra 1920x1080, Bolivar Roads. Bean's Saved was held aside and restored (B57AA3AF).
  - **Common args:** `-SailingBoat=Bluebonnet -SailingWorld=1 -SailingNoHud -SailingQuality=Ultra -SailingNoGpuSlices -ForceRes`
  - `bluebonnet-helm.png`: `-SailingCamTarget=-10.85,1.1,2.6 -SailingCamDist=7 -SailingCamYaw=60 -SailingCamPitch=-15`. This is the c39fd563 helm framing.
  - `bluebonnet-deck.png`: `-SailingCamTarget=-8,0,2.4 -SailingCamDist=6 -SailingCamYaw=150 -SailingCamPitch=-35`, looking down on the after deck.
  - **1:1 crops:**
    - `bluebonnet-helm-deck-1to1.png`: x 1000-1720, y 760-1080 of the helm still.
    - `bluebonnet-deck-1to1.png`: x 1080-1480, y 180-620 of the deck still.

## What I saw at 1:1

- **No checker:** every part draws with its material. The game logs have no default-material lines and no failed asset loads; the only "Failed to load" lines are the usual profiler DLLs and the sound-concurrency default. Visible parts:
  - bronze winches, bollards and cleats
  - varnished teak doghouse, skylight and wheel box
  - the wheel, compass binnacle and cockpit well
  - running rigging
  - the dark blue topsides with the gold cove line
  - the cream spars
- **Deck:** a uniform tan with a fine woven or knit texture, the same look as the earlier c39fd563 stills. There are:
  - no individual planks or black seams;
  - no staggered butts;
  - no king plank;
  - no nibbed covering boards or after margin.

  So the LaidTeak slot is assigned, but its planking terms aren't drawing. Places to look:
  - the LaidDeck static switch on `MI_Boat_LaidTeak`;
  - the extra UV channels (Planking, Margin and DA in UV2, UV3 and UV1.y) reaching the imported mesh;
  - the material reading those UVs.

  I didn't dig further or change anything.
