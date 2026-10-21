# Sails look (boat fidelity, no photos of our own needed)

Before this change, every class's sail seams, coloured bands and batten pockets were drawn horizontal, at one 0.9 m
spacing. On a real crosscut sail the panels meet the leech at right angles. So do the batten pockets and the coloured
panels of a Hobie 16 or a Sunfish, and the seams slope down toward the luff. That is what the reference photos below
show.

## The change (`SAIL_CODE` in `scripts/make_materials.py`, `ASailboatPawn` sail setup)

- **The panel coordinate.** `alongLeech` is the distance along the leech, in metres, from the foot. It comes from the
  cloth mesh's UVs and `LeechLean`, the leech's forward travel per metre of height. The pawn computes `LeechLean` for
  the main and for the jib from the sail's strips (leech X = luff X − chord, bottom strip to top strip). Seams, the
  panels' tone variation, the Sunfish's and Hobie's colour bands, the batten pockets and their stitching all follow it.
- **Cloth width per class (`PanelWidth`).** These are approximations of each class's cloth, not measured sailmakers'
  plans:

  | Class | Width |
  | --- | --- |
  | Sunfish | 0.42 m bands |
  | ILCA | 0.72 m |
  | Hobie 16 | 0.85 m |
  | J/22, Catalina 22, Corsair | 0.9 m |
  | Catalina 30, Lagoon | 1.0 m |
  | Maxi | unchanged |

- **Jib window (`Window`).** The club keelboats' jibs (J/22, Catalina 22, Catalina 30) carry a clear vinyl window low on
  the sail, ahead of the clew. From the lit side it reads darker and glossy (roughness 0.08) with a stitched border;
  against the light it lets more through than the cloth.
- **Unchanged:**
  - The layouts per class: crosscut for the J/22, Catalinas and ILCA; the Sunfish's stripes; the Hobie's colour
    panels; tri-radial for the Corsair and Lagoon mains (their upper sections are crosscut, now at right angles to the
    leech); the maxi's membrane.
  - The telltales: their geometry and rules (`SailingSim.Visual.Telltales`).
  - The insignia, numbers, tabling and corner patches.
- **Typed literals.** Every conditional the change touches uses typed literals (`FullBattens > 0.5f ? 50.0f : ...`),
  as the new panel coordinate does.

## Stills (Ultra, beating at 10 kn, uncooked)

- `<class>-before-after.jpg`: a close side view of each class's sails, main at left of each pair.
- `fleet-before.jpg` / `fleet-after.jpg`: all eight classes, lee and close views.

## Reference photos (Wikimedia Commons; not in the repo: they show people)

| Class | File | Author | Licence |
| --- | --- | --- | --- |
| Sunfish | [Sunfish Lessons](https://commons.wikimedia.org/wiki/File%3ASunfish_Lessons.jpg) | Thedjatclubrock | CC BY-SA 3.0 |
| ILCA | [Ivan scimonelli](https://commons.wikimedia.org/wiki/File%3AIvan_scimonelli.jpg) | Utente fiv derive | CC BY-SA 4.0 |
| Hobie 16 | [Hobie Cat à l'Aber-Wrac'h](https://commons.wikimedia.org/wiki/File%3AHobie_Cat_%C3%A0_l%27Aber-Wrac%27h_%289593980115%29.jpg) | Yann Caradec | CC BY-SA 2.0 |
| Catalina 30 | [Catalina 30 sailboat Rootless 0110](https://commons.wikimedia.org/wiki/File%3ACatalina_30_sailboat_Rootless_0110.jpg) | Jim Sorbie | CC BY 2.0 |
| Corsair F-27 | [Corsair F-27 Sport Cruiser Zephyr 0619](https://commons.wikimedia.org/wiki/File%3ACorsair_F-27_Sport_Cruiser_Zephyr_0619.jpg) | Ahunt | CC0 (sails furled) |

Commons had no J/22 or Catalina 22 under sail (all moored, sails down) and nothing for the Lagoon 42. Those classes
follow the general crosscut rule. `Tools/blindtest/fetch_commons.py` fetched them into git-ignored
`Artifacts/commons-sails/`.
