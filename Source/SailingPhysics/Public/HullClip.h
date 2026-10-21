#pragma once

#include "SailingPhysicsApi.h"
#include "BoatModel.h"

#include <vector>

namespace Sailing
{
	/**
	 * The water's hull clip (docs/boat-water-clip/): every hull of a boat on one grid in her body frame, which
	 * M_WaterV4 reads (AWaterSurface::UpdateHullClip) to drop the drawn sea below her bottom wherever it is inside a
	 * hull. One map serves every boat: a catamaran's two hulls, a trimaran's amas and the maxi's sections
	 * (FHullShape::Stations) are all just texels, and the water between the hulls stays.
	 *
	 * Each texel (column along X, row along Y) holds four floats for the hull nearest to being around it:
	 * the bottom's height (FHullShape::BottomZ, the sheer past the deck edge), the sheer's height, the side margin
	 * (m inside the deck edge, negative outside; past the ends, the end section's) and the end margin (m inside the bow
	 * and the transom). The GPU samples it bilinearly; Sample does the same, so the tests hold what the shader sees.
	 */
	struct SAILINGPHYSICS_API FHullClipMap
	{
		static constexpr int Cols = 256;
		static constexpr int Rows = 128;

		struct FTexel
		{
			float Bottom = 0.f, Sheer = 0.f, Side = -1.f, End = -1.f;
		};

		double X0 = 0.0, Y0 = 0.0, SizeX = 1.0, SizeY = 1.0; // the grid's corner and size (m, body frame)
		double MainDepth = 0.0;                               // the canoe depth it was built for
		std::vector<FTexel> Texels;                           // Rows x Cols, row major

		/** Builds the map for these hulls at this canoe depth (FBoatModel::HullDepth). */
		void Build(const std::vector<FHullShape>& Hulls, double InMainDepth);
		bool IsBuilt() const { return !Texels.empty(); }
		/** Bilinear between texel centres, clamped at the edges (the GPU's TA_Clamp). */
		FTexel Sample(double X, double Y) const;
		/** The four floats per texel, RGBA, for the texture. */
		std::vector<float> Pixels() const;

		/**
		 * How far M_WaterV4 drops the water surface at a point of it in the body frame (m, along the world's vertical),
		 * mirroring its V4_WPO hull block: 1.1 times its immersion below the bottom plus 3 cm, faded to zero over the
		 * last 5 cm inside the skin (15 cm over the sheer), capped at 2 m. UpZ is the body's up axis' world Z (the drop
		 * is vertical, the immersion along the body's Z).
		 */
		double Drop(double X, double Y, double Z, double UpZ) const;
	};
}
