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

/**
 * Visual V7: how a skeleton other than SK_Sailor's takes the same poses (the MetaHuman crew). Its frame (a MetaHuman faces
 * +Y), the bones each sailor joint spreads over (spine over spine_01..02, chest over spine_03..05, neck over
 * neck_01..02, forearm to lowerarm) and its reference pose turned into SK_Sailor's T-pose (a MetaHuman stands in an
 * A-pose), so every stance's rotations mean the same on both.
 */
struct SAILINGSIM_API FCrewRig
{
	bool bValid = false;
	FQuat Frame = FQuat::Identity;              // character frame (X facing, Y right, Z up) to the mesh's component frame
	TArray<FTransform> RestCS;                  // the T-posed reference, component space
	TMap<FName, TArray<TPair<FName, float>>> Map;
	FVector Pelvis = FVector::ZeroVector;       // T-posed rest pelvis (cm, component space)

	/** The rest transform of a bone (component space, T-posed); identity if it has none. */
	FTransform Rest(const class USkeletalMesh* Mesh, FName Bone) const;
};

/** The MetaHuman crew's roles (scripts/make_metahumans.py): 0 the helm, 1 the trimmer, 2 the bow. */
constexpr int32 NumMetaHumanRoles = 3;
SAILINGSIM_API const TCHAR* MetaHumanRoleName(int32 Role);

/** Loads a role's built MetaHuman (body, face, outfit under /Game/Crew/MetaHumans, git-ignored); false if not built. */
SAILINGSIM_API bool LoadMetaHumanCrew(int32 Role, class USkeletalMesh*& Body, class USkeletalMesh*& Face, class USkeletalMesh*& Outfit);
/** Graphics G3: a MetaHuman's grooms (hair, brows, beard) with their face bindings, from its Grooms folder. */
SAILINGSIM_API void LoadMetaHumanGrooms(int32 Role, TArray<TPair<class UGroomAsset*, class UGroomBindingAsset*>>& Grooms);

/** Builds the rig for a skeleton (identity for SK_Sailor's own). */
SAILINGSIM_API void BuildCrewRig(const class USkeletalMesh* Mesh, FCrewRig& Out);

/** Poses the skeleton: forward kinematics from the reference pose with the joint rotations (missing joints rest). With
 *  a rig, the sailor's joints are carried to its skeleton first. */
SAILINGSIM_API void ApplyCrewPose(UPoseableMeshComponent* Mesh, const TMap<FName, FQuat>& Joints, const FCrewRig* Rig = nullptr);

/** Component-space joint positions of the reference skeleton posed with the rotations (cm): for the tests. */
SAILINGSIM_API void CrewPosedJoints(const class USkeletalMesh* Mesh, const TMap<FName, FQuat>& Joints, TMap<FName, FVector>& OutPositions,
	const FCrewRig* Rig = nullptr);
