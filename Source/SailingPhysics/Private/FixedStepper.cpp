#include "FixedStepper.h"
#include <algorithm>

namespace Sailing
{
	int FFixedStepper::Advance(double FrameDt)
	{
		Accumulator += std::max(FrameDt, 0.0);
		int Steps = 0;
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
		Accumulator = std::max(Accumulator, 0.0);
		return Steps;
	}
}
