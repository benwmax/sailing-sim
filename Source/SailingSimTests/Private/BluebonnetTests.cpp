#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "AutoTrim.h"
#include "BoatModel.h"
#include "FixedStepper.h"
#include "LakeData.h"
#include "PolarReference.h"
#include "Waves.h"
#include "UI/SailCatalog.h"

#if WITH_DEV_AUTOMATION_TESTS

using namespace Sailing;

// Bluebonnet, the invented 1937 J-Class (Tools/shipkit/jclass, docs/jclass-13/ and docs/jclass-14/): her physics sheet in
// the game, her roll under the crew's trim, and where she can start. Her polar is SailingSim.Fleet.Polar.Bluebonnet.
namespace BluebonnetTestsLocal
{
	constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	TSharedPtr<FJsonObject> ReadSheet(FAutomationTestBase& Test)
	{
		FString Text;
		const FString Path = FPaths::ProjectDir() / TEXT("docs/jclass-13/baseline/physics.json");
		TSharedPtr<FJsonObject> Root;
		if (!FFileHelper::LoadFileToString(Text, *Path) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root.IsValid())
		{
			Test.AddError(FString::Printf(TEXT("Could not read %s"), *Path));
			return nullptr;
		}
		return Root;
	}

	struct FRollResult { double MeanKnots = 0.0, MeanHeel = 0.0, MinHeel = 1e9, MaxHeel = -1e9; };

	/** Sails her upwind 90 s with the autopilot and a trimmer (the game's hands, or the polar's ideal ones) and measures the
	 *  last 20 s, as the reference polars do (the lake chop of the calibration sea). */
	FRollResult SailUpwind(const FBoatConfig& Config, double Tws, double Twa, bool bHands)
	{
		FWindParams WindParams;
		WindParams.SpeedKnots = Tws;
		WindParams.FromDegrees = 0.0;
		const FWindField Wind(WindParams);
		FWaveField Waves(7);
		FWaveParams WaveParams;
		WaveParams.WindSpeedKnots = Tws;
		WaveParams.WindFromDegrees = 0.0;
		WaveParams.FetchMeters = kPolarFetchMeters;
		WaveParams.bCalibrationSea = true;
		Waves.SetWind(WaveParams);
		Waves.SnapToTarget();
		FBoatModel Boat(Config);
		Boat.Reset(0.0, 0.0, -Twa * kDegToRad, 0.6 * Tws * kKnot);
		Boat.GetMutableState().WindwardSide = 1;
		Boat.GetMutableState().CrewOffset = Config.CrewSitOut;
		FAutopilot Pilot;
		Pilot.TargetTWADeg = Twa;
		FAutoTrim Trim;
		Trim.Settings.bHands = bHands;
		FBoatControls Controls;
		Controls.MainSheet = Controls.JibSheet = Twa / 180.0;
		Controls.Hike = 1.0;
		FRollResult R;
		int32 N = 0;
		for (int32 I = 0; I < int32(90.0 * PhysicsHz); ++I)
		{
			Controls = Trim.Update(Boat, Controls, PhysicsDt);
			Controls.Tiller = Pilot.Update(Boat);
			Boat.Step(PhysicsDt, Controls, Wind, &Waves);
			if (I < int32(70.0 * PhysicsHz)) continue;
			const double Heel = Boat.GetTelemetry().Heel * kRadToDeg;
			R.MeanKnots += Boat.GetTelemetry().BoatSpeed / kKnot;
			R.MeanHeel += Heel;
			R.MinHeel = FMath::Min(R.MinHeel, Heel);
			R.MaxHeel = FMath::Max(R.MaxHeel, Heel);
			++N;
		}
		R.MeanKnots /= FMath::Max(N, 1);
		R.MeanHeel /= FMath::Max(N, 1);
		return R;
	}
}

/** Her config is the physics sheet (Tools/shipkit/jclass/physics.py on the slice 13 build): she floats on her lines. */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingBluebonnetHullTest, "SailingSim.Physics.BluebonnetHull", BluebonnetTestsLocal::Flags)
bool FSailingBluebonnetHullTest::RunTest(const FString&)
{
	const TSharedPtr<FJsonObject> Sheet = BluebonnetTestsLocal::ReadSheet(*this);
	if (!Sheet) return false;
	const TSharedPtr<FJsonObject> Hull = Sheet->GetObjectField(TEXT("hull"));
	const TSharedPtr<FJsonObject> Mass = Sheet->GetObjectField(TEXT("mass"));
	const FBoatConfig C = FBoatConfig::Make(EBoatType::Bluebonnet);
	const FBoatModel Boat(C);
	if (!TestEqual(TEXT("One hull, drawn by its stations"), int32(C.Hulls.size()), 1) || !TestTrue(TEXT("... the sheet's"), C.Hulls[0].HasStations())) return false;
	TestEqual(TEXT("Every station of the sheet"), int32(C.Hulls[0].Stations.size()), Hull->GetArrayField(TEXT("stations")).Num());
	AddInfo(FString::Printf(TEXT("Mass %.0f kg (sheet %.0f), canoe depth %.3f m (sheet %.3f), canoe volume %.2f m^3 (sheet %.2f)"), Boat.TotalMass(),
		Mass->GetNumberField(TEXT("sim_kg")), Boat.HullDepth(), Hull->GetNumberField(TEXT("station_depth_m")), Boat.DesignDisplacedVolume(),
		Hull->GetNumberField(TEXT("canoe_volume_m3"))));
	TestTrue(TEXT("Her weight as the sheet (0.5%)"), FMath::Abs(Boat.TotalMass() / Mass->GetNumberField(TEXT("sim_kg")) - 1.0) <= 0.005);
	TestTrue(TEXT("Floating on her lines (canoe depth within 2 cm)"), FMath::Abs(Boat.HullDepth() - Hull->GetNumberField(TEXT("station_depth_m"))) <= 0.02);
	TestTrue(TEXT("Weight = water displaced by the canoe body and appendages (1%)"),
		FMath::Abs(Boat.TotalMass() / (kWaterDensity * (Boat.DesignDisplacedVolume() + C.AppendageVolume)) - 1.0) <= 0.01);
	TestTrue(TEXT("LOA, LWL, beam and draft as the sheet"), FMath::IsNearlyEqual(C.LengthOverall, Hull->GetNumberField(TEXT("loa_m")), 0.01)
		&& FMath::IsNearlyEqual(C.WaterlineLength, Hull->GetNumberField(TEXT("lwl_m")), 0.01) && FMath::IsNearlyEqual(C.Beam, Hull->GetNumberField(TEXT("beam_m")), 0.01)
		&& FMath::IsNearlyEqual(C.Draft, Hull->GetNumberField(TEXT("draft_m")), 0.01));
	TestEqual(TEXT("Thirty crew in her weight"), C.CrewMass, Mass->GetObjectField(TEXT("crew"))->GetNumberField(TEXT("kg")));
	TestEqual(TEXT("Twelve of them drawn"), C.CrewCount, 12);
	TestTrue(TEXT("No engine"), C.Engines.empty());
	TestTrue(TEXT("Steered by a wheel"), C.WheelHardOverSeconds > 0.0);

	// The righting curve: a deep lead keel under a narrow hull, positive past 90 deg and stiffening to 45.
	double Last = 0.0;
	for (const double Deg : { 5.0, 10.0, 20.0, 30.0, 45.0, 60.0, 90.0 })
	{
		const double Rm = Boat.RightingMomentAt(Deg * kDegToRad);
		AddInfo(FString::Printf(TEXT("RM at %2.0f deg: %8.0f N m (GZ %.2f m)"), Deg, Rm, Rm / (Boat.TotalMass() * kGravity)));
		TestTrue(FString::Printf(TEXT("Righting at %.0f deg"), Deg), Rm > 0.0);
		if (Deg <= 45.0) TestTrue(FString::Printf(TEXT("... and stiffening to %.0f deg"), Deg), Rm > Last);
		Last = Rm;
	}
	const double Gm = Boat.RightingMomentAt(2.0 * kDegToRad) / (Boat.TotalMass() * kGravity * FMath::Sin(2.0 * kDegToRad));
	AddInfo(FString::Printf(TEXT("GM %.2f m (from her lines 2.10)"), Gm));
	TestTrue(TEXT("Her metacentric height from her lines (1.9-2.3 m)"), Gm > 1.9 && Gm < 2.3);
	return true;
}

/**
 * docs/jclass-14/: her slow roll (8 s free) swings the apparent wind high on her rig, and a trimmer who chased each swing
 * fed it: she rolled 1 to 30 deg every 10 s from 13 kn upwind. Trimmed over her roll (FBoatConfig::TrimRollSeconds) she
 * holds her heel within a few degrees, with the game's hands and with the polar's ideal ones, up to 24 kn.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingBluebonnetRollTest, "SailingSim.Physics.BluebonnetRoll", BluebonnetTestsLocal::Flags)
bool FSailingBluebonnetRollTest::RunTest(const FString&)
{
	using namespace BluebonnetTestsLocal;
	const FBoatConfig C = FBoatConfig::Make(EBoatType::Bluebonnet);
	TestEqual(TEXT("Her free roll period"), C.TrimRollSeconds, 8.0);
	for (const double Tws : { 12.0, 16.0, 20.0, 24.0 })
	{
		for (const bool bHands : { true, false })
		{
			const FRollResult R = SailUpwind(C, Tws, 52.0, bHands);
			const FString Case = FString::Printf(TEXT("%.0f kn at 52 deg, %s"), Tws, bHands ? TEXT("the game's hands") : TEXT("ideal trim"));
			AddInfo(FString::Printf(TEXT("%s: %.2f kn, heel %.1f (%.1f to %.1f)"), *Case, R.MeanKnots, R.MeanHeel, R.MinHeel, R.MaxHeel));
			TestTrue(Case + TEXT(": heel steady within 5 deg"), R.MaxHeel - R.MinHeel < 5.0);
			TestTrue(Case + TEXT(": at her working heel (15-28 deg)"), R.MeanHeel > 15.0 && R.MeanHeel < 28.0);
		}
	}
	// Without it (the trimmer every other boat has) she rolls, which is what the knob is for: reported, not failed.
	FBoatConfig Old = C;
	Old.TrimRollSeconds = 0.0;
	const FRollResult R = SailUpwind(Old, 16.0, 52.0, true);
	AddInfo(FString::Printf(TEXT("Without TrimRollSeconds, 16 kn at 52 deg: heel %.1f to %.1f"), R.MinHeel, R.MaxHeel));
	return true;
}

/**
 * docs/jclass-14/: a launch spot fits a boat with a fifth of her draft under the keel (LaunchSpotFits). Every club boat fits
 * every spot on the lake and the bay as before; Bluebonnet (4.5 m) starts from Bolivar Roads or the lake's deep spots, and
 * the Boat screen says so elsewhere (SailCatalog::DepthLockReason).
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingBluebonnetStartsTest, "SailingSim.UI.DeepKeelStarts", BluebonnetTestsLocal::Flags)
bool FSailingBluebonnetStartsTest::RunTest(const FString&)
{
	const int32 Blue = int32(EBoatType::Bluebonnet);
	for (const int32 WorldIndex : { 0, 1 })
	{
		const SailCatalog::FWorld& W = SailCatalog::World(WorldIndex);
		int32 Fits = 0;
		for (int32 S = 0; S < W.Spots.Num(); ++S)
		{
			TestTrue(FString::Printf(TEXT("%s: %s has its depth"), *W.Name, *W.Spots[S].Name), W.Spots[S].DepthM > 0.0);
			for (const SailCatalog::FBoat& B : SailCatalog::Boats())
			{
				if (B.Type == Blue || B.Type == int32(EBoatType::Maxi)) continue;
				TestTrue(FString::Printf(TEXT("%s fits %s"), *B.Name, *W.Spots[S].Name), SailCatalog::DepthLockReason(WorldIndex, S, B.Type).IsEmpty());
			}
			const FString Reason = SailCatalog::DepthLockReason(WorldIndex, S, Blue);
			AddInfo(FString::Printf(TEXT("Bluebonnet at %s (%.1f m): %s"), *W.Spots[S].Name, W.Spots[S].DepthM, Reason.IsEmpty() ? TEXT("fits") : *Reason));
			if (Reason.IsEmpty()) ++Fits;
			else TestTrue(FString::Printf(TEXT("... names a deep spot at %s"), *W.Spots[S].Name), Reason.Contains(WorldIndex == 1 ? TEXT("Bolivar Roads") : TEXT("near the dam")));
		}
		TestEqual(FString::Printf(TEXT("%s: Bluebonnet's spots"), *W.Name), Fits, WorldIndex == 1 ? 1 : 4);
	}
	TestTrue(TEXT("A spot without a depth fits any boat"), LaunchSpotFits(-1.0, 10.0));
	return true;
}

#endif
