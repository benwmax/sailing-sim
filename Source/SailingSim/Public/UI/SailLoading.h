#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"
#include "SailSession.h"

/**
 * Graphics G4: the loading screen (ui-spec.md 5.7), shown from the map's load until the player confirms "Start sailing":
 * the world's image, the session's summary, a sailing tip, and progress through real readiness checks (the shore
 * streamed in, the cloud weather map painted, the boat and crew rigged, the shaders compiled, the traffic placed).
 */
class SAILINGSIM_API SSailLoading : public SCompoundWidget
{
public:
	SLATE_BEGIN_ARGS(SSailLoading) {}
		SLATE_ARGUMENT(TWeakObjectPtr<UWorld>, World)
		SLATE_EVENT(FSimpleDelegate, OnStart)
		/** The session to show instead of the world's (tests: SailingSim.UI.LoadingStill). */
		SLATE_ARGUMENT(TOptional<FSailSessionConfig>, Config)
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs);
	virtual bool SupportsKeyboardFocus() const override { return true; }
	virtual FReply OnKeyDown(const FGeometry& Geometry, const FKeyEvent& Event) override;
	virtual FReply OnMouseButtonDown(const FGeometry& Geometry, const FPointerEvent& Event) override;
	/** Readiness, 0..1, and the current stage's label. */
	float Progress(FString& Stage) const;
	bool IsReady() const;
	/** The loading still shown (null: the plain screen). */
	const UObject* ShownStill() const;
	/** The tip shown (0-based), and how many there are. */
	int32 ShownTip() const { return Tip; }
	static int32 NumTips();
	/** A tip's heading, and the tip with a heading (INDEX_NONE if none has it). */
	static const TCHAR* TipHeading(int32 Index);
	static int32 TipIndex(const TCHAR* Heading);
	/** #595: the first tip for a session: a lesson's own (Leaving a slip for leaving the dock, Docking for return and dock,
	 *  Points of sail for the triangle, Heaving to, Crew overboard), Points of sail for the first job, Thunderstorms when the
	 *  session has storms; otherwise INDEX_NONE: a random tip that isn't the thunderstorm one. */
	static int32 FirstTip(const struct FSailSessionConfig& Config);
	/** #595: the session has storms (its sky is Storms): only then the storm still and tip. */
	static bool IsStormy(const struct FSailSessionConfig& Config);

private:
	TWeakObjectPtr<UWorld> World;
	FSimpleDelegate OnStart;
	int32 Tip = 0;
	TSharedPtr<struct FSlateBrush> Image;
	double ShownAt = 0.0;
	int32 InitialChunks = -1;
};
