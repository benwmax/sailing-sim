#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"

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
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs);
	virtual bool SupportsKeyboardFocus() const override { return true; }
	virtual FReply OnKeyDown(const FGeometry& Geometry, const FKeyEvent& Event) override;
	virtual FReply OnMouseButtonDown(const FGeometry& Geometry, const FPointerEvent& Event) override;
	/** Readiness, 0..1, and the current stage's label. */
	float Progress(FString& Stage) const;
	bool IsReady() const;

private:
	TWeakObjectPtr<UWorld> World;
	FSimpleDelegate OnStart;
	int32 Tip = 0;
	TSharedPtr<struct FSlateBrush> Image;
	double ShownAt = 0.0;
	int32 InitialChunks = -1;
};
