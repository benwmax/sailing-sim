#pragma once

#include "SailingPhysicsApi.h"

namespace Sailing
{
	/**
	 * Wide World Rendering PR 3 (docs/world-far-lights): how far a light is seen. A light's nominal range is the
	 * distance its luminous intensity carries at 10 nautical miles of meteorological visibility to the night threshold
	 * of 0.2 microlux (IALA E-200-2); Allard's law then gives the illuminance at the eye through any haze,
	 * E = I T^d / d^2, with the transmissivity per mile T = 0.05^(1 / V) (V the visibility in miles: 5% contrast at V).
	 * A light below the sea horizon (geographic range 2.08 (sqrt h + sqrt H) miles, the refracted horizon of the
	 * curvature code) is hidden, only its loom glows in the haze above it.
	 */
	struct SAILINGPHYSICS_API FFarLightMath
	{
		static constexpr double MetresPerMile = 1852.0;
		static constexpr double NightThresholdLux = 2.0e-7;   // a light just picked out against a dark sky
		static constexpr double DayThresholdLux = 1.0e-3;     // against daylight a buoy light is gone

		/** Transmissivity per nautical mile at a meteorological visibility (km). */
		static double TransmissivityPerMile(double VisibilityKm);
		/** Luminous intensity (cd) that carries the nominal range (nm) at 10 nm visibility to the night threshold. */
		static double IntensityForNominalRange(double RangeNm);
		/** Allard's law: illuminance at the eye (lux) from a light of IntensityCd at DistanceM through VisibilityKm. */
		static double IlluminanceLux(double IntensityCd, double DistanceM, double VisibilityKm);
		/** The distance (m) at which a light of HeightM dips under the horizon for an eye EyeM above the water. */
		static double GeographicRangeM(double HeightM, double EyeM);
		/** How bright the light reads, 0 (unseen) to 1 (bold): log of the illuminance over the threshold, three decades. */
		static double Brightness(double IlluminanceLuxAtEye, bool bNight);
	};
}
