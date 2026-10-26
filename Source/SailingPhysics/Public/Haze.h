#pragma once

#include "SailingPhysicsApi.h"

namespace Sailing
{
	/**
	 * Wide World Rendering PR 4 (docs/world-haze): the fog's density for a meteorological visibility. Koschmieder:
	 * visibility = 3.912 / extinction (2% contrast). The exponential height fog was tuned so 25 km is a clear lake day
	 * and 1.5 km a downpour, density = 0.06 / V(km) at the surface, which makes the extinction 65.2 x density per km.
	 * The clamp used to stop at 40 km; a mistral day sees 60 to 80 km, so it stops at 80 km now.
	 */
	struct SAILINGPHYSICS_API FHaze
	{
		static constexpr double DensityPerInverseKm = 0.06;
		static constexpr double MaxVisibilityKm = 80.0;
		static constexpr double MinVisibilityKm = 0.5;

		/** The fog density for a visibility (km), clamped to 0.5..80 km. */
		static double FogDensity(double VisibilityKm);
		/** The visibility (km) the fog shows at a density (Koschmieder: 3.912 / extinction). */
		static double VisibilityKm(double FogDensity);
		/** The fog's height falloff for a haze scale height (m): the density falls by e every ScaleHeightM. Unreal's
		 *  falloff is per 1,000 world units (10 m), so 50 m is today's 0.2. */
		static double HeightFalloff(double ScaleHeightM);

		/** docs/horizon-sky-colour/: clean air's own extinction at the surface (Rayleigh at 550 nm), per km. */
		static constexpr double RayleighExtinctionPerKm = 0.0116;
		/** The aerosol's extinction at the surface (per km) for a visibility: Koschmieder's total less clean air's,
		 *  over the same 0.5..80 km clamp. */
		static double AerosolExtinctionPerKm(double VisibilityKm);

		/** docs/far-haze/: the engine's two fogs at one density. The analytic fog takes density / 1000 per cm in base 2
		 *  (exp2, HeightFogCommon.ush), so its extinction is 100 ln 2 x density per km. Inside its distance (3 km) the
		 *  volumetric fog replaces it, at half the density per cm in base e (VolumetricFog.usf's MatchHeightFogFactor) times
		 *  its extinction scale: 50 x scale x density per km. */
		static double AnalyticExtinctionPerKm(double FogDensity);
		static double VolumetricExtinctionPerKm(double FogDensity, double ExtinctionScale);
		/** The volumetric fog's extinction scale that gives it the analytic fog's extinction, 2 ln 2: the haze over the
		 *  first 3 km thins the shore as the visibility says, and runs on into the analytic fog without a step. */
		static constexpr double VolumetricExtinctionScale = 1.3862943611198906;
	};
}
