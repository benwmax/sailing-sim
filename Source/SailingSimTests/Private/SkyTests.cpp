#include "Misc/AutomationTest.h"
#include "CloudSky.h"
#include "Weather.h"

using namespace Sailing;

namespace
{
	constexpr EAutomationTestFlags SkyFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
}

/**
 * The cloud layers from the weather (Visual V5): the weather map painted for each preset carries each layer's coverage
 * (cumulus, stratus, cirrus means within 0.05 of the preset table), the summer cumulus build after noon with bases at
 * 1.2 to 1.5 km, overcast and rain are low decks, and only the thunderstorm paints a storm.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSkyCloudLayersTest, "SailingSim.Visual.CloudLayers", SkyFlags)
bool FSkyCloudLayersTest::RunTest(const FString&)
{
	struct FCase { EWeatherPreset Preset; double Hour; double T; };
	const FCase Cases[] = {
		{ EWeatherPreset::CalmMorning, 9.0, 60.0 }, { EWeatherPreset::AfternoonBreeze, 11.0, 60.0 }, { EWeatherPreset::AfternoonBreeze, 15.0, 60.0 },
		{ EWeatherPreset::Overcast, 13.0, 60.0 }, { EWeatherPreset::Rain, 13.0, 60.0 }, { EWeatherPreset::Thunderstorm, 15.0, 30.0 },
		{ EWeatherPreset::Thunderstorm, 15.0, 200.0 },
	};
	for (const FCase& C : Cases)
	{
		FWeatherSystem W;
		W.Configure(C.Preset, 7, C.Hour);
		const FWeatherState S = W.Evaluate(C.T);
		FWeatherMap Map;
		Map.Paint(S.Sky, S.Front, 0.0, 0.0, C.T);
		const FString Name = FString::Printf(TEXT("%s %.0fh +%.0fs"), ANSI_TO_TCHAR(WeatherPresetName(C.Preset)), C.Hour, C.T);
		const ECloudLayer Painted[] = { ECloudLayer::Cumulus, ECloudLayer::Stratus, ECloudLayer::Cirrus };
		FString Line = Name + TEXT(":");
		for (int32 I = 0; I < 3; ++I)
		{
			const double Want = S.Sky[Painted[I]].Coverage, Got = Map.Mean(I);
			Line += FString::Printf(TEXT(" %s %.2f/%.2f"), ANSI_TO_TCHAR(CloudLayerName(Painted[I])), Got, Want);
			TestTrue(FString::Printf(TEXT("%s: %s coverage from the map"), *Name, ANSI_TO_TCHAR(CloudLayerName(Painted[I]))), FMath::Abs(Got - Want) < 0.05);
		}
		Line += FString::Printf(TEXT(" storm %.2f, cumulus base %.2f km, haze %.2f"), Map.Mean(3), S.Sky[ECloudLayer::Cumulus].BaseKm, S.Sky.Haze);
		AddInfo(Line);
		TestEqual(*(Name + TEXT(": a storm only in the thunderstorm")), Map.Mean(3) > 0.01, C.Preset == EWeatherPreset::Thunderstorm);
	}
	// Summer cumulus: few in the late morning, about a fifth of the sky mid-afternoon (C1). Their bases at the lifting
	// condensation level, 125 m per degree of dew-point spread: near 1 km on a June morning, near 2 km mid-afternoon (the weather's default month).
	FWeatherSystem W;
	W.Configure(EWeatherPreset::AfternoonBreeze, 7, 10.0);
	const FCloudLayer Morning = W.Evaluate(0.0).Sky[ECloudLayer::Cumulus];
	W.Configure(EWeatherPreset::AfternoonBreeze, 7, 15.5);
	const FCloudLayer Afternoon = W.Evaluate(0.0).Sky[ECloudLayer::Cumulus];
	TestTrue(TEXT("Cumulus build after noon"), Afternoon.Coverage > 0.18 && Morning.Coverage < 0.1);
	AddInfo(FString::Printf(TEXT("June cumulus bases: %.2f km at 10:00, %.2f km at 15:30"), Morning.BaseKm, Afternoon.BaseKm));
	TestTrue(TEXT("Summer cumulus bases from the dew-point spread"), Morning.BaseKm >= 0.7 && Morning.BaseKm <= 1.3 && Afternoon.BaseKm >= 1.5 && Afternoon.BaseKm <= 2.3 && Afternoon.BaseKm > Morning.BaseKm);
	{
		FWeatherSystem Coast;
		Coast.SetClimate(6, true);
		Coast.Configure(EWeatherPreset::AfternoonBreeze, 7, 15.5);
		TestTrue(TEXT("The humid coast's bases are lower than the lake's"), Coast.Evaluate(0.0).Sky[ECloudLayer::Cumulus].BaseKm < Afternoon.BaseKm - 0.3);
	}
	// Low decks under overcast and rain; the storm's base lower than the fair-weather cumulus.
	W.Configure(EWeatherPreset::Overcast, 7, 13.0);
	TestTrue(TEXT("Overcast is a low stratus deck"), W.Evaluate(0.0).Sky[ECloudLayer::Stratus].Coverage > 0.9 && W.Evaluate(0.0).Sky[ECloudLayer::Stratus].BaseKm < 1.2);
	// Graphics G6: and an unbroken one (eight oktas): no texel of the map without stratus.
	{
		const FWeatherState Over = W.Evaluate(60.0);
		FWeatherMap Deck;
		Deck.Paint(Over.Sky, Over.Front, 0.0, 0.0, 60.0);
		float Thinnest = 1.f;
		for (int32 I = 0; I < FWeatherMap::N * FWeatherMap::N; ++I) Thinnest = FMath::Min(Thinnest, Deck.Pixels()[I * 4 + 1]);
		AddInfo(FString::Printf(TEXT("Overcast: thinnest stratus texel %.2f"), Thinnest));
		TestTrue(TEXT("The overcast has no holes"), Thinnest > 0.99f);
	}
	W.Configure(EWeatherPreset::Thunderstorm, 7, 15.0);
	const FWeatherState Storm = W.Evaluate(140.0);
	TestTrue(TEXT("The storm's base is below the cumulus"), Storm.Sky[ECloudLayer::Storm].BaseKm < Storm.Sky[ECloudLayer::Cumulus].BaseKm && Storm.Sky[ECloudLayer::Cirrus].Coverage > 0.3);
	// Cumulus over the land: a map half land, half lake has more cloud over the land.
	FWeatherMap Land;
	Land.LandFraction = [](double X, double) { return X > 0.0 ? 1.0 : 0.0; };
	const FWeatherState Afternoon2 = W.Evaluate(0.0);
	FCloudSky Sky = Afternoon2.Sky;
	Sky[ECloudLayer::Cumulus].Coverage = 0.3;
	Sky.DriftX = Sky.DriftY = 0.0;
	Land.Paint(Sky, FGustFront(), 0.0, 0.0, 0.0);
	double OverLand = 0.0, OverLake = 0.0;
	const int32 N = FWeatherMap::N;
	for (int32 R = 0; R < N; ++R)
		for (int32 C = 0; C < N; ++C) (R >= N / 2 ? OverLand : OverLake) += Land.Pixels()[(R * N + C) * 4];
	AddInfo(FString::Printf(TEXT("Cumulus over land %.2f, over the lake %.2f"), OverLand / (N * N / 2), OverLake / (N * N / 2)));
	TestTrue(TEXT("Cumulus favour the land"), OverLand > 1.3 * OverLake);
	return true;
}

/**
 * docs/night-clouds/: fair-weather cumulus is the day's heat rising: it dies away over a couple of hours after sunset
 * (whatever the date), stays down through the night, and builds again the next day; the decks and the storm keep theirs.
 */
// Realism audit 1 (docs/cumulus-size/): the map carries each cumulus cell's size (FWeatherMap::CumulusTop), so the renderer
// stands a cell about as tall as it is wide. On a fair afternoon the painted cells span the size classes: small cells
// well under the largest class, the largest at the top; none outside 0..1, and no size where no cell paints.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSkyCumulusSizeTest, "SailingSim.Visual.CumulusSize", SkyFlags)
bool FSkyCumulusSizeTest::RunTest(const FString&)
{
	FWeatherSystem W;
	W.Configure(EWeatherPreset::AfternoonBreeze, 7, 15.0);
	const FWeatherState S = W.Evaluate(60.0);
	FWeatherMap Map;
	Map.Paint(S.Sky, S.Front, 0.0, 0.0, 60.0);
	const std::vector<float>& Top = Map.CumulusTop();
	const std::vector<float>& Px = Map.Pixels();
	TestEqual(TEXT("One size per texel"), int32(Top.size()), FWeatherMap::N * FWeatherMap::N);
	int32 Small = 0, Large = 0, Cloudy = 0, Bad = 0;
	for (size_t I = 0; I < Top.size(); ++I)
	{
		if (Top[I] < 0.f || Top[I] > 1.f + 1e-4f) ++Bad;
		if (Px[I * 4] < 0.2f || Top[I] <= 0.f) continue;
		++Cloudy;
		if (Top[I] < 0.5f) ++Small;
		if (Top[I] > 0.9f) ++Large;
	}
	AddInfo(FString::Printf(TEXT("Cloudy texels %d: small cells (size < 0.5) %d, the largest class (> 0.9) %d"), Cloudy, Small, Large));
	TestEqual(TEXT("Sizes within 0..1"), Bad, 0);
	TestTrue(TEXT("Small cells are painted small"), Small > Cloudy / 20);
	TestTrue(TEXT("The largest class is painted"), Large > 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSkyCumulusAfterSunsetTest, "SailingSim.Visual.CumulusAfterSunset", SkyFlags)
bool FSkyCumulusAfterSunsetTest::RunTest(const FString&)
{
	auto CuAt = [](EWeatherPreset P, double Sunset, double Hour)
	{
		FWeatherSystem W;
		W.SetSunset(Sunset);
		W.Configure(P, 7, Hour);
		return W.Evaluate(0.0).Sky[ECloudLayer::Cumulus].Coverage;
	};
	for (const double Sunset : { 18.75, 20.6 })   // late October and late June at the lake
	{
		const double Day = CuAt(EWeatherPreset::AfternoonBreeze, Sunset, 16.0), Before = CuAt(EWeatherPreset::AfternoonBreeze, Sunset, Sunset - 0.5);
		const double After1 = CuAt(EWeatherPreset::AfternoonBreeze, Sunset, Sunset + 1.0), After2 = CuAt(EWeatherPreset::AfternoonBreeze, Sunset, Sunset + 2.0);
		const double Midnight = CuAt(EWeatherPreset::AfternoonBreeze, Sunset, 23.9), Small = CuAt(EWeatherPreset::AfternoonBreeze, Sunset, 3.0);
		AddInfo(FString::Printf(TEXT("Sunset %.2f h: cumulus %.3f at 16 h, %.3f half an hour before, %.3f an hour after, %.3f two hours after, %.3f at midnight, %.3f at 3 h"),
			Sunset, Day, Before, After1, After2, Midnight, Small));
		TestTrue(FString::Printf(TEXT("Sunset %.2f: still up just before sunset"), Sunset), Before > 0.7 * Day);
		TestTrue(FString::Printf(TEXT("Sunset %.2f: dying an hour after"), Sunset), After1 < 0.75 * Day && After1 > 0.15 * Day);
		TestTrue(FString::Printf(TEXT("Sunset %.2f: a few remnants two hours after"), Sunset), After2 <= 0.2 * Day);
		TestTrue(FString::Printf(TEXT("Sunset %.2f: down through the night"), Sunset), Midnight <= 0.2 * Day && Small <= 0.2 * Day);
	}
	TestTrue(TEXT("The next day builds again"), CuAt(EWeatherPreset::AfternoonBreeze, 18.75, 15.0) > 0.18);
	FWeatherSystem Deck;
	Deck.SetSunset(18.75);
	Deck.Configure(EWeatherPreset::Overcast, 7, 22.0);
	TestTrue(TEXT("An overcast keeps its deck at night"), Deck.Evaluate(0.0).Sky[ECloudLayer::Stratus].Coverage > 0.9);
	return true;
}

/**
 * The shelf cloud rides the physics gust front (Visual V5): the shelf's leading edge, as the cloud shader draws it
 * (FStormShape, mirrored in make_materials.py), arrives over the boat within 30 s of the front itself; the rain core and
 * its darker, higher cloud follow.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSkyShelfCloudTest, "SailingSim.Visual.ShelfCloud", SkyFlags)
bool FSkyShelfCloudTest::RunTest(const FString&)
{
	FWeatherSystem W;
	W.Configure(EWeatherPreset::Thunderstorm, 3, 15.0, 0.0, 0.0);
	double FrontAt = -1.0, ShelfAt = -1.0, CoreAt = -1.0;
	double LowestShelf = 1e9;
	for (double T = 0.0; T < 400.0; T += 0.5)
	{
		const FWeatherState S = W.Evaluate(T);
		const double D = S.Front.DistanceAhead(0.0, 0.0, T);
		const double Build = S.Sky[ECloudLayer::Storm].Coverage;
		if (FrontAt < 0.0 && D <= 0.0) FrontAt = T;
		// Is there shelf cloud overhead (looking straight up, anywhere from 300 m to 1.5 km)?
		double Overhead = 0.0;
		for (double Alt = 300.0; Alt <= 1500.0; Alt += 25.0)
		{
			const double Dens = FStormShape::Density(D, Alt, 1.0, Build);
			if (Dens > 0.2 && Alt < LowestShelf && D > -FStormShape::CoreBehindM) LowestShelf = Alt;
			Overhead = FMath::Max(Overhead, Dens);
		}
		if (ShelfAt < 0.0 && Overhead > 0.2) ShelfAt = T;
		if (CoreAt < 0.0 && FStormShape::Density(D, 4000.0, 1.0, Build) > 0.5) CoreAt = T;
	}
	AddInfo(FString::Printf(TEXT("Gust front over the boat at %.1f s, shelf cloud's leading edge at %.1f s (%.1f s ahead), rain core at %.1f s; shelf base %.0f m"),
		FrontAt, ShelfAt, FrontAt - ShelfAt, CoreAt, LowestShelf));
	TestTrue(TEXT("The front arrives"), FrontAt > 0.0);
	TestTrue(TEXT("The shelf cloud arrives with the front (within 30 s)"), ShelfAt > 0.0 && FMath::Abs(FrontAt - ShelfAt) <= 30.0);
	TestTrue(TEXT("The shelf is low (under 600 m)"), LowestShelf < 600.0);
	TestTrue(TEXT("The rain core follows the front"), CoreAt > FrontAt);

	// W8: the leading edge is crisp (the arcus): at the lip's middle the density goes from nothing to full within 100 m.
	const double Lead = FStormShape::ShelfLeadM;
	auto Thickest = [](double D) { double M = 0.0; for (double Alt = 300.0; Alt <= 900.0; Alt += 5.0) M = FMath::Max(M, FStormShape::Density(D, Alt, 1.0, 1.0)); return M; };
	const double Outside = Thickest(Lead + 5.0), Inside = Thickest(Lead - 100.0);
	// And the rolled front face is lit and pale over a dark slate underside (as M_CloudLayers shades it).
	const double Face = FStormShape::ShelfShade(150.0, 0.6), Under = FStormShape::ShelfShade(1500.0, 0.05);
	AddInfo(FString::Printf(TEXT("Shelf edge: density %.2f just ahead of the lip, %.2f 100 m behind it; face shade %.2f, underside %.2f (%.1fx)"),
		Outside, Inside, Face, Under, Face / FMath::Max(Under, 1e-6)));
	TestTrue(TEXT("Nothing ahead of the lip"), Outside < 0.05);
	TestTrue(TEXT("Full density within 100 m of the lip (a crisp edge)"), Inside > 0.9);
	TestTrue(TEXT("The shelf's front face is at least three times as bright as its underside"), Face > 3.0 * Under);
	return true;
}

/**
 * W8 (storm from the sunshine): ahead of the front the boat is in the sun until the shelf is close. The anvil spreading
 * ahead is a thin ice veil (FStormShape::AnvilDensity, AnvilIceExtinction), so the direct sun (FWeatherMap::
 * SunTransmittance) reaches the water 4 km and more ahead of the front with the sun 70 deg off the storm's track, and is
 * cut once the shelf and the core are overhead; the sky's gloom (FWeatherState::LocalizeStorm) follows the shelf, not the
 * clock. Fair cumulus fade out near the front (FStormShape::CumulusFade).
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSkyStormSunshineTest, "SailingSim.Visual.StormSunshine", SkyFlags)
bool FSkyStormSunshineTest::RunTest(const FString&)
{
	FWeatherSystem Weather;
	Weather.Configure(EWeatherPreset::Thunderstorm, 3, 15.0, 0.0, 0.0);
	const double T = FWeatherSystem::kFrontArrives;   // full build; the front is over the start
	FWeatherState S = Weather.Evaluate(T);
	const FGustFront& F = S.Front;
	if (!TestTrue(TEXT("The storm is on"), F.bActive)) return false;
	// The storm's shade alone (a fair cumulus cell's shadow can fall anywhere ahead).
	S.Sky[ECloudLayer::Cumulus].Coverage = 0.0;
	FWeatherMap Map;
	Map.Paint(S.Sky, F, 0.0, 0.0, T);
	const double Move = F.MoveDegrees * kDegToRad;
	const double Mx = FMath::Cos(Move), My = FMath::Sin(Move);
	// The round's stills: 15:00 on Oct 15, the sun at 41 deg from 218 (72 deg off the storm's 290).
	const double E = 41.0 * kDegToRad, A = 218.0 * kDegToRad;
	const double Sx = FMath::Cos(E) * FMath::Cos(A), Sy = FMath::Cos(E) * FMath::Sin(A), Sz = FMath::Sin(E);
	const double Travel = F.SpeedMs * (T - F.StartTime);
	FString Line;
	double SunFar = 1.0, SunUnder = 0.0, GloomFar = 0.0, GloomUnder = 1.0;
	for (double D : { 8000.0, 6000.0, 4000.0, 3000.0, 2000.0, 1000.0, 0.0, -1000.0 })
	{
		const double X = D * Mx, Y = D * My;
		const double Sun = Map.SunTransmittance(S.Sky, F, Travel, T, X, Y, Sx, Sy, Sz);
		FWeatherState L = S;
		L.Rain = L.RainAt(X, Y, T);
		L.LocalizeStorm(X, Y, T);
		Line += FString::Printf(TEXT(" %.0f km: sun %.2f gloom %.2f;"), D / 1000.0, Sun, L.CloudDarkness);
		if (D >= 4000.0) { SunFar = FMath::Min(SunFar, Sun); }
		if (D >= 3000.0) { GloomFar = FMath::Max(GloomFar, L.CloudDarkness); }
		if (D <= 0.0) { SunUnder = FMath::Max(SunUnder, Sun); GloomUnder = FMath::Min(GloomUnder, L.CloudDarkness); }
	}
	AddInfo(TEXT("Ahead of the front:") + Line);
	TestTrue(TEXT("The sun reaches the water 4 km and more ahead of the front (over 0.7)"), SunFar > 0.7);
	TestTrue(TEXT("Under the shelf and the core the sun is cut (under 0.3)"), SunUnder < 0.3);
	TestTrue(TEXT("No storm gloom 3 km and more ahead (darkness 0.2 or less)"), GloomFar <= 0.2);
	TestTrue(TEXT("Storm gloom under the front (darkness 0.8 or more)"), GloomUnder >= 0.8);
	// Cumulus: full 6 km ahead, gone from 1.5 km ahead to well behind the front.
	TestTrue(TEXT("Cumulus far ahead stay"), FStormShape::CumulusFade(6000.0, 1.0) > 0.99);
	TestTrue(TEXT("Cumulus near the front are gone"), FStormShape::CumulusFade(1000.0, 1.0) < 0.01 && FStormShape::CumulusFade(-5000.0, 1.0) < 0.01);
	return true;
}

#include "LakeData.h"
#include "TreePlacement.h"

/**
 * The shore's trees stand where the canopy map has trees (Visual V6): over the lake bake, the trees per hectare in each
 * 100 m cell follow the baked canopy (correlation over 0.8), none stand in the water or where the canopy is bare, and
 * every species of the lake's mix appears (T2 species: the cross timbers' six, the waterline willows and cottonwoods fewer).
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWorldCanopyTest, "SailingSim.Visual.Canopy", SkyFlags)
bool FWorldCanopyTest::RunTest(const FString&)
{
	FLakeData Lake;
	if (!TestTrue(TEXT("Lake data loads"), Lake.Load(FLakeData::DefaultDirectory(), TEXT("RayHubbard")))) return false;
	const FLakeTerrain& T = Lake.Terrain;
	TArray<FTreeInstance> Trees;
	PlaceTreeInstances(T, 1.f, Trees, ETreeRegion::CrossTimbers);
	TestTrue(TEXT("Trees placed"), Trees.Num() > 10000);
	// Count per 100 m cell.
	TMap<FIntPoint, int32> Counts;
	int32 InWater = 0, OnBare = 0, Species[int32(ETreeSpecies::Count)] = {};
	for (const FTreeInstance& I : Trees)
	{
		Counts.FindOrAdd(FIntPoint(FMath::FloorToInt(I.Position.X / 100.0), FMath::FloorToInt(I.Position.Y / 100.0)))++;
		InWater += T.HeightAt(I.Position.X, I.Position.Y) < 0.0;
		OnBare += T.CanopyAt(I.Position.X, I.Position.Y) <= 0.0;
		Species[int32(I.Species)]++;
	}
	// Correlate the count with the mean canopy over cells with trees.
	double Sx = 0, Sy = 0, Sxx = 0, Syy = 0, Sxy = 0;
	int32 N = 0;
	TSet<FIntPoint> Cells;
	for (const auto& KV : Counts) Cells.Add(KV.Key);
	for (const FIntPoint& Cell : Cells)
	{
		// Cells wholly on dry land (the shore's water's-edge cells lose their trees to the 0.8 m rule).
		double Canopy = 0.0;
		bool bLand = true;
		for (int32 I = 0; I < 5; ++I)
			for (int32 J = 0; J < 5; ++J)
			{
				const double X = Cell.X * 100.0 + 10.0 + I * 20.0, Y = Cell.Y * 100.0 + 10.0 + J * 20.0;
				Canopy += T.CanopyAt(X, Y) / 25.0;
				bLand &= T.HeightAt(X - 10.0, Y - 10.0) > 1.0 && T.HeightAt(X + 10.0, Y + 10.0) > 1.0;
			}
		if (!bLand) continue;
		const double C = Counts.FindRef(Cell);
		Sx += Canopy; Sy += C; Sxx += Canopy * Canopy; Syy += C * C; Sxy += Canopy * C; ++N;
	}
	const double Corr = (N * Sxy - Sx * Sy) / FMath::Sqrt(FMath::Max((N * Sxx - Sx * Sx) * (N * Syy - Sy * Sy), 1e-9));
	AddInfo(FString::Printf(TEXT("%d trees in %d cells: correlation with the canopy %.2f; in water %d, on bare ground %d; live oak %d, post oak %d, cedar elm %d, red cedar %d, sugarberry %d, black willow %d, cottonwood %d"),
		Trees.Num(), N, Corr, InWater, OnBare, Species[0], Species[1], Species[2], Species[3], Species[4], Species[5], Species[6]));
	TestTrue(TEXT("Tree counts follow the canopy map"), Corr > 0.8);
	TestEqual(TEXT("No trees in the water"), InWater, 0);
	TestTrue(TEXT("Hardly any on bare ground (edges of canopy cells)"), OnBare < Trees.Num() / 50);
	for (ETreeSpecies S : { ETreeSpecies::LiveOak, ETreeSpecies::PostOak, ETreeSpecies::CedarElm, ETreeSpecies::RedCedar, ETreeSpecies::Sugarberry })
		TestTrue(TEXT("Every upland species grows"), Species[int32(S)] > Trees.Num() / 20);
	TestTrue(TEXT("Black willows by the water"), Species[int32(ETreeSpecies::BlackWillow)] > Trees.Num() / 400);
	TestTrue(TEXT("Cottonwoods by the water"), Species[int32(ETreeSpecies::Cottonwood)] > Trees.Num() / 400);
	TestEqual(TEXT("No salt cedar on the lake"), Species[int32(ETreeSpecies::SaltCedar)], 0);
	return true;
}

/**
 * T2 species (docs/trees-2): each world's own mix. The lake's black willows and cottonwoods stand only on the low ground by
 * the water and the willows lean toward it (their models lean to +X: the yaw turns that side downhill); Galveston grows
 * live oak most, salt cedar on its low ground, and no post oak, red cedar, willow or cottonwood; Marseille keeps V6's four.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWorldTreeSpeciesTest, "SailingSim.Visual.TreeSpecies", SkyFlags)
bool FWorldTreeSpeciesTest::RunTest(const FString&)
{
	TestEqual(TEXT("The lake is cross timbers"), int32(TreeRegionFor(TEXT("RayHubbard"))), int32(ETreeRegion::CrossTimbers));
	TestEqual(TEXT("Galveston is Gulf coast"), int32(TreeRegionFor(TEXT("GalvestonBay"))), int32(ETreeRegion::GulfCoast));
	TestEqual(TEXT("The Texas coast is Gulf coast"), int32(TreeRegionFor(TEXT("TexasCoast"))), int32(ETreeRegion::GulfCoast));
	TestEqual(TEXT("Marseille keeps the classic mix"), int32(TreeRegionFor(TEXT("Marseille"))), int32(ETreeRegion::Classic));

	FLakeData Lake;
	if (!TestTrue(TEXT("Lake data loads"), Lake.Load(FLakeData::DefaultDirectory(), TEXT("RayHubbard")))) return false;
	const FLakeTerrain& T = Lake.Terrain;
	TArray<FTreeInstance> Trees;
	PlaceTreeInstances(T, 1.f, Trees, ETreeRegion::CrossTimbers);
	int32 Waterline = 0, HighWaterline = 0, Willows = 0, Facing = 0;
	for (const FTreeInstance& I : Trees)
	{
		if (I.Species != ETreeSpecies::BlackWillow && I.Species != ETreeSpecies::Cottonwood) continue;
		++Waterline;
		HighWaterline += I.Ground >= 2.5f;
		if (I.Species != ETreeSpecies::BlackWillow) continue;
		const double GX = T.HeightAt(I.Position.X + 10.0, I.Position.Y) - T.HeightAt(I.Position.X - 10.0, I.Position.Y);
		const double GY = T.HeightAt(I.Position.X, I.Position.Y + 10.0) - T.HeightAt(I.Position.X, I.Position.Y - 10.0);
		if (GX * GX + GY * GY < 0.01) continue;
		++Willows;
		const FVector2D Lean(FMath::Cos(FMath::DegreesToRadians(I.Yaw)), FMath::Sin(FMath::DegreesToRadians(I.Yaw)));
		Facing += FVector2D::DotProduct(Lean, FVector2D(-GX, -GY).GetSafeNormal()) > 0.85;
	}
	AddInfo(FString::Printf(TEXT("Lake: %d waterline trees (%d above 2.5 m), %d willows on a slope, %d leaning downhill"), Waterline, HighWaterline, Willows, Facing));
	TestTrue(TEXT("Waterline trees grow"), Waterline > 100);
	TestEqual(TEXT("Willows and cottonwoods only by the water"), HighWaterline, 0);
	TestTrue(TEXT("Willows lean toward the water"), Willows > 0 && Facing >= Willows * 95 / 100);

	TArray<FTreeInstance> Classic;
	PlaceTreeInstances(T, 1.f, Classic, ETreeRegion::Classic);
	int32 New = 0;
	for (const FTreeInstance& I : Classic) New += int32(I.Species) > int32(ETreeSpecies::RedCedar);
	TestEqual(TEXT("The classic mix is V6's four species"), New, 0);

	FLakeData Bay;
	if (!TestTrue(TEXT("Galveston Bay data loads"), Bay.Load(FLakeData::DefaultDirectory(), TEXT("GalvestonBay")))) return false;
	TArray<FTreeInstance> Coast;
	if (Bay.Crowns.Num() > 0) PlaceCrownTrees(Bay.Terrain, Bay.Crowns, 1.f, Coast, ETreeRegion::GulfCoast);
	else PlaceTreeInstances(Bay.Terrain, 1.f, Coast, ETreeRegion::GulfCoast);
	int32 Species[int32(ETreeSpecies::Count)] = {}, SaltHigh = 0;
	for (const FTreeInstance& I : Coast)
	{
		Species[int32(I.Species)]++;
		SaltHigh += I.Species == ETreeSpecies::SaltCedar && Bay.Terrain.HeightAt(I.Position.X, I.Position.Y) > 6.0;
	}
	AddInfo(FString::Printf(TEXT("Galveston: %d trees; live oak %d, sugarberry %d, cedar elm %d, salt cedar %d (%d above 6 m)"), Coast.Num(),
		Species[int32(ETreeSpecies::LiveOak)], Species[int32(ETreeSpecies::Sugarberry)], Species[int32(ETreeSpecies::CedarElm)], Species[int32(ETreeSpecies::SaltCedar)], SaltHigh));
	TestTrue(TEXT("Galveston has trees"), Coast.Num() > 1000);
	for (ETreeSpecies S : { ETreeSpecies::PostOak, ETreeSpecies::RedCedar, ETreeSpecies::BlackWillow, ETreeSpecies::Cottonwood })
		TestEqual(TEXT("No cross-timbers or lake-waterline species on the coast"), Species[int32(S)], 0);
	const int32 Most = FMath::Max(FMath::Max(Species[int32(ETreeSpecies::Sugarberry)], Species[int32(ETreeSpecies::CedarElm)]), Species[int32(ETreeSpecies::SaltCedar)]);
	TestTrue(TEXT("Live oak the commonest"), Species[int32(ETreeSpecies::LiveOak)] > Most);
	TestTrue(TEXT("Salt cedar grows"), Species[int32(ETreeSpecies::SaltCedar)] > Coast.Num() / 100);
	TestTrue(TEXT("Salt cedar mostly on the low ground"), SaltHigh < Species[int32(ETreeSpecies::SaltCedar)] / 4);
	return true;
}
#if WITH_EDITORONLY_DATA
#include "Engine/VolumeTexture.h"
#include "Engine/Texture2D.h"

namespace
{
	/** A texture's source texels (BGRA8), for sampling on the CPU the way the cloud shader samples on the GPU. */
	struct FSourceTexels
	{
		int32 X = 0, Y = 0, Z = 0;
		TArray64<uint8> Data;
		bool Load(UTexture* Tex)
		{
			if (!Tex || Tex->Source.GetFormat() != TSF_BGRA8) return false;
			X = Tex->Source.GetSizeX();
			Y = Tex->Source.GetSizeY();
			Z = FMath::Max(1, Tex->Source.GetNumSlices());
			return Tex->Source.GetMipData(Data, 0) && Data.Num() >= int64(X) * Y * Z * 4;
		}
		/** Channel (0 R, 1 G, 2 B, 3 A) at texel coordinates, wrapped. */
		float At(int32 I, int32 J, int32 K, int32 Channel) const
		{
			I = ((I % X) + X) % X; J = ((J % Y) + Y) % Y; K = ((K % Z) + Z) % Z;
			static const int32 Bgra[4] = { 2, 1, 0, 3 };
			return Data[((int64(K) * Y + J) * X + I) * 4 + Bgra[Channel]] / 255.f;
		}
		/** Trilinear (bilinear for a 2D texture) at uv in tiles. */
		float Sample(double U, double V, double W, int32 Channel) const
		{
			const double Fx = U * X - 0.5, Fy = V * Y - 0.5, Fz = W * Z - 0.5;
			const int32 I = FMath::FloorToInt32(Fx), J = FMath::FloorToInt32(Fy), K = FMath::FloorToInt32(Fz);
			const float Tx = float(Fx - I), Ty = float(Fy - J), Tz = float(Fz - K);
			auto Plane = [&](int32 Kk) { return FMath::Lerp(FMath::Lerp(At(I, J, Kk, Channel), At(I + 1, J, Kk, Channel), Tx), FMath::Lerp(At(I, J + 1, Kk, Channel), At(I + 1, J + 1, Kk, Channel), Tx), Ty); };
			return Z > 1 ? FMath::Lerp(Plane(K), Plane(K + 1), Tz) : Plane(K);
		}
	};

	/** Highest normalised autocorrelation of a series over a range of lags. */
	double MaxAutocorrelation(const TArray<double>& S, int32 LagFrom, int32 LagTo)
	{
		double Mean = 0.0, Var = 0.0;
		for (double V : S) Mean += V;
		Mean /= S.Num();
		for (double V : S) Var += (V - Mean) * (V - Mean);
		double Best = -1.0;
		for (int32 Lag = LagFrom; Lag <= LagTo; ++Lag)
		{
			double C = 0.0;
			for (int32 I = 0; I + Lag < S.Num(); ++I) C += (S[I] - Mean) * (S[I + Lag] - Mean);
			Best = FMath::Max(Best, C / Var * S.Num() / (S.Num() - Lag));
		}
		return Best;
	}
}

/**
 * Graphics G1: the cloud noise is ours (Tools/clouds/make_cloud_noise.py): the shape and detail volumes and the curl
 * field load at their sizes, and the shape field the shader draws (the shape volume's 4 km tile warped by the 13 km curl
 * field) doesn't repeat: along a 40 km line its autocorrelation stays under 0.5 at every lag from 2 to 15 km, where the
 * unwarped volume repeats exactly every 4 km (the V5 noise every 1.25 km: the same puff over and over). The 1024^2
 * weather map's cumulus field doesn't repeat either, nor do the cumulus billow lobes (T_CloudBillow).
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSkyCloudNoiseTest, "SailingSim.Visual.CloudNoise", SkyFlags)
bool FSkyCloudNoiseTest::RunTest(const FString&)
{
	UVolumeTexture* Shape = LoadObject<UVolumeTexture>(nullptr, TEXT("/Game/Materials/Clouds/T_CloudShape.T_CloudShape"));
	UVolumeTexture* Detail = LoadObject<UVolumeTexture>(nullptr, TEXT("/Game/Materials/Clouds/T_CloudDetail.T_CloudDetail"));
	UTexture2D* Curl = LoadObject<UTexture2D>(nullptr, TEXT("/Game/Materials/Clouds/T_CloudCurl.T_CloudCurl"));
	if (!TestNotNull(TEXT("T_CloudShape (scripts/make-content.sh)"), Shape) || !TestNotNull(TEXT("T_CloudDetail"), Detail) || !TestNotNull(TEXT("T_CloudCurl"), Curl)) return false;
	FSourceTexels S, D, C;
	if (!TestTrue(TEXT("Shape source readable"), S.Load(Shape)) || !TestTrue(TEXT("Detail source readable"), D.Load(Detail)) || !TestTrue(TEXT("Curl source readable"), C.Load(Curl))) return false;
	TestEqual(TEXT("Shape volume 128^3"), S.X * 10000 + S.Y * 100 + S.Z, 128 * 10000 + 128 * 100 + 128);
	TestEqual(TEXT("Detail volume 64^3"), D.X * 10000 + D.Y * 100 + D.Z, 64 * 10000 + 64 * 100 + 64);
	TestEqual(TEXT("Curl 128^2"), C.X * 1000 + C.Y, 128 * 1000 + 128);

	// The shader's sampling (make_materials.py, CLOUD_CODE): q in km; curl at 0.077 cycles/km, +/-1.3 km; shape at 0.25.
	constexpr int32 Count = 800;          // 50 m steps over 40 km
	TArray<double> Plain, Warped;
	for (int32 I = 0; I < Count; ++I)
	{
		const double Qx = 0.05 * I, Qy = 3.1, Qz = 1.8;   // along an axis: the worst case for a tiling volume
		Plain.Add(S.Sample(Qx * 0.25, Qy * 0.25, Qz * 0.25, 0));
		const double Cx = C.Sample(Qx * 0.077, Qy * 0.077, 0.0, 0) * 2.0 - 1.0, Cy = C.Sample(Qx * 0.077, Qy * 0.077, 0.0, 1) * 2.0 - 1.0;
		Warped.Add(S.Sample((Qx + 1.3 * Cx) * 0.25, (Qy + 1.3 * Cy) * 0.25, (Qz + 0.2 * Cx) * 0.25, 0));
	}
	const double PlainRepeat = MaxAutocorrelation(Plain, 40, 300), WarpedRepeat = MaxAutocorrelation(Warped, 40, 300);
	AddInfo(FString::Printf(TEXT("Shape autocorrelation, 2-15 km lags: unwarped %.2f, warped %.2f"), PlainRepeat, WarpedRepeat));
	TestTrue(TEXT("The unwarped volume repeats (sanity: it tiles every 4 km)"), PlainRepeat > 0.8);
	TestTrue(TEXT("The warped shape field doesn't repeat within 15 km"), WarpedRepeat < 0.5);

	// Cumulus billows (docs/cumulus-billows/): the packed lobes, 128^3 over 3 x 3 x 1.5 km. CLOUD_CODE takes out their mean
	// (0.79) so the cells' coverage holds; about a fifth of the volume is crease (under 0.7), so lobes are packed, not
	// solid. Sampled as the shader does (warped q at 1/3 a km), the line doesn't repeat either.
	UVolumeTexture* Billow = LoadObject<UVolumeTexture>(nullptr, TEXT("/Game/Materials/Clouds/T_CloudBillow.T_CloudBillow"));
	FSourceTexels B;
	if (TestNotNull(TEXT("T_CloudBillow"), Billow) && TestTrue(TEXT("Billow source readable"), B.Load(Billow)))
	{
		TestEqual(TEXT("Billow volume 128^3"), B.X * 10000 + B.Y * 100 + B.Z, 128 * 10000 + 128 * 100 + 128);
		double Sum = 0.0;
		int64 Crease = 0;
		for (int32 K = 0; K < B.Z; ++K)
			for (int32 J = 0; J < B.Y; ++J)
				for (int32 I = 0; I < B.X; ++I)
				{
					const float V = B.At(I, J, K, 0);
					Sum += V;
					Crease += V < 0.7f;
				}
		const double Texels = double(B.X) * B.Y * B.Z, Mean = Sum / Texels, CreaseShare = Crease / Texels;
		AddInfo(FString::Printf(TEXT("Billow %dx%dx%d: mean %.3f, crease share %.2f"), B.X, B.Y, B.Z, Mean, CreaseShare));
		TestTrue(TEXT("Billow mean is the shader's 0.79"), FMath::Abs(Mean - 0.79) < 0.02);
		TestTrue(TEXT("Billow lobes are packed with creases between them"), CreaseShare > 0.1 && CreaseShare < 0.4);
		TArray<double> Lobes;
		for (int32 I = 0; I < Count; ++I)
		{
			const double Qx = 0.05 * I, Qy = 3.1, Qz = 1.8;
			const double Cx = C.Sample(Qx * 0.077, Qy * 0.077, 0.0, 0) * 2.0 - 1.0, Cy = C.Sample(Qx * 0.077, Qy * 0.077, 0.0, 1) * 2.0 - 1.0;
			Lobes.Add(B.Sample((Qx + 1.3 * Cx) / 3.0, (Qy + 1.3 * Cy) / 3.0, (Qz + 0.2 * Cx) / 1.5, 0));
		}
		const double LobeRepeat = MaxAutocorrelation(Lobes, 40, 300);
		AddInfo(FString::Printf(TEXT("Billow autocorrelation, 2-15 km lags: %.2f"), LobeRepeat));
		TestTrue(TEXT("The warped billows don't repeat within 15 km"), LobeRepeat < 0.5);
	}

	// The weather map: 1024^2 over 64 km; its cumulus doesn't repeat across a row.
	FWeatherSystem W;
	W.Configure(EWeatherPreset::AfternoonBreeze, 7, 15.0);
	FWeatherMap Map;
	Map.Paint(W.Evaluate(60.0).Sky, FGustFront(), 0.0, 0.0, 0.0);
	TestEqual(TEXT("Weather map 1024^2"), int32(Map.Pixels().size() / 4), FWeatherMap::N * FWeatherMap::N);
	TArray<double> Row;
	for (int32 Col = 0; Col < FWeatherMap::N; ++Col) Row.Add(Map.Pixels()[(size_t(FWeatherMap::N / 2) * FWeatherMap::N + Col) * 4]);
	const double MapRepeat = MaxAutocorrelation(Row, 48, 400);   // 3 to 25 km
	AddInfo(FString::Printf(TEXT("Weather map cumulus autocorrelation, 3-25 km: %.2f"), MapRepeat));
	TestTrue(TEXT("The weather map's cumulus doesn't repeat"), MapRepeat < 0.5);

	// W5a: the cumulus come in many sizes (a power law: many small, few large), not one. Count the clouds (presence over
	// half, 4-connected) by area.
	{
		const int32 N = FWeatherMap::N;
		const double CellKm2 = FMath::Square(FWeatherMap::SizeMeters / N / 1000.0);
		TArray<uint8> Seen;
		Seen.SetNumZeroed(N * N);
		TArray<int32> Stack;
		int32 Small = 0, Mid = 0, Large = 0;
		double Largest = 0.0;
		for (int32 Start = 0; Start < N * N; ++Start)
		{
			if (Seen[Start] || Map.Pixels()[size_t(Start) * 4] < 0.5f) continue;
			int32 Area = 0;
			Stack.Reset();
			Stack.Add(Start);
			Seen[Start] = 1;
			while (Stack.Num())
			{
				const int32 I = Stack.Pop(EAllowShrinking::No);
				++Area;
				const int32 PixR = I / N, PixC = I % N;
				const int32 Next[4] = { PixR > 0 ? I - N : -1, PixR < N - 1 ? I + N : -1, PixC > 0 ? I - 1 : -1, PixC < N - 1 ? I + 1 : -1 };
				for (const int32 J : Next)
				{
					if (J >= 0 && !Seen[J] && Map.Pixels()[size_t(J) * 4] >= 0.5f) { Seen[J] = 1; Stack.Add(J); }
				}
			}
			const double Km2 = Area * CellKm2;
			if (Km2 < 0.05) continue;                // a few texels: noise, not a cloud
			Largest = FMath::Max(Largest, Km2);
			(Km2 < 1.0 ? Small : (Km2 < 4.0 ? Mid : Large)) += 1;
		}
		AddInfo(FString::Printf(TEXT("Cumulus by size: %d under 1 km^2, %d of 1-4 km^2, %d over 4 km^2; the largest %.1f km^2"), Small, Mid, Large, Largest));
		// C1: a fair afternoon's cells stay near 1.5 km in radius (7 km^2 at most); two touching make up to about 12 (the W5a
		// sizes, to 2.5 km in radius, made single clouds of 20 km^2).
		TestTrue(TEXT("Fair-weather cumulus stay small (largest under 15 km^2)"), Largest < 15.0);
		TestTrue(TEXT("Cumulus in many sizes: small ones outnumber mid-sized ones, which outnumber large ones"), Small > Mid && Mid > Large && Large > 0);
	}
	return true;
}

/**
 * T1 (round 12: "shore trees all the same size and colour"): each tree's look is a pure function of its position (the same
 * after a regroup, on the Mac and the PC), spread from yellow-green to blue-green; the evergreens never turn; the season
 * follows the date: green in July, turning by mid-October, at its peak near Thanksgiving, spring's fresh green in April.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWorldTreeLooksTest, "SailingSim.Visual.TreeLooks", SkyFlags)
bool FWorldTreeLooksTest::RunTest(const FString&)
{
	FTreeInstance Tree;
	Tree.Position = FVector2D(1234.5, -678.25);
	Tree.Species = ETreeSpecies::PostOak;
	const FTreeLook A = TreeLookFor(Tree), B = TreeLookFor(Tree);
	TestTrue(TEXT("The same tree, the same look"), A.Tint == B.Tint && A.Deciduous == B.Deciduous && A.LeanPitch == B.LeanPitch);
	double MinTint = 1.0, MaxTint = 0.0, MaxLean = 0.0;
	int32 Turning = 0;
	for (int32 I = 0; I < 2000; ++I)
	{
		FTreeInstance T;
		T.Position = FVector2D(37.0 * I, -11.0 * I + 0.25 * (I % 7));
		T.Species = ETreeSpecies(I % int32(ETreeSpecies::Count));
		const FTreeLook L = TreeLookFor(T);
		MinTint = FMath::Min(MinTint, double(L.Tint));
		MaxTint = FMath::Max(MaxTint, double(L.Tint));
		MaxLean = FMath::Max(MaxLean, double(FMath::Max(FMath::Abs(L.LeanPitch), FMath::Abs(L.LeanRoll))));
		const bool bEvergreen = T.Species == ETreeSpecies::LiveOak || T.Species == ETreeSpecies::RedCedar;
		if (bEvergreen) TestEqual(TEXT("Evergreens never turn"), L.Deciduous, 0.f);
		else Turning += L.Deciduous > 0.3f;
	}
	TestTrue(TEXT("Greens spread across the range"), MinTint < 0.05 && MaxTint > 0.95);
	TestTrue(TEXT("Leans of a few degrees"), MaxLean > 2.0 && MaxLean <= 3.0);
	// Every deciduous tree turns: all but the two evergreens (T2 species: six of the eight species).
	TestEqual(TEXT("Every deciduous tree turns"), Turning, 2000 * (int32(ETreeSpecies::Count) - 2) / int32(ETreeSpecies::Count));
	AddInfo(FString::Printf(TEXT("Autumn: %.2f in July, %.2f on Oct 17, %.2f on Nov 25, %.2f on Jan 10, %.2f on Apr 10; spring %.2f on Apr 5"),
		AutumnAmount(196), AutumnAmount(290), AutumnAmount(329), AutumnAmount(10), AutumnAmount(100), SpringAmount(95)));
	TestEqual(TEXT("Green in July"), AutumnAmount(196), 0.f);
	TestTrue(TEXT("Turning by mid-October"), AutumnAmount(290) > 0.1f && AutumnAmount(290) < 0.5f);
	TestTrue(TEXT("Peak near Thanksgiving"), AutumnAmount(329) > 0.99f);
	TestTrue(TEXT("Fresh green in early April, none in October"), SpringAmount(95) > 0.9f && SpringAmount(290) == 0.f);
	return true;
}
#endif
