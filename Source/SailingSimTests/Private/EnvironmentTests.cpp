#include "Misc/AutomationTest.h"
#include "LakeData.h"
#include "Marina.h"
#include "MarinaActor.h"
#include "WorldKit.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
	constexpr EAutomationTestFlags EnvFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSlipWearTest, "SailingSim.Visual.SlipWear", EnvFlags)
bool FSailingSlipWearTest::RunTest(const FString& Parameters)
{
	// Environment E1 (docs/environment-1): no two neighbouring slips share a dress, a dock clutter set or a cover, and the
	// wear seeds are a pure function of the structure's id, the same on the Mac and the PC.
	FLakeData Lake;
	if (!TestTrue(TEXT("Lake data loads"), Lake.Load(FLakeData::DefaultDirectory(), TEXT("RayHubbard")))) return false;
	const FMarina& M = Lake.Marina;
	if (!TestTrue(TEXT("Marina loads"), M.IsLoaded())) return false;
	TArray<FSlipLook> Looks;
	AssignSlipLooks(M, Looks);
	TestEqual(TEXT("One look per slip"), Looks.Num(), M.Slips.Num());
	int32 Pairs = 0, Clashes = 0;
	TSet<int32> Dresses, Clutters, Covers;
	for (int32 I = 0; I < M.Slips.Num(); ++I)
	{
		Dresses.Add(Looks[I].Dress);
		Clutters.Add(Looks[I].Clutter);
		Covers.Add(Looks[I].Cover);
		TestTrue(TEXT("Dress in range"), Looks[I].Dress >= 0 && Looks[I].Dress < FSlipLook::NumDress);
		TestTrue(TEXT("Clutter in range"), Looks[I].Clutter >= 0 && Looks[I].Clutter < FSlipLook::NumClutter);
		TestTrue(TEXT("Cover in range"), Looks[I].Cover >= 0 && Looks[I].Cover < FSlipLook::NumCover);
		for (int32 J = I + 1; J < M.Slips.Num(); ++J)
		{
			if (!AreNeighbourSlips(M.Slips[I], M.Slips[J])) continue;
			++Pairs;
			const bool bClash = Looks[I].Dress == Looks[J].Dress || Looks[I].Clutter == Looks[J].Clutter || Looks[I].Cover == Looks[J].Cover;
			if (bClash && Clashes++ < 5)
			{
				AddError(FString::Printf(TEXT("%s and %s share a look (dress %d/%d, clutter %d/%d, cover %d/%d)"), *M.Slips[I].Id, *M.Slips[J].Id,
					Looks[I].Dress, Looks[J].Dress, Looks[I].Clutter, Looks[J].Clutter, Looks[I].Cover, Looks[J].Cover));
			}
		}
	}
	TestTrue(TEXT("Neighbour pairs found (both sides of every row)"), Pairs > M.Slips.Num());
	TestEqual(TEXT("No neighbours share a dress, clutter set or cover"), Clashes, 0);
	TestEqual(TEXT("Every dress is used"), Dresses.Num(), FSlipLook::NumDress);
	TestEqual(TEXT("Every clutter set is used"), Clutters.Num(), FSlipLook::NumClutter);
	TestEqual(TEXT("Every cover is used"), Covers.Num(), FSlipLook::NumCover);
	TArray<FSlipLook> Again;
	AssignSlipLooks(M, Again);
	bool bSame = Again.Num() == Looks.Num();
	for (int32 I = 0; bSame && I < Looks.Num(); ++I) bSame = Again[I].Dress == Looks[I].Dress && Again[I].Clutter == Looks[I].Clutter && Again[I].Cover == Looks[I].Cover;
	TestTrue(TEXT("Looks are deterministic"), bSame);

	// The id hash is pinned (FNV-1a over UTF-16 then lowbias32): the PC's 2-byte TCHAR and the Mac's 4-byte one must agree.
	TestEqual(TEXT("IdOf is platform independent"), int64(FWearSeed::IdOf(TEXT("rcyc.dock.a.n01"))), int64(993655941));
	TestTrue(TEXT("IdAt ignores sub-centimetre noise"), FWearSeed::IdAt(FVector2D(-120.3, 57.8)) == FWearSeed::IdAt(FVector2D(-120.3001, 57.8001)));

	// Ranges and the stain band by site and contact with the water.
	double MeanAge = 0.0, SunSW = 0.0, SunN = 0.0;
	constexpr int32 N = 2000;
	for (int32 I = 0; I < N; ++I)
	{
		const uint32 Id = FWearSeed::IdAt(FVector2D(I * 3.7, -I * 1.3));
		const FWearSeed W = FWearSeed::Make(Id, EWearSite::Lake, EWearWater::Fixed, 225.f);
		const FWearSeed Same = FWearSeed::Make(Id, EWearSite::Lake, EWearWater::Fixed, 225.f);
		if (W.Age != Same.Age || W.Care != Same.Care || W.Sun != Same.Sun || W.Wet != Same.Wet || W.Variant != Same.Variant)
		{
			AddError(TEXT("FWearSeed::Make is not a function of its inputs"));
			break;
		}
		if (W.Age < 0.f || W.Age > 25.f || W.Care < 0.f || W.Care > 1.f || W.Sun < 0.f || W.Sun > 1.f || W.Variant < 0 || W.Variant >= FWearSeed::Variants)
		{
			AddError(FString::Printf(TEXT("Seed out of range: age %.2f care %.2f sun %.2f variant %d"), W.Age, W.Care, W.Sun, W.Variant));
			break;
		}
		MeanAge += W.Age / N;
		SunSW += W.Sun / N;
		SunN += FWearSeed::Make(Id, EWearSite::Lake, EWearWater::Fixed, 45.f).Sun / N;
		TestTrue(TEXT("A lake piling's band spans the drawdown"), W.Wet >= 0.3f && W.Wet <= 0.9f);
		const FWearSeed Float = FWearSeed::Make(Id, EWearSite::Gulf, EWearWater::Floating, 0.f);
		TestTrue(TEXT("A float's band rides the water"), Float.Wet >= 0.05f && Float.Wet <= 0.25f);
		TestEqual(TEXT("A house is dry"), FWearSeed::Make(Id, EWearSite::Bay, EWearWater::Dry, 0.f).Wet, 0.f);
		TestTrue(TEXT("The Gulf's splash band is higher than the lake's"), FWearSeed::Make(Id, EWearSite::Gulf, EWearWater::Fixed, 0.f).Wet > W.Wet);
	}
	TestTrue(TEXT("Ages spread over 0-25 years"), FMath::Abs(MeanAge - 12.5) < 1.0);
	TestTrue(TEXT("South-west faces bleach more than north-east ones"), SunSW > SunN + 0.5);
	float Packed[FWearSeed::NumFloats];
	FWearSeed::Make(7u, EWearSite::Bay, EWearWater::Dry, 0.f, 3).Write(Packed);
	TestEqual(TEXT("Slot 4 is the site"), Packed[4], 1.f);
	TestEqual(TEXT("Slot 5 is the variant"), Packed[5], 3.f);
	AddInfo(FString::Printf(TEXT("%d slips, %d neighbour pairs, mean age %.1f yr, sun SW %.2f NE %.2f"), M.Slips.Num(), Pairs, MeanAge, SunSW, SunN));
	return true;
}

#endif
