#include "CrewAnimInstance.h"
#include "BoatModel.h"
#include "Animation/AnimNodeBase.h"
#include "BonePose.h"

void FAnimNode_CrewMotion::Advance(float DeltaSeconds)
{
	CrewMotionUpdate(State, Input, FMath::Clamp(DeltaSeconds, 0.f, 0.25f));
}

void FAnimNode_CrewMotion::Update_AnyThread(const FAnimationUpdateContext& Context)
{
	Advance(Context.GetDeltaTime());
}

void FAnimNode_CrewMotion::Evaluate_AnyThread(FPoseContext& Output)
{
	FCompactPose& Pose = Output.Pose;
	const FBoneContainer& Bones = Pose.GetBoneContainer();
	const FReferenceSkeleton& Ref = Bones.GetReferenceSkeleton();
	Output.ResetToRefPose();
	if (!State.bStarted) Advance(0.f);
	CrewMotionPose(Ref, Rig.Get(), Config.Get(), HullDepth, State, Input, CS);
	if (CS.Num() != Ref.GetNum()) return;
	// Every required bone, local to its parent (the compact pose keeps each bone's parents, so the mesh's parent is its parent).
	for (const FCompactPoseBoneIndex Index : Pose.ForEachBoneIndex())
	{
		const int32 Mesh = Bones.MakeMeshPoseIndex(Index).GetInt();
		if (!CS.IsValidIndex(Mesh)) continue;
		const int32 Parent = Ref.GetParentIndex(Mesh);
		Pose[Index] = Parent >= 0 ? CS[Mesh].GetRelativeTransform(CS[Parent]) : CS[Mesh];
	}
}

void FCrewAnimInstanceProxy::PreUpdate(UAnimInstance* Instance, float DeltaSeconds)
{
	FAnimInstanceProxy::PreUpdate(Instance, DeltaSeconds);
	UCrewAnimInstance* Crew = CastChecked<UCrewAnimInstance>(Instance);
	if (Crew->bSetupDirty)
	{
		Node.Rig = Crew->Rig;
		Node.Config = Crew->Config;
		Node.HullDepth = Crew->HullDepth;
		Node.State = FCrewMotionState();
		Crew->bSetupDirty = false;
	}
	Node.Input = Crew->Input;
}

void FCrewAnimInstanceProxy::Update(float DeltaSeconds)
{
	Node.Advance(DeltaSeconds);
}

bool FCrewAnimInstanceProxy::Evaluate(FPoseContext& Output)
{
	Node.Evaluate_AnyThread(Output);
	return true;
}

void FCrewAnimInstanceProxy::PostEvaluate(UAnimInstance* Instance)
{
	FAnimInstanceProxy::PostEvaluate(Instance);
	CastChecked<UCrewAnimInstance>(Instance)->Report = Node.State.Report;
}

void UCrewAnimInstance::Setup(TSharedPtr<const FCrewRig> InRig, TSharedPtr<const Sailing::FBoatConfig> InConfig, double InHullDepth)
{
	Rig = MoveTemp(InRig);
	Config = MoveTemp(InConfig);
	HullDepth = InHullDepth;
	bSetupDirty = true;
}
