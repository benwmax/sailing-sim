#pragma once

#include "SailingPhysicsApi.h"
#include "BoatModel.h"

namespace Sailing
{
	struct FAutoTrimSettings
	{
		double AlphaMarginDeg = 2.0;   // aim this far below each sail's stall angle
		double HeelLimitDeg = 22.0;    // start depowering above this heel
		double FlattenFromKnots = 9.0; // start flattening sails above this true wind
		double FlattenRangeKnots = 6.0;
		bool bTrimMain = true;
		bool bTrimJib = true;
		bool bHike = true;
		bool bShape = true;            // vang, outhaul, cunningham, backstay
		double RateScale = 1.0;        // sheet speed against a good crew's (Easy mode: faster)
		bool bEasePuffs = false;       // a keelboat crew eases in a puff the way a dinghy sailor does (Easy mode)
		/**
		 * docs/trimmer-hands/: the crew's hands. A trimmer sees the sail and the heel over a couple of seconds, not each roll
		 * (ReactionSeconds; in light air they play the sheets, LightReactionSeconds; HeelTrendSeconds, while a sheet in the
		 * hand on a dinghy or a beach cat answers the heel at once), makes an
		 * adjustment when what they see is off by more than a dead band (degrees of the sail's angle at the boom or clew),
		 * moving at the sheet's own rate until it is close, and otherwise only creeps it in or out.
		 */
		bool bHands = true;            // false: ideal trim, every step at the target (the reference polars, as a VPP trims)
		double ReactionSeconds = 1.5;
		double LightReactionSeconds = 0.2; // in light air, LightAirKnots and under, blended to ReactionSeconds by BreezeKnots
		double LightAirKnots = 8.0;
		double BreezeKnots = 14.0;
		double HeelTrendSeconds = 0.5; // at a 6 m waterline; longer boats as the square root of their waterline
		double HandHeelTrendSeconds = 0.0;  // a sheet in the hand (under HandSheetMassKg, or a dinghy sailor): felt at once
		double HandSheetMassKg = 500.0;
		double LightDeadBandDeg = 0.75; // the dead band in light air, blended to DeadBandDeg by BreezeKnots
		double DeadBandDeg = 2.0;
		double RestSeconds = 1.5;      // in a breeze, after an adjustment the hand rests this long before the next (it creeps
		                               // meanwhile); in light air none
		double CreepDegPerSecond = 1.0; // below the dead band
		double HeelDeadBandDeg = 1.0;  // a keelboat crew eases past the heel limit plus this, trims back below it minus this
	};

	/**
	 * Trims the sails to the apparent wind the way a good crew would: each sail at a target angle of attack,
	 * flattened as the breeze builds, eased and feathered when heel passes a limit, crew hiking.
	 * Used by the polar tests and by the easy difficulty's trim assist.
	 */
	class SAILINGPHYSICS_API FAutoTrim
	{
	public:
		FAutoTrimSettings Settings;
		/**
		 * The helm has called a tack (FStationControls holds it from the call until she settles on the new tack): the main
		 * trimmer holds the main in, no easing for heel, the traveller no further to leeward than the centre, so she heads up
		 * on her weather helm. Eased instead, the main gives her lee helm the rudder cannot beat at the speed she has left.
		 */
		bool bHoldMain = false;

		/** Returns new controls; Tiller and anything not enabled in the settings pass through unchanged. */
		FBoatControls Update(const FBoatModel& Boat, const FBoatControls& Current, double Dt);

		/** Deliberate adjustments the hands have started (moves past the dead band, not the creep), for the tests. */
		int GetAdjustments() const { return Adjustments; }

		void Reset() { MainEase = 0.0; SpinEase = 0.0; FeltWind = 0.0; SetUpWind = 0.0; bSensed = false; MainHand = TravelerHand = JibHand = FHand(); bMainSeen = bJibSeen = false; }

	private:
		double MainEase = 0.0; // rad, extra ease from heel feedback
		double SpinEase = 0.0;   // spinnaker sheet blown (0..1) when she heels past the limit: how a crew stops a broach
		// A dinghy sailor's feel for a puff (0 until the first update):
		double FeltWind = 0.0;   // m/s, the true wind as the sailor feels it, a reaction time behind
		double SetUpWind = 0.0;  // m/s, the wind the boat is set up for (the last half minute's mean)
		// The trimmers' senses and hands (docs/trimmer-hands/).
		bool bSensed = false;
		double HeelSeen = 0.0, HeelRateSeen = 0.0; // deg, deg/s: the heel's trend
		struct FHand { bool bMoving = false; double Rest = 0.0; };
		FHand MainHand, TravelerHand, JibHand;
		// Each sail's foot angle as the trimmer sees it (rad): its angle of attack over ReactionSeconds, not each roll.
		double MainFootSeen = 0.0, JibFootSeen = 0.0;
		double ReactionNow = 1.5, DeadBandNow = 2.0, RestNow = 1.5; // this step's (light air to a breeze)
		bool bHandsNow = true;
		mutable int Adjustments = 0;
		bool bMainSeen = false, bJibSeen = false;
		/** One hand on a control: a move at the control's rate past the dead band, a creep below it. */
		double Work(FHand& Hand, double Now, double Target, double DegPerUnit, double RateOut, double RateIn, double Dt) const;
		double See(double& Seen, bool& bSeen, double Raw, double Dt) const;
	};

	/** Holds a true wind angle with the tiller. For tests and the AI later. */
	struct SAILINGPHYSICS_API FAutopilot
	{
		double TargetTWADeg = 45.0; // signed: + = wind from starboard
		double Gain = 2.5;          // tiller per radian of heading error
		double RateGain = 1.2;      // tiller per rad/s of yaw rate
		double MaxTiller = 0.6;     // a good helmsman keeps the rudder short of stalling (about 18 degrees)
		bool bKeepShortOfStall = true; // also limit the rudder to just past its stall angle (off for a deliberate hard tack)
		/** A helmsman leans on the tiller against the weather helm, which grows as she heels: rudder degrees per degree
		 *  of heel held in advance, so she does not settle a few degrees above her course. */
		double HelmPerHeel = 0.25;
		/**
		 * docs/gale-tack/: in a sea (Hs 0.5 m or more, not the calibration sea) a helmsman told to tack waits, up to one mean
		 * wave period, for her to be on a back (the waves' slope push along her bow against her: going uphill, SeaTrials'
		 * bins) with way on (forward speed at least TackSpeedShare of her upwind speed, the last 20 s's mean close-hauled),
		 * and holds the old tack's angle meanwhile. On flat water and in lake chop she tacks at once, as before.
		 */
		bool bTimeTacks = true;
		double TackSpeedShare = 0.7;
		/**
		 * docs/hobie-run/: the run guard. With the wind field given, a target deeper than 180 - margin is held at it: the
		 * margin is ByTheLeeMarginDeg, plus ByTheLeePerGust per unit of the gustiness where she is (GustIntensity and the
		 * puffs, times the shelter's GustScaleAt), plus RunMarginPerSpeedShare per unit of her speed over the true wind's
		 * past 0.25 (a fast cat's weak apparent wind from astern swings across with any wobble), 40 at most. On a run she
		 * steers with RunGainShare of the gain and bears away by RunBearAwayMax of tiller at most (a hard bear-away rolls a
		 * cat to windward); past 175 deg, by the lee, or with the apparent wind deep (past 168) she heads up 10 deg more at
		 * twice the gain. A gybe she is told to make (the target moved to the other side) goes through untouched. Without
		 * the wind (the calibrated polars, scenarios, sea trials, the traffic AI for now) nothing changes.
		 */
		const FWindField* Wind = nullptr;
		double ByTheLeeMarginDeg = 5.0;
		double ByTheLeePerGust = 80.0;
		/** With the guard on a run: the share of Gain she steers with, and the most tiller she bears away with. */
		double RunGainShare = 0.5;
		/** Degrees more margin per unit of her speed over the true wind's past 0.25 (to 0.6). */
		double RunMarginPerSpeedShare = 60.0;
		double RunBearAwayMax = 0.08;

		double Update(const FBoatModel& Boat) const;
		/** The margin from dead downwind (deg) the run guard keeps at a point, for the wind given (ByTheLeeMarginDeg without). */
		double RunMarginDeg(double X, double Y) const;

	private:
		// The helm's own sense of the boat (Update is called every step): her upwind speed, and a tack she is waiting to start.
		mutable double UpwindSpeed = -1.0, LastTime = -1.0, TackAskedAt = -1.0;
		mutable bool bTackGo = false;
		// The run guard: the side the target was on last step, and a gybe she was told to make (until she is round).
		mutable double LastTargetSide = 0.0;
		mutable bool bGybeOrdered = false;
	};
}
