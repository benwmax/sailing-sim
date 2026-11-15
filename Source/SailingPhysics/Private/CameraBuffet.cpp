#include "CameraBuffet.h"
#include "SailingMath.h"

#include <algorithm>
#include <cmath>

namespace Sailing
{
	void FCameraBuffet::Reset()
	{
		*this = FCameraBuffet();
	}

	void FCameraBuffet::Kick(double Strength)
	{
		const double S = std::clamp(Strength, 0.0, 1.0);
		if (S <= 0.0) return;
		Judder = std::min(Judder + S, 1.5);
		Lurch = std::min(Lurch + 0.8 * S, 1.2);
		JudderPhase = 0.0;
		KickSide = -KickSide;
	}

	void FCameraBuffet::Step(const FCameraBuffetInput& In)
	{
		const double Dt = std::clamp(In.Dt, 0.0, 0.1);
		// The events, each on its rising edge.
		const bool bSlam = In.SlamClosingMs > SlamThresholdMs;
		if (bSlam && !bSlamWasOn) Kick((In.SlamClosingMs - SlamThresholdMs) / 1.3);
		bSlamWasOn = bSlam;
		const bool bGreen = In.GreenWaterM > GreenWaterThresholdM;
		if (bGreen && !bGreenWasOn) Kick(0.7 * std::min(In.GreenWaterM / 0.15, 1.0));
		bGreenWasOn = bGreen;
		// The envelopes: the judder gone in about a third of a second (e-fold 0.12 s), the lurch in about a second (0.4 s).
		Judder *= std::exp(-Dt / 0.12);
		Lurch *= std::exp(-Dt / 0.4);
		JudderPhase += Dt * 2.0 * kPi * 7.0;
		LurchPhase += Dt * 2.0 * kPi * 1.6;
		const double J = Judder * std::sin(JudderPhase), L = Lurch * std::sin(LurchPhase + 0.7) * KickSide;
		// The wind's tremble past about 22 kn apparent, growing to its full (small) size by about 40 kn.
		const double W = std::clamp((In.ApparentWindMs - TrembleFromMs) / 10.0, 0.0, 1.0);
		const double T = In.Time;
		const double Tr = W * (0.5 * std::sin(T * 2.0 * kPi * 9.3) + 0.3 * std::sin(T * 2.0 * kPi * 13.1 + 1.7) + 0.2 * std::sin(T * 2.0 * kPi * 5.2 + 0.4));
		const double Tr2 = W * (0.5 * std::sin(T * 2.0 * kPi * 8.1 + 2.3) + 0.5 * std::sin(T * 2.0 * kPi * 11.7 + 0.9));
		// Sizes at the hardest kick: 3 cm up and down, a degree and a half of pitch, a degree of roll; the tremble a tenth
		// of a degree and a few millimetres.
		OffsetX = -0.01 * J;
		OffsetY = 0.015 * L + 0.002 * Tr2;
		OffsetZ = 0.03 * J + 0.01 * L + 0.003 * Tr;
		PitchDeg = 1.5 * J + 0.12 * Tr;
		RollDeg = 1.0 * L + 0.08 * Tr2;
		YawDeg = 0.3 * L + 0.05 * Tr;
	}
}
