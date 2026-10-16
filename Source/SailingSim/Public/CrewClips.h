#pragma once

#include "CoreMinimal.h"
#include "CrewPose.h"

/**
 * Crew C1b: idles from motion capture under the reaction layer (CrewMotion.h). Small clips of real people waiting,
 * shifting their weight, looking round and sitting (CMU Graphics Lab, Tools/crew/clips.csv, baked by
 * Tools/crew/bake_idles.py into CrewClipData.inl) play as motion about the stance: each joint's turn about the posture it
 * was held in, in the character frame, so the stance stays the base pose and the clip only moves the sailor about it. A
 * MetaHuman takes the same turns through FCrewRig. The layer chooses clips per sailor (seeded, mirrored half the time),
 * crossfades between them, starts a weight shift in step with a change of heel, and goes quiet while the sailor moves (a
 * tack's crossing, a change of seat, bracing, ducking) or hangs from a line.
 */
enum class ECrewClipKind : uint8 { Standing, Seated };

struct FCrewClipInfo
{
	const TCHAR* Label;
	const TCHAR* Trial;     // CMU subject_trial
	ECrewClipKind Kind;
	bool bArms;             // the arms move too (else trunk and gaze only)
	int32 Frames;
	int32 Offset;           // into the value table
	int32 OnsetBegin, OnsetCount;
};

/** A weight shift's start in a clip: the trunk's lean begins a move toward the sailor's right or forward (+1), or the
 *  other way (-1); Axis 0 sideways, 1 fore and aft. */
struct FCrewClipOnset
{
	int32 Frame;
	int32 Direction;
	int32 Axis;
};

namespace CrewClips
{
	constexpr int32 MaxJoints = 11;
	SAILINGSIM_API int32 Num();
	SAILINGSIM_API const FCrewClipInfo& Info(int32 Clip);
	SAILINGSIM_API const FCrewClipOnset& Onset(int32 Index);
	SAILINGSIM_API float Duration(int32 Clip);
	SAILINGSIM_API float Rate();
	SAILINGSIM_API int32 NumJoints();
	SAILINGSIM_API FName JointName(int32 Joint);
	/** How far the layer may turn a joint from the stance (degrees). */
	SAILINGSIM_API float LimitDeg(int32 Joint);
	/** The gaze's limits (degrees): [0] yaw, [1] pitch. */
	SAILINGSIM_API float GazeLimitDeg(int32 Axis);
	/** A clip at T seconds (Catmull-Rom between frames): each joint's rotation vector (radians, character frame) and the
	 *  gaze's yaw (+ right) and pitch (+ up), degrees. Mirrored, left and right swap. */
	SAILINGSIM_API void Sample(int32 Clip, float T, bool bMirror, FVector* OutJoints, float& OutYaw, float& OutPitch);
	/** The trunk's lean (degrees) for pelvis, spine and chest rotation vectors: Axis 0 toward the sailor's right, 1 forward. */
	SAILINGSIM_API float TrunkLean(const FVector* Joints, int32 Axis = 0);
}

struct FCrewClipCursor
{
	int32 Clip = -1;
	float T = 0.f;
	bool bMirror = false;
};

struct SAILINGSIM_API FCrewClipInput
{
	ECrewStance Stance = ECrewStance::Cockpit;
	float Hike = 0.f;
	bool bQuiet = false;            // moving (crossing, changing seat), bracing or ducking: the clip lets go
	float Roll = 0.f;               // rad, the sailor's balance (FCrewBalance::Roll: + tipping toward their right;
	float Pitch = 0.f;              //   Pitch: + tipping forward). Heel changes either, by which way they face.
	uint32 Seed = 0;
};

/** One sailor's clip layer, kept between frames. */
struct SAILINGSIM_API FCrewClipState
{
	FCrewClipState() { for (FVector& J : Joints) J = FVector::ZeroVector; }

	FCrewClipCursor Cur, Next;
	float Blend = 1.f;              // 0..1 into Next while a crossfade runs (1: none)
	float BlendSeconds = 1.f;
	float Activity = 0.f;           // 0 quiet .. 1 playing, ramped (the weight is its minimum-jerk curve)
	float Cooldown = 0.f;           // s before another heel-matched shift
	uint32 Rng = 0;
	bool bStarted = false;
	int32 HeelShifts = 0;           // weight shifts started on a change of heel
	int32 LastShiftDirection = 0;   // +1 toward the sailor's right or forward
	int32 LastShiftAxis = 0;
	float TiltF[2][3] = {};         // roll and pitch through three 1 s lags: their slow trend, not the chop
	float TiltTrend[2] = {};        // rad/s

	// Out, after each step: the joints' turns (radians, character frame, weighted and within the limits) and the gaze.
	FVector Joints[CrewClips::MaxJoints];
	float GazeYaw = 0.f, GazePitch = 0.f;
	float Weight = 0.f;
	float Lean[2] = {}, LeanRate[2] = {}; // the trunk's lean from the layer (deg, deg/s): [0] + right, [1] + forward
};

/** How strongly a stance takes the clips (0 for the stances that hang from a line or move). */
SAILINGSIM_API float CrewClipStanceWeight(ECrewStance Stance, float Hike);
SAILINGSIM_API void CrewClipStep(FCrewClipState& S, const FCrewClipInput& In, float Dt);
