#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "SailSession.generated.h"

/**
 * Graphics G4: everything the front end chooses for a session (Inputs/g4/ui-spec.md 2.3). Choosing a world sets the
 * session and reloads the one map with it; the game mode applies the rest at InitGame (the same paths the command-line
 * overrides use), so a session started from the menus and a benchmark started from arguments go the same way.
 */
UENUM(BlueprintType)
// Rain is last so the int uses of the others (SailCatalog::Expect) and old saves (string ids) keep their meaning; the
// Conditions screen shows it after Overcast (SkyRowOrder).
enum class ESailSky : uint8 { Clear, Fair, Overcast, Storms, Fog, Rain };

UENUM(BlueprintType)
enum class ESailMode : uint8 { Free, Drill, Race, Passage };

USTRUCT(BlueprintType)
struct FSailConditions
{
	GENERATED_BODY()

	UPROPERTY(config) float WindFromDeg = 180.f;   // true, where it blows from
	UPROPERTY(config) float WindKn = 10.f;
	UPROPERTY(config) float GustKn = 13.f;
	UPROPERTY(config) ESailSky Sky = ESailSky::Fair;
	UPROPERTY(config) float LocalHour = 10.f;
	UPROPERTY(config) int32 Month = 4;
	UPROPERTY(config) int32 Day = 18;
	UPROPERTY(config) float AirTempF = 74.f;
	UPROPERTY(config) float LakeLevelFt = 0.f;      // Ray Hubbard: relative to the 435.5 ft pool
	UPROPERTY(config) FName PresetId = TEXT("Lesson");
	UPROPERTY(config) FString RealDay;              // W5b: a baked real day (YYYY-MM-DD), Lake Ray Hubbard only; empty = none
};

USTRUCT(BlueprintType)
struct FSailSessionConfig
{
	GENERATED_BODY()

	UPROPERTY(config) int32 World = 0;             // 0 Lake Ray Hubbard, 1 Galveston Bay, 2 Gulf passage
	UPROPERTY(config) int32 LaunchSpot = 0;        // index into the world's launch spots
	UPROPERTY(config) int32 Boat = 0;              // Sailing::EBoatType
	UPROPERTY(config) FSailConditions Conditions;
	UPROPERTY(config) ESailMode Mode = ESailMode::Free;
	UPROPERTY(config) int32 DrillIndex = 0;
	UPROPERTY(config) bool bLearningMode = true;
	UPROPERTY(config) bool bEasy = true;
	UPROPERTY(config) bool bLearningTips = true;
	UPROPERTY(config) bool bFreeSail = false;      // the play mode (docs/free-sail): Free Sail, or Career
	UPROPERTY(config) int32 Traffic = 1;           // 0 off, 1 light, 2 busy
	UPROPERTY(config) FDateTime SavedAt;
};

/** A named set of conditions (the spec's six presets). */
struct FSailPreset
{
	FName Id;
	FString Name, Summary;
	FSailConditions Values;
	bool bGalvestonOnly = false;
};

/** The last session, kept in GameUserSettings.ini for Continue. */
UCLASS(config = GameUserSettings)
class SAILINGSIM_API USailSessionSave : public UObject
{
	GENERATED_BODY()
public:
	UPROPERTY(config) bool bHasLast = false;
	UPROPERTY(config) FSailSessionConfig Last;
	UPROPERTY(config) TArray<int32> DrillsPassed;   // drill indices passed at least once
	static USailSessionSave* Get() { return GetMutableDefault<USailSessionSave>(); }
	/** Writes it to the save file (SailSave.h) and the ini, unless the run ignores saved choices. */
	void Commit();
};

UCLASS()
class SAILINGSIM_API USailSessionSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()
public:
	/** The config being built in the menus. */
	FSailSessionConfig Pending;
	/** The menus closed with Pending in hand (docs/showroom-wiring/): they open on it again until a session starts. */
	bool bHasPending = false;
	/** The config the running session was started with (valid when bHasActive). */
	FSailSessionConfig Active;
	bool bHasActive = false;
	/** The player confirmed "Start sailing" (or the session needs no loading screen). */
	bool bStarted = false;
	/** Graphics G4: -SailingUIScript keys still to play (they carry over the reload a cast off makes). */
	TArray<FString> UIScript;
	bool bUIScriptRead = false;

	/** Reads the save file (SailSaveStore::LoadOnce) before anything reads the settings. */
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	/** Starts a session: saves it for Continue, applies the settings it overrides, and reloads the map. */
	void StartSession(const FSailSessionConfig& Config, UObject* WorldContext);
	/** Bench-fast: back to a new process's state (no session, nothing pending, no UI script); a bench list's next view. */
	void ResetForRun();
	/** Writes a session's choices into the persistent settings (world, spot, boat, difficulty, traffic...). */
	static void ApplyToSettings(const FSailSessionConfig& Config);
	/** Wide World Rendering PR 6: Passage mode's world and start for a chosen world (Galveston sails the Gulf world to
	 *  Freeport from the chosen spot; Marseille sails its own passage to Cassis from the Vieux-Port entrance). */
	static int32 PassageWorld(int32 World);
	static int32 PassageStartSpot(int32 World, int32 ChosenSpot);
	/** Whether a world has a passage to sail (Galveston's Gulf passage, Marseille's to Cassis). */
	static bool HasPassage(int32 World) { return World == 1 || World == 3; }
	/** A fresh config: the last world, the J/22, the lesson-day preset, free sail, learning, easy, the title's play mode. */
	static FSailSessionConfig MakeDefault();
	static const TArray<FSailPreset>& Presets();
	static void ApplyPreset(FSailConditions& Conditions, const FSailPreset& Preset);
	/** The weather preset (Sailing::EWeatherPreset) a sky choice runs on. */
	static int32 WeatherPresetFor(ESailSky Sky);
	static FString SkyName(ESailSky Sky);
	static FString ModeName(ESailMode Mode);
	/** Compass point for a direction in degrees (16 points). */
	static FString CompassPoint(float Degrees);

	static USailSessionSubsystem* Get(const UObject* WorldContext);
};
