// W1: dumps a top-down patch of the wind field (speed factor, direction shift; puffs alone and everything) for
// Tools/wind/plot_field.py. Built and run by Tools/wind/plot_field.sh (standalone, no Unreal).
#include "Weather.h"
#include "Wind.h"
#include "WindClimate.h"
#include <cstdio>
#include <cstdlib>

int main(int Argc, char** Argv)
{
	using namespace Sailing;
	FTurbulenceTile::LoadShared("Content/TerrainData/Wind.mann");
	const int Month = Argc > 1 ? std::atoi(Argv[1]) : 7;
	const double Hour = Argc > 2 ? std::atof(Argv[2]) : 15.0;
	const double Knots = Argc > 3 ? std::atof(Argv[3]) : 12.0;
	FWeatherSystem Weather;
	Weather.Configure(EWeatherPreset::AfternoonBreeze, 5, Hour);
	Weather.SetClimate(Month, false);
	FWeatherState S = Weather.Evaluate(0.0);
	S.Wind.SpeedKnots = Knots;
	S.Wind.FromDegrees = 180.0; // from the south: up the page is north (+X)
	const FWindField Wind(S.Wind);
	const FWindField::FDerived& D = Wind.GetDerived();
	std::printf("# month %d hour %.1f knots %.1f air-water %.1f mixed %.0f gust %.3f puff %.3f across %.0f along %.0f streets %.2f amp %.2f\n", Month, Hour, Knots,
		S.Wind.AirMinusWaterC, S.Wind.MixedLayerMeters, S.Wind.GustIntensity, S.Wind.PuffIntensity, D.PuffAcross, D.PuffAlong, D.Streets, D.PuffAmplitude);
	// Optional fourth argument: half the patch's side (m); the kilometre cells want 6 km.
	const double T = 1800.0, Half = Argc > 4 ? std::atof(Argv[4]) : 2000.0, Step = Half / 80.0;
	for (double X = -Half; X <= Half; X += Step)
	{
		for (double Y = -Half; Y <= Half; Y += Step)
		{
			double PF, PS;
			Wind.PuffAt(X, Y, T, PF, PS);
			const Vec3 V = Wind.VelocityAt(Vec3(X, Y, 10.0), T);
			std::printf("%.0f %.0f %.4f %.3f %.4f %.3f\n", X, Y, PF, PS * kRadToDeg, V.LengthXY() / Wind.MeanSpeedAtHeight(10.0),
				std::atan2(V.Y, V.X) * kRadToDeg); // the air goes north (0) turned toward east (+)
		}
	}
}
