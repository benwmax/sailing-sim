#include "Misc/AutomationTest.h"
#include "CrewPose.h"
#include "Engine/SkeletalMesh.h"
#include "HAL/FileManager.h"
#include "Math/RandomStream.h"
#include "Misc/Paths.h"
#include "ReferenceSkeleton.h"

#if WITH_DEV_AUTOMATION_TESTS

// docs/crew-elbow/: the crew's two-bone solve bends elbows and knees only about their own hinge, the right way, within
// their limits (Bean's playtest: elbows bent backwards).

namespace
{
	constexpr EAutomationTestFlags CrewElbowFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

	/** The reference pose in component space (SK_Sailor's is its T-pose). */
	void RestOf(const FReferenceSkeleton& Ref, TArray<FTransform>& Out)
	{
		const TArray<FTransform>& Local = Ref.GetRefBonePose();
		Out.SetNum(Ref.GetNum());
		for (int32 B = 0; B < Ref.GetNum(); ++B)
		{
			const int32 Parent = Ref.GetParentIndex(B);
			Out[B] = Parent == INDEX_NONE ? Local[B] : Local[B] * Out[Parent];
		}
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualCrewElbowTest, "SailingSim.Visual.CrewElbow", CrewElbowFlags)
bool FVisualCrewElbowTest::RunTest(const FString& Parameters)
{
	struct FSkeleton { FString Name; const FReferenceSkeleton* Ref; TArray<FTransform> Rest; };
	TArray<FSkeleton> Skeletons;
	USkeletalMesh* Sailor = LoadObject<USkeletalMesh>(nullptr, TEXT("/Game/Crew/SK_Sailor.SK_Sailor"));
	if (!TestNotNull(TEXT("SK_Sailor"), Sailor)) return false;
	{
		FSkeleton& S = Skeletons.AddDefaulted_GetRef();
		S.Name = TEXT("SK_Sailor");
		S.Ref = &Sailor->GetRefSkeleton();
		RestOf(*S.Ref, S.Rest);
	}
	TArray<FCrewRig> Rigs;
	Rigs.SetNum(NumMetaHumanRoles);
	if (IFileManager::Get().DirectoryExists(*FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Crew/MetaHumans"))))
	{
		for (int32 Role = 0; Role < NumMetaHumanRoles; ++Role)
		{
			USkeletalMesh *Body = nullptr, *Face = nullptr, *Outfit = nullptr;
			if (!LoadMetaHumanCrew(Role, Body, Face, Outfit)) continue;
			BuildCrewRig(Body, Rigs[Role]);
			if (!Rigs[Role].bValid) continue;
			FSkeleton& S = Skeletons.AddDefaulted_GetRef();
			S.Name = MetaHumanRoleName(Role);
			S.Ref = &Body->GetRefSkeleton();
			S.Rest = Rigs[Role].RestCS;
		}
	}
	if (Skeletons.Num() == 1) AddInfo(TEXT("No MetaHumans built here: SK_Sailor only"));

	static const TCHAR* const Ends[4] = { TEXT("hand_l"), TEXT("hand_r"), TEXT("foot_l"), TEXT("foot_r") };
	static const TCHAR* const Roots[4] = { TEXT("upperarm_l"), TEXT("upperarm_r"), TEXT("thigh_l"), TEXT("thigh_r") };
	for (const FSkeleton& S : Skeletons)
	{
		for (int32 K = 0; K < 4; ++K)
		{
			const int32 End = S.Ref->FindBoneIndex(Ends[K]);
			const int32 Root = S.Ref->FindBoneIndex(Roots[K]);
			if (!TestTrue(FString::Printf(TEXT("%s: %s found"), *S.Name, Ends[K]), End != INDEX_NONE && Root != INDEX_NONE)) continue;
			const int32 Mid = S.Ref->GetParentIndex(End);
			const FVector Shoulder = S.Rest[Root].GetLocation();
			const double Reach = FVector::Dist(Shoulder, S.Rest[Mid].GetLocation()) + FVector::Dist(S.Rest[Mid].GetLocation(), S.Rest[End].GetLocation());
			const bool bLeg = K >= 2;
			const double Limit = bLeg ? 150.0 : 145.0;
			FRandomStream Rng(1234 + K);
			int32 Backward = 0, OverLimit = 0, OffHinge = 0, Missed = 0, Reachable = 0;
			double WorstFlex = 1e9, WorstOff = 0.0, WorstMiss = 0.0;
			for (int32 I = 0; I < 500; ++I)
			{
				// A start pose: the limb turned anywhere within 60 deg of the T-pose (a stance's arm or leg), bent a little.
				TMap<FName, FQuat> Joints;
				Joints.Add(Roots[K], FQuat(Rng.GetUnitVector(), FMath::DegreesToRadians(Rng.FRandRange(0.f, 60.f))));
				// A target anywhere in the reach sphere (not the shoulder itself).
				const FVector Target = Shoulder + Rng.GetUnitVector() * Reach * Rng.FRandRange(0.35f, 1.1f);
				double Flex = 0.0, Off = 0.0, Miss = 0.0;
				if (!CrewReachCheck(*S.Ref, S.Rest, Joints, End, Target, Flex, Off, Miss)) { ++Missed; continue; }
				Backward += Flex < -3.0 ? 1 : 0;
				OverLimit += Flex > Limit + 1.0 ? 1 : 0;
				OffHinge += Off > 3.0 ? 1 : 0;
				WorstFlex = FMath::Min(WorstFlex, Flex);
				WorstOff = FMath::Max(WorstOff, Off);
				const double ToTarget = FVector::Dist(Shoulder, Target);
				// Reachable: inside the straight limb (less 1 cm) and outside the folded one (the joint at its limit, plus 1 cm).
				const double Folded = FMath::Sqrt(FMath::Max(0.0, 2.0 * FMath::Square(0.5 * Reach) * (1.0 - FMath::Cos(FMath::DegreesToRadians(180.0 - Limit))))) + 1.0;
				if (ToTarget < Reach - 1.0 && ToTarget > Folded + 2.0)
				{
					++Reachable;
					Missed += Miss > 2.0 ? 1 : 0;
					WorstMiss = FMath::Max(WorstMiss, Miss);
				}
			}
			AddInfo(FString::Printf(TEXT("%s %s: %d reachable of 500, worst flexion %.1f deg, worst off-hinge %.2f deg, worst miss %.2f cm"),
				*S.Name, Ends[K], Reachable, WorstFlex, WorstOff, WorstMiss));
			TestEqual(FString::Printf(TEXT("%s %s: bent backwards"), *S.Name, Ends[K]), Backward, 0);
			TestEqual(FString::Printf(TEXT("%s %s: bent past %.0f deg"), *S.Name, Ends[K], Limit), OverLimit, 0);
			TestEqual(FString::Printf(TEXT("%s %s: off the hinge by more than 3 deg"), *S.Name, Ends[K]), OffHinge, 0);
			TestEqual(FString::Printf(TEXT("%s %s: reachable targets missed by more than 2 cm"), *S.Name, Ends[K]), Missed, 0);
			TestTrue(FString::Printf(TEXT("%s %s: enough reachable targets"), *S.Name, Ends[K]), Reachable > 200);
		}
	}
	return true;
}

#endif
