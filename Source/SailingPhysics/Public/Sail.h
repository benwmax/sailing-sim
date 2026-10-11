#pragma once

#include "SailingPhysicsApi.h"
#include "SailingMath.h"

namespace Sailing
{
	constexpr int kMaxSailStrips = 5;

	enum class ESailFlow : unsigned char
	{
		Attached,  // telltales streaming on both sides
		Luffing,   // eased too far or pinching: the luff bubbles or flogs
		Stalled,   // trimmed too tight for the flow: leeward telltales stall
		Backed     // wind on the wrong side of the sail
	};

	/** One horizontal strip of a sail, in the boat frame with the sail on the centerline. */
	struct FSailStripGeometry
	{
		double ZBottom = 0.0, ZTop = 0.0; // body Z, m above the waterline
		double LuffX = 0.0;               // body X of the luff at the strip's mid-height
		double Chord = 1.0;               // m
		double Area = 1.0;                // m^2
		double HeightFraction = 0.0;      // 0 at the foot, 1 at the head (mid-strip)
	};

	struct FSailGeometry
	{
		FSailStripGeometry Strips[kMaxSailStrips];
		int NumStrips = 4;
		double TotalArea = 0.0;
		double LiftSlope = 4.2;           // per radian, 3D sail
		double InducedAspectRatio = 6.0;  // for induced drag of the whole rig, including the deck's mirror effect
		double BaseCamber = 0.12;         // depth/chord at mid height
	};

	/** Per-strip shape and aerodynamic state, kept for the visuals and the tests. */
	struct FSailStripState
	{
		double AngleFromCenterline = 0.0; // rad, chord angle; positive = sail on the starboard side
		double Camber = 0.12;
		double TwistFromFoot = 0.0;       // rad, extra angle relative to the boom/foot
		double AlphaN = 0.0;              // rad, angle of attack, positive when the sail is loaded normally
		double LuffAlpha = 0.0;           // rad, below this the luff collapses
		double StallAlpha = 0.0;          // rad, above this the flow separates
		double LiftCoefficient = 0.0;     // >0 = driving the normal way
		double DragCoefficient = 0.0;
		double ApparentSpeed = 0.0;       // m/s at the strip
		double ApparentAngle = 0.0;       // rad, apparent wind angle at the strip (0 = from ahead, + = from starboard)
		ESailFlow Flow = ESailFlow::Attached;
		Vec3 CenterOfEffort;              // body frame
		Vec3 Force;                       // body frame, N
	};

	/** Shape controls for one sail, already converted to physical amounts by the boat model. */
	struct FSailShape
	{
		double FootAngle = 0.0;    // rad, angle of the boom/jib foot from the centerline (magnitude)
		int Side = 1;              // +1 sail on the starboard side, -1 on port
		double HeadTwist = 0.0;    // rad, extra angle at the head relative to the foot
		double CamberScale[kMaxSailStrips] = { 1, 1, 1, 1, 1 };
		double CamberOffset[kMaxSailStrips] = { 0, 0, 0, 0, 0 };
		double StallDelta = 0.0;   // rad, extra stall margin (cunningham pulls the draft forward)
		double DownwashAlpha = 0.0; // rad, slot effect from the jib reduces the main's angle of attack
		double MaxDownwashZ = 0.0;  // downwash only applies to strips below this height (the jib's head)
		double LiftScale = 1.0;    // upwash from the main boosts the jib
		double WindScale = 1.0;    // blanketing behind the main when running
	};

	/** Coefficients for a soft sail at a given normal angle of attack and camber. */
	SAILINGPHYSICS_API void SailCoefficients(const FSailGeometry& Geo, double AlphaN, double Camber, double StallDelta,
		double& OutCL, double& OutCD, double& OutLuffAlpha, double& OutStallAlpha, ESailFlow& OutFlow);

	/** Chord direction (luff to leech) in the body XY plane for a sail at an angle on a side. */
	inline Vec3 SailChordDir(double Angle, int Side) { return Vec3(-std::cos(Angle), Side * std::sin(Angle), 0.0); }
}
