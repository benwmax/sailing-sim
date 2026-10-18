#pragma once

#include "CoreMinimal.h"
#include "SailSession.h"
#include "SailingSettings.h"

class FJsonObject;

/**
 * The versioned save file (docs/save/README.md): one JSON file per profile, Saved/SaveGames/profile.json. Every
 * reference in it is a string id (world, launch spot, boat, drill, weather preset, enum names), never an index, so a
 * new boat, spot or drill never shifts what an old save means. Plain logic: no world, so the tests round-trip it.
 *
 * Version 0 is the data before this file existed (GameUserSettings.ini: USailingSettings and USailSessionSave with
 * their indices); version 1 is the first file. A reader of an older version migrates it forward one step at a time
 * (Migrate); a newer version is refused (the game runs on its defaults and never writes over that file). Fields the
 * game does not know are kept and written back as they were.
 */
struct SAILINGSIM_API FSailSave
{
	static constexpr int32 CurrentVersion = 1;
	/** A spot id the game no longer has falls back to the spot nearest the saved lat/lon within this (metres); beyond
	 *  it, the world's first spot. Spots are 800 m apart or more, so a spot moved in a rebake still matches. */
	static constexpr double SpotSnapMeters = 500.0;

	/** The player's choices from the Settings screen and the next start (USailingSettings). */
	struct FSettings
	{
		ESailingQuality Quality = ESailingQuality::Medium;
		ESailingDifficulty Difficulty = ESailingDifficulty::Easy;
		ESailingControlLayout ControlLayout = ESailingControlLayout::Simple;
		bool bLearningMode = true;
		bool bTrimAssist = true;
		bool bShowHud = true;
		float Volume = 0.8f;
		int32 ResolutionScale = 0;
		int32 FrameCap = 0;
		bool bCinematicLook = false;
		int32 HudScale = 100;
		int32 TextScale = 100;
		FString SpeedUnits = TEXT("kn");     // kn, mph, kmh
		FString DepthUnits = TEXT("ft");     // ft, m, fathoms
		bool bHeadingsTrue = false;
		bool bAutoStart = false;
		bool bPauseOnFocusLoss = false;
		// The next start.
		FString WorldId = TEXT("ray-hubbard");
		FString SpotId;                      // empty: the world's first spot
		/** The spot on the earth (docs/geo-anchor): where the id is gone (renamed or removed in a rebake), the spot
		 *  nearest this within FSailSave::SpotSnapMeters. Optional in version 1: a file without it reads as before. */
		bool bHasSpotAt = false;
		double SpotLat = 0.0, SpotLon = 0.0;
		FString BoatId = TEXT("J22");
		FString WeatherId = TEXT("AfternoonBreeze");
		float StartHour = 15.f;
		int32 Traffic = 1;
		int32 WeatherSeed = 2027;
		bool bGaugeLakeLevel = false;
		/** Career (docs/career): every world and boat open whatever certificates are held. Optional in version 1. */
		bool bOpenEverything = false;
		/** Key bindings stay in Input.ini (USailingInputSettings); the save names where they are. */
		FString InputBindings = TEXT("Input.ini");
	};

	/** The last session, for Continue (USailSessionSave::Last). */
	struct FSession
	{
		FString WorldId = TEXT("ray-hubbard");
		FString SpotId;
		/** Where the last session started (its launch spot) on the earth: the fallback for SpotId, as in FSettings.
		 *  Continue starts there; a session saved mid-sail would add its own position beside it. */
		bool bHasSpotAt = false;
		double SpotLat = 0.0, SpotLon = 0.0;
		FString BoatId = TEXT("J22");
		FString ModeId = TEXT("Free");
		FString DrillId = TEXT("LeaveTheDock");
		bool bLearningMode = true;
		bool bEasy = true;
		bool bLearningTips = true;
		int32 Traffic = 1;
		FDateTime SavedAt;                   // UTC (the session's own is local)
		// Conditions.
		FString PresetId = TEXT("Lesson");
		FString SkyId = TEXT("Fair");
		float WindFromDeg = 180.f, WindKn = 10.f, GustKn = 13.f, LocalHour = 10.f, AirTempF = 74.f, LakeLevelFt = 0.f;
		int32 Month = 4, Day = 18;
		FString RealDay;
	};

	/** A career lesson (docs/career): its best medal and time, and its quiz. Medal is a string id (bronze, silver, gold). */
	struct FLessonRecord
	{
		FString Id;
		FString Medal;                       // empty: none yet
		bool bMedalEasy = false;             // that medal was earned on Easy (capped: career.json's easy_max_medal)
		double BestSeconds = 0.0;            // the fastest run that earned a medal
		int32 Runs = 0;
		bool bQuizPassed = false;
		int32 QuizBest = 0, QuizOf = 0;
	};
	/** A tier's checkride: its written quiz's best score. */
	struct FCheckrideRecord
	{
		FString Id;
		bool bPassed = false;
		int32 QuizBest = 0, QuizOf = 0;
	};
	struct FCertificateRecord
	{
		FString Id;
		FDateTime EarnedAt;                  // UTC
	};

	/** Progress: drills passed, the career's lessons, checkrides and certificates, races, the logbook's totals. The
	 *  career fields were added in version 1 without a version change (a missing field reads as empty). */
	struct FProgress
	{
		TArray<FString> DrillsPassed;        // drill ids
		TArray<FLessonRecord> Lessons;       // by lesson id (career.json)
		TArray<FCheckrideRecord> Checkrides; // by checkride id
		TArray<FCertificateRecord> Certificates;
		FLessonRecord* FindLesson(const FString& Id) { return Lessons.FindByPredicate([&Id](const FLessonRecord& L) { return L.Id == Id; }); }
		const FLessonRecord* FindLesson(const FString& Id) const { return Lessons.FindByPredicate([&Id](const FLessonRecord& L) { return L.Id == Id; }); }
		FCheckrideRecord* FindCheckride(const FString& Id) { return Checkrides.FindByPredicate([&Id](const FCheckrideRecord& C) { return C.Id == Id; }); }
		const FCheckrideRecord* FindCheckride(const FString& Id) const { return Checkrides.FindByPredicate([&Id](const FCheckrideRecord& C) { return C.Id == Id; }); }
		bool HasCertificate(const FString& Id) const { return Certificates.ContainsByPredicate([&Id](const FCertificateRecord& C) { return C.Id == Id; }); }
		int32 RacesSailed = 0;
		int32 RacesWon = 0;
		int32 LogbookSessions = 0;
		int32 LogbookEntries = 0;
		double LogbookMiles = 0.0;
		double HoursSailed = 0.0;
	};

	int32 Version = CurrentVersion;
	FDateTime WrittenAt;
	FSettings Settings;
	bool bHasLast = false;
	FSession Last;
	FProgress Progress;
	/** The file as it was read (after migration): fields this version doesn't know are written back from it. */
	TSharedPtr<FJsonObject> Raw;

	enum class EResult : uint8 { Ok, Migrated, Refused, Invalid };
	/** Reads a save's JSON text. Refused: a newer version than this game (the save is left at its defaults). */
	static EResult FromJson(const FString& Text, FSailSave& Out, FString* OutMessage = nullptr);
	FString ToJson() const;
	/** One forward step at a time from From to CurrentVersion, on the JSON itself. False if a step is missing. */
	static bool Migrate(FJsonObject& Root, int32 From);

	/** Takes the game's state: the settings and the last session (ids from the catalogue), drills passed. */
	void Capture(const USailingSettings& InSettings, const USailSessionSave& InSession);
	/** Puts the save into the game's objects (unknown ids fall back to the defaults, with a log line). */
	void Apply(USailingSettings& OutSettings, USailSessionSave& OutSession) const;

	/** Writes the text next to the path and renames it over (no partial file, the old one kept if it fails). */
	static bool WriteAtomic(const FString& Path, const FString& Text);

	// Ids. A world id for the settings world (0 lake, 1 Galveston Bay, 2 the Gulf passage).
	static FString WorldId(int32 World);
	static int32 WorldIndex(const FString& Id);   // -1 if unknown
	static FString BoatId(int32 Boat);
	static int32 BoatIndex(const FString& Id);
	/** The drill id of a session's drill index (ESailingDrill - 1). */
	static FString DrillId(int32 DrillIndex);
	static int32 DrillIndex(const FString& Id);
	/** A settings world's launch spot index for a saved spot: by id, else by lat/lon (rule 6), else 0. */
	static int32 SpotIndex(int32 World, const FString& Id, bool bHasAt, double Lat, double Lon);
};

/**
 * Where the game keeps its save: loaded once when the game instance starts, written whenever the settings or the
 * session are saved. Bench, capture, shot, demo, drill and automation runs never write it (USailingSettings::
 * IgnoresSavedChoices) and only read it when -SailingSave=<path> names one.
 */
namespace SailSaveStore
{
	/** -SailingSave=<path>, or Saved/SaveGames/profile.json. */
	SAILINGSIM_API FString Path();
	/** Reads the save into the settings and the session (or migrates GameUserSettings.ini into a new one). */
	SAILINGSIM_API void LoadOnce();
	/** Writes the settings and the session to the save. */
	SAILINGSIM_API void Commit();
	/** What the load did, for the log and the UI script's Log key. */
	SAILINGSIM_API FString Status();
	/** The save's progress, which the career (Career.h) and the session totals edit in place; Commit writes it. */
	SAILINGSIM_API FSailSave::FProgress& Progress();
}
