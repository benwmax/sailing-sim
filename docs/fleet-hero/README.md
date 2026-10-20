# Fleet hero pass

The fleet's boats in career order, each brought up to hero detail in `Tools/blender/build_fleet.py` (still exactly the
physics hull below the waterline: `SailingSim.Visual.FleetMesh`), rebuilt with
`scripts\windows\make-boat-models.ps1 -Parts fleet -Fleet <Tag>`. (The Sunfish is on its own branch, sunfish-hero.)

## Catalina 22

- **Cabin trunk:** the class's two smoked windows a side with rounded ends in aluminium frames, in place of the generic
  window band; a teak eyebrow along both edges of the trunk top.
- **Companionway:** three teak drop boards, their edges proud, in place of the black stand-in.
- `import_boats.py fleet` imports only the seven fleet boats (it had re-imported the maxi whenever her FBX was in
  `Artifacts\models`).

![Before (left), after (middle) and the deck from above (right), Ultra on the lake](catalina22-before-after.jpg)
