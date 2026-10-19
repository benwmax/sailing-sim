// W5b: storms with measured numbers (the Vicroy microburst, the cold pool's density current, the rain foot) and real
// weather days baked from HRRR and MRMS (docs/w5b/README.md).
#include "Misc/AutomationTest.h"
#include "Algo/Reverse.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Ocean.h"
#include "ScriptedScene.h"
#include "SailingGameMode.h"
#include "Storm.h"
#include "Weather.h"
#include "WeatherDay.h"
#include "Wind.h"
#include "WindClimate.h"

#if WITH_DEV_AUTOMATION_TESTS

using namespace Sailing;

namespace
{
	constexpr EAutomationTestFlags StormTestFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	std::shared_ptr<const FWeatherDay> LoadDay(const TCHAR* Date)
	{
		TArray<uint8> Bytes;
		const FString Path = FPaths::ProjectContentDir() / TEXT("TerrainData") / TEXT("Weather") / (FString(Date) + TEXT(".wxday"));
		auto Day = std::make_shared<FWeatherDay>();
		if (!FFileHelper::LoadFileToArray(Bytes, *Path) || !Day->LoadFromMemory(Bytes.GetData(), size_t(Bytes.Num()))) return nullptr;
		return Day;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMicroburstShapeTest, "SailingSim.Physics.MicroburstVicroy", StormTestFlags)
bool FMicroburstShapeTest::RunTest(const FString& Parameters)
{
	// Vicroy (NASA TM-104053, 1991): the outflow peaks at um on the ring r = rp at height zm; z* over epsilon is 12.5 (c2 / c1);
	// the flow conserves mass; a downdraft at the centre, an updraft beyond rp 2^(1/(2 alpha)).
	FMicroburst M;
	M.PeakRadiusM = 1000.0;
	M.PeakHeightM = 60.0;
	M.PeakOutflowMs = 20.0;
	double U, V, W;
	M.At(M.PeakRadiusM, 0.0, M.PeakHeightM, U, V, W);
	TestEqual(TEXT("Peak outflow um at (rp, zm)"), U, 20.0, 1e-6);
	TestEqual(TEXT("Radial: no sideways flow on the x axis"), V, 0.0, 1e-9);
	TestEqual(TEXT("z* over epsilon is 12.5"), FMicroburst::C2 / FMicroburst::C1, 12.5, 0.01);
	double BestR = 0.0, BestU = -1.0, BestZ = 0.0, BestUz = -1.0;
	for (double R = 50.0; R <= 3000.0; R += 5.0)
	{
		M.At(R, 0.0, M.PeakHeightM, U, V, W);
		if (U > BestU) { BestU = U; BestR = R; }
	}
	for (double Z = 1.0; Z <= 600.0; Z += 0.5)
	{
		M.At(M.PeakRadiusM, 0.0, Z, U, V, W);
		if (U > BestUz) { BestUz = U; BestZ = Z; }
	}
	AddInfo(FString::Printf(TEXT("Outflow peaks %.1f m/s at r %.0f m (rp 1000) and z %.1f m (zm 60)"), BestU, BestR, BestZ));
	TestTrue(TEXT("Strongest outflow on the ring rp"), FMath::Abs(BestR - M.PeakRadiusM) <= 10.0);
	TestTrue(TEXT("... at the height zm"), FMath::Abs(BestZ - M.PeakHeightM) <= 1.0);
	// Continuity in cylindrical coordinates: (1/r) d(r u)/dr + dw/dz = 0.
	double WorstDiv = 0.0;
	for (const double R : { 300.0, 900.0, 1500.0, 2400.0 })
	{
		for (const double Z : { 10.0, 60.0, 250.0 })
		{
			const double H = 0.5;
			double U1, U2, W1, W2, Dummy;
			M.At(R - H, 0.0, Z, U1, Dummy, Dummy);
			M.At(R + H, 0.0, Z, U2, Dummy, Dummy);
			M.At(R, 0.0, Z - H, Dummy, Dummy, W1);
			M.At(R, 0.0, Z + H, Dummy, Dummy, W2);
			const double Div = ((R + H) * U2 - (R - H) * U1) / (2.0 * H * R) + (W2 - W1) / (2.0 * H);
			WorstDiv = FMath::Max(WorstDiv, FMath::Abs(Div) / (M.PeakOutflowMs / M.PeakRadiusM));
		}
	}
	AddInfo(FString::Printf(TEXT("Largest divergence, relative to um / rp: %.2g"), WorstDiv));
	TestTrue(TEXT("Mass is conserved (to the finite difference's error)"), WorstDiv < 1e-3);
	M.At(0.0, 0.0, 300.0, U, V, W);
	TestTrue(TEXT("Downdraft at the centre"), W < -1.0);
	double WIn, WOut;
	M.At(M.UpdraftRadius() * 0.95, 0.0, 300.0, U, V, WIn);
	M.At(M.UpdraftRadius() * 1.05, 0.0, 300.0, U, V, WOut);
	TestTrue(TEXT("The air turns upward just beyond rp 2^(1/(2 alpha))"), WIn < 0.0 && WOut > 0.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FGustFrontColdPoolTest, "SailingSim.Physics.GustFrontColdPool", StormTestFlags)
bool FGustFrontColdPoolTest::RunTest(const FString& Parameters)
{
	// The preset storm's gust front: a density current (Charba 1974, Wakimoto 1982): measured wind jumps of 10 to 20 m/s and
	// temperature drops of 3 to 8 C; its speed from the cold pool's depth and coldness.
	const double Speed = FWeatherSystem::StormFrontSpeed();
	TestTrue(TEXT("Front speed of a thunderstorm outflow (8 to 16 m/s)"), Speed > 8.0 && Speed < 16.0);
	TestTrue(TEXT("A colder pool runs faster"), FColdPool::FrontSpeed(8.0, 1000.0, 30.0, 0.0) > FColdPool::FrontSpeed(4.0, 1000.0, 30.0, 0.0));
	TestTrue(TEXT("... and a deeper one"), FColdPool::FrontSpeed(6.0, 1500.0, 30.0, 0.0) > FColdPool::FrontSpeed(6.0, 800.0, 30.0, 0.0));
	FWeatherSystem Weather;
	Weather.Configure(EWeatherPreset::Thunderstorm, 11, 16.0);
	Weather.SetClimate(7, false);
	const double T = FWeatherSystem::kFrontArrives + 20.0;
	FWeatherState S = Weather.Evaluate(T);
	S.Wind.GustIntensity = 0.0;
	S.Wind.PuffIntensity = 0.0;
	S.Front.OutflowGustIntensity = 0.0;
	FWindField Wind(S.Wind);
	Wind.SetFront(S.Front);
	const double A = S.Front.MoveDegrees * kDegToRad;
	auto At = [&](double D)
	{
		// The point on the storm's axis D metres ahead of the front at time T.
		const double Off = S.Front.SpeedMs * (T - S.Front.StartTime) + D;
		return Vec3(S.Front.StartX + std::cos(A) * Off, S.Front.StartY + std::sin(A) * Off, 10.0);
	};
	const double Ahead = Wind.VelocityAt(At(800.0), T).LengthXY();
	double Behind = 0.0;
	for (double D = -100.0; D >= -600.0; D -= 50.0) Behind = FMath::Max(Behind, Wind.VelocityAt(At(D), T).LengthXY());
	const double Drop = S.Front.TemperatureDropAt(At(-500.0).X, At(-500.0).Y, T);
	AddInfo(FString::Printf(TEXT("Front %.1f m/s; 10 m wind %.1f m/s ahead, %.1f behind (a jump of %.1f); %.1f C colder; outflow %.0f kn"),
		Speed, Ahead, Behind, Behind - Ahead, Drop, S.Front.OutflowKnots));
	TestTrue(TEXT("Wind jump 10 to 20 m/s across the front"), Behind - Ahead >= 10.0 && Behind - Ahead <= 20.0);
	TestTrue(TEXT("Temperature drop 3 to 8 C behind it"), Drop >= 3.0 && Drop <= 8.0);
	TestEqual(TEXT("Not colder ahead of the front"), S.Front.TemperatureDropAt(At(600.0).X, At(600.0).Y, T), 0.0, 1e-9);
	// The microburst rides in the core behind the front and adds to the outflow there.
	const Vec3 Burst = S.Front.BurstAt(At(-1500.0 + 1200.0).X, At(-1500.0 + 1200.0).Y, 50.0, T);
	TestTrue(TEXT("The microburst blows out from the core toward the front"), Burst.LengthXY() > 5.0
		&& (Burst.X * std::cos(A) + Burst.Y * std::sin(A)) > 0.0);
	// The cloud material's frame is unchanged: DistanceAhead is the same line the shelf, core and anvil follow.
	TestEqual(TEXT("DistanceAhead at the front line is zero"), S.Front.DistanceAhead(At(0.0).X, At(0.0).Y, T), 0.0, 1e-6);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FRainFootTest, "SailingSim.Physics.RainFootAheadOfCore", StormTestFlags)
bool FRainFootTest::RunTest(const FString& Parameters)
{
	// The rain hangs from the core aloft; near the water the outflow sweeps it forward into the rain foot.
	TestTrue(TEXT("The curtain's edge is further ahead at the water than at the cloud base"),
		FStormRain::LeadingEdge(0.0) > FStormRain::LeadingEdge(750.0) + 200.0);
	const double D = 0.5 * (FStormRain::LeadingEdge(0.0) + FStormRain::LeadingEdge(600.0));
	TestTrue(TEXT("Ahead of the core: rain at the water, none aloft"), FStormRain::RateAt(D, 0.0, 0.0) > 5.0 && FStormRain::RateAt(D, 600.0, 0.0) < 0.5);
	TestEqual(TEXT("No rain ahead of the gust front"), FStormRain::RateAt(100.0, 0.0, 0.0), 0.0, 1e-9);
	double Peak = 0.0;
	for (double X = 0.0; X >= -15000.0; X -= 50.0) Peak = FMath::Max(Peak, FStormRain::RateAt(X, 0.0, 0.0));
	AddInfo(FString::Printf(TEXT("Rain foot reaches %.0f m behind the front at the water, %.0f m aloft; peak %.0f mm/h"),
		-FStormRain::LeadingEdge(0.0), -FStormRain::LeadingEdge(750.0), Peak));
	TestTrue(TEXT("A strong storm's core: 50 to 100 mm/h"), Peak >= 50.0 && Peak <= 100.0);
	TestTrue(TEXT("The storm's rain ends at its lateral extent"), FStormRain::RateAt(-1500.0, 0.0, 25000.0) == 0.0);
	// At the start, the rain arrives after the front and lasts until the storm clears.
	FWeatherSystem Weather;
	Weather.Configure(EWeatherPreset::Thunderstorm, 3, 16.0);
	double FirstRain = -1.0;
	for (double T = 0.0; T < FWeatherSystem::kClear; T += 2.0)
	{
		if (Weather.Evaluate(T).Rain > 0.05) { FirstRain = T; break; }
	}
	AddInfo(FString::Printf(TEXT("Rain at the start %.0f s after the gust front"), FirstRain - FWeatherSystem::kFrontArrives));
	TestTrue(TEXT("The rain follows the front by under a minute"), FirstRain > FWeatherSystem::kFrontArrives && FirstRain < FWeatherSystem::kFrontArrives + 60.0);
	const FWeatherState Mid = Weather.Evaluate(FWeatherSystem::kRainStarts + 60.0);
	TestTrue(TEXT("Heavy rain under the core"), Mid.Rain > 0.7);
	TestTrue(TEXT("Dry a few kilometres ahead of the storm at the same moment"), Mid.RainAt(Mid.Front.StartX + std::cos(Mid.Front.MoveDegrees * kDegToRad) * 1e5,
		Mid.Front.StartY + std::sin(Mid.Front.MoveDegrees * kDegToRad) * 1e5, FWeatherSystem::kRainStarts + 60.0) == 0.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FRealDayTest, "SailingSim.Weather.RealDays", StormTestFlags)
bool FRealDayTest::RunTest(const FString& Parameters)
{
	// The three committed days (Content/TerrainData/Weather, Tools/weather): each loads, and its timeline drives the wind,
	// the stability and the sky; the storm day's front and rain replay the radar's.
	for (const TCHAR* Date : { TEXT("2023-06-11"), TEXT("2023-11-20"), TEXT("2025-09-16") })
	{
		const std::shared_ptr<const FWeatherDay> Day = LoadDay(Date);
		if (!TestTrue(FString::Printf(TEXT("%s loads"), Date), Day && Day->IsValid())) continue;
		FWeatherSystem Weather;
		Weather.ConfigureDay(Day, 5, 12.0);
		for (const double Hour : { 12.0, 15.5 })
		{
			const double T = (Hour - 12.0) * 3600.0;
			const FWeatherState S = Weather.Evaluate(T);
			const FWeatherHour H = Day->At(Hour);
			TestEqual(FString::Printf(TEXT("%s %.1f h: the wind is the day's"), Date, Hour), S.Wind.SpeedKnots, H.WindKnots, 1e-6);
			TestEqual(FString::Printf(TEXT("%s %.1f h: the mixed layer is the day's"), Date, Hour), S.Wind.MixedLayerMeters, FMath::Clamp(H.MixedLayerM, 100.0, 4000.0), 1e-6);
			TestEqual(FString::Printf(TEXT("%s %.1f h: high cloud is the day's cirrus"), Date, Hour), S.Sky[ECloudLayer::Cirrus].Coverage, H.CloudHigh, 1e-6);
			FWindField Wind;
			FWeatherSystem::ApplyToWind(S, Wind, T);
			TestEqual(FString::Printf(TEXT("%s %.1f h: the wind field runs on it"), Date, Hour), Wind.MeanSpeedAtHeight(10.0) / kKnot, H.WindKnots, 0.01);
		}
	}
	// The norther: southerly in the morning, from the northwest by evening, and colder.
	if (const std::shared_ptr<const FWeatherDay> N = LoadDay(TEXT("2023-11-20")))
	{
		AddInfo(FString::Printf(TEXT("Norther: %.0f kn from %.0f at 09:00, %.0f kn from %.0f at 21:00; %.1f C then %.1f C"), N->At(9.0).WindKnots,
			N->At(9.0).FromDegrees, N->At(21.0).WindKnots, N->At(21.0).FromDegrees, N->At(9.0).AirC, N->At(21.0).AirC));
		TestTrue(TEXT("Norther: southerly before"), N->At(9.0).FromDegrees > 150.0 && N->At(9.0).FromDegrees < 240.0);
		TestTrue(TEXT("Norther: north-westerly after"), N->At(21.0).FromDegrees > 290.0 || N->At(21.0).FromDegrees < 20.0);
		TestTrue(TEXT("Norther: colder"), N->At(21.0).AirC < N->At(12.0).AirC - 3.0);
	}
	// The storm: its front reaches the start at the hour it reached the lake, the radar rains there then, the stations'
	// cold pool and gust shape it.
	if (const std::shared_ptr<const FWeatherDay> Day = LoadDay(TEXT("2023-06-11")))
	{
		TestTrue(TEXT("Storm day has a storm and radar"), Day->bStorm && Day->HasRadar());
		FWeatherSystem Weather;
		const double StartX = 1200.0, StartY = -800.0;
		Weather.ConfigureDay(Day, 5, Day->StartHour, StartX, StartY);
		const double TArrive = (Day->StormArrivalHour - Day->StartHour) * 3600.0;
		const FWeatherState S = Weather.Evaluate(TArrive);
		AddInfo(FString::Printf(TEXT("Storm: arrives %.2f h, toward %.0f at %.1f m/s, %.1f C cold pool, %.0f kn peak gust, %.0f mm/h peak rain"),
			Day->StormArrivalHour, Day->StormMoveDegrees, Day->StormSpeedMs, Day->ColdPoolDeltaC, Day->PeakGustKnots, Day->PeakRainMmPerHour));
		TestTrue(TEXT("Storm: the front is active as it arrives"), S.Front.bActive);
		TestEqual(TEXT("Storm: the front reaches the start at the real arrival"), S.Front.DistanceAhead(StartX, StartY, TArrive), 0.0, 1.0);
		double MaxRain = 0.0;
		for (double T = TArrive; T < TArrive + 3600.0; T += 60.0) MaxRain = FMath::Max(MaxRain, Weather.Evaluate(T).Rain);
		TestTrue(TEXT("Storm: the radar rains on the start within the hour"), MaxRain > 0.6);
		TestTrue(TEXT("Storm: dark sky as it arrives"), S.CloudDarkness > 0.5 && S.Sky[ECloudLayer::Storm].Coverage > 0.3);
		TestTrue(TEXT("Storm: lightning"), Weather.GetStrikes().size() > 10);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FStormDeterminismTest, "SailingSim.Weather.StormDeterminism", StormTestFlags)
bool FStormDeterminismTest::RunTest(const FString& Parameters)
{
	// The same storm (preset or real day) and seed give the same wind, rain, temperature and lightning, evaluated in any order.
	auto Run = [](FWeatherSystem& Weather, bool bReverse)
	{
		TArray<double> Out;
		TArray<double> Times;
		for (double T = 0.0; T <= 900.0; T += 37.0) Times.Add(T);
		if (bReverse) Algo::Reverse(Times);
		for (const double T : Times)
		{
			const FWeatherState S = Weather.Evaluate(T);
			FWindField Wind;
			FWeatherSystem::ApplyToWind(S, Wind, T);
			const Vec3 V = Wind.VelocityAt(Vec3(300.0, -200.0, 10.0), T);
			Out.Append({ V.X, V.Y, S.Rain, S.RainAt(-900.0, 400.0, T), S.Front.TemperatureDropAt(-900.0, 400.0, T), S.CloudDarkness });
		}
		if (bReverse)
		{
			TArray<double> Back;
			for (int32 I = Out.Num() / 6 - 1; I >= 0; --I) for (int32 K = 0; K < 6; ++K) Back.Add(Out[I * 6 + K]);
			Out = Back;
		}
		for (const FLightningStrike& L : Weather.GetStrikes()) Out.Append({ L.Time, L.X, L.Y });
		return Out;
	};
	FWeatherSystem A, B;
	A.Configure(EWeatherPreset::Thunderstorm, 21, 16.0);
	B.Configure(EWeatherPreset::Thunderstorm, 21, 16.0);
	TestTrue(TEXT("Thunderstorm: the same, in any order"), Run(A, false) == Run(B, true));
	if (const std::shared_ptr<const FWeatherDay> Day = LoadDay(TEXT("2023-06-11")))
	{
		FWeatherSystem C, D;
		C.ConfigureDay(Day, 21, Day->StartHour);
		D.ConfigureDay(LoadDay(TEXT("2023-06-11")), 21, Day->StartHour);
		TestTrue(TEXT("Real storm day: the same, in any order (and from a fresh load)"), Run(C, false) == Run(D, true));
	}
	return true;
}

/**
 * Prologue step 4 (docs/prologue/README.md): the mistral preset. 32 kn gusting 40 measured the way the stations measure
 * it, a cold unstable air with no thunderstorm, light rain from a low fast deck, 5-8 km visibility, the short steep 3.5 m
 * sea; the squall on cue (a step's weather in the scene file) arriving on the scene's clock with a 40 kn front and a line
 * of heavier rain, and the break after it.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMistralPresetTest, "SailingSim.Weather.Mistral", StormTestFlags)
bool FMistralPresetTest::RunTest(const FString& Parameters)
{
	FWeatherSystem Weather;
	Weather.Configure(EWeatherPreset::Mistral, 5, 17.5, 0.0, 0.0);
	Weather.SetClimate(10, true);
	TestEqual(TEXT("Named"), FString(WeatherPresetName(EWeatherPreset::Mistral)), FString(TEXT("Mistral")));
	const FWeatherState W = Weather.Evaluate(30.0);
	AddInfo(FString::Printf(TEXT("Mistral: %.1f kn from %.0f, gust intensity %.3f, puffs %.3f, air %.0f C over %.0f C water, cover %.2f, darkness %.2f, visibility %.1f km, rain %.2f mm/h"),
		W.Wind.SpeedKnots, W.Wind.FromDegrees, W.Wind.GustIntensity, W.Wind.PuffIntensity, W.AirC, W.AirC - W.Wind.AirMinusWaterC, W.CloudCover, W.CloudDarkness,
		W.VisibilityKm, W.RainRateAt(0.0, 0.0, 0.0, 30.0)));
	TestEqual(TEXT("32 kn"), W.Wind.SpeedKnots, FWeatherSystem::kMistralKnots);
	TestEqual(TEXT("From the northwest (the preset's own)"), W.Wind.FromDegrees, FWeatherSystem::kMistralFromDeg);
	TestTrue(TEXT("Cold air over warmer water (unstable: the gusts reach the water)"), W.Wind.AirMinusWaterC < -1.0);
	TestTrue(TEXT("No thunderstorm: no storm cloud, no lightning, no microburst"), W.Sky[ECloudLayer::Storm].Coverage == 0.0 && Weather.GetStrikes().empty() && W.Front.Burst.PeakOutflowMs == 0.0);
	TestTrue(TEXT("Overcast 80-90%"), W.CloudCover >= 0.8 && W.CloudCover <= 0.9);
	const FCloudLayer& St = W.Sky[ECloudLayer::Stratus];
	const FCloudLayer& Cu = W.Sky[ECloudLayer::Cumulus];
	TestTrue(TEXT("A low deck (stratocumulus near 0.5 km) with scud under it"), St.Coverage >= 0.8 && St.BaseKm < 0.7 && Cu.Coverage > 0.0 && Cu.BaseKm < St.BaseKm);
	const double Drift = FMath::Sqrt(W.Sky.DriftX * W.Sky.DriftX + W.Sky.DriftY * W.Sky.DriftY);
	TestTrue(TEXT("... running fast (faster than the surface wind)"), Drift > W.Wind.SpeedKnots * kKnot);
	const double Light = W.RainRateAt(5000.0, 5000.0, 0.0, 30.0);
	TestTrue(TEXT("Light rain, 1-2 mm/h, between squalls"), Light >= 1.0 && Light <= 2.0);
	TestTrue(TEXT("Visibility 5-8 km in it"), W.VisibilityKm >= 5.0 && W.VisibilityKm <= 8.0);

	// The gusts the way the stations measure them: a field built from the preset.
	FWindField Field(W.Wind);
	FWeatherSystem::ApplyToWind(W, Field, 0.0);
	Field.SetFront(FGustFront()); // the squall apart: the gale itself
	const FGustStats G = MeasureGustStats(Field, 1.0, 4);
	AddInfo(FString::Printf(TEXT("Mistral field: mean %.1f kn, gust factor %.2f (5 s peaks to %.1f kn), puffs %.3f, sigma %.3f"), G.MeanFactor * W.Wind.SpeedKnots,
		G.GustFactor, G.GustFactor * G.MeanFactor * W.Wind.SpeedKnots, G.SlowRms, G.Sigma));
	TestTrue(TEXT("Gusting 40: a gust factor of 1.25 within 0.06"), FMath::Abs(G.GustFactor - FWeatherSystem::kMistralGustKnots / FWeatherSystem::kMistralKnots) < 0.06);
	TestTrue(TEXT("... about a 32 kn mean"), FMath::Abs(G.MeanFactor - 1.0) < 0.05);

	// The sea: 3.5 m, short and steep, with the wind.
	FOcean Ocean;
	FOceanParams O;
	O.WindMs = W.Wind.SpeedKnots * kKnot;
	O.WindFromRad = W.Wind.FromDegrees * kDegToRad;
	O.WindSeaHs = W.WindSeaHsM;
	O.WindSeaTp = W.WindSeaTpS;
	O.SwellHs = W.SwellHsM;
	O.SwellTp = W.SwellTpS;
	O.SwellFromRad = W.SwellFromDeg * kDegToRad;
	Ocean.Configure(O);
	const double Lp = 9.81 * W.WindSeaTpS * W.WindSeaTpS / (2.0 * PI);
	AddInfo(FString::Printf(TEXT("Mistral sea: Hs %.2f m (wind sea %.2f at Tp %.1f s, %.0f m long: steepness 1/%.0f), Tm01 %.1f s, swell %.1f m from %.0f"), Ocean.SignificantHeight(),
		Ocean.WindSeaHs(), W.WindSeaTpS, Lp, Lp / W.WindSeaHsM, Ocean.MeanPeriod(), W.SwellHsM, W.SwellFromDeg));
	TestTrue(TEXT("Hs about 3.5 m"), FMath::Abs(Ocean.SignificantHeight() - 3.5) < 0.25);
	TestTrue(TEXT("A short period for the fetch: Tp about 7 s"), W.WindSeaTpS >= 6.0 && W.WindSeaTpS <= 8.0 && Ocean.MeanPeriod() < 8.0);
	TestTrue(TEXT("The older sea runs with the wind"), W.SwellFromDeg == W.Wind.FromDegrees);
	{
		FOcean Default;
		FOceanParams D = O;
		D.WindSeaHs = D.WindSeaTp = 0.0;
		Default.Configure(D);
		TestTrue(TEXT("Without a given sea the ocean is the wind's own, as before (fully developed: higher)"), Default.WindSeaHs() > Ocean.WindSeaHs() + 1.0);
	}

	// Its own timeline when no scene cues it: the squall's front reaches the start at kSquallArrives, the break after.
	{
		const double Arr = FWeatherSystem::kSquallArrives;
		const FWeatherState A = Weather.Evaluate(Arr - 10.0), B = Weather.Evaluate(Arr + 0.5);
		TestTrue(TEXT("Uncued: the squall's wind reaches the start on the preset's timeline"), A.Front.bActive && A.Front.Behind(0.0, 0.0, Arr - 10.0) < 0.05 && B.Front.Behind(0.0, 0.0, Arr + 0.5) >= 0.99);
		TestTrue(TEXT("... and the sky breaks after it"), Weather.Evaluate(FWeatherSystem::kSquallClears + FWeatherSystem::kClearingSeconds + 5.0).CloudCover < 0.5);
	}

	// On cue: the scene's squall step. Its front reaches the boat (here sailing downwind at 8 m/s) the step's in_s after the
	// step begins: when the step's gust trigger (6 kn over the mean, after 10 s) is due.
	FScriptedScene Scene;
	FString Error;
	if (!ASailingGameMode::LoadPrologue(Scene, &Error)) { AddError(Error); return false; }
	const FSceneStep* Squall = nullptr;
	const FSceneStep* Break = nullptr;
	for (const FSceneStep& S : Scene.GetSteps())
	{
		if (S.WeatherCue == "squall") Squall = &S;
		if (S.WeatherCue == "clearing") Break = &S;
	}
	if (!TestNotNull(TEXT("A step brings the squall"), Squall) || !TestNotNull(TEXT("... and one the break"), Break)) return false;
	TestEqual(TEXT("The squall comes with the \"dump the main\" step"), FString(UTF8_TO_TCHAR(Squall->Id.c_str())), FString(TEXT("dump-main")));
	TestEqual(TEXT("The break with \"the break\""), FString(UTF8_TO_TCHAR(Break->Id.c_str())), FString(TEXT("the-break")));
	TestEqual(TEXT("The front is due as the step's gust trigger is"), Squall->WeatherInSeconds, Squall->Trigger.AfterSeconds);
	const double T0 = 75.0, Vx = -8.0;
	auto BoatX = [&](double T) { return Vx * (T - T0); };
	Weather.ApplySceneCue("", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0);
	TestTrue(TEXT("Cued: no squall before its step (the preset's own is off)"), !Weather.Evaluate(FWeatherSystem::kSquallArrives + 5.0).Front.bActive);
	Weather.ApplySceneCue(Squall->WeatherCue, Squall->WeatherInSeconds, T0, BoatX(T0), 0.0, Vx, 0.0);
	const double Due = T0 + Squall->WeatherInSeconds;
	double Crossed = -1.0, Peak = 0.0, Rain = 0.0, Vis = 100.0, Before = 0.0;
	FWindField Live(W.Wind);
	for (double T = T0; T < Due + 40.0; T += 0.1)
	{
		FWeatherState S = Weather.Evaluate(T);
		FWeatherSystem::ApplyToWind(S, Live, T);
		S.LocalizeStorm(BoatX(T), 0.0, T);
		const double In = S.Front.Behind(BoatX(T), 0.0, T);
		if (Crossed < 0.0 && In >= 0.99) Crossed = T;
		const double Kn = Live.VelocityAt(Vec3(BoatX(T), 0.0, 10.0), T).LengthXY() / kKnot;
		if (T < T0 + 1.0) Before = FMath::Max(Before, In);
		if (Crossed > 0.0 && T < Crossed + 20.0) Peak = FMath::Max(Peak, Kn);
		Rain = FMath::Max(Rain, S.RainRateAt(BoatX(T), 0.0, 0.0, T));
		Vis = FMath::Min(Vis, S.VisibilityKm);
	}
	AddInfo(FString::Printf(TEXT("Squall cued at %.0f s for %.0f s: its wind was on the boat at %.1f s, %.1f kn at 10 m in its first 20 s, rain to %.1f mm/h, visibility down to %.1f km (front %.1f m/s)"),
		T0, Squall->WeatherInSeconds, Crossed, Peak, Rain, Vis, FWeatherSystem::SquallFrontSpeed()));
	TestTrue(TEXT("The front reaches her on the step's clock (within a second)"), FMath::Abs(Crossed - Due) < 1.0);
	TestTrue(TEXT("... and none of it is on her as the step begins"), Before < 0.05);
	TestTrue(TEXT("A 40 kn gust front (38-46 kn at 10 m)"), Peak >= 38.0 && Peak <= 46.0);
	TestTrue(TEXT("A line of heavier rain (5-20 mm/h)"), Rain >= 5.0 && Rain <= 20.0);
	TestTrue(TEXT("Lower visibility in the squall (under 4 km)"), Vis < 4.0);
	TestEqual(TEXT("Its phase"), int32(Weather.Evaluate(Due + 5.0).Storm), int32(EStormPhase::GustFront));

	// The break: from the next step's start the outflow eases, the rain stops, the deck breaks up and the gale eases a little.
	const double T1 = Due + 25.0;
	Weather.ApplySceneCue(Break->WeatherCue, Break->WeatherInSeconds, T1, BoatX(T1), 0.0, Vx, 0.0);
	FWeatherState After = Weather.Evaluate(T1 + FWeatherSystem::kClearingSeconds + 5.0);
	After.LocalizeStorm(BoatX(T1 + 50.0), 0.0, T1 + 50.0);
	const FWeatherState During = Weather.Evaluate(T1 - 1.0);
	AddInfo(FString::Printf(TEXT("The break at %.0f s: cover %.2f to %.2f, rain %.1f to %.1f mm/h, visibility %.1f to %.1f km, wind %.1f to %.1f kn"), T1, During.CloudCover,
		After.CloudCover, During.RainRateAt(BoatX(T1), 0.0, 0.0, T1 - 1.0), After.RainRateAt(BoatX(T1 + 50.0), 0.0, 0.0, T1 + 50.0), During.VisibilityKm, After.VisibilityKm,
		During.Wind.SpeedKnots, After.Wind.SpeedKnots));
	TestTrue(TEXT("The squall's outflow has gone"), After.Front.Behind(BoatX(T1 + 50.0), 0.0, T1 + 50.0) < 0.01);
	TestTrue(TEXT("The rain has stopped"), After.RainRateAt(BoatX(T1 + 50.0), 0.0, 0.0, T1 + 50.0) < 0.05);
	TestTrue(TEXT("The sky opens (cover under half) and the harbour shows (visibility 20 km and more)"), After.CloudCover < 0.5 && After.VisibilityKm >= 20.0);
	TestTrue(TEXT("The gale eases a little, no more"), After.Wind.SpeedKnots < During.Wind.SpeedKnots && After.Wind.SpeedKnots > 0.8 * During.Wind.SpeedKnots);
	TestEqual(TEXT("Phase: passed"), int32(After.Storm), int32(EStormPhase::Clear));

	// A restart at the break (no squall cued yet this run) still gets a passed squall and the break; one before the squall
	// takes both back.
	FWeatherSystem Restart;
	Restart.Configure(EWeatherPreset::Mistral, 5, 17.5);
	Restart.ApplySceneCue("clearing", 0.0, 200.0, 0.0, 0.0, 0.0, 0.0);
	TestTrue(TEXT("Restart at the break: clear 50 s on"), Restart.Evaluate(250.0).CloudCover < 0.5 && Restart.Evaluate(250.0).Storm == EStormPhase::Clear);
	Restart.ApplySceneCue("", 0.0, 300.0, 0.0, 0.0, 0.0, 0.0);
	TestTrue(TEXT("Restart before the squall: the gale's deck again, no front"), !Restart.Evaluate(310.0).Front.bActive && Restart.Evaluate(310.0).CloudCover > 0.8);

	// The stand-in world turns the gale to its open water (the Gulf's south); the squall follows it.
	FWeatherSystem Gulf;
	Gulf.Configure(EWeatherPreset::Mistral, 5, 17.5);
	Gulf.SetPrevailingFrom(180.0);
	const FWeatherState GW = Gulf.Evaluate(FWeatherSystem::kSquallArrives + 10.0);
	TestTrue(TEXT("Stand-in: from the south, the squall's outflow and the sea with it"), GW.Wind.FromDegrees == 180.0 && GW.Front.OutflowFromDegrees == 180.0 && GW.SwellFromDeg == 180.0);
	return true;
}

#endif
