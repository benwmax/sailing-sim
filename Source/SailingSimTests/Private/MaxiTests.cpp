#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "BoatModel.h"
#include "EasyAssists.h"
#include "FixedStepper.h"
#include "PolarReference.h"
#include "Scenarios.h"

#if WITH_DEV_AUTOMATION_TESTS

using namespace Sailing;

// Prologue step 3 (docs/prologue/README.md): the maxi's physics class, built from the PC's exported hull
// (Tools/boats/maxi/ref.json and sections.json).
namespace MaxiTestsLocal
{
	constexpr EAutomationTestFlags MaxiFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	TSharedPtr<FJsonObject> ReadJson(FAutomationTestBase& Test, const TCHAR* Name)
	{
		FString Text;
		const FString Path = FPaths::ProjectDir() / TEXT("Tools/boats/maxi") / Name;
		TSharedPtr<FJsonObject> Root;
		if (!FFileHelper::LoadFileToString(Text, *Path) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root.IsValid())
		{
			Test.AddError(FString::Printf(TEXT("Could not read %s"), *Path));
			return nullptr;
		}
		return Root;
	}
}

/** The floating draft, centre of buoyancy and displacement come from the exported hull and keel. */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingMaxiHullTest, "SailingSim.Physics.MaxiHull", MaxiTestsLocal::MaxiFlags)
bool FSailingMaxiHullTest::RunTest(const FString&)
{
	using namespace MaxiTestsLocal;
	const TSharedPtr<FJsonObject> Ref = ReadJson(*this, TEXT("ref.json"));
	const TSharedPtr<FJsonObject> Sections = ReadJson(*this, TEXT("sections.json"));
	if (!Ref || !Sections) return false;
	const FBoatConfig C = FBoatConfig::Make(EBoatType::Maxi);
	const FBoatModel Boat(C);
	if (!TestEqual(TEXT("One hull, drawn by its sections"), int32(C.Hulls.size()), 1) || !TestTrue(TEXT("... the exported ones"), C.Hulls[0].HasStations())) return false;
	TestEqual(TEXT("Every exported station"), int32(C.Hulls[0].Stations.size()), Sections->GetArrayField(TEXT("stations")).Num());

	// Draft: she floats on the design waterline the model is drawn to.
	const double CanoeDepth = Ref->GetNumberField(TEXT("canoe_depth"));
	AddInfo(FString::Printf(TEXT("Mass %.0f kg, canoe depth %.3f m (ref.json %.3f), canoe volume %.2f m^3 (sections.json %.2f), appendages %.2f m^3"), Boat.TotalMass(),
		Boat.HullDepth(), CanoeDepth, Boat.DesignDisplacedVolume(), Sections->GetNumberField(TEXT("canoe_volume_m3")), C.AppendageVolume));
	TestTrue(TEXT("Floating draft of the canoe body within 2 cm of ref.json"), FMath::Abs(Boat.HullDepth() - CanoeDepth) <= 0.02);
	TestTrue(TEXT("The keel's foot at ref.json's draft"), FMath::IsNearlyEqual(C.Draft, Ref->GetNumberField(TEXT("draft")), 0.01));

	// Centre of buoyancy (x, z) within 5 cm of the export's.
	const TArray<TSharedPtr<FJsonValue>>& Cb = Sections->GetArrayField(TEXT("centre_of_buoyancy"));
	const Vec3 B = Boat.DesignBuoyancyCentre();
	AddInfo(FString::Printf(TEXT("Centre of buoyancy (%.3f, %.3f), export (%.3f, %.3f)"), B.X, B.Z, Cb[0]->AsNumber(), Cb[1]->AsNumber()));
	TestTrue(TEXT("Centre of buoyancy x within 5 cm"), FMath::Abs(B.X - Cb[0]->AsNumber()) <= 0.05);
	TestTrue(TEXT("Centre of buoyancy z within 5 cm"), FMath::Abs(B.Z - Cb[1]->AsNumber()) <= 0.05);
	TestTrue(TEXT("... on the centreline"), FMath::Abs(B.Y) < 1e-6);

	// Displacement: the canoe body's volume as exported, plus the fin, bulb and rudders, floats her whole weight.
	TestTrue(TEXT("Canoe volume within 2% of the export"), FMath::Abs(Boat.DesignDisplacedVolume() / Sections->GetNumberField(TEXT("canoe_volume_m3")) - 1.0) <= 0.02);
	TestTrue(TEXT("Weight = water displaced by the canoe body and appendages (0.5%)"),
		FMath::Abs(Boat.TotalMass() / (kWaterDensity * (Boat.DesignDisplacedVolume() + C.AppendageVolume)) - 1.0) <= 0.005);
	// ref.json's 42 t is sea water (1025 kg/m^3); the sim's water is fresh, so compare the volumes.
	const double RefVolume = Ref->GetNumberField(TEXT("displacement_kg")) / 1025.0;
	TestTrue(TEXT("Displaced volume within 3% of ref.json's 42 t in sea water"), FMath::Abs(Boat.TotalMass() / kWaterDensity / RefVolume - 1.0) <= 0.03);
	TestTrue(TEXT("LOA, LWL and beam as ref.json"), FMath::IsNearlyEqual(C.LengthOverall, Ref->GetNumberField(TEXT("loa")), 0.01)
		&& FMath::IsNearlyEqual(C.WaterlineLength, Ref->GetNumberField(TEXT("lwl")), 0.01) && FMath::IsNearlyEqual(C.Beam, Ref->GetNumberField(TEXT("beam_max")), 0.01));
	TestEqual(TEXT("Twelve crew"), C.CrewCount, Ref->GetArrayField(TEXT("crew_stations")).Num());

	// The hull follows the sections: the deck edge at each station, and the keel line.
	for (const TSharedPtr<FJsonValue>& V : Sections->GetArrayField(TEXT("stations")))
	{
		const TSharedPtr<FJsonObject> S = V->AsObject();
		const double X = S->GetNumberField(TEXT("x"));
		const TArray<TSharedPtr<FJsonValue>>& Half = S->GetArrayField(TEXT("half_section"));
		const double DeckY = Half.Last()->AsArray()[0]->AsNumber(), KeelZ = Half[0]->AsArray()[1]->AsNumber();
		const FHullShape& H = C.Hulls[0];
		TestTrue(FString::Printf(TEXT("Deck half-beam at x %.2f"), X), FMath::Abs(H.DeckHalfBeam(X) - FMath::Max(DeckY, 0.02)) < 0.01);
		TestTrue(FString::Printf(TEXT("Keel at x %.2f (moved by the sinkage)"), X), FMath::Abs(-H.KeelLineDepth(X, Boat.HullDepth()) - (KeelZ - (Boat.HullDepth() - H.StationDepth))) < 0.01);
	}

	// Floating level, and the righting curve from the hull and keel: stiff, positive all the way past 90 deg.
	FBoatModel Free(C);
	Free.Reset(0.0, 0.0, 0.0, 0.0);
	FWindParams Calm;
	Calm.SpeedKnots = 0.0;
	const FWindField Still(Calm);
	FBoatControls Loose;
	Loose.MainSheet = Loose.JibSheet = 1.0;
	for (int32 I = 0; I < int32(20.0 * PhysicsHz); ++I) { ++GFrameCounter; Free.Step(PhysicsDt, Loose, Still); }
	AddInfo(FString::Printf(TEXT("At rest: pitch %.2f deg, heel %.2f deg, sinkage %.3f m"), Free.GetTelemetry().Pitch * kRadToDeg, Free.GetTelemetry().Heel * kRadToDeg,
		Free.OriginPosition().Z));
	TestTrue(TEXT("Trimmed level at rest (within 0.3 deg)"), FMath::Abs(Free.GetTelemetry().Pitch) < 0.3 * kDegToRad);
	TestTrue(TEXT("Floating on her lines (within 2 cm)"), FMath::Abs(Free.OriginPosition().Z) < 0.02);
	double Last = 0.0;
	for (const double Deg : { 5.0, 10.0, 20.0, 30.0, 45.0, 60.0, 90.0, 110.0 })
	{
		const double Rm = Boat.RightingMomentAt(Deg * kDegToRad);
		AddInfo(FString::Printf(TEXT("RM at %3.0f deg: %8.0f N m (GZ %.2f m)"), Deg, Rm, Rm / (Boat.TotalMass() * kGravity)));
		TestTrue(FString::Printf(TEXT("Righting at %.0f deg"), Deg), Rm > 0.0);
		if (Deg <= 45.0) TestTrue(FString::Printf(TEXT("... and stiffening to %.0f deg"), Deg), Rm > Last);
		Last = Rm;
	}
	const double Gm = Boat.RightingMomentAt(2.0 * kDegToRad) / (Boat.TotalMass() * kGravity * FMath::Sin(2.0 * kDegToRad));
	AddInfo(FString::Printf(TEXT("GM %.2f m"), Gm));
	TestTrue(TEXT("A maxi's metacentric height (4-10 m: a deep bulb under a wide hull)"), Gm > 4.0 && Gm < 10.0);
	return true;
}

/** The estimated reference polar (no published polar: FleetReferencePolar's comment says how) within its tolerance. */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingMaxiPolarTest, "SailingSim.Physics.MaxiPolar", MaxiTestsLocal::MaxiFlags)
bool FSailingMaxiPolarTest::RunTest(const FString&)
{
	const FBoatConfig Config = FBoatConfig::Make(EBoatType::Maxi);
	const std::vector<FPolarPoint>& Polar = FleetReferencePolar(EBoatType::Maxi);
	TestEqual(TEXT("Fifteen points: 6, 10 and 16 kn, five angles"), int32(Polar.size()), 15);
	double Worst = 0.0;
	for (const FPolarPoint& P : Polar)
	{
		const FSteadyResult R = SailSteady(P.TrueWindKnots, P.TrueWindAngleDeg, Config, true, P.bSpinnaker);
		const double Err = (R.BoatSpeedKnots - P.BoatSpeedKnots) / P.BoatSpeedKnots;
		Worst = FMath::Max(Worst, FMath::Abs(Err));
		AddInfo(FString::Printf(TEXT("%4.0f %5.1f%s %5.2f %5.2f %+5.1f%% heel %4.1f rudder %4.1f"), P.TrueWindKnots, P.TrueWindAngleDeg, P.bSpinnaker ? TEXT("s") : TEXT(" "),
			P.BoatSpeedKnots, R.BoatSpeedKnots, Err * 100.0, R.HeelDeg, R.RudderDeg));
		TestTrue(FString::Printf(TEXT("%.0f kn at %.0f deg within %.0f%% (%.2f vs %.2f kn)"), P.TrueWindKnots, P.TrueWindAngleDeg, P.Tolerance * 100.0,
			R.BoatSpeedKnots, P.BoatSpeedKnots), FMath::Abs(Err) <= P.Tolerance);
		// A sailing maxi carries a little weather helm upwind (positive), never lee helm.
		if (P.TrueWindAngleDeg < 70.0 && P.TrueWindKnots >= 10.0) TestTrue(FString::Printf(TEXT("Weather helm upwind in %.0f kn (%.1f deg)"), P.TrueWindKnots, R.RudderDeg), R.RudderDeg > 0.0 && R.RudderDeg < 6.0);
	}
	AddInfo(FString::Printf(TEXT("Worst error %.1f%%"), Worst * 100.0));
	// Heavy-air tacks: under her gale sails she tacks in 30 kn; with full sail she cannot (the reason for the reefs).
	const FTackResult Reefed = RunTack(Config, 30.0, 2);
	const FTackResult Full = RunTack(Config, 30.0, 0);
	AddInfo(FString::Printf(TEXT("Tack in 30 kn, two reefs: %s in %.1f s, %.1f -> min %.1f kn; full sail: %s"), Reefed.bCompleted ? TEXT("done") : TEXT("not done"), Reefed.TackSeconds,
		Reefed.SpeedBeforeKnots, Reefed.MinSpeedKnots, Full.bCompleted ? TEXT("done") : TEXT("not done")));
	TestTrue(TEXT("Tacks in 30 kn with two reefs, inside 25 s"), Reefed.bCompleted && Reefed.TackSeconds < 25.0);
	TestTrue(TEXT("... keeping way on"), Reefed.MinSpeedKnots > 2.0);
	TestTrue(TEXT("The reefs and the J4 shrink the sails"), [&]
	{
		FBoatConfig R = Config;
		R.BuildMain(2);
		return R.Main.TotalArea < 0.75 * Config.Main.TotalArea && FMath::IsNearlyEqual(R.Jib.TotalArea, 0.35 * Config.Jib.TotalArea, 1.0);
	}());
	return true;
}

/** A 40 kn gust on a close reach: past 30 deg of heel but no capsize without the limits; the prologue's limits cap it. */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingMaxiGaleTest, "SailingSim.Physics.MaxiGale", MaxiTestsLocal::MaxiFlags)
bool FSailingMaxiGaleTest::RunTest(const FString&)
{
	const FBoatConfig Config = FBoatConfig::Make(EBoatType::Maxi);
	const FGustReachResult Off = RunGustReach(Config, 30.0, 40.0, 70.0, 2, false);
	const FGustReachResult On = RunGustReach(Config, 30.0, 40.0, 70.0, 2, true);
	for (const FGustReachResult* R : { &Off, &On })
	{
		AddInfo(FString::Printf(TEXT("Gust 30 -> 40 kn at TWA 70, two reefs, limits %s: heel %.1f deg, %.1f -> %.1f kn, closest to the wind %.0f deg, course error %.0f deg, capsized %d"),
			R == &On ? TEXT("on") : TEXT("off"), R->MaxHeelDeg, R->SpeedBeforeKnots, R->MaxSpeedKnots, R->MinTwaDeg, R->MaxCourseErrorDeg, int32(R->bCapsized)));
	}
	TestTrue(TEXT("Limits off: the gust lays her past 30 deg"), Off.MaxHeelDeg > 30.0);
	TestTrue(TEXT("... but the bulb brings her back: no capsize, never past 60"), !Off.bCapsized && Off.MaxHeelDeg < 60.0);
	TestTrue(TEXT("Limits on: held near the 35 deg cap"), On.MaxHeelDeg < FSceneLimits().HeelCapDeg + 2.0 && !On.bCapsized);
	TestTrue(TEXT("... and no broach: within 15 deg of her course, never closer than 55 deg to the wind"), On.MaxCourseErrorDeg < 15.0 && On.MinTwaDeg > 55.0);
	// A broad reach too: the gust drives her fast and level enough to steer.
	const FGustReachResult Broad = RunGustReach(Config, 30.0, 40.0, 100.0, 2, true);
	AddInfo(FString::Printf(TEXT("Gust at TWA 100, limits on: heel %.1f deg, %.1f -> %.1f kn, course error %.0f deg"), Broad.MaxHeelDeg, Broad.SpeedBeforeKnots, Broad.MaxSpeedKnots, Broad.MaxCourseErrorDeg));
	TestTrue(TEXT("Broad reach: no capsize, no broach"), !Broad.bCapsized && Broad.MaxCourseErrorDeg < 20.0 && Broad.MinTwaDeg > 70.0);
	TestTrue(TEXT("... and faster in the gust"), Broad.MaxSpeedKnots > Broad.SpeedBeforeKnots);
	// Normal sailing never sets the limits: off, the boat's own config is untouched.
	FBoatConfig Plain = Config;
	FSceneLimits::For(false).ApplyTo(Plain);
	TestTrue(TEXT("Off changes nothing"), Plain.HeelCapDeg == Config.HeelCapDeg && Plain.YawDampingLinear == Config.YawDampingLinear && Plain.Foils[1].VentDepth == Config.Foils[1].VentDepth);
	FBoatConfig Scene = Config;
	FSceneLimits::For(true).ApplyTo(Scene);
	TestTrue(TEXT("On sets the cap"), Scene.HeelCapDeg == FSceneLimits().HeelCapDeg && Scene.HeelCapLeverM > 0.0);
	return true;
}

#endif
