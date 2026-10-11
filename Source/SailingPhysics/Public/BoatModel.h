#pragma once

#include "SailingPhysicsApi.h"
#include "SailingMath.h"
#include "Foil.h"
#include "Sail.h"
#include "Wind.h"
#include <vector>

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
		double Hike = 0.0;       // -1 = crew on the leeward side, 0 = sitting on the windward rail, 1 = fully hiked
	};

	/** J/22 particulars and model tuning. Class figures: LOA 22 ft 6 in, LWL 19 ft, beam 8 ft, 1,790 lb, 700 lb ballast. */
	struct SAILINGPHYSICS_API FBoatConfig
	{
		// Mass budget (body frame: origin at the design waterline, midships of the waterline; X fwd, Y stbd, Z up).
		double HullRigMass = 494.0;  Vec3 HullRigCG = Vec3(-0.15, 0.0, 0.35);
		double BallastMass = 318.0;  Vec3 BallastCG = Vec3(0.10, 0.0, -0.65); // centroid of a cast-lead fin
		double CrewMass = 240.0;     Vec3 CrewCG = Vec3(-1.20, 0.0, 0.55); // three crew, sitting on centerline
		double CrewSitOut = 0.30;    // m from centerline sitting on the windward side
		double CrewHikeOut = 0.65;   // extra m at full hike (torso over the lifelines)
		double CrewMoveSpeed = 1.6;  // m/s moving across the boat

		Vec3 RadiiOfGyration = Vec3(0.95, 1.75, 1.65); // roll, pitch, yaw (m)
		Vec3 AddedMassRatio = Vec3(0.05, 0.75, 1.0);    // surge, sway, heave as a fraction of mass
		Vec3 AddedInertiaRatio = Vec3(0.35, 0.8, 0.6);  // roll, pitch, yaw

		// Hull.
		double LengthOverall = 6.86, WaterlineLength = 5.79, Beam = 2.44, WaterlineBeam = 2.0;
		double WettedArea = 6.8;          // m^2, canoe body
		double FormFactor = 1.10;         // (1 + k) on ITTC-57 friction
		double HeaveDamping = 900.0;      // N s/m^3 per m^2 of submerged column (radiation damping stand-in)
		double YawDampingLinear = 400.0;  // N m s, low-speed yaw damping
		double HullLateralCd = 1.0;
		double HullLateralArea = 0.55;    // m^2 at each of two stations
		double MunkAddedMass = 250.0;     // A22 - A11 of the canoe body (kg)
		double ExtraRollDamping = 0.0;    // N m s; the easy difficulty adds some
		// Added resistance from wind-driven chop, as fraction of displacement weight at 10 kn true wind heading
		// straight into it. Scales with wind speed cubed (chop barely exists in light air) and (1 + cos TWA)^2 / 4. The flat water of Phase 1
		// has no waves to slow the boat; ORC's polars include a sea state, so this stands in until Phase 2.
		double ChopResistance = 0.008;

		// Foils.
		FFoilParams Keel;
		FFoilParams Rudder;
		double KeelDownwashFactor = 1.0;  // fraction of the keel's downwash angle that reaches the rudder
		double MaxRudderAngleDeg = 30.0;
		double RudderStockToCP = 0.09;    // m, center of pressure behind the stock (unbalanced transom rudder)
		double TillerLength = 1.0;        // m
		double HelmStiffness = 600.0;     // N m/rad, how firmly the helm holds the tiller; lower = more helm feel
		double RudderResponseTime = 0.10; // s

		// Sails.
		FSailGeometry Main;
		FSailGeometry Jib;
		double MastX = 1.0;
		double MastheadZ = 9.25;
		double RigWindageCdA = 0.8;       // m^2 (mast, rigging)
		double HullWindageCdA = 0.8;      // m^2 (topsides, crew)

		FBoatConfig();
		static FBoatConfig J22() { return FBoatConfig(); }
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
		double CrewOffset = 0.0;    // m, crew position from centerline (+ = starboard)
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
		bool IsStarboardTack() const { return TrueWindAngle > 0.0; }

		FSailStripState MainStrips[kMaxSailStrips];
		FSailStripState JibStrips[kMaxSailStrips];
		int NumMainStrips = 0, NumJibStrips = 0;
		Vec3 MastheadWindBody;        // apparent wind at the masthead, body frame (air velocity)
	};

	/**
	 * Force-based 6-DOF J/22: hydrostatics from hull columns against the water surface, ITTC-57 friction and
	 * Froude-number wave resistance, keel and rudder as finite wings, main and jib as strips with lift/drag
	 * against angle of attack. Leeway, weather helm, heel, stall and luffing come out of the forces.
	 * Deterministic: the same controls and wind give the same result.
	 */
	class SAILINGPHYSICS_API FBoatModel
	{
	public:
		explicit FBoatModel(const FBoatConfig& InConfig = FBoatConfig::J22());

		/** Puts the boat on the water at a world XY with a heading (rad) and forward speed (m/s), floating level. */
		void Reset(double X, double Y, double Heading, double Speed = 0.0);

		/** One fixed physics step. */
		void Step(double Dt, const FBoatControls& Controls, const FWindField& Wind);

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

		/** Water surface height at a world XY. Flat for Phase 1; waves arrive in Phase 2. */
		double WaterHeightAt(double, double) const { return 0.0; }

		/** Hydrostatic righting moment (N m) at a fixed heel, boat level in pitch and floating at its waterline. For tests. */
		double RightingMomentAt(double HeelRad) const;

	private:
		struct FColumn { double X, Y, ZBottom, ZTop, Area; };

		void BuildHull();
		double SubmergedVolumeUpright(double Depth) const;
		void ComputeSails(double Dt, const FBoatControls& Controls, const FWindField& Wind, Vec3& InOutForceBody, Vec3& InOutTorqueBody);
		Vec3 PointVelocityWorld(const Vec3& BodyPoint) const;
		double ResistanceCoefficient(double Froude) const;

		FBoatConfig Config;
		FBoatState State;
		FBoatTelemetry Telemetry;
		std::vector<FColumn> Columns;
		double Mass = 0.0;
		Vec3 CenterOfGravity;
		Vec3 Inertia, EffectiveInertia, EffectiveMass;
		double CanoeDepth = 0.25;
		double MainMeanLift = 0.0;
	};
}
