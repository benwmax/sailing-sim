#pragma once

#include "SailingPhysicsApi.h"
#include "Rules.h"
#include <string>
#include <vector>

namespace Sailing
{
	/** A mark of the course, rounded to port unless said otherwise. */
	struct SAILINGPHYSICS_API FRaceMark
	{
		double X = 0.0, Y = 0.0;
		bool bToPort = true;
		std::string Name;
	};

	/**
	 * A windward-leeward course: a start line square to the wind with the committee boat at its starboard end and a
	 * pin buoy at the port end; a windward mark up the wind, a leeward mark just below the line; laps of
	 * windward-leeward, then a finish upwind through the start line.
	 */
	struct SAILINGPHYSICS_API FRaceCourse
	{
		double CommitteeX = 0.0, CommitteeY = 0.0;   // starboard end of the line (looking upwind)
		double PinX = 0.0, PinY = 0.0;               // port end
		double WindFromRad = 0.0;
		std::vector<FRaceMark> Marks;

		static FRaceCourse WindwardLeeward(double LineX, double LineY, double WindFromRad, double BeatLength, double LineLength, int Laps);
		/** Signed distance of a point from the line along the wind: + on the course side (upwind), - on the pre-start side. */
		double CourseSide(double X, double Y) const;
		/** Where along the line a point is: 0 at the pin, 1 at the committee boat. */
		double AlongLine(double X, double Y) const;
		double LineLength() const;
	};

	/** One boat in the race. */
	struct SAILINGPHYSICS_API FRaceEntry
	{
		int VesselId = 0;
		std::string Name;
		int NextMark = 0;          // index of the mark to round next; == Marks.size(): sailing to the finish
		double Sweep = 0.0;        // radians swept around the next mark inside its zone (- = counterclockwise seen from above)
		double PrevBearing = 0.0;
		bool bInZone = false;
		bool bStarted = false;
		bool bOcs = false;         // over the line early at the start signal: must return to the pre-start side
		bool bFinished = false;
		double FinishTime = 0.0;
		int Place = 0;
		int Points = 0;
		std::string Status;        // "", "OCS" (never came back), "DNF"
		double PrevSide = 0.0, PrevX = 0.0, PrevY = 0.0;
		bool bHavePrev = false;
		// The AI racer's own plan.
		bool bAimPassed = false;
		double StartTarget = 0.5;  // where along the line she aims to start
	};

	/**
	 * Runs a race: the start sequence of the Racing Rules of Sailing (rule 26: warning at 5 minutes, preparatory at 4,
	 * one minute, start), on-course-side boats at the start (rule 29.1: individual recall, they must come back), mark
	 * rounding (each mark left on the required side, checked by the angle swept around it), the finish, and scoring
	 * by the low-point system (Appendix A: first 1 point, second 2...; OCS, DNF and DNS score the number of entries
	 * plus one).
	 */
	struct SAILINGPHYSICS_API FRaceRunner
	{
		static constexpr double SequenceSeconds = 300.0;
		static constexpr double ZoneRadius = 100.0;      // m around a mark where rounding is counted
		static constexpr double RoundingSweep = 2.6;     // rad (about 150 degrees) swept the right way round

		enum class EPhase : uint8_t { NotStarted, Warning, Preparatory, OneMinute, Racing, Finished };

		FRaceCourse Course;
		std::vector<FRaceEntry> Entries;
		double SequenceStart = 0.0;
		bool bBegun = false;
		double TimeLimit = 3600.0;   // after the start; boats still racing then are DNF
		std::vector<std::pair<double, std::string>> Signals; // the committee's signals as they are made

		int AddEntry(int VesselId, const std::string& Name);
		/** Starts the sequence with SecondsToStart left (300 for the full five minutes). */
		void Begin(double Now, double SecondsToStart = SequenceSeconds);
		double StartTime() const { return SequenceStart + SequenceSeconds; }
		EPhase Phase(double Now) const;
		/** Follows every boat: Snapshot(Id) gives where each is. */
		void Update(double Now, const std::vector<FVesselSnapshot>& Boats);
		bool IsOver() const { return bOver; }
		FRaceEntry* FindEntry(int VesselId);
		const FRaceEntry* FindEntry(int VesselId) const;
		/** The next thing an entry must do, in words ("Round Windward 1 to port", "Return: you were over early"). */
		std::string NextTask(const FRaceEntry& Entry) const;

		/** The AI racer's course to steer now, and whether to slow (luff and ease) to avoid being early at the line. */
		struct FTactic { double Heading = 0.0; bool bSlow = false; };
		FTactic Tactic(FRaceEntry& Entry, const FVesselSnapshot& Boat, double Now, double SpeedEstimate) const;

	private:
		void Score(double Now);
		void Signal(double Time, const std::string& Text);
		int SignalsMade = 0;
		bool bStartChecked = false;
		bool bOver = false;
	};
}
