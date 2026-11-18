// The rebuilt Catalina 22 in the physics (slice 10, docs/c22-11): her hull is the model's sections, her swing keel turns
// about its pin with its iron, her rudder kicks up on the bottom, and her rig is the model's (the boom 11.5 cm higher).
#include "Misc/AutomationTest.h"
#include "AutoTrim.h"
#include "BoatModel.h"
#include "FixedStepper.h"
#include "LakeTerrain.h"

#if WITH_DEV_AUTOMATION_TESTS

using namespace Sailing;

namespace C22PhysicsTestsLocal
{
	constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	FWindField WindFrom(double Knots, double FromDeg)
	{
		FWindParams P;
		P.SpeedKnots = Knots;
		P.FromDegrees = FromDeg;
		return FWindField(P);
	}

	/** Water `ShallowDepth` deep for X under `DeepFromX`, 5 m from there on, flat across (Y -100 to 100). */
	FLakeTerrain StepLake(double ShallowDepth, double DeepFromX)
	{
		const int Rows = 200, Cols = 100;
		std::vector<float> H(Rows * Cols);
		for (int R = 0; R < Rows; ++R)
			for (int C = 0; C < Cols; ++C)
				H[R * Cols + C] = float(-20.0 + R * 2.0 < DeepFromX ? -ShallowDepth : -5.0);
		FLakeTerrain T;
		T.InitSynthetic(Rows, Cols, 2.0, -20.0, -100.0, H);
		return T;
	}

	struct FRun { double Knots = 0.0, HeelDeg = 0.0, LeewayDeg = 0.0, MaxKick = 0.0, EndKick = 0.0, X = 0.0; bool bAground = false; };

	/** Sails her north on a beam reach (or at TWA) for Seconds with the board at Board, the polars' ideal trimmer and the autopilot. */
	FRun Sail(double Board, double Knots, double Twa, double Seconds, const FLakeTerrain* Lake = nullptr)
	{
		FBoatModel Boat(FBoatConfig::Make(EBoatType::Catalina22));
		if (Lake) Boat.SetTerrain(Lake);
		Boat.Reset(0.0, 0.0, 0.0, 3.0 * kKnot);
		const FWindField Wind = WindFrom(Knots, Twa);
		FBoatControls C;
		C.Board = Board;
		FAutoTrim Trim;
		Trim.Settings.bHands = false;
		FAutopilot Helm;
		Helm.TargetTWADeg = Twa;
		FRun R;
		const int32 Steps = FMath::RoundToInt(Seconds * PhysicsHz);
		double Heel = 0.0, Leeway = 0.0, Speed = 0.0;
		int32 N = 0;
		for (int32 I = 0; I < Steps; ++I)
		{
			C = Trim.Update(Boat, C, PhysicsDt);
			C.Board = Board;
			C.Tiller = Helm.Update(Boat);
			Boat.Step(PhysicsDt, C, Wind);
			const FBoatTelemetry& T = Boat.GetTelemetry();
			R.bAground |= T.bAground && T.DepthUnderKeel < -0.05;
			R.MaxKick = FMath::Max(R.MaxKick, T.RudderKick);
			if (I > Steps / 2)
			{
				Heel += FMath::Abs(T.Heel) * kRadToDeg; Leeway += FMath::Abs(T.Leeway) * kRadToDeg; Speed += T.SpeedThroughWater / kKnot; ++N;
			}
		}
		R.HeelDeg = Heel / FMath::Max(N, 1); R.LeewayDeg = Leeway / FMath::Max(N, 1); R.Knots = Speed / FMath::Max(N, 1);
		R.EndKick = Boat.GetTelemetry().RudderKick;
		R.X = Boat.OriginPosition().X;
		return R;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingC22HullTest, "SailingSim.Physics.C22Hull", C22PhysicsTestsLocal::Flags)
bool FSailingC22HullTest::RunTest(const FString& Parameters)
{
	// Her hull is the model's own sections (Catalina22HullData.inl, export_physics_c22.py): the size card's length and
	// beam, the keel's 5 ft draft plus her crew's 2.8 cm sink, and the hull's volume and centre of buoyancy from hull_c22.
	// She floats level on her drawn waterline.
	const FBoatConfig C = FBoatConfig::Make(EBoatType::Catalina22);
	if (!TestEqual(TEXT("One hull"), int32(C.Hulls.size()), 1)) return false;
	const FHullShape& H = C.Hulls[0];
	TestTrue(TEXT("The hull is drawn by its sections"), H.HasStations());
	AddInfo(FString::Printf(TEXT("Hull %.3f m long, %.3f m beam, %d stations; draft %.3f"), H.BowX - H.SternX, 2.0 * H.MaxHalfBeam, int32(H.Stations.size()), C.Draft));
	TestTrue(TEXT("Length 21 ft 6 in (6.553 m)"), FMath::Abs(H.BowX - H.SternX - 6.553) < 0.02);
	TestTrue(TEXT("Beam 7 ft 8 in (2.337 m)"), FMath::Abs(2.0 * H.MaxHalfBeam - 2.337) < 0.02);
	TestTrue(TEXT("Draft 5 ft (1.524 m) plus the crew's sink"), FMath::Abs(C.Draft - 1.552) < 0.01);
	const FBoatModel Boat(C);
	const Vec3 CB = Boat.DesignBuoyancyCentre();
	AddInfo(FString::Printf(TEXT("Canoe depth %.4f m, volume %.4f m^3, CB x %.3f z %.3f; mass %.0f kg"), Boat.HullDepth(), Boat.DesignDisplacedVolume(), CB.X, CB.Z, Boat.TotalMass()));
	TestTrue(TEXT("2,250 lb with her crew"), FMath::Abs(Boat.TotalMass() - 1248.0) < 2.0);
	TestTrue(TEXT("The hull's volume is hull_c22's 1.220 m^3 (2%)"), FMath::Abs(Boat.DesignDisplacedVolume() / 1.220 - 1.0) < 0.02);
	TestTrue(TEXT("Its centre of buoyancy is hull_c22's (2 cm)"), FMath::Abs(CB.X + 0.093) < 0.02 && FMath::Abs(CB.Z + 0.087) < 0.02);
	TestTrue(TEXT("The canoe body floats at the model's depth (0.237 m, 5 mm)"), FMath::Abs(Boat.HullDepth() - 0.2367) < 0.005);

	FBoatModel Rest(C);
	Rest.Reset(0.0, 0.0, 0.0, 0.0);
	FBoatControls Calm;
	const FWindField Still = C22PhysicsTestsLocal::WindFrom(0.01, 0.0);
	for (int32 I = 0; I < FMath::RoundToInt(20.0 * PhysicsHz); ++I) Rest.Step(PhysicsDt, Calm, Still);
	const double Pitch = Rest.GetTelemetry().Pitch * kRadToDeg;
	AddInfo(FString::Printf(TEXT("At rest: pitch %.2f deg"), Pitch));
	TestTrue(TEXT("She floats on her lines, not by the stern or the bow"), FMath::Abs(Pitch) < 0.3);

	// The rig: the boom 11.5 cm above the old physics' (Bean, Nov 16), the main from the gooseneck, the genoa cut high.
	AddInfo(FString::Printf(TEXT("Boom %.3f m, main luff x %.3f, masthead %.3f; genoa %.2f m^2 tacked %.3f m up"), C.BoomZ, C.MainLuffX, C.MastheadZ, C.Jib.TotalArea, C.Jib.Strips[0].ZBottom));
	TestTrue(TEXT("The boom raised 11.5 cm"), FMath::Abs(C.BoomZ - (1.45 + 0.115)) < 0.002);
	TestTrue(TEXT("The main's foot on the boom"), FMath::Abs(C.MainFootZ - C.BoomZ) < 1e-6);
	TestTrue(TEXT("Its luff P (21 ft 0 in) long"), FMath::Abs(C.MainHeadZ - C.MainFootZ - 6.401) < 0.01);
	TestTrue(TEXT("The main's tack at the gooseneck"), FMath::Abs(C.MainLuffX - 0.78) < 0.01);
	TestTrue(TEXT("The genoa as drawn (12.54 m^2)"), FMath::Abs(C.Jib.TotalArea - 12.54) < 0.05);
	TestTrue(TEXT("Its tack on the pennant, over the pulpit"), C.Jib.Strips[0].ZBottom > 1.4);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingC22SwingKeelTest, "SailingSim.Physics.C22SwingKeel", C22PhysicsTestsLocal::Flags)
bool FSailingC22SwingKeelTest::RunTest(const FString& Parameters)
{
	// The swing keel turns about its pin from 5 ft down to 2 ft up (plus the crew's sink): its foot, its area and its iron
	// follow it. Raised she makes more leeway and heels more (the iron is higher), and floats over a 1 m shoal the keel
	// down would ground on.
	using namespace C22PhysicsTestsLocal;
	const FBoatConfig C = FBoatConfig::Make(EBoatType::Catalina22);
	const FFoilDef* Keel = nullptr;
	for (const FFoilDef& F : C.Foils) if (F.Role == EFoilRole::Keel) Keel = &F;
	if (!TestNotNull(TEXT("A keel"), Keel)) return false;
	TestTrue(TEXT("It swings (a table, Board 0 to 1)"), Keel->bRetractable && Keel->Swing.size() >= 2);
	const FFoilDef::FSwingPoint Up = Keel->SwingAt(0.0), Down = Keel->SwingAt(1.0);
	AddInfo(FString::Printf(TEXT("Down: %.3f m^2, foot z %.3f, iron z %.3f; up: %.3f m^2, foot z %.3f, iron z %.3f"), Down.Area, Down.TipZ, Down.MassZ, Up.Area, Up.TipZ, Up.MassZ));
	TestTrue(TEXT("Down to 5 ft 0 in plus the sink"), FMath::Abs(Down.TipZ + 1.552) < 0.01);
	TestTrue(TEXT("Up to 2 ft 0 in plus the sink"), FMath::Abs(Up.TipZ + 0.638) < 0.01);
	TestTrue(TEXT("The keel's place in the config is the table's down"), FMath::Abs(Keel->Params.Area - Down.Area) < 1e-6 && FMath::Abs(Keel->Params.Center.X - Down.X) < 1e-6);
	TestTrue(TEXT("The iron rises with it"), Up.MassZ > Down.MassZ + 0.4);
	TestTrue(TEXT("Its 249 kg swing"), FMath::Abs(Keel->SwingMass - 249.0) < 1.0);
	bool bMonotonic = true;
	for (size_t I = 1; I < Keel->Swing.size(); ++I)
		bMonotonic &= Keel->Swing[I].Area >= Keel->Swing[I - 1].Area && Keel->Swing[I].TipZ <= Keel->Swing[I - 1].TipZ;
	TestTrue(TEXT("More keel in the water, and deeper, the further down"), bMonotonic);

	const FRun KeelDown = Sail(1.0, 12.0, 50.0, 90.0);
	const FRun KeelUp = Sail(0.0, 12.0, 50.0, 90.0);
	AddInfo(FString::Printf(TEXT("12 kn at 50 deg: keel down %.2f kn, heel %.1f, leeway %.1f; up %.2f kn, heel %.1f, leeway %.1f"),
		KeelDown.Knots, KeelDown.HeelDeg, KeelDown.LeewayDeg, KeelUp.Knots, KeelUp.HeelDeg, KeelUp.LeewayDeg));
	TestTrue(TEXT("Keel up, she slips to leeward"), KeelUp.LeewayDeg > KeelDown.LeewayDeg + 3.0);

	// In a calm her crew on the side lists her: more with the iron raised.
	double List[2] = { 0.0, 0.0 };
	for (int32 K = 0; K < 2; ++K)
	{
		FBoatModel Boat(C);
		Boat.Reset(0.0, 0.0, 0.0, 0.0);
		FBoatControls Calm;
		Calm.Board = K == 0 ? 1.0 : 0.0;
		const FWindField Still = WindFrom(0.01, 0.0);
		for (int32 I = 0; I < FMath::RoundToInt(20.0 * PhysicsHz); ++I) Boat.Step(PhysicsDt, Calm, Still);
		List[K] = FMath::Abs(Boat.GetTelemetry().Heel) * kRadToDeg;
	}
	AddInfo(FString::Printf(TEXT("Calm, the crew on one side: list %.2f deg keel down, %.2f up"), List[0], List[1]));
	TestTrue(TEXT("Keel up, the same crew list her more"), List[1] > List[0] + 0.2);

	const FLakeTerrain Shoal = StepLake(1.0, 1000.0);
	const FRun GroundDown = Sail(1.0, 10.0, 90.0, 30.0, &Shoal);
	const FRun GroundUp = Sail(0.0, 10.0, 90.0, 30.0, &Shoal);
	AddInfo(FString::Printf(TEXT("1 m of water: keel down aground %d, %.1f m; up aground %d, %.1f m"), GroundDown.bAground, GroundDown.X, GroundUp.bAground, GroundUp.X));
	TestTrue(TEXT("Keel down, a 1 m shoal grounds her"), GroundDown.bAground);
	TestFalse(TEXT("Keel up, she sails over it"), GroundUp.bAground);
	TestTrue(TEXT("and on across it"), GroundUp.X > GroundDown.X + 20.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingC22KickUpRudderTest, "SailingSim.Physics.C22KickUpRudder", C22PhysicsTestsLocal::Flags)
bool FSailingC22KickUpRudderTest::RunTest(const FString& Parameters)
{
	// Keel up in 0.8 m of water, the rudder's 0.94 m blade touches: it kicks up as far as the bottom pushes it, she keeps
	// sailing and steering, and once in deep water it drops back down.
	using namespace C22PhysicsTestsLocal;
	const FBoatConfig C = FBoatConfig::Make(EBoatType::Catalina22);
	const FFoilDef* Rudder = nullptr;
	for (const FFoilDef& F : C.Foils) if (F.Role == EFoilRole::Rudder) Rudder = &F;
	if (!TestNotNull(TEXT("A rudder"), Rudder)) return false;
	TestTrue(TEXT("It kicks up"), Rudder->KickUp.size() >= 2);
	TestTrue(TEXT("Down, its foot 36 in plus the sink under the water"), FMath::Abs(Rudder->KickAt(0.0).TipZ + 0.942) < 0.01);
	TestTrue(TEXT("Kicked up, clear of the water"), Rudder->KickAt(1.0).TipZ > 0.0 && Rudder->KickAt(1.0).Area < 0.005);

	const FLakeTerrain Lake = StepLake(0.8, 60.0);
	const FRun R = Sail(0.0, 10.0, 90.0, 40.0, &Lake);
	AddInfo(FString::Printf(TEXT("0.8 m then deep: kick up to %.2f, %.2f at the end; aground %d; %.1f m sailed, %.2f kn"), R.MaxKick, R.EndKick, R.bAground, R.X, R.Knots));
	TestTrue(TEXT("The bottom kicked the blade up"), R.MaxKick > 0.15);
	TestFalse(TEXT("The rudder doesn't ground her"), R.bAground);
	TestTrue(TEXT("She sailed on into deep water"), R.X > 80.0);
	TestTrue(TEXT("and the blade came back down"), R.EndKick < 0.01);
	return true;
}

#endif
