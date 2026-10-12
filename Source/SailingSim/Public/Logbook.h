#pragma once

#include "CoreMinimal.h"

/**
 * The ship's log, kept the way a navigator keeps one: a watch entry every half hour of sailing (time, position,
 * course and speed, heading, distance run by the log, wind and sea) and an entry for anything that happens (a fix,
 * a drill, a mark rounded, a grounding, a race result, a waypoint passed). Each session is written to
 * Saved/Logbook/<date> <time> <area>.json as it goes, so a crash loses nothing.
 */
struct SAILINGSIM_API FLogEntry
{
	double UnixTime = 0.0;   // UTC seconds
	FString Clock;           // local time, "14:30"
	FString Kind;            // "Watch", "Event"
	double Latitude = 0.0, Longitude = 0.0;
	double CourseTrue = 0.0, SpeedKnots = 0.0, HeadingMagnetic = 0.0;
	double LogNm = 0.0;      // distance run through the water since the session began
	double WindFromDeg = 0.0, WindKnots = 0.0, SeaMeters = 0.0;
	FString Remarks;
};

class SAILINGSIM_API FLogbook
{
public:
	/** Starts a session's log (and its file). */
	void Begin(const FString& Area, const FString& Boat, double UnixTime, const FString& Clock);
	void Add(const FLogEntry& Entry);
	const TArray<FLogEntry>& GetEntries() const { return Entries; }
	const FString& GetArea() const { return Area; }
	const FString& GetBoat() const { return Boat; }
	FString GetFilePath() const { return FilePath; }
	/** Totals for the page header. */
	double MaxSpeedKnots = 0.0;
	double SessionStartUnix = 0.0;

	/** "29 deg 33.10' N  95 deg 01.37' W" style position, as written in a log. */
	static FString FormatPosition(double Latitude, double Longitude);

private:
	void Save() const;
	TArray<FLogEntry> Entries;
	FString Area, Boat, FilePath;
};
