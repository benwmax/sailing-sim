# The sheets' audit

`SailingSim.Visual.SheetClearance` is the RigClearance of the running lines. What it checks:

- **The lines:** every drawn sheet (working and lazy jib sheets, the mainsheet's tackle), their tails and the vang. No
  boat draws spinnaker sheets yet.
- **The boats and conditions:** all nine boats, on the eight points of sail RigClearance holds, and through a tack and
  a gybe, sampled every third of a second while the autopilot turns her.
- **What each line is checked against:**
  - the solid boat (hull, deck, cabin trunk, cockpit: `CrewInsideBoat`);
  - the lifelines;
  - the crew's flesh;
  - the standing rig (shrouds, stays, spreaders, the trapeze wire) and the mast.
- **What isn't checked:** a few centimetres at each end of a line, where it meets its block, the clew or a hand.

Everything it finds is listed. It fails when one of these happens in more than two samples of a boat:

- a sheet more than 10 cm into the solid boat, away from its fittings;
- a sheet through a wire or the mast, away from both its ends;
- a sheet more than 4 cm into a sailor, away from a hand holding it and off the deck. A line on the deck or the cockpit
  floor under a sailor is sat or lain on, which is realistic.

## What it found on main (b236e158), and the fixes

| boat | contact | fix |
| --- | --- | --- |
| Catalina 30 | the lazy jib sheet through the mast through a tack | `UpdateModelRig`: the lazy sheet goes over the cabin top forward of the mast (`LazySheetVia`) only while the clew is forward of it too. An overlapping genoa's clew is aft of the mast during a tack; the sheet then crosses the cabin top aft of the mast, at the via's height, level with the clew. Mast: 3 samples down to 1. |
| Catalina 22 | the mainsheet's tackle through the helm's back through a tack (spine 4 cm, 5 samples) | `CrewPlacement`: her helm crosses forward of the tackle, which runs from the boom's end (`MainLuffX` less the foot) down to the transom. Before, they crossed at the tiller's end, under the tackle. |
| Sunfish | the mainsheet tail across the sailor's back while ducking under her boom | **done** (docs/sunfish-duck/): her sailor now stoops and kneels lower under the boom. |
| Maxi 100 | a lazy jib sheet under two seated crew in the gybe | on the deck under them: sat on, listed |
| Catalina 22 | the mainsheet against the top lifeline, close-hauled in a breeze | a sheet rubbing a lifeline: listed |
| every boat | sheets 2–7 cm "into" the deck and cabin top | lines lying on a surface (the drape): listed |

The test's stand-in mast starts at the sheer, so the Lagoon's vang foot, on her coachroof's mast step, read as mid-mast.
The vang isn't checked against the mast it's fixed to.

After the fixes: 0 failures, 48 kinds of contact listed. `SailingSim.Visual.RigClearance` and `SailingSim.Visual.Crew*`
still pass.
