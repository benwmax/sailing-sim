# The helm-eye capture at the helm's head

**The symptom:** in every `-SailingCapture=HelmEye` still (the gate's `helm-eye` bench view and the reference
scenes), the bottom third of the frame was black: the camera looked down into the hero J/22's dark cabin
(`helm-*-before.jpg`).

**Why:** `OnboardCameraMount` puts the helm's eye at the aftmost crew place, guessed from the physics crew centre
(`CrewCG.X - 0.55 (n - 1) / 2 + 0.1`). On the J/22 that is about where the hero's cabin ends, so the eye stood over the
companionway, not at the tiller. The player's cockpit view had the same guess and already corrects it from the helm
figure's head bone (`docs/cockpit-eye/`); the capture never did.

**Fix:** the capture's eye is the helm's own head, as the cockpit view's:
- 10 cm ahead of the head bone and 8 cm above it;
- in the boat's frame;
- the figure hidden, but still posed;
- the mount's look kept: forward and 12 deg to leeward, toward the jib luff.

`OnboardCameraMount` stays as the fallback (no crew figure) and is what `SailingSim.Reference` holds.

**Now** (`helm-*-after.jpg`): the eye is aft in the cockpit. You see the cabin's aft face and companionway as they are,
and the trimmer close ahead, the same picture as the player's cockpit view (`\`).

**Note:** the gate's `helm-eye` view now has crew in frame, so its frame time is not comparable with earlier gates.
