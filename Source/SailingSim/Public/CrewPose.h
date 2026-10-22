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
	float Inboard = 0.f;    // a dinghy sailor sitting in from the deck edge (light air, a run): 0 at the edge .. 1 well in
	float Stoop = 0.f;      // crossing under a boom less than a metre over the floor: 0 crouched .. 1 folded flat under it
	// docs/crew-hull-clip/: sitting on a deck whose floor ahead of the sailor is as high as the seat (the maxi's deck
	// beside her cockpit, a multihull's nets or bridgedeck): knees up and the feet on the deck, not down into a well.
	bool bFlatDeck = false;
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
	// Round 12: per hand ([0] left) and thumb joint (01..03), the turn a closed hand adds before the joint's curl, so the
	// thumb comes down round a held line instead of standing straight up off it.
	FQuat ThumbTurn[2][3] = { { FQuat::Identity, FQuat::Identity, FQuat::Identity }, { FQuat::Identity, FQuat::Identity, FQuat::Identity } };

	/** The rest transform of a bone (component space, T-posed); identity if it has none. */
	FTransform Rest(const class USkeletalMesh* Mesh, FName Bone) const;
};

/** The MetaHuman crew's roles (scripts/make_metahumans.py): 0 the helm, 1 the trimmer, 2 the bow. */
constexpr int32 NumMetaHumanRoles = 3;
SAILINGSIM_API const TCHAR* MetaHumanRoleName(int32 Role);
/** Which built MetaHuman crews figure I of N: the helm (the last) role 0, the trimmer (the one before) 1, the rest the bow,
 *  2. docs/crew-followups/: a big crew (more than four: the maxi's twelve) cycles the other hands through all three, so
 *  her rail is not one face repeated. */
inline int32 CrewMetaHumanRole(int32 N, int32 I)
{
	if (I == N - 1) return 0;
	if (I == N - 2) return 1;
	return N > 4 ? I % NumMetaHumanRoles : 2;
}

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
	bool bSeated = false;       // round 12: sitting (not hiking under a dinghy's straps): a foot on the floor lies flat
	bool bTravelerBridge = true; // the drawn model has the cockpit's traveler bridge (the light J/22); false: the hero J/22's own cockpit
	bool bFeetDown = false;     // sitting in a cockpit (Helm, Cockpit): a foot hanging over the well's sole or a seat goes down onto it
	bool bFlatDeck = false;     // docs/crew-followups/: sitting with the feet on the deck (FCrewPoseParams::bFlatDeck): never sent into a well
};

/** The cockpit well of a class (m, boat frame): open above the seats and the sole. False for the cats (nets). */
struct SAILINGSIM_API FCrewCockpitWell
{
	double X0 = 0.0, X1 = 0.0;   // aft and forward ends
	double SideDeck = -1.0;      // the J/22: the well runs to the deck edge less this; else HalfWidth
	double HalfWidth = 0.0;
	double SeatZ = -1.0, SeatW = 0.0, SoleZ = 0.0;
	double SeatIn = 0.0;         // the hero J/22: the seats' inboard edge at this half-width (else the well's edge less SeatW)
	// Round 12: a traveler bridge across the well between the seats (the J/22's, build_j22.py TRAV_X), solid from the sole
	// to its top; BridgeHalfX 0 for none.
	double BridgeX = 0.0, BridgeHalfX = 0.0, BridgeZ = 0.0;
};
/** bTravelerBridge false is the hero J/22 (the player's boat): its own cockpit (build_j22_hero.py, J22H_sockets.json), no bridge. */
SAILINGSIM_API bool CrewCockpitWell(const Sailing::FBoatConfig& Config, FCrewCockpitWell& Out, bool bTravelerBridge = true);
/** The surface a foot stands on at (X, Y) (m, boat frame): seat or sole in the well, the deck elsewhere; -1e9 off the boat. */
SAILINGSIM_API double CrewFloorZ(const Sailing::FBoatConfig& Config, double X, double Y, bool bTravelerBridge = true);
/** A multihull's surface between the hulls at (X, Y) (m, boat frame): the Hobie's trampoline, the Corsair's nets, the
 *  Lagoon's bridgedeck (Tools/blender/build_fleet.py); -1e9 where there is none (or on a monohull). */
SAILINGSIM_API double CrewBetweenHullsZ(const Sailing::FBoatConfig& Config, double X, double Y);
/** The nets' or trampoline's fore-and-aft extent on a multihull (build_fleet.py beams, akas, bridgedeck); false otherwise. */
SAILINGSIM_API bool CrewNetSpan(const Sailing::FBoatConfig& Config, double& AftX, double& ForwardX);
/** What a multihull sailor sits on at (X, Y): a hull's crowned deck (its sheer in the cockpit well, where the keelboat
 *  stances' offsets apply), else the surface between the hulls, else the nearest hull's deck at its centreline. */
SAILINGSIM_API double CrewSeatSurfaceZ(const Sailing::FBoatConfig& Config, double X, double Y);
/** A keelboat's cabin trunk (m, boat frame): from X0 to X1, Height over the sheer, its sides HalfWidth out (or the deck
 *  edge less SideDeck). False where the drawn model has none. */
struct SAILINGSIM_API FCrewCabinTrunk
{
	double X0 = 0.0, X1 = 0.0;
	double HalfWidth = 0.0;
	double SideDeck = -1.0;
	double Height = 0.0;
};
/** The boats whose drawn models carry lifelines (build_fleet.py lifelines(): the Catalinas, the Corsair's main hull). */
SAILINGSIM_API bool CrewHasLifelines(const Sailing::FBoatConfig& Config);
SAILINGSIM_API bool CrewCabinTrunk(const Sailing::FBoatConfig& Config, FCrewCabinTrunk& Out, bool bTravelerBridge = true);
/** Is a point (m, boat frame) inside the solid boat: under the deck (its crown too), inside the topsides, not in the
 *  cockpit well, in a cabin trunk; between a multihull's hulls, through the nets, the bridgedeck, saloon or table? */
SAILINGSIM_API bool CrewInsideBoat(const Sailing::FBoatConfig& Config, double HullDepth, const FVector& P, bool bTravelerBridge = true);

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
