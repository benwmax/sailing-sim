#pragma once

#include "SailingPhysicsApi.h"
#include "AutoTrim.h"
#include "BoatModel.h"
#include "Rules.h"
#include <functional>
#include <memory>
#include <random>
#include <string>
#include <vector>

namespace Sailing
{
	class FLakeTerrain;
	class FWindField;
	class FWaveField;
	struct FRaceRunner;

	/** The kinds of traffic: sailboats sail on the full physics; the rest are power-driven (or say so in their status). */
	enum class ETrafficKind : uint8_t
	{
		Sailboat,
		Powerboat,   // ski boat, bass boat, center console
		Trawler,     // shrimp boat with her nets out: engaged in fishing
		TugAndTow,   // a tug pushing barges: restricted in her ability to maneuver
		Ship,        // a deep-draft ship in the channel: constrained by her draft
		Committee,   // the race committee boat, at anchor on the start line
	};

	SAILINGPHYSICS_API const char* TrafficKindName(ETrafficKind Kind);

	/** How a power-driven vessel handles: a turn rate and acceleration, not a hull model. */
	struct SAILINGPHYSICS_API FPowerVesselType
	{
		double Length = 6.0, Beam = 2.4, Draft = 0.6;
		double CruiseKnots = 20.0;
		double TurnRateDeg = 12.0;    // at cruising speed; slower vessels turn proportionally slower
		double Accel = 1.5;           // m/s^2 (and as much to slow down)
		EVesselStatus Status = EVesselStatus::PowerDriven;

		static FPowerVesselType For(ETrafficKind Kind);
	};

	/** A power-driven vessel steered by course and speed orders (kinematic, with the current added). */
	struct SAILINGPHYSICS_API FPowerVessel
	{
		FPowerVesselType Type;
		double X = 0.0, Y = 0.0, Heading = 0.0, Speed = 0.0; // Speed through the water, m/s (negative: astern)
		double VX = 0.0, VY = 0.0;                           // over the ground
		double OrderedHeading = 0.0, OrderedSpeed = 0.0;

		void Step(double Dt, const Vec3& Current);
	};

	/** Something worth telling the player about (and what the tests check). */
	struct SAILINGPHYSICS_API FTrafficEvent
	{
		enum EType : uint8_t { Signal, GiveWay, StandOnAction, Collision };
		EType Type = Signal;
		double Time = 0.0;
		int Vessel = 0;          // who acted (or the first of the pair)
		int Other = -1;
		ESoundSignal Sound = ESoundSignal::None;
		int GiveWayId = -1;      // for collisions: who was required to keep clear at the time
		std::string Text;
	};

	/** One vessel of the traffic: either a sailboat on the physics or a power vessel, with her helmsman's state. */
	struct SAILINGPHYSICS_API FTrafficVessel
	{
		int Id = 0;
		ETrafficKind Kind = ETrafficKind::Sailboat;
		std::string Name;
		std::shared_ptr<FBoatModel> Boat; // sailboats
		FBoatControls Controls;
		FAutoTrim Trim;
		FAutopilot Pilot;
		FPowerVessel Power;               // everything else

		std::vector<std::pair<double, double>> Route;
		size_t RouteIndex = 0;
		bool bLoopRoute = true;
		bool bAnchored = false;
		double CruiseFraction = 1.0;      // power: share of cruising speed

		// The helmsman.
		double DesiredHeading = 0.0;      // what the route asks for
		double SteerHeading = 0.0;        // what she steers (avoiding something, or the route)
		double SpeedFactor = 1.0;
		int Avoiding = -1;                // Id she is keeping clear of
		bool bStandOnAction = false;      // Rule 17(b): taking action as the stand-on vessel
		int ActingFor = -1;               // the vessel she is taking that action for
		int Side = 1;                     // sailboats: the tack or gybe she is on (+1 wind from starboard), held through a tack
		double LastTackTime = -100.0;
		double StoppedUntil = -1.0;       // power: engines stopped after a collision
		double LastSignalTime = -100.0;
		double FiveBlastTime = -100.0;
		int RaceEntry = -1;               // index in the race, or -1
		bool bIgnoresRules = false;       // tests: a vessel that will not give way (to check the stand-on vessel's Rule 17(b))

		bool IsSail() const { return Kind == ETrafficKind::Sailboat; }
		double Length() const;
		double Beam() const;
		double Draft() const;
		FVesselSnapshot Snapshot() const;
	};

	/**
	 * The traffic on the water around the player: AI sailboats on the same physics as the player's, and power
	 * vessels from runabouts to ships. Each helmsman follows a route and the Navigation Rules: the give-way vessel
	 * takes early and substantial action (Rule 16) by turning (to starboard where she can, never across the other's
	 * bow if she can help it) or slowing; the stand-on vessel holds course and speed (Rule 17(a)) until the other is
	 * clearly not acting, then sounds the danger signal and does what best avoids collision (Rule 17(b)). Power-driven
	 * vessels sound maneuvering signals when they turn for another vessel (Rule 34). Collisions are recorded with who
	 * was required to keep clear.
	 */
	class SAILINGPHYSICS_API FTrafficSim
	{
	public:
		static constexpr int PlayerId = 0;
		static constexpr double DecisionInterval = 0.25; // s between the helmsmen's looks around
		/** Off: every helmsman ignores everyone (for showing that a test scenario really is a collision course). */
		bool bFollowRules = true;

		void SetWorld(const FWindField* InWind, const FWaveField* InWaves, const FLakeTerrain* InTerrain, std::function<Vec3(double, double)> InCurrentAt = nullptr);

		int AddSailboat(EBoatType Type, double X, double Y, double Heading, std::vector<std::pair<double, double>> Route, const std::string& Name);
		int AddPower(ETrafficKind Kind, double X, double Y, double Heading, std::vector<std::pair<double, double>> Route, const std::string& Name);
		/** A sailboat whose model lives elsewhere (the game's boat actor draws it); already placed and configured. */
		int AddSailboatModel(std::shared_ptr<FBoatModel> Model, std::vector<std::pair<double, double>> Route, const std::string& Name);
		void Remove(int Id);
		void Clear();

		/** The player's boat as the AI sees her this step (or not present). Hull: length, beam, heading at her center. */
		void SetPlayer(const FVesselSnapshot& Player, double Beam, bool bPresent = true);

		void Step(double Dt);
		/** Perf 1: runs Body(0..Count-1), perhaps in parallel. The game sets it to Unreal's ParallelFor: each sailboat's
		 *  step touches only that boat (wind, waves, terrain and the current are read-only meanwhile), so the result is
		 *  the same as stepping them in order, which is what happens when it is unset. */
		std::function<void(int, const std::function<void(int)>&)> ParallelFor;

		/** Other vessels' hulls as obstacle segments near a point (for the player's boat physics). */
		std::vector<FObstacleSegment> HullsNear(double X, double Y, double Radius, int ExcludeId) const;

		/** The rules decision and risk between the player and each nearby vessel (for the HUD and the coach). */
		struct FPlayerSituation { int Other = -1; FCollisionRisk Risk; FRuleDecision Decision; };
		std::vector<FPlayerSituation> PlayerSituations(double MaxRange) const;

		std::vector<FTrafficVessel>& GetVessels() { return Vessels; }
		const std::vector<FTrafficVessel>& GetVessels() const { return Vessels; }
		const FTrafficVessel* Find(int Id) const;
		FTrafficVessel* Find(int Id);
		std::vector<FTrafficEvent>& Events() { return EventLog; }
		const std::vector<FTrafficEvent>& Events() const { return EventLog; }
		/** Puts the traffic clock in step with the game's (wind and waves run on it). */
		void SetTime(double InTime) { Time = InTime; NextDecision = InTime; }
		double GetTime() const { return Time; }
		double WindFrom() const;
		/** W1: where the wind at a place comes from now (rad): the puffs and shifts a sailor sees there. */
		double LocalWindFrom(double X, double Y) const;

		/** Racing: the race the AI racers follow (owned by the caller). */
		void SetRace(FRaceRunner* InRace) { Race = InRace; }

	private:
		void Decide(FTrafficVessel& V);
		void DecideCourse(FTrafficVessel& V);
		double Lookahead(const FTrafficVessel& V) const;
		bool HeadingClear(const FTrafficVessel& V, double X, double Y, double Heading, double Distance) const;
		void Navigate(FTrafficVessel& V);
		void Apply(FTrafficVessel& V, double Dt);
		double SailableHeading(const FTrafficVessel& V, double Heading, bool bKeepTack) const;
		/** W1: tack upwind on a header, or for clearly more pressure on the other tack. */
		bool WantsShiftTack(const FTrafficVessel& V, double Target) const;
		double ChooseAvoidance(const FTrafficVessel& V, const FVesselSnapshot& Own, const FVesselSnapshot& Other, double Safe, bool bStarboardOnly, bool& bOutSlow,
			const std::vector<std::pair<FVesselSnapshot, double>>& Nearby) const;
		void DetectCollisions();
		std::vector<FVesselSnapshot> Snapshots() const;
		void Emit(FTrafficEvent Event);

		std::vector<FTrafficVessel> Vessels;
		const FWindField* Wind = nullptr;
		const FWaveField* Waves = nullptr;
		const FLakeTerrain* Terrain = nullptr;
		std::function<Vec3(double, double)> CurrentAt;
		FVesselSnapshot Player;
		double PlayerBeam = 2.4;
		bool bPlayer = false;
		double Time = 0.0, Accumulator = 0.0, NextDecision = 0.0;
		int NextId = 1;
		std::vector<FTrafficEvent> EventLog;
		std::vector<std::pair<int, int>> Touching; // pairs in contact (so one collision is one event)
		std::vector<std::pair<std::pair<int, int>, double>> LastContact; // pair -> last time they touched
		std::vector<std::pair<std::pair<int, int>, int>> LastGiveWay; // pair -> give-way Id at the last look
		FRaceRunner* Race = nullptr;
	};

	/** Routes through water deep enough for a draft (straight legs that stay off the bottom). */
	namespace TrafficRoutes
	{
		/** True if the straight line stays in water at least MinDepth deep (checked every 15 m). */
		SAILINGPHYSICS_API bool ClearPath(const FLakeTerrain& Terrain, double AX, double AY, double BX, double BY, double MinDepth);
		/** A random point within Radius of a center in water at least MinDepth deep; false if none found. */
		SAILINGPHYSICS_API bool DeepPoint(const FLakeTerrain& Terrain, std::mt19937& Rng, double CX, double CY, double Radius, double MinDepth, double& OutX, double& OutY);
		/** A loop of Count waypoints joined by clear legs, starting at (X, Y). */
		SAILINGPHYSICS_API std::vector<std::pair<double, double>> RandomLoop(const FLakeTerrain& Terrain, std::mt19937& Rng, double X, double Y, double Radius, double MinDepth, int Count);
		/**
		 * The shortest path through water deeper than MinDepth between two points (a 4-connected search on a grid of
		 * Cell meters, then straightened): how a ship keeps to the dredged channel. Empty if there is none.
		 */
		SAILINGPHYSICS_API std::vector<std::pair<double, double>> DeepWaterPath(const FLakeTerrain& Terrain, double AX, double AY, double BX, double BY, double MinDepth, double Cell = 60.0);
	}
}
