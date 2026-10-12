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
		bool bSpinnaker = false; // spinnaker (or gennaker / screacher) hoisted, if the boat has one
		double SpinSheet = 0.5;  // 0 = trimmed in, 1 = eased
		int Reef = 0;            // mainsail reefs taken in (0 = full main)
		double Board = 1.0;      // centerboard / daggerboard / swing keel: 1 = fully down, 0 = up
		double Throttle = 0.0;   // engine(s): -1 full astern .. 1 full ahead (0 = neutral)
		double ThrottleSplit = 0.0; // twin engines: + = more thrust on the port engine (turns the bow to starboard)
		bool bRighting = false;  // capsized: crew on the centerboard (dinghy) or on the righting line (beach cat)
	};

	enum class EBoatType : unsigned char
	{
		J22, Sunfish, ILCA7, Catalina22, Catalina30, Hobie16, Corsair880, Lagoon42, Count
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

		double DeckHalfBeam(double X) const;
		double SheerHeight(double X) const;
		double KeelLineDepth(double X, double MainDepth) const;
		double BottomZ(double X, double Y, double MainDepth) const; // Y relative to CenterY
		double WaterlineLength() const { return 2.0 * WaterlineHalfLength; }
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
		double CrewMass = 240.0;     Vec3 CrewCG = Vec3(-1.20, 0.0, 0.55); // three crew, sitting on centerline
		int CrewCount = 3;
		double CrewSitOut = 0.30;    // m from centerline sitting on the windward side
		double CrewHikeOut = 0.65;   // extra m at full hike (torso over the lifelines) or out on the trapeze
		double CrewMoveSpeed = 1.6;  // m/s moving across the boat
		bool bTrapeze = false;
		double RightingLever = 0.0;  // m below the hull the righting crew stands (board tip, or leaning on the righting line); 0 = cannot be righted

		Vec3 RadiiOfGyration = Vec3(0.95, 1.75, 1.65); // roll, pitch, yaw (m)
		Vec3 AddedMassRatio = Vec3(0.05, 0.75, 1.0);    // surge, sway, heave as a fraction of mass
		Vec3 AddedInertiaRatio = Vec3(0.35, 0.8, 0.6);  // roll, pitch, yaw

		// Hulls (one for a monohull, two for a catamaran, three for a trimaran: main hull first).
		std::vector<FHullShape> Hulls;
		double LengthOverall = 6.86, WaterlineLength = 5.79, Beam = 2.44, WaterlineBeam = 2.0;
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
		double ExtraRollDamping = 0.0;    // N m s; the easy difficulty adds some
		// Added resistance in waves: AddedResistanceCoef x R(lambda/LWL) x rho g (Hs/2)^2 B^2 / LWL, largest heading
		// into the waves ((1 + cos)^2 / 4 of the angle off the wave direction) and growing with speed up to about 4 kn.
		// R = r^4 / (0.25 + r^4) with r = mean wavelength / LWL: short chop barely pitches the boat, waves near hull
		// length do (Gerritsma-Beukelman style scaling). The coefficient is calibrated so the J/22 matches ORC's polar,
		// which assumes a moderate sea state. Heave and pitch in the waves come from the hydrostatics directly.
		double AddedResistanceCoef = 1.3;
		// Speed (m/s / 2) at which the added resistance stops growing: a keelboat's pitching saturates by about 4 kn;
		// a light catamaran keeps slamming harder into the chop the faster it goes.
		double AddedResistanceSpeedCap = 1.0;

		// Foils: keels, boards and rudders. Rudders are linked to one tiller (or wheel).
		std::vector<FFoilDef> Foils;
		double KeelDownwashFactor = 1.0;  // fraction of the keel's downwash angle that reaches the rudder
		double MaxRudderAngleDeg = 30.0;
		double RudderStockToCP = 0.09;    // m, center of pressure behind the stock (unbalanced transom rudder)
		double TillerLength = 1.0;        // m
		double HelmStiffness = 600.0;     // N m/rad, how firmly the helm holds the tiller; lower = more helm feel
		double RudderResponseTime = 0.10; // s

		// Sails. A sail with NumStrips = 0 is absent (una and lateen rigs have no jib).
		FSailGeometry Main;
		FSailGeometry Jib;
		FSailGeometry Spinnaker;
		bool bAsymmetricSpinnaker = false; // gennaker or screacher tacked to the bow or a sprit (no pole)
		double MastX = 1.0;
		double MastheadZ = 9.25;
		double MastDiameter = 0.10;       // m; a sealed mast floats a little when the boat is on its side
		double BoomZ = 1.45;              // m, gooseneck height
		double MainMaxEaseDeg = 85.0;     // how far the boom can go out (shrouds)
		double TravelerRangeDeg = 8.0;    // boom angle the traveler moves either side of the centerline
		double JibMinAngleDeg = 8.0, JibMaxAngleDeg = 80.0;
		double RigWindageCdA = 0.8;       // m^2 (mast, rigging)
		double HullWindageCdA = 0.8;      // m^2 (topsides, crew)
		// Reefing: luff length left at each reef, as a fraction of the full main.
		std::vector<double> ReefLuffFraction;
		// Main build recipe, kept so reefs can rebuild it: foot and head heights, chords, roach, luff X.
		double MainFootZ = 1.45, MainHeadZ = 9.05, MainFootChord = 2.97, MainHeadChord = 0.45, MainRoach = 0.12, MainLuffX = 0.95, MainLuffXHead = 0.95, MainArea = 11.5;

		std::vector<FEngineDef> Engines;

		// How a good crew sails this boat: the heel they depower at, and how far they will ease the main to do it.
		double TrimHeelLimitDeg = 22.0;
		double TrimMaxEaseDeg = 25.0;

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
		bool bCollision = false;      // touching a dock or bridge this step
		double DepthUnderKeel = 100.0; // m of water below the keel tip
		double SpeedThroughWater = 0.0; // m/s, forward speed relative to the water (the log); BoatSpeed is over ground
		double CourseOverGround = 0.0;  // rad, direction of travel over the ground
		bool bCapsized = false;       // lying on its side (or worse) for more than two seconds
		bool bPlaning = false;        // dinghies and beach cats: up on the plane
		bool bFlyingHull = false;     // multihulls: the windward hull (or ama) is clear of the water
		double Froude = 0.0;          // boat speed / sqrt(g LWL)
		bool IsStarboardTack() const { return TrueWindAngle > 0.0; }

		FSailStripState MainStrips[kMaxSailStrips];
		FSailStripState JibStrips[kMaxSailStrips];
		FSailStripState SpinStrips[kMaxSailStrips];
		int NumMainStrips = 0, NumJibStrips = 0, NumSpinStrips = 0;
		Vec3 MastheadWindBody;        // apparent wind at the masthead, body frame (air velocity)
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
		const FBoatConfig& GetConfig() const { return Config; }
		FBoatConfig& GetMutableConfig() { return Config; }

		/** World position of the body origin (design waterline, midships). */
		Vec3 OriginPosition() const { return State.Position - State.Orientation.Rotate(CenterOfGravity); }
		Vec3 BodyToWorld(const Vec3& BodyPoint) const { return OriginPosition() + State.Orientation.Rotate(BodyPoint); }

		double TotalMass() const { return Mass; }
		const Vec3& GetCenterOfGravity() const { return CenterOfGravity; }
		double HullDepth() const { return CanoeDepth; }

		/** Lake bed for grounding (optional), docks and bridges for collisions (optional). */
		void SetTerrain(const FLakeTerrain* InTerrain) { Terrain = InTerrain; }
		/** Obstacles are indexed on a grid when set, so a bay full of piers and jetties costs no more than a lake. */
		void SetObstacles(const std::vector<FObstacleSegment>* InObstacles);
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

		void BuildHull();
		double SubmergedVolumeUpright(double Depth) const;
		void ComputeSails(double Dt, const FBoatControls& Controls, const FWindField& Wind, Vec3& InOutForceBody, Vec3& InOutTorqueBody);
		Vec3 PointVelocityWorld(const Vec3& BodyPoint) const;
		/** Velocity of a body point relative to the water (over ground minus the current). */
		Vec3 PointVelocityThroughWater(const Vec3& BodyPoint) const { return PointVelocityWorld(BodyPoint) - WaterCurrent; }
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
		const FWaveField* CurrentWaves = nullptr;
		const FLakeTerrain* Terrain = nullptr;
		const std::vector<FObstacleSegment>* Obstacles = nullptr;
		// Obstacle grid: cells of ObstacleCell meters, each listing the segments (with their radius) that reach into it.
		double ObstacleCell = 32.0, ObstacleX0 = 0.0, ObstacleY0 = 0.0;
		int ObstacleRows = 0, ObstacleCols = 0;
		std::vector<std::vector<int>> ObstacleBuckets;
		Vec3 WaterCurrent;
		std::vector<FMooringLine> Mooring;
	};
}
