#pragma once

#include "SailingPhysicsApi.h"
#include "SailingMath.h"

#include <algorithm>
#include <cmath>
#include <vector>

namespace Sailing
{
	/**
	 * Rope realism phase 1 (docs/rope-lay/): how a rope is laid where it is drawn. Drawing only: the shape never feeds the
	 * simulation (online-readiness rule 1), it has no state between frames and no randomness, so the same inputs give the
	 * same rope to the bit on every machine.
	 *
	 * A line is its free curve (the chord from A to B plus a parabola-shaped sag, as the rig has always drawn it) lifted
	 * where it would pass through something. Today's drape lifted each of ten rings straight up in 2 cm steps; here the lift
	 * is the shape a cable of the same tension takes over the obstacle:
	 *
	 *   1. along the free curve, how far up each sample must go to clear (LiftToClear: continuous, to a millimetre, not in
	 *      2 cm steps), with the edges between a free and a lifted sample found by bisection;
	 *   2. the upper convex hull of those lifts over the chord parameter. Lifting the free curve by a straight line in that
	 *      plane keeps each free span a parabola of the free curve's own curvature, so the rope runs down to an edge in a
	 *      gentle hang (not the sag's dip and a jump), lies on a flat roof (the lifts there are concave, all on the hull)
	 *      and bends only where it meets something;
	 *   3. RoundCorners turns each bend over an edge, a block or a fairlead into a short curve of a given radius, so the rope
	 *      enters fittings on its tangent;
	 *   4. PlaceRings puts a fixed number of rings along it, packed where it bends (the mesh keeps its vertex count);
	 *   5. ClearSpans lifts any ring whose straight span to the next still cuts an edge.
	 *
	 * WinchWraps draws a sheet's turns on a winch drum: in on the drum's tangent, clockwise seen from above, rising.
	 *
	 * Units are the caller's (the rig works in cm); Up is the direction a lift goes (the boat's up).
	 */
	namespace RopeLay
	{
		struct FSettings
		{
			int Samples = 24;           // samples along the free curve: at least this many,
			double MaxSpacing = 6.0;    // no further apart than this (a trunk's corner a few centimetres across is not missed),
			int MaxSamples = 64;        // and at most this many
			double MaxLift = 150.0;     // a point that can't clear within this is left where it is (as the old drape did)
			double Tolerance = 0.1;     // the lift's bisection
			int EdgeRefine = 4;         // bisection steps for an edge between a free and a lifted sample
		};

		/** How far (a share of the rope's radius) a curve over an edge may press into it: the lay's edges are sharp, a real
		 *  deck's are radiused a few millimetres and a loaded rope flattens on them. */
		constexpr double kDipShare = 1.0 / 3.0;

		/** A point of the laid rope: where it is, whether the rope bends there (a hull corner: an edge it rests on; after
		 *  RoundCorners, the middle of the curve that replaced it) and where it is on the free curve (0 to 1). */
		struct FPoint
		{
			Vec3 P;
			bool bCorner = false;
			double T = 0.0;
			double BendR = 0.0;    // RoundCorners' radius here (0: the call's)
			bool bJoint = false;   // where one drawn line of a rope runs on into the next (kept through RoundCorners)
		};

		/** The free curve: chord plus the parabola-shaped sag (4 t (1 - t) of Sag). */
		inline Vec3 FreePoint(const Vec3& A, const Vec3& B, const Vec3& Sag, double T)
		{
			return A + (B - A) * T + Sag * (4.0 * T * (1.0 - T));
		}

		/** How far along Up the point must go to be clear (continuous, to Tolerance), plus Radius; 0 when it is clear, or
		 *  can't clear within MaxLift. */
		template <typename BlockedFn>
		double LiftToClear(const Vec3& P, const Vec3& Up, double Radius, const FSettings& Set, const BlockedFn& Blocked)
		{
			if (!Blocked(P)) return 0.0;
			double Lo = 0.0, Hi = 1.0;
			while (Hi < Set.MaxLift && Blocked(P + Up * Hi)) { Lo = Hi; Hi *= 2.0; }
			if (Hi >= Set.MaxLift)
			{
				Hi = Set.MaxLift;
				if (Blocked(P + Up * Hi)) return 0.0;
			}
			while (Hi - Lo > Set.Tolerance)
			{
				const double Mid = 0.5 * (Lo + Hi);
				if (Blocked(P + Up * Mid)) Lo = Mid; else Hi = Mid;
			}
			return Hi + Radius;
		}

		/** Steps 1 and 2: the line from A to B with its free sag, lifted over what Blocked says is solid. The ends stay at their
		 *  fittings. Out runs from A to B (Samples + 1 points, plus those refined at edges). Returns whether anything was
		 *  lifted (when not, Out is exactly the free curve). */
		template <typename BlockedFn>
		bool Lay(const Vec3& A, const Vec3& B, const Vec3& Sag, double Radius, const Vec3& Up, const FSettings& Set,
			const BlockedFn& Blocked, std::vector<FPoint>& Out)
		{
			const int M = std::clamp(int(std::ceil((B - A).Length() / std::max(Set.MaxSpacing, 1e-6))), std::max(Set.Samples, 2), std::max(Set.MaxSamples, Set.Samples));
			std::vector<double> Ts, Ls;
			Ts.reserve(4 * M);
			Ls.reserve(4 * M);
			// Between two samples where either is lifted, the edge (or a step in the surface: a trunk's side) is found by
			// halving: a midpoint whose lift is off the straight line between its neighbours' (by more than a millimetre),
			// or free where they are lifted, is kept and both halves looked at again, EdgeRefine deep.
			auto Refine = [&](auto&& Self, double T0, double L0, double T1, double L1, int Depth) -> void
			{
				if (Depth <= 0 || (L0 <= 0.0 && L1 <= 0.0)) return;
				const double Tm = 0.5 * (T0 + T1);
				const double Lm = LiftToClear(FreePoint(A, B, Sag, Tm), Up, Radius, Set, Blocked);
				if (std::fabs(Lm - 0.5 * (L0 + L1)) <= 0.1 && (Lm > 0.0) == (L0 > 0.0) && (Lm > 0.0) == (L1 > 0.0)) return;
				Self(Self, T0, L0, Tm, Lm, Depth - 1);
				Ts.push_back(Tm);
				Ls.push_back(Lm);
				Self(Self, Tm, Lm, T1, L1, Depth - 1);
			};
			bool bAny = false;
			for (int I = 0; I <= M; ++I)
			{
				const double T = double(I) / M;
				const double L = (I == 0 || I == M) ? 0.0 : LiftToClear(FreePoint(A, B, Sag, T), Up, Radius, Set, Blocked);
				bAny = bAny || L > 0.0;
				if (I > 0) Refine(Refine, Ts.back(), Ls.back(), T, L, Set.EdgeRefine);
				Ts.push_back(T);
				Ls.push_back(L);
			}
			Out.clear();
			if (!bAny)
			{
				for (double T : Ts) { FPoint Q; Q.P = FreePoint(A, B, Sag, T); Q.T = T; Out.push_back(Q); }
				return false;
			}
			// The upper convex hull of the lifts (monotone chain: Ts ascend).
			std::vector<int> Hull;
			Hull.reserve(Ts.size());
			for (int I = 0; I < int(Ts.size()); ++I)
			{
				while (Hull.size() >= 2)
				{
					const int H0 = Hull[Hull.size() - 2], H1 = Hull.back();
					const double Cross = (Ts[H1] - Ts[H0]) * (Ls[I] - Ls[H0]) - (Ls[H1] - Ls[H0]) * (Ts[I] - Ts[H0]);
					if (Cross >= 0.0) Hull.pop_back(); else break;
				}
				Hull.push_back(I);
			}
			// Each sample lifted by the hull (a straight line between its corners), a corner where the hull turns.
			size_t Seg = 0;
			std::vector<bool> IsCorner(Ts.size(), false);
			for (size_t H = 1; H + 1 < Hull.size(); ++H)
			{
				const int H0 = Hull[H - 1], H1 = Hull[H], H2 = Hull[H + 1];
				const double S0 = (Ls[H1] - Ls[H0]) / std::max(Ts[H1] - Ts[H0], 1e-12);
				const double S1 = (Ls[H2] - Ls[H1]) / std::max(Ts[H2] - Ts[H1], 1e-12);
				// (a corner worth rounding: the lift's slope changes by more than a millimetre over the line's whole length)
				IsCorner[H1] = std::fabs(S1 - S0) > 0.1;
			}
			for (size_t I = 0; I < Ts.size(); ++I)
			{
				while (Seg + 2 < Hull.size() && Ts[Hull[Seg + 1]] <= Ts[I]) ++Seg;
				const int H0 = Hull[Seg], H1 = Hull[Seg + 1];
				const double F = std::clamp((Ts[I] - Ts[H0]) / std::max(Ts[H1] - Ts[H0], 1e-12), 0.0, 1.0);
				const double Lift = Ls[H0] + (Ls[H1] - Ls[H0]) * F;
				FPoint Q;
				Q.P = FreePoint(A, B, Sag, Ts[I]) + Up * Lift;
				Q.bCorner = IsCorner[I];
				Q.T = Ts[I];
				Out.push_back(Q);
			}
			return true;
		}

		/** Step 3: each corner of the polyline (bCorner) becomes a curve of about BendRadius (or the point's own BendR: a
		 *  circular arc between its tangent points, Steps + 1 points, each marked a corner so the rings go on it), tighter where the
		 *  neighbours are close. The ends are never moved; a join (bJoint) stays on exactly one point. */
		inline void RoundCorners(std::vector<FPoint>& Pts, double BendRadius, int Steps, double MaxDip = 1e30)
		{
			if (Pts.size() < 3 || BendRadius <= 0.0) return;
			const size_t N = Pts.size();
			std::vector<FPoint> Out;
			Out.reserve(N + 8 * size_t(Steps));
			Out.push_back(Pts[0]);
			for (size_t I = 1; I + 1 < N; ++I)
			{
				if (!Pts[I].bCorner) { Out.push_back(Pts[I]); continue; }
				const double Rb = Pts[I].BendR > 0.0 ? Pts[I].BendR : BendRadius;
				// A cluster: the lay finds an edge with samples millimetres apart, several of them corners: every corner within two
				// bend radii is one bend. (A join is never merged with anything.)
				size_t Last = I;
				for (size_t K = I + 1; !Pts[I].bJoint && K + 1 < N && !Pts[K].bJoint && (Pts[K].P - Pts[I].P).Length() < 2.0 * Rb; ++K)
				{
					if (Pts[K].bCorner) Last = K;
				}
				// The way in and out, from a bend radius back and ahead of the cluster, stopping at a join or the ends.
				size_t Ib = I - 1, Ia = Last + 1;
				while (Ib > 0 && !Pts[Ib].bJoint && (Pts[Ib].P - Pts[I].P).Length() < Rb) --Ib;
				while (Ia + 1 < N && !Pts[Ia].bJoint && (Pts[Ia].P - Pts[Last].P).Length() < Rb) ++Ia;
				const Vec3 In = Pts[I].P - Pts[Ib].P, OutDir = Pts[Ia].P - Pts[Last].P;
				const double LIn = In.Length(), LOut = OutDir.Length();
				if (LIn < 1e-6 || LOut < 1e-6) { Out.push_back(Pts[I]); continue; }
				const Vec3 DIn = In / LIn, DOut = OutDir / LOut;
				const double Turn = std::acos(std::clamp(DIn.Dot(DOut), -1.0, 1.0));
				// (under 7 degrees it is a rope lying on a curved roof, under 3 a block it barely turns on: no corner to round)
				if (Turn < (Pts[I].bJoint ? 0.05 : 0.12))
				{
					for (size_t K = I; K <= Last; ++K) { FPoint Same = Pts[K]; Same.bCorner = false; Out.push_back(Same); }
					I = Last;
					continue;
				}
				// The bend's apex: where the line in meets the line out (their closest approach), over the cluster.
				Vec3 V = Pts[I].P;
				if (Last > I)
				{
					const Vec3 W0 = Pts[I].P - Pts[Last].P;
					const double B = DIn.Dot(DOut), Den = 1.0 - B * B;
					if (Den > 1e-9)
					{
						const double Sa = (B * DOut.Dot(W0) - DIn.Dot(W0)) / Den, Sb = (DOut.Dot(W0) - B * DIn.Dot(W0)) / Den;
						V = (Pts[I].P + DIn * Sa + Pts[Last].P + DOut * Sb) * 0.5;
					}
				}
				// (an edge the rope lies over, not a block: a curve no deeper under the apex than MaxDip, since the apex is where the
				// lay found the rope must be)
				const double Sec = 1.0 / std::cos(0.5 * std::min(Turn, 2.6)) - 1.0;
				const double RbHere = Pts[I].bJoint || Sec < 1e-9 ? Rb : std::min(Rb, MaxDip / Sec);
				const double D = std::min(RbHere * std::tan(0.5 * std::min(Turn, 2.6)), 0.9 * std::min((V - Pts[Ib].P).Length(), (Pts[Ia].P - V).Length()));
				// The points the curve replaces: those already out past its start (not the rope's start or a join), and
				// those ahead short of its end.
				while (Out.size() > 1 && !Out.back().bJoint && (Out.back().P - V).Dot(DIn) > -D) Out.pop_back();
				const Vec3 T0 = V - DIn * D, T1 = V + DOut * D;
				// A circular arc from T0 to T1 (its centre inside the bend, the radius D / tan(turn / 2): Rb unless the
				// neighbours were too close), each of its points a corner for the rings.
				const Vec3 Inward = (DOut - DIn * DIn.Dot(DOut)).Normalized();
				const double Rad = D / std::tan(0.5 * std::min(Turn, 2.6));
				const Vec3 C = T0 + Inward * Rad, V0 = T0 - C, V1 = T1 - C;
				const double SinT = std::sin(Turn);
				// (a point every 12 degrees, at most Steps + 1)
				const int Arcs = std::clamp(int(std::ceil(Turn / 0.2094)), 1, std::max(Steps, 1));
				for (int K = 0; K <= Arcs; ++K)
				{
					const double U = double(K) / Arcs;
					FPoint Q;
					Q.P = SinT > 1e-9 ? C + V0 * (std::sin((1.0 - U) * Turn) / SinT) + V1 * (std::sin(U * Turn) / SinT) : T0 + (T1 - T0) * U;
					Q.bCorner = true;
					Q.bJoint = Pts[I].bJoint && (Arcs % 2 == 0 ? 2 * K == Arcs : K == Arcs / 2);
					Q.T = Pts[I].T;
					Out.push_back(Q);
				}
				I = Last;
				while (I + 2 < N && !Pts[I + 1].bJoint && (Pts[I + 1].P - V).Dot(DOut) < D) ++I;
			}
			Out.push_back(Pts.back());
			Pts = std::move(Out);
		}

		/** Step 3 for a rope drawn as several lines in a row (a sheet from the clew to its lead block, on to the winch, its
		 *  turns, its tail): the lines' points joined into one polyline, each join rounded on its radius (JoinBend[k], the
		 *  join after Lines[k]; under 0.05 a join that isn't rounded) and the lines' own corners on BendRadius, then split
		 *  back at the middle of each join's curve, so each line ends where the next begins, on the same tangent. A line
		 *  whose first point is more than half a unit from the last one's end keeps it (a gap through a cam's jaws). */
		inline void RoundChain(const std::vector<std::vector<FPoint>*>& Lines, const std::vector<double>& JoinBend, double BendRadius, double MaxDip, int Steps = 4)
		{
			if (Lines.empty()) return;
			std::vector<FPoint> Chain;
			for (size_t K = 0; K < Lines.size(); ++K)
			{
				const std::vector<FPoint>& D = *Lines[K];
				for (size_t I = 0; I < D.size(); ++I)
				{
					if (K > 0 && I == 0 && !Chain.empty() && (D[0].P - Chain.back().P).Length() <= 0.5) continue;
					FPoint Q = D[I];
					Q.bJoint = false;
					Chain.push_back(Q);
				}
				if (K + 1 < Lines.size() && !Chain.empty())
				{
					FPoint& J = Chain.back();
					J.bJoint = true;
					const double R = K < JoinBend.size() ? JoinBend[K] : 0.0;
					J.bCorner = R >= 0.05;
					J.BendR = R;
				}
			}
			RoundCorners(Chain, BendRadius, Steps, MaxDip);
			size_t K = 0;
			Lines[0]->clear();
			for (const FPoint& Q : Chain)
			{
				Lines[K]->push_back(Q);
				if (Q.bJoint && K + 1 < Lines.size())
				{
					Lines[++K]->clear();
					Lines[K]->push_back(Q);
				}
			}
			// (a join lost on the way, which RoundCorners never does: the lines left empty end on the last point)
			for (++K; K < Lines.size(); ++K) { Lines[K]->clear(); Lines[K]->push_back(Chain.back()); }
			for (std::vector<FPoint>* L : Lines) for (FPoint& Q : *L) Q.bJoint = false;
		}

		/** Step 4: Count + 1 rings along the polyline, the first and last on its ends, spaced in equal steps of
		 *  arc / length + Bend x turn / pi: packed where it bends. Each corner (bCorner: the curve over an edge, round a block)
		 *  has a ring on it, so no straight span between two rings cuts under it. Ts (optional) gets each ring's place on the
		 *  free curve. */
		inline void PlaceRings(const std::vector<FPoint>& Pts, int Count, double Bend, std::vector<Vec3>& Rings, std::vector<double>* Ts = nullptr)
		{
			Rings.clear();
			if (Ts) Ts->clear();
			const size_t N = Pts.size();
			if (N < 2 || Count < 1)
			{
				for (int K = 0; K <= Count; ++K) { Rings.push_back(N ? Pts[0].P : Vec3()); if (Ts) Ts->push_back(0.0); }
				return;
			}
			std::vector<double> Len(N - 1), Turn(N, 0.0);
			double Total = 0.0;
			for (size_t I = 0; I + 1 < N; ++I) { Len[I] = (Pts[I + 1].P - Pts[I].P).Length(); Total += Len[I]; }
			for (size_t I = 1; I + 1 < N; ++I)
			{
				if (Len[I - 1] < 1e-9 || Len[I] < 1e-9) continue;
				const Vec3 D0 = (Pts[I].P - Pts[I - 1].P) / Len[I - 1], D1 = (Pts[I + 1].P - Pts[I].P) / Len[I];
				Turn[I] = std::acos(std::clamp(D0.Dot(D1), -1.0, 1.0));
			}
			// Each span's weight: its share of the length, and half the turn at each of its ends.
			std::vector<double> Cum(N, 0.0);
			const double InvTotal = Total > 1e-9 ? 1.0 / Total : 0.0;
			const double InvPi = 1.0 / 3.14159265358979323846;
			for (size_t I = 0; I + 1 < N; ++I)
			{
				const double W = (Total > 1e-9 ? Len[I] * InvTotal : 1.0 / double(N - 1)) + Bend * 0.5 * (Turn[I] + Turn[I + 1]) * InvPi;
				Cum[I + 1] = Cum[I] + W;
			}
			const double WTotal = Cum[N - 1];
			// The corners (an edge's curve, a block's sheave) each get a ring of their own, up to half the rings; the rest go
			// at equal steps of the weight, and the two sets are merged in order along the rope.
			std::vector<size_t> Corners;
			for (size_t I = 1; I + 1 < N; ++I) if (Pts[I].bCorner) Corners.push_back(I);
			const size_t MaxCorners = size_t(Count / 2);
			if (Corners.size() > MaxCorners)
			{
				std::vector<size_t> Kept;
				for (size_t K = 0; K < MaxCorners; ++K) Kept.push_back(Corners[K * Corners.size() / MaxCorners]);
				Corners.swap(Kept);
			}
			const int Free = Count - 1 - int(Corners.size());
			// Where each ring goes, as a weight along the rope: the free ones at equal steps, merged with the corners'.
			struct FSlot { double W; long Corner; };
			std::vector<FSlot> Slots;
			Slots.reserve(size_t(Count) + 1);
			Slots.push_back({ 0.0, -1 });
			size_t C = 0;
			for (int K = 1; K <= Free; ++K)
			{
				const double Target = WTotal * double(K) / double(Free + 1);
				while (C < Corners.size() && Cum[Corners[C]] <= Target) { Slots.push_back({ Cum[Corners[C]], long(Corners[C]) }); ++C; }
				Slots.push_back({ Target, -1 });
			}
			for (; C < Corners.size(); ++C) Slots.push_back({ Cum[Corners[C]], long(Corners[C]) });
			Slots.push_back({ WTotal, -1 });
			// A free ring right next to a corner's would draw a sliver: each free ring keeps a quarter of the mean ring step
			// (in length) from its neighbours where it can (a forward and a backward sweep; corners and ends stay).
			std::vector<double> Arc(N, 0.0);
			for (size_t I = 0; I + 1 < N; ++I) Arc[I + 1] = Arc[I] + Len[I];
			auto ArcAtWeight = [&](double W)
			{
				size_t I = size_t(std::upper_bound(Cum.begin(), Cum.end(), W) - Cum.begin());
				I = std::clamp<size_t>(I, 1, N - 1);
				const double Span = Cum[I] - Cum[I - 1];
				return Arc[I - 1] + (Span > 1e-12 ? std::clamp((W - Cum[I - 1]) / Span, 0.0, 1.0) : 0.0) * Len[I - 1];
			};
			const size_t S = Slots.size();
			std::vector<double> At(S);
			for (size_t K = 0; K < S; ++K) At[K] = Slots[K].Corner >= 0 ? Arc[size_t(Slots[K].Corner)] : ArcAtWeight(Slots[K].W);
			At[0] = 0.0;
			At[S - 1] = Total;
			const double Gap = 0.25 * Total / Count;
			for (size_t K = 1; K + 1 < S; ++K) if (Slots[K].Corner < 0) At[K] = std::max(At[K], At[K - 1] + Gap);
			for (size_t K = S - 2; K >= 1; --K)
			{
				if (Slots[K].Corner < 0)
				{
					At[K] = std::min(At[K], At[K + 1] - Gap);
					if (At[K] < At[K - 1] + Gap) At[K] = 0.5 * (At[K - 1] + At[K + 1]);
				}
				if (K == 1) break;
			}
			Rings.reserve(S);
			size_t J = 0;
			for (size_t K = 0; K < S; ++K)
			{
				if (K == 0) { Rings.push_back(Pts[0].P); if (Ts) Ts->push_back(Pts[0].T); continue; }
				if (K + 1 == S) { Rings.push_back(Pts[N - 1].P); if (Ts) Ts->push_back(Pts[N - 1].T); continue; }
				if (Slots[K].Corner >= 0)
				{
					Rings.push_back(Pts[size_t(Slots[K].Corner)].P);
					if (Ts) Ts->push_back(Pts[size_t(Slots[K].Corner)].T);
					continue;
				}
				const double Target = std::clamp(At[K], 0.0, Total);
				while (J > 0 && Arc[J] > Target) --J;
				while (J + 2 < N && Arc[J + 1] < Target) ++J;
				const double F = Len[J] > 1e-12 ? std::clamp((Target - Arc[J]) / Len[J], 0.0, 1.0) : 0.0;
				Rings.push_back(Pts[J].P + (Pts[J + 1].P - Pts[J].P) * F);
				if (Ts) Ts->push_back(Pts[J].T + (Pts[J + 1].T - Pts[J].T) * F);
			}
		}

		/** Step 5: a straight span between two rings can still cut a corner the curve went round: each span is checked at its
		 *  quarters (and no further apart than MaxStep along it, when given), and a point inside lifts the span's free rings
		 *  (the ends stay at their fittings) until it clears. Returns the rings lifted. */
		template <typename BlockedFn>
		int ClearSpans(std::vector<Vec3>& Rings, double Radius, const Vec3& Up, const FSettings& Set, const BlockedFn& Blocked, int Passes = 3,
			double MaxStep = 0.0)
		{
			int Lifted = 0;
			const int N = int(Rings.size());
			for (int Pass = 0; Pass < Passes; ++Pass)
			{
				bool bAny = false;
				// The rings themselves first, by the rope's underside less what a curve over an edge may press into it
				// (MaxDip: a third of the radius, kDipShare), then the spans.
				for (int I = 1; I + 1 < N; ++I)
				{
					const double Need = LiftToClear(Rings[I] - Up * (Radius * (1.0 - kDipShare)), Up, 0.0, Set, Blocked);
					if (Need > 0.0) { Rings[I] += Up * Need; ++Lifted; bAny = true; }
				}
				for (int I = 0; I + 1 < N; ++I)
				{
					// (its middle first, then the rest of its parts: quarters, or finer for a thin thing a quarter-span check
					// can step over, a lifeline's 3 cm wire crossed at its corner)
					int Parts = 4;
					if (MaxStep > 0.0) Parts = std::clamp(int(std::ceil((Rings[I + 1] - Rings[I]).Length() / MaxStep)), 4, 64);
					// (the lift is the most any of its points needs: lifting by the first one found climbed a steep span over a
					// sailor's shoulder a few millimetres a pass)
					const bool bFree0 = I > 0, bFree1 = I + 1 < N - 1;
					double Lift = 0.0;
					for (int QI = 0; QI < Parts; ++QI)
					{
						if (QI > 0 && 2 * QI == Parts) continue;
						const double Q = QI == 0 ? 0.5 : double(QI) / Parts;
						const double Need = LiftToClear(Rings[I] + (Rings[I + 1] - Rings[I]) * Q, Up, Radius, Set, Blocked);
						if (Need <= 0.0) continue;
						// (next to an end held at its fitting, the free ring goes up enough to raise the point that much)
						Lift = std::max(Lift, bFree0 && bFree1 ? Need : bFree1 ? Need / Q : bFree0 ? Need / (1.0 - Q) : 0.0);
					}
					if (Lift > 0.0)
					{
						if (bFree0) Rings[I] += Up * Lift;
						if (bFree1) Rings[I + 1] += Up * Lift;
						++Lifted;
						bAny = true;
					}
				}
				if (!bAny) break;
			}
			return Lifted;
		}

		/** Steps 1 to 5 for one line on its own: Count + 1 rings from A to B. BendRadius rounds the edges it rests on (the
		 *  rope's own stiffness and the gelcoat's radius); Bend packs rings at bends (0.35 in the rig). The spans between
		 *  the rings are checked when the line was lifted, or always with bCheckSpans (a line near a sailor or a lifeline,
		 *  thin things a span can step over between samples). Returns whether the line was lifted. */
		template <typename BlockedFn>
		bool LayRings(const Vec3& A, const Vec3& B, const Vec3& Sag, double Radius, const Vec3& Up, const FSettings& Set,
			const BlockedFn& Blocked, int Count, double BendRadius, double Bend, bool bCheckSpans, std::vector<FPoint>& Scratch,
			std::vector<Vec3>& Rings)
		{
			const bool bLifted = Lay(A, B, Sag, Radius, Up, Set, Blocked, Scratch);
			if (bLifted) RoundCorners(Scratch, BendRadius, 4, kDipShare * Radius);
			std::vector<double> Ts;
			PlaceRings(Scratch, Count, Bend, Rings, bLifted ? nullptr : &Ts);
			// A free line's rings are on its curve itself, not on the samples' chords.
			if (!bLifted) for (size_t K = 0; K < Rings.size(); ++K) Rings[K] = FreePoint(A, B, Sag, Ts[K]);
			if (bLifted || bCheckSpans) ClearSpans(Rings, Radius, Up, Set, Blocked);
			return bLifted;
		}

		/** The angle (rad, about Up = +Z) where a rope arriving from From meets a drum of radius R at Centre on its tangent,
		 *  winding clockwise seen from above (+X toward +Y in the boat frame, the way a winch turns). */
		inline double DrumEntryAngle(const Vec3& From, const Vec3& Centre, double R)
		{
			const double Vx = From.X - Centre.X, Vy = From.Y - Centre.Y;
			const double D = std::max(std::sqrt(Vx * Vx + Vy * Vy), R * 1.0001);
			const double Phi = std::atan2(Vy, Vx), Alpha = std::acos(R / D);
			// Of the two tangent points, the one where the rope's way in runs with the drum's turn.
			for (const double Theta : { Phi + Alpha, Phi - Alpha })
			{
				const double Px = Centre.X + R * std::cos(Theta), Py = Centre.Y + R * std::sin(Theta);
				if ((Px - From.X) * -std::sin(Theta) + (Py - From.Y) * std::cos(Theta) > 0.0) return Theta;
			}
			return Phi + Alpha;
		}

		/** A sheet's turns on a vertical winch drum: from the tangent point where it arrives from From (first point), Turns
		 *  turns clockwise seen from above rising from Z0 to Z1 about Centre's axis at radius R (drum plus rope), Steps
		 *  points a turn, then off the top along its tangent for StubLength, dropping StubDrop (the tail). */
		inline void WinchWraps(const Vec3& From, const Vec3& Centre, double R, double Z0, double Z1, double Turns, int StepsPerTurn,
			double StubLength, double StubDrop, std::vector<Vec3>& Out)
		{
			Out.clear();
			const double Theta0 = DrumEntryAngle(Vec3(From.X, From.Y, Z0), Centre, R);
			const int Steps = std::max(int(std::ceil(Turns * StepsPerTurn)), 1);
			const double TwoPi = 2.0 * 3.14159265358979323846;
			for (int K = 0; K <= Steps; ++K)
			{
				const double U = double(K) / Steps;
				const double Theta = Theta0 + TwoPi * Turns * U;
				Out.push_back({ Centre.X + R * std::cos(Theta), Centre.Y + R * std::sin(Theta), Z0 + (Z1 - Z0) * U });
			}
			if (StubLength > 0.0)
			{
				const double ThetaE = Theta0 + TwoPi * Turns;
				const Vec3 Along(-std::sin(ThetaE), std::cos(ThetaE), 0.0);
				Out.push_back(Out.back() + Along * (0.5 * StubLength) + Vec3(0.0, 0.0, -0.15 * StubDrop));
				Out.push_back(Out[Out.size() - 2] + Along * StubLength + Vec3(0.0, 0.0, -StubDrop));
			}
		}

		/** The drawn length of a polyline. */
		inline double Length(const std::vector<Vec3>& P)
		{
			double L = 0.0;
			for (size_t I = 1; I < P.size(); ++I) L += (P[I] - P[I - 1]).Length();
			return L;
		}
	}
}
