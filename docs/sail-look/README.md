# Sail look (realism audit 3)

`docs/realism-audit-1022`, item 3: the sails looked flat and chalky, with no shading from their draft and no realistic
translucency. Worse, the far side's sail number showed through mirrored and nearly as strong as the near one ("1288"
reversed over "1288"). This pass fixes that in `M_SailCloth` (`scripts/make_materials.py` `SAIL_CODE`,
`build_sail_cloth`). The per-class layouts, seams, battens, patches and marks are unchanged.

- **Translucency is the cloth's.** A new `Translucency` parameter sets how much light passes through: 0.34 for
  resinated Dacron (`MI_Sail_Main`, `MI_Sail_Jib`) and 0.55 for spinnaker nylon (`MI_Sail_Spinnaker`). Before, every
  sail transmitted 0.7 of its colour. The glow is strongest when looking toward the sun through the cloth (forward
  scattering, with the sky's sun direction): up to about double.
- **The show-through is faint.** The other side's number is ink on the far face. It used to block 90% of the
  transmitted light, as much as the near ink. Now it blocks 18% normally and up to 50% with the sun right behind it,
  and leaves a 6% trace in the lit side's cloth.
- **The draft shading.** Cloth turning away from the eye darkens, to 0.74 at a grazing look (the vertex normal, signed
  by the face, against the view). The belly, the twist and the roll of the leech now read even in flat light.

Frame cost (uncooked, 1920 x 1080, the sail filling the view, total GPU per frame): High 14.22 ms before, 14.00 after;
Ultra 18.09 ms before, 18.36 after. Within the noise.

Before and after (game only): `g5-chase-before-after.jpg` and `g5-hobie-before-after.jpg` (the audit's G5 scenes),
`main-wind-before-after.jpg` and `main-lee-before-after.jpg` (the J/22's main from windward and leeward).

Seen, not changed here:
- The spinnaker's blotchy, stair-stepped self-shadow is item 7 (`pc/spin-colour`).
- In the backlit G5 Hobie capture, the strong number reads mirrored. That was the case before this pass too. From
  either side in flat light both numbers read correctly, so it is likely the sail grid's face (`FSailCloth`) in that
  pose. It is for the Mac.
