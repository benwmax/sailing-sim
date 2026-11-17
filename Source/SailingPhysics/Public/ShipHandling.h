#pragma once

#include "SailingPhysicsApi.h"
#include "AutoTrim.h"
#include "BoatModel.h"

namespace Sailing
{
	/**
	 * docs/frigate-physics/: a square-rigged ship's manoeuvres as her officers ordered them, step by step on the brace,
	 * sail and helm controls (FBoatControls). Plain logic: the game's orders panel starts one and calls Update after the
	 * trimmer each physics step; the trial and the tests drive it the same way.
	 *
	 * Tacking (going about, the bow through the wind), from close-hauled:
	 *   "Ready about" ... "Helm's a-lee": the wheel put over to bring her up, the headsheets let fly, the spanker hauled
	 *   amidships to drive her stern round; "rise tacks and sheets" as she nears the wind (the courses' clews hauled up).
	 *   "Mainsail haul": nearly head to wind, the main and mizzen yards swung round for the new tack while the fore yards
	 *   stay as they were, their sails aback, paying her bow off on the new side (she gathers sternway, and the helm is
	 *   shifted for it). "Let go and haul": past the wind with the main yards drawing, the fore yards swung round and the
	 *   courses set again; she is kept a little free with the spanker brailed until she has way on, then brought to
	 *   close-hauled on the new tack. If she falls back on the old tack (missed stays, in light air or a short sea) the
	 *   order is given to wear instead.
	 * Wearing (the stern through the wind): the spanker brailed up and the helm put up; the yards trimmed as she bears
	 *   away, the wind brought aft and across the stern, then she is hauled up close-hauled on the new tack and the
	 *   spanker set again. Surer than tacking but it loses ground to leeward.
	 * Heaving to: the main yards laid square, their sails aback ("the main topsail to the mast"), against the fore and
	 *   mizzen yards braced up and drawing, the spanker's sheet eased, the helm minding her: she lies near-stopped, about
	 *   five points off the wind, forereaching a knot at most and drifting to leeward.
	 */
	enum class EShipManoeuvre : unsigned char { None, Tack, Wear, HeaveTo };

	/** Where a manoeuvre is, for the orders panel's captions. */
	enum class EShipManoeuvreStep : unsigned char
	{
		Idle,
		HelmsALee,       // tacking: the helm over, coming up toward the wind
		MainsailHaul,    // the main and mizzen yards swung; fore yards aback
		LetGoAndHaul,    // the fore yards swung; meeting her on the new tack
		BearAway,        // wearing: helm up, yards squaring
		Gybing,          // wearing: the stern through the wind
		HaulUp,          // wearing: coming up to close-hauled on the new tack
		HoveTo,          // lying hove to
		Done,
		MissedStays,     // a tack that failed head to wind: she wears instead
	};

	struct SAILINGPHYSICS_API FShipHandlingSettings
	{
		double CloseHauledDeg = 67.5;    // the course she is brought to on the new tack (true wind angle, six points)
		// Tacking.
		double RiseTacksDeg = 35.0;      // "rise tacks and sheets" (the courses' clews hauled up) this close to the true wind
		double MainsailHaulDeg = 15.0;   // "mainsail haul" this close to the true wind
		double MainHaulBrace = 1.0;      // "mainsail haul": the after yards swung this share of braced up for the new tack
		double LetGoDeg = 12.0;          // "let go and haul" no sooner than this far past the wind, once the main yards draw ...
		double DrawAlphaDeg = 2.0;       // ... (their lowest set sail's angle of attack past this) ...
		double LetGoLatestDeg = 25.0;    // ... or this far past it whether they draw or not
		double FullDeg = 15.0;           // after "let go and haul" she is kept this much free of close-hauled ...
		bool bBrailToPayOff = true;      // ... with the spanker brailed in ...
		double WayOnShare = 0.6;         // ... until her speed is back to this share of what it was before the tack
		double GatherWaySeconds = 240.0; // the tack is over this long after "let go and haul" whatever her speed
		double MissedStaysSeconds = 150.0; // still on the old side of the wind this long after the helm went over: she wears
		double PilotMaxTiller = 1.0;     // steering a course in a manoeuvre, the helm goes hard over if it must
		// Wearing.
		double WearTurnDegPerSecond = 1.5; // how fast the officer of the watch brings her round (the course ordered)
		double WearLeadDeg = 30.0;       // the course ordered at most this far ahead of where she is
		double WearGiveUpSeconds = 900.0; // a wear not round in this long ends (the helmsman takes her on whatever tack she is)
		// Heaving to.
		double HoveToBraceShare = 0.0;   // the main yards laid square, aback (a share past 0: braced for the other tack)
		double HoveToTwaDeg = 60.0;      // she lies about five points off the wind
		double HoveToSpankerSheet = 1.0; // the spanker's sheet eased right off (sheeted in, it heads her up into stays)
	};

	class SAILINGPHYSICS_API FShipHandling
	{
	public:
		FShipHandlingSettings Settings;

		/** Starts a manoeuvre from where she is (the tack she is on is the side the wind is on now). None ends one; the
		 *  courses and spanker an earlier order took in are set again at the next Update (call it once after None). */
		void Start(EShipManoeuvre Manoeuvre, const FBoatModel& Boat);
		/** Gives this step's orders over the controls the trimmer and the helmsman set (a no-op when idle or done).
		 *  Returns true while it holds the helm; the caller steers by its own helmsman otherwise. */
		bool Update(const FBoatModel& Boat, FBoatControls& Controls, double Dt);

		EShipManoeuvre Manoeuvre() const { return Current; }
		EShipManoeuvreStep Step() const { return StepNow; }
		bool IsActive() const { return Current != EShipManoeuvre::None && StepNow != EShipManoeuvreStep::Done; }
		/** The tack she will be on after it: + wind from starboard. */
		double NewSide() const { return -FromSide; }
		/** For a helmsman taking over after Done: the true wind angle to steer (deg, signed). */
		double CourseAfterDeg() const { return NewSide() * Settings.CloseHauledDeg; }
		double SecondsInManoeuvre() const { return Time; }
		static const char* StepName(EShipManoeuvreStep Step);

	private:
		/** Tacking: the courses' tacks and sheets hauled down again (as they were before "rise tacks and sheets"). */
		void LowerCourses(const FBoatConfig& C, FBoatControls& Controls);
		/** Tacking: the main mast's lowest set sail is full on the new tack. */
		bool MainDraws(const FBoatModel& Boat) const;
		/** The spanker brailed up (or set again), remembered so a cancelled order sets it again. */
		void Brail(FBoatControls& Controls, bool bDown);
		/** The helm at the wheel's pace toward a share of hard over (+ = bow to starboard). */
		void HelmToward(const FBoatModel& Boat, FBoatControls& Controls, double Target, double Dt);
		/** The helm steering for a true wind angle (deg, signed) at the wheel's pace. */
		void SteerFor(const FBoatModel& Boat, FBoatControls& Controls, double TwaDeg, double Dt);

		EShipManoeuvre Current = EShipManoeuvre::None;
		EShipManoeuvreStep StepNow = EShipManoeuvreStep::Idle;
		double FromSide = 1.0;   // the tack she started on (+ wind from starboard)
		double Time = 0.0;
		double StepTime = 0.0;
		double Ordered = 0.0;    // wearing: the course ordered (true wind angle, deg, on the old side's sense)
		double Helm = 0.0;       // the wheel as the helmsman holds it
		double HeldBrace[kMaxMasts] = { 0, 0, 0 }; // tacking: the yards as they were when the helm went over
		ESailSet HeldSet[kMaxSquareSails] = {}; // tacking: the square sails as they were before "rise tacks and sheets"
		bool bCoursesRisen = false;
		bool bSpankerBrailed = false; // the spanker is brailed up by an order
		bool bRestorePending = false; // a new order (or None): put the courses and spanker back at the next update
		bool bWayOn = false;     // tacking: way on again after "let go and haul"
		double SpeedBefore = 0.0; // her speed through the water when the manoeuvre started (m/s)
		FAutopilot Pilot;        // the helmsman when the order is a course
	};
}
