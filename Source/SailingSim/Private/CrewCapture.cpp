#include "CrewCapture.h"
#include "CrewPose.h"
#include "CrewSolver.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimData/IAnimationDataModel.h"
#include "Animation/AnimData/IAnimationDataController.h"
#include "Engine/SkeletalMesh.h"
#include "UObject/Package.h"

namespace
{
	/** A target bone's turn from the source: one source bone, or a blend between two (a MetaHuman's in-between spine and
	 *  neck bones from SK_Sailor's spine, chest and neck). */
	struct FSourceOf { FName A, B; float W = 0.f; };

	/** How each target bone finds its source bone (CrewPose.h's FCrewRig map, both ways). */
	bool SourceFor(const FReferenceSkeleton& Src, FName Target, FSourceOf& Out)
	{
		if (Src.FindBoneIndex(Target) != INDEX_NONE) { Out = { Target, Target, 0.f }; return true; }
		static const TMap<FName, FSourceOf> Alias = {
			// SK_Sailor from a MetaHuman: each sailor joint ends where its spread over the MetaHuman's bones ends.
			{ TEXT("spine"), { TEXT("spine_02"), TEXT("spine_02"), 0.f } },
			{ TEXT("chest"), { TEXT("spine_05"), TEXT("spine_05"), 0.f } },
			{ TEXT("neck"), { TEXT("neck_02"), TEXT("neck_02"), 0.f } },
			{ TEXT("forearm_l"), { TEXT("lowerarm_l"), TEXT("lowerarm_l"), 0.f } },
			{ TEXT("forearm_r"), { TEXT("lowerarm_r"), TEXT("lowerarm_r"), 0.f } },
			// A MetaHuman from SK_Sailor: the chain's ends match, the bones between take their share of the turn.
			{ TEXT("spine_01"), { TEXT("pelvis"), TEXT("spine"), 0.5f } },
			{ TEXT("spine_02"), { TEXT("spine"), TEXT("spine"), 0.f } },
			{ TEXT("spine_03"), { TEXT("spine"), TEXT("chest"), 0.34f } },
			{ TEXT("spine_04"), { TEXT("spine"), TEXT("chest"), 0.67f } },
			{ TEXT("spine_05"), { TEXT("chest"), TEXT("chest"), 0.f } },
			{ TEXT("neck_01"), { TEXT("chest"), TEXT("neck"), 0.5f } },
			{ TEXT("neck_02"), { TEXT("neck"), TEXT("neck"), 0.f } },
			{ TEXT("lowerarm_l"), { TEXT("forearm_l"), TEXT("forearm_l"), 0.f } },
			{ TEXT("lowerarm_r"), { TEXT("forearm_r"), TEXT("forearm_r"), 0.f } },
		};
		const FSourceOf* S = Alias.Find(Target);
		if (!S || Src.FindBoneIndex(S->A) == INDEX_NONE || Src.FindBoneIndex(S->B) == INDEX_NONE) return false;
		Out = *S;
		return true;
	}

	struct FSkel
	{
		const USkeletalMesh* Mesh = nullptr;
		FCrewRig Rig;    // its T-posed rest and frame (identity frame for SK_Sailor)
	};

	FSkel MakeSkel(const USkeletalMesh* Mesh)
	{
		FSkel S;
		S.Mesh = Mesh;
		BuildCrewRig(Mesh, S.Rig);
		if (!S.Rig.bValid) CrewSolver::RestPose(Mesh->GetRefSkeleton(), S.Rig.RestCS);
		return S;
	}

	/** Component-space bone turns from the T-posed rest (CrewSolver's D), in the character frame. */
	void TurnsOf(const FSkel& S, const TArray<FTransform>& CS, TArray<FQuat>& Out)
	{
		const FQuat F = S.Rig.Frame, FInv = F.Inverse();
		Out.SetNum(CS.Num());
		for (int32 B = 0; B < CS.Num(); ++B) Out[B] = FInv * (CS[B].GetRotation() * S.Rig.RestCS[B].GetRotation().Inverse()) * F;
	}

	/** Poses the target from the source's turns (character frame) and the pelvis's move (character frame, cm). */
	void PoseTarget(const FSkel& Src, const FSkel& Tgt, const TArray<FQuat>& SrcTurns, const FVector& PelvisMove, TArray<FTransform>& OutCS)
	{
		const FReferenceSkeleton& SRef = Src.Mesh->GetRefSkeleton();
		const FReferenceSkeleton& TRef = Tgt.Mesh->GetRefSkeleton();
		const int32 N = TRef.GetNum();
		const FQuat F = Tgt.Rig.Frame, FInv = F.Inverse();
		TArray<FQuat> D;
		D.SetNum(N);
		TMap<FName, FQuat> Joints;
		for (int32 B = 0; B < N; ++B)
		{
			const int32 Parent = TRef.GetParentIndex(B);
			const FQuat DParent = Parent == INDEX_NONE ? FQuat::Identity : D[Parent];
			FSourceOf S;
			// The root bone ("root") stays put; a skeleton whose root is the pelvis turns it like any other.
			const bool bFixedRoot = Parent == INDEX_NONE && TRef.GetBoneName(B) == FName(TEXT("root"));
			if (!bFixedRoot && SourceFor(SRef, TRef.GetBoneName(B), S))
			{
				const FQuat A = SrcTurns[SRef.FindBoneIndex(S.A)], Bq = SrcTurns[SRef.FindBoneIndex(S.B)];
				D[B] = F * FQuat::Slerp(A, Bq, S.W).GetNormalized() * FInv;
			}
			else
			{
				D[B] = DParent;   // no match (twist and corrective bones, the root): follows its parent
			}
			const FQuat Local = DParent.Inverse() * D[B];
			if (!Local.Equals(FQuat::Identity, 1e-6)) Joints.Add(TRef.GetBoneName(B), Local);
		}
		CrewSolver::Solve(TRef, Tgt.Rig.RestCS, Joints, OutCS);
		// The pelvis carries the body's move; the root stays where it is (on the cockpit sole).
		const bool bRootBone = TRef.GetBoneName(0) == FName(TEXT("root"));
		const FVector Move = F.RotateVector(PelvisMove);
		for (int32 B = bRootBone ? 1 : 0; B < N; ++B) OutCS[B].AddToTranslation(Move);
	}

	/** A new animation for Mesh's skeleton: in a package at AssetPath, or transient. */
	UAnimSequence* NewClip(const USkeletalMesh* Mesh, const FString& AssetPath)
	{
		UObject* Outer = GetTransientPackage();
		FName Name = MakeUniqueObjectName(Outer, UAnimSequence::StaticClass(), TEXT("CrewClip"));
		EObjectFlags Flags = RF_Transient;
		if (!AssetPath.IsEmpty())
		{
			UPackage* Package = CreatePackage(*AssetPath);
			Package->FullyLoad();
			Outer = Package;
			Name = *FPackageName::GetLongPackageAssetName(AssetPath);
			Flags = RF_Public | RF_Standalone;
			if (UAnimSequence* Old = FindObject<UAnimSequence>(Package, *Name.ToString()))
			{
				Old->Rename(nullptr, GetTransientPackage(), REN_DontCreateRedirectors | REN_NonTransactional);
			}
		}
		UAnimSequence* Seq = NewObject<UAnimSequence>(Outer, Name, Flags);
		Seq->SetSkeleton(const_cast<USkeletalMesh*>(Mesh)->GetSkeleton());
		Seq->SetPreviewMesh(const_cast<USkeletalMesh*>(Mesh));
		return Seq;
	}

	/** Writes frames of component-space transforms as the clip's bone tracks (every bone, local to its parent). */
	void WriteFrames(UAnimSequence* Seq, const USkeletalMesh* Mesh, const TArray<TArray<FTransform>>& Frames, int32 Fps)
	{
#if WITH_EDITOR
		const FReferenceSkeleton& Ref = Mesh->GetRefSkeleton();
		const int32 N = Ref.GetNum(), K = Frames.Num();
		IAnimationDataController& C = Seq->GetController();
		C.OpenBracket(FText::FromString(TEXT("Crew capture")), false);
		C.InitializeModel();
		C.SetFrameRate(FFrameRate(Fps, 1), false);
		C.SetNumberOfFrames(FFrameNumber(FMath::Max(K - 1, 1)), false);
		for (int32 B = 0; B < N; ++B)
		{
			TArray<FVector> P; TArray<FQuat> R; TArray<FVector> S;
			P.Reserve(K); R.Reserve(K); S.Reserve(K);
			const int32 Parent = Ref.GetParentIndex(B);
			for (int32 I = 0; I < FMath::Max(K, 2); ++I)
			{
				const TArray<FTransform>& CS = Frames[FMath::Min(I, K - 1)];
				const FTransform Local = Parent == INDEX_NONE ? CS[B] : CS[B].GetRelativeTransform(CS[Parent]);
				P.Add(Local.GetLocation());
				R.Add(Local.GetRotation().GetNormalized());
				S.Add(Local.GetScale3D());   // SK_Sailor's root (the Blender armature) carries the export scale
			}
			const FName Bone = Ref.GetBoneName(B);
			C.AddBoneCurve(Bone, false);
			C.SetBoneTrackKeys(Bone, P, R, S, false);
		}
		C.NotifyPopulated();
		C.CloseBracket(false);
#endif
	}
}

double UCrewCaptureLibrary::ClipSeconds(const UAnimSequence* Seq)
{
#if WITH_EDITOR
	return Seq && Seq->GetDataModel() ? Seq->GetDataModel()->GetPlayLength() : 0.0;
#else
	return Seq ? Seq->GetPlayLength() : 0.0;
#endif
}

void UCrewCaptureLibrary::EvaluateClip(const UAnimSequence* Seq, const USkeletalMesh* Mesh, double Seconds, TArray<FTransform>& OutCS)
{
	OutCS.Reset();
	if (!Seq || !Mesh) return;
	const FReferenceSkeleton& Ref = Mesh->GetRefSkeleton();
	const TArray<FTransform>& RefLocal = Ref.GetRefBonePose();
	OutCS.SetNum(Ref.GetNum());
#if WITH_EDITOR
	const IAnimationDataModel* Model = Seq->GetDataModel();
	const FFrameTime Time = Model ? Model->GetFrameRate().AsFrameTime(FMath::Clamp(Seconds, 0.0, Model->GetPlayLength())) : FFrameTime();
#endif
	for (int32 B = 0; B < Ref.GetNum(); ++B)
	{
		FTransform Local = RefLocal[B];
#if WITH_EDITOR
		const FName Bone = Ref.GetBoneName(B);
		if (Model && Model->IsValidBoneTrackName(Bone)) Local = Model->EvaluateBoneTrackTransform(Bone, Time, EAnimInterpolationType::Linear);
#endif
		const int32 Parent = Ref.GetParentIndex(B);
		OutCS[B] = Parent == INDEX_NONE ? Local : Local * OutCS[Parent];
	}
}

UAnimSequence* UCrewCaptureLibrary::RetargetClip(UAnimSequence* Source, USkeletalMesh* SourceMesh, USkeletalMesh* TargetMesh, float StartSeconds,
	float EndSeconds, int32 Fps, const FString& AssetPath)
{
	if (!Source || !SourceMesh || !TargetMesh || Fps <= 0) return nullptr;
	const FSkel Src = MakeSkel(SourceMesh), Tgt = MakeSkel(TargetMesh);
	const double Length = ClipSeconds(Source);
	const double T0 = FMath::Clamp(double(StartSeconds), 0.0, Length);
	const double T1 = EndSeconds > 0.f ? FMath::Clamp(double(EndSeconds), T0, Length) : Length;
	const int32 Keys = FMath::Max(2, FMath::RoundToInt((T1 - T0) * Fps) + 1);
	const int32 SrcPelvis = SourceMesh->GetRefSkeleton().FindBoneIndex(TEXT("pelvis"));
	const double Scale = Src.Rig.Pelvis.Z > 1.0 && Tgt.Rig.Pelvis.Z > 1.0 ? Tgt.Rig.Pelvis.Z / Src.Rig.Pelvis.Z : 1.0;
	TArray<TArray<FTransform>> Frames;
	Frames.SetNum(Keys);
	TArray<FTransform> CS;
	TArray<FQuat> Turns;
	for (int32 I = 0; I < Keys; ++I)
	{
		EvaluateClip(Source, SourceMesh, T0 + (T1 - T0) * I / (Keys - 1), CS);
		TurnsOf(Src, CS, Turns);
		FVector Move = FVector::ZeroVector;
		if (SrcPelvis != INDEX_NONE) Move = Src.Rig.Frame.Inverse().RotateVector(CS[SrcPelvis].GetLocation() - Src.Rig.RestCS[SrcPelvis].GetLocation()) * Scale;
		PoseTarget(Src, Tgt, Turns, Move, Frames[I]);
	}
	UAnimSequence* Out = NewClip(TargetMesh, AssetPath);
	WriteFrames(Out, TargetMesh, Frames, Fps);
	return Out;
}

UAnimSequence* UCrewCaptureLibrary::MakeStanceClip(USkeletalMesh* Mesh, const FString& Spec, int32 Fps, const FString& AssetPath)
{
	if (!Mesh || Fps <= 0) return nullptr;
	struct FPart { TMap<FName, FQuat> Joints; double Seconds = 1.0; };
	TArray<FPart> Parts;
	TArray<FString> Items;
	Spec.ParseIntoArray(Items, TEXT(","));
	for (const FString& Item : Items)
	{
		FString Pose, Secs;
		if (!Item.Split(TEXT("="), &Pose, &Secs)) { Pose = Item; Secs = TEXT("1"); }
		FString Name, Hike;
		if (!Pose.Split(TEXT(":"), &Name, &Hike)) { Name = Pose; Hike = TEXT("0"); }
		static const TMap<FString, ECrewStance> Stances = {
			{ TEXT("RailHike"), ECrewStance::RailHike }, { TEXT("Helm"), ECrewStance::Helm }, { TEXT("Cockpit"), ECrewStance::Cockpit },
			{ TEXT("Crossing"), ECrewStance::Crossing }, { TEXT("DinghyHike"), ECrewStance::DinghyHike }, { TEXT("Trapeze"), ECrewStance::Trapeze },
			{ TEXT("Righting"), ECrewStance::Righting } };
		const ECrewStance* S = Stances.Find(Name.TrimStartAndEnd());
		if (!S) { UE_LOG(LogTemp, Warning, TEXT("MakeStanceClip: no stance %s"), *Name); return nullptr; }
		FCrewPoseParams P;
		P.Stance = *S;
		P.Hike = FCString::Atof(*Hike);
		FPart Part;
		CrewJointRotations(P, Part.Joints);
		Part.Seconds = FMath::Max(0.1, double(FCString::Atof(*Secs)));
		Parts.Add(MoveTemp(Part));
	}
	if (Parts.Num() == 0) return nullptr;
	FCrewRig Rig;
	BuildCrewRig(Mesh, Rig);
	const FReferenceSkeleton& Ref = Mesh->GetRefSkeleton();
	double Total = 0.0;
	for (const FPart& P : Parts) Total += P.Seconds;
	const int32 Keys = FMath::Max(2, FMath::RoundToInt(Total * Fps) + 1);
	TArray<TArray<FTransform>> Frames;
	Frames.SetNum(Keys);
	for (int32 I = 0; I < Keys; ++I)
	{
		double T = Total * I / (Keys - 1), Start = 0.0;
		int32 K = 0;
		while (K < Parts.Num() - 1 && T > Start + Parts[K].Seconds) { Start += Parts[K].Seconds; ++K; }
		// Blend in from the previous stance over the first 40% of this one (smoothstep).
		const double A = K == 0 ? 1.0 : FMath::SmoothStep(0.0, 0.4 * Parts[K].Seconds, T - Start);
		TMap<FName, FQuat> Joints;
		const TMap<FName, FQuat>& Now = Parts[K].Joints;
		const TMap<FName, FQuat>* Before = K > 0 ? &Parts[K - 1].Joints : nullptr;
		TSet<FName> Names;
		for (const TPair<FName, FQuat>& J : Now) Names.Add(J.Key);
		if (Before) for (const TPair<FName, FQuat>& J : *Before) Names.Add(J.Key);
		for (const FName& N : Names)
		{
			const FQuat* Q1 = Now.Find(N);
			const FQuat* Q0 = Before ? Before->Find(N) : nullptr;
			Joints.Add(N, FQuat::Slerp(Q0 ? *Q0 : FQuat::Identity, Q1 ? *Q1 : FQuat::Identity, A).GetNormalized());
		}
		CrewSolver::Pose(Ref, Joints, Rig.bValid ? &Rig : nullptr, Frames[I]);
	}
	UAnimSequence* Out = NewClip(Mesh, AssetPath);
	WriteFrames(Out, Mesh, Frames, Fps);
	return Out;
}
