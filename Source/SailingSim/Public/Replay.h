#pragma once

#include "CoreMinimal.h"
#include "BoatModel.h"

/** One sail strip as drawn: its chord angle, camber, twist and whether the flow is attached, luffing or stalled. */
struct FReplayStrip
{
	float Angle = 0.f, Camber = 0.f, Twist = 0.f;
	uint8 Flow = 0;
};

/** The boat at one moment of a run: her full rigid-body state and what the drawing needs of her sails. */
struct FReplayFrame
{
	double Time = 0.0;                 // s since the run began
	Sailing::FBoatState State;
	float BoatSpeed = 0.f, ApparentWindAngle = 0.f, ApparentWindSpeed = 0.f, Heading = 0.f, Heel = 0.f;
	uint8 NumStrips[3] = { 0, 0, 0 };  // main, jib, spinnaker
	FReplayStrip Strips[3][Sailing::kMaxSailStrips];
};

/**
 * A run (from a reset, a drill or a race start) recorded ten times a second, for the debrief: watch it again with the
 * world paused, or sail against it as a ghost. Kept to the last forty minutes.
 */
struct SAILINGSIM_API FReplay
{
	static constexpr double Interval = 0.1;
	static constexpr int32 MaxFrames = 24000;

	int32 BoatType = 0;
	FString Label;
	double StartTime = 0.0;   // physics time the run began
	TArray<FReplayFrame> Frames;

	void Begin(int32 InBoatType, const FString& InLabel, double InStartTime);
	void Record(const Sailing::FBoatModel& Boat);
	double Duration() const { return Frames.Num() ? Frames.Last().Time : 0.0; }
	bool IsEmpty() const { return Frames.Num() < 2; }
	/** The boat at a time into the run (positions interpolated, the rest from the nearer frame). */
	bool Sample(double T, FReplayFrame& Out) const;
	/** Puts a recorded moment into a model for drawing. */
	static void Apply(const FReplayFrame& Frame, Sailing::FBoatModel& Boat);
};
