#pragma once

#include "CoreMinimal.h"

/**
 * Hardware fit wave 2 (docs/hardware-fit/): where the boat kit's moving fittings sit on a sail. Plain math, shared by the
 * pawn (BoatKitFittings.cpp) and SailingSim.Visual.KitFittings. Boat frame, cm. Kit meshes come in with Unreal's frame
 * (x, -y, z) x 100 of the kit's metres, and their sockets with them (scripts/import_hardware_kit.py).
 */
namespace KitFittings
{
	/** Piston hanks up a J/22 jib's luff (class boats carry 8 or 9; docs/part-detail-loop/jibhank.md). */
	constexpr int32 NumJibHanks = 8;

	/** Height (0 tack .. 1 head) of hank I of N on the luff: evenly spaced, half a gap from either end. */
	inline float HankV(int32 I, int32 N) { return (float(I) + 0.5f) / float(FMath::Max(N, 1)); }

	/** A rotation with its Y along `Y` and its X as near `X` as Y allows. Degenerate inputs (zero length, NaN, X along Y:
	 *  a boat switching mid-build, a collapsed cloth) fall back to Z up and any X square to Y, never a scaled matrix
	 *  (FQuat(FMatrix) ensures on one). */
	inline FQuat SafeRotationYX(const FVector& Y, const FVector& X)
	{
		FVector Yn = Y.ContainsNaN() ? FVector::ZeroVector : Y.GetSafeNormal();
		if (Yn.IsNearlyZero()) Yn = FVector::UpVector;
		FVector Xp = X.ContainsNaN() ? FVector::ZeroVector : X - Yn * FVector::DotProduct(X, Yn);
		if (Xp.SizeSquared() < 1e-8)
		{
			FVector A, B;
			Yn.FindBestAxisVectors(A, B);
			Xp = A;
		}
		const FVector Xn = Xp.GetSafeNormal();
		const FVector Zn = FVector::CrossProduct(Xn, Yn).GetSafeNormal();
		FQuat Q(FMatrix(Xn, Yn, Zn, FVector::ZeroVector));
		Q.Normalize();
		return Q;
	}

	/** Whether a fitting's transform may be handed to its component (USceneComponent::SetRelativeTransform ensures
	 *  otherwise): finite, unit rotation, no zero scale. */
	inline bool Placeable(const FTransform& X)
	{
		return X.IsValid() && !X.GetScale3D().IsNearlyZero();
	}

	/** A hank on the luff: the kit JibHank's stay runs along its Y and the sail lies aft along its -X, so Y follows the luff
	 *  up (UpLuff) and -X the sail's chord (Aft), and the hank's `Luff` socket (LuffSocket, mesh cm) lands on the cloth's
	 *  luff point (LuffPoint). */
	inline FTransform HankTransform(const FVector& LuffPoint, const FVector& UpLuff, const FVector& Aft, const FVector& LuffSocket)
	{
		const FQuat Q = SafeRotationYX(UpLuff, -Aft);
		return FTransform(Q, LuffPoint - Q.RotateVector(LuffSocket));
	}

	/** A hank clipped on the forestay wire (Tack to Hounds): its stay socket (the mesh origin) on the wire at the height of
	 *  the cloth's luff point (Luff), its Y along the wire and its sail (local -X) toward that point. */
	inline FTransform HankOnStay(const FVector& Tack, const FVector& Hounds, const FVector& Luff)
	{
		const FVector Wire = Hounds - Tack;
		const double T = FMath::Clamp(FMath::Abs(Wire.Z) > 1.0 ? (Luff.Z - Tack.Z) / Wire.Z : 0.5, 0.0, 1.0);
		const FVector Stay = Tack + Wire * T;
		FVector ToSail = Luff - Stay;
		ToSail -= Wire.GetSafeNormal() * FVector::DotProduct(ToSail, Wire.GetSafeNormal());
		if (ToSail.SizeSquared() < 1e-4) ToSail = FVector(-1.0, 0.0, 0.0);   // the luff on the wire: the sail aft
		return FTransform(SafeRotationYX(Wire, -ToSail), Stay.ContainsNaN() ? Tack : Stay);
	}

	/** The jib halyard's snap shackle on the head: the kit SnapShackle's bail is its origin and the part hangs along its -Z
	 *  (the eye 54 mm from the bail), so on a halyard its -Z points up the luff, the eye toward the halyard, and its X lies
	 *  forward in the sail's plane. */
	inline FTransform HeadShackleTransform(const FVector& Head, const FVector& UpLuff, const FVector& Aft)
	{
		// Z = -UpLuff exactly and X = -Aft square to it; Y = Z x X (FRotationMatrix::MakeFromZX's frame, built safely)
		const FVector Z = UpLuff.IsNearlyZero() || UpLuff.ContainsNaN() ? -FVector::UpVector : -UpLuff.GetSafeNormal();
		const FVector X = Aft.ContainsNaN() ? FVector::ZeroVector : -Aft - Z * FVector::DotProduct(-Aft, Z);
		return FTransform(SafeRotationYX(FVector::CrossProduct(Z, X), X), Head);
	}
}
