# Camera views: before (main 8f5331f4)

Uncooked (`scripts/run-game.sh 10`, its defaults `-SailingBench=10 -SailingDemo -SailingWorld=Lake`), 1920x1080 `-ForceRes
-SailingNoGpuSlices`, the J/22 on Lake Ray Hubbard, High, `-SailingNoHud` unless noted. Shot at the end of the 10 s window.

| File | Args | Seen |
|---|---|---|
| 1-chase.png | `-SailingBoat=J22 -SailingCamYaw=180` | Chase camera from ahead and above, the whole boat mid-frame with the shore behind. |
| 2-dist4.png | same + `-SailingCamDist=4` | The camera sits beside the mast: the main and jib fill the right two thirds and the hull drops out of frame except the cockpit corner and the outboard at the bottom left. |
| 3-dist40.png | same + `-SailingCamDist=40` | Boat small in frame, high and far; fine as a wide shot. |
| 4-pitch5.png | `-SailingCamYaw=180 -SailingCamPitch=5` | Camera low over the water looking slightly up; the boat at the horizon line, much sky. |
| 5-sunfish.png | `-SailingBoat=Sunfish -SailingCamYaw=180` | Sunfish default chase at the same yaw: the whole boat in frame, framed similarly to the J/22. |
| 6-cockpit.png | `-SailingCockpit` | Helm's eye looking forward along the starboard side deck: cabin top, winch and boom in front, water to port. |
| 7-photo-pad.png | `-SailingPhoto=5 -SailingPad` (HUD on) | Photo mode opens on its Camera page (the panel's first page; no input needed): Focal length 18 mm, Tilt Level; hints as text ("X next row · D-pad left / D-pad right change · B hide"), small panel top left. |
| 7b-photo-pad-nohud.png | the same with `-SailingNoHud` | The photo camera without the panel. |
