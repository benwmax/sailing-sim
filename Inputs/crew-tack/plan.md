# Crew arms and tacking plan (Oct 27 2026)

Bean's playtest: crew elbows bend backwards, and crossing the cockpit on a tack or gybe looks nothing like real
sailors. Full write-up with sources: https://claude.ai/artifact/CZUcZMxRydCzYmDQ88NfKT (Claude Doc). This file is the
brief for the Mac lane. Three PRs, in order, each one PR against main, `--scope crew` gate.

## PR 1: hinge-aware arm solver (`crew-elbow`)

Diagnosis: every held hand (tiller extension, sheets, wheel, knee, handhold on a brace) goes through
`CrewSolver::ReachArm` (`Source/SailingSim/Private/CrewPose.cpp` ~line 209). It is two-bone IK with no hinge: the
elbow is put in "the plane the stance had it in" and the upper arm and forearm are turned there with two
`FQuat::FindBetweenVectors`. So (1) when the target is on the other side of that plane the forearm folds the wrong
way (hyperextension), (2) the second rotation adds twist about the elbow, (3) the held-line swing (K = -6..6, 60 deg
about the shoulder-wrist axis) walks the elbow freely round that axis with only "not above the shoulder" as a limit.
A Python rebuild of the solver with the J/22 arm (28 + 26 cm) and the seated stances' arm angles gives, for random
reachable targets on the sailor's own side: ~50% elbows bent backwards (flexion < -3 deg), ~68% with > 20 deg of
off-hinge bend; 3-25% when the target is within 30 deg of the stance's own wrist, 60-97% past 120 deg. Legs use the
same function (PlantFeet, brace, strap), so knees too. The CMU idle clips add free rotation vectors to forearm_*
before the IK; nothing removes their off-hinge part.

Fix (same signature and callers, one optional hinge argument):

1. Hinge from the rig, not the old elbow: `h = D[Upper].RotateVector(Frame.RotateVector(Up))`, sign per side as
   `Elbow(bLeft, deg)` (+Z left, -Z right); flexion positive toward the palm. Knee: the character's right axis carried
   by the thigh (`KneeBend`), flexion positive backwards.
2. Elbow plane from the hinge: `Y = normalize(h x X)` signed so flexion is positive. The stance's elbow plane becomes
   a pole swing of the hinge about X, at most +-45 deg from the rig's rest hinge, nearest the stance's elbow. The
   held-line search keeps 10 deg steps inside that band; "elbow not above the shoulder" stays.
3. Forearm turns about the hinge only: phi = acos((A^2 + B^2 - Dist^2) / 2AB) clamped 0..145 (knee 0..150); forearm
   local = Elbow(bLeft, phi - phiRest). Upper arm by aim-with-up (like `Aim()` in CrewMotion.cpp): (upper-arm dir,
   hinge) -> (E2 - S, Y).
4. Out of reach: keep the A + B - 0.5 clamp; straight arm, hand falls short. Project any clip rotation on forearm_*
   onto the hinge before solving.
5. Test `SailingSim.Visual.CrewElbow`: each MetaHuman rig and SK_Sailor, 500 random targets in the reach sphere, both
   arms and legs: flexion 0..145 (knee 0..150), off-hinge < 3 deg, hand within 2 cm when reachable. CrewHeldLine (18)
   and fleet stills must still pass. Stills: J/22 helm and trimmer at 12 kn, 25 deg heel, cockpit camera and abeam,
   before/after, `docs/crew-elbow/`.

Risk: elbows move, so RigClearance / CrewHullClip may shift a little; the +-45 band keeps them near today's.

## PR 2: the crossing script (`crew-cross`)

Today: `CrewPlacement` (CrewMotion.cpp) makes a tack one stance, `ECrewStance::Crossing` (fixed crouch, legs 75/112,
spine 25-45 fwd), facing the new side, blended in 0.45 s / out 0.6 s, pelvis moved by the crew model's CrewOffset and
lowered by Duck. No steps, no hand reaches, no handholds, yaw jumps. That reads as a mannequin slid across.

What real crews do (sources in the doc): stay on the old windward side until head to wind; trimmer lets the old sheet
run as the jib backs, crosses low under the boom with the new sheet's tail, hauls hand over hand while the jib is
soft, grinds the last bit; forward hand crosses with them, lowest, hand on the cabin handrail/coaming; helm faces
forward the whole time, slides aft of the traveler in a half-crouch, sits, THEN swaps hands behind the back (old
mainsheet hand takes the extension, freed hand picks the mainsheet from the cam). 4-6 s helm's-a-lee to settled on
a 22-footer. Gybe: crouch low BEFORE the boom moves, hold still as it passes (0.3-0.5 s), then cross to the side away
from the boom. Dinghies: 1.5-2.5 s rail to rail, extension passed in front. Roll tack in light air: delay the cross
until head to wind, cross together, hike hard on the new side.

Script (t = 0 when the boom starts across the centreline, predicted from BoomRate; pelvis heights above the sole):

| Phase | t (s) | Body | Feet | Hands | Head |
|---|---|---|---|---|---|
| A Set | -1.2..-0.8 | trunk upright, pelvis 10 cm inboard | fwd foot flat on sole under knee; aft foot on seat | aft hand to coaming/cabin rail by hip | turns fwd to the jib |
| B Rise+turn | -0.8..-0.3 | half-crouch, pelvis 0.55 m, hips 90 deg to face fwd, spine 45 fwd | aft foot down to sole (step 1) | aft hand pushes off seat then lifts; sheet hand holds | below boom, eyes fwd |
| C Cross | -0.3..+0.7 | two steps, knees 90-110, pelvis 0.5-0.55, trunk 50-60 fwd, deepest at t = 0..+0.3 | each step 0.3 s, 12 cm arc, 0.4-0.5 m, other foot planted | free hand sweeps to far coaming/traveler bar/cabin rail, takes it at +0.4 | lowest at 0, lifts to new luff |
| D Sit | +0.7..+1.3 | hips 90 deg to face inboard; pelvis down to 0.4 then seat | both feet on sole or new leeward seat | handhold until seated; trimmer first pull | up, fwd |
| E Settle | +1.3..+3.0 | RailHike lean with Hike | brace as RailHike | back to job; trimmer 3-4 pulls then grind | luff and water ahead |

Variants: Helm: no rise, slide aft of the traveler facing fwd, pelvis <= 0.6 m, two shuffle steps, sit facing
fwd-inboard; hand swap at +1.3..+2.0 (behind the back); extension stays in the old aft hand through B-D. Gybe: A and B
at -2.0..-1.0, pelvis 0.45, chin to knees, hold still -0.2..+0.3, then C-E. Dinghy: 0.65x durations, extension in
front, Sunfish/ILCA pelvis 0.3 with Stoop. Light air (TWS < 8 kn): delay A 0.5 s, hike hard 1 s on E.

Implementation:

1. `FCrewCrossing` in `FCrewMotionState`: phase A-E, clock, from/to sides, tBoom (BoomAngle / BoomRate clamped
   0.2..2 s, re-estimated until the boom passes), variant, two foot anchors (boat frame), swing-foot flag.
2. `CrewPlacement` starts it where it sets Crossing today, reports tBoom, keeps the pelvis on the old side until B;
   CrewOffset still gives the destination. Pelvis height per phase from the table, min-jerk within each phase; Duck
   still clamps it under a low boom.
3. Facing: B turns yaw inboard -> forward over 0.5 s, D forward -> inboard on the new side (two transitions on the
   existing F.Yaw min-jerk lerp).
4. Feet: two anchors on the sole 0.25 m apart fore-aft (CrewFloorZ). A step moves one anchor 0.4-0.5 m over 0.3 s on
   a 12 cm arc; the other stays. Each foot reaches its anchor with the hinge-aware ReachArm leg solve. Keelboats two
   steps, dinghies one.
5. Hands: A-C aft hand on Attach.HandholdCoaming[old side] (HandholdCabin for the forward hand); C-D free hand on
   HandholdCoaming[new side]; trimmer's sheet hand keeps Along on the jib sheet; helm keeps TillerExtTip. All through
   FCrewHands reach mode.
6. Head: existing gaze/level code plus a cap: head top 0.15 m under BoomZ while |BoomAngle| < 30 deg under the boom.
7. Idle clips stay quiet (already so). Timings in one struct for tuning from stills.

Tests (CrewMotionTests.cpp already fakes a tack at 6 s in CrewClipTack): `SailingSim.Visual.CrewTack`, scripted J/22
tack and gybe at 8 and 16 kn: head top < BoomZ - 0.1 while the boom is within 30 deg of centre; pelvis inside the
well; elbows/knees within hinge limits; a non-swinging foot's sole points on sole or seat within 2 cm; hands within
3 cm of handhold/line while assigned; after +3 s the pose matches CrewPlacement's stance. Fleet hull-clip and rig
tests keep listing crossing frames as transient; the count per crossing must not grow. Stills: 12-frame strip at
0.25 s from the cockpit camera and abeam, J/22 tack and gybe plus the ILCA tack, `docs/crew-tack/`.

## PR 3: helm hand swap, gybe, roll tack (`crew-cross-2`)

The behind-the-back swap as a 0.7 s hand sequence in phase E; the gybe variant's early deep crouch; the light-air
roll-tack delay.

## Process

Standalone crew tests before each gate; push every commit before starting a gate; never commit while a gate runs
(gate.sh checks out its own merge branch). Bean may send a phone clip of a tack and gybe (optional); until then the
timings above stand.
