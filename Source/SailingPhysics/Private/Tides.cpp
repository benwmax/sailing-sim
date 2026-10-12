#include "Tides.h"
#include <cstring>
#include <unordered_map>

namespace Sailing
{
	namespace
	{
		enum class ENodal { None, M2, K1, O1, K2, J1, OO1, Mm, Mf, MSf, M2Sq, M2Cube, M2Fourth, M2K1, TwoMK3, M3 };

		struct FConstituentDef
		{
			int Mult[6];    // multipliers of T (mean solar hour angle), s, h, p, N', p1
			double Offset;  // degrees
			ENodal Nodal;
		};

		// Schureman's equilibrium arguments with T = 180 + 15 x UT hours.
		const std::unordered_map<std::string, FConstituentDef>& Definitions()
		{
			static const std::unordered_map<std::string, FConstituentDef> Table = {
				{ "M2", { { 2, -2, 2, 0, 0, 0 }, 0, ENodal::M2 } }, { "S2", { { 2, 0, 0, 0, 0, 0 }, 0, ENodal::None } },
				{ "N2", { { 2, -3, 2, 1, 0, 0 }, 0, ENodal::M2 } }, { "K1", { { 1, 0, 1, 0, 0, 0 }, -90, ENodal::K1 } },
				{ "M4", { { 4, -4, 4, 0, 0, 0 }, 0, ENodal::M2Sq } }, { "O1", { { 1, -2, 1, 0, 0, 0 }, 90, ENodal::O1 } },
				{ "M6", { { 6, -6, 6, 0, 0, 0 }, 0, ENodal::M2Cube } }, { "MK3", { { 3, -2, 3, 0, 0, 0 }, -90, ENodal::M2K1 } },
				{ "S4", { { 4, 0, 0, 0, 0, 0 }, 0, ENodal::None } }, { "MN4", { { 4, -5, 4, 1, 0, 0 }, 0, ENodal::M2Sq } },
				{ "NU2", { { 2, -3, 4, -1, 0, 0 }, 0, ENodal::M2 } }, { "S6", { { 6, 0, 0, 0, 0, 0 }, 0, ENodal::None } },
				{ "MU2", { { 2, -4, 4, 0, 0, 0 }, 0, ENodal::M2 } }, { "2N2", { { 2, -4, 2, 2, 0, 0 }, 0, ENodal::M2 } },
				{ "OO1", { { 1, 2, 1, 0, 0, 0 }, -90, ENodal::OO1 } }, { "LAM2", { { 2, -1, 0, 1, 0, 0 }, 180, ENodal::M2 } },
				{ "S1", { { 1, 0, 0, 0, 0, 0 }, 0, ENodal::None } }, { "M1", { { 1, -1, 1, 1, 0, 0 }, -90, ENodal::O1 } },
				{ "J1", { { 1, 1, 1, -1, 0, 0 }, -90, ENodal::J1 } }, { "MM", { { 0, 1, 0, -1, 0, 0 }, 0, ENodal::Mm } },
				{ "SSA", { { 0, 0, 2, 0, 0, 0 }, 0, ENodal::None } }, { "SA", { { 0, 0, 1, 0, 0, 0 }, 0, ENodal::None } },
				{ "MSF", { { 0, 2, -2, 0, 0, 0 }, 0, ENodal::MSf } }, { "MF", { { 0, 2, 0, 0, 0, 0 }, 0, ENodal::Mf } },
				{ "RHO", { { 1, -3, 3, -1, 0, 0 }, 90, ENodal::O1 } }, { "Q1", { { 1, -3, 1, 1, 0, 0 }, 90, ENodal::O1 } },
				{ "T2", { { 2, 0, -1, 0, 0, 1 }, 0, ENodal::None } }, { "R2", { { 2, 0, 1, 0, 0, -1 }, 180, ENodal::None } },
				{ "2Q1", { { 1, -4, 1, 2, 0, 0 }, 90, ENodal::O1 } }, { "P1", { { 1, 0, -1, 0, 0, 0 }, 90, ENodal::None } },
				{ "2SM2", { { 2, 2, -2, 0, 0, 0 }, 0, ENodal::MSf } }, { "M3", { { 3, -3, 3, 0, 0, 0 }, 0, ENodal::M3 } },
				{ "L2", { { 2, -1, 2, -1, 0, 0 }, 180, ENodal::M2 } }, { "2MK3", { { 3, -4, 3, 0, 0, 0 }, 90, ENodal::TwoMK3 } },
				{ "K2", { { 2, 0, 2, 0, 0, 0 }, 0, ENodal::K2 } }, { "M8", { { 8, -8, 8, 0, 0, 0 }, 0, ENodal::M2Fourth } },
				{ "MS4", { { 4, -2, 2, 0, 0, 0 }, 0, ENodal::M2 } },
			};
			return Table;
		}

		void NodalFactors(ENodal Group, double NRad, double& F, double& U)
		{
			const double C1 = std::cos(NRad), C2 = std::cos(2 * NRad), C3 = std::cos(3 * NRad);
			const double S1 = std::sin(NRad), S2 = std::sin(2 * NRad), S3 = std::sin(3 * NRad);
			const double FM2 = 1.0004 - 0.0373 * C1 + 0.0002 * C2, UM2 = -2.14 * S1;
			const double FK1 = 1.0060 + 0.1150 * C1 - 0.0088 * C2 + 0.0006 * C3, UK1 = -8.86 * S1 + 0.68 * S2 - 0.07 * S3;
			const double FO1 = 1.0089 + 0.1871 * C1 - 0.0147 * C2 + 0.0014 * C3, UO1 = 10.80 * S1 - 1.34 * S2 + 0.19 * S3;
			switch (Group)
			{
			case ENodal::M2: F = FM2; U = UM2; break;
			case ENodal::K1: F = FK1; U = UK1; break;
			case ENodal::O1: F = FO1; U = UO1; break;
			case ENodal::K2: F = 1.0241 + 0.2863 * C1 + 0.0083 * C2 - 0.0015 * C3; U = -17.74 * S1 + 0.68 * S2 - 0.04 * S3; break;
			case ENodal::J1: F = 1.1029 + 0.1676 * C1 - 0.0170 * C2 + 0.0016 * C3; U = -12.94 * S1 + 1.34 * S2 - 0.19 * S3; break;
			case ENodal::OO1: F = 1.1027 + 0.6504 * C1 + 0.0317 * C2 - 0.0014 * C3; U = -36.68 * S1 + 4.02 * S2 - 0.57 * S3; break;
			case ENodal::Mm: F = 1.0 - 0.1300 * C1 + 0.0013 * C2; U = 0.0; break;
			case ENodal::Mf: F = 1.0429 + 0.4135 * C1 - 0.004 * C2; U = -23.74 * S1 + 2.68 * S2 - 0.38 * S3; break;
			case ENodal::MSf: F = FM2; U = -UM2; break;
			case ENodal::M2Sq: F = FM2 * FM2; U = 2 * UM2; break;
			case ENodal::M2Cube: F = FM2 * FM2 * FM2; U = 3 * UM2; break;
			case ENodal::M2Fourth: F = FM2 * FM2 * FM2 * FM2; U = 4 * UM2; break;
			case ENodal::M2K1: F = FM2 * FK1; U = UM2 + UK1; break;
			case ENodal::TwoMK3: F = FM2 * FM2 * FK1; U = 2 * UM2 - UK1; break;
			case ENodal::M3: F = std::pow(FM2, 1.5); U = 1.5 * UM2; break;
			default: F = 1.0; U = 0.0; break;
			}
		}

		template <typename T>
		T ReadLE(const uint8_t* P) { T V; std::memcpy(&V, P, sizeof(T)); return V; }
	}

	double UnixSecondsUtc(int Year, int Month, int Day, int Hour, int Minute, double Second)
	{
		// Days from civil (Howard Hinnant's algorithm), proleptic Gregorian calendar.
		const int Y = Year - (Month <= 2 ? 1 : 0);
		const int Era = (Y >= 0 ? Y : Y - 399) / 400;
		const int Yoe = Y - Era * 400;
		const int Doy = (153 * (Month + (Month > 2 ? -3 : 9)) + 2) / 5 + Day - 1;
		const int Doe = Yoe * 365 + Yoe / 4 - Yoe / 100 + Doy;
		const long long Days = (long long)Era * 146097 + Doe - 719468;
		return double(Days) * 86400.0 + Hour * 3600.0 + Minute * 60.0 + Second;
	}

	double PredictTide(const FTideStation& Station, double UnixSeconds)
	{
		// Mean longitudes (degrees) from J2000.0.
		const double Days = (UnixSeconds - 946728000.0) / 86400.0;
		const double Cent = Days / 36525.0;
		const double S = 218.3164477 + 481267.88123421 * Cent;
		const double H = 280.4664567 + 36000.7697489 * Cent;
		const double P = 83.3532465 + 4069.0137287 * Cent;
		const double N = 125.0445479 - 1934.1362891 * Cent;
		const double P1 = 282.9373 + 1.71946 * Cent;
		const double DayFraction = std::fmod(UnixSeconds, 86400.0) / 86400.0;
		const double T = 180.0 + 360.0 * (DayFraction < 0.0 ? DayFraction + 1.0 : DayFraction);
		const double Args[6] = { T, S, H, P, N, P1 };

		double Total = Station.Z0;
		for (const FTideConstituent& C : Station.Constituents)
		{
			if (C.Amplitude == 0.0) continue;
			const auto It = Definitions().find(C.Name);
			if (It == Definitions().end()) continue;
			const FConstituentDef& D = It->second;
			double V = D.Offset;
			for (int I = 0; I < 6; ++I) V += D.Mult[I] * Args[I];
			double F, U;
			NodalFactors(D.Nodal, N * kDegToRad, F, U);
			Total += F * C.Amplitude * std::cos((V + U - C.PhaseDeg) * kDegToRad);
		}
		return Total;
	}

	bool FTideModel::LoadCurrentField(const uint8_t* Data, size_t Size)
	{
		const size_t Header = 4 + 4 + 4 * 2 + 4 * 3;
		if (Size < Header || std::memcmp(Data, "SSCF", 4) != 0) return false;
		Cols = int(ReadLE<uint32_t>(Data + 8));
		Rows = int(ReadLE<uint32_t>(Data + 12));
		Cell = ReadLE<float>(Data + 16);
		OriginX = ReadLE<float>(Data + 20);
		OriginY = ReadLE<float>(Data + 24);
		const size_t N = size_t(Rows) * Cols;
		if (Size < Header + N * 8) { Rows = Cols = 0; return false; }
		DirX.resize(N); DirY.resize(N); Gain.resize(N); Delay.resize(N);
		const uint8_t* P = Data + Header;
		std::memcpy(DirX.data(), P, N * 2); P += N * 2;
		std::memcpy(DirY.data(), P, N * 2); P += N * 2;
		std::memcpy(Gain.data(), P, N * 2); P += N * 2;
		std::memcpy(Delay.data(), P, N * 2);
		return true;
	}

	double FTideModel::HeightAt(double X, double Y, double UnixSeconds) const
	{
		if (HeightStations.empty()) return 0.0;
		// Inverse-distance-squared blend: each station carries its own amplitude and phase.
		double Sum = 0.0, Weights = 0.0;
		for (const FTideStation& S : HeightStations)
		{
			const double D2 = (X - S.X) * (X - S.X) + (Y - S.Y) * (Y - S.Y) + 250000.0; // 500 m softening
			const double W = 1.0 / D2;
			Sum += W * PredictTide(S, UnixSeconds);
			Weights += W;
		}
		return Sum / Weights;
	}

	double FTideModel::StationCurrent(double UnixSeconds) const
	{
		return bHasCurrent ? PredictTide(CurrentStation, UnixSeconds) : 0.0;
	}

	Vec3 FTideModel::CurrentAt(double X, double Y, double UnixSeconds) const
	{
		if (!bHasCurrent || Rows == 0) return Vec3();
		const int R = int(std::floor((X - OriginX) / Cell + 0.5)), C = int(std::floor((Y - OriginY) / Cell + 0.5));
		if (R < 0 || C < 0 || R >= Rows || C >= Cols) return Vec3();
		const size_t I = size_t(R) * Cols + C;
		if (Gain[I] == 0) return Vec3();
		const double Speed = StationCurrent(UnixSeconds - Delay[I]) * (Gain[I] / 1000.0);
		// The field stores the flood direction; an ebb (negative speed) runs the other way.
		return Vec3(DirX[I] / 10000.0, DirY[I] / 10000.0, 0.0) * Speed;
	}
}
