#include "Misc/AutomationTest.h"
#include "BareTestWorld.h"
#include "BoatModel.h"
#include "Camera/CameraComponent.h"
#include "ChaseCamera.h"
#include "SailSave.h"
#include "SailboatPawn.h"
#include "SailingSettings.h"
#include "WaterSurface.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
	constexpr EAutomationTestFlags ChaseCameraFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

	/** The lens's height over the arm's origin's water (m) for an arm of ArmCm at Pitch (the socket's push is in arm space). */
	double LensUpM(const ChaseCamera::FRig& Rig, float ArmCm, float PitchDeg)
	{
		const double P = FMath::DegreesToRadians(double(-PitchDeg));
		return (Rig.PivotUpCm + ArmCm * FMath::Sin(P) + ChaseCamera::SocketUpCm(Rig, ArmCm) * FMath::Cos(P)) / 100.0;
	}

	/** Half the vertical field of view (deg) of a 16:9 frame at the game's 90 deg. */
	double HalfVerticalFovDeg() { return FMath::RadiansToDegrees(FMath::Atan(9.0 / 16.0)); }
}

// Camera views slice 1 (docs/camera-views/): every boat's rigs hold her in frame at every zoom. The players' chase camera
// sits low (boom height, the J/22's lens about 3 m up, not 7), the masthead in a 16:9 frame at its default distance; zoom
// is by ratio inside each rig's range and never moves the boat on screen; Classic is the old rig exactly (measured runs).
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingChaseCameraRigTest, "SailingSim.Visual.ChaseCamera.Rig", ChaseCameraFlags)
bool FSailingChaseCameraRigTest::RunTest(const FString&)
{
	using namespace ChaseCamera;
	const double HalfV = HalfVerticalFovDeg();
	for (int32 T = 0; T < int32(Sailing::EBoatType::Count); ++T)
	{
		if (Sailing::IsSquareRigged(Sailing::EBoatType(T))) continue; // The frigate's square rig, crew and cameras come with the frigate wiring (IsSquareRigged).
		const Sailing::FBoatConfig C = Sailing::FBoatConfig::Make(Sailing::EBoatType(T));
		const FString Boat = UTF8_TO_TCHAR(Sailing::BoatTypeName(Sailing::EBoatType(T)));
		for (const ERig Kind : { ERig::Chase, ERig::Overview, ERig::Classic })
		{
			const TCHAR* KindName = Kind == ERig::Chase ? TEXT("Chase") : Kind == ERig::Overview ? TEXT("Overview") : TEXT("Classic");
			const FRig R = RigFor(Kind, C.LengthOverall, C.MastheadZ, C.BoomZ);
			TestTrue(FString::Printf(TEXT("%s %s: min <= default <= max (%.0f, %.0f, %.0f cm)"), *Boat, KindName, R.MinArmCm, R.ArmCm, R.MaxArmCm),
				R.MinArmCm <= R.ArmCm && R.ArmCm <= R.MaxArmCm);
			// (Classic is the old rig: only its default distance is held; zoomed in, its fixed push was what lost the boat)
			for (const float Arm : Kind == ERig::Classic ? TArray<float>{ R.ArmCm } : TArray<float>{ R.MinArmCm, R.ArmCm, R.MaxArmCm })
			{
				const double Below = PivotBelowCentreDeg(R, Arm);
				TestTrue(FString::Printf(TEXT("%s %s at %.0f m: the boat in frame (%.1f deg under the middle)"), *Boat, KindName, Arm / 100.f, Below),
					Below >= 0.0 && Below < HalfV - 8.0);
				const double Up = LensUpM(R, Arm, R.PitchDeg);
				TestTrue(FString::Printf(TEXT("%s %s at %.0f m: the lens over the water (%.2f m)"), *Boat, KindName, Arm / 100.f, Up), Up >= 0.8);
			}
			if (Kind != ERig::Classic)
			{
				// The push scales with the arm, so zooming keeps the boat where she is on screen.
				TestTrue(FString::Printf(TEXT("%s %s: zoom never moves the boat on screen"), *Boat, KindName),
					FMath::IsNearlyEqual(PivotBelowCentreDeg(R, R.MinArmCm), PivotBelowCentreDeg(R, R.MaxArmCm), 0.01f));
			}
		}
		// The chase camera: low, about boom height, and the whole rig in a 16:9 frame at 90 deg at its default distance.
		const FRig Chase = RigFor(ERig::Chase, C.LengthOverall, C.MastheadZ, C.BoomZ);
		const FRig Classic = RigFor(ERig::Classic, C.LengthOverall, C.MastheadZ, C.BoomZ);
		const double LensChase = LensUpM(Chase, Chase.ArmCm, Chase.PitchDeg), LensClassic = LensUpM(Classic, Classic.ArmCm, Classic.PitchDeg);
		AddInfo(FString::Printf(TEXT("%s: chase lens %.2f m up, %.1f m back; the old view's %.2f m up, %.1f m back"), *Boat, LensChase, Chase.ArmCm / 100.f,
			LensClassic, Classic.ArmCm / 100.f));
		TestTrue(FString::Printf(TEXT("%s: the chase camera is lower than the old view"), *Boat), LensChase < LensClassic);
		const double Back = Chase.ArmCm / 100.0 * FMath::Cos(FMath::DegreesToRadians(double(-Chase.PitchDeg))) + C.MastX;
		const double MastUpDeg = FMath::RadiansToDegrees(FMath::Atan2(C.MastheadZ - LensChase, Back));
		const double TopDeg = Chase.PitchDeg + HalfV;
		TestTrue(FString::Printf(TEXT("%s: the masthead in frame (%.1f deg up, the frame's top %.1f)"), *Boat, MastUpDeg, TopDeg), MastUpDeg <= TopDeg);
	}
	// The J/22, Bean's boat: the lens about 3 m over the water (it was about 7).
	const Sailing::FBoatConfig J22;
	const FRig J = RigFor(ERig::Chase, J22.LengthOverall, J22.MastheadZ, J22.BoomZ);
	const double JUp = LensUpM(J, J.ArmCm, J.PitchDeg);
	TestTrue(FString::Printf(TEXT("J/22: the chase lens is 2.5 to 4 m up (%.2f m)"), JUp), JUp > 2.5 && JUp < 4.0);
	TestEqual(TEXT("J/22: the arm turns about boom height"), J.PivotUpCm, float(J22.BoomZ * 100.0), 0.5f);
	// Classic is the old rig: 2.4 boat lengths, a third of the masthead up, 14 deg down, no smoothing.
	const FRig Old = RigFor(ERig::Classic, J22.LengthOverall, J22.MastheadZ, J22.BoomZ);
	TestEqual(TEXT("Classic: the old arm"), Old.ArmCm, float(J22.LengthOverall * 2.4 * 100.0), 0.5f);
	TestEqual(TEXT("Classic: the old push at any zoom"), SocketUpCm(Old, Old.MinArmCm), float(J22.MastheadZ * 0.33 * 100.0), 0.5f);
	TestEqual(TEXT("Classic: the old pitch"), Old.PitchDeg, -14.f);
	TestFalse(TEXT("Classic: no yaw smoothing"), Old.bSmoothYaw);
	TestEqual(TEXT("Classic: the old zoom range"), Old.MinArmCm, 400.f);
	TestEqual(TEXT("... to 40 m"), Old.MaxArmCm, 4000.f);
	return true;
}

// Zoom by ratio inside the rig's range, the ease back behind the boat after a look, and the view names.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingChaseCameraControlsTest, "SailingSim.Visual.ChaseCamera.Controls", ChaseCameraFlags)
bool FSailingChaseCameraControlsTest::RunTest(const FString&)
{
	using namespace ChaseCamera;
	const Sailing::FBoatConfig J22;
	const FRig R = RigFor(ERig::Chase, J22.LengthOverall, J22.MastheadZ, J22.BoomZ);
	TestEqual(TEXT("One notch in: 0.88 of the distance"), Zoom(R, R.ArmCm, 1.f), R.ArmCm * ZoomRatio, 0.5f);
	TestEqual(TEXT("One notch out: back again"), Zoom(R, Zoom(R, R.ArmCm, 1.f), -1.f), R.ArmCm, 0.5f);
	TestEqual(TEXT("All the way in stops at the minimum"), Zoom(R, R.ArmCm, 100.f), R.MinArmCm);
	TestEqual(TEXT("All the way out stops at the maximum"), Zoom(R, R.ArmCm, -100.f), R.MaxArmCm);
	// Near and far, a notch is the same share of the distance (a fixed step was a jump near the boat and a crawl far off).
	TestEqual(TEXT("A notch near is the same ratio as a notch far"), Zoom(R, R.MinArmCm * 2.f, 1.f) / (R.MinArmCm * 2.f), Zoom(R, R.MaxArmCm * 0.5f, 1.f) / (R.MaxArmCm * 0.5f), 1e-4f);

	TestEqual(TEXT("Recentre: nothing before the wait"), RecentreYaw(90.f, 1.f / 60.f, RecentreAfterS - 0.1f), 90.f);
	float Yaw = 120.f;
	for (int32 I = 0; I < 60; ++I) Yaw = RecentreYaw(Yaw, 1.f / 60.f, RecentreAfterS + I / 60.f);
	TestTrue(FString::Printf(TEXT("Recentre: after a second most of the way back (%.1f deg)"), Yaw), Yaw > 0.f && Yaw < 120.f * 0.35f);
	for (int32 I = 0; I < 600; ++I) Yaw = RecentreYaw(Yaw, 1.f / 60.f, RecentreAfterS + 1.f + I / 60.f);
	TestEqual(TEXT("Recentre: then exactly behind"), Yaw, 0.f);
	TestTrue(TEXT("Recentre takes the short way round (350 deg goes up to 360, not down)"), RecentreYaw(350.f, 0.1f, 10.f) < 0.f && RecentreYaw(350.f, 0.1f, 10.f) > -10.f);

	TestTrue(TEXT("Chase, then Overview"), Next(EView::Chase) == EView::Overview);
	TestTrue(TEXT("Overview, then Helm"), Next(EView::Overview) == EView::Helm);
	TestTrue(TEXT("Helm, then Chase again"), Next(EView::Helm) == EView::Chase);
	EView Parsed = EView::Chase;
	TestTrue(TEXT("Parses any case"), Parse(TEXT("overview"), Parsed) && Parsed == EView::Overview);
	TestTrue(TEXT("Parses Helm"), Parse(TEXT("HELM"), Parsed) && Parsed == EView::Helm);
	TestFalse(TEXT("Refuses others"), Parse(TEXT("Drone"), Parsed));

	// The save keeps the view (by name, never an index), the look speed and the switches; out of range is clamped.
	FSailSave A;
	A.Settings.CameraView = int32(EView::Overview);
	A.Settings.LookSpeed = 1.75f;
	A.Settings.bInvertLook = true;
	A.Settings.bCameraRecentre = false;
	const FString Text = A.ToJson();
	TestTrue(TEXT("The file names the view"), Text.Contains(TEXT("\"cameraView\": \"overview\"")) || Text.Contains(TEXT("\"cameraView\":\"overview\"")));
	FSailSave B;
	TestEqual(TEXT("Reads back"), int32(FSailSave::FromJson(Text, B)), int32(FSailSave::EResult::Ok));
	TestEqual(TEXT("... the view"), B.Settings.CameraView, int32(EView::Overview));
	TestEqual(TEXT("... the look speed"), B.Settings.LookSpeed, 1.75f);
	TestTrue(TEXT("... invert and recentre"), B.Settings.bInvertLook && !B.Settings.bCameraRecentre);
	FSailSave Old;
	FSailSave::FromJson(TEXT(R"({"version":1,"settings":{"display":{"cameraShake":true}}})"), Old);
	TestEqual(TEXT("An older file starts in the chase camera"), Old.Settings.CameraView, int32(EView::Chase));
	TestTrue(TEXT("... with the camera easing back"), Old.Settings.bCameraRecentre);
	return true;
}

// The pawn: a sail starts in the chase camera, the arm turning about boom height; the view cycles Chase, Overview, Helm;
// the lens is low and the boat in the middle of the frame; Overview is the high view; after a look the camera eases back.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingChaseCameraPawnTest, "SailingSim.Visual.ChaseCamera.Pawn", ChaseCameraFlags)
bool FSailingChaseCameraPawnTest::RunTest(const FString&)
{
	using namespace ChaseCamera;
	// The player's own settings are put back after.
	struct FScopedView
	{
		USailingSettings* S = USailingSettings::Get();
		int32 WasView = S->CameraView;
		bool bWasRecentre = S->bCameraRecentre;
		FScopedView() { S->CameraView = int32(EView::Chase); S->bCameraRecentre = true; }
		~FScopedView() { S->CameraView = WasView; S->bCameraRecentre = bWasRecentre; }
	} Scoped;
	FBareTestWorld W(TEXT("SailingChaseCameraWorld"));
	W.World->SpawnActor<AWaterSurface>(FVector::ZeroVector, FRotator::ZeroRotator);
	ASailboatPawn* Boat = W.World->SpawnActor<ASailboatPawn>(FVector(1000.f, 0.f, 0.f), FRotator(0.f, 90.f, 0.f));
	if (!TestNotNull(TEXT("A boat"), Boat)) return false;
	W.Tick(60);
	TestTrue(TEXT("Starts in the chase camera"), Boat->GetCameraView() == EView::Chase);
	const Sailing::FBoatConfig J22;
	TestEqual(TEXT("The arm's origin is at boom height"), Boat->GetChaseRig().PivotUpCm, float(J22.BoomZ * 100.0), 1.f);
	auto Lens = [Boat]()
	{
		FMinimalViewInfo View;
		Boat->CalcCamera(1.f / 60.f, View);
		return View;
	};
	auto UpM = [Boat](const FMinimalViewInfo& V) { return (V.Location.Z - Boat->GetActorLocation().Z) / 100.0; };
	auto OffDeg = [Boat](const FMinimalViewInfo& V)
	{
		const FVector ToBoat = (Boat->GetActorLocation() + FVector(0.f, 0.f, Boat->GetChaseRig().PivotUpCm) - V.Location).GetSafeNormal();
		return FMath::RadiansToDegrees(FMath::Acos(FVector::DotProduct(ToBoat, V.Rotation.Vector())));
	};
	const FMinimalViewInfo Chase = Lens();
	TestTrue(FString::Printf(TEXT("Chase: the lens low, 2 to 4.5 m over the hull (%.2f m)"), UpM(Chase)), UpM(Chase) > 2.0 && UpM(Chase) < 4.5);
	TestTrue(FString::Printf(TEXT("Chase: the boat near the middle (%.1f deg off)"), OffDeg(Chase)), OffDeg(Chase) < 8.0);
	TestEqual(TEXT("Chase: 4 deg down"), Chase.Rotation.Pitch, double(Boat->GetChaseRig().PitchDeg), 3.0);

	Boat->SetCameraView(Next(Boat->GetCameraView()), false);
	W.Tick(30);
	TestTrue(TEXT("Then Overview"), Boat->GetCameraView() == EView::Overview);
	const FMinimalViewInfo Over = Lens();
	TestTrue(FString::Printf(TEXT("Overview is the high view (%.2f m against the chase's %.2f m)"), UpM(Over), UpM(Chase)), UpM(Over) > UpM(Chase) + 2.0);
	Boat->SetCameraView(Next(Boat->GetCameraView()), false);
	W.Tick(30);
	TestTrue(TEXT("Then Helm"), Boat->GetCameraView() == EView::Helm);
	TestTrue(TEXT("... the cockpit view"), Boat->IsCockpitView());
	Boat->SetCameraView(Next(Boat->GetCameraView()), false);
	W.Tick(30);
	TestTrue(TEXT("Then Chase again"), Boat->GetCameraView() == EView::Chase);
	TestFalse(TEXT("... out of the cockpit"), Boat->IsCockpitView());
	TestEqual(TEXT("... at the chase's own distance"), Boat->GetChaseArmCm(), Boat->GetChaseRig().ArmCm, 1.f);

	// Zoom keeps the boat in the same place on screen.
	Boat->AddCameraOrbit(FVector2D::ZeroVector, 4.f);
	W.Tick(60);
	const FMinimalViewInfo Near = Lens();
	Boat->AddCameraOrbit(FVector2D::ZeroVector, -8.f);
	W.Tick(90);
	const FMinimalViewInfo Far = Lens();
	// (the hull bobs and the lens lags it, so the view moves a degree or two; the framing's own sums are held in .Rig)
	TestTrue(FString::Printf(TEXT("Zoomed in and out, the boat stays near the middle (%.1f and %.1f deg off)"), OffDeg(Near), OffDeg(Far)),
		OffDeg(Near) < 8.0 && OffDeg(Far) < 8.0);
	TestEqual(TEXT("... the push the same share of the arm near and far"), PivotBelowCentreDeg(Boat->GetChaseRig(), Boat->GetChaseRig().MinArmCm),
		PivotBelowCentreDeg(Boat->GetChaseRig(), Boat->GetChaseArmCm()), 0.01f);
	return true;
}

#endif
