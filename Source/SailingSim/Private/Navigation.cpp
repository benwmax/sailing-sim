#include "Navigation.h"

namespace SailingNav
{
	double NormalizeDeg(double Deg)
	{
		Deg = FMath::Fmod(Deg, 360.0);
		return Deg < 0.0 ? Deg + 360.0 : Deg;
	}

	double MagneticToTrue(double MagneticDeg, double VariationEastDeg) { return NormalizeDeg(MagneticDeg + VariationEastDeg); }
	double TrueToMagnetic(double TrueDeg, double VariationEastDeg) { return NormalizeDeg(TrueDeg - VariationEastDeg); }

	double BearingDeg(const FVector2D& From, const FVector2D& To)
	{
		// Map frame: X north, Y east, so atan2(east, north) is the compass bearing.
		return NormalizeDeg(FMath::RadiansToDegrees(FMath::Atan2(To.Y - From.Y, To.X - From.X)));
	}

	bool PlotFix(const TArray<FBearing>& Bearings, double VariationEastDeg, FVector2D& OutFix, double& OutSpread)
	{
		if (Bearings.Num() < 2) return false;
		// Each line of position: points P with n . (P - Object) = 0, n the normal to the bearing direction.
		double A11 = 0, A12 = 0, A22 = 0, B1 = 0, B2 = 0;
		TArray<TPair<FVector2D, FVector2D>> Lines;
		for (const FBearing& B : Bearings)
		{
			const double T = FMath::DegreesToRadians(MagneticToTrue(B.MagneticDeg, VariationEastDeg));
			const FVector2D Dir(FMath::Cos(T), FMath::Sin(T));
			const FVector2D N(-Dir.Y, Dir.X);
			A11 += N.X * N.X; A12 += N.X * N.Y; A22 += N.Y * N.Y;
			const double C = N.X * B.Object.X + N.Y * B.Object.Y;
			B1 += N.X * C; B2 += N.Y * C;
			Lines.Add({ B.Object, N });
		}
		const double Det = A11 * A22 - A12 * A12;
		if (FMath::Abs(Det) < 1e-3 * Bearings.Num() * Bearings.Num()) return false; // lines too close to parallel
		OutFix = FVector2D((A22 * B1 - A12 * B2) / Det, (A11 * B2 - A12 * B1) / Det);
		double Sum = 0.0;
		for (const TPair<FVector2D, FVector2D>& L : Lines)
		{
			const double D = FVector2D::DotProduct(L.Value, OutFix - L.Key);
			Sum += D * D;
		}
		OutSpread = FMath::Sqrt(Sum / Lines.Num());
		return true;
	}

	FVector2D DeadReckon(const FVector2D& From, double CourseTrueDeg, double SpeedMs, double Seconds)
	{
		const double T = FMath::DegreesToRadians(CourseTrueDeg);
		return From + FVector2D(FMath::Cos(T), FMath::Sin(T)) * (SpeedMs * Seconds);
	}

	FString FormatDistance(double Meters)
	{
		const double Nm = Meters / MetersPerNauticalMile;
		return Nm < 0.1 ? FString::Printf(TEXT("%.0f m"), Meters) : FString::Printf(TEXT("%.2f nm"), Nm);
	}
}
