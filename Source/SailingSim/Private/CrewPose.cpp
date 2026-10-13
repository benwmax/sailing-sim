#include "CrewPose.h"
#include "Components/PoseableMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "ReferenceSkeleton.h"

namespace
{
	// Rotations in the character frame (X forward, Y right, Z up). The reference pose is a T-pose.
	FQuat Q(const FVector& Axis, float Deg) { return FQuat(Axis, FMath::DegreesToRadians(Deg)); }
	FQuat LegForward(float Deg) { return Q(FVector::RightVector, -Deg); }  // a downward bone swings forward
	FQuat KneeBend(float Deg) { return Q(FVector::RightVector, Deg); }     // ... and back
	FQuat Lean(float Deg) { return Q(FVector::RightVector, Deg); }         // an upward bone leans forward (+) or back (-)
	FQuat LeanSide(float Deg) { return Q(FVector::ForwardVector, Deg); }   // toward the right (+)
	// Arms: from the T-pose down by Down degrees, then swung forward by Forward; the elbow bends forward.
	FQuat Arm(bool bLeft, float Down, float Forward) { return Q(FVector::RightVector, -Forward) * Q(FVector::ForwardVector, bLeft ? Down : -Down); }
	FQuat Elbow(bool bLeft, float Deg) { return Q(FVector::UpVector, bLeft ? Deg : -Deg); }

	void Legs(TMap<FName, FQuat>& Out, float Raise, float Knee, float Splay = 6.f)
	{
		Out.Add(TEXT("thigh_l"), LeanSide(-Splay) * LegForward(Raise));
		Out.Add(TEXT("thigh_r"), LeanSide(Splay) * LegForward(Raise));
		Out.Add(TEXT("calf_l"), KneeBend(Knee));
		Out.Add(TEXT("calf_r"), KneeBend(Knee));
		Out.Add(TEXT("foot_l"), KneeBend(-0.6f * Knee + 0.4f * Raise));
		Out.Add(TEXT("foot_r"), KneeBend(-0.6f * Knee + 0.4f * Raise));
	}

	void Arms(TMap<FName, FQuat>& Out, float DownL, float FwdL, float ElbowL, float DownR, float FwdR, float ElbowR)
	{
		Out.Add(TEXT("upperarm_l"), Arm(true, DownL, FwdL));
		Out.Add(TEXT("upperarm_r"), Arm(false, DownR, FwdR));
		Out.Add(TEXT("forearm_l"), Elbow(true, ElbowL));
		Out.Add(TEXT("forearm_r"), Elbow(false, ElbowR));
	}
}

float CrewFacingYaw(const FCrewPoseParams& P)
{
	switch (P.Stance)
	{
	case ECrewStance::RailHike: return 90.f * P.Side;          // facing outboard, legs over the side
	case ECrewStance::Helm: return -25.f * P.Side;             // forward, turned a little inboard
	case ECrewStance::Crossing: return -90.f * P.Side;         // across, toward the new side
	case ECrewStance::Trapeze: return -10.f * P.Side;          // forward on the rail
	case ECrewStance::Righting: return 90.f * P.Side;          // facing the boat (she lies to the other side)
	default: return -90.f * P.Side;                           // facing inboard
	}
}

void CrewJointRotations(const FCrewPoseParams& P, TMap<FName, FQuat>& Out)
{
	Out.Reset();
	const float H = FMath::Clamp(P.Hike, 0.f, 1.f);
	switch (P.Stance)
	{
	case ECrewStance::RailHike:
	{
		// On the rail facing out: thighs over the deck edge, lower legs hanging down the topsides, leaning out over
		// the lifeline the harder they hike; hands on the wire and the thighs.
		Legs(Out, 72.f, 78.f);
		const float L = 8.f + 32.f * H;
		Out.Add(TEXT("spine"), Lean(0.5f * L));
		Out.Add(TEXT("chest"), Lean(0.5f * L));
		Out.Add(TEXT("neck"), Lean(-0.6f * L));
		Arms(Out, 70.f, 40.f, 45.f, 70.f, 40.f, 45.f);
		break;
	}
	case ECrewStance::Helm:
	{
		// Aft on the windward deck facing forward, legs into the cockpit; leaning out over the side as the boat
		// heels; the aft hand on the tiller extension, the forward hand on the mainsheet.
		Legs(Out, 82.f, 80.f, 10.f);
		const float Out_ = (6.f + 22.f * H) * P.Side;
		Out.Add(TEXT("pelvis"), LeanSide(Out_ * 0.4f));
		Out.Add(TEXT("spine"), LeanSide(Out_ * 0.6f) * Lean(5.f));
		Out.Add(TEXT("neck"), LeanSide(-Out_ * 0.7f));
		const bool bLeftOutboard = P.Side < 0.f; // facing forward, the left hand is outboard on the port side
		Arms(Out, bLeftOutboard ? 55.f : 70.f, bLeftOutboard ? 60.f : 45.f, bLeftOutboard ? 25.f : 70.f,
			bLeftOutboard ? 70.f : 55.f, bLeftOutboard ? 45.f : 60.f, bLeftOutboard ? 70.f : 25.f);
		break;
	}
	case ECrewStance::Cockpit:
		// Sitting on the cockpit seat (or low to leeward in light air), facing inboard.
		Legs(Out, 86.f, 84.f);
		Out.Add(TEXT("spine"), Lean(6.f));
		Arms(Out, 76.f, 28.f, 55.f, 76.f, 28.f, 55.f);
		break;
	case ECrewStance::Crossing:
		// Crouched, moving across the cockpit under the boom on a tack.
		Legs(Out, 75.f, 112.f);
		Out.Add(TEXT("spine"), Lean(25.f));
		Out.Add(TEXT("chest"), Lean(20.f));
		Out.Add(TEXT("neck"), Lean(-30.f));
		Arms(Out, 60.f, 55.f, 30.f, 60.f, 55.f, 30.f);
		break;
	case ECrewStance::DinghyHike:
	{
		// On the deck edge facing inboard, feet under the hiking strap, leaning back out over the water; the aft hand
		// on the tiller extension, the forward hand on the mainsheet.
		Legs(Out, 68.f, 30.f + 20.f * (1.f - H));
		const float L = -(12.f + 58.f * H);
		Out.Add(TEXT("spine"), Lean(0.5f * L));
		Out.Add(TEXT("chest"), Lean(0.5f * L));
		Out.Add(TEXT("neck"), Lean(-0.7f * L));
		Arms(Out, 40.f, 70.f, 30.f, 40.f, 70.f, 30.f);
		break;
	}
	case ECrewStance::Trapeze:
		// Standing on the rail, body straight; one hand on the handle, the other on the sheet.
		Legs(Out, 4.f, 6.f, 8.f);
		Arms(Out, -55.f, 10.f, 20.f, 70.f, 40.f, 40.f);
		break;
	case ECrewStance::Righting:
		// Standing on the board, leaning back with the hands on the gunwale.
		Legs(Out, 18.f, 25.f, 12.f);
		Out.Add(TEXT("spine"), Lean(-20.f));
		Out.Add(TEXT("chest"), Lean(-15.f));
		Out.Add(TEXT("neck"), Lean(25.f));
		Arms(Out, 25.f, 75.f, 10.f, 25.f, 75.f, 10.f);
		break;
	}
}

namespace
{
	/** Component-space posed transforms from the reference pose: D(bone) = D(parent) * R(bone); rotation D * rest;
	 *  position = parent's posed position + D(parent) * (rest offset from the parent). */
	void Solve(const FReferenceSkeleton& Ref, const TMap<FName, FQuat>& Joints, TArray<FTransform>& OutCS)
	{
		const TArray<FTransform>& Local = Ref.GetRefBonePose();
		const int32 N = Ref.GetNum();
		TArray<FTransform> RestCS;
		RestCS.SetNum(N);
		TArray<FQuat> D;
		D.SetNum(N);
		OutCS.SetNum(N);
		for (int32 B = 0; B < N; ++B)
		{
			const int32 Parent = Ref.GetParentIndex(B);
			RestCS[B] = Parent == INDEX_NONE ? Local[B] : Local[B] * RestCS[Parent];
			const FQuat* R = Joints.Find(Ref.GetBoneName(B));
			const FQuat Rot = R ? *R : FQuat::Identity;
			D[B] = Parent == INDEX_NONE ? Rot : D[Parent] * Rot;
			const FQuat Rotation = D[B] * RestCS[B].GetRotation();
			const FVector Position = Parent == INDEX_NONE ? RestCS[B].GetLocation()
				: OutCS[Parent].GetLocation() + D[Parent].RotateVector(RestCS[B].GetLocation() - RestCS[Parent].GetLocation());
			OutCS[B] = FTransform(Rotation, Position, RestCS[B].GetScale3D());
		}
	}
}

void ApplyCrewPose(UPoseableMeshComponent* Mesh, const TMap<FName, FQuat>& Joints)
{
	if (!Mesh || !Mesh->GetSkinnedAsset()) return;
	const FReferenceSkeleton& Ref = Mesh->GetSkinnedAsset()->GetRefSkeleton();
	TArray<FTransform> CS;
	Solve(Ref, Joints, CS);
	for (int32 B = 0; B < CS.Num(); ++B)
	{
		Mesh->SetBoneTransformByName(Ref.GetBoneName(B), CS[B], EBoneSpaces::ComponentSpace);
	}
}

void CrewPosedJoints(const USkeletalMesh* Mesh, const TMap<FName, FQuat>& Joints, TMap<FName, FVector>& Out)
{
	Out.Reset();
	if (!Mesh) return;
	const FReferenceSkeleton& Ref = Mesh->GetRefSkeleton();
	TArray<FTransform> CS;
	Solve(Ref, Joints, CS);
	for (int32 B = 0; B < CS.Num(); ++B) Out.Add(Ref.GetBoneName(B), CS[B].GetLocation());
}
