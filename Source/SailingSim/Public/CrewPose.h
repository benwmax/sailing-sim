#pragma once

#include "CoreMinimal.h"

class UPoseableMeshComponent;

/**
 * Visual V3: the crew's poses (SK_Sailor, Tools/blender/build_crew.py), from the physics crew model.
 *
 * A stance is picked from the boat and the crew state (BoatModelVisuals: where the crew sits, how hard they hike,
 * whether they are crossing on a tack, on the wire, or righting a capsize), and each stance is a set of joint rotations
 * in the character's own frame (X the way the sailor faces, Y to their right, Z up), applied to the skeleton by forward
 * kinematics from its reference pose. Keelboat crews sit on the windward rail facing outboard with their legs over the
 * side and lean out over the lifeline; the helmsman sits aft on the windward deck facing forward on the tiller
 * extension; in light air or downwind they sit in the cockpit; on a tack they cross crouched; dinghy sailors hike from
 * the straps facing inboard, leaning back; the Hobie crew stands on the rail on the trapeze; to right a capsized dinghy
 * the sailor stands on the board leaning back.
 */
enum class ECrewStance : uint8 { RailHike, Helm, Cockpit, Crossing, DinghyHike, Trapeze, Righting };

struct SAILINGSIM_API FCrewPoseParams
{
	ECrewStance Stance = ECrewStance::Cockpit;
	float Hike = 0.f;       // 0 sitting up .. 1 hiked hard (or flat out on the wire)
	float Side = 1.f;       // +1 the sailor is on the starboard side, -1 port
};

/** Joint rotations for a stance (character frame, applied about each joint, parent first). */
SAILINGSIM_API void CrewJointRotations(const FCrewPoseParams& Params, TMap<FName, FQuat>& Out);

/** The yaw (deg, boat frame) the sailor faces for a stance: outboard, forward, inboard. */
SAILINGSIM_API float CrewFacingYaw(const FCrewPoseParams& Params);

/** Poses the skeleton: forward kinematics from the reference pose with the joint rotations (missing joints rest). */
SAILINGSIM_API void ApplyCrewPose(UPoseableMeshComponent* Mesh, const TMap<FName, FQuat>& Joints);

/** Component-space joint positions of the reference skeleton posed with the rotations (cm): for the tests. */
SAILINGSIM_API void CrewPosedJoints(const class USkeletalMesh* Mesh, const TMap<FName, FQuat>& Joints, TMap<FName, FVector>& OutPositions);
