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
	High
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

	/** Simple layout is in effect (always on Easy). */
	bool UseSimpleControls() const { return Difficulty == ESailingDifficulty::Easy || ControlLayout == ESailingControlLayout::Simple; }

	static USailingSettings* Get() { return GetMutableDefault<USailingSettings>(); }
	void Save() { SaveConfig(); }
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

private:
	TArray<FSailingKeyBinding> Defaults;
};
