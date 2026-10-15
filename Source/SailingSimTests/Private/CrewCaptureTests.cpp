#include "Misc/AutomationTest.h"
#include "CrewPose.h"
#include "CrewCapture.h"
#include "Animation/AnimSequence.h"
#include "Engine/SkeletalMesh.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "HAL/FileManager.h"
#include "Misc/Paths.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
	constexpr EAutomationTestFlags CaptureFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

	/** The limb and trunk segments the MetaHumanCrew test holds to SK_Sailor's (SK_Sailor's bones, then the MetaHuman's). */
	struct FSeg { const TCHAR* A; const TCHAR* B; const TCHAR* MA; const TCHAR* MB; };
	const FSeg Segs[] = {
		{ TEXT("thigh_l"), TEXT("calf_l"), TEXT("thigh_l"), TEXT("calf_l") }, { TEXT("thigh_r"), TEXT("calf_r"), TEXT("thigh_r"), TEXT("calf_r") },
		{ TEXT("calf_l"), TEXT("foot_l"), TEXT("calf_l"), TEXT("foot_l") }, { TEXT("calf_r"), TEXT("foot_r"), TEXT("calf_r"), TEXT("foot_r") },
		{ TEXT("upperarm_l"), TEXT("forearm_l"), TEXT("upperarm_l"), TEXT("lowerarm_l") }, { TEXT("upperarm_r"), TEXT("forearm_r"), TEXT("upperarm_r"), TEXT("lowerarm_r") },
		{ TEXT("forearm_l"), TEXT("hand_l"), TEXT("lowerarm_l"), TEXT("hand_l") }, { TEXT("forearm_r"), TEXT("hand_r"), TEXT("lowerarm_r"), TEXT("hand_r") },
		{ TEXT("pelvis"), TEXT("neck"), TEXT("pelvis"), TEXT("neck_01") },
	};

	TMap<FName, FVector> Positions(const USkeletalMesh* Mesh, const TArray<FTransform>& CS)
	{
		TMap<FName, FVector> Out;
		for (int32 B = 0; B < CS.Num(); ++B) Out.Add(Mesh->GetRefSkeleton().GetBoneName(B), CS[B].GetLocation());
		return Out;
	}

	/** Worst angle (deg) between the segments of two posed skeletons, each in its own character frame. */
	float WorstSegment(const TMap<FName, FVector>& S, const TMap<FName, FVector>& M, const FQuat& MFrame, bool bMetaHumanNames, FString& Which)
	{
		float Worst = 0.f;
		const FQuat ToChar = MFrame.Inverse();
		for (const FSeg& G : Segs)
		{
			const FName MA = bMetaHumanNames ? G.MA : G.A, MB = bMetaHumanNames ? G.MB : G.B;
			if (!S.Contains(G.A) || !S.Contains(G.B) || !M.Contains(MA) || !M.Contains(MB)) continue;
			const FVector Ds = (S[G.B] - S[G.A]).GetSafeNormal();
			const FVector Dm = ToChar.RotateVector(M[MB] - M[MA]).GetSafeNormal();
			const float Deg = FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector::DotProduct(Ds, Dm), -1.0, 1.0)));
			if (Deg > Worst) { Worst = Deg; Which = FString::Printf(TEXT("%s-%s"), G.A, G.B); }
		}
		return Worst;
	}
}

/**
 * Crew C2: the capture pipeline (CrewCapture.h, Tools/capture/capture_clips.py).
 *  1. Round trip, before any filmed clip exists: each crew stance as a synthetic clip on the helm MetaHuman's skeleton
 *     (the body solve's output skeleton), retargeted to SK_Sailor, poses SK_Sailor as the stance itself does.
 *  2. Every captured clip present (/Game/Crew/Capture/Sailor, git-ignored): the root stays on the cockpit sole (at the
 *     origin), the pelvis at a sailor's height above it and no foot through the sole; and where the MetaHuman version
 *     is there, its limbs point as SK_Sailor's do (the MetaHumanCrew test's segments).
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualCrewCaptureTest, "SailingSim.Visual.CrewCapture", CaptureFlags)
bool FVisualCrewCaptureTest::RunTest(const FString& Parameters)
{
	USkeletalMesh* Sailor = LoadObject<USkeletalMesh>(nullptr, TEXT("/Game/Crew/SK_Sailor.SK_Sailor"));
	if (!TestNotNull(TEXT("SK_Sailor"), Sailor)) return false;
	USkeletalMesh *Body = nullptr, *Face = nullptr, *Outfit = nullptr;
	const bool bMetaHumans = IFileManager::Get().DirectoryExists(*FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Crew/MetaHumans")))
		&& LoadMetaHumanCrew(0, Body, Face, Outfit);
	FCrewRig BodyRig;
	if (bMetaHumans) BuildCrewRig(Body, BodyRig);

	// 1. The round trip.
	if (!bMetaHumans)
	{
		AddWarning(TEXT("Content/Crew/MetaHumans is not installed: the round trip through the MetaHuman skeleton is skipped"));
	}
	else
	{
		struct FCase { const TCHAR* Spec; ECrewStance Stance; float Hike; };
		const FCase Cases[] = { { TEXT("Helm=1"), ECrewStance::Helm, 0.f }, { TEXT("RailHike:1=1"), ECrewStance::RailHike, 1.f },
			{ TEXT("Crossing=1"), ECrewStance::Crossing, 0.f }, { TEXT("Cockpit=1"), ECrewStance::Cockpit, 0.f } };
		for (const FCase& C : Cases)
		{
			UAnimSequence* Solved = UCrewCaptureLibrary::MakeStanceClip(Body, C.Spec, 30, FString());
			if (!TestNotNull(FString::Printf(TEXT("%s: synthetic clip"), C.Spec), Solved)) continue;
			UAnimSequence* OnSailor = UCrewCaptureLibrary::RetargetClip(Solved, Body, Sailor, 0.f, 0.f, 30, FString());
			if (!TestNotNull(FString::Printf(TEXT("%s: retargeted"), C.Spec), OnSailor)) continue;
			TestTrue(FString::Printf(TEXT("%s: length kept (%.2f s)"), C.Spec, UCrewCaptureLibrary::ClipSeconds(OnSailor)),
				FMath::Abs(UCrewCaptureLibrary::ClipSeconds(OnSailor) - 1.0) < 0.05);
			TArray<FTransform> CS;
			UCrewCaptureLibrary::EvaluateClip(OnSailor, Sailor, 0.5, CS);
			FCrewPoseParams P;
			P.Stance = C.Stance;
			P.Hike = C.Hike;
			TMap<FName, FQuat> Joints;
			CrewJointRotations(P, Joints);
			TMap<FName, FVector> Want;
			CrewPosedJoints(Sailor, Joints, Want);
			FString Which;
			const float Worst = WorstSegment(Want, Positions(Sailor, CS), FQuat::Identity, false, Which);
			AddInfo(FString::Printf(TEXT("%s: MetaHuman -> SK_Sailor, worst segment %s %.1f deg off the stance"), C.Spec, *Which, Worst));
			TestTrue(FString::Printf(TEXT("%s: the retargeted clip takes the stance (worst %s %.1f deg)"), C.Spec, *Which, Worst), Worst < 10.f);
			const int32 Pelvis = Sailor->GetRefSkeleton().FindBoneIndex(TEXT("pelvis"));
			if (Pelvis != INDEX_NONE && Want.Contains(TEXT("pelvis")))
			{
				const double Off = FVector::Dist(CS[Pelvis].GetLocation(), Want[TEXT("pelvis")]);
				AddInfo(FString::Printf(TEXT("%s: pelvis %s, the stance's %s (root bone %s)"), C.Spec, *CS[Pelvis].GetLocation().ToCompactString(),
					*Want[TEXT("pelvis")].ToCompactString(), *Sailor->GetRefSkeleton().GetBoneName(0).ToString()));
				TestTrue(FString::Printf(TEXT("%s: the pelvis where the stance puts it (%.1f cm off)"), C.Spec, Off), Off < 3.0);
			}
		}
	}

	// 2. Captured clips present.
	IAssetRegistry& Registry = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get();
	const FString SailorDir = TEXT("/Game/Crew/Capture/Sailor");
	Registry.ScanPathsSynchronous({ SailorDir });
	TArray<FAssetData> Clips;
	Registry.GetAssetsByPath(FName(*SailorDir), Clips);
	int32 Checked = 0;
	for (const FAssetData& A : Clips)
	{
		const UAnimSequence* Seq = Cast<UAnimSequence>(A.GetAsset());
		if (!Seq) continue;
		++Checked;
		const FString Name = A.AssetName.ToString();
		const UAnimSequence* MH = bMetaHumans ? LoadObject<UAnimSequence>(nullptr, *FString::Printf(TEXT("/Game/Crew/Capture/MetaHuman/%s.%s"), *Name, *Name), nullptr, LOAD_NoWarn | LOAD_Quiet) : nullptr;
		const double Length = UCrewCaptureLibrary::ClipSeconds(Seq);
		const FReferenceSkeleton& Ref = Sailor->GetRefSkeleton();
		const int32 Root = 0, Pelvis = Ref.FindBoneIndex(TEXT("pelvis"));
		float WorstSeg = 0.f, MinPelvis = 1e6f, MaxPelvis = -1e6f, LowestFoot = 1e6f, RootOff = 0.f;
		FString WorstWhich;
		for (int32 K = 0; K <= 8; ++K)
		{
			const double T = Length * K / 8.0;
			TArray<FTransform> CS;
			UCrewCaptureLibrary::EvaluateClip(Seq, Sailor, T, CS);
			const TMap<FName, FVector> P = Positions(Sailor, CS);
			RootOff = FMath::Max(RootOff, float(CS[Root].GetLocation().Size()));
			if (Pelvis != INDEX_NONE)
			{
				MinPelvis = FMath::Min(MinPelvis, float(CS[Pelvis].GetLocation().Z));
				MaxPelvis = FMath::Max(MaxPelvis, float(CS[Pelvis].GetLocation().Z));
			}
			for (const TCHAR* Foot : { TEXT("foot_l"), TEXT("foot_r") })
			{
				if (const FVector* F = P.Find(Foot)) LowestFoot = FMath::Min(LowestFoot, float(F->Z));
			}
			if (MH)
			{
				TArray<FTransform> MCS;
				UCrewCaptureLibrary::EvaluateClip(MH, Body, T, MCS);
				FString Which;
				const float W = WorstSegment(P, Positions(Body, MCS), BodyRig.Frame, true, Which);
				if (W > WorstSeg) { WorstSeg = W; WorstWhich = Which; }
			}
		}
		AddInfo(FString::Printf(TEXT("%s: %.1f s, pelvis %.0f-%.0f cm, lowest ankle %.0f cm, root off %.1f cm, MetaHuman worst segment %s %.0f deg"),
			*Name, Length, MinPelvis, MaxPelvis, LowestFoot, RootOff, *WorstWhich, WorstSeg));
		TestTrue(FString::Printf(TEXT("%s: the root stays on the sole (%.1f cm off)"), *Name, RootOff), RootOff < 2.f);
		TestTrue(FString::Printf(TEXT("%s: the pelvis at a sailor's height (%.0f-%.0f cm)"), *Name, MinPelvis, MaxPelvis), MinPelvis > 20.f && MaxPelvis < 120.f);
		TestTrue(FString::Printf(TEXT("%s: no ankle through the sole (%.0f cm)"), *Name, LowestFoot), LowestFoot > -5.f);
		if (MH) TestTrue(FString::Printf(TEXT("%s: the MetaHuman's limbs point as SK_Sailor's (worst %s %.0f deg)"), *Name, *WorstWhich, WorstSeg), WorstSeg < 20.f);
	}
	AddInfo(FString::Printf(TEXT("Captured clips checked: %d (Tools/capture/clips.csv)"), Checked));
	return true;
}

#endif
