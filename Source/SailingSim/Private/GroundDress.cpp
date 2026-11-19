#include "GroundDress.h"
#include "LakeData.h"
#include "Marina.h"

namespace SailingGround
{
	namespace
	{
		double Smoothstep(double A, double B, double X)
		{
			const double T = FMath::Clamp((X - A) / (B - A), 0.0, 1.0);
			return T * T * (3.0 - 2.0 * T);
		}

		/** Value noise in -1..1 on a 7 m lattice (the mown edge's raggedness), the sin hash the ground material uses. */
		double Hash(double X, double Y)
		{
			return FMath::Frac(FMath::Abs(FMath::Sin(X * 127.1 + Y * 311.7) * 43758.5453));
		}

		double VNoise(double X, double Y)
		{
			const double IX = FMath::Floor(X), IY = FMath::Floor(Y);
			double FX = X - IX, FY = Y - IY;
			FX = FX * FX * (3.0 - 2.0 * FX);
			FY = FY * FY * (3.0 - 2.0 * FY);
			const double A = Hash(IX, IY), B = Hash(IX + 1, IY), C = Hash(IX, IY + 1), D = Hash(IX + 1, IY + 1);
			const double AB = A + (B - A) * FX, CD = C + (D - C) * FX;
			return 2.0 * (AB + (CD - AB) * FY) - 1.0;
		}
	}

	double BankTone(double X, double Y)
	{
		// scene.py (Track A's test shore), bank_noise "smooth": the integration change the round 1 renders used.
		return FMath::Clamp(0.5 + 0.5 * FMath::Sin(X / 13.0 + 0.6 * FMath::Sin(Y / 9.0)) * FMath::Sin(X / 31.0 + 1.3), 0.0, 1.0);
	}

	float SeasonAmount(int32 DayOfYear)
	{
		const double D = double((DayOfYear - 1 + 366) % 366 + 1);
		if (D >= 200.0) return float(Smoothstep(305.0, 335.0, D));          // browning through November
		return float(1.0 - Smoothstep(74.0, 110.0, D));                     // greening from mid-March through April
	}

	void FMownSource::Build(const FLakeData& Lake)
	{
		Houses.Reset();
		Lawns.Reset();
		for (const FLakeHouse& H : Lake.Houses)
		{
			if (!H.bFullDetail || H.bCommercial) continue;
			AddHouse(H.X, H.Y);
		}
		for (const FMarinaBuilding& B : Lake.Marina.Buildings)
		{
			const double R = 0.5 * FMath::Max(B.Size.X, B.Size.Y) + ClubLawnM;
			Lawns.Add(FBox2D(B.Center - FVector2D(R, R), B.Center + FVector2D(R, R)));
		}
	}

	void FMownSource::AddHouse(double X, double Y)
	{
		Houses.FindOrAdd(FIntPoint(FMath::FloorToInt32(X / CellM), FMath::FloorToInt32(Y / CellM))).Add(FVector2D(X, Y));
	}

	float FMownSource::At(double X, double Y) const
	{
		double Mown = 0.0;
		for (const FBox2D& L : Lawns)
		{
			if (X < L.Min.X - FadeM || X > L.Max.X + FadeM || Y < L.Min.Y - FadeM || Y > L.Max.Y + FadeM) continue;
			const double Out = FMath::Max(FMath::Max(L.Min.X - X, X - L.Max.X), FMath::Max(L.Min.Y - Y, Y - L.Max.Y));   // < 0 inside
			Mown = FMath::Max(Mown, 1.0 - Smoothstep(0.0, FadeM, Out + 3.0 * VNoise(X / 7.0, Y / 7.0)));
			if (Mown >= 1.0) return 1.f;
		}
		if (Houses.Num() == 0) return float(Mown);
		const FIntPoint Cell(FMath::FloorToInt32(X / CellM), FMath::FloorToInt32(Y / CellM));
		double Nearest = 1e9;
		for (int32 DX = -1; DX <= 1; ++DX)
		{
			for (int32 DY = -1; DY <= 1; ++DY)
			{
				const TArray<FVector2D>* Cells = Houses.Find(Cell + FIntPoint(DX, DY));
				if (!Cells) continue;
				for (const FVector2D& H : *Cells) Nearest = FMath::Min(Nearest, FVector2D::Distance(H, FVector2D(X, Y)));
			}
		}
		if (Nearest > ReachM + FadeM + 4.0) return float(Mown);
		return float(FMath::Max(Mown, 1.0 - Smoothstep(ReachM, ReachM + FadeM, Nearest + 4.0 * VNoise(X / 7.0 + 3.0, Y / 7.0 - 1.0))));
	}
}
