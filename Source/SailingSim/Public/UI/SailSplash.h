#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"

/**
 * The opening splash (docs/splash/): shown once at each launch while the first world loads, then handed to the
 * title. It carries the game's name, "Made with Unreal Engine" and, in a build that contains NVIDIA's DLSS plugin,
 * the DLSS attribution NVIDIA's RTX SDKs licence asks for on splash screens (supplement 7.1(b)). Any key, click or pad
 * button skips it. It fades in from black, holds, and fades out; a skip fades out quickly.
 */
namespace SailSplash
{
	constexpr double FadeInSeconds = 0.6;
	constexpr double HoldSeconds = 3.0;
	constexpr double FadeOutSeconds = 0.6;
	constexpr double SkipFadeSeconds = 0.25;
	/** Total length of an unskipped splash. */
	constexpr double TotalSeconds = FadeInSeconds + HoldSeconds + FadeOutSeconds;

	/** The content's opacity (0..1) at T seconds. SkippedAt is when a skip came (negative: none): the opacity it had then
	 *  fades to zero over SkipFadeSeconds. */
	SAILINGSIM_API float ContentAlpha(double T, double SkippedAt = -1.0);
	/** The black backdrop's opacity: solid until the exit starts, then it fades with the content. */
	SAILINGSIM_API float BackdropAlpha(double T, double SkippedAt = -1.0);
	SAILINGSIM_API bool IsFinished(double T, double SkippedAt = -1.0);

	/** True when this build contains NVIDIA's DLSS plugin (its console variable exists), on any GPU: the licence asks for
	 *  the attribution wherever the SDK ships in the application. */
	SAILINGSIM_API bool NvidiaPluginPresent();
	/** The attribution's words. NVIDIA's mark replaces the plain-text box only once NVIDIA has approved a sample. */
	SAILINGSIM_API FString NvidiaAttribution();
	/** Whether this launch shows the splash: the first time in the process, not in a measuring or scripted run. */
	SAILINGSIM_API bool Wanted();
	/** True for the still hook, -SailingFrontEnd=Splash: Wanted() allows it and the splash is held at full opacity. */
	SAILINGSIM_API bool IsStillRun();
	/** Marks this launch's splash as shown (the map reloads on cast-off and must not show it again). */
	SAILINGSIM_API void MarkShown();
}

class SAILINGSIM_API SSailSplash : public SCompoundWidget
{
public:
	SLATE_BEGIN_ARGS(SSailSplash) {}
		/** Show the NVIDIA DLSS block (a test can force it either way). */
		SLATE_ARGUMENT(bool, ShowNvidia)
		/** Stills (-SailingFrontEnd=Splash): stays at full opacity, ignores input, never finishes. */
		SLATE_ARGUMENT(bool, Hold)
		/** Called once, when the splash has faded out. */
		SLATE_EVENT(FSimpleDelegate, OnDone)
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs);
	virtual ~SSailSplash() override;
	virtual void Tick(const FGeometry& AllottedGeometry, const double InCurrentTime, const float InDeltaTime) override;

	/** Skips: the content fades out quickly. Ignored once skipped. */
	void Skip();
	/** Seconds the splash has been up (hitches, as in a map load, count at most 0.1 s a frame). */
	double Elapsed() const { return T; }
	bool IsSkipped() const { return SkippedAt >= 0.0; }
	bool IsDone() const { return bDone; }
	/** Tests: advances the clock as Tick does. */
	void Advance(float DeltaSeconds);

private:
	TSharedPtr<class SWidget> Backdrop, Content;
	TSharedPtr<class FSplashSkipper> Skipper;
	FSimpleDelegate OnDone;
	double T = 0.0;
	double SkippedAt = -1.0;
	bool bDone = false;
	bool bHold = false;
};
