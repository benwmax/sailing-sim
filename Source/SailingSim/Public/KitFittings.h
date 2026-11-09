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

	/** A hank on the luff: the kit JibHank's stay runs along its Y and the sail lies aft along its -X, so Y follows the luff
	 *  up (UpLuff) and -X the sail's chord (Aft), and the hank's `Luff` socket (LuffSocket, mesh cm) lands on the cloth's
	 *  luff point (LuffPoint). */
	inline FTransform HankTransform(const FVector& LuffPoint, const FVector& UpLuff, const FVector& Aft, const FVector& LuffSocket)
	{
		const FQuat Q(FRotationMatrix::MakeFromYX(UpLuff, -Aft));
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
		return FTransform(FQuat(FRotationMatrix::MakeFromYX(Wire, -ToSail)), Stay);
	}

	/** The jib halyard's snap shackle on the head: the kit SnapShackle's bail is its origin and the part hangs along its -Z
	 *  (the eye 54 mm from the bail), so on a halyard its -Z points up the luff, the eye toward the halyard, and its X lies
	 *  forward in the sail's plane. */
	inline FTransform HeadShackleTransform(const FVector& Head, const FVector& UpLuff, const FVector& Aft)
	{
		return FTransform(FQuat(FRotationMatrix::MakeFromZX(-UpLuff, -Aft)), Head);
	}
}
