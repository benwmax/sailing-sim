#include "Misc/AutomationTest.h"
#include "BareTestWorld.h"
#include "SailboatPawn.h"
#include "SailingHUD.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
	constexpr EAutomationTestFlags StartHoldFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
	struct FStartHoldWorld : FBareTestWorld { FStartHoldWorld() : FBareTestWorld(TEXT("SailingStartHoldWorld")) {} };
}

// #598: the pawn's own clock for the no-go tips' hold. A reset 100 s into a session starts it on the restored boat clock
// (Boat.Reset zeroes it), and time the UI holds her (the loading screen, the briefing) is left out.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingStartHoldSmokeTest, "SailingSim.Smoke.StartHold", StartHoldFlags)
bool FSailingStartHoldSmokeTest::RunTest(const FString&)
{
	FStartHoldWorld W;
	ASailboatPawn* Boat = W.World->SpawnActor<ASailboatPawn>(FVector::ZeroVector, FRotator::ZeroRotator);
	if (!TestNotNull(TEXT("A boat"), Boat)) return false;
	Boat->GetMutableBoatModel().GetMutableState().Time = 100.0;
	Boat->ResetBoat();
	TestEqual(TEXT("ResetBoat keeps the clock (100 s)"), Boat->GetBoatModel().GetState().Time, 100.0);
	TestEqual(TEXT("... and starts the hold on it"), Boat->GetSecondsSinceStart(), 0.0, 1e-6);
	Boat->SetHeldByUI(true);
	Boat->GetMutableBoatModel().GetMutableState().Time = 130.0;   // 30 s on the loading screen
	TestEqual(TEXT("Held: the hold's clock stands"), Boat->GetSecondsSinceStart(), 0.0, 1e-6);
	Boat->SetHeldByUI(false);
	TestEqual(TEXT("Let go after 30 s held: still 0"), Boat->GetSecondsSinceStart(), 0.0, 1e-6);
	Boat->GetMutableBoatModel().GetMutableState().Time = 136.0;
	TestEqual(TEXT("6 s after: 6"), Boat->GetSecondsSinceStart(), 6.0, 1e-6);
	TestTrue(TEXT("... inside the hold"), Boat->GetSecondsSinceStart() < SailingNoGoTipHoldSeconds);
	return true;
}

#endif
