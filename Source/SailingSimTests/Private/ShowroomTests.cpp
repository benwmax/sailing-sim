#include "Misc/AutomationTest.h"
#include "BareTestWorld.h"
#include "Engine/StaticMeshActor.h"
#include "UObject/UObjectGlobals.h"
#include "FreeCamera.h"
#include "Showroom.h"
#include "SailboatPawn.h"
#include "SailingGameMode.h"
#include "UI/SailFrontEnd.h"
#include "WaterSurface.h"
#include "SailSession.h"
#include "SailingSettings.h"
#include "Engine/GameInstance.h"

#if WITH_DEV_AUTOMATION_TESTS

// docs/showroom-wiring/: the wiring the Boat and Conditions screens sit on (Inputs/ui-showroom/brief.md, Mac PR 1).
namespace
{
	constexpr EAutomationTestFlags ShowroomFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

	// Every test that ticks a bare game world goes through BareTestWorld.h, which ends play before the world goes.
	struct FBareWorld : FBareTestWorld { FBareWorld() : FBareTestWorld(TEXT("SailingShowroomWorld")) {} };
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


// #623 follow-up: backing out of Change conditions puts the weather back as it was. In a thunderstorm 30 s in, a previewed
// change starts a new timeline (as before); EndPreview(false) restores the inputs and keeps the weather's clock, so the
// storm front is as far off as it was and the weather time runs on from where it stood.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingConditionsKeepTimeTest, "SailingSim.Smoke.ConditionsKeepTime", ShowroomFlags)
bool FSailingConditionsKeepTimeTest::RunTest(const FString&)
{
	USailingSettings* S = USailingSettings::Get();
	const ESailingWeather WasPreset = S->WeatherPreset;
	const float WasHour = S->StartHour;
	FBareWorld W;
	ASailingGameMode* GM = W.World->SpawnActor<ASailingGameMode>();
	if (!TestNotNull(TEXT("A game mode"), GM)) return false;
	auto Frames = [&](int32 N) { for (int32 I = 0; I < N; ++I) { ++GFrameCounter; GM->AdvanceClock(1.f / 60.f); } };
	FSailConditions Storm;
	Storm.Sky = ESailSky::Storms;
	Storm.WindKn = 10.f;
	Storm.GustKn = 14.f;
	Storm.LocalHour = 15.f;
	GM->ApplyConditions(Storm);
	TestEqual(TEXT("A thunderstorm"), int32(S->WeatherPreset), USailSessionSubsystem::WeatherPresetFor(ESailSky::Storms));
	Frames(30 * 60);
	const double Tw = GM->GetWeatherTime();
	const double Km = GM->GetWeather().Evaluate(Tw).StormDistanceKm;
	const double Hour = GM->GetLocalHour();
	TestTrue(FString::Printf(TEXT("30 s of weather (%.2f s)"), Tw), FMath::Abs(Tw - 30.0) < 0.1);
	FSailConditions Fair = Storm;
	Fair.Sky = ESailSky::Fair;
	Fair.WindKn = 8.f;
	Fair.GustKn = 11.f;
	GM->PreviewConditions(Fair);
	TestTrue(TEXT("Previewing"), GM->IsPreviewing());
	TestTrue(FString::Printf(TEXT("A previewed change starts the weather over (%.2f s)"), GM->GetWeatherTime()), GM->GetWeatherTime() < 0.1);
	Frames(2 * 60);
	GM->EndPreview(false);
	TestEqual(TEXT("Put back: the thunderstorm"), int32(S->WeatherPreset), USailSessionSubsystem::WeatherPresetFor(ESailSky::Storms));
	TestEqual(TEXT("Put back: the weather time runs on from where it stood"), GM->GetWeatherTime(), Tw + 2.0, 1.0 / 30.0);
	const double KmAfter = GM->GetWeather().Evaluate(Tw).StormDistanceKm;
	TestEqual(FString::Printf(TEXT("Put back: the front where it was (%.3f km)"), Km), KmAfter, Km, 1e-6);
	// #624 QA: the day's clock (sun, HUD, tide) runs on with the weather's, not back to the start hour.
	TestEqual(TEXT("Put back: the local hour runs on"), GM->GetLocalHour(), Hour + 2.0 / 3600.0, 1.0 / 3600.0);
	AddInfo(FString::Printf(TEXT("Front %.3f km off at %.1f s; after the preview and Back, %.1f s of weather"), Km, Tw, GM->GetWeatherTime()));
	// The difficulty toggle (Easy and back to Realistic) re-applies the wind, keeping the weather's clock too.
	const ESailingDifficulty WasDifficulty = S->Difficulty;
	const double Before = GM->GetWeatherTime();
	const double KmBefore = GM->GetWeather().Evaluate(Before).StormDistanceKm;
	const double HourBefore = GM->GetLocalHour();
	for (const ESailingDifficulty D : { ESailingDifficulty::Easy, ESailingDifficulty::Realistic })
	{
		S->Difficulty = D;
		GM->ApplyDifficultyToWind();
		TestEqual(FString::Printf(TEXT("Difficulty %s: the weather time as it was"), D == ESailingDifficulty::Easy ? TEXT("Easy") : TEXT("Realistic")), GM->GetWeatherTime(), Before, 1e-6);
		TestEqual(TEXT("... and the front"), GM->GetWeather().Evaluate(GM->GetWeatherTime()).StormDistanceKm, KmBefore, 1e-6);
		TestEqual(TEXT("... and the local hour"), GM->GetLocalHour(), HourBefore, 1e-6);
	}
	S->Difficulty = WasDifficulty;
	S->WeatherPreset = WasPreset;
	S->StartHour = WasHour;
	return true;
}

// #624 QA: with a session running, a preview that lands back on its own conditions puts the weather back as it was (the
// screen's slider moved and moved back), and Apply on its own conditions keeps the weather's clock; a real Apply starts over.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingConditionsKeepTimeSessionTest, "SailingSim.Smoke.ConditionsKeepTimeSession", ShowroomFlags)
bool FSailingConditionsKeepTimeSessionTest::RunTest(const FString&)
{
	USailingSettings* S = USailingSettings::Get();
	const ESailingWeather WasPreset = S->WeatherPreset;
	const float WasHour = S->StartHour;
	FBareWorld W;
	UGameInstance* GI = W.UseGameInstance();
	GI->Init();   // its subsystems: the session
	ASailingGameMode* GM = W.World->SpawnActor<ASailingGameMode>();
	if (!TestNotNull(TEXT("A game mode"), GM)) return false;
	USailSessionSubsystem* Session = USailSessionSubsystem::Get(GM);
	if (!TestNotNull(TEXT("A session subsystem"), Session)) { GI->Shutdown(); return false; }
	auto Frames = [&](int32 N) { for (int32 I = 0; I < N; ++I) { ++GFrameCounter; GM->AdvanceClock(1.f / 60.f); } };
	FSailConditions Storm;
	Storm.Sky = ESailSky::Storms;
	Storm.WindKn = 10.f;
	Storm.GustKn = 14.f;
	Storm.LocalHour = 15.f;
	Session->bHasActive = true;
	Session->Active.Conditions = Storm;
	GM->ApplyConditions(Storm);
	Frames(20 * 60);
	const double Tw = GM->GetWeatherTime(), Hour = GM->GetLocalHour();
	FSailConditions Fair = Storm;
	Fair.Sky = ESailSky::Fair;
	GM->PreviewConditions(Fair);
	TestTrue(TEXT("A previewed change starts over"), GM->GetWeatherTime() < 0.1);
	GM->PreviewConditions(Storm);   // the slider back where it was
	TestEqual(TEXT("Previewed back on the session's own: the weather time as it was"), GM->GetWeatherTime(), Tw, 1e-6);
	TestEqual(TEXT("... and the hour"), GM->GetLocalHour(), Hour, 1e-6);
	GM->ApplyConditions(Storm);
	TestEqual(TEXT("Apply on the session's own conditions: the weather time kept"), GM->GetWeatherTime(), Tw, 1e-6);
	Frames(60);
	GM->ApplyConditions(Storm);
	TestEqual(TEXT("Apply unchanged, no preview: kept"), GM->GetWeatherTime(), Tw + 1.0, 1.0 / 30.0);
	GM->ApplyConditions(Fair);
	TestTrue(TEXT("A real change applied starts over"), GM->GetWeatherTime() < 0.1);
	Session->bHasActive = false;
	GI->Shutdown();
	S->WeatherPreset = WasPreset;
	S->StartHour = WasHour;
	return true;
}

// docs/showroom-world/: the picked world loads behind the menus. Leaving the World screen for Launch with another world
// travels (not in game, not for the world already loaded); the session carries the choices and the screen to come back to,
// and the settings' world and spot are the picked ones (nothing saved).
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingShowroomWorldTest, "SailingSim.UI.Showroom.WorldBehindMenus", ShowroomFlags)
bool FSailingShowroomWorldTest::RunTest(const FString&)
{
	TestTrue(TEXT("World to Launch with another world travels"), SSailFrontEnd::TravelsOnPush(ESailScreen::World, ESailScreen::Launch, false, 1, 0));
	TestFalse(TEXT("The world already loaded does not"), SSailFrontEnd::TravelsOnPush(ESailScreen::World, ESailScreen::Launch, false, 0, 0));
	TestFalse(TEXT("Nor in game"), SSailFrontEnd::TravelsOnPush(ESailScreen::World, ESailScreen::Launch, true, 1, 0));
	TestFalse(TEXT("Nor any other push"), SSailFrontEnd::TravelsOnPush(ESailScreen::Launch, ESailScreen::Boat, false, 1, 0));

	UGameInstance* GI = NewObject<UGameInstance>(GetTransientPackage());
	USailSessionSubsystem* Session = NewObject<USailSessionSubsystem>(GI);
	USailingSettings* S = USailingSettings::Get();
	const int32 WasWorld = S->World, WasSpot = S->LaunchSpot;
	FSailSessionConfig Pending = USailSessionSubsystem::MakeDefault();
	Pending.World = 1;
	Pending.LaunchSpot = 2;
	Pending.Boat = 5;
	Session->TravelBehindMenus(Pending, int32(ESailScreen::Launch), nullptr);
	TestEqual(TEXT("The screen to come back to"), Session->MenuResumeScreen, int32(ESailScreen::Launch));
	TestTrue(TEXT("The choices carried"), Session->bHasPending && Session->Pending.Boat == 5 && Session->Pending.World == 1);
	TestTrue(TEXT("The picked place in the settings"), S->World == 1 && S->LaunchSpot == 2);
	Session->ResetForRun();
	TestEqual(TEXT("A new run ends the travel"), Session->MenuResumeScreen, -1);
	TestFalse(TEXT("And the pending choices"), Session->bHasPending);
	S->World = WasWorld;
	S->LaunchSpot = WasSpot;
	return true;
}

#endif
