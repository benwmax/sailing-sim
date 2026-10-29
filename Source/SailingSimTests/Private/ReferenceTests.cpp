#include "Misc/AutomationTest.h"
#include <algorithm>
#include "BoatModel.h"
#include "PolarReference.h"
#include "ReferenceChecks.h"
#include "AutoTrim.h"
#include "ReferenceCapture.h"
#include "SailingSim.h"
#include "SailingEnvironment.h"
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
	TestEqual(TEXT("GoPro wide 118 deg (rendered at 125, the lens keeps the corners)"), CapturePresetInfo(ECapturePreset::ActionCam).HFovDeg, 125.f);
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
	TestTrue(TEXT("Chase boat stands off 1.9 mast heights to frame the rig"), FMath::IsNearlyEqual(FVector2D(L - Boat).Size(), 1.9 * 925.0, 1.0));
	TestTrue(TEXT("Chase boat 2 m up"), FMath::IsNearlyEqual(L.Z, 200.0, 0.1));
	TestTrue(TEXT("Chase boat to port of a boat heading 030 stands on bearing 300"), FMath::IsNearlyEqual(FMath::RadiansToDegrees(FMath::Atan2(L.Y - Boat.Y, L.X - Boat.X)), -60.0, 0.1));
	WorldCameraPose(ECapturePreset::Chase, Boat, 30.f, -90.f, 6.0f, 0.f, L, R);
	TestTrue(TEXT("Never closer than 15 m"), FMath::IsNearlyEqual(FVector2D(L - Boat).Size(), 1500.0, 1.0));
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

// Phase 8 fixes 2 and 5: the J/22 carries weather helm that grows as she heels, and her crew keeps her nearly flat.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWeatherHelmTest, "SailingSim.Physics.WeatherHelm", RefFlags)
bool FWeatherHelmTest::RunTest(const FString& Parameters)
{
	const FBoatConfig J22;
	const FSteadyResult Light = SailSteady(6.0, 43.5, J22, false);
	const FSteadyResult Medium = SailSteady(10.0, 40.9, J22, false);
	const FSteadyResult Fresh = SailSteady(15.0, 38.6, J22, false);
	AddInfo(FString::Printf(TEXT("Rudder (+ = weather helm): %.1f / %.1f / %.1f deg at 6 / 10 / 15 kn, heel %.1f / %.1f / %.1f"),
		Light.RudderDeg, Medium.RudderDeg, Fresh.RudderDeg, Light.HeelDeg, Medium.HeelDeg, Fresh.HeelDeg));
	TestTrue(TEXT("Weather helm, not lee helm, in light air"), Light.RudderDeg > 0.3);
	TestTrue(TEXT("A degree or two at 10 kn"), Medium.RudderDeg > 0.8 && Medium.RudderDeg < 4.0);
	// Kept flat by the crew she carries a little less helm than she would heeled right over (easing depowers the helm too).
	TestTrue(TEXT("A couple of degrees or more at 15 kn, more than at 10"), Fresh.RudderDeg > 1.5 && Fresh.RudderDeg < 7.0 && Fresh.RudderDeg > Medium.RudderDeg);
	TestTrue(TEXT("Kept nearly flat at 15 kn (under 16 deg)"), Fresh.HeelDeg < 16.0);
	return true;
}

// Phase 8 step 3: every physics check against real numbers passes, except the gaps the fix list still carries.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReferenceChecksTest, "SailingSim.Physics.ReferenceChecks", RefFlags)
bool FReferenceChecksTest::RunTest(const FString& Parameters)
{
	// Open items on docs/phase-8/fix-list.md, with the reason each is still open.
	const TCHAR* KnownGaps[] = {
		// (W1: the J/22's gusty spinnaker run, a known gap since Visual V3 at 12.1 kn, is back in range in the new puffs.)
		// (Physics gaps: the ILCA's 16 kn gusting 22 reach, a known gap since W1, holds now that the sailor eases on the puff
		// itself, not only on the heel: SailingSim.Physics.LaserPuffHandling.)
		// (W8: the Hobie 16's 12+ kn lap, a known gap since Phase 8, is in band with her added resistance in chop at 9, and
		// the Catalina 22's 4-7 kn lap with her plate keel's profile drag: docs/water-8/portsmouth.)
		nullptr,
	};
	int32 Failures = 0;
	for (const FReferenceCheck& C : RunReferenceChecks(true))
	{
		const FString Name(UTF8_TO_TCHAR(C.Name.c_str()));
		bool bKnown = false;
		for (const TCHAR* Gap : KnownGaps) bKnown |= Gap && Name.Equals(Gap);
		AddInfo(FString::Printf(TEXT("%-10hs %-55s %7.2f %-5hs [%6.2f .. %6.2f] %s"), C.Group.c_str(), *Name, C.Value, C.Unit.c_str(), C.Low, C.High,
			C.Pass() ? TEXT("ok") : (bKnown ? TEXT("known gap") : TEXT("OUT"))));
		if (!C.Pass() && !bKnown)
		{
			AddError(FString::Printf(TEXT("%s: %.2f %hs outside [%.2f, %.2f] (%hs)"), *Name, C.Value, C.Unit.c_str(), C.Low, C.High, C.Source.c_str()));
			++Failures;
		}
	}
	return Failures == 0;
}

// Phase 8, fix 11: the moon has its phase and its place (almanac: full 2024-10-17 11:26 UTC, new 2024-10-02 18:49 UTC).
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMoonPhaseTest, "SailingSim.Smoke.MoonPhase", RefFlags)
bool FMoonPhaseTest::RunTest(const FString& Parameters)
{
	const double Full = 1729164360.0, New = 1727894940.0;
	const double AgeFull = ASailingEnvironment::MoonAgeDays(Full), AgeNew = ASailingEnvironment::MoonAgeDays(New);
	TestTrue(FString::Printf(TEXT("Full moon age %.2f d is about 14.8"), AgeFull), FMath::Abs(AgeFull - 14.77) < 0.6);
	TestTrue(FString::Printf(TEXT("New moon age %.2f d is about 0"), AgeNew), AgeNew < 0.6 || AgeNew > 28.9);
	TestTrue(TEXT("Full moon is lit"), ASailingEnvironment::MoonIllumination(AgeFull) > 0.98);
	TestTrue(TEXT("New moon is dark"), ASailingEnvironment::MoonIllumination(AgeNew) < 0.02);
	// Ray Hubbard, CDT: the full moon is high at midnight and down at noon; the new moon rides with the sun.
	double El = 0.0, Az = 0.0;
	ASailingEnvironment::MoonPosition(23.9, 291, AgeFull, 32.82, -96.50, -5.0, El, Az);
	TestTrue(FString::Printf(TEXT("Full moon high at midnight (%.0f deg)"), El), El > 40.0);
	ASailingEnvironment::MoonPosition(12.0, 291, AgeFull, 32.82, -96.50, -5.0, El, Az);
	TestTrue(FString::Printf(TEXT("Full moon down at noon (%.0f deg)"), El), El < 0.0);
	ASailingEnvironment::MoonPosition(13.3, 276, AgeNew, 32.82, -96.50, -5.0, El, Az);
	TestTrue(FString::Printf(TEXT("New moon up at midday (%.0f deg)"), El), El > 40.0);
	return true;
}

// Laser planing drag: above Froude 1.3 the ILCA's residuary climbs again (Fleet.cpp), so on a steady 22 kn broad reach,
// anywhere from 100 to 130 degrees, her best one-second speed stays under 18 kn (a big gust's 15 kn GPS, the class's logs to
// 21.6-22.2 kn in 40 kn of wind; since docs/wave-physics/ she surfs the chop), and the drag below Froude 1.3 is the shared
// dinghy table's. She stays up at all but a few angles: between 110 and 120 deg she can round up on a wave, lift clear
// over its crest and crash-gybe as she lands (main before docs/wave-physics/: 3 of these 16 angles, at 112, 116 and 118
// deg; since: 2, at 114 and 120; on c2cb055c 1, at 116; since docs/ilca-tiller/, none: SailingSim.Physics.AirborneTiller).
// The test used to sample four angles, which missed main's.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingLaserPlaningDragTest, "SailingSim.Physics.LaserPlaningDrag", RefFlags)
bool FSailingLaserPlaningDragTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	const FBoatConfig Ilca = FBoatConfig::Make(EBoatType::ILCA7);
	const FBoatConfig Sunfish = FBoatConfig::Make(EBoatType::Sunfish);
	TestTrue(TEXT("The ILCA's table is the shared dinghy table up to Froude 1.3"),
		Ilca.Residuary.size() > Sunfish.Residuary.size() && std::equal(Sunfish.Residuary.begin(), Sunfish.Residuary.end(), Ilca.Residuary.begin()));
	TestTrue(TEXT("... and climbs past it"), Ilca.Residuary.back().first > 1.3 && Ilca.Residuary.back().second > 2.0 * Sunfish.Residuary.back().second);
	int32 Capsized = 0;
	for (int32 Twa = 100; Twa <= 130; Twa += 2)
	{
		const FSpeedRun R = SpeedRun(Ilca, 22.0, double(Twa), false, 0.0, 13000.0, 180.0);
		AddInfo(FString::Printf(TEXT("ILCA, 22 kn at %d deg: peak %.2f kn, mean %.2f, tilt at most %.0f deg"), Twa, R.PeakKnots, R.MeanKnots, R.MaxTiltDeg));
		TestTrue(FString::Printf(TEXT("%d deg: peak under 18 kn (%.2f)"), Twa, R.PeakKnots), R.PeakKnots <= 18.0);
		Capsized += R.MaxTiltDeg >= 70.0;
	}
	TestTrue(FString::Printf(TEXT("She stays up at all but 3 of 16 angles (%d over)"), Capsized), Capsized <= 3);
	return true;
}

// docs/ilca-tiller/: the ILCA's crash gybes on the 22 kn reach came with her rudder clear of the water. Over a crest the
// helm, feeling nothing through it, had wound the tiller to the stop, and the rudder landed hard over (on c2cb055c at 116
// deg: a spin past 130 deg/s and over). A light boat's helm now holds the tiller (0.3 of its travel a second at most while
// the rudder is clear), so she stays up at all 16 angles from 100 to 130 deg, as fast; and a keelboat's helm is as before.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingAirborneTillerTest, "SailingSim.Physics.AirborneTiller", RefFlags)
bool FSailingAirborneTillerTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	const FBoatConfig Ilca = FBoatConfig::Make(EBoatType::ILCA7);
	TestTrue(TEXT("The ILCA is a light boat"), FBoatModel(Ilca).TotalMass() < FAutopilot().AirborneTillerMassKg);
	TestTrue(TEXT("The J/22 is not"), FBoatModel(FBoatConfig()).TotalMass() >= FAutopilot().AirborneTillerMassKg);
	int32 Capsized = 0;
	for (int32 Twa = 100; Twa <= 130; Twa += 2)
	{
		const FSpeedRun R = SpeedRun(Ilca, 22.0, double(Twa), false, 0.0, 13000.0, 180.0);
		Capsized += R.MaxTiltDeg >= 70.0;
		if (R.MaxTiltDeg >= 70.0) AddInfo(FString::Printf(TEXT("ILCA, 22 kn at %d deg: over (tilt %.0f deg)"), Twa, R.MaxTiltDeg));
		TestTrue(FString::Printf(TEXT("%d deg: still fast (%.2f kn mean)"), Twa, R.MeanKnots), R.MaxTiltDeg >= 70.0 || R.MeanKnots > 11.0);
	}
	TestEqual(TEXT("She stays up at all 16 angles"), Capsized, 0);
	return true;
}

// Physics gaps: W1's biggest puffs (25 to 29 kn on a 16 kn day, seed 3) capsized the ILCA on a broad reach at 110 and 120
// deg. Hiked flat, she hardly heeled, so the heel-driven ease never came; she surged past 16 kn, buried the bow and rounded
// up with the rudder stalled. The sailor now feels the puff 0.4 s late and eases on it (FAutoTrim): both runs stay up and
// under the ceiling (16 kn then, 18 since she surfs: docs/wave-physics/). The steady 22 kn reach has no puffs, so the change can't touch it.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingLaserPuffHandlingTest, "SailingSim.Physics.LaserPuffHandling", RefFlags)
bool FSailingLaserPuffHandlingTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	const FBoatConfig Ilca = FBoatConfig::Make(EBoatType::ILCA7);
	for (const double Twa : { 110.0, 120.0 })
	{
		const FSpeedRun R = SpeedRun(Ilca, 16.0, Twa, false, 0.14, 13000.0, 180.0);
		AddInfo(FString::Printf(TEXT("ILCA, 16 kn gusting 22 at %.0f deg: peak %.2f kn, mean %.2f, tilt at most %.0f deg"), Twa, R.PeakKnots, R.MeanKnots, R.MaxTiltDeg));
		TestTrue(FString::Printf(TEXT("%.0f deg: she stays up through the puffs (%.0f deg)"), Twa, R.MaxTiltDeg), R.MaxTiltDeg < 70.0);
		TestTrue(FString::Printf(TEXT("%.0f deg: peak under 18 kn (%.2f)"), Twa, R.PeakKnots), R.PeakKnots <= 18.0);
		TestTrue(FString::Printf(TEXT("%.0f deg: and still sails fast (%.2f kn mean)"), Twa, R.MeanKnots), R.MeanKnots > 8.0);
	}
	// A keelboat crew on winches and cleats has no puff ease: the J/22's controls are unchanged in the same puffs.
	const FSpeedRun J = SpeedRun(FBoatConfig(), 16.0, 110.0, false, 0.14, 13000.0, 60.0);
	TestTrue(TEXT("The J/22 sails the same puffs upright"), J.MaxTiltDeg < 45.0);
	return true;
}

#endif
