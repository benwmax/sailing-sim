#pragma once

#include "CoreMinimal.h"

/**
 * Angle wraps that always return. FMath::UnwindDegrees loops by 360 until the angle is in range: on a heading of 1e17 (a
 * boat state gone wrong) A -= 360 never changes A and the game thread hangs there (the PC's soak 3, UpdateNavLights).
 * Game code that wraps a value from telemetry, a position or a camera uses these instead.
 */
namespace SailingAngles
{
	/** A in (-180, 180]; 0 for NaN or infinity. Fmod, then at most one step: bounded time for any input. */
	template <typename T>
	T WrapDegrees(T A)
	{
		if (!FMath::IsFinite(A)) return T(0);
		A = FMath::Fmod(A, T(360));
		if (A > T(180)) A -= T(360);
		else if (A <= T(-180)) A += T(360);
		return A;
	}
}
