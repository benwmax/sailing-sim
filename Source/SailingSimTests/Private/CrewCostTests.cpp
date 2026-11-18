#include "Misc/AutomationTest.h"
#include "BareTestWorld.h"
#include "BenchRunner.h"
#include "BoatModel.h"
#include "CrewMotion.h"
#include "CrewPose.h"
#include "SailboatPawn.h"
#include "SailingSettings.h"
#include "WaterSurface.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
	constexpr EAutomationTestFlags CrewCostFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
	struct FCrewCostWorld : FBareTestWorld { FCrewCostWorld() : FBareTestWorld(TEXT("SailingCrewCostWorld")) {} };
}

// docs/crew-cost/: a big crew has MetaHumans aft only. At most kMaxMetaHumanCrew of any crew; every crew of that many or
// fewer whole (no boat but the big ones changes); the helm and the trimmer always; and the MetaHumans are the aftmost figures
// on every tack and hike (the ones the helm's eye and the chase camera see closest), not one face repeated.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingMetaHumanCrewCapTest, "SailingSim.Visual.MetaHumanCrewCap", CrewCostFlags)
bool FSailingMetaHumanCrewCapTest::RunTest(const FString&)
{
	using namespace Sailing;
	int32 Capped = 0;
	for (int32 T = 0; T < int32(EBoatType::Count); ++T)
	{
		if (IsSquareRigged(EBoatType(T))) continue; // The frigate's deck watch are SK_Sailor stand-ins, no MetaHumans (CrewFigureCount, docs/ship-rig/).
		const FBoatConfig Cfg = FBoatConfig::Make(EBoatType(T));
		const FString Name = ANSI_TO_TCHAR(BoatTypeName(Cfg.Type));
		const int32 N = Cfg.CrewCount;
		int32 Meta = 0;
		TSet<int32> Roles;
		for (int32 I = 0; I < N; ++I)
		{
			if (!CrewFigureIsMetaHuman(N, I)) continue;
			++Meta;
			Roles.Add(CrewMetaHumanRole(N, I));
		}
		TestEqual(*FString::Printf(TEXT("%s: %d of a crew of %d are MetaHumans"), *Name, FMath::Min(N, kMaxMetaHumanCrew), N), Meta, FMath::Min(N, kMaxMetaHumanCrew));
		TestTrue(*FString::Printf(TEXT("%s: the helm is a MetaHuman"), *Name), CrewFigureIsMetaHuman(N, N - 1));
		if (N >= 2) TestTrue(*FString::Printf(TEXT("%s: the trimmer is a MetaHuman"), *Name), CrewFigureIsMetaHuman(N, N - 2));
		if (N > 4) TestEqual(*FString::Printf(TEXT("%s: her MetaHumans are all three faces"), *Name), Roles.Num(), NumMetaHumanRoles);
		if (N <= kMaxMetaHumanCrew) continue;
		++Capped;

		// The MetaHumans sit aft of every stand-in, both tacks, sitting up and hiked, upwind and running.
		for (const double Side : { 1.0, -1.0 })
		{
			for (const double Hike : { 0.0, 1.0 })
			{
				for (const double Twa : { 0.7, 2.8 })
				{
					double MetaFwd = -1e9, StandInAft = 1e9;   // the forwardmost MetaHuman, the aftmost stand-in (+X forward)
					for (int32 I = 0; I < N; ++I)
					{
						FCrewPlaceInput Place;
						Place.Config = &Cfg;
						Place.Index = I;
						Place.CrewOffset = Side * (Cfg.CrewSitOut * 0.8 + Hike * FMath::Max(Cfg.CrewHikeOut, 0.1));
						Place.WindwardSide = Side > 0.0 ? 1 : -1;
						Place.TrueWindAngle = Side * Twa;
						FCrewPlacement Pl;
						CrewPlacement(Place, Pl);
						if (CrewFigureIsMetaHuman(N, I)) MetaFwd = FMath::Max(MetaFwd, Pl.Pelvis.X);
						else StandInAft = FMath::Min(StandInAft, Pl.Pelvis.X);
					}
					TestTrue(*FString::Printf(TEXT("%s (side %+.0f, hike %.0f, TWA %.0f deg): the MetaHumans aft of every stand-in (forwardmost MetaHuman at x %.2f m, aftmost stand-in at %.2f m)"),
						*Name, Side, Hike, FMath::RadiansToDegrees(Twa), MetaFwd, StandInAft), MetaFwd < StandInAft);
				}
			}
		}
	}
	TestTrue(TEXT("Some boat's crew is capped (the maxi, Bluebonnet)"), Capped > 0);

	// -SailingMetaCrew=<n> for measuring: none, or the whole crew as before.
	for (int32 I = 0; I < 12; ++I)
	{
		TestFalse(TEXT("A cap of 0: no MetaHumans"), CrewFigureIsMetaHuman(12, I, 0));
		TestTrue(TEXT("A cap of the crew or more: all MetaHumans"), CrewFigureIsMetaHuman(12, I, 12) && CrewFigureIsMetaHuman(12, I, 99));
	}
	TestFalse(TEXT("No figure past the crew"), CrewFigureIsMetaHuman(12, 12, 99));
	return true;
}

// The pawn builds it: on High her twelve are five MetaHumans aft and seven SK_Sailor forward, all twelve drawn; the J/22 keeps
// her three; -SailingMetaCrew=12 brings back the whole MetaHuman crew; Low is all SK_Sailor as before. (Without the MetaHumans
// built, scripts/make-metahumans.sh, only the counts are checked.)
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingMetaHumanCrewMixTest, "SailingSim.Smoke.MetaHumanCrewMix", CrewCostFlags)
bool FSailingMetaHumanCrewMixTest::RunTest(const FString&)
{
	using namespace Sailing;
	const FString WasLine = FCommandLine::Get();
	const ESailingQuality WasQuality = USailingSettings::Get()->Quality;
	FScopedShowCrew Setting(true);
	USailingSettings::Get()->Quality = ESailingQuality::High;
	FCrewCostWorld W;
	W.World->SpawnActor<AWaterSurface>(FVector::ZeroVector, FRotator::ZeroRotator);
	ASailboatPawn* Pawn = W.World->SpawnActor<ASailboatPawn>(FVector(1000.f, 0.f, 0.f), FRotator(0.f, 90.f, 0.f));
	if (!TestNotNull(TEXT("A boat"), Pawn))
	{
		USailingSettings::Get()->Quality = WasQuality;
		return false;
	}
	auto IsSailor = [](const USkeletalMeshComponent* C) { return C && C->GetSkeletalMeshAsset() && C->GetSkeletalMeshAsset()->GetName() == TEXT("SK_Sailor"); };
	auto Visible = [](const TArray<TObjectPtr<USkeletalMeshComponent>>& Crew) { int32 V = 0; for (const USkeletalMeshComponent* C : Crew) { if (C && C->IsVisible()) ++V; } return V; };

	Pawn->SetBoat(int32(EBoatType::J22));
	W.Tick(2);
	const bool bBuilt = Pawn->HasMetaHumanCrew();
	if (!bBuilt) AddWarning(TEXT("The MetaHumans are not built here (scripts/make-metahumans.sh): only the counts are checked"));
	TestEqual(TEXT("J/22: three crew"), Pawn->GetCrewMeshes().Num(), 3);
	if (bBuilt) TestEqual(TEXT("J/22: all three MetaHumans, as before"), Pawn->NumMetaHumanCrew(), 3);

	for (const EBoatType Big : { EBoatType::Bluebonnet, EBoatType::Maxi })
	{
		Pawn->SetBoat(int32(Big));
		W.Tick(2);
		const FString Name = ANSI_TO_TCHAR(BoatTypeName(Big));
		const TArray<TObjectPtr<USkeletalMeshComponent>>& Crew = Pawn->GetCrewMeshes();
		const int32 N = Pawn->GetBoatModel().GetConfig().CrewCount;
		TestEqual(*FString::Printf(TEXT("%s: all %d crew built"), *Name, N), Crew.Num(), N);
		TestEqual(*FString::Printf(TEXT("%s: all drawn"), *Name), Visible(Crew), Crew.Num());
		if (!bBuilt || Crew.Num() != N) continue;
		TestEqual(*FString::Printf(TEXT("%s: %d MetaHumans"), *Name, kMaxMetaHumanCrew), Pawn->NumMetaHumanCrew(), kMaxMetaHumanCrew);
		TestFalse(*FString::Printf(TEXT("%s: the helm is a MetaHuman"), *Name), IsSailor(Crew.Last()));
		TestTrue(*FString::Printf(TEXT("%s: the forward hand is SK_Sailor"), *Name), IsSailor(Crew[0]));
		int32 Sailors = 0;
		for (int32 I = 0; I < N; ++I)
		{
			if (IsSailor(Crew[I])) ++Sailors;
			TestTrue(*FString::Printf(TEXT("%s: figure %d is %s"), *Name, I, CrewFigureIsMetaHuman(N, I) ? TEXT("a MetaHuman") : TEXT("SK_Sailor")),
				IsSailor(Crew[I]) == !CrewFigureIsMetaHuman(N, I));
		}
		TestEqual(*FString::Printf(TEXT("%s: the rest SK_Sailor"), *Name), Sailors, N - kMaxMetaHumanCrew);
	}

	if (bBuilt)
	{
		SailingArgs::SetCommandLine(WasLine + TEXT(" -SailingMetaCrew=12"));
		Pawn->SetBoat(int32(EBoatType::Bluebonnet));
		W.Tick(2);
		TestEqual(TEXT("-SailingMetaCrew=12: her whole crew MetaHumans, as before"), Pawn->NumMetaHumanCrew(), 12);
		SailingArgs::SetCommandLine(WasLine);
	}
	USailingSettings::Get()->Quality = ESailingQuality::Low;
	Pawn->SetBoat(int32(EBoatType::Bluebonnet));
	W.Tick(2);
	TestEqual(TEXT("Low: no MetaHumans"), Pawn->NumMetaHumanCrew(), 0);
	TestEqual(TEXT("Low: her twelve SK_Sailor"), Pawn->GetCrewMeshes().Num(), 12);
	USailingSettings::Get()->Quality = WasQuality;
	return true;
}

#endif
