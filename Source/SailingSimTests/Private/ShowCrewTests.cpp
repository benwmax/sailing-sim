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

// #612 follow-up: with the crew hidden, the tiller extension is stowed back along the tiller (the hero J/22's TillerExtUJ to
// TillerExtTip), not left posed for the hidden helm's hand; shown, it goes to the helm's hand.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingStowExtensionTest, "SailingSim.Smoke.StowExtension", ShowCrewFlags)
bool FSailingStowExtensionTest::RunTest(const FString&)
{
	FScopedShowCrew Setting(false);
	FShowCrewWorld W;
	W.World->SpawnActor<AWaterSurface>(FVector::ZeroVector, FRotator::ZeroRotator);
	ASailboatPawn* Boat = W.World->SpawnActor<ASailboatPawn>(FVector(1000.f, 0.f, 0.f), FRotator(0.f, 90.f, 0.f));
	if (!TestNotNull(TEXT("A boat"), Boat)) return false;
	W.Tick(60);
	const TOptional<FVector> Hinge = Boat->GetTillerExtensionHingeCm(), Tip = Boat->GetTillerExtensionTipCm();
	if (!TestTrue(TEXT("The J/22 draws a tiller extension"), Hinge.IsSet() && Tip.IsSet())) return false;
	AddInfo(FString::Printf(TEXT("Crew hidden: extension from (%.0f, %.0f, %.0f) to (%.0f, %.0f, %.0f) cm"), Hinge->X, Hinge->Y, Hinge->Z, Tip->X, Tip->Y, Tip->Z));
	TestFalse(TEXT("Crew hidden"), Boat->IsCrewShownNow());
	TestTrue(TEXT("... the extension folded back toward the rudder head (its free end aft of the hinge)"), Tip->X < Hinge->X - 40.0);
	TestTrue(TEXT("... lying along the tiller, not raised (within 15 cm of the hinge's height)"), FMath::Abs(Tip->Z - Hinge->Z) < 15.0);
	TestTrue(TEXT("... on the centreline, inside the boat"), FMath::Abs(Tip->Y) < 40.0);
	TestTrue(TEXT("... and about the extension's length"), FVector::Dist(*Hinge, *Tip) > 50.0 && FVector::Dist(*Hinge, *Tip) < 120.0);
	USailingSettings::Get()->bShowCrew = true;
	W.Tick(30);
	const TOptional<FVector> Held = Boat->GetTillerExtensionTipCm();
	if (!TestTrue(TEXT("Shown: still drawn"), Held.IsSet())) return false;
	AddInfo(FString::Printf(TEXT("Crew shown: the free end at (%.0f, %.0f, %.0f) cm"), Held->X, Held->Y, Held->Z));
	TestTrue(TEXT("Shown: the extension goes to the helm's hand (not the stowed end)"), FVector::Dist(*Held, *Tip) > 15.0);
	return true;
}

#endif
