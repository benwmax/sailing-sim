// W5b: storms with measured numbers (the Vicroy microburst, the cold pool's density current, the rain foot) and real
// weather days baked from HRRR and MRMS (docs/w5b/README.md).
#include "Misc/AutomationTest.h"
#include "Algo/Reverse.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Storm.h"
#include "Weather.h"
#include "WeatherDay.h"
#include "Wind.h"

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

#endif
