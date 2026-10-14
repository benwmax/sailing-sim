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
	/** The reference pose in component space. */
	void RestPose(const FReferenceSkeleton& Ref, TArray<FTransform>& Out)
	{
		const TArray<FTransform>& Local = Ref.GetRefBonePose();
		Out.SetNum(Ref.GetNum());
		for (int32 B = 0; B < Ref.GetNum(); ++B)
		{
			const int32 Parent = Ref.GetParentIndex(B);
			Out[B] = Parent == INDEX_NONE ? Local[B] : Local[B] * Out[Parent];
		}
	}

	/** Component-space posed transforms from a rest pose: D(bone) = D(parent) * R(bone); rotation D * rest;
	 *  position = parent's posed position + D(parent) * (rest offset from the parent). */
	void Solve(const FReferenceSkeleton& Ref, const TArray<FTransform>& RestCS, const TMap<FName, FQuat>& Joints, TArray<FTransform>& OutCS)
	{
		const int32 N = Ref.GetNum();
		TArray<FQuat> D;
		D.SetNum(N);
		OutCS.SetNum(N);
		for (int32 B = 0; B < N; ++B)
		{
			const int32 Parent = Ref.GetParentIndex(B);
			const FQuat* R = Joints.Find(Ref.GetBoneName(B));
			const FQuat Rot = R ? *R : FQuat::Identity;
			D[B] = Parent == INDEX_NONE ? Rot : D[Parent] * Rot;
			const FQuat Rotation = D[B] * RestCS[B].GetRotation();
			const FVector Position = Parent == INDEX_NONE ? RestCS[B].GetLocation()
				: OutCS[Parent].GetLocation() + D[Parent].RotateVector(RestCS[B].GetLocation() - RestCS[Parent].GetLocation());
			OutCS[B] = FTransform(Rotation, Position, RestCS[B].GetScale3D());
		}
	}

	/** The sailor's joints on the rig's skeleton. */
	void Carry(const FCrewRig& Rig, const TMap<FName, FQuat>& Joints, TMap<FName, FQuat>& Out)
	{
		Out.Reset();
		const FQuat Inv = Rig.Frame.Inverse();
		for (const TPair<FName, FQuat>& J : Joints)
		{
			const FQuat R = Rig.Frame * J.Value * Inv;
			if (const TArray<TPair<FName, float>>* Bones = Rig.Map.Find(J.Key))
			{
				for (const TPair<FName, float>& B : *Bones) Out.Add(B.Key, FQuat::Slerp(FQuat::Identity, R, B.Value));
			}
			else
			{
				Out.Add(J.Key, R);
			}
		}
	}

	void Pose(const FReferenceSkeleton& Ref, const TMap<FName, FQuat>& Joints, const FCrewRig* Rig, TArray<FTransform>& CS)
	{
		if (Rig && Rig->bValid && Rig->RestCS.Num() == Ref.GetNum())
		{
			TMap<FName, FQuat> Carried;
			Carry(*Rig, Joints, Carried);
			Solve(Ref, Rig->RestCS, Carried, CS);
			return;
		}
		TArray<FTransform> Rest;
		RestPose(Ref, Rest);
		Solve(Ref, Rest, Joints, CS);
	}
}

const TCHAR* MetaHumanRoleName(int32 Role)
{
	static const TCHAR* Names[NumMetaHumanRoles] = { TEXT("Helm"), TEXT("Trimmer"), TEXT("Bow") };
	return Names[FMath::Clamp(Role, 0, NumMetaHumanRoles - 1)];
}

bool LoadMetaHumanCrew(int32 Role, USkeletalMesh*& Body, USkeletalMesh*& Face, USkeletalMesh*& Outfit)
{
	const FString R = MetaHumanRoleName(Role);
	auto Load = [](const FString& Path) { return LoadObject<USkeletalMesh>(nullptr, *Path, nullptr, LOAD_NoWarn | LOAD_Quiet); };
	Body = Load(FString::Printf(TEXT("/Game/Crew/MetaHumans/%s/Body/SKM_%s_BodyMesh.SKM_%s_BodyMesh"), *R, *R, *R));
	Face = Load(FString::Printf(TEXT("/Game/Crew/MetaHumans/%s/Face/SKM_%s_FaceMesh.SKM_%s_FaceMesh"), *R, *R, *R));
	Outfit = Load(FString::Printf(TEXT("/Game/Crew/MetaHumans/%s/Clothing/%s_Outfits.%s_Outfits"), *R, *R, *R));
	return Body && Face;
}

void BuildCrewRig(const USkeletalMesh* Mesh, FCrewRig& Rig)
{
	Rig = FCrewRig();
	if (!Mesh) return;
	const FReferenceSkeleton& Ref = Mesh->GetRefSkeleton();
	TArray<FTransform> Rest;
	RestPose(Ref, Rest);
	auto At = [&](const TCHAR* Name) -> FVector
	{
		const int32 B = Ref.FindBoneIndex(Name);
		return B == INDEX_NONE ? FVector::ZeroVector : Rest[B].GetLocation();
	};
	// Facing: heel to ball of the foot.
	if (Ref.FindBoneIndex(TEXT("foot_l")) != INDEX_NONE && Ref.FindBoneIndex(TEXT("ball_l")) != INDEX_NONE)
	{
		const FVector Fwd = (At(TEXT("ball_l")) - At(TEXT("foot_l"))).GetSafeNormal2D();
		if (!Fwd.IsNearlyZero()) Rig.Frame = FQuat::FindBetweenNormals(FVector::ForwardVector, Fwd);
	}
	if (Ref.FindBoneIndex(TEXT("spine_01")) != INDEX_NONE)
	{
		auto Add = [&](const TCHAR* Joint, std::initializer_list<TPair<FName, float>> Bones) { Rig.Map.Add(Joint, TArray<TPair<FName, float>>(Bones)); };
		Add(TEXT("spine"), { { TEXT("spine_01"), 0.5f }, { TEXT("spine_02"), 0.5f } });
		Add(TEXT("chest"), { { TEXT("spine_03"), 0.34f }, { TEXT("spine_04"), 0.33f }, { TEXT("spine_05"), 0.33f } });
		Add(TEXT("neck"), { { TEXT("neck_01"), 0.5f }, { TEXT("neck_02"), 0.5f } });
		Add(TEXT("forearm_l"), { { TEXT("lowerarm_l"), 1.f } });
		Add(TEXT("forearm_r"), { { TEXT("lowerarm_r"), 1.f } });
	}
	// The arms out level (SK_Sailor's T-pose): turn each upper arm to point straight out, then straighten the elbow.
	TMap<FName, FQuat> Fix;
	for (const bool bLeft : { true, false })
	{
		const FName Upper = bLeft ? TEXT("upperarm_l") : TEXT("upperarm_r");
		const FName Lower = bLeft ? TEXT("lowerarm_l") : TEXT("lowerarm_r");
		const FName Hand = bLeft ? TEXT("hand_l") : TEXT("hand_r");
		const int32 U = Ref.FindBoneIndex(Upper), L = Ref.FindBoneIndex(Lower), H = Ref.FindBoneIndex(Hand);
		if (U == INDEX_NONE || L == INDEX_NONE || H == INDEX_NONE) continue;
		const FVector Want = Rig.Frame.RotateVector(bLeft ? -FVector::RightVector : FVector::RightVector);
		const FQuat CU = FQuat::FindBetweenNormals((Rest[L].GetLocation() - Rest[U].GetLocation()).GetSafeNormal(), Want);
		const FQuat CL = FQuat::FindBetweenNormals((Rest[H].GetLocation() - Rest[L].GetLocation()).GetSafeNormal(), CU.Inverse().RotateVector(Want));
		Fix.Add(Upper, CU);
		Fix.Add(Lower, CL);
	}
	Solve(Ref, Rest, Fix, Rig.RestCS);
	const int32 P = Ref.FindBoneIndex(TEXT("pelvis"));
	Rig.Pelvis = P == INDEX_NONE ? FVector::ZeroVector : Rig.RestCS[P].GetLocation();
	Rig.bValid = true;
}

FTransform FCrewRig::Rest(const USkeletalMesh* Mesh, FName Bone) const
{
	const int32 B = Mesh ? Mesh->GetRefSkeleton().FindBoneIndex(Bone) : INDEX_NONE;
	return B == INDEX_NONE || !RestCS.IsValidIndex(B) ? FTransform::Identity : RestCS[B];
}

void ApplyCrewPose(UPoseableMeshComponent* Mesh, const TMap<FName, FQuat>& Joints, const FCrewRig* Rig)
{
	if (!Mesh || !Mesh->GetSkinnedAsset()) return;
	const FReferenceSkeleton& Ref = Mesh->GetSkinnedAsset()->GetRefSkeleton();
	TArray<FTransform> CS;
	Pose(Ref, Joints, Rig, CS);
	for (int32 B = 0; B < CS.Num(); ++B)
	{
		Mesh->SetBoneTransformByName(Ref.GetBoneName(B), CS[B], EBoneSpaces::ComponentSpace);
	}
}

void CrewPosedJoints(const USkeletalMesh* Mesh, const TMap<FName, FQuat>& Joints, TMap<FName, FVector>& Out, const FCrewRig* Rig)
{
	Out.Reset();
	if (!Mesh) return;
	const FReferenceSkeleton& Ref = Mesh->GetRefSkeleton();
	TArray<FTransform> CS;
	Pose(Ref, Joints, Rig, CS);
	for (int32 B = 0; B < CS.Num(); ++B) Out.Add(Ref.GetBoneName(B), CS[B].GetLocation());
}
