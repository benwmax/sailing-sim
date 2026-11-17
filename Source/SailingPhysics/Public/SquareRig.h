#pragma once

#include "SailingPhysicsApi.h"
#include "SailingMath.h"
#include "Sail.h"
#include <vector>

namespace Sailing
{
	/**
	 * Square sails (docs/frigate-physics/): sails hung from yards across the masts, the frigate Commonwealth's courses,
	 * topsails, topgallants and royals. A square sail has no fixed luff: either yardarm can lead, so its chord is its
	 * yard (port arm to starboard arm) and its angle of attack is the angle between the apparent wind and the yard,
	 * 0 (wind along the yard: it shakes) to 90 deg (wind square on it: running). The cloth hangs on the yard's fore
	 * side and bellies away from the wind: with the wind on its after face it is full, on its fore face it is aback,
	 * pressed flat against the mast and the rigging, and pushes the ship astern (how a square-rigger tacks, heaves to
	 * and backs off a lee shore).
	 *
	 * The crew turn the yards with the braces ("bracing"): each mast's yards together, the upper ones a little squarer
	 * than the lower (FSquareSailDef::BraceOffsetDeg), each held to the angle at which it or its sail meets the shrouds
	 * and backstays (BraceLimitDeg). Each sail is set (full), clewed up (hanging in its gear: a little windage) or furled
	 * (rolled on its yard), and a topsail or course can be reefed. Setting or taking in a sail takes the crew time
	 * (SetSeconds, ClewSeconds), and so does bracing (BraceDegPerSecond).
	 *
	 * Yard angle convention: positive turns the starboard yardarm forward and the port one aft: the yards braced up for a
	 * wind from starboard (the starboard tack: bracing up hauls the lee braces, so the lee yardarms go aft). Radians in
	 * FBoatState::YardAngle; FBoatControls::Brace has the same sign. With the apparent wind at A (+ from starboard) and
	 * a yard at psi, the sail is full when A + psi > 90 deg, at an angle of attack A + psi - 90 (mirrored for A < 0).
	 */
	constexpr int kMaxSquareSails = 12;
	constexpr int kMaxMasts = 3;

	enum class ESquareSailKind : unsigned char { Course, Topsail, Topgallant, Royal };

	/** What the crew have done with a square sail (FBoatControls::SquareSet). */
	enum class ESailSet : unsigned char { Furled, Clewed, Set };

	struct FSquareSailDef
	{
		ESquareSailKind Kind = ESquareSailKind::Topsail;
		int Mast = 0;                // 0 = the foremost mast
		double PivotX = 0.0;         // body X of its yard's turning axis (the mast) at the sail's mid height
		double ForeOffset = 0.5;     // m the sail's plane stands forward of that axis (the yard's half width, the belly)
		double FootZ = 0.0, HeadZ = 1.0; // set, m above the DWL
		double HeadWidth = 1.0, FootWidth = 1.0; // m, head earing to head earing, clew to clew
		double Area = 1.0;           // m^2 as cut
		double BraceLimitDeg = 35.0; // how far its yard braces from square with this sail set
		double BraceOffsetDeg = 0.0; // braced this much squarer than its mast's lowest yard
		std::vector<double> ReefAreaFraction; // area left at each reef (empty: no reef bands)
		double MidZ() const { return 0.5 * (FootZ + HeadZ); }
	};

	struct FSquareRig
	{
		std::vector<FSquareSailDef> Sails;
		int NumMasts = 0;
		double MastX[kMaxMasts] = { 0, 0, 0 };
		// The sails' aerodynamics (SquareSailCoefficients): a soft, deeply cut sail of low aspect ratio. Estimates from
		// Marchaj's square-sail coefficients and wind-tunnel tests of square rigs, each a knob for the trial to settle.
		double Camber = 0.10;            // belly over chord set and drawing (the belly the model's set sails carry)
		double AspectRatio = 1.6;        // effective, for the lift slope (one sail on a mast of sails, end-plated by those above and below)
		double InducedAspectRatio = 2.2; // for the induced drag of the whole square rig
		double LuffDeg = 5.0;            // below this angle of attack the weather leech lifts and the sail shakes
		double RunningCD = 1.3;          // the drag of a sail square to the wind (a deep bluff plate)
		double BackedLiftShare = 0.6;    // aback: pressed flat against the mast and rigging
		double BackedDragShare = 0.85;
		double ClewedCdAShare = 0.06;    // a sail hanging in its gear: windage as this share of its area
		// Interference: running, the after masts' sails blanket the ones before them (wind speed share kept at a dead
		// run); close-hauled, the after masts sail in the forward masts' downwash (deg the flow is headed per mast ahead).
		double BlanketShare = 0.3;
		double DownwashDegPerMast = 2.0;
		// The crew's pace.
		double BraceDegPerSecond = 2.0;  // a mast's yards swung round together
		double SetSeconds = 60.0;        // from furled to drawing (loose, sheet home, hoist)
		double ClewSeconds = 20.0;       // from drawing to clewed up
		double FurlSeconds = 90.0;       // from clewed up to furled (information only: no force either way)

		bool Has() const { return !Sails.empty(); }
		/** The lowest (largest) sail on a mast, whose yard the mast's brace angle names (its index, or -1). */
		int LowestOn(int Mast) const;
		/** The mast's whole square canvas, set as cut (m^2). */
		double AreaOn(int Mast) const;
	};

	/**
	 * Lift and drag of a filled square sail at an angle of attack AlphaDeg (0..90, the wind's angle to its yard).
	 * Lift is across the wind toward the sail's belly, drag along it; OutFlow says how it draws (Luffing below LuffDeg).
	 */
	SAILINGPHYSICS_API void SquareSailCoefficients(const FSquareRig& Rig, double AlphaRad, double& OutCL, double& OutCD, ESailFlow& OutFlow);

	/** The angle of attack (rad) at which a square sail of this rig stalls (its lift is greatest). */
	SAILINGPHYSICS_API double SquareStallAlpha(const FSquareRig& Rig);

	/** The yard angle (rad, signed as FBoatState::YardAngle) for a mast's brace control (-1..1 of its lowest yard's
	 *  limit) on one sail: squarer by its offset, held to its own limit. */
	SAILINGPHYSICS_API double YardAngleFor(const FSquareRig& Rig, int Sail, double Brace);

	/** The brace control that puts a mast's lowest yard at an angle of attack AlphaDeg to an apparent wind angle AwaRad
	 *  (signed, + from starboard), clamped to -1..1 (the trimmer's target). */
	SAILINGPHYSICS_API double BraceForAlpha(const FSquareRig& Rig, int Mast, double AwaRad, double AlphaDeg);
}
