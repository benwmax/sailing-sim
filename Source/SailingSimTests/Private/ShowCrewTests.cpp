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

#endif
