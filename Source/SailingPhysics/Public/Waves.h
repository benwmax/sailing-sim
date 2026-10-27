#pragma once

#include "SailingPhysicsApi.h"
#include "SailingMath.h"
#include <cstdint>
#include <memory>
#include <mutex>
#include <vector>

namespace Sailing
{
	class FOcean;
	class FSeaMap;

	constexpr int kWaveBands = 16;
	constexpr int kWaveDirectionsPerBand = 3;
	constexpr int kWaveComponents = kWaveBands * kWaveDirectionsPerBand; // 48

	/** A slice of the sea's spectrum: its wavelength, its share of the surface variance and where it travels. */
	struct FWaveBand
	{
		double Wavelength = 0.0; // m
		double Variance = 0.0;   // m^2 (a^2 / 2 summed over the slice)
		double Direction = 0.0;  // rad, where it travels toward
	};

	/** One linear (Airy) wave train. Direction and wavenumber are fixed; only the amplitude follows the wind. */
	struct FWaveComponent
	{
		double Kx = 0.0, Ky = 0.0; // wavenumber vector (rad/m), pointing where the wave travels
		double Omega = 0.0;        // rad/s, deep-water dispersion: omega^2 = g k
		double Phase = 0.0;        // rad
		double Amplitude = 0.0;    // m
	};

	struct FWaveParams
	{
		double WindSpeedKnots = 10.0;    // at 10 m
		double WindFromDegrees = 0.0;    // same convention as FWindParams
		double FetchMeters = 4000.0;     // open water upwind (Lake Ray Roberts: roughly 2 to 10 km depending on direction)
		/**
		 * The sea the fleet's polars and reference checks were calibrated in: the growth laws in the 10 m wind U, as before
		 * W3's adjusted wind. Their runs keep it so a change of growth law doesn't move every boat's calibration; the game's
		 * waters grow on U_A.
		 */
		bool bCalibrationSea = false;
		/** Where turning the components to a new wind keeps the surface where it was (the boat; AnchorDirections). */
		double HoldX = 0.0, HoldY = 0.0;
		uint32_t Seed = 1;
	};

	/**
	 * Fetch-limited wind waves (lake chop) as a sum of 48 linear wave trains with a JONSWAP spectrum and the measured
	 * directional spreading about the wind (Donelan, Hamilton and Hui's sech^2, Banner's past 1.6 fp; the calibration
	 * sea keeps cos^2). Significant height and peak period follow the fetch-limited growth
	 * laws (U.S. Army Corps Shore Protection Manual / JONSWAP): g Hs / U^2 = 0.0016 (g F / U^2)^0.5,
	 * g Tp / U = 0.286 (g F / U^2)^(1/3), capped at a fully developed sea.
	 *
	 * Each band's three directions are laid about the wind (AnchorDirections) and then kept, so the surface stays
	 * continuous when the wind does; when the wind builds or shifts, amplitudes move smoothly between components. Only a
	 * turn past kReanchorRadians lays them again (about the new wind, in phase at the params' hold point). The renderer evaluates exactly the
	 * same sum on the GPU (see GetComponents), so the boat floats on the waves you see.
	 */
	class SAILINGPHYSICS_API FWaveField
	{
	public:
		explicit FWaveField(uint32_t Seed = 1);

		/** Target sea state from the wind. Amplitudes approach it band by band when Update is called. */
		void SetWind(const FWaveParams& Params);
		/**
		 * Moves amplitudes toward the target sea state (waves take time to build and decay). Each band has its own
		 * time (GrowthSeconds): a puff raises the ripples and chop within seconds, the longest waves over minutes.
		 */
		void Update(double Dt);
		/**
		 * Water and weather W0: how long a band of this period takes to follow the wind (time constant, s). Wave growth
		 * by wind input scales as the period squared (the growth rate per cycle falls as the waves catch up with the
		 * wind, Plant 1982); 8 T^2 puts the 2.5 s peak of a 12 kn lake near the old 40 s, clamped to 5..300 s.
		 */
		static double GrowthSeconds(double PeriodSeconds);
		/** Period at the centre of a band (s), for tests. */
		double BandPeriod(int Band) const { return 1.0 / BandFrequency[Band]; }
		/** Jumps straight to the target sea state. */
		void SnapToTarget();

		double Height(double X, double Y, double T) const;
		/** Height, vertical velocity and surface slope (dh/dx, dh/dy) at a point. */
		void Sample(double X, double Y, double T, double& OutHeight, double& OutVerticalVelocity, double& OutSlopeX, double& OutSlopeY) const;

		/**
		 * docs/surfing/: the water's horizontal orbital velocity (m/s, X and Y) Below meters under the surface (stretched:
		 * measured from the local surface, so it doesn't grow above the mean level). Linear theory: each component moves
		 * the water a omega cosh(k (h - d)) / sinh(k h) along its travel direction, in phase with its height (forward
		 * under a crest, back under a trough); exp(-k d) in deep water. Plus the ocean's.
		 */
		void OrbitalVelocity(double X, double Y, double T, double Below, double& OutU, double& OutV) const;

		/** Significant wave height (4 x standard deviation of the surface) of the current amplitudes, m. */
		double SignificantHeight() const;
		/** The same where the sea is at a point: the ocean's part only as far as its mask lets it in (gulf-swell). */
		double SignificantHeightAt(double X, double Y) const;
		/** Energy-weighted mean wave period (Tm01), s. */
		double MeanPeriod() const;
		/** Direction the waves travel toward (energy-weighted mean), radians in the XY plane. */
		double MeanDirection() const;

		/** Fetch-limited growth law targets (SPM forms in GrowthStressWind: U_A, steepened above 18 kn; the period from that Hs by Toba's 3/2 law in U_A). */
		static double TargetSignificantHeight(double WindMs, double FetchMeters);
		static double TargetPeakPeriod(double WindMs, double FetchMeters);
		/** The growth laws' wind-stress factor U_A = 0.71 U^1.23 (m/s in, m/s out). */
		static double AdjustedWindSpeed(double WindMs);
		/** The wind the targets grow the sea in: U_A, times (U / 18 kn)^0.43 above 18 kn (m/s in, m/s out). */
		static double GrowthStressWind(double WindMs);
		/** The SPM laws in whatever wind is given (TargetSignificantHeight is this in U_A). */
		static double GrowthLawHeight(double StressWindMs, double FetchMeters);
		static double GrowthLawPeriod(double StressWindMs, double FetchMeters);

		const FWaveComponent* GetComponents() const { return Components; }
		/** Counts changes of the components' directions, wavenumbers or phases (the renderer re-uploads them). */
		uint32_t GetDirectionGeneration() const { return DirectionGeneration; }

		/**
		 * docs/short-wave-spreading/: Donelan, Hamilton and Hui's (1985) spreading parameter beta at f over the peak fp
		 * (Banner 1990 past 1.6 fp, held at 0.56 fp's below), and the normalized sech^2 spreading
		 * D(theta) = 0.5 beta sech^2(beta theta) / tanh(beta pi). FWaveDetail's short waves follow the same law.
		 */
		static double SpreadingBeta(double F, double Fp);
		static double DirectionalSpreading(double F, double Fp, double Theta);
		/**
		 * The side directions' angle off the wind for a band whose spreading has this beta: three directions at
		 * -Delta, 0, +Delta weighted by the spreading carry its mean cos(theta) (its directional width), capped at 75 deg.
		 */
		static double SideAngle(double Beta);
		/**
		 * Lays each band's three directions about the wind's travel direction (radians) at -Delta, 0 and +Delta (SideAngle
		 * of the band's beta at this sea's peak) with a little seeded jitter, keeping frequencies; wavenumbers follow the
		 * depth. Phases are chosen so each component's phase at (HoldX, HoldY) is what it was: the height and its rate there
		 * don't jump. SetWind calls it on the first wind and after a turn past kReanchorRadians (not in the calibration sea).
		 */
		void AnchorDirections(double TravelDir, double HoldX, double HoldY);
		bool IsAnchored() const { return bAnchored; }
		double GetAnchorDirection() const { return AnchorDir; }
		static constexpr double kReanchorRadians = 0.785398163397448; // 45 deg
		/** The sea's spectrum in bands (the lake components one by one, the ocean in wavelength bins), for added resistance. */
		const std::vector<FWaveBand>& Bands() const;
		/** Where the ocean's bins start in Bands() (after the lake components; its size without an ocean). Read after Bands(). */
		size_t OceanBandStart() const { return BandOceanStart; }
		/** The ocean's share of its energy at a point (FOcean's mask squared; 0 without an ocean). */
		double OceanShareAt(double X, double Y) const;

		/**
		 * W3, sea state by direction (SeaState.h): with a sea map the components grow toward the sea of the map's
		 * reference fetch (15 km) and each point scales them by its own fetch for their direction and its depth. Height,
		 * Sample, SignificantHeightAt and BandsAt read the map; without one (polars, reference checks) nothing changes.
		 */
		void SetSeaMap(std::shared_ptr<const FSeaMap> InMap);
		const FSeaMap* GetSeaMap() const { return SeaMap.get(); }
		std::shared_ptr<const FSeaMap> GetSeaMapShared() const { return SeaMap; }
		/** Counts SetSeaMap calls (the renderer re-uploads the atlas when it changes). */
		uint32_t GetSeaMapGeneration() const { return SeaMapGeneration; }
		/** The fetch the components' targets grow on: the map's reference, else the params' fetch. */
		double ReferenceFetch() const;
		/** The map's channels at a point (kSeaChannels: the long components' ratios, then the short scale); 1 without a map. */
		void SeaRatiosAt(double X, double Y, float* Out) const;
		/**
		 * W3: the water's depth for the components' dispersion (omega^2 = g k tanh(k h)): their frequencies stay, their
		 * wavelengths shorten and they travel slower in shallow water. 0 = deep (the default). Call before the sea is used.
		 */
		void SetDepth(double DepthMeters);
		double GetDepth() const { return Depth; }
		/** The band's centre frequency and width (Hz): the same for every field. */
		static double BandCentreHz(int Band);
		static double BandWidthHz(int Band);
		/**
		 * W3: the amplitude a band's components get per unit of their direction share, in the growth laws' sea at this wind
		 * and fetch: ComputeTargetAmplitudes' JONSWAP band energy scaled to the target Hs (A = this x sqrt(w / sum w)).
		 */
		static double BandAmplitudeFactor(int Band, double WindMs, double FetchMeters);
		/** Bands() with the lake components' variance as it is at a point (the sea map's ratios). */
		void BandsAt(double X, double Y, std::vector<FWaveBand>& Out) const;

		/** Open sea: an FFT ocean (wind sea and swell) added to everything this field reports. */
		void SetOcean(std::shared_ptr<FOcean> InOcean) { Ocean = std::move(InOcean); bBandsDirty = true; }
		const FOcean* GetOcean() const { return Ocean.get(); }
		const FWaveParams& GetParams() const { return Params; }

	private:
		void ComputeTargetAmplitudes();

		FWaveComponent Components[kWaveComponents];
		double TargetAmplitude[kWaveComponents];
		double BandFrequency[kWaveBands];
		double BandWidth[kWaveBands];
		FWaveParams Params;
		std::shared_ptr<FOcean> Ocean;
		std::shared_ptr<const FSeaMap> SeaMap;
		uint32_t SeaMapGeneration = 0;
		double Depth = 0.0;
		bool bAnchored = false;
		double AnchorDir = 0.0;
		uint32_t DirectionGeneration = 0;
		/** The component each lake entry of BandCache came from (BandsAt scales them). */
		mutable std::vector<int> BandComponent;
		// Perf 1: boats stepping in parallel call Bands(): it is rebuilt under a lock, and only when the amplitudes or the
		// ocean changed (on the game thread, never during a step).
		mutable std::vector<FWaveBand> BandCache;
		mutable bool bBandsDirty = true;
		mutable uint64_t BandOceanGeneration = ~0ull;
		mutable size_t BandOceanStart = 0;
		struct FLock { std::mutex M; FLock() = default; FLock(const FLock&) {} FLock& operator=(const FLock&) { return *this; } };
		mutable FLock BandLock;
	};
}
