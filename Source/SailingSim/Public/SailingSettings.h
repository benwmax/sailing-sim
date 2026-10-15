#pragma once

#include "CoreMinimal.h"
#include "UObject/Object.h"
#include "InputCoreTypes.h"
#include "SailingSettings.generated.h"

UENUM(BlueprintType)
enum class ESailingDifficulty : uint8
{
	/** Same physics, with help: auto-trim assist on the sheets, extra roll damping, a light helm, softer gusts. */
	Easy,
	/** The raw model: you trim everything, feel weather helm, and take the gusts as they come. */
	Realistic
};

/** Weather picker; same order as Sailing::EWeatherPreset. */
UENUM(BlueprintType)
enum class ESailingWeather : uint8
{
	CalmMorning,
	AfternoonBreeze,
	Overcast,
	Rain,
	Thunderstorm,
	RandomDay
};

/** Graphics quality tier, measured on the build Mac (see docs/phase-2). */
UENUM(BlueprintType)
enum class ESailingQuality : uint8
{
	Low,
	Medium,
	High,
	Ultra      // Graphics G1: for a desktop GPU (Bean's RTX 4090); the Mac's gates stay Medium 60 and High 45
};

/** Simple: tiller, mainsheet, jib sheet and hiking; the crew handles the rest. Full: every control. */
UENUM(BlueprintType)
enum class ESailingControlLayout : uint8
{
	Simple,
	Full
};

/**
 * Player-facing settings, saved per user in GameUserSettings.ini. The physics is identical in learning and
 * game mode; learning mode only adds help on screen.
 */
UCLASS(config = GameUserSettings)
class SAILINGSIM_API USailingSettings : public UObject
{
	GENERATED_BODY()

public:
	USailingSettings();

	/** Learning mode shows wind arrows, point-of-sail names and trim tips. Game mode hides them. */
	UPROPERTY(config, EditAnywhere, Category = "Sailing")
	bool bLearningMode = true;

	UPROPERTY(config, EditAnywhere, Category = "Sailing")
	ESailingDifficulty Difficulty = ESailingDifficulty::Easy;

	UPROPERTY(config, EditAnywhere, Category = "Sailing")
	bool bShowHud = true;

	/** Simple is the default; on Easy the layout is always Simple. */
	UPROPERTY(config, EditAnywhere, Category = "Sailing")
	ESailingControlLayout ControlLayout = ESailingControlLayout::Simple;

	/** The crew trims the sails whenever you leave the sheets alone for a few seconds. */
	UPROPERTY(config, EditAnywhere, Category = "Sailing")
	bool bTrimAssist = true;

	UPROPERTY(config, EditAnywhere, Category = "Weather")
	ESailingWeather WeatherPreset = ESailingWeather::AfternoonBreeze;

	/** Local solar time the session starts at (dawn to dusk; night sailing comes in a later phase). */
	UPROPERTY(config, EditAnywhere, Category = "Weather", meta = (ClampMin = "6.0", ClampMax = "20.0"))
	float StartHour = 15.f;

	/** Same seed, same weather: gusts, shifts, lightning and the random day all repeat. */
	UPROPERTY(config, EditAnywhere, Category = "Weather")
	int32 WeatherSeed = 2027;

	UPROPERTY(config, EditAnywhere, Category = "Graphics")
	ESailingQuality Quality = ESailingQuality::Medium;

	/** Where the boat starts on the lake (index into the lake's launch spots; 0 = the home club). */
	UPROPERTY(config, EditAnywhere, Category = "Sailing")
	int32 LaunchSpot = 0;

	/** Sailing area: 0 = Lake Ray Hubbard (Rush Creek Yacht Club), 1 = Galveston Bay (Clear Lake / Kemah). */
	UPROPERTY(config, EditAnywhere, Category = "Sailing")
	int32 World = 0;

	/** Other vessels on the water: 0 none, 1 light, 2 busy. */
	UPROPERTY(config, EditAnywhere, Category = "Sailing")
	int32 TrafficLevel = 1;

	/** The boat you sail (Sailing::EBoatType: 0 = J/22, the lesson boat). */
	UPROPERTY(config, EditAnywhere, Category = "Sailing")
	int32 BoatType = 0;

	/** Sail at the lake's last gauge reading instead of full pool (takes effect at the next start). */
	UPROPERTY(config, EditAnywhere, Category = "Sailing")
	bool bGaugeLakeLevel = false;

	UPROPERTY(config, EditAnywhere, Category = "Audio", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float Volume = 0.8f;

	// Graphics G4: the Settings screen's rows (ui-spec.md 5.10).
	/** Render resolution: 0 = the tier's own (and High's governor), otherwise a fixed percentage. */
	UPROPERTY(config, EditAnywhere, Category = "Graphics")
	int32 ResolutionScale = 0;

	/** Frame-rate cap (t.MaxFPS); 0 = uncapped. */
	UPROPERTY(config, EditAnywhere, Category = "Graphics")
	int32 FrameCap = 0;

	/** HUD scale around its anchors, percent (85..130). */
	UPROPERTY(config, EditAnywhere, Category = "Display")
	int32 HudScale = 100;

	/** Body, small and UI text, percent (100..150). */
	UPROPERTY(config, EditAnywhere, Category = "Accessibility")
	int32 TextScale = 100;

	/** Boat speed and wind: 0 knots, 1 mph, 2 km/h. */
	UPROPERTY(config, EditAnywhere, Category = "Gameplay")
	int32 SpeedUnits = 0;

	/** Depth: 0 feet, 1 metres, 2 fathoms. */
	UPROPERTY(config, EditAnywhere, Category = "Gameplay")
	int32 DepthUnits = 0;

	/** Headings in degrees true instead of magnetic. */
	UPROPERTY(config, EditAnywhere, Category = "Gameplay")
	bool bHeadingsTrue = false;

	/** Skip the "Start sailing" prompt when the world has loaded. */
	UPROPERTY(config, EditAnywhere, Category = "Gameplay")
	bool bAutoStart = false;

	/** Pause when the window loses focus. */
	UPROPERTY(config, EditAnywhere, Category = "Gameplay")
	bool bPauseOnFocusLoss = false;

	/** Speed (m/s) in the chosen unit, and the unit's label. */
	double SpeedIn(double MetersPerSecond) const { return MetersPerSecond * (SpeedUnits == 1 ? 2.236936 : (SpeedUnits == 2 ? 3.6 : 1.943844)); }
	const TCHAR* SpeedUnit() const { return SpeedUnits == 1 ? TEXT("mph") : (SpeedUnits == 2 ? TEXT("km/h") : TEXT("kn")); }
	double DepthIn(double Meters) const { return Meters / (DepthUnits == 1 ? 1.0 : (DepthUnits == 2 ? 1.8288 : 0.3048)); }
	const TCHAR* DepthUnit() const { return DepthUnits == 1 ? TEXT("m") : (DepthUnits == 2 ? TEXT("fm") : TEXT("ft")); }
	/** Applies the display rows that live outside the quality tiers (frame cap, focus pause). */
	void ApplyDisplay() const;
	/** A benchmark or capture run (-SailingBench): it measures the tiers as they are, not the player's display rows. */
	static bool IsMeasuring();
	/**
	 * Bench, capture, shot, demo, drill and automation runs: the player's saved choices (GameUserSettings.ini) are
	 * neither used nor written. Such a run takes the class defaults (the J/22 at Rush Creek, Lake Ray Hubbard) plus its
	 * own command line.
	 */
	static bool IgnoresSavedChoices();
	/** Puts every saved choice back to the class default for this run, once per process; nothing is saved. */
	static void UseRunDefaults();
	/** Sets every config property of the settings back to its class default (in memory only). */
	static void RestoreClassDefaults();
	/** -SailingBoat=<prefix>: the fleet boat whose name starts with it, ignoring case, spaces and slashes (J22 is the J/22); -1 if none. */
	static int32 MatchBoatName(const FString& Prefix);
	/** The player's fixed resolution percentage, or 0 (the tier's own; always 0 when measuring). */
	int32 FixedResolutionScale() const { return IsMeasuring() ? 0 : ResolutionScale; }

	/** Simple layout is in effect (always on Easy). */
	bool UseSimpleControls() const { return Difficulty == ESailingDifficulty::Easy || ControlLayout == ESailingControlLayout::Simple; }

	static USailingSettings* Get() { return GetMutableDefault<USailingSettings>(); }
	/** Writes the player's choices to GameUserSettings.ini (never in a run that ignores them). */
	void Save() { if (!IgnoresSavedChoices()) SaveConfig(); }

private:
	void SnapshotClassDefaults();
};

/** One key bound to one action. Scale -1 reverses an axis (for example A steers left, D right). */
USTRUCT()
struct FSailingKeyBinding
{
	GENERATED_BODY()

	UPROPERTY(config, EditAnywhere, Category = "Input")
	FName Action;

	UPROPERTY(config, EditAnywhere, Category = "Input")
	FKey Key;

	UPROPERTY(config, EditAnywhere, Category = "Input")
	float Scale = 1.f;
};

/**
 * Key bindings, read from Input.ini so they can be changed without code: add a
 * [/Script/SailingSim.SailingInputSettings] section with +Bindings=(Action="Tiller",Key=J,Scale=-1)
 * lines (in Config/DefaultInput.ini for everyone, or the user's Saved/Config Input.ini). If none are
 * configured, the defaults in the constructor are used.
 */
UCLASS(config = Input)
class SAILINGSIM_API USailingInputSettings : public UObject
{
	GENERATED_BODY()

public:
	USailingInputSettings();

	UPROPERTY(config, EditAnywhere, Category = "Input")
	TArray<FSailingKeyBinding> Bindings;

	/** Bindings in effect: the configured ones, or the defaults. */
	const TArray<FSailingKeyBinding>& GetBindings() const { return Bindings.Num() > 0 ? Bindings : Defaults; }
	const TArray<FSailingKeyBinding>& GetDefaults() const { return Defaults; }

private:
	TArray<FSailingKeyBinding> Defaults;
};
