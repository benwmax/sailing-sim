#include "FixedStepper.h"

namespace Sailing
{
	int32 FFixedStepper::Advance(double FrameDt)
	{
		Accumulator += FMath::Max(FrameDt, 0.0);
		int32 Steps = 0;
		// Small epsilon so 1/120 s of frame time is exactly one step despite float rounding.
		while (Accumulator + 1e-9 >= StepDt && Steps < MaxStepsPerFrame)
		{
			Accumulator -= StepDt;
			++Steps;
		}
		if (Steps == MaxStepsPerFrame && Accumulator >= StepDt)
		{
			Accumulator = 0.0;
		}
		Accumulator = FMath::Max(Accumulator, 0.0);
		return Steps;
	}
}
