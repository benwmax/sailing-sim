# Frigate import round 3 on the PC (3946b08c, code only), Nov 24 2026 (UTC)

**Head:** `claude/project-thread-xkunbh` at **3946b08c** (on a5670d9b), in the kept worktree, fast-forwarded with no
force. Nothing was pushed this round.

| | |
|---|---|
| MSVC build | Succeeded, 0 errors |
| SailingSim.Visual.WakeGrid | 2 tests (WakeGrid, WakeGridShip), **0 failed** |
| SailingSim.ShipOutside | 3/3 |
| SailingSim.ShipRig | 3/3 |
| SailingSim.ShipFrames | 5/5 |
| SailingSim.ShipWalk | 7/7 |
| SailingSim.Smoke | 32/32 (1 standing warning) |
| Dev package `Windows-frigate-3946b08c` | exit 0; cook 0 errors, 1 warning |

## WakeGrid AddInfo, verbatim (`wakegrid-info.txt`)

```
SailingSim.Visual.WakeGrid [Info] 6 kn: largest wave 0.218 m, bow crest 0.019 m, 99% of the wake's energy inside 24 degrees
SailingSim.Visual.WakeGrid [Info] Wake lane: 1.00 under her, 0.66 5 m astern, 0.29 20 m astern, 0.00 8 m aside
SailingSim.Visual.WakeGrid [Info] Wake lane 5 m astern: 3.5 m wide (beam 2.4 m)
SailingSim.Visual.WakeGrid [Info] Foam 2 m astern 1.00, 25 m astern 0.16, 6 m ahead of the bow 0.00
SailingSim.Visual.WakeGrid [Info] 40 s after stopping: largest wave 0.0002 m
SailingSim.Visual.WakeGrid [Info] 40 s after stopping: lane 0.007 at most
SailingSim.Visual.WakeGridShip [Info] 9 kn: largest wave 0.60 m, foam beside her 0.05 (port) 0.05 (starboard), in her lane astern 0.49
SailingSim.Visual.WakeGridShip [Info] 20 s after she stops: mean foam 0.0008
```

## Stills (Ultra 1920x1080, `-SailingBoat=Comm -SailingWorld=Gulf -SailingLaunch=2 -SailingWind=12`)

`round2-vs-round3.png`: round 2 on the left, round 3 on the right; wide on top, deck below.

- **The white sheet is gone.** In the wide shot (`-SailingCamDist=120 -SailingCamYaw=140 -SailingCamPitch=-8`) she sits
  on open water, with only her reflection and a faint wake astern.
- **Deck (`-SailingCamDist=60`):** the water beside her is clear too. There is a darker patch of water under her lee
  quarter, which reads as her shadow.
- **Log lines, unchanged from round 2:** "Ship rig Commonwealth: 87 parts on the model, 0 to load, 0 not in the
  project"; "Ship outside Commonwealth: 244 parts on the boat, 0 did not load"; "Ship frames: 12 to load, 0 not in the
  project".

Bean's Saved was held aside and restored (7B5CA7BE).
