#include "ShipFrames.h"

#include <algorithm>
#include <cmath>
#include <cstring>

#include "CommonwealthFramesData.inl"

namespace Sailing
{

	namespace
	{
		FShipFramesData MakeCommonwealthFrames()
		{
			FShipFramesData D;
			D.Frames = CommonwealthFramesTable::kFrames;
			D.NumFrames = int(sizeof(CommonwealthFramesTable::kFrames) / sizeof(CommonwealthFramesTable::kFrames[0]));
			D.Poses = CommonwealthFramesTable::kPoses;
			D.NumPoses = int(sizeof(CommonwealthFramesTable::kPoses) / sizeof(CommonwealthFramesTable::kPoses[0]));
			D.HardOverDeg = CommonwealthFramesTable::kHardOverDeg;
			D.WheelTurnsHardOver = CommonwealthFramesTable::kWheelTurnsHardOver;
			D.DoorOpenDeg = CommonwealthFramesTable::kDoorOpenDeg;
			return D;
		}

		/** Rotation by Deg about a unit axis (Rodrigues). */
		void AxisTurn(const Vec3& A, double Deg, double M[3][3])
		{
			const double C = std::cos(Deg * kDegToRad), S = std::sin(Deg * kDegToRad), K = 1.0 - C;
			M[0][0] = C + A.X * A.X * K;       M[0][1] = A.X * A.Y * K - A.Z * S; M[0][2] = A.X * A.Z * K + A.Y * S;
			M[1][0] = A.Y * A.X * K + A.Z * S; M[1][1] = C + A.Y * A.Y * K;       M[1][2] = A.Y * A.Z * K - A.X * S;
			M[2][0] = A.Z * A.X * K - A.Y * S; M[2][1] = A.Z * A.Y * K + A.X * S; M[2][2] = C + A.Z * A.Z * K;
		}

		/** The motion taking the rest frame (origin, axes as columns) to a posed one: P' = R1 S R0^T (P - O0) + O1. */
		FRigMotion FrameToPose(const FShipFrame& Rest, const FRopePosePart& Pose)
		{
			const double R0[3][3] = { { Rest.X.X, Rest.Y.X, Rest.Z.X }, { Rest.X.Y, Rest.Y.Y, Rest.Z.Y }, { Rest.X.Z, Rest.Y.Z, Rest.Z.Z } };
			const double S[3] = { Pose.ScaleX, 1.0, 1.0 };
			FRigMotion Out;
			for (int I = 0; I < 3; ++I)
			{
				for (int J = 0; J < 3; ++J)
				{
					double Sum = 0.0;
					for (int K = 0; K < 3; ++K) Sum += Pose.R[I][K] * S[K] * R0[J][K];   // R0^T[K][J] = R0[J][K]
					Out.M[I][J] = Sum;
				}
			}
			Out.T = Pose.O - Out.ApplyVector(Rest.Origin);
			return Out;
		}

		FRigMotion Blend(const FRigMotion& A, const FRigMotion& B, double T)
		{
			FRigMotion Out;
			for (int I = 0; I < 3; ++I) for (int J = 0; J < 3; ++J) Out.M[I][J] = A.M[I][J] + (B.M[I][J] - A.M[I][J]) * T;
			Out.T = A.T + (B.T - A.T) * T;
			return Out;
		}
	}

	int FShipFramesData::FrameNamed(const char* Name) const
	{
		for (int K = 0; K < NumFrames; ++K) if (std::strcmp(Frames[K].Name, Name) == 0) return K;
		return -1;
	}

	const FShipFramesData& CommonwealthFrames()
	{
		static const FShipFramesData Data = MakeCommonwealthFrames();
		return Data;
	}

	const FShipFramesData* ShipFramesFor(const char* ConfigName)
	{
		if (ConfigName && std::strcmp(ConfigName, "Commonwealth") == 0) return &CommonwealthFrames();
		return nullptr;
	}

	double TillerHelmDeg(const FShipFramesData& Data, double RudderAngleRad)
	{
		// The blade's trailing edge goes to starboard (the bow after it); the tiller, forward of the head, goes the other way.
		return std::clamp(-RudderAngleRad * kRadToDeg, -Data.HardOverDeg, Data.HardOverDeg);
	}

	double WheelTurns(const FShipFramesData& Data, double HelmDeg)
	{
		return Data.HardOverDeg > 0.0 ? HelmDeg / Data.HardOverDeg * Data.WheelTurnsHardOver : 0.0;
	}

	FRigMotion FrameTurn(const FShipFrame& Frame, double Deg, int Axis)
	{
		FRigMotion Out;
		const Vec3& A = Axis == 0 ? Frame.X : (Axis == 1 ? Frame.Y : Frame.Z);
		const double L = A.Length();
		if (L < 1e-9 || Deg == 0.0) return Out;
		AxisTurn(A / L, Deg, Out.M);
		Out.T = Frame.Origin - Out.ApplyVector(Frame.Origin);
		return Out;
	}

	FRigMotion RopePartMotion(const FShipFramesData& Data, const FShipFrame& Frame, double HelmDeg)
	{
		if (Frame.Rope < 0 || Frame.Rope >= kRopeParts || Data.NumPoses == 0) return FRigMotion();
		const double H = std::clamp(HelmDeg, Data.Poses[0].HelmDeg, Data.Poses[Data.NumPoses - 1].HelmDeg);
		int Hi = 0;
		while (Hi < Data.NumPoses - 1 && Data.Poses[Hi].HelmDeg < H) ++Hi;
		const int Lo = std::max(Hi - 1, 0);
		const FRigMotion A = FrameToPose(Frame, Data.Poses[Lo].Part[Frame.Rope]);
		if (Lo == Hi) return A;
		const double Span = Data.Poses[Hi].HelmDeg - Data.Poses[Lo].HelmDeg;
		const double T = Span > 1e-9 ? std::clamp((H - Data.Poses[Lo].HelmDeg) / Span, 0.0, 1.0) : 0.0;
		if (T <= 0.0) return A;
		return Blend(A, FrameToPose(Frame, Data.Poses[Hi].Part[Frame.Rope]), T);
	}

	bool ShipDoorNear(const FShipFrame& Door, const Vec3& Feet, double WithinM)
	{
		const Vec3 D = Feet - Door.Origin;
		// (his feet a step below the hinge on the gun deck; not from the quarterdeck 1.8 m over it or the berth deck under it)
		return D.LengthXY() < WithinM && D.Z > -1.2 && D.Z < 0.6;
	}

	void FShipFramesPose::Reset(const FShipFramesData& Data)
	{
		(void)Data;
		HelmDeg = 0.0;
		for (int K = 0; K < MaxDoors; ++K) { DoorOpen[K] = 0.0; DoorSince[K] = DoorHoldSeconds; }
	}

	void FShipFramesPose::Update(const FShipFramesData& Data, double RudderAngleRad, const Vec3* Feet, double Dt)
	{
		HelmDeg = TillerHelmDeg(Data, RudderAngleRad);
		int Door = 0;
		for (int K = 0; K < Data.NumFrames && Door < MaxDoors; ++K)
		{
			if (Data.Frames[K].Kind != EShipFrameKind::Door) continue;
			if (Feet && ShipDoorNear(Data.Frames[K], *Feet, DoorNearM)) DoorSince[Door] = 0.0;
			else DoorSince[Door] = std::min(DoorSince[Door] + Dt, 1e6);
			const double Want = DoorSince[Door] < DoorHoldSeconds ? 1.0 : 0.0;
			const double Step = Dt / DoorSeconds;
			DoorOpen[Door] = std::clamp(DoorOpen[Door] + std::clamp(Want - DoorOpen[Door], -Step, Step), 0.0, 1.0);
			++Door;
		}
	}

	FRigMotion FShipFramesPose::Motion(const FShipFramesData& Data, int Frame) const
	{
		if (Frame < 0 || Frame >= Data.NumFrames) return FRigMotion();
		const FShipFrame& F = Data.Frames[Frame];
		switch (F.Kind)
		{
		case EShipFrameKind::Tiller:
			return FrameTurn(F, HelmDeg);
		case EShipFrameKind::Rope:
			return RopePartMotion(Data, F, HelmDeg);
		case EShipFrameKind::Door:
		{
			int Door = 0;
			for (int K = 0; K < Frame; ++K) if (Data.Frames[K].Kind == EShipFrameKind::Door) ++Door;
			// (eased: the leaf slows into its stop)
			const double Open = GetDoorOpen(Door);
			const double Eased = Open * Open * (3.0 - 2.0 * Open);
			return FrameTurn(F, F.Sign * Data.DoorOpenDeg * Eased);
		}
		case EShipFrameKind::Wheel:
			// About its axle: a positive turn takes the top of the wheel to port, with the helm's sign (her head to port).
			return FrameTurn(F, 360.0 * WheelTurns(Data, HelmDeg), 0);
		case EShipFrameKind::Capstan:
		default:
			return FRigMotion();
		}
	}
}
