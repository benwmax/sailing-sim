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
	WrinkleGrid.Reset();
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

	// (The luff's wrinkles from a soft halyard were a sine on this grid's target: at 20-33 cm a cell their 22 cm waves
	// aliased. They are FSailWrinkles now, on the render grid.)

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

	// The wires: the shape the cloth follows keeps clear of them too (the cloth itself is held clear after every substep).
	TurnDt = bStarted ? Drive.DeltaSeconds : 10.f;
	KeepClear(Target, true);

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
		KeepClear(Pos);
		Prev = Pos;
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
		// The wires come last: the cloth rests against them however the shape and the panels pull.
		const TArray<FVector> Before = Pos;
		KeepClear(Pos);
		for (int32 I = 0; I < Pos.Num(); ++I) Prev[I] += Pos[I] - Before[I]; // pressed onto the wire, not thrown off it
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

void FSailCloth::KeepClear(TArray<FVector>& P, bool bTarget)
{
	if (bTarget) FootTurn = 0.f;
	// (The main's target only: the cloth follows it, and turning or denting the cloth itself kinked it across the spreaders.)
	if (Kind == ESailKind::Main && !bTarget) return;
	if (Obstacles.Num() == 0 || Kind == ESailKind::Spinnaker || P.Num() != Rows * Cols) return;
	constexpr bool bDentOnly = false;
	constexpr float kGapCm = 2.f;      // the cloth's surface off the wire
	constexpr float kNearLuffCm = 12.f; // the luff's own neighbourhood: the mast and the forestay
	constexpr int32 kBarSamples = 6;   // points along a spreader
	// A row turns about its luff, level in the boat frame (the rows are), just far enough to clear every wire it meets at
	// its height: the main's cloth stays inside the shrouds and spreaders (eased onto them it lies against them, the boom
	// stopped at the shroud), and a jib that reaches past them (an overlapping genoa) goes outside. Angles are from aft:
	// both sails run aft from their luffs. A spreader is level: the rows within a panel of it keep clear of it, so no
	// panel spans it.
	const float RowPitch = float(FMath::Max(ZHead - ZFoot, 0.01) / (Rows - 1)) * Sailing::CmPerMeter;
	const bool bMain = Kind == ESailKind::Main;
	if (!bDentOnly)
	{
		// docs/sail-dent/: the main turns as far as the wires need, up to 0.6 rad (34 deg), like a boom stopped at the shroud.
		// At 0.2 (11 deg, "a sheet's few degrees") an eased main running past the shroud was left to the dent below, which
		// folded a deep trough into it at the spreader's height (Bean's playtest, Oct 27).
		constexpr float kMainTurnMax = 0.6f;
		constexpr float kJibTurnMax = 0.35f;
		double Turns[Rows] = {};
		// (The main's foot too, on the boom: the boom is drawn turned with it, FootTurn. A jib's foot ends at its sheet.)
		for (int32 R = bMain ? 0 : 1; R < Rows - 1; ++R)
		{
			const FVector L = P[Index(R, 0)];
			double Z = 0.0, RowReach = 0.0;
			for (int32 C = 0; C < Cols; ++C)
			{
				Z += P[Index(R, C)].Z / Cols;
				RowReach = FMath::Max(RowReach, FVector::Dist2D(P[Index(R, C)], L));
			}
			auto FromAft = [&](const FVector& Q) { return FMath::Atan2(Q.Y - L.Y, -(Q.X - L.X)); }; // + to starboard
			// Where the cloth is at a distance from the luff: the first crossing of that radius along the row.
			auto ClothAt = [&](double Radius, double& Angle) -> bool
			{
				for (int32 C = 1; C < Cols; ++C)
				{
					const FVector A = P[Index(R, C - 1)], B = P[Index(R, C)];
					const double Ra = FVector::Dist2D(A, L), Rb = FVector::Dist2D(B, L);
					if (Rb < Radius || Ra >= Radius) continue;
					Angle = FromAft(FMath::Lerp(A, B, (Radius - Ra) / FMath::Max(Rb - Ra, 1e-3)));
					return true;
				}
				return false;
			};
			double Turn = 0.0; // radians, toward the side the row must go
			for (const FSailObstacle& O : Obstacles)
			{
				const FVector Axis = O.B - O.A;
				const double Len = Axis.Size();
				if (Len < 1.0) continue;
				TArray<FVector, TInlineAllocator<kBarSamples + 1>> Points;
				if (FMath::Abs(Axis.Z) > 0.3 * Len)
				{
					// A shroud or a trapeze wire: where it passes this row's height, and half a row either way (the panels between
					// the rows span it there).
					for (const double Dz : { 0.0, -0.5 * RowPitch, 0.5 * RowPitch })
					{
						const double T = (Z + Dz - O.A.Z) / Axis.Z;
						if (T < 0.0 || T > 1.0 || T * Len < O.FreeA || (1.0 - T) * Len < O.FreeB) continue;
						Points.Add(O.A + Axis * T - FVector(0.0, 0.0, Dz));  // (compared level with the row)
					}
				}
				else
				{
					if (FMath::Abs(Z - 0.5 * (O.A.Z + O.B.Z)) > RowPitch + O.RadiusCm) continue;
					for (int32 K = 1; K <= kBarSamples; ++K) Points.Add(O.A + Axis * (double(K) / kBarSamples));
				}
				for (const FVector& W : Points)
				{
					const double Radius = FVector::Dist2D(W, L);
					if (Radius < kNearLuffCm || Radius > RowReach) continue;
					double Cloth = 0.0;
					if (!ClothAt(Radius, Cloth)) continue;
					const double Wire = FromAft(W);
					if (Wire * Cloth <= 0.0) continue;  // the other side's wires
					const double Margin = (O.RadiusCm + kGapCm) / Radius;
					// The main inside the wire (nearer aft), a jib outside it.
					const double Need = bMain ? FMath::Abs(Cloth) - (FMath::Abs(Wire) - Margin) : (FMath::Abs(Wire) + Margin) - FMath::Abs(Cloth);
					if (Need > 0.0) Turn = FMath::Max(Turn, FMath::Min(Need, 0.6));
				}
			}
			Turns[R] = Turn;
		}
		// The turns, as the cloth can take them. The main turns as one, like a boom stopped at the shroud, as far as its wires
		// need (kMainTurnMax): what is left after that, a twisted head past the upper shroud, is dented below (turning each row
		// its own way tore the sail into steps). A jib's rows turn with their neighbours.
		double Applied[Rows] = {};
		if (bMain)
		{
			double Most = 0.0;
			for (int32 R = 0; R < Rows - 1; ++R) Most = FMath::Max(Most, Turns[R]);
			// Eased over a few tenths of a second: a flogging leech mustn't shake the boom. (The cloth follows the target's turn;
			// only the target turns.)
			MainTurn = FMath::Lerp(MainTurn, FMath::Min(float(Most), kMainTurnMax), 1.f - FMath::Exp(-TurnDt / 0.3f));
			for (int32 R = 0; R < Rows - 1; ++R) Applied[R] = MainTurn;
		}
		else
		{
			for (int32 R = 1; R < Rows - 1; ++R)
			{
				for (int32 K = 1; K < Rows - 1; ++K)
				{
					Applied[R] = FMath::Max(Applied[R], Turns[K] * FMath::Max(0.0, 1.0 - FMath::Abs(R - K) / 4.0));
				}
				Applied[R] = FMath::Min(Applied[R], double(kJibTurnMax));
			}
		}
		// Which way: the main toward aft (against its side), a jib away from it.
		const double Side = FMath::Atan2(P[Index(0, Cols - 1)].Y - P[Index(0, 0)].Y, -(P[Index(0, Cols - 1)].X - P[Index(0, 0)].X)) >= 0.0 ? 1.0 : -1.0;
		for (int32 R = bMain ? 0 : 1; R < Rows - 1; ++R)
		{
			if (Applied[R] <= 0.0) continue;
			const double Rot = (bMain ? -Side : Side) * Applied[R]; // + turns from aft toward starboard
			// The angle from aft grows toward +Y; in the boat frame's XY that is a turn of -Rot about Z (aft is -X).
			const FQuat Q(FVector::UpVector, -Rot);
			if (R == 0 && bTarget) FootTurn = float(-Rot);
			const FVector L = P[Index(R, 0)];
			for (int32 C = 1; C < Cols; ++C)
			{
				FVector& V = P[Index(R, C)];
				const FVector D = V - L;
				V = L + Q.RotateVector(FVector(D.X, D.Y, 0.0)) + FVector(0.0, 0.0, D.Z);
			}
		}
	}
	// The main's belly where it still presses on a wire past the turn (a running main eased onto a shroud near the mast,
	// RigClearance's listed gap): the row dents round the wire, the cloth there lying against it on its own side, full
	// within kDentFlatCm of the wire's radius from the luff and easing out over kDentFallCm either side, the way a sail
	// pressed on a shroud creases round it.
	if (!bMain) return;
	constexpr double kDentFlatCm = 15.0;
	constexpr double kDentFallCm = 45.0;
	for (int32 R = 0; R < Rows - 1; ++R)
	{
		const FVector L = P[Index(R, 0)];
		double Z = 0.0;
		for (int32 C = 0; C < Cols; ++C) Z += P[Index(R, C)].Z / Cols;
		auto FromAft = [&](const FVector& Q) { return FMath::Atan2(Q.Y - L.Y, -(Q.X - L.X)); };
		for (const FSailObstacle& O : Obstacles)
		{
			const FVector Axis = O.B - O.A;
			const double Len = Axis.Size();
			if (Len < 1.0 || FMath::Abs(Axis.Z) <= 0.3 * Len) continue; // the wires (a spreader is level: the turn above keeps it)
			// (At the row's height and half a row either way, as the turn does: the panels between rows span the wire there.
			// At the row's height alone the J/22's main went through her upper shroud just under the spreader tip.)
			for (const double Dz : { 0.0, -0.5 * RowPitch, 0.5 * RowPitch })
			{
				const double T = (Z + Dz - O.A.Z) / Axis.Z;
				if (T < 0.0 || T > 1.0 || T * Len < O.FreeA || (1.0 - T) * Len < O.FreeB) continue;
				const FVector W = O.A + Axis * T - FVector(0.0, 0.0, Dz);
				const double Radius = FVector::Dist2D(W, L);
				if (Radius < kNearLuffCm) continue;
				const double Wire = FromAft(W), Margin = (O.RadiusCm + kGapCm) / Radius;
				// How far past the wire the cloth is at its radius (the largest over the dent's flat), turned back by that at most.
				double Need = 0.0;
				for (int32 C = 1; C < Cols; ++C)
				{
					const FVector& V = P[Index(R, C)];
					const double Rc = FVector::Dist2D(V, L);
					if (FMath::Abs(Rc - Radius) > kDentFlatCm + kDentFallCm) continue;
					const double Cloth = FromAft(V);
					if (Wire * Cloth <= 0.0) continue;
					Need = FMath::Max(Need, FMath::Abs(Cloth) - (FMath::Abs(Wire) - Margin));
				}
				if (Need <= 0.0) continue;
				Need = FMath::Min(Need, 0.6);
				const double Sign = Wire >= 0.0 ? 1.0 : -1.0; // the wire's side: the dent turns back toward aft
				for (int32 C = 1; C < Cols; ++C)
				{
					FVector& V = P[Index(R, C)];
					const FVector D = V - L;
					const double Rc = FVector::Dist2D(V, L);
					const double Off = FMath::Abs(Rc - Radius);
					const double Wt = Off <= kDentFlatCm ? 1.0 : FMath::Max(0.0, 1.0 - (Off - kDentFlatCm) / kDentFallCm);
					const double Cloth = FromAft(V);
					if (Wt <= 0.0 || Cloth * Sign <= 0.0) continue;
					// (No further than aft: a point already inside the wire's angle only moves as far as the dent needs it to.)
					const double Rot = Sign * FMath::Min(Need * Wt, FMath::Abs(Cloth));
					const FQuat Q(FVector::UpVector, Rot);
					V = L + Q.RotateVector(FVector(D.X, D.Y, 0.0)) + FVector(0.0, 0.0, D.Z);
				}
			}
		}
	}
	// docs/sail-spreaders/: a running main eased onto a spreader lies over it. The turn above stops at kMainTurnMax
	// and the wire dents are for the shrouds, so a spreader still stood through the belly (RigClearance: the J/22, Catalina
	// 30, Corsair and maxi running, boom 72-80 deg). Each row near the bar's height is dented back onto the clew's side of
	// every point along it, fully within kSpreaderFlatRows rows of the bar and easing out over kSpreaderFallRows more: the
	// cloth drapes over the bar in a crease running up and down the sail from it, as a running main does on its spreaders
	// (where sailmakers sew the chafe patches).
	constexpr double kSpreaderFlatRows = 0.75;
	constexpr double kSpreaderFallRows = 1.25;
	for (const FSailObstacle& O : Obstacles)
	{
		const FVector Axis = O.B - O.A;
		const double Len = Axis.Size();
		if (Len < 1.0 || FMath::Abs(Axis.Z) > 0.3 * Len) continue; // the level bars only
		const double BarZ = 0.5 * (O.A.Z + O.B.Z);
		for (int32 R = 0; R < Rows - 1; ++R)
		{
			const FVector L = P[Index(R, 0)];
			double Z = 0.0;
			for (int32 C = 0; C < Cols; ++C) Z += P[Index(R, C)].Z / Cols;
			const double Dz = FMath::Abs(Z - BarZ) / FMath::Max(double(RowPitch), 1.0);
			const double Vw = Dz <= kSpreaderFlatRows ? 1.0 : FMath::Max(0.0, 1.0 - (Dz - kSpreaderFlatRows) / kSpreaderFallRows);
			if (Vw <= 0.0) continue;
			auto FromAft = [&](const FVector& Q) { return FMath::Atan2(Q.Y - L.Y, -(Q.X - L.X)); };
			for (int32 K = 1; K <= kBarSamples; ++K)
			{
				const FVector W = O.A + Axis * (double(K) / kBarSamples);
				if (FVector::Dist(W, O.A) < O.FreeA) continue;
				const double Radius = FVector::Dist2D(W, L);
				if (Radius < kNearLuffCm) continue;
				const double Wire = FromAft(W), Margin = (O.RadiusCm + kGapCm) / Radius;
				double Need = 0.0;
				for (int32 C = 1; C < Cols; ++C)
				{
					const FVector& V = P[Index(R, C)];
					if (FMath::Abs(FVector::Dist2D(V, L) - Radius) > kDentFlatCm + kDentFallCm) continue;
					const double Cloth = FromAft(V);
					if (Wire * Cloth <= 0.0) continue;
					Need = FMath::Max(Need, FMath::Abs(Cloth) - (FMath::Abs(Wire) - Margin));
				}
				if (Need <= 0.0) continue;
				Need = FMath::Min(Need, 0.6) * Vw;
				const double Sign = Wire >= 0.0 ? 1.0 : -1.0;
				for (int32 C = 1; C < Cols; ++C)
				{
					FVector& V = P[Index(R, C)];
					const FVector D = V - L;
					const double Off = FMath::Abs(FVector::Dist2D(V, L) - Radius);
					const double Wt = Off <= kDentFlatCm ? 1.0 : FMath::Max(0.0, 1.0 - (Off - kDentFlatCm) / kDentFallCm);
					const double Cloth = FromAft(V);
					if (Wt <= 0.0 || Cloth * Sign <= 0.0) continue;
					const double Rot = Sign * FMath::Min(Need * Wt, FMath::Abs(Cloth));
					const FQuat Q(FVector::UpVector, Rot);
					V = L + Q.RotateVector(FVector(D.X, D.Y, 0.0)) + FVector(0.0, 0.0, D.Z);
				}
			}
		}
	}
}

FSailWrinkles SailWrinklesFor(const FSailCloth& Cloth, const Sailing::FSailStripState* Strips, const FSailClothDrive& Drive)
{
	FSailWrinkles W;
	if (!Cloth.IsValid() || Cloth.GetKind() == ESailKind::Spinnaker || !Drive.bSimulate) return W;
	const TArray<FVector2D>& UV = Cloth.UV0();
	W.Tack = UV[0];
	W.Clew = UV[FSailCloth::Cols - 1];
	W.Head = UV[(FSailCloth::Rows - 1) * FSailCloth::Cols];
	// The sail's normal force, q A |C_L| over its strips, and half of it to the clew and half to the head (the leech
	// carries the load between them; the luff's half goes to the mast and forestay).
	double Force = 0.0, Q = 0.0;
	const int32 N = Cloth.GetNumStrips();
	for (int32 K = 0; K < N; ++K)
	{
		const double V = Strips[K].ApparentSpeed;
		Q += 0.5 * 1.225 * V * V / N;
		Force += 0.5 * 1.225 * V * V * FMath::Abs(Strips[K].LiftCoefficient) / N;
	}
	Force *= Cloth.Geometry().TotalArea * Cloth.Load();
	W.SheetN = 0.5 * Force;
	W.HalyardN = 0.5 * Force;
	// A soft halyard in a breeze leaves up to 0.4 % more cloth behind the luff than along it.
	const double Breeze = FMath::Clamp((Drive.ApparentWindKnots - 8.0) / 10.0, 0.0, 1.0);
	W.LuffStrain = 0.004 * Breeze * (1.0 - FMath::Clamp(double(Drive.Cunningham), 0.0, 1.0));
	// Across them, the membrane's hoop tension q R, R = chord / (8 camber) for a circular-arc section.
	const double Foot = FVector2D::Distance(W.Tack, W.Clew);
	W.LuffTension = FMath::Max(Q * Foot / (8.0 * FMath::Max(Cloth.Geometry().BaseCamber, 0.05)), 1.0);
	W.bOn = Force > 1.0 || W.LuffStrain > 0.0;
	return W;
}

void SailCornerWrinkle(double F, double Beta, double R, double& OutLambda, double& OutAmp)
{
	const double Tr = F / (FMath::Max(Beta, 0.2) * FMath::Max(R, 0.05));
	const double Strain = FMath::Min(FSailWrinkles::Poisson * Tr / FSailWrinkles::BiasStiffness, 0.01);
	OutLambda = 2.0 * UE_DOUBLE_PI * FMath::Pow(FSailWrinkles::BendingStiffness * R * R / FMath::Max(Tr, 1.0), 0.25);
	OutAmp = OutLambda / UE_DOUBLE_PI * FMath::Sqrt(Strain);
}

float SailWrinkleCm(const FSailWrinkles& W, const FVector2D& UVm, float CellU, float CellV)
{
	if (!W.bOn) return 0.f;
	// A wavelength under three cells along its own direction (Dir: across the crests) fades out (two and a half cells and
	// less is gone): no aliasing.
	auto Resolved = [CellU, CellV](double Lambda, const FVector2D& Dir)
	{
		const double Cell = FMath::Max(FMath::Sqrt(FMath::Square(CellU * Dir.X) + FMath::Square(CellV * Dir.Y)), 1e-3);
		return FMath::Clamp((Lambda / Cell - 2.5) / 1.5, 0.0, 1.0);
	};
	double Offset = 0.0;
	const double Foot = FVector2D::Distance(W.Tack, W.Clew);
	// The fans: radial wrinkles inside the corner's angle, from its reinforcing patch (12 cm) to a third of the foot.
	auto Fan = [&](const FVector2D& Corner, const FVector2D& EdgeA, const FVector2D& EdgeB, double F)
	{
		if (F <= 0.0) return;
		const FVector2D D = UVm - Corner;
		const double R = D.Size();
		const double RMax = 0.33 * Foot;
		if (R < 0.12 || R > RMax) return;
		const FVector2D A = (EdgeA - Corner).GetSafeNormal(), B = (EdgeB - Corner).GetSafeNormal();
		const double Beta = FMath::Acos(FMath::Clamp(FVector2D::DotProduct(A, B), -1.0, 1.0));
		const FVector2D Mid = (A + B).GetSafeNormal();
		const FVector2D Dir = D / R;
		const double Theta = FMath::Atan2(FVector2D::CrossProduct(Mid, Dir), FVector2D::DotProduct(Mid, Dir));
		const double Edge = FMath::Clamp(1.0 - FMath::Abs(Theta) / (0.5 * Beta), 0.0, 1.0);
		if (Edge <= 0.0) return;
		double Lambda, Amp;
		SailCornerWrinkle(F, Beta, R, Lambda, Amp);
		// Crests run out from the corner; between them, the arc's waves (they coarsen outward as the tension falls).
		const double Phase = 2.0 * UE_DOUBLE_PI * Theta * R / Lambda;
		const double Fade = FMath::SmoothStep(0.12, 0.2, R) * (1.0 - FMath::SmoothStep(0.6 * RMax, RMax, R)) * FMath::Sin(0.5 * UE_DOUBLE_PI * Edge);
		Offset += Amp * Fade * Resolved(Lambda, FVector2D(-Dir.Y, Dir.X)) * FMath::Sin(Phase);
	};
	Fan(W.Clew, W.Tack, W.Head, W.SheetN);
	Fan(W.Head, W.Tack, W.Clew, W.HalyardN);
	// The luff: across it (crests running back from the luff), within its first 60 cm.
	if (W.LuffStrain > 0.0 && UVm.X < 0.6)
	{
		const double L = 0.3;
		const double Lambda = 2.0 * UE_DOUBLE_PI * FMath::Pow(FSailWrinkles::BendingStiffness * L * L / W.LuffTension, 0.25);
		const double Amp = Lambda / UE_DOUBLE_PI * FMath::Sqrt(W.LuffStrain);
		const double Fade = 1.0 - FMath::SmoothStep(0.15, 0.6, UVm.X);
		Offset += Amp * Fade * Resolved(Lambda, FVector2D(0.0, 1.0)) * FMath::Sin(2.0 * UE_DOUBLE_PI * UVm.Y / Lambda);
	}
	return float(Offset * Sailing::CmPerMeter);
}
