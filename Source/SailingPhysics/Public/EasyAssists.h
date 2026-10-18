#pragma once

#include "SailingPhysicsApi.h"
#include "BoatModel.h"
#include "AutoTrim.h"

namespace Sailing
{
	/**
	 * Easy mode (docs/easy-mode/README.md): one switch that implies this set of assists, each a plain number. The sim
	 * applies them through the boat's config (ApplyTo), the trim's settings (ApplyTo) and FEasyHelm; nothing here reads a
	 * setting or a player. Off (the default, and Realistic) every knob is the boat's own and nothing changes: polars,
	 * reference checks, benches and traffic never turn it on.
	 */
	struct SAILINGPHYSICS_API FEasyAssists
	{
		bool bEnabled = false;

		// Forgiving helm.
		// The helm holds the tiller where it is put: no weather helm pulling it to leeward (600 N m/rad on the J/22's
		// tiller is a light hand; 1e5 is a locked one).
		double HelmStiffness = 1.0e5;
		// Roll damping per tonne of boat (N m s): about 2.4 kN m s on the J/22, so a puff heels her over a couple of
		// seconds instead of one. Kept from the old easy difficulty.
		double RollDampingPerTonne = 2376.0;
		// The heel-induced yaw toward the wind (FBoatConfig::HeelYawCoef) at 40%: she still carries weather helm when she
		// heels (the lesson), but it no longer swings her head to wind in a puff faster than a beginner can answer.
		double HeelYawScale = 0.4;
		// Yaw damping at twice the boat's own: a round-up starts slower, a turn the tiller asks for still comes (the
		// rudder's moment on the J/22 at 5 kn is about 50 times this damping's at a tack's turn rate).
		double YawDampingScale = 2.0;

		// No capsize. A righting assist starts HeelCapSoftDeg short of the cap and grows with the square of the heel past
		// that, reaching CapLeverM times the boat's weight at the cap (2 m of righting arm: several times the J/22's own at
		// any heel; 1 m let the light Hobie past her cap by 9 deg in a 30% gusty 22 kn), so a puff that would lay her over
		// stops at the cap. The cap is HeelCapPerTrimLimit times the heel the crew depowers at (FBoatConfig::
		// TrimHeelLimitDeg), at most HeelCapMaxDeg: J/22 24.7 deg (her rail touches at about 30), the dinghies 15, the Hobie
		// 20 (a hull flies at about 10), the Lagoon 8, the Catalinas 25.
		double HeelCapPerTrimLimit = 1.9;
		double HeelCapMaxDeg = 25.0;
		double HeelCapSoftDeg = 6.0;
		double CapLeverM = 2.0;

		// Stronger auto-trim: always on, with the sheets moving 1.5 times as fast, depowering at 85% of the crew's usual
		// heel (J/22 11 deg instead of 13) and easing in a puff like a dinghy sailor does (FAutoTrimSettings::bEasePuffs).
		double TrimRateScale = 1.5;
		double TrimHeelScale = 0.85;
		bool bEasePuffs = true;
		// The assist trims again this soon after the player touches a sheet (the Realistic assist waits for the setting's
		// idle time, or never when it is off).
		double TrimIdleSeconds = 4.0;

		// Wider no-go cue: the HUD draws the no-go zone this many degrees either side of the true wind (the boat's own
		// edge is 35, where FBoatModel calls her in irons), and warns from WarnMarginDeg outside it.
		double NoGoCueDeg = 45.0;
		double NoGoWarnMarginDeg = 10.0;

		// Irons recovery: stuck (inside the no-go cue under StuckKnots) for IronsHelpSeconds, the crew backs the jib, lets the
		// main run and steers the bow off toward the tack she was nearer, until she is RecoveredTWADeg off the wind. Head to
		// wind with no way on a J/22 in 10 kn is sailing again (1.5 kn, 50 deg off) about 17 s after the start.
		double IronsHelpSeconds = 3.0;
		double StuckKnots = 1.0;
		double RecoveryTiller = 1.0;    // hard over: she turns on the backed jib and the rudder going astern
		double RecoveryJibSheet = 0.5;  // held half out (hard in it pushed the bow off half as fast: 19 s against 12)
		double RecoveredTWADeg = 60.0;

		// The bear-away guard: with the tiller let go (inside GuardDeadband of centre) inside the no-go cue and way on, the
		// crew bears her off toward the cue's edge with up to GuardTiller (9 deg of rudder on the J/22). A beginner who
		// lets go after a tack, or pinches, sails off at 45 instead of luffing into irons.
		double GuardTiller = 0.3;
		double GuardDeadband = 0.15;

		// The wind's gusts, puffs and shifts at half strength (the game mode applies it to the weather; kept from the
		// old easy difficulty).
		double WindVariabilityScale = 0.5;

		/** The assists for a boat, on or off. */
		static FEasyAssists For(const FBoatConfig& Config, bool bOn);

		/** The heel cap for this boat (deg), 0 when off. */
		double HeelCapDegFor(const FBoatConfig& Config) const;
		/** The half-angle of the no-go cue (deg) and the warning's edge outside it. */
		double NoGoDeg() const { return bEnabled ? NoGoCueDeg : kRealisticNoGoDeg; }
		double NoGoWarnDeg() const { return NoGoDeg() + (bEnabled ? NoGoWarnMarginDeg : 0.0); }

		/** Sets the helm, damping and heel-cap knobs on a boat's config: the assisted values, or the boat's own
		 *  (FBoatConfig::Make) when off. Other fields are left alone (reefs, crew weight). */
		void ApplyTo(FBoatConfig& Config, double TotalMassKg) const;
		/** The trim's settings: the assisted ones, or the defaults when off. */
		void ApplyTo(FAutoTrimSettings& Settings) const;

		/** The edge FBoatModel uses for bInIrons (and the Realistic no-go cue). */
		static constexpr double kRealisticNoGoDeg = 35.0;
	};

	/** Where the bow is against the no-go cue: clear, close to it (the early warning), or inside. */
	enum class ENoGoCue : unsigned char { Clear, Near, Inside };
	SAILINGPHYSICS_API ENoGoCue NoGoCueFor(const FBoatTelemetry& T, const FEasyAssists& Assists);

	/**
	 * Easy mode's crew help on the helm, after the trim and the player's tiller: the irons recovery. Works on a copy of
	 * the controls the boat steps with, so the player's own tiller and sheets are where they left them afterwards.
	 */
	class SAILINGPHYSICS_API FEasyHelm
	{
	public:
		FBoatControls Update(const FBoatModel& Boat, const FBoatControls& Controls, const FEasyAssists& Assists, double Dt);
		bool IsRecovering() const { return Side != 0; }
		void Reset() { StuckTime = 0.0; Side = 0; }

	private:
		double StuckTime = 0.0;
		int Side = 0; // the tack she is falling off onto (+1 wind from starboard), 0 when not recovering
	};

	/** The Easy mode checks (SailingSim.Physics.EasyMode, scripts/polar.sh --easy). */
	struct FEasyReachResult
	{
		double MaxHeelDeg = 0.0;      // toward leeward
		double MaxCourseErrorDeg = 0.0; // heading off the course (the TWA held in the mean wind) after the first 20 s
		double MeanSpeedKnots = 0.0;
		double HeelCapDeg = 0.0;
		bool bCapsized = false;
	};
	/** Steers the course at TwaDeg in the mean wind with the autopilot (a steady helm) and the trim assist, in a gusty
	 *  breeze for Seconds. */
	SAILINGPHYSICS_API FEasyReachResult RunEasyReach(EBoatType Type, bool bEasy, double TrueWindKnots, double TwaDeg, double Seconds,
		double GustIntensity = 0.2);

	struct FEasyIronsResult
	{
		double FilledSeconds = -1.0;  // until she is off the wind and moving (|TWA| past 50, 1.5 kn ahead); -1 never
		double FinalTwaDeg = 0.0;
		double FinalSpeedKnots = 0.0;
	};
	/** Head to wind with no way on, the player's tiller centred and the sheets left alone (trim assist as the mode has it). */
	SAILINGPHYSICS_API FEasyIronsResult RunEasyIrons(EBoatType Type, bool bEasy, double TrueWindKnots, double Seconds);

	struct FEasyTackResult
	{
		bool bTacked = false;         // on the new tack, off the wind and moving 30 s after the helm went over
		double MaxHeelDeg = 0.0;
		double FinalTwaDeg = 0.0;
		double FinalSpeedKnots = 0.0;
	};
	/** Close-hauled, then a beginner's tack: the tiller hard over for HoldSeconds, then let go (centred). */
	SAILINGPHYSICS_API FEasyTackResult RunEasyTack(EBoatType Type, bool bEasy, double TrueWindKnots, double HoldSeconds = 4.0);
}
