#include "Replay.h"

using namespace Sailing;

namespace
{
	void Store(const FSailStripState* Src, int32 Num, uint8& OutNum, FReplayStrip* Dst)
	{
		OutNum = uint8(FMath::Clamp(Num, 0, kMaxSailStrips));
		for (int32 I = 0; I < OutNum; ++I)
		{
			Dst[I].Angle = float(Src[I].AngleFromCenterline);
			Dst[I].Camber = float(Src[I].Camber);
			Dst[I].Twist = float(Src[I].TwistFromFoot);
			Dst[I].Flow = uint8(Src[I].Flow);
		}
	}

	void Restore(const FReplayStrip* Src, uint8 Num, FSailStripState* Dst, int& OutNum)
	{
		OutNum = Num;
		for (int32 I = 0; I < Num; ++I)
		{
			Dst[I].AngleFromCenterline = Src[I].Angle;
			Dst[I].Camber = Src[I].Camber;
			Dst[I].TwistFromFoot = Src[I].Twist;
			Dst[I].Flow = ESailFlow(Src[I].Flow);
		}
	}
}

void FReplay::Begin(int32 InBoatType, const FString& InLabel, double InStartTime)
{
	BoatType = InBoatType;
	Label = InLabel;
	StartTime = InStartTime;
	Frames.Reset();
}

void FReplay::Record(const FBoatModel& Boat)
{
	const FBoatState& S = Boat.GetState();
	const double T = S.Time - StartTime;
	if (Frames.Num() > 0 && T < Frames.Last().Time + Interval - 1e-6) return;
	if (Frames.Num() >= MaxFrames) Frames.RemoveAt(0, MaxFrames / 10); // keep the latest forty minutes
	FReplayFrame& F = Frames.AddDefaulted_GetRef();
	const FBoatTelemetry& Tel = Boat.GetTelemetry();
	F.Time = T;
	F.State = S;
	F.BoatSpeed = float(Tel.BoatSpeed);
	F.ApparentWindAngle = float(Tel.ApparentWindAngle);
	F.ApparentWindSpeed = float(Tel.ApparentWindSpeed);
	F.Heading = float(Tel.Heading);
	F.Heel = float(Tel.Heel);
	Store(Tel.MainStrips, Tel.NumMainStrips, F.NumStrips[0], F.Strips[0]);
	Store(Tel.JibStrips, Tel.NumJibStrips, F.NumStrips[1], F.Strips[1]);
	Store(Tel.SpinStrips, Tel.NumSpinStrips, F.NumStrips[2], F.Strips[2]);
}

bool FReplay::Sample(double T, FReplayFrame& Out) const
{
	if (IsEmpty() || T < 0.0 || T > Duration()) return false;
	// Frames are evenly spaced (until the oldest are dropped): find the pair around T.
	int32 Lo = 0, Hi = Frames.Num() - 1;
	while (Hi - Lo > 1)
	{
		const int32 Mid = (Lo + Hi) / 2;
		(Frames[Mid].Time <= T ? Lo : Hi) = Mid;
	}
	const FReplayFrame& A = Frames[Lo];
	const FReplayFrame& B = Frames[Hi];
	const double W = B.Time > A.Time ? FMath::Clamp((T - A.Time) / (B.Time - A.Time), 0.0, 1.0) : 0.0;
	Out = W < 0.5 ? A : B;
	Out.Time = T;
	Out.State.Position = A.State.Position + (B.State.Position - A.State.Position) * W;
	const FQuat QA(A.State.Orientation.X, A.State.Orientation.Y, A.State.Orientation.Z, A.State.Orientation.W);
	const FQuat QB(B.State.Orientation.X, B.State.Orientation.Y, B.State.Orientation.Z, B.State.Orientation.W);
	const FQuat Q = FQuat::Slerp(QA, QB, W);
	Out.State.Orientation = Quat(Q.X, Q.Y, Q.Z, Q.W);
	Out.State.BoomAngle = A.State.BoomAngle + (B.State.BoomAngle - A.State.BoomAngle) * W;
	Out.State.RudderAngle = A.State.RudderAngle + (B.State.RudderAngle - A.State.RudderAngle) * W;
	return true;
}

void FReplay::Apply(const FReplayFrame& Frame, FBoatModel& Boat)
{
	const double Time = Boat.GetState().Time;
	Boat.GetMutableState() = Frame.State;
	Boat.GetMutableState().Time = Time;
	FBoatTelemetry& Tel = Boat.GetMutableTelemetry();
	Tel.BoatSpeed = Frame.BoatSpeed;
	Tel.ApparentWindAngle = Frame.ApparentWindAngle;
	Tel.ApparentWindSpeed = Frame.ApparentWindSpeed;
	Tel.Heading = Frame.Heading;
	Tel.Heel = Frame.Heel;
	Restore(Frame.Strips[0], Frame.NumStrips[0], Tel.MainStrips, Tel.NumMainStrips);
	Restore(Frame.Strips[1], Frame.NumStrips[1], Tel.JibStrips, Tel.NumJibStrips);
	Restore(Frame.Strips[2], Frame.NumStrips[2], Tel.SpinStrips, Tel.NumSpinStrips);
}
