# Clipping audit 2 (Ultra regression after #195–#212, Oct 21 2026)

This is a second pass of the clipping audit (`docs/clipping-audit/`), run on the PC's RTX 4090 at Ultra (uncooked,
1600×900, launch arguments only) on main 01977fe0. A second batch ran on 62fd45a8, after the Lagoon's self-tacking jib
(#212) landed.

## What was shot

- **All nine boats:** J/22, Sunfish, ILCA 7, Catalina 22, Catalina 30, Hobie 16, Corsair 880, Lagoon 42 and the maxi.
- **Four conditions each:** beating (TWA 42–45) and running (TWA 165), at 4 and 15 kn.
- **Four views each:**
  - chase: yaw −40, pitch −15;
  - above: pitch −70;
  - close: the cockpit and side deck at 0.4 of the chase distance;
  - the cockpit (helm-eye) camera, `-SailingCockpit`.
- **Rain:** one close view per boat in the Rain preset, with `-SailingDeckWet=1 -SailingPuddle=0.8`.
- **Lagoon 42:** a beat at 15 kn, and a demo tack at 15 kn caught at 14, 20, 26 and 32 s, with the camera on the
  self-tacker's track on the saloon roof.
- **J/22 puddles:** close-ups at about 1 m on the cockpit sole and the foredeck, plus the helm eye, in the Rain preset
  with `-SailingPuddle=1`.

That's 163 stills. The log showed no default or world-grid material on any boat (`DefaultMaterial`/`WorldGridMaterial`: 0
lines).

The contact sheets are `sheet-<boat>.jpg`. Each has the rows B4, B15, R4, R15 and the columns chase, above, close,
cockpit. `sheet-rain.jpg` has the rain close-ups.

The wrist and vest fixes for the held line weren't judged here (the Mac has them).

## Findings

| # | Boat | Issue | Owner | File (guess) | State |
| --- | --- | --- | --- | --- | --- |
| 1 | every keelboat, worst at 15 kn | The wet line's ragged edge sawed along the topsides near the sheer: regular dark teeth every 30 cm, up to 20 cm tall. Spray-hull's raised band (#202) scaled the old streak up with it. | PC | `BOAT_CODE` (make_materials.py), `DETAIL_CODE` (import_j22_hero.py) | **Fixed** (this branch) |
| 2 | J/22, 15 kn beat | A hard-edged rectangle of flat, raised water off the port quarter, a metre or so out from the hull. | Mac | `M_WaterV4` hull clip (`FHullClipMap` rect) or a ring seam in `AWaterSurface` | open |
| 3 | Catalina 30 (also Hobie, Catalina 22) | The cockpit camera sits inside the helm's head and vest, and the Catalina 30's dodger. The view is the inside of a cap, a vest and a face. | Mac | Crew placement at the helm vs `UpdateCockpitCamera`. Hide the helm figure in that view, or put the eye ahead of the helm's head. | open |
| 4 | Sunfish, ILCA, running at 4 kn | The dinghy sailor is in a full hike in light air: back arched over the side deck, face to the sky, arms akimbo. | Mac | `CrewPlacement` / `FCrewBalance` (DinghyHike in light air downwind) | open |
| 5 | Hobie 16 | Both crew kneel on the trampoline with their arms raised overhead toward the sail, in the close views at 4 and 15 kn and in the rain shot. | Mac | `CrewMotion` / `CrewPose` (the Hobie's stances) | open |
| 6 | J/22 and others, at speed in the sun | Lens-water drops have blocky, pixelated insides (the refraction looks sampled at low resolution). | Mac | Lens-water post-process blendable (`ASailingEnvironment`) | open |
| 7 | J/22, 15 kn beat | Check: the third crew sits on the cabin top's aft edge with the legs down over the companionway. That reads as perched, not clipped. | Mac | `CrewPlacement` | check |
| 8 | Hobie 16, 15 kn beat | The boat sails onto the beach from the launch spot within 12 s. This comes from the shot setup (start heading), not a bug. | — | — | note |

Clean:
- No new hull, water, rig or sail clipping on the other views of all nine boats.
- Coils, rig lines and the bow-wave curl show nothing broken at contact-sheet scale (the curl is checked close only on the J/22).
- **Lagoon 42 self-tacker:** the jib crosses on its track over the saloon roof through the tack with no clipping
  (`lagoon-selftacker-tack.jpg`).
- **Rain:** drips, puddles and rings show on every boat. On the J/22 at about 1 m, the puddles are dark mirrors that
  reflect the hatch and boom, and the rings show on the sole and the foredeck (`puddles-*.jpg`).

## Stills

| Still | Shows |
| --- | --- |
| `wetline-before-after.jpg` | #1, before and after |
| `water-rectangle.jpg` | #2 |
| `cat30-cockpit-camera.jpg` | #3 |
| `ilca-light-air-hike.jpg` | #4 |
| `hobie-arms-up.jpg` | #5 (here she has also run onto the beach: #8) |
| `lens-drops-blocky.jpg` | #6 |
| `lagoon-selftacker-tack.jpg` | Lagoon tack at 20 s |
| `puddles-foredeck-1m.jpg`, `puddles-sole-1m.jpg`, `puddles-helm-eye.jpg` | J/22 rain close-ups |

Repro: the capture script's arguments are in the table above. For example, the J/22 at 15 kn close-up is
`-SailingBoat=J22 -SailingWind=15 -SailingTWA=42 -SailingHoldTWA=42 -SailingCamTarget=-1.2,0,0.48 -SailingCamYaw=-125
-SailingCamPitch=-20 -SailingCamDist=3.2 -SailingQuality=Ultra`.
