#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/WorldSettings.h"
#include "AutoTrim.h"
#include "BoatModel.h"
#include "FixedStepper.h"
#include "LakeData.h"
#include "Logbook.h"
#include "Ocean.h"
#include "Replay.h"
#include "SailboatPawn.h"
#include "SailingSettings.h"
#include "Traffic.h"
#include "Waves.h"
#include "Wind.h"
#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include <memory>

#if WITH_DEV_AUTOMATION_TESTS

using namespace Sailing;

namespace
{
	constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	FOceanParams GulfSea(double SwellHs = 1.2)
	{
		FOceanParams P;
		P.WindMs = 12.0 * kKnot;
		P.WindFromRad = kPi;              // from the south
		P.SwellHs = SwellHs;
		P.SwellTp = 9.0;
		P.SwellFromRad = 135.0 * kDegToRad;
		return P;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FOceanSpectrumTest, "SailingSim.Physics.OceanSpectrum", Flags)
bool FOceanSpectrumTest::RunTest(const FString& Parameters)
{
	FOcean Ocean;
	Ocean.Configure(GulfSea());
	// Fully developed wind sea for 12 kn (Pierson-Moskowitz: 0.21 U^2 / g) plus the swell, added in energy.
	const double U = 12.0 * kKnot, WindHs = 0.21 * U * U / 9.81;
	const double Expected = FMath::Sqrt(WindHs * WindHs + 1.2 * 1.2);
	AddInfo(FString::Printf(TEXT("Hs %.2f m (wind sea %.2f, swell 1.20; expected %.2f), mean period %.1f s"), Ocean.SignificantHeight(), Ocean.WindSeaHs(), Expected, Ocean.MeanPeriod()));
	TestTrue(TEXT("Spectrum carries the significant height asked for"), FMath::Abs(Ocean.SignificantHeight() - Expected) < 0.02);
	// The surface itself: 4 x its standard deviation over a wide area.
	double Sum = 0.0, Sum2 = 0.0;
	int32 N = 0;
	for (int32 I = 0; I < 300; ++I)
		for (int32 J = 0; J < 300; ++J)
		{
			const double H = Ocean.Height(I * 3.7, J * 4.1, 20.0);
			Sum += H;
			Sum2 += H * H;
			++N;
		}
	const double Measured = 4.0 * FMath::Sqrt(Sum2 / N - FMath::Square(Sum / N));
	AddInfo(FString::Printf(TEXT("Measured on the surface: Hs %.2f m"), Measured));
	TestTrue(TEXT("The surface has that height (within 12%: bilinear sampling smooths the shortest waves)"), FMath::Abs(Measured - Expected) < 0.12 * Expected);
	// Vertical velocity and slope agree with the surface's own rates of change.
	double H0, Vz, Sx, Sy;
	Ocean.Sample(37.0, 51.0, 30.0, H0, Vz, Sx, Sy);
	const double DhDt = (Ocean.Height(37.0, 51.0, 30.001) - Ocean.Height(37.0, 51.0, 29.999)) / 0.002;
	AddInfo(FString::Printf(TEXT("Vertical velocity %.4f m/s, from the surface %.4f"), Vz, DhDt));
	TestTrue(TEXT("Vertical velocity matches dh/dt"), FMath::Abs(Vz - DhDt) < 0.02 + 0.05 * FMath::Abs(DhDt));
	// Deterministic: the same time gives the same sea.
	TestEqual(TEXT("Same time, same height"), Ocean.Height(100.0, 200.0, 55.5), Ocean.Height(100.0, 200.0, 55.5));

	// The mask on the Gulf passage: open sea offshore, none inside the barrier islands.
	FLakeData Gulf;
	if (TestTrue(TEXT("Gulf passage loads"), Gulf.Load(FLakeData::DefaultDirectory(), TEXT("GulfPassage"))))
	{
		Ocean.BuildMask(Gulf.Terrain);
		const double Offshore = Ocean.MaskAt(-31000.0, -5000.0), WestBay = Ocean.MaskAt(-12000.0, -25000.0), Inside = Ocean.MaskAt(3000.0, -6000.0);
		AddInfo(FString::Printf(TEXT("Mask: offshore %.2f, inside Bolivar Roads %.2f, West Bay %.2f"), Offshore, Inside, WestBay));
		TestTrue(TEXT("Full sea offshore"), Offshore > 0.95);
		// gulf-swell: the swell reaches through the entrance by the part of its spread the gap lets in.
		TestTrue(TEXT("No swell in West Bay, a reduced one inside the entrance"), WestBay < 0.05 && Inside < 0.6);
		TestTrue(TEXT("Gulf passage is an ocean area with a passage plan"), Gulf.bOcean && Gulf.Passage.Num() >= 4);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FGalvestonSwellTest, "SailingSim.Coast.GalvestonSwell", Flags)
bool FGalvestonSwellTest::RunTest(const FString& Parameters)
{
	// gulf-swell: the Galveston world carries the Gulf's ocean. Its mask is the open sea off the Seawall, falls through
	// Bolivar Roads into the bay (only the part of the swell's spread the jetties' gap lets in) and is nothing in Clear
	// Lake; the boat feels it only where the mask lets it in.
	FLakeData Bay;
	if (!TestTrue(TEXT("Galveston Bay loads"), Bay.Load(FLakeData::DefaultDirectory(), TEXT("GalvestonBay")))) return false;
	TestTrue(TEXT("Galveston Bay is an ocean area (the Gulf front)"), Bay.bOcean);
	FOceanParams Fair = GulfSea(0.9);   // the game's fair-weather swell (ASailingGameMode::UpdateOcean)
	std::shared_ptr<FOcean> Ocean = std::make_shared<FOcean>();
	Ocean->Configure(Fair);
	const double BuildStart = FPlatformTime::Seconds();
	Ocean->BuildMask(Bay.Terrain);
	const double BuildMs = (FPlatformTime::Seconds() - BuildStart) * 1000.0;
	struct FPoint { const TCHAR* Name; double X, Y; };
	const FPoint Seawall = { TEXT("1 km off the Seawall"), -29700.0, 23000.0 }, Pier = { TEXT("Pleasure Pier end"), -29000.0, 22350.0 },
		Mouth = { TEXT("between the jetty heads"), -24800.0, 31500.0 }, Roads = { TEXT("Bolivar Roads"), -20990.0, 24210.0 },
		Dike = { TEXT("Texas City Dike"), -16020.0, 15460.0 }, ClearLake = { TEXT("Clear Lake"), 430.0, -4410.0 };
	for (const FPoint& Pt : { Seawall, Pier, Mouth, Roads, Dike, ClearLake })
	{
		AddInfo(FString::Printf(TEXT("%s: mask %.2f"), Pt.Name, Ocean->MaskAt(Pt.X, Pt.Y)));
	}
	AddInfo(FString::Printf(TEXT("Mask built in %.0f ms"), BuildMs));
	TestTrue(TEXT("Full sea off the Seawall"), Ocean->MaskAt(Seawall.X, Seawall.Y) > 0.95);
	TestTrue(TEXT("Full sea at the Pleasure Pier"), Ocean->MaskAt(Pier.X, Pier.Y) > 0.9);
	TestTrue(TEXT("Full sea between the jetty heads"), Ocean->MaskAt(Mouth.X, Mouth.Y) > 0.9);
	TestTrue(TEXT("Falls inside Bolivar Roads (some, but well under the open sea)"), Ocean->MaskAt(Roads.X, Roads.Y) > 0.05 && Ocean->MaskAt(Roads.X, Roads.Y) < 0.6);
	TestTrue(TEXT("Next to nothing at the Texas City Dike"), Ocean->MaskAt(Dike.X, Dike.Y) < 0.1);
	TestEqual(TEXT("None in Clear Lake"), Ocean->MaskAt(ClearLake.X, ClearLake.Y), 0.0);
	TestTrue(TEXT("Mask builds fast enough for the game thread (under 0.5 s)"), BuildMs < 500.0);

	// Felt where it reaches: the sea height and the added resistance follow the mask.
	FWaveField Waves(3);
	Waves.SetOcean(Ocean);
	const double Chop = FWaveField(3).SignificantHeight();
	TestTrue(TEXT("Clear Lake's sea is the chop alone"), FMath::Abs(Waves.SignificantHeightAt(ClearLake.X, ClearLake.Y) - Chop) < 1e-9);
	TestTrue(TEXT("Off the Seawall the sea carries the swell"), Waves.SignificantHeightAt(Seawall.X, Seawall.Y) > 0.95 * Ocean->SignificantHeight());
	auto Sail = [&](const FPoint& At, bool bOcean)
	{
		FWindParams P;
		P.SpeedKnots = 12.0;
		P.FromDegrees = 140.0;   // close-hauled (TWA 50) heading east
		const FWindField Wind(P);
		FWaveField Sea(3);
		if (bOcean) Sea.SetOcean(Ocean);
		FBoatModel Boat;
		Boat.Reset(At.X, At.Y, 90.0 * kDegToRad, 3.0);
		FBoatControls C;
		FAutoTrim Trim;
		FAutopilot Pilot;
		Pilot.TargetTWADeg = 50.0;
		double Speed = 0.0;
		int32 N = 0;
		for (int32 I = 0; I < int32(90.0 * PhysicsHz); ++I)
		{
			C = Trim.Update(Boat, C, PhysicsDt);
			C.Tiller = Pilot.Update(Boat);
			Boat.Step(PhysicsDt, C, Wind, &Sea);
			if (I > int32(45.0 * PhysicsHz)) { Speed += Boat.GetTelemetry().BoatSpeed; ++N; }
		}
		return Speed / N / kKnot;
	};
	const double LakeFlat = Sail(ClearLake, false), LakeOcean = Sail(ClearLake, true);
	const double GulfFlat = Sail(Seawall, false), GulfOcean = Sail(Seawall, true);
	AddInfo(FString::Printf(TEXT("Close-hauled: Clear Lake %.2f kn without the ocean, %.2f with; off the Seawall %.2f without, %.2f with"),
		LakeFlat, LakeOcean, GulfFlat, GulfOcean));
	TestTrue(TEXT("In Clear Lake the ocean changes nothing"), FMath::Abs(LakeOcean - LakeFlat) < 1e-6);
	TestTrue(TEXT("Off the Seawall the swell slows her upwind"), GulfOcean < 0.97 * GulfFlat);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FOceanAddedResistanceTest, "SailingSim.Physics.AddedResistanceInWaves", Flags)
bool FOceanAddedResistanceTest::RunTest(const FString& Parameters)
{
	// A J/22 in 12 kn: flat water, then a 1.5 m Gulf sea (wind sea and swell). Upwind she pitches into it and slows
	// noticeably; reaching and running she barely notices (long waves are ridden over, not pushed through).
	auto Sail = [](double TwaDeg, bool bSea)
	{
		FWindParams P;
		P.SpeedKnots = 12.0;
		P.FromDegrees = 180.0;
		const FWindField Wind(P);
		FWaveField Waves(3);
		if (bSea)
		{
			std::shared_ptr<FOcean> Ocean = std::make_shared<FOcean>();
			Ocean->Configure(GulfSea());
			Waves.SetOcean(Ocean);
		}
		FBoatModel Boat;
		Boat.Reset(0.0, 0.0, (180.0 - TwaDeg) * kDegToRad, 3.0);
		FBoatControls C;
		FAutoTrim Trim;
		FAutopilot Pilot;
		Pilot.TargetTWADeg = TwaDeg;
		double Speed = 0.0;
		int32 N = 0;
		for (int32 I = 0; I < int32(180.0 * PhysicsHz); ++I)
		{
			C = Trim.Update(Boat, C, PhysicsDt);
			C.Tiller = Pilot.Update(Boat);
			Boat.Step(PhysicsDt, C, Wind, &Waves);
			if (I > int32(60.0 * PhysicsHz)) { Speed += Boat.GetTelemetry().BoatSpeed; ++N; }
		}
		return Speed / N / kKnot;
	};
	for (const double Twa : { 50.0, 90.0, 140.0 })
	{
		const double Flat = Sail(Twa, false), Sea = Sail(Twa, true);
		const double Loss = 1.0 - Sea / Flat;
		AddInfo(FString::Printf(TEXT("TWA %.0f: %.2f kn flat, %.2f kn in the sea (%.0f%% slower)"), Twa, Flat, Sea, Loss * 100.0));
		// A 22-footer close-hauled in a short 1.5 m sea loses a quarter to a third of her speed (Gerritsma-Beukelman added
		// resistance; since Phase 8 the rudder also carries weather helm through it).
		if (Twa < 60.0) TestTrue(TEXT("Upwind in a 1.5 m sea: 10 to 35% slower"), Loss > 0.10 && Loss < 0.35);
		else TestTrue(FString::Printf(TEXT("TWA %.0f: under 10%% slower"), Twa), Loss < 0.10);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FOceanLongPassageTest, "SailingSim.Coast.LongPassageStable", Flags)
bool FOceanLongPassageTest::RunTest(const FString& Parameters)
{
	// A J/22 sets out on the Gulf passage plan (Galveston entrance, sea buoy, along the beach toward Freeport) with the
	// AI helmsman, in the open sea, for ninety minutes: she must stay upright, afloat, off the bottom and keep making
	// way down the plan, with nothing in the simulation running away (no NaN, bounded motion).
	FLakeData Gulf;
	if (!TestTrue(TEXT("Gulf passage loads"), Gulf.Load(FLakeData::DefaultDirectory(), TEXT("GulfPassage")))) return false;
	FWindParams P;
	P.SpeedKnots = 12.0;
	P.FromDegrees = 150.0;
	P.GustIntensity = 0.15;
	P.ShiftDegrees = 6.0;
	const FWindField Wind(P);
	FWaveField Waves(5);
	std::shared_ptr<FOcean> Ocean = std::make_shared<FOcean>();
	Ocean->Configure(GulfSea(1.0));
	Ocean->BuildMask(Gulf.Terrain);
	Waves.SetOcean(Ocean);
	FTrafficSim Sim;
	Sim.SetWorld(&Wind, &Waves, &Gulf.Terrain);
	std::vector<std::pair<double, double>> Route;
	for (const TPair<FString, FVector2D>& W : Gulf.Passage) Route.push_back({ W.Value.X, W.Value.Y });
	const FVector2D Start = Gulf.Passage[0].Value;
	const int32 Id = Sim.AddSailboat(EBoatType::J22, Start.X, Start.Y, FMath::Atan2(Route[1].second - Start.Y, Route[1].first - Start.X), Route, "Passage J/22");
	Sim.Find(Id)->bLoopRoute = false;
	Sim.Find(Id)->RouteIndex = 1;
	double MaxHeel = 0.0, LogNm = 0.0;
	int32 Aground = 0, Capsized = 0;
	bool bFinite = true;
	const double Minutes = 90.0;
	for (int32 Frame = 0; Frame < int32(Minutes * 60.0 * 10.0); ++Frame)
	{
		Sim.Step(0.1);
		const FTrafficVessel* V = Sim.Find(Id);
		const FBoatTelemetry& T = V->Boat->GetTelemetry();
		LogNm += FMath::Max(0.0, T.SpeedThroughWater) * 0.1 / 1852.0;
		MaxHeel = FMath::Max(MaxHeel, FMath::Abs(T.Heel));
		Aground += T.bAground;
		Capsized += T.bCapsized;
		const Vec3 Pos = V->Boat->GetState().Position;
		if (!FMath::IsFinite(Pos.X) || !FMath::IsFinite(Pos.Y) || !FMath::IsFinite(Pos.Z)) { bFinite = false; break; }
	}
	const FTrafficVessel* V = Sim.Find(Id);
	AddInfo(FString::Printf(TEXT("%.0f minutes: %.1f nm by the log, waypoint %d of %d reached, max heel %.0f deg, aground %d samples, capsized %d"),
		Minutes, LogNm, int32(V->RouteIndex), int32(Route.size()), FMath::RadiansToDegrees(MaxHeel), Aground, Capsized));
	TestTrue(TEXT("Physics stays finite"), bFinite);
	TestEqual(TEXT("Never capsized"), Capsized, 0);
	TestEqual(TEXT("Never aground"), Aground, 0);
	TestTrue(TEXT("Heel stays within a knockdown (under 50 degrees)"), MaxHeel < FMath::DegreesToRadians(50.0));
	TestTrue(TEXT("Makes her way down the plan (6 nm or more by the log)"), LogNm > 6.0);
	TestTrue(TEXT("Passes the sea buoy and on toward the next mark"), V->RouteIndex >= 2);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReplayTest, "SailingSim.Smoke.ReplayRecordsAndPlays", Flags)
bool FReplayTest::RunTest(const FString& Parameters)
{
	// Record a minute of sailing, then draw it back: the replayed boat is where the real one was.
	FWindParams P;
	P.SpeedKnots = 12.0;
	const FWindField Wind(P);
	FBoatModel Boat;
	Boat.Reset(0.0, 0.0, 1.2, 3.0);
	FBoatControls C;
	FAutoTrim Trim;
	FAutopilot Pilot;
	Pilot.TargetTWADeg = 70.0;
	FReplay Run;
	Run.Begin(int32(EBoatType::J22), TEXT("Test"), Boat.GetState().Time);
	FBoatState At30;
	for (int32 I = 0; I < int32(60.0 * PhysicsHz); ++I)
	{
		C = Trim.Update(Boat, C, PhysicsDt);
		C.Tiller = Pilot.Update(Boat);
		Boat.Step(PhysicsDt, C, Wind);
		Run.Record(Boat);
		if (I == int32(30.0 * PhysicsHz)) At30 = Boat.GetState();
	}
	AddInfo(FString::Printf(TEXT("%d frames over %.1f s"), Run.Frames.Num(), Run.Duration()));
	TestTrue(TEXT("Ten frames a second"), FMath::Abs(Run.Frames.Num() - 600) <= 2);
	FReplayFrame F;
	TestTrue(TEXT("A moment in the run samples"), Run.Sample(At30.Time - Run.StartTime, F));
	const double Off = (F.State.Position - At30.Position).Length();
	AddInfo(FString::Printf(TEXT("At 30 s the replay is %.3f m from where she was"), Off));
	TestTrue(TEXT("The replay is where she was (within 5 cm)"), Off < 0.05);
	FBoatModel Ghost;
	FReplay::Apply(F, Ghost);
	TestTrue(TEXT("A ghost model takes the frame"), (Ghost.GetState().Position - F.State.Position).Length() < 1e-6 && Ghost.GetTelemetry().NumMainStrips == Boat.GetTelemetry().NumMainStrips);
	TestFalse(TEXT("No frame past the end"), Run.Sample(Run.Duration() + 1.0, F));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLogbookTest, "SailingSim.Smoke.LogbookWritesEntries", Flags)
bool FLogbookTest::RunTest(const FString& Parameters)
{
	FLogbook Log;
	Log.Begin(TEXT("Test water"), TEXT("J/22"), 1792000000.0, TEXT("10:00"));
	for (int32 I = 0; I < 3; ++I)
	{
		FLogEntry E;
		E.UnixTime = 1792000000.0 + I * 1800.0;
		E.Kind = I == 1 ? TEXT("Event") : TEXT("Watch");
		E.Latitude = 29.5446;
		E.Longitude = -95.0193;
		E.SpeedKnots = 5.0 + I;
		E.Remarks = I == 1 ? TEXT("Fix by bearings") : TEXT("");
		Log.Add(E);
	}
	FString Json;
	TSharedPtr<FJsonObject> Root;
	TestTrue(TEXT("The log file is written"), FFileHelper::LoadFileToString(Json, *Log.GetFilePath()) && FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json), Root) && Root.IsValid());
	if (Root.IsValid()) TestEqual(TEXT("All three entries saved"), Root->GetArrayField(TEXT("entries")).Num(), 3);
	TestEqual(TEXT("Best speed"), Log.MaxSpeedKnots, 7.0);
	const FString Pos = FLogbook::FormatPosition(29.5446, -95.0193);
	AddInfo(Pos);
	TestTrue(TEXT("Position written in degrees and minutes"), Pos.Contains(TEXT("29")) && Pos.Contains(TEXT("32.68'N")) && Pos.Contains(TEXT("01.16'W")));
	IFileManager::Get().Delete(*Log.GetFilePath());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FKeyRebindTest, "SailingSim.Smoke.KeyRebinding", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FKeyRebindTest::RunTest(const FString& Parameters)
{
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, TEXT("SailingKeysWorld"));
	FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
	Context.SetCurrentWorld(World);
	World->InitializeActorsForPlay(FURL());
	World->GetWorldSettings()->NotifyBeginPlay();
	ASailboatPawn* Boat = World->SpawnActor<ASailboatPawn>(FVector::ZeroVector, FRotator::ZeroRotator);
	USailingInputSettings* Settings = GetMutableDefault<USailingInputSettings>();
	const TArray<FSailingKeyBinding> Saved = Settings->Bindings;
	auto KeyOf = [&](FName Action, bool bNeg)
	{
		for (const FSailingKeyBinding& B : Settings->GetBindings())
			if (B.Action == Action && (B.Scale < 0.f) == bNeg && !B.Key.IsGamepadKey() && !B.Key.IsMouseButton() && !B.Key.IsAxis1D() && !B.Key.IsAxis2D()) return B.Key;
		return FKey();
	};
	if (TestNotNull(TEXT("Boat spawns"), Boat))
	{
		// Board up/down to K: K was difficulty, so difficulty takes J.
		TestTrue(TEXT("Rebind the board"), Boat->Rebind(TEXT("Board"), false, EKeys::K));
		TestEqual(TEXT("Board is on K"), KeyOf(TEXT("Board"), false), EKeys::K);
		TestEqual(TEXT("Difficulty took the board's old key (J)"), KeyOf(TEXT("ToggleDifficulty"), false), EKeys::J);
		// Steering to port moves to the left arrow's partner: Q (the jib sheet's ease, which swaps to A).
		TestTrue(TEXT("Rebind steering to port"), Boat->Rebind(TEXT("Tiller"), true, EKeys::Q));
		TestEqual(TEXT("Steer to port on Q"), KeyOf(TEXT("Tiller"), true), EKeys::Q);
		TestEqual(TEXT("Jib ease took A"), KeyOf(TEXT("JibSheet"), false), EKeys::A);
		TestFalse(TEXT("No such command"), Boat->Rebind(TEXT("Teleport"), false, EKeys::F1));
		Boat->Destroy();
	}
	// Leave the player's keys as they were.
	Settings->Bindings = Saved;
	Settings->SaveConfig();
	GEngine->DestroyWorldContext(World);
	World->DestroyWorld(false);
	return true;
}

#endif
