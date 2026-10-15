// W7 numbers: the game's side of Tools/wind/puff_shape.py. Samples the weather's wind at fixed points at 1 Hz the way
// MeasureGustStats does (12 kn, the lake's climate for the month and hour) and prints each point's 2-minute vector-mean
// speed (kn) and from-direction (deg, clockwise) at 1-minute steps, for puff_shape.py --series to analyse with the
// stations' rule. Built and run by scripts/w7-numbers.sh (standalone, no Unreal).
#include "Weather.h"
#include "Wind.h"
#include "WindClimate.h"
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <vector>

int main(int Argc, char** Argv)
{
	using namespace Sailing;
	FTurbulenceTile::LoadShared("Content/TerrainData/Wind.mann");
	const int Month = Argc > 1 ? std::atoi(Argv[1]) : 7;
	const double Hour = Argc > 2 ? std::atof(Argv[2]) : 15.0;
	const double Hours = Argc > 3 ? std::atof(Argv[3]) : 6.0;
	const int Points = Argc > 4 ? std::atoi(Argv[4]) : 6;
	FWeatherSystem Weather;
	Weather.Configure(EWeatherPreset::AfternoonBreeze, 5, Hour);
	Weather.SetClimate(Month, false);
	FWeatherState S = Weather.Evaluate(0.0);
	S.Wind.SpeedKnots = 12.0;
	const FWindField Wind(S.Wind);
	const int N = int(Hours * 3600.0);
	for (int P = 0; P < Points; ++P)
	{
		// Points 2.7 km apart across the wind, as in MeasureGustStats.
		const double Ang = Wind.GetParams().FromDegrees * kDegToRad + 0.5 * kPi;
		const double X = std::cos(Ang) * 2737.0 * P, Y = std::sin(Ang) * 2737.0 * P;
		std::vector<double> Vx(N), Vy(N);
		for (int I = 0; I < N; ++I)
		{
			const Vec3 V = Wind.VelocityAt(Vec3(X, Y, 10.0), double(I));
			Vx[I] = V.X;
			Vy[I] = V.Y;
		}
		for (int M = 2; (M + 1) * 60 <= N; ++M)
		{
			double Sx = 0.0, Sy = 0.0, Sp = 0.0;
			for (int I = (M + 1) * 60 - 120; I < (M + 1) * 60; ++I)
			{
				Sx += Vx[I];
				Sy += Vy[I];
				Sp += std::sqrt(Vx[I] * Vx[I] + Vy[I] * Vy[I]);
			}
			// From-direction: the air goes (north X, east Y); it comes from the opposite way, clockwise from north.
			double From = std::atan2(-Sy, -Sx) * kRadToDeg;
			if (From < 0.0) From += 360.0;
			std::printf("%d %d %.3f %.2f\n", P, M, Sp / 120.0 / kKnot, From);
		}
	}
}
