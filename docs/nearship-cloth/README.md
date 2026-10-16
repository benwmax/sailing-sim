# Near-ship cloth reset

With `-SailingNearShip` the Mac saw the J/22's sails blow out into a huge flat sheet in two of six runs. The likely cause
was the mid-run `ResetBoat` (traffic spawns the first ship, then the player is moved abeam of her), which reset the boat
but carried the sail cloth's old positions and velocities over.

## Change

- `FSailCloth::Reset()` forgets the cloth's motion; the next `Step` starts again from the target shape.
  `ASailboatPawn::ResetBoat` calls it for the main, jib and spinnaker.
- `FSailCloth::Step` also restarts from the target when any vertex is non-finite or more than `kRunawayCm` (6 m) from
  it, so a bad frame can't leave a sail blown out for the rest of the run.

## PC runs (packaged, High)

`-SailingWorld=1 -SailingLaunch=3 -SailingTraffic=2 -SailingTrafficNear -SailingNearShip=150 -SailingWind=12
-SailingHour=11`, six runs of each build. Before is main b9e9ccec, after is this branch.

![Six runs before (top two rows) and after (bottom two rows)](before-after-6x2.jpg)

None of the twelve runs blew out, so the PC did not reproduce the Mac's two in six; the change is aimed at the
mechanism, not confirmed against a failure on this machine. The reset really happens in these runs: framed abeam, the
boat sits 150 m off the container ship's side (camera yaw 90 top, 270 bottom, after build).

![The boat moved abeam of the first ship](ship-abeam.jpg)
