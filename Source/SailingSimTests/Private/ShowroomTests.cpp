#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Engine/StaticMeshActor.h"
#include "GameFramework/WorldSettings.h"
#include "UObject/UObjectGlobals.h"
#include "FreeCamera.h"
#include "Showroom.h"
#include "SailboatPawn.h"
#include "SailingGameMode.h"
#include "UI/SailFrontEnd.h"
#include "WaterSurface.h"

#if WITH_DEV_AUTOMATION_TESTS

// docs/showroom-wiring/: the wiring the Boat and Conditions screens sit on (Inputs/ui-showroom/brief.md, Mac PR 1).
namespace
{
	constexpr EAutomationTestFlags ShowroomFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

	struct FBareWorld
	{
		UWorld* World = nullptr;
		FBareWorld()
		{
			World = UWorld::CreateWorld(EWorldType::Game, false, TEXT("SailingShowroomWorld"));
			FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
			Context.SetCurrentWorld(World);
			World->InitializeActorsForPlay(FURL());
			World->GetWorldSettings()->NotifyBeginPlay();
		}
		~FBareWorld()
		{
			World->EndPlay(EEndPlayReason::Quit);
			GEngine->DestroyWorldContext(World);
			World->DestroyWorld(false);
		}
		void Tick(int32 Frames)
		{
			for (int32 I = 0; I < Frames; ++I)
			{
				++GFrameCounter;
				World->Tick(LEVELTICK_All, 1.f / 60.f);
			}
		}
	};
}

// The pure parts: which screen shows which stage, when two sets of conditions look alike, the debounce, and the
// showroom spot (open water off the slip).
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingShowroomLogicTest, "SailingSim.UI.Showroom.Logic", ShowroomFlags)
bool FSailingShowroomLogicTest::RunTest(const FString&)
{
	using namespace SailShowroom;
	TestTrue(TEXT("The Boat screen is the showroom"), StageFor(ESailScreen::Boat, false) == EShowroomStage::Boat);
	TestTrue(TEXT("Conditions is the weather preview"), StageFor(ESailScreen::Conditions, false) == EShowroomStage::Weather);
	TestTrue(TEXT("The title is the chase camera"), StageFor(ESailScreen::Title, false) == EShowroomStage::None);
	TestTrue(TEXT("World, Launch and Mode too"), StageFor(ESailScreen::World, false) == EShowroomStage::None
		&& StageFor(ESailScreen::Launch, false) == EShowroomStage::None && StageFor(ESailScreen::Mode, false) == EShowroomStage::None);
	TestTrue(TEXT("In game, Change conditions previews"), StageFor(ESailScreen::ConditionsInGame, true) == EShowroomStage::Weather);
	TestTrue(TEXT("In game, Pause does not"), StageFor(ESailScreen::Pause, true) == EShowroomStage::None);
	TestTrue(TEXT("In game there is no showroom"), StageFor(ESailScreen::Boat, true) == EShowroomStage::None);

	FSailConditions A, B;
	TestTrue(TEXT("Equal conditions"), SameConditions(A, B));
	B.LocalHour += 0.25f;
	TestFalse(TEXT("A quarter hour later differs"), SameConditions(A, B));
	B = A;
	B.RealDay = TEXT("2024-05-28");
	TestFalse(TEXT("A real day differs"), SameConditions(A, B));

	FSailDebounce D;
	D.DelaySeconds = 0.2;
	TestFalse(TEXT("Nothing changed: nothing fires"), D.Fire(1.0));
	D.Changed(1.0);
	TestFalse(TEXT("Not yet after 0.1 s"), D.Fire(1.1));
	D.Changed(1.15);
	TestFalse(TEXT("A new change restarts the wait"), D.Fire(1.3));
	TestTrue(TEXT("Fires 0.2 s after the last change"), D.Fire(1.36));
	TestFalse(TEXT("Once"), D.Fire(2.0));

	// A shore along x = 0 (land to the west, water deepening east at 10 cm a metre to 8 m), a slip at the shore.
	auto Height = [](double X, double) { return X < 0.0 ? 2.0 : -FMath::Min(0.1 * X, 8.0); };
	const FVector2D Open = FindOpenWater(Height, 5.0, 0.0);
	TestTrue(FString::Printf(TEXT("From the slip: open water %.0f m out"), Open.X), Open.X >= 60.0 && Open.X <= 100.0 && FMath::Abs(Open.Y) < 1.0);
	TestTrue(TEXT("3 m deep there, 60 m clear of the shore"), Height(Open.X, Open.Y) <= -3.0 && Open.X - 60.0 >= 0.0);
	const FVector2D Already = FindOpenWater(Height, 400.0, 30.0);
	TestTrue(TEXT("Already in open water: stays"), Already.Equals(FVector2D(400.0, 30.0), 1e-9));
	auto Land = [](double, double) { return 5.0; };
	TestTrue(TEXT("Nothing open: stays"), FindOpenWater(Land, 7.0, 8.0).Equals(FVector2D(7.0, 8.0), 1e-9));
	return true;
}

// The orbit parameters set from code: the framing's distance, pitch limits and offsets; it turns by itself once left
// alone for the idle delay and stops when looked with.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingShowroomOrbitTest, "SailingSim.UI.Showroom.Orbit", ShowroomFlags)
bool FSailingShowroomOrbitTest::RunTest(const FString&)
{
	FBareWorld W;
	AActor* Boat = W.World->SpawnActor<AStaticMeshActor>(FVector::ZeroVector, FRotator::ZeroRotator);
	AFreeCamera* Cam = W.World->SpawnActor<AFreeCamera>(FVector(-2000.0, 0.0, 500.0), FRotator::ZeroRotator);
	if (!TestNotNull(TEXT("A camera"), Cam)) return false;
	Cam->SetAnchor(Boat, FVector(0.0, 0.0, 400.0));
	Cam->Limits.WaterClearM = 0.5;
	FFreeCameraOrbit O;
	O.DistanceCm = 1500.f;
	O.MinDistanceCm = 900.f;
	O.MaxDistanceCm = 2400.f;
	O.PitchDeg = -12.f;
	O.MinPitchDeg = -35.f;
	O.MaxPitchDeg = -3.f;
	O.YawDeg = 0.f;
	O.SpinDegPerSec = 6.f;
	O.SpinIdleSeconds = 4.f;
	O.EaseSeconds = 0.6f;
	Cam->SetOrbit(O);
	FFreeCameraInput None;
	for (int32 I = 0; I < 45; ++I) Cam->Update(1.f / 60.f, None);
	const double Partway = FVector::Dist(Cam->GetActorLocation(), Cam->GetPivot());
	TestTrue(FString::Printf(TEXT("Eases over: nearly there after 0.75 s at a 0.6 s ease: %.0f cm"), Partway), Partway > 1450.0 && Partway < 1560.0);
	for (int32 I = 0; I < 120; ++I) Cam->Update(1.f / 60.f, None);
	TestEqual(TEXT("At its distance"), FVector::Dist(Cam->GetActorLocation(), Cam->GetPivot()), 1500.0, 5.0);
	TestTrue(TEXT("Facing the pivot"), FVector::DotProduct((Cam->GetPivot() - Cam->GetActorLocation()).GetSafeNormal(), Cam->GetActorForwardVector()) > 0.999);

	// Spinning from the start (a framing set from code), then looked with: it stops for the idle delay, then turns again.
	const float Y0 = float(Cam->GetActorRotation().Yaw);
	for (int32 I = 0; I < 60; ++I) Cam->Update(1.f / 60.f, None);
	TestTrue(TEXT("Turns by itself at about 6 deg/s"), FMath::Abs(FMath::FindDeltaAngleDegrees(Y0, float(Cam->GetActorRotation().Yaw)) - 6.f) < 1.5f);
	Cam->AddLook(FVector2D(0.0, 0.0));
	Cam->AddLook(FVector2D(1.0, -100.0));
	for (int32 I = 0; I < 60; ++I) Cam->Update(1.f / 60.f, None);
	const float Y1 = float(Cam->GetActorRotation().Yaw);
	for (int32 I = 0; I < 120; ++I) Cam->Update(1.f / 60.f, None);
	TestTrue(TEXT("Looked with: still for the idle delay"), FMath::Abs(FMath::FindDeltaAngleDegrees(Y1, float(Cam->GetActorRotation().Yaw))) < 0.5f);
	for (int32 I = 0; I < 180; ++I) Cam->Update(1.f / 60.f, None);
	TestTrue(TEXT("Then turns again"), FMath::Abs(FMath::FindDeltaAngleDegrees(Y1, float(Cam->GetActorRotation().Yaw))) > 3.f);
	TestTrue(TEXT("Pitch held in its limits (pushed down 100 deg: 35 at most)"), Cam->GetActorRotation().Pitch >= -35.5 && Cam->GetActorRotation().Pitch <= -3.0);
	Cam->StepSpeed(-10);
	TestEqual(TEXT("Zoom held at its far limit"), double(Cam->GetOrbit().DistanceCm), 2400.0, 0.01);

	// The lateral offset: the pivot moves right of the view, so the subject sits left of centre (or right, negative).
	FFreeCameraOrbit Side = O;
	Side.SpinDegPerSec = 0.f;
	Side.LateralOffsetCm = -500.f;
	Cam->SetOrbit(Side);
	for (int32 I = 0; I < 240; ++I) Cam->Update(1.f / 60.f, None);
	const FVector ToBoat = (FVector(0.0, 0.0, 400.0) - Cam->GetActorLocation());
	const double Right = FVector::DotProduct(ToBoat, Cam->GetActorRightVector());
	TestTrue(FString::Printf(TEXT("Negative offset: the boat right of centre (%.0f cm)"), Right), Right > 300.0);
	return true;
}

// The pawn on a stage: afloat and sailing, the helm holding a close reach, the sails trimmed; a boat swapped in where
// she is (loaded asynchronously, then built), the same spot and heading.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingShowroomPawnTest, "SailingSim.Smoke.ShowroomSwap", ShowroomFlags)
bool FSailingShowroomPawnTest::RunTest(const FString&)
{
	FBareWorld W;
	W.World->SpawnActor<AWaterSurface>(FVector::ZeroVector, FRotator::ZeroRotator);
	ASailboatPawn* Boat = W.World->SpawnActor<ASailboatPawn>(FVector(1000.f, 0.f, 0.f), FRotator(0.f, 90.f, 0.f));
	if (!TestNotNull(TEXT("A boat"), Boat)) return false;
	Boat->SetHeldByUI(true);
	W.Tick(60);
	const double HeldTime = Boat->GetBoatModel().GetState().Time;
	W.Tick(60);
	TestEqual(TEXT("Held by the menus: still (no steps)"), Boat->GetBoatModel().GetState().Time, HeldTime);
	const FVector OnStage = Boat->GetActorLocation();
	Boat->SetShowroomStage(EShowroomStage::Boat, false);
	W.Tick(60 * 15);
	TestTrue(FString::Printf(TEXT("Fifteen seconds sailing: still on her spot (%.0f cm off)"), FVector::Dist2D(OnStage, Boat->GetActorLocation())),
		FVector::Dist2D(OnStage, Boat->GetActorLocation()) < 150.0);
	const Sailing::FBoatTelemetry& T = Boat->GetBoatModel().GetTelemetry();
	TestTrue(TEXT("On the stage the physics runs"), Boat->GetBoatModel().GetState().Time > HeldTime + 10.0);
	TestTrue(FString::Printf(TEXT("The helm holds a close reach: TWA %.0f"), FMath::RadiansToDegrees(T.TrueWindAngle)),
		FMath::Abs(FMath::Abs(FMath::RadiansToDegrees(T.TrueWindAngle)) - 70.0) < 15.0);
	TestTrue(FString::Printf(TEXT("Sailing: %.1f kn, heel %.0f deg"), T.BoatSpeed / Sailing::kKnot, FMath::RadiansToDegrees(T.Heel)),
		T.BoatSpeed > 1.0 && FMath::Abs(T.Heel) > 0.02);

	const FVector At = Boat->GetActorLocation();
	const float Yaw = float(Boat->GetActorRotation().Yaw);
	Boat->ShowBoat(int32(Sailing::EBoatType::Hobie16));
	for (int32 I = 0; I < 600 && Boat->GetShowroomLoadingType() >= 0; ++I)
	{
		FlushAsyncLoading();
		W.Tick(1);
	}
	TestEqual(TEXT("The Hobie is shown"), Boat->GetBoatTypeIndex(), int32(Sailing::EBoatType::Hobie16));
	TestTrue(FString::Printf(TEXT("Where the J/22 was (%.0f cm off)"), FVector::Dist2D(At, Boat->GetActorLocation())), FVector::Dist2D(At, Boat->GetActorLocation()) < 150.0);
	TestTrue(TEXT("On her heading"), FMath::Abs(FMath::FindDeltaAngleDegrees(Yaw, float(Boat->GetActorRotation().Yaw))) < 5.f);
	Boat->ShowBoat(int32(Sailing::EBoatType::Hobie16));
	TestEqual(TEXT("The shown boat again: nothing to load"), Boat->GetShowroomLoadingType(), -1);
	Boat->SetShowroomStage(EShowroomStage::None, false);
	const double Off = Boat->GetBoatModel().GetState().Time;
	W.Tick(60);
	TestEqual(TEXT("Off the stage, held still again"), Boat->GetBoatModel().GetState().Time, Off);
	return true;
}

// Rule 9 and the preview: Change conditions keeps the world live even while something holds it (photo mode's switch).
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingShowroomLiveTest, "SailingSim.Smoke.ShowroomPreviewLive", ShowroomFlags)
bool FSailingShowroomLiveTest::RunTest(const FString&)
{
	FBareWorld W;
	ASailingGameMode* GM = W.World->SpawnActor<ASailingGameMode>();
	if (!TestNotNull(TEXT("A game mode"), GM)) return false;
	auto Frames = [&](int32 N) { for (int32 I = 0; I < N; ++I) { ++GFrameCounter; GM->AdvanceClock(1.f / 60.f); } };
	GM->SetWorldHeld(true);
	Frames(60);
	const double T0 = GM->GetSimTime();
	GM->SetPreviewLive(true);
	TestFalse(TEXT("The preview lifts the hold"), GM->IsWorldHeld());
	Frames(60);
	TestEqual(TEXT("The clock runs while the preview is live"), GM->GetSimTime(), T0 + 1.0, 1.0 / 60.0);
	GM->SetPreviewLive(false);
	TestTrue(TEXT("And the hold stands again after"), GM->IsWorldHeld());
	const double T1 = GM->GetSimTime();
	Frames(60);
	TestEqual(TEXT("Held"), GM->GetSimTime(), T1);
	GM->SetWorldHeld(false);
	TestFalse(TEXT("No preview: EndPreview does nothing"), GM->IsPreviewing());
	GM->EndPreview(false);
	return true;
}

#endif
