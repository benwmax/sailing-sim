#pragma once

#include "SailingPhysicsApi.h"
#include "AutoTrim.h"
#include "BoatModel.h"
#include <string>

namespace Sailing
{
	/**
	 * Prologue step 2 (docs/prologue/README.md): crew-station control mode. On a big boat the player is one of the crew
	 * and works one station at a time; the rest of the crew hold everything else. FStationControls merges the player's
	 * hands at their station with the crew's held controls into one FBoatControls every physics step, so a player at the
	 * jib cannot steer and a player at the helm cannot touch a sheet. Plain logic on the sim clock (online rule 1): the
	 * game hands it the player's input as FStationInput and steps the boat with what it returns.
	 *
	 * Stations: the helm (a wheel: the tiller input turns it at the boat's own rate and it stays where it is put), the
	 * jib trimmer (ease the jib sheet; trimming in is grinding, rate limited against the sheet's load, and on a tack the
	 * old sheet is let go so the new one has to be ground in) and the main trimmer (mainsheet, traveller, and the
	 * traveller dump: the car to leeward in one go). None is normal sailing: the player holds every control.
	 */
	enum class ECrewStation : unsigned char { None, Helm, JibTrimmer, MainTrimmer, Count };

	/** The controls a station's hands work (and that a scene can ask for by name: "wheel", "grinder", ...). */
	enum class EStationControl : unsigned char { Wheel, JibSheet, Grinder, MainSheet, Traveller, TravellerDump, Count };

	/** "helm", "jib-trimmer", "main-trimmer" ("" for None). */
	SAILINGPHYSICS_API const char* CrewStationName(ECrewStation S);
	/** The station of that name; Count if none. */
	SAILINGPHYSICS_API ECrewStation CrewStationFromName(const std::string& Name);
	/** The next station in the order helm, jib trimmer, main trimmer (the station key's cycle). */
	SAILINGPHYSICS_API ECrewStation NextCrewStation(ECrewStation S);
	/** "wheel", "jib-sheet", "grinder", "main-sheet", "traveller", "traveller-dump". */
	SAILINGPHYSICS_API const char* StationControlName(EStationControl C);
	/** The control of that name; Count if none. */
	SAILINGPHYSICS_API EStationControl StationControlFromName(const std::string& Name);
	/** Whether a station's hands work that control (None works them all). */
	SAILINGPHYSICS_API bool StationOwns(ECrewStation S, EStationControl C);
	/** One bit per control (for FStationControls::TakeWorked and FSceneInput::Worked). */
	inline unsigned StationControlBit(EStationControl C) { return 1u << unsigned(C); }

	/** The station's hardware for a boat: the wheel, the jib sheet and its winch, a sheet's rates. */
	struct SAILINGPHYSICS_API FStationConfig
	{
		/** The wheel turns the rudder from amidships to hard over (Tiller 0 to 1) in this long with the key held. */
		double WheelHardOverSeconds = 0.9;
		/** Jib sheet let out from hard in (JibSheet 0) to fully eased (1), m. The J/22's clew sweeps about 3 m. */
		double JibSheetTravelM = 3.0;
		/** Sheet tension per newton of the jib's net sail force. The clew holds the leech and foot, whose membrane tension
		 *  is larger than the net force on a flat-ish sail: Harken's sizing rule (load lb = 0.00431 x area ft^2 x AWS kn^2,
		 *  2400 N for the J/22's jib at 30 kn apparent) is about 1.6 times the jib force the model gives there. */
		double SheetLoadShare = 1.6;
		/** One grinder flat out, W at the handle (a sprint a fit sailor holds for 10-20 s), and the winch's efficiency. */
		double GrinderPowerW = 300.0;
		double WinchEfficiency = 0.8;
		/** Line speed in top gear with no load, m/s (handle speed times drum over gear). */
		double MaxLineSpeedMs = 0.6;
		/** A tap of the grind key: this long of grinding (about half a turn of the handle). */
		double GrindTapSeconds = 0.35;
		/** Sheets eased round the winch or the cleat, fraction of the travel per second. */
		double EaseRate = 0.5;
		/** The mainsheet and traveller at the main trimmer's hands, per second (the pawn's own rates). */
		double MainSheetRate = 0.35;
		double TravellerRate = 0.8;
		/** The rest of the crew grind flat out too (they are the same people). */
		double CrewGrindEffort = 1.0;
		/** The crew's heavy-air tack while the player steers (the jib let fly and the main hard in, then the jib aback and the
		 *  main eased): the J/22 stand-in needs it in 25 kn; the maxi tacks on her helm and trim and only stalls with it. */
		bool bTackHelp = true;

		/** The station hardware of this boat: the maxi's pedestal and primaries, the J/22 stand-in's for the rest, and the
		 *  boat's own wheel rate where she has a wheel. */
		static FStationConfig For(const FBoatConfig& Boat);
	};

	/** What the player's hands are doing this step at their station; what the station does not own is ignored. */
	struct FStationInput
	{
		double Wheel = 0.0;     // -1..1: turning the wheel (a rate), + turns the bow to starboard; the tiller keys or stick
		double JibSheet = 0.0;  // + eases, - trims (at the jib, trimming in is grinding)
		double Grind = 0.0;     // 0..1: the grind key held
		int GrindTaps = 0;      // grind key presses since the last step (each is GrindTapSeconds of grinding)
		double MainSheet = 0.0; // + eases, - trims
		double Traveller = 0.0; // + to leeward, - to windward
		bool bTravellerDump = false; // pressed since the last step
	};

	class SAILINGPHYSICS_API FStationControls
	{
	public:
		FStationConfig Config;
		FAutoTrim CrewTrim;     // the crew on the sheets and sail shape
		FAutopilot CrewHelm;    // the crew on the wheel (holds the course the player left)

		/** Starts station mode (or ends it with None) from the controls the boat has now. */
		void Reset(const FBoatModel& Boat, const FBoatControls& Start, ECrewStation S);
		/** The player moves to a station (the scene's order or the station key). Whoever takes over starts from where the
		 *  control is; the crew at the wheel holds the true wind angle the boat has as the player lets go. */
		void MoveTo(const FBoatModel& Boat, ECrewStation S);
		ECrewStation GetStation() const { return Station; }
		bool IsActive() const { return Station != ECrewStation::None; }

		/** One physics step: the crew's controls, the player's at their station, merged. Returns the controls to step with. */
		const FBoatControls& Step(const FBoatModel& Boat, const FStationInput& In, double Dt);
		const FBoatControls& GetControls() const { return Controls; }

		/** The controls the player works at a station from Player, everything else from Crew. */
		static FBoatControls Merge(ECrewStation S, const FBoatControls& Player, const FBoatControls& Crew);

		/** The jib sheet's tension, N: from the jib's sail force in the telemetry, else 0.5 rho AWS^2 x the jib's area. */
		double SheetLoad(const FBoatModel& Boat) const;
		/** How fast a grinder brings the sheet in against a load, m/s (Effort 0..1). */
		double GrindLineSpeed(double LoadN, double Effort) const;

		/** The controls the player worked since the last call (StationControlBit), then cleared. */
		unsigned TakeWorked() { const unsigned W = Worked; Worked = 0; return W; }
		/** Sheet the player has ground in since station mode started, m (for the HUD and the tests). */
		double GetPlayerGrindM() const { return PlayerGrindM; }
		/** The wheel's position, -1..1 (Tiller): for the HUD's wheel. */
		double GetWheel() const { return Controls.Tiller; }
		/** The crew's heavy-air tack help is under way (the jib let fly, then backed). */
		bool IsCrewTacking() const { return TackPhase != 0; }

	private:
		void Grind(double& Sheet, double Effort, double LoadN, double Dt, bool bPlayer);
		void TackHelp(const FBoatModel& Boat, FBoatControls& Crew);
		void Settle(const FBoatModel& Boat);
		static double CrewCourse(double TwaDeg);

		ECrewStation Station = ECrewStation::None;
		FBoatControls Controls;  // the merged controls (also the player's own values: they start from here)
		FBoatControls Crew;      // what the crew hold
		double TapLeft = 0.0;    // grinding left from taps, s
		unsigned Worked = 0;
		double PlayerGrindM = 0.0;
		int WindSide = 0;        // +1 wind from starboard; changes only past 10 degrees on the other side
		int TackPhase = 0;       // 0 none, 1 heading up (jib let fly, main in), 2 through (jib backed, main out)
		double TackTime = 0.0;
		double LastTwaDeg = 0.0;
		bool bCourseSet = false; // the crew's course and the wind side, from the first step with a real wind angle
	};
}
