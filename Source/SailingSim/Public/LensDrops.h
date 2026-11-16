#pragma once

#include "CoreMinimal.h"

/**
 * Lens drops (feedback #28, docs/storm-look/lens-water/): where M_LensWater puts its drops, how big, for how long and when
 * they run. This is the CPU twin of the drop placement in make_materials.py's LENS_CODE, so the tests can hold it; keep
 * the two in step (same constants, same integer hash, same order of random numbers). The tests check that LENS_CODE
 * still carries the hash's constants.
 *
 * Each layer is a lattice of cells, turned and shifted per layer so the layers' grids never line up. A cell holds at most
 * one drop at a time. Its time runs in epochs of its own length (2.7 to 8.1 s for rain, from the cell's hash) and phase;
 * each epoch draws a new drop or none: where it sits in the cell, its size, its shape, whether it runs. So no two cells
 * keep step and no drop comes back to the same place. A drop lands at once, sits, and dries or is blown off: the harder
 * the air over the glass (the wind less the camera's own motion, so camera speed too), the shorter its life and the more
 * of them run downwind. The rain rate sets how many there are.
 */
namespace SailingLens
{
	inline constexpr int32 NumLayers = 4;          // three of rain, one of a slam's splashes
	inline constexpr int32 SplashLayer = 3;

	/** Cells per screen height. */
	inline float LayerScale(int32 Layer)
	{
		return Layer == 0 ? 11.f : Layer == 1 ? 17.f : Layer == 2 ? 26.f : 5.f;
	}

	/** The share of a layer's cells holding a drop in an epoch, for the rain at the camera (0..1) and a slam's spray (0..1). */
	inline float LayerChance(int32 Layer, float Rain, float Spray)
	{
		if (Layer == SplashLayer) return 0.35f * Spray * Spray;
		const float R = FMath::Clamp(Rain, 0.f, 1.f);
		return Layer == 0 ? 0.16f * R + 0.35f * Spray : Layer == 1 ? 0.13f * R + 0.12f * Spray : 0.10f * R + 0.06f * Spray;
	}

	/** How hard the air pushes on the glass, 0 (still, under 3 m/s) to 1 (15 m/s and up). */
	inline float WindShare(float AirMs)
	{
		return FMath::Clamp((AirMs - 3.f) / 12.f, 0.f, 1.f);
	}

	/** The share of its epoch a drop is on the glass: 0.9 in still air, 0.4 at 15 m/s; a splash 0.9. */
	inline float VisibleShare(int32 Layer, float AirMs)
	{
		return Layer == SplashLayer ? 0.9f : FMath::Lerp(0.9f, 0.4f, WindShare(AirMs));
	}

	/** The layer's lattice turn (radians) and shift (cells). */
	inline float LayerAngle(int32 Layer) { return 0.7f * float(Layer); }
	inline FVector2f LayerShift(int32 Layer) { return FVector2f(0.37f, 0.61f) * float(Layer); }

	/** Screen (aspect-corrected, in screen heights) to the layer's lattice, and a direction into its frame. */
	inline FVector2f ToLattice(int32 Layer, const FVector2f& Screen)
	{
		const float C = FMath::Cos(LayerAngle(Layer)), S = FMath::Sin(LayerAngle(Layer));
		const FVector2f P = Screen * LayerScale(Layer);
		return FVector2f(C * P.X - S * P.Y, S * P.X + C * P.Y) + LayerShift(Layer);
	}
	inline FVector2f TurnToLayer(int32 Layer, const FVector2f& V)
	{
		const float C = FMath::Cos(LayerAngle(Layer)), S = FMath::Sin(LayerAngle(Layer));
		return FVector2f(C * V.X - S * V.Y, S * V.X + C * V.Y);
	}

	/** lowbias32 (Chris Wellons): the shader's hash, exactly. */
	inline uint32 Hash(uint32 X)
	{
		X ^= X >> 16; X *= 0x7feb352du; X ^= X >> 15; X *= 0x846ca68bu; X ^= X >> 16;
		return X;
	}
	inline float Unit(uint32 H) { return float(H >> 8) * (1.f / 16777216.f); }
	inline uint32 CellSeed(int32 CellX, int32 CellY, int32 Layer)
	{
		return (uint32(CellX) * 0x8da6b343u) ^ (uint32(CellY) * 0xd8163841u) ^ (uint32(Layer) * 0xcb1ab31fu);
	}

	struct FLensDrop
	{
		float Present = 0.f;        // 0..1: the presence draw against the layer's chance, eased over 0.02
		float Life = 0.f;           // 0..1: lands, sits, dries (times Spray on the splash layer)
		float Age = 0.f;            // 0..1 through its epoch
		float Period = 0.f;         // seconds
		int32 Epoch = 0;
		FVector2f Centre = FVector2f::ZeroVector;   // in its cell, in the layer's frame
		float Radius = 0.f;         // cells, after drying
		float Aspect = 1.f;         // across the way it runs, over along
		float StretchMax = 1.f;     // its tail never takes it past 0.66 of a cell from its centre
		bool bRuns = false;
		float Rand[12] = {};        // the draws, in the shader's order (rim wobble and glint use 7..11)
	};

	/** The drop in a cell of a layer at time T (seconds). WindLayer: the screen direction the air pushes, turned into the layer. */
	inline FLensDrop DropAt(int32 CellX, int32 CellY, int32 Layer, float T, float Rain, float Spray, float AirMs, const FVector2f& WindLayer)
	{
		FLensDrop D;
		const bool bSplash = Layer == SplashLayer;
		const uint32 Seed = CellSeed(CellX, CellY, Layer);
		uint32 H = Seed;
		for (int32 K = 0; K < 2; ++K) { H = Hash(H); D.Rand[K] = Unit(H); }
		D.Period = (bSplash ? 6.f : 4.5f) * (0.6f + 0.8f * D.Rand[0]);
		const float Tt = T / D.Period + D.Rand[1];
		const float Epoch = FMath::FloorToFloat(Tt);
		D.Epoch = int32(Epoch);
		D.Age = Tt - Epoch;
		H = Seed ^ (uint32(D.Epoch) * 0x9e3779b9u);
		H = Hash(H); D.Rand[2] = Unit(H);
		D.Present = FMath::Clamp((LayerChance(Layer, Rain, Spray) - D.Rand[2]) / 0.02f, 0.f, 1.f);
		if (D.Present <= 0.f) return D;
		for (int32 K = 3; K < 12; ++K) { H = Hash(H); D.Rand[K] = Unit(H); }
		const float L = VisibleShare(Layer, AirMs);
		D.Life = FMath::Clamp(D.Age / 0.03f, 0.f, 1.f) * (1.f - FMath::SmoothStep(0.6f * L, L, D.Age));
		if (bSplash) D.Life *= Spray;
		// Many small drops, a few big ones; they shrink as they dry.
		const float S = D.Rand[3];
		D.Radius = (bSplash ? 0.18f + 0.14f * S : 0.07f + 0.23f * S * S) * (1.f - 0.35f * FMath::SmoothStep(0.5f * L, L, D.Age));
		D.Aspect = 0.8f + 0.25f * D.Rand[8];
		D.StretchMax = 0.66f / (D.Radius * 1.1f);
		const FVector2f C0 = FVector2f(D.Rand[4], D.Rand[5]) * 0.6f + FVector2f(0.2f, 0.2f);
		D.bRuns = !bSplash && D.Rand[6] < 0.7f * WindShare(AirMs);
		float Run = 0.f;
		if (D.bRuns)
		{
			// As far along the push as the box its centre lives in allows (0.2 to 0.8 of the cell), so it stays findable.
			const float Rx = WindLayer.X > 0.f ? (0.8f - C0.X) / FMath::Max(WindLayer.X, 1e-4f) : (C0.X - 0.2f) / FMath::Max(-WindLayer.X, 1e-4f);
			const float Ry = WindLayer.Y > 0.f ? (0.8f - C0.Y) / FMath::Max(WindLayer.Y, 1e-4f) : (C0.Y - 0.2f) / FMath::Max(-WindLayer.Y, 1e-4f);
			Run = FMath::Min(Rx, Ry) * (0.5f + 0.5f * D.Rand[7]) * FMath::SmoothStep(0.15f, L, D.Age);
		}
		D.Centre = C0 + WindLayer * Run;
		return D;
	}
}
