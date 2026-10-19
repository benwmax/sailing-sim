#include "Misc/AutomationTest.h"
#include "LakeData.h"
#include "Lights.h"
#include "SailingGameMode.h"

#if WITH_DEV_AUTOMATION_TESTS

// world-marseille: the first port baked from a box and a name (Tools/coast/worlds/Marseille.json, docs/world-marseille):
// OpenStreetMap coastline and seamarks, EMODnet depths, NGA Pub 113 lights, Copernicus land, no tide model.

using namespace Sailing;

namespace
{
	constexpr EAutomationTestFlags MarseilleFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	const FLakeData& Marseille()
	{
		static FLakeData Lake;
		static bool bLoaded = Lake.Load(FLakeData::DefaultDirectory(), TEXT("Marseille"));
		return Lake;
	}

	const FNavaid* FindMarseilleAid(const FLakeData& Lake, const TCHAR* Name)
	{
		return Lake.Navaids.FindByPredicate([&](const FNavaid& N) { return N.Name.Contains(Name); });
	}
}

/** The bake loads as a coast without tides: chart, IALA A, the spots by role in the water, the clock in Paris time. */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMarseilleLoadsTest, "SailingSim.Coast.MarseilleLoads", MarseilleFlags)
bool FMarseilleLoadsTest::RunTest(const FString& Parameters)
{
	const FLakeData& Lake = Marseille();
	if (!TestTrue(TEXT("Marseille loads"), Lake.IsLoaded())) return false;
	TestTrue(TEXT("A coast"), Lake.IsCoast());
	TestFalse(TEXT("No tide model (the Mediterranean's range is under 0.3 m)"), Lake.IsTidal());
	TestTrue(TEXT("Open sea"), Lake.bOcean);
	TestEqual(TEXT("IALA region A"), Lake.Iala, TCHAR('A'));
	TestEqual(TEXT("Central European time"), Lake.TimeZone, FString(TEXT("Europe/Paris")));
	TestTrue(TEXT("Swell from the south-southwest"), FMath::IsFinite(Lake.SwellFromDeg) && Lake.SwellFromDeg > 180.0 && Lake.SwellFromDeg < 240.0);
	TestTrue(TEXT("Variation about 2.8 E"), FMath::Abs(Lake.VariationDeg - 2.83) < 0.2);
	TestTrue(TEXT("The anchor is the Vieux-Port entrance"), Lake.Anchor.bValid && FMath::Abs(Lake.Anchor.Lat0Deg - 43.295) < 1e-6);
	for (const TCHAR* Role : { TEXT("home_slip"), TEXT("anchorage"), TEXT("gale") })
	{
		const int32* I = Lake.SpotRoles.Find(Role);
		if (!TestTrue(FString::Printf(TEXT("A %s spot"), Role), I != nullptr && Lake.LaunchSpots.IsValidIndex(*I))) continue;
		const FLaunchSpot& S = Lake.LaunchSpots[*I];
		const double Depth = -Lake.Terrain.HeightAt(S.X, S.Y);
		AddInfo(FString::Printf(TEXT("%s: %s, %.1f m of water"), Role, *S.Name, Depth));
		TestTrue(FString::Printf(TEXT("%s is afloat"), *S.Name), Depth > 1.5);
	}
	TestTrue(TEXT("The gale spot is offshore in deep water"), Lake.SpotRoles.Contains(TEXT("gale")) && -Lake.Terrain.HeightAt(
		Lake.LaunchSpots[Lake.SpotRoles[TEXT("gale")]].X, Lake.LaunchSpots[Lake.SpotRoles[TEXT("gale")]].Y) > 40.0);
	TestTrue(TEXT("The passage runs Vieux-Port to Cassis"), Lake.Passage.Num() >= 5 && Lake.Passage.Last().Key.Contains(TEXT("Cassis")));
	TestEqual(TEXT("Summer time on 19 October 2026"), ASailingGameMode::CentralEuropeanOffsetHours(FDateTime(2026, 10, 19)), 2);
	TestEqual(TEXT("Winter time from 25 October 2026"), ASailingGameMode::CentralEuropeanOffsetHours(FDateTime(2026, 10, 25)), 1);
	TestEqual(TEXT("Winter time in January"), ASailingGameMode::CentralEuropeanOffsetHours(FDateTime(2026, 1, 15)), 1);
	TestEqual(TEXT("Summer time from 29 March 2026"), ASailingGameMode::CentralEuropeanOffsetHours(FDateTime(2026, 3, 29)), 2);
	TestEqual(TEXT("World 3 is Marseille"), FString(ASailingGameMode::WorldFileName(ASailingGameMode::WorldIndexFromName(TEXT("Marseille")))), FString(TEXT("Marseille")));
	return true;
}

/** The water's edge falls on the OSM coastline, and the sea bed has no seams where its sources meet. */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMarseilleShoreTest, "SailingSim.Coast.MarseilleShoreAndSeams", MarseilleFlags)
bool FMarseilleShoreTest::RunTest(const FString& Parameters)
{
	const FLakeData& Lake = Marseille();
	if (!TestTrue(TEXT("Marseille loads"), Lake.IsLoaded())) return false;
	TestTrue(TEXT("Four shoreline checkpoints"), Lake.Checkpoints.Num() >= 4);
	const double Mhw = Lake.MeanHighWater;
	for (const TPair<FString, FVector2D>& Cp : Lake.Checkpoints)
	{
		// From the OSM coastline's nearest point to the terrain's mean-high-water contour (the bake puts it on the line).
		double Best = 1e9;
		for (int32 A = 0; A < 72; ++A)
		{
			const double Ang = A * 5.0 * kDegToRad;
			double Prev = Lake.Terrain.HeightAt(Cp.Value.X, Cp.Value.Y) - Mhw;
			for (double D = 0.25; D <= 30.0; D += 0.25)
			{
				const double H = Lake.Terrain.HeightAt(Cp.Value.X + FMath::Cos(Ang) * D, Cp.Value.Y + FMath::Sin(Ang) * D) - Mhw;
				if ((H < 0.0) != (Prev < 0.0)) { Best = FMath::Min(Best, D - 0.125); break; }
				Prev = H;
			}
		}
		AddInfo(FString::Printf(TEXT("%s: the water's edge %.1f m from the OSM coastline"), *Cp.Key, Best));
		TestTrue(FString::Printf(TEXT("%s: shoreline within 6 m of the OSM line (10 m grid)"), *Cp.Key), Best <= 6.0);
	}
	// Seams: away from the shore (where the Calanques' cliffs drop 10 m in a cell) neighbouring cells never step more
	// than the steepest real slope off the islands, and steps over 5 m are rare.
	const int32 Rows = Lake.Terrain.GetRows(), Cols = Lake.Terrain.GetCols();
	auto Open = [&](int32 R, int32 C)
	{
		for (int32 Dr = -3; Dr <= 3; ++Dr)
			for (int32 Dc = -3; Dc <= 3; ++Dc)
				if (Lake.Terrain.NodeHeight(FMath::Clamp(R + Dr, 0, Rows - 1), FMath::Clamp(C + Dc, 0, Cols - 1)) >= 0.0) return false;
		return true;
	};
	double Worst = 0.0;
	int32 Pairs = 0, Big = 0;
	double Deepest = 0.0;
	for (int32 R = 3; R < Rows - 4; R += 2)
	{
		for (int32 C = 3; C < Cols - 4; C += 2)
		{
			const double H = Lake.Terrain.NodeHeight(R, C);
			Deepest = FMath::Min(Deepest, H);
			if (H >= 0.0 || !Open(R, C)) continue;
			for (const FIntPoint& D : { FIntPoint(1, 0), FIntPoint(0, 1) })
			{
				const double Step = FMath::Abs(Lake.Terrain.NodeHeight(R + D.X, C + D.Y) - H);
				Worst = FMath::Max(Worst, Step);
				Big += Step > 5.0;
				++Pairs;
			}
		}
	}
	AddInfo(FString::Printf(TEXT("Open water: %d neighbour pairs, largest step %.1f m, %d over 5 m; deepest %.0f m"), Pairs, Worst, Big, -Deepest));
	TestTrue(TEXT("No step over 20 m in open water"), Worst < 20.0);
	TestTrue(TEXT("Steps over 5 m under one in ten thousand"), Big * 10000 < Pairs);
	TestTrue(TEXT("The Planier shelf reaches past 100 m"), Deepest < -100.0);
	TestTrue(TEXT("The Vieux-Port is dredged (5 m and more)"), -Lake.Terrain.HeightAt(Lake.LaunchSpots[0].X, Lake.LaunchSpots[0].Y) >= 5.0);
	return true;
}

/** The lights flash their Pub 113 characters, and the lateral marks wear region A's colours. */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMarseilleLightsTest, "SailingSim.Coast.MarseilleLights", MarseilleFlags)
bool FMarseilleLightsTest::RunTest(const FString& Parameters)
{
	const FLakeData& Lake = Marseille();
	if (!TestTrue(TEXT("Marseille loads"), Lake.IsLoaded())) return false;
	struct FCase { const TCHAR* Name; const char* Label; };
	const FCase Cases[] = {
		{ TEXT("Planier"), "Fl W 5s" },               // NGA 6688, E0680
		{ TEXT("Chateau d'If"), "Fl(2) W 6s" },       // NGA 6660, E0676
		{ TEXT("Desirade"), "Fl G 4s" },              // the Pharo, NGA 6628
		{ TEXT("Sourdaras"), "Q(9) W 15s" },          // the west cardinal off If
	};
	for (const FCase& C : Cases)
	{
		const FNavaid* N = FindMarseilleAid(Lake, C.Name);
		if (!TestTrue(FString::Printf(TEXT("%s is charted and lit"), C.Name), N != nullptr && N->bLit)) continue;
		// The label carries the height and range after the character ("Fl W 5s 223ft 23M").
		const FString Label(UTF8_TO_TCHAR(N->Light.Label().c_str()));
		AddInfo(FString::Printf(TEXT("%s: %s"), *N->Name, *Label));
		TestTrue(FString::Printf(TEXT("%s shows %hs"), C.Name, C.Label), Label == UTF8_TO_TCHAR(C.Label) || Label.StartsWith(FString(UTF8_TO_TCHAR(C.Label)) + TEXT(" ")));
	}
	int32 Lit = 0, Ok = 0, Lateral = 0, RegionA = 0;
	for (const FNavaid& N : Lake.Navaids)
	{
		if (N.CatLam == 1 || N.CatLam == 2)
		{
			++Lateral;
			// IALA A: port hand red (3), starboard hand green (4).
			RegionA += N.Colours.Num() > 0 && N.Colours[0] == (N.CatLam == 1 ? 3 : 4);
		}
		if (!N.bLit) continue;
		++Lit;
		Ok += N.Light.Period <= 0.0 || FMath::Abs(N.Light.CycleLength() - N.Light.Period) < 1e-6;
	}
	AddInfo(FString::Printf(TEXT("%d aids, %d lit, %d lateral"), Lake.Navaids.Num(), Lit, Lateral));
	TestTrue(TEXT("Over 40 lit aids"), Lit > 40);
	TestEqual(TEXT("Every lit aid's rhythm fits its period"), Ok, Lit);
	TestEqual(TEXT("Every lateral mark is region A's colour"), RegionA, Lateral);
	return true;
}

/** Moored boats float: none on land, none where the water is shallower than her draft; the harbours are full. */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMarseilleMooredBoatsTest, "SailingSim.Coast.MarseilleMooredBoatsAfloat", MarseilleFlags)
bool FMarseilleMooredBoatsTest::RunTest(const FString& Parameters)
{
	const FLakeData& Lake = Marseille();
	if (!TestTrue(TEXT("Marseille loads"), Lake.IsLoaded())) return false;
	int32 OnLand = 0, Aground = 0, VieuxPort = 0, Frioul = 0;
	for (const FMooredBoat& B : Lake.MooredBoats)
	{
		const double Ground = Lake.Terrain.HeightAt(B.Center.X, B.Center.Y);
		const double Draft = B.bMast ? 0.3 + 0.13 * B.Length : 0.2 + 0.07 * B.Length;   // osm_harbour.draft_m
		if (Ground > 0.0 && OnLand++ < 3) AddInfo(FString::Printf(TEXT("On land: %.0f, %.0f (%.2f m)"), B.Center.X, B.Center.Y, Ground));
		if (Ground > -Draft && Aground++ < 3) AddInfo(FString::Printf(TEXT("Aground: %.0f, %.0f (%.2f m under a %.1f m draft)"), B.Center.X, B.Center.Y, -Ground, Draft));
		VieuxPort += B.Marina == 0;
		Frioul += B.Marina == 2;
	}
	AddInfo(FString::Printf(TEXT("%d moored boats: %d in the Vieux-Port, %d at Frioul"), Lake.MooredBoats.Num(), VieuxPort, Frioul));
	TestTrue(TEXT("Over 2,500 moored boats"), Lake.MooredBoats.Num() > 2500);
	TestTrue(TEXT("The Vieux-Port holds over 1,000"), VieuxPort > 1000);
	TestTrue(TEXT("Port du Frioul has boats"), Frioul > 100);
	TestEqual(TEXT("No moored boat on land"), OnLand, 0);
	TestEqual(TEXT("None aground"), Aground, 0);
	TestTrue(TEXT("The pontoons became floating docks"), Lake.Docks.FilterByPredicate([](const FLakeDock& D) { return D.Kind == TEXT("floating"); }).Num() > 100);
	TestTrue(TEXT("The breakwaters carry crest and width"), Lake.Docks.ContainsByPredicate([](const FLakeDock& D) { return D.Kind == TEXT("breakwater") && D.Width > 5.f && D.Crest > 2.f; }));
	return true;
}

#endif
