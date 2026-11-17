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
#include "BoatPacks.h"
#include "CrewMotion.h"
#include "CrewPose.h"
#include "SailboatPawn.h"
#include "SailingSim.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshSocket.h"
#include "Materials/MaterialInterface.h"
#include "MeshDescription.h"
#include "StaticMeshAttributes.h"

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
 * docs/jclass-upwind/: upwind in a breeze she was 12% under her estimate, held at 18 deg by the fleet's heeled drag. Her
 * wave-making is read on her sailing length (her waves climbing her overhangs, by speed), her heeled drag is her own lines',
 * and the boom swings on the build's gooseneck pin. Light air is about where it was; her beat in 12 kn stays under Ranger's
 * 1937 record (7.26 kn VMG), the fastest J there was.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingBluebonnetUpwindTest, "SailingSim.Physics.BluebonnetUpwind", BluebonnetTestsLocal::Flags)
bool FSailingBluebonnetUpwindTest::RunTest(const FString&)
{
	const TSharedPtr<FJsonObject> Sheet = BluebonnetTestsLocal::ReadSheet(*this);
	if (!Sheet) return false;
	const TSharedPtr<FJsonObject> Main = Sheet->GetObjectField(TEXT("rig"))->GetObjectField(TEXT("main"));
	const FBoatConfig C = FBoatConfig::Make(EBoatType::Bluebonnet);

	// The gooseneck: the boom's pin (slice 4's build, x 2.3508 at BoomZ), the clew and the area where the sheet has them.
	const double SheetClew = Main->GetNumberField(TEXT("luff_x")) - Main->GetNumberField(TEXT("foot_chord"));
	TestTrue(FString::Printf(TEXT("The gooseneck on the boom's pin (MainLuffX %.4f, build 2.3508)"), C.MainLuffX), FMath::Abs(C.MainLuffX - 2.3508) < 0.001);
	TestTrue(FString::Printf(TEXT("... the clew where the sheet has it (%.3f, sheet %.3f)"), C.MainLuffX - C.MainFootChord, SheetClew),
		FMath::Abs(C.MainLuffX - C.MainFootChord - SheetClew) < 0.001);
	TestTrue(FString::Printf(TEXT("... the main's area kept (%.1f m^2, sheet %.1f)"), C.Main.TotalArea, Main->GetNumberField(TEXT("area_m2"))),
		FMath::Abs(C.Main.TotalArea / Main->GetNumberField(TEXT("area_m2")) - 1.0) < 0.005);
	TestTrue(TEXT("... its foot strip starting at the pin"), C.Main.Strips[0].LuffX < Main->GetNumberField(TEXT("luff_x")));

	// Heeled drag from her lines; the fleet keeps its own.
	const FBoatConfig J22 = FBoatConfig::J22();
	TestEqual(TEXT("Her heeled friction (her lines: 0.6% more wetted area at 18 deg)"), C.HeelFrictionCoef, 0.02);
	TestEqual(TEXT("Her heeled wave-making (her lines: 1.5% longer at 18 deg)"), C.HeelResiduaryCoef, 0.0);
	TestTrue(TEXT("The J/22's heeled drag unchanged (0.4, 2.0)"), J22.HeelFrictionCoef == 0.4 && J22.HeelResiduaryCoef == 2.0);

	// Her wave-making on her sailing length: about the sheet's in light air, much less fast, never falling with speed.
	TArray<TPair<double, double>> Rest;
	for (const TSharedPtr<FJsonValue>& Row : Sheet->GetObjectField(TEXT("resistance"))->GetArrayField(TEXT("residuary")))
	{
		const TArray<TSharedPtr<FJsonValue>>& P = Row->AsArray();
		Rest.Add({ P[0]->AsNumber(), P[1]->AsNumber() });
	}
	auto SheetAt = [&Rest](double Fn)
	{
		for (int32 I = 1; I < Rest.Num(); ++I)
			if (Fn <= Rest[I].Key) return Rest[I - 1].Value + (Rest[I].Value - Rest[I - 1].Value) * (Fn - Rest[I - 1].Key) / (Rest[I].Key - Rest[I - 1].Key);
		return Rest.Last().Value;
	};
	auto HerAt = [&C](double Fn)
	{
		for (size_t I = 1; I < C.Residuary.size(); ++I)
			if (Fn <= C.Residuary[I].first)
				return C.Residuary[I - 1].second + (C.Residuary[I].second - C.Residuary[I - 1].second) * (Fn - C.Residuary[I - 1].first) / (C.Residuary[I].first - C.Residuary[I - 1].first);
		return C.Residuary.back().second;
	};
	double Last = 0.0;
	for (const std::pair<double, double>& R : C.Residuary)
	{
		TestTrue(FString::Printf(TEXT("Wave-making never falls with speed (Fn %.3f)"), R.first), R.second >= Last);
		Last = R.second;
	}
	for (const double Fn : { 0.1, 0.2, 0.3, 0.35, 0.4, 0.45 })
	{
		const double Ratio = HerAt(Fn) / SheetAt(Fn);
		AddInfo(FString::Printf(TEXT("Fn %.2f: %.2f of the sheet's (slice 13's flat factor 0.6)"), Fn, Ratio));
		if (Fn <= 0.1) TestTrue(TEXT("Light air: within 10% of the sheet's"), Ratio > 0.9 && Ratio <= 1.0);
		if (Fn >= 0.4) TestTrue(FString::Printf(TEXT("Fn %.2f: her waves up her overhangs halve it or more"), Fn), Ratio > 0.2 && Ratio < 0.5);
	}

	// Sailing: close-hauled in 16 kn at her working heel and within 7% of her estimate (12.09, was 12% under at 18 deg);
	// her beat in 12 kn near, not past, Ranger's record.
	const FSteadyResult Close = SailSteady(16.0, 52.0, C, true, false);
	AddInfo(FString::Printf(TEXT("16 kn at 52 deg: %.2f kn (estimate 12.09), heel %.1f"), Close.BoatSpeedKnots, Close.HeelDeg));
	TestTrue(TEXT("16 kn at 52 deg within 7% of the estimate"), FMath::Abs(Close.BoatSpeedKnots / 12.09 - 1.0) < 0.07);
	TestTrue(TEXT("... heeled 20 to 27 deg, as the Js sailed"), Close.HeelDeg > 20.0 && Close.HeelDeg < 27.0);
	const FSteadyResult Beat = SailSteady(12.0, 34.0, C, true, false);
	const double Vmg = Beat.BoatSpeedKnots * FMath::Cos(FMath::DegreesToRadians(34.0));
	AddInfo(FString::Printf(TEXT("12 kn at 34 deg: %.2f kn, VMG %.2f (Ranger 1937: 7.26)"), Beat.BoatSpeedKnots, Vmg));
	TestTrue(TEXT("Her beat in 12 kn 0.95 to 1.0 of Ranger's"), Vmg > 0.95 * 7.26 && Vmg <= 7.26);
	return true;
}

/**
 * docs/jclass-14/: her slow roll (8 s free) swings the apparent wind high on her rig, and a trimmer who chased each swing
 * fed it: she rolled 1 to 30 deg every 10 s from 13 kn upwind. Trimmed over her roll (FBoatConfig::TrimRollSeconds) she
 * holds her heel within a few degrees, with the game's hands and with the polar's ideal ones, up to 24 kn. Since her
 * sailing length (docs/jclass-upwind/) she is faster in a breeze, and at 8 s the game's hands swung her 19 to 27 deg in
 * 20 to 22 kn; she is trimmed over 10 s, and 22 kn is checked too.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingBluebonnetRollTest, "SailingSim.Physics.BluebonnetRoll", BluebonnetTestsLocal::Flags)
bool FSailingBluebonnetRollTest::RunTest(const FString&)
{
	using namespace BluebonnetTestsLocal;
	const FBoatConfig C = FBoatConfig::Make(EBoatType::Bluebonnet);
	TestEqual(TEXT("Trimmed over 10 s (her free roll period 8 s, a quarter more since her sailing length: docs/jclass-upwind/)"), C.TrimRollSeconds, 10.0);
	for (const double Tws : { 12.0, 16.0, 20.0, 22.0, 24.0 })
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

/**
 * docs/jclass-14/ step 2: her model (Tools/shipkit/jclass/export_game.py on the build, imported to /Game/Boats/Bluebonnet by
 * scripts/import_boats.py bluebonnet) held to her physics as FleetMesh holds the fleet's: the canoe as imported (the
 * hull's and the rudder's canoe slots below the load waterline, the rudder at its pivot) displaces the physics' canoe and
 * keel within 2% about the same centre (5 cm), and her length, beam and draft are the config's (2 cm). The points the game
 * reads are on the parts it reads them from, the rudder turns about her raked stock, there are no live-wire sockets (her
 * standing rigging is in the mast's part), and every part is Nanite within the 8-slot budget (BoatBudget). Skipped, with a
 * warning, until the PC imports her.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingBluebonnetMeshTest, "SailingSim.Visual.BluebonnetMesh", BluebonnetTestsLocal::Flags)
bool FSailingBluebonnetMeshTest::RunTest(const FString&)
{
	auto Load = [](const TCHAR* Part)
	{
		return LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/Boats/Bluebonnet/SM_Bluebonnet_%s.SM_Bluebonnet_%s"), Part, Part), nullptr, LOAD_NoWarn | LOAD_Quiet);
	};
	UStaticMesh* Hull = Load(TEXT("Hull"));
	if (!Hull)
	{
		AddWarning(TEXT("Bluebonnet's model isn't imported yet (scripts/make-boat-models.sh, J-Class 14 step 3); skipped"));
		return true;
	}
	UStaticMesh* Mast = Load(TEXT("Mast"));
	UStaticMesh* Boom = Load(TEXT("Boom"));
	UStaticMesh* Rudder = Load(TEXT("Rudder"));
	if (!TestNotNull(TEXT("SM_Bluebonnet_Mast"), Mast) || !TestNotNull(TEXT("SM_Bluebonnet_Boom"), Boom) || !TestNotNull(TEXT("SM_Bluebonnet_Rudder"), Rudder)) return false;
	const FBoatConfig C = FBoatConfig::Make(EBoatType::Bluebonnet);
	const FBoatModel Physics(C);

	// The points the game reads, on their parts (sockets relative to each part's origin).
	auto Socket = [this](UStaticMesh* Mesh, const TCHAR* Name, FVector& Out)
	{
		const UStaticMeshSocket* S = Mesh->FindSocket(Name);
		TestNotNull(FString::Printf(TEXT("%s: socket %s"), *Mesh->GetName(), Name), S);
		Out = S ? S->RelativeLocation : FVector::ZeroVector;
		return S != nullptr;
	};
	FVector P = FVector::ZeroVector;
	for (const TCHAR* Name : { TEXT("JibLead_P"), TEXT("JibWinch_S"), TEXT("JibWinch_P"), TEXT("JibTailer_S"), TEXT("JibTailer_P"), TEXT("JibTailRest_S"),
		TEXT("JibTailRest_P"), TEXT("LazySheetVia"), TEXT("Traveler_C"), TEXT("Traveler_S") }) Socket(Hull, Name, P);
	for (const TCHAR* Name : { TEXT("MastBase"), TEXT("SpreaderTip_S"), TEXT("SpreaderTip_P") }) Socket(Mast, Name, P);
	Socket(Boom, TEXT("Boom_Mainsheet"), P);
	for (const TCHAR* Name : { TEXT("TillerEnd"), TEXT("RudderStock") }) Socket(Rudder, Name, P);
	// J-Class 14: her wheel, a part of its own on its shaft (export_game.py, deck_bluebonnet.json steering.wheel: x -10.15 on
	// the centreline, the rim 0.6 m in radius), turned about the line from the hull's WheelHub to WheelAxis.
	UStaticMesh* Wheel = Load(TEXT("Wheel"));
	FVector Hub = FVector::ZeroVector, Shaft = FVector::ZeroVector, Rim = FVector::ZeroVector;
	if (TestNotNull(TEXT("SM_Bluebonnet_Wheel (export_game.py's wheel part, imported by import_boats.py)"), Wheel))
	{
		if (Socket(Hull, TEXT("WheelHub"), Hub))
		{
			TestTrue(FString::Printf(TEXT("The wheel's hub at x %.1f cm on the centreline (her deck plan -1015)"), Hub.X), FMath::Abs(Hub.X + 1015.0) < 2.0 && FMath::Abs(Hub.Y) < 1.0);
		}
		if (Socket(Hull, TEXT("WheelAxis"), Shaft))
		{
			const FVector Along = (Shaft - Hub).GetSafeNormal();
			TestTrue(FString::Printf(TEXT("The wheel's shaft runs forward and level (%.3f, %.3f, %.3f)"), Along.X, Along.Y, Along.Z), Along.X > 0.99);
		}
		if (Socket(Wheel, TEXT("WheelRim"), Rim))
		{
			TestTrue(FString::Printf(TEXT("WheelRim straight up from the hub at the rim's radius (%.1f, %.1f, %.1f cm; 60)"), Rim.X, Rim.Y, Rim.Z),
				FMath::Abs(Rim.Z - 60.0) < 1.0 && FMath::Abs(Rim.X) < 1.0 && FMath::Abs(Rim.Y) < 1.0);
		}
		// Only the wheel (and its shaft back to the box): not a piece of the deck turning with it.
		const FBox B = Wheel->GetBoundingBox();
		TestTrue(FString::Printf(TEXT("The wheel part is the wheel: %.0f by %.0f by %.0f cm about its hub"), B.GetSize().X, B.GetSize().Y, B.GetSize().Z),
			B.GetSize().Y < 130.0 && B.GetSize().Z < 130.0 && B.Max.X < 45.0 && B.Min.X > -20.0);
	}
	FVector Step = FVector::ZeroVector, Pivot = FVector::ZeroVector, Axis = FVector::ZeroVector, Lead = FVector::ZeroVector, Hounds = FVector::ZeroVector;
	if (Socket(Hull, TEXT("MastStep"), Step))
	{
		TestTrue(FString::Printf(TEXT("The mast stands at the physics' MastX (%.1f cm, physics %.1f)"), Step.X, C.MastX * Sailing::CmPerMeter),
			FMath::Abs(Step.X - C.MastX * Sailing::CmPerMeter) < 1.0 && FMath::Abs(Step.Y) < 1.0);
	}
	if (Socket(Hull, TEXT("JibLead_S"), Lead)) TestTrue(TEXT("Starboard is +Y"), Lead.Y > 100.f);
	if (Socket(Mast, TEXT("Hounds"), Hounds))
	{
		TestTrue(FString::Printf(TEXT("The hounds (%.0f cm) over the genoa's head (%.0f cm), so the game keeps its height"), Step.Z + Hounds.Z, C.JibHeadZ * Sailing::CmPerMeter),
			Step.Z + Hounds.Z > C.JibHeadZ * Sailing::CmPerMeter);
	}
	if (Socket(Hull, TEXT("RudderPivot"), Pivot) && Socket(Hull, TEXT("RudderAxis"), Axis))
	{
		const FVector Up = (Axis - Pivot).GetSafeNormal();
		const double Rake = FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(double(Up.Z), -1.0, 1.0)));
		TestTrue(FString::Printf(TEXT("The rudder's stock raked aft (%.1f deg, her lines 39)"), Rake), Up.X < 0.f && FMath::Abs(Rake - 39.0) < 3.0);
		TestTrue(TEXT("... on the centreline, at the load waterline"), FMath::Abs(Pivot.Y) < 1.0 && FMath::Abs(Pivot.Z) < 1.0 && FMath::Abs(Up.Y) < 0.01);
	}
	for (const TCHAR* Name : { TEXT("ForestayTack"), TEXT("ChainplateUpper_S"), TEXT("ChainplateLower_S"), TEXT("BackstayPlate"), TEXT("RudderPivot_1") })
	{
		TestTrue(FString::Printf(TEXT("No %s: her standing rigging is in the mast's part, so the game draws none twice"), Name), Hull->FindSocket(Name) == nullptr);
	}

#if WITH_EDITORONLY_DATA
	// The canoe: the canoe slots of the hull and of the rudder (at its pivot), cut at Z = 0, tetrahedra to the origin.
	double Volume = 0.0, MinZ = 1e9;
	FVector3d Moment(0.0);
	FBox Canoe(ForceInit);
	auto Add = [&](UStaticMesh* Mesh, const FVector3d& Offset, bool bExtent)
	{
		const FMeshDescription* MD = Mesh->GetMeshDescription(0);
		if (!TestNotNull(FString::Printf(TEXT("%s: source mesh"), *Mesh->GetName()), MD)) return;
		FStaticMeshConstAttributes Attr(*MD);
		const TVertexAttributesConstRef<FVector3f> Pos = Attr.GetVertexPositions();
		const TPolygonGroupAttributesConstRef<FName> Slots = Attr.GetPolygonGroupMaterialSlotNames();
		double V = 0.0;
		FVector3d M(0.0);
		for (const FTriangleID T : MD->Triangles().GetElementIDs())
		{
			if (!SailingBoatPacks::IsCanoeSlot(Slots[MD->GetTrianglePolygonGroup(T)])) continue;
			const TArrayView<const FVertexID> Ids = MD->GetTriangleVertices(T);
			FVector3d Q[3];
			for (int32 K = 0; K < 3; ++K)
			{
				Q[K] = (FVector3d(Pos[Ids[K]]) + Offset) / Sailing::CmPerMeter;
				MinZ = FMath::Min(MinZ, Q[K].Z);
				if (bExtent) Canoe += FVector(Q[K]);
			}
			TArray<FVector3d, TInlineAllocator<4>> Poly;
			for (int32 K = 0; K < 3; ++K)
			{
				const FVector3d& A = Q[K], & B = Q[(K + 1) % 3];
				if (A.Z <= 0.0) Poly.Add(A);
				if ((A.Z <= 0.0) != (B.Z <= 0.0)) Poly.Add(A + (B - A) * (-A.Z / (B.Z - A.Z)));
			}
			for (int32 K = 1; K + 1 < Poly.Num(); ++K)
			{
				const double Vol = FVector3d::DotProduct(Poly[0], FVector3d::CrossProduct(Poly[K], Poly[K + 1])) / 6.0;
				V += Vol;
				M += Vol * (Poly[0] + Poly[K] + Poly[K + 1]) / 4.0;
			}
		}
		// Each part closed on its own (the rudder's face against the keel is in both), so each gets its own sign.
		Volume += FMath::Abs(V);
		Moment += V < 0.0 ? -M : M;
	};
	Add(Hull, FVector3d(0.0), true);
	Add(Rudder, FVector3d(Pivot), false);
	const double PhysVolume = Physics.DesignDisplacedVolume() + C.AppendageVolume;
	const Vec3 CanoeCB = Physics.DesignBuoyancyCentre();
	const Vec3 PhysCB = (CanoeCB * Physics.DesignDisplacedVolume() + C.AppendageCentre * C.AppendageVolume) * (1.0 / PhysVolume);
	const FVector3d CB = Volume > 1e-9 ? Moment / Volume : FVector3d(0.0);
	const double Tol = 0.02;
	TestTrue(FString::Printf(TEXT("Length overall %.3f m (physics %.3f)"), Canoe.GetSize().X, C.LengthOverall), FMath::Abs(Canoe.GetSize().X - C.LengthOverall) < Tol);
	TestTrue(FString::Printf(TEXT("Beam %.3f m (physics %.3f)"), Canoe.GetSize().Y, C.Beam), FMath::Abs(Canoe.GetSize().Y - C.Beam) < Tol);
	TestTrue(FString::Printf(TEXT("Draft %.3f m (physics %.3f)"), -MinZ, C.Draft), FMath::Abs(-MinZ - C.Draft) < Tol);
	TestTrue(FString::Printf(TEXT("Canoe and keel %.3f m^3 within 2%% of the physics %.3f (canoe %.3f, keel and rudder %.3f)"), Volume, PhysVolume,
		Physics.DesignDisplacedVolume(), C.AppendageVolume), FMath::Abs(Volume - PhysVolume) < 0.02 * PhysVolume);
	TestTrue(FString::Printf(TEXT("Centre of buoyancy (%.3f, %.3f, %.3f) within 5 cm of the physics (%.3f, %.3f, %.3f)"), CB.X, CB.Y, CB.Z, PhysCB.X, PhysCB.Y, PhysCB.Z),
		FVector3d::Dist(CB, FVector3d(PhysCB.X, PhysCB.Y, PhysCB.Z)) < 0.05);
#endif

	// Nanite (the mast too: her bend is held at zero), within the 8-slot budget, every slot a boat material, the mast's
	// bending slot where the game sets it.
	TArray<UStaticMesh*> Parts = { Hull, Mast, Boom, Rudder };
	if (Wheel) Parts.Add(Wheel);
	for (UStaticMesh* Mesh : Parts)
	{
		TestTrue(FString::Printf(TEXT("%s is Nanite"), *Mesh->GetName()), Mesh->IsNaniteEnabled());
		TestTrue(FString::Printf(TEXT("%s: %d material slots, at most 8"), *Mesh->GetName(), Mesh->GetStaticMaterials().Num()), Mesh->GetStaticMaterials().Num() <= 8);
		for (const FStaticMaterial& M : Mesh->GetStaticMaterials())
		{
			TestTrue(FString::Printf(TEXT("%s: slot %s has a boat material"), *Mesh->GetName(), *M.MaterialSlotName.ToString()),
				M.MaterialInterface && M.MaterialInterface->GetName().StartsWith(TEXT("MI_Boat_")));
		}
	}
	TestTrue(TEXT("The mast's Aluminium slot (the game's bend parameter) is MI_Boat_MastAluminium"), Mast->GetStaticMaterials().ContainsByPredicate([](const FStaticMaterial& M)
		{ return M.MaterialSlotName == TEXT("Aluminium") && M.MaterialInterface && M.MaterialInterface->GetName() == TEXT("MI_Boat_MastAluminium"); }));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingBluebonnetHelmReachTest, "SailingSim.Visual.BluebonnetHelmReach", BluebonnetTestsLocal::Flags)
bool FSailingBluebonnetHelmReachTest::RunTest(const FString&)
{
	// J-Class 14: her helm sits where both hands reach her wheel's rim (BoatModelVisuals.cpp: each hand at the rim's point
	// nearest its shoulder on the helm's side, the inboard 15-60 deg off the top, the outboard 60-110, held within 63 cm of
	// the shoulder). Shoulders estimated from the placement: 0.5 m over the pelvis, 0.17 m either side across the facing.
	// (At x -10.85, 1.1 m out, the outboard hand was 0.95 m from the rim and both stayed on the knees.)
	const FBoatConfig C = FBoatConfig::Make(EBoatType::Bluebonnet);
	const FVector Hub(-10.15, 0.0, CrewSeatSurfaceZ(C, -10.15, 0.0) + 0.33);  // deck_bluebonnet.json steering.wheel
	constexpr double RimR = 0.6, Reach = 0.63;
	for (const int32 Windward : { 1, -1 })
	{
		FCrewPlaceInput In;
		In.Config = &C;
		In.Index = C.CrewCount - 1;
		In.WindwardSide = Windward;
		In.CrewOffset = Windward * 1.0;
		FCrewPlacement Pl;
		CrewPlacement(In, Pl);
		if (!TestTrue(TEXT("The last figure is the helm"), Pl.bHelm)) continue;
		const double Side = Pl.Pelvis.Y < 0.0 ? -1.0 : 1.0;
		TestTrue(FString::Printf(TEXT("The helm sits clear of the rim (%.2f m out; the rim 0.6)"), FMath::Abs(Pl.Pelvis.Y)), FMath::Abs(Pl.Pelvis.Y) > RimR + 0.25);
		const FVector Facing = FRotator(0.0, Pl.Yaw, 0.0).Vector(), Right(-Facing.Y, Facing.X, 0.0);
		for (const double Across : { -0.17, 0.17 })
		{
			const FVector Shoulder = Pl.Pelvis + Right * Across + FVector(0.0, 0.0, 0.5);
			const bool bInboard = FMath::Abs(Shoulder.Y) < FMath::Abs(Pl.Pelvis.Y);
			const FVector Rel = Shoulder - Hub;
			const double Off = FMath::Atan2(Side * Rel.Y, Rel.Z);
			const double A = bInboard ? FMath::Clamp(Off, FMath::DegreesToRadians(15.0), FMath::DegreesToRadians(60.0))
				: FMath::Clamp(Off, FMath::DegreesToRadians(60.0), FMath::DegreesToRadians(110.0));
			const FVector At = Hub + RimR * FVector(0.0, Side * FMath::Sin(A), FMath::Cos(A));
			const double D = FVector::Dist(Shoulder, At);
			TestTrue(FString::Printf(TEXT("Windward %d, %s hand: the rim %.2f m from the shoulder (reach %.2f)"), Windward, bInboard ? TEXT("inboard") : TEXT("outboard"), D, Reach), D < Reach);
		}
	}
	// The wheel turns 1.5 turns to hard over, its top to starboard as the bow goes to starboard (a positive helm).
	const double Hard = FMath::DegreesToRadians(C.MaxRudderAngleDeg);
	TestTrue(TEXT("Hard over to starboard turns the wheel 1.5 turns, top to starboard (negative about the forward shaft)"),
		FMath::IsNearlyEqual(ASailboatPawn::WheelTurnFor(Hard, C.MaxRudderAngleDeg), -3.0 * UE_DOUBLE_PI, 1e-9));
	const FVector Top = FQuat(FVector::ForwardVector, ASailboatPawn::WheelTurnFor(0.1, C.MaxRudderAngleDeg)).RotateVector(FVector::UpVector);
	TestTrue(TEXT("... a little helm to starboard takes the top to starboard"), Top.Y > 0.0);
	return true;
}

#endif
