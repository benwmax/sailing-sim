#include "WindClimate.h"
#include <algorithm>
#include <vector>

namespace Sailing
{
	namespace
	{
		/**
		 * Tools/wind/fit_gusts.py on 2024 (docs/w1/gust-calibration.csv): per season (DJF, MAM, JJA, SON) and 3-hour bin
		 * from midnight, { lake gust factor over water, coast gust factor (1-minute window), median minutes between puffs,
		 * puff strength (RMS of the 2-minute mean over its 31-minute running mean, times sqrt(0.54) for water) }.
		 * Lake: NCEI ASOS one-minute (TD-6405) at Dallas Love Field, Terrell and Dallas Executive, 5 s peak over the
		 * 2-minute mean for means of 8 kn and up, (GF - 1) times ln(10/0.03)/ln(10/0.0002) = 0.54 for grass to water.
		 * Coast: NOAA CO-OPS 8771341 Galveston Bay Entrance North Jetty, 8771013 Eagle Point, 8770613 Morgans Point,
		 * 6-minute reports, (GF - 1) times 0.76 for the 6-minute peak to a 1-minute one.
		 */
		struct FCell { double Lake, Coast, Puff, Slow; };
		constexpr FCell kTable[4][8] = {
			{ { 1.189, 1.169, 6.0, 0.076 }, { 1.190, 1.182, 6.0, 0.078 }, { 1.188, 1.182, 6.0, 0.082 }, { 1.188, 1.190, 6.0, 0.083 }, { 1.183, 1.195, 6.0, 0.092 }, { 1.178, 1.185, 6.0, 0.085 }, { 1.182, 1.169, 6.0, 0.077 }, { 1.192, 1.166, 6.0, 0.078 } },
			{ { 1.190, 1.166, 6.0, 0.079 }, { 1.189, 1.171, 6.0, 0.087 }, { 1.185, 1.164, 6.0, 0.086 }, { 1.185, 1.170, 6.0, 0.091 }, { 1.188, 1.177, 6.0, 0.100 }, { 1.182, 1.172, 7.0, 0.095 }, { 1.182, 1.165, 6.0, 0.094 }, { 1.190, 1.164, 6.0, 0.080 } },
			{ { 1.188, 1.157, 7.0, 0.076 }, { 1.186, 1.163, 6.0, 0.086 }, { 1.185, 1.159, 6.0, 0.090 }, { 1.187, 1.176, 6.0, 0.100 }, { 1.188, 1.178, 7.0, 0.119 }, { 1.173, 1.174, 7.0, 0.103 }, { 1.165, 1.155, 7.0, 0.085 }, { 1.181, 1.151, 6.0, 0.071 } },
			{ { 1.188, 1.156, 7.0, 0.075 }, { 1.187, 1.162, 6.0, 0.084 }, { 1.183, 1.160, 6.0, 0.080 }, { 1.186, 1.176, 6.0, 0.091 }, { 1.188, 1.180, 7.0, 0.106 }, { 1.175, 1.166, 6.0, 0.098 }, { 1.179, 1.152, 6.0, 0.077 }, { 1.184, 1.155, 6.0, 0.077 } },
		};

		/** The table at a month and hour: linear between the bins' centres (1:30, 4:30, ...) and the seasons' (Jan, Apr, Jul, Oct). */
		template <typename F>
		double Interpolate(int Month, double Hour, F Field)
		{
			const double M = Clamp(double(Month), 1.0, 12.0);
			const double S = std::fmod(M - 1.0 + 12.0, 12.0) / 3.0; // 0 at January (DJF's centre), 1 at April ...
			const int S0 = int(std::floor(S)) % 4, S1 = (S0 + 1) % 4;
			const double TS = S - std::floor(S);
			const double H = std::fmod(std::fmod(Hour, 24.0) + 24.0, 24.0) / 3.0 - 0.5;
			const int B0 = (int(std::floor(H)) + 8) % 8, B1 = (B0 + 1) % 8;
			const double TB = H - std::floor(H);
			auto At = [&](int Season) { return Lerp(Field(kTable[Season][B0]), Field(kTable[Season][B1]), TB); };
			return Lerp(At(S0), At(S1), TS);
		}

		// Monthly normals (1991-2020, NOAA NCEI): Dallas-Fort Worth and Galveston highs and lows, C.
		constexpr double kDfwHigh[12] = { 13.9, 16.1, 20.6, 25.0, 28.9, 33.3, 35.6, 35.6, 31.7, 26.1, 19.4, 14.4 };
		constexpr double kDfwLow[12] = { 2.8, 5.0, 9.4, 13.9, 18.9, 22.8, 25.0, 24.4, 20.6, 14.4, 8.3, 3.9 };
		constexpr double kGlsHigh[12] = { 16.7, 17.8, 21.1, 24.4, 28.3, 31.1, 32.2, 32.8, 30.6, 26.7, 21.7, 17.8 };
		constexpr double kGlsLow[12] = { 10.0, 11.7, 15.0, 18.9, 22.8, 26.1, 27.2, 27.2, 25.0, 20.6, 15.6, 11.1 };
		// C1: dew point normals, monthly means (C), rounded from the NCEI normals for DFW and Galveston (Scholes Field).
		constexpr double kDfwDew[12] = { 0.0, 2.0, 6.0, 11.0, 16.0, 19.5, 20.0, 19.5, 17.0, 11.5, 6.0, 1.5 };
		constexpr double kGlsDew[12] = { 9.0, 10.5, 13.5, 17.0, 21.0, 23.5, 24.0, 24.0, 22.0, 17.0, 13.0, 10.0 };
		// Surface water: north Texas reservoirs (TCEQ / TRA profiles at Lavon and Ray Hubbard) and NOAA's Galveston
		// coastal water temperature guide, monthly means, C.
		constexpr double kLakeWater[12] = { 10.0, 10.5, 14.0, 19.0, 24.0, 28.5, 30.5, 31.0, 28.5, 23.0, 16.5, 11.5 };
		constexpr double kBayWater[12] = { 13.0, 14.0, 18.0, 22.0, 26.0, 29.0, 30.5, 31.0, 29.0, 25.0, 19.5, 15.0 };
		// Afternoon depth of the convective boundary layer over north Texas by month (m; radiosonde climatologies put
		// summer afternoons at 2 km and more, winter near 1 km).
		constexpr double kMixedPeak[12] = { 900.0, 1100.0, 1400.0, 1700.0, 1900.0, 2100.0, 2200.0, 2100.0, 1800.0, 1400.0, 1000.0, 850.0 };

		int MonthIndex(int Month) { return std::min(std::max(Month, 1), 12) - 1; }

		/** The 5-second running mean's highest value in each minute over the 2-minute mean, summed (ASOS TD-6405). */
		void PeaksAndMeans(const std::vector<double>& Hz, double& SumPeak, double& SumMean)
		{
			const int N = int(Hz.size());
			std::vector<double> Run5(N, 0.0), Run120(N, 0.0);
			double S5 = 0.0, S120 = 0.0;
			for (int I = 0; I < N; ++I)
			{
				S5 += Hz[I] - (I >= 5 ? Hz[I - 5] : 0.0);
				S120 += Hz[I] - (I >= 120 ? Hz[I - 120] : 0.0);
				Run5[I] = S5 / std::min(I + 1, 5);
				Run120[I] = S120 / std::min(I + 1, 120);
			}
			for (int M = 2; (M + 1) * 60 <= N; ++M)
			{
				double Peak = 0.0;
				for (int I = M * 60; I < (M + 1) * 60; ++I) Peak = std::max(Peak, Run5[I]);
				SumPeak += Peak;
				SumMean += Run120[(M + 1) * 60 - 1];
			}
		}
	}

	double ClimateGustFactor(int Month, double Hour, bool bCoast)
	{
		return bCoast ? Interpolate(Month, Hour, [](const FCell& C) { return C.Coast; }) : Interpolate(Month, Hour, [](const FCell& C) { return C.Lake; });
	}

	double ClimatePuffMinutes(int Month, double Hour, bool)
	{
		return Interpolate(Month, Hour, [](const FCell& C) { return C.Puff; });
	}

	double ClimatePuffStrength(int Month, double Hour, bool)
	{
		return Interpolate(Month, Hour, [](const FCell& C) { return C.Slow; });
	}

	double ClimateWaterC(int Month, bool bCoast)
	{
		return (bCoast ? kBayWater : kLakeWater)[MonthIndex(Month)];
	}

	double ClimateDewC(int Month, bool bCoast)
	{
		return (bCoast ? kGlsDew : kDfwDew)[MonthIndex(Month)];
	}

	double ClimateAirC(int Month, double Hour, bool bCoast)
	{
		const int M = MonthIndex(Month);
		const double Hi = (bCoast ? kGlsHigh : kDfwHigh)[M], Lo = (bCoast ? kGlsLow : kDfwLow)[M];
		// Coldest near 6:30, warmest near 15:30; the cooling is slower than the warming.
		const double H = std::fmod(std::fmod(Hour, 24.0) + 24.0, 24.0);
		const double Warm = H >= 6.5 && H <= 15.5 ? 0.5 - 0.5 * std::cos((H - 6.5) / 9.0 * kPi)
			: 0.5 + 0.5 * std::cos(std::fmod(H - 15.5 + 24.0, 24.0) / 15.0 * kPi);
		return Lo + (Hi - Lo) * Warm;
	}

	double ClimateMixedLayerM(int Month, double Hour, bool bCoast)
	{
		const double H = std::fmod(std::fmod(Hour, 24.0) + 24.0, 24.0);
		const double Day = SmoothStep(8.5, 14.0, H) * (1.0 - 0.8 * SmoothStep(17.5, 20.5, H));
		const double Land = 250.0 + (kMixedPeak[MonthIndex(Month)] - 250.0) * Day;
		// Over the bay and the Gulf the marine layer is shallower and keeps less of the daily cycle.
		return bCoast ? 500.0 + 0.35 * (Land - 250.0) : Land;
	}

	double GustIntensityForFactor(double GustFactor)
	{
		// FWindField's gust factor rises with its fine turbulence as GF = 1 + kPeak * GI, measured with MeasureGustStats
		// over the presets' conditions (SailingSim.Physics.WindPuffStatistics keeps it honest).
		constexpr double kPeak = 1.58; // 1.50 before the kilometre cells (W1 follow-up): the streaks inside them pass within a minute
		return std::max(GustFactor - 1.0, 0.0) / kPeak;
	}

	FGustStats MeasureGustStats(const FWindField& Wind, double Hours, int Points)
	{
		FGustStats Out;
		const int N = int(Hours * 3600.0);
		const double Mean = Wind.MeanSpeedAtHeight(10.0);
		if (N < 600 || Mean <= 0.0) return Out;
		double SumPeak = 0.0, SumMean = 0.0, Sum = 0.0, Sum2 = 0.0;
		long Count = 0, SlowCount = 0;
		double SlowSum = 0.0;
		std::vector<double> Intervals;
		for (int P = 0; P < Points; ++P)
		{
			// Points 2.7 km apart across the wind (not a multiple of any lane spacing), so they see different puffs.
			const double Ang = Wind.GetParams().FromDegrees * kDegToRad + 0.5 * kPi;
			const double X = std::cos(Ang) * 2737.0 * P, Y = std::sin(Ang) * 2737.0 * P;
			std::vector<double> Hz(N);
			for (int I = 0; I < N; ++I)
			{
				Hz[I] = Wind.VelocityAt(Vec3(X, Y, 10.0), double(I)).LengthXY() / Mean;
				Sum += Hz[I];
				Sum2 += Hz[I] * Hz[I];
				++Count;
			}
			PeaksAndMeans(Hz, SumPeak, SumMean);
			// Puffs: fit_gusts.py's rule on the 2-minute means at 1-minute steps.
			std::vector<double> Two;
			for (int M = 2; (M + 1) * 60 <= N; ++M)
			{
				double S = 0.0;
				for (int I = (M + 1) * 60 - 120; I < (M + 1) * 60; ++I) S += Hz[I];
				Two.push_back(S / 120.0);
			}
			int Last = -1;
			for (int M = 15; M + 16 < int(Two.size()); ++M)
			{
				double S = 0.0, S2 = 0.0;
				for (int K = M - 15; K <= M + 15; ++K) { S += Two[K]; S2 += Two[K] * Two[K]; }
				const double RM = S / 31.0, SD = std::sqrt(std::max(S2 / 31.0 - RM * RM, 0.0));
				SlowSum += (Two[M] / RM - 1.0) * (Two[M] / RM - 1.0);
				++SlowCount;
				if (Two[M] - RM >= 0.5 * std::max(SD, 0.5 / (Mean / kKnot)) && Two[M] >= Two[M - 1] && Two[M] > Two[M + 1])
				{
					if (Last >= 0 && M - Last >= 2 && M - Last <= 40) Intervals.push_back(M - Last);
					Last = M;
				}
			}
		}
		Out.GustFactor = SumMean > 0.0 ? SumPeak / SumMean : 1.0;
		Out.MeanFactor = Sum / Count;
		Out.SlowRms = SlowCount ? std::sqrt(SlowSum / SlowCount) : 0.0;
		Out.Sigma = std::sqrt(std::max(Sum2 / Count - Out.MeanFactor * Out.MeanFactor, 0.0));
		if (!Intervals.empty())
		{
			std::nth_element(Intervals.begin(), Intervals.begin() + Intervals.size() / 2, Intervals.end());
			Out.PuffMinutes = Intervals[Intervals.size() / 2];
		}
		return Out;
	}
}
