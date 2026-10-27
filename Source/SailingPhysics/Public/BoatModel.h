#pragma once

#include "SailingPhysicsApi.h"
#include "SailingMath.h"
#include "Foil.h"
#include "Sail.h"
#include "Wind.h"
#include "Waves.h"
#include "LakeTerrain.h"
#include <vector>
#include <utility>
#include <algorithm>

namespace Sailing
{
	/** What the crew does. All values are normalized; the boat model turns them into angles and loads. */
	struct FBoatControls
	{
		double Tiller = 0.0;     // -1..1, positive turns the bow to starboard (tiller pushed to port)
		double MainSheet = 0.3;  // 0 = trimmed hard in, 1 = fully eased
		double JibSheet = 0.3;   // 0 = trimmed hard in, 1 = fully eased
		double Traveler = 0.0;   // -1 = car to windward, 0 = centered, 1 = car to leeward
		double Vang = 0.3;       // 0..1 boom vang tension
		double Cunningham = 0.0; // 0..1
		double Outhaul = 0.3;    // 0..1, 1 = foot flat
		double Backstay = 0.0;   // 0..1, bends the mast and tightens the forestay
		bool bWingOnWing = false; // running: hold the jib out on the windward side, opposite the main
		bool bBackJib = false;    // hold the jib aback (sheeted on the windward side): heaving to, getting out of irons
		double Hike = 0.0;       // -1 = crew on the leeward side, 0 = sitting on the windward rail, 1 = fully hiked (or out on the wire)
		double CrewAft = 0.0;    // 0 = the crew's usual place, 1 = as far aft as they go (a dinghy sailor sits back planing)
		bool bSpinnaker = false; // spinnaker (or gennaker / screacher) hoisted, if the boat has one
		bool bSailsDown = false; // furled and covered (tied up in her slip): no sail force; the rig's and hull's windage stay
		double SpinSheet = 0.5;  // 0 = trimmed in, 1 = eased
		int Reef = 0;            // mainsail reefs taken in (0 = full main)
		double Board = 1.0;      // centerboard / daggerboard / swing keel: 1 = fully down, 0 = up
		double Throttle = 0.0;   // engine(s): -1 full astern .. 1 full ahead (0 = neutral)
		double ThrottleSplit = 0.0; // twin engines: + = more thrust on the port engine (turns the bow to starboard)
		bool bRighting = false;  // capsized: crew on the centerboard (dinghy) or on the righting line (beach cat)
	};

	enum class EBoatType : unsigned char
	{
		J22, Sunfish, ILCA7, Catalina22, Catalina30, Hobie16, Corsair880, Lagoon42,
		Maxi, // the prologue's made-up 100 ft maxi (Tools/boats/maxi): in the catalogue only for the prologue for now
		Count
	};

	SAILINGPHYSICS_API const char* BoatTypeName(EBoatType Type);

	/**
	 * One hull's shape in the boat frame (origin at the design waterline, midships of the waterline; X fwd, Y stbd,
	 * Z up). Plan view: a half-ellipse forward of the widest station, a gentle taper aft to the transom. Sections: a
	 * flat run with a turn of the bilge set by BilgePower (4 = firm bilge, 2 = round, closer to 1 = V).
	 */
	struct SAILINGPHYSICS_API FHullShape
	{
		double CenterY = 0.0;          // lateral position of this hull's centerline (multihulls)
		double BowX = 3.45, SternX = -3.41;
		double WaterlineMidX = -0.15, WaterlineHalfLength = 2.895;
		double MaxHalfBeam = 1.22, MaxBeamX = -0.4;
		double AftLength = 3.0, TransomBeamLoss = 0.27; // half-beam lost from the widest station to AftLength aft of it
		double SheerZ = 0.62, SheerRise = 0.10, SheerRiseFromX = 1.0;
		double BowOverhangSlope = 1.1, SternOverhangSlope = 0.5;
		double BilgePower = 4.0;
		double DepthScale = 1.0;       // canoe depth relative to the main hull's
		double DepthOffset = 0.0;      // m the keel line sits above the main hull's (amas clear of the water at rest)
		double PlaningLift = 0.0;      // dynamic lift coefficient of the bottom (planing dinghies)

		/**
		 * A hull drawn by its sections instead of the formula above (the prologue maxi: the PC's exported hull). Each
		 * station is a half section from the keel (Y 0) to the sheer, half breadths never decreasing, every station with
		 * the same number of points; stations run stern to bow. With stations, DeckHalfBeam, SheerHeight, KeelLineDepth
		 * and BottomZ follow them (between stations point by point) and the parameters above are only a stand-in fit
		 * for the water's hull clip and BoatExport. The canoe depth the boat floats at moves the sections down by its
		 * difference from StationDepth (their own keel depth), so a heavier boat sinks the drawn hull.
		 */
		struct FStation
		{
			double X = 0.0, Sheer = 0.0;
			std::vector<double> Y, Z;
		};
		std::vector<FStation> Stations;
		double StationDepth = 0.0;     // the sections' deepest keel point below the DWL (m)
		bool HasStations() const { return Stations.size() >= 2; }

		double DeckHalfBeam(double X) const;
		double SheerHeight(double X) const;
		double KeelLineDepth(double X, double MainDepth) const;
		double BottomZ(double X, double Y, double MainDepth) const; // Y relative to CenterY
		double WaterlineLength() const { return 2.0 * WaterlineHalfLength; }
		/** The station pair around X (I and I + 1, T from I to I + 1), clamped to the ends. */
		void StationAt(double X, int& OutI, double& OutT) const;
		/** The bottom's height at |Y| on the section between stations I and I + 1 (the sheer past the deck edge). */
		double StationBottomZ(int I, double T, double AbsY) const;
	};

	enum class EFoilRole : unsigned char { Keel, Board, Rudder, HullLateral };

	/** A keel, centerboard, daggerboard, rudder, or a slender hull's own lift (no-board beach cats). */
	struct FFoilDef
	{
		FFoilParams Params;
		EFoilRole Role = EFoilRole::Keel;
		int Hull = 0;
		bool bRetractable = false;     // follows the Board control
		// Ventilation by heel, as a fraction of lift kept: 1 below Start, 1 - Depth past End (degrees).
		double VentStartDeg = 60.0, VentEndDeg = 85.0, VentDepth = 0.9;
		// Where the foil's foot touches bottom (body frame x of its bottom chord's leading and trailing edges), when
		// that is not under Params.Center: the J/22's keel Center is a balance knob, 45 cm ahead of the drawn fin.
		// Both zero means the foot sits under Params.Center, 0.8 chord wide.
		double ContactLeadingX = 0.0, ContactTrailingX = 0.0;
		bool HasContactFootprint() const { return ContactLeadingX != ContactTrailingX; }
		double Span() const { return Params.Area / std::max(Params.Chord, 1e-3); }
	};

	/** An engine: propeller position (body frame), thrust and the hull it hangs on. */
	struct FEngineDef
	{
		Vec3 Position = Vec3(-3.0, 0.0, -0.5);
		double MaxThrustN = 600.0;     // static bollard thrust ahead
		double ReverseFraction = 0.55; // astern thrust as a fraction
		double PropSpeedKnots = 7.0;   // speed at which the thrust ahead falls to zero (pitch speed)
		double PropDiameter = 0.25;    // m
		double PropWalk = 0.06;        // side force in reverse as a fraction of thrust (right-handed: stern to port)
		int Hull = 0;
	};

	/** Physical particulars and model tuning for one boat. FBoatConfig::Make builds each boat in the fleet. */
	struct SAILINGPHYSICS_API FBoatConfig
	{
		EBoatType Type = EBoatType::J22;
		const char* Name = "J/22";
		bool bMultihull = false;

		// Mass budget (body frame: origin at the design waterline, midships of the waterline; X fwd, Y stbd, Z up).
		double HullRigMass = 494.0;  Vec3 HullRigCG = Vec3(-0.15, 0.0, 0.35);
		double BallastMass = 318.0;  Vec3 BallastCG = Vec3(0.10, 0.0, -0.65); // centroid of a cast-lead fin
		// The fixed appendages' own buoyancy (a big fin and bulb, fixed rudders), m^3 and their centroid: always under
		// water upright, so the canoe body floats the rest. 0 = folded into the ballast's weight (the small boats: the
		// J/22's fin displaces 40 litres).
		double AppendageVolume = 0.0; Vec3 AppendageCentre;
		double CrewMass = 240.0;     Vec3 CrewCG = Vec3(-1.20, 0.0, 0.55); // three crew, sitting on centerline
		int CrewCount = 3;
		double CrewSitOut = 0.30;    // m from centerline sitting on the windward side
		double CrewHikeOut = 0.65;   // extra m at full hike (torso over the lifelines) or out on the trapeze
		double CrewMoveSpeed = 1.6;  // m/s moving across the boat
		double CrewAftRange = 0.0;   // m the crew can slide aft of CrewCG (dinghies: to the back of the cockpit, keeping the bow up planing)
		bool bTrapeze = false;
		double RightingLever = 0.0;  // m below the hull the righting crew stands (board tip, or leaning on the righting line); 0 = cannot be righted

		Vec3 RadiiOfGyration = Vec3(0.95, 1.75, 1.65); // roll, pitch, yaw (m)
		Vec3 AddedMassRatio = Vec3(0.05, 0.75, 1.0);    // surge, sway, heave as a fraction of mass
		Vec3 AddedInertiaRatio = Vec3(0.35, 0.8, 0.6);  // roll, pitch, yaw

		// Hulls (one for a monohull, two for a catamaran, three for a trimaran: main hull first).
		std::vector<FHullShape> Hulls;
		double LengthOverall = 6.86, WaterlineLength = 5.79, Beam = 2.44, WaterlineBeam = 2.0;
		double Bowsprit = 0.0; // of LengthOverall, ahead of the hulls (a fixed sprit)
		double Draft = 1.16;              // m, deepest point with the board down (grounding probes stop here)
		double WettedAreaCoef = 2.75;     // wetted area = coef x sqrt(volume x LWL), per hull (6.8 m^2 for the J/22 at rest)
		double FormFactor = 1.10;         // (1 + k) on ITTC-57 friction
		// Residuary (wave-making) resistance per unit displacement weight against each hull's Froude number.
		std::vector<std::pair<double, double>> Residuary;
		double HeaveDamping = 900.0;      // N s/m^3 per m^2 of submerged column (radiation damping stand-in)
		double YawDampingLinear = 400.0;  // N m s, low-speed yaw damping
		double HullLateralCd = 1.0;
		double HullLateralArea = 0.55;    // m^2 at each of two stations (shared among the hulls by displacement)
		double MunkAddedMass = 250.0;     // A22 - A11 of the canoe body (kg)
		// Heeled, the immersed hull is lopsided (the lee bow digs in, the windward quarter lifts) and the boat wants to turn
		// to windward: the yaw moment is HeelYawCoef x 1/2 rho V^2 x LWL^2 x canoe depth x sin(heel). With the drive pulled
		// out to leeward by the heeled rig, it is why a keelboat's weather helm grows as she heels (Keuning & Sonnenberg).
		double HeelYawCoef = 0.0;
		double ExtraRollDamping = 0.0;    // N m s; the easy difficulty adds some
		// Easy mode's righting assist (EasyAssists.h; 0 = none): from HeelCapSoftDeg short of HeelCapDeg it adds a righting
		// moment growing with the square of the heel, HeelCapLeverM times the boat's weight at the cap.
		double HeelCapDeg = 0.0;
		double HeelCapSoftDeg = 6.0;
		double HeelCapLeverM = 0.0;
		// Added resistance in waves (docs/wave-physics/): AddedResistanceCoef x R(lambda/LWL) x rho g 2 m0 B^2 / LWL summed
		// over the sea's bands (ORC VPP 2023 eq. 6.61's 2 x the spectral integral), largest heading into the waves
		// ((1 + cos)^2 / 4 of the angle off the wave direction), growing with the Froude number up to 0.265 x the speed cap.
		// R = r^4 / (0.25 + r^4) with r = wavelength / LWL up to her peak (short chop barely pitches her), then Jinkine &
		// Ferdinande's long-wave fall (she rides waves much longer than her). The J/22's 2.6 is calibrated so she matches
		// ORC's polar in the lake's chop; boats the lake's chop does not load (the maxi) or that ORC scales differently
		// (the Catalina 30) take ORC's length scaling against her (Fleet.cpp). Heave and pitch come from the hydrostatics.
		double AddedResistanceCoef = 2.6;
		// Froude number (in units of 0.265, the J/22's 4 kn) at which the added resistance stops growing: a keelboat's
		// pitching saturates there; a light catamaran keeps slamming harder into the chop the faster it goes.
		double AddedResistanceSpeedCap = 1.0;
		// The waves' slope push on the hull (Froude-Krylov surge and sway, the surf down a face): 1 is the physics, 0
		// leaves the buoyancy vertical as it was before docs/wave-physics/ (for comparisons only).
		double WaveSlopeForceScale = 1.0;
		// docs/surfing/: the waves' orbital velocity as a flow past the hull, keels and rudders (1 is the physics, 0 the
		// still water they met before, for comparisons). Never in the calibration sea (FWaveParams::bCalibrationSea).
		double WaveOrbitalFlowScale = 1.0;

		// Foils: keels, boards and rudders. Rudders are linked to one tiller (or wheel).
		std::vector<FFoilDef> Foils;
		double KeelDownwashFactor = 1.0;  // fraction of the keel's downwash angle that reaches the rudder
		double MaxRudderAngleDeg = 30.0;
		double RudderStockToCP = 0.09;    // m, center of pressure behind the stock (unbalanced transom rudder)
		double TillerLength = 1.0;        // m
		double HelmStiffness = 600.0;     // N m/rad, how firmly the helm holds the tiller; lower = more helm feel
		double RudderResponseTime = 0.10; // s
		// Wheel steering: the helm turns the rudder from amidships to hard over in this long, wheel turned flat out (the
		// crew-station wheel reads it: CrewStation.h). 0 = a tiller (the station's own default stands in).
		double WheelHardOverSeconds = 0.0;

		// Sails. A sail with NumStrips = 0 is absent (una and lateen rigs have no jib).
		FSailGeometry Main;
		FSailGeometry Jib;
		FSailGeometry Spinnaker;
		bool bAsymmetricSpinnaker = false; // gennaker or screacher tacked to the bow or a sprit (no pole)
		double MastX = 1.0;
		double MastheadZ = 9.25;
		double MastDiameter = 0.10;       // m; a sealed mast floats a little when the boat is on its side
		double SparFloatLiters = 0.0; // sealed spars (yard, boom, mast plugs, mast float) that float a capsized rig: holds a dinghy on her side
		double BoomZ = 1.45;              // m, gooseneck height
		// How far the boom can go out: on a stayed rig, until its side meets the aftmost shroud leg at boom height (from
		// the gooseneck, MainLuffX at BoomZ; docs/boom-stop/). The J/22's: her upper shroud from its chainplate (0.48 m
		// forward, 1.086 m out, J22H_sockets.json) to the spreader tip passes 1.02 m from the gooseneck at boom height, at
		// 80 deg from aft less the boom's 4 cm half-width. (85 had the boom, and the eased main with it, through it.)
		double MainMaxEaseDeg = 80.0;
		double TravelerRangeDeg = 8.0;    // boom angle the traveler moves either side of the centerline
		double JibMinAngleDeg = 8.0, JibMaxAngleDeg = 80.0;
		double RigWindageCdA = 0.8;       // m^2 (mast, rigging)
		double HullWindageCdA = 0.8;      // m^2 (topsides, crew)
		// Reefing: luff length left at each reef, as a fraction of the full main.
		std::vector<double> ReefLuffFraction;
		// Main build recipe, kept so reefs can rebuild it: foot and head heights, chords, roach, luff X.
		double MainFootZ = 1.45, MainHeadZ = 9.05, MainFootChord = 2.97, MainHeadChord = 0.45, MainRoach = 0.12, MainLuffX = 0.95, MainLuffXHead = 0.95, MainArea = 11.5;
		// The headsail change that goes with each reef (a big boat's J1 -> J3 -> J4), as a fraction of the full jib's area
		// (BuildMain rebuilds the jib too: luff and foot each by the square root). Empty = the jib stays (the small boats
		// reef the main only). The full jib's recipe is kept here by the boats that use it.
		std::vector<double> ReefJibFraction;
		double JibFootZ = 0.0, JibHeadZ = 0.0, JibFootChord = 0.0, JibHeadChord = 0.0, JibLuffX = 0.0, JibLuffXHead = 0.0, JibArea = 0.0;

		std::vector<FEngineDef> Engines;

		// How a good crew sails this boat: the heel they depower at, and how far they will ease the main to do it.
		double TrimHeelLimitDeg = 22.0;
		double TrimReachHeelLimitDeg = 0.0; // the heel limit reaching (TWA 80 to 110 deg and on); 0 = TrimHeelLimitDeg
		double TrimMaxEaseDeg = 25.0;
		// A dinghy sailor holds the sheet in the hand and sails the boat flat (0 = a keelboat crew on winches and cleats):
		// boom degrees dumped at once per degree of heel past the limit (and of the roll toward it), and the sheet's travel
		// per second when dumping.
		double DinghyEasePerHeelDeg = 0.0;
		double DinghySheetRate = 0.0;

		FBoatConfig();
		static FBoatConfig J22() { return FBoatConfig(); }
		static FBoatConfig Make(EBoatType Type);

		/** Rebuilds the main for a number of reefs (0 = full). */
		void BuildMain(int Reefs);
		bool HasJib() const { return Jib.NumStrips > 0; }
		bool HasSpinnaker() const { return Spinnaker.NumStrips > 0; }
		bool HasBoard() const;
	};

	/** Builds a sail as strips between two heights, with chords tapering foot to head and a roach, to an exact area. */
	SAILINGPHYSICS_API void BuildSail(FSailGeometry& Sail, int NumStrips, double ZFoot, double ZHead, double FootChord, double HeadChord,
		double RoachFraction, double LuffXFoot, double LuffXHead, double TargetArea);

	/**
	 * Something the boat can hit: a dock edge, piling or bridge deck, as a capsule around a horizontal segment
	 * between Bottom and Top heights (m). Docks reach down into the water; a bridge deck spans from its clearance
	 * upward, so the hull passes under but a tall mast does not.
	 */
	struct FObstacleSegment
	{
		double AX = 0, AY = 0, BX = 0, BY = 0;
		double Radius = 0.3;
		double Bottom = -1.0, Top = 0.5;
		double VX = 0.0, VY = 0.0;   // velocity of a moving obstacle (another vessel's hull), m/s
	};

	/** A dock line from a cleat on the boat (body frame) to a point ashore (world), slack below its length. */
	struct FMooringLine
	{
		Vec3 BodyPoint;
		Vec3 Anchor;
		double Length = 1.0;
	};

	struct FBoatState
	{
		Vec3 Position;          // world position of the center of gravity (m)
		Vec3 Velocity;          // world velocity of the center of gravity (m/s)
		Quat Orientation;       // body to world
		Vec3 AngularVelocity;   // body frame (rad/s): roll, pitch, yaw rates
		double RudderAngle = 0.0;   // rad, positive turns the bow to starboard
		double BoomAngle = 0.0;     // rad, positive = boom on the starboard side
		double JibAngle = 0.0;      // rad, positive = jib clew on the starboard side
		int MainSide = 1, JibSide = 1;
		int BackedJibSide = 0;      // side the jib is held aback on (fixed by its sheet), 0 = not backed
		double CrewOffset = 0.0;    // m, crew position from centerline (+ = starboard)
		double CrewOffsetZ = 0.0;   // m, crew height change (standing on the board to right a capsized boat)
		double CrewOffsetX = 0.0;   // m, crew moved fore (+) or aft (-) of their usual place
		double SpinAngle = 0.0;     // rad, spinnaker chord angle, positive = starboard
		int SpinSide = 1;
		int Reef = 0;               // reefs in the main as currently built
		double EngineThrust[4] = { 0, 0, 0, 0 }; // N, each engine, lagging the throttle
		double CapsizedTime = 0.0;  // s spent past 70 degrees of heel
		int WindwardSide = 1;       // +1 = wind from starboard (starboard tack), -1 = from port
		double Time = 0.0;
	};

	/** Derived quantities for the HUD, the tests and the visuals. Angles in radians unless noted. */
	struct FBoatTelemetry
	{
		double BoatSpeed = 0.0;       // m/s over ground (flat water, no current: same as through water)
		double ForwardSpeed = 0.0;    // m/s along the bow
		double Heading = 0.0;
		double Heel = 0.0;            // positive = heeled to port
		double Pitch = 0.0;
		double Leeway = 0.0;          // angle between heading and track
		double TrueWindSpeed = 0.0;   // m/s at 10 m
		double TrueWindAngle = 0.0;   // + = wind from starboard
		double ApparentWindSpeed = 0.0; // m/s at the masthead
		double ApparentWindAngle = 0.0; // + = wind from starboard
		double VMG = 0.0;             // m/s toward the true wind (negative running)
		double HelmForce = 0.0;       // N at the tiller end; positive = weather helm
		double RudderAngle = 0.0;
		double DriveForce = 0.0;      // N, sail force along the bow
		double HeelingForce = 0.0;    // N, sail force across the boat
		bool bInIrons = false;
		bool bAground = false;        // keel, rudder or hull touching the bottom
		bool bCollision = false;      // touching a dock, bridge or another vessel this step
		bool bVesselContact = false;  // touching another vessel this step
		double DepthUnderKeel = 100.0; // m of water below the keel tip
		double SpeedThroughWater = 0.0; // m/s, forward speed relative to the water (the log); BoatSpeed is over ground
		double CourseOverGround = 0.0;  // rad, direction of travel over the ground
		bool bCapsized = false;       // lying on its side (or worse) for more than two seconds
		bool bPlaning = false;        // dinghies and beach cats: up on the plane
		bool bFlyingHull = false;     // multihulls: the windward hull (or ama) is clear of the water
		double Froude = 0.0;          // boat speed / sqrt(g LWL)
		// Wave physics (docs/wave-physics/): the hulls' calm-water resistance (friction and residuary), their added
		// resistance in the waves, both N against her motion, and the waves' slope push along the bow (N, positive
		// forward: the surf down a face; it averages out over a wave she does not ride).
		double CalmResistance = 0.0;
		double WaveResistance = 0.0;
		double WaveSlopeSurge = 0.0;
		bool IsStarboardTack() const { return TrueWindAngle > 0.0; }

		FSailStripState MainStrips[kMaxSailStrips];
		FSailStripState JibStrips[kMaxSailStrips];
		FSailStripState SpinStrips[kMaxSailStrips];
		int NumMainStrips = 0, NumJibStrips = 0, NumSpinStrips = 0;
		Vec3 MastheadWindBody;        // apparent wind at the masthead, body frame (air velocity)
		// Crew C1: what the crew feel. The centre of gravity's acceleration (at rest afloat it reads zero) and the
		// angular acceleration, both body frame, each a 25 ms mean so one contact step does not spike them; the turn
		// rate is FBoatState::AngularVelocity.
		Vec3 AccelBody;               // m/s^2
		Vec3 AngularAccelBody;        // rad/s^2
	};

	/**
	 * Force-based 6-DOF sailboat: hydrostatics from hull columns against the water surface (one or more hulls),
	 * ITTC-57 friction and Froude-number wave resistance per hull, keels, boards and rudders as finite wings, main,
	 * jib and spinnaker as strips with lift/drag against angle of attack, engines, and crew weight that hikes,
	 * trapezes or rights a capsized boat. Leeway, weather helm, heel, stall, luffing, flying a hull and capsize
	 * come out of the forces. Deterministic: the same controls and wind give the same result.
	 */
	class SAILINGPHYSICS_API FBoatModel
	{
	public:
		explicit FBoatModel(const FBoatConfig& InConfig = FBoatConfig::J22());

		/** Puts the boat on the water at a world XY with a heading (rad) and forward speed (m/s), floating level. */
		void Reset(double X, double Y, double Heading, double Speed = 0.0);

		/** One fixed physics step. Waves are optional (flat water when null). */
		void Step(double Dt, const FBoatControls& Controls, const FWindField& Wind, const FWaveField* Waves = nullptr);

		const FBoatState& GetState() const { return State; }
		FBoatState& GetMutableState() { return State; }
		const FBoatTelemetry& GetTelemetry() const { return Telemetry; }
		/** Replays draw a recorded boat by setting her telemetry (sail shapes) directly. */
		FBoatTelemetry& GetMutableTelemetry() { return Telemetry; }
		const FBoatConfig& GetConfig() const { return Config; }
		FBoatConfig& GetMutableConfig() { return Config; }

		/** World position of the body origin (design waterline, midships). */
		Vec3 OriginPosition() const { return State.Position - State.Orientation.Rotate(CenterOfGravity); }
		Vec3 BodyToWorld(const Vec3& BodyPoint) const { return OriginPosition() + State.Orientation.Rotate(BodyPoint); }

		double TotalMass() const { return Mass; }
		const Vec3& GetCenterOfGravity() const { return CenterOfGravity; }
		double HullDepth() const { return CanoeDepth; }
		/** Grounding probes (body frame): foil feet and the hulls' keel lines. */
		const std::vector<Vec3>& GetBottomPoints() const { return BottomPoints; }
		/** The design (upright, at rest) displaced volume of the canoe bodies (m^3) and its centroid, the centre of
		 *  buoyancy, in the body frame. The visual models are checked against these (SailingSim.Visual.J22Mesh). */
		double DesignDisplacedVolume() const { return DesignVolume; }
		Vec3 DesignBuoyancyCentre() const;

		/** Lake bed for grounding (optional), docks and bridges for collisions (optional). */
		void SetTerrain(const FLakeTerrain* InTerrain) { Terrain = InTerrain; }
		/** Obstacles are indexed on a grid when set, so a bay full of piers and jetties costs no more than a lake. */
		void SetObstacles(const std::vector<FObstacleSegment>* InObstacles);
		/** Other vessels' hulls near this one (a few segments each, replaced every frame; checked without the grid). */
		void SetMovingObstacles(const std::vector<FObstacleSegment>& InMoving) { MovingObstacles = InMoving; }
		/** The water's own motion (tidal current, m/s, world XY) around the boat: the hull and foils feel water relative to it. */
		void SetWaterCurrent(const Vec3& Current) { WaterCurrent = Vec3(Current.X, Current.Y, 0.0); }
		const Vec3& GetWaterCurrent() const { return WaterCurrent; }
		std::vector<FMooringLine>& GetMooringLines() { return Mooring; }
		const std::vector<FMooringLine>& GetMooringLines() const { return Mooring; }

		/** Water surface height at a world XY at the boat's current time (the wave field of the last Step). */
		double WaterHeightAt(double X, double Y) const { return CurrentWaves ? CurrentWaves->Height(X, Y, State.Time) : 0.0; }

		/** Hydrostatic righting moment (N m) at a fixed heel, boat level in pitch and floating at its waterline. For tests. */
		double RightingMomentAt(double HeelRad) const;

		/** Cleats for dock lines (body frame): bow, both quarters and both midship springs. */
		std::vector<Vec3> CleatPoints() const;

	private:
		struct FColumn { double X, Y, ZBottom, ZTop, Area; int Hull; };
		/** W3: the sea's bands where she is (FWaveField::BandsAt), refilled each step when the field has a sea map. */
		std::vector<FWaveBand> LocalSeaBands;

		void BuildHull();
		double SubmergedVolumeUpright(double Depth) const;
		void ComputeSails(double Dt, const FBoatControls& Controls, const FWindField& Wind, Vec3& InOutForceBody, Vec3& InOutTorqueBody);
		Vec3 PointVelocityWorld(const Vec3& BodyPoint) const;
		/** Velocity of a body point relative to the water (over ground minus the current and the waves' orbital flow). */
		Vec3 PointVelocityThroughWater(const Vec3& BodyPoint) const { return PointVelocityWorld(BodyPoint) - WaterCurrent - OrbitalFlowAt(BodyPoint); }
		/**
		 * docs/surfing/: the waves' orbital velocity (world XY) at a body point, from this step's samples at her bow and stern
		 * ends at two depths (her canoe body's middle and her deepest foil's), linear along her length and in depth.
		 */
		void SampleOrbitalFlow(const FWaveField* Waves);
		Vec3 OrbitalFlowAt(const Vec3& BodyPoint) const;
		double ResistanceCoefficient(double Froude) const;
		void BuildContactPoints();

		FBoatConfig Config;
		FBoatState State;
		FBoatTelemetry Telemetry;
		std::vector<FColumn> Columns;
		double Mass = 0.0;
		Vec3 CenterOfGravity;
		Vec3 Inertia, EffectiveInertia, EffectiveMass;
		double CanoeDepth = 0.25;
		std::vector<double> DesignHullVolume; // m^3 each hull displaces floating upright at rest
		double DesignVolume = 0.0;
		std::vector<Vec3> BottomPoints, OutlinePoints; // grounding and collision probes (body frame)
		double MainMeanLift = 0.0;
		std::vector<double> ColumnMeanVolume; // each column's immersion below her mean waterplane, averaged (the slope push, m^3)
		struct FColumnWater { Vec3 Low; double Water, VZ, SlopeX, SlopeY; bool bNear; };
		std::vector<FColumnWater> ColumnWater; // this step's water at each column (scratch)
		bool bColumnMeanFresh = true;         // after a reset: start the averages at the immersion she has
		const FWaveField* CurrentWaves = nullptr;
		const FLakeTerrain* Terrain = nullptr;
		const std::vector<FObstacleSegment>* Obstacles = nullptr;
		std::vector<FObstacleSegment> MovingObstacles;
		// Obstacle grid: cells of ObstacleCell meters, each listing the segments (with their radius) that reach into it.
		double ObstacleCell = 32.0, ObstacleX0 = 0.0, ObstacleY0 = 0.0;
		int ObstacleRows = 0, ObstacleCols = 0;
		std::vector<std::vector<int>> ObstacleBuckets;
		Vec3 WaterCurrent;
		bool bOrbitalFlow = false;
		double OrbitalX[2] = {}, OrbitalDepth[2] = {}; // body x of the stations (aft, fore) and the sample depths (m)
		Vec3 OrbitalFlow[2][2];                        // [station][depth], world XY
		std::vector<FMooringLine> Mooring;
	};
}
