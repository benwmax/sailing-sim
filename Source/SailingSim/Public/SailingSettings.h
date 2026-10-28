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
	RandomDay,
	Mistral,    // prologue step 4 (the scene's gale)
	ClearMistral // Wide World Rendering PR 4: a dry, cloudless mistral day, 60 km of visibility
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

	/** Graphics G8 cinematic look (docs/graphics-8/cinematic): the grade, bloom and glitter of a photograph rather than
	 *  the metered neutral look. Photo mode always uses it; -SailingCinematic=0|1 overrides. Medium and above. */
	UPROPERTY(config, EditAnywhere, Category = "Graphics")
	bool bCinematicLook = false;

	// Bean's playtest (Oct 20): the Display and Graphics page. Each row is -1 (Auto: the Quality tier's own, so the tiers are
	// presets that fill them in) or an override; benches and captures ignore them all (IsMeasuring).
	/** Anti-aliasing: -1 Auto, 0 off, 2 TAA, 4 TSR, 5 SMAA (r.AntiAliasingMethod); with NVIDIA's DLSS plugin on an NVIDIA
	 *  GPU (DLSSAvailable) also 10 DLAA, 11 DLSS Quality, 12 Balanced, 13 Performance (their own render scale). */
	UPROPERTY(config, EditAnywhere, Category = "Graphics")
	int32 AntiAliasing = -1;
	/** Per-feature detail, -1 Auto or an ESailingQuality (0 Low .. 3 Ultra): the engine's scalability group, or ours. */
	UPROPERTY(config, EditAnywhere, Category = "Graphics")
	int32 ShadowQuality = -1;
	UPROPERTY(config, EditAnywhere, Category = "Graphics")
	int32 LightingQuality = -1;
	UPROPERTY(config, EditAnywhere, Category = "Graphics")
	int32 ReflectionQuality = -1;
	UPROPERTY(config, EditAnywhere, Category = "Graphics")
	int32 CloudQuality = -1;
	UPROPERTY(config, EditAnywhere, Category = "Graphics")
	int32 WaterQuality = -1;
	UPROPERTY(config, EditAnywhere, Category = "Graphics")
	int32 FoliageQuality = -1;
	UPROPERTY(config, EditAnywhere, Category = "Graphics")
	int32 ViewDistanceQuality = -1;
	/** Motion blur: -1 Auto (the tier's camera look), 0 off, 1 on. */
	UPROPERTY(config, EditAnywhere, Category = "Graphics")
	int32 MotionBlur = -1;
	/** Wait for the display's refresh (r.VSync). */
	UPROPERTY(config, EditAnywhere, Category = "Display")
	bool bVSync = false;
	/** The chase camera's horizontal field of view, degrees; 0 = the game's 90 (the cockpit view takes 10 less). */
	UPROPERTY(config, EditAnywhere, Category = "Display")
	int32 FieldOfView = 0;
	/** Brightness, percent (50..150): an exposure bias of log2(Brightness / 100) stops on the metered exposure. */
	UPROPERTY(config, EditAnywhere, Category = "Display")
	int32 Brightness = 100;

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

	/** The play mode (docs/free-sail), chosen on the title screen: Free Sail opens every world, spot, boat, condition and
	 *  mode and earns no career medals or unlocks (the logbook still counts); false is Career. Career 1's Open
	 *  everything switch became this. */
	UPROPERTY(config, EditAnywhere, Category = "Gameplay")
	bool bFreeSail = false;

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
	/** A Graphics row's override as it applies: -1 (the tier's) when measuring or when the row is Auto. */
	static int32 Override(int32 Row) { return IsMeasuring() ? -1 : Row; }
	/** The chase camera's field of view (degrees), and the exposure bias the Brightness row adds (stops). */
	float ChaseFov() const { return IsMeasuring() || FieldOfView <= 0 ? 90.f : float(FMath::Clamp(FieldOfView, 60, 120)); }
	float BrightnessBias() const { return IsMeasuring() ? 0.f : FMath::Log2(FMath::Clamp(float(Brightness), 50.f, 150.f) / 100.f); }
	/** Choosing a Quality tier makes it the preset again: every Graphics row back to Auto. */
	void ResetGraphicsRows();
	/** NVIDIA DLSS can run: the optional plugin is installed (its r.NGX.DLSS.Enable exists) and the GPU is NVIDIA's. */
	static bool DLSSAvailable();
	/** The DLSS mode in force (10..13), or -1: none chosen, measuring, or DLSS not available here (another GPU, the Mac). */
	int32 DLSSMode() const { const int32 A = Override(AntiAliasing); return A >= 10 && A <= 13 && DLSSAvailable() ? A : -1; }
	/** A DLSS mode's render scale, percent: DLAA native, Quality 67, Balanced 58, Performance 50. */
	static float DLSSScreenPercentage(int32 Mode) { return Mode == 10 ? 100.f : (Mode == 11 ? 66.7f : (Mode == 12 ? 58.f : 50.f)); }

	/**
	 * Easy mode's assists are on (Sailing::FEasyAssists, docs/easy-mode/README.md): -SailingEasy=0|1 decides; otherwise the
	 * Difficulty, except in measuring, capture and automation runs, which sail Realistic.
	 */
	bool IsEasy() const;
	/** -SailingEasy=0|1, or -1 when the command line doesn't say. */
	static int32 EasyArg();
	/** The run is in Free Sail mode: -SailingFreeSail=0|1 decides, otherwise bFreeSail (docs/free-sail). */
	bool IsFreeSail() const;
	/** -SailingFreeSail=0|1, or -1 when the command line doesn't say. */
	static int32 FreeSailArg();

	/** Simple layout is in effect (always on Easy). */
	bool UseSimpleControls() const { return Difficulty == ESailingDifficulty::Easy || ControlLayout == ESailingControlLayout::Simple; }

	static USailingSettings* Get() { return GetMutableDefault<USailingSettings>(); }
	/**
	 * Developer tools (the asset gallery, docs/gallery-core/): on in development builds; in Shipping only with this line
	 * in the user's GameUserSettings.ini (no settings page shows it):
	 *   [/Script/SailingSim.SailingSettings]
	 *   bDeveloperTools=True
	 */
	UPROPERTY(config)
	bool bDeveloperTools = !UE_BUILD_SHIPPING;
	static bool DeveloperTools() { return Get()->bDeveloperTools; }
	/** Writes the player's choices to the save file and GameUserSettings.ini (never in a run that ignores them). */
	void Save();

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

	virtual void PostInitProperties() override;
	virtual void PostReloadConfig(FProperty* PropertyThatWasLoaded) override;

private:
	TArray<FSailingKeyBinding> Defaults;
	/** A saved list from before a command existed (photo mode's free camera) gets that command's default keys. */
	void AddMissingActions();
};
