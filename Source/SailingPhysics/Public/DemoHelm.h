#pragma once

#include "SailingPhysicsApi.h"
#include "BoatModel.h"
#include "LakeTerrain.h"
#include <cstdint>
#include <unordered_map>
#include <vector>

namespace Sailing
{
	/**
	 * docs/demo-shoal-guard/ (sailing-feedback #31): the demo autopilot's lookout. The demo (-SailingDemo) beats to windward
	 * in short tacks (or holds a wind angle), so left alone it sails until it meets the shore upwind and stays aground there
	 * (Galveston from launch 1 at minute 11, Ray Hubbard's south shore). The guard reads the chart ahead: while the water
	 * along her mean course (straight upwind when beating, her heading when holding an angle) is deep enough for LookSeconds
	 * of sailing and her tacks' own headings are clear close by, the demo sails exactly as before (open-water views and gate
	 * benches are unchanged). When it is not, she bears away onto the wind angle with the longest clear water (preferring to
	 * sail away from the wind, then to keep her tack) and holds it for HoldSeconds and until the water upwind is open again;
	 * that course is watched the same way and changed if it runs into shallows too.
	 * Plain logic, no Unreal: SailingSim.Physics.DemoShoalGuard drives it on the real lakes.
	 */
	struct SAILINGPHYSICS_API FDemoShoalGuard
	{
		// What she reads: the chart's depth (water level at Z = 0, as the boat's probes) and the docks, piers and bridges.
		const FLakeTerrain* Terrain = nullptr;
		const std::vector<FObstacleSegment>* Obstacles = nullptr;
		double Draft = 1.16;            // m, the boat's deepest point (FBoatConfig::Draft)
		double KeelMarginM = 0.6;       // water kept under the keel: the depth alarm's 2 ft (Galveston's bay is 2 to 3 m deep)
		double ObstacleMarginM = 12.0;  // room kept from a dock, piling or bridge pier (past its own radius)
		double CloseMarginM = 1.5;      // already nearer one than that (leaving the marina): the room kept from it instead
		double MastClearM = 12.0;       // a bridge deck higher than this (her masthead plus room) is not in her way

		// How far she looks: LookSeconds at her speed (MinLookM at least, MaxLookM at most); ScanM when choosing a course.
		double LookSeconds = 90.0;
		double MinLookM = 150.0;
		double MaxLookM = 400.0;
		double TackLookM = 40.0;        // beating: each tack's own heading must be clear this far (her legs are ~25 m)
		double ScanM = 1000.0;
		double StepM = 5.0;
		double HoldSeconds = 120.0;     // a bear-away is held at least this long
		double RepickSeconds = 10.0;    // and not sooner than this after the last choice, unless the way is shut right ahead
		double RepickM = 60.0;          // a bear-away's course is chosen again when it has less clear water than this (or the look)
		double CheckEverySeconds = 1.0;
		double BeatTwaDeg = 45.0;
		/** The guard keeps watch from this time on (s, the Update clock). The game's views and stills that hold a set angle
		 *  (-SailingHoldTWA: the gate's bench views, framed on that course for their first half minute) start it at 60 s. */
		double StartAfterSeconds = 0.0;

		/**
		 * The wind angle to steer (deg, signed as FAutopilot::TargetTWADeg) at Time, for a boat at (X, Y) going SpeedMs with the
		 * wind from WindFromRad (map frame). BaseTwaDeg is what the demo would sail on its own; bBeating says it is short-tacking
		 * upwind (its mean course is then the wind's direction, not its heading). Returns BaseTwaDeg while the water is clear.
		 */
		double Update(double Time, double X, double Y, double WindFromRad, double SpeedMs, double BaseTwaDeg, bool bBeating);

		/** Clear water (m) from (X, Y) along Heading (rad, map frame), MaxM at most: to the first point too shallow for her keel
		 *  plus the margin, or within the margin of an obstacle. */
		double ClearAhead(double X, double Y, double Heading, double MaxM) const;

		bool IsAvoiding() const { return bAvoiding; }
		double AvoidTwaDeg() const { return AvoidTwa; }
		int Avoidances() const { return Count; }
		void Reset() { bAvoiding = false; NextCheck = -1.0; Count = 0; ThinRef = -1.0; }
		/** The water she keeps to from a place: her keel plus the margin, or, in thinner water than that already, no
		 *  shallower than here (she then heads for the deepest water near: PickEscape). */
		double NeedAt(double X, double Y) const;

	private:
		double LookFor(double SpeedMs) const;
		bool CourseClear(double X, double Y, double WindFromRad, double BaseTwaDeg, bool bBeating, double Look) const;
		/** The bear-away's wind angle. Away from: the heading of the course being given up when choosing again (rad; 1e9 at the
		 *  first choice, when sailing back the way she came is what she wants). */
		double PickEscape(double X, double Y, double WindFromRad, double BaseTwaDeg, double AwayFrom) const;

		/** The obstacles on a grid of BucketM cells (built the first time a ray meets them; again if the list changes). */
		void IndexObstacles() const;
		static constexpr double BucketM = 100.0;
		mutable const std::vector<FObstacleSegment>* Indexed = nullptr;
		mutable size_t IndexedCount = 0;
		mutable std::unordered_map<int64_t, std::vector<int>> Buckets;
		mutable std::vector<int> Seen;   // per obstacle: the last ray that measured it

		mutable int Ray = 0;
		bool bAvoiding = false;
		double AvoidTwa = 0.0, AvoidSince = 0.0, PickedAt = 0.0, NextCheck = -1.0;
		double ThinRef = -1.0;   // depth (m) when she came into thin water, raised as she finds deeper; -1 in deep enough water
		int Count = 0;
	};
}
