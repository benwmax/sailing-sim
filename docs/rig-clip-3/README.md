# The main through the rig: the last real clips

After the boom stop (#224), RigClearance still listed three running cases where the main passes through a wire:

- the J/22's and the Maxi's main through the upper shroud's lower leg, from chainplate to spreader tip, just under the
  tip;
- the Hobie 16's main through her trapeze wire.

## The fix

`FSailCloth::KeepClear`'s dent, the main's target bent round a wire it still presses on, checked each wire only at the
row's mean height. The cloth between two rows spans the wire there, and the rows above and below were both clear of
it. The dent now checks each wire at the row's height and half a row either way, as the main's turn already does.

## RigClearance on the runs

| entry | main (772bc7bd) | this branch |
| --- | --- | --- |
| J/22 upper shroud through the main | 16 samples | gone |
| Maxi upper shroud through the main | 15 samples | gone |
| Hobie 16 trapeze wire through the main | 8 samples | gone |
| mains over the spreaders (C30, Corsair, Maxi, now also the J/22's) | listed | listed: a running main lies on its spreaders |

The J/22's spreader entry appears now because her upper shroud entry no longer comes first in her list.

## Not in this branch

The trapeze wire is drawn to any sailor whose hips are outside the rail. On a run that includes the Hobie's crew sitting
out on her hull, and the wire then runs a metre aft and down across the main.

I tried drawing it only to a sailor on the trapeze. That exposed a second problem: on a run her crew sit aft on the
leeward hull, under the boom. The wire had been an obstacle that held the main and boom in a little. Without it, the
mainsheet passes 2.8 cm into the forward sailor's back (RigClearance fails). Both are fix-list item 14.

`race-high.jpg` is the lake race on High, AI J/22s with nothing out of place.
