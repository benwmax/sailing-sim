#pragma once

#include "SailingPhysicsApi.h"
#include <cstddef>
#include <cstdint>
#include <vector>

namespace Sailing
{
	/**
	 * Wide World Rendering PR 4, band D (docs/world-haze): the mountains beyond the far coast ring as seen from the boat.
	 * A 500 m height grid in the map frame (<World>.skyline, Tools/terrain/build_skyline.py); Compute marches it from
	 * the eye along each azimuth between MinM and MaxM for the highest elevation angle, on the curvature code's earth
	 * (drop d^2 / 2R, R = 7/6 of the earth's: refraction included), and where along the ray that summit stands.
	 */
	class SAILINGPHYSICS_API FSkyline
	{
	public:
		static constexpr double EarthR = 7.433e6;

		bool Load(const uint8_t* Data, size_t Size);
		bool IsValid() const { return !Heights.empty(); }
		/** Bilinear height (m) at a map point; 0 off the grid (the sea). */
		double HeightAt(double X, double Y) const;
		/** The highest elevation angle (rad) along one azimuth (rad from north toward east), from an eye at (X, Y, EyeZ),
		 *  marching Step metres from MinM to MaxM; OutDistance is where it stands (m). -pi/2 when nothing is above. */
		double ElevationAngle(double X, double Y, double EyeZ, double Azimuth, double MinM, double MaxM, double Step, double* OutDistance = nullptr) const;
		/** Count azimuths round the horizon (azimuth k at k / Count turns). */
		void Compute(double X, double Y, double EyeZ, int Count, double MinM, double MaxM, std::vector<float>& OutAngles, std::vector<float>& OutDistances) const;

	private:
		int Cols = 0, Rows = 0;
		double Cell = 500.0, OriginX = 0.0, OriginY = 0.0;
		std::vector<int16_t> Heights;
	};
}
