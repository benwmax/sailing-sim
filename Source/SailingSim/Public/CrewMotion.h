#pragma once

#include "CoreMinimal.h"
#include "CrewPose.h"
#include "CrewClips.h"

namespace Sailing { struct FBoatConfig; }
struct FReferenceSkeleton;

/**
 * Crew C1: the crew move with the boat. The stance poses (CrewPose.h) are the base; on top a physics reaction layer
 * (each sailor balances against the gravity they feel at their seat, with a human lag), breathing and sway, a gaze,
 * arm tension, bracing past the tipping limit, a give on a bow slam, and tacks timed to the boom with a duck under it.
 * The pose is computed on the animation worker threads by FAnimNode_CrewMotion (CrewAnimInstance.h); everything here
 * is plain logic so the tests can drive it without a world.
 */

/**
 * docs/crew-tack/: one sailor's crossing on a tack or gybe, timed to the boom as real crews do it (the doc's sources):
 * on the old side until the boom nears the centreline (A, set), up into a half-crouch facing forward (B), across low in
 * two steps with a hand on the coaming (C, deepest as the boom passes), turning and sitting on the new side (D), then the
 * stance takes over (E). Tau is the time from the boom crossing the centreline, re-estimated from its swing until it
 * has; a gybe sets and crouches earlier and holds still as the boom passes; a dinghy's crossing takes 0.65 of the time.
 * Kept by the caller between frames (the pawn, per figure; the tests).
 */
struct SAILINGSIM_API FCrewCrossing
{
	bool bActive = false;
	bool bGybe = false;
	bool bBoomPassed = false;
	float Clock = 0.f;                       // s since the crossing began
	float Cooldown = 0.f;                    // s before another may start
	float TBoom = 1.2f;                      // s from its start to the boom at the centreline
	float Scale = 1.f;                       // a dinghy's crossing is quicker
	float StartBoomSign = 0.f;
	FVector From = FVector::ZeroVector;      // the pelvis where it began (m, boat frame)
	float FromYaw = 0.f;
	double ToX = 0.0;                        // m, where the cross goes fore and aft (taken as it begins)
	FVector Last = FVector::ZeroVector;      // the last placement (the next crossing starts from it)
	float LastYaw = 0.f;
	bool bHasLast = false;
	/** Seconds from the boom crossing the centreline, in the script's own time (a dinghy's runs faster). */
	float Tau() const { return (Clock - TBoom) / FMath::Max(Scale, 0.1f); }
	/** The phase's end (tau) after which the stance takes over. */
	float EndTau() const { return bGybe ? 1.9f : 1.3f; }
};

/** Where a sailor sits and which stance they take: shared by ASailboatPawn::UpdateCrewFigures and the tests. */
struct SAILINGSIM_API FCrewPlaceInput
{
	const Sailing::FBoatConfig* Config = nullptr;
	int32 Index = 0;               // figure index; the helm is the last
	double CrewOffset = 0.0;       // m, FBoatState::CrewOffset (+ starboard)
	double CrewOffsetZ = 0.0;
	double CrewOffsetX = 0.0;      // m, FBoatState::CrewOffsetX (+ forward: a dinghy sailor slides aft on the plane)
	int32 WindwardSide = 1;
	double OffsetRate = 0.0;       // m/s, how fast the crew model is moving them across
	bool bRighting = false;        // capsized and righting
	double BoomAngle = 0.0;        // rad, + starboard
	double BoomRate = 0.0;         // rad/s
	double TrueWindAngle = 0.5;    // rad, FBoatTelemetry::TrueWindAngle (+ from starboard)
	double TurnRate = 0.0;         // rad/s, yaw (+ bow to starboard)
	FCrewCrossing* Crossing = nullptr; // docs/crew-tack/: the scripted crossing's state (none: the crossing stance as before)
	float Dt = 0.f;                // s since the last placement (the crossing's clock)
};

struct SAILINGSIM_API FCrewPlacement
{
	FCrewPoseParams Params;
	FVector Pelvis = FVector::ZeroVector;   // m, boat frame
	float Yaw = 0.f;                        // deg, boat frame
	float Roll = 0.f;
	float Duck = 0.f;                       // 0 upright .. 1 crouched as low as the stance goes, under the boom
	bool bHelm = false;
	// docs/crew-tack/: a scripted crossing: where it is (tau, s from the boom at the centreline), the feet's anchors on the
	// floor (ankles, m, boat frame; [0] left, [1] right) and how much they hold, and the coaming the free hand takes
	// ([0] starboard, [1] port; -1 none) with which hand (0 left, 1 right).
	bool bScripted = false;
	float Tau = 0.f;
	FVector FootAnchor[2] = { FVector::ZeroVector, FVector::ZeroVector };
	float FootWeight = 0.f;
	int32 HoldSide = -1;
	int32 HoldHand = 0;
};

/** The stance and place (the boom's swing over the cockpit sets when the crew cross and how low they go). */
SAILINGSIM_API void CrewPlacement(const FCrewPlaceInput& In, FCrewPlacement& Out);

/** How long a change of stance takes (s): crossing a tack is quick, settling into a new seat slower. */
SAILINGSIM_API float CrewTransitionSeconds(ECrewStance From, ECrewStance To);
/** Minimum-jerk blend weight (0..1) over a transition: no sudden start or stop. */
inline float CrewMinJerk(float S) { S = FMath::Clamp(S, 0.f, 1.f); return S * S * S * (10.f + S * (-15.f + 6.f * S)); }

/** How the boat moves (boat frame, SI): for the gravity a sailor feels at their seat. */
struct SAILINGSIM_API FCrewBoatMotion
{
	FVector Gravity = FVector(0.0, 0.0, -9.81); // the boat heels and pitches under it
	FVector Accel = FVector::ZeroVector;        // centre of gravity (FBoatTelemetry::AccelBody)
	FVector Omega = FVector::ZeroVector;        // turn rate (FBoatState::AngularVelocity)
	FVector Alpha = FVector::ZeroVector;        // FBoatTelemetry::AngularAccelBody
};

/** Felt gravity at R (m from the centre of gravity, boat frame): g - (a + alpha x r + omega x (omega x r)). */
SAILINGSIM_API FVector CrewFeltGravity(const FCrewBoatMotion& M, const FVector& R);

/**
 * One sailor's balance: the felt gravity's tilt in the sailor's own frame (X facing, Y right, Z up) and its load,
 * seen after a human reaction lag, tracked by critically damped springs (they settle without overshoot).
 */
struct SAILINGSIM_API FCrewBalance
{
	float Lag = 0.18f;          // s, reaction time (0.1 to 0.3 by sailor)
	float Omega = 9.f;          // rad/s, the lean spring (2 % settling in 5.8/Omega after the lag)
	float SquatOmega = 14.f;    // the knees and spine give and recover faster
	// Response, radians: roll toward the sailor's right (+), pitch forward (+); Squat: extra load in g (a slam > 0).
	float Roll = 0.f, Pitch = 0.f, Squat = 0.f;
	float RollV = 0.f, PitchV = 0.f, SquatV = 0.f;

	void Reset(const FVector& FeltLocal);
	void Step(float Dt, const FVector& FeltLocal);
	/** The input as it was Lag ago (interpolated). */
	FVector Delayed() const;

	/** The felt gravity's tilt (roll, pitch) and load for an input in the sailor's frame. */
	static void Decompose(const FVector& FeltLocal, float& OutRoll, float& OutPitch, float& OutLoad);

private:
	struct FSample { double T; FVector V; };
	TArray<FSample> History;
	double Clock = 0.0;
	bool bStarted = false;
};

/** Critically damped spring step toward a fixed target over Dt (exact: stable for any step). */
SAILINGSIM_API void CrewSpring(float& X, float& V, float Target, float Omega, float Dt);

/** Named attach points the crew use (J22H_sockets.json names), boat frame, cm. */
struct SAILINGSIM_API FCrewAttachPoints
{
	FVector HandholdCabin[2], HandholdCoaming[2], Seat[2], FootBrace[2], SideDeck[2]; // [0] starboard, [1] port
	FVector CockpitSole = FVector::ZeroVector;
	bool bValid = false;
};
/** Derived from the physics geometry (the cockpit well, the deck, the cabin) at a station, for a model without sockets. */
SAILINGSIM_API void CrewDerivedAttachPoints(const Sailing::FBoatConfig& Config, double X, FCrewAttachPoints& Out);

/** What the game thread hands one sailor's animation each frame (all in the boat frame, cm, unless noted). */
struct SAILINGSIM_API FCrewMotionInput
{
	FCrewPoseParams Params;
	int32 Transition = 0;                   // bumped on every change of stance
	float TransitionSeconds = 0.6f;
	float Duck = 0.f;
	FTransform ToBoat;                      // the figure's component frame to the boat frame (cm)
	FCrewBoatMotion Motion;
	FVector SeatFromCG = FVector::ZeroVector; // m, boat frame
	FCrewHands Hands;                       // reach targets in the figure's component frame; Ground filled by the node
	float Tension[2] = { 0.f, 0.f };        // 0..1, the load on what each hand holds (helm force, sheet load)
	FVector Gaze = FVector::ZeroVector;     // where they look (boat frame, cm); zero: ahead
	FCrewAttachPoints Attach;               // handholds and braces
	// docs/crew-tack/: a scripted crossing's foot anchors (boat frame, cm) and their weight (0: the stance's feet).
	FVector FootAnchor[2] = { FVector::ZeroVector, FVector::ZeroVector };
	float FootWeight = 0.f;
	float Time = 0.f;                       // s, the game clock (breathing and sway)
	uint32 Seed = 0;
	bool bReact = true;                     // the reaction layer (off: the stance alone, as before C1)
	bool bClips = true;                     // C1b: the motion-capture idles under it (CrewClips.h)
	bool bTravelerBridge = true;            // the drawn model has the cockpit's traveler bridge (FCrewGround)
};

/** What the posing found, for the tests and the debug log. */
struct SAILINGSIM_API FCrewMotionReport
{
	bool bBracing = false;
	float TipRatio = 0.f;                   // felt tilt's tangent over the tipping limit's
	float HeadTiltDeg = 0.f;                // the head's up from the world's up
	FVector Felt = FVector::ZeroVector;     // felt gravity, the sailor's frame
	float ClipWeight = 0.f;                 // C1b: how much of the idle clip is playing
	int32 Clip = -1;
};

/** One sailor's motion state, kept between frames (owned by the animation node). */
struct SAILINGSIM_API FCrewMotionState
{
	FCrewBalance Balance;
	FCrewClipState Clip;                    // C1b
	TMap<FName, FQuat> Current, From;       // the stance joints as blended, and where the last transition started
	int32 Transition = -1;
	float TransitionS = 1.f;
	FVector GazeDir = FVector::ForwardVector; // boat frame, smoothed
	FVector GazeV = FVector::ZeroVector;
	float BraceHold = 0.f;                  // s left of the current brace
	bool bBracing = false;
	bool bStarted = false;
	TArray<FTransform> Rest;                // rest pose (no rig), cached
	FCrewMotionReport Report;
};

/**
 * Advances a sailor's motion by Dt and poses the skeleton (component space, cm). The base stance from CrewPose, the
 * reaction layer, then the feet (brace, planted on the boat), the hands (holds, knee, brace) and the head (level, gaze).
 */
SAILINGSIM_API void CrewMotionUpdate(FCrewMotionState& State, const FCrewMotionInput& In, float Dt);
SAILINGSIM_API void CrewMotionPose(const FReferenceSkeleton& Ref, const FCrewRig* Rig, const Sailing::FBoatConfig* Config, double HullDepth,
	FCrewMotionState& State, const FCrewMotionInput& In, TArray<FTransform>& OutCS);
/** Each shoe's heel and toe on its sole (component space, cm) in a posed skeleton: [0 left, 1 right][0 heel, 1 toe]. */
SAILINGSIM_API void CrewSolePoints(const FReferenceSkeleton& Ref, const FCrewRig* Rig, const TArray<FTransform>& CS, FVector Out[2][2]);
