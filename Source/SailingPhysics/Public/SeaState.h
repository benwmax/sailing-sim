#pragma once

#include "SailingPhysicsApi.h"
#include "SailingMath.h"
#include <cstdint>
#include <functional>
#include <vector>

namespace Sailing
{
	class FLakeTerrain;

	/** W3: the long wave trains drawn exactly by the water shader (M_WaterV4 and AWaterSurface::LongComponents). */
	constexpr int kSeaLongComponents = 24;
	/** Direction bins of the fetch map: every 22.5 deg of the direction the waves travel toward. */
	constexpr int kSeaBins = 16;
	/** The sea map's channels: one per long component, then the short waves' scale. */
	constexpr int kSeaChannels = kSeaLongComponents + 1;

	/**
	 * W3, sea state by direction: the open water a wave travelling each way has had to grow over, at every point of a
	 * world (docs/water-3). For each of 16 directions, Saville's effective fetch (the SPM's nine rays at 11.25 deg over
	 * +/-45 deg, as FLakeTerrain::EffectiveFetch) of the distance to land upwind of the waves. The distances are marched
	 * semi-Lagrangian on a grid half the map's cell: each cell's fetch is the fetch one cell upwind, interpolated, plus the
	 * step, so all 32 directions take a fraction of a second where a ray from every cell would take seconds. Also the depth
	 * of each cell (TMA) and the world's median depth (the components' dispersion).
	 */
	class SAILINGPHYSICS_API FSeaFetch
	{
	public:
		/**
		 * MapCell 0 picks it from the world's size: 50 m, doubled until neither side has more than 600 cells (Ray
		 * Hubbard 50 m, Galveston Bay 100 m). OpenSea (optional) is 0..1, the ocean's share at a point (FOcean's mask):
		 * where it is over half, the open sea's FFT carries the wind sea and the chop keeps a 200 m fetch, as the game did.
		 */
		void Build(const FLakeTerrain& Terrain, double MapCell = 0.0, double MaxFetch = 15000.0,
			const std::function<double(double, double)>& OpenSea = nullptr);
		bool IsValid() const { return Rows > 0; }

		int GetRows() const { return Rows; }
		int GetCols() const { return Cols; }
		double GetCell() const { return Cell; }
		double GetOriginX() const { return OriginX; }
		double GetOriginY() const { return OriginY; }
		double GetMaxFetch() const { return MaxFetch; }
		double GetMedianDepth() const { return MedianDepth; }
		/** Effective fetch (m) for waves travelling toward bin Bin's direction (Bin x 22.5 deg, 0 = north, 90 = east). */
		double FetchAt(int Row, int Col, int Bin) const { return Fetch[(size_t(Row) * Cols + Col) * kSeaBins + Bin]; }
		/** Water depth of a cell (m, mean over its quarters; 0 on land). */
		double DepthAt(int Row, int Col) const { return Depth[size_t(Row) * Cols + Col]; }
		/** The same, for a direction between bins (linear in angle), at the nearest cell. Tests and tools. */
		double FetchToward(double X, double Y, double TravelRadians) const;

		/** One direction's fetch (no Saville spread) on a grid of MarchCell, as the cells' distance to land toward From. */
		static void March(const std::vector<uint8_t>& Water, int Rows, int Cols, double MarchCell, double FromRadians,
			double MaxFetch, std::vector<float>& Out);

	private:
		int Rows = 0, Cols = 0;
		double Cell = 50.0, OriginX = 0.0, OriginY = 0.0, MaxFetch = 15000.0, MedianDepth = 0.0;
		std::vector<float> Fetch;   // Rows x Cols x kSeaBins
		std::vector<float> Depth;   // Rows x Cols
	};

	struct FWaveComponent;

	/**
	 * W3: how much of each long wave train there is at every point, relative to the field's reference sea (the sea a
	 * 15 km fetch grows in the wind), for one wind speed: R = A(F, h) / A(F_ref) with F the component's own direction's
	 * fetch and the growth laws' spectrum at that fetch (FWaveField::BandAmplitudeFactor), times the TMA depth factor at
	 * the cell. The short waves (the components past the long ones, and the FFT detail the shader draws) share one scale,
	 * their energy-weighted ratio in the field's current direction. The shader samples the same numbers (uploaded as an
	 * atlas by AWaterSurface) bilinearly, as FWaveField does here.
	 */
	class SAILINGPHYSICS_API FSeaMap
	{
	public:
		/** Ratios for the components at wind WindMs travelling toward TravelRadians (for the short waves' weights). */
		void Build(const FSeaFetch& Fetch, const FWaveComponent* Components, double WindMs, double TravelRadians,
			bool bShallow = true);
		bool IsValid() const { return Rows > 0; }
		double GetWindMs() const { return WindMs; }
		double GetTravelRadians() const { return TravelRadians; }
		double GetReferenceFetch() const { return ReferenceFetch; }
		int GetRows() const { return Rows; }
		int GetCols() const { return Cols; }
		double GetCell() const { return Cell; }
		double GetOriginX() const { return OriginX; }
		double GetOriginY() const { return OriginY; }
		/** The channels of a cell: kSeaLongComponents ratios, then the short scale. */
		const float* CellAt(int Row, int Col) const { return &Values[(size_t(Row) * Cols + Col) * kSeaChannels]; }

		/**
		 * The channels at a point, bilinear between cell centres and clamped at the edge (as the shader's sampler with
		 * its padded tiles): Out[kSeaChannels].
		 */
		void Sample(double X, double Y, float* Out) const;

		/** Kitaigorodskii's depth factor of the TMA spectrum for a component of angular frequency Omega in depth H. */
		static double TmaFactor(double Omega, double Depth);

	private:
		int Rows = 0, Cols = 0;
		double Cell = 50.0, OriginX = 0.0, OriginY = 0.0;
		double WindMs = 0.0, TravelRadians = 0.0, ReferenceFetch = 15000.0;
		std::vector<float> Values;  // Rows x Cols x kSeaChannels
	};
}
