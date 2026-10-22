#pragma once

#include "CoreMinimal.h"
#include "BoatModel.h"
#include <complex>

/**
 * Visual V4: the water the boats push around. A square grid of the surface around the player's boat on which the
 * linear deep-water wave equation is solved exactly, mode by mode in Fourier space (every wavelength at its own
 * speed, omega^2 = g k), forced by every hull in range as a pressure patch on the surface: its draft at each cell, from
 * the physics hull shape at the boat's position, heading, heel and heave. A moving pressure is what makes a ship's
 * waves, so the right patterns come by themselves: the bow wave, the transverse and diverging waves of the Kelvin
 * wake inside about 19.5 degrees, the quarter wave, the hollow along a heeled hull. (Tessendorf's iWave does the same
 * with a truncated convolution kernel; on a grid this fine its truncation gives every wave nearly the same frequency
 * and a 1.7 m wake behind a 6 kn boat instead of 6 m, so the derivative is done spectrally here.)
 * Foam builds where the surface moves fast (the bow wave breaking, the turbulent stern) and fades over a few seconds.
 * The grid stays fixed in the water and re-centres in whole cells as the boat moves; a sponge at the edges lets the
 * waves out. Visual only: the physics never reads it.
 */
class SAILINGSIM_API FWakeGrid
{
public:
	struct FHull
	{
		FVector2D Position;     // map frame, m (body origin: design waterline amidships)
		float Heading = 0.f;    // rad, map frame
		float Heel = 0.f;       // rad, positive = starboard side up
		float Sink = 0.f;       // m the hull sits deeper than its design waterline (heave)
		const Sailing::FHullShape* Shape = nullptr;
		float CanoeDepth = 0.2f;
		float Speed = 0.f;      // m/s through the water
	};

	void Init(int32 InN, float InCell);
	bool IsValid() const { return N > 0; }
	/** Keeps the grid around a point (shifts by whole cells when it drifts more than a quarter of the grid off centre). */
	void Follow(const FVector2D& Point);
	/** Advances at a fixed 30 Hz, forced by the hulls. */
	void Step(float DeltaSeconds, const TArray<FHull>& Hulls);

	int32 Size() const { return N; }
	float CellSize() const { return Cell; }
	/** Map position (m) of cell (0, 0); rows run north (X), columns east (Y). */
	FVector2D Origin() const { return Corner; }
	const TArray<float>& Heights() const { return H; }
	const TArray<float>& Foam() const { return FoamField; }
	/** The turbulent lane a hull leaves (0..1): its wake's smooth track, where the stirred water damps the wind's ripples. */
	const TArray<float>& Slick() const { return SlickField; }
	/** Height (m) at a map point (0 outside). */
	float HeightAt(const FVector2D& Point) const;

private:
	void StepOnce(float Dt, const TArray<FHull>& Hulls);
	float DisplacedDepth(const FHull& Hull, const FVector2D& Point) const;

	int32 N = 0;
	float Cell = 0.2f;
	FVector2D Corner = FVector2D::ZeroVector;
	TArray<float> H, Velocity, Pressure, Depth, PrevDepth, FoamField, SlickField, SlickScratch;
	TArray<float> Omega;                      // per mode, rad/s (deep water)
	TArray<std::complex<float>> Spectrum;     // scratch
	float Accumulator = 0.f;
	bool bHasDepth = false;
	bool bPlaced = false;
};
