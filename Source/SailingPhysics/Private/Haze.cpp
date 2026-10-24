#include "Haze.h"
#include <algorithm>

namespace Sailing
{
	double FHaze::FogDensity(double VisibilityKm)
	{
		return DensityPerInverseKm / std::clamp(VisibilityKm, MinVisibilityKm, MaxVisibilityKm);
	}

	double FHaze::VisibilityKm(double FogDensity)
	{
		const double ExtinctionPerKm = 3.912 / DensityPerInverseKm * FogDensity;
		return 3.912 / std::max(ExtinctionPerKm, 1e-9);
	}

	double FHaze::AerosolExtinctionPerKm(double VisibilityKm)
	{
		return std::max(3.912 / std::clamp(VisibilityKm, MinVisibilityKm, MaxVisibilityKm) - RayleighExtinctionPerKm, 0.0);
	}

	double FHaze::HeightFalloff(double ScaleHeightM)
	{
		return 10.0 / std::max(ScaleHeightM, 1.0);
	}
}
