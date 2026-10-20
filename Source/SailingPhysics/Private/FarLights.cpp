#include "FarLights.h"
#include <algorithm>
#include <cmath>

namespace Sailing
{
	double FFarLightMath::TransmissivityPerMile(double VisibilityKm)
	{
		const double Miles = std::max(VisibilityKm * 1000.0 / MetresPerMile, 0.05);
		return std::pow(0.05, 1.0 / Miles);
	}

	double FFarLightMath::IntensityForNominalRange(double RangeNm)
	{
		const double R = std::max(RangeNm, 0.5);
		const double D = R * MetresPerMile;
		return NightThresholdLux * D * D / std::pow(TransmissivityPerMile(10.0 * MetresPerMile / 1000.0), R);
	}

	double FFarLightMath::IlluminanceLux(double IntensityCd, double DistanceM, double VisibilityKm)
	{
		const double D = std::max(DistanceM, 1.0);
		return IntensityCd * std::pow(TransmissivityPerMile(VisibilityKm), D / MetresPerMile) / (D * D);
	}

	double FFarLightMath::GeographicRangeM(double HeightM, double EyeM)
	{
		return 2.08 * (std::sqrt(std::max(HeightM, 0.0)) + std::sqrt(std::max(EyeM, 0.0))) * MetresPerMile;
	}

	double FFarLightMath::Brightness(double IlluminanceLuxAtEye, bool bNight)
	{
		const double Threshold = bNight ? NightThresholdLux : DayThresholdLux;
		if (IlluminanceLuxAtEye < Threshold) return 0.0;
		return std::clamp(0.15 + std::log10(IlluminanceLuxAtEye / Threshold) / 3.0, 0.15, 1.0);
	}
}
