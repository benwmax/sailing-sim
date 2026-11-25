#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "LakeData.h"
#include "Wildlife.h"

#if WITH_DEV_AUTOMATION_TESTS

using namespace Sailing;

// Wildlife Phase 1 (docs/wildlife-1/README.md): the distant birds' logic, on the worlds' tables and a made-up round lake.
// scripts/wildlife-check.sh runs the same on every world's real terrain.
namespace WildlifeTestsLocal
{
	constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;
	constexpr double LakeR = 3000.0;   // the made-up lake's shore

	/** A round lake of radius 3 km round the origin: 7 m deep in the middle, shoaling to the shore, land climbing 0.2 m a metre. */
	FWildlifeWorld RoundLake()
	{
		FWildlifeWorld W;
		W.HeightAt = [](double N, double E)
		{
			const double R = FMath::Sqrt(N * N + E * E);
			return R < LakeR ? -(0.3 + 6.7 * (1.0 - R / LakeR)) : (R - LakeR) * 0.2;
		};
		return W;
	}

	/** A table in build_tables.py's shape with the given bird rows (JSON objects). */
	FString TableJson(const TArray<FString>& Rows)
	{
		return FString::Printf(TEXT("{\"world\": \"Test\", \"water\": \"fresh\", \"box\": [-96.6, 32.8, -96.5, 32.9], \"species\": [%s]}"),
			*FString::Join(Rows, TEXT(",")));
	}
	FString Bird(const TCHAR* Id, const TCHAR* Style, const TCHAR* Habitats, int32 Typical, int32 P90, double FlushM = 0.0)
	{
		return FString::Printf(TEXT("{\"id\": \"%s\", \"name\": \"%s\", \"kind\": \"bird\", \"style\": \"%s\", \"size_m\": 1.2, \"flush_m\": %g, ")
			TEXT("\"months\": [1,1,1,1,1,1,1,1,1,1,1,1], \"habitats\": [%s], \"activity\": \"day\", \"group\": {\"typical\": %d, \"p90\": %d}, ")
			TEXT("\"water\": \"any\"}"), Id, Id, Style, FlushM, Habitats, Typical, P90);
	}
	bool LoadTable(const FString& Json, FWildlifeTable& Out, FAutomationTestBase& Test)
	{
		std::string Err;
		const bool bOk = Out.LoadText(TCHAR_TO_UTF8(*Json), &Err);
		if (!bOk) Test.AddError(FString::Printf(TEXT("table: %s"), UTF8_TO_TCHAR(Err.c_str())));
		return bOk;
	}
	FWildlifeConditions Noon(int32 Month = 6)
	{
		FWildlifeConditions C;
		C.Month = Month;
		C.LocalHour = 12.0;
		C.SunElevationDeg = 60.0;
		C.WindKn = 8.0;
		return C;
	}
	FBirdObservers At(double N, double E, double HeadingRad = 0.0, double SpeedMs = 0.0)
	{
		FBirdObservers O;
		O.CamNorth = N; O.CamEast = E; O.CamUp = 3.0;
		FBirdObservers::FBoat B;
		B.North = N; B.East = E; B.HeadingRad = HeadingRad; B.SpeedMs = SpeedMs; B.bPlayer = true;
		O.Boats.push_back(B);
		return O;
	}
	bool Airborne(const FBirdDraw& D)
	{
		return D.State != EBirdState::OnWater && D.State != EBirdState::Standing && D.State != EBirdState::Diving &&
			D.State != EBirdState::Landing && D.State != EBirdState::TakingOff;
	}
}

// Every world's table loads, has birds with seasons and groups, and keeps sea birds off the lake.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingWildlifeTablesTest, "SailingSim.Wildlife.Tables", WildlifeTestsLocal::Flags)
bool FSailingWildlifeTablesTest::RunTest(const FString&)
{
	for (const TCHAR* World : { TEXT("RayHubbard"), TEXT("GalvestonBay"), TEXT("GulfPassage"), TEXT("Marseille"), TEXT("TexasCoast") })
	{
		FString Text;
		if (!TestTrue(FString::Printf(TEXT("%s.wildlife.json is staged"), World),
			FFileHelper::LoadFileToString(Text, *(FLakeData::DefaultDirectory() / FString(World) + TEXT(".wildlife.json"))))) continue;
		FWildlifeTable T;
		if (!WildlifeTestsLocal::LoadTable(Text, T, *this)) continue;
		TestTrue(FString::Printf(TEXT("%s has birds"), World), T.Birds.size() >= 5);
		TestTrue(FString::Printf(TEXT("%s has other animals for later phases"), World), T.OtherAnimals > 0);
		for (const FWildBird& B : T.Birds)
		{
			double Sum = 0.0;
			for (double M : B.Months) Sum += M;
			TestTrue(FString::Printf(TEXT("%s %s is about some months"), World, UTF8_TO_TCHAR(B.Id.c_str())), Sum > 0.0);
			TestTrue(FString::Printf(TEXT("%s %s has a group size"), World, UTF8_TO_TCHAR(B.Id.c_str())), B.GroupTypical >= 1 && B.GroupP90 >= B.GroupTypical);
			TestTrue(FString::Printf(TEXT("%s %s has a wingspan"), World, UTF8_TO_TCHAR(B.Id.c_str())), B.SizeM > 0.1 && B.SizeM < 3.0);
			bool bListed = false;
			BirdLookFor(B.Id, B.Style, &bListed);
			TestTrue(FString::Printf(TEXT("%s %s has its own plumage (BirdLookFor)"), World, UTF8_TO_TCHAR(B.Id.c_str())), bListed);
			if (FString(World) == TEXT("RayHubbard"))
				TestFalse(FString::Printf(TEXT("no salt-water bird on the lake (%s)"), UTF8_TO_TCHAR(B.Id.c_str())), B.Water == "salt");
		}
	}
	return true;
}

// The habitat map tells open water, the channel, offshore water, shallows, the shore and cliffs apart.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingWildlifeHabitatsTest, "SailingSim.Wildlife.Habitats", WildlifeTestsLocal::Flags)
bool FSailingWildlifeHabitatsTest::RunTest(const FString&)
{
	using namespace WildlifeTestsLocal;
	FWildlifeHabitatMap Map;
	Map.Build(RoundLake(), 0.0, 0.0, 4000.0, 50.0);
	TestTrue(TEXT("built"), Map.IsBuilt());
	const uint32 Middle = Map.BitsAt(0.0, 0.0);
	TestTrue(TEXT("the middle is open water, deep enough for the channel, and offshore"),
		(Middle & HabOpenWater) && (Middle & HabChannel) && (Middle & HabOffshore));
	const uint32 Edge = Map.BitsAt(LakeR - 60.0, 0.0);
	TestTrue(TEXT("just inside the shore: shallows on the shore"), (Edge & HabShallows) && (Edge & HabShore) && !(Edge & HabOffshore));
	const uint32 Bank = Map.BitsAt(0.0, LakeR + 100.0);
	TestTrue(TEXT("the bank is shore, not water"), (Bank & HabShore) && !(Bank & (HabOpenWater | HabShallows)));
	TestTrue(TEXT("the bank 200 m back, 40 m up, is a cliff"), (Map.BitsAt(0.0, -(LakeR + 200.0)) & HabCliffs) != 0);
	TestTrue(TEXT("far inland is neither shore nor cliff"), (Map.BitsAt(LakeR + 800.0, 0.0) & (HabShore | HabCliffs)) == 0);
	TestTrue(TEXT("the sky is everywhere"), (Map.BitsAt(LakeR + 800.0, 0.0) & HabSky) != 0);
	TestTrue(TEXT("flight clears the land: the cell's top is at least its ground"), Map.TopAt(LakeR + 500.0, 0.0) >= Map.HeightAt(LakeR + 500.0, 0.0));
	const double Area = Map.AreaKm2(HabOpenWater, 0.0, 0.0, 2000.0);
	TestTrue(TEXT("a 2 km disc in the middle is all open water (12.6 km^2)"), FMath::Abs(Area - 12.566) < 0.4);
	std::vector<std::pair<uint32_t, double>> H;
	Map.Histogram(0.0, 0.0, 2000.0, H);
	TestTrue(TEXT("the histogram's areas add up the same"), FMath::Abs(FWildlifeHabitatMap::AreaOf(HabOpenWater, H) - Area) < 1e-6);
	TestEqual(TEXT("no habitat words: open water"), HabitatBits({}), uint32(HabOpenWater));
	TestEqual(TEXT("habitat words"), HabitatBits({ "beach", "marina", "cliffs", "unknown" }), uint32(HabShore | HabHarbour | HabCliffs));
	return true;
}

// When the birds are about: none at night for day birds, thermals only round midday, rain and gales thin them out.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingWildlifeDayTest, "SailingSim.Wildlife.Day", WildlifeTestsLocal::Flags)
bool FSailingWildlifeDayTest::RunTest(const FString&)
{
	TestTrue(TEXT("day birds at noon"), ActivityAt("day", 12.0, 60.0) > 0.95);
	TestTrue(TEXT("day birds at night"), ActivityAt("day", 2.0, -30.0) < 0.05);
	TestTrue(TEXT("dawn and dusk birds busiest at dusk"), ActivityAt("dawn_dusk", 19.5, 3.0) > ActivityAt("dawn_dusk", 12.0, 60.0));
	TestTrue(TEXT("no thermals at 8 am"), ActivityAt("midday_soaring", 8.0, 25.0) < 0.2);
	TestTrue(TEXT("thermals at 2 pm"), ActivityAt("midday_soaring", 14.0, 55.0) > 0.9);
	FWildlifeConditions C = WildlifeTestsLocal::Noon();
	TestTrue(TEXT("fair weather"), FMath::IsNearlyEqual(WeatherFactor(EBirdStyle::FlapHang, C), 1.0));
	C.RainMmH = 6.0;
	TestTrue(TEXT("heavy rain thins the gulls"), WeatherFactor(EBirdStyle::FlapHang, C) <= 0.25);
	TestTrue(TEXT("no soaring in rain"), WeatherFactor(EBirdStyle::Soaring, C) < 0.1);
	C.RainMmH = 0.0;
	C.WindKn = 30.0;
	TestTrue(TEXT("a gale thins them"), WeatherFactor(EBirdStyle::HeavyGlider, C) < 0.5);
	TestTrue(TEXT("no soaring in a gale"), WeatherFactor(EBirdStyle::Soaring, C) < 0.1);
	const FBirdBudget Low = BirdBudgetForTier(0), Ultra = BirdBudgetForTier(3);
	// (Low keeps a few birds inside 400 m, drawn as quads: with none a bird coming close would vanish.)
	TestTrue(TEXT("Low draws the fewest"), Low.Far > 0 && Low.Mid > 0 && Low.Mid <= 20 && Low.Near <= 4);
	TestTrue(TEXT("Ultra draws the most"), Ultra.Far > Low.Far && Ultra.Mid > Low.Mid && Ultra.Near > Low.Near);
	return true;
}

// Each bird keeps about the number of flocks its table expects, the drawn birds stay in the tier's budget, and flying
// birds stay over the ground.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingWildlifeCountsTest, "SailingSim.Wildlife.Counts", WildlifeTestsLocal::Flags)
bool FSailingWildlifeCountsTest::RunTest(const FString&)
{
	using namespace WildlifeTestsLocal;
	FWildlifeTable T;
	if (!LoadTable(TableJson({ Bird(TEXT("gull"), TEXT("flap_hang"), TEXT("\"open_water\""), 6, 30),
		Bird(TEXT("pelican"), TEXT("heavy_glider"), TEXT("\"open_water\""), 12, 60),
		Bird(TEXT("heron"), TEXT("wading"), TEXT("\"shallows\", \"shore\""), 1, 2),
		Bird(TEXT("vulture"), TEXT("soaring"), TEXT("\"over_shore\""), 3, 8),
		Bird(TEXT("cormorant"), TEXT("fast_low"), TEXT("\"open_water\""), 5, 20) }), T, *this)) return false;
	FWildlifeHabitatMap Map;
	Map.Build(RoundLake(), 0.0, 0.0);
	for (const int32 Tier : { 0, 2 })
	{
		const FBirdBudget Budget = BirdBudgetForTier(Tier);
		FBirdFlocks Flocks;
		Flocks.Reset(T, 7);
		Flocks.SetBudget(Budget);
		Flocks.SetDensityScale(3.0);
		// near the shore, so the shore birds and the open-water birds both have room
		const FBirdObservers Obs = At(LakeR - 1200.0, 0.0);
		const FWildlifeConditions C = Noon();
		TArray<double> Have, Want;
		Have.Init(0.0, Flocks.TableBirds());
		Want.Init(0.0, Flocks.TableBirds());
		int32 Samples = 0, OverBudget = 0, Under = 0;
		const double Dt = 1.0 / 30.0;
		for (int32 K = 0; K < 30 * 60 * 12; ++K)
		{
			Flocks.Update(Dt, C, Obs, Map);
			const FBirdFlocks::FStats& St = Flocks.Stats();
			OverBudget += St.Far > Budget.Far || St.Mid > Budget.Mid || St.Near > Budget.Near;
			for (const FBirdDraw& D : Flocks.Draw()) Under += Airborne(D) && D.Up < Map.TopAt(D.North, D.East) - 1.0;
			if (K < 30 * 60 * 2 || K % 30) continue;
			++Samples;
			for (int32 B = 0; B < Flocks.TableBirds(); ++B) { Have[B] += Flocks.FlockCountOf(B); Want[B] += Flocks.ExpectedNow(B); }
		}
		TestEqual(FString::Printf(TEXT("tier %d: every frame within the budget"), Tier), OverBudget, 0);
		TestEqual(FString::Printf(TEXT("tier %d: no flying bird under the ground"), Tier), Under, 0);
		for (int32 B = 0; B < Flocks.TableBirds(); ++B)
		{
			const double H = Have[B] / Samples, W = Want[B] / Samples;
			TestTrue(FString::Printf(TEXT("tier %d: %s expected somewhere"), Tier, UTF8_TO_TCHAR(Flocks.TableBird(B).Id.c_str())), W > 0.2);
			TestTrue(FString::Printf(TEXT("tier %d: %s keeps its count (%.1f flocks, expected %.1f)"), Tier,
				UTF8_TO_TCHAR(Flocks.TableBird(B).Id.c_str()), H, W), FMath::Abs(H - W) <= FMath::Max(1.5, 0.4 * W));
		}
		{
			// bodies only inside 400 m and within their budgets; every other bird drawn is a quad within Far
			int32 Bodies = 0, FarBodies = 0;
			for (const FBirdDraw& D : Flocks.Draw()) { Bodies += D.bBody; FarBodies += D.bBody && D.DistanceM >= FBirdFlocks::MidM; }
			TestTrue(FString::Printf(TEXT("tier %d: bodies within their budgets"), Tier), Bodies <= Budget.Mid + Budget.Near);
			TestEqual(FString::Printf(TEXT("tier %d: no body past 400 m"), Tier), FarBodies, 0);
			TestTrue(FString::Printf(TEXT("tier %d: everything drawn within the budget"), Tier),
				int32(Flocks.Draw().size()) <= Budget.Far + Budget.Mid + Budget.Near);
		}
		// nothing when it's out of season or night
		FWildlifeConditions Night = C;
		Night.LocalHour = 2.0;
		Night.SunElevationDeg = -40.0;
		double NightWant = 0.0;
		for (int32 B = 0; B < Flocks.TableBirds(); ++B) NightWant += Flocks.ExpectedFlocks(B, Night, Map, Obs.CamNorth, Obs.CamEast);
		double DayWant = 0.0;
		for (int32 B = 0; B < Flocks.TableBirds(); ++B) DayWant += Flocks.ExpectedFlocks(B, C, Map, Obs.CamNorth, Obs.CamEast);
		TestTrue(TEXT("hardly any at night"), NightWant < 0.05 * DayWant);
	}
	return true;
}

// Birds on the water lift when a boat comes inside their flush distance, nearest first, away from her, and not before.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingWildlifeFlushTest, "SailingSim.Wildlife.Flush", WildlifeTestsLocal::Flags)
bool FSailingWildlifeFlushTest::RunTest(const FString&)
{
	using namespace WildlifeTestsLocal;
	FWildlifeTable T;
	if (!LoadTable(TableJson({ Bird(TEXT("ducks"), TEXT("raft"), TEXT("\"open_water\""), 20, 40, 60.0) }), T, *this)) return false;
	FWildlifeHabitatMap Map;
	Map.Build(RoundLake(), 0.0, 0.0);
	FBirdFlocks Flocks;
	Flocks.Reset(T, 11);
	Flocks.SetDensityScale(4.0);
	const FWildlifeConditions C = Noon();
	FBirdObservers Obs = At(0.0, 0.0);
	Obs.Boats.clear();   // the camera alone first, so nothing is flushed while the rafts settle
	const double Dt = 1.0 / 30.0;
	for (int32 K = 0; K < 30 * 5; ++K) Flocks.Update(Dt, C, Obs, Map);
	auto SittingWithin = [&](double N0, double E0, double R)
	{
		int32 N = 0;
		for (const FBirdDraw& D : Flocks.Draw()) N += D.State == EBirdState::OnWater && FMath::Sqrt(FMath::Square(D.North - N0) + FMath::Square(D.East - E0)) < R;
		return N;
	};
	// the nearest raft of five or more sitting on the water 300 m or more out, and still sitting two seconds on (not one
	// taking off on its own)
	double RN = 0.0, RE = 0.0, Best = 1e9;
	int32 Count = 0;
	for (const FBirdDraw& D : Flocks.Draw())
	{
		if (D.State != EBirdState::OnWater || D.DistanceM < 300.0 || D.DistanceM > Best) continue;
		const int32 N = SittingWithin(D.North, D.East, 40.0);
		if (N >= 5) { RN = D.North; RE = D.East; Best = D.DistanceM; Count = N; }
	}
	if (!TestTrue(TEXT("a raft sits on the water"), Count >= 5)) return false;
	for (int32 K = 0; K < 30 * 2; ++K) Flocks.Update(Dt, C, Obs, Map);
	if (!TestEqual(TEXT("and stays there"), SittingWithin(RN, RE, 40.0), Count)) return false;
	auto SittingNear = [&]() { return SittingWithin(RN, RE, 120.0); };
	// a boat lying 250 m off for half a minute: nobody moves
	const double Bearing = FMath::Atan2(RE - 0.0, RN - 0.0);
	FBirdObservers Off = At(RN - 250.0 * FMath::Cos(Bearing), RE - 250.0 * FMath::Sin(Bearing), Bearing, 0.0);
	const int32 FlushesBefore = Flocks.Stats().Flushes;
	for (int32 K = 0; K < 30 * 30; ++K) Flocks.Update(Dt, C, Off, Map);
	TestEqual(TEXT("no flush from 250 m"), Flocks.Stats().Flushes, FlushesBefore);
	const int32 Sat = SittingNear();
	TestTrue(TEXT("still sitting"), Sat > 0);
	// she sails at them at 3 m/s
	double BN = Off.Boats[0].North, BE = Off.Boats[0].East;
	double MinGap = 1e9;
	for (int32 K = 0; K < 30 * 80; ++K)
	{
		BN += 3.0 * FMath::Cos(Bearing) * Dt;
		BE += 3.0 * FMath::Sin(Bearing) * Dt;
		const FBirdObservers Sail = At(BN, BE, Bearing, 3.0);
		Flocks.Update(Dt, C, Sail, Map);
		if (Flocks.Stats().Flushes > FlushesBefore) break;
		for (const FBirdDraw& D : Flocks.Draw())
			if (D.State == EBirdState::OnWater) MinGap = FMath::Min(MinGap, FMath::Sqrt(FMath::Square(D.North - BN) + FMath::Square(D.East - BE)));
	}
	TestTrue(TEXT("they flush as she comes"), Flocks.Stats().Flushes > FlushesBefore);
	TestTrue(TEXT("not before she is inside 60 m"), MinGap > 55.0);
	// ten seconds on they are up and further from her than they sat
	for (int32 K = 0; K < 30 * 10; ++K) Flocks.Update(Dt, C, At(BN, BE, Bearing, 0.0), Map);
	int32 Up = 0, Away = 0;
	for (const FBirdDraw& D : Flocks.Draw())
	{
		if (FMath::Sqrt(FMath::Square(D.North - RN) + FMath::Square(D.East - RE)) > 400.0) continue;
		if (D.State == EBirdState::OnWater) continue;
		++Up;
		Away += FMath::Sqrt(FMath::Square(D.North - BN) + FMath::Square(D.East - BE)) > 60.0;
	}
	TestTrue(TEXT("the raft is flying"), Up > 0);
	TestTrue(TEXT("away from the boat"), Away >= Up * 3 / 4);
	TestTrue(TEXT("fewer sitting where they were"), SittingNear() < Sat);
	return true;
}

// The same seed and the same inputs give the same birds.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingWildlifeRepeatableTest, "SailingSim.Wildlife.Repeatable", WildlifeTestsLocal::Flags)
bool FSailingWildlifeRepeatableTest::RunTest(const FString&)
{
	using namespace WildlifeTestsLocal;
	FWildlifeTable T;
	if (!LoadTable(TableJson({ Bird(TEXT("gull"), TEXT("flap_hang"), TEXT("\"open_water\""), 6, 30),
		Bird(TEXT("tern"), TEXT("hover_plunge"), TEXT("\"open_water\""), 3, 12) }), T, *this)) return false;
	FWildlifeHabitatMap Map;
	Map.Build(RoundLake(), 0.0, 0.0);
	FBirdFlocks A, B;
	A.Reset(T, 99);
	B.Reset(T, 99);
	const FWildlifeConditions C = Noon();
	for (int32 K = 0; K < 30 * 120; ++K)
	{
		const FBirdObservers Obs = At(0.1 * K, 0.0, 0.0, 3.0);
		A.Update(1.0 / 30.0, C, Obs, Map);
		B.Update(1.0 / 30.0, C, Obs, Map);
	}
	if (!TestEqual(TEXT("same birds drawn"), int32(A.Draw().size()), int32(B.Draw().size()))) return false;
	bool bSame = true;
	for (size_t I = 0; I < A.Draw().size(); ++I)
		bSame &= A.Draw()[I].North == B.Draw()[I].North && A.Draw()[I].East == B.Draw()[I].East && A.Draw()[I].Up == B.Draw()[I].Up;
	TestTrue(TEXT("in the same places"), bSame);
	TestTrue(TEXT("some birds about"), A.Draw().size() > 0);
	return true;
}

// With the camera's view, the birds on screen take the budget first; a near flock past the bodies' budget is drawn on as
// quads, not cut off.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingWildlifeViewTest, "SailingSim.Wildlife.View", WildlifeTestsLocal::Flags)
bool FSailingWildlifeViewTest::RunTest(const FString&)
{
	using namespace WildlifeTestsLocal;
	FWildlifeTable T;
	if (!LoadTable(TableJson({ Bird(TEXT("gull"), TEXT("flap_hang"), TEXT("\"open_water\""), 6, 30),
		Bird(TEXT("coot"), TEXT("raft"), TEXT("\"open_water\""), 20, 80) }), T, *this)) return false;
	FWildlifeHabitatMap Map;
	Map.Build(RoundLake(), 0.0, 0.0);
	FBirdBudget Small;
	Small.Far = 40; Small.Mid = 6; Small.Near = 2;
	FBirdFlocks Blind, Seeing;
	Blind.Reset(T, 21);
	Seeing.Reset(T, 21);
	Blind.SetBudget(Small);
	Seeing.SetBudget(Small);
	Blind.SetDensityScale(4.0);
	Seeing.SetDensityScale(4.0);
	const FWildlifeConditions C = Noon(1);
	FBirdObservers Plain = At(0.0, 0.0);
	FBirdObservers View = Plain;
	View.bHasView = true;                       // looking east and level, a cone 35 deg round
	View.ViewNorth = 0.0; View.ViewEast = 1.0; View.ViewUp = 0.0;
	View.ViewCosHalf = 0.8191520443;            // cos 35 deg
	auto InCone = [&](const FBirdDraw& D)
	{
		const double DN = D.North - View.CamNorth, DE = D.East - View.CamEast, DU = D.Up - View.CamUp;
		const double L = FMath::Sqrt(DN * DN + DE * DE + DU * DU);
		return L < 1e-3 || DN * View.ViewNorth + DE * View.ViewEast + DU * View.ViewUp >= View.ViewCosHalf * L;
	};
	int32 BlindInView = 0, SeeingInView = 0;
	int32 Frames = 0, Fewer = 0, Overflow = 0, OverflowEarly = 0, Mislabelled = 0;
	for (int32 K = 0; K < 30 * 60 * 3; ++K)
	{
		Blind.Update(1.0 / 30.0, C, Plain, Map);
		Seeing.Update(1.0 / 30.0, C, View, Map);
		if (K % 15) continue;
		++Frames;
		int32 B = 0, S = 0, Flagged = 0;
		for (const FBirdDraw& D : Blind.Draw()) B += InCone(D);
		for (const FBirdDraw& D : Seeing.Draw())
		{
			S += InCone(D);
			Flagged += D.bInView;
			Mislabelled += D.bInView != InCone(D);
			if (!D.bBody && D.DistanceM < FBirdFlocks::MidM)
			{
				++Overflow;
				OverflowEarly += Seeing.Stats().Mid < Small.Mid;   // a quad inside 400 m only once the mid bodies are spent
			}
		}
		BlindInView += B;
		SeeingInView += S;
		Fewer += S < B;
		TestEqual(TEXT("the stats count the birds in view"), Seeing.Stats().InView, Flagged);
	}
	TestEqual(TEXT("each bird's in-view flag is its place in the cone"), Mislabelled, 0);
	TestEqual(TEXT("never fewer birds on screen with the view than without"), Fewer, 0);
	TestTrue(FString::Printf(TEXT("more birds on screen with the view (%d against %d over %d frames)"), SeeingInView, BlindInView, Frames),
		SeeingInView > BlindInView + Frames);
	TestTrue(TEXT("a flock close by past the bodies' budget is drawn on as quads"), Overflow > 0);
	TestEqual(TEXT("and only once the mid bodies are spent"), OverflowEarly, 0);
	return true;
}

#endif
