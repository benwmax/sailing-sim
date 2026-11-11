#include "Misc/AutomationTest.h"
#include "BareTestWorld.h"
#include "BenchRunner.h"
#include "Components/SkeletalMeshComponent.h"
#include "SailboatPawn.h"
#include "SailingSettings.h"
#include "WaterSurface.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
	constexpr EAutomationTestFlags ShowCrewFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
	struct FShowCrewWorld : FBareTestWorld { FShowCrewWorld() : FBareTestWorld(TEXT("SailingShowCrewWorld")) {} };
}

// Settings > Show crew: off, your boat's figures are hidden (never deleted), the helm still posed for the cockpit view and
// the onboard camera, the others resting; an AI boat keeps its crew; on again mid-sail, they are drawn again;
// -SailingShowCrew=0|1 beats the setting.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingShowCrewTest, "SailingSim.Smoke.ShowCrew", ShowCrewFlags)
bool FSailingShowCrewTest::RunTest(const FString&)
{
	const FString WasLine = FCommandLine::Get();
	FScopedShowCrew Setting(false);
	TestFalse(TEXT("Off by default (the class default)"), GetDefault<USailingSettings>()->bShowCrew);
	FShowCrewWorld W;
	W.World->SpawnActor<AWaterSurface>(FVector::ZeroVector, FRotator::ZeroRotator);
	ASailboatPawn* Boat = W.World->SpawnActor<ASailboatPawn>(FVector(1000.f, 0.f, 0.f), FRotator(0.f, 90.f, 0.f));
	ASailboatPawn* Ai = W.World->SpawnActorDeferred<ASailboatPawn>(ASailboatPawn::StaticClass(), FTransform(FVector(9000.f, 0.f, 0.f)));
	if (!TestNotNull(TEXT("A boat"), Boat) || !TestNotNull(TEXT("An AI boat"), Ai)) return false;
	Ai->bTrafficBoat = true;
	Ai->AutoPossessPlayer = EAutoReceiveInput::Disabled;
	Ai->AutoPossessAI = EAutoPossessAI::Disabled;
	Ai->FinishSpawning(FTransform(FVector(9000.f, 0.f, 0.f)));
	Ai->InitTraffic(0, 90.0, 0.0, 0.0);
	W.Tick(30);
	const TArray<TObjectPtr<USkeletalMeshComponent>>& Crew = Boat->GetCrewMeshes();
	if (!TestTrue(TEXT("The boat has crew"), Crew.Num() >= 2)) return false;
	const int32 Count = Crew.Num();
	auto Shown = [](const TArray<TObjectPtr<USkeletalMeshComponent>>& Figures, int32& Visible)
	{
		Visible = 0;
		for (const USkeletalMeshComponent* F : Figures) Visible += F && F->IsVisible();
		return Visible;
	};
	int32 Visible = 0;
	TestEqual(TEXT("Off: none of your figures drawn"), Shown(Crew, Visible), 0);
	TestEqual(TEXT("... none deleted"), Boat->GetCrewMeshes().Num(), Count);
	TestTrue(TEXT("... the helm still posed (its head is the cockpit eye)"),
		Crew.Last()->VisibilityBasedAnimTickOption == EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones);
	TestTrue(TEXT("... the others resting"), Crew[0]->VisibilityBasedAnimTickOption == EVisibilityBasedAnimTickOption::OnlyTickPoseWhenRendered);
	TestTrue(TEXT("The AI boat has crew"), Ai->GetCrewMeshes().Num() > 0);
	TestEqual(TEXT("The AI boat keeps its crew"), Shown(Ai->GetCrewMeshes(), Visible), Ai->GetCrewMeshes().Num());
	USailingSettings::Get()->bShowCrew = true;
	W.Tick(2);
	TestEqual(TEXT("On again mid-sail: all drawn"), Shown(Boat->GetCrewMeshes(), Visible), Count);
	SailingArgs::SetCommandLine(WasLine + TEXT(" -SailingShowCrew=0"));
	TestFalse(TEXT("-SailingShowCrew=0 beats the setting"), USailingSettings::Get()->IsShowCrew());
	W.Tick(2);
	TestEqual(TEXT("... hidden"), Shown(Boat->GetCrewMeshes(), Visible), 0);
	USailingSettings::Get()->bShowCrew = false;
	SailingArgs::SetCommandLine(WasLine + TEXT(" -SailingShowCrew=1"));
	TestTrue(TEXT("-SailingShowCrew=1 beats the setting"), USailingSettings::Get()->IsShowCrew());
	W.Tick(2);
	TestEqual(TEXT("... drawn"), Shown(Boat->GetCrewMeshes(), Visible), Count);
	SailingArgs::SetCommandLine(WasLine);
	return true;
}

// #612 follow-up: with the crew hidden (or in the cockpit view, where the helm is you), the tiller extension is not posed for
// a hidden hand. On the hero J/22 and the Sunfish, whose models bake the extension folded along the tiller, the live one
// collapses to a point inside the tiller's end; shown (chase view), it goes to the helm's hand.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingStowExtensionTest, "SailingSim.Smoke.StowExtension", ShowCrewFlags)
bool FSailingStowExtensionTest::RunTest(const FString&)
{
	FScopedShowCrew Setting(false);
	FShowCrewWorld W;
	W.World->SpawnActor<AWaterSurface>(FVector::ZeroVector, FRotator::ZeroRotator);
	ASailboatPawn* Boat = W.World->SpawnActor<ASailboatPawn>(FVector(1000.f, 0.f, 0.f), FRotator(0.f, 90.f, 0.f));
	if (!TestNotNull(TEXT("A boat"), Boat)) return false;
	auto Check = [this, Boat](const TCHAR* What, bool bCollapsed)
	{
		const TOptional<FVector> Hinge = Boat->GetTillerExtensionHingeCm(), Tip = Boat->GetTillerExtensionTipCm();
		if (!TestTrue(FString::Printf(TEXT("%s: an extension drawn"), What), Hinge.IsSet() && Tip.IsSet())) return FVector::ZeroVector;
		AddInfo(FString::Printf(TEXT("%s: extension from (%.0f, %.0f, %.0f) to (%.0f, %.0f, %.0f) cm"), What, Hinge->X, Hinge->Y, Hinge->Z, Tip->X, Tip->Y, Tip->Z));
		if (bCollapsed) TestTrue(FString::Printf(TEXT("%s: the live extension collapsed into the tiller's end (the model's own shows)"), What), FVector::Dist(*Hinge, *Tip) < 2.0);
		else
		{
			// #620 follow-up: held, the live line reaches the helm's hand (a dinghy's runs a hand's width, 12 cm, past the grip).
			const TOptional<FVector> Grip = Boat->GetHelmGripCm();
			if (TestTrue(FString::Printf(TEXT("%s: the helm's hand holds the extension"), What), Grip.IsSet()))
			{
				TestTrue(FString::Printf(TEXT("%s: the live extension reaches the helm's hand (%.1f cm off)"), What, FVector::Dist(*Grip, *Tip)), FVector::Dist(*Grip, *Tip) <= 13.0);
			}
		}
		return *Tip;
	};
	W.Tick(60);
	TestFalse(TEXT("Crew hidden"), Boat->IsCrewShownNow());
	// #618: the hero J/22's stowed extension is its own part (SM_J22H_TillerExt, split out of its rudder mesh): shown while
	// stowed, hidden while the helm holds the live one, as the Sunfish's below.
	const bool bHeroExt = TestNotNull(TEXT("J/22 hero: the stowed extension is its own part (SM_J22H_TillerExt)"), Boat->GetModelTillerExt());
	if (bHeroExt) TestTrue(TEXT("J/22, crew hidden: the stowed extension shows"), Boat->IsModelTillerExtShown());
	const FVector Stowed = Check(TEXT("J/22, crew hidden"), true);
	USailingSettings::Get()->bShowCrew = true;
	W.Tick(30);
	const FVector Held = Check(TEXT("J/22, crew shown"), false);
	if (bHeroExt) TestFalse(TEXT("J/22, crew shown: the stowed one is hidden while the helm holds the live one"), Boat->IsModelTillerExtShown());
	TestTrue(TEXT("Shown: the extension goes to the helm's hand"), FVector::Dist(Held, Stowed) > 15.0);
	Boat->SetCockpitView(true);
	W.Tick(30);
	Check(TEXT("J/22, cockpit view (crew shown)"), true);
	Boat->SetCockpitView(false);
	USailingSettings::Get()->bShowCrew = false;
	Boat->SetBoat(int32(Sailing::EBoatType::Sunfish));
	W.Tick(60);
	Check(TEXT("Sunfish, crew hidden"), true);
	// #618: the Sunfish's stowed extension is a part of its own (SM_Sunfish_TillerExt): shown while stowed, hidden while the
	// helm holds the live one (they had shown both).
	if (TestNotNull(TEXT("Sunfish: the stowed extension is its own part"), Boat->GetModelTillerExt()))
	{
		TestTrue(TEXT("Sunfish, crew hidden: the stowed extension shows"), Boat->IsModelTillerExtShown());
		USailingSettings::Get()->bShowCrew = true;
		W.Tick(30);
		Check(TEXT("Sunfish, crew shown"), false);
		TestFalse(TEXT("Sunfish, crew shown: the stowed one is hidden while the helm holds the live one"), Boat->IsModelTillerExtShown());
		// The cockpit view (the helm is you, hidden): stowed, the model's own part shows, the live one collapses.
		Boat->SetCockpitView(true);
		W.Tick(30);
		Check(TEXT("Sunfish, cockpit view (crew shown)"), true);
		TestTrue(TEXT("Sunfish, cockpit view: the stowed one shows"), Boat->IsModelTillerExtShown());
		Boat->SetCockpitView(false);
		W.Tick(30);
		USailingSettings::Get()->bShowCrew = false;
		W.Tick(30);
		Check(TEXT("Sunfish, crew hidden again"), true);
		TestTrue(TEXT("Sunfish, crew hidden again: the stowed one shows"), Boat->IsModelTillerExtShown());
	}
	return true;
}

#endif
