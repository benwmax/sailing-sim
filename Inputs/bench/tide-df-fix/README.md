# Tide-step stall fix: prototype and measurements (PC, Nov 25 2026)

**The patch:** `tide-df-fix-on-7304f52.patch` applies on 7304f52, branch claude/project-thread-69jipd. It touches
`Source/` only. I've pushed nothing to the branch.

## What the patch does

1. **Batched kept moves** (`ALakeTerrainActor::FollowActor`): this is the fix.
   - A tide step now moves the terrain actor's kept components a budget of instances at a time: 20,000 a frame, set by
     `-SailingTideBatch=<n>`; 0 moves everything at once, as before.
   - It no longer moves everything in one frame. The crown tiles hold about 525k instances, so a step finishes in about
     27 frames (0.5 s).
   - Each kept component remembers where it stands (`KeptAtEach`). A world re-centre still shifts everything at once and
     keeps any lag.
   - A component bigger than the budget still moves whole.
2. **Tide followers out of the distance fields** (`MarkTideFollower` in WorldKit):
   - On a tidal world on High/Ultra (hardware Lumen), followers get `bAffectDistanceFieldLighting = false`, conservative
     instance bounds and no navigation, per docs/recentre-hitch.
   - It covers the terrain's kept components (crowns, proxies, houses, kit tiles) through `KeepWithActor`, moving and kept
     kit tiles in `SpawnKitTiles`, the bridge traffic ISMs, the landmark ISM and the navaid ISMs.
   - Medium and the lake keep the distance fields.
   - Compare switches: `-SailingTideDF=1` keeps everything in the DF (7304f52's behaviour), and `=2` takes only the crowns
     out, and only on Ultra.

**Tests:** `SailingSim.Coast` is all green on the PC (22 tests, 0 failed), including `KeptStaticFollowsTide`. It has
single components, so they move at once.

## Forced steps

**Setup:** 2-min runs at 4K Ultra on Galveston, using 7304f52's `-SailingTideStepEvery=20` (6 steps). The route is the
soak's: the deep-water start in Bolivar Roads, the demo, clock 15:00. The figures are the most render-thread ms in each
step's 20 s window.

| Run (package) | Each step's peak render ms | Frames > 50 ms | fps |
|---|---|---|---|
| 7304f52 as is (`-SailingTideDF=1`, tidedf) | 777 / 809 / 733 / 726 / 583 / 403 | 39 | 45.6 |
| DF off only (tidedf) | 432 / 238 / 215 / 218 / 219 / 236 | 8 | 50.3 |
| Crowns' DF off only, Ultra (`=2`, tidedf) | 417 / 249 / 212 / 234 / 216 / 220 | 8 | 50.2 |
| Batching only, DF kept (`-SailingTideDF=1`, tidedf2) | 56 / 56 / 56 / 58 / 55 / 56 | 7 | 51.4 |
| **Both (the patch, tidedf2)** | **55 / 54 / 52 / 56 / 55 / 52** | 8 | 50.7 |

Without steps the frame is about 19-20 ms of render thread.

- **The steps fall from 400-810 ms to 52-58 ms.** At 52-58 ms, each step is a single frame of roughly three normal frames.
- The first "both" run read 39 fps, with render at 25-30 ms between steps too. A traced re-run was clean (table). I
  count the first as noise on the PC; I haven't explained it.

## Distance-field census

The 8 s "Distance-field instances:" line, in `*-log.txt` here:

| Run | DF instances |
|---|---|
| 7304f52 | **539,070**: LakeTerrainActor static ISMs 524,252 in 738 components; BridgesActor 634 meshes; navaids 1,598; LakeTerrainActor meshes 1,202; ... |
| Patch | **11,198**: the rest is the water, the moored boats (CoastMarinasActor 3,182), vessels and one movable LakeTerrainActor ISM of 4,097 that isn't a follower I marked |
| Crowns only (`=2`) | **15,711** |

## The coordinator's questions

1. **The DF census line, with and without the patch:** above, 539,070 against 11,198.
2. **Peak render ms at each forced step, with and without:** above. DF off alone takes 580-810 ms to 210-240 ms. The
   batching takes it to about 55 ms.
3. **Are the crown tiles and proxies in the DF scene?** Yes. They are almost all of it: about 523k of the 524k
   LakeTerrainActor ISM instances. Turning only the crowns' DF off, on Ultra, does as much as turning off all the
   followers (`=2` row). **But DF off is not enough on its own.** The trace of the DF-off run at a step
   (`df0.utrace`, local) shows:
   - `PrepareDistanceFieldScene` falls from 443 ms to 6 ms;
   - **`SceneCulling_Update_FinalizeAndClear` takes 142 ms**: the renderer re-bins the half-million crown instances that
     moved.

   Only moving fewer instances per frame removes that, hence the batching.
   - The shore walls: `bAffectDistanceFieldLighting = bWall` (LakeTerrainActor.cpp) puts them in the DF. They are kept
     components, so the patch takes them out on High/Ultra too.

## Does the lighting change? Dusk stills, 4K Ultra

**Setup:** Galveston, from the Kemah launch spot. Date 2026-10-22, clock 18.9, capture camera fixed in the world.

**Comparison:** each image is main 83aa7652 on the left and the patched package on the right.
- `compare-dusk-marina.jpg`: the docks and shore houses west of the Kemah channel.
- `compare-dusk-bridge.jpg`: up the Kemah channel toward the SH 146 bridge. The shore houses hide the bridge from here,
  but it's the same lit shore and trees.

**Result:** I can't see a difference in either pair: shore, trees, window lights, reflections, sky.

## Not done yet

- **The 45-min natural-tide soak with the patch.** The coordinator's order puts it after the Saturday package and
  rehearsal at d8f2a3dc.
- **Medium (software Lumen):** not measured. The patch leaves Medium's distance fields alone, so only the batching applies
  there.

Bean's Saved was held aside and restored (7B5CA7BE) for every run.
