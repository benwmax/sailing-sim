#pragma once

#include "SailingMath.h"
#include <cmath>
#include <vector>

namespace Sailing
{
	/**
	 * Rope realism phase 2 (docs/rope-lay/): the knots the player's boat shows, as rope centrelines baked tight by
	 * Tools/rope/make_knot_data.py (RopeKnotData.inl, in rope diameters). The game places one at a fitting and draws it as
	 * part of the live rope, in its colourway, so the knot and the sheet read as one rope (the plan's K0 + K1).
	 *
	 * Frame: +X along the standing part, towards the live rope; the up hint (the boat's up) gives Z, Y = Z x X.
	 *  Bowline: round a bar along Z at Origin (a jib's clew); the points run from the tail's end round the loop to the
	 *           standing part's exit (the last point), where the live sheet starts along +X.
	 *  FigureEight: a stopper on a rope's end. The live line comes in from +X and ends at Origin; the knot lies on
 *           beyond it along -X, its points from Origin to the tail's end.
 */
	namespace RopeKnots
	{
#include "RopeKnotData.inl"

		enum class EKnot { Bowline, FigureEight };

		inline int Count(EKnot K) { return K == EKnot::Bowline ? kKnotBowlineCount : kKnotFigureEightCount; }
		inline const double (*Data(EKnot K))[3] { return K == EKnot::Bowline ? kKnotBowline : kKnotFigureEight; }

		/** The knot's frame: X along the standing part, Y and Z square to it (Z towards the up hint). */
		inline void Frame(const Vec3& X0, const Vec3& UpHint, Vec3& X, Vec3& Y, Vec3& Z)
		{
			X = X0.Length() > 1e-9 ? X0.Normalized() : Vec3(1.0, 0.0, 0.0);
			Y = UpHint.Cross(X);
			if (Y.Length() < 1e-6) Y = Vec3(0.0, 1.0, 0.0).Cross(X);
			if (Y.Length() < 1e-6) Y = Vec3(0.0, 0.0, 1.0).Cross(X);
			Y = Y.Normalized();
			Z = X.Cross(Y);
		}

		/** The knot's points: Origin + Diameter x (x X + y Y + z Z), in the baked order. Always Count(K) points. */
		inline void Place(EKnot K, const Vec3& Origin, const Vec3& Along, const Vec3& UpHint, double Diameter, std::vector<Vec3>& Out)
		{
			Vec3 X, Y, Z;
			Frame(Along, UpHint, X, Y, Z);
			const int N = Count(K);
			const double (*P)[3] = Data(K);
			Out.resize(size_t(N));
			for (int I = 0; I < N; ++I) Out[size_t(I)] = Origin + (X * P[I][0] + Y * P[I][1] + Z * P[I][2]) * Diameter;
		}

		/** Where the live rope joins the knot: a bowline's standing exit (its last point), a stopper's start (Origin). */
		inline Vec3 Exit(EKnot K, const Vec3& Origin, const Vec3& Along, const Vec3& UpHint, double Diameter)
		{
			if (K == EKnot::FigureEight) return Origin;
			Vec3 X, Y, Z;
			Frame(Along, UpHint, X, Y, Z);
			const double* Q = kKnotBowline[kKnotBowlineCount - 1];
			return Origin + (X * Q[0] + Y * Q[1] + Z * Q[2]) * Diameter;
		}
	}
}
