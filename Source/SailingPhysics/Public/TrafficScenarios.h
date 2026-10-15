#pragma once

#include "SailingPhysicsApi.h"
#include <string>
#include <vector>

namespace Sailing
{
	/** The outcome of one Navigation Rules scenario (two vessels set on a collision course, or a busy stretch of water). */
	struct SAILINGPHYSICS_API FRulesScenarioResult
	{
		std::string Name;
		std::string Rule;              // the rule the scenario exercises
		bool bConflict = false;        // with every helmsman ignoring the rules they would collide or nearly so
		double MinRangeNoRules = 0.0;  // m, closest approach then
		double MinRange = 0.0;         // m, closest approach following the rules
		double Safe = 0.0;             // m, the passing distance the AI aims for
		double GiveWayTurnDeg = 0.0;   // largest alteration by the vessel(s) required to give way
		double GiveWaySlowdown = 0.0;  // largest fraction of speed taken off by them
		double StandOnTurnDeg = 0.0;   // largest alteration by the stand-on vessel before the closest approach
		int Collisions = 0;
		int AiCausedCollisions = 0;    // collisions where an AI vessel was required to keep clear
		std::vector<std::string> Signals;
		std::vector<std::string> Events;
		bool bPassed = false;
		std::string Failure;           // why not, in words
	};

	/** The scenarios, by index: 0 .. RulesScenarioCount() - 1. */
	SAILINGPHYSICS_API int RulesScenarioCount();
	SAILINGPHYSICS_API FRulesScenarioResult RunRulesScenario(int Index);

	/** An AI fleet race: who started, rounded and finished, the scores, and any collisions. */
	struct SAILINGPHYSICS_API FRaceScenarioResult
	{
		struct FBoat { std::string Name; int Place = 0; int Points = 0; std::string Status; double FinishSeconds = 0.0; int MarksRounded = 0; bool bOcsAtStart = false; };
		std::vector<FBoat> Boats;
		std::vector<std::string> Signals;
		int Collisions = 0;
		int AiCausedCollisions = 0;
		int Tacks = 0;                 // tacks and gybes by the whole fleet
		double RaceSeconds = 0.0;
		bool bOver = false;
	};

	/** Boats J/22s race a windward-leeward course (BeatMeters, Laps) in 12 knots, starting from a minute before the gun.
	 *  W1: bShifty gives them an afternoon breeze's puffs and shifts (the station calibration for July at 15:00). */
	SAILINGPHYSICS_API FRaceScenarioResult RunAiRace(int Boats, int Laps, double BeatMeters, unsigned Seed = 3, bool bShifty = false);
}
