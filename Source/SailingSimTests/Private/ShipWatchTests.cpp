#include "Misc/AutomationTest.h"
#include "BoatModel.h"
#include "CrewPose.h"
#include "CrewMotion.h"
#include "ShipWalk.h"

#include <limits>

#if WITH_DEV_AUTOMATION_TESTS

/**
 * A square-rigged ship's deck watch (docs/ship-rig/): her spar deck under the sheer for the crew's feet, the watch's
 * stations on it (with and without her walk map), and the standing stance.
 */
namespace ShipWatchTestsLocal
{
	constexpr EAutomationTestFlags TestFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	/** One flat deck 4.1 m up over the frigate's plan, with the Helm spot where her walk map has it. */
	Sailing::FWalkMap FlatShip(const Sailing::FBoatConfig& Cfg, double Z)
	{
		using namespace Sailing;
		const FHullShape& H = Cfg.Hulls[0];
		FWalkDeck D;
		D.Name = "Spar";
		D.Cell = 0.2;
		D.X0 = H.SternX;
		D.Y0 = -7.0;
		D.NX = int(FMath::CeilToInt((H.BowX - H.SternX) / D.Cell)) + 1;
		D.NY = 71;
		D.Floor.assign(size_t(D.NX) * D.NY, std::numeric_limits<float>::quiet_NaN());
		D.Overhead.assign(size_t(D.NX) * D.NY, std::numeric_limits<float>::infinity());
		for (int J = 0; J < D.NY; ++J)
		{
			for (int I = 0; I < D.NX; ++I)
			{
				const double X = D.X0 + I * D.Cell, Y = D.Y0 + J * D.Cell;
				if (X >= H.SternX && X <= H.BowX && FMath::Abs(Y) < H.DeckHalfBeam(X) - 0.15) D.Floor[D.Index(I, J)] = float(Z);
			}
		}
		FWalkMap M;
		M.Decks.push_back(D);
		FWalkSpot Helm;
		Helm.Name = "Helm";
		Helm.Deck = 0;
		Helm.X = -23.2;
		M.Spots.push_back(Helm);
		M.Finish();
		return M;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FShipWatchDeckTest, "SailingSim.Visual.ShipWatch.Deck", ShipWatchTestsLocal::TestFlags)
bool FShipWatchDeckTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	const FBoatConfig Ship = FBoatConfig::Make(EBoatType::Commonwealth);
	const FBoatConfig J22;
	TestTrue(TEXT("the frigate is square-rigged"), Ship.HasSquareRig());
	TestEqual(TEXT("a watch of eight"), ShipWatchCount(Ship), 8);
	TestEqual(TEXT("a J/22 has no deck watch"), ShipWatchCount(J22), 0);
	const FHullShape& H = Ship.Hulls[0];
	for (const double X : { -20.0, 0.0, 15.0 })
	{
		const double Deck = CrewShipDeckZ(Ship, X);
		TestEqual(FString::Printf(TEXT("the spar deck at x %.0f is the bulwark's height under the sheer"), X), Deck, H.SheerHeight(X) - CrewShipBulwarkM, 1e-9);
		TestEqual(FString::Printf(TEXT("the crew's floor at x %.0f is the deck"), X), CrewFloorZ(Ship, X, 0.0), Deck, 1e-9);
		const double Half = H.DeckHalfBeam(X);
		TestTrue(TEXT("solid under the deck"), CrewInsideBoat(Ship, 3.0, FVector(X, 0.0, Deck - 0.1)));
		TestFalse(TEXT("open over it"), CrewInsideBoat(Ship, 3.0, FVector(X, 0.0, Deck + 0.05)));
		TestFalse(TEXT("open at head height amidships"), CrewInsideBoat(Ship, 3.0, FVector(X, 0.5 * Half, Deck + 1.7)));
		TestTrue(TEXT("the bulwark is solid up to the sheer"), CrewInsideBoat(Ship, 3.0, FVector(X, Half - 0.05, Deck + 0.7)));
		TestFalse(TEXT("nothing over the rail"), CrewInsideBoat(Ship, 3.0, FVector(X, Half - 0.05, H.SheerHeight(X) + 0.05)));
	}
	// The J/22 is as it was (CrewHullClearance and the others hold the fleet; this is the guard that the ship branch is hers only).
	TestTrue(TEXT("a J/22's deck is at her sheer, not under a bulwark"), CrewFloorZ(J22, -1.0, 0.9) > J22.Hulls[0].SheerHeight(-1.0) - 0.5);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FShipWatchStationsTest, "SailingSim.Visual.ShipWatch.Stations", ShipWatchTestsLocal::TestFlags)
bool FShipWatchStationsTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	const FBoatConfig Ship = FBoatConfig::Make(EBoatType::Commonwealth);
	const FHullShape& H = Ship.Hulls[0];
	const int32 N = ShipWatchCount(Ship);
	const FWalkMap Map = ShipWatchTestsLocal::FlatShip(Ship, 4.1);
	for (int32 Pass = 0; Pass < 2; ++Pass)
	{
		const bool bMap = Pass == 1;
		TArray<FVector> Pelvis;
		for (int32 I = 0; I < N; ++I)
		{
			for (const int32 Wind : { 1, -1 })
			{
				FCrewPlaceInput Place;
				Place.Config = &Ship;
				Place.Index = I;
				Place.WindwardSide = Wind;
				Place.TrueWindAngle = 0.9 * Wind;
				Place.WalkMap = bMap ? &Map : nullptr;
				FCrewPlacement Pl;
				CrewPlacement(Place, Pl);
				const FString Who = FString::Printf(TEXT("figure %d%s, wind %s"), I, bMap ? TEXT(" (walk map)") : TEXT(""), Wind > 0 ? TEXT("starboard") : TEXT("port"));
				TestTrue(Who + TEXT(": standing"), Pl.Params.Stance == ECrewStance::Stand);
				TestTrue(Who + TEXT(": on her plan"), Pl.Pelvis.X > H.SternX && Pl.Pelvis.X < H.BowX && FMath::Abs(Pl.Pelvis.Y) < H.DeckHalfBeam(Pl.Pelvis.X) - 0.6);
				const double Floor = bMap ? 4.1 : CrewShipDeckZ(Ship, Pl.Pelvis.X);
				TestEqual(Who + TEXT(": the pelvis 93 cm over the deck"), Pl.Pelvis.Z, Floor + 0.93, 1e-6);
				TestEqual(Who + TEXT(": faces its station's way"), Pl.Yaw, Pl.Params.StandYaw, 1e-6f);
				TestEqual(Who + TEXT(": the facing yaw is the stance's"), CrewFacingYaw(Pl.Params), Pl.Yaw, 1e-6f);
				TestTrue(Who + TEXT(": the side is where they stand"), Pl.Params.Side == (Pl.Pelvis.Y >= 0.0 ? 1.f : -1.f));
				TestFalse(Who + TEXT(": not scripted"), Pl.bScripted);
				TestEqual(Who + TEXT(": the station keeps its side whatever the tack"), Pl.Pelvis.Y, Pelvis.IsValidIndex(I) ? Pelvis[I].Y : Pl.Pelvis.Y, 1e-9);
				if (Wind > 0) Pelvis.Add(Pl.Pelvis);
				TestTrue(Who + TEXT(": the last figure is the helm"), Pl.bHelm == (I == N - 1));
			}
		}
		for (int32 A = 0; A < Pelvis.Num(); ++A)
		{
			for (int32 B = A + 1; B < Pelvis.Num(); ++B)
			{
				TestTrue(FString::Printf(TEXT("figures %d and %d stand apart"), A, B), FVector::Dist2D(Pelvis[A], Pelvis[B]) > 0.6);
			}
		}
		// The helmsmen flank the wheel (the Helm spot with a map), the hands at the pin rails face inboard, the lookout is
		// well forward of the officer, who stands ahead of the wheel.
		TestEqual(TEXT("the helmsmen share the wheel's x"), Pelvis[N - 1].X, Pelvis[N - 2].X, 1e-9);
		TestTrue(TEXT("one either side of it"), Pelvis[N - 1].Y > 0.5 && Pelvis[N - 2].Y < -0.5);
		if (bMap) TestEqual(TEXT("at the walk map's Helm spot"), Pelvis[N - 1].X, -23.2, 1e-9);
		TestTrue(TEXT("the officer ahead of the wheel, to starboard"), Pelvis[5].X > Pelvis[N - 1].X + 2.0 && Pelvis[5].Y > 2.0);
		TestTrue(TEXT("the lookout far forward"), Pelvis[4].X > Pelvis[5].X + 20.0 && Pelvis[4].X > Ship.Square.MastX[0]);
		TestTrue(TEXT("hands at the fore and main pin rails, both sides"), Pelvis[0].Y < -3.0 && Pelvis[1].Y > 3.0 && Pelvis[2].Y < -3.0 && Pelvis[3].Y > 3.0
			&& FMath::Abs(Pelvis[0].X - Ship.Square.MastX[0]) < 3.0 && FMath::Abs(Pelvis[2].X - Ship.Square.MastX[1]) < 3.0);
		for (int32 I = 0; I < 4; ++I)
		{
			FCrewPlaceInput Place;
			Place.Config = &Ship;
			Place.Index = I;
			Place.WalkMap = bMap ? &Map : nullptr;
			FCrewPlacement Pl;
			CrewPlacement(Place, Pl);
			TestEqual(FString::Printf(TEXT("hand %d faces inboard"), I), Pl.Yaw, Pl.Pelvis.Y > 0.0 ? -90.f : 90.f, 1e-6f);
		}
	}
	// The stance itself: on the feet, the arms down; the officer's hands behind the back bring the elbows further round.
	FCrewPoseParams Stand;
	Stand.Stance = ECrewStance::Stand;
	Stand.StandYaw = 37.f;
	TMap<FName, FQuat> Joints, Officer;
	CrewJointRotations(Stand, Joints);
	TestTrue(TEXT("the stance poses the legs and arms"), Joints.Contains(TEXT("thigh_l")) && Joints.Contains(TEXT("calf_r")) && Joints.Contains(TEXT("upperarm_l")) && Joints.Contains(TEXT("lowerarm_r")));
	TestEqual(TEXT("faces the yaw given"), CrewFacingYaw(Stand), 37.f, 1e-6f);
	Stand.Hike = 1.f;
	CrewJointRotations(Stand, Officer);
	TestTrue(TEXT("the officer's arms differ from a hand's"), !Officer[TEXT("upperarm_l")].Equals(Joints[TEXT("upperarm_l")], 1e-4f));
	return true;
}

#endif
