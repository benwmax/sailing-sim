# Frigate import round 2 on the PC, Nov 24 2026 (UTC)

**Branch** `claude/project-thread-xkunbh`:

- `366ffb3d`: the wiring thread's fixes (movable outside parts, no stand-in sails, flat materials).
- **`a5670d9b`**: my Content commit, a normal push on 366ffb3d. It has exactly the 48
  `Content/Boats/Frigate/Materials/MI_Frigate_*.uasset` from `import_frigate.py materials`: "Built 48 MI_Frigate_*
  instances", 0 errors, 0 slot warnings. Nothing outside that folder changed.

**Checks at a5670d9b**, in the kept worktree `D:\dev\ss-fix-wt\frigate`:

| | |
|---|---|
| MSVC build | Succeeded, 0 errors |
| SailingSim.ShipOutside | 3/3 |
| SailingSim.ShipRig | 3/3 |
| SailingSim.ShipFrames | 5/5 |
| SailingSim.ShipWalk | 7/7 |
| SailingSim.Smoke | 32/32 (1 standing warning) |
| Dev package `Windows-frigate-a5670d9b` | exit 0, 2 min; cook 0 errors, 1 warning |

## Log lines (the same in all three stills; `*.lines.txt`)

```
Ship outside Commonwealth: 244 parts to load (heroes)
Ship rig Commonwealth: 0 parts on the model, 0 to load, 87 not in the project
Ship frames Commonwealth: 0 parts on the model, 12 to load, 0 not in the project
Ship outside Commonwealth: 244 parts on the boat, 0 did not load
Ship rig Commonwealth: 87 parts on the model, 0 to load, 0 not in the project
```

- **The rig now binds: "Ship rig Commonwealth: 87 parts on the model".** The first rig line is the pass before the
  outside model is on her. Once it is, the binder finds all 87.
- **Outside:** 244 on the boat, 0 did not load.
- **Frames:** 12 to load, 0 not in the project.
- **Gun deck:** "-SailingWalkAt: walking on Gun at (-19.00, 0.00) facing 0".
- No "Deck mesh ... did not load" anywhere.

## Stills (Ultra 1920x1080, `-SailingBoat=Comm -SailingWorld=Gulf -SailingLaunch=2 -SailingWind=12`; `args.csv`)

- **frigate-r2-deck** (`-SailingCamDist=60`): her full rig is set and attached, with the yards across, square sails,
  staysails and shrouds. The deck reads as pale holystoned planking.
- **frigate-r2-gundeck** (`-SailingWalkAt=Gun,-19,0,0`): the battery, the carriages in red, the breechings, and the
  lit gun ports. **The wavy ripple on the wood is gone:** the pillars and beams are plain. The deck below is dark, as
  you'd expect away from the ports.
- **frigate-r2-wide** (`-SailingCamDist=120 -SailingCamYaw=140 -SailingCamPitch=-8`): the whole ship under sail, with
  the black and ochre hull, the rig, and every sail set.

## What still looks wrong

**A flat white sheet at the waterline beside and behind the hull,** in the deck and wide stills. It's flat on the water,
wider than her beam, and extends aft to starboard. It looks like the water's hull cut-out (`FHullClipMap`) built from
her config stand-in's plan rather than the model: the water is dropped over a shape the new hull doesn't fill. It
could also be a leftover stand-in surface. It's the one thing left that breaks the wide shot.

Bean's Saved was held aside and restored (7B5CA7BE).
