#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Components/StaticMeshComponent.h"
#include "GameFramework/WorldSettings.h"
#include "InputAction.h"
#include "InputMappingContext.h"
#include "InputTriggers.h"
#include "FreeCamera.h"
#include "SailboatPawn.h"
#include "SailingBindings.h"
#include "SailingGameMode.h"
#include "SailingSettings.h"
#include "PhotoSettings.h"

#if WITH_DEV_AUTOMATION_TESTS

// Photo mode PR 1 (docs/photo-freefly/): the free camera's limits, its input context over the boat's, and the world held.
namespace
{
	constexpr EAutomationTestFlags PhotoFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

	struct FBareWorld
	{
		UWorld* World = nullptr;
		FBareWorld()
		{
			World = UWorld::CreateWorld(EWorldType::Game, false, TEXT("SailingPhotoWorld"));
			FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
			Context.SetCurrentWorld(World);
			World->InitializeActorsForPlay(FURL());
			World->GetWorldSettings()->NotifyBeginPlay();
		}
		~FBareWorld()
		{
			GEngine->DestroyWorldContext(World);
			World->DestroyWorld(false);
		}
	};

	/** The actions a context maps a key to. */
	TArray<FName> ActionsOn(const UInputMappingContext* Context, const FKey& Key)
	{
		TArray<FName> Out;
		for (const FEnhancedActionKeyMapping& M : Context->GetMappings())
		{
			if (M.Key == Key && M.Action) Out.Add(FName(*M.Action->GetName().RightChop(3))); // IA_<name>
		}
		return Out;
	}

	bool Only(const TArray<FName>& On, FName Action) { return On.Num() == 1 && On[0] == Action; }

	template <class T>
	bool HasTrigger(const UInputMappingContext* Context, const FKey& Key, FName Action)
	{
		for (const FEnhancedActionKeyMapping& M : Context->GetMappings())
		{
			if (M.Key != Key || !M.Action || M.Action->GetName() != TEXT("IA_") + Action.ToString()) continue;
			for (const TObjectPtr<UInputTrigger>& Trig : M.Triggers) if (Cast<T>(Trig)) return true;
		}
		return false;
	}
}

// The arithmetic: the leash softens over its last 500 m and holds at 5 km, the floor is over the wave and the ground,
// the ceiling at 1,500 m, the speeds step from walking to 120 m/s and ease in about a quarter second.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingPhotoLimitsTest, "SailingSim.UI.PhotoFreeFly.Limits", PhotoFlags)
bool FSailingPhotoLimitsTest::RunTest(const FString&)
{
	using namespace FreeCameraMath;
	const FFreeCameraLimits L;
	TestEqual(TEXT("The leash is 5 km"), L.LeashM, 5000.0);
	TestEqual(TEXT("Full speed inside the soft stretch"), LeashScale(4400.0, L), 1.0);
	TestEqual(TEXT("Half way down it at 4.75 km"), LeashScale(4750.0, L), 0.5, 1e-9);
	TestEqual(TEXT("Nothing outward at the leash"), LeashScale(5000.0, L), 0.0);
	const FVector2D Out = LeashVelocity(FVector2D(4750.0, 0.0), FVector2D(10.0, 10.0), L);
	TestEqual(TEXT("Near the leash: outward halved"), Out.X, 5.0, 1e-9);
	TestEqual(TEXT("Near the leash: along the circle free"), Out.Y, 10.0, 1e-9);
	TestEqual(TEXT("Back toward the boat is free"), LeashVelocity(FVector2D(5000.0, 0.0), FVector2D(-30.0, 0.0), L).X, -30.0, 1e-9);
	TestEqual(TEXT("At the leash nothing goes out"), LeashVelocity(FVector2D(0.0, -5000.0), FVector2D(0.0, -30.0), L).Y, 0.0, 1e-9);
	const FVector2D Clamped = ClampToLeash(FVector2D(6000.0, 8000.0), L);
	TestEqual(TEXT("A place past the leash comes back onto it"), Clamped.Size(), 5000.0, 1e-6);
	TestEqual(TEXT("On the same bearing"), Clamped.X / Clamped.Y, 0.75, 1e-9);
	TestTrue(TEXT("Inside the leash: unchanged"), ClampToLeash(FVector2D(100.0, 200.0), L).Equals(FVector2D(100.0, 200.0), 1e-9));

	// Floor and ceiling (heights above the water at rest; the wave at the camera, the ground under it).
	TestEqual(TEXT("Over water: 15 cm above the wave top"), ClampHeightM(-3.0, 0.4, -6.0, L), 0.55, 1e-9);
	TestEqual(TEXT("In a trough: 15 cm above the trough"), ClampHeightM(-3.0, -0.4, -6.0, L), -0.25, 1e-9);
	TestEqual(TEXT("Over land: 50 cm above the ground"), ClampHeightM(2.0, 0.0, 12.0, L), 12.5, 1e-9);
	TestEqual(TEXT("A shoal under a wave: the wave wins"), FloorM(0.3, -0.1, L), 0.45, 1e-9);
	TestEqual(TEXT("The ceiling is 1,500 m"), ClampHeightM(2400.0, 0.0, -10.0, L), 1500.0, 1e-9);
	TestEqual(TEXT("A summit above the ceiling: over the summit"), ClampHeightM(1600.0, 0.0, 1700.0, L), 1700.5, 1e-9);
	TestEqual(TEXT("In between: free"), ClampHeightM(42.0, 0.2, -3.0, L), 42.0);

	TestEqual(TEXT("Five speeds"), NumSpeeds, 5);
	TestEqual(TEXT("Slowest: walking"), SpeedStep(0), 0.5);
	TestEqual(TEXT("Fastest: 120 m/s"), SpeedStep(NumSpeeds - 1), 120.0);
	TestEqual(TEXT("Steps past the ends hold"), SpeedStep(9), 120.0);
	TestEqual(TEXT("Boost is five times"), Speed(2, true, false), 40.0, 1e-9);
	TestEqual(TEXT("Precision a fifth"), Speed(2, false, true), 1.6, 1e-9);
	double V = 0.0;
	for (int32 I = 0; I < 15; ++I) V += (1.0 - V) * EaseAlpha(1.0 / 60.0);
	TestTrue(TEXT("Eased: 95% of the speed after a quarter second"), FMath::Abs(V - 0.95) < 0.01);
	double V30 = 0.0;
	for (int32 I = 0; I < 8; ++I) V30 += (1.0 - V30) * EaseAlpha(1.0 / 30.0);
	TestTrue(TEXT("The same at 30 fps"), FMath::Abs(V30 - (1.0 - FMath::Exp(-3.0 * 8.0 / 30.0 / 0.25))) < 1e-9 && V30 > 0.93);
	return true;
}

// The actor in a bare world: flown flat out away from its anchor it stops at 5 km, flown down it stops 15 cm over the
// water, flown up at 1,500 m; a box in its way stops it short; orbit faces the anchor; back to the boat is still.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingPhotoCameraTest, "SailingSim.UI.PhotoFreeFly.Camera", PhotoFlags)
bool FSailingPhotoCameraTest::RunTest(const FString&)
{
	FBareWorld W;
	AActor* Boat = W.World->SpawnActor<AStaticMeshActor>(FVector::ZeroVector, FRotator::ZeroRotator);
	AFreeCamera* Cam = W.World->SpawnActor<AFreeCamera>(FVector(0.0, 0.0, 1000.0), FRotator::ZeroRotator);
	if (!TestNotNull(TEXT("The camera spawns"), Cam) || !TestNotNull(TEXT("The anchor spawns"), Boat)) return false;
	Cam->SetAnchor(Boat);
	Cam->SnapTo(FVector(0.0, 0.0, 1000.0), FRotator::ZeroRotator);
	for (int32 I = 0; I < 4; ++I) Cam->StepSpeed(1);
	TestEqual(TEXT("Top speed"), Cam->GetBaseSpeed(), 120.0);

	FFreeCameraInput Fly;
	Fly.Move = FVector2D(0.0, 1.0);
	Fly.bBoost = true; // 600 m/s
	double MaxDist = 0.0;
	for (int32 I = 0; I < 60 * 20; ++I)
	{
		Cam->Update(1.f / 60.f, Fly);
		MaxDist = FMath::Max(MaxDist, Cam->GetLeashDistanceM());
	}
	TestTrue(TEXT("Flown away for 20 s at 600 m/s: never past 5 km"), MaxDist <= 5000.0 + 1e-6);
	TestTrue(FString::Printf(TEXT("And close to it (the last 500 m ease in): %.0f m"), MaxDist), MaxDist > 4900.0);
	TestTrue(TEXT("The leash shows"), Cam->IsAtLeash());
	TestTrue(TEXT("Level heading: still at 10 m"), FMath::IsNearlyEqual(Cam->GetActorLocation().Z, 1000.0, 1.0));

	// Down onto the water (flat: no game mode), then up to the ceiling.
	FFreeCameraInput Down;
	Down.Vertical = -1.f;
	for (int32 I = 0; I < 120; ++I) Cam->Update(1.f / 60.f, Down);
	TestEqual(TEXT("Floor: 15 cm over the water"), Cam->GetActorLocation().Z, 15.0, 0.5);
	FFreeCameraInput Up;
	Up.Vertical = 1.f;
	Up.bBoost = true;
	for (int32 I = 0; I < 60 * 6; ++I) Cam->Update(1.f / 60.f, Up);
	TestEqual(TEXT("Ceiling: 1,500 m"), Cam->GetActorLocation().Z, 150000.0, 0.5);

	// A box in the way (visibility collision), 20 m ahead: the camera stops at it, its 20 cm sphere outside.
	UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
	AStaticMeshActor* Wall = W.World->SpawnActor<AStaticMeshActor>(FVector(2000.0, 0.0, 500.0), FRotator::ZeroRotator);
	if (Cube && Wall)
	{
		Wall->GetStaticMeshComponent()->SetMobility(EComponentMobility::Movable);
		Wall->GetStaticMeshComponent()->SetStaticMesh(Cube);
		Wall->GetStaticMeshComponent()->SetWorldScale3D(FVector(1.0, 20.0, 20.0)); // 1 m thick, 20 m across
		Wall->GetStaticMeshComponent()->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
		Wall->GetStaticMeshComponent()->SetCollisionResponseToAllChannels(ECR_Block);
		++GFrameCounter;
		W.World->Tick(LEVELTICK_All, 1.f / 60.f); // the physics scene takes the box in at a tick
		Cam->SnapTo(FVector(0.0, 0.0, 500.0), FRotator::ZeroRotator);
		FFreeCameraInput Ahead;
		Ahead.Move = FVector2D(0.0, 1.0);
		while (Cam->GetSpeedIndex() > 2) Cam->StepSpeed(-1); // 8 m/s
		for (int32 I = 0; I < 60 * 6; ++I) Cam->Update(1.f / 60.f, Ahead);
		const double X = Cam->GetActorLocation().X;
		TestTrue(FString::Printf(TEXT("Stopped at the wall's face (1950 cm) less its sphere: %.1f cm"), X), X < 1950.0 - 19.0 && X > 1900.0);
	}

	// Orbit faces the anchor's pivot; the wheel moves it in.
	Cam->SnapTo(FVector(-3000.0, 0.0, 600.0), FRotator::ZeroRotator);
	Cam->SetAnchor(Boat, FVector(0.0, 0.0, 300.0));
	Cam->SetMode(EFreeCameraMode::Orbit);
	for (int32 I = 0; I < 60; ++I) Cam->Update(1.f / 60.f, FFreeCameraInput());
	const FVector ToPivot = (FVector(0.0, 0.0, 300.0) - Cam->GetActorLocation()).GetSafeNormal();
	TestTrue(TEXT("Orbit faces the pivot"), FVector::DotProduct(ToPivot, Cam->GetActorForwardVector()) > 0.999);
	const double Before = FVector::Dist(Cam->GetActorLocation(), FVector(0.0, 0.0, 300.0));
	Cam->StepSpeed(2);
	for (int32 I = 0; I < 60; ++I) Cam->Update(1.f / 60.f, FFreeCameraInput());
	TestTrue(TEXT("The wheel moves the orbit in"), FVector::Dist(Cam->GetActorLocation(), FVector(0.0, 0.0, 300.0)) < Before * 0.8);
	TestEqual(TEXT("And leaves the fly speed alone"), Cam->GetSpeedIndex(), 2);

	// Back to the boat: put where asked, still.
	Cam->SetMode(EFreeCameraMode::Fly);
	Cam->SnapTo(FVector(100.0, 200.0, 300.0), FRotator(-10.0, 45.0, 0.0));
	Cam->Update(1.f / 60.f, FFreeCameraInput());
	TestTrue(TEXT("Snapped and still"), Cam->GetActorLocation().Equals(FVector(100.0, 200.0, 300.0), 0.01));
	// A still placed past the limits lands on them.
	Cam->PlaceAt(FVector(800000.0, 0.0, 300000.0), FRotator::ZeroRotator);
	TestEqual(TEXT("Placed 8 km out: on the leash"), Cam->GetLeashDistanceM(), 5000.0, 0.01);
	TestEqual(TEXT("Placed 3 km up: at the ceiling"), Cam->GetActorLocation().Z, 150000.0, 0.01);
	return true;
}

// The input context swap: in photo mode IMC_Photo sits above the boat's context and maps the keys and sticks the boat
// uses, so the left stick, WASD and the triggers fly the camera instead of steering and trimming. The pad's toggle is
// a half-second hold of View (its tap stays the controls card, and in photo mode the orbit toggle); A is the shutter
// only in photo mode. A saved key list from before photo mode gets the new commands' keys.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingPhotoInputTest, "SailingSim.UI.PhotoFreeFly.Input", PhotoFlags)
bool FSailingPhotoInputTest::RunTest(const FString&)
{
	using namespace SailingBindings;
	const TArray<FSailingKeyBinding>& Defaults = GetDefault<USailingInputSettings>()->GetDefaults();
	UObject* Outer = NewObject<UInputMappingContext>(GetTransientPackage()); // a fresh outer: the actions take fixed names
	TMap<FName, TObjectPtr<UInputAction>> Actions;
	ASailboatPawn::MakeActions(Outer, Defaults, Actions);
	const UInputMappingContext* Boat = ASailboatPawn::BuildContext(Outer, TEXT("IMC_TestBoat"), Defaults, Actions, false);
	const UInputMappingContext* Photo = ASailboatPawn::BuildContext(Outer, TEXT("IMC_TestPhoto"), Defaults, Actions, true);
	TestTrue(TEXT("Photo's context is above the boat's"), ASailboatPawn::PhotoContextPriority > 0);

	TestTrue(TEXT("Sailing, the left stick steers"), Only(ActionsOn(Boat, EKeys::Gamepad_LeftX), TEXT("Tiller")));
	TestTrue(TEXT("In photo mode it flies"), Only(ActionsOn(Photo, EKeys::Gamepad_LeftX), TEXT("PhotoRight")));
	TestTrue(TEXT("Photo mode takes W"), Only(ActionsOn(Photo, EKeys::W), TEXT("PhotoForward")));
	TestTrue(TEXT("And the right trigger"), Only(ActionsOn(Photo, EKeys::Gamepad_RightTriggerAxis), TEXT("PhotoUpDown")));
	TestTrue(TEXT("And Tab (orbit; Esc still leaves)"), Only(ActionsOn(Photo, EKeys::Tab), TEXT("PhotoOrbit")));
	bool bBoatClean = true, bPhotoClean = true;
	for (const FEnhancedActionKeyMapping& M : Boat->GetMappings())
	{
		const FName N(*M.Action->GetName().RightChop(3));
		if (IsPhotoAction(N) && !(N == TEXT("PhotoShot") && !M.Key.IsGamepadKey())) bBoatClean = false;
	}
	for (const FEnhancedActionKeyMapping& M : Photo->GetMappings())
	{
		const FName N(*M.Action->GetName().RightChop(3));
		if (!IsPhotoAction(N) && N != TEXT("Photo")) bPhotoClean = false;
	}
	TestTrue(TEXT("The boat's context has no camera commands (the shutter's Enter only)"), bBoatClean);
	TestTrue(TEXT("Photo's context has nothing of the boat's"), bPhotoClean);
	// Every key photo mode needs from the boat's context is in its own, so nothing reaches the boat while flying.
	TestTrue(TEXT("The stick's other axis flies too"), Only(ActionsOn(Photo, EKeys::Gamepad_LeftY), TEXT("PhotoForward")));
	for (const FKey& K : { EKeys::Gamepad_LeftX, EKeys::Gamepad_LeftTriggerAxis, EKeys::Gamepad_RightTriggerAxis,
		EKeys::Gamepad_LeftShoulder, EKeys::Gamepad_RightShoulder, EKeys::W, EKeys::A, EKeys::S, EKeys::D, EKeys::Q, EKeys::E, EKeys::Z, EKeys::C })
	{
		TestTrue(FString::Printf(TEXT("%s is photo mode's while it is open"), *K.ToString()), ActionsOn(Photo, K).Num() > 0 && ActionsOn(Boat, K).Num() > 0);
	}

	// The pad: the toggle is a hold of View, beside the controls card's tap; in photo mode beside the orbit's tap.
	TestTrue(TEXT("Sailing: hold View for photo mode"), HasTrigger<UInputTriggerHold>(Boat, EKeys::Gamepad_Special_Left, TEXT("Photo")));
	TestTrue(TEXT("Sailing: tap View for the controls card"), HasTrigger<UInputTriggerTap>(Boat, EKeys::Gamepad_Special_Left, TEXT("ControlsCard")));
	TestTrue(TEXT("Photo mode: hold View leaves"), HasTrigger<UInputTriggerHold>(Photo, EKeys::Gamepad_Special_Left, TEXT("Photo")));
	TestTrue(TEXT("Photo mode: tap View orbits"), HasTrigger<UInputTriggerTap>(Photo, EKeys::Gamepad_Special_Left, TEXT("PhotoOrbit")));
	TestTrue(TEXT("9 toggles on the press"), HasTrigger<UInputTriggerPressed>(Boat, EKeys::Nine, TEXT("Photo")));
	TestTrue(TEXT("Esc opens the menu on the press"), HasTrigger<UInputTriggerPressed>(Boat, EKeys::Escape, TEXT("Menu")));
	TestFalse(TEXT("Sailing, A is not the shutter"), ActionsOn(Boat, EKeys::Gamepad_FaceButton_Bottom).Contains(TEXT("PhotoShot")));
	TestTrue(TEXT("In photo mode A is"), Only(ActionsOn(Photo, EKeys::Gamepad_FaceButton_Bottom), TEXT("PhotoShot")));
	TestTrue(TEXT("Enter is the shutter in both (the Controls screen chooses with it)"),
		ActionsOn(Boat, EKeys::Enter).Contains(TEXT("PhotoShot")) && ActionsOn(Photo, EKeys::Enter).Contains(TEXT("PhotoShot")));

	// Layers: photo commands share keys with the boat's, never with each other.
	TestFalse(TEXT("Photo and boat layers may share a key"), SameLayer(TEXT("PhotoForward"), TEXT("MainSheet")));
	TestFalse(TEXT("Tab: orbit beside the menu"), SameLayer(TEXT("PhotoOrbit"), TEXT("Menu")));
	TestTrue(TEXT("Within photo mode keys clash"), SameLayer(TEXT("PhotoOrbit"), TEXT("PhotoToBoat")));
	TSet<FString> Seen;
	bool bUnique = true;
	for (const FSailingKeyBinding& B : Defaults)
	{
		if (!IsPhotoAction(B.Action)) continue;
		const FString K = B.Key.ToString();
		if (Seen.Contains(K)) { bUnique = false; AddInfo(FString::Printf(TEXT("%s twice in photo mode"), *K)); }
		Seen.Add(K);
	}
	TestTrue(TEXT("No key twice in photo mode's defaults"), bUnique);
	TArray<FSailingKeyBinding> L = Defaults;
	const FAssignResult R = Assign(L, TEXT("PhotoToBoat"), false, EKeys::G);
	TestTrue(TEXT("A photo key can take a boat command's key without moving it"), R.bChanged && !R.bSwapped);
	TestEqual(TEXT("Wing-on-wing keeps G"), Find(L, TEXT("WingOnWing"), false, EColumn::Keyboard), EKeys::G);

	// A saved list from before photo mode's free camera gets its commands.
	USailingInputSettings* Settings = GetMutableDefault<USailingInputSettings>();
	const TArray<FSailingKeyBinding> Saved = Settings->Bindings;
	Settings->Bindings = Defaults.FilterByPredicate([](const FSailingKeyBinding& B) { return !IsPhotoAction(B.Action) || B.Action == TEXT("PhotoShot"); });
	Settings->PostReloadConfig(nullptr);
	TestEqual(TEXT("An old list: the free camera's keys added"), Find(Settings->Bindings, TEXT("PhotoToBoat"), false, EColumn::Keyboard), EKeys::F);
	TestEqual(TEXT("And nothing else"), Settings->Bindings.Num(), Defaults.Num());
	Settings->Bindings = Saved;
	return true;
}

// Rule 9: the hold is the game mode's one switch. Held, the world clock stops (the boats, traffic, weather and water
// run on it); let go, it runs on from where it stood.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingPhotoWorldHeldTest, "SailingSim.Smoke.PhotoWorldHeld", PhotoFlags)
bool FSailingPhotoWorldHeldTest::RunTest(const FString&)
{
	FBareWorld W;
	ASailingGameMode* GM = W.World->SpawnActor<ASailingGameMode>();
	if (!TestNotNull(TEXT("A game mode"), GM)) return false;
	auto Frames = [&](int32 N) { for (int32 I = 0; I < N; ++I) { ++GFrameCounter; GM->AdvanceClock(1.f / 60.f); } };
	Frames(60);
	const double T0 = GM->GetSimTime();
	TestTrue(TEXT("The clock runs"), T0 > 0.9);
	GM->SetWorldHeld(true);
	TestTrue(TEXT("Held"), GM->IsWorldHeld());
	Frames(120);
	TestEqual(TEXT("Held for two seconds: the clock stands"), GM->GetSimTime(), T0);
	GM->SetWorldHeld(false);
	Frames(60);
	TestEqual(TEXT("Let go: on from where it stood"), GM->GetSimTime(), T0 + 1.0, 1.0 / 60.0);
	return true;
}

// Photo mode PR 2 (docs/photo-mode/pc/): the panel's lens maths, its rows and pages, its keys in photo mode's context,
// and the drawn time of day that never touches the clock.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingPhotoPanelTest, "SailingSim.UI.PhotoPanel", PhotoFlags)
bool FSailingPhotoPanelTest::RunTest(const FString&)
{
	using namespace PhotoMath;
	// The lens: 50 mm on full frame is 39.6 deg across; the marks span the brief's 14-200 mm inside the old 10-110 deg zoom.
	TestEqual(TEXT("50 mm is 39.6 deg"), FovForFocal(50.f), 39.6f, 0.05f);
	TestEqual(TEXT("And back"), FocalForFov(FovForFocal(85.f)), 85.f, 0.01f);
	TestTrue(TEXT("14 mm fits the zoom's 110 deg"), FovForFocal(14.f) <= 110.f && FovForFocal(200.f) >= 10.f);
	TestEqual(TEXT("From 40 mm the next mark up is 50"), StepFocal(40.f, 1), 50.f);
	TestEqual(TEXT("And down 35"), StepFocal(40.f, -1), 35.f);
	TestEqual(TEXT("On a mark, the next one"), StepFocal(50.f, 1), 70.f);
	TestEqual(TEXT("200 mm is the end"), StepFocal(200.f, 1), 200.f);
	TestEqual(TEXT("f/1.4 to f/22"), Aperture(0), 1.4f);
	TestEqual(TEXT("f/22"), Aperture(NumApertures - 1), 22.f);

	// Stepping rows: the aperture runs past f/22 to off; exposure in half stops to +3; the look and crop cycle.
	FPhotoSettings S;
	float Fov = 90.f, Roll = 0.f;
	for (int32 I = 0; I < 12; ++I) StepRow(S, EPhotoRow::Aperture, 1, Fov, Roll, true, 12.f);
	TestEqual(TEXT("The aperture stops at off"), S.ApertureStop, NumApertures);
	TestTrue(TEXT("Off reads as all sharp"), RowValue(S, EPhotoRow::Aperture, Fov, Roll, 20.f, true).StartsWith(TEXT("Off")));
	for (int32 I = 0; I < 10; ++I) StepRow(S, EPhotoRow::Exposure, 1, Fov, Roll, true, 12.f);
	TestEqual(TEXT("Exposure tops out at +3 EV"), S.ExposureEV, 3.f);
	StepRow(S, EPhotoRow::Look, 1, Fov, Roll, true, 12.f);
	TestTrue(TEXT("Cinematic, then black and white"), S.Look == EPhotoLook::Mono);
	StepRow(S, EPhotoRow::Look, 1, Fov, Roll, true, 12.f);
	TestTrue(TEXT("Then natural"), S.Look == EPhotoLook::Natural);
	StepRow(S, EPhotoRow::Roll, -1, Fov, Roll, true, 12.f);
	TestEqual(TEXT("Tilt in 5 deg steps"), Roll, -5.f);
	StepRow(S, EPhotoRow::Focal, 1, Fov, Roll, true, 12.f);
	TestEqual(TEXT("From 90 deg (18 mm) the lens goes to 24 mm"), FocalForFov(Fov), 24.f, 0.01f);
	StepRow(S, EPhotoRow::Capture, 1, Fov, Roll, false, 12.f);
	TestEqual(TEXT("No 2x below High"), S.CaptureScale, 1);
	TestTrue(TEXT("And the row is idle there"), RowIdle(S, EPhotoRow::Capture, false));
	StepRow(S, EPhotoRow::Capture, 1, Fov, Roll, true, 12.f);
	TestEqual(TEXT("2x on High"), S.CaptureScale, 2);

	// Time of day: half hours from the clock's, back to the clock passing it.
	TestEqual(TEXT("From the clock (14:10) up"), StepSunHour(-1.f, 1, 14.17f), 14.5f);
	TestEqual(TEXT("And down"), StepSunHour(-1.f, -1, 14.17f), 13.5f);
	TestEqual(TEXT("Stepping back to the clock's half hour follows the clock"), StepSunHour(14.5f, -1, 14.17f), -1.f);
	TestEqual(TEXT("Away from it, half hours"), StepSunHour(18.f, 1, 14.17f), 18.5f);

	// Pages and rows: every row on one of five pages, in order.
	int32 LastPage = 0;
	bool bOrdered = true;
	for (int32 R = 0; R < int32(EPhotoRow::Count); ++R) { const int32 P = PageOf(EPhotoRow(R)); bOrdered &= P >= LastPage && P < NumPages; LastPage = P; }
	TestTrue(TEXT("Rows run through the pages in order"), bOrdered && LastPage == NumPages - 1);
	TestTrue(TEXT("Frame starts at the grid"), FirstRowOf(4) == EPhotoRow::Grid);

	// Crop guides: the largest centred rectangle.
	const FVector4f Sq = CropRect(EPhotoCrop::Square, 1920.f, 1080.f);
	TestTrue(TEXT("1:1 in 16:9 is 1080 square, centred"), FMath::IsNearlyEqual(Sq.Z, 1080.f) && FMath::IsNearlyEqual(Sq.W, 1080.f) && FMath::IsNearlyEqual(Sq.X, 420.f));
	const FVector4f Cin = CropRect(EPhotoCrop::Cinema219, 1920.f, 1080.f);
	TestTrue(TEXT("21:9 is full width, letterboxed"), FMath::IsNearlyEqual(Cin.Z, 1920.f) && FMath::IsNearlyEqual(Cin.W, 1920.f * 9.f / 21.f, 0.01f));

	// Keys: arrows and Page Up/Down in photo mode's context (the boat's arrows are the menus'); X and the D-pad's sides on a pad.
	const TArray<FSailingKeyBinding>& Defaults = GetDefault<USailingInputSettings>()->GetDefaults();
	UObject* Outer = NewObject<UInputMappingContext>(GetTransientPackage());
	TMap<FName, TObjectPtr<UInputAction>> Actions;
	ASailboatPawn::MakeActions(Outer, Defaults, Actions);
	const UInputMappingContext* Photo = ASailboatPawn::BuildContext(Outer, TEXT("IMC_TestPhotoPanel"), Defaults, Actions, true);
	TestTrue(TEXT("Down steps the rows"), Only(ActionsOn(Photo, EKeys::Down), TEXT("PhotoRowDown")));
	TestTrue(TEXT("Right raises the value"), Only(ActionsOn(Photo, EKeys::Right), TEXT("PhotoValueUp")));
	TestTrue(TEXT("Page Down turns the page"), Only(ActionsOn(Photo, EKeys::PageDown), TEXT("PhotoPageNext")));
	TestTrue(TEXT("X on a pad steps the rows"), Only(ActionsOn(Photo, EKeys::Gamepad_FaceButton_Left), TEXT("PhotoRowDown")));
	TestTrue(TEXT("The D-pad's left lowers the value"), Only(ActionsOn(Photo, EKeys::Gamepad_DPad_Left), TEXT("PhotoValueDown")));
	TestTrue(TEXT("Panel keys fire on the press"), HasTrigger<UInputTriggerPressed>(Photo, EKeys::Right, TEXT("PhotoValueUp")));

	// The drawn hour: set and cleared, the clock's hour untouched.
	FBareWorld W;
	ASailingGameMode* GM = W.World->SpawnActor<ASailingGameMode>();
	if (!TestNotNull(TEXT("A game mode"), GM)) return false;
	const double Clock = GM->GetWeatherState().HourOfDay;
	TestEqual(TEXT("Unset, the clock's hour is drawn"), GM->GetDrawnHour(), Clock);
	GM->SetDrawnHourOverride(19.5);
	TestEqual(TEXT("Set, photo mode's"), GM->GetDrawnHour(), 19.5);
	TestEqual(TEXT("The weather's hour stays the clock's"), GM->GetWeatherState().HourOfDay, Clock);
	GM->SetDrawnHourOverride(-1.0);
	TestEqual(TEXT("Cleared"), GM->GetDrawnHour(), Clock);
	return true;
}

#endif
