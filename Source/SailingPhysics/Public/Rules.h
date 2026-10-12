#pragma once

#include "SailingPhysicsApi.h"
#include <cstdint>
#include <string>

namespace Sailing
{
	/**
	 * What a vessel is, as the Navigation Rules (COLREGS / U.S. Inland Rules) see it. The order is Rule 18's: a vessel
	 * keeps out of the way of those above it.
	 */
	enum class EVesselStatus : uint8_t
	{
		Anchored,                  // not underway (the race committee boat): everyone keeps clear (Rules 2 and 8)
		NotUnderCommand,           // Rule 18: everyone keeps clear
		RestrictedManeuverability, // a tug with a tow she cannot leave, a dredge, a buoy tender at work
		ConstrainedByDraft,        // a deep ship that can only use the channel (sail and small craft must not impede: Rule 9)
		Fishing,                   // trawling or with gear out, not a sportfisherman trolling
		Sailing,                   // under sail alone (an engine running makes her power-driven: Rule 3(c), 25(e))
		PowerDriven,
	};

	SAILINGPHYSICS_API const char* VesselStatusName(EVesselStatus Status);

	/** Rule 18 rank: lower keeps clear of nothing above it; a vessel keeps out of the way of any vessel with a lower rank. */
	SAILINGPHYSICS_API int StatusRank(EVesselStatus Status);

	/** One vessel as the rules see her at a moment. Map frame: X north, Y east; headings are compass radians. */
	struct SAILINGPHYSICS_API FVesselSnapshot
	{
		int Id = 0;
		double X = 0.0, Y = 0.0;
		double VX = 0.0, VY = 0.0;  // over the ground
		double Heading = 0.0;       // where the bow points (0 = north, + = clockwise)
		double Length = 7.0;
		EVesselStatus Status = EVesselStatus::PowerDriven;
		int Tack = 0;               // under sail: +1 starboard tack (wind over the starboard side), -1 port tack
		const char* Name = "";

		double Speed() const;
	};

	/** Risk of collision (Rule 7) by the closest point of approach on present courses and speeds. */
	struct SAILINGPHYSICS_API FCollisionRisk
	{
		double Range = 0.0;         // m now
		double Cpa = 0.0;           // m at the closest point of approach
		double Tcpa = 0.0;          // s to it (negative: already past)
		double RelativeBearing = 0.0; // of B from A's bow, radians (+ = to starboard)
		bool bRisk = false;
	};

	/** Distance two vessels should keep: about two and a half combined lengths, at least 40 m, at most 400 m. */
	SAILINGPHYSICS_API double SafePassingDistance(const FVesselSnapshot& A, const FVesselSnapshot& B);

	SAILINGPHYSICS_API FCollisionRisk AssessRisk(const FVesselSnapshot& A, const FVesselSnapshot& B, double SafeDistance, double HorizonSeconds = 480.0);

	/** Which rule governs two vessels meeting. */
	enum class EEncounter : uint8_t { None, Overtaking, Responsibilities, SailingVessels, HeadOn, Crossing };

	SAILINGPHYSICS_API const char* EncounterName(EEncounter Encounter);

	/** The rule's answer: who keeps out of the way, under which rule, and why, in plain words. */
	struct SAILINGPHYSICS_API FRuleDecision
	{
		static constexpr int Both = -2;   // head-on: each alters to starboard
		EEncounter Encounter = EEncounter::None;
		int GiveWayId = -1;               // the give-way vessel's Id, Both, or -1 when neither
		int StandOnId = -1;
		const char* Rule = "";
		std::string Reason;

		bool IsGiveWay(int Id) const { return GiveWayId == Id || GiveWayId == Both; }
	};

	/**
	 * Right of way between two vessels in sight of one another, in the order the rules apply: overtaking (Rule 13)
	 * first whatever the vessels are; then Rule 18's responsibilities between different kinds; then Rule 12 between
	 * sailing vessels (port tack keeps clear of starboard; on the same tack the windward boat keeps clear); then
	 * Rule 14 (head-on: both alter to starboard) and Rule 15 (crossing: the vessel with the other on her starboard
	 * side keeps clear) between power-driven vessels. WindFromRad is where the true wind blows from.
	 */
	SAILINGPHYSICS_API FRuleDecision DecideRightOfWay(const FVesselSnapshot& A, const FVesselSnapshot& B, double WindFromRad);

	/** Maneuvering and warning signals (Rule 34), sounded by power-driven vessels in sight of one another. */
	enum class ESoundSignal : uint8_t
	{
		None,
		OneShort,    // I am altering my course to starboard
		TwoShort,    // I am altering my course to port
		ThreeShort,  // I am operating astern propulsion
		FiveShort,   // I do not understand your intentions / I doubt you are taking enough action
	};

	SAILINGPHYSICS_API const char* SoundSignalMeaning(ESoundSignal Signal);
	SAILINGPHYSICS_API int SoundSignalBlasts(ESoundSignal Signal);
}
