# J/22 water hull clip at the bow, in a chop (shape wave 1)

Branch claude/shape-j22-hull-wave1 at 96a7ab66, uncooked (scripts/run-game.sh), High, 16 kn at TWA 45, demo autopilot,
camera on the bow (`-SailingCamTarget=2.4,0,0 -SailingCamDist=3.8`, yaw 150 / -150 / 100 / 160 from the boat's stern).
The player's J/22 draws the hero model (built on the old hull); FHullClipMap reads the physics hull.

- No water shows inside the boat (deck and well dry in all four).
- At the bow's waterline, small bright notches (zoom_beam, zoom_stbd) and a lighter band under the forefoot (zoom_port):
  the clip dropping the surface a few cm outside the hull, showing its underside. Small; worth a look after the hero
  rebake, when model and clip share the new hull.
