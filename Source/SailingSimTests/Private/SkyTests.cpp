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
	// Summer cumulus: few in the late morning, about a third of the sky mid-afternoon, bases 1.2 to 1.5 km.
	FWeatherSystem W;
	W.Configure(EWeatherPreset::AfternoonBreeze, 7, 10.0);
	const FCloudLayer Morning = W.Evaluate(0.0).Sky[ECloudLayer::Cumulus];
	W.Configure(EWeatherPreset::AfternoonBreeze, 7, 15.5);
	const FCloudLayer Afternoon = W.Evaluate(0.0).Sky[ECloudLayer::Cumulus];
	TestTrue(TEXT("Cumulus build after noon"), Afternoon.Coverage > 0.3 && Morning.Coverage < 0.12);
	TestTrue(TEXT("Summer cumulus bases near 1.2 to 1.5 km"), Morning.BaseKm >= 1.15 && Afternoon.BaseKm <= 1.55 && Afternoon.BaseKm > Morning.BaseKm);
	// Low decks under overcast and rain; the storm's base lower than the fair-weather cumulus.
	W.Configure(EWeatherPreset::Overcast, 7, 13.0);
	TestTrue(TEXT("Overcast is a low stratus deck"), W.Evaluate(0.0).Sky[ECloudLayer::Stratus].Coverage > 0.9 && W.Evaluate(0.0).Sky[ECloudLayer::Stratus].BaseKm < 1.2);
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
	return true;
}
