# The J/22's rail crew: feet in the well, not on the cabin

**The symptom:** on a beat, a crew member's leg was raised onto the cabin top right across the helm's view
(`helm-beat-before.jpg`). It is the same with `-SailingCrewStill` and `-SailingNoCrewClips`, so it is the stance itself.

**Why:** on a beat the J/22's bow and trimmer sit on the windward side deck facing inboard (RailHike), legs down into the
cockpit well. Their fore-and-aft place came from the crew model, clamped only to the well's forward end less 0.12 m:
the bow at x -0.84, the trimmer at -1.30. On the hero J/22, the bow's feet came up against the cabin face, and the
trimmer's onto the bridge deck at the well's forward end. (The physics well ends at -0.72; `-SailingDebugCrew` now logs
it.)

**Fix:** the J/22's rail crew sit aft of the well's end:
- the bow 0.55 m aft of it, at -1.27;
- the trimmer 0.5 m behind that, at -1.77;
- the helm stays at -2.26.

This is visual only: the physics crew moment is unchanged. Their feet now go down into the well
(`crew-top-after.jpg`). In the player's cockpit view, the crew sit beside the helm on the rail with the view forward
clear (`cockpit-beat-after.jpg`).

**Also fixed:** the helm-eye capture always hides the helm's own figure, as the cockpit view does. Its origin is the
boat's, so the 2.2 m rule had left it drawn.

**Gate baseline:** the `helm-eye` view (High) is about 60 fps again. On its beat, the rail crew are now within 2.2 m of
the eye and hidden. With #239 alone, which put the eye at the helm's head, it was 55 (`docs/bench-fast/`).
