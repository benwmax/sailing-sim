#pragma once

#include "CoreMinimal.h"

// docs/traffic-rig-rate/: how often an AI boat (or the ghost) rebuilds its rig lines, sail cloth and telltales. Each is a
// procedural mesh section, and every rebuild is an upload the render thread waits on: the three AI boats rebuilding theirs
// every frame cost about 9 fps on the PC's crew view (Nov 17 profile). Near the camera they rebuild every frame; farther
// off they rebuild on a time grid and hold their last shape (in the boat's frame, so they still heel, pitch and move with
// her) in between. A boat whose sails change sides, sets or drops a sail, or comes back on screen rebuilds at once.
// The player's boat is never paced.
namespace TrafficRigRate
{
	/** Seconds between rebuilds; 0 is every frame. */
	inline double IntervalSeconds(double DistanceM, bool bOnScreen)
	{
		if (!bOnScreen) return 1.0;               // off screen: kept roughly current for when it turns back into view
		if (DistanceM < 50.0) return 0.0;         // near: every frame
		if (DistanceM < 100.0) return 1.0 / 30.0; // 30 Hz
		if (DistanceM < 400.0) return 1.0 / 8.0;  // 8 Hz: a sail 100 m off is a few dozen pixels tall
		if (DistanceM < 1000.0) return 1.0 / 3.0; // 3 Hz
		return 4.0;                               // far: all but static (a trim change shows within 4 s; tacks force one)
	}

	/** A stagger in [0, 1) from the boat's id, so the boats' rebuilds fall on different frames. */
	inline double Phase(uint32 Id)
	{
		return FMath::Frac(double(Id) * 0.6180339887498949);
	}

	/** Is a rebuild due at Now (seconds), the last one at LastBuilt? On a grid of Interval offset by Phase of a step: due
	 *  once per step, whatever the frame rate. LastBuilt < 0 (never built) or Interval <= 0 is always due. */
	inline bool Due(double Interval, double Phase01, double LastBuilt, double Now)
	{
		if (Interval <= 0.0 || LastBuilt < 0.0) return true;
		const double Offset = Phase01 * Interval;
		return FMath::FloorToDouble((Now + Offset) / Interval) > FMath::FloorToDouble((LastBuilt + Offset) / Interval);
	}
}
