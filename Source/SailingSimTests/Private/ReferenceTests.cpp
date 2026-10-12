#include "Misc/AutomationTest.h"
#include "BoatModel.h"
#include "ReferenceCapture.h"
#include "SailingSim.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

#if WITH_DEV_AUTOMATION_TESTS

using namespace Sailing;

namespace
{
	constexpr EAutomationTestFlags RefFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;
}

// Phase 8, step 2: the reference cameras sit where real ones do, with their lenses, and the telemetry is complete.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReferenceCaptureTest, "SailingSim.Smoke.ReferenceCapture", RefFlags)
bool FReferenceCaptureTest::RunTest(const FString& Parameters)
{
	TestEqual(TEXT("Helm eye by name"), ParseCapturePreset(TEXT("helmeye")), ECapturePreset::HelmEye);
	TestEqual(TEXT("The method's 'Action cam stern'"), ParseCapturePreset(TEXT("Action cam stern")), ECapturePreset::ActionCam);
	TestEqual(TEXT("Chase boat"), ParseCapturePreset(TEXT("Chase boat")), ECapturePreset::Chase);
	TestEqual(TEXT("Shore tele"), ParseCapturePreset(TEXT("shore")), ECapturePreset::ShoreTele);
	TestEqual(TEXT("Unknown names do nothing"), ParseCapturePreset(TEXT("fisheye")), ECapturePreset::None);
	TestEqual(TEXT("Phone main camera 70 deg"), CapturePresetInfo(ECapturePreset::HelmEye).HFovDeg, 70.f);
	TestEqual(TEXT("GoPro wide 118 deg"), CapturePresetInfo(ECapturePreset::ActionCam).HFovDeg, 118.f);
	TestTrue(TEXT("Only the action cam is distorted"), CapturePresetInfo(ECapturePreset::ActionCam).bBarrel && !CapturePresetInfo(ECapturePreset::Chase).bBarrel);

	// Onboard mounts land on the boat: inside the hull's length, within its beam, above the deck, for every boat.
	for (int32 I = 0; I < int32(EBoatType::Count); ++I)
	{
		const FBoatConfig C = FBoatConfig::Make(EBoatType(I));
		for (ECapturePreset P : { ECapturePreset::HelmEye, ECapturePreset::ActionCam })
		{
			FVector L;
			FRotator R;
			OnboardCameraMount(P, C, 1.f, L, R);
			const FHullShape& H = C.Hulls[0];
			const FVector M = L / CmPerMeter;
			TestTrue(FString::Printf(TEXT("%hs %s: along the hull (%.2f m)"), C.Name, CapturePresetInfo(P).Name, M.X), M.X > H.SternX - 0.01 && M.X < H.BowX);
			TestTrue(FString::Printf(TEXT("%hs %s: within the beam (%.2f m)"), C.Name, CapturePresetInfo(P).Name, M.Y), FMath::Abs(M.Y) <= 0.5 * C.Beam + 0.01);
			TestTrue(FString::Printf(TEXT("%hs %s: eye above the water (%.2f m)"), C.Name, CapturePresetInfo(P).Name, M.Z), M.Z > 0.5 && M.Z < 3.0);
		}
		FVector Starboard, Port;
		FRotator RS, RP;
		OnboardCameraMount(ECapturePreset::HelmEye, C, 1.f, Starboard, RS);
		OnboardCameraMount(ECapturePreset::HelmEye, C, -1.f, Port, RP);
		if (!C.bMultihull)
		{
			TestTrue(FString::Printf(TEXT("%hs: the helmsman sits to windward and looks to leeward"), C.Name),
				Starboard.Y > 0.0 && Port.Y < 0.0 && RS.Yaw < 0.f && RP.Yaw > 0.f);
		}
	}

	// World cameras: the method's distances and angles.
	const FVector Boat(1000.0, 2000.0, 0.0);
	FVector L;
	FRotator R;
	WorldCameraPose(ECapturePreset::Chase, Boat, 30.f, -90.f, 9.25f, 0.f, L, R);
	TestTrue(TEXT("Chase boat 15 m off"), FMath::IsNearlyEqual(FVector2D(L - Boat).Size(), 1500.0, 1.0));
	TestTrue(TEXT("Chase boat 2 m up"), FMath::IsNearlyEqual(L.Z, 200.0, 0.1));
	TestTrue(TEXT("Chase boat to port of a boat heading 030 stands on bearing 300"), FMath::IsNearlyEqual(FMath::RadiansToDegrees(FMath::Atan2(L.Y - Boat.Y, L.X - Boat.X)), -60.0, 0.1));
	WorldCameraPose(ECapturePreset::Drone, Boat, 0.f, 90.f, 9.25f, 0.f, L, R);
	TestTrue(TEXT("Drone 30 m up, 30 m off"), FMath::IsNearlyEqual(L.Z, 3000.0, 0.1) && FMath::IsNearlyEqual(FVector2D(L - Boat).Size(), 3000.0, 1.0));
	TestTrue(FString::Printf(TEXT("Drone looks down about 45 deg (%.1f)"), R.Pitch), R.Pitch < -40.f && R.Pitch > -48.f);
	WorldCameraPose(ECapturePreset::ShoreTele, Boat, 0.f, 90.f, 9.25f, 0.f, L, R);
	TestTrue(TEXT("Shore camera 200 m off, 3 m up"), FMath::IsNearlyEqual(FVector2D(L - Boat).Size(), 20000.0, 1.0) && FMath::IsNearlyEqual(L.Z, 300.0, 0.1));

	// Telemetry: one header and one row per frame, the same number of columns, values a sailor reads.
	FBoatModel Model;
	Model.Reset(0.0, 0.0, 0.0, 2.5);
	FBoatControls Controls;
	FWindField Wind;
	FWindParams WP;
	WP.SpeedKnots = 12.0;
	WP.FromDegrees = 45.0;
	Wind.SetParams(WP);
	for (int32 I = 0; I < 240; ++I) Model.Step(1.0 / 120.0, Controls, Wind);
	const FCaptureTelemetryRow Row = FCaptureTelemetryRow::FromBoat(2.0, Model, Controls, 0.12);
	TestTrue(FString::Printf(TEXT("True wind from 045 (%.1f)"), Row.TrueWindFromDeg), FMath::Abs(Row.TrueWindFromDeg - 45.0) < 3.0);
	TestTrue(FString::Printf(TEXT("True wind about 12 kn at 10 m (%.1f)"), Row.TrueWindKn), FMath::Abs(Row.TrueWindKn - 12.0) < 1.5);
	TArray<FString> HeaderCols, RowCols;
	FCaptureTelemetry::Header().ParseIntoArray(HeaderCols, TEXT(","));
	FCaptureTelemetry::Format(Row).ParseIntoArray(RowCols, TEXT(","));
	TestEqual(TEXT("Columns match the header"), RowCols.Num(), HeaderCols.Num());
	const FString Path = FPaths::ProjectSavedDir() / TEXT("Automation/telemetry-test.csv");
	{
		FCaptureTelemetry Csv;
		TestTrue(TEXT("Telemetry file opens"), Csv.Open(Path));
		for (int32 I = 0; I < 3; ++I) Csv.Add(Row);
		TestEqual(TEXT("Three rows"), Csv.NumRows(), 3);
	}
	TArray<FString> Lines;
	FFileHelper::LoadFileToStringArray(Lines, *Path);
	TestEqual(TEXT("Header plus three rows on disk"), Lines.Num(), 4);
	IFileManager::Get().Delete(*Path);
	return true;
}

// A boat turned turtle is capsized (the heel alone reads near zero upside down).
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FTurtleCapsizedTest, "SailingSim.Physics.TurtledCountsAsCapsized", RefFlags)
bool FTurtleCapsizedTest::RunTest(const FString& Parameters)
{
	FWindParams Calm;
	Calm.SpeedKnots = 5.0;
	const FWindField Wind(Calm);
	FBoatModel Boat(FBoatConfig::Make(EBoatType::Sunfish));
	Boat.Reset(0.0, 0.0, 0.0, 0.0);
	FBoatState& S = Boat.GetMutableState();
	S.Orientation = S.Orientation * Quat::FromAxisAngle({ 1, 0, 0 }, 178.0 * kDegToRad);
	FBoatControls Controls;
	Controls.MainSheet = Controls.JibSheet = 1.0;
	for (int32 I = 0; I < 3 * 120; ++I) Boat.Step(1.0 / 120.0, Controls, Wind);
	TestTrue(FString::Printf(TEXT("Upside down (tilt %.0f deg)"), Boat.GetState().Orientation.Tilt() * kRadToDeg), Boat.GetState().Orientation.Tilt() > 120.0 * kDegToRad);
	TestTrue(TEXT("Turtled counts as capsized"), Boat.GetTelemetry().bCapsized);
	return true;
}

#endif
