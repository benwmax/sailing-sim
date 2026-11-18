#include "ShipRig.h"

#include <algorithm>
#include <cmath>
#include <cstring>

namespace Sailing
{
	namespace
	{
#include "CommonwealthRigData.inl"

		const FShipRigData kCommonwealth = {
			kCommonwealthSpars, int(sizeof(kCommonwealthSpars) / sizeof(kCommonwealthSpars[0])),
			kCommonwealthSails, int(sizeof(kCommonwealthSails) / sizeof(kCommonwealthSails[0])) };
		static_assert(sizeof(kCommonwealthSpars) / sizeof(kCommonwealthSpars[0]) <= size_t(kMaxRigSpars), "spars fit the pose");
		static_assert(sizeof(kCommonwealthSails) / sizeof(kCommonwealthSails[0]) <= size_t(kMaxRigSails), "sails fit the pose");

		constexpr double kRigDegToRad = 3.14159265358979323846 / 180.0;

		Vec3 SparForward(const FRigSpar& S)
		{
			const Vec3 Z = S.Axis.Normalized();
			return (Vec3(1.0, 0.0, 0.0) - Z * Z.X).Normalized();
		}

		double OutOf(const FShipRigInput& In, const FRigSail& S)
		{
			switch (S.Kind)
			{
			case ERigSailKind::Square: return S.Square >= 0 && S.Square < kMaxRigSquare ? In.SquareOut[S.Square] : 1.0;
			case ERigSailKind::Headsail: return In.JibOut;
			case ERigSailKind::Staysail: return In.StaysailOut;
			default: return In.MainOut;
			}
		}

		int SideOf(const FShipRigInput& In, const FRigSail& S)
		{
			switch (S.Kind)
			{
			case ERigSailKind::Headsail: return In.JibSide;
			case ERigSailKind::Staysail: return In.StaysailSide;
			case ERigSailKind::Spanker: return In.MainSide;
			default: return 1;
			}
		}
	}

	int FShipRigData::SailOnSpar(int Spar) const
	{
		for (int K = 0; K < NumSails; ++K)
		{
			if (Sails[K].Spar == Spar && (Sails[K].Kind == ERigSailKind::Square || Sails[K].Kind == ERigSailKind::Spanker)) return K;
		}
		return -1;
	}

	int FShipRigData::SparNamed(const char* Name) const
	{
		for (int K = 0; K < NumSpars; ++K) if (Name && std::strcmp(Spars[K].Name, Name) == 0) return K;
		return -1;
	}

	int FShipRigData::SailNamed(const char* Name) const
	{
		for (int K = 0; K < NumSails; ++K) if (Name && std::strcmp(Sails[K].Name, Name) == 0) return K;
		return -1;
	}

	const FShipRigData& CommonwealthRig() { return kCommonwealth; }

	const FShipRigData* ShipRigFor(const char* ConfigName)
	{
		if (ConfigName && std::strcmp(ConfigName, "Commonwealth") == 0) return &kCommonwealth;
		return nullptr;
	}

	Vec3 FRigMotion::ApplyVector(const Vec3& V) const
	{
		return { M[0][0] * V.X + M[0][1] * V.Y + M[0][2] * V.Z,
			M[1][0] * V.X + M[1][1] * V.Y + M[1][2] * V.Z,
			M[2][0] * V.X + M[2][1] * V.Y + M[2][2] * V.Z };
	}

	Vec3 FRigMotion::Apply(const Vec3& P) const { return ApplyVector(P) + T; }

	FRigMotion FRigMotion::operator*(const FRigMotion& B) const
	{
		FRigMotion Out;
		for (int I = 0; I < 3; ++I)
		{
			for (int J = 0; J < 3; ++J)
			{
				Out.M[I][J] = M[I][0] * B.M[0][J] + M[I][1] * B.M[1][J] + M[I][2] * B.M[2][J];
			}
		}
		Out.T = Apply(B.T);
		return Out;
	}

	double FRigMotion::Determinant() const
	{
		return M[0][0] * (M[1][1] * M[2][2] - M[1][2] * M[2][1]) - M[0][1] * (M[1][0] * M[2][2] - M[1][2] * M[2][0])
			+ M[0][2] * (M[1][0] * M[2][1] - M[1][1] * M[2][0]);
	}

	double RigTableAt(const FRigRow* Rows, int Num, double Deg)
	{
		if (!Rows || Num <= 0) return 0.0;
		if (Deg <= Rows[0].Deg) return Rows[0].Metres;
		for (int K = 1; K < Num; ++K)
		{
			if (Deg <= Rows[K].Deg)
			{
				const double Span = Rows[K].Deg - Rows[K - 1].Deg;
				const double U = Span > 1e-9 ? (Deg - Rows[K - 1].Deg) / Span : 1.0;
				return Rows[K - 1].Metres + (Rows[K].Metres - Rows[K - 1].Metres) * U;
			}
		}
		return Rows[Num - 1].Metres;
	}

	void RigBraceLimits(const FShipRigData& Rig, int Spar, double Hoist, int Sail, double& OutLo, double& OutHi)
	{
		OutLo = 0.0;
		OutHi = 0.0;
		if (Spar < 0 || Spar >= Rig.NumSpars) return;
		const FRigSpar& S = Rig.Spars[Spar];
		OutLo = S.BraceLo;
		OutHi = S.BraceHi;
		const int N = std::min(S.NumBraceByHoist, kMaxRigHoistRows);
		if (N > 0)
		{
			const double H = std::clamp(Hoist, 0.0, 1.0);
			int A = 0;
			while (A + 1 < N && S.BraceByHoist[A + 1][0] <= H) ++A;
			int B = A;
			if (S.BraceByHoist[A][0] < H && A + 1 < N) B = A + 1;
			if (H < S.BraceByHoist[0][0]) B = A = 0;
			OutLo = std::max(S.BraceByHoist[A][1], S.BraceByHoist[B][1]);
			OutHi = std::min(S.BraceByHoist[A][2], S.BraceByHoist[B][2]);
		}
		if (Sail >= 0 && Sail < Rig.NumSails)
		{
			const FRigSail& Sl = Rig.Sails[Sail];
			if (Sl.SetBraceLo != 0.0 || Sl.SetBraceHi != 0.0)
			{
				OutLo = std::max(OutLo, Sl.SetBraceLo);
				OutHi = std::min(OutHi, Sl.SetBraceHi);
			}
		}
		if (OutLo > OutHi) OutLo = OutHi = 0.5 * (OutLo + OutHi);
	}

	double RigEase(const FShipRigData& Rig, int Spar, double Hoist, int Sail, double TurnDeg)
	{
		if (Spar < 0 || Spar >= Rig.NumSpars) return 0.0;
		const FRigSpar& S = Rig.Spars[Spar];
		const double A = std::fabs(TurnDeg);
		const double H = std::clamp(Hoist, 0.0, 1.0);
		const double Up = RigTableAt(S.Ease, std::min(S.NumEase, kMaxRigRows), A);
		const double Down = RigTableAt(S.EaseLowered, std::min(S.NumEaseLowered, kMaxRigRows), A);
		double E = Down + (Up - Down) * H;
		if (Sail >= 0 && Sail < Rig.NumSails && Rig.Sails[Sail].NumSetEase > 0)
		{
			const FRigSail& Sl = Rig.Sails[Sail];
			E = std::max(E, RigTableAt(Sl.SetEase, std::min(Sl.NumSetEase, kMaxRigRows), A));
		}
		return E;
	}

	FRigMotion RigSparMotion(const FRigSpar& Spar, double Hoist, double EaseM, double TurnDeg)
	{
		const Vec3 K = Spar.Axis.Normalized();
		const double A = TurnDeg * kRigDegToRad;
		const double C = std::cos(A), S = std::sin(A), V = 1.0 - C;
		FRigMotion Out;
		// Rodrigues: R v = v cos + (k x v) sin + k (k.v)(1 - cos).
		Out.M[0][0] = C + K.X * K.X * V;       Out.M[0][1] = K.X * K.Y * V - K.Z * S; Out.M[0][2] = K.X * K.Z * V + K.Y * S;
		Out.M[1][0] = K.Y * K.X * V + K.Z * S; Out.M[1][1] = C + K.Y * K.Y * V;       Out.M[1][2] = K.Y * K.Z * V - K.X * S;
		Out.M[2][0] = K.Z * K.X * V - K.Y * S; Out.M[2][1] = K.Z * K.Y * V + K.X * S; Out.M[2][2] = C + K.Z * K.Z * V;
		const Vec3 Moved = Spar.Origin + SparForward(Spar) * EaseM + K * ((1.0 - std::clamp(Hoist, 0.0, 1.0)) * Spar.HoistLowered);
		Out.T = Moved - Out.ApplyVector(Spar.Origin);
		return Out;
	}

	FRigMotion RigSailMirror(const FRigSail& Sail)
	{
		FRigMotion Out;
		if (!Sail.bMirror) return Out;
		const Vec3 N = Sail.MirrorNormal.Normalized();
		const double Nv[3] = { N.X, N.Y, N.Z };
		for (int I = 0; I < 3; ++I)
		{
			for (int J = 0; J < 3; ++J) Out.M[I][J] = (I == J ? 1.0 : 0.0) - 2.0 * Nv[I] * Nv[J];
		}
		Out.T = N * (2.0 * N.Dot(Sail.MirrorPoint));
		return Out;
	}

	void FShipRigPose::Reset(const FShipRigData& Rig)
	{
		for (int K = 0; K < kMaxRigSpars; ++K)
		{
			Hoist[K] = 1.0;
			TurnDeg[K] = 0.0;
			Ease[K] = 0.0;
		}
		for (int K = 0; K < kMaxRigSails; ++K)
		{
			Shown[K] = ESailShown::Set;
			bMirrored[K] = false;
		}
		(void)Rig;
	}

	void FShipRigPose::Update(const FShipRigData& Rig, const FShipRigInput& In, double Dt)
	{
		const int NumSpars = std::min(Rig.NumSpars, kMaxRigSpars);
		const int NumSails = std::min(Rig.NumSails, kMaxRigSails);
		double HoistTarget[kMaxRigSpars];
		for (int K = 0; K < kMaxRigSpars; ++K) HoistTarget[K] = 1.0;

		// Each sail's state from what is out; a yard that lowers to furl comes down once its sail is clewed up.
		for (int K = 0; K < NumSails; ++K)
		{
			const FRigSail& S = Rig.Sails[K];
			const double Out = OutOf(In, S);
			const bool bSquare = S.Kind == ERigSailKind::Square && S.Square >= 0 && S.Square < kMaxRigSquare;
			const bool bFurl = bSquare ? In.bSquareFurl[S.Square] : Out < FurledUnder;
			const bool bLowers = bSquare && S.Spar >= 0 && S.Spar < NumSpars && Rig.Spars[S.Spar].HoistLowered < 0.0;
			if (bLowers && bFurl && Out < FurledUnder) HoistTarget[S.Spar] = 0.0;
			if (Out >= SetFrom) Shown[K] = ESailShown::Set;
			else if (bFurl && Out < FurledUnder && (!bLowers || Hoist[S.Spar] <= 0.05)) Shown[K] = ESailShown::Furled;
			else Shown[K] = ESailShown::Clewed;
			bMirrored[K] = S.bMirror && Shown[K] == ESailShown::Set && SideOf(In, S) < 0;
		}

		const double Step = Dt > 0.0 ? Dt / HoistSeconds : 0.0;
		for (int K = 0; K < NumSpars; ++K)
		{
			const FRigSpar& S = Rig.Spars[K];
			Hoist[K] = S.HoistLowered < 0.0 ? MoveToward(Hoist[K], HoistTarget[K], Step) : 1.0;
			double Want = 0.0;
			if (S.Drive == ERigSparDrive::Square && S.Square >= 0 && S.Square < kMaxRigSquare) Want = -In.YardAngle[S.Square] / kRigDegToRad;
			else if (S.Drive == ERigSparDrive::Boom) Want = -In.BoomAngle / kRigDegToRad;
			const int Sail = Rig.SailOnSpar(K);
			const int SetSail = Sail >= 0 && Sail < NumSails && Shown[Sail] == ESailShown::Set ? Sail : -1;
			double Lo = 0.0, Hi = 0.0;
			RigBraceLimits(Rig, K, Hoist[K], SetSail, Lo, Hi);
			TurnDeg[K] = std::clamp(Want, Lo, Hi);
			Ease[K] = RigEase(Rig, K, Hoist[K], SetSail, TurnDeg[K]);
		}
	}

	FRigMotion FShipRigPose::SparMotion(const FShipRigData& Rig, int Spar) const
	{
		if (Spar < 0 || Spar >= std::min(Rig.NumSpars, kMaxRigSpars)) return FRigMotion();
		return RigSparMotion(Rig.Spars[Spar], Hoist[Spar], Ease[Spar], TurnDeg[Spar]);
	}

	FRigMotion FShipRigPose::SailMotion(const FShipRigData& Rig, int Sail) const
	{
		if (Sail < 0 || Sail >= std::min(Rig.NumSails, kMaxRigSails)) return FRigMotion();
		const FRigSail& S = Rig.Sails[Sail];
		const FRigMotion Spar = SparMotion(Rig, S.Spar);
		return bMirrored[Sail] ? Spar * RigSailMirror(S) : Spar;
	}
}
