#include "SailCloth.h"
#include "ProceduralMeshComponent.h"
#include "SailingSim.h"

using namespace Sailing;

ETelltaleState JibTelltaleState(const FSailStripState& St, bool bWindwardFace)
{
	if (bWindwardFace)
	{
		// The windward ribbon lifts when you pinch (angle of attack at or under the luff angle) or the luff bubbles.
		const bool bLifting = St.Flow == ESailFlow::Luffing || St.Flow == ESailFlow::Backed || St.AlphaN < St.LuffAlpha + 3.0 * kDegToRad;
		return bLifting ? ETelltaleState::Lifting : ETelltaleState::Streaming;
	}
	// The leeward ribbon stalls (droops and twirls) when over-sheeted or sailed too low for the trim.
	if (St.Flow == ESailFlow::Stalled) return ETelltaleState::Stalled;
	if (St.Flow == ESailFlow::Luffing || St.Flow == ESailFlow::Backed) return ETelltaleState::Fluttering;
	return ETelltaleState::Streaming;
}

ETelltaleState LeechTelltaleState(const FSailStripState& St)
{
	if (St.Flow == ESailFlow::Stalled) return ETelltaleState::Stalled;   // curls behind the leech
	if (St.Flow == ESailFlow::Luffing || St.Flow == ESailFlow::Backed) return ETelltaleState::Fluttering;
	return ETelltaleState::Streaming;
}

void FSailCloth::Init(const FSailGeometry& InGeo, ESailKind InKind)
{
	Geo = InGeo;
	Kind = InKind;
	NumStrips = Geo.NumStrips;
	bStarted = false;
	if (NumStrips <= 0) return;
	ZFoot = Geo.Strips[0].ZBottom;
	ZHead = Geo.Strips[NumStrips - 1].ZTop;
	LuffZ0 = 0.5 * (Geo.Strips[0].ZBottom + Geo.Strips[0].ZTop);
	LuffSlope = NumStrips > 1 ? (Geo.Strips[NumStrips - 1].LuffX - Geo.Strips[0].LuffX) / (0.5 * (Geo.Strips[NumStrips - 1].ZBottom + Geo.Strips[NumStrips - 1].ZTop) - LuffZ0) : 0.0;

	// Planform chord per row: through the strips' mid-heights, out to the foot, and in to a headboard at the top.
	RowChord.SetNum(Rows);
	for (int32 R = 0; R < Rows; ++R)
	{
		const double Z = ZFoot + (ZHead - ZFoot) * R / (Rows - 1);
		double Chord;
		const double ZC0 = 0.5 * (Geo.Strips[0].ZBottom + Geo.Strips[0].ZTop);
		const double ZCN = 0.5 * (Geo.Strips[NumStrips - 1].ZBottom + Geo.Strips[NumStrips - 1].ZTop);
		if (Z <= ZC0 || NumStrips == 1)
		{
			const double Slope = NumStrips > 1 ? (Geo.Strips[1].Chord - Geo.Strips[0].Chord) / (0.5 * (Geo.Strips[1].ZBottom + Geo.Strips[1].ZTop) - ZC0) : 0.0;
			Chord = Geo.Strips[0].Chord + Slope * (Z - ZC0);
		}
		else if (Z >= ZCN)
		{
			const double Head = Kind == ESailKind::Main ? 0.14 : (Kind == ESailKind::Jib ? 0.04 : 0.35 * Geo.Strips[NumStrips - 1].Chord);
			Chord = FMath::Lerp(Geo.Strips[NumStrips - 1].Chord, Head, (Z - ZCN) / FMath::Max(ZHead - ZCN, 1e-3));
		}
		else
		{
			int32 I = 0;
			while (I + 1 < NumStrips && 0.5 * (Geo.Strips[I + 1].ZBottom + Geo.Strips[I + 1].ZTop) < Z) ++I;
			const double Za = 0.5 * (Geo.Strips[I].ZBottom + Geo.Strips[I].ZTop), Zb = 0.5 * (Geo.Strips[I + 1].ZBottom + Geo.Strips[I + 1].ZTop);
			Chord = FMath::Lerp(Geo.Strips[I].Chord, Geo.Strips[I + 1].Chord, (Z - Za) / (Zb - Za));
		}
		RowChord[R] = FMath::Max(Chord, 0.03);
	}

	const int32 N = Rows * Cols;
	Pos.SetNum(N);
	Prev.SetNum(N);
	Target.SetNum(N);
	UVMeters.SetNum(N);
	UVNormal.SetNum(N);
	UVLeech.SetNum(N);
	RowLoad.Init(1.f, Rows);
	for (int32 R = 0; R < Rows; ++R)
	{
		const double V = double(R) / (Rows - 1);
		for (int32 C = 0; C < Cols; ++C)
		{
			const double U = double(C) / (Cols - 1);
			UVMeters[Index(R, C)] = FVector2D(U * RowChord[R], V * (ZHead - ZFoot));
			UVNormal[Index(R, C)] = FVector2D(U, V);
			UVLeech[Index(R, C)] = FVector2D((1.0 - U) * RowChord[R], 0.0);
		}
	}
}

void FSailCloth::RowAt(const FSailStripState* Strips, int32 Side, int32 R, FRowShape& Out) const
{
	Out.Z = ZFoot + (ZHead - ZFoot) * R / (Rows - 1);
	Out.LuffX = Geo.Strips[0].LuffX + LuffSlope * (Out.Z - LuffZ0);
	Out.Chord = RowChord[R];
	// Strip state at this height: between the two strips whose mid-heights bracket it.
	int32 A = 0, B = 0;
	double T = 0.0;
	for (int32 I = 0; I < NumStrips; ++I)
	{
		const double Zc = 0.5 * (Geo.Strips[I].ZBottom + Geo.Strips[I].ZTop);
		if (Zc <= Out.Z) A = I;
	}
	B = FMath::Min(A + 1, NumStrips - 1);
	const double Za = 0.5 * (Geo.Strips[A].ZBottom + Geo.Strips[A].ZTop), Zb = 0.5 * (Geo.Strips[B].ZBottom + Geo.Strips[B].ZTop);
	T = B != A ? FMath::Clamp((Out.Z - Za) / (Zb - Za), 0.0, 1.0) : 0.0;
	if (Out.Z < 0.5 * (Geo.Strips[0].ZBottom + Geo.Strips[0].ZTop)) { A = B = 0; T = 0.0; }
	const FSailStripState& SA = Strips[A];
	const FSailStripState& SB = Strips[B];
	Out.Angle = FMath::Lerp(SA.AngleFromCenterline, SB.AngleFromCenterline, T) * Side;
	// docs/sails-1/: a luffing main or jib still has its battens and leech tension (0.15); only a spinnaker goes slack.
	const double LuffLoad = Kind == ESailKind::Spinnaker ? 0.05 : 0.15;
	auto Load = [LuffLoad](const FSailStripState& S)
	{
		switch (S.Flow)
		{
		case ESailFlow::Luffing: return LuffLoad;
		case ESailFlow::Backed: return 0.5;
		case ESailFlow::Stalled: return 0.85;
		default: return 1.0;
		}
	};
	Out.Load = FMath::Lerp(Load(SA), Load(SB), T);
	Out.Camber = FMath::Lerp(SA.Camber, SB.Camber, T);
	// A backed sail bulges to windward.
	if (SA.Flow == ESailFlow::Backed && SB.Flow == ESailFlow::Backed) Out.Camber = -Out.Camber;
}

void FSailCloth::ComputeTarget(const FSailStripState* Strips, int32 Side, TArray<FVector>& Out) const
{
	Out.SetNum(Rows * Cols);
	for (int32 R = 0; R < Rows; ++R)
	{
		FRowShape Row;
		RowAt(Strips, Side, R, Row);
		const Vec3 Chord = SailChordDir(Row.Angle, Side);
		const Vec3 Leeward = Vec3(Chord.Y, -Chord.X, 0.0) * Side;
		for (int32 C = 0; C < Cols; ++C)
		{
			const double U = double(C) / (Cols - 1);
			// A sail's section: deepest a little forward of mid-chord (about 42%).
			double Depth = 4.0 * Row.Camber * Row.Chord * U * (1.0 - U) * (1.0 + 0.3 * (1.0 - 2.0 * U));
			if (Kind == ESailKind::Spinnaker)
			{
				// A symmetric spinnaker is a dome, not a deep jib: fuller in section, and curved top to bottom as well
				// (both edges curl in toward the head and the clews).
				const double V = double(R) / (Rows - 1);
				Depth = 1.5 * Depth + 0.09 * (ZHead - ZFoot) * FMath::Sin(PI * FMath::Min(V * 1.15, 1.0)) * FMath::Sqrt(FMath::Max(FMath::Sin(PI * U), 0.0));
			}
			const Vec3 P = Vec3(Row.LuffX, 0.0, Row.Z) + Chord * (U * Row.Chord) + Leeward * Depth;
			Out[Index(R, C)] = FVector(P.X, P.Y, P.Z) * Sailing::CmPerMeter;
		}
	}
}

void FSailCloth::Step(const FSailStripState* Strips, int32 Side, const FSailClothDrive& Drive)
{
	if (!IsValid()) return;
	ComputeTarget(Strips, Side, Target);
	// docs/sails-1/: a row's tension follows its strip's flow over 0.4 s, not in a frame. In a seaway the masthead's
	// apparent wind swings with every roll, the upper strips flicker between drawing and luffing, and a stiffness that
	// jumped with them threw the head of the main into jagged folds.
	const float Ease = bStarted && Drive.bSimulate ? 1.f - FMath::Exp(-Drive.DeltaSeconds / 0.4f) : 1.f;
	float LoadSum = 0.f;
	for (int32 R = 0; R < Rows; ++R)
	{
		FRowShape Row;
		RowAt(Strips, Side, R, Row);
		RowLoad[R] = FMath::Lerp(RowLoad[R], float(Row.Load), Ease);
		LoadSum += RowLoad[R];
	}
	MeanLoad = LoadSum / Rows;

	// Details the strips can't carry, added to the target: luff wrinkles from a soft halyard in a breeze (fine
	// diagonal folds near the luff), on the main and jib.
	const float Breeze = FMath::Clamp((Drive.ApparentWindKnots - 8.f) / 10.f, 0.f, 1.f);
	const float Wrinkle = Kind != ESailKind::Spinnaker ? 0.9f * Breeze * (1.f - FMath::Clamp(Drive.Cunningham, 0.f, 1.f)) : 0.f;
	if (Wrinkle > 0.01f)
	{
		// (The target's normals: this used to copy the target over the cloth to take them, which reset the cloth every
		// frame of a breeze with a soft halyard and kicked it by the difference.)
		TArray<FVector> N;
		NormalsOf(Target, N);
		for (int32 R = 1; R < Rows - 1; ++R)
		{
			for (int32 C = 1; C < Cols / 3; ++C)
			{
				const FVector2D& UV = UVMeters[Index(R, C)];
				const float Envelope = 1.f - float(C) / (Cols / 3);
				Target[Index(R, C)] += N[Index(R, C)] * (Wrinkle * Envelope * FMath::Sin(2.f * PI * (UV.X * 0.7f + UV.Y * 0.7f) / 0.22f));
			}
		}
	}

	// Leech flutter at speed: a shiver of the last tenth of a drawing sail, a wave running up the leech, as a movement of
	// the target the cloth follows. docs/sails-1/: it was a push on the cloth at 11 Hz with neighbouring rows nearly
	// opposite, near the drawing rows' own ringing (their spring rings at about 6 Hz), so it built up into a row-by-row
	// zigzag along the leech: the dark leech creases.
	const float FlutterWind = FMath::Clamp((Drive.ApparentWindKnots - 10.f) / 10.f, 0.f, 1.f);
	if (Kind != ESailKind::Spinnaker && FlutterWind > 0.f)
	{
		TArray<FVector> N;
		NormalsOf(Target, N);
		for (int32 R = 1; R < Rows - 1; ++R)
		{
			const float Amp = 1.5f * FlutterWind * RowLoad[R];   // cm at the leech
			for (int32 C = Cols - 3; C < Cols; ++C)
			{
				const float U = float(C) / (Cols - 1);
				Target[Index(R, C)] += N[Index(R, C)] * (Amp * FMath::Clamp((U - 0.86f) / 0.14f, 0.f, 1.f) * FMath::Sin(2.f * PI * 9.f * Drive.Time - R * 0.5f));
			}
		}
	}

	// A cloth that has run away from its target (a bad frame's strips, a non-finite vertex) starts again from it.
	bool bRunaway = Pos.Num() != Target.Num();
	for (int32 I = 0; I < Pos.Num() && !bRunaway; ++I)
	{
		bRunaway = !Pos[I].ContainsNaN() ? FVector::DistSquared(Pos[I], Target[I]) > FMath::Square(kRunawayCm) : true;
	}
	if (!Drive.bSimulate || !bStarted || bRunaway)
	{
		Pos = Target;
		Prev = Target;
		bStarted = true;
		if (!Drive.bSimulate) return;
	}

	// Position-based cloth at a fixed 60 Hz (up to three substeps a frame).
	const float H = 1.f / 60.f;
	Accumulator = FMath::Min(Accumulator + Drive.DeltaSeconds, 3.f * H);
	TArray<FVector> Normals;
	Normals.SetNum(Pos.Num());
	while (Accumulator >= H)
	{
		Accumulator -= H;
		ComputeNormals(Normals);
		const float T = Drive.Time - Accumulator;
		for (int32 R = 0; R < Rows; ++R)
		{
			const float Load = RowLoad[R];
			// Drawing rows hold their shape; slack rows follow it only loosely and flog in the wind. The last rows under the
			// head (the headboard and the panels a few centimetres wide below it) hold theirs: docs/sails-1/, their panels
			// were near degenerate and flipped their normals as they flogged.
			const float HeadHold = FMath::Clamp(float(R - (Rows - 4)) / 3.f, 0.f, 1.f);
			const float Stiff = FMath::Max(FMath::Lerp(0.04f, 0.45f, Load * Load), 0.45f * HeadHold);
			// A narrow row flogs less than a wide one (its cloth is short and held at both ends).
			const float Width = float(FMath::Clamp(RowChord[R] / FMath::Max(RowChord[0], 0.1), 0.15, 1.0));
			for (int32 C = 0; C < Cols; ++C)
			{
				const int32 I = Index(R, C);
				const bool bPinned = C == 0 || (Kind == ESailKind::Main && R == 0) || (Kind == ESailKind::Jib && R == 0 && C == Cols - 1)
					|| (Kind == ESailKind::Spinnaker && (R == 0 && (C == 0 || C == Cols - 1))) || (R == Rows - 1 && C == 0);
				if (bPinned)
				{
					Pos[I] = Prev[I] = Target[I];
					continue;
				}
				const float U = float(C) / (Cols - 1);
				const FVector Velocity = (Pos[I] - Prev[I]) * 0.94f;
				Prev[I] = Pos[I];
				FVector Next = Pos[I] + Velocity + (Target[I] - Pos[I]) * Stiff;
				// Flogging: a wave running aft along a slack panel at 3-5 Hz, stronger in more wind.
				const float Slack = (1.f - Load) * Width * (1.f - HeadHold);
				const float Wind = FMath::Clamp(Drive.ApparentWindKnots / 15.f, 0.2f, 1.6f);
				Next += Normals[I] * (Slack * Wind * 1.4f * FMath::Sin(2.f * PI * 4.f * T - U * 9.f + R * 0.25f) * FMath::Sqrt(U + 0.05f));
				// A slack spinnaker sags as it collapses.
				if (Kind == ESailKind::Spinnaker) Next += Drive.GravityBody * (Slack * 0.35f);
				Pos[I] = Next;
			}
		}
		// Keep the cloth's panel lengths (edge constraints, rest lengths from the target), and resist sharp folds:
		// docs/sails-1/: the cloth had only the neighbours' lengths, so nothing stopped it creasing at every vertex; a
		// weaker constraint between every other vertex (a bending stiffness) rounds a fold over a few panels, as
		// sailcloth does.
		for (int32 Pass = 0; Pass < 3; ++Pass)
		{
			auto Edge = [&](int32 A, int32 B, float K)
			{
				const float Rest = FVector::Dist(Target[A], Target[B]);
				FVector D = Pos[B] - Pos[A];
				const float Len = D.Size();
				if (Len < 1e-3f) return;
				const FVector Corr = D * (0.5f * K * (Len - Rest) / Len);
				const bool bA = (A % Cols) == 0, bB = (B % Cols) == 0;
				if (!bA) Pos[A] += bB ? Corr * 2.f : Corr;
				if (!bB) Pos[B] -= bA ? Corr * 2.f : Corr;
			};
			for (int32 R = 0; R < Rows; ++R)
			{
				for (int32 C = 0; C < Cols; ++C)
				{
					if (C + 1 < Cols) Edge(Index(R, C), Index(R, C + 1), 1.f);
					if (R + 1 < Rows) Edge(Index(R, C), Index(R + 1, C), 1.f);
					if (C + 2 < Cols) Edge(Index(R, C), Index(R, C + 2), 0.3f);
					if (R + 2 < Rows) Edge(Index(R, C), Index(R + 2, C), 0.3f);
				}
			}
		}
	}
}

void FSailCloth::NormalsOf(const TArray<FVector>& P, TArray<FVector>& Out)
{
	Out.SetNum(P.Num());
	for (int32 R = 0; R < Rows; ++R)
	{
		for (int32 C = 0; C < Cols; ++C)
		{
			const FVector DU = P[Index(R, FMath::Min(C + 1, Cols - 1))] - P[Index(R, FMath::Max(C - 1, 0))];
			const FVector DV = P[Index(FMath::Min(R + 1, Rows - 1), C)] - P[Index(FMath::Max(R - 1, 0), C)];
			Out[Index(R, C)] = FVector::CrossProduct(DU, DV).GetSafeNormal();
		}
	}
}

void FSailCloth::ComputeTangents(TArray<FProcMeshTangent>& Out) const
{
	Out.SetNum(Pos.Num());
	for (int32 R = 0; R < Rows; ++R)
	{
		for (int32 C = 0; C < Cols; ++C)
		{
			const FVector DU = Pos[Index(R, FMath::Min(C + 1, Cols - 1))] - Pos[Index(R, FMath::Max(C - 1, 0))];
			Out[Index(R, C)] = FProcMeshTangent(DU.GetSafeNormal(), false);
		}
	}
}

void FSailCloth::Triangles(TArray<int32>& Out) const
{
	Out.Reset();
	for (int32 R = 0; R < Rows - 1; ++R)
	{
		for (int32 C = 0; C < Cols - 1; ++C)
		{
			const int32 A = Index(R, C), B = Index(R, C + 1), D = Index(R + 1, C), E = Index(R + 1, C + 1);
			Out.Append({ A, D, B, B, D, E });
		}
	}
}

FVector FSailCloth::PointAt(float U, float V) const
{
	const float Fc = FMath::Clamp(U, 0.f, 1.f) * (Cols - 1), Fr = FMath::Clamp(V, 0.f, 1.f) * (Rows - 1);
	const int32 C0 = FMath::Min(int32(Fc), Cols - 2), R0 = FMath::Min(int32(Fr), Rows - 2);
	const float Tc = Fc - C0, Tr = Fr - R0;
	const FVector A = FMath::Lerp(Pos[Index(R0, C0)], Pos[Index(R0, C0 + 1)], Tc);
	const FVector B = FMath::Lerp(Pos[Index(R0 + 1, C0)], Pos[Index(R0 + 1, C0 + 1)], Tc);
	return FMath::Lerp(A, B, Tr);
}

FVector FSailCloth::ChordTangentAt(float U, float V) const
{
	return (PointAt(FMath::Min(U + 0.05f, 1.f), V) - PointAt(FMath::Max(U - 0.05f, 0.f), V)).GetSafeNormal();
}

FVector FSailCloth::NormalAt(float U, float V) const
{
	const FVector DU = ChordTangentAt(U, V);
	const FVector DV = (PointAt(U, FMath::Min(V + 0.05f, 1.f)) - PointAt(U, FMath::Max(V - 0.05f, 0.f))).GetSafeNormal();
	return FVector::CrossProduct(DU, DV).GetSafeNormal();
}
