# Calm-water reflection against the shore photo: the scene's wind, not the water (Oct 24 2026)

Realism audit Oct 23, item 7: in the G5 overcast-shore view the far shore's reflection on calm water was a crisp mirror,
where the photo (Lake Tawakoni State Park, Larry D. Moore, CC BY 4.0) shows it broken up by faint ripples.

## What the water does

The scene asks for 3 kn, but the cove shelters it: the boat's local wind is 1.2 kn (0.6 m/s). That is below the wind at
which capillary ripples start. Kahma and Donelan (1988) measured wavelets appearing at a 10 m wind of about 1.6 to
3.3 m/s, and M_WaterV4's glass fades out over 1.5 to 3.0 m/s. A lake at 0.6 m/s is a mirror, as our water draws it.

The photo isn't calm. Regular, long-crested wavelets run across the whole surface and break the trees' reflection
short, so its local wind is above onset, about 3–4 kn or more.

## Measured

The reflection's detail against the shore's: the mean brightness gradient in a band just under the far waterline over
the same in the band of trees above it, across and up-down.

| | across | up-down |
| --- | --- | --- |
| Photo | 1.07 | 3.40 |
| Scene, 3 kn (1.2 local) | 0.56 | 0.59 |
| 6 kn (2.1 local) | 0.59 | 0.62 |
| 9 kn (3.9 local) | 0.57 | 0.72 |
| 12 kn (5.5 local) | 0.66 | 0.95 |

The photo's up-down detail (its streaks) is matched only as the local wind climbs past onset. At the scene's own wind
our reflection is the mirror physics gives.

## Change

`docs/graphics-5/blind/scenes.csv`: g5-shore at 9 kn (about 4 kn in the cove), the conditions the photo shows. Nothing
in the game changes.

`photo-3kn-9kn.jpg`: the photo, the scene at 3 kn, and at 9 kn.

## Left

The photo's wavelets are more regular and long-crested than ours, which come out irregular at 9 kn and still stream less
(up-down 0.72 against 3.40). That is the short-wave spectrum's shape at low wind and short fetch (`FWaveDetail`), a larger
item of its own if wanted.
