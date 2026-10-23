# Realism audit, Oct 23 2026

The second look-truth pass, on main e2e3a0e5 (#273), one day after `docs/realism-audit-1022/`. It uses the same method
and the same scenes, recaptured on High in the capture mode (`scripts/capture-scenes.sh`, 14 s):
- the 12 phase-8 reference scenes (`docs/phase-8/reference-scenes.csv`);
- the 15 G5 blind-pack scenes (`docs/graphics-5/blind/scenes.csv`).

Each is compared with yesterday's capture and, for the G5 scenes, with its Commons photo. As before, real photos that
show people are left out: the shelf cloud's beach, and the J/24, J/22 and Hobie photos.

The same day's full sweep (`scripts/gate.sh --scope all --force` on e2e3a0e5) passed: all 230 tests, and every view on
every tier is above its floor.

## Contact sheets

G5 scenes: real photo left, Oct 22 middle, today right. Bridge, open lake, overcast shore, sunset, cumulus:

![g5 real, 1](g5-real-before-now-1.jpg)

Dusk, Gulf swell, ship, storm shelf (no photo):

![g5 real, 2](g5-real-before-now-2.jpg)

G5 boat scenes, Oct 22 left and today right. Their real photos have people in them. Chase, crew, spinnaker, Hobie,
marina, slip:

![g5 boats](g5-before-now-boats.jpg)

Phase-8 scenes, Oct 22 left and today right. Bay Hobie, Gulf passage, action cam, heavy chase, helm on a reservoir,
light chase:

![phase 8, 1](phase8-before-now-1.jpg)

Moderate chase, Catalina 30 evening, drone over a catamaran, squall, storm, Sunfish reach:

![phase 8, 2](phase8-before-now-2.jpg)

## What changed since Oct 22

Items 1, 5, 6, 8 and 9 of yesterday's list were fixed. Items 2, 3, 7 and 10 were improved in part.

- **Cumulus (item 1; #260, #271).** Cells are as tall as they are wide, and their outlines are cauliflowered by packed
  lobes. The pillars and glossy balloons are gone (cumulus, bridge, chase, moderate chase).
- **Storm (item 5; #255, #256, #259).** The shelf's face is dark slate over a rain wall, not white (shelf, storm,
  squall).
- **Overcast (item 6; #263, #272).** The deck reaches the horizon. Its edge no longer shows overhead (Sunfish reach), and
  the haze band on the sea's horizon is gone (swell).
- **Low sun (item 2, in part; #265).** The far clouds go darker against a low sun.
- **Water at the boat (items 8 and 9; #262, #269, #270).** The wake and quarter wave show at speed, and the hulls have
  contact shading at the waterline.
- **Sails (items 3 and 7, in part; #261, #264, #267).** The far side's number is now faint, not nearly as strong as the
  near one. Shadow edges on the sails no longer step.
- **Shore (item 10, in part; #266).** Reeds and bank grass on the Rush Creek shore.

## The biggest remaining gaps

Ranked as before: how often a gap is on screen, times how far off it is. Lanes as the project splits them: the Mac does
physics, clipping, crew, water and sky; the PC does models, materials, the sails' look and rope. The sizes are rough.
There are eight this time, not ten. Two candidates from the contact sheets turned out not to be gaps on a closer look
(see Checked, below), and padding the list would rank noise.

| # | Gap | Where it shows | Lane | Size |
|---|---|---|---|---|
| 1 | **The lake is olive-brown, not blue-grey.** In the Tawakoni photos the open lake reads blue-grey to slate, mostly sky reflected off the chop, and dark at the horizon. Ours is olive to the horizon, with a pale strip where it meets the sky, and olive-brown seen from above. This was yesterday's item 4. It is parked for a low-angle Lake Ray Hubbard reference: the roughness and specular trials changed little, and the Tawakoni photos may be a bluer lake. | Every open-water view (bridge, open lake, chases, drone) | Mac (water: body colour, sky reflection at grazing angles) | 0.5–1 day, once a reference is in |
| 2 | **An overcast is too dark against the ground.** In the shore photo the overcast is near white, several times brighter than the grass and trees. Ours is a mid grey deck, about as bright as the lawn. A Lambertian surface lit by a uniform overcast is as bright as the sky only if it is white; grass at about 0.2 albedo should read about five times darker than the deck. | Overcast views (shore, Sunfish reach, swell) | Mac (sky: deck luminance against the incident-metered exposure) | 0.5 day |
| 3 | **A low sun leaves the sky blue-grey.** In the sunset and Aeolian photos the whole sky goes orange to gold, and the haze near the sun glows. Ours keeps a neutral blue-grey above the horizon band, with lit cloud rims over it. The clouds' undersides got darker in #265; the sky did not. | Sunset, dusk and evening views (lakesunset, dusk, C30 evening) | Mac (sky: atmosphere and haze at low sun) | 1 day |
| 4 | **Cumulus outlines glow, and the horizon is packed.** Each cell has a bright rim all round, like a drawn outline, and toward the horizon the small cells pack into a solid band. In the photos the edges away from the sun are no brighter than the body, and there is clear sky between the far clouds. | Every fair-weather view | Mac (sky: CLOUD_CODE edge light, cell spacing with distance) | 0.5–1 day |
| 5 | **The open sea is green.** In the swell photo the open Gulf is dark blue-grey, the same family as the sky. Ours is bottle green. That suits the bay and the lake, but not the Gulf's open water. | Gulf views (swell, Gulf passage) | Mac (water: the Gulf body's albedo and extinction in `WaterBodyFor`) | 2–4 hours |
| 6 | **The sails' shape reads only faintly.** #261 (draft shading to 0.74 at a grazing look, translucency per cloth, the faint far-side number) and #264 (the spinnaker's panels and radial head, dye lots, darker seams on coloured cloth) are both in these captures: the mirrored number is faint and the spinnaker's panels show. But the belly and twist of a white sail, and the spinnaker's curve, still read as nearly even tone in flat light. The G5 sail photos all have people in them, so this rests on judgement, not on a side-by-side. A people-free sail photo, or a pass with the PC's own references, would settle how far to take it. | Every boat view | PC (M_SailCloth look) | 0.5 day, after a reference |
| 7 | **The far shore's reflection on calm water is too sharp.** In the overcast-shore view the trees and buildings reflect as a crisp mirror image. In the photo the reflection is broken and softened by the faint ripples. | Calm-water views (shore, marina) | Mac (water: calm-water roughness floor and ripple at 2–3 kn) | 2–4 hours |
| 8 | **The far banks are clean.** #266's bank grass and weed are drawn to 250 m. Past that, a bank is grass meeting the water in a line, as on the far side of the overcast-shore view. (The shore photo's weed is at the photographer's feet, so it is not a like-for-like compare; #266's own cove and marina stills show the near plants.) | Wide shore views | PC (models: a far-band stand-in for the bank plants, or a terrain tint) | 0.5 day |

## Checked: not gaps

- **The captures include today's merges.** `capture-scenes.sh` runs the game uncooked from this checkout (`run-game.sh`).
  It was at main e2e3a0e5, built by the sweep just before, so #261, #264, #266 and every other merge are in them.
- **Sails under the squall.** On the contact sheet they looked nearly black. At full size the jib's shaded side (55,
  grey) is brighter than the squall sky behind it (38). Yesterday the jib was level with the sky (95 against 94). The
  whole sky is 2.7 times darker since the storm-gloom work (#256, #259), the sails followed it by 42%, and the water
  is unchanged (58 and 57). The sails are not too dark for the light; the downscale misled.
- **The trimmer in the helm view.** Yesterday's 16 s frame caught the trimmer mid-crossing: centred in the cockpit,
  facing forward, the crossing pose. Today all three crew are on the windward seat, beside the helm and out of the
  forward view (checked from above). No crew-placement code changed between the two captures; #273 only turns joints
  a few degrees about the stance.

## Smaller

- **Ship.** The container ship is now lit and coloured (#268), not a silhouette.
