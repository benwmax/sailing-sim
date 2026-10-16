#pragma once

#include "CoreMinimal.h"

namespace Sailing { struct FBoatConfig; }

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
	// Graphics G8: per finger bone, the component-space axis (rest pose) a positive turn about which curls it toward the palm.
	TMap<FName, FVector> CurlAxis;

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

/**
 * Graphics G8: where the hands go once the stance is posed (round 8: open hands held in the air read as a mannequin).
 * Reach puts the palm on a point (component space of the posed mesh, cm: the tiller extension, a sheet) by two-bone IK
 * from the shoulder, keeping the stance's elbow plane; Knee rests it on that side's knee. Grip curls the fingers (rigs
 * with finger bones): 0 open, about 0.3 relaxed, 1 closed round a line.
 */
/**
 * Crew pose fix (round 8/9: the helm's foot came out through the J/22's topsides): what the crew stand on. The boat's
 * deck in its own frame (m): the side decks at the sheer, the cockpit well's seats and sole (from the Blender builds:
 * Tools/blender/build_j22.py, build_fleet.py SPECS), and the solid boat under them. With a ground, a foot the stance
 * would put inside the boat is planted on the floor above it (or brought inboard into the well) by two-bone IK on the
 * leg, keeping the stance's knee plane.
 */
struct SAILINGSIM_API FCrewGround
{
	const Sailing::FBoatConfig* Config = nullptr;
	double HullDepth = 0.25;    // m, FBoatModel::HullDepth
	FTransform ToBoat;          // the figure's component frame to the boat frame (cm)
	bool bSeated = false;       // round 12: sitting, so a foot hanging a little over the floor goes down onto it
};

/** The cockpit well of a class (m, boat frame): open above the seats and the sole. False for the cats (nets). */
struct SAILINGSIM_API FCrewCockpitWell
{
	double X0 = 0.0, X1 = 0.0;   // aft and forward ends
	double SideDeck = -1.0;      // the J/22: the well runs to the deck edge less this; else HalfWidth
	double HalfWidth = 0.0;
	double SeatZ = -1.0, SeatW = 0.0, SoleZ = 0.0;
};
SAILINGSIM_API bool CrewCockpitWell(const Sailing::FBoatConfig& Config, FCrewCockpitWell& Out);
/** The surface a foot stands on at (X, Y) (m, boat frame): seat or sole in the well, the deck elsewhere; -1e9 off the boat. */
SAILINGSIM_API double CrewFloorZ(const Sailing::FBoatConfig& Config, double X, double Y);
/** Is a point (m, boat frame) inside the solid boat: under the deck, inside the topsides, not in the cockpit well? */
SAILINGSIM_API bool CrewInsideBoat(const Sailing::FBoatConfig& Config, double HullDepth, const FVector& P);

struct SAILINGSIM_API FCrewHands
{
	enum class EMode : uint8 { Free, Reach, Knee };
	EMode Mode[2] = { EMode::Free, EMode::Free };          // [0] left, [1] right
	FVector Target[2] = { FVector::ZeroVector, FVector::ZeroVector };
	float Grip[2] = { 0.3f, 0.3f };
	// Round 12: for Reach, the line or bar through the palm (component space; the tiller extension, a sheet's tail, a
	// handrail): the wrist turns so it runs across the palm, knuckle to knuckle. Zero leaves the wrist as the stance has it.
	FVector Along[2] = { FVector::ZeroVector, FVector::ZeroVector };
	const FCrewGround* Ground = nullptr;                    // plant the feet on the boat (FCrewGround)
};

/** Component-space joint positions of the reference skeleton posed with the rotations (cm): for the tests. */
SAILINGSIM_API void CrewPosedJoints(const class USkeletalMesh* Mesh, const TMap<FName, FQuat>& Joints, TMap<FName, FVector>& OutPositions,
	const FCrewRig* Rig = nullptr, const FCrewHands* Hands = nullptr);

/** Where each shoe's sole meets the ground, posed (component space, cm): [side 0 left, 1 right][0 heel, 1 toe]. From
 *  the rest pose (the sole a centimetre above the ground under the ankle, the toe past the ball) carried by the foot. */
SAILINGSIM_API void CrewFootPoints(const class USkeletalMesh* Mesh, const TMap<FName, FQuat>& Joints, FVector Out[2][2], const FCrewRig* Rig = nullptr,
	const FCrewHands* Hands = nullptr);
