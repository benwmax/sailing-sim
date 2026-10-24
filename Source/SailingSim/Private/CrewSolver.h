#pragma once

#include "CoreMinimal.h"
#include "CrewPose.h"

struct FReferenceSkeleton;

/** The crew posing's stages (CrewPose.cpp), shared by the stance pose and the C1 motion node (CrewMotion.cpp). */
namespace CrewSolver
{
	extern const TCHAR* const FingerNames[5];

	/** The reference pose in component space. */
	void RestPose(const FReferenceSkeleton& Ref, TArray<FTransform>& Out);
	/** Forward kinematics from the rest pose with joint rotations; D (optional) gets each bone's component-space turn. */
	void Solve(const FReferenceSkeleton& Ref, const TArray<FTransform>& RestCS, const TMap<FName, FQuat>& Joints, TArray<FTransform>& OutCS,
		TArray<FQuat>* OutD = nullptr);
	/** The sailor's joints on the rig's skeleton. */
	void Carry(const FCrewRig& Rig, const TMap<FName, FQuat>& Joints, TMap<FName, FQuat>& Out);
	/** Two-bone IK of the chain ending at Hand (a hand or a foot) toward Target, keeping the stance's bend plane (or bending
	 *  the middle joint toward Bend, component space, when given). */
	void ReachArm(const FReferenceSkeleton& Ref, const TArray<FTransform>& CS, const TArray<FQuat>& D, int32 Hand, const FVector& Target,
		TMap<FName, FQuat>& Joints, const FVector& HeldLine = FVector::ZeroVector, const FVector& Bend = FVector::ZeroVector);
	bool SolePoints(const FReferenceSkeleton& Ref, const TArray<FTransform>& Rest, const TArray<FTransform>& CS, const FQuat& Frame, int32 Side, FVector Out[2]);
	void CurlFingers(const FCrewRig& Rig, const FCrewHands& Hands, TMap<FName, FQuat>& Carried);
	bool ClearFingers(const FReferenceSkeleton& Ref, const TArray<FTransform>& RestCS, TArray<FTransform>& CS, TArray<FQuat>& D, const FCrewHands& Hands,
		TMap<FName, FQuat>& Carried);
	void PlantAllFeet(const FReferenceSkeleton& Ref, const TArray<FTransform>& RestCS, TArray<FTransform>& CS, TArray<FQuat>& D, const FQuat& Frame,
		const FCrewGround& Ground, TMap<FName, FQuat>& Carried);
	/** Reach and knee holds; true if a knee hold moved an arm without re-solving. */
	bool PlaceHands(const FReferenceSkeleton& Ref, const TArray<FTransform>& RestCS, TArray<FTransform>& CS, TArray<FQuat>& D, const FCrewHands& Hands,
		TMap<FName, FQuat>& Carried);
	void Pose(const FReferenceSkeleton& Ref, const TMap<FName, FQuat>& Joints, const FCrewRig* Rig, TArray<FTransform>& CS, const FCrewHands* Hands = nullptr);
}
