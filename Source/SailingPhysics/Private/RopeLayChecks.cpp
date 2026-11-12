#include "RopeLayChecks.h"
#include "RopeLay.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <string>

namespace Sailing
{
	namespace
	{
		using namespace RopeLay;

		constexpr double kRadius = 0.45;   // a jib sheet (cm), as the rig draws it
		constexpr int kRings = 24;         // the player's boat's rings a line
		constexpr double kBend = 0.35;
		const Vec3 kUp(0.0, 0.0, 1.0);

		std::string Fmt(const char* Format, double A = 0.0, double B = 0.0, double C = 0.0, double D = 0.0)
		{
			char Buf[256];
			std::snprintf(Buf, sizeof(Buf), Format, A, B, C, D);
			return Buf;
		}

		/** The model trunk (cm, boat frame): the deck at 20 cm everywhere, a cabin trunk from x 90 to 245 whose roof is at 70,
		 *  its faces sloping over 10 cm, 60 cm either side of the centreline. */
		double TrunkTop(double X, double Y)
		{
			if (std::fabs(Y) > 60.0) return 20.0;
			if (X < 80.0 || X > 255.0) return 20.0;
			if (X < 90.0) return 20.0 + 50.0 * (X - 80.0) / 10.0;
			if (X > 245.0) return 20.0 + 50.0 * (255.0 - X) / 10.0;
			return 70.0;
		}
		struct FTrunk
		{
			bool operator()(const Vec3& P) const { return P.Z < TrunkTop(P.X, P.Y); }
		};
		struct FNothing
		{
			bool operator()(const Vec3&) const { return false; }
		};

		/** How deep the rope's centre is inside the trunk: the shortest way out along the six axes, up to 30 cm, as
		 *  SailingSim.Visual.RigClearance measures it in the boat. */
		double DepthInTrunk(const Vec3& P)
		{
			auto Inside = [](const Vec3& Q) { return Q.Z < TrunkTop(Q.X, Q.Y); };
			if (!Inside(P)) return 0.0;
			double Best = 30.0;
			for (const Vec3& Dir : { Vec3(0, 0, 1), Vec3(0, 0, -1), Vec3(0, 1, 0), Vec3(0, -1, 0), Vec3(1, 0, 0), Vec3(-1, 0, 0) })
			{
				for (double S = 0.01; S < Best; S += 0.01)
				{
					if (!Inside(P + Dir * S)) { Best = S; break; }
				}
			}
			return Best;
		}

		/** SagOf (BoatModelVisuals.cpp): across the line, in the plane of the line and gravity, the parabola's depth. */
		Vec3 SagOf(const Vec3& A, const Vec3& B, double Slack)
		{
			const Vec3 D = B - A;
			const double Len = D.Length();
			const Vec3 Dir = D / Len, Down(0.0, 0.0, -1.0);
			return (Down - Dir * Down.Dot(Dir)).Normalized() * (Len * std::sqrt(Slack * 3.0 / 8.0));
		}

		/** Today's drape (BoatModelVisuals.cpp before the rope lay), for comparison: ten segments on the free curve, each
		 *  ring lifted straight up in 2 cm steps to clear any point within half a span of it, then up to six passes lifting
		 *  the free rings of a span whose eighths are still inside. */
		template <typename BlockedFn>
		std::vector<Vec3> OldDrape(const Vec3& A, const Vec3& B, const Vec3& Sag, double Radius, const BlockedFn& Blocked)
		{
			constexpr int Segs = 10;
			double Lift[Segs + 1] = {};
			auto Under = [&](const Vec3& C) -> double
			{
				if (!Blocked(C)) return 0.0;
				double Up = 2.0;
				while (Up < 150.0 && Blocked(C + Vec3(0, 0, Up))) Up += 2.0;
				return Up < 150.0 ? Up + Radius : 0.0;
			};
			auto Point = [&](int I) { return FreePoint(A, B, Sag, double(I) / Segs) + Vec3(0, 0, Lift[I]); };
			for (int I = 1; I < Segs; ++I)
			{
				for (const double Off : { -0.5, -0.25, 0.0, 0.25, 0.5 })
				{
					const double U = std::clamp((I + Off) / Segs, 0.0, 1.0);
					Lift[I] = std::max(Lift[I], Under(FreePoint(A, B, Sag, U)));
				}
			}
			for (int Pass = 0; Pass < 6; ++Pass)
			{
				bool bLifted = false;
				for (int I = 0; I < Segs && !bLifted; ++I)
				{
					const Vec3 P0 = Point(I), P1 = Point(I + 1);
					if (Lift[I] <= 0.0 && Lift[I + 1] <= 0.0) continue;
					for (const double Q : { 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875 })
					{
						const double Need = Under(P0 + (P1 - P0) * Q);
						if (Need <= 0.0) continue;
						const bool bFree0 = I > 0, bFree1 = I + 1 < Segs;
						if (bFree0 && bFree1) { Lift[I] += Need; Lift[I + 1] += Need; }
						else if (bFree1) Lift[I + 1] += Need / Q;
						else if (bFree0) Lift[I] += Need / (1.0 - Q);
						bLifted = true;
						break;
					}
				}
				if (!bLifted) break;
			}
			std::vector<Vec3> Out;
			for (int I = 0; I <= Segs; ++I) Out.push_back(Point(I));
			return Out;
		}

		/** The lazy sheet of the plan's figure. */
		const Vec3 kClew(0.0, 0.0, 95.0), kLead(330.0, 0.0, 24.0);
		constexpr double kLazySlack = 0.05;

		std::vector<Vec3> LazySheet(const Vec3& Clew)
		{
			std::vector<FPoint> Scratch;
			std::vector<Vec3> Rings;
			LayRings(Clew, kLead, SagOf(Clew, kLead, kLazySlack), kRadius, kUp, FSettings(), FTrunk(), kRings, 6.0 * kRadius, kBend, true, Scratch, Rings);
			return Rings;
		}

		/** The shortest distance from P to the polyline. */
		double DistToPolyline(const Vec3& P, const std::vector<Vec3>& L)
		{
			double Best = 1e30;
			for (size_t I = 0; I + 1 < L.size(); ++I)
			{
				const Vec3 D = L[I + 1] - L[I];
				const double T = std::clamp((P - L[I]).Dot(D) / std::max(D.Dot(D), 1e-12), 0.0, 1.0);
				Best = std::min(Best, (L[I] + D * T - P).Length());
			}
			return Best;
		}

		/** The radius of the circle through three points. */
		double Circumradius(const Vec3& A, const Vec3& B, const Vec3& C)
		{
			const double a = (B - C).Length(), b = (A - C).Length(), c = (A - B).Length();
			const double Area2 = (B - A).Cross(C - A).Length();
			return Area2 > 1e-12 ? a * b * c / (2.0 * Area2) : 1e30;
		}
	}

	FRopeLayCheck RopeLayChecks::FreeLine()
	{
		FRopeLayCheck R{ "FreeLine", true, {} };
		const Vec3 A(0.0, 0.0, 100.0), B(300.0, 40.0, 60.0);
		constexpr double Slack = 0.03;
		const Vec3 Sag = SagOf(A, B, Slack);
		std::vector<FPoint> Scratch;
		std::vector<Vec3> Rings;
		const bool bLifted = LayRings(A, B, Sag, kRadius, kUp, FSettings(), FNothing(), kRings, 6.0 * kRadius, kBend, true, Scratch, Rings);
		std::vector<Vec3> Curve;
		for (int I = 0; I <= 2000; ++I) Curve.push_back(FreePoint(A, B, Sag, I / 2000.0));
		double Off = 0.0;
		for (const Vec3& P : Rings) Off = std::max(Off, DistToPolyline(P, Curve));
		const double Drawn = Length(Rings), Real = (B - A).Length() * (1.0 + Slack);
		R.Lines.push_back(Fmt("rings off the free curve at most %.4f cm; drawn %.1f cm, the line %.1f cm (%.2f%%)", Off, Drawn, Real, 100.0 * (Drawn / Real - 1.0)));
		R.bPass = !bLifted && Off < 0.01 && std::fabs(Drawn / Real - 1.0) < 0.02 && int(Rings.size()) == kRings + 1;
		return R;
	}

	FRopeLayCheck RopeLayChecks::DrapeOverTrunk()
	{
		FRopeLayCheck R{ "DrapeOverTrunk", true, {} };
		const std::vector<Vec3> Rings = LazySheet(kClew);
		// Inside: every ring and every span's eighths, the rope's centre at least its radius over the surface.
		double Deepest = 0.0;
		for (size_t I = 0; I + 1 < Rings.size(); ++I)
		{
			for (int K = 0; K <= 8; ++K)
			{
				const Vec3 P = Rings[I] + (Rings[I + 1] - Rings[I]) * (K / 8.0);
				if (I == 0 && K == 0) continue;
				Deepest = std::max(Deepest, TrunkTop(P.X, P.Y) + kRadius - P.Z);
			}
		}
		// Resting on the roof, not floating; steps; bends; rings at the edges.
		double Float = -1e9, Steep = 0.0, Tightest = 1e30, EdgeGap = 1e30, Mean = 0.0;
		int OnRoof = 0;
		for (size_t I = 0; I < Rings.size(); ++I)
		{
			const Vec3& P = Rings[I];
			if (P.X > 95.0 && P.X < 240.0) { Float = std::max(Float, P.Z - (70.0 + kRadius)); ++OnRoof; }
			if (I + 1 < Rings.size())
			{
				const Vec3 D = Rings[I + 1] - P;
				Steep = std::max(Steep, std::fabs(D.Z) / std::max(std::sqrt(D.X * D.X + D.Y * D.Y), 1e-6));
				Mean += D.Length();
				const double Mx = 0.5 * (P.X + Rings[I + 1].X);
				if (std::fabs(Mx - 90.0) < 12.0 || std::fabs(Mx - 245.0) < 12.0) EdgeGap = std::min(EdgeGap, D.Length());
			}
			if (I >= 2 && I + 2 < Rings.size()) Tightest = std::min(Tightest, Circumradius(Rings[I - 1], P, Rings[I + 1]));
		}
		Mean /= double(Rings.size() - 1);
		R.Lines.push_back(Fmt("deepest %.3f cm inside the trunk; %.0f rings over the roof, the highest %.2f cm off it", Deepest, OnRoof, Float));
		{
			// Today's drape of the same sheet, for comparison.
			const std::vector<Vec3> Old = OldDrape(kClew, kLead, SagOf(kClew, kLead, kLazySlack), kRadius, FTrunk());
			double OldFloat = -1e9, OldSteep = 0.0;
			for (size_t I = 0; I < Old.size(); ++I)
			{
				if (Old[I].X > 95.0 && Old[I].X < 240.0) OldFloat = std::max(OldFloat, Old[I].Z - (70.0 + kRadius));
				if (I + 1 < Old.size())
				{
					const Vec3 D = Old[I + 1] - Old[I];
					OldSteep = std::max(OldSteep, std::fabs(D.Z) / std::max(std::sqrt(D.X * D.X + D.Y * D.Y), 1e-6));
				}
			}
			R.Lines.push_back(Fmt("(today's drape of the same sheet: rings up to %.2f cm off the roof, steepest step %.2f)", OldFloat, OldSteep));
		}
		R.Lines.push_back(Fmt("steepest step %.2f (rise over run); tightest bend %.1f cm; ring gap at the edges %.1f cm, mean %.1f cm", Steep, Tightest, EdgeGap, Mean));
		R.bPass = Deepest < kDipShare * kRadius + 0.05 && OnRoof >= 3 && Float < 1.0 && Float > -0.05 && Steep < 1.5 && Tightest > 4.0 * kRadius && EdgeGap < 0.6 * Mean;
		return R;
	}

	FRopeLayCheck RopeLayChecks::NoShimmer()
	{
		FRopeLayCheck R{ "NoShimmer", true, {} };
		std::vector<Vec3> Last = LazySheet(kClew);
		double Worst = 0.0, WorstZ = 0.0;
		for (int K = 1; K <= 30; ++K)
		{
			const Vec3 Clew = kClew + Vec3(0.0, 0.0, -0.1 * K);
			const std::vector<Vec3> Now = LazySheet(Clew);
			for (const Vec3& P : Now)
			{
				const double D = DistToPolyline(P, Last);
				if (D > Worst) { Worst = D; WorstZ = Clew.Z; }
			}
			Last = Now;
		}
		R.Lines.push_back(Fmt("clew lowered 3 cm in 1 mm steps: the most a ring left the last frame's rope was %.3f cm (clew at %.1f cm)", Worst, WorstZ));
		{
			// Today's drape, the same sweep.
			auto Old = [](const Vec3& Clew) { return OldDrape(Clew, kLead, SagOf(Clew, kLead, kLazySlack), kRadius, FTrunk()); };
			std::vector<Vec3> Prev = Old(kClew);
			double OldWorst = 0.0;
			for (int K = 1; K <= 30; ++K)
			{
				const std::vector<Vec3> Now = Old(kClew + Vec3(0.0, 0.0, -0.1 * K));
				for (const Vec3& P : Now) OldWorst = std::max(OldWorst, DistToPolyline(P, Prev));
				Prev = Now;
			}
			R.Lines.push_back(Fmt("(today's drape, the same sweep: %.3f cm)", OldWorst));
		}
		R.bPass = Worst < 0.3;
		return R;
	}

	FRopeLayCheck RopeLayChecks::Deterministic()
	{
		FRopeLayCheck R{ "Deterministic", true, {} };
		const std::vector<Vec3> A = LazySheet(kClew), B = LazySheet(kClew);
		bool bSame = A.size() == B.size();
		for (size_t I = 0; bSame && I < A.size(); ++I) bSame = A[I].X == B[I].X && A[I].Y == B[I].Y && A[I].Z == B[I].Z;
		R.Lines.push_back(bSame ? "two lays of the same sheet are identical to the bit" : "two lays of the same sheet differ");
		R.bPass = bSame;
		return R;
	}

	FRopeLayCheck RopeLayChecks::BlockTangent()
	{
		FRopeLayCheck R{ "BlockTangent", true, {} };
		// Clew to a lead block on the side deck, on to a winch aft and inboard: 55 deg round the block.
		const Vec3 Clew(0.0, 80.0, 90.0), Lead(250.0, 110.0, 25.0), Winch(330.0, 70.0, 45.0);
		std::vector<FPoint> In, OutLine;
		for (int I = 0; I <= 16; ++I) { FPoint Q; Q.P = Clew + (Lead - Clew) * (I / 16.0); In.push_back(Q); }
		for (int I = 0; I <= 8; ++I) { FPoint Q; Q.P = Lead + (Winch - Lead) * (I / 8.0); OutLine.push_back(Q); }
		const Vec3 D0 = (Lead - Clew).Normalized(), D1 = (Winch - Lead).Normalized();
		const double Whole = std::acos(std::clamp(D0.Dot(D1), -1.0, 1.0));
		// As the rig does it: two lines of one sheet, the join at the block rounded on its sheave (2.5 cm), each given its rings.
		RoundChain({ &In, &OutLine }, { 2.5 }, 6.0 * kRadius, kDipShare * kRadius);
		std::vector<Vec3> RingsIn, RingsOut;
		PlaceRings(In, kRings, kBend, RingsIn);
		PlaceRings(OutLine, kRings, kBend, RingsOut);
		const double Gap = (RingsIn.back() - RingsOut.front()).Length();
		std::vector<Vec3> Run = RingsIn;
		Run.insert(Run.end(), RingsOut.begin() + 1, RingsOut.end());
		double Sharpest = 0.0;
		for (size_t I = 1; I + 1 < Run.size(); ++I)
		{
			const Vec3 A = (Run[I] - Run[I - 1]).Normalized(), B = (Run[I + 1] - Run[I]).Normalized();
			Sharpest = std::max(Sharpest, std::acos(std::clamp(A.Dot(B), -1.0, 1.0)));
		}
		const double Off = std::min((RingsIn.back() - Lead).Length(), 10.0);
		R.Lines.push_back(Fmt("the two lines meet %.4f cm apart, %.2f cm from the block's centre (inside the sheave's curve)", Gap, Off));
		R.bPass = Gap < 1e-9 && Off < 2.5;
		R.Lines.push_back(Fmt("%.1f deg round the block; no ring turns more than %.1f deg", Whole * 57.2958, Sharpest * 57.2958));
		R.bPass = R.bPass && Sharpest < Whole / 3.0;
		return R;
	}

	FRopeLayCheck RopeLayChecks::WinchTurns()
	{
		FRopeLayCheck R{ "WinchTurns", true, {} };
		const Vec3 Centre(0.0, 0.0, 50.0);
		constexpr double Rad = 3.2 + kRadius;
		for (const double Side : { 1.0, -1.0 })
		{
			// The lead forward of the winch and outboard (starboard, then port).
			const Vec3 Lead(60.0, Side * 45.0, 47.0);
			std::vector<Vec3> W;
			WinchWraps(Lead, Centre, Rad, 46.0, 49.5, 3.0, 12, 10.0, 6.0, W);
			const int Helix = 36;
			// Entry on the tangent: the way in against the drum's turn at the first point.
			const Vec3 In = Vec3(W[0].X - Lead.X, W[0].Y - Lead.Y, 0.0).Normalized();
			const double Th0 = std::atan2(W[0].Y - Centre.Y, W[0].X - Centre.X);
			const Vec3 Turn(-std::sin(Th0), std::cos(Th0), 0.0);
			const double EntryDeg = std::acos(std::clamp(In.Dot(Turn), -1.0, 1.0)) * 57.2958;
			// Swept angle (+X toward +Y is clockwise seen from above), radius, rising.
			double Swept = 0.0, RadErr = 0.0;
			bool bRising = true, bClockwise = true;
			for (int K = 1; K <= Helix; ++K)
			{
				const double A0 = std::atan2(W[K - 1].Y, W[K - 1].X), A1 = std::atan2(W[K].Y, W[K].X);
				double D = A1 - A0;
				while (D > 3.14159265358979) D -= 2.0 * 3.14159265358979;
				while (D < -3.14159265358979) D += 2.0 * 3.14159265358979;
				Swept += D;
				bClockwise = bClockwise && D > 0.0;
				bRising = bRising && W[K].Z > W[K - 1].Z;
				RadErr = std::max(RadErr, std::fabs(std::sqrt(W[K].X * W[K].X + W[K].Y * W[K].Y) - Rad));
			}
			R.Lines.push_back(std::string("lead to ") + (Side > 0 ? "starboard" : "port")
				+ Fmt(": in %.2f deg off the drum's tangent, %.2f turns clockwise, radius off by %.4f cm", EntryDeg, Swept / (2.0 * 3.14159265358979), RadErr));
			R.bPass = R.bPass && EntryDeg < 1.0 && std::fabs(Swept / (2.0 * 3.14159265358979) - 3.0) < 0.01 && bClockwise && bRising && RadErr < 1e-6;
		}
		return R;
	}

	FRopeLayCheck RopeLayChecks::ManyCases()
	{
		FRopeLayCheck R{ "ManyCases", true, {} };
		// Clews round the trunk (fore and aft, across, high and low), leads on the deck either side and on the roof, slack from
		// taut to lazy: 1,296 lays.
		int Cases = 0, Bad = 0;
		double Deepest = 0.0, Steepest = 0.0, OldDeepest = 0.0;
		std::string Worst;
		for (const double Cx : { -40.0, 40.0, 120.0, 200.0, 280.0, 360.0 })
		for (const double Cy : { -50.0, 0.0, 70.0 })
		for (const double Cz : { 30.0, 75.0, 140.0 })
		for (const double Lx : { -20.0, 100.0, 170.0, 330.0 })
		for (const double Ly : { -80.0, 30.0, 90.0 })
		for (const double Slack : { 0.0005, 0.02, 0.06, 0.12 })
		{
			const Vec3 A(Cx, Cy, Cz + (Cx > 85.0 && Cx < 250.0 && std::fabs(Cy) < 60.0 ? 50.0 : 0.0));
			const Vec3 B(Lx, Ly, TrunkTop(Lx, Ly) + 4.0);
			if ((B - A).Length() < 10.0) continue;
			std::vector<FPoint> Scratch;
			std::vector<Vec3> Rings;
			LayRings(A, B, SagOf(A, B, Slack), kRadius, kUp, FSettings(), FTrunk(), kRings, 6.0 * kRadius, kBend, true, Scratch, Rings);
			++Cases;
			bool bOk = int(Rings.size()) == kRings + 1;
			for (size_t I = 0; bOk && I < Rings.size(); ++I) bOk = std::isfinite(Rings[I].X) && std::isfinite(Rings[I].Y) && std::isfinite(Rings[I].Z);
			for (size_t I = 1; bOk && I + 1 < Rings.size(); ++I)
			{
				// (the ring's own depth, then its span's eighths, away from the end fittings)
				for (int K = 0; K < 8; ++K)
				{
					const Vec3 P = Rings[I] + (Rings[I + 1] - Rings[I]) * (K / 8.0);
					if ((P - B).Length() < 6.0 || (P - A).Length() < 6.0) continue;
					if (TrunkTop(P.X, P.Y) - P.Z <= Deepest) continue;
					const double Depth = DepthInTrunk(P);
					if (Depth > Deepest) { Deepest = Depth; Worst = Fmt("clew (%.0f, %.0f, %.0f) cm, ", A.X, A.Y, A.Z) + Fmt("lead (%.0f, %.0f, %.0f) cm, ", B.X, B.Y, B.Z) + Fmt("slack %.4f, at (%.0f, %.0f, %.1f)", Slack, P.X, P.Y, P.Z); }
				}
				const Vec3 D = Rings[I + 1] - Rings[I];
				if (Rings[I].Z > 72.0 && Rings[I + 1].Z > 72.0) continue;
				Steepest = std::max(Steepest, std::fabs(D.Z) / std::max(std::sqrt(D.X * D.X + D.Y * D.Y), 1e-6));
			}
			Bad += bOk ? 0 : 1;
			// Today's drape of the same line, for comparison.
			const std::vector<Vec3> Old = OldDrape(A, B, SagOf(A, B, Slack), kRadius, FTrunk());
			for (size_t I = 0; I + 1 < Old.size(); ++I)
			{
				for (int K = 0; K < 8; ++K)
				{
					const Vec3 P = Old[I] + (Old[I + 1] - Old[I]) * (K / 8.0);
					if ((P - B).Length() < 6.0 || (P - A).Length() < 6.0 || TrunkTop(P.X, P.Y) - P.Z <= OldDeepest) continue;
					OldDeepest = std::max(OldDeepest, DepthInTrunk(P));
				}
			}
		}
		R.Lines.push_back(Fmt("%.0f lays, %.0f with a bad ring; the deepest centre %.3f cm into the trunk (the shortest way out, as the rig's clearance test measures)", Cases, Bad, Deepest));
		if (!Worst.empty()) R.Lines.push_back("deepest: " + Worst);
		R.Lines.push_back(Fmt("(today's drape of the same lines: the deepest centre %.3f cm into the trunk)", OldDeepest));
		// (The lay lifts, it doesn't push sideways: a rope climbing a trunk's wall, or grazing the foot of its sloping face,
		// can come a little inside its corner. Its centre never goes further in than its radius and the third of it a curve
		// over an edge may press in: the rope is never more than half buried in anything.)
		R.bPass = Bad == 0 && Deepest < (1.0 + kDipShare) * kRadius;
		(void)Steepest;
		return R;
	}

	std::vector<FRopeLayCheck> RopeLayChecks::All()
	{
		return { FreeLine(), DrapeOverTrunk(), NoShimmer(), Deterministic(), BlockTangent(), WinchTurns(), ManyCases() };
	}
}
