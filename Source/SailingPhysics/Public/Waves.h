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
		uint32_t Seed = 1;
	};

	/**
	 * Fetch-limited wind waves (lake chop) as a sum of 48 linear wave trains with a JONSWAP spectrum and cos^2
	 * directional spreading about the wind. Significant height and peak period follow the fetch-limited growth
	 * laws (U.S. Army Corps Shore Protection Manual / JONSWAP): g Hs / U^2 = 0.0016 (g F / U^2)^0.5,
	 * g Tp / U = 0.286 (g F / U^2)^(1/3), capped at a fully developed sea.
	 *
	 * Component directions and wavenumbers never change, so the surface stays continuous when the wind does; when
	 * the wind builds or shifts, amplitudes move smoothly between components. The renderer evaluates exactly the
	 * same sum on the GPU (see GetComponents), so the boat floats on the waves you see.
	 */
	class SAILINGPHYSICS_API FWaveField
	{
	public:
		explicit FWaveField(uint32_t Seed = 1);

		/** Target sea state from the wind. Amplitudes approach it over ResponseSeconds when Update is called. */
		void SetWind(const FWaveParams& Params);
		/** Moves amplitudes toward the target sea state (waves take time to build and decay). */
		void Update(double Dt, double ResponseSeconds = 45.0);
		/** Jumps straight to the target sea state. */
		void SnapToTarget();

		double Height(double X, double Y, double T) const;
		/** Height, vertical velocity and surface slope (dh/dx, dh/dy) at a point. */
		void Sample(double X, double Y, double T, double& OutHeight, double& OutVerticalVelocity, double& OutSlopeX, double& OutSlopeY) const;

		/** Significant wave height (4 x standard deviation of the surface) of the current amplitudes, m. */
		double SignificantHeight() const;
		/** Energy-weighted mean wave period (Tm01), s. */
		double MeanPeriod() const;
		/** Direction the waves travel toward (energy-weighted mean), radians in the XY plane. */
		double MeanDirection() const;

		/** Fetch-limited growth law targets. */
		static double TargetSignificantHeight(double WindMs, double FetchMeters);
		static double TargetPeakPeriod(double WindMs, double FetchMeters);

		const FWaveComponent* GetComponents() const { return Components; }
		/** The sea's spectrum in bands (the lake components one by one, the ocean in wavelength bins), for added resistance. */
		const std::vector<FWaveBand>& Bands() const;

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
		// Perf 1: boats stepping in parallel call Bands(): it is rebuilt under a lock, and only when the amplitudes or the
		// ocean changed (on the game thread, never during a step).
		mutable std::vector<FWaveBand> BandCache;
		mutable bool bBandsDirty = true;
		mutable uint64_t BandOceanGeneration = ~0ull;
		struct FLock { std::mutex M; FLock() = default; FLock(const FLock&) {} FLock& operator=(const FLock&) { return *this; } };
		mutable FLock BandLock;
	};
}
