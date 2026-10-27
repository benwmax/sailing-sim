#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "LakeData.h"
#include "Haze.h"
#include "Skyline.h"
#include "Weather.h"

#if WITH_DEV_AUTOMATION_TESTS

// Wide World Rendering PR 4 (docs/world-haze): the haze at range, the far water per world, the mountains past the ring.

using namespace Sailing;

namespace
{
	constexpr EAutomationTestFlags HazeFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWorldHazeTest, "SailingSim.World.Haze", HazeFlags)
bool FWorldHazeTest::RunTest(const FString& Parameters)
{
	// The fog's density gives back the visibility it was set for (Koschmieder, within 10%) out to 80 km: the old clamp
	// stopped at 40 km, so a 60 km mistral day drew 40.
	for (const double V : { 1.5, 4.0, 12.0, 25.0, 40.0, 60.0, 80.0 })
	{
		const double Shown = FHaze::VisibilityKm(FHaze::FogDensity(V));
		TestTrue(FString::Printf(TEXT("%.1f km of visibility shows as %.1f km"), V, Shown), FMath::Abs(Shown / V - 1.0) < 0.1);
	}
	TestTrue(TEXT("Past 80 km the fog stays at 80 km"), FMath::IsNearlyEqual(FHaze::VisibilityKm(FHaze::FogDensity(200.0)), 80.0, 1e-6));
	TestTrue(TEXT("A 50 m haze layer is the fog's old falloff (0.2)"), FMath::IsNearlyEqual(FHaze::HeightFalloff(50.0), 0.2, 1e-9));
	// docs/horizon-sky-colour/: the aerosol is Koschmieder's extinction less clean air's (Rayleigh at 550 nm), never
	// negative; a 25 km lake day carries about 32 times the engine's alpine Mie (0.0044 per km).
	TestTrue(TEXT("25 km of visibility is 0.145 per km of aerosol"), FMath::IsNearlyEqual(FHaze::AerosolExtinctionPerKm(25.0), 3.912 / 25.0 - FHaze::RayleighExtinctionPerKm, 1e-9));
	TestTrue(TEXT("The aerosol thins with the visibility"), FHaze::AerosolExtinctionPerKm(60.0) < FHaze::AerosolExtinctionPerKm(25.0) && FHaze::AerosolExtinctionPerKm(1.5) > 2.0);
	TestTrue(TEXT("Past 80 km it stays at 80 km's, above clean air"), FMath::IsNearlyEqual(FHaze::AerosolExtinctionPerKm(500.0), FHaze::AerosolExtinctionPerKm(80.0), 1e-12) && FHaze::AerosolExtinctionPerKm(80.0) > 0.0);

	// docs/far-haze/: the volumetric fog draws the first 3 km, the analytic fog beyond. At the shipped scale both thin a
	// shore as Koschmieder says for the visibility (within 10%), and the extinction runs on through 3 km without a step.
	// The old scale (0.12 to 0.3) left 3 km of shore at 94% of its contrast on a 25 km day, against Koschmieder's 63%.
	for (const double V : { 4.0, 12.0, 25.0, 60.0 })
	{
		const double Density = FHaze::FogDensity(V);
		const double Vol = FHaze::VolumetricExtinctionPerKm(Density, FHaze::VolumetricExtinctionScale);
		const double Ana = FHaze::AnalyticExtinctionPerKm(Density);
		TestTrue(FString::Printf(TEXT("%.0f km: the fogs meet at 3 km without a step"), V), FMath::IsNearlyEqual(Vol, Ana, 1e-9 * Ana));
		for (const double D : { 1.0, 3.0 })
		{
			const double Shown = FMath::Exp(-Vol * D), Koschmieder = FMath::Exp(-3.912 * D / V);
			TestTrue(FString::Printf(TEXT("%.0f km: a shore %.0f km off keeps %.2f of its contrast (Koschmieder %.2f)"), V, D, Shown, Koschmieder),
				FMath::Abs(FMath::Loge(Shown) / FMath::Loge(Koschmieder) - 1.0) < 0.1);
		}
	}
	TestTrue(TEXT("The old scale was five times too clear"), FHaze::VolumetricExtinctionPerKm(1.0, 0.3) < 0.25 * FHaze::AnalyticExtinctionPerKm(1.0));

	// The clear mistral: cloudless, 60 km, a northwesterly near 24 kn.
	FWeatherSystem Weather;
	Weather.Configure(EWeatherPreset::ClearMistral, 3, 14.0);
	Weather.SetClimate(10, true);
	const FWeatherState W = Weather.Evaluate(60.0);
	AddInfo(FString::Printf(TEXT("Clear mistral: %.0f kn from %.0f, visibility %.0f km, cover %.2f, haze %.2f"), W.Wind.SpeedKnots, W.Wind.FromDegrees,
		W.VisibilityKm, W.CloudCover, W.Sky.Haze));
	TestEqual(TEXT("Named"), FString(WeatherPresetName(EWeatherPreset::ClearMistral)), FString(TEXT("Clear mistral")));
	TestTrue(TEXT("60 km of visibility"), FMath::IsNearlyEqual(W.VisibilityKm, 60.0, 0.5));
	TestTrue(TEXT("Cloudless"), W.CloudCover < 0.1 && W.Rain <= 0.0);
	TestTrue(TEXT("A northwesterly"), W.Wind.FromDegrees > 290.0 && W.Wind.FromDegrees < 340.0 && W.Wind.SpeedKnots > 18.0 && W.Wind.SpeedKnots < 30.0);

	// The far water and the haze layer per world.
	FLakeData Marseille, Galveston;
	TestTrue(TEXT("Marseille loads"), Marseille.Load(FLakeData::DefaultDirectory(), TEXT("Marseille")));
	TestTrue(TEXT("Galveston loads"), Galveston.Load(FLakeData::DefaultDirectory(), TEXT("GalvestonBay")));
	TestTrue(TEXT("Marseille's far plane is 60 km across"), FMath::IsNearlyEqual(Marseille.FarPlaneKm, 60.0));
	TestTrue(TEXT("The Texas coast keeps 40 km"), FMath::IsNearlyEqual(Galveston.FarPlaneKm, 40.0));
	TestTrue(TEXT("Marseille's haze layer is 400 m; Galveston keeps the fog's own"), FMath::IsNearlyEqual(Marseille.FogScaleHeightM, 400.0) && Galveston.FogScaleHeightM <= 0.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWorldSkylineTest, "SailingSim.World.Skyline", HazeFlags)
bool FWorldSkylineTest::RunTest(const FString& Parameters)
{
	TArray<uint8> Bytes;
	FSkyline Sky;
	if (!TestTrue(TEXT("Marseille.skyline loads"), FFileHelper::LoadFileToArray(Bytes, *(FLakeData::DefaultDirectory() / TEXT("Marseille.skyline")))
		&& Sky.Load(Bytes.GetData(), Bytes.Num()))) return false;
	FLakeData Lake;
	Lake.Load(FLakeData::DefaultDirectory(), TEXT("Marseille"));
	// The march the game runs (2048 azimuths, half-cell steps from 45 to 160 km) against a fine brute force over the
	// same grid (100 m steps), from the Vieux-Port's entrance at a 2.5 m eye.
	constexpr int32 Count = 2048;
	std::vector<float> Angles, Distances;
	const double Start = FPlatformTime::Seconds();
	Sky.Compute(0.0, 0.0, 2.5, Count, 45000.0, 160000.0, Angles, Distances);
	AddInfo(FString::Printf(TEXT("Skyline marched in %.1f ms"), (FPlatformTime::Seconds() - Start) * 1000.0));
	double Worst = 0.0;
	int32 Land = 0;
	for (int32 K = 0; K < Count; K += 16)
	{
		const double Fine = Sky.ElevationAngle(0.0, 0.0, 2.5, 2.0 * UE_DOUBLE_PI * K / Count, 45000.0, 160000.0, 100.0);
		if (Fine < -1.0) continue;
		++Land;
		Worst = FMath::Max(Worst, FMath::Abs(FMath::RadiansToDegrees(Fine - double(Angles[K]))));
	}
	AddInfo(FString::Printf(TEXT("%d azimuths with land past 45 km, worst %.3f deg from the fine march"), Land, Worst));
	TestTrue(TEXT("Mountains past the ring on many bearings"), Land > 20);
	TestTrue(TEXT("The skyline matches the DEM's elevation angles within 0.1 deg"), Worst < 0.1);

	// Mont Ventoux (1,909 m, 97 km north): on the skyline, a little under a degree up after the earth's curve.
	const FMapPoint Ventoux = Lake.Anchor.ToMap(FLatLon{ 44.1739, 5.2789 });
	const double Az = FMath::Atan2(Ventoux.East, Ventoux.North);
	const int32 Bin = (int32(FMath::RoundToInt(Az / (2.0 * UE_DOUBLE_PI) * Count)) % Count + Count) % Count;
	const double Expected = FMath::Atan2(1909.0 - FMath::Square(97000.0) / (2.0 * FSkyline::EarthR) - 2.5, 97000.0);
	AddInfo(FString::Printf(TEXT("Mont Ventoux: bearing %.1f deg, skyline %.2f deg at %.0f km (its summit alone %.2f deg)"),
		FMath::RadiansToDegrees(Az < 0 ? Az + 2 * UE_DOUBLE_PI : Az), FMath::RadiansToDegrees(Angles[Bin]), Distances[Bin] / 1000.0, FMath::RadiansToDegrees(Expected)));
	TestTrue(TEXT("Ventoux stands on the skyline (within 0.15 deg of its summit's angle)"), FMath::Abs(FMath::RadiansToDegrees(Angles[Bin] - Expected)) < 0.15);
	return true;
}

#endif
