#include "Misc/AutomationTest.h"
#include "GeoAnchor.h"
#include "LakeData.h"
#include "Navigation.h"
#include "SailSave.h"
#include "SailSession.h"
#include "SailingSettings.h"
#include "UI/SailCatalog.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

// Online readiness rule 6 (docs/geo-anchor/README.md): each world's anchor is the bake's own transverse Mercator, so
// lat/lon <-> map metres agrees with pyproj to the centimetre; the chart's lat/lon lands on the baked navaid; a save
// whose spot id is gone finds the spot by its lat/lon.
namespace GeoTestsLocal
{
	constexpr EAutomationTestFlags GeoFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
	const TCHAR* const Files[] = { TEXT("RayHubbard"), TEXT("GalvestonBay"), TEXT("GulfPassage") };

	TSharedPtr<FJsonObject> Header(const TCHAR* File)
	{
		FString Text;
		TSharedPtr<FJsonObject> Root;
		if (FFileHelper::LoadFileToString(Text, *(FLakeData::DefaultDirectory() / (FString(File) + TEXT(".json")))))
		{
			FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root);
		}
		return Root;
	}

	/** pyproj 3.8 (PROJ 9.8.1), EPSG:4326 -> each bake's projection string, inverted at the grid's origin and corners
	 *  (north, east, lat, lon). Computed Oct 18 2026 (docs/geo-anchor/README.md has the script). */
	struct FRef { int32 World; double North, East, Lat, Lon; };
	const FRef PyprojCorners[] = {
		{ 0, -4795, -11235, 32.78000581220231, -96.61992381573776 },
		{ 0, -4795, 5145, 32.78005117581414, -96.44508157600646 },
		{ 0, 22370, -11235, 33.02494966160488, -96.6202544046544 },
		{ 0, 22370, 5145, 33.02499545004146, -96.44493018435622 },
		{ 1, -39240, -9250, 29.190548328430037, -95.11440620508084 },
		{ 1, -39240, 34300, 29.190117624465515, -94.66663847390376 },
		{ 1, 8900, -9250, 29.624857574626944, -95.11481134439427 },
		{ 1, 8900, 34300, 29.62441920821946, -94.66513621986125 },
		{ 2, -62900, -70800, 28.760553075639866, -95.41493425055259 },
		{ 2, -62900, 12550, 28.762436483881817, -94.56149413359304 },
		{ 2, 3250, -70800, 29.357328584870952, -95.41912065319866 },
		{ 2, 3250, 12550, 29.359258542603747, -94.56075195125695 },
	};

	/** Metres between two lat/lons near a world (small separations). */
	double GroundMeters(const Sailing::FLatLon& A, const Sailing::FLatLon& B)
	{
		const double North = (A.LatDeg - B.LatDeg) * 111000.0;
		const double East = (A.LonDeg - B.LonDeg) * 111000.0 * FMath::Cos(FMath::DegreesToRadians(A.LatDeg));
		return FMath::Sqrt(North * North + East * East);
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingGeoAnchorParseTest, "SailingSim.Geo.Anchor", GeoTestsLocal::GeoFlags)
bool FSailingGeoAnchorParseTest::RunTest(const FString&)
{
	using namespace GeoTestsLocal;
	for (int32 W = 0; W < 3; ++W)
	{
		const TSharedPtr<FJsonObject> Root = Header(Files[W]);
		if (!TestTrue(FString::Printf(TEXT("%s header"), Files[W]), Root.IsValid())) return false;
		Sailing::FGeoAnchor A;
		TestTrue(FString::Printf(TEXT("%s: the projection parses"), Files[W]), Sailing::FGeoAnchor::ParseProj4(TCHAR_TO_UTF8(*Root->GetStringField(TEXT("projection"))), A));
		const Sailing::FGeoAnchor Fallback = Sailing::FGeoAnchor::ForWorld(TCHAR_TO_UTF8(Files[W]));
		TestEqual(FString::Printf(TEXT("%s: lat_0 is the build script's"), Files[W]), A.Lat0Deg, Fallback.Lat0Deg);
		TestEqual(FString::Printf(TEXT("%s: lon_0 is the build script's"), Files[W]), A.Lon0Deg, Fallback.Lon0Deg);
		TestEqual(FString::Printf(TEXT("%s: k"), Files[W]), A.ScaleK0, 1.0);
		TestTrue(FString::Printf(TEXT("%s: the catalogue reads the same anchor"), Files[W]),
			SailCatalog::Anchor(W).Lat0Deg == A.Lat0Deg && SailCatalog::Anchor(W).Lon0Deg == A.Lon0Deg && SailCatalog::Anchor(W).bValid);
	}
	Sailing::FGeoAnchor Bad;
	TestFalse(TEXT("A UTM string is not a local tmerc"), Sailing::FGeoAnchor::ParseProj4("+proj=utm +zone=14 +datum=NAD83", Bad));
	TestFalse(TEXT("No lat_0: refused"), Sailing::FGeoAnchor::ParseProj4("+proj=tmerc +lon_0=-96.5 +datum=NAD83", Bad));
	TestFalse(TEXT("Unknown world: invalid"), Sailing::FGeoAnchor::ForWorld("Atlantis").bValid);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingGeoRoundTripTest, "SailingSim.Geo.RoundTrip", GeoTestsLocal::GeoFlags)
bool FSailingGeoRoundTripTest::RunTest(const FString&)
{
	using namespace GeoTestsLocal;
	double WorstRoundTrip = 0.0, WorstPyproj = 0.0;
	for (int32 W = 0; W < 3; ++W)
	{
		const Sailing::FGeoAnchor& A = SailCatalog::Anchor(W);
		const TSharedPtr<FJsonObject> Grid = Header(Files[W])->GetObjectField(TEXT("grid"));
		const double Cell = Grid->GetNumberField(TEXT("cell_m"));
		const double N0 = Grid->GetNumberField(TEXT("origin_north_m")), E0 = Grid->GetNumberField(TEXT("origin_east_m"));
		const double N1 = N0 + (Grid->GetNumberField(TEXT("rows_north")) - 1) * Cell, E1 = E0 + (Grid->GetNumberField(TEXT("cols_east")) - 1) * Cell;
		// The origin, the four corners, the edge midpoints and the grid's centre.
		const Sailing::FMapPoint Points[] = { { 0, 0 }, { N0, E0 }, { N0, E1 }, { N1, E0 }, { N1, E1 }, { N0, 0.5 * (E0 + E1) }, { N1, 0.5 * (E0 + E1) },
			{ 0.5 * (N0 + N1), E0 }, { 0.5 * (N0 + N1), E1 }, { 0.5 * (N0 + N1), 0.5 * (E0 + E1) } };
		for (const Sailing::FMapPoint& P : Points)
		{
			const Sailing::FMapPoint Back = A.ToMap(A.ToLatLon(P));
			const double D = Sailing::FGeoAnchor::Distance(P, Back);
			WorstRoundTrip = FMath::Max(WorstRoundTrip, D);
			TestTrue(FString::Printf(TEXT("%s (%.0f, %.0f): map -> lat/lon -> map within 1 cm (%.2e m)"), Files[W], P.North, P.East, D), D < 0.01);
			// And the other way: lat/lon -> map -> lat/lon.
			const Sailing::FLatLon Geo = A.ToLatLon(P);
			const double G = GroundMeters(Geo, A.ToLatLon(A.ToMap(Geo)));
			TestTrue(FString::Printf(TEXT("%s (%.0f, %.0f): lat/lon -> map -> lat/lon within 1 cm (%.2e m)"), Files[W], P.North, P.East, G), G < 0.01);
		}
		const Sailing::FLatLon Origin = A.ToLatLon({ 0, 0 });
		TestTrue(FString::Printf(TEXT("%s: the origin is lat_0, lon_0"), Files[W]),
			FMath::Abs(Origin.LatDeg - A.Lat0Deg) < 1e-10 && FMath::Abs(Origin.LonDeg - A.Lon0Deg) < 1e-10);
	}
	// Against PROJ itself (what made the bakes): every corner within 1 cm, both ways.
	for (const FRef& R : PyprojCorners)
	{
		const Sailing::FGeoAnchor& A = SailCatalog::Anchor(R.World);
		const double Fwd = Sailing::FGeoAnchor::Distance(A.ToMap({ R.Lat, R.Lon }), { R.North, R.East });
		const double Inv = GroundMeters(A.ToLatLon({ R.North, R.East }), { R.Lat, R.Lon });
		WorstPyproj = FMath::Max(WorstPyproj, FMath::Max(Fwd, Inv));
		TestTrue(FString::Printf(TEXT("%s (%.0f, %.0f): matches pyproj within 1 cm (forward %.2e m, inverse %.2e m)"), Files[R.World], R.North, R.East, Fwd, Inv),
			Fwd < 0.01 && Inv < 0.01);
	}
	// Galveston's grid reaches the Gulf front at 29.19 N.
	const Sailing::FLatLon South = SailCatalog::Anchor(1).ToLatLon({ -39240.0, 0.0 });
	TestTrue(FString::Printf(TEXT("Galveston's south edge is at 29.19 N (%.5f)"), South.LatDeg), FMath::Abs(South.LatDeg - 29.19) < 0.005);
	AddInfo(FString::Printf(TEXT("Worst round trip %.2e m, worst against pyproj %.2e m"), WorstRoundTrip, WorstPyproj));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingGeoKnownPointsTest, "SailingSim.Geo.KnownPoints", GeoTestsLocal::GeoFlags)
bool FSailingGeoKnownPointsTest::RunTest(const FString&)
{
	using namespace GeoTestsLocal;
	// Rush Creek Yacht Club is the lake's origin (build_rayhubbard.py's LAT0, LON0).
	const Sailing::FLatLon Club = SailCatalog::Anchor(0).ToLatLon({ 0.0, 0.0 });
	TestTrue(TEXT("Rush Creek Yacht Club: 32.8233 N 96.5000 W at the lake's origin"), FMath::Abs(Club.LatDeg - 32.8233) < 1e-9 && FMath::Abs(Club.LonDeg + 96.5) < 1e-9);
	// The club's launch spot in the bake carries its own lat/lon beside its metres.
	const SailCatalog::FSpot& Home = SailCatalog::Spots(0)[0];
	const double HomeErr = GroundMeters({ Home.Lat, Home.Lon }, { 32.82335, -96.5004 });
	TestTrue(FString::Printf(TEXT("The club's spot: the bake's lat/lon within 1 m of its metres (%.3f m)"), HomeErr), HomeErr < 1.0);

	// A Galveston navaid: NOAA ENC US5HOUAI gives Houston Ship Channel Lighted Buoy 34 at 29.4082353 N 94.8202819 W.
	const TSharedPtr<FJsonObject> Root = Header(TEXT("GalvestonBay"));
	FVector2D Baked(0.0, 0.0);
	bool bFound = false;
	for (const TSharedPtr<FJsonValue>& V : Root->GetArrayField(TEXT("navaids")))
	{
		const TSharedPtr<FJsonObject> O = V->AsObject();
		if (O->GetStringField(TEXT("name")) == TEXT("Houston Ship Channel Lighted Buoy 34"))
		{
			Baked = FVector2D(O->GetNumberField(TEXT("x")), O->GetNumberField(TEXT("y")));
			bFound = true;
		}
	}
	if (!TestTrue(TEXT("Buoy 34 is in the bake"), bFound)) return false;
	const FVector2D Chart = SailingNav::MapAt(SailCatalog::Anchor(1), { 29.4082353, -94.8202819 });
	const double BuoyErr = FVector2D::Distance(Chart, Baked);
	TestTrue(FString::Printf(TEXT("Buoy 34: the chart's lat/lon within 1 m of the baked position (%.3f m)"), BuoyErr), BuoyErr < 1.0);
	// The boundary helper agrees with the anchor both ways.
	const Sailing::FLatLon BuoyGeo = SailingNav::LatLonAt(SailCatalog::Anchor(1), Baked);
	TestTrue(TEXT("SailingNav::LatLonAt inverts MapAt"), FVector2D::Distance(SailingNav::MapAt(SailCatalog::Anchor(1), BuoyGeo), Baked) < 0.001);
	AddInfo(FString::Printf(TEXT("Club spot %.3f m, Buoy 34 %.3f m"), HomeErr, BuoyErr));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingGeoSaveFallbackTest, "SailingSim.Geo.SaveFallback", GeoTestsLocal::GeoFlags)
bool FSailingGeoSaveFallbackTest::RunTest(const FString&)
{
	// Every spot of every world carries its lat/lon into the save, and resolves to itself by id and by lat/lon alone.
	for (int32 W = 0; W < 3; ++W)
	{
		const TArray<SailCatalog::FSpot>& Spots = SailCatalog::Spots(W);
		for (int32 I = 0; I < Spots.Num(); ++I)
		{
			TestEqual(FString::Printf(TEXT("%s: by id"), *Spots[I].Id), FSailSave::SpotIndex(W, Spots[I].Id, true, Spots[I].Lat, Spots[I].Lon), I);
			TestEqual(FString::Printf(TEXT("%s: renamed, by lat/lon"), *Spots[I].Id), FSailSave::SpotIndex(W, TEXT("renamed-in-a-rebake"), true, Spots[I].Lat, Spots[I].Lon), I);
			const FVector2D Back = SailingNav::MapAt(SailCatalog::Anchor(W), { Spots[I].Lat, Spots[I].Lon });
			const double D = FVector2D::Distance(Back, FVector2D(Spots[I].North, Spots[I].East));
			TestTrue(FString::Printf(TEXT("%s: its saved lat/lon is within 1 m of it (%.4f m)"), *Spots[I].Id, D), D < 1.0);
		}
	}

	// A version-1 file naming a spot the game no longer has (renamed in a rebake), with the spot's lat/lon: the session
	// and the next start land on that spot. The save's version doesn't change for the optional field.
	const SailCatalog::FSpot& Dam = SailCatalog::Spots(0)[2];
	const SailCatalog::FSpot& Kemah = SailCatalog::Spots(1)[1];
	const FString Text = FString::Printf(TEXT("{\"version\":1,\"settings\":{\"start\":{\"world\":\"galveston-bay\",\"launchSpot\":\"old-kemah-name\","
		"\"launchSpotAt\":{\"lat\":%.9f,\"lon\":%.9f}}},\"lastSession\":{\"world\":\"ray-hubbard\",\"launchSpot\":\"the-dam-before-the-rebake\","
		"\"launchSpotAt\":{\"lat\":%.9f,\"lon\":%.9f},\"boat\":\"J22\"}}"), Kemah.Lat, Kemah.Lon, Dam.Lat + 0.0002, Dam.Lon);   // the dam spot 22 m off
	FSailSave Save;
	TestEqual(TEXT("Read as version 1"), int32(FSailSave::FromJson(Text, Save)), int32(FSailSave::EResult::Ok));
	TestEqual(TEXT("Version stays 1"), FSailSave::CurrentVersion, 1);
	TestTrue(TEXT("Start lat/lon read"), Save.Settings.bHasSpotAt);
	USailingSettings* Settings = NewObject<USailingSettings>();
	USailSessionSave* Session = NewObject<USailSessionSave>();
	Save.Apply(*Settings, *Session);
	TestEqual(TEXT("Next start: Galveston"), Settings->World, 1);
	TestEqual(TEXT("Next start: the Kemah spot by lat/lon"), Settings->LaunchSpot, 1);
	TestEqual(TEXT("Last session: the dam spot by lat/lon"), Session->Last.LaunchSpot, 2);
	const double Landed = FVector2D::Distance(FVector2D(SailCatalog::Spots(0)[Session->Last.LaunchSpot].North, SailCatalog::Spots(0)[Session->Last.LaunchSpot].East),
		FVector2D(Dam.North, Dam.East));
	TestTrue(FString::Printf(TEXT("Landed within 1 m of the spot (%.3f m)"), Landed), Landed < 1.0);

	// Captured back, the current ids and lat/lon are written; the old file's unknown fields stay.
	FSailSave Again = Save;
	Again.Capture(*Settings, *Session);
	TestEqual(TEXT("Captured: the current id"), Again.Last.SpotId, Dam.Id);
	TestTrue(TEXT("Captured: the spot's lat/lon"), Again.Last.bHasSpotAt && Again.Last.SpotLat == Dam.Lat && Again.Last.SpotLon == Dam.Lon);

	// Far from every spot (over 500 m): the first spot, as for an unknown id without lat/lon.
	TestEqual(TEXT("Nothing near: the first spot"), FSailSave::SpotIndex(0, TEXT("gone"), true, 32.5, -96.0), 0);
	TestEqual(TEXT("No lat/lon, unknown id: the first spot"), FSailSave::SpotIndex(0, TEXT("gone"), false, 0.0, 0.0), 0);
	// An id that exists wins over a lat/lon pointing elsewhere.
	TestEqual(TEXT("Id first"), FSailSave::SpotIndex(0, SailCatalog::Spots(0)[3].Id, true, Dam.Lat, Dam.Lon), 3);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingGeoLakeDataTest, "SailingSim.Geo.LakeData", GeoTestsLocal::GeoFlags)
bool FSailingGeoLakeDataTest::RunTest(const FString&)
{
	// The loaded world exposes the same anchor as the catalogue (Galveston's bake: its terrain and chart).
	FLakeData Lake;
	if (!TestTrue(TEXT("Galveston loads"), Lake.Load(FLakeData::DefaultDirectory(), TEXT("GalvestonBay")))) return false;
	TestTrue(TEXT("Anchor from the header"), Lake.Anchor.bValid && Lake.Anchor.Lat0Deg == 29.5446 && Lake.Anchor.Lon0Deg == -95.0193);
	// Every navaid's position goes to lat/lon inside the chart's cells and back to the same metres.
	double Worst = 0.0;
	for (const FNavaid& N : Lake.Navaids)
	{
		const FVector2D P(N.X, N.Y);
		Worst = FMath::Max(Worst, FVector2D::Distance(SailingNav::MapAt(Lake.Anchor, SailingNav::LatLonAt(Lake.Anchor, P)), P));
	}
	TestTrue(FString::Printf(TEXT("%d navaids round-trip within 1 cm (%.2e m)"), Lake.Navaids.Num(), Worst), Lake.Navaids.Num() > 0 && Worst < 0.01);
	return true;
}
