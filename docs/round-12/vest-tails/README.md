# Vest strap tails: a cut end (round 12 follow-up)

The life jacket's three loose strap ends (round 11: 15 to 20 cm of webbing out of each chest buckle's adjuster) ended
in a flat square slab, which read as a cut-off box at close range. `Tools/blender/build_vest.py`'s `tail()` now ends
each one as webbing is cut, with a hot-knife point 14 mm long: the ribbon's corners fold in to a tip on the strap's line,
both faces meeting the two cut edges. Nothing else on the vest changes (25,300 triangles a vest, as before; 3 tails).

The MetaHuman exports stay git-ignored: rebuild with `scripts/make-crew-clothes.sh` (`PIECES=Vest` imports only the
vests). On the PC: Blender `build_vest.py` per role, then `run-python.ps1 import_crew_clothes.py` with `PIECES=Vest`.

## Stills (left main, right this branch)

- `tail-mesh-before-after.jpg`: the shipped vest mesh (the helm's) in Blender, front, the lower tail across the strap.
- `crew-inboard-before-after.jpg`: in game, High, uncooked (`run-game.ps1`), the trimmer and bow from inside the cockpit
  (`-SailingCamTarget=-1.0,0.8,0.85 -SailingCamDist=1.1 -SailingCamYaw=110 -SailingCamPitch=0 -SailingCrewStill`,
  10 kn at 45 degrees, 15:00). The crew's forearms cover the tails from every seated camera tried (round 11 found the
  same), so the mesh still is the one that shows the cut; this one shows nothing else changed.
