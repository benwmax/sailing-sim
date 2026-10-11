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
