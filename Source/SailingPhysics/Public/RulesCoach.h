#pragma once

#include "SailingPhysicsApi.h"
#include "Rules.h"
#include "Traffic.h"
#include <string>
#include <vector>

namespace Sailing
{
	/**
	 * Watches the player's encounters with other vessels and judges them the way an instructor would: as the give-way
	 * vessel, did you keep well clear and act early and obviously (Rules 8 and 16)? As the stand-on vessel, did you hold
	 * your course and speed (Rule 17(a))? It also writes the learning-mode callout for the most pressing encounter:
	 * who she is, where, your role, the rule, and what to do.
	 */
	class SAILINGPHYSICS_API FRulesCoach
	{
	public:
		struct FScore
		{
			double Time = 0.0;
			int Points = 0;
			std::string Text;
		};

		struct FAdvice
		{
			bool bActive = false;
			int Other = -1;
			bool bGiveWay = false, bStandOn = false;
			double Range = 0.0, Cpa = 0.0, Tcpa = 0.0;
			std::string Who;      // "Runabout (power-driven vessel) on your starboard bow, 240 m"
			std::string Role;     // "You give way" / "You stand on" / "Both alter to starboard"
			std::string Rule;     // "Rule 12(a)(i)"
			std::string Reason;
			std::string Action;   // what to do now
			// Graphics G7: what the learning tips key on.
			EEncounter Encounter = EEncounter::None;
			EVesselStatus PlayerStatus = EVesselStatus::Sailing, OtherStatus = EVesselStatus::PowerDriven;
			int PlayerTack = 0, OtherTack = 0;
			bool bRisk = false;
		};

		void Update(double Now, const FVesselSnapshot& Player, const FTrafficSim& Sim);

		int GetScore() const { return Score; }
		const std::vector<FScore>& GetScores() const { return Scores; }
		const FAdvice& GetAdvice() const { return Advice; }
		int OpenEncounters() const { return int(Open.size()); }

		/** "on your starboard bow", "dead ahead", "abeam to port"... from a relative bearing in radians. */
		static std::string RelativePosition(double RelativeBearing);

	private:
		struct FEncounter
		{
			int Other = -1;
			bool bGiveWay = false, bBoth = false;
			std::string Rule, OtherName;
			double StartHeading = 0.0, StartSpeed = 0.0, Safe = 40.0;
			double MinRange = 1e9;
			double MaxTurnEarly = 0.0;   // largest alteration while still well apart (over 1.5 x the passing distance)
			double MaxSlowEarly = 0.0;
			double MaxTurnStandOn = 0.0; // largest alteration while not yet at close quarters
			bool bCollided = false;
			bool bOtherActed = false;    // the other vessel had to take Rule 17(b) action for the player
		};

		void Close(const FEncounter& E, double Now);

		std::vector<FEncounter> Open;
		std::vector<FScore> Scores;
		int Score = 0;
		double LastEventTime = -1.0;
		FAdvice Advice;
	};
}
